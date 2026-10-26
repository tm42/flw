# flw

A spec-driven workflow for coding agents, and the tool that keeps it current across them.

It takes intent to a versioned contract, works against that contract, and stops when the work would drift from what was agreed.

Host-agnostic: flw installs as [Agent Skills](https://agentskills.io) into Claude Code, Codex and OpenCode. Language-agnostic: it bakes in no toolchain, no test runner and no manifest — a project declares its own commands and flw runs them.

## The idea

An agent asked to build something will build something adjacent to it, and the gap becomes visible later. flw makes the agreement a file:

- **The contract is the source of truth.** One per project, stating what exists when the work is done and how you will know it works. A project is the directory the contract sits in, and flw resolves the innermost one — so a repository whose parts release independently carries one contract per part, each with its own version number.
- **The contract is edited, not operated on.** Ordinary edits, so `git diff` is the review surface.
- **Gaps surface as proposals.** When work hits something the contract does not cover, it stops and asks rather than inventing.
- **Every version leaves a record.** One file per version under `specs/versions/`, carrying what changed, why, and the reasoning behind the plan. A record is addressed by a name chosen when it is specced and never changed, so two people can spec at once; the contract's `applied` list holds the order they landed in.
- **flw claims nothing about whether work is done.** It runs what it can of your checks, hands back what it could not run, and leaves the judgment to you.

## What it is not

Not a hook layer. flw does not intercept, wrap or police your agent's operation — hosts have their own permission systems. Its entire runtime presence is skills a host chooses to load.

Not a framework. There is no plugin API. A **bundle** adds a skill: a folder with a `SKILL.md` in it, shaped like flw's own. An **extension** amends a skill you already have: prose at `.flw/extensions/<skill name>.md`, read from every project root at or above the one it resolved to. `flw doctor` says which extensions are live and which sit there read by nobody.

Not a scaffolder. It writes no boilerplate and invents no files.

## Install

```sh
git clone https://github.com/tm42/flw.git ~/.agentic/flw
ln -s ~/.agentic/flw/cli/flw.py ~/.local/bin/flw    # one time, so `flw` is on PATH

flw install            # symlink the skills into every host's discovery path
flw doctor             # verify: links resolve, no overrides, no orphans
```

`docs/install.md` has the rest, including the optional ambient block and the writing style.

Moving the checkout dangles the PATH link and the skill links with it. Re-run the `ln` line, then `flw install`.

## Commands

```sh
flw install            symlink the skills into every host; uninstall removes exactly that
flw doctor             verify the install: links, hosts, style, live extensions
flw update             pull, then re-verify; -n reports what a pull would bring
flw sync               repair links after a checkout moved
flw add <path>         register your own bundle of skills; list and remove go with it
flw style install      put flw's writing style in front of the host, optional
flw context <skill>    what a skill reads at its opening; every skill runs this first
flw validate           check the contract and every version record
flw test               run the project's declared checks; -A for the full definition of done
flw scout              rank a repo by what depends on what
flw know [path]        the knowledge store: what this system is built of, found from a path
flw map [node]         every seam the store declares, folded together
flw stale              which documents are spent, and which nobody has read
flw ledger <terms>     search the contract, the records, the review configs and plans/*.md
flw kb                 the note store: what an agent worked out, kept for the next one
flw version            which checkout flw is running from, and at what revision
```

`install`, `doctor`, `update`, `sync`, `add`, `style`, `scout` and `kb` run anywhere. The rest read a project's own files, so run those from inside one.

Every command takes `--help`, and that is where its flags and its own rules are written.

## The skills

Your host loads these after `flw install`, and you invoke them by name — `/flw-spec` in Claude Code, the equivalent elsewhere. A newly linked skill is not discoverable until the host rescans; in Claude Code that is `/reload-skills`.

| Skill | Use |
|---|---|
| `/flw-spec` | Author or amend the contract. Interview-driven; nothing inferred silently. |
| `/flw-execute` | Walk the pending record's phases, run the declared checks, propose the commits. |
| `/flw-review` | Review at any stage — one reader by default, a team of lenses when you name one. Reports; fixes nothing. |
| `/flw-research` | Bring flw to a repo you did not set up: learn how it is tested and built, write that into its own config. |
| `/flw-style` | Find this session's own instances of a writing failure you name, and stop doing it. |

Nothing chains. You drive, and each skill stops and hands back.

## The two artifacts

`specs/current.toml` is the contract — what is true when the work is done. `specs/versions/<name>.toml` is one file per version — how that version came about. There is no index file; the directory listing is the index.

Read together, never instead of each other. A version record never restates what the contract says.

## Two stores, and why they do not merge

`flw ledger` reads what was agreed: the contract, every version record, the review team configs and `plans/*.md`. `flw validate` enforces the schema of the two that have one.

`flw kb` reads what an agent worked out and nobody checked — markdown under `~/.flw/kb/`, which follows the machine, and `<project>/plans/notes/`, which follows the repository. A note is a file: no schema, no registry, no index on disk. Every surface prints a note's age and size, because a note is a hint to verify rather than a fact to act on.

The two corpora are disjoint by directory, so no file is reachable from both.

```sh
flw kb                              # what is in the store, per category and per root
flw kb search discriminator -T      # whole words, ANDed, as titles and descriptions
flw kb show pydantic-unions         # one note, whole, with its path, age and size
flw kb write python "title" -d "…" < note.md
flw kb lint                         # reports, decides nothing, exits 0
```

## The writing style

`core/styles/terse_prose.md` is how flw writes. The skills read it themselves and hand it to every reviewer they dispatch, so flw's own reports follow it whether or not you install anything.

Installing it puts the same rules in front of the host for everything else you do, which is a bigger claim on your session than a skill makes — so it is a separate command.

```sh
flw style install            # the shipped style, into every host present
flw style install <name>     # your own, from ~/.flw/styles/<name>.md
flw style uninstall          # remove it, and put back whatever it replaced
```

The skills are symlinks, so an edit is live on every host at once. The style is a copy, because Claude Code needs a frontmatter header the source file does not carry — `flw doctor` reports a copy that no longer matches, and `flw update` offers to refresh it.

## Requirements

Python 3.11 or later, as a system interpreter. No runtime dependencies.

Running flw's own checks is the one exception: `flw test` in this checkout creates `.venv/` and installs pytest and ruff, because that is what this project's `.flw/config.toml` declares as its `[tests] setup`. Nothing inherits it.

## Layout

```text
cli/flw.py           the CLI: install, verify, and the front end for every engine
core/skills/         the skills, as standard SKILL.md folders
core/reviews/        reviewer teams, as data
core/scripts/        validation, the check runner, the scout, the stores (stdlib only)
core/shared/         fragments every skill reads
core/styles/         the writing style
core/schemas/        contract and version-record shapes
docs/                install, extending, measuring, layout
plans/               design prose, and plans/backlog/ for what is not yet specced
specs/               flw's own contract and version records
```

`plans/design-v3.md` is the design and `plans/backlog/index.md` is what is not yet built, each item with what it is blocked on. `specs/current.toml` is what "done" means, and its `applied` list is the order it was built in.

## License

MIT. See `LICENSE`.
