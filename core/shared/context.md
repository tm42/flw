# Shared context

Read once per run, by every flw skill.

## The project

**Project root** is the nearest directory at or above `$PWD` containing `specs/` or
`.flw/`. Resolve upward and stop at the first hit. Deliberately not a VCS command: flw
makes no assumption about which version control a project uses, or that it uses one.

## The artifacts

| File | Holds | Schema |
|---|---|---|
| `specs/current.toml` | the contract — what is true when the work is done | `spec-v4.schema.json` |
| `specs/versions/<name>.toml` | one per version, addressed by a name it keeps — how that version came about | `version.schema.json` |

There is no index file. The directory listing is the index, and each file's `base` names
the one before it.

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
```

If either file exists but does not parse, **stop and say so**. A defective config that
silently falls back to defaults is a config that lies.

## Extensions

`<project root>/.flw/extensions/<skill name>.md`, when present, is prose to read into
context for that skill — this repo's local amendments to how it behaves. The name is the
skill's own: `flw-spec` reads `.flw/extensions/flw-spec.md`. Read it after this file and
before starting. Nothing else reads it, and no other file names it.

It is prose, not a plugin API: nothing to register, nothing to implement, no shape to
conform to. There is no config key pointing at it — the path is fixed so that `flw doctor`
can tell a live extension from one that no skill will ever read.

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
