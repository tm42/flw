# flw-execute — the phase reviewer

Read when the run reviews each phase: an attended run whose user said yes at the start,
or any `--auto` run. A `--yolo` run never reviews, and with both flags `--yolo` wins,
because that run already reports itself built and not verified.

## When and what

After `flw test` at the phase boundary and before the commit is proposed. One reviewer, a
fresh context, discarded after the phase. It is given, in this order:

- the lens: the `correctness` entry of `quick.toml`, project copy first, with `probes`
  on — or every entry of the team `[review] phase = "<config>"` names in the flw config,
  resolved the way `flw-review/references/team-dispatch.md` §1 resolves one
- the scope: this phase's diff, by file, and the record's `approach`
- the contract narrowed to those paths, by `flw context --scope <paths>`
- the project's `flw-review.md` extension and the knowledge store heads for the paths
- the ledger below, read first
- the discipline block from `flw-review/SKILL.md`, verbatim, and the writing style path
- its target file, `<reports>/<record name>-phase<n>.md`, and the one-line reply rule

A reproduction runs read-only or in a scratch copy of the tree, because the tree holds
this phase's uncommitted work. A command that would write to it is reported as `not run`.

## The ledger

`<reports>/<record name>-ledger.md`, one line per finding ever raised in this record's
runs:

```text
R-<stamp>-<n> | <severity> | <path:line> | <claim> | <phase> | <open|fixed|decided|withdrawn>
```

`<stamp>` is the one in the first phase report's filename, and `<n>` continues from the
ledger's last id, so an id is stable across the phases of one run. A later phase's
reviewer re-raises nothing already in the ledger, whatever its status. A re-run of the
record — after a stop, or a phase redone — continues the same file: prior lines stay and
count as already raised.

## The refute call

Every finding the reviewer files passes one fresh call on a `cheap` model whose only task
is to knock it down, the same call `team-dispatch.md` §3 gives a team's findings. It gets
the finding, its evidence, the file at the cited line and the tools to run the
`Reproduce:` command under the same read-only rule; it is not told which lens filed it.
It returns `stands`, `demoted` with the reason, or `withdrawn`. A MAJOR or CRITICAL whose
`Reproduce:` line is `none` is demoted to MINOR with the note `no reproduction`. A refute
call that returns nothing leaves the finding at the severity filed, marked `unrefuted`.
The verdict goes beside the finding in the ledger and the phase report; the reviewer's
own file is not edited.

## What happens next

Severity means the severity after the refute call.

**Attended.** Print the commit proposal and then the decision list: the findings above
MINOR, one line each, id, severity, file:line, claim, verdict — at most a screen, with
MINOR left in the file. The user marks each `fixed`, `decided` or `withdrawn` in the
ledger before the next phase, and you act on a finding only through that mark. A `Fix:`
line is a direction and no run applies one.

**`--auto`.** Nobody reads between phases. A CRITICAL stops the run at this boundary the
way a failed check does: the phase stays uncommitted and the STOPPED block names the
finding by id. A reviewer that returns nothing stops the run the same way — it stands in
for the human read, and a phase it did not read is a phase nobody read. MAJOR and below
go into the ledger and the final report, and the run continues.

**Attended, reviewer returned nothing.** Say the phase went unreviewed and let the user
decide whether to go on.

The report's `Review:` line names, per phase, the findings above MINOR by id and verdict,
or `none`, or `not run` with the reason.
