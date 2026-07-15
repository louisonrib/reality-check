---
name: write-it-right
description: >
  Use when about to write or substantially edit a persistent prose file
  whose reader is not in the current conversation — documentation, a
  README, an agent prompt or skill, a decision record — and when the user
  asks for a pass on a file that reads wrong. Not for commit messages,
  code comments, chat replies, or throwaway notes.
---

# Write It Right

You are about to write something whose reader is not here. Everything you
know right now — this conversation, the change you just made, the
decisions settled along the way — is exactly what the reader does not
share. Fresh context leaks into documents by default; your job is to keep
the document the reader's, not yours.

## Before writing: name the reader and the job

One sentence, to yourself: who reads this file, knowing what, to do what?
Then the document's single job: teach, get a task done, describe what is,
or record a decision. A sentence that serves another job belongs
elsewhere — link to where it lives, or leave it out. Never embed it.

## The three tests

Run every sentence — written or about to be written — through all three.

### 1. The reader test — no conversation residue

Would the target reader, with no access to this conversation, understand
this sentence and need it? Cut what fails:

- process narration: "we decided to…", "after trying X…", "as discussed"
- the requester's voice: "the error handling you asked for"
- settled decisions replayed: the record that made the decision owns the
  why; state the outcome and link the record.

The test is relative to the document's job. In a decision record, the
reasoning IS the content — keep it; but "as discussed earlier" still
fails there, because the reader wasn't in the discussion.

### 2. The state test — describe what is, not what changed

Would this sentence stay true and informative for a reader who never knew
the previous state? Rewrite what fails:

- "now supports", "no longer", "used to", "new", "currently", "as of…"
- what the thing does NOT do — unless the reader would wrongly expect it
- version numbers, dates, and future promises that rot in place

Exception: a changelog or release notes — there, the delta is the job.

### 3. The cost test — every sentence pays its way

Does this sentence serve the named reader's need enough to justify their
time? The most useful information comes first — no warm-up preamble, no
meta-commentary ("This section describes the options" → give the
options). No filler or difficulty-minimizers: "simply", "just", "note
that", "it's worth noting". Structure stays proportionate to content:
three sentences don't need four headings. Depth follows the reader's
need, not symmetry across sections.

## Cross-cutting rules

- One home per fact: already written somewhere? Link, don't restate.
- One term per thing, everywhere. Synonym variety reads as new entities.
- Show over tell: one example or command beats a paragraph about it.

## On an existing file

Apply the three tests as a purge, sentence by sentence. Report what you
cut and why in the conversation — never inside the document. If a cut
removes information some other reader needs, move it to the file that
owns it — or name the missing home — instead of deleting it silently.
