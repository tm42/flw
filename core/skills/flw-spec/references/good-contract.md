# What a good contract looks like

Read during the interview, and again by the critic. Seven rules, each of which flw's own
contract has broken at least once.

## Every `provides` is something a **user** can do

> ✅ "A user can recover a note deleted in the last 30 days."
> ❌ "There is a `TrashService` with a 30-day retention policy."

The second is an implementation talking about itself. It cannot be checked by anyone who
does not already read the code, and it goes stale the moment the class is renamed.

The test: could someone who has never seen the code tell whether this is true?

## A component that provides nothing is a file list

If you cannot say what a user gets from it, it is not a component — it is either part of
another one, or an implementation detail that belongs in `implementation`.

## `implementation` holds only what is binding

A constraint whose violation would need a re-spec.

> ✅ "SQLite, one file per user. No ORM."
> ❌ "Probably use a dataclass for the row type."

If it does not constrain, it is not spec. It belongs in the version file's `approach`, or
nowhere.

## Assumptions are testable propositions

> ✅ "Input files fit in memory; there is no streaming requirement."
> ❌ "The data is small."

The first can turn out false in a way you would notice. The second cannot.

An assumption is worth recording when its being wrong would force a redesign. "Doesn't
matter here" is a legitimate answer to an interview question — record it as an assumption
so it surfaces if it later does matter.

## Tests are commands that actually run in this repo

Not aspirational ones. `pytest -q` is wrong if pytest lives in `.venv/bin`. A test nobody
has ever run is a test that fails the first time it matters.

Run them once before locking the contract.

## `criteria` says what the tests cannot

A green suite is not the same claim as the work being done. `criteria` is where you say
what a human has to look at, what could not be automated, and what "working" means beyond
exit zero.

## Open questions are recorded, not answered by assumption

A contract with a live question in it is honest. A contract that quietly picked an answer
is a bug with a delay on it.

---

## The shape of the whole thing

Five questions, one home each. If something does not fit, it probably is not contract.

| Question | Field |
|---|---|
| What exists when this is done? | `final_state.components[]` |
| What can a user do with it? | that component's `provides[]` |
| What is gone? | `final_state.removed[]` |
| How do we know it works? | `success_criteria` |
| What would force a redesign if false? | `assumptions` |

Nothing lives in two places. Nothing is homeless.

## What is not contract

- **How to get there.** That is the version file.
- **Why you chose this over that.** Also the version file, in `decisions`.
- **Durable project rules** — "all IO goes through the adapter layer". If it binds the
  product, it is an `assumption` or a component's `implementation` note here. If it is
  how flw operates in this repo, it is `.flw/extensions/<skill name>.md`.
