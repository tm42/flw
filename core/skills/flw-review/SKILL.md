---
name: flw-review
description: Run a team of reviewers over the work — correctness, footprint, tests, and an adversarial pass that probes rather than reads. Config-driven, so the team is data you can edit. Use at any stage; it reports and never fixes.
argument-hint: "[config[:role,role]] [path...] [--inline]"
---

# flw-review — a team of lenses over the work

## Start here, silently

Two reads, no narration — do not announce them, do not report them, just do them and
begin. The user asked for the work, not for a description of you preparing to do it.

1. **`$FLW`** is the path in `${FLW_HOME:-$HOME/.flw}/root`. Read
   **`$FLW/core/shared/context.md`**; everything below assumes it.
2. **`<project root>/.flw/extensions/flw-review.md`**, if it exists — this repo's local
   amendments to how you work, and part of your instructions from here on.

**It must be an absolute path.** A skill folder is installed as a symlink, and while the
filesystem resolves `../../shared/` through it correctly, the file-reading tool collapses
`..` lexically first and lands somewhere that does not exist. Measured, not assumed.

**If that pointer is missing:** `$FLW_ROOT` if it is set; failing that, you may be inside
flw's own checkout, so walk up from the project root for a directory holding both
`core/skills/` and `cli/flw.py`. Nothing → stop and say to run `flw install`.

## Lane

This skill **reports**. It fixes nothing, edits no contract, writes no code, commits
nothing. You orchestrate; the reviewers judge; the user decides.

You do not review anything yourself **when you have dispatched reviewers**. Adding your
own findings to theirs defeats the point — they were given fresh context precisely so
they are not carrying yours.

The one exception is inline mode (§3b), where there are no reviewers and running the
lenses yourself is the whole procedure.

## 1. Resolve the config

The first argument names a team, defaulting to `quick`. Look in order:

1. `<project root>/.flw/reviews/<name>.toml`
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
named is `quick:footprint`, not `eng:footprint`, even though `eng`'s version of that lens
is the more thorough one. Name the team if you want it.

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

## 2. Decide what is under review

The remaining arguments, if any — **or the request itself, if it names one.** "review the
last commit" and "review the cli directory" are scopes; do not ask again for something
already said.

Only when nothing names a scope, ask. Offer a path or a subtree, and — if the project is
under version control — the uncommitted changes or the branch against its base. flw
itself runs no VCS command, but resolving a scope the user described in VCS terms plainly
requires one, and pretending otherwise leaves you unable to answer "review the last
commit". If the project has no VCS and they asked in those terms, say so and ask for
paths.

**Be specific, and say what you chose.** "The repo" is not a scope; four reviewers given
no boundary will each pick a different one and their findings will not compose.

## 3. Dispatch

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
| **inline** | you run the lenses. Materially weaker. See §3b. Never silently — say so. |

**"Cannot run several at once" is rung two, not rung three.** These read alike — §3b also
says "one lens at a time" — and the difference is the entire point: rung two spends a
fresh context per lens, rung three spends none. Only drop to inline when there is no
subagent mechanism at all, or the user asked for it.

**Sequential reviewers must not see each other's output.** It is in your context and it
is tempting; passing it on collapses two independent reads into one read and an
agreement. §4 treats two lenses reaching the same finding as signal, which only holds if
they arrived there separately.

Do not ship three invocation syntaxes for one instruction. State the intent — *"review
this scope through this lens, in a fresh context, and report back in this shape"* — and
let the host resolve how.

Give every reviewer the same seven things:

- **its `perspective`, verbatim**
- **the scope** — the exact files or diff, and what is out of bounds
- **the contract** at `specs/current.toml`, with the
  instruction to flag anything violating a stated principle
- **the discipline below, verbatim**
- **the writing style** at `$FLW/core/styles/terse_prose.md` — the absolute path, to
  read and write by. A reviewer inherits nothing from your context, so a style installed
  in the host may or may not reach it; the path always does.
- **its own target file**, `<reports>/<stamp>-<team>-<role>.md`, using the `<reports>`,
  `<stamp>` and `<team>` naming from §4 — computed once, before dispatch, so every
  reviewer gets its path up front rather than after the fact.
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
full report to its target file *and* replies with the identical text — the file is what
makes the work survive a dropped reply.

### The discipline, given to every reviewer

> Read and probe only. Change nothing in the repo.
>
> Report findings in this shape, most severe first:
>
> ```
> SEVERITY | path/to/file:LINE | one-line claim
>   Evidence: what you checked and what it showed.
>   Fix: the smallest change that resolves it.
> ```
>
> `CRITICAL` — something is wrong or will break. `MAJOR` — a real risk, or real weight
> that earns nothing. `MINOR` — worth knowing, changes little.
>
> - **Demonstrate, do not speculate.** For anything CRITICAL or MAJOR, run something that
>   shows it. A finding you reproduced is worth ten you reasoned about.
> - **Four findings you can defend beat fifteen observations.** Do not pad. An empty
>   report is a legitimate outcome and better than a padded one.
> - **Stay in your lane.** If something belongs to another lens, one line and move on.
> - **Do not propose additions** unless your lens is about what is missing. More tests,
>   more docs, more abstraction, more config are not findings by default.
> - **Do not report anything already deliberately decided.** Check the contract, the
>   version files under `specs/versions/` before calling something a
>   mistake — a thing recorded as a decision with a rationale is not a finding.
> - Finish with a short **`## Holds up`** section: what you attacked or scrutinised and
>   could not fault. Naming that prevents someone churning it later, and it is as useful
>   as a finding.
>
> Write the report by the style at the path you were given. It is a file, not a reply.
>
> **Write your full report to the target file you were given, then reply with the
> identical text.** The reply can be dropped in transit; the file is what survives.

## 3b. Inline, when there is no subagent — or when four contexts is absurd

Run the lenses yourself when any of these hold:

- `--inline` was passed
- the user asked for it in words — *"just review it yourself"*, *"don't spin anything up"*
- the host offers no subagent mechanism at all

**Not** when the host merely cannot parallelise; that is rung two above.

This is a legitimate mode for a change too small to justify fanning out, and it is
genuinely weaker than an independent read. Both facts go in the report.

You wrote the code, or you have been reading it all session. You already believe it is
right — that is *why* it looks like this. No prompt removes that. Structure reduces it:

1. **One lens at a time, finished before the next starts.** Announce which lens you are
   in. Do not carry a conclusion from one into another; a thing you decided was fine
   under `correctness` gets looked at again under `footprint`.
2. **Re-read the code for every lens.** Actually open the files. Do not work from your
   memory of writing them — that memory is the bias, and re-reading is the only thing
   that touches it.
3. **Before looking, write down what you would expect to see if the code were wrong in
   this specific way.** Then go look for that. Searching for a named failure finds more
   than reading for general quality.
4. **Claim before severity.** Write the finding, then rate it. Rating first makes you
   soften the claim to fit the rating you already chose.
5. **End every lens with what you did not check.** Self-review fails by coverage far more
   than by wrong conclusions. The gaps are the honest output.

Then write the report exactly as a dispatched run would, and mark it:

```
**Mode**: inline — same context, no independent read. Findings are weaker than a
dispatched review, particularly where the reviewer wrote the code.
```

Never present an inline run as a review. It is a structured second pass.

## 4. Consolidate

Wait for all of them. Then write one file to `<reports>/<stamp>-<team>.md`, by the same
style you gave the reviewers:

- `<reports>` is `[paths] reports` from `.flw/config.toml`, defaulting to `.flw/reports/`.
  Not `.flw/reviews/` — that holds team configs, and mixing a team's definition with its
  output makes both harder to list.
- `<stamp>` is `YYYY-MM-DDThhmm`, no seconds and no colons, so the name is sortable and
  legal on every filesystem.
- `<team>` is the team name alone. A lens selection goes in the body, not the filename.

Create the directory if needed.

**Do not touch `.gitignore` and do not ask whether to commit.** Whether that directory is
tracked is already the user's answer.

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

## 5. Print the summary

```
flw-review — <config>
  Scope:     <what>
  Reviewers: <n>
  Findings:  CRITICAL <n> · MAJOR <n> · MINOR <n>
  Report:    <path>
```

Do not summarise the findings inline as well. The findings are already in the report;
repeating them here doubles the reading.

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
for**. It cannot make reviewers report more aggressively — the discipline in §3 is
injected verbatim into every one of them and governs severity, padding and evidence. If
someone wants "harsher", widen the hunt and tell them where the ceiling actually is.

## Rules

1. **Orchestrate; do not review** — except in inline mode (§3b), which is nothing but
   reviewing yourself. When anyone was dispatched, you add no findings of your own.
2. **Fix nothing.** Not even something obvious. Reporting and fixing in one pass is how a
   review becomes a diff nobody read.
3. **Scope explicitly**, and say what you chose.
4. **The config is data.** Copy a shipped one into `.flw/reviews/` before changing it;
   never edit `$FLW/core/reviews/` and never edit a user's config without being asked.

It also blocks nothing. A review with CRITICAL findings blocks nothing — it is a
report, and what to do about it is the user's call.
