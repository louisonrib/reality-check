# Stage 2: the base

**On trial.** This stage is a hypothesis: it has been tried on one project. Record in the report what it changed in the pass (what the user removed here, what the later stages no longer had to read), so a later pass can confirm it or drop it.

Whether a folder or a decision still belongs to the project rests on the user's context, which the docs do not hold. Settle it first: what the user removes here is not analysed passage by passage, and the later stages work on a base the user recognises.

## The units

- **Each docs folder** (`folders[]`), from the top down. A subfolder gets its own card when its purpose differs from its parent's. A folder that holds no doc file (`files: 0`, its `other_files` an image, a script, an archive) gets a card too: search the repo for its path to find what uses it.
- **Each decision doc that others cite as a constraint**: a doc that settles something (a decision record, a position, a policy) and that other docs point to (`pointed_to_by`), or that tickets cite under their constraints when the project's issue tracker can be read. Count the docs and tickets that cite it.

## The card

For each unit, establish:

- **Date and who decided.** The date the doc gives itself (`dated`) and its creating commit. Who decided: the user, or an agent session with no request from the user quoted in it (an agent trailer such as `Co-Authored-By` on the creating commit, the session in `created_in_session`). A dated doc with commits after its date (`dated.commits_after`) has been edited since: a decision record "should never be reopened or changed" ([Fowler][fowler] [practitioner]); one that is reversed is superseded by a new record ([Nygard][nygard] [practitioner]).
- **Its use, measured**: sessions that opened its files to use them (`sessions.read`, against the instruction that makes them list or copy, [`provenance.md`](provenance.md), Readers), and the docs and tickets that cite it as a constraint.
- **Its premises, rechecked**: each fact the decision rests on, checked against the project's state today (the code, the audience, the prices, what has shipped since), each with the file:line or command that settles it.
- **Its review triggers**: whether each one is an event that will happen (a launch, a budget, a number of users) or an action no agent takes on its own (adding a dependency). No source was found on how to word a review trigger; say so.
- **A recommendation**, with its reason.

## Showing a decision to the user

Show a decision by its effect on the user: what they see, or what it stops them from doing today ("the sign-up screen asks for X", "you cannot Y"), then ask "is this the intent, or a detail that can change?". A decision with no visible effect is checked against the code and its premises, and enters the report as a card.

In indexes of decisions, look for the words that freeze them ("locked", "immutable", "must never", "do not reopen"). Quote each one with the user's answer: the gap between what the user holds firmly and what the doc freezes is the finding.

## What stays

The user says what belongs to the project. A unit that goes takes its verdict from the table of [`provenance.md`](provenance.md) (archive, mark obsolete, delete, supersede), and that verdict is its whole card. What stays goes on to stage 3, which analyses it passage by passage.

[fowler]: https://martinfowler.com/bliki/ArchitectureDecisionRecord.html
[nygard]: https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions
