# Installing flw

## What you need

Python 3.11 or later, as a system interpreter. flw has no runtime dependencies.

Running flw's own checks is the exception. flw's per-project directory is local, so this checkout ships no `.flw/config.toml` and `flw test` here declares no setup line of its own — its four checks call `.venv/bin/…` and fail until that exists. To run them, write your own:

```toml
# .flw/config.toml
[tests]
setup = "test -x .venv/bin/pytest || { python3 -m venv .venv && .venv/bin/pip install -q pytest ruff; }"
```

It needs the network once. Every other project declares its own setup line or none.

## Put `flw` on PATH

```sh
git clone https://github.com/tm42/flw.git ~/.agentic/flw
ln -s ~/.agentic/flw/cli/flw.py ~/.local/bin/flw
```

A symlink, not a copy, so `flw update` is a `git pull` with nothing to re-copy. Any directory on your PATH will do instead of `~/.local/bin`.

Moving the checkout later dangles this link and the skill links with it. Re-run the `ln` line to repair it, then `flw install`.

## Install the skills

```sh
flw install
```

The skills are symlinked into each present host's discovery path, so editing `core/skills/<name>/SKILL.md` is live everywhere at once. A host that is not on this machine is named and skipped; name one to install anyway:

```sh
flw install claude-code
```

OpenCode reads Claude Code's and Codex's skill directories as well as its own, so installing all three usually creates two link sets.

## Verify

```sh
flw doctor
```

It reports which links resolve, which hosts the skills reach, whether the writing style is installed, and — run inside a project — which extensions an installed skill will read and which sit there read by nobody. `flw doctor -v` adds each host's notes. The last line is `OK` or a problem count.

## The host has to reload

A newly linked skill is not discoverable until the host rescans. In Claude Code that is `/reload-skills`; other hosts differ. Nothing is wrong if `flw doctor` is clean and the skill has not appeared yet.

## Optional: the ambient block

```sh
flw install --ambient
```

Offers a tagged block for your top-level `CLAUDE.md` or `AGENTS.md` describing the workflow and the engineering posture. It asks first, and `flw uninstall` strips it exactly, leaving the rest of the file untouched.

## Optional: the writing style

```sh
flw style install
```

Puts `core/styles/terse_prose.md` in front of the host for everything you do, not only for flw's skills. Claude Code gets a file in `~/.claude/output-styles/` and is asked before `outputStyle` is set; Codex and OpenCode have no style slot, so the text goes into their instructions file as its own tagged block.

The style is a copy rather than a symlink, because Claude Code needs a frontmatter header the source file does not carry. `flw doctor` reports a copy that no longer matches its source, and `flw update` offers to refresh it.

## Removing it

```sh
flw uninstall            # every host
flw uninstall codex      # one
```

`uninstall` reaches a host even if you have since removed that host, which is how leftover links get cleaned. It removes only what flw recorded creating.

## First run

`flw scout` in any repository gives a ranked orientation with nothing installed and nothing cached. `/flw-research` configures a repository flw did not set up. Neither needs a contract.

A repository that holds only a `.flw/` directory is a complete flw project. `flw scout`, `flw know`, `flw map`, `flw stale`, `flw kb` and plain `flw test` all run there, and so do `/flw-research` and `/flw-review`. `flw validate` says there is no contract to check against and exits 0. Only `flw test -A` needs one, because the full definition of done is a contract field — so a repository that already ships can be adopted before anything is agreed.

`-n` on `install`, `sync`, `update` and `style install` writes nothing and reports what the command would do.
