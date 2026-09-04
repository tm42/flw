# Executing in flw

**Every check the contract declares runs here**, and nothing is handed back as
`[tests] yours`. There is no `[tests] checks` on purpose — the full set is fast enough that
a targeted subset would make plain `flw test` weaker than `-A` and save nothing.

**A new flag is declared in the contract before the parser gets it.**
`tests/test_cli.py` diffs `build_parser()` against the CLI component's `surfaces` lines —
search it for `_parser_surface` — so an undeclared flag fails the suite and so does a
declared one nobody built.

**Editing `cli/flw.py` changes the `flw` you are running.** When the change is in the
parser, run `.venv/bin/pytest -q tests/test_cli.py` directly rather than through
`flw test`.
