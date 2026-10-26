"""Tests of `inventory.py repeats`: what several chosen doc files repeat, verbatim or around the
same code, on a small repo built here."""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INVENTORY = os.path.join(HERE, "..", "..", "skills", "fix-my-context", "scripts", "inventory.py")

DOCS = {
    "CLAUDE.md": """
        # Rules

        Query prod only inside a read-only transaction:

        ```
        supabase db query --linked "begin read only; <your select>; commit;"
        ```

        The paywall reads `paywall_cutoff` from the billing config.
        Run `pnpm test -f 200` before a push.
        """,
    "docs/qa.md": """
        # QA

        To look at production data, wrap the select so nothing can be written:
        `supabase db query --linked "begin read only; select … ; commit;"`.

        Then `alpha beta gamma`, and later `beta gamma delta`.
        """,
    "docs/ops/runbook.md": """
        # Launch day

        - [ ] `supabase db query --linked "begin read only; select paywall_cutoff from billing_config; commit;"`
          returns the merge instant.
        - [ ] See `docs/qa.md` for the QA pass, and run `pnpm build -f 200`.
        - [ ] `alpha beta gamma delta`
        """,
    "docs/notes.md": """
        # Notes

        `supabase db query --linked "begin read only; select 1; commit;"`
        """,
}


def build(root):
    repo = os.path.join(root, "app")
    for rel, text in DOCS.items():
        path = os.path.join(repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(text).lstrip("\n"))
    os.symlink("CLAUDE.md", os.path.join(repo, "AGENTS.md"))
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "docs"]):
        subprocess.run(["git", "-C", repo, *args], check=True, env=env, capture_output=True)
    return repo


def repeats(repo, home, *paths):
    out = subprocess.run([sys.executable, "-I", INVENTORY, "repeats", repo, *paths],
                         env=dict(os.environ, HOME=home), capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


class RepeatsOnChosenFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.repo = build(cls.tmp.name)
        cls.home = os.path.join(cls.tmp.name, "home")
        os.makedirs(cls.home)
        cls.out = repeats(cls.repo, cls.home, "AGENTS.md", "CLAUDE.md", "docs/qa.md", "docs/ops/runbook.md")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def group(self, *files):
        found = [g for g in self.out["shared_code"] if g["files"] == sorted(files)]
        self.assertEqual(len(found), 1, self.out["shared_code"])
        return found[0]

    def test_a_command_repeated_in_other_words_comes_out_with_its_files_and_lines(self):
        group = self.group("CLAUDE.md", "docs/ops/runbook.md", "docs/qa.md")
        lines = {(o["path"], o["line"]) for t in group["terms"] for o in t["occurrences"]}
        self.assertEqual(lines, {("CLAUDE.md", 6), ("docs/qa.md", 4), ("docs/ops/runbook.md", 3)})
        self.assertIn("supabase db query --linked begin read only", [t["term"] for t in group["terms"]])

    def test_a_single_identifier_shared_by_two_files_is_a_candidate(self):
        group = self.group("CLAUDE.md", "docs/ops/runbook.md")
        self.assertIn({"term": "paywall_cutoff", "occurrences": [
            {"path": "CLAUDE.md", "line": 9}, {"path": "docs/ops/runbook.md", "line": 3}]}, group["terms"])

    def test_plain_words_numbers_short_flags_and_doc_paths_are_not_terms(self):
        terms = {t["term"] for g in self.out["shared_code"] for t in g["terms"]}
        self.assertFalse({"pnpm", "-f", "200", "docs/qa.md", "commit", "select"} & terms)
        self.assertIn("--linked", terms)

    def test_a_symlink_to_a_chosen_file_is_counted_once(self):
        self.assertEqual(self.out["files"], ["CLAUDE.md", "docs/ops/runbook.md", "docs/qa.md"])
        self.assertEqual(self.out["same_file"], [{"path": "AGENTS.md", "same_as": "CLAUDE.md"}])

    def test_a_run_is_reported_only_where_it_is_written_whole(self):
        # docs/qa.md holds the two halves of runbook.md's longer command on separate lines.
        terms = {t["term"]: {o["path"] for o in t["occurrences"]}
                 for g in self.out["shared_code"] for t in g["terms"]}
        self.assertNotIn("alpha beta gamma delta", terms)
        self.assertEqual(terms["alpha beta gamma"], {"docs/ops/runbook.md", "docs/qa.md"})
        self.assertEqual(terms["beta gamma delta"], {"docs/ops/runbook.md", "docs/qa.md"})

    def test_a_path_outside_the_repo_or_not_a_doc_is_refused(self):
        for path in ("../app/CLAUDE.md", os.path.join(self.repo, "CLAUDE.md"), "docs/missing.md"):
            run = subprocess.run([sys.executable, "-I", INVENTORY, "repeats", self.repo, "CLAUDE.md", path],
                                 env=dict(os.environ, HOME=self.home), capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0, path)
            self.assertIn(path, run.stderr)

    def test_a_file_not_chosen_is_left_out(self):
        occurrences = [o["path"] for g in self.out["shared_code"] for t in g["terms"] for o in t["occurrences"]]
        occurrences += [o["path"] for d in self.out["duplicates"] for o in d["occurrences"]]
        self.assertNotIn("docs/notes.md", occurrences)


if __name__ == "__main__":
    unittest.main()
