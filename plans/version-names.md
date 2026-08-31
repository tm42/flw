# Version records identified by name, not by a number

## The problem

`specs/versions/` is a single numbered line. Every record carries `base`, the number of the
record before it, and `check_chain` walks that line expecting exactly one predecessor per
record. The number is a global counter.

That works for one person building one thing at a time. It fails the moment two people
spec in parallel, which is the ordinary case the workflow claims to support: a service, a
feature X, a colleague's feature Y. Both branch from 4.6. Both write `v4.7.toml`. The
filenames collide, the `base` values collide, and whoever merges second has to renumber a
file that was already reviewed and agreed.

Renumbering at merge time is the failure to avoid. The version record is the durable
account of how a change came about; rewriting its identity when it lands means the file in
git is not the file anyone reviewed.

## The shape

A version's identity is its **name**, chosen when it is specced and never changed.
`specs/versions/add-build-posture.toml`, not `v4.7.toml`. Two people cannot pick the same
name by accident the way they cannot pick the same branch name by accident, and if they do,
git reports the collision as a conflict on a file rather than silently accepting two records
that claim the same number.

**Order lives in the contract, not in the records.** `specs/current.toml` gains `applied`,
an ordered list of the record names whose runs have finished. `flw-execute` appends to it
when a run completes, in the same step that already applies `contract_edit`. The order is
written once, where the work actually landed, rather than being inferred from a chain of
`base` pointers that only one branch can hold.

**The release number stays on the contract.** `spec_version` in `current.toml` remains, and
remains a number a human sets. That is what the user asked for: names on the branches,
versions preserved in main.

**`base` survives with a narrower job.** It stops being the ordering mechanism and becomes
what it was always useful for: a note of which contract state this was specced against, so
`flw validate` can say when a version was written against a contract that has since moved.

**MAJOR/MINOR becomes a word.** The number carried one real bit — whether the change deletes
or replaces something. That bit moves to a `kind` field, `"additive"` or `"replacing"`,
which is legible where a digit position was not.

## Migration

The seventeen existing records keep their filenames. `v4.6` is a perfectly good name; it is
only a bad *counter*. `applied` lists them in the order they landed, which is the order
their numbers already imply, so nothing has to be renamed and every reference in a commit
message, a review report or a design document still resolves.

New records get kebab-case names. Nothing forces the old ones to be rewritten.

## What this is not

Not a change to what a contract or a version record says — only to how a record is
addressed and how the order is stored. Not a git integration: flw still runs no VCS
commands. Not an attempt to merge two contracts automatically; two branches editing the
same contract sentence is a text conflict, and git already reports those.

## What it costs

`check_chain` is rewritten: the numeric sort and the single-predecessor walk both go, and
in their place it checks that every applied name has a file, that names are unique, and
that a record not yet applied is in flight rather than missing. `flw-execute` appends to
`applied` instead of setting a number. The version schema gains `name` and `kind` and
loosens `spec_version`. Three skills and `context.md` describe the numbering and have to
describe naming instead.

The crash fixed on 2026-08-25 — `check_chain` raising `ValueError` on any filename that is
not `v<int>.<int>` — is what this change would have hit on every file, so it is a
precondition rather than a coincidence.
