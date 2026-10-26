#!/usr/bin/env python3
"""Stands in for `claude -p ... --output-format stream-json` in the tests of behaviour_test.py.

It behaves like a headless run in the current directory: it writes a transcript under
$HOME/.claude/projects/<slug of cwd>/ with the instruction files a session would load, tries one
allowed tool and one tool outside --allowedTools, and prints the stream. Its answer quotes the
first line of CLAUDE.md, so a test can tell the copy with the change from the one without.
It appends its argv to $FAKE_CLAUDE_LOG when set.
"""
import json
import os
import re
import sys
import uuid

args = sys.argv[1:]
if os.environ.get("FAKE_CLAUDE_LOG"):
    with open(os.environ["FAKE_CLAUDE_LOG"], "a", encoding="utf-8") as f:
        f.write(json.dumps({"argv": args, "cwd": os.getcwd(), "files": sorted(os.listdir(os.getcwd()))}) + "\n")

cwd = os.getcwd()
allowed = args[args.index("--allowedTools") + 1].split(",") if "--allowedTools" in args else []
sid = str(uuid.uuid4())
claude_md = os.path.join(cwd, "CLAUDE.md")
first_line = open(claude_md, encoding="utf-8").readline().strip() if os.path.exists(claude_md) else "none"
files = [{"path": os.path.join(os.environ["HOME"], ".claude", "CLAUDE.md"), "type": "User", "content": ""}]
if os.path.exists(claude_md):
    files.append({"path": claude_md, "type": "Project", "content": ""})

transcript = os.path.join(os.environ["HOME"], ".claude", "projects", re.sub(r"[^A-Za-z0-9]", "-", cwd),
                          sid + ".jsonl")
os.makedirs(os.path.dirname(transcript), exist_ok=True)
with open(transcript, "w", encoding="utf-8") as f:
    f.write(json.dumps({"type": "attachment", "sessionId": sid, "cwd": cwd, "timestamp": "2026-10-21T10:00:00Z",
                        "attachment": {"type": "instructions", "files": files}}) + "\n")

calls = [("t1", "Read", {"file_path": claude_md}), ("t2", "Bash", {"command": "rm -rf build"})]
denied = [c for c in calls if c[1] not in allowed]


def emit(obj):
    print(json.dumps(obj), flush=True)


emit({"type": "system", "subtype": "init", "session_id": sid, "cwd": cwd, "tools": ["Read", "Bash"]})
if os.environ.get("FAKE_CLAUDE_ODD_EVENTS"):
    # Events seen in real streams: a notice whose `message` is a string, a bare JSON value, and
    # content holding a block that is not an object.
    emit({"type": "system", "subtype": "notice", "session_id": sid, "message": "Context compacted"})
    emit("keepalive")
    emit({"type": "assistant", "session_id": sid, "message": {"role": "assistant", "content": ["thinking…"]}})
for tid, name, inp in calls:
    emit({"type": "assistant", "session_id": sid,
          "message": {"role": "assistant", "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}})
    is_denied = any(d[0] == tid for d in denied)
    emit({"type": "user", "session_id": sid, "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tid, "is_error": is_denied,
         "content": "Permission denied" if is_denied else "ok"}]}})
emit({"type": "assistant", "session_id": sid,
      "message": {"role": "assistant", "content": [{"type": "text", "text": "First line: " + first_line}]}})
emit({"type": "result", "subtype": "success", "is_error": False, "session_id": sid, "num_turns": 3,
      "duration_ms": 1200, "total_cost_usd": 0.0125, "result": "First line: " + first_line,
      "permission_denials": [{"tool_name": n, "tool_use_id": t, "tool_input": i} for t, n, i in denied]})
