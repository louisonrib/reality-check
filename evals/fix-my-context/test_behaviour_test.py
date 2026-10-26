"""Tests of skills/fix-my-context/scripts/behaviour_test.py, through its command line, with a stub `claude`."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fixture_repo  # noqa: E402

SCRIPT = os.path.join(HERE, "..", "..", "skills", "fix-my-context", "scripts", "behaviour_test.py")
FAKE = os.path.join(HERE, "fake_claude.py")


def git(repo, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", "-C", repo, *args], check=True, env=env)


class BehaviourTestWithStub(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.home = os.path.join(cls.tmp.name, "home")
        os.makedirs(os.path.join(cls.home, ".claude"))
        with open(os.path.join(cls.home, ".claude", "CLAUDE.md"), "w") as f:
            f.write("# Global\n")
        # The user's own allow rules would let a run execute these: the runs must deny them.
        with open(os.path.join(cls.home, ".claude", "settings.json"), "w") as f:
            json.dump({"permissions": {"allow": ["Bash(mkdir:*)", "Read", "mcp__mail__send"]}}, f)
        cls.home = os.path.realpath(cls.home)
        cls.repo = fixture_repo.build(os.path.join(cls.tmp.name, "app"))
        # `git archive` would leave docs/ out of a copy of this repo.
        with open(os.path.join(cls.repo, ".gitattributes"), "w") as f:
            f.write("docs export-ignore\n")
        git(cls.repo, "add", ".gitattributes")
        git(cls.repo, "commit", "-q", "-m", "attributes")
        cls.patch = os.path.join(cls.tmp.name, "change.patch")
        # The change under test: CLAUDE.md gets a new first line.
        with open(cls.patch, "w") as f:
            f.write("--- a/CLAUDE.md\n+++ b/CLAUDE.md\n@@ -1 +1,2 @@\n+# Changed\n # CLAUDE.md\n")
        cls.prompt = os.path.join(cls.tmp.name, "prompt.txt")
        with open(cls.prompt, "w") as f:
            f.write("What does CLAUDE.md say first?\n")
        # A user whose commits are signed: the copies' snapshot commits must not try to sign.
        cls.gitconfig = os.path.join(cls.tmp.name, "gitconfig")
        with open(cls.gitconfig, "w") as f:
            f.write("[commit]\n\tgpgsign = true\n[gpg]\n\tprogram = false\n")
        cls.log = os.path.join(cls.tmp.name, "argv.jsonl")
        proc = cls.run_script("--patch", cls.patch, "--runs", "2")
        if proc.returncode:
            raise AssertionError(proc.stderr)
        cls.out = json.loads(proc.stdout)
        with open(cls.log) as f:
            cls.calls = [json.loads(line) for line in f]

    @classmethod
    def run_script(cls, *args, **env):
        env = {**os.environ, "HOME": cls.home, "FAKE_CLAUDE_LOG": cls.log, "GIT_CONFIG_GLOBAL": cls.gitconfig, **env}
        return subprocess.run([sys.executable, "-I", SCRIPT, cls.repo, "--base", "HEAD", "--prompt-file",
                               cls.prompt, "--claude-bin", FAKE, *args], env=env, capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def runs(self, side):
        return [r for r in self.out["runs"] if r["side"] == side]

    def test_runs_alternate_between_the_two_copies(self):
        self.assertEqual([(r["side"], r["run"]) for r in self.out["runs"]],
                         [("with", 1), ("without", 1), ("with", 2), ("without", 2)])

    def test_only_the_copy_with_the_change_carries_it(self):
        self.assertEqual({r["answer"] for r in self.runs("with")}, {"First line: # Changed"})
        self.assertEqual({r["answer"] for r in self.runs("without")}, {"First line: # CLAUDE.md"})

    def test_each_run_reports_the_instruction_files_it_loaded(self):
        for r in self.out["runs"]:
            self.assertEqual(r["instructions_loaded"], [{"path": "~/.claude/CLAUDE.md", "type": "User"},
                                                        {"path": "CLAUDE.md", "type": "Project"}])

    def test_tool_calls_are_reported_with_the_denied_ones_marked(self):
        r = self.out["runs"][0]
        self.assertEqual([(c["name"], c["denied"]) for c in r["tool_calls"]], [("Read", False), ("Bash", True)])
        self.assertEqual(r["tool_calls"][1]["input"], {"command": "rm -rf build"})

    def test_runs_carry_no_cost_or_duration(self):
        self.assertFalse({"cost_usd", "duration_ms", "num_turns"} & set(self.out["runs"][0]))
        self.assertEqual(self.out["totals"], {"runs": 4})

    def test_no_spending_cap_is_passed(self):
        self.assertNotIn("--max-budget-usd", self.calls[0]["argv"])

    def test_the_agent_runs_headless_with_read_only_tools_allowed(self):
        argv = self.calls[0]["argv"]
        self.assertIn("-p", argv)
        self.assertEqual(argv[argv.index("--allowedTools") + 1], "Read,Grep,Glob")
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "dontAsk")

    def test_the_users_own_allow_rules_are_denied_and_hooks_are_off(self):
        argv = self.calls[0]["argv"]
        settings = json.loads(argv[argv.index("--settings") + 1])
        self.assertEqual(settings["permissions"]["deny"], ["Bash(mkdir:*)", "mcp__mail__send"])
        self.assertIs(settings["disableAllHooks"], True)
        self.assertEqual(self.out["denied_allow_rules"], ["Bash(mkdir:*)", "mcp__mail__send"])

    def test_copies_live_outside_any_tree_with_instruction_files_and_are_removed(self):
        cwds = {c["cwd"] for c in self.calls}
        self.assertEqual(len(cwds), 2)
        for cwd in cwds:
            self.assertEqual(os.path.basename(cwd), "app")  # the folder name does not say which copy
            self.assertFalse(os.path.exists(cwd))

    def test_copies_hold_every_tracked_file_whatever_the_export_attributes(self):
        for call in self.calls:
            self.assertLessEqual({"docs", "CLAUDE.md", ".gitattributes", ".git"}, set(call["files"]))

    def test_a_ref_can_stand_for_the_change(self):
        git(self.repo, "checkout", "-q", "-b", "change")
        with open(os.path.join(self.repo, "CLAUDE.md")) as f:
            text = f.read()
        with open(os.path.join(self.repo, "CLAUDE.md"), "w") as f:
            f.write("# Changed\n" + text)
        git(self.repo, "commit", "-q", "-am", "change")
        git(self.repo, "checkout", "-q", "main")
        proc = self.run_script("--with-ref", "change", FAKE_CLAUDE_LOG=os.devnull)
        out = json.loads(proc.stdout)
        self.assertEqual([r["answer"] for r in out["runs"]], ["First line: # Changed", "First line: # CLAUDE.md"])

    def test_each_sessions_raw_stream_is_kept_after_the_copies_go(self):
        self.assertTrue(os.path.isdir(self.out["raw_dir"]))
        self.assertFalse(self.out["raw_dir"].startswith(self.repo))
        for r in self.out["runs"]:
            self.assertEqual(os.path.dirname(r["raw"]), self.out["raw_dir"])
            with open(r["raw"]) as f:
                events = [json.loads(line) for line in f]
            self.assertEqual(events[-1]["type"], "result")
            self.assertEqual(events[-1]["result"], r["answer"])

    def test_the_raw_streams_go_where_asked(self):
        raw_dir = os.path.join(self.tmp.name, "raw")
        proc = self.run_script("--patch", self.patch, "--raw-dir", raw_dir, FAKE_CLAUDE_LOG=os.devnull)
        out = json.loads(proc.stdout)
        self.assertEqual(out["raw_dir"], os.path.realpath(raw_dir))
        self.assertEqual(sorted(os.listdir(raw_dir)), ["with-1.jsonl", "without-1.jsonl"])

    def test_it_refuses_raw_streams_inside_the_audited_repo(self):
        proc = self.run_script("--patch", self.patch, "--raw-dir", os.path.join(self.repo, "raw"),
                               FAKE_CLAUDE_LOG=os.devnull)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("raw", proc.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.repo, "raw")))

    def test_events_that_are_not_tool_blocks_are_stepped_over(self):
        proc = self.run_script("--patch", self.patch, FAKE_CLAUDE_LOG=os.devnull, FAKE_CLAUDE_ODD_EVENTS="1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        [with_run, _] = json.loads(proc.stdout)["runs"]
        self.assertEqual([c["name"] for c in with_run["tool_calls"]], ["Read", "Bash"])
        self.assertEqual(with_run["answer"], "First line: # Changed")

    def test_it_refuses_a_temporary_folder_below_an_instruction_file(self):
        parent = os.path.join(self.tmp.name, "under")
        os.makedirs(os.path.join(parent, "tmp"))
        with open(os.path.join(parent, "CLAUDE.md"), "w") as f:
            f.write("# Would load into both runs\n")
        proc = self.run_script("--patch", self.patch, TMPDIR=os.path.join(parent, "tmp"))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("CLAUDE.md", proc.stderr)
        self.assertEqual(os.listdir(os.path.join(parent, "tmp")), [])

    def test_the_audited_repo_is_left_untouched(self):
        status = subprocess.run(["git", "-C", self.repo, "status", "--porcelain"], capture_output=True,
                                text=True, check=True).stdout
        self.assertEqual(status, "?? notes-draft.md\n")


if __name__ == "__main__":
    unittest.main()
