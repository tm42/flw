# flw-execute — when a check does not simply pass

Read when step 4 goes any way other than green: a check failed, a check could not run here,
or the user asked for `--yolo`. The ordinary path is three lines in `SKILL.md` and needs
none of this.

## `--yolo` — skipping the checks

**`--yolo` skips step 4 entirely.** Rules 3 and 4 are unaffected: it changes what the run
*executes*, not what it may *claim*. So a run that skipped its checks may never print the
completion block in step 6, because that block reads as verified — it prints the
BUILT, NOT VERIFIED block instead, and step 5 does not move the contract.

It is for a suite that runs fine and is too slow to sit through right now.

**It is not the answer to "these checks cannot run in this session".** That is
`[tests] yours` in `.flw/config.toml`, which outlives any single run. Propose adding a check
there instead of reaching for `--yolo` when the problem is that it cannot run here at all.

It composes with `--auto`; neither implies the other.

## A check that failed

**Read the whole table before stopping.** `flw test` runs every check regardless of earlier
failures, and Rule 3's "stop" means do not proceed past the check step — not truncate the
report.

**Nothing is inferred from an exit code.** 127 is bash's "command not found", which an
absent binary returns and `npm run <script>` also returns when a devDependency is missing,
while `cargo <subcommand>` returns 101 whether the subcommand is absent or the code failed
to compile. A `curl` with no route exits 7 and a test that dials out exits 1, and neither is
distinguishable from a real failure.

So everything that fails is reported as **failed**, including a check that failed only
because this session has no network or no database.

## When you believe a failure is a missing capability

- **Report it as failed.** You may not reclassify it. A check you could not run is not a
  check that passed, and an agent that gets to decide which failures do not count is worse
  than no check at all.
- **Say what you think and why**, naming the check and the capability.
- **Propose adding it to `[tests] yours`** in `.flw/config.toml`, so future runs hand it
  over instead of failing every time. That file may not exist yet; creating it is part of
  the proposal, and the user decides.

**One kind of check is handed back as yours: one the project declared in `[tests] yours`.**
Plain `flw test` still exits 0 when it hands one back and the rest pass, because declaring a
check there must not turn every green run red. The contract names the exit-2 cases.
