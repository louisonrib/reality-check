# What `inventory.py` writes

`scripts/inventory.py <repo> [--history-of <path>]` prints one JSON document on stdout. It only reads. Lists are sorted and nothing depends on the clock, so two runs on the same inputs give the same output.

`scripts/inventory.py measure <repo> --base <sha> [--history-of <path>]` prints the before/after measures (last section).

`scripts/inventory.py repeats <repo> <path>... [--history-of <path>]` prints what the named doc files repeat among themselves (section `repeats`).

A field the run could not establish is `null` or an empty list, and `limits` says why. **An empty reader list means "none found", never "nobody reads it".**

## Top level

| Field | Meaning |
|---|---|
| `schema` | Format version, `1`. |
| `repo` | Absolute path of the audited repo (its git root). |
| `head` | Commit the run read. |
| `history_of` | Path whose transcripts and auto-memory were read: `--history-of` if given, else the repo's main checkout (run from a worktree, that is the checkout the worktree belongs to). |
| `auto_memory_dir` | The repo's Claude Code auto-memory directory (`~/`-prefixed), or `null` if it does not exist. |
| `files` | One entry per doc file (below). |
| `folders` | One entry per folder unit (below). |
| `pointers` | Every edge "file A names file B" found in the doc files. |
| `duplicates` | Passages repeated verbatim across files. |
| `global_refs` | Lines of the repo that hand something to one of the user's global files (`scope: user`): `{from, line, to, token, via}`. `via`: `import` (an `@~/…` import in a file that expands imports; `to` may be a file the inventory does not list), `path` (the file's `~/` path), `name` (its file name, when no repo file has that name: `~/.claude/RULES.md` named `RULES.md`), `global` (a name the repo shares, such as `CLAUDE.md`, after the word "global" on the line). Each is a rule whose wording lives in the global file. |
| `memory_refs` | References from the repo's tracked text files, code included, to auto-memory files: `{from, line, to, token, via}`, `via: file` for the file name (or its stem, when it holds `-` or `_`), `via: name` for the `name:` of the file's front matter (a `[[name]]` link, a comment). A one-word stem or name is not matched. The pointer graph does not hold these: emptying or moving a memory file breaks each of them. |
| `tools` | Installed skills, commands and agents that name at least one doc file or folder, keyed by tool id. |
| `doc_writers` | Mechanisms of the harness that write docs with no rule in the docs asking for it (below). |
| `skills_invoked` | Every skill or slash command invoked in this project's transcripts, used or not by a doc. |
| `limits` | What the run could not see. |

## `files[]`

| Field | Meaning |
|---|---|
| `path` | Repo-relative for `scope: repo`; `~/`-prefixed absolute path for `auto_memory` and `user`. Paths are unique across scopes. |
| `scope` | `repo` (tracked doc file), `auto_memory` (a file of the repo's auto-memory), or `user` (the user's global instruction files and their imports, as loaded in the transcripts or found at `~/.claude/CLAUDE.md`). `user` files are listed only so `duplicates` can show what the project repeats from them; they carry `path`, `scope`, `lines`, `words` and `harness` only. |
| `tracked` | `true` for `repo` files, `false` for `auto_memory` files. |
| `symlink_to` | For a doc that is a symbolic link to another file of the repo (an `AGENTS.md` linked to `CLAUDE.md`), that file's path; otherwise `null`. A link reads as its target, at a commit as in the working tree. Its size is its target's; its passages, references and pointers are counted under the target only. |
| `lines`, `words` | Size of the file now. `words` counts whitespace-separated tokens, as `wc -w`. |
| `history` | Git history with renames followed, or `null` outside git: `commits`, `lines_added`, `lines_deleted`, `former_paths` (names the file had before a rename, `[]` if none), `created` (`sha`, `date`, `author`, `subject`, `body`: the creating commit's whole message body; a squash merge lists there every commit it merged, and the one that names the file can come late) and `last` (`sha`, `date`, `subject`). |
| `harness` | Vendor-documented loading rules that apply to this path (below). Empty when no harness or platform reads the file by its name or location. |
| `loaded_in_sessions` | From Claude Code transcripts: in how many sessions this file was loaded as an instruction file, with the `first` and `last` dates it loaded. `null` when never observed. |
| `named_by_tools` | Installed tools that name this file (`via: file`), or a name it had before a rename (`via: former_path`; such a tool looks for a file that is no longer there, so it is not a reader). Each: `tool` (an id in `tools`), `token` (what matched), `hits` (number of matching lines) and `quotes` (up to 3 `{file, line, text}`). A tool that names one of the file's folders is listed under that folder in `folders[]`, not here: a skill that mentions `docs/` for its own purpose does not read every file under it. Only `repo` files are matched; `auto_memory` files carry `[]`. |
| `sessions` | From transcripts: `read` (number of sessions in which a tool's input names the file's path: a `Read`, a shell command, a search, a brief to a subagent; the text a `Write` or an `Edit` writes does not count), `wrote` (number of sessions that wrote or edited it with `Write`, `Edit`, `MultiEdit` or `NotebookEdit`), `last_read`, `last_wrote` (dates or `null`), and `read_by` (`{tool: sessions}`, each tool that named it). A path is absolute, under `~/` or `$HOME/`, or relative; a relative one resolves against the last `cd` before it in the same shell command, else the session's folder. Naming is a candidate read: a `git add`, a `sed -i` or a question to the user names the file too. |
| `cursor_conversations` | Number of Cursor agent conversations of this project that mention the file's path (its name alone for a root file); `null` when no Cursor transcript exists for the project. |
| `created_in_session` | The earliest transcript session that wrote the file with the Write tool, unless git already had the file before that day: `session`, `date`, `skills` (skills invoked in that session). `null` when the creation predates the transcripts or happened outside Claude Code. |
| `unresolved_refs` | Links, backticked paths and `@` imports in this file that resolve to nothing: `{line, ref, kind}` with `kind` in `link`, `backtick`, `import`. A reference resolves against the file's folder, the repo root, then any repo path ending with it (`app.py` for `src/app.py`). Fenced code blocks are skipped. A staleness signal to check, not a verdict. |
| `issue_refs` | Count of issue/PR references (`#123`, `/pull/123`, `/issues/123`). |
| `dates` | Count of ISO dates (`2026-10-21`). |
| `dated` | The date the doc gives itself, or `null`: `date`, `source` (`name` for a date in the file name, `header` for a labelled line among the first 10, such as `Date: …` or `**Status:** Accepted, …`), `line` (`null` for `name`), `commits_after` (commits to the file on a later day, its creating commit aside) and `last_after` (the latest of those days). A dated doc with commits after its date has been edited since: neither left as it was written nor declared living. |
| `pointed_to_by` | Number of other doc files that point to this one (`pointers` whose `to` is this file, `rule_paths` aside, counted by distinct `from`). The figure to quote for "what points to it": `pointers` holds one entry per line, so a file named on several lines counts several times there. |
| `orphan` | `true` when the file has no harness rule, no tool naming it (`former_path` and a folder do not count), `pointed_to_by` 0, `sessions.read` 0, never loaded in a transcript, and no Cursor conversation mentions it. |

### `harness[]`

| Field | Meaning |
|---|---|
| `harness` | `claude-code`, `codex`, `copilot`, `cursor`, `gemini-cli`, `github`. |
| `when` | `session_start` (loaded when a session starts), `on_touch` (loaded when the agent works on a file in that folder), `path_scoped` (loaded when a file matching `paths`/`globs`/`applyTo` is touched), `on_invoke` (a skill, command or agent body, loaded when invoked), `displayed` / `linked` (GitHub shows or links it), `ignored` (the location is documented as ignored, e.g. a `.md` in `.cursor/rules/`). |
| `rule` | The rule in one sentence. |
| `condition` | Present when the rule only applies under a condition, e.g. Claude Code reads `AGENTS.md` only when no `CLAUDE.md`/`CLAUDE.local.md` sits at or above the working directory. |
| `condition_met` | `true`/`false` when the repo and the folders above the project's real checkout (`history_of`) settle the condition, `null` otherwise. |
| `shadowed_by` | For GitHub's precedence rules: the path of a copy GitHub uses instead. |
| `paths` | For `path_scoped`: the patterns as written. |
| `source` | URL of the vendor page the rule comes from. |

## `folders[]`

A folder unit is every directory, other than the root, that holds doc files, and every directory inside a *docs area*: a directory whose tracked files are at least half doc files. A folder of images among the docs is a unit, with no doc file; the asset folders of a code folder that holds one README are not.

`path`, `files` (doc files inside, recursively), `words` (their total), `other_files` (the tracked files directly in the folder that are not doc files: images, scripts, archives), `named_by_tools` (same shape as for files, `via: folder`): the tools whose text names the folder. Read the quoted line to tell a tool that reads or writes the files there from one that names the folder for its own purpose.

## `pointers[]`

`{from, to, kind, line}`, one entry per line that names the target. `from` and `to` are paths as in `files[].path`; an auto-memory file can point to a repo file. `kind`: `link` (Markdown link), `backtick` (a backticked path that resolves), `import` (`@path` in a file Claude Code or Gemini CLI expands), `rule_paths` (a rule's `paths:`/`globs:`/`applyTo:` matches the target; `line` is `0`), `citation` (a decision record cited by its number, "ADR-0024" or "ADR 24", and each number of the same width listed after it, "ADR-0021/0022", "ADR-0041 et 0048"; no entry when a link or backticked path on the same line already names it). A decision record is a doc file whose name starts with its number (`0024-…`, `adr-24-…`), in or below a folder named for decisions (`adr`, `decisions`, `architecture-decisions`), or itself named `adr-…`. A reference that matches several files (a bare `README.md`, a number two records share) resolves but makes no pointer.

## `duplicates[]`

`{words, text, occurrences}`. `words`: length of the shared passage, at least 12. `text`: its first 300 characters. `occurrences`: `[{path, scope, line}]`, two or more files, `repo`, `auto_memory` and `user` alike. Matching ignores case, punctuation and Markdown markup. Repeats inside one file and reworded repeats are not detected (`repeats` lists candidates for those). Sorted longest first.

## `tools`

Keyed by tool id: the skill name for user and project skills (`domain-modeling`), `plugin:skill` for plugin skills (`mattpocock-skills:tdd`), same pattern for commands and agents. Each: `kind` (`skill`, `command`, `agent`), `scope` (`user`, `project`, `plugin`), `path` (its directory or file, `~/`-prefixed), `invocations`, `in_subagents` and `sessions` (as in `skills_invoked`, exact id match), `last_invoked` (date or `null`).

## `doc_writers`

- `auto_memory`: `enabled` (on by default), `set_by`, `tracked`, `dir`, `files` (doc files there now), `source` (the vendor page). `autoMemoryEnabled` follows settings precedence: `.claude/settings.local.json` over `.claude/settings.json` over `~/.claude/settings.json`. `CLAUDE_CODE_DISABLE_AUTO_MEMORY`, in a settings file's `env` or in the environment the inventory runs in, turns memory off whatever the setting says: the vendor page gives no order between the two. `set_by` is the file that settles it (`~/`-prefixed or repo-relative), `"environment"`, or `null` for the default. `tracked`: whether the repo tracks that file, `null` when it is not a repo file; a setting in an ignored file holds in this checkout only, not in a worktree or a clone. Managed settings are not read.
- `hooks`: every command hook of `~/.claude/settings.json`, `.claude/settings.json`, `.claude/settings.local.json` and the active plugins' `hooks/hooks.json`: `{source, event, matcher, command}`. Read each command, or the script it runs, to tell one that writes files from one that does not.
- `tools`: the project's skills, commands and agents, and the tools invoked in this project, whose text tells the agent to write a doc: a line with a write verb and, at most 60 characters after it, a doc path or a backticked folder that is not a link target or a file the tool bundles. `{tool, kind, scope, invocations, hits, quotes}` (up to 3 `{file, line, text}`). A candidate list: read each quote.

## `skills_invoked[]`

`{name, invocations, in_subagents, sessions, last}`: every name seen in a `Skill` tool call or a `<command-name>`, leading `/` removed. `invocations` counts the calls in the main sessions and in their subagents alike; `in_subagents` says how many of them a subagent made (a transcript under `subagents/`, or an entry marked `isSidechain`). `sessions` counts the distinct sessions, a subagent counting as its parent session. A bare name can mean a user skill or a plugin skill of the same name; the inventory does not guess which.

## `limits`

| Field | Meaning |
|---|---|
| `transcripts` | `dirs` (project directories under `~/.claude/projects/`: main checkout and worktrees), `files` (transcript files read, subagents' included), `sessions` (distinct sessions), `first`, `last` (dates), `retention_days` (`cleanupPeriodDays`, or `null` if unset). Usage older than `first` is unknown, not zero. |
| `other_checkouts` | Other checkouts of this repo (sharing its first commit) that have Claude Code sessions: `[{path, sessions}]`, main checkouts only, their worktrees counted with them. Run on a copy made elsewhere, this names where its history lives; that history is read only with `--history-of <path>`. |
| `logs` | One entry per harness that has an instruction file in the repo: `{harness, status, note}`, `status` in `read`, `counts_only`, `unreadable`, `absent`. Anything but `read` is a question for the user. |
| `untracked_doc_files` | Doc files present but not tracked by git (not ignored), left out of `files`. |
| `tool_roots` | Directories scanned for installed tools. |
| `notes` | Fixed caveats of the method, e.g. a name that a skill bundles in its own directory does not count as that skill naming the project's file. |

## `measure`

`{schema, base, worktree}`. `base` and `worktree` have the same shape: `ref` (sha, or `"worktree"`), `words` (`{path: words}` for repo doc files, symbolic links left out), `always_loaded_words` (total words of repo and auto-memory files with a `session_start` rule in any harness, imports included, a symbolic link counted once under its target; the auto-memory index is the same on both sides), `duplicated_passages` (count of `duplicates` entries) and `duplicated_words` (words that could go: each passage's `words` times its occurrences minus one), `unresolved_refs` (count over repo files), `orphans` (repo paths). The working tree side includes untracked files that git does not ignore.

## `repeats`

`{schema, repo, files, same_file, duplicates, shared_code}`, computed on the files named on the command line only. Paths are written as in `files[].path`: repo-relative, or `~/`-prefixed for auto-memory and user files.

- `files`: the files compared.
- `same_file`: `[{path, same_as}]`, a named path that is a symlink to another named file (an `AGENTS.md` linked to `CLAUDE.md`). It is compared once, under `same_as`.
- `duplicates`: as the inventory's `duplicates`, between these files only.
- `shared_code`: candidates for a rule written in several files in different words. `[{files, terms}]`, one entry per set of files, sorted by number of files, then by path. `terms`: `[{term, occurrences: [{path, line}]}]`. A term is code that two or more of the files hold, read from inline code spans and fenced blocks, lowercased, with quotes and brackets dropped:
  - an **identifier**: one token that is not punctuation or a number, not a plain word (`select`), not a one-letter flag (`-f`), and not a doc file or a docs folder (the pointer graph has those): `billing_cutoff`, `--dry-run`, `/api/health`;
  - a **run** of 3 or more consecutive tokens (`pg_dump --schema-only --no-owner`): windows of 3 merged where each follows the other at every place it is written.

  A term is a candidate, not a verdict: two files can share a command for different reasons. A rule stated without any code, or whose only shared code is a name written as a plain word (`users`, `make`), shares no term and does not appear here.

Why both kinds, and why runs of 3. Measured on one project only: its 64 living and auto-memory files, out of 576 doc files, where one rule (wrap every production query in a read-only transaction, shown as a command) is written in four files in different words:

| Terms kept | Terms | Groups of files | That rule found |
|---|---|---|---|
| Single tokens with plain words | 606 | 340 | yes, as plain words (`only`, `begin`) |
| Identifiers only (no plain words) | 293 | 172 | no: the command's tokens are plain words and one flag |
| Runs of 2 tokens | 174 | 92 | yes |
| Runs of 3 tokens | 88 | 44 | yes |
| **Identifiers and runs of 3** (this output) | 385 | 206 | yes, one group holding its four files |

Single tokens with plain words are mostly plain words; runs of 3 hold commands, queries and expressions; a rule whose only shared term is one identifier (a column, a route, a long flag) appears through the identifiers. Over all 576 doc files, runs of 3 alone form 4,839 groups: run `repeats` on the files a stage judges, not on the whole doc set.

