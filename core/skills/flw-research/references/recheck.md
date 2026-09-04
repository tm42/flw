# Re-check mode

Read when the ask is to check what a survey already recorded, rather than to run one.
A full survey scouts a repository, probes how it runs, and rewrites its store. A re-check
reads what is on disk, says what moved under it, and rewrites the files the evidence
names. It is triggered by the ask and never by a flag, so it composes with being handed a
list of paths.

## What triggers it

*"Is what we recorded still true?"*, *"re-check the store"*, *"flw stale says these three
knowledge files have changed under them"*, or a list of paths with no other instruction.

`flw stale` is what produces such a list. It prints which knowledge files the code has
moved under, which extensions and notes carry a claim a commit could falsify, and which
review reports nobody has read. It reports shape and never truth: it cannot say whether
`638 tests in 7.3 seconds` still holds, because finding out costs a run. That run is this
mode, and it is the only place in flw where a claim is judged rather than measured.

## What it skips, and why

**Step 1's scout does not run.** Its product is orientation, and orientation is what the
recorded store already is. Scouting a repository whose architecture you are about to read
off disk answers a question nobody asked.

**A step 2 probe whose answer is in `.flw/config.toml` does not run again.** `[tests]
checks`, `setup` and `yours` were settled by a survey that ran them. Re-running a probe
whose answer is recorded costs a build and can only agree. Re-run one when the evidence
under it moved — a changed `Makefile`, a new lockfile, a CI workflow that was rewritten —
and say which and why.

**Step 4 does not rewrite the tree.** A survey writes a store; a re-check corrects the
files whose claims the diff falsified, one at a time, and stamps each with `flw know
--stamp`. Rewriting a file the diff did not touch puts words in the store nobody asked for.

## What it does

1. **Take the paths.** From the ask, or from `flw stale`, or — given neither — from
   `flw know --check`, which names every file the code has moved under.
2. **Read the recorded claim and the code beside it**, per path. `flw know <path> --full`
   gives the claim; the diff since that file's revision gives what moved.
3. **Decide, per file, and say which.** The claim survived and only the revision is
   behind → re-stamp it. The claim is now false → rewrite that one file and stamp it. The
   file describes a directory that is gone → say so and let the user decide, because
   deleting a knowledge file is not this mode's call.
4. **An extension or a note is different.** Neither carries a revision, so nothing can say
   how far it has drifted and the diff cannot decide for you. Re-take the measurement — run
   the check, open the file at the line — and either correct the line or say it still holds.
   A countable that keeps needing this is a knowledge fact in an extension, and moving it is
   a proposal to the user rather than an edit you make.

## What it reports

```text
flw-research — <repo>, re-check
  Read:        <n> files · <n> the code moved under
  Re-stamped:  <files whose claim survived>
  Rewrote:     <files whose claim the code falsified>
  Still true:  <claims re-measured and unchanged>
  For you:     <what needs a decision, or nothing>
```

`Still true` is the row that makes the mode worth running: a claim re-measured and
unchanged is a result, and a report that lists only what it rewrote reads as though nothing
was checked.

## What it is not

**Not a sweep that deletes.** Nothing here removes a document. `flw stale` lists and the
user acts, and this mode is the judgment between those two, not a third thing that tidies.

**Not a re-survey.** If the recorded store describes a repository the code no longer
resembles — a rewrite, a directory tree that moved wholesale — say so and run the full
survey instead. Correcting fifteen files one at a time is the expensive way to do what
step 4 does in one pass.
