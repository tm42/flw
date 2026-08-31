# Posture: what flw's agent should be told, and where

Design document. Precedes a spec; nothing here is a contract yet, and nothing here is specced
until the 3.x stack lands.

Written 2026-08-23, revised 2026-08-24 after two independent reviews. The source of record is
flw's own defect history — the review reports and the version files — read alongside an
external skill with a published benchmark. Where the two disagree the record wins, because it
is about this project rather than about agents in general.

One fact out of it frames everything below. **There is no over-build finding anywhere in flw's
record** — not in either review report, not in `docs/verified.md`, not in any version file. What
flw has actually shipped is the opposite failure: minimal code with no check behind it. So the
ranking is led by that, not by a benchmark.

## 1. What to add, ranked by the evidence behind it

### 1.1 Code without its check is unfinished

**Primary.** Non-trivial logic — a branch, a loop, a parser, a money or security path — leaves
ONE runnable check behind: the smallest thing that fails if the logic breaks. An assert-based
self-check or one small test file. No frameworks, no fixtures, no per-function suites. Trivial
one-liners need none.

This is the only proposed line that maps onto damage flw actually shipped:

- `.flw/reports/2026-08-22T1959-final.md:18` — a CRITICAL where the previous review's two-part
  fix went in half-done. Verbatim: *"Only the first half shipped, and it is the half with a
  test."* The half without a check silently did not land, and uninstall then selected a style
  flw had just deleted.
- `.flw/reports/2026-08-22T1434-styling.md` — four independent findings where a mutation
  survived: the dry-run guard, `report_style`'s branches, doctor's exit code, and
  `shadowing_style`. Non-trivial logic shipped with nothing that fails when it breaks.

It is also the counterweight that makes everything else here safe. Every other element pushes
toward writing less; this is the one that says what writing less does not excuse.

**It collides with an existing lane and the collision must be resolved in the same edit.**
`core/skills/flw-execute/SKILL.md`, under "What this skill does not do", lists *"write tests
the contract did not ask for"* (`:272-273`). Adopted verbatim, ambient and execute contradict each other
inside every execute run. The reconciling sentence: a change's own check is part of the change,
not a test the contract did not ask for.

Adherence is unmeasured, here and in the external work that suggested the rule — the one
harness that computes the metric has never published it. Say so rather than implying
otherwise.

### 1.2 Reach for what already exists before writing anything new

flw's Posture says to name what breaks without a new artifact, and to search for the helper
that already exists under another name. It says nothing about the language's own library, the
platform's own features, or a dependency already installed.

**In flw's own wording, because flw is language-agnostic.** "Stdlib does it" is
right for Python and Go, weak for TypeScript, and meaningless for Terraform. One rung:

> Before new code, reach for what is already here — the language's own library, the platform's
> own features, a dependency the project already has, and the conventions this repo already
> follows. New code before a new dependency.

The trailing clause is deliberate. The standing objection to any "prefer native over a
dependency" rule is that it is wrong in a repo with an established component library. Ordering
the rungs answers it structurally — "already in this codebase" and "already-installed
dependency" both fire before the native rung — but agents read the native rule as absolute. flw
is better placed than a rule file alone, because `flw-research` writes a repo's conventions into
`.flw/extensions/*.md`; but that only applies inside a skill invocation, and the ambient block
is always-on and not per-repo. So the clause has to live in the ambient text itself.

### 1.3 Never simplify away

flw says "minimal is not partial" and names nothing. Name them: input validation at trust
boundaries, error handling that prevents data loss, security, accessibility, anything
explicitly requested.

Two lines, and the evidence is thin but real and points the right way. In the one benchmark
that looked, the only arm that dropped a guard was the one told to be minimal and nothing else,
which let `../../` escape on the task where it wrote fewest lines. One slip in twenty, n=4,
one model. flw's own record has the same shape once: `style_source` accepted `../evil` and wrote
outside the host's directory (`2026-08-22T1434-styling.md:92`).

### 1.4 Root cause, not symptom

A report names a symptom. Grep every caller of the function you are about to touch; one guard in
the shared function is a smaller diff than a guard in every caller, and patching only the path
the ticket names leaves every sibling caller broken.

Backed twice in flw's record. `2026-08-22T1959-final.md:98` — `shadowing_style` "moved the path
off `~/.claude` and stopped one step short", fixing the case the finding named while the sibling
case stayed broken. And `docs/verified.md:89` — the host LSP returned 1 of 8 real callers for a
symbol reached through a dynamic import, which is why the rule says *grep*, not *use the
reference tool*.

### 1.5 Nothing found is not nothing looked at

**Not adopted from anywhere; this one is flw's own.** An empty result and an unexamined question produce the same silence,
and this is the most-repeated failure class in flw's whole record.

**v4.1 addressed it on the tool side and stopped there.** Its summary: *"every place a tool
reports a false negative about its own work: a setup typo that turns failures into skips, a
validator that stops at the first bad file, a reviewer whose report is lost in silence."*
`run_tests.py:33` now reads `SETUP_FAILED = 125  # deliberately not 127, which Result.state
reserves for a missing command`. That fixes the instances in flw's own tools and states no
rule for an agent working in someone else's repo. What follows is the agent-side complement,
not a duplicate — and the four instances below are now the argument for the rule rather than
live defects.

Four instances, each patched at its own site, no rule stated anywhere:

- `flw test` exiting 2 is not a pass (`core/shared/context.md:42`)
- the `-A` run with nothing declared, which "reads as a pass" (`docs/verified.md:81`)
- an LSP returning nothing, indistinguishable from a symbol nobody calls (`docs/verified.md:89`)
- `doctor` printing problems and exiting 0 (`2026-08-22T1434-styling.md:113`)

Its sibling, already named in `docs/verified.md` after biting twice and predicted to bite a
third time: **evidence you produced yourself is not evidence.** A file you wrote, a test shaped
until it passed, a summary of your own work — none of them confirm anything about the world.

### 1.6 Considered and not adopted

**Reordering the existing bullets into a ladder with a stop condition.** It is re-arrangement
of content flw already has — *Smallest change that fully satisfies the ask*, *Follow what is
already there* and *Root cause, not symptom* are all present in `ambient.md`'s Posture — and
there is no evidence in either direction that the ordered form changes behaviour.

There is now one weak data point against it. Facing the same problem in the same week — a
list of prose rules with no stopping condition — `9cb9255` chose a **two-part test** ("each
fact earns its place twice") rather than an ordered ladder, and the result is shorter and
covers a case the ladder missed. One author's choice is not evidence about models. It is
still the only thing either way, and it points away from ladder form.

**Promoting "state the limits" into the ambient block as its own leg.** It is already stated
at every point of use: `flw-execute/SKILL.md:267` ("A check you could not run is not a check
that passed") and its refusal to claim the work is done, `flw-research/SKILL.md:153` ("Say what
you could not determine"), `flw-review/SKILL.md:170`'s `## Holds up`, `context.md:103` ("The verification is
the user's. Do not simulate it."). Promoting it adds coverage only for non-flw work under the
block. Worth one sentence, not a leg.

## 2. The prose counterpart: relaying is not piping

Same shape as §1, different file — this lands in `core/styles/terse_prose.md`.

**Most of what this section originally proposed has already shipped.** Commit `9cb9255`
rewrote the style guide with a "The reply as a whole" section, and its central sentence is
the evidence stop-condition this document was designed around:

> Each fact then earns its place twice: the reader acts on it, or without it they would not
> believe a claim they must act on. The same measurement can be either — the product when
> they asked what you found, the derivation when they asked what to do.

That is a stricter rule than the ladder drafted here, and it carries something the ladder did
not: whether a fact is evidence depends on what was asked, not on the fact. Nothing further is
needed for the general case.

**What remains unwritten is the relay case.** The observed failure: relaying a subagent's
review, the same findings were written twice — once at roughly forty lines, once at eight. The
long one was unreadable through bulk; the short one was unusable, because a claim like "zero
over-build findings" cannot be acted on without knowing what corpus it is over. Neither
version was wrong about the findings. Both got the reply's *kind* wrong, and the style guide
now names that failure without covering the case that produces it most reliably.

The rule:

> When you are relaying another agent's findings, you are the filter, not the pipe. Give what
> changed, the one thing you verified yourself, and where the rest is. A review is already a
> written artifact; reproducing it inline is refusing to do the job.

One rule. It is not a ladder, and §1.6 records why.

## 3. Delivery

`core/shared/ambient.md`, installed as the tagged block flw already writes into all three
hosts' top-level instructions files. About ten lines added to the `## Posture` section, plus the
reconciling sentence in `flw-execute`, plus §2's rule in `terse_prose.md`.

**Not the output-style slot.** `outputStyle` is singular on Claude Code — one key, one value —
so prose and build discipline could not both be selected and would have to become one file.
The slot stays a prose slot.

**No hooks.** An earlier draft proposed `SessionStart`, `SubagentStart` and a write-time hook to
re-establish the block. Dropped entirely, for four reasons, any one of which is sufficient:

- The payload does not justify it. Ten lines added to a block that already installs everywhere.
- The premise was wrong. An instructions-file block is in the system prompt, which is rebuilt
  every request; a compaction does not remove it. What changes is salience, not presence — and
  the subagent claim rested on a v3.2 measurement about the *output style*, a different channel.
- A tool-call hook falsifies the contract's own assumption. "flw does not intercept, wrap, or
  police host operation" — a `PreToolUse` hook intercepts under any plain reading, and can block
  by exit code, and the layer flw deleted explicitly included a post-edit hook.
- On Codex it needs plugin packaging, which is the first entry in `final_state.removed`
  (`test ! -e .claude-plugin`). On Claude Code the plugin-free path mutates
  `~/.claude/settings.json`, the same class v3.2 deliberately gated behind a y/N prompt.

If the block turns out not to reach subagents, that is a probe and a separate decision about a
mechanism flw already owns — handing a reviewer an absolute path, which `flw-review` does today
for the style.

## 4. What we do not know

- **Whether the block reaches subagents, and how much salience it loses across a compaction.**
  Both are measurable with a probe; `flw-probe-test` is the pattern. Neither is measured.
- **Whether §1.1 is adhered to.** The one harness that computes the metric never published it.
- **Whether the ladder form does anything.** §2 is the trial; §1 declines to run one.
- **How any of this behaves in a repo with an established design system.** flw is better placed
  than a rule file alone because of `flw-research`, but "better placed" is not "tested".

## 5. Where this lands

**v4.5.** The 4.x work it waited on has landed; the contract sits at 4.4 and this is next.

It is: about ten lines into `ambient.md`'s Posture (`:30-46`), one reconciling sentence in
`flw-execute/SKILL.md` (`:272-273`), one rule in `terse_prose.md`, and one path in
`specs/current.toml:140` — `plans/design-v3.md` widened to `plans/`, so a design document is
covered by the component that already promises a reader can find "why flw is shaped the way
it is, including what was deliberately not built". No CLI change, no new file, no new
mechanism, no assumption touched. Small enough to execute in one phase.

Two things deliberately outside it. **The dispatched-reviewer coverage gap** — `:206` is
inline mode, and the dispatched discipline ends at `:170` with `## Holds up`, which is what
withstood attack rather than what went unexamined. Real, unaddressed across five versions, and
a different change with a different justification. **5.0** — three commits that landed during
this work (`84b2ddc`, `cd4aca9`, `0984d94`) removed most of what motivated dropping numbered
spec versions, so what 5.0 is for wants re-deciding before it is scheduled.
