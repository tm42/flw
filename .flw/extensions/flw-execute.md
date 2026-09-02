# Executing in flw

**Three checks, all of which run here**, in about eight seconds together:
`.venv/bin/pytest -q`, `.venv/bin/ruff check .`, `.venv/bin/python core/scripts/budget.py`.
Nothing is handed back as `[tests] yours`. There is no `[tests] checks` on purpose — a
targeted subset would make plain `flw test` weaker than `-A` and save nothing.

**A new flag is declared in the contract before the parser gets it.**
`tests/test_cli.py:3056` diffs `build_parser()` against the CLI component's `surfaces`
lines, so an undeclared flag fails the suite and so does a declared one nobody built.

**Editing `cli/flw.py` changes the `flw` you are running.** When the change is in the
parser, run `.venv/bin/pytest -q tests/test_cli.py` directly rather than through
`flw test`.
