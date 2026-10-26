#!/usr/bin/env python3
"""Facts about a repo's doc files, for the fix-my-context skill. Read-only.

    inventory.py <repo> [--history-of <path>]
    inventory.py measure <repo> --base <sha> [--history-of <path>]
    inventory.py repeats <repo> <path>... [--history-of <path>]

Writes one JSON document on stdout. Its fields are described in
../references/inventory-output.md. Standard library only.
"""
import argparse
import json
import os
import posixpath
import re
import subprocess
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

SCHEMA = 1
DOC_EXTENSIONS = (".md", ".mdx", ".mdc", ".rst", ".adoc")
DEPENDENCY_DIRS = {"node_modules", "vendor", "bower_components", ".venv", "venv", "site-packages",
                   "third_party", "Pods", "Carthage"}
# Extensions that make a backticked token read as a file path rather than a symbol (`os.path`).
FILE_EXTENSIONS = set("""md mdx mdc rst adoc txt py pyi js jsx ts tsx mjs cjs json jsonc yaml yml toml
    ini cfg conf env sh bash zsh sql go rs java kt kts swift rb php c h cc cpp hpp cs css scss sass less
    html htm vue svelte astro xml csv lock dart ex exs erl hs ml scala gradle tf hcl proto graphql gql
    ipynb r jl lua pl dockerfile mk cmake bat ps1 plist pbxproj storyboard xib sqlite db log svg png jpg
    jpeg gif webp pdf""".split())

LINK = re.compile(r"\[[^\]\n]*\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^\"']*[\"'])?\s*\)")
BACKTICK = re.compile(r"`([^`\n]+)`")
IMPORT = re.compile(r"(?:^|(?<=\s))@([^\s`]+)")
ISSUE = re.compile(r"(?<![\w&/#])#\d{1,6}\b|/(?:pull|issues)/\d+")
DATE = re.compile(r"(?<!\d)20\d\d-[01]\d-[0-3]\d(?!\d)")
FENCE = re.compile(r"^\s*(```|~~~)")
# Numbered decision records (`0024-keep-backups.md`, `adr-24.md`) and their citations ("ADR-0024", "ADR 24").
NUMBERED = re.compile(r"(?i)^(adr[-_ ]?)?0*(\d{1,5})(?=[-_ .])")
DECISION_FOLDER = re.compile(r"(?i)(?:^|[-_ ])(?:adrs?|decisions?)(?:[-_ ]|$)")
CITATION = re.compile(r"(?i)(?<![\w/-])ADR[-_ ]?(\d{1,5})(?!\d)")


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, encoding="utf-8",
                          errors="replace", check=True).stdout


def is_doc(path):
    parts = path.split("/")
    return path.endswith(DOC_EXTENSIONS) and not DEPENDENCY_DIRS.intersection(parts[:-1])


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


class Tree:
    """The repo's files at one point: the working tree (ref None) or a commit. Its docs are the
    tracked doc files, plus the untracked ones that git does not ignore if with_untracked."""

    def __init__(self, repo, ref=None, with_untracked=False):
        self.repo, self.ref = repo, ref
        links = {}  # a symlink -> the repo path it points to
        if ref:
            paths = []
            for entry in git(repo, "ls-tree", "-r", "-z", ref).split("\0"):
                if not entry:
                    continue
                meta, path = entry.split("\t", 1)
                paths.append(path)
                if meta.startswith("120000"):  # git stores a symlink as a blob holding its target
                    target = git(repo, "cat-file", "blob", meta.split()[2])
                    links[path] = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
            self.untracked = []
        else:
            paths = [p for p in git(repo, "ls-files", "-z").split("\0")
                     if p and os.path.isfile(os.path.join(repo, p))]
            self.untracked = sorted(p for p in git(repo, "ls-files", "-z", "--others",
                                                   "--exclude-standard").split("\0") if p)
            for p in paths:
                if os.path.islink(os.path.join(repo, p)):
                    real = os.path.relpath(os.path.realpath(os.path.join(repo, p)), os.path.realpath(repo))
                    links[p] = real.replace(os.sep, "/")
        self.files = {p for p in paths if p}
        # Only a link to a file of the repo is read as that file; any other reads as itself.
        self.links = {p: t for p, t in links.items() if t in self.files}
        self.dirs = {posixpath.dirname(p) for p in self.files | set(self.untracked)}
        for d in list(self.dirs):
            while d:
                d = posixpath.dirname(d)
                self.dirs.add(d)
        self.listed = self.files | set(self.untracked) if with_untracked else self.files
        self.docs = sorted(p for p in self.listed if is_doc(p))
        self.suffixes = {}  # "lib/x.ts" -> paths ending with it, for references written short
        for p in self.files | self.dirs:
            parts = p.split("/")
            for i in range(1, len(parts)):
                self.suffixes.setdefault("/".join(parts[i:]), []).append(p)

    def find(self, rel):
        """The one path that ends with rel, True when several do, None when none does."""
        paths = self.suffixes.get(rel)
        if not paths:
            return None
        return paths[0] if len(paths) == 1 else True

    def exists(self, rel):
        if rel in self.files or rel in self.dirs or rel in self.untracked:
            return True
        return self.ref is None and os.path.exists(os.path.join(self.repo, rel))

    def read(self, rel):
        if self.ref:  # a symlink reads as its target, as it does in the working tree
            return git(self.repo, "show", f"{self.ref}:{self.links.get(rel, rel)}")
        return read_text(os.path.join(self.repo, rel))


def size(text):
    return {"lines": len(text.splitlines()), "words": len(text.split())}


def renamed_paths(field):
    """Paths in a numstat path field: `a.md`, `old.md => new.md` or `docs/{old => new}/a.md`."""
    m = re.match(r"^(.*)\{(.*) => (.*)\}(.*)$", field)
    if m:
        pre, old, new, post = m.groups()
        return {re.sub("/+", "/", pre + old + post), re.sub("/+", "/", pre + new + post)}
    return set(field.split(" => "))


def history(repo, path):
    """Commits touching path, renames followed: (summary or None, their dates newest first)."""
    log = git(repo, "log", "--follow", "--numstat", "--format=%x1e%H%x1f%aI%x1f%an%x1f%s", "--", path)
    commits, added, deleted, names = [], 0, 0, set()
    for block in log.split("\x1e")[1:]:
        head, _, stats = block.partition("\n")
        commits.append(head.split("\x1f"))
        for line in stats.splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                names.update(renamed_paths(parts[2]))
                if parts[0].isdigit():
                    added += int(parts[0])
                    deleted += int(parts[1])
    if not commits:
        return None, []
    first, last = commits[-1], commits[0]
    body = git(repo, "show", "-s", "--format=%b", first[0]).strip()
    return {
        "commits": len(commits), "lines_added": added, "lines_deleted": deleted,
        "former_paths": sorted({n for n in names if n and n != path}),
        "created": {"sha": first[0], "date": first[1], "author": first[2], "subject": first[3],
                    "body": body},
        "last": {"sha": last[0], "date": last[1], "subject": last[3]},
    }, [c[1] for c in commits]


HEADER_LINES = 10
# A header line is a short label and a colon, the date after it: "Date: 2026-06-25",
# "**Status**: Accepted · **Date**: …", "**Date :** …", "date: …" in front matter.
HEADER_LABEL = re.compile(r"^[\s>*_\-]*[^\W\d_][\w' -]{0,30}?[*_]*\s*:")


def dated(path, text, commit_dates):
    """The date a doc gives itself, in its file name or in a header line among its first lines,
    and the commits made to it on later days, its creating commit aside; None when it gives
    no date."""
    m = DATE.search(posixpath.basename(path))
    date, source, line = (m.group(), "name", None) if m else (None, None, None)
    if not date:
        for n, text_line in prose_lines(text):
            if n > HEADER_LINES:
                break
            label = HEADER_LABEL.match(text_line)
            m = label and DATE.search(text_line, label.end())
            if m:
                date, source, line = m.group(), "header", n
                break
    if not date:
        return None
    after = [d[:10] for d in commit_dates[:-1] if d[:10] > date]
    return {"date": date, "source": source, "line": line, "commits_after": len(after),
            "last_after": max(after) if after else None}


def prose_lines(text):
    """(line number, line) for lines outside fenced code blocks."""
    fenced = False
    for n, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            yield n, line


def looks_like_path(token, top_level_exists):
    if re.search(r"\s|://|[*?{}<>\[\]|=]", token) or token[0] in "~$-@/#":
        return False
    if token.endswith("/"):
        return True
    ext = token.rsplit(".", 1)[-1].lower() if "." in posixpath.basename(token) else ""
    if ext in FILE_EXTENSIONS:
        return True
    return "/" in token and top_level_exists(token.split("/")[0])


def resolve(target, from_path, tree):
    """Path the target names in tree, trying the doc's folder, then the root, then any path that
    ends with it (`app.py` for src/app.py). True when it exists but several paths match;
    None when nothing is there."""
    target = target.rstrip("/")
    candidates = [posixpath.normpath(posixpath.join(posixpath.dirname(from_path), target))]
    candidates.append(posixpath.normpath(target.lstrip("/")))
    for c in candidates:
        if not c.startswith("..") and c != "." and tree.exists(c):
            return c
    if not target.startswith((".", "/")):
        return tree.find(posixpath.normpath(target))
    return None


def expands_imports(path):
    """Files whose `@path` lines Claude Code or Gemini CLI expand (vendor docs, see harness_rules)."""
    base = posixpath.basename(path)
    return base in ("CLAUDE.md", "CLAUDE.local.md", "GEMINI.md") or path.startswith(".claude/rules/")


def imports_in(text):
    for n, line in prose_lines(text):
        for m in IMPORT.finditer(BACKTICK.sub(" ", line)):
            token = m.group(1).rstrip(".,;:)")
            if token:
                yield n, token


def decision_records(docs):
    """Number -> path of each numbered decision record: a numbered doc file in a folder named for
    decisions (`adr`, `decisions`, `architecture-decisions`), or named `adr-<n>-…` itself.
    A number two records share maps to None: citing it names no one file."""
    out = {}
    for path in docs:
        folder, name = posixpath.split(path)
        m = NUMBERED.match(name)
        if m and (m.group(1) or DECISION_FOLDER.search(posixpath.basename(folder))):
            n = int(m.group(2))
            out[n] = None if n in out else path
    return out


def citations(path, text, records, named):
    """Pointers from path to the decision records its text cites by number, except on a line
    whose link or backticked path already names that record (`named`, from scan_refs)."""
    seen = {(to, n) for n, to, _ in named}
    out = set()
    for n, line in prose_lines(text):
        for m in CITATION.finditer(line):
            to = records.get(int(m.group(1)))
            if to and to != path and (to, n) not in seen:
                out.add((path, to, "citation", n))
    return out


def scan_refs(text, resolver, top_level_exists, imports):
    """Return (named, unresolved): named = [(line, target, kind)], unresolved = [{line, ref, kind}].
    resolver(target) gives the path a reference names, or None when nothing is there."""
    named, unresolved = [], []

    def note(n, target, ref, kind):
        hit = resolver(target)
        if isinstance(hit, str):
            named.append((n, hit, kind))
        elif hit is None and not re.match(r"^\.[A-Za-z0-9.]+$", target):  # `.test.ts`: a kind of file
            unresolved.append({"line": n, "ref": ref, "kind": kind})

    for n, line in prose_lines(text):
        for m in LINK.finditer(line):
            target = urllib.parse.unquote(m.group(1).split("#")[0].split("?")[0])
            if target and not re.match(r"^[a-zA-Z][\w+.-]*:", target):
                note(n, target, m.group(1), "link")
        for m in BACKTICK.finditer(line):
            token = re.sub(r":\d+(-\d+)?$", "", m.group(1).strip())
            if token and looks_like_path(token, top_level_exists):
                note(n, token, token, "backtick")
    if imports:
        for n, token in imports_in(text):
            if not token.startswith("~"):
                note(n, token, token, "import")
    return named, unresolved


class DirTree:
    """A plain folder (the auto-memory directory) with the same reading interface as Tree."""

    def __init__(self, root):
        self.root, self.files = root, set()
        for dirpath, _, names in os.walk(root):
            for name in names:
                self.files.add(os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/"))
        self.docs = sorted(p for p in self.files if is_doc(p))

    def exists(self, rel):
        return os.path.exists(os.path.join(self.root, rel))

    def find(self, rel):
        return None  # memory files name each other by their exact relative path

    def read(self, rel):
        return read_text(os.path.join(self.root, rel))


def frontmatter_patterns(text):
    """Patterns under `paths:`, `globs:` or `applyTo:` in a leading YAML block."""
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    if not m:
        return []
    out, current = [], False
    for line in m.group(1).splitlines():
        key = re.match(r"^(\w+):\s*(.*)$", line)
        if key:
            current = key.group(1) in ("paths", "globs", "applyTo")
            if current and key.group(2):
                out += [v.strip().strip("\"'") for v in key.group(2).strip("[]").split(",") if v.strip()]
        elif current and re.match(r"^\s*-\s*", line):
            out.append(re.sub(r"^\s*-\s*", "", line).strip().strip("\"'"))
    return out


def glob_regex(pattern):
    i, out = 0, ""
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
            continue
        if pattern.startswith("**", i):
            out, i = out + ".*", i + 2
            continue
        if c == "*":
            out += "[^/]*"
        elif c == "?":
            out += "[^/]"
        elif c == "{":
            j = pattern.index("}", i)
            out += "(?:" + "|".join(re.escape(x) for x in pattern[i + 1:j].split(",")) + ")"
            i = j
        else:
            out += re.escape(c)
        i += 1
    return re.compile(out + r"\Z")


# Vendor-documented loading rules. Each source was read on 2026-10-21; see
# docs/research/sources/A-vendor-harness.md and F-doc-set-structure-and-placement.md in the
# fix-my-context repo for the quoted sentences.
CC_MEMORY = "https://code.claude.com/docs/en/memory"
CC_SKILLS = "https://code.claude.com/docs/en/skills"
CC_AGENTS = "https://code.claude.com/docs/en/sub-agents"
CODEX = "https://learn.chatgpt.com/docs/agent-configuration/agents-md"
COPILOT = ("https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/"
           "add-custom-instructions/add-repository-instructions")
CURSOR = "https://cursor.com/docs/rules"
GEMINI = "https://geminicli.com/docs/cli/gemini-md/"
GH_HEALTH = ("https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/"
             "creating-a-default-community-health-file")
GH_README = ("https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/"
             "customizing-your-repository/about-readmes")
GH_TEMPLATES = ("https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-"
                "pull-requests/about-issue-and-pull-request-templates")
# GitHub looks in .github/, then the root, then docs/, and uses the first match.
GH_PRECEDENCE = [".github", "", "docs"]
GH_COMMUNITY = {"README": ("displayed", "Shown on the repository's front page.", GH_README),
                "CONTRIBUTING": ("linked", "Linked when someone opens an issue or a pull request.", GH_HEALTH),
                "CODE_OF_CONDUCT": ("displayed", "Shown in the repository's community profile.", GH_HEALTH),
                "SECURITY": ("displayed", "Shown on the repository's Security tab.", GH_HEALTH),
                "SUPPORT": ("linked", "Linked when someone opens an issue.", GH_HEALTH),
                "PULL_REQUEST_TEMPLATE": ("displayed", "Pre-fills the description of new pull requests.",
                                          GH_TEMPLATES)}


def rule(harness, when, text, source, **extra):
    return {"harness": harness, "when": when, "rule": text, "source": source, **extra}


def claude_md_above(project, tree):
    """Whether a CLAUDE.md or CLAUDE.local.md sits at the repo root or in a folder above the
    project's real checkout (not above a copy of it made elsewhere)."""
    if {"CLAUDE.md", "CLAUDE.local.md", ".claude/CLAUDE.md"} & tree.files:
        return True
    d = os.path.dirname(project)
    while True:
        if any(os.path.isfile(os.path.join(d, n)) for n in ("CLAUDE.md", "CLAUDE.local.md")):
            return True
        if d == os.path.dirname(d):
            return False
        d = os.path.dirname(d)


def harness_rules(path, text, tree, agents_condition_met):
    rules = []
    folder, base = posixpath.dirname(path), posixpath.basename(path)
    stem = base.split(".")[0].upper()
    at_root = folder == ""

    # Claude Code
    if path in ("CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md"):
        rules.append(rule("claude-code", "session_start", "Loaded when a session starts in the repo.",
                          CC_MEMORY))
    elif base in ("CLAUDE.md", "CLAUDE.local.md") and not path.startswith(".claude/"):
        rules.append(rule("claude-code", "on_touch",
                          f"Loaded when the agent reads, writes or edits a file in {folder}/, "
                          "or at start for a session launched there.", CC_MEMORY))
    elif path.startswith(".claude/rules/") and base.endswith(".md"):
        patterns = frontmatter_patterns(text)
        if patterns:
            rules.append(rule("claude-code", "path_scoped",
                              "Loaded when the agent reads, writes or edits a file matching `paths`.",
                              CC_MEMORY, paths=patterns))
        else:
            rules.append(rule("claude-code", "session_start",
                              "A rule without `paths` loads when a session starts.", CC_MEMORY))
    elif re.match(r"^\.claude/skills/[^/]+/SKILL\.md$", path):
        rules.append(rule("claude-code", "on_invoke",
                          "Its description is listed at session start; the body loads when the skill is "
                          "invoked.", CC_SKILLS))
    elif path.startswith(".claude/commands/") and base.endswith(".md"):
        rules.append(rule("claude-code", "on_invoke", "Loaded when the command is invoked.", CC_SKILLS))
    elif re.match(r"^\.claude/agents/[^/]+\.md$", path):
        rules.append(rule("claude-code", "on_invoke", "Loaded as the subagent's prompt when it runs.",
                          CC_AGENTS))
    if base == "AGENTS.md":
        condition = ("Claude Code reads AGENTS.md only when no CLAUDE.md or CLAUDE.local.md sits in the "
                     "working directory or above it (default setting).")
        if at_root:
            rules.append(rule("claude-code", "session_start", "Loaded when a session starts in the repo.",
                              CC_MEMORY, condition=condition, condition_met=agents_condition_met))
        else:
            rules.append(rule("claude-code", "on_touch",
                              f"Loaded when the agent opens a file in {folder}/ with the Read tool.",
                              CC_MEMORY, condition=condition, condition_met=agents_condition_met))

    # Codex, Copilot, Cursor: AGENTS.md
    if base in ("AGENTS.md", "AGENTS.override.md"):
        if at_root:
            rules.append(rule("codex", "session_start",
                              "Joins the instruction chain built at start, root first, 32 KiB in total.", CODEX))
        else:
            rules.append(rule("codex", "session_start",
                              "Joins the instruction chain when the session starts in this folder or below.",
                              CODEX, condition=f"The session starts in {folder}/ or below.",
                              condition_met=None))
    if base == "AGENTS.md":
        rules.append(rule("copilot", "session_start" if at_root else "on_touch",
                          "The nearest AGENTS.md in the directory tree applies.", COPILOT))
        rules.append(rule("cursor", "session_start" if at_root else "on_touch",
                          "Root and nested AGENTS.md are combined, the more specific one winning.", CURSOR))
    if path in ("CLAUDE.md", "GEMINI.md"):
        rules.append(rule("copilot", "session_start",
                          "A single root CLAUDE.md or GEMINI.md can stand in for AGENTS.md.", COPILOT,
                          condition="Used as Copilot's instructions instead of AGENTS.md.",
                          condition_met=None))
    if path == ".github/copilot-instructions.md":
        rules.append(rule("copilot", "session_start", "Repository-wide instructions, sent with every request.",
                          COPILOT))
    if path.startswith(".github/instructions/") and base.endswith(".instructions.md"):
        rules.append(rule("copilot", "path_scoped", "Applies to files matching `applyTo`.", COPILOT,
                          paths=frontmatter_patterns(text)))
    if path.startswith(".cursor/rules/"):
        if base.endswith(".mdc"):
            always = re.search(r"^alwaysApply:\s*true\s*$", text, re.M)
            globs = frontmatter_patterns(text)
            if always:
                rules.append(rule("cursor", "session_start", "`alwaysApply: true`: in every chat.", CURSOR))
            elif globs:
                rules.append(rule("cursor", "path_scoped", "Applied to files matching `globs`.", CURSOR,
                                  paths=globs))
            else:
                rules.append(rule("cursor", "on_invoke",
                                  "Applied when the agent judges its description relevant, or by hand.", CURSOR))
        else:
            rules.append(rule("cursor", "ignored", "A plain .md file in .cursor/rules is ignored.", CURSOR))

    # Gemini CLI
    if base == "GEMINI.md":
        rules.append(rule("gemini-cli", "session_start" if at_root else "on_touch",
                          "Loaded at start from the workspace and its parents, and just in time from a "
                          "folder a tool touches.", GEMINI))

    # GitHub
    if folder in GH_PRECEDENCE and stem in GH_COMMUNITY:
        when, description, source = GH_COMMUNITY[stem]
        extra = {}
        for higher in GH_PRECEDENCE[:GH_PRECEDENCE.index(folder)]:
            shadow = [p for p in tree.files if posixpath.dirname(p) == higher
                      and posixpath.basename(p).split(".")[0].upper() == stem]
            if shadow:
                extra["shadowed_by"] = sorted(shadow)[0]
                break
        rules.append(rule("github", when, description, source, **extra))
    elif path.startswith(".github/PULL_REQUEST_TEMPLATE/"):
        rules.append(rule("github", "displayed", "Offered as a pull request template.", GH_TEMPLATES))
    elif path.startswith(".github/ISSUE_TEMPLATE/"):
        rules.append(rule("github", "displayed", "Offered as an issue template.", GH_TEMPLATES))
    return rules


def propagate_imports(files_by_path, pointers):
    """A file imported (up to four hops) by a Claude Code file inherits its loading moment."""
    imports = {}
    for f, t, kind, _ in pointers:
        if kind == "import":
            imports.setdefault(f, []).append(t)
    for root, entry in sorted(files_by_path.items()):
        own = [r for r in entry["harness"] if r["harness"] == "claude-code"
               and r["when"] in ("session_start", "on_touch") and "imported by" not in r["rule"]]
        if not own:
            continue
        frontier, seen = [root], {root}
        for _ in range(IMPORT_HOPS):
            nxt = []
            for f in frontier:
                for t in sorted(imports.get(f, [])):
                    if t in seen:
                        continue
                    seen.add(t)
                    nxt.append(t)
                    target = files_by_path[t]["harness"]
                    if not any(r["harness"] == "claude-code" and r["when"] == own[0]["when"] for r in target):
                        target.append(rule("claude-code", own[0]["when"],
                                           f"Expanded into context with {root}, which imports it "
                                           f"(imported by {f}).", CC_MEMORY))
            frontier = nxt


def slug(path):
    """Claude Code's project directory name for a working directory (observed 2026-10-21)."""
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def auto_memory_dir(history_of, home):
    return os.path.join(home, ".claude", "projects", slug(history_of), "memory")


def tilde(path, home):
    return "~" + path[len(home):] if path == home or path.startswith(home + "/") else path


TS = re.compile(r'"timestamp":\s*"([^"]+)"')
CWD = re.compile(r'"cwd":\s*"([^"]+)"')
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
MARKERS = ('"instructions"', '"nested_memory"', '"tool_use"', "<command-name>")
# A doc path written in a tool's input: absolute, `~/`-prefixed or relative.
NAMED_DOC = re.compile(r"(?<![\w./~-])((?:~/|/)?(?:[\w@+.-]+/)*[\w@+-][\w@+.-]*\.(?:md|mdx|mdc|rst|adoc))(?![\w/-])")
CD = re.compile(r"(?<![\w-])cd\s+([\"']?)([^\s;&|()\"']+)\1")
PATH_FIELDS = ("file_path", "notebook_path", "path")


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)


class Transcripts:
    """What Claude Code transcripts say about one project: its main checkout, its worktrees and
    sessions launched in a subfolder, recognised by the `cwd` they record."""

    def __init__(self, history_of, home):
        self.history_of, self.home = history_of, home
        self.memory_dir = auto_memory_dir(history_of, home)
        self.dirs, self.session_dates = set(), {}
        self.loaded, self.read, self.wrote = {}, {}, {}  # key -> {session: last date}
        self.read_by = {}  # key -> {tool name: {session}}
        self.loaded_first = {}  # key -> {session: first date}
        self.first_write = {}  # key -> (timestamp, session)
        self.skills = []  # (session, name, date, made by a subagent)
        self.user_files = set()  # paths loaded as user instructions
        self.files_read = 0
        root = os.path.join(home, ".claude", "projects")
        base = slug(history_of)
        try:
            candidates = sorted(d for d in os.listdir(root) if d == base or d.startswith(base + "-"))
        except OSError:
            candidates = []
        for d in candidates:
            for dirpath, _, names in os.walk(os.path.join(root, d)):
                for name in sorted(names):
                    if name.endswith(".jsonl"):
                        self._read_file(os.path.join(dirpath, name), d)

    def within(self, path):
        return path == self.history_of or path.startswith(self.history_of + "/")

    def key(self, path):
        """("repo", rel) for a path in the project or one of its worktrees, else ("abs", path)."""
        path = os.path.normpath(path)
        m = re.match(re.escape(self.history_of) + r"(?:/\.claude/worktrees/[^/]+)?/(.+)$", path)
        if m:
            return ("repo", m.group(1))
        return ("abs", path)

    def named(self, inp, cwd):
        """Keys of the files a tool's input names: its path fields whole, and every doc path in
        its text. A relative path resolves against the folder of the last `cd` before it in the
        same text (`cd <memory dir> && cat feedback.md`), else against the session's folder."""
        def absolute(p, base):
            if p == "~" or p.startswith("~/"):
                return self.home + p[1:]
            return os.path.join(base, p) if base else (p if p.startswith("/") else None)

        paths = {absolute(inp[k], cwd) for k in PATH_FIELDS if isinstance(inp.get(k), str) and inp[k]}
        for text in strings(inp):
            base = cwd
            hits = sorted([(m.start(), True, m.group(2)) for m in CD.finditer(text)]
                          + [(m.start(), False, m.group(1)) for m in NAMED_DOC.finditer(text)])
            for _, is_cd, p in hits:
                if is_cd:
                    base = absolute(p, base)
                else:
                    paths.add(absolute(p, base))
        return {self.key(p) for p in paths if p}

    def _read_file(self, path, dirname):
        stem = os.path.splitext(os.path.basename(path))[0]
        mine = None
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith(('{"type":"api-request', '{"type":"file-history')):
                    continue
                if mine is None:
                    cwd = CWD.search(line)
                    if not cwd:
                        continue
                    mine = self.within(cwd.group(1))
                    if not mine:
                        return
                    self.dirs.add(dirname)
                    self.files_read += 1
                ts = TS.search(line)
                if not ts:
                    continue
                if not any(m in line for m in MARKERS):
                    sid = re.search(r'"sessionId":\s*"([^"]+)"', line)
                    self._seen(sid.group(1) if sid else stem, ts.group(1)[:10])
                    continue
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                self._entry(e, e.get("sessionId") or stem, ts.group(1),
                            e.get("isSidechain") is True or "/subagents/" in path)

    def _seen(self, sid, date):
        first, last = self.session_dates.get(sid, (date, date))
        self.session_dates[sid] = (min(first, date), max(last, date))

    @staticmethod
    def _mark(table, key, sid, date):
        sessions = table.setdefault(key, {})
        sessions[sid] = max(sessions.get(sid, date), date)

    def _entry(self, e, sid, ts, subagent):
        date = ts[:10]
        self._seen(sid, date)
        a = e.get("attachment") or {}
        if a.get("type") == "instructions":
            for f in a.get("files") or []:
                if f.get("path"):
                    self._mark(self.loaded, self.key(f["path"]), sid, date)
                    first = self.loaded_first.setdefault(self.key(f["path"]), {})
                    first[sid] = min(first.get(sid, date), date)
                    if f.get("type") == "User":
                        self.user_files.add(f["path"])
        elif a.get("type") == "nested_memory" and a.get("path"):
            key = self.key(os.path.join(e.get("cwd") or "", a["path"]))
            self._mark(self.loaded, key, sid, date)
            first = self.loaded_first.setdefault(key, {})
            first[sid] = min(first.get(sid, date), date)
        msg = e.get("message") if isinstance(e.get("message"), dict) else {}
        content = msg.get("content")
        if isinstance(content, str) and "<command-name>" in content:
            name = content.split("<command-name>")[1].split("</command-name>")[0].strip().lstrip("/")
            self.skills.append((sid, name, date, subagent))
        if isinstance(content, list):
            for b in content:
                if not isinstance(b, dict) or b.get("type") != "tool_use":
                    continue
                inp = b.get("input") or {}
                name = b.get("name")
                if name == "Skill" and inp.get("skill"):
                    self.skills.append((sid, inp["skill"].lstrip("/"), date, subagent))
                if name in WRITE_TOOLS:  # the text it writes names files it does not read
                    path = inp.get("file_path") or inp.get("notebook_path")
                    if not path:
                        continue
                    key = self.key(path)
                    self._mark(self.wrote, key, sid, date)
                    if name == "Write" and (key not in self.first_write or ts < self.first_write[key][0]):
                        self.first_write[key] = (ts, sid)
                    continue
                for key in self.named(inp, e.get("cwd")):
                    self._mark(self.read, key, sid, date)
                    self.read_by.setdefault(key, {}).setdefault(name, set()).add(sid)

    def loaded_in_sessions(self, key):
        sessions = self.loaded.get(key)
        if not sessions:
            return None
        return {"sessions": len(sessions), "first": min(self.loaded_first[key].values()),
                "last": max(sessions.values())}

    def sessions(self, key):
        r, w = self.read.get(key, {}), self.wrote.get(key, {})
        return {"read": len(r), "wrote": len(w), "last_read": max(r.values()) if r else None,
                "last_wrote": max(w.values()) if w else None,
                "read_by": {tool: len(s) for tool, s in self.read_by.get(key, {}).items()}}

    def created_in_session(self, key, git_created):
        if key not in self.first_write:
            return None
        ts, sid = self.first_write[key]
        if git_created and git_created[:10] < ts[:10]:
            return None  # git already had the file: that session overwrote it
        skills = sorted({n for s, n, _, _ in self.skills if s == sid})
        return {"session": sid, "date": ts[:10], "skills": skills}

    def skills_invoked(self):
        out = {}
        for sid, name, date, subagent in self.skills:
            entry = out.setdefault(name, {"name": name, "invocations": 0, "in_subagents": 0, "sessions": set(),
                                          "last": date})
            entry["invocations"] += 1
            entry["in_subagents"] += subagent
            entry["sessions"].add(sid)
            entry["last"] = max(entry["last"], date)
        return [dict(e, sessions=len(e["sessions"])) for _, e in sorted(out.items())]

    def window(self, retention_days):
        firsts = [f for f, _ in self.session_dates.values()]
        lasts = [last for _, last in self.session_dates.values()]
        return {"dirs": len(self.dirs), "files": self.files_read, "sessions": len(self.session_dates),
                "first": min(firsts) if firsts else None, "last": max(lasts) if lasts else None,
                "retention_days": retention_days}


def root_commits(path):
    try:
        return set(git(path, "rev-list", "--max-parents=0", "HEAD").split())
    except (subprocess.CalledProcessError, OSError):
        return set()


def other_checkouts(repo, history_of, home):
    """Other checkouts of this repo (sharing a first commit) that have Claude Code sessions: where
    the history of a copy made elsewhere lives. [{path, sessions}]"""
    root = os.path.join(home, ".claude", "projects")
    mine, seen = root_commits(repo), set()
    try:
        dirs = sorted(os.listdir(root))
    except OSError:
        dirs = []
    for d in dirs:
        # A project directory is named after the directory its sessions start in, so the first
        # cwd its first transcript records says which checkout it belongs to.
        try:
            names = sorted(n for n in os.listdir(os.path.join(root, d)) if n.endswith(".jsonl"))
            if not names:
                continue
            with open(os.path.join(root, d, names[0]), encoding="utf-8", errors="replace") as f:
                cwd = next((m.group(1) for m in map(CWD.search, f) if m), None)
        except OSError:
            continue
        if cwd and os.path.isdir(cwd):
            seen.add(cwd)
    checkouts = set()
    for cwd in sorted(seen):
        try:
            top = main_checkout(git(cwd, "rev-parse", "--show-toplevel").strip())
        except (subprocess.CalledProcessError, OSError):
            continue
        if top not in (history_of, repo) and mine & root_commits(top):
            checkouts.add(top)
    return [{"path": p, "sessions": len(Transcripts(p, home).session_dates)} for p in sorted(checkouts)]


def retention_days(home):
    try:
        with open(os.path.join(home, ".claude", "settings.json"), encoding="utf-8") as f:
            return json.load(f).get("cleanupPeriodDays")
    except (OSError, ValueError):
        return None


TOOL_TEXT = (".md", ".mdc", ".txt", ".mjs", ".js", ".cjs", ".ts", ".py", ".sh", ".json", ".yaml", ".yml")
TOOL_SKIP_DIRS = {"tests", "test", "node_modules", ".git", "__pycache__", ".changeset"}


def frontmatter_name(path):
    m = re.match(r"---\n(.*?)\n---", read_text(path) or "", re.S)
    name = m and re.search(r"^name:\s*['\"]?([^'\"\n]+)", m.group(1), re.M)
    return name.group(1).strip() if name else None


def walk_files(root):
    for dirpath, dirnames, names in os.walk(root, followlinks=True):
        dirnames[:] = sorted(d for d in dirnames if d not in TOOL_SKIP_DIRS)
        for name in sorted(names):
            if name.endswith(TOOL_TEXT) and name != "CHANGELOG.md":
                yield os.path.join(dirpath, name)


class Tools:
    """Installed skills, commands and agents, user-level, project-level and from plugins.
    Each tool is a set of text files that the agent reads when the tool runs."""

    def __init__(self, home, history_of, repo):
        self.home = home
        self.tools = {}  # id -> {"kind", "scope", "path", "files": [...], "own": set of basenames}
        self.roots = []
        claude = os.path.join(home, ".claude")
        for root, scope in ((os.path.join(claude, "skills"), "user"),
                            (os.path.join(home, ".agents", "skills"), "user"),
                            (os.path.join(repo, ".claude", "skills"), "project")):
            self._skills(root, scope, prefix="")
        for root, scope in ((claude, "user"), (os.path.join(repo, ".claude"), "project")):
            self._commands_agents(root, scope, prefix="")
        self.plugin_roots = []
        for name, root in self._plugins(home, history_of):
            self.plugin_roots.append(root)
            self._skills(os.path.join(root, "skills"), "plugin", prefix=name + ":")
            self._commands_agents(root, "plugin", prefix=name + ":")

    def _add(self, tool_id, kind, scope, path, files, own_root):
        if tool_id in self.tools:
            return
        own = set()
        for dirpath, _, names in os.walk(own_root, followlinks=True):
            own.update(names)
        self.tools[tool_id] = {"kind": kind, "scope": scope, "path": path, "files": files, "own": own}

    def _skills(self, root, scope, prefix):
        if not os.path.isdir(root):
            return
        self.roots.append(root)
        seen = set()
        for dirpath, dirnames, names in os.walk(root, followlinks=True):
            dirnames[:] = sorted(d for d in dirnames if d not in TOOL_SKIP_DIRS)
            if "SKILL.md" not in names:
                continue
            real = os.path.realpath(dirpath)
            if real in seen:
                continue
            seen.add(real)
            name = frontmatter_name(os.path.join(dirpath, "SKILL.md")) or os.path.basename(dirpath)
            self._add(prefix + name, "skill", scope, dirpath, list(walk_files(dirpath)), dirpath)

    def _commands_agents(self, root, scope, prefix):
        for sub, kind in (("commands", "command"), ("agents", "agent")):
            base = os.path.join(root, sub)
            if not os.path.isdir(base):
                continue
            self.roots.append(base)
            for path in walk_files(base):
                if not path.endswith(".md"):
                    continue
                rel = os.path.splitext(os.path.relpath(path, base))[0].replace(os.sep, ":")
                name = (frontmatter_name(path) if kind == "agent" else None) or rel
                self._add(prefix + name, kind, scope, path, [path], root if prefix else base)

    @staticmethod
    def _plugins(home, history_of):
        """(name, root) of plugins active for this project: installed for the user or for this
        project, and the account's synced plugins."""
        claude = os.path.join(home, ".claude")
        try:
            with open(os.path.join(claude, "settings.json"), encoding="utf-8") as f:
                enabled = json.load(f).get("enabledPlugins") or {}
        except (OSError, ValueError):
            enabled = {}
        out = []
        try:
            with open(os.path.join(claude, "plugins", "installed_plugins.json"), encoding="utf-8") as f:
                installed = json.load(f).get("plugins") or {}
        except (OSError, ValueError):
            installed = {}
        for key, entries in sorted(installed.items()):
            if enabled.get(key) is False:
                continue
            for e in entries:
                project = e.get("projectPath")
                if e.get("scope") == "user" or (project and (history_of == project or
                                                             history_of.startswith(project + "/"))):
                    out.append((key.split("@")[0], e.get("installPath", "")))
                    break
        synced = os.path.join(claude, "plugins", "synced")
        for manifest in sorted(glob_files(synced, ".claude-plugin/plugin.json", depth=4)):
            root = os.path.dirname(os.path.dirname(manifest))
            try:
                with open(manifest, encoding="utf-8") as f:
                    name = json.load(f).get("name") or os.path.basename(root)
            except (OSError, ValueError):
                name = os.path.basename(root)
            out.append((name, root))
        return out

    def doc_writers(self, invoked, shown):
        """The project's tools, and the tools invoked in this project, whose text tells the agent
        to write a doc, with the lines (writes_doc). invoked: {id: skills_invoked entry}."""
        out = []
        for tool_id, t in sorted(self.tools.items()):
            if t["scope"] != "project" and tool_id not in invoked:
                continue
            quotes = [{"file": shown(path), "line": n, "text": line.strip()[:300]}
                      for path in t["files"]
                      for n, line in enumerate((read_text(path) or "").splitlines(), 1)
                      if writes_doc(line, t["own"])]
            if quotes:
                out.append({"tool": tool_id, "kind": t["kind"], "scope": t["scope"],
                            "invocations": invoked[tool_id]["invocations"] if tool_id in invoked else 0,
                            "hits": len(quotes), "quotes": quotes[:3]})
        return out

    def matches(self, docs, folders, former):
        """Scan every tool file once for the doc paths, doc basenames, folders, and the names a
        doc had before a rename (former: {doc: [former paths]}).
        Returns {(tool id, target, via, token): [(file, line, text)]}."""
        by_base = {}
        for d in docs:
            by_base.setdefault(posixpath.basename(d), []).append(d)
        tokens = {}  # token -> [(target, via)]
        for base, paths in by_base.items():
            depth = min(p.count("/") for p in paths)
            tokens.setdefault(base, []).extend((p, "file") for p in paths if p.count("/") == depth)
        for d in docs:
            if "/" in d:
                tokens.setdefault(d, []).append((d, "file"))
        for d, olds in sorted(former.items()):
            for old in olds:
                for token in {old, posixpath.basename(old)}:
                    if token not in tokens or all(via == "former_path" for _, via in tokens[token]):
                        tokens.setdefault(token, []).append((d, "former_path"))
        folder_tokens = {f + "/": f for f in folders}
        folder_tokens.update({f: f for f in folders if "/" in f})
        alternatives = sorted(set(tokens) | set(folder_tokens), key=len, reverse=True)
        if not alternatives:
            return {}
        rx = re.compile(r"(?<![\w.\-/])(" + "|".join(map(re.escape, alternatives)) + r")(?![\w\-])")
        hits = {}
        for tool_id, tool in sorted(self.tools.items()):
            for path in tool["files"]:
                try:
                    text = read_text(path) if os.path.getsize(path) < 512_000 else None
                except OSError:  # a dead symlink
                    continue
                for n, line in enumerate((text or "").splitlines(), 1):
                    for m in rx.finditer(line):
                        token = m.group(1)
                        if posixpath.basename(token.rstrip("/")) in tool["own"] and token in tokens:
                            continue  # the tool bundles a file of that name: it names its own
                        targets = tokens.get(token) or [(folder_tokens[token], "folder")]
                        for target, via in targets:
                            hits.setdefault((tool_id, target, via, token), []).append(
                                (tilde(path, self.home), n, line.strip()[:300]))
        return hits


def glob_files(root, suffix, depth):
    """Files under root, at most depth levels down, whose path ends with suffix."""
    out = []
    for dirpath, dirnames, names in os.walk(root):
        if dirpath[len(root):].count(os.sep) >= depth:
            dirnames[:] = []
        for name in names:
            p = os.path.join(dirpath, name)
            if p.endswith(suffix):
                out.append(p)
    return out


def cursor_conversations(home, history_of):
    """{conversation id: text} from Cursor's agent transcripts for this project, or None."""
    root = os.path.join(home, ".cursor", "projects", slug(history_of).lstrip("-"), "agent-transcripts")
    if not os.path.isdir(root):
        return None
    out = {}
    for dirpath, _, names in os.walk(root):
        for name in sorted(names):
            if name.endswith(".jsonl"):
                cid = os.path.relpath(dirpath, root)
                out[cid] = out.get(cid, "") + (read_text(os.path.join(dirpath, name)) or "")
    return out


DUP_MIN_WORDS = 12
IMPORT_HOPS = 4  # Claude Code expands imports up to four hops (memory page)
WORD = re.compile(r"\w+")


def tokens(text):
    """[(word, line, start, end)], words lowercased."""
    out, line, next_nl = [], 1, text.find("\n")
    for m in WORD.finditer(text):
        while next_nl != -1 and next_nl < m.start():
            line += 1
            next_nl = text.find("\n", next_nl + 1)
        out.append((m.group().lower(), line, m.start(), m.end()))
    return out


def duplicates(texts):
    """Passages of at least DUP_MIN_WORDS words shared verbatim by two or more files.
    texts: {(scope, path): text}. Case, punctuation and markup are ignored."""
    keys = sorted(texts)
    words = [tokens(texts[k]) for k in keys]
    window = DUP_MIN_WORDS
    index = {}
    for fi, toks in enumerate(words):
        for i in range(len(toks) - window + 1):
            index.setdefault(tuple(t[0] for t in toks[i:i + window]), []).append((fi, i))
    pairs = {}  # (file a, file b) -> {(start in a, start in b)} of shared n-grams
    for occ in index.values():
        if len({fi for fi, _ in occ}) < 2:
            continue
        for x, (fa, ia) in enumerate(occ):
            for fb, ib in occ[x + 1:]:
                if fa != fb:
                    pairs.setdefault((fa, fb), set()).add((ia, ib))
    passages = {}  # words of a maximal shared run -> {(file, start)}
    for (fa, fb), matches in pairs.items():
        for ia, ib in matches:
            if (ia - 1, ib - 1) in matches:
                continue  # inside a run that starts earlier
            n = 0
            while (ia + n + 1, ib + n + 1) in matches:
                n += 1
            run = tuple(t[0] for t in words[fa][ia:ia + n + window])
            passages.setdefault(run, set()).update({(fa, ia), (fb, ib)})
    def covered(run, occ):
        """Every occurrence overlaps one of a passage found in more files (a word of context
        that two of them happen to share does not make a separate passage)."""
        return any(len(o2) > len(occ) and all(
            any(fi == f2 and i < i2 + len(r2) and i2 < i + len(run) for f2, i2 in o2) for fi, i in occ)
            for r2, o2 in passages.items())

    out = []
    for run, occ in passages.items():
        if covered(run, occ):
            continue
        fa, ia = min(occ)
        first, last = words[fa][ia], words[fa][ia + len(run) - 1]
        out.append({"words": len(run),
                    "text": " ".join(texts[keys[fa]][first[2]:last[3]].split())[:300],
                    "occurrences": [{"path": keys[fi][1], "scope": keys[fi][0], "line": words[fi][i][1]}
                                    for fi, i in sorted(occ, key=lambda o: (keys[o[0]][1], o[1]))]})
    return sorted(out, key=lambda d: (-d["words"], d["text"]))


def user_instruction_files(home, transcripts):
    """~/.claude/CLAUDE.md, the user files the transcripts show loaded, and their imports."""
    found = set()
    frontier = [os.path.join(home, ".claude", "CLAUDE.md"), *sorted(transcripts.user_files)]
    for _ in range(IMPORT_HOPS + 1):  # the files themselves, then their imports
        nxt = []
        for path in frontier:
            if path in found or not os.path.isfile(path):
                continue
            found.add(path)
            for _, token in imports_in(read_text(path) or ""):
                target = home + token[1:] if token.startswith("~/") else \
                    os.path.join(os.path.dirname(path), token)
                nxt.append(os.path.normpath(target))
        frontier = nxt
    return sorted(found)


class Context:
    """What lies outside the repo and does not change between two states of it."""

    def __init__(self, repo, history_of):
        self.repo, self.history_of = repo, history_of
        self.home = os.path.realpath(os.path.expanduser("~"))
        self.transcripts = Transcripts(history_of, self.home)
        self.tools = Tools(self.home, history_of, repo)
        self.cursor = cursor_conversations(self.home, history_of)
        memory_dir = self.transcripts.memory_dir
        self.memory = DirTree(memory_dir) if os.path.isdir(memory_dir) else None
        self.user_files = user_instruction_files(self.home, self.transcripts)


def analyse(tree, ctx, with_history):
    """Files, pointers, texts and tool names for one state of the repo."""
    repo, home, transcripts = ctx.repo, ctx.home, ctx.transcripts
    histories = [(None, [])] * len(tree.docs)
    if with_history:
        with ThreadPoolExecutor(max_workers=8) as pool:
            histories = list(pool.map(lambda p: history(repo, p), tree.docs))
    files, pointers, texts = [], set(), {}
    agents_condition_met = not claude_md_above(ctx.history_of, tree)
    records = decision_records(tree.docs)

    for path, (hist, commit_dates) in zip(tree.docs, histories):
        text = tree.read(path)
        link = tree.links.get(path)
        unresolved = []
        if not link:  # a symlinked doc is its target's text: the target carries its passages and refs
            texts[("repo", path)] = text
            named, unresolved = scan_refs(text, lambda t, p=path: resolve(t, p, tree), tree.exists,
                                          expands_imports(path))
            pointers |= {(path, to, kind, n) for n, to, kind in named if to != path and to in tree.docs}
            pointers |= citations(path, text, records, named)
            for pattern in frontmatter_patterns(text):
                rx = glob_regex(pattern)
                pointers |= {(path, d, "rule_paths", 0) for d in tree.docs if rx.match(d) and d != path}
        key = ("repo", path)
        files.append({"path": path, "scope": "repo", "tracked": True, "symlink_to": link,
                      **size(text), "history": hist,
                      "unresolved_refs": unresolved, "issue_refs": len(ISSUE.findall(text)),
                      "dates": len(DATE.findall(text)), "dated": dated(path, text, commit_dates),
                      "harness": harness_rules(path, text, tree, agents_condition_met),
                      "loaded_in_sessions": transcripts.loaded_in_sessions(key),
                      "sessions": transcripts.sessions(key),
                      "created_in_session": transcripts.created_in_session(
                          key, hist and hist["created"]["date"])})
    propagate_imports({f["path"]: f for f in files}, pointers)

    memory = ctx.memory
    for rel in memory.docs if memory else []:
        abspath = os.path.join(memory.root, rel)
        path, text = tilde(abspath, home), memory.read(rel)
        texts[("auto_memory", path)] = text

        def resolver(target, rel=rel):
            hit = resolve(target, rel, memory)
            return tilde(os.path.join(memory.root, hit), home) if hit else resolve(target, "", tree)

        named, unresolved = scan_refs(text, resolver, tree.exists, False)
        pointers |= {(path, to, kind, n) for n, to, kind in named if to != path}
        pointers |= citations(path, text, records, named)
        key = ("abs", abspath)
        harness = [rule("claude-code", "session_start",
                        "The auto-memory index: its first 200 lines or 25KB load when a session starts.",
                        CC_MEMORY)] if rel == "MEMORY.md" else []
        files.append({"path": path, "scope": "auto_memory", "tracked": False, "symlink_to": None, **size(text),
                      "history": None, "unresolved_refs": unresolved,
                      "issue_refs": len(ISSUE.findall(text)), "dates": len(DATE.findall(text)),
                      "harness": harness, "loaded_in_sessions": transcripts.loaded_in_sessions(key),
                      "sessions": transcripts.sessions(key),
                      "created_in_session": transcripts.created_in_session(key, None)})

    for abspath in ctx.user_files:
        path, text = tilde(abspath, home), read_text(abspath) or ""
        texts[("user", path)] = text
        files.append({"path": path, "scope": "user", **size(text),
                      "harness": [rule("claude-code", "session_start",
                                       "User instructions, loaded in every session of every project.",
                                       CC_MEMORY)]})

    folders = sorted(folder_units(tree))
    named = {}  # target -> [named_by entry]
    former = {f["path"]: f["history"]["former_paths"] for f in files
              if f["scope"] == "repo" and f["history"] and f["history"]["former_paths"]}
    for (tool_id, target, via, token), quotes in sorted(ctx.tools.matches(tree.docs, folders, former).items()):
        named.setdefault(target, []).append({
            "tool": tool_id, "via": via, "token": token, "hits": len(quotes),
            "quotes": [{"file": f, "line": n, "text": t} for f, n, t in quotes[:3]]})
    inbound = {}  # target -> the doc files that point to it (a rule's paths: match is no pointer)
    for f, t, kind, _ in pointers:
        if kind != "rule_paths":
            inbound.setdefault(t, set()).add(f)
    for f in files:
        if f["scope"] == "user":
            continue
        # A tool that names a folder (`docs/`) is evidence about the folder, kept in folders[]:
        # it does not show that the tool reads any one file under it.
        f["named_by_tools"] = named.get(f["path"], []) if f["scope"] == "repo" else []
        f["cursor_conversations"] = None if ctx.cursor is None else sum(
            1 for text in ctx.cursor.values() if mentions(text, f["path"]))
        f["pointed_to_by"] = len(inbound.get(f["path"], ()))
        readers = [e for e in f["named_by_tools"] if e["via"] != "former_path"]
        f["orphan"] = not (f["harness"] or readers or f["pointed_to_by"]
                           or f["loaded_in_sessions"] or f["sessions"]["read"] or f["cursor_conversations"])
    return {"files": sorted(files, key=lambda f: (f["scope"], f["path"])), "pointers": pointers,
            "texts": texts, "named": named, "folders": folders}


def inventory(repo, history_of):
    ctx = Context(repo, history_of)
    home, transcripts, tools = ctx.home, ctx.transcripts, ctx.tools
    tree = Tree(repo)
    state = analyse(tree, ctx, with_history=True)
    files, named = state["files"], state["named"]
    used = {e["tool"] for entries in named.values() for e in entries}
    invoked = {s["name"]: s for s in transcripts.skills_invoked()}
    tools_out = {}
    for tool_id in sorted(used):
        t, inv = tools.tools[tool_id], invoked.get(tool_id)
        tools_out[tool_id] = {"kind": t["kind"], "scope": t["scope"], "path": tilde(t["path"], home),
                              "invocations": inv["invocations"] if inv else 0,
                              "in_subagents": inv["in_subagents"] if inv else 0,
                              "sessions": inv["sessions"] if inv else 0,
                              "last_invoked": inv["last"] if inv else None}
    folders_out = []
    for d in state["folders"]:
        inside = [f for f in files if f["scope"] == "repo" and f["path"].startswith(d + "/")]
        folders_out.append({"path": d, "files": len(inside), "words": sum(f["words"] for f in inside),
                            "other_files": sorted(p for p in tree.files
                                                  if posixpath.dirname(p) == d and not is_doc(p)),
                            "named_by_tools": named.get(d, [])})
    return {
        "schema": SCHEMA,
        "repo": repo,
        "head": git(repo, "rev-parse", "HEAD").strip(),
        "history_of": history_of,
        "auto_memory_dir": tilde(ctx.memory.root, home) if ctx.memory else None,
        "files": files,
        "folders": folders_out,
        "pointers": [{"from": f, "to": t, "kind": k, "line": n} for f, t, k, n in sorted(state["pointers"])],
        "duplicates": duplicates(state["texts"]),
        "memory_refs": memory_refs(repo, ctx.memory, home),
        "global_refs": global_refs(repo, tree, state["texts"], ctx.user_files, home),
        "tools": tools_out,
        "doc_writers": doc_writers(ctx, tree, invoked),
        "skills_invoked": transcripts.skills_invoked(),
        "limits": {"untracked_doc_files": [p for p in tree.untracked if is_doc(p)],
                   "transcripts": transcripts.window(retention_days(home)),
                   "other_checkouts": other_checkouts(repo, history_of, home),
                   "logs": harness_logs(files, transcripts, ctx.cursor, home),
                   "tool_roots": sorted(tilde(r, home) for r in tools.roots),
                   "notes": NOTES},
    }


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


WRITE_VERB = re.compile(r"(?<![\w-])(?:write|writes|create|creates|save|saves|append|appends|record|"
                        r"records)(?![\w-])", re.I)
DOC_TARGET = re.compile(r"[\w<>{}*./-]*\.(?:md|mdx|rst|adoc)\b|`[^`\s/][^`\s]*/[^`\s]*`")  # not `/command`
WRITE_REACH = 60  # characters between the verb and its object: "write the report to `docs/…`"


def writes_doc(line, bundled):
    """Whether a line of a tool tells the agent to write a doc file: a write verb, then, close
    after it, a doc path or a backticked folder that is neither a link target nor a file the
    tool bundles."""
    for verb in WRITE_VERB.finditer(line):
        text = re.sub(r"\]\([^)]*\)", "]", line[verb.end():])  # a link is something to read
        if any(m.start() <= WRITE_REACH and posixpath.basename(m.group().strip("`").rstrip("/")) not in bundled
               for m in DOC_TARGET.finditer(text)):
            return True
    return False


def doc_writers(ctx, tree, invoked):
    """Mechanisms of the harness that write docs on their own: auto memory, hooks, and tools
    whose text writes a doc file. Hooks are all listed, with their command, for the agent to judge."""
    repo, home = ctx.repo, ctx.home

    def shown(path):
        return os.path.relpath(path, repo) if path.startswith(repo + "/") else tilde(path, home)

    # Settings, lowest precedence first (vendor settings page): user, project, local project.
    # The memory page gives no order between `autoMemoryEnabled` and CLAUDE_CODE_DISABLE_AUTO_MEMORY:
    # the setting follows precedence, and the variable, wherever it is set, turns memory off.
    settings = [os.path.join(home, ".claude", "settings.json"), os.path.join(repo, ".claude", "settings.json"),
                os.path.join(repo, ".claude", "settings.local.json")]
    enabled, set_by, disabled_by = True, None, None  # on by default (memory page)
    hooks = []
    for path in settings:
        data = read_json(path)
        env = data.get("env") if isinstance(data.get("env"), dict) else {}
        if isinstance(data.get("autoMemoryEnabled"), bool):
            enabled, set_by = data["autoMemoryEnabled"], shown(path)
        if env.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY") in ("1", "true", 1, True):
            disabled_by = disabled_by or shown(path)
        hooks += settings_hooks(data, shown(path))
    if os.environ.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY") in ("1", "true"):
        disabled_by = disabled_by or "environment"
    if disabled_by:
        enabled, set_by = False, disabled_by
    for root in ctx.tools.plugin_roots:
        path = os.path.join(root, "hooks", "hooks.json")
        hooks += settings_hooks(read_json(path), shown(path))
    memory = ctx.memory
    in_repo = set_by and not set_by.startswith("~") and set_by != "environment"
    auto_memory = {"enabled": enabled, "set_by": set_by, "tracked": set_by in tree.files if in_repo else None,
                   "dir": tilde(memory.root, home) if memory else None,
                   "files": len(memory.docs) if memory else 0, "source": CC_MEMORY}
    return {"auto_memory": auto_memory, "hooks": hooks, "tools": ctx.tools.doc_writers(invoked, shown)}


def settings_hooks(data, source):
    """[{source, event, matcher, command}] for the command hooks of a settings or hooks.json file."""
    out = []
    events = data.get("hooks") if isinstance(data.get("hooks"), dict) else {}
    for event, groups in sorted(events.items()):
        for group in groups if isinstance(groups, list) else []:
            if not isinstance(group, dict):
                continue
            for h in group.get("hooks") or []:
                if isinstance(h, dict) and h.get("command"):
                    out.append({"source": source, "event": event, "matcher": group.get("matcher", ""),
                                "command": h["command"]})
    return out


def measure_state(tree, ctx, ref):
    state = analyse(tree, ctx, with_history=False)
    repo_files = [f for f in state["files"] if f["scope"] == "repo"]
    texts = [f for f in state["files"] if f["scope"] != "user" and not f["symlink_to"]]  # a link counts once
    dups = duplicates(state["texts"])
    return {
        "ref": ref,
        "words": {f["path"]: f["words"] for f in repo_files if not f["symlink_to"]},
        "always_loaded_words": sum(f["words"] for f in texts
                                   if any(r["when"] == "session_start" for r in f["harness"])),
        "duplicated_passages": len(dups),
        "duplicated_words": sum(d["words"] * (len(d["occurrences"]) - 1) for d in dups),
        "unresolved_refs": sum(len(f["unresolved_refs"]) for f in repo_files),
        "orphans": [f["path"] for f in repo_files if f["orphan"]],
    }


def measure(repo, history_of, base):
    ctx = Context(repo, history_of)
    sha = git(repo, "rev-parse", base).strip()
    return {"schema": SCHEMA, "base": measure_state(Tree(repo, sha), ctx, sha),
            "worktree": measure_state(Tree(repo, with_untracked=True), ctx, "worktree")}


NOTES = [
    "A name that a skill bundles in its own directory does not count as that skill naming the "
    "project's file.",
    "A basename mentioned alone (`README.md`) is attributed to the shallowest doc files of that name.",
    "Tool usage counts exact ids: a plugin skill invoked by its bare name is listed in skills_invoked "
    "under that bare name.",
    "Transcripts are matched to the project by the working directory they record; sessions launched "
    "in a worktree outside .claude/worktrees/ are not mapped back to repo paths.",
    "The auto-memory directory is located from the main checkout's path; a relocated "
    "autoMemoryDirectory is not followed.",
    "Doc files under dependency folders (node_modules, vendor, bower_components, .venv, venv, "
    "site-packages, third_party, Pods, Carthage) are left out. In installed tools, tests folders and "
    "CHANGELOG.md are not scanned.",
]


def parent_dirs(path):
    d = posixpath.dirname(path)
    while d:
        yield d
        d = posixpath.dirname(d)


def grep_repo(repo, tokens):
    """[(path, line, token, text before it)] for each whole-token occurrence of the tokens in the
    repo's tracked text files, code included."""
    if not tokens:
        return []
    argv = ["git", "-C", repo, "grep", "-n", "-I", "--null", "-F"]
    for t in sorted(tokens):
        argv += ["-e", t]
    out = subprocess.run(argv, capture_output=True, encoding="utf-8", errors="replace").stdout
    rx = re.compile(r"(?<![\w.\-/])(" + "|".join(map(re.escape, sorted(tokens, key=len, reverse=True)))
                    + r")(?![\w\-])")
    hits = []
    for record in out.splitlines():
        path, n, text = record.split("\0", 2)  # --null with -n: path NUL line NUL text
        hits += [(path, int(n), m.group(1), text[:m.start()]) for m in rx.finditer(text)]
    return hits


GLOBAL_WORD = re.compile(r"\bglobal\b", re.I)


def global_refs(repo, tree, texts, user_files, home):
    """Lines of the repo that hand something to the user's global files: an `@~/` import
    (`import`), a global file's full path (`path`), its name when no repo file has that name
    (`name`), or a name the repo shares (`CLAUDE.md`) after the word "global" (`global`).
    One per line and target, in that order of preference."""
    repo_names = {posixpath.basename(p) for p in tree.files}
    tokens = {}  # token -> (global file, via)
    for abspath in user_files:
        path = tilde(abspath, home)
        tokens[path] = (path, "path")
        base = os.path.basename(abspath)
        tokens.setdefault(base, (path, "global" if base in repo_names else "name"))
    found = []
    for src, n, token, before in grep_repo(repo, tokens):
        to, via = tokens[token]
        if via != "global" or GLOBAL_WORD.search(before):
            found.append({"from": src, "line": n, "to": to, "token": token, "via": via})
    for (scope, src), text in texts.items():
        if scope == "repo" and expands_imports(src):
            found += [{"from": src, "line": n, "to": t, "token": "@" + t, "via": "import"}
                      for n, t in imports_in(text) if t.startswith("~/")]
    rank = ["import", "path", "name", "global"]
    best = {}
    for r in sorted(found, key=lambda r: rank.index(r["via"])):
        best.setdefault((r["from"], r["line"], r["to"]), r)
    return [best[k] for k in sorted(best)]


def memory_refs(repo, memory, home):
    """References from the repo to files of its auto memory, by file name or by front-matter
    name, one per line and target: the longest token wins (`a_b.md` over `a_b`)."""
    if not memory:
        return []
    tokens = {}  # token -> (memory path, via)
    for rel in memory.docs:
        path = tilde(os.path.join(memory.root, rel), home)
        base = posixpath.basename(rel)
        tokens[base] = (path, "file")
        stem, name = base.rsplit(".", 1)[0], frontmatter_name(os.path.join(memory.root, rel))
        # A one-word stem or name (`MEMORY`, `testing`) is an ordinary word: only the file name counts.
        if re.search(r"[-_]", stem):
            tokens.setdefault(stem, (path, "file"))
        if name and re.search(r"[-_]", name):
            tokens.setdefault(name, (path, "name"))
    best = {}
    for src, n, token, _ in grep_repo(repo, tokens):
        to, via = tokens[token]
        if len(token) > len(best.get((src, n, to), {}).get("token", "")):
            best[(src, n, to)] = {"from": src, "line": n, "to": to, "token": token, "via": via}
    return [best[k] for k in sorted(best)]


def folder_units(tree):
    """The folders that are units: every directory holding doc files, and every directory inside
    a docs area, a directory whose files are at least half doc files. A folder of images among
    the docs is a unit; the asset folders of a code folder that holds one README are not."""
    holding = {d for p in tree.docs for d in parent_dirs(p)}
    counts = {}  # directory -> [doc files, other files] under it, among the files the tree lists
    for p in tree.listed:
        for d in parent_dirs(p):
            counts.setdefault(d, [0, 0])[0 if is_doc(p) else 1] += 1
    areas = {d for d in holding if counts[d][0] >= counts[d][1]}
    return holding | {d for d in counts if any(a in areas for a in parent_dirs(d))}


def mentions(text, path):
    token = path if "/" in path and not path.startswith("~") else posixpath.basename(path)
    return re.search(r"(?<![\w.\-/])" + re.escape(token) + r"(?![\w\-])", text) is not None


def harness_logs(files, transcripts, cursor, home):
    """For each harness that reads a file of the repo: can the run see that harness's usage?"""
    harnesses = {r["harness"] for f in files if f["scope"] == "repo" for r in f["harness"]} - {"github"}
    out = []
    for h in sorted(harnesses):
        if h == "claude-code":
            status, note = ("read", "Transcripts read in full.") if transcripts.session_dates else \
                ("absent", "No Claude Code transcript found for this project.")
        elif h == "cursor":
            status, note = ("counts_only", "Conversation counts and file mentions only; Cursor does not "
                            "record which instruction files loaded.") if cursor is not None else \
                ("absent", "No Cursor agent transcripts found for this project.")
        elif h == "codex":
            status, note = ("unreadable", "~/.codex exists; its logs are not read.") \
                if os.path.isdir(os.path.join(home, ".codex")) else ("absent", "No ~/.codex directory.")
        elif h == "gemini-cli":
            status, note = ("unreadable", "~/.gemini exists; its logs are binary and not read.") \
                if os.path.isdir(os.path.join(home, ".gemini")) else ("absent", "No ~/.gemini directory.")
        else:
            status, note = "absent", "No local log of this harness is known to the inventory."
        out.append({"harness": h, "status": status, "note": note})
    return out


CODE_TOKEN = re.compile(r"[^\s\"'`,;()\[\]{}<>]+")
PLAIN_WORD = re.compile(r"^[a-z]+$")
RUN_TOKENS = 3  # why 3, and why identifiers too: see shared_code in ../references/inventory-output.md


def code_chunks(text):
    """(line number, code) for each inline code span and each line of a fenced block."""
    fenced = False
    for n, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            fenced = not fenced
        elif fenced:
            yield n, line
        else:
            for m in BACKTICK.finditer(line):
                yield n, m.group(1)


def code_tokens(chunk):
    return [t for t in (t.strip(".:;,!?*").lower() for t in CODE_TOKEN.findall(chunk)) if t]


def is_identifier(token, doc_folders):
    """A token that names something on its own: not punctuation or a number, not a plain word
    (`select`), not a one-letter flag (`-f`), not a doc file or a docs folder (the pointer graph
    has those)."""
    if not re.search(r"[a-z]", token) or PLAIN_WORD.match(token):
        return False
    if token.startswith("-") and not token.startswith("--"):
        return False
    bare = token.split("#")[0].rstrip("/")
    return not (bare.endswith(DOC_EXTENSIONS) or bare in doc_folders)


def shared_code(texts, doc_folders):
    """Identifiers, and runs of RUN_TOKENS or more code tokens, that two or more of the files
    hold, grouped by the set of files that hold them. texts: {path: text}."""
    idents, grams, chunks = {}, {}, []  # grams: window -> {(path, line, chunk, position)}
    for path, text in sorted(texts.items()):
        for n, chunk in code_chunks(text):
            toks = code_tokens(chunk)
            chunks.append(toks)
            for t in toks:
                if is_identifier(t, doc_folders):
                    idents.setdefault(t, set()).add((path, n))
            for i in range(len(toks) - RUN_TOKENS + 1):
                grams.setdefault(tuple(toks[i:i + RUN_TOKENS]), set()).add((path, n, len(chunks), i))

    def files(occ):
        return frozenset(o[0] for o in occ)

    def window(toks, i):
        return grams[tuple(toks[i:i + RUN_TOKENS])]

    def continues(occ, nxt):
        """Every occurrence of a window is followed by the next one, and only there."""
        return {(p, n, c, i + 1) for p, n, c, i in occ} == nxt

    terms = {t: occ for t, occ in idents.items() if len(files(occ)) > 1}
    for toks in chunks:  # merge shared windows that follow each other wherever they occur
        i = 0
        while i <= len(toks) - RUN_TOKENS:
            occ = window(toks, i)
            if len(files(occ)) < 2:
                i += 1
                continue
            j = i
            while j + 1 <= len(toks) - RUN_TOKENS and continues(window(toks, j), window(toks, j + 1)):
                j += 1
            terms.setdefault(" ".join(toks[i:j + RUN_TOKENS]), set()).update((p, n) for p, n, _, _ in occ)
            i = j + 1
    groups = {}
    for term, occ in terms.items():
        groups.setdefault(files(occ), []).append(
            {"term": term, "occurrences": [{"path": p, "line": n} for p, n in sorted(occ)]})
    return [{"files": sorted(fs), "terms": sorted(ts, key=lambda t: t["term"])}
            for fs, ts in sorted(groups.items(), key=lambda g: (-len(g[0]), sorted(g[0])))]


def repeats(repo, history_of, paths):
    """What the given doc files repeat among themselves, verbatim or around the same code."""
    home = os.path.realpath(os.path.expanduser("~"))
    memory_dir = tilde(auto_memory_dir(history_of, home), home)
    tree = Tree(repo, with_untracked=True)
    chosen, same_file, real = {}, [], {}
    for path in paths:
        inside = path.startswith("~/") or not (os.path.isabs(path)
                                               or posixpath.normpath(path).startswith(".."))
        if not (inside and is_doc(path) and os.path.isfile(absolute(path, repo, home))):
            sys.exit(f"inventory.py repeats: not a doc file of the repo or of ~/: {path}")
    for path in sorted(set(paths), key=lambda p: (os.path.islink(absolute(p, repo, home)), p)):
        abspath = absolute(path, repo, home)
        target = os.path.realpath(abspath)
        if target in real:
            same_file.append({"path": path, "same_as": real[target]})
            continue
        real[target] = path
        chosen[path] = read_text(abspath) or ""
    scope = {p: "repo" if not p.startswith("~/") else
             "auto_memory" if p.startswith(memory_dir + "/") else "user" for p in chosen}
    doc_folders = {d for p in tree.docs for d in parent_dirs(p)}
    return {"schema": SCHEMA, "repo": repo, "files": sorted(chosen), "same_file": same_file,
            "duplicates": duplicates({(scope[p], p): t for p, t in chosen.items()}),
            "shared_code": shared_code(chosen, doc_folders)}


def absolute(path, repo, home):
    return home + path[1:] if path.startswith("~/") else os.path.join(repo, path)


def main_checkout(repo):
    """The main checkout of the repo, whose path names its transcripts and auto-memory (a worktree
    shares them, as the vendor documents)."""
    common = git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    return os.path.realpath(os.path.dirname(common)) if os.path.basename(common) == ".git" else repo


def main(argv):
    command = argv[0] if argv and argv[0] in ("measure", "repeats") else None
    ap = argparse.ArgumentParser(prog="inventory.py" + (f" {command}" if command else ""),
                                 description=__doc__.splitlines()[0])
    ap.add_argument("repo", help="the audited repo (read only)")
    ap.add_argument("--history-of", help="path whose transcripts and auto-memory to read, for a copy "
                    "of a repo made elsewhere")
    if command == "measure":
        ap.add_argument("--base", required=True, help="commit to compare the working tree with")
    if command == "repeats":
        ap.add_argument("paths", nargs="+", help="doc files to compare, as files[].path writes them")
    a = ap.parse_args(argv[1:] if command else argv)
    repo = git(os.path.realpath(a.repo), "rev-parse", "--show-toplevel").strip()
    history_of = os.path.realpath(a.history_of) if a.history_of else main_checkout(repo)
    if command == "measure":
        result = measure(repo, history_of, a.base)
    elif command == "repeats":
        result = repeats(repo, history_of, a.paths)
    else:
        result = inventory(repo, history_of)
    json.dump(result, sys.stdout, indent=1, sort_keys=True, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1:])
