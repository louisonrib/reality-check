---
name: fix-my-context
description: One-time repair of a project's agent docs. Explains what each doc was for and who still reads it, decides with you what stays, fixes the rules that make docs grow, and applies the approved changes on a branch.
disable-model-invocation: true
---

# Fix my context

One pass over a project whose docs have drifted under coding agents. Scripts establish the facts, you judge them against cited criteria, and the user decides. The pass ends with a lean doc set on a branch, a report, and before/after measures.

## Rules that hold for the whole pass

- **Explain before judging.** Before proposing anything about a file or a docs folder, establish what created it and for what purpose, what reads it today, whether that reader is still in use, and what points to it.
- **Start from what is there.** Work from the files the inventory found. A file name you recognise is a guess about its owner until the evidence confirms it.
- **Every verdict carries a reason the user can check**, a keep as much as a change, and one of four labels, written in the user's language:
  - *checked by a script*: the inventory measured it in this repo or its transcripts (a path that no longer resolves, a passage repeated verbatim, a count of sessions, a file nothing reads or points to). A loading rule it reports (`harness[]`) is the vendor's, so a verdict resting on it is *judged*, citing `harness[].source`;
  - *checked in the code*: you checked a claim about the code against the code, and the verdict quotes the file:line, or the command and what it printed, that settles it. A check you cannot quote that way is *judged*;
  - *judged*: you read the text against a criterion and name its source (owner and URL), or state that no source was found (the references name these gaps);
  - *to be tested*: the verdict rests on whether the agent behaves differently without the text, and a wrong call would cost. No study was found that checks a model's prediction of this against runs with and without the text, so it goes through a [behavioural test](references/behaviour-test.md), which gives the exact conditions for this label.
- **Fix the source first.** When a doc keeps growing, fix what makes it grow before pruning its content (stage 4 before stage 5).
- **Remove, move or keep.** Verdicts take text out or put it where it belongs, which can mean creating the file it moves to. What lives in the code gets a pointer or nothing. The only new text you write is what a source fix requires, such as a scoped rule or a CI check, and only when the user wants it.
- **A missing log is a question.** When a reader's logs cannot be read, ask the user whether it is used. Treat "no evidence found" as unknown, never as "unused".
- **Decide alone what is invisible.** A change the user will not see and that can be undone at no cost (renaming a constant, adding a test, one more check in a script, not creating a file) is made without asking and listed in the report as done; the user reviews it with the branch. What is visible, costs, leaves the repo or bears on the user's method goes to the user. You write to the audited repo only on the pass's branch, and you never merge.
- **Check a figure against the work done.** A measure that goes against what the pass did, such as more always-loaded words after a pruning, is checked before it is reported.
- **Stay on the docs.** A point outside the docs met along the way (a dependency, a bug in the code, a product question) is noted in the report with its evidence and left for the closing stage.

## Tools and sources

- `scripts/inventory.py` and `scripts/behaviour_test.py`, in this skill's directory, run with `python3` (standard library only). Run each with `--help` for its options. They never write to the audited repo. The inventory's output is described in [`references/inventory-output.md`](references/inventory-output.md).
- The criteria you judge against are in `references/`, one file per stage, loaded when the stage starts. Each criterion names its owner, its URL and its grade: [vendor] (the harness or platform vendor's documentation), [measured] (a study with a stated method), [practitioner] (an individual's or a community's guidance). Carry the owner, the URL and the quote into the verdict.
- Transcripts, when you need more than the inventory gives: Claude Code sessions are JSONL files in the directories listed in `limits.transcripts.dirs`. The instruction files a session loaded at start are in the entry with `"type": "attachment"` and `attachment.type == "instructions"` (`attachment.files[].path`). Files read or written appear as `tool_use` blocks named `Read`, `Edit` or `Write`, with `input.file_path`.
- Two kinds of doc are judged differently. A *living doc* is read to learn how things are now, and misleads when stale: an architecture map, a glossary, a runbook, a README. A *dated record* holds what was known at a date and is never rewritten: a decision record, a postmortem, a plan whose code is built.

## Start

1. Find the audited repo's git root.
2. Read its status. A clean working tree is a fact for the report. Uncommitted changes are a question: list them and ask the user what to do with them before creating the branch, and leave files you did not create untouched.
3. Propose, in one question, a location for the report in the audited repo and a name for the branch; the user confirms or changes them. If a report from an earlier pass exists, read it and resume from the stage it records.
4. Create the branch from the current commit and write that commit's sha in the report as the base. Build the report from [`references/report.md`](references/report.md). Keep it out of the decision commits until its destination is chosen at the end.

## Stage 1: inventory

Run `inventory.py <repo>` (with `--history-of` if needed) and save its output outside the audited repo, for example under `$TMPDIR/fix-my-context/`. The output can run to megabytes: query it with `python3` or `jq` for the fields and files you need, rather than reading it whole.

Read `limits` first. When `limits.other_checkouts` names one checkout with more sessions than `limits.transcripts.sessions`, the repo is a copy of it and the project's sessions ran there (the copy's own sessions can be this pass alone): rerun the inventory with `--history-of <that path>` and record it in the report. When it names several such checkouts, ask the user which one the repo is a copy of. Then read the dates the transcripts cover and the untracked doc files left out.

Ask the user which agent tools they run on this project. The inventory reads Claude Code's and Cursor's logs and knows the instruction files of a few harnesses (`limits.logs`); a tool it does not know leaves no trace in its output. Name in the question, as examples, the harnesses of `limits.logs` whose status is not `read`. Record the limits and the answer in the report.

Read the mechanisms that write docs by themselves (`doc_writers`: auto memory and what settles it, the hooks, the tools whose text writes a doc) and the project's lines that hand a rule to a global file (`global_refs`). Stage 4 judges both.

The user's global instruction files (`~/.claude/CLAUDE.md` and what it imports) appear with `scope: user`. They enter the pass as a reference: stage 5 reports what the project repeats from them as facts ([`references/placement.md`](references/placement.md), Repetition). A global file's wording gets a verdict when a project rule hands its wording to it (stage 4), or in a pass the user asks for on that file.

*Done when* the report lists every doc file and docs folder with its readers, or "none found" with the limits that apply, and the user's answer on the agent tools they run.

## Stage 2: the base (on trial)

Load [`references/base.md`](references/base.md).

*Done when* every docs folder and every decision doc that others cite as a constraint has its card, the user has said for each one whether it belongs to the project, and each one that goes has its verdict.

## Stage 3: provenance and reason to exist

Load [`references/provenance.md`](references/provenance.md).

*Done when* every doc file of scope `repo` or `auto_memory`, and every docs folder, that stage 2 kept has its card in the report, and every card that proposes a change has the user's decision or is listed as done.

## Stage 4: what makes docs grow

Load [`references/growth-rules.md`](references/growth-rules.md).

*Done when* every text in the project that tells agents to write or update docs, and every mechanism of `doc_writers`, has a verdict with its source, and every fix proposed has the user's decision or is listed as done.

## Stage 5: placement and pruning

Load [`references/placement.md`](references/placement.md).

*Done when* every passage of every always-loaded file carries a verdict, every living doc that stays is covered section by section, and every entry `inventory.py repeats` lists has a verdict.

## Asking the user

A question is for what only the user can settle: a change that is visible, costs, leaves the repo or bears on their method (delete, move, merge, archive, reword, a rule to add, a setting, a test to run), or a fact the evidence cannot give (which agent tools they run, which checkout a copy comes from, whether a rule or convention came from them and is still their method). What is invisible and reversible is decided and listed as done. Everything else goes into the report as a card: a file the evidence shows in use whose verdict is to keep it, a clean working tree, a fact the inventory established.

- **Start from the user's situation.** A question opens on what happens to the user today, in their words, and what it costs or risks them; then the option you recommend and what it changes for them. The mechanism comes after (the file, the line, the setting), with its jargon glossed.
- **One kind of decision per question.** A question groups the points that call for one kind of decision: files that share an origin and readers and the same verdict, or the settings of one mechanism. The findings of one section of the report can call for different decisions; ask about those apart.

Bring each decision up when you reach it.

A question is the card of [`references/report.md`](references/report.md) for the files it covers, ending on the choices in place of the decision. Load `write-it-right` before writing the first question and the report, and apply its reader test to every question and to the report: the user reads plain words, such as "with the change / without the change", and the four labels in their language.

Write each decision into the report when the user gives it, with where the pass now stands.

## Delegating to subagents

A stage's reading can be split across subagents, by files. Brief each one with the stage's reference file and the four labels. It returns, for each section of its files, the verdict with its label and source, and the rules and facts the section states, one line each with its file and line.

Repetition is judged in your own context, from `inventory.py repeats` and the rule lines every subagent returned, so a rule written in two folders is seen whole ([`references/placement.md`](references/placement.md), Repetition).

The report holds your merged findings, written as its cards in the user's language. A subagent's reply is material: before a finding of it supports a proposed change, re-read the lines it cites; then rewrite it into the cards.

## Applying decisions

Apply each family of approved decisions as it is decided: one commit on the branch per family, its message naming the decisions. When a family moves, renames or deletes files, update every pointer to them (`pointers`) in the same commit, then rerun the inventory so the next stage reads the real state.

- **Work from the verdicts.** Apply the report's verdicts line by line, and check each line off in the report as its change lands. The doc is where you edit; the verdicts say what changes.
- **Moving a rule tests it.** To move a rule into the file it governs, read that file: check the rule against the code there, and report the comments nearby that contradict it. The report counts apart the rules already stated there, the rules added, and the rules found false.
- **An acceptance criterion meets the measures.** An acceptance criterion written for an issue is checked against the measures the docs already hold (a threshold, a noise level, a timing).
- **State outside the repo moves with its setting.** A change to state outside the repo, such as emptying auto memory, happens at the merge, or together with the setting that stops it coming back. Before moving or emptying an auto-memory file, update every line of the repo that names it (`memory_refs`). The report says when a gap remains, such as a setting on the branch while the state has already changed.

When a verdict labelled *to be tested* comes up, propose the test before applying the change.

## Closing

1. Sort the points noted along the way:
   - a doc point that one sentence settles is done;
   - a point outside the docs becomes an issue for the project's tracker, with its evidence, and its fix belongs to that issue; propose each issue, and open it when the user agrees;
   - the rest is dropped, and the report names what was dropped.
2. Run `inventory.py measure <repo> --base <base sha>`, with `--history-of` if stage 1 used it, and put its before/after figures in the report's table. The after side counts untracked doc files: the report itself, and any listed in stage 1's `limits.untracked_doc_files`. Subtract them, or name them under the table.
3. Propose where the report goes: the PR description when the project is on GitHub, otherwise the merge commit message, or a dated record if the project keeps such records.
4. Hand the branch to the user with a final report: what was done and where (commits, issues), and feedback on this skill: what served the pass and what it missed. Merging is theirs.
