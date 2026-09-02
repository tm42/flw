---
name: flw-execute
description: Do the work a version file describes — walk its phases, run the project's declared checks, and refuse to drift from what the contract says. Use after flw-spec has recorded a version.
argument-hint: "[version] [--auto] [--yolo]"
---

# flw-execute — do the work, then check it

## Start here, silently

One command, no narration — do not announce it, do not report it, just run it and begin.
The user asked for the work, not for a description of you preparing to do it.

```sh
flw context flw-execute
```

It prints everything this skill opens with: the shared context, the project root it
resolved and where that came from, this repo's extensions from the outermost project root
inward, the note store listing for this project's category, and the contract's components
with the paths each one covers. Everything below assumes it.

**If the request names a repository, a directory or a file, pass it** —
`flw context flw-execute --root <that path>`. The rule and its reason are in the shared
context the command just printed; this is the only part of it the command cannot tell you,
because you have to call it first.

**Every extension it printed is part of your instructions from here on.**

**If `flw` is not on PATH:** run it out of the checkout — `<interpreter> "$FLW/cli/flw.py"
context flw-execute` — where `$FLW` is the absolute path in `${FLW_HOME:-$HOME/.flw}/root`.
It must be an absolute path: a skill folder is installed as a symlink, and the file-reading
tool collapses `..` lexically before the filesystem resolves it, landing somewhere that
does not exist. If that pointer is missing you may be inside flw's own checkout, so walk up
from the project root for a directory holding both `core/skills/` and `cli/flw.py`.
Nothing → stop and say to run `flw install`.

## Lane, and the one hard rule

This skill builds. It does not author contract changes — it applies the one the version
file already carries, in step 5 — and it does not judge code quality.

**A knowledge file you find wrong is yours to correct.** Rewrite that one file and
`flw know --stamp` it. That one file — not the store, and not a rewrite nobody asked for.
This is not a spec change: the store records what is, and the contract records what was
agreed.

**No silent spec drift.** If you need anything the contract does not cover — a component
that has to exist, a capability nobody agreed to, a check that should have been declared —
**stop and surface a proposal**: what is missing, why you need it, and the specific change
you would make. The user approves, edits or rejects, the change goes through `flw-spec`,
and only then does the code get written.

Never extend the contract by implication. Writing code that assumes an unapproved change
is exactly what this system exists to prevent, and it is not negotiable under time
pressure or a `--auto` flag.

**A `dag` is not an approval.** It was authored and reviewed by a human, which makes it a
plan — not a licence to build something the contract does not describe. When a task and
the contract disagree, the contract wins and the task becomes a proposal. This is the rule
most likely to be read past, because a reviewed plan feels like permission.

**What counts as "the contract does not cover it":** compare the target against every
component's `paths`. A directory-valued path covers new files inside it. A path naming
specific files does not extend to a sibling — a new `core/scripts/render.py` is not
covered by a component listing `core/scripts/run_tests.py`. When it is genuinely borderline,
ask rather than taking the reading that lets you continue.

## Posture

The general engineering posture — read before writing, smallest change that satisfies the
ask, minimal is not partial — is in `$FLW/core/shared/ambient.md`, meant to be installed
into your top-level instructions. What is specific to working from a version file:

- **The plan names what to change; it does not tell you what is already there.** Read the
  code before touching it. "Move X into Y" is not a statement that Y is empty.
- **`approach` outranks `dag`.** The tasks say what; the approach says why, and often what
  the work is *not*. If they seem to disagree, the approach is the one that was thought
  about — surface the conflict rather than picking.
- **Deleting counts as doing.** If a task is satisfied by removing code, remove it.
- **Minimal narration.** Phase headers, one line per task, proposals. Nothing else.

## 1. Find the work

The version files are in `specs/versions/`, one per version, each addressed by the name it
was given when it was specced. Use the one the user named. Failing that, the one the
contract's `applied` list does not name — a record that has been written and not yet run.

**If more than one record is unapplied, ask which.** There is no newest: names do not
order, deliberately, because two people speccing in parallel both branch from the same
contract and neither of their versions comes after the other. Picking one would be a guess
about whose work to build.

**Record where the run starts.** Before writing anything, capture the current commit —
`git rev-parse HEAD`, or the equivalent in whatever VCS the project uses. You cannot
recover it afterwards, and step 5 needs it to show what the run changed. If the project
has no VCS, skip it and say so at the end.

**Then check whether it is already built, before doing anything.** flw tracks no notion of
done, so this is on you and it is not optional: read what the version claims and look for
it in the tree. Components that should exist, files that should be gone, tests that should
be there.

- **Already built** → say so, name the evidence, and ask what they meant. Do not rebuild
  it. Re-running a version's work over a tree that already has it is the most destructive
  thing this skill can do, and nothing downstream will notice.
- **Partly built** → say which parts, and ask whether to continue or start the phase
  again. There is no per-phase record, so you cannot know how far a phase got; a task
  whose output file exists may be half-written. When in doubt, redo the phase rather than
  guessing where it stopped.
- **Not built** → proceed.

## 2. Read the context

Read the contract, the version file, and enough of the tree to
know what already exists.

**Run `flw know <path>` for each path the record names**, and read the plan the record's
`approach` cites. Use `--full` where the work actually lands.

**Now search the note store**, with the terms the version file just gave you — the
components it touches, the libraries, the failure it is about. Titles scanned at the
opening were scanned against nothing; this is the first moment you know your subject. State back in three to five lines: the version, what it
changes, the phases and their task counts, and what is already in place. This is the only
non-terse moment.

**Always ask before writing anything**, `dag` or not — unless `--auto`.

- **With a `dag`**: print the phase list, then ask **"Proceed with phase 1?"**
- **Without one**: the summary and approach are the instruction. Say what you are about to
  do, in a few lines, then ask **"Proceed?"** A version with no dag is small, not
  pre-approved.

`--auto` skips both, and skips them at every later boundary too. It does not relax the
drift rule.

Treat a plain request for an unattended run — *"just do the whole thing"*, *"don't ask me
between phases"* — as `--auto`. Say that you are reading it that way, and say up front that
a gap in the contract will still stop the run.

## 3. Per phase

```
── Phase <n>: <phase> (<k> tasks) ──
```

Work the tasks in dependency order, honouring `depends_on` across groups as well as
within them. One line per task: `  ✓ <id> — <files touched>` or `  ✗ <id> — <reason>`.

A failure aborts the phase. There are no half-phase commits.

At the phase boundary, **propose a commit** — the files touched and a message — and let
the user or their agent make it, in whatever VCS the repo uses. flw does not commit or
tag. It does stage, by name, and step 6 says why.

**Also at the boundary, re-read what this phase falsified.** A run that builds something
has falsified the knowledge file describing that part, and this is the commoner trigger of
the two. For each path this phase changed, re-read the files `flw know <path>` returns
against the code as it now is, and correct what is wrong.

**The `flw know --stamp <file>…` follows the commit**, with `flw know --reindex` once
after it. A stamp records HEAD, so stamping before the commit records the revision from
before this phase, and the first read after the user commits reports the file falsified by
the diff it was just re-read against. When the run makes the commit, stamp right after it.
When the run only proposes one, leave the files unstamped and let step 6's `Knowledge:`
line name them as awaiting the commit, so whoever makes it knows what to stamp.

**What a commit is, and what its message says, are in `$FLW/core/shared/commits.md`.**
Read it before proposing the first one. It is the only place those rules are written, so
nothing here repeats them.

**A phase is the usual unit.** It was authored as one coherent piece of work, so it
normally maps to one commit. Split it only when it holds a change with its own blast
radius — something a reviewer would want to revert alone. Merge across phases when two of
them turn out to be the same part of the product; commits.md decides that, not the dag.

Under `--auto`, propose and keep going rather than waiting. Then say clearly at the end
that the commits were proposed and none were made, and list them in order — otherwise the
run finishes with every phase's work sitting uncommitted and nothing saying so.

## 4. Check it

Run `flw test --no-stream` — plain, which runs the branch set when `[tests] checks`
exists and the contract's full set otherwise. Use `-A` only if the user asked for
everything. It collects the checks you would otherwise have to remember, and
reports rather than judging:

| exit | meaning |
|---|---|
| 0 | everything it ran passed |
| 1 | something it ran failed |
| 2 | the run proved nothing |

**`--yolo` skips this step entirely.** Rules 3 and 4 are unaffected — it changes what the
run *executes*, not what it may *claim*, so a run that skipped its checks may never print
the completion block in step 6, because that block reads as verified. It is for a suite
that runs fine and is too slow to sit through right now. It is not the answer to "these
checks cannot run in this session" — that is `[tests] yours` in `.flw/config.toml`, which
outlives any single run; propose adding a check there instead of reaching for `--yolo`
when the problem is that it cannot run here at all. It composes with `--auto`; neither
implies the other.

The contract names the exit-2 cases. Plain `flw test` still exits 0 when it hands one back
and the rest pass, because declaring a check in `[tests] yours` must not turn every green
run red.

**One kind of check is handed back as yours: one the project declared in `[tests] yours`.**
Nothing is inferred from an exit code. 127 is bash's "command not found", which an absent
binary returns and `npm run <script>` also returns when a devDependency is missing, while
`cargo <subcommand>` returns 101 whether the subcommand is absent or the code failed to
compile. Everything that fails is reported as **failed**, including a check that failed only
because this session has no network or no database — a `curl` with no route exits 7 and a
test that dials out exits 1, and neither is distinguishable from a real failure.

So when you believe a failure is a missing capability rather than broken work:

- **Report it as failed.** You may not reclassify it. A check you could not run is not a
  check that passed, and an agent that gets to decide which failures do not count is worse
  than no check at all.
- **Say what you think and why**, naming the check and the capability.
- **Propose adding it to `[tests] yours`** in `.flw/config.toml`, so future runs hand it
  over instead of failing every time. That file may not exist yet; creating it is
  part of the proposal, and the user decides.

Read the whole table before stopping. `flw test` runs every check regardless of earlier
failures, and Rule 3's "stop" means do not proceed past the check step — not truncate the
report.

## 5. Record it

On a run that completed every phase with `flw test` passing, three edits to
`current.toml`, all ordinary ones:

1. **Append this version's `name`** to the end of `applied`. Appending is what records the
   order versions landed in, so it goes at the end and never in the middle.
2. **Move `spec_version`** by this record's filename: `-major` gives `<line>.<X+1>.0`,
   `-minor` gives `<line>.<X>.<Y+1>`; a record's own `release_line`, when it declares one,
   restarts the count instead, to `<release_line>.0.0`. Say the new number in the report.
   You do not have to get this right from memory: the validate run below folds the same
   number out of `applied` and refuses a contract whose number disagrees.
3. **Apply the version file's `contract_edit`** if it has one.

Skip all three when `applied` already carries that name; they have landed already, from an
earlier run or by hand. Do none of them on a run that stopped, and do none of them on a
`--yolo` run: it moves the contract only once `flw test` has actually passed, and a
`--yolo` run never ran it. Say so in the report (step 6) instead.

**Apply what it says and nothing more.** Do not restate, reflow, or reorder anything the
`contract_edit` did not name. A neighbouring sentence that now reads awkwardly is a
proposal, not a licence — the wording was reviewed at spec time and improving it here puts
words in the contract the user never saw.

**Print `git diff specs/current.toml` on its own, before the run's overall staged diff in
step 6, and paste it into the reply.** This is the diff to read line by line: it should
show exactly the agreement above and nothing else. Commit `cd4aca9` both added the rule in
the paragraph above and violated it, repunctuating two clauses the edit never mentioned —
the contract was one file of eleven in a single staged diff, and a diff that size is
skimmed. A contract edit shown on its own is reviewed; the same edit inside a larger diff
is not.

**Then run `flw validate`.** It is the only check that reads the contract against the record
set, and the three edits above are exactly what it looks at: a name in `applied` that no
record carries, a release number disagreeing with what the records fold to, a `contract_edit`
that produced a document the schema refuses, a duplicate component name making every later
reference ambiguous. `flw test` does not cover this. A project runs the checks it declared,
and validating flw's own documents is not among them — flw's own suite happens to validate
its own contract, which is why this went unnoticed here and would not travel.

**If it fails, stop before step 6 and say what state the tree is in.** Every other stop in this
skill happens before the contract moves. This one happens after, so step 6's STOPPED block is
wrong here — it says the contract did not move. Say instead that the phases completed, that
the contract was written and does not validate, and that nothing should be committed until it
does. Paste validate's own output: it names the document and the disagreement, and neither is
reconstructable from a summary.

If the edit added a `final_state.removed` check, re-run `flw test -A` and say so — that
check has not run in any session yet, and the newly-edited contract is the first thing
that could tell you it fails.

## 6. Report

**Show what the run changed**, from the commit recorded in step 1. Stage the files this
run touched — **by name, the ones from your own task lines** — then diff the index:

```
git add <the files this run touched>
git diff --stat --staged <baseline>
```

**Never `git add -A` or `git add .`.** The user's tree is theirs: a fixture edited for
local testing, a scratch file, a half-finished experiment. A blanket add sweeps those into
the report as though the run made them, and — worse — stages them, so they ride along in
the next commit. Name the files.

Staging is needed at all because an untracked file is invisible to every `diff`, so a run
that created a directory would otherwise report nothing. Staging is not committing.

If the user's own changes were already staged before the run, say so rather than trying to
separate them — the diff will include them and you cannot tell which are yours.

**Paste the output into your reply.** A command's output goes to you, not reliably to the
user's terminal — so a diff you merely ran is a diff they never saw. Drop `| cat` on the
end so no pager or colour escape mangles it, and put the result in the message, above the
report block.

```
flw-execute — <version>
  Phases: <n> of <m>
  Checks: <p> passed · <q> failed · <r> for you
  Knowledge: <files re-stamped · files awaiting the commit, or none>
  Left to do: <what stopped, or nothing>
```

When you stopped on a proposal rather than reaching the end, use this instead — the shape
above implies a run that finished:

```
flw-execute — <version> — STOPPED, awaiting a decision
  Done:        <phases and tasks that completed>
  Stopped at:  <task id> — <what the contract does not cover>
  Uncommitted: <files from this phase, left in place>
  Contract:    not moved — the run did not finish
  Waiting on:  the spec change above, through flw-spec
```

Say where the run stopped, plainly, so the next one can pick up. Do not claim the work is
done — the checks you could not run are the user's to run, and the judgment is theirs.

**A `--yolo` run gets neither block above.** Both read as verified, and this run is not.
Use a shape that cannot be mistaken for either at a glance:

```
flw-execute — <version> — BUILT, NOT VERIFIED (--yolo)
  Phases:   <n> of <m>
  Checks:   skipped by --yolo, not run
  Contract: not moved — flw test has not passed
  Finish it: flw test --no-stream, then record the version once it passes
```

**Then offer a note.** One sentence decides whether there is one: *write it only if it
was measured, and the next agent, in a repository that does not hold this one's history,
could not get it faster than measuring it again.* Almost always the answer is no and you
are done. If it is yes, read `flw kb write --help` first — the rules for what a note
carries live there and nowhere else — then say what you would write. It is an offer, not
a step: the run declines by doing nothing, because a write moment that blocks is a write
moment that gets skipped under pressure.

What belongs here is what the run measured and the version record does not carry: a check
that failed for an environmental reason, a library behaviour the approach had to work
around, a path the plan assumed and the tree did not have.

## Rules

1. **No silent spec drift.** Every gap becomes a proposal.
2. **Commit at phase boundaries, never mid-phase**, and propose rather than perform.
3. **Fail loud.** A failing check, a test error — stop and show it.
4. **A check you could not run is not a check that passed.**

A non-trivial change's own check is part of the change, not a test the contract did not ask
for.
