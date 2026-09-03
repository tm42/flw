# flw, for every skill

flw is its own subject: this repo builds the skills you are running under. `flw` on
PATH is a symlink into this checkout, so an edit to `cli/flw.py` changes the command you
are running now.

**Stdlib only, by construction.** Nothing under `cli/` or `core/scripts/` may import a
third party. flw exists to stop a workflow assuming a package manager, so it cannot
require one. `.venv/` holds pytest and ruff and nothing that ships.

**Python 3.11 is the floor**, for `tomllib`. `cli/flw.py` runs under whatever `python3`
the machine has and refuses older versions itself, in its first 30 lines, before
importing anything that would fail less clearly.

**Every module opens with a docstring saying why it exists**, not what it does. Read the
first fifteen lines of a file under `core/scripts/` before changing it.

**The knowledge store at `.flw/knowledge/` is gitignored** and local to this checkout.
The tracked store under `core/skills/flw-research/references/knowledge-example/` is a
shipped example, not this project's architecture.
