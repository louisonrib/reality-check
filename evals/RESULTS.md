# Eval results

Recorded runs of the harnesses in this directory. Raw run logs are not published — every number
below is reproducible from this repo: `cd evals/<skill> && ./run-eval.sh`.

What these runs measure is **behavioural conformity** — the skill triggers when it should, stays
quiet when it shouldn't, and follows its own protocol. They do not measure whether the skill
improves the outcome of real work.

Model: `sonnet` for both the assistant under test and the judge, on every run below.

## Reference runs — `RUNS=5`, `PASS_MIN=4`

The harness default. A scenario passes only if at least 4 of its 5 runs pass, because one deviant
output is model variance rather than a defect.

### `im-dumb` — 2026-07-12

| Scenario | Checks | Result |
|---|---|---|
| `declaration-trigger` | fires on an explicit "total beginner here", declares provenance, glosses terms | 5/5 |
| `material-premise` | blocks on the load-bearing false premise, declares provenance, glosses terms | 5/5 |
| `benign-premise` | corrects a weightless false premise in ≤ 1 sentence and still delivers the work | 5/5 |
| `no-false-premise` | nothing to correct → no manufactured doubt, terms still glossed | 5/5 |
| `no-declaration` | **negative** — stays silent absent a declaration (deterministic, no judge) | 5/5 |

### `are-we-doing-things-right` — 2026-07-11

| Scenario | Checks | Result |
|---|---|---|
| `literal-loop` | fires when the same attempt keeps failing | 5/5 |
| `false-fix-cycle` | fires when the user says "still broken" after a claimed fix | 5/5 |
| `non-code` | fires outside code, on a non-technical stuck point | 5/5 |
| `manual` | runs the full protocol when invoked by name | 5/5 |
| `no-loop` | **negative** — stays silent when nothing is stuck | 5/5 |

### `write-it-right` — 2026-07-15

| Scenario | Checks | Result |
|---|---|---|
| `readme-trigger` | fires before writing a persistent doc, and delivers it | 5/5 |
| `doc-contaminated` | delivers the doc with zero conversation residue | 5/5 |
| `adr-record` | keeps the reasoning a decision record exists to carry | 5/5 |
| `clean-copy` | does not over-edit prose that is already fine | 5/5 |
| `changelog-prose` | describes current state, not the change that produced it | 4/5 |
| `no-trigger` | **negative** — stays silent on a throwaway note | 5/5 |

`changelog-prose` 4/5: in one run the assistant asked the user clarifying questions instead of
writing the document. Every other criterion in the rubric passed on that run. This is the
tolerance threshold doing its job — not a green light laundered from a red run.

## Confirmation smoke — `RUNS=1`, 2026-07-29

The plugin was renamed to `reality-check` after the reference runs above. Each harness matches the
skill id it expects (`grep -qx "$SKILL_ID"`), so a rename can silently break the measurement
without touching a single skill. This run exists to prove it did not: all three reports carry
`reality-check:<skill>`, and every scenario that requires an invocation passed.

`RUNS=1` forces `PASS_MIN=1` — zero tolerance by construction. Three of sixteen scenarios did not
come back green, and none of the three is a change in skill behaviour:

- `im-dumb / no-false-premise` → verdict `error`. The scenario run returned
  `API Error: 529 Overloaded`. When the judge output is unreadable the harness records `error`
  rather than a silent verdict, so this counts as neither a pass nor a fail.
- `are-we-doing-things-right / no-loop` → verdict `error`. The run itself was correct — the skill
  stayed silent, as this negative scenario requires — but the judge call returned nothing.
- `write-it-right / changelog-prose` → verdict `fail`, with `work_delivered: false` and every
  other rubric criterion passing. This is the same deviation as the 1-in-5 run recorded on
  2026-07-15, and at `RUNS=1` there is no tolerance left to absorb it.

The `SKILL.md` files under `skills/` were byte-identical to the published ones at the time of both
sets of runs.
