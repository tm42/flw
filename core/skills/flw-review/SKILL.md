---
name: flw-review
description: Review the work with one reader by default — correctness, footprint, tests or an adversarial pass, told what its own position makes it bad at — and escalate to a configurable team of lenses in fresh contexts by naming one. Use at any stage; it reports and never fixes.
argument-hint: "[team[:role,role]] [path...]"
---

# flw-review — one reader by default, a team on request

## Start here, silently

One command, no narration — do not announce it, do not report it, just run it and begin.
The user asked for the work, not for a description of you preparing to do it.

```sh
flw context flw-review
```

It prints everything this skill opens with: the shared context, the project root it
resolved and where that came from, this repo's extensions from the outermost project root
inward, the note store listing for this project's category, and the contract's components
with the paths each one covers. Everything below assumes it.

**If the request names a repository, a directory or a file, pass it** —
`flw context flw-review --root <that path>`. The rule and its reason are in the shared
context the command just printed; this is the only part of it the command cannot tell you,
because you have to call it first.

**Every extension it printed is part of your instructions from here on.**

**If `flw` is not on PATH:** run it out of the checkout — `<interpreter> "$FLW/cli/flw.py"
context flw-review` — where `$FLW` is the absolute path in `${FLW_HOME:-$HOME/.flw}/root`.
It must be an absolute path: a skill folder is installed as a symlink, and the file-reading
tool collapses `..` lexically before the filesystem resolves it, landing somewhere that
does not exist. If that pointer is missing you may be inside flw's own checkout, so walk up
from the project root for a directory holding both `core/skills/` and `cli/flw.py`.
Nothing → stop and say to run `flw install`.

## Lane

This skill **reports**. It fixes nothing, edits no contract, writes no code, commits
nothing. By default you are the reviewer yourself — read §3 below. Naming a team flips
this: you orchestrate, the dispatched reviewers judge, and you add no findings of your
own — they were given a fresh context precisely so they are not carrying yours.

**A knowledge file you find wrong is yours to correct.** Rewrite that one file and
`flw know --stamp` it. That one file — the single exception to reporting and never fixing,
because the store records what is, and what is has already changed.

## 1. Decide what is under review

The remaining arguments, if any — **or the request itself, if it names one.** "review the
last commit" and "review the cli directory" are scopes; do not ask again for something
already said.

Only when nothing names a scope, ask. Offer a path or a subtree, and — if the project is
under version control — the uncommitted changes or the branch against its base. flw
itself runs no VCS command, but resolving a scope the user described in VCS terms plainly
requires one, and pretending otherwise leaves you unable to answer "review the last
commit". If the project has no VCS and they asked in those terms, say so and ask for
paths.

**Be specific, and say what you chose.** "The repo" is not a scope; a run given no
boundary picks its own and a later round cannot tell what this one covered.

## 2. Pick the lens

**A team named in the request — or as the first argument — sends you to
`references/team-dispatch.md` now.** That file owns config resolution, dispatch and
consolidation from here; nothing below applies to that run. Naming a team is the only
thing that triggers it.

Without one, you are the sole reviewer, through the lens or lenses named — a
comma-separated list, the way a team's `:role,role` selects more than one. Users ask for
it by what they want looked at, not by role name. Map it, and **say which lens or lenses
you chose** so a wrong guess is visible:

| they say | lens |
|---|---|
| redundant, bloated, over-engineered, dead code | `footprint` |
| bugs, correctness, does it work, edge cases | `correctness` |
| tests, coverage, are the tests any good | `tests` |
| break it, security, robustness, what if | `adversarial` |

Nothing in the request maps to one of these — "just review it", no lens named — defaults
to `correctness`: whether the code does what it claims is the question every lens leaves
for someone else if it doesn't ask it first, and it is the one every shipped team carries.

**Resolve the chosen lens's `perspective` text the way a dispatched reviewer's config
gets resolved:** `.flw/reviews/quick.toml` if the project has one, else
`$FLW/core/reviews/quick.toml`. `quick` defines `correctness` and `footprint` only; for
`tests` or `adversarial`, the same project-then-core lookup on `eng.toml` instead — say
which file the perspective came from. `flw validate <config>` first if it is
user-authored and you have not seen it before.

## 3. Review it

You are the reviewer for the lens §2 resolved. Bias risk depends on how you got here (see
the Mode line below): if you wrote the code, you already believe it is right — that is
*why* it looks like this, and no prompt removes that, only structure does. If you did
not write it, the risk is coverage instead — reading less than you think you did. The
five steps below address both:

1. **One lens at a time, finished before the next starts.** Announce which lens you are
   in. Do not carry a conclusion from one into another; a thing you decided was fine
   under `correctness` gets looked at again under `footprint`.
2. **Re-read the code for the lens.** Open the files again. Do not work from your
   memory of reading them earlier in this session — that memory is the bias, and
   re-reading is the only thing that touches it.
3. **Before looking, write down what you would expect to see if the code were wrong in
   this specific way.** Then go look for that. Searching for a named failure finds more
   than reading for general quality.
4. **Claim before severity.** Write the finding, then rate it. Rating first makes you
   soften the claim to fit the rating you already chose.
5. **End with what you did not check.** Coverage, not conclusions, is where a solo read
   fails hardest. The gaps are as useful as a finding.

You already have two of the eight things `references/team-dispatch.md` §2 has to hand a
dispatched reviewer explicitly: the writing style, from your own opening, and the note
store, printed there too. Line up the rest yourself: the scope from §1; the contract
narrowed to it, by running `flw context flw-review --scope <the paths in scope>` rather
than reading the whole file; and the knowledge store narrowed to it — `flw know <path>`
for each path in scope, heads not bodies. Compute your target file before you start:
`<reports>/<stamp>-<config>-<role>.md`, the same naming a dispatched reviewer's own file
uses, with `<reports>` and `<stamp>` named the way `references/team-dispatch.md` §3
states and `<config>` the file §2 resolved the perspective from.

### The discipline, followed even reviewing alone

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
> - Finish also with **`## What I did not check`** — the boundary of what you read and
>   ran. It is the half a later round needs, and the half `flw-spec` carries into the
>   version record that outlives this report.
>
> Write the report by the style at `$FLW/core/styles/terse_prose.md` — the absolute
> path, to read and write by. It is a file, not a reply.

Then mark the report with a Mode line naming which of these you are, not just that you
ran alone — each bounds what the report can claim differently:

- **wrote the code under review** — weakest. The re-read and probe discipline above is
  the partial compensation.
- **wrote the version record and watched another agent execute it** — can confirm the
  record landed, cannot audit whether the record was right. Three of the four findings
  the spec critic filed against `finish-the-store` were in the record, not the run.
- **had no hand in it** — a fresh read that happens to share a context. The coverage
  boundary in "What I did not check" is what to watch.

Never present this as a dispatched review. It is a structured, disclosed read.

## 4. Print the summary

```
flw-review — <config>
  Scope:     <what>
  Reviewers: <n>
  Findings:  CRITICAL <n> · MAJOR <n> · MINOR <n>
  Report:    <path>
```

Do not summarise the findings inline as well. The findings are already in the report;
repeating them here doubles the reading.

## 5. Offer a note

*Write it only if it was measured, and the next agent, in a repository that does not hold
this one's history, could not get it faster than measuring it again.* Yes means read `flw
kb write --help` first, then say what you would write. It is an offer — the run declines
by doing nothing.

## Rules

1. **Review by default; orchestrate when a team was named.** Dispatch adds no findings
   of your own — the reviewers were given a fresh context precisely so they are not
   carrying yours.
2. **Fix nothing.** Not even something obvious, and except the knowledge-file correction
   above. Reporting and fixing in one pass is how a review becomes a diff nobody read.
3. **Scope explicitly**, and say what you chose.
4. **The config is data.** Copy a shipped one into `.flw/reviews/` before changing it;
   never edit `$FLW/core/reviews/` and never edit a user's config without being asked.

It also blocks nothing. A review with CRITICAL findings blocks nothing — it is a
report, and what to do about it is the user's call.
