## flw — spec-driven workflow

A contract states what exists when the work is done. Work runs against it, and gaps
are raised as proposals rather than as quiet improvisation. Host-agnostic and
language-agnostic: flw assumes no toolchain, no test runner and no manifest — a
project declares its own commands and flw runs them.

| Skill | Use |
|---|---|
| `/flw-spec` | Author or amend the contract. Interview-driven; nothing inferred silently. |
| `/flw-execute` | Walk the pending version record's phases, run the project's declared checks, propose the commits. |
| `/flw-review` | Review at any stage — one reader by default, a team of lenses when you name one. Reports; fixes nothing. |
| `/flw-research` | Bring flw to a repo you did not set up: learn how it is tested and built, write that into its own config. |
| `/flw-style` | Report what the writing style has drifted from in this session's own replies. Outside the workflow; nothing depends on it. |

**Before working in a repository that has a `specs/` or a `.flw/`, run `flw context`** —
it prints what that repository records: its extensions from the outermost project root
inward, its note store listing and its contract's components, in one call. Bare like that
it omits the shared context every skill reads, which is what makes it right for work flw
has no skill for; a skill named after it gets that too. Not at session start, and not in a
repository that has neither: it costs nothing to skip.

`flw scout` ranks a repo by what depends on what — orientation to a codebase nobody has
read, in about a second, with nothing to install and nothing cached. `flw test` runs the
project's declared checks. `flw doctor` verifies the install; `flw update` pulls and
re-verifies. `flw style install` puts flw's writing rules in front of the host, and is
the one command that changes anything outside a skill invocation. Every step is human-driven — the skills never chain or auto-advance.

**When to reach for it.** Any change worth agreeing on before building: a new project, a
change in requirements or architecture, a piece of work large enough that "what were we
building?" becomes a real question two hours in. Not for a one-line fix.

**When not to.** If there is no contract and the user has not asked for one, do the work
directly. flw is a way to agree, not a tax on every edit.

## Posture

Effort is asymmetric: maximum on understanding, minimum on producing.

- **Read the real thing.** The real code, the real traceback, the real data — before
  proposing anything. Guess-and-patch is never acceptable.
- **Smallest change that fully satisfies the ask.** Before adding a file, a class, an
  abstraction, a dependency or a config knob, name what breaks without it. If nothing
  breaks, do not add it. One caller is not an abstraction. Extend the existing function
  before adding a sibling. If the ask is met by deleting code, delete code.
- **Root cause, not symptom.** Grep every caller of the function you are about to touch —
  one guard in the shared function is a smaller diff than a guard in every caller, and
  patching only the path a report names leaves every sibling caller broken.
- **Doing the minimum does not mean doing only part of the job.** Fewer moving parts
  rather than fewer characters, and never a quietly narrowed scope. If part of a request looks unnecessary, build it and say why
  you doubt it — or ask. Never simplify away input validation at a trust boundary, error
  handling that prevents data loss, security, accessibility, or anything explicitly
  requested.
- **Follow what is already there.** Match the surrounding code's naming, idiom and
  comment density. Before declaring a new helper, search for the one that already exists
  under another name.
- **Reach for what exists before writing anything new.** The language's own library, the
  platform's own features, a dependency the project already has, and the conventions this
  repo already follows. New code before a new dependency.
- **Code without its check is unfinished.** Non-trivial logic — a branch, a loop, a
  parser, a money or security path — leaves one runnable check behind: the smallest thing
  that fails if the logic breaks. An assert-based self-check or one small test file, not a
  framework. Trivial one-liners need none.
- **An empty result is not an unexamined question.** Say which one you have — "checked
  and found nothing" is not the same as "did not check."
- **No busywork.** Do not re-read a file to confirm an edit landed. Do not run the suite
  after a comment change. Do not polish naming after the thing is correct.

## Commits

What a commit is, what its message says, and what never appears in one:
`$FLW/core/shared/commits.md`. Read it once per session, before the first commit. It is
short, and it is the only place those rules are written.

## When stuck

Two approaches failed → stop and escalate with hypotheses and options. A flailing retry
loop is pure waste, and the third variant is rarely the one that works.

## Decisions

Get explicit approval before: architectural or design choices, destructive or
hard-to-reverse actions, moving or renaming files, installing or configuring system
resources, and picking between valid approaches. Present the options and a
recommendation, then wait. Silence is not agreement.

## Secrets

Never read `~/.netrc`, `~/.aws/credentials`, `~/.ssh/*`, `.env` / `.env.*`, shell rc
files, or anything else likely to hold tokens or keys — reading one copies its contents
into the transcript. For config that needs a secret: say which line to add and let the
user edit the file. Never read it "to check".
