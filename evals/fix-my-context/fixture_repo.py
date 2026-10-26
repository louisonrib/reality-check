"""Build the fixture repo the script tests and the evals share.

    python3 evals/fix-my-context/fixture_repo.py <dest> [--home <fake-home>]

<dest> becomes a git repo with planted defects whose answers are known (see PLANTED).
With --home, a fake home directory is also populated with what the inventory reads outside
the repo: installed skills and plugins, Claude Code transcripts for <dest>, its auto-memory,
a Cursor conversation and the user's global CLAUDE.md. The evals run against the real home
and leave --home out.
"""
import argparse
import json
import os
import re
import subprocess
import textwrap

# The defects, as the plan's validation item 1 lists them: the expected findings the evals check.
PLANTED = {
    "tool_created_file": "PROMPTS.md",  # its creating commit names the tool: docforge
    "rule_files_verbatim": ["CLAUDE.md", "docs/runbook.md"],
    "rule_file_reworded": "docs/ARCHITECTURE.md",
    "dead_backtick_path": ("docs/ARCHITECTURE.md", "src/legacy/importer.py"),
    "grow_instruction": "CLAUDE.md",
    "growing_doc": "docs/ARCHITECTURE.md",
    "restating_claude_md": "CLAUDE.md",
    "orphan": "docs/notes/old-ideas.md",
}

RULE = ("Never run a schema migration against the production database unless a fresh backup "
        "has been taken and checked by restoring it on staging first.")
RULE_REWORDED = ("Production migrations need a verified backup beforehand: restore it on staging "
                 "to prove it works, then migrate.")
USER_RULE = ("Always write commit messages in the imperative mood and keep the subject line "
             "under seventy characters so that the log stays readable.")


def slug(path):
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(text).lstrip("\n"))


def _git(repo, *args, date=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="Fixture Author", GIT_AUTHOR_EMAIL="author@example.com",
               GIT_COMMITTER_NAME="Fixture Author", GIT_COMMITTER_EMAIL="author@example.com",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    subprocess.run(["git", "-C", repo, *args], check=True, env=env, capture_output=True)


def _commit(repo, date, *message):
    _git(repo, "add", "-A", date=date)
    args = ["commit", "-q"]
    for m in message:
        args += ["-m", m]
    _git(repo, *args, date=date)


ARCH_GROWTH = [
    ("2026-07-10T10:00:00+00:00", "Update architecture doc after the export feature", """
        ## Export

        `export_rows()` in `src/app.py` calls `fetch_all()` then writes CSV with `EXPORT_BATCH = 500`.
        The constant `EXPORT_BATCH` is 500 and `EXPORT_TIMEOUT` is 30 seconds.
        """),
    ("2026-07-20T10:00:00+00:00", "Update architecture doc after the import rewrite", """
        ## Import

        The legacy importer was removed in #12. `import_rows()` now validates each row with
        `validate_row()` and retries three times (`IMPORT_RETRIES = 3`), measured on #14.
        """),
    ("2026-08-01T10:00:00+00:00", "Update architecture doc after the auth feature", """
        ## Auth

        `login()` in `src/app.py` checks `SESSION_TTL = 3600` and calls `db.get_user()`.
        Since #21 the session cookie is `sid`. Since 2026-08-01 tokens expire after one hour.
        """),
]


def build_repo(dest):
    os.makedirs(dest, exist_ok=True)
    dest = os.path.realpath(dest)
    _git(dest, "init", "-q", "-b", "main")

    _write(dest, "README.md", """
        # Fixture app

        A small app. See [the architecture](docs/ARCHITECTURE.md), [contributing](CONTRIBUTING.md)
        and [the terms](VOCAB.md). The entry point is `app.py`.
        """)
    _write(dest, "VOCAB.md", """
        # Vocabulary

        - **Batch**: rows exported together.
        """)
    _write(dest, "CONTRIBUTING.md", """
        # Contributing

        Open a pull request against `main`.
        """)
    _write(dest, "CLAUDE.md", f"""
        # CLAUDE.md

        @docs/runbook.md

        ## Dependencies

        - flask 3.1
        - sqlalchemy 2.0
        - pytest 8.3

        ## Layout

        - `src/app.py`: the web app
        - `src/db.py`: the database layer
        - `docs/`: documentation

        ## Rules

        {RULE}

        {USER_RULE}

        After each feature, update `docs/ARCHITECTURE.md` so it matches what shipped.
        """)
    _write(dest, "AGENTS.md", """
        # AGENTS.md

        Run `pytest` before you push.
        """)
    _write(dest, "docs/runbook.md", f"""
        # Runbook

        ## Migrations

        {RULE}
        """)
    _write(dest, "docs/ARCHITECTURE.md", f"""
        # Architecture

        The importer lives in `src/legacy/importer.py`.

        {RULE_REWORDED}
        """)
    _write(dest, ".claude/rules/docs-writing.md", """
        ---
        paths:
          - "docs/**/*.md"
        ---
        Keep docs short.
        """)
    _write(dest, "src/app.py", "def export_rows():\n    pass\n")
    _write(dest, "src/db.py", "def get_user():\n    pass\n")
    _write(dest, "src/legacy/importer.py", "def run():\n    pass\n")
    _write(dest, "pyproject.toml", '[project]\nname = "fixture"\ndependencies = ["flask", "sqlalchemy"]\n')
    _write(dest, "node_modules/leftpad/README.md", "# leftpad\n")
    _commit(dest, "2026-07-01T10:00:00+00:00", "Initial project")

    _write(dest, "PROMPTS.md", """
        # Prompts

        Prompt library generated for this project.

        - summarise: Summarise the diff.
        """)
    _commit(dest, "2026-07-05T10:00:00+00:00", "docforge init: generate PROMPTS.md",
            "Generated by docforge 0.4 (`docforge init`).")

    os.remove(os.path.join(dest, "src/legacy/importer.py"))
    for date, subject, section in ARCH_GROWTH:
        with open(os.path.join(dest, "docs/ARCHITECTURE.md"), "a", encoding="utf-8") as f:
            f.write("\n" + textwrap.dedent(section).lstrip("\n"))
        _commit(dest, date, subject)

    _write(dest, "docs/notes/old-ideas.md", """
        # Old ideas

        Maybe a dark mode one day.
        """)
    _commit(dest, "2026-08-05T10:00:00+00:00", "Add notes")

    _write(dest, "GLOSSARY.md", """
        # Glossary

        - **Row**: one line of an import file.
        """)
    _commit(dest, "2026-09-01T12:00:00+00:00", "Add glossary")

    # A rename: an installed skill still names the old file.
    _git(dest, "mv", "VOCAB.md", "TERMS.md")
    readme = os.path.join(dest, "README.md")
    with open(readme, encoding="utf-8") as f:
        text = f.read().replace("(VOCAB.md)", "(TERMS.md)")
    with open(readme, "w", encoding="utf-8") as f:
        f.write(text)
    _commit(dest, "2026-09-05T10:00:00+00:00", "Rename VOCAB.md to TERMS.md")

    _write(dest, "notes-draft.md", "# Draft\n")  # untracked on purpose
    return dest


def _skill(home, rel, text):
    _write(home, rel, text)


def _jsonl(path, entries):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _instructions(sid, cwd, ts, files):
    return {"type": "attachment", "sessionId": sid, "cwd": cwd, "timestamp": ts,
            "attachment": {"type": "instructions",
                           "files": [{"path": p, "type": t, "content": ""} for p, t in files]}}


def _tool_use(sid, cwd, ts, name, inp):
    return {"type": "assistant", "sessionId": sid, "cwd": cwd, "timestamp": ts,
            "message": {"role": "assistant",
                        "content": [{"type": "tool_use", "id": "t", "name": name, "input": inp}]}}


def _user(sid, cwd, ts, text):
    return {"type": "user", "sessionId": sid, "cwd": cwd, "timestamp": ts,
            "message": {"role": "user", "content": text}}


def build_home(home, repo):
    home = os.path.realpath(home)
    claude = os.path.join(home, ".claude")
    _write(home, ".claude/settings.json", '{"cleanupPeriodDays": 90}\n')
    _write(home, ".claude/CLAUDE.md", f"""
        # Global

        {USER_RULE}
        """)

    # A user skill that reads the glossary, and one that bundles its own README.md.
    _skill(home, ".claude/skills/glossary-keeper/SKILL.md", """
        ---
        name: glossary-keeper
        description: Keep the glossary.
        ---
        Read `GLOSSARY.md` at the repo root before naming anything.
        """)
    _skill(home, ".claude/skills/vocab-reader/SKILL.md", """
        ---
        name: vocab-reader
        description: Reads the vocabulary under its old name.
        ---
        Load VOCAB.md first.
        """)
    _skill(home, ".claude/skills/bundler/SKILL.md", """
        ---
        name: bundler
        description: Uses its own readme.
        ---
        See README.md in this skill for details.
        """)
    _skill(home, ".claude/skills/bundler/README.md", "# bundler\n")
    # A skill that names a common folder for its own purpose, as code-review does.
    _skill(home, ".claude/skills/spec-checker/SKILL.md", """
        ---
        name: spec-checker
        description: Checks a change against its spec.
        ---
        A spec file under `docs/` describes what the change should do.
        """)
    # A dead symlink inside an installed skill: the scan must step over it.
    os.symlink(os.path.join(home, "gone.md"), os.path.join(home, ".claude/skills/bundler/notes.md"))

    # Plugins: one active for every project, one scoped to another project.
    plugins = {"version": 2, "plugins": {
        "opskit@market": [{"scope": "user",
                           "installPath": os.path.join(claude, "plugins/cache/market/opskit/1.0.0")}],
        "elsewhere@market": [{"scope": "local", "projectPath": "/somewhere/else",
                              "installPath": os.path.join(claude, "plugins/cache/market/elsewhere/1.0.0")}],
    }}
    _write(home, ".claude/plugins/installed_plugins.json", json.dumps(plugins))
    _skill(home, ".claude/plugins/cache/market/opskit/1.0.0/commands/migrate.md", """
        Before migrating, follow docs/runbook.md step by step.
        """)
    _skill(home, ".claude/plugins/cache/market/elsewhere/1.0.0/skills/notes/SKILL.md", """
        ---
        name: notes
        description: Elsewhere only.
        ---
        Read `docs/notes/old-ideas.md`.
        """)

    # Transcripts: a main-checkout session, a worktree session, and a session of another
    # project whose slug shares the prefix.
    projects = os.path.join(claude, "projects")
    main_slug = slug(repo)
    wt = os.path.join(repo, ".claude/worktrees/feat")
    mem = os.path.join(projects, main_slug, "memory")
    user_md = os.path.join(claude, "CLAUDE.md")
    _jsonl(os.path.join(projects, main_slug, "s1.jsonl"), [
        _instructions("s1", repo, "2026-09-01T10:00:00Z", [
            (user_md, "User"), (os.path.join(repo, "CLAUDE.md"), "Project"),
            (os.path.join(repo, "docs/runbook.md"), "Project"), (os.path.join(mem, "MEMORY.md"), "AutoMem")]),
        _tool_use("s1", repo, "2026-09-01T10:01:00Z", "Skill", {"skill": "glossary-keeper"}),
        _tool_use("s1", repo, "2026-09-01T10:02:00Z", "Write", {"file_path": os.path.join(repo, "GLOSSARY.md")}),
        _tool_use("s1", repo, "2026-09-01T10:03:00Z", "Read", {"file_path": os.path.join(repo, "docs/runbook.md")}),
    ])
    # A subagent of s1 invokes the skill too: its transcript carries s1's id and isSidechain.
    sub = _tool_use("s1", repo, "2026-09-01T10:04:00Z", "Skill", {"skill": "glossary-keeper"})
    sub["isSidechain"] = True
    _jsonl(os.path.join(projects, main_slug, "s1", "subagents", "agent-a1.jsonl"), [sub])
    _jsonl(os.path.join(projects, main_slug + "--claude-worktrees-feat", "s2.jsonl"), [
        _instructions("s2", wt, "2026-09-10T10:00:00Z", [
            (user_md, "User"), (os.path.join(wt, "CLAUDE.md"), "Project"),
            (os.path.join(wt, "docs/runbook.md"), "Project")]),
        _user("s2", wt, "2026-09-10T10:01:00Z", "<command-name>/glossary-keeper</command-name>"),
        _tool_use("s2", wt, "2026-09-10T10:02:00Z", "Read", {"file_path": os.path.join(wt, "GLOSSARY.md")}),
        _tool_use("s2", wt, "2026-09-10T10:03:00Z", "Edit", {"file_path": os.path.join(wt, "docs/ARCHITECTURE.md")}),
    ])
    other = repo + "-other"
    _jsonl(os.path.join(projects, slug(other), "s3.jsonl"), [
        _instructions("s3", other, "2026-09-15T10:00:00Z", [(os.path.join(other, "CLAUDE.md"), "Project")]),
        _tool_use("s3", other, "2026-09-15T10:01:00Z", "Skill", {"skill": "glossary-keeper"}),
    ])
    _write(mem, "MEMORY.md", "- [Backups](feedback_backups.md) — check the restore\n")
    _write(mem, "feedback_backups.md", f"""
        ---
        name: feedback-backups
        description: backups before migrations
        ---
        {RULE}
        """)

    # Cursor: one conversation that mentions the glossary.
    cursor = os.path.join(home, ".cursor/projects", slug(repo).lstrip("-"), "agent-transcripts/c1/c1.jsonl")
    _jsonl(cursor, [{"role": "user", "message": {"content": [{"type": "text", "text": "update GLOSSARY.md"}]}}])
    return home


def build(dest, home=None):
    repo = build_repo(dest)
    if home:
        build_home(home, repo)
    return repo


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dest")
    ap.add_argument("--home")
    a = ap.parse_args()
    print(build(a.dest, a.home))
