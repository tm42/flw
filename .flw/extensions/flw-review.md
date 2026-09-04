# Reviewing flw

**Mutation is the method that has worked here**: revert one production line in a clone,
run `.venv/bin/pytest -q`, and a green suite is the finding. Nine survived mutations were
filed that way against `finish-the-store`. The suite runs in seconds, so the loop is cheap.

**Prose is a reviewable surface.** `core/skills/*/SKILL.md` and `core/shared/*.md` are
instructions to every later run, so a sentence that reads two ways is a defect the way a
branch can be. `core/scripts/budget.py` holds each of them to a byte ceiling.

**Past reports are in `.flw/reports/`, gitignored.** Read the ones covering
your scope first: a finding already filed and deliberately left is a decision, and the
record that took it is under `specs/versions/`.
