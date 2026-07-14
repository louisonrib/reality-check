---
name: are-we-doing-things-right
description: >
  Break out of a stuck loop by stepping back instead of trying again. Use when
  the user signals that a result you presented as good is still wrong (you
  fixed it → "still broken"; you corrected it → "still not what I meant"),
  when the same attempt — or a light variant of it — keeps failing, when the
  user asks "are we doing things right?", or when they say they feel stuck or
  that you are going in circles — in any activity: code, configuration,
  writing, design, advice.
---

# Are We Doing Things Right?

You are here because the current approach is suspect: either the same attempt
keeps failing, or — more often — you believed the work was done and the user
keeps telling you it is not. Treat that second signal as seriously as a hard
error: **the user's judgment is the failure signal**. Do not defend the work;
investigate it.

## The protocol

Run all five steps, in order, before any new attempt.
Write your findings in plain language a non-expert can follow — they must be
able to arbitrate at the end. Explain any technical term the moment you use
it.

### 1. Stop

No new attempt, fix, or variant while you run this protocol. The next try, if
any, comes out of step 5 — not out of reflex.

### 2. Restate the problem cold

In 2-4 sentences, from scratch: what does the user actually need — not the
task you have been iterating on? Zoom out: if the current sub-task vanished,
what would success still look like? If your restatement and the work you have
been doing don't match, say so plainly.

### 3. Retrospective suspicion (mandatory)

List the significant decisions, assumptions, and productions made earlier —
**including the ones that seemed fine and anything already validated**. Work
from whatever record you have: your own visible history, or the user's
account of it if that's all there is. Thin material is still material — do
not stall this step to ask for more of it first. Name at least one as the
prime suspect and
say why. The real fault is often not in the last step but in something older
that everything since was built on. If you genuinely cannot name a suspect
even from what's available, say so and treat your framing of the problem
(step 2) as the suspect.

### 4. Alternative hypotheses, outside the current scope

Propose at least two explanations or approaches that live outside what you
have been varying so far — a different layer, a different assumption, a
different interpretation of what the user meant. "The same thing, but more
carefully" is not an alternative.

### 5. One justified attempt — or escalate

Either pick ONE next attempt and state explicitly how it differs from every
previous attempt (which suspect from step 3 or hypothesis from step 4 it acts
on) — or, if no attempt clearly differs, escalate to the user with an honest
summary: what was tried, what is known, what is not, and two or three options
with their trade-offs, in plain language, so they can decide.

## After the protocol

If the justified attempt fails too, escalate as in step 5 — one protocol
pass per stuck point.
