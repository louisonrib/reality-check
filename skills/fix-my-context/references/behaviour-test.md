# Behavioural test

A verdict labelled *to be tested* rests on a prediction that the agent behaves the same, or better, with the change. Give a verdict that label when both hold:

- its only basis is that the agent would behave the same without the text ([Anthropic best practices](https://code.claude.com/docs/en/best-practices) [vendor]: "For each line, ask: 'Would removing this cause Claude to make mistakes?' If not, cut it.");
- a wrong call would cost: the text governs a destructive or production action, or a convention nothing else enforces.

A verdict with a basis of its own (the text restates the code, holds a secret, or states a rule that must always hold) is *judged*, *checked in the code* or *checked by a script*.

The test checks that prediction by running the agent on the same task in two copies of the repo, one with the change and one without. It is a tool you use from stages 3 to 5, before applying the change, and only with the user's approval.

## Before proposing it, fix the test in the report

Write these down before anything runs; they stay as written:

- **The change**: the exact diff.
- **The task**: a prompt for a realistic piece of work in this repo where the text under test, if followed, changes what the agent does. In the copies, read-only tools run and every other tool call is denied but recorded, so the behaviour has to show in the calls the agent attempts or in its final answer. End the prompt with: "Writes are recorded, not applied: continue as if each one succeeded, and list at the end every file you would have written and what it would hold."
- **The expected behaviour** with the change and without it.
- **The pass/fail criteria** for one run, each one observable in the recorded calls or the answer. A criterion bears on the first action with an effect that the task calls for, or on the files and contents the agent lists at the end: after a denied write, an agent may stop and report instead of trying the next one.

Then check the task against the repo:

- **Its premise is true in the code**: what it asks to add does not exist yet, under any name.
- **The repo's workflow lets the agent act now**: when the project requires steps before code (a spec, a plan, a review), the task says which of them are done.
- **Its terms follow the project's glossary.**

A criterion that the rule "reached the agent" passes when the file under test was loaded (`instructions_loaded`) or read explicitly (a `Read` of it in `tool_calls`). To test whether a path-scoped rule loads by its path, use a change in which no always-loaded file points to it.

## Propose it to the user

Say what is tested and why, in plain words: "with the change / without the change". Propose a pilot first: one run with the change and one without, to check that the prompt and the criteria tell the two sides apart. Then propose the full test: 3 runs with the change and 3 without, unless the user chooses another count.

Tell the user how the runs differ from a real session: hooks are off, and the user's and project's own allow rules are denied, on both sides alike.

Run nothing the user has not approved.

## Run it

`scripts/behaviour_test.py --help` gives the options. Per run it reports the instruction files the session loaded (`instructions_loaded`), the tool calls with those denied (`tool_calls`), the final answer, how the run ended (`exit_code`, `error`), and the file holding the session's raw stream (`raw`, in `raw_dir`). Give `--raw-dir` a folder outside the audited repo (the script refuses one inside) and note it in the report: a run the script failed to read is read again from its stream rather than run again.

Check each run first. A run that ended in an error, neither loaded nor read the file under test, or loaded the copy from the wrong side says nothing about the change: report it as void and rerun it.

## Read the result

Grade each run against the criteria written before the runs.

- **Confirmed** when every run on both sides matches its expected behaviour.
- **Not confirmed** otherwise. A single run that departs may be chance; say so, and offer more runs. Until the result is confirmed the verdict is withdrawn, and the change is not applied on its strength.

In the report, keep for each run: the files loaded, the calls attempted, an excerpt of the answer, the grade against each criterion; then the outcome and what happened to the verdict.
