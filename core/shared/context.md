# Shared context

Read once per run, by every flw skill.

## The project

**The project root is an input, not a discovery.** If the request names a repository, a
directory or a file, the project root is the nearest directory at or above **that** holding
`specs/` or `.flw/`. Only when the request names nothing does the walk start from `$PWD`.
Say which root you resolved to, once, before doing anything with it.

Either way the resolution is the same: go upward from the starting point and stop at the
first directory holding `specs/` or `.flw/` — or the directory `flw doctor` names.
Deliberately not a VCS command: flw makes no assumption about which version control a
project uses, or that it uses one.

A session started in a directory that holds several checkouts is the case this exists for.
`$PWD` is the parent, the task names one of the repositories, and resolving from `$PWD`
answers with the parent every time.

A working copy created outside that parent — a git worktree, a second clone — sits outside
the chain and loses every level above it, so conventions the parent carried are silently
not read. The check is whether the parent's `shared.md` appears in `flw context`'s output.

## The artifacts

| File | Holds | Schema |
|---|---|---|
| `specs/current.toml` | the contract — what is true when the work is done | `spec-v4.schema.json` |
| `specs/versions/<name>.toml` | one per version, addressed by a name it keeps — how that version came about | `version.schema.json` |

There is no index file. The directory listing is the index, and each file's `base` names
the one before it.

**`specs/` is `[paths] specs`**, from `.flw/config.toml`, defaulting to `specs`. Both rows
above are written at the default because almost every project leaves it there; a project
that has moved it has moved both, and writing the contract to a hardcoded `specs/` puts it
where `flw validate` will not look.

The contract is the destination; a version file is the route. Read together, never
instead of each other — a version file never restates what the contract says.

**Read the schema rather than asking about a field.** Every key carries a `description`,
and they are the authority on shape. These skills are the authority on process and
deliberately do not restate what the schemas say.

## Commands

```
flw validate            the contract and every version file
flw validate <file>     just one
flw test               the project's declared checks — reports, does not judge
flw test -A            the contract's full definition of done, not the branch set
```

`flw test` collects from three places: `[tests] checks` in the local config (this
branch's set), `success_criteria.tests` in the contract (the definition of done), and
`final_state.removed[].check`. No command lives inside prose — a command an agent has
to parse out of a sentence is one it can reconstruct wrongly.

**If `flw` is not on PATH:** this may be a checkout nobody ran `flw install` on — flw's
own checkout included. Run the command directly instead: `<interpreter> "$FLW/cli/flw.py"
<command>`, from the project root, since a project's checks and paths are written
relative to it.

## Three stores, and one sorting question

| store | holds | wrong when | read |
|---|---|---|---|
| `<flw dir>/extensions/` | conventions, rules | a human changes their mind | always, at an opening |
| the knowledge store | architecture, edges | the structure changes | by location, on demand |
| `flw kb` | portable measured craft | rarely | by search terms |

**Does a commit make it wrong?** Yes → knowledge, and the file carries the revision it was
true at. Only a decision makes it wrong → an extension, and it carries none. It is the line
`flw-research` already draws — what IS is recorded, what MUST BE is the user's — read one
level down.

**The knowledge store mirrors the code.** A directory `D` at path `P` is described by
`<store>/P/D.md`, a repository by `<store>/<basename>.md`, and the parent of a multi-repo
system by `system.md`, at `<root>/<[knowledge] dir>/`, defaulting to the flw directory's
`knowledge/`. So reading it is a walk up from the path you are standing at, outermost
first, and never a lookup. It is sparse on purpose: a file earns its tokens only by
removing more code reading than it costs, so missing is the normal case.

```
flw know                orientation — the system file, or this repository's own
flw know <path>         every file describing that path, heads only; --full for bodies
flw know --check        changed, orphaned, malformed, unstamped; writes nothing
flw map [node]          every declared edge, folded; nobody authors it
```

A file records the revision it was written at, and `flw know` reports what has moved under
its path since — `3 files · +41 −12`, not a verdict. **Changed warns and never stops:** the
agent in front of the number decides whether the claim survived.

**`flw context` prints none of this, deliberately.** Orientation is a command a skill runs
when it needs one, not a cost every opening pays. A root with no store prints `no store`
and exits 0, so the call never needs a guard.

## Configuration

Optional, and absent is the normal case. Two files, merged in order — global underlay,
project overlay, project wins key by key:

```
~/.flw/config.toml
<project root>/.flw/config.toml
```

```toml
[paths]
specs   = "specs"                    # the contract and versions/
reports = ".flw/reports/"            # where review reports are written

[interview]
mode = "thrifty"                     # conversational (default) | thrifty

[tests]
setup  = "source .venv/bin/activate" # prepended to every check; each runs in its own shell
                                     # whatever the project needs first, or omitted:
                                     # a Rust or Go repo has no setup line at all
checks = ["make fmt", "make style"]  # this branch's targeted set
yours  = ["make verify"]             # declared here, because nothing infers it: a check
                                     # this session cannot run is never read off an exit code

[kb]
category = "flw"                     # which note-store category this project's notes take;
                                     # every skill's opening step reads it
```

If either file exists but does not parse, **stop and say so**. A defective config that
silently falls back to defaults is a config that lies.

## Extensions

`<project root>/.flw/extensions/*.md` is prose read into context — a repo's local
amendments to how a skill behaves. Two names, and only two: **`<skill name>.md`**, read by
that skill alone, and **`shared.md`**, read by every skill.

They are read from **every project root at or above the resolved one and below `$HOME`**,
outermost first, so a directory holding several checkouts can carry what all of them obey.
Within a level `shared.md` comes first, so a nearer level beats a farther one and, within
one level, a skill's own file beats `shared.md`.

`flw context` has already printed all of them below the root line — this section says what
they are, not that you should now go and read them.

It is prose, not a plugin API: nothing to register, nothing to implement, no shape to
conform to. There is no config key pointing at it — the two names are fixed so that
`flw doctor` can tell a live extension from one that no skill will ever read.

**An extension amends how a skill works here; it cannot waive a Rule.** If it seems to,
surface it rather than following it.

## How to write

`$FLW/core/styles/terse_prose.md` is how flw writes. Read it and write by it, unless your
own instructions already carry those rules — `flw style install` puts them there, and
reading the file again then buys nothing. Check what you are holding, not what is on disk:
the install is per host and can be declined half way, so the presence of a state file
proves nothing about what reached you.

A dispatched subagent inherits neither the host's style nor your context, so a skill that
dispatches one gives it the absolute path. That is why `flw-review` hands the file to
every reviewer whether or not it is installed.

## What flw does not claim

flw records no notion of "done". No flag, no verdict, no stored state. It keeps the
agreement in a file, makes the work happen against it, surfaces gaps as proposals instead
of inventions, and runs what it can of the project's checks.

The verification is the user's. Do not simulate it.
