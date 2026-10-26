# The report

The report is the pass's memory: a later invocation resumes from it, so it always says where the pass stands. Its reader is the user, who has not read these instructions. Write all of it in the user's language, headings and field names included, and in plain words. Update it as each decision is made. Text in angle brackets is yours to fill; drop a section that stays empty.

Every finding is written as a **card**: a heading, then one bullet per field. That holds down to a single passage, section or memory file; findings that share a verdict and its reason share one card, whose heading names each of them. The one table is Before and after.

A card is finished when every field of its kind below is filled, a keep card as much as any other. **Why** opens on one of the four labels and gives what the label rests on: the inventory field for *checked by a script*, the file:line or the command and what it printed for *checked in the code*, the source's owner and URL for *judged*, the test for *to be tested*.

A card that puts a question to the user opens on **For you**: what happens to the user today, in their words, what it costs or risks them, and what the recommended option changes for them. The other fields follow, then the choices in place of the decision.

```markdown
# Documentation repair: <project name>

Branch `<branch>`, started from `<base sha>` on <date>.

## Where this repair stands

<Current stage, the next question to put to the user, and the decisions applied so far with their commits.>

## What this repair could not see

- Sessions read: <count>, from <first date> to <last date>, run from <path>. Older use is unknown.
- Agent tools you run on this project: <the user's answer>. <Each of them whose logs were not read.>
- <Doc files left out because git does not track them.>

## Done without asking

Changes you will not see and that can be undone at no cost. You review them with the branch.

- <the change>: <why it is invisible and reversible>. Commit <sha>.

## Folders and decisions that hold the rest

<This stage is on trial: what it changed in the pass.>

### <docs folder, or decision doc>

- **Date and who decided.** <the date it gives itself, the creating commit; the user, or an agent session; edits after its date>
- **Use.** <sessions that opened it for its content; the docs and tickets that cite it as a constraint>
- **Premises today.** <each premise, true or no longer, with what settles it>
- **Review triggers.** <each one, and whether it is an event that will happen>
- **Proposed.** <stays, or the verdict>
- **Why.** <label>. <what it rests on>
- **Decision.** <…>
- **Commit.** <sha>

## Files and folders

### <file, folder, or family of files>

- **Origin.** <what created it and when, quoting the line of the commit message or session that names it>
- **Readers.** <what reads it, whether each reader is still used, with the counts>
- **Proposed.** <verdict>
- **Why.** <label>. <what it rests on>
- **Decision.** <the user's decision; for a card that proposes no change, "no change">
- **Commit.** <sha>

## What makes the docs grow

### <file and lines, or the mechanism>

- **The wording.** <quote, or the setting and where it is set>
- **What it does to the docs.** <what the growth shows, with the commits or sessions that cite it>
- **Proposed.** <the fix>
- **Why.** <label>. <what it rests on>
- **Decision.** <…>
- **Commit.** <sha>

## Files the agent reads at the start of every session

### <file>

#### <section, passage, or several sharing a verdict: lines and first words>

- **Proposed.** <stays, deleted, moves to X>
- **Why.** <label>. <what it rests on>
- **Decision.** <…>
- **Commit.** <sha>

## Docs kept up to date as the project changes

### <file>

#### <section, or sections sharing a verdict>

- **Proposed.** <stays, deleted, moves to X, replaced by a pointer to Y>
- **Why.** <label>. <what it rests on>
- **Decision.** <…>
- **Commit.** <sha>

## Rules written in several places

<How many entries `repeats` listed, and how many were repeats.>

### <the rule, in a few words>

- **Where it is written.** <file:line, for each place>
- **Proposed.** <the one home, and what happens to each copy>
- **Why.** <label>. <what it rests on>
- **Decision.** <…>
- **Commit.** <sha>

## Rules moved into the files they govern

Already stated there: <count>. Added: <count>. Found false against the code: <count>, each with its file:line. Comments nearby that contradict a rule: <file:line, each>.

## What the project repeats from your global files

- <the passage>: <project file:line>; <global file:line>

A pass on these files is yours to ask for.

## Tests with and without a change

### <what was tested>

- **The change.** <diff or summary>
- **The task given to the agent.** <prompt>
- **Expected.** With the change: <…>. Without it: <…>
- **What counts as a pass.** <criteria, written before the runs>
- **Runs.** <per run: side, files loaded, what the agent tried, pass or fail per criterion>
- **Outcome.** <confirmed, or not confirmed and the proposal withdrawn>

## Noted along the way

- <the point, with its evidence>: <done, with its commit | issue <link> | dropped>

## Before and after

| Measure | Before (`<base sha>`) | After |
|---|---|---|
| Words in files loaded in every session | | |
| Words in all doc files | | |
| Passages repeated across files | | |
| References that point to nothing | | |
| Files nothing reads or points to | | |
```
