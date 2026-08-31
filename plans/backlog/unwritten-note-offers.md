# Two notes were offered and never written

Both passed the write test — measured, and not derivable from this repository — and both are
still only in a session transcript.

- **`Path.read_text()` hides CRLF from a newline-anchored regex.** Offered by the adversarial
  reviewer on 2026-08-31. It applies universal-newline translation, so a `\n`-anchored parser
  matches CRLF input unchanged; the reviewer proved it by `xxd`-ing the bytes. Worth having
  because it is a false positive a reviewer will otherwise file against any such parser.
- **A stale `.pyc` reports a mutation as caught.** A timestamp-based pyc validates on
  `(int(mtime), size)`, so a same-size edit inside one second is invisible; neither
  `importlib.invalidate_caches()` nor `python -B` prevents it. Largely captured now in
  `docs/measuring.md`, so this one may not need a note at all.

**Why they are still here.** Both go to the machine-wide store, which is empty. Writing the first
two notes in it is a decision about starting the store rather than about these two facts.
