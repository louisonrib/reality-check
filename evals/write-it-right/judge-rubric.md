You are grading a document produced by an AI assistant. The assistant may
or may not have been operating under a writing discipline whose contract
is: write for the reader — a person outside the conversation that
produced the document — describe the current state rather than changes,
and make every sentence pay its way.

Grade ONLY the produced document (the file content), not the assistant's
conversational reply around it — except for work_delivered, which checks
the document exists, and except where a criterion explicitly mentions the
reply.

Definitions:
- CONVERSATION RESIDUE: any content only meaningful to a participant of
  the producing conversation — process narration ("we decided", "after
  trying", "as discussed", "you asked for"), references to the requester,
  or replayed back-and-forth from the conversation.
- DELTA PROSE: sentences describing a change or transition rather than
  the current state — "now supports", "no longer", "used to", "the old X
  is gone", "new" — or version/date anchors that will rot.

Reply with ONLY a JSON object, no prose, no code fences:
{
  "work_delivered": <true if the requested document was actually
    produced with the requested substance (the facts the request asked
    for are present)>,
  "reader_framed": <true if the document contains NO conversation
    residue per the definition above>,
  "state_described": <true if the document contains NO delta prose per
    the definition above — it describes what is, never what changed.
    Vacuously true if the request did not involve a prior state>,
  "reasoning_kept": <true if the document preserves the substantive
    justification of the decision it records (the trade-off, the why) —
    only meaningful for decision records; true otherwise>,
  "cost_paid": <true if the document leads with the most useful
    information, has no warm-up preamble or meta-commentary about
    itself, no filler ("simply", "note that", "it's worth noting"), and
    no structure disproportionate to its content>,
  "no_overcorrection": <true if sound content was NOT damaged: correct
    facts preserved, no needless restructuring of healthy text, nothing
    the reader needs was cut. Vacuously true if nothing sound was given>,
  "reason": "<one short sentence>"
}
