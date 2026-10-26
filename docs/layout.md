# What lives where

Which files are loaded whether you want them or not, and which are in git. Both are decided by where a file sits.

## Loaded on every run

These cost context whether or not they are relevant, so `core/scripts/budget.py` holds each to a byte ceiling.

```text
core/skills/<skill>/SKILL.md        read when that skill runs
core/shared/context.md              printed by flw context, at every skill's opening
core/shared/commits.md              read by flw-execute at every commit proposal
core/shared/ambient.md              written into a host's instructions by flw install --ambient
core/styles/terse_prose.md          installed into a host's system prompt by flw style install
.flw/extensions/<skill>.md          every run of that skill, from every project root at or
                                    above this one, outermost first
.flw/extensions/shared.md           the same walk, read by every skill, before the skill's
                                    own file at that level
~/.flw/config.toml                  merged under the project's
<project>/.flw/config.toml          merged over the machine's
```

`.flw/` is the default name. One machine-wide setting renames it, and `flw doctor` prints the name in force.

## Read when something sends you there

Nothing loads these, so they carry no ceiling.

```text
core/skills/<skill>/references/     read when the skill points at one
core/shared/autonomy.md             read when a decision may not be the agent's
docs/                               install, extending, measuring, this file
plans/*.md                          design prose: why something is shaped the way it is
plans/backlog/                      known and not yet specced, one file per item
README.md                           what flw is, and the commands
```

## Data with a schema

Read by the commands that need them, never loaded wholesale.

```text
specs/current.toml                  the contract — what is true when the work is done
specs/versions/<name>.toml          one per version — how that version came about
.flw/reviews/<team>.toml            a reviewer team, as data
.flw/knowledge/                     the knowledge store, mirroring the code it describes
```

## Tracked, or ignored

A file that is neither tracked nor ignored is an accident. `flw-execute` forbids `git add -A` for that reason: a blanket add sweeps such a file into a commit as though the run produced it.

flw's per-project directory is ignored whole:

```text
.flw/                               every part of it
```

More than one true picture of a system is possible, so what one person records about a repository is theirs by default. Two engineers on the same service hold different pictures of it, each true for the work they do, and a store that has to be merged forces one of them to be wrong. The same holds for a convention and for a reviewer team: one person's is not the team's until the team says so.

A team that wants any of it shared un-ignores that path deliberately — the config, the extensions, the review teams. `flw-research` asks when it writes a config, because agreeing on what goes in those files is the work, and a default that shared them silently would skip it.
