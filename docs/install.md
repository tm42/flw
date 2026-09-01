# Installing flw

This is the walkthrough as actually performed, on macOS with Claude Code, including what
each step reported. Findings behind it are recorded as comments at the code each one
explains.

## What you need

Python 3.11 or later as a system interpreter. Nothing else — flw has no runtime
dependencies, and an installer that exists to stop a workflow assuming a package manager
cannot itself require one.

## Put `flw` on PATH

Clone wherever you keep things, then link the CLI onto PATH:

```sh
ln -s /path/to/flw/cli/flw.py ~/.local/bin/flw
```

**A symlink, not a copy.** `flw update` is then a `git pull` with nothing to re-copy and no
stale duplicate to detect. `cli/flw.py` is already executable and carries
`#!/usr/bin/env python3`.

If `~/.local/bin` is not on your PATH, any directory that is will do.

## Install the skills

```sh
flw install
```

Skills are linked into each present host's discovery path — again symlinks, so editing
`core/skills/<name>/SKILL.md` is live everywhere immediately.

**Only hosts that are actually here.** flw checks for the host's own binary or its config
directory. A host that is not installed is named and skipped:

```
  codex: not on this machine — skipping
  opencode: not on this machine — skipping
  claude-code: ~/.claude/skills
    + flw-execute
    + flw-research
    + flw-review
    + flw-spec

  ~/.flw/root -> /path/to/flw

  style: flw ships a writing style and has not installed it — `flw style install`

Run `flw doctor` to verify.
```

Name a host to install regardless — `flw install claude-code` — which is what you want when
setting up ahead of a host, or building an image.

**Two link sets serve three hosts.** OpenCode reads Claude Code's and Codex's skill
directories as well as its own, so installing all three usually creates two.

## Verify

```sh
flw doctor
```

```
flw: /path/to/flw
  ✓ ~/.flw/root -> /path/to/flw

skills: 4

links:
  ~/.claude/skills
    ✓ flw-execute
    ✓ flw-research
    ✓ flw-review
    ✓ flw-spec

hosts:
  ✓ claude-code: via ~/.claude/skills
  · codex: not installed
  ✓ opencode: reachable via ~/.claude/skills

style:
  · not installed — `flw style install` writes it into each host

OK
```

**`reachable via` is not `via`.** Claude Code is here and reads that directory. OpenCode
is not here, but reads the same one, so its skills would resolve the moment it arrived —
which is why `flw install` calls it absent and `flw doctor` still ticks it.

**`·` is not a failure.** It means nothing of flw's reaches that host, and the line says
which of the two reasons applies: `not installed` is a host that is not on this machine,
and `on this machine, not installed into` is one that is here and was never named. A host
that is here and whose links are all broken gets `!` instead, because that one is worth
acting on. `✗` is a failure — a link that is dangling, hijacked, stale, or recorded but
no longer there. `flw doctor -v` adds each host's notes and quirks.

Run inside a project, `doctor` also reports which of that repo's `.flw/extensions/` files
an installed skill will actually read, and which sit there read by nobody.

## The host has to reload

A newly linked skill is not discoverable until the host rescans. In Claude Code that is
`/reload-skills`; other hosts differ. Nothing is wrong if `flw doctor` is clean and the
skill has not appeared yet.

## Optional: the ambient block

```sh
flw install --ambient
```

Offers a tagged block for your top-level `CLAUDE.md` or `AGENTS.md` describing the workflow
and the posture. It asks first, and `flw uninstall` strips it exactly, leaving the
surrounding file untouched. This is your global instruction file and flw is a guest in it.

## Removing it

```sh
flw uninstall            # every host
flw uninstall codex      # one
```

`uninstall` reaches a host **even if you have since removed that host** — that is how
leftover links get cleaned. It removes only what flw recorded creating, and only from the
root each host writes to, never one it merely reads.

## First run

`flw scout` in any repository gives you a ranked orientation in about a second, with
nothing installed and nothing cached. `flw-research` configures a repository flw did not
set up. Neither needs a contract.

`flw kb` needs one even less: it reads `~/.flw/kb/` and, inside a project, that project's
`plans/notes/`. Both are empty until something writes to them, and an empty store prints
that rather than failing. The skills fill it — flw-execute, flw-research and each
dispatched flw-review reviewer are offered a note at the point they have just measured
something, and decline by doing nothing.
