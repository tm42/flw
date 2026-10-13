# Autonomy boundaries

Where the limits on what an agent may do here are already written down. Read when you need
to know whether something is yours to decide or the user's, and cite the place rather than
this file.

This adds no mechanism. Every boundary below is recorded in an artifact flw already has;
what was missing was a single page saying which artifact holds which.

## The boundaries, and where each one lives

**Decisions already approved** — a record's `decisions` in `specs/versions/<name>.toml`.
Each carries the options that were on the table and why one was chosen, so a decision you
are about to re-open may already be settled with a reason.

**Decisions still needing the user** — the contract's `open_questions`. A question sitting
there is not an oversight; it is a thing nobody has decided, and deciding it quietly is the
failure.

**Files and behaviour you may change** — a component's `paths`, `properties` and
`surfaces` in `specs/current.toml`. A directory-valued path covers new files inside it; a
path naming specific files does not extend to a sibling.

**Which tests and commits are authorised** — `success_criteria.tests` in the contract and
`[tests] checks` in `.flw/config.toml` for the checks; `$FLW/core/shared/commits.md` plus
propose-never-perform for the commits. flw stages by name and never commits.

**What stays the user's to run** — `[tests] yours` in `.flw/config.toml`. A check declared
there is not a failure and not a mystery: it is work this session cannot do.

## The two that are not recorded yet

**What a gap in the contract classifies as.** `flw-execute` says a gap becomes a proposal,
and nothing says whether a given gap is a minor amendment or a change of scope. The
executor decides in the moment and the decision is not written anywhere.

**What a skipped check means.** A check that could not run is not a check that passed, and
that is as far as it goes — there is no declared form for a check that requires something
absent, so a skip and a failure are told apart by a human reading the output.

Both are later records. Until they land, both are the user's call and neither is yours to
settle on your own.

## Why this is a page and not a manager

A separate agent supervising the work was measured and is not worth its cost: it mostly
repeats context that is already in the artifacts, and it raises the price of every step.
The same result arrived from the other direction when review teams were run against flw's
own tree — they returned findings about wording and confirmed what had already been
verified. The boundaries are cheap to read and expensive to re-derive, which is why they
belong in files rather than in another context.
