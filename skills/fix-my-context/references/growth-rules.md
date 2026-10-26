# Stage 4: the rules that make docs grow

A doc set regrows after every cleanup while the rules that feed it stay as they are. This stage finds what makes agents write docs, the texts and the harness mechanisms, judges each one, and fixes it at the source.

## Find them

Read every text that instructs agents to write or update docs, wherever it sits:

- steps in the instruction files that close a piece of work (an integration gate, a definition of done, a merge checklist);
- rules that create a dated doc per unit of work: a report, plan or postmortem per issue;
- doc headers and charters that say what earns a place in the doc;
- plan templates, and plans that carry a standing "update the docs" task;
- skills, commands and agents in the project that write docs;
- memory files, and commits that moved memory content into docs;
- the harness mechanisms that write docs by themselves (`doc_writers`): auto memory, hooks whose commands write files, skills whose text writes a file at each invocation;
- the project's lines that hand a rule to one of the user's global files (`global_refs`): the wording that governs is in the global file. Other text of the global files enters the report as facts: its quoted wording, and the writing sessions that cite it.

Then work from the growth. For each living doc, read the commits that added to it (`git log --numstat --follow -- <file>`) and the sessions that wrote them, until every addition is traced to the instruction its session said it was carrying out, or marked as traced to none. Quote those instructions. A rule the writers cite is a growth rule even when its wording looks harmless.

## Judge them

Each finding in the project's own files, and in a global file that a project rule hands its wording to, gets a verdict with its source and label.

- **A living doc's job framed as completeness.** Wording that gives a doc the job of being complete, so that each change adds to it and nothing ever prompts a removal, pushes towards growth. Against it:
  - [Google docguide][docguide] [vendor]: "A small set of fresh and accurate docs is better than a large assembly of 'documentation' in various states of disrepair.";
  - [Anthropic best practices][bp] [vendor] excludes "Information that changes frequently" and "Anything Claude can figure out by reading code";
  - [matklad, ARCHITECTURE.md][matklad] [practitioner]: "Don't try to keep it synchronized with code."

  The other side, to state when you cite these: [Write the Docs][wtd] [practitioner] allows blocking a merge on missing docs, for user-facing feature docs.
- **An admission rule the sources do not support.** [Anthropic memory page][memory] [vendor] adds a line when "Claude makes the same mistake a second time"; [Anthropic best practices][bp] [vendor] removes one that fails "Would removing this cause Claude to make mistakes?". A rule that admits an entry on another ground, such as a single occurrence or the effort it took, departs from both. No source was found for or against text that tells how an entry was learnt (an issue number, an incident): say so, and show the measured facts (`issue_refs` and `dates` per doc).
- **A rule that creates a dated doc per unit of work** is a growth rule, whatever its wording: each issue adds a file. Judge it on whether what it produces is read for its content ([`provenance.md`](provenance.md), Readers): "When a document no longer serves any purpose, either remove it or identify it as obsolete" ([*SWE at Google* ch. 10][swe] [vendor]).
- **A harness mechanism that writes docs** is a growth source of its own: it writes outside any review of the docs. Before its content, put the mechanism to the user: "does this mechanism suit your method?", with the options switch it off, restrict it, or bring it into the repo. Judge its content after that answer, at stage 5; auto-memory entries are sorted by [`placement.md`](placement.md), Auto-memory entries.
- **A standing docs task in plans.** No source was found that addresses it: say so, and show the facts from history: how many plans carry the task, and how the docs grew after it appeared.
- **A writing rule that does not reach the writer.** A rule reaches an agent only through what loads ([Anthropic memory page][memory], [skills page][skillspage] [vendor]): a doc header is in context only when the doc is open; a memory topic file only when read ("Claude reads them on demand"); a skill body only "when invoked". Check in the transcripts whether the writing sessions had the rule in context: loaded at start (the `instructions` attachment), or read before writing.

## Fix at the source

- **Follow a delegated rule to its source.** When the project's rule hands its wording to a global file (`global_refs`: an `@~/` import, "the global X's"), judge the wording in that file and propose the fix there: rewording the project's copy would make two rules. The global file is the user's; the user decides whether it is written.
- **Fix a mechanism with its setting.** The fix at the source of a harness mechanism can be a setting rather than a sentence. For auto memory: "To turn it off for a single project, set `autoMemoryEnabled` in that project's settings" ([Anthropic memory page][memory] [vendor]), in a settings file the repo tracks (`doc_writers.auto_memory.tracked`), so the setting holds in every worktree and clone. A sentence in `CLAUDE.md` that limits what memory holds would sit beside the harness's own instruction to save memories: two rules in conflict.
- **Reword the rule itself.** Point it at what the sources support: [Google docguide][docguide] [vendor], "Change your documentation in the same CL as the code change" and "First delete what you're certain is wrong, ignore what's unclear." The fix replaces the faulty wording. A counter-rule beside it leaves two rules in conflict, and "Claude may pick one arbitrarily" ([Anthropic memory page][memory] [vendor]).
- **Deliver the writing rule where the writer will see it.** In Claude Code, a `.claude/rules/` file with `paths:` matching the living docs: "A path-scoped rule loads when Claude uses the Read, Write, or Edit tool on a matching file" ([Anthropic memory page][memory] [vendor]). Other harnesses have scoped equivalents: nested `AGENTS.md` ([agents.md][agentsmd]), `.github/instructions/*.instructions.md` with `applyTo` ([GitHub Copilot][copilot]), `.cursor/rules` with globs ([Cursor][cursor]), all [vendor]. Tell the user that no study has measured whether such a rule changes what the writer writes.
- **Prefer a check to a sentence** when the rule is mechanical (a broken path, a forbidden term): "convert it to a hook" ([Anthropic best practices][bp] [vendor]), or a link or vocabulary linter in CI. Add it only if the user wants it.

Propose each fix with the finding it fixes.

[docguide]: https://google.github.io/styleguide/docguide/best_practices.html
[swe]: https://abseil.io/resources/swe-book/html/ch10.html
[bp]: https://code.claude.com/docs/en/best-practices
[matklad]: https://matklad.github.io/2021/02/06/ARCHITECTURE.md.html
[wtd]: https://www.writethedocs.org/guide/docs-as-code/
[memory]: https://code.claude.com/docs/en/memory
[skillspage]: https://code.claude.com/docs/en/skills
[agentsmd]: https://agents.md/
[copilot]: https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions
[cursor]: https://cursor.com/docs/rules
