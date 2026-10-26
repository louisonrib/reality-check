#!/usr/bin/env python3
"""Run the agent with and without a change to a repo's docs, and report what each run did.

    behaviour_test.py <repo> --base <ref> (--patch <file> | --with-ref <ref>) --prompt-file <file>
                      [--runs N] [--model <model>] [--allow <tool> ...]
                      [--raw-dir <dir>] [--keep] [--claude-bin <path>]

Two clean copies of the repo are checked out from git objects, in a fresh temporary folder that no
CLAUDE.md, CLAUDE.local.md or AGENTS.md sits above: "without" is <base>, "with" is <base> plus the
patch (or the tree of --with-ref). Each copy is its own git repo with one commit, and both copies
have the same folder name. A headless Claude Code session runs the prompt in each copy, N times per
side, alternating. Read-only tools are allowed (Read, Grep, Glob, plus --allow); any other tool
call is denied but recorded, so a run shows what the agent tried without executing it. The user's
and the project's own allow rules are denied for the runs, and hooks are off, since either would
otherwise let a call through. The user's instruction files, skills and plugins still load, as
they do in the user's sessions.

Prints one JSON document: per run, the instruction files actually loaded (read from the session's
transcript), the tool calls with the denied ones marked, the final answer and how the run
ended; then the number of runs. Each session's raw stream is written to <raw-dir>/<side>-<n>.jsonl
before it is read, so a session already run survives an error in reading it. It never writes to
<repo>. The copies are deleted at the end unless --keep; the raw streams stay.
Standard library only.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

SCHEMA = 1
READ_ONLY_TOOLS = ["Read", "Grep", "Glob"]
INSTRUCTION_FILES = ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md")
GIT_ENV = {"GIT_AUTHOR_NAME": "behaviour-test", "GIT_AUTHOR_EMAIL": "behaviour-test@localhost",
           "GIT_COMMITTER_NAME": "behaviour-test", "GIT_COMMITTER_EMAIL": "behaviour-test@localhost",
           "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00"}


def git(cwd, *args, **env):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, check=True, encoding="utf-8",
                          errors="replace", env=dict(os.environ, **GIT_ENV, **env)).stdout


def instruction_file_above(path):
    """The first CLAUDE.md, CLAUDE.local.md or AGENTS.md in path or a folder above it, if any."""
    d = path
    while True:
        for name in INSTRUCTION_FILES:
            if os.path.isfile(os.path.join(d, name)):
                return os.path.join(d, name)
        if d == os.path.dirname(d):
            return None
        d = os.path.dirname(d)


def make_copy(repo, ref, dest, patch=None):
    """Check every tracked file of ref out into dest, apply patch, and commit the result in a
    fresh repo. The checkout goes through a throwaway index next to dest, so the audited repo's
    own index is never touched; unlike `git archive`, it ignores export-ignore attributes."""
    os.makedirs(dest)
    index = dest + ".index"
    git(repo, f"--work-tree={dest}", "read-tree", ref, GIT_INDEX_FILE=index)
    git(repo, f"--work-tree={dest}", "checkout-index", "-a", "-f", GIT_INDEX_FILE=index)
    os.remove(index)
    git(dest, "init", "-q", "-b", "main")
    if patch:
        git(dest, "apply", "--whitespace=nowarn", os.path.abspath(patch))
    git(dest, "add", "-A")
    git(dest, "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", "commit", "-q",
        "--allow-empty", "-m", "snapshot")


def slug(path):
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def tilde(path, home):
    return "~" + path[len(home):] if path.startswith(home + "/") else path


def loaded_instructions(home, cwd, session_id):
    """Instruction files a session loaded, from its transcript, in load order."""
    transcript = os.path.join(home, ".claude", "projects", slug(cwd), session_id + ".jsonl")
    out, seen = [], set()
    try:
        lines = open(transcript, encoding="utf-8", errors="replace").readlines()
    except OSError:
        return None
    for line in lines:
        if '"instructions"' not in line and '"nested_memory"' not in line:
            continue
        try:
            a = json.loads(line).get("attachment") or {}
        except ValueError:
            continue
        if a.get("type") == "instructions":
            entries = [(f.get("path"), f.get("type")) for f in a.get("files") or []]
        elif a.get("type") == "nested_memory":
            entries = [(os.path.join(cwd, a.get("path", "")), "nested")]
        else:
            continue
        for path, kind in entries:
            if not path:
                continue
            shown = os.path.relpath(path, cwd) if path.startswith(cwd + "/") else tilde(path, home)
            if (shown, kind) not in seen:
                seen.add((shown, kind))
                out.append({"path": shown, "type": kind})
    return out


def allow_rules(paths):
    """Permission allow rules in the given settings files."""
    rules = set()
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                rules.update((json.load(f).get("permissions") or {}).get("allow") or [])
        except (OSError, ValueError, AttributeError):
            continue
    return rules


def run_once(claude, cwd, prompt, allowed, model, home, deny, raw):
    # The user's and the project's allow rules still apply in a headless run, and a hook can
    # approve a call: deny every allow rule outside `allowed` (a deny rule wins over an allow
    # rule) and turn hooks off, so only the read-only tools can run.
    settings = {"disableAllHooks": True, "permissions": {"deny": deny}}
    argv = [claude, "-p", prompt, "--output-format", "stream-json", "--verbose",
            "--allowedTools", ",".join(allowed), "--permission-mode", "dontAsk",
            "--permission-prompts", "none", "--settings", json.dumps(settings)]
    if model:
        argv += ["--model", model]
    proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    with open(raw, "w", encoding="utf-8") as f:
        f.write(proc.stdout)
    calls, results, final, session_id = [], {}, None, None
    for line in proc.stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if not isinstance(e, dict):
            continue
        session_id = session_id or e.get("session_id")
        # Some events (system notices, errors) carry `message` as a string.
        message = e.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        blocks = [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []
        if e.get("type") == "assistant":
            calls += [b for b in blocks if b.get("type") == "tool_use"]
        elif e.get("type") == "user":
            results.update({b.get("tool_use_id"): b for b in blocks if b.get("type") == "tool_result"})
        elif e.get("type") == "result":
            final = e
    denied = {d.get("tool_use_id") for d in (final or {}).get("permission_denials") or []}
    return {
        "session_id": session_id,
        "raw": raw,
        "instructions_loaded": loaded_instructions(home, cwd, session_id) if session_id else None,
        "tool_calls": [{"name": c.get("name"), "input": c.get("input"), "denied": c.get("id") in denied,
                        "error": bool((results.get(c.get("id")) or {}).get("is_error"))} for c in calls],
        "answer": (final or {}).get("result"),
        "exit_code": proc.returncode,
        "error": None if final and not final.get("is_error") else (proc.stderr.strip()[-2000:] or
                                                                  (final or {}).get("subtype") or "no result"),
    }


def main(argv):
    ap = argparse.ArgumentParser(prog="behaviour_test.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("repo", help="the audited repo (read only)")
    ap.add_argument("--base", required=True, help="the ref both copies start from")
    change = ap.add_mutually_exclusive_group(required=True)
    change.add_argument("--patch", help="a patch (git diff) applied to the 'with' copy")
    change.add_argument("--with-ref", help="a ref whose tree is the 'with' copy")
    ap.add_argument("--prompt-file", required=True, help="the prompt given to both copies")
    ap.add_argument("--runs", type=int, default=1, help="runs per side (default 1: the pilot pair)")
    ap.add_argument("--model", help="model for the runs (default: Claude Code's)")
    ap.add_argument("--allow", action="append", default=[], help="another tool to allow, e.g. 'Bash(git log:*)'")
    ap.add_argument("--raw-dir", help="folder for each session's raw stream (default: a new temporary folder)")
    ap.add_argument("--keep", action="store_true", help="keep the two copies")
    ap.add_argument("--claude-bin", default="claude", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    home = os.path.realpath(os.path.expanduser("~"))
    repo = git(os.path.realpath(a.repo), "rev-parse", "--show-toplevel").strip()
    base = git(repo, "rev-parse", a.base).strip()
    with open(a.prompt_file, encoding="utf-8") as f:
        prompt = f.read()
    if a.raw_dir and (os.path.realpath(a.raw_dir) + "/").startswith(repo + "/"):
        sys.exit(f"behaviour_test.py: --raw-dir {a.raw_dir} is inside the audited repo; give a folder outside it.")

    root = os.path.realpath(tempfile.mkdtemp(prefix="behaviour-test-"))
    above = instruction_file_above(root)
    if above:
        shutil.rmtree(root)
        sys.exit(f"behaviour_test.py: {above} sits above the temporary folder {root}; it would load "
                 "into both runs. Set TMPDIR to a folder with no instruction file above it.")
    raw_dir = os.path.realpath(a.raw_dir or tempfile.mkdtemp(prefix="behaviour-test-raw-"))
    os.makedirs(raw_dir, exist_ok=True)
    name = os.path.basename(repo)
    copies = {"with": os.path.join(root, "a", name), "without": os.path.join(root, "b", name)}
    try:
        make_copy(repo, base, copies["without"])
        if a.patch:
            make_copy(repo, base, copies["with"], patch=a.patch)
        else:
            make_copy(repo, git(repo, "rev-parse", a.with_ref).strip(), copies["with"])
        allowed = READ_ONLY_TOOLS + a.allow
        settings_files = [os.path.join(home, ".claude", n) for n in ("settings.json", "settings.local.json")]
        settings_files += [os.path.join(c, ".claude", n) for c in copies.values()
                           for n in ("settings.json", "settings.local.json")]
        deny = sorted(allow_rules(settings_files) - set(allowed))
        runs = []
        for i in range(1, a.runs + 1):
            for side in ("with", "without"):
                result = run_once(a.claude_bin, copies[side], prompt, allowed, a.model,
                                  home, deny, os.path.join(raw_dir, f"{side}-{i}.jsonl"))
                runs.append({"side": side, "run": i, **result})
    finally:
        if not a.keep:
            shutil.rmtree(root, ignore_errors=True)
    out = {
        "schema": SCHEMA,
        "repo": repo,
        "base": base,
        "change": {"patch": os.path.abspath(a.patch)} if a.patch else
                  {"ref": git(repo, "rev-parse", a.with_ref).strip()},
        "prompt": prompt,
        "allowed_tools": allowed,
        "denied_allow_rules": deny,
        "copies": copies if a.keep else None,
        "raw_dir": raw_dir,
        "runs": runs,
        "totals": {"runs": len(runs)},
    }
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1:])
