# Reviewing flw

**Mutation is the method that has worked here**: revert one production line in a clone,
run `.venv/bin/pytest -q`, and a green suite is the finding. Nine survived mutations were
filed that way against `finish-the-store`. 638 tests in 7.3 seconds, so the loop is cheap.

**Prose is a reviewable surface.** `core/skills/*/SKILL.md` and `core/shared/*.md` are
instructions to every later run, so a sentence that reads two ways is a defect the way a
branch can be. `core/scripts/budget.py` holds each of them to a byte ceiling.

**Past reports are in `.flw/reports/`, gitignored, 44 of them.** Read the ones covering
your scope first: a finding already filed and deliberately left is a decision, and the
record that took it is under `specs/versions/`.
