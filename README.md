# flw

A spec-driven workflow for coding agents, and the tool that keeps it current across them.

It takes intent to a versioned contract, works against that contract, and refuses to let
the work drift from what was agreed. It also installs itself into every host you use,
runs whatever checks your project declares, and extends the same way it ships — so
adding your own skill is copying the shape of an existing one.

Host-agnostic: flw installs as [Agent Skills](https://agentskills.io) into Claude Code,
Codex and OpenCode. Language-agnostic: it bakes in no toolchain, no test runner and no
manifest — a project declares its own commands and flw runs them.

> **Status: in construction.** The schemas, the four skills, the scout, the check
> runner and the CLI work and are tested. What running flw against a real host and a
> real repository has found is recorded as a comment at the code each finding
> explains, not in a separate document. See `plans/design-v3.md` for the full design,
> `specs/current.toml` for what "done" means, and its `applied` list for the order it
> was built in.

## The idea

An agent asked to build something will happily build something adjacent to it, and the
gap only becomes visible later. flw closes that gap by making the agreement a file:

- **The contract is the source of truth.** One per project, complete and current, stating
  what exists when the work is done and how you will know it works.
- **The contract is edited, not operated on.** Ordinary edits, so `git diff` is the review
  surface. Change only what was agreed and the diff shows exactly that.
- **Gaps surface as proposals.** When work hits something the contract does not cover, it
  stops and asks rather than inventing. That refusal is the whole product.
- **Every version leaves a record.** One file per version under `specs/versions/`, carrying
  what changed, why, and the reasoning behind the plan. Size follows the change: a one-line
  correction is a four-line file. A record is addressed by a name chosen when it is specced
  and never changed, so two people can spec at once without either being renumbered when it
  lands; the contract's `applied` list is where the order they landed in is kept.
- **flw claims nothing about whether work is done.** No flag, no verdict. It runs what it
  can of your checks, hands back what it could not run, and leaves the judgment to you.

## What it is not

Not a hook layer. flw does not intercept, wrap, or police your agent's operation — hosts
have their own permission systems and theirs are better. Its entire runtime presence is
skills a host chooses to load.

Not a framework. There is no plugin API, and both ways of extending flw are things you
can write by hand. A **bundle** adds a skill: a folder with a `SKILL.md` in it, shaped
exactly like flw's own, which is why an agent can write one by copying the shape of an
existing one. An **extension** amends a skill you already have — prose at
`.flw/extensions/<skill name>.md`, read by that skill in that repo, with nothing to
register and no shape to conform to. `flw doctor` says which extensions are live and
which are read by nobody.

Not a scaffolder. It writes no boilerplate and invents no files.

## Install

```sh
git clone https://github.com/tm42/flw.git ~/.agentic/flw
ln -s ~/.agentic/flw/cli/flw.py ~/.local/bin/flw    # one time, so `flw` is on PATH
                                                    # moving the checkout later dangles
                                                    # this link and the skill links with
                                                    # it; re-run this line to repair, as
                                                    # `flw sync` is itself unreachable

flw install            # symlink the skills into every host's discovery path
flw doctor             # verify: links resolve, no overrides, no orphans
flw validate           # check the contract and every version record
flw test              # run the project's declared checks
flw scout              # rank a repo by what depends on what
flw ledger <terms>     # search the contract, the version records, the review configs and plans/*.md
flw kb                 # the note store: what an agent worked out, kept for the next one
flw add <path>         # register your own bundle of skills
flw style install      # put flw's writing style in front of the host, optional
```

`install`, `doctor`, `scout`, `kb`, `add` and `style` run anywhere. `validate`, `test` and
`ledger` read a project's own files, so run those from inside one — flw's own checkout will
do.

`flw install --ambient` also offers a tagged block for your top-level `CLAUDE.md` or
`AGENTS.md`, describing the workflow and the posture. It asks first, and
`flw uninstall` strips it exactly.

## The four skills

The commands above are the plumbing. The workflow itself is four skills, which your host
loads after `flw install` and you invoke by name — `/flw-spec` in Claude Code, the
equivalent in Codex and OpenCode. A newly linked skill is not discoverable until the host
rescans; in Claude Code that is `/reload-skills`.

| Skill | Use |
|---|---|
| `/flw-spec` | Author or amend the contract. Interview-driven; nothing inferred silently. |
| `/flw-execute` | Walk the pending work order phase by phase, run every declared test, record the result. |
| `/flw-review` | Run a configurable team of reviewers over the work at any stage. Reports; fixes nothing. |
| `/flw-research` | Bring flw to a repo you did not set up: learn how it is tested and built, write that into its own config. |

Nothing chains. You drive, and each skill stops and hands back — `flw-execute` proposes
commits rather than making them, and `flw-review` reports rather than fixing.

## Two stores, and why they do not merge

`flw ledger` reads what was agreed: the contract, every version record, the review team
configs and `plans/*.md`. Every sentence in it is binding or was written to justify
something binding, and `flw validate` enforces the schema of the two that have one.

`flw kb` reads what an agent worked out and nobody checked — freeform markdown under
`~/.flw/kb/`, which follows the machine, and `<project>/plans/notes/`, which follows the
repository. A note is a file: no schema, no registry, no database, no index on disk, and
nothing about the format can refuse one, so any agent that can write a file can write a
note. Every surface prints its age and its size for the same reason, because a note is a
hint to verify rather than a fact to act on.

The two corpora are disjoint by directory — the ledger keeps `plans/*.md`, the store's
project root is `plans/notes/` — so no file is reachable from both and a query spanning
them is two commands.

```sh
flw kb                              # what is in the store, per category and per root
flw kb -c python                    # that category's notes
flw kb search discriminator -T      # whole words, ANDed, as titles and descriptions
flw kb show pydantic-unions         # one note, whole, with its path, age and size
flw kb write python "title" -d "…" < note.md
flw kb lint                         # seven checks; reports, decides nothing, exits 0
```

`docs/layout.md` says which files are loaded on every run and which are found when you go looking,
and why nothing here is untracked without being ignored. `plans/backlog/` holds what is known and
not yet specced.

`docs/measuring.md` is the protocol for timing any of this on a machine that is not this one:
seeded corpus generators, the commands worth timing, a baseline to compare against, and the
shape a report should come back in.

## The writing style

`core/styles/terse_prose.md` is how flw writes: claim first, no preamble, replies
hard-wrapped and files never. The skills read it themselves and hand it to every
reviewer they dispatch, so flw's own reports follow it whether or not you install
anything.

Installing it puts the same rules in front of the host for everything else you do, which
is a bigger claim on your session than a skill makes — so it is a separate command and
never happens on its own.

```sh
flw style install            # the shipped style, into every host present
flw style install <name>     # your own, from ~/.flw/styles/<name>.md
flw style uninstall          # remove it, and put back whatever it replaced
```

Claude Code gets a file in `~/.claude/output-styles/` and is asked before the
`outputStyle` key is set; Codex and OpenCode have no style slot, so the text goes into
their instructions file as its own tagged block beside the ambient one. `flw doctor`
reports it as installed, installed but not selected, or no longer matching the file it
was copied from — and in that last case whether flw's source moved on or the copy was
edited by hand, because install records what it wrote.

The four skills are symlinks, so `flw update` — a pull, then a re-verify — makes them
live on every host the moment it lands, with no sync step. The style is the exception:
Claude Code needs a frontmatter header that the source file deliberately does not
carry, so what a host holds is a generated copy. `flw update` offers to refresh every
copy that no longer matches, one host at a time, saying which side moved before it
asks, rather than leaving it silently stale.

`flw update -n` writes nothing: it fetches, reports which commits a pull would bring, and
says what the style check found without refreshing anything. HEAD and your working tree do
not move — the same thing `-n` means on `install`, `sync` and `style install`.

## Requirements

Python 3.11 or later, as a system interpreter. No runtime dependencies at all.

Running flw's own checks is the one exception: `flw test` in this checkout creates
`.venv/` and pip-installs pytest and ruff, because flw's `.flw/config.toml` declares that
as its `[tests] setup`. It is one project's own line and nothing inherits it.

## Layout

```
cli/flw.py           install, uninstall, doctor, add/list/remove, update, version
core/skills/         the skills, as standard SKILL.md folders
core/reviews/        reviewer teams, as data
core/scripts/        validation, the check runner and the scout (stdlib only)
core/shared/         fragments every skill reads: project context, the ambient block
core/schemas/        contract and version-record shapes
docs/                install and extension notes for someone bringing flw to a repo
plans/design-v3.md   why flw is shaped this way, and what was deliberately not built
specs/               flw's own contract and version records
```

## License

MIT. See `LICENSE`.
