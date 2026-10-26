For people who move with AI faster than they can double-check it — catch the wrong turn before you build on it, and climb out of the loop when you're already stuck.

Claude Code skills that audit your premises, declare their sources, break retry loops, and keep your documents written for their reader.

## Installation

### Plugin marketplace

```
/plugin marketplace add louisonrib/reality-check
/plugin install reality-check@reality-check
```

### npx skills

```
npx skills add louisonrib/reality-check
```

## Skills

| Skill | Description |
|-------|-------------|
| [im-dumb](skills/im-dumb) | Forces the agent to treat the factual claims in your request as suspects — checking the load-bearing ones against primary sources before building on them — and to explain each technical term and choice as it goes, so you stay able to follow and verify your own project even outside your expertise. |
| [are-we-doing-things-right](skills/are-we-doing-things-right) | Breaks an endless fail-fix-retry loop by running a five-step stop-and-diagnose protocol before trying again — restates the problem, names the earlier decision most likely at fault, and weighs alternatives outside what's already been tried. |
| [write-it-right](skills/write-it-right) | Keeps conversation context from leaking into documents meant for someone who wasn't there — names the reader before writing, ships each visible value bare and offers any note beside it as an option, describes the current state instead of the change that produced it, and cuts every sentence serving the writer rather than the reader. |
| [fix-my-context](skills/fix-my-context) | Repairs a project's agent docs in one pass, run only when you invoke it — finds out what each doc was for and what still reads it, fixes the rules that make docs grow before pruning them, and applies the changes you approve on a branch, with before/after measures of the doc set. |

## Evals

Each skill ships with its own eval harness in [`evals/`](evals).

### Judged behavioural harnesses

`im-dumb`, `are-we-doing-things-right` and `write-it-right`. Needs `jq` and the `claude` CLI.

```
cd evals/im-dumb && ./run-eval.sh        # RUNS=5, ~45-55 model calls
cd evals/im-dumb && RUNS=1 ./run-eval.sh # smoke
cd evals/im-dumb && ./test-parse.sh      # extractors only, no model calls
```

A harness replays each scenario N times, has a judge grade every run against a written rubric
([`judge-rubric.md`](evals/im-dumb/judge-rubric.md)), and passes a scenario only if at least
`PASS_MIN` runs pass — one deviant output is model variance, not necessarily a defect. Sessions
are neutralised (`--setting-sources ""`, and the plugin loaded session-only via `--plugin-dir`)
so nothing installed locally contaminates the measurement. Negative scenarios check that the
skill stays *silent* when it should. Where a skill's main failure mode is doing too much of its
own job, the rubric grades that too — `no_overcorrection` in `im-dumb` and `write-it-right`.

**What this measures:** behavioural conformity — the skill triggers when it should, stays quiet
when it shouldn't, and follows its own protocol. **What it does not measure:** whether the skill
improves the outcome of real work. Recorded runs: [`evals/RESULTS.md`](evals/RESULTS.md).

### Script tests — `fix-my-context`

A `fix-my-context` pass covers a whole repository, with the user deciding at each stage, so no
scenario replays it end to end. Its harness tests the two scripts the skill takes its facts from:
unit tests build a fixture repository — docs, pointers, installed skills, transcripts, auto
memory — and check what `inventory.py` and `behaviour_test.py` report on it. Needs `python3` and
`git`; `behaviour_test.py` runs against a stub `claude`, so no model is called.

```
cd evals/fix-my-context && python3 -m unittest discover
```

**What this measures:** the facts the scripts hand the agent — what reads each doc, what points to
it, what repeats, the before/after counts — are correct on a known repository. **What it does not
measure:** the agent's judgement and questions during a pass. Those are validated by running a
full pass on a real project, with its owner in the session.
