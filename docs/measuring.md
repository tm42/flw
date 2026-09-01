# Measuring flw

A protocol, not a benchmark suite. Its job is to make numbers from two machines comparable, which
takes a fixed corpus and a fixed set of commands more than it takes a stopwatch.

Point an agent at this file. It needs the repository, a Python 3.11 or later interpreter, and
nothing else — no install, no `flw install`, no network.

## What is worth measuring, and what is not

flw does almost no computation. It manages symlinks, merges config, reads TOML and shells out.
Three commands do real work and they are the ones to time:

- **`flw scout`** parses every source file and runs PageRank over the import graph. It scales
  with the repository.
- **`flw kb`** walks and parses both note stores on every query, with no index on disk. It scales
  with the store.
- **`flw ledger`** searches the contract and version records. Its corpus is bounded by how much
  a project has specced, which is small and grows slowly.

`flw install`, `flw doctor`, `flw sync` and `flw validate` are filesystem work over tens of files.
Time them once to confirm they are trivial; do not build a corpus for them.

**Report what surprises you, not what confirms this document.** A number matching the baseline
below is worth one line. A number three times the baseline is the finding.

## Building the corpora

Both generators are seeded, so the same size gives the same corpus on every machine. Copy them
into a scratch directory — they are deliberately not shipped as scripts, because they are for
measuring flw and not part of it.

### A note store

```python
# gen_store.py — python3 gen_store.py <dir>/kb <n> [--degenerate]
import random, sys
from pathlib import Path

STEMS = ("resolver lockfile venv proxy egress keychain discriminator literal enum autovacuum "
         "pagerank symlink barrel transitive damping frontmatter checkout quarantine idempotent "
         "coalesce truncation provenance migration throttle backoff sharding replica cursor "
         "vacuum bloat planner index scanner buffer").split()
CATS = ["python", "python/pandas", "rust", "go", "macos", "ci", "docker", "k8s",
        "terraform", "flw", "postgres", "node"]

root, n = Path(sys.argv[1]), int(sys.argv[2])
degenerate = "--degenerate" in sys.argv
rng = random.Random(7)
for i in range(n):
    d = root / CATS[i % len(CATS)]
    d.mkdir(parents=True, exist_ok=True)
    title = " ".join(rng.sample(STEMS, 3))
    if not degenerate:
        # A distinguishing token, as a real title has: a version, a name, a number.
        title += f" case{i:05d}"
    body = " ".join(
        rng.choice(STEMS) + ("" if degenerate else str(rng.randint(0, 400)))
        for _ in range(400)
    )
    (d / f"note-{i:05d}.md").write_text(
        f'+++\ntitle = "{title}"\ndescription = "one line"\ntype = "gotcha"\n'
        f'tags = ["{STEMS[i % len(STEMS)]}"]\nupdated = 2026-01-01\n+++\n\n{body}\n')
print(f"{n} notes in {root}")
```

`--degenerate` draws every title from one small vocabulary, so nearly every note is a genuine
near-duplicate of every other. That is not a realistic store; it is the worst case, and it is
worth running because it is where the only known non-linear cost lives.

### A source tree for the scout

```python
# gen_tree.py — python3 gen_tree.py <dir> <n>
import random, sys
from pathlib import Path

root, n = Path(sys.argv[1]), int(sys.argv[2])
rng = random.Random(3)
pkgs = [f"pkg{i:02d}" for i in range(max(4, n // 100))]
mods = [f"{pkgs[i % len(pkgs)]}.mod{i:05d}" for i in range(n)]
for name in mods:
    pkg, mod = name.split(".")
    d = root / pkg
    d.mkdir(parents=True, exist_ok=True)
    (d / "__init__.py").touch()
    imports = "\n".join(
        f"from {t.split('.')[0]}.{t.split('.')[1]} import Thing{t[-3:]}"
        for t in rng.sample(mods, min(6, len(mods))) if t != name)
    body = "\n".join(f"def helper_{j}(x):\n    return x + {j}\n" for j in range(8))
    (d / f"{mod}.py").write_text(
        f"{imports}\n\n\nclass Thing{name[-3:]}:\n    pass\n\n\n{body}\n")
print(f"{n} modules in {len(pkgs)} packages")
```

## Running it

`FLW_HOME` points flw at a scratch machine-wide store, so nothing touches your real `~/.flw/`.
Run from the repository root. `cli/flw.py` is the entry point and needs no install.

```sh
S=$(mktemp -d)
python3 gen_store.py "$S/store/kb" 1000
python3 gen_store.py "$S/degen/kb" 1000 --degenerate
python3 gen_tree.py  "$S/tree" 8000

for cmd in "-s" "search proxy" "-c python" "lint"; do
  printf '%-18s ' "flw kb $cmd"
  FLW_HOME="$S/store" /usr/bin/time -p python3 cli/flw.py kb $cmd >/dev/null
done
printf '%-18s ' "flw kb lint (degen)"
FLW_HOME="$S/degen" /usr/bin/time -p python3 cli/flw.py kb lint >/dev/null

/usr/bin/time -p python3 cli/flw.py scout "$S/tree" >/dev/null
/usr/bin/time -p python3 cli/flw.py ledger locking >/dev/null
/usr/bin/time -p python3 cli/flw.py doctor >/dev/null
```

Take the `real` line. Run each twice and report the second, so a cold filesystem cache is not
what you measured.

To find *where* a slow command spends its time rather than only that it is slow:

```sh
python3 -c "
import cProfile, pstats, sys
sys.path.insert(0, 'core/scripts')
from pathlib import Path
import store
notes = store.walk(Path('$S/degen'), None)
cProfile.run('store.lint(notes)', sort='tottime')" 2>&1 | head -20
```

## The baseline

Apple M3 Pro, macOS 26.6.2, Python 3.12.14, at flw 0.11.5. Wall clock, second run.

| command | corpus | time |
|---|---|---|
| `flw kb -s` | 1,000 notes | 0.10 s |
| `flw kb -s` | 4,000 notes | 0.27 s |
| `flw kb search proxy` | 4,000 notes | 0.44 s |
| `flw kb lint` | 1,000 notes, varied titles | 0.24 s |
| `flw kb lint` | 4,000 notes, varied titles | 0.94 s |
| `flw kb lint` | 1,000 notes, `--degenerate` | 0.84 s |
| `flw scout` | 500 files | 0.18 s |
| `flw scout` | 2,000 files | 0.59 s |
| `flw scout` | 8,000 files | 2.25 s |
| `flw ledger locking` | this repository | 0.08 s |
| `flw doctor` | this repository | 0.05 s |
| `flw validate` | this repository | 0.09 s |

About 20 ms of every one of those is interpreter startup, so the small numbers are partly Python
booting rather than flw working.

**This table replaces one measured on Python 3.11.14, and the whole table was re-run rather than
corrected row by row, because a table measured on two interpreters is not a baseline.** Two
things a reader comparing against the old one should know. The `flw kb search proxy` row read
0.03 s and was wrong: it sat below the interpreter's own startup floor, and the store is parsed
in full on every query, so a search cannot beat `flw kb -s` over the same corpus. It was never
0.03 s. The three `flw scout` rows are genuinely about 1.7x their 3.11 figures, which is the
3.12 slowdown already recorded in `specs/versions/declared-behaviour-major.toml` and not a
regression in flw.

## What is already known, so nobody re-finds it

- **`flw kb lint` is bounded by how many duplicate pairs the store actually contains**, not by
  its note count. A store whose titles all draw on one small vocabulary holds n²/2 genuine pairs
  — 499,500 at 1,000 notes — and enumerating those is quadratic whatever the algorithm. That is
  what `--degenerate` measures. It was 15.2 s at 1,000 notes and over 120 s at 4,000 before
  commit `1aa8775`.
- **`walk` holds every note's body in memory at once.** A single 256 MB note was measured taking
  the process to 568 MB RSS. Nothing refuses an enormous body. Worth re-measuring the shape of
  that curve on a machine with less memory.
- **`flw scout` extrapolates to roughly 3 s at 20,000 files**, which is what the contract claims.
  It has not been measured at that size on real code, only on generated trees — a real
  monorepo is the interesting test, because generated imports resolve cleanly and real ones do
  not.
- **The TypeScript scout has no numbers at all.** It runs on the target repository's own
  `typescript`, so it needs a real TS monorepo to measure and none has been.
- **Two concurrent `flw kb write` calls with the same title both succeed and the later wins.**
  The refusal is check-then-write with no lock.

## The trap that will waste your afternoon

If you are mutating source to check whether a test catches something, **clear `__pycache__`
between every run.** A timestamp-based `.pyc` validates on `(int(mtime), size)`, so a same-size
edit inside the same integer second is invisible: Python serves the stale bytecode and the test
reports the *unmutated* result, which reads as "the test caught it". Neither
`importlib.invalidate_caches()` nor `python -B` helps — `-B` stops writing bytecode, not reading
a cache that already exists.

## Reporting back

One file. This shape, so two reports compose:

```markdown
# flw measurements — <machine>, <date>

**Machine**: CPU, OS version, Python version, filesystem if unusual
**Commit**: the git SHA measured
**Corpora**: which generators, which sizes, any deviation from the protocol

| command | corpus | time | baseline | ratio |
|---|---|---|---|---|

## What differed
Anything more than ~1.5x the baseline, with the profile output for it.

## What was measured that this document does not cover
The interesting half. Name what you tried and what it showed, including the attempts that
found nothing.

## What could not be run here, and why
```

A number without the machine and the commit beside it cannot be compared to anything, so it is
not a measurement. Say what you could not run rather than leaving the row out.
