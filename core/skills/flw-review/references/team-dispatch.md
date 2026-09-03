# flw-review — dispatching a team

Read only when a team was named — in the request, or as the first argument. The default,
solo path in `SKILL.md` never reads this file: naming a team is what sends you here.

## 1. Resolve the config

The first argument names a team. Look in order:

1. `<project root>/.flw/reviews/<name>.toml` (or the directory `flw doctor` names)
2. `$FLW/core/reviews/<name>.toml`

Project wins. `flw validate <config>` checks it — do that if it is user-authored and you
have not seen it before, because a reviewer with an empty perspective dispatches happily
and returns nothing useful.

If the name resolves nowhere, list what does exist in both directories and stop.

**A trailing `:role` selects lenses from that team.** `eng:footprint` runs one;
`eng:tests,adversarial` runs two. Use it when the change is narrow enough that the other
lenses would return nothing — four reviewers on a one-file change is four contexts spent
to say "looks fine" three times.

Selecting a lens does **not** change which team you are in. `:footprint` with no team
named is not a name this file resolves at all — a bare call with no team stays on the
default solo path in `SKILL.md`. Name the team if you want its version of a lens.

An unknown role is an error, not a filter that quietly matches nothing: list the team's
roles and stop.

Users ask for lenses by what they want looked at, not by role name. Map it, and **say
which lens you chose** so a wrong guess is visible:

| they say | lens |
|---|---|
| redundant, bloated, over-engineered, dead code | `footprint` |
| bugs, correctness, does it work, edge cases | `correctness` |
| tests, coverage, are the tests any good | `tests` |
| break it, security, robustness, what if | `adversarial` |

If the request maps to no lens in the resolved team, say so and offer the team that has
one rather than silently running something adjacent.

## 2. Dispatch

One reviewer per selected `[[reviewer]]` entry. Map `effort` to whatever the host offers
— `high` means the strongest thing available, `normal` means the cheap one. A reviewer
with `probes = true` may execute things; the others read.

**The property that matters is a fresh context, not parallelism.** A reviewer exists to
look at the work without having decided anything about it. Parallelism only buys speed.
So take the first rung of this ladder your host supports, and say in the report which one
you used:

| | |
|---|---|
| **parallel subagents** | best. Every host targeted here has some subagent mechanism — Claude Code forks context, Codex has subagent lifecycle events, OpenCode commands take `subtask`. Use whichever your host actually gives you. |
| **sequential subagents** | just as good for findings, only slower. A host that spawns one at a time still spawns. Dispatch, wait, dispatch the next — **each is a separate subagent**, not a lens you run yourself. |
| **inline** | you run the lenses yourself, one at a time. Follow flw-review's own default procedure in `SKILL.md`. Never silently — say so. |

**"Cannot run several at once" is rung two, not rung three.** These read alike — flw-review's
own default procedure also runs one lens at a time — and the difference is the entire
point: rung two spends a fresh context per lens, rung three spends none. Only drop to
inline when there is no subagent mechanism at all, or the user asked for it.

**Sequential reviewers must not see each other's output.** It is in your context and it
is tempting; passing it on collapses two independent reads into one read and an
agreement. §3 treats two lenses reaching the same finding as signal, which only holds if
they arrived there separately.

Do not ship three invocation syntaxes for one instruction. State the intent — *"review
this scope through this lens, in a fresh context, and report back in this shape"* — and
let the host resolve how.

Give every reviewer the same eight things:

- **its `perspective`, verbatim**
- **the scope** — the exact files or diff, and what is out of bounds
- **the contract, narrowed to the scope** — not `specs/current.toml` whole, and not
  intersected against `paths` by hand: run `flw context --scope <each path in the scope>`,
  with no skill named, and pass its output, plus `assumptions` and `open_questions` read from the
  contract directly, since they belong to no component and the command does not print
  them. Name the components the command matched, so a reviewer reasoning about one it was
  not given can ask for it instead of guessing. A scope covering the whole repository is
  the case where the narrowed output is the whole contract, and that is correct — pass it
  as the command printed it rather than reaching for the raw file instead. The
  instruction is unchanged: flag anything violating a stated principle.
  **Naming a skill is what makes `flw context` print `core/shared/context.md`**, which
  opens "Read once per run, by every flw skill" — and a dispatched reviewer runs no flw
  skill. The orchestrator resolved the root already and passes the result. The reviewer
  still needs the project's own conventions, so hand it
  `<project>/.flw/extensions/flw-review.md` separately.

  **Why narrowing is worth doing.** A reviewer inherits no prompt cache — not from you,
  not from another reviewer — so every one of them pays the contract cold. Measure it
  rather than quoting a number from here: `flw context --scope <the paths> | wc -c`, over
  the eight things above, times the number of reviewers. A figure written down drifts —
  flw's own contract grew 3.1% in one day — and a measured number that has drifted is
  worse than no number, because it is quoted rather than re-measured.
- **the discipline below, verbatim**
- **the writing style** at `$FLW/core/styles/terse_prose.md` — the absolute path, to
  read and write by. A reviewer inherits nothing from your context, so a style installed
  in the host may or may not reach it; the path always does.
- **its own target file**, `<reports>/<stamp>-<team>-<role>.md`, using the `<reports>`,
  `<stamp>` and `<team>` naming from §3 — computed once, before dispatch, so every
  reviewer gets its path up front rather than after the fact.
- **the knowledge store, narrowed to the scope**: the output of `flw know <path>` for
  each path in the scope already fixed, before this file was opened — heads, not bodies.
  What the part is for and what crosses it is what separates a reviewer reading a diff
  from one reading a change, and a reviewer inherits none of your context, so a walk you
  ran is a walk they never saw. Say which paths you walked, and where there was nothing
  to walk, say that.
- **the note store**: the output of `flw kb -c <the project's category>`, and the
  instruction to offer a note at the end of its read. Both go to the reviewer rather than
  to you. You review nothing and a dispatched reviewer inherits none of your context, so a
  read here would be paid by the one context that produces no findings and reach none of
  the ones that do — and this is the skill whose entire output is things just learned,
  written into a reports directory that is gitignored by default. The gate is one
  sentence: *write it only if it was measured, and the next agent, in a repository that
  does not hold this one's history, could not get it faster than measuring it again.*
  Yes means read `flw kb write --help` first. It is an offer, never a step.

**The delivery contract, because a reply is not durable.** On 2026-08-23 three of four
reviewers had their replies dropped by the session mailbox; the work was done and the
reports were written, but they only surfaced after being chased. Every reviewer writes its
full report to its target file and replies with **one line — the path and the finding
counts**. Not the report again: on 2026-09-02 every dispatched agent was told to reply
with the identical text, each report was emitted twice, and the replies arrived truncated,
so the file was read anyway — three copies of every report for one. The path was fixed
before dispatch, so a dropped line is recovered by reading it when the agent goes idle.

### The discipline, given to every reviewer

`SKILL.md`'s "The discipline, followed even reviewing alone" — the same block, verbatim,
to every dispatched reviewer.

> **Write your full report to the target file you were given, then reply with one
> line: the path and the finding counts.** Not the report — it is read from the file.
> The reply can be dropped in transit; the file is what survives.

## 3. Consolidate

Wait for all of them. Then write one file to `<reports>/<stamp>-<team>.md`, by the same
style you gave the reviewers:

- `<reports>` and `<stamp>` are defined in `SKILL.md` §3, which every run reads and a
  solo run reads instead of this file.
- `<team>` is the team name alone. A lens selection goes in the body, not the filename.

Create the directory if needed, and leave `.gitignore` alone, as §3 there says.

```markdown
# flw-review — <config>

**Scope**: <what was reviewed>
**Reviewers**: <role>, <role>, …
**Mode**: parallel | sequential | inline

## Findings

### CRITICAL
#### <role>
- **<file:line>** — <claim>
  - *Evidence*: …
  - *Fix*: …

### MAJOR
### MINOR

## Holds up
<merged, deduplicated>

## What was not checked
<merged from every reviewer, deduplicated — the round's coverage boundary, and what a
next round starts from>

## Disagreements
<where two reviewers reached opposite conclusions on the same thing — do not resolve
these, name them>
```

Deduplicate only exact repeats. **Two reviewers reaching the same finding from different
lenses is signal, not noise** — keep both and say so.

If a reviewer returns nothing or fails, ask it for what it has before giving up on it —
partial and honest beats complete and late. Record it as `(no report: <reason>)` only
after that, and carry on with the others.

**The report is scaffolding, not an artifact to keep.** What survives it is the version
file `flw-spec` drafts when it specs from these findings — carrying forward the coverage
line and any measurement the report made, since those cannot be re-derived by reading.
Once that has happened, the report itself is disposable.

Once the file is written, return to `SKILL.md`'s own step for printing the summary — the
terminal line is the same shape whether the run was solo or dispatched.

## Changing a team

A config is data, and it is meant to be tuned — a perspective that keeps returning noise
is a perspective to rewrite.

**Never edit `$FLW/core/reviews/`.** That is inside flw's own checkout, and `flw update`
rebases over it: the next update either clobbers the change or stops with a conflict, and
the fix it will tell you about is this one. Instead:

```sh
mkdir -p .flw/reviews
cp "$FLW/core/reviews/eng.toml" .flw/reviews/eng.toml    # then edit
flw validate .flw/reviews/eng.toml
```

The project copy now wins by name, travels with the repo, and survives every update. The
same applies to a team that is entirely yours — it is a file in `.flw/reviews/` with the
shape in `$FLW/core/schemas/review.schema.json`, and nothing else is required to make it
real.

If the user asks to change how a lens behaves, do this rather than editing in place, and
tell them the copy is now theirs to maintain.

**Ask which team first** when the role exists in more than one — `correctness` is in both
shipped teams with materially different text, and flw keeps no history of which you last
ran, so there is nothing to infer from. If a project copy already exists, edit it
directly; the copy step is only for a shipped config.

What a perspective can and cannot change: it widens or narrows **what the lens hunts
for**. It cannot make reviewers report more aggressively — the discipline in §2 is
injected verbatim into every one of them and governs severity, padding and evidence. If
someone wants "harsher", widen the hunt and tell them where the ceiling actually is.
