# Stage 5: placement and pruning in the files that stay

Two kinds of file, judged differently: the always-loaded files section by section, then passage by passage, and the other docs that stay section by section, each by the criteria of its type.

## Always-loaded files

These are the files that enter every session: those with a `harness` rule whose `when` is `session_start` (and whose `condition_met` is not `false`), and everything they `@`-import (`pointers` of kind `import`). In Claude Code that is `CLAUDE.md` at the root and above it, `AGENTS.md` when no `CLAUDE.md` is loaded, unscoped `.claude/rules/*.md` and the `MEMORY.md` index. Each costs context in every session. All Anthropic sources are [vendor].

**Sections first.** Ask of each section, under its heading: must it load in every session? [Anthropic memory page][memory]: "Keep it to facts Claude should hold in every session"; "Use path-scoped rules to load instructions only when Claude works with matching files, or trim content that isn't needed in every session." A section the agent needs only when it works on certain files moves whole to a rule scoped with `paths:` on those files. Writing a doc is working on a file: "A path-scoped rule loads when Claude uses the Read, Write, or Edit tool on a matching file" (same page). A section on where each kind of doc lives and how to write it is needed when the agent writes a `.md`; scoped to the doc paths, it stays out of the sessions that change only code. Ask it of every section, including one whose passages would each stay by the grid below: a passage judged alone can earn its place while its section loads in sessions that never use it.

**Then the passages** of the sections that stay. A passage is the smallest piece that says one thing: a bullet, a table row, a short paragraph. Give each one a verdict from this grid.

| The passage holds | Verdict | Source |
|---|---|---|
| A command the agent cannot guess; a style rule that differs from defaults; a gotcha that is not self-evident; an architectural decision specific to the project | Stays | [Anthropic best practices][bp], "Include" list: "Bash commands Claude can't guess", "Code style rules that differ from defaults", "Common gotchas or behaviors that aren't self-evident", "Architectural decisions specific to your project" |
| A "never do X" rule | Stays | [Anthropic features overview][features]: "Put it in CLAUDE.md if Claude should always know it: … "never do X" rules." |
| Something the agent can read in the code: dependency list, directory layout, file-by-file description | Deleted | [Anthropic best practices][bp] excludes "Anything Claude can figure out by reading code"; `/doctor` "cuts content Claude can derive from the codebase, such as directory layouts, dependency lists, and architecture overviews" ([memory page][memory]) |
| A multi-step procedure, or a convention for one area of the repo, code or docs | Moves to a skill, or to a nested instruction file or a rule scoped with `paths:` | [Anthropic memory page][memory]: "If an entry is a multi-step procedure or only matters for one part of the codebase, move it to a skill or a path-scoped rule instead." |
| Something that must happen every time | Moves to a hook or a permission | [Anthropic best practices][bp]: "Unlike CLAUDE.md instructions which are advisory, hooks are deterministic and guarantee the action happens." |
| A style rule a tool can check | Moves to the linter or CI | [Cursor rules][cursor] [vendor]: "Copying entire style guides: Use a linter instead."; [dos Santos et al.][smells] [measured]: "Lint Leakage" in 62 of 100 popular repos' files |
| A note for the humans who maintain the file | Moves to an HTML comment | [Anthropic memory page][memory]: HTML comments "are stripped before the content is injected into Claude's context" |
| A personal preference | Moves to `~/.claude/CLAUDE.md`, `CLAUDE.local.md`, or auto memory | [Anthropic memory page][memory]: "Personal preferences for all projects"; "Personal project-specific preferences" |
| A secret | Removed, and a `Read` deny permission on its path | [Anthropic blog][blog]: "Don't include sensitive information, API keys, credentials"; [permissions page][perms]: "add a `Read` deny rule for its path" |
| A pointer to a doc | Stays if it says what the doc is for and when to open it | [dos Santos et al.][smells] [measured, 87 % precision]: "Blind References", "references to external documents, files, or directories without explaining their purpose or scope" |

Four kinds have no settled answer; present the sides and let the user decide:

- **An architecture overview.** Keep: the [memory page][memory] lists "project architecture" as `CLAUDE.md` content. Cut: [best practices][bp] excludes "File-by-file descriptions of the codebase" and `/doctor` cuts "architecture overviews". [Gloaguen et al.][gloaguen] [measured]: "context files are not effective at providing a repository overview."
- **Whether a stated decision should point to its decision record.** No source was found.
- **Text that tells how a line was learnt** ("since #123", an incident). No source was found for or against.
- **Why the code is the way it is.** [Google docguide][docguide] [vendor]: "The primary purpose of inline comments is to provide information that the code itself cannot contain, such as why the code is there."; [Nygard][nygard] [practitioner] puts decisions in decision records; `/doctor` keeps "rationale" in the loaded file ([memory page][memory]). No source compares them.

**Length.** Judge content, not size. No study measured a line or word threshold; the vendors' numbers (200, 500, 1,000 lines, 32 KiB) come with no stated basis.

**Pruning.** Prune in place: move sections, cut passages. [Chakrabarti][chakrabarti] [measured, single-author preprint]: a wholesale rewrite resets a file's size but not its growth rate (4.1 % per commit before the first rewrite, 4.9 % after).

## Living docs and dated records

Judge each doc that stays by its type, section by section:

| Type | What the sources say |
|---|---|
| Architecture map | [matklad][matklad] [practitioner]: "only specify things that are unlikely to frequently change. Don't try to keep it synchronized with code."; "Do name important files, modules, and types. Do not directly link them (links go stale)."; "Explicitly call-out architectural invariants." |
| Domain glossary | [arc42][arc42] [practitioner]: "Keep the number of terms in your glossary quite small"; "Avoid trivia" |
| Runbook, QA procedure | [Google SRE workbook][sre] [vendor]: "notice when your playbooks have accumulated a lot of information beyond these structured details"; a deterministic list of commands becomes automation |
| Decision record | Superseded, never deleted ([Nygard][nygard] [practitioner]). Whether an accepted one may be edited is contested: [Fowler][fowler] [practitioner] says it "should never be reopened or changed"; other templates carry a "last updated" field |
| Plan, design doc | [Google docguide][docguide] [vendor]: "once the code is implemented, design docs should serve as archives of these decisions, not as half-correct docs" |
| README | [GitHub][readme] [vendor]: "A README should only contain information necessary for developers to get started using and contributing to your project." |
| Auto memory | Judged once the user has answered on the mechanism itself (stage 4). [Anthropic memory page][memory] [vendor]: "Claude skips anything it can derive from the codebase … It also skips anything your CLAUDE.md files already say."; `MEMORY.md` is an index, one line per entry |

**Restated code.** A passage that restates the code (identifiers, constants, counts, file lists, what a module does or does not do) gets a pointer to the code or is removed, whether or not it is still true. No owner states this as a general rule; they state cases: [matklad][matklad] on links, [Ubl][ubl] [practitioner] on copied interfaces and schemas, which "quickly get out of date". [Tan, Wagner, Treude][docer] [measured]: outdated code references in READMEs and wikis stayed wrong for years. Check each restatement against the code, with a search or the compiler rather than by eye, and report the false ones as such, quoting in the verdict the file:line, or the command and what it printed, that settles each one: that quote is what makes it *checked in the code*. Paths and links that no longer resolve (`unresolved_refs`) are *checked by a script*: check each one before proposing its removal, since a path can name a file the change is about to create or one outside the repo.

## Repetition

Each fact gets one home: [*SWE at Google* ch. 10][swe] [vendor], "designate canonical documentation". One exception is forced by the harness: Explore and Plan subagents "start without your CLAUDE.md files", so a rule that must hold in delegated work is restated "in the prompt you give Claude when delegating" ([sub-agents page][subagents] [vendor]).

Find the repeats with `scripts/inventory.py repeats <repo> <path>...`, given every file this stage judges: the always-loaded files, the living docs that stay, the auto-memory files and the user's global files (`scope: user`). It lists, between those files only, the passages repeated word for word (`duplicates`) and the code they share (`shared_code`): an identifier or a command written in several files, grouped by the files that hold it, with lines. Read each entry's lines in their context and decide whether they state one rule. A rule written in prose with no code appears in neither list: compare the rule lines from your own reading and from the subagents', side by side.

A repeat gets a card: the rule in a few words, every place it is written, the home proposed and the copies to cut or replace with a pointer. Entries that are not repeats are counted in the report, not listed.

A passage the project repeats from the user's global files is a fact for the report: the passage, where in the project, where in the global file. The global file's copy is the reference the project's copy is compared with. The project's copy gets its verdict in its own file's card, and cutting it is a question, since the global file reaches this user only, not their collaborators.

[bp]: https://code.claude.com/docs/en/best-practices
[features]: https://code.claude.com/docs/en/features-overview
[memory]: https://code.claude.com/docs/en/memory
[perms]: https://code.claude.com/docs/en/permissions
[subagents]: https://code.claude.com/docs/en/sub-agents
[blog]: https://claude.com/blog/using-claude-md-files
[cursor]: https://cursor.com/docs/rules
[smells]: https://arxiv.org/abs/2606.15828
[gloaguen]: https://arxiv.org/abs/2602.11988
[chakrabarti]: https://arxiv.org/abs/2608.11095
[docer]: https://arxiv.org/abs/2212.01479
[docguide]: https://google.github.io/styleguide/docguide/best_practices.html
[swe]: https://abseil.io/resources/swe-book/html/ch10.html
[nygard]: https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions
[fowler]: https://martinfowler.com/bliki/ArchitectureDecisionRecord.html
[matklad]: https://matklad.github.io/2021/02/06/ARCHITECTURE.md.html
[arc42]: https://docs.arc42.org/section-12/
[sre]: https://sre.google/workbook/on-call/
[readme]: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes
[ubl]: https://www.industrialempathy.com/posts/design-docs-at-google/
