# flow v3 — design document

**Status**: built and installed. The design is history; §1.1 records where the build
went another way. What running it established is recorded as comments at the code each
finding explains.
· **Date**: 2026-08-20, superseded-list updated 2026-08-22
**Supersedes**: flow v2 (schema v2, Claude Code plugin) and the `flw` fork
**Evidence base**: `plans/generalisation-research.md`; host research verified against
primary docs, August 2026

---

## 1. What this document is

A complete design for flow v3: what it is, what it deletes, what it keeps, and how it
ships. It is the input to the spec, not the spec.

**Read §1.1 first.** This document was the input to the build, and the build disagreed
with it in fifteen places. The code is the authority; this is why the code is shaped the
way it is, including what was deliberately not built. For what running flw actually
established — as opposed to what it was designed to do — read the comments at the code:
`specs/current.toml:53` records why there is no separate document.

### 1.1 What the build superseded

This document was written before the build, and the build settled some of it differently.
The code is the authority where they disagree; this list exists so the difference reads as
a decision rather than as drift.

| Here | Shipped | Why |
|---|---|---|
| `flow`, `/flow:<skill>` | `flw`, `/flw-spec` and `/flw-execute` | The name changed, and without plugin namespacing a skill's directory name *is* its invocation, so a bare `spec` would collide. |
| §6's modes `init / respec / delta / quick_fix` | `spec / re-spec / quick_fix` | Superseded by §5.4 within this document: `delta` is an artifact, not a change type. |
| §7's `[paths] contract = "specs/current.toml"` | `[paths] specs = "specs"` | Tools address a specs *directory* and find the contract and version files inside it; pointing at a lone file leaves the rest homeless. |
| §7's `~/.flow/config.toml`, §4's `~/.agentic/config.toml` | `~/.flw/config.toml` | The document disagreed with itself; `$FLW_HOME` relocates the whole directory. |
| §7's `[paths] reports` | not built | Belongs to the review skill, which is not built. It arrives with it or not at all. |
| §9.1's "superset frontmatter carrying every host's optional keys" | `name`, `description`, `argument-hint` | The OpenCode keys are for OpenCode *commands*, not skills. The superset means fields that do something somewhere, not every field that exists. |
| §8.2's POSIX shim at `~/.local/bin/flw` | `cli/flw.py` symlinked directly | A version check ahead of the `tomllib` import does what the shim was for. |
| §9.2's `flow doctor --host <name>` | `flw doctor` reports every host | Filtering a nine-line report earns nothing. |
| An amendment engine editing the contract through keyed operations | ordinary text editing | Editing is byte-preserving by construction; the engine created a corruption class editing does not have. §5.5. |
| `specs/ledger.toml`, an append-only version index | one file per version under `specs/versions/` | The directory listing is the index; `applied` is the queue. §5.5. |
| kind and impact derived from operations, and stored | neither derived nor stored | The derivation guarded a version number, and the human reviews the version file regardless. §5.5. |
| `specs/deltas/` holding work orders for large changes only | `specs/versions/` holding one file per version | Every version leaves a record; how much it carries follows the change. §5.3. |
| `applied`, and any record of whether work is done | nothing | flw tracks no notion of done. Every flag protected a version number a human assigns while numbering the file. |
| §9's `adapters/` — a directory of per-host paths and setup notes | `Host` in `cli/flw.py`, printed by `flw doctor -v` | The CLI already held the data and already printed it. A directory of notes was a second home for something live, which is the duplication §14 removed elsewhere. |
| `design.md` — durable principles, injected into every skill, with `check:` lines parsed out of prose | `.flw/extensions/<skill>.md`, written by `flw-research` | Extensions became the per-repo prose layer, per skill and generated rather than typed. flw was built with flw and never wrote a `design.md`. Removing it also deleted a regex that parsed commands out of prose — no command in flw now lives inside a sentence. |
| §11's `/flow:research` producing a regenerable repo *map* | `flw scout`, run on demand, output never stored | A published A/B test (N=438) found static repo overviews do not improve agent performance and LLM-generated ones slightly hurt. The scout runs in under a second, so the recipe is recorded and the orientation is not. |
| §11's conventions going into `design.md` | `.flw/extensions/flw-review.md` and the contract | Research records what **is**; what **must be** stays the user's, in the contract. A distilled convention may be a habit worth killing rather than a rule worth enforcing. |
| §12's `--justdoit` and `mode = "trusted"` | neither, with the hook layer | flw has no hook layer to relax. Hosts own permission policy. |
| "gates" throughout — `flw gates`, `success_criteria.gates`, `[gates]` | "tests" — `flw test`, `success_criteria.tests`, `[tests]` | A gate is agent-shop jargon for a thing every developer already calls a test. The historical prose below still says gate; the live surface does not. |

---

## 2. Why v3 rather than an amendment

v2 is a Claude Code plugin that assumes Python, uv, and a taxonomy of project types.
Each assumption was true of the first projects flow ran on and none is true in general.
The evidence (full detail in the research note, each item reproduced by execution):

- A canonical DS project **cannot be specced** — `.ipynb` has no language profile, and
  an unregistered extension is a hard semantic error.
- MLE **cannot express an unbounded metric** — `threshold` is clamped `0.0–1.0`,
  rejecting RMSE, MAE, perplexity, latency. `metric`/`threshold`/`baseline` are
  **never read by any code**: structure cosplaying as enforcement.
- A Rust project **cannot have one checked `design.md` principle** — `check_design`'s
  hand-copied runner list has drifted from the registry and omits every cargo runner.
- `project_type` is **mechanically inert** in v2: its only live effect is selecting one
  of three `success_criteria` shapes, and forcing exactly one.
- `interface` is read in **exactly one place** (`scaffold.render_module`), written once,
  and never compared to the file again. It is a seed, not a contract.

And the sharpest one: **flow's own contract cannot use flow's central abstraction.**
`specs/current.toml` carries `modules = []` plus an assumption apologising for it, and
empty `dependencies`. Two of the four fields the v2 schema requires of every project are
placeholders in the one project we know best.

The changes needed carry `remove` ops throughout and delete the packaging model. In v2's
own vocabulary that is a respec — the largest kind of amendment. But it is not even that:
v2's contract is discarded rather than amended (§16), so v3 begins with an `init` that
happens to reuse some of v2's code.

### 2.1 What flow-lite (`flw`) already proved

flow-lite is a prior attempt at exactly this — a portable, language-agnostic fork,
now running on a second machine and further upgraded there. It is not a false start; it
is **empirical validation of four v3 decisions**, and it de-risks them:

| flw shipped | v3 decision it validates |
|---|---|
| No language registry; `runner` is a free-form string — *"flw declares no registry; the environment provides the tool"* | §7 — commands are a project property, not a language one |
| Structure-only scaffold: dirs + verbatim stubs + declared test files, then stop. No manifest, no venv, no compile | §6.1 — provisioning is not a separate command's job |
| Ships **no hooks**; runs under normal permission prompts. *"Hooks may be layered on per-environment later, but are never part of flw"* | §9.3 — v3 ships no hooks at all. flw has run hookless for months; that is the field evidence |
| `SETUP.md` written as a prompt **for an agent to execute** — idempotent, detect-and-skip, "never edit `permissions` or `hooks`" | §9.2 — human+agent setup, verified rather than claimed |
| `CLAUDE.sample.md` — token discipline, agent posture, an flw quick-reference, when-stuck and decision rules | §13 — the ambient-context extension |

It also demonstrates the size prize: **2,481 lines against flow's 6,166** for commands +
scripts + agents — 40% of the surface, from deletions v3 makes permanent.

**The deployed version validates more than the snapshot does.** Reported from use
(the tree itself is not reachable from here, so this is the author's account, not
inspection):

| Running in production on the second machine | v3 section it de-risks |
|---|---|
| Specs carry versions | §5.4 |
| `spec` / `re-spec` / `quick_fix` as the taxonomy, with deltas for re-spec | §5.4 — and see the divergence below |
| **A symlink mechanism against a core skills repo, spread across Codex, OpenCode and CC** | §8.3 — the distribution model is not a proposal, it already works |
| **Skills carry everything every host needs, in one file** | §8.3's superset-frontmatter bet, already proven |
| Custom env-specific skills added through the same mechanism | §10's one-shape-for-everything |
| Only **`spec` and `execute`** are used, both heavily modified for token economy and a *minimal-implementation, think-and-probe-before-coding* posture | §6, §11, §12 |

Two divergences the design must reconcile rather than paper over:

- ~~Three change types, not four~~ **— resolved toward the field version.** §5.4 now runs
  `spec | re-spec | quick_fix`, with `delta` demoted from a change type to the artifact a
  re-spec produces, and `quick_fix` taking the minor slot. That also deletes the PATCH
  level an earlier draft invented, and with it three call sites of breakage.
- **Two commands carry the load.** `review` is not used on that machine at all. §6's five-skill
  surface should be read as *two load-bearing skills and three that must justify their
  existence*, not five equals.

### 2.2 What flow-lite did not solve

- **Still a Claude Code plugin.** `marketplace.json`, `plugin.json`, `/plugin install`,
  an `flw:` namespace. "Portable" meant *toolchain*-portable, never *host*-portable.
  No CLI, no adapters, no centralisation.
- **Still carries `project_type`** with all four of MLE/DS/ENG/CHANGE, and the
  four-branch `oneOf`. The taxonomy problem is untouched.
- **Forked from v1**, so it has *no* amendment engine, no ledger, no delta records, no
  `spec_version`. Its `scripts/` holds one file. In going lite it **lost v2's single
  best idea** — amendment-not-restatement.

### 2.3 Why v3 absorbs flw rather than coexisting

flw's own `/flw:review` found 3 CRITICAL and 7 WARN, and the CRITICALs are **all
fork-drift artifacts**, not coding errors:

- `validate.md` and `validator-smoke.md` still invoke `scripts/check_design.py`, which
  does not exist in flw — *"the advertised `design.md` `check:` capability cannot run"*, a
  documented feature with the implementation deleted.
- `spec.md` hardcodes a runner allow-list that **contradicts both the schema and
  `execute.md`**, which are free-form.
- Two command files mislabel the agent namespace as `flow:` rather than `flw:`.

That is the fork-maintenance tax, in its purest form: two codebases of one lineage
drifting, with each simplification leaving live references to what it removed. It is not
sloppiness — it is the structural cost of hand-porting.

So the strategic point: **v3 is not "flow, generalised" alongside flw. It is the thing
that makes flw unnecessary.** And the architecture that achieves it — one core, host
adapters, bundles for local variation — is precisely an anti-fork architecture. The
forked version of flw exists because there was no supported way to vary flow per
environment; §7 and §10 are that way.

Stated as an equation: **v3 = flw's portability + v2's contract engine + the CLI and
adapters neither had.**

---

## 3. Identity

`design.md` commits flow to being *"narrow, deep, enforced + verified — the opposite of
broad, portable, team-governed process tooling."* v3 does not weaken that. The
distinction that makes both true:

- **The workflow stays narrow** — few commands, one job each, interview-driven,
  amendment-not-restatement. This is the product.
- **The substrate stops being narrow by accident** — Python-and-uv, two extensions,
  three project types were never design commitments.

The substrate narrowness actively *undermines* "deep + enforced": a Rust project cannot
use the checked layer at all, so the enforcement flow advertises is Python-only in
practice. Widening the substrate makes the identity more true, not less.

**What v3 adds to the identity**: flow is *host-agnostic*. It is not a Claude Code
plugin that might work elsewhere; it is a tool with adapters, one of which is Claude
Code.

**And it ships as MIT open source.** That changes the audience without changing the
design: a stranger has to be able to install it, understand what it is, and extend it
without reading the author's mind. What it must *not* change is the leanness — an OSS
release is a reason for a good README and a clean install path, never a reason for
governance machinery, a plugin API, or a compatibility promise. §15's non-goals hold
under publication; §17's discipline matters more, not less, when the surface is public.

### Principles carried forward unchanged

Interview over inference · one job per unit · the spec is the contract · the atomic unit
is the amendment, the spec is never restated · every spec change is user-reviewed ·
single source of truth at execution time · lean over ceremonial · optional +
backward-compatible.

### Principles added

- **Declared over inferred.** Where v2 inferred a project's toolchain from file
  extensions, v3 asks once and records the answer. Inference inside a tool built to not
  infer silently was always the wrong shape.
- **Minimal restatement, everywhere.** In the contract, in the skills, in the reports,
  in the dialogue. Restatement is the failure mode flow exists to prevent in specs; it
  applies equally to flow's own prose.
- **Honest degradation.** Where a host lacks a capability, say so and degrade visibly.
  Never let a skill silently not work.
- **A workflow, not a hook layer.** flow is prescriptive and opinionated about the *loop*
  — contract, amendment, gates, review — and expandable through skills and extensions. It
  does not intercept, wrap, or police the host's own operation. Its entire runtime
  presence is skills a host chooses to load.
- **Deterministic where failure is silent; authored everywhere else.** flow's mechanical
  guarantees exist because their failure modes are invisible — a corrupted contract, a
  lost concurrent write, a version file disagreeing with the contract beside it. Those earn
  machinery. Where the work is genuine judgment and a human is already in the loop, a
  deterministic solution costs more than it saves and **harms real usage**: it produces a
  confident answer where the honest one is "this needs a decision". The line is not
  "mechanise what you can" — it is *mechanise the invariants, author the intent*.

---

## 4. Architecture

```
~/.agentic/
  flow/                     ← the clone. upstream-owned, disposable, re-clonable
    cli/                    flow CLI (stdlib only)
    core/
      skills/<name>/SKILL.md    standard Agent Skills folders (§9.0)
              <name>/scripts/   per-skill scripts — part of the standard
      scripts/*.py              shared stdlib CLIs
      schemas/*.json
      shared/*.md               fragments included by skills (spec resolution, …)
    adapters/
      claude-code/  codex/  opencode/   ← install paths + a setup note each
  bundles/                  ← yours. extension skill packages
  config.toml               ← yours. global underlay

<repo>/
  design.md                 principles + conventions (rules)
  specs/current.toml        the contract (declarative)
  specs/versions/*.toml     one file per version
  specs/deltas/*.toml       work orders (imperative)
  .flow/config.toml         project overlay
  .flow/bundles/            project-scoped skills
  .flow/extensions/*.md     prose injected into a named skill
  .flow/map.md              generated repo map (§11) — lives with its project
```

**As built** — `adapters/`, `design.md`, `specs/deltas/` and `.flw/map.md` are all gone,
and `docs/` arrived. See §1.1 for each:

```
flw/
  cli/flw.py
  core/skills/<name>/SKILL.md      four: spec, execute, review, research
       skills/<name>/references/   loaded only when that path is taken
       scripts/*.py                validate_spec, run_tests, scout (+ scout.mjs)
       reviews/*.toml              reviewer teams, as data
       schemas/*.json
       shared/{context,ambient}.md
  docs/                            what running it established
  specs/                           flw's own contract and version records

<repo>/
  specs/current.toml               the contract
  specs/versions/v<x.y>.toml       one per version
  .flw/config.toml                 project overlay, incl. [tests]
  .flw/extensions/<skill>.md       prose that skill reads here
```

The separation of `flow/` from `bundles/` + `config.toml` is load-bearing: **you can
delete and re-clone `flow/` without losing anything.** That is what makes deployment on a
new machine one clone and one command, and it removes almost all of the update conflict
surface (§8.3).

---

## 5. The contract — schema v3

### 5.1 Shape

```toml
schema_version = 3
spec_version   = "2.3"            # MAJOR.MINOR — re-spec / quick_fix

[final_state]                     # what is true when this is done
[[final_state.components]]
name     = "the note store"
paths    = ["src/notes/store.py"]
provides = [
  "a user can create, edit and delete a note",
  "a user can recover a note deleted in the last 30 days",
]
implementation = "SQLite, one file per user, WAL mode. No ORM."   # optional

removed = [
  { statement = "the v0.6.x three-agent pipeline", check = "..." },
]

[success_criteria]                # how we know — commands first
tests    = [{ command = "pytest -q" }, { command = "ruff check ." }]
criteria = "what the tests cannot express"

assumptions    = ["..."]          # what would force redesign if false
open_questions = ["..."]
```

**No `project_type`. No `description`. No `modules`. No `interface`. No `dependencies`.
No `[[dag]]`. No `[[changes]]`.**

`implementation` is optional and holds only what is **binding** — a constraint that, if
violated, would need a re-spec. "SQLite, not a service" qualifies; "probably use a
dataclass" does not. If it does not constrain, it is not spec.

### 5.2 Why this is MECE

Five questions, one home each:

| Question | Field |
|---|---|
| What exists when this is done? | `final_state.components[]` |
| What can a user do with it? | that component's `provides[]` |
| What is gone? | `final_state.removed[]` |
| How do we know it works? | `success_criteria` |
| What would force a redesign if false? | `assumptions` |

Tested against flow's own current contract: every `behaviour.statement` maps to exactly
one component's `provides`, every `final_state.present` entry becomes a component,
nothing lands in two places, nothing is homeless.

`description` is deleted outright rather than absorbed: the first version file already
carries `summary = "<one line: what this project is>"`. It was triply redundant.

Cross-cutting behaviours work because a component may be conceptual rather than
file-shaped — flow's existing contract already does this: "the v2 amendment engine (…)"
names one capability spanning four files.

**Known cost**: the flat, scannable "what can a user do" list is gone. It is derivable
by concatenating every `provides`, and skills that need it should render it rather than
the contract storing it twice.

### 5.3 The artifacts

Two file types. Nothing else.

```
specs/current.toml         the contract — what is true when the work is done
specs/versions/v2.0.toml   one file per version — how this version came about
```

The contract is **declarative**: the destination. A version file is **imperative**: the
route, plus a record of why. Reading them together is the normal case — a version file
never restates what the contract says, because the contract is right there.

```toml
base         = "1.2"        # the version this one starts from; absent on the first
spec_version = "2.0"
summary      = "tags become notebooks: a note belongs to exactly one"
applied      = false        # flipped by /flw:execute once every declared gate passes

approach = """..."""        # optional — the analysis behind the plan
[[dag]]                     # optional — phases and tasks, when the work needs ordering
[[decisions]]               # optional — forks settled, with the rejected option kept
```

**Only four fields are required, and file size follows what the change needs.** A one-line
correction is four lines. A migration with a lossy backfill and a one-way step is fifty.
Nothing about the classification dictates which fields appear — a small additive change
that happens to need three ordered steps gets a dag, and a large reconception that is one
obvious move does not.

**`applied` is the whole state machine.** The lowest version file with `applied = false`
is the pending work. There is no index file; the directory listing is the index, and the
`base` chain across filenames is the order. This makes out-of-order execution
unrepresentable rather than merely checked.

**`approach` is the field that earns the most and is easiest to get wrong.** Its job is
the reasoning that produced the plan — what is actually in the tree, what survives, what
gets recycled out of the thing being deleted, what order protects what. The rule that
keeps it from becoming a second spec: **only what is true during the move.** If a
sentence would still be true after the work lands, it belongs in the contract.

The clearest case for it is negative. A version summarised as "restore offline search"
reads like a feature; the approach explaining that search was already local and only the
notebook filter called the network turns it into two small changes. Without it, an agent
builds a sync layer nobody asked for.

### 5.4 Change types

`project_type` is replaced by *change* type, and in v3 it is **descriptive rather than
structural**:

| kind | version | the line |
|---|---|---|
| `spec` | `1.0` | the project's first contract |
| `re-spec` | **MAJOR** | something is deleted or replaced |
| `quick_fix` | **MINOR** | purely additive or corrective |

**Two levels, not three.** `MAJOR.MINOR` is sufficient. An earlier draft invented a PATCH
level for `quick_fix` and thereby invented three call sites of breakage.

Nothing branches on the kind. It does not decide which fields a version file carries, it
is not stored anywhere, and no code enforces it. It is a word people use to describe a
change, and its one real consequence — a removal bumps major — is a rule a human applies
while numbering the file.

#### The two layers

The working sequence is `spec` → `re-spec` → plan, and the two halves are different kinds
of work at different altitudes:

| | the contract edit | the version file |
|---|---|---|
| answers | *what* and *why* | *how* |
| concerns | requirements, architecture, design | implementation, re-use, recycling, order |
| method | describe the updated thing, lean on the language already there | read the actual codebase and decide what survives |

**Neither layer is reliably the hard one.** A contract edit is hard when the domain
genuinely is; plenty of business work is not, at that altitude. A plan is hard when the
code is a mess, which is often. Either can be trivial, either can be the whole job. The
design encodes no ranking because there isn't one.

They can also collapse together — a change where *what* and *how* are one sentence — or
pull far apart: a clean, obvious contract edit landing in a codebase where nothing about
the migration is obvious. The consequence is that **effort is assessed per change, not
assigned per layer.**

**A plan is authored and reviewed, not extracted.** It carries knowledge neither contract
version holds: that implementing B can reuse A's parser while deleting the rest of A is
an implementation judgment, and no diff of the two contracts contains it. flw drafts a
plan; the human reads and edits it before anything runs. Treating the draft as final is
how a re-spec becomes a demolition nobody sanctioned.

### 5.5 Deliberately not built

Three mechanisms were designed in detail, partly built, and cut. Recorded because each
looked obviously correct and was not.

**An amendment engine.** The contract was to be edited only through a program taking a
keyed operation payload, so that every edit was byte-preserving and every version's kind
and impact were derived from the operations rather than declared. It worked. It was cut
because ordinary text editing is byte-preserving *by construction* — the engine's headline
justification was written against a different alternative, an LLM re-emitting the whole
file, and did not survive contact with a plain string replacement. Worse, whole-entry
replacement created a corruption class that editing does not have: it discarded the
comments an author wrote beside a component.

**A computed diff, and the record built on it.** With the engine gone, kind and impact
could still be derived by diffing the contract before and after. This is sound — 88 lines,
no heuristics, and it does catch a capability deleted by accident. It was cut on use, not
on correctness: it needs a stored baseline copy of the contract to diff against, and the
mistakes it catches are the ones `git diff specs/current.toml` already shows in a format
people read fluently. Its remaining unique contribution was labelling a change and picking
a version number — machinery guarding a number.

**A ledger.** An append-only index of every version: kind, impact, summary, applied. Cut
once the diff went, because what remained was a queue with history as a side effect. The
queue is one boolean per version file, and the history was mostly redundant with a VCS.
Its most load-bearing field, `applied`, was also the one field in a
computed-and-append-only file that was authored and mutable — the integrity story never
covered it.

What survives from all three is the property they were built to protect, moved to where it
was always going to live: **a human reviews the version file before the work runs.** That
review was going to happen anyway. The machinery was insurance against an agent
misdescribing its own change, and the cost of that going wrong is a version number.

---

## 6. Command surface

Five skills, down from seven.

| Skill | Job |
|---|---|
| `/flow:design` | author `design.md` — principles **and conventions** |
| `/flow:research` | repo reconnaissance → design.md proposals + a regenerable map |
| `/flow:spec` | author or amend the contract. Modes: `init` (incl. consolidation) / `respec` / `delta` / `quick_fix` |
| `/flow:execute` | walk the delta's dag, run the gates, commit per phase |
| `/flow:review` | config-driven assessment — absorbs validate's perspectives |

**Four shipped, not five.** `design` folded into `research`, which writes
`.flw/extensions/*.md` rather than a `design.md`; `flw scout` is a command, not a skill,
because ranking a repo is deterministic and needs no judgment. §1.1.

### 6.1 Deleted commands

- **`/flow:scaffold`** — its projection depended on `interface` and the language
  registry, both deleted. Provisioning survives as execute's phase zero: run the
  project's declared setup commands. `design.md`'s *"scaffold provisions from scratch"*
  principle is preserved; only the separate unit dies.
- **`/flow:validate`** — its lane overlapped execute's regression gate, and it was
  hardcoded to two agents while review was config-driven. It dissolves in two directions:
  `design.md` `check:` directives and `final_state.removed` checks **are just declared
  commands** and join the gate; coverage and test-quality assessment become reviewer
  perspectives in a config.

  **A review perspective may run probes.** This has to be said explicitly or the
  adversarial lane decays silently: `validator-smoke` *executed* things — malformed
  input, boundary values, idempotency re-runs — and "reviewer perspective" otherwise
  reads as opinion-only. Reviewers already fire targeted probes in v2; v3 keeps that and
  a config may declare an adversarial perspective whose whole job is probing. What does
  not survive is the fixed two-agent dispatch.
- **`/flow:consolidate`** — becomes a discovery step inside `init`, plus a documented
  section explaining what consolidation is and when a project needs it. The one-time
  v1→v2 migration it existed for does not recur.

### 6.2 One gate, one place

`check_design.py` is deleted entirely. Its allow-list, its Python-only `build_argv`, and
its venv gate all disappear, and the shipped Rust bug disappears with them. Every check —
regressions, design principles, removal verification — is a declared command in
`success_criteria.gates` or on a `removed` entry, run by execute through the project's
declared runner.

The allow-list was never a security boundary: `check_design`'s own docstring admits
`python -m` and `uv run` execute arbitrary code. It cost generality and bought nothing
that a user-reviewed spec does not already provide.

---

## 7. Configuration

One file, one merge order, extending the mechanism v2 already has
(`~/.flow/config.toml` underlay → project overlay, fail-closed on defect).

```toml

[paths]
contract = "specs/current.toml"
reports  = "no-commit/flow/"         # e.g. a workplace no-commit convention

[interview]
mode = "thrifty"                     # conversational | thrifty

[extensions]
spec = ".flow/extensions/spec.md"
```

**Machine-specific invocation is deliberately not a config table.** An earlier draft had
a `[commands]` block (`test = "pytest -q"`, `setup = [...]`) as the replacement for the
language registry. It is the wrong level: it duplicates what the contract's gates already
say, and it creates a precedence question nobody wants to answer — does the committed
contract or the local config win when they disagree?

The contract's `success_criteria.gates` carry the commands, because that is what a gate
*is*. Where a machine genuinely needs a different invocation, that belongs in a per-repo
or per-workplace **extension** (`.flow/extensions/*.md`) — prose the skill reads, in the
repo, next to everything else. One mechanism, already needed for other reasons.

What replaces the language registry is not another table but the **contract's gates**,
authored by interview. The registry's key was always wrong: `pytest` is not a fact about
Python, it is a fact about *this project* — which might use unittest, or pytest behind a
wrapper, or a Makefile target. Two repos in one company routinely disagree.

**Built-in profiles survive as interview seeds, not authorities.** On `init`, flow may
propose *"looks like Python — test `pytest -q`, setup `uv venv .venv`?"* and the user
confirms or edits. Inference becomes a proposal the user locks in, which is flow's
pattern everywhere else, and it preserves the from-an-empty-directory provisioning
`design.md` requires.

**VCS: flow is not prescriptive, and builds no profile.** An earlier draft added a
`[vcs]` table for `git`/`hg`/`sl`/`arc`, reversing the research note's own conclusion
(*"a VCS abstraction layer is ceremony for approximately zero real users"*) on an assumed
fact about a workplace. The note was right and the reversal was not earned.

The real fix is smaller: **flow stops needing to know.** It does not commit, stage, or
tag — `/flow:execute` proposes commits and the human or their agent makes them, in
whatever VCS the repo uses. `git` remains in exactly one place, flow's *own* distribution
(§8), which is flow's repository and flow's choice — unrelated to what a user's project
uses.

**Project root** stops being `git rev-parse --show-toplevel` unconditionally: resolve
upward from cwd to the nearest `specs/` or `.flow/`. That is the entire monorepo story —
users split by service themselves; flow only has to stop forcing repo-root resolution —
and it is also what makes the VCS question moot, since the resolution no longer runs
through a VCS command.

**Extensions live in the repo they belong to** (`.flow/extensions/`, gitignored or not).
That is deliberate: storing them centrally would require mapping extension → repo by some
key, and repo names are neither stable nor unique. In-repo needs no mapping at all.

---

## 8. The CLI

`flow` is the distribution mechanism and the reason the adapter split is real rather
than a per-machine porting chore.

### 8.1 Surface

```
flow install <host>...      symlink skills; offer the ambient block
flow uninstall <host>...    exact reverse, tag-scoped
flow doctor                 verify: links resolve, overrides, orphans
flow add <path>             register a local bundle
flow list | flow remove <name>
flow update                 fetch upstream, then doctor
flow version                git describe --always --dirty
```

### 8.2 Hard constraints

- **Zero dependencies, by construction.** The installer cannot depend on a package
  manager it exists to stop assuming. Stdlib-only Python behind a POSIX shim symlinked
  to `~/.local/bin/flow`. The one hard requirement is **Python 3.11+** (`tomllib`),
  stated explicitly rather than assumed.
- **Dry-run before touching agent config.** With hooks gone (§9.3) the only file `install`
  may edit is the user's `CLAUDE.md` / `AGENTS.md`, and only for the opt-in ambient block.
  It never touches `settings.json`, `permissions`, or any host's hook configuration. Show
  the diff, ask; `--yes` to skip.
- **Uninstall must be exact**, or the feature is worse than manual. Tag the ambient block
  and strip by tag; symlinks are removed by target. flw's `SETUP.md` and
  `justdoit_smoketest.py` both already implement the tagged merge/strip pattern
  correctly — that logic survives its subject and becomes the ambient-block installer.
- **Git is the version.** No `bump_version.py`, no marketplace, no plugin manifest, no
  four-location bump with a drift detector. `flow version` shells out to `git describe`.
  `schema_version` is unrelated and stays — that is a contract version.

### 8.3 Distribution: symlink only

An earlier draft split this — symlink the shared assets, *generate* per-host skill copies
with a source hash so `doctor` could detect staleness. The §9.0 research removed the need:
skills are standard `SKILL.md` folders; Claude Code **documents** symlink support with
cross-location deduplication; `~/.agents/skills/` covers Codex and OpenCode, and OpenCode
also reads `~/.claude/skills/`. Two symlink targets serve three hosts:

```
~/.claude/skills/flow-spec   →  ~/.agentic/flow/core/skills/spec/     # CC + OpenCode
~/.agents/skills/flow-spec   →  ~/.agentic/flow/core/skills/spec/     # Codex + OpenCode
```

`scripts/` is part of the skill standard and the symlink resolves to a real directory, so
a skill reaching its sibling scripts by relative path works on every host. One core,
edited once, live everywhere — **no sync step, no staleness, no source hashes, no
generated-file drift.** The machinery for detecting stale copies disappears along with
the copies themselves.

**Generation is not built at all** — not as a fallback, not behind a flag. Two reasons it
is not needed:

- **Write the superset of frontmatter once.** The standard requires `name` and
  `description`; each host adds its own optional keys (CC's `context: fork`,
  `disable-model-invocation`, `allowed-tools`; OpenCode's `agent`, `model`, `subtask`).
  Unknown keys are optional-by-spec and expected to be ignored, so one `SKILL.md` can
  carry every field any host wants. A few extra keys break nothing.
- **Symlinking is basic, and belongs to the user's environment.** `flow install` creates
  the links and `flow doctor` verifies them, but neither is load-bearing machinery — an
  agent and a human can link a directory and address it however their host prefers. flow
  suggests the mechanism and checks the result; it does not own it.

That also settles where host-specific *dispatch* lives, which frontmatter tolerance does
not solve on its own: **nowhere special.** A skill states the intent — "review these
files from N perspectives, in parallel if the host can" — and the host's own agent
resolves it. flow does not ship three invocation syntaxes for one instruction, and does
not fork a procedure to carry them.

### 8.4 Update

`flow update` is `git pull --ff-only` in `~/.agentic/flow/`, then `doctor`. There is no
sync step: symlinks (§8.3) mean a successful pull is live immediately on every host.
Because user content lives outside the clone (§4), the common case has **zero conflict
surface**.

Rebase remains supported for the case where core genuinely is patched locally, under two
invariants:

- **Never leave the install unusable.** On conflict, auto `rebase --abort` and report
  which files diverged. The failure to avoid is a half-rebased tree where the skills that
  would help fix it are themselves full of conflict markers.
- **`update` implies `doctor`.** A pull can land a new skill, retire an old one, or
  break an override; the link graph should be re-verified while the user is still
  looking at the output.

Advised workflow: commit local changes, never push. But when a rebase *does* conflict,
the useful message is not "resolve these" — it is *"you have patched
`core/skills/spec.md`; that belongs in a bundle or `.flow/extensions/spec.md`, and then
this stops happening."* Layering is the permanent fix; rebase is the transition path.

---

## 9. Hosts and adapters

**Targets for v1: Claude Code, codex, opencode.** Amp and others later, and only if the
adapter interface earns it.

### 9.0 Research findings — the ground is far friendlier than assumed

Verified against each host's own documentation (August 2026) — Claude Code, Codex and
OpenCode skill/hook references, plus the `agentskills.io` specification. Two assumptions
in earlier drafts were
**wrong**, and both wrong in flow's favour.

**Agent Skills is a real, adopted open standard.** Originated at Anthropic, released as
an open format, published at `agentskills.io`, and implemented by 40+ tools including
all three targets. A skill is a folder:

```
my-skill/
├── SKILL.md      # required: `name` + `description` frontmatter, then instructions
├── scripts/      # optional: executable code          ← the standard has this
├── references/   # optional
└── assets/       # optional
```

Progressive disclosure: hosts load `name` + `description` at startup and the body only
when the skill is invoked or judged relevant.

**Skill discovery paths, per host:**

| Host | Global | Project |
|---|---|---|
| Claude Code | `~/.claude/skills/<n>/SKILL.md` | `.claude/skills/<n>/SKILL.md` |
| Codex | `$HOME/.agents/skills/`, then `/etc/codex/skills/` | `$CWD/.agents/skills/`, `$CWD/../.agents/skills/`, `$REPO_ROOT/.agents/skills/` |
| OpenCode | `~/.config/opencode/skills/`, **`~/.claude/skills/`**, **`~/.agents/skills/`** | `.opencode/skills/`, `.claude/skills/`, `.agents/skills/` |

Codex's list is from its own docs and supersedes the `~/.codex/skills/` path reported by
secondary sources — that path is not in the official scan order. Note Codex scans
`$CWD/../.agents/skills` explicitly "for nested repositories", which corroborates §7's
resolve-upward-from-cwd decision from a second direction.

Two overlaps do most of the work: **`~/.agents/skills/` is read by both Codex and
OpenCode**, and **OpenCode also reads `~/.claude/skills/`**. Two symlink targets cover
three hosts.

**Two of three hosts document symlink support explicitly.** Claude Code: *"A
`<skill-name>` entry … can be a symlink to a directory elsewhere on disk. Claude Code
follows the symlink and reads `SKILL.md` from the target directory, and if the same target
is reachable from more than one location, Claude Code loads the skill once"* —
deduplication included. Codex: *"Codex supports symlinked skill folders and follows the
symlink target when scanning these locations."* This is exactly the mechanism §8.3 needs,
blessed rather than tolerated. OpenCode's docs do not address symlinks either way, which
makes it the one to check on first install.

**Also**: Claude Code has *merged custom commands into skills* —
`.claude/commands/deploy.md` and `.claude/skills/deploy/SKILL.md` both produce `/deploy`.
flow's `commands/*.md` are the legacy form; `SKILL.md` is the current one.

**Both other hosts have hooks.** This was the assumption most worth correcting:

- **Codex** — `~/.codex/hooks.json` or a `[hooks]` table in `config.toml`, project-level
  equivalents, and plugin-bundled `hooks/hooks.json`. Events: `PreToolUse`,
  `PermissionRequest`, `PostToolUse`, `PreCompact`, `PostCompact`, `UserPromptSubmit`,
  `SubagentStart`, `SubagentStop`, `Stop`, `SessionStart`, `SessionEnd`. A `PreToolUse`
  hook blocks by returning `"permissionDecision": "deny"` — **the same envelope key flow
  already emits** — or by exiting 2 with stderr. `matcher` is a regex over `tool_name`.
  Limitation: **`PreToolUse` fires for Bash only**; `apply_patch`, Edit/Write/Read, web
  fetch and MCP calls do not trigger it.
- **OpenCode** — JS/TS plugins in `~/.config/opencode/plugins/` or `.opencode/plugins/`,
  with `tool.execute.before` / `tool.execute.after` and `permission.asked` /
  `permission.replied`. `tool.execute.before` can prevent or modify execution — a real
  permission gate, reached through a different language.

The hook findings turned out to be **moot** — v3 ships no hooks at all (§9.3). They are
recorded because they were researched, because they prove the option was available and
declined rather than missed, and because a future bundle may want them.

**Subagents exist on all three**: Codex has `SubagentStart`/`SubagentStop` lifecycle
events; OpenCode commands take `subtask: true` plus `agent` and `model`; Claude Code has
`context: fork` in skill frontmatter.

### 9.1 What an adapter actually has to carry

Given the above, the adapter is thin — a path map plus a small frontmatter and dispatch
delta, not a translation layer:

| Concern | Portable | Host-specific |
|---|---|---|
| skill body | ✅ the whole procedure | — |
| frontmatter | `name`, `description` | CC: `context: fork`, `disable-model-invocation`, `when_to_use`, `allowed-tools`, `argument-hint`. OpenCode commands: `agent`, `model`, `subtask` |
| bundled scripts | ✅ `scripts/` is in the standard | — |
| subagent dispatch | the *intent* ("run these reviewers in parallel") | the invocation |
| ambient context | the snippet | `CLAUDE.md` vs `AGENTS.md` |

Unknown frontmatter keys appear to be ignored rather than rejected — the standard defines
optional fields and expects agent-specific extensions — so a **single `SKILL.md` carrying
CC's extras may install unmodified everywhere**. That would make installation pure
symlink with zero generation. It is the single highest-value thing to verify on first
install, because it decides §8.3.

A skill still declares what it needs and the adapter declares what the host provides, so
`flow install` can warn on a genuine gap (*"Codex: PreToolUse is Bash-only — file-tool
checks will not run"*). Honest degradation, but the gaps are now narrow and known rather
than assumed.

### 9.2 Setup is human+agent, verified — not claimed

flow does not pretend to fully automate a host it does not control. The flow:

1. `flow install <host>` does what it can: symlink the skills into that host's
   discovery path, and offer the ambient block. No hooks, no `settings.json`.
2. The adapter ships as a **documented suggestion** — what to configure, where, and what
   to expect — not a guaranteed automation.
3. The human, with their agent, completes host-specific setup and **verifies it works**.
4. `flow doctor --host <name>` confirms the result, and from then on flow owns
   symlinking, update and centralisation.

This is the honest division: flow is excellent at centralising and keeping things
current; it cannot promise correctness inside a third-party tool's configuration model.

**There is a working prototype to copy from.** flw's `SETUP.md` is written as a prompt
*for an agent to execute*, and it already gets the hard parts right: every step
idempotent ("detect the existing state and skip rather than duplicate"), explicit
no-clobber rules on the user's config ("never edit `permissions` or `hooks`" — a rule
v3 keeps by never going near them at all), merge-only-if-absent on shared keys, and a
closing smoke test. Each adapter's setup
document should be that shape. The one thing to add is the machine-checkable finish:
flw ends with a human-read report, where v3 ends with `flow doctor` returning an exit
code.

### 9.3 v3 ships no hooks — the auto-approve layer is deleted

The hooks were valuable for a stretch, in a period when hosts had blunt
all-or-nothing permission models and an unattended run meant a human clicking *Yes*.
**That problem is now solved natively, and by better mechanisms than flow's.** Codex
ships an LLM-based command classifier; Claude Code has permission modes including an
accept-edits mode; OpenCode has its own permission configuration. These are not the blunt
prefix matchers flow's hook was built to improve on — a classifier reasons about a command
the way flow's parser tried to and does not fail open on a shell construct it cannot parse.
flow reimplementing this is duplicated effort against a moving target, in the one place
where being wrong is expensive.

flw is the field evidence: it has run **hookless for months**, deliberately —
*"flw ships no hooks; every command runs under normal permission prompts"* — and the
loss never featured in its review.

What deletes with it:

| | Lines |
|---|---|
| `hooks/pre_tool_use/*` + `hooks/post_tool_use/*` | 3,252 |
| their tests | 3,960 |
| `justdoit.py`, `justdoit_smoketest.py`, `justdoit.md`, the smoketest runbook | 579 |
| `shell-hygiene.md` | 107 |
| `hooks.json`, `mcp_allowlist.json`, `config.py`'s `venv_policy` + `mode` | — |
| the "Shell hygiene" preamble in **9 files**, the `--justdoit` block in **4** | ~150 |
| **Total** | **≈8,050** |

**The style tax is the bigger win.** `shell-hygiene.md` opens *"writing Bash that flow
auto-approves"* — its rules (never a `subprocess` heredoc, no explicit deletes, write
interpreter paths literally, never `$VAR` in command position) exist **only** to satisfy
the scanner. v2's skills are contorted to please a parser, and nine files carry the
contortion. Deleting the scanner lets every skill write the obvious command. That is a
clarity gain, not merely a deletion.

It also resolves the largest robustness question in the plan: a fail-open denylist
parsing a Turing-complete language, with a CRITICAL bypass found in it days ago, is not
"robust good stuff". It was going to ship three times or none (§9.0). None.

**Consequences through the design:**

- `flow install` no longer edits `settings.json`. The only file it may touch is the
  ambient `CLAUDE.md` / `AGENTS.md` block (§13) — opt-in and tagged.
- `flow hooks install|remove` is gone from the CLI (§8.1).
- `.flow/config.toml` loses `venv_policy` and `mode` — its entire v2 content.
- The `--justdoit` unattended mode disappears. Unattended runs are now the host's
  permission configuration, which is where they belong.
- `design.md`'s denial-layer principle and its declaration-based successor
  (`plans/denial-layer-declaration.md`) are both retired.
- Downstream, the user's global `CLAUDE.md` section on the flow auto-approve hook
  becomes obsolete and should be removed on migration.

**`post_tool_use` goes too, and not merely as collateral.** It is a different feature —
format-on-edit, lint-on-edit, spec-validate-on-edit — and it survives none of the same
reasoning. It goes because of a positioning choice: **v3 is a prescriptive, opinionated,
expandable *workflow*, not a layer of hooks.** Formatting on every keystroke is the
editor's job or a gate's job; flow's job is the contract and the loop around it. Keeping
one hook would also mean keeping the entire hook-installation surface — settings files
across three hosts, tagged merge/strip, exact uninstall — for a convenience that
duplicates what a declared gate already does at a phase boundary.

That drops flow's runtime footprint in a host to exactly one thing: **skills.** No
background process, no config injection, no interception. A host either finds the skills
or it does not, which is the whole of §9.2's setup story and why it can be verified in a
line.

If a hook is ever wanted again, §9.0 records that all three hosts support one and the
research is done — it returns as an **optional bundle**, never as core. "Not yet" rather
than "never": the mechanism is understood, the appetite is not there.

### 9.4 What remains unverified

The research (§9.0) answers discovery paths, frontmatter, hooks and subagents for all
three hosts. Three things can only be settled by installing:

- **Does a single `SKILL.md` carrying the superset of every host's frontmatter install
  cleanly on all three?** Expected yes — the optional keys are optional by spec. Cheapest
  test, and the one §8.3 leans on.
- **Is a structured ask-the-user primitive available on Codex and OpenCode?** Determines
  whether thrifty mode is merely preferable there or the only workable interview mode.
- ~~**Does a skill reliably resolve its own directory on every host**, so it can reach
  `../../scripts/` through the symlink?~~ **Answered 2026-08-22, by probe skill installed
  into a real Claude Code.** The host states the skill's base directory outright. But the
  answer splits: bash resolves `../../shared/context.md` through the install symlink
  correctly, while the agent's file-reading tool collapses `..` lexically before walking
  and lands in a directory that does not exist. So relative paths work *inside* a skill
  folder (`references/*.md`) and not *outside* it. Reaching shared material needs an
  absolute path, which is what `~/.flw/root` is for — the locate step is load-bearing,
  not scaffolding.
- **Does OpenCode follow symlinked skill folders?** Claude Code and Codex both document
  that they do; OpenCode's docs are silent, and it is the only host where §8.3's
  mechanism is unconfirmed.

Each is a one-hour experiment on a real install, not a research question.

---

## 10. Bundles and extensions

**One shape for everything.** flow's core is simply the first bundle; a user bundle has
the identical layout. There is no plugin API, no manifest format, no registration
lifecycle, no first-class/second-class split. An agent asked to add a skill copies the
shape of an existing one and it works — which is the whole reason "humans and agents can
figure this out" is true.

```
bundles/<name>/
  skills/*.md      scripts/*.py      schemas/*.json
```

Two tiers, by weight:

- **Augment an existing skill** — `.flow/extensions/spec.md`, prose injected into that
  skill's context. `design.md` already proves the pattern.
- **Add a new skill** — a full bundle, discovered and installed like core's.

**Resolution**: core → global bundles → project bundles, mirroring the config merge.

**Overrides are checksummed and reported.** A project bundle shadowing a core skill is
powerful and a debugging nightmare when implicit, so it must be declared, and `doctor`
reports every active override, every stale generated file, and every orphan left by a
removed bundle.

**Local paths only.** Remote fetch means trust, verification and update semantics — a
materially larger surface for no v1 benefit.

A deliberate refusal: extensions stay **prose**, not a code plugin API. A plugin API is
where lean tools become frameworks.

---

## 11. Repo context — `/flow:research`

The problem is concrete: agents recreate methods and classes that already exist because
they never researched the repo.

It surfaces at two moments. At **spec time** it prevents declaring a component that
already exists under another name. At **delta time** it is load-bearing in a different
way: the delta's job includes deciding what to reuse, recycle and tear out (§5.4), and
none of that is answerable without knowing what is actually there — a delta authored
blind will delete things worth keeping and rebuild things that already work.

Which of the two matters more depends entirely on the change in front of you.

The trap is equally concrete: a notes file rots, and `design.md` forbids competing
sources of truth at execution time (*"execution follows exactly two things: design.md and
the current spec"*). So the output splits by **lifetime**:

- **Conventions and rules** — "helpers live in `lib/`", "all IO goes through the adapter
  layer", "never raise bare Exception". Durable, and they are *rules*. They go into
  **`design.md`**, which already exists, is already injected into spec and every
  reviewer, and is already user-locked. No new artifact, no competing authority.
- **The map** — modules, entry points, call relationships. Volatile, rots fast.
  **Regenerated, never trusted.** Timestamped, stale-by-default, and phrased as a
  pointer-list ("look at these") rather than an assertion ("this does X").

`/flow:research` runs on `init` and on demand. `/flow:spec` consumes both during the
interview.

**This is the mechanism for the senior-engineer posture.** "Follow existing conventions
deeply" cannot be an instruction — every agent already believes it is doing that. It
becomes real when spec-time has (i) the conventions in context as rules and (ii) a
mechanical duplicate check: before a new artifact is declared, grep for the symbol or
name it proposes and surface hits in the interview. Cheap, and it is exactly the failure
being described.

---

## 12. Thrifty mode and the war on restatement

### 12.1 Thrifty mode

Two interview modes, selectable by `--thrifty` or `[interview] mode`:

- **Conversational** (today's) — one question at a time, per-section lock. Right when the
  shape is genuinely undecided.
- **Thrifty** — the skill writes the draft to disk with inline `# TODO(flow):` markers
  where a decision is needed, prints a short index of what needs attention, and stops.
  The user edits the file directly. The skill re-reads, validates, and asks only about
  what is still unresolved.

Thrifty turns a twenty-turn dialogue into one or two, and it puts the decisions in the
medium that keeps them — the file — rather than in chat scrollback. It suits an
experienced user who knows what they want, which is most amendments.

### 12.2 Reducing restatement generally

flow's own prose is a restatement offender. Measured in v2: `commands/*.md` is 2098
lines, and the *same* "Shell hygiene", "Plugin root", "Project root" and `--justdoit`
blocks appear in six or seven files each — roughly 150 lines of pure duplication.
`core/shared/*.md` fragments, included once and referenced, remove it.

Applied across the board:

- skills reference the schema; they never restate it
- reports collapse from four `.flow/` directories to one, keyed by run
- `--justdoit` and `mode = "trusted"` were two mechanisms for one behaviour (v2's own
  `floor.py`: *"now one identical floor"*). Both delete outright with the auto-approve
  layer (§9.3); no config key survives.
- the contract stops carrying anything derivable from itself

---

## 13. Ambient context — `CLAUDE.md` / `AGENTS.md`

flow ships a snippet describing the system, the CLI, when to reach for it, and the
senior-engineer posture, for a user's top-level agent instructions. This is what makes an
agent reach for flow instead of freelancing — the piece that operates *outside* any flow
skill.

Installed by `flow install` as an **opt-in, tagged block**, so `flow uninstall` removes it
exactly and never disturbs the surrounding file. Same discipline as hooks: this is a
user's global instruction file and flow is a guest in it. flw's `SETUP.md` already sets
the right posture here — *"Show the user … and offer to merge … Never edit
`~/.claude/CLAUDE.md` without the user's say-so"* — and v3 keeps that, adding only the
tagging that makes removal exact.

**Start from flw's `CLAUDE.sample.md`, don't rewrite it.** It already carries token
discipline, agent-fan-out posture, a command quick-reference, when-stuck rules, the
decision protocol and the security list — most of the senior-engineer posture, already
tuned by use.

One thing it surfaces that the design must handle: its **solo-first** section
("default to doing the work in the main session… each subagent is a fresh context =
multiplied input cost") directly reverses a teams-by-default posture, and flw's SETUP
flags that as a conflict for the human to resolve by hand. The reason is environmental —
the two machines have different cost constraints — not a change of mind. So the ambient snippet cannot be one
global text — it would be wrong on one machine or the other. But that does not justify
building **profile machinery** for two machines belonging to one person: the snippet is a
file, and the two machines can simply hold different files. flow ships the default and
`flow install` offers it; a machine that wants the cost-capped variant keeps its own copy
or a bundle. No `--profile` flag, no named-profile resolution, no third concept.

---

## 14. Deleted, with rationale

| Deleted | Because |
|---|---|
| `project_type` (MLE/DS/ENG/CHANGE) | mechanically inert in v2; replaced by change type. The research note proposed keeping it as an optional free-text `domain` hint for agent probe-planning; that consumer died with `/flow:validate`, so it is dropped outright |
| `success_criteria` MLE/DS branches | never read by any code; the clamp made MLE wrong |
| `description` | the first version file's `summary` already carries the one-liner |
| `interface` | read in one place, never re-checked; a seed, not a contract |
| `[[modules]]` in the contract | work units move to deltas; contract becomes declarative |
| language registry as authority | the key was wrong — commands are a project property |
| `/flow:scaffold` | its projection depended on both deletions above |
| `/flow:validate` | lane overlapped execute's gate; not config-driven; sandbox reality |
| `check_design.py` | checks are just declared commands; removes a shipped Rust bug |
| `/flow:consolidate` | a mode of `init` plus a docs section |
| plugin + marketplace manifests | flow is a CLI with adapters, not a plugin |
| `bump_version.py` | git is the version |
| the runner allow-list | never a security boundary; cost generality, bought nothing |
| **the entire auto-approve hook layer** | solved natively by every host now; ~8,050 lines incl. tests (§9.3) |
| `post_tool_use` (format/lint/validate on edit) | a different feature, deleted on positioning: flow is a workflow, not a hook layer (§9.3) |
| `justdoit.py` + smoketest + `--justdoit` | existed only to relax the auto-approve floor |
| `shell-hygiene.md` + its preamble in 9 files | existed only to keep Bash scanner-friendly |
| `config.toml`'s `venv_policy` + `mode` | both were auto-approve knobs |
| **the `flw` fork itself** | v3 subsumes it; a maintained fork is a permanent drift tax (§2.3) |

### 14.1 Retiring flw

flw is retired, not archived-and-forgotten — its deployment on the second machine is live and
further upgraded beyond the flow-lite snapshot, so retirement has prerequisites:

1. **Diff the deployed version against the flow-lite snapshot first.** Those upgrades are
   field experience under real constraints and are the highest-value input still
   outstanding. Anything there that v3 lacks is a requirement, not a nice-to-have.
2. **Everything flw varied must be expressible as config or a bundle** — solo-first
   posture, cost-capped profile, its own namespace. Its biggest variation, shipping
   hookless, is now simply what v3 does. If any of the rest still needs a fork, §7 and
   §10 are incomplete.
3. **The statusline does not come along.** flw's cost-tracking statusline is a personal,
   host-specific artifact. It stays where it is; v3 has no opinion about it.
4. Then the second machine runs `flow install claude-code`, keeps its own ambient snippet,
   and the fork goes away.

---

## 15. Non-goals

Generalising these trades the identity for portability:

- **The command set and its lanes.** One job per unit is the product.
- **Interview over inference.** Cheaper to skip; skipping it is what flow prevents.
- **The contract and version files.** Already fully language-agnostic — their
  *mechanism* carries forward untouched. Its *vocabulary* does not; see §5.5.
- **A code plugin API.** Prose extensions, deliberately.
- **Remote bundles.** Local only.
- **Monorepo machinery.** Users split by service; flow only stops forcing repo-root
  resolution.
- **`.flow/` as the project state directory name.** Configurable *paths* within it, yes;
  a configurable name buys nothing.
- **Permission and approval policy.** Deleted, not generalised (§9.3). Every host now
  ships its own; flow reimplementing it duplicated effort against a moving target. The
  `plans/denial-layer-declaration.md` line of work is retired with it — a
  declaration-based floor is a better denial layer, and v3 wants none.

---

## 16. Sequencing

**v3 is built forward. There is no migration, no compatibility obligation, and no
interregnum to manage** — v2 is discarded, not transitioned. That removes the two hardest
scheduling problems a rewrite normally has: nothing must keep working while the
replacement is built, and no deletion has to be staged behind its successor.

It also settles a question the design would otherwise have to answer: whether building v3
is itself governed by flow's contract. It is not. `specs/current.toml` declares the hooks,
`justdoit.py`, `scaffold.py` and `check_design.py` under `final_state.present`, so
deleting them would be a contract change under v2's own rules — but v2's contract is being
discarded along with v2. v3 writes its own contract at `init`, describing what v3 is. That
is the first thing built under flow's rules, not the last thing done under v2's.

0. **Diff the deployed flw against the flow-lite snapshot** (§14.1). Cheap, and it is the
   only source of field experience v3 does not already have. Anything it upgraded is a
   requirement.
1. **Deletions** — the auto-approve layer and everything that served it (§9.3), scaffold,
   validate, check_design, the language registry, project types, `interface`,
   `description`, bump machinery. First because the rest is smaller afterward, and
   because it frees every skill from `shell-hygiene`'s constraints before the prose
   sweep rewrites them.
2. **Contract v3** — MECE, change types, patch slot, work-units-in-deltas — and the
   amendment engine's v3 vocabulary (§5.5), which is a prerequisite, not a follow-on.
3. **Skills + CLI** — the five procedures as `SKILL.md` bundles, and
   install/doctor/update against Claude Code.
4. **The other hosts** — Codex and OpenCode, per §9.0, verifying §9.4 on real installs.
5. **`/flow:research`** — delivers the senior-engineer posture (§11).
6. **Thrifty mode and the restatement sweep** — last, once the prose has stopped moving.

**`design.md` is rewritten as part of step 1**, not left to drift: the denial-layer
principle, both scaffold principles, and the `check: ruff check flow-plugin/hooks
flow-plugin/scripts` directive all point at things step 1 deletes.

---

## 17. Minimising the footprint

The goal is not a smaller number. It is **only robust, load-bearing things** — nothing
shaky, nothing flaky, nothing that exists because it once seemed like a good idea. Where
clarity costs lines, spend them; where lines buy nothing, delete them.

### 17.1 Where the weight is today

Each row counted once; the §9.3 total (~8,050) is these hook rows plus the justdoit
scripts and the prose that served them, not an additional sum.

| Area | Lines | Disposition |
|---|---|---|
| tests — hook-related | 3,960 | deleted with their subject (§9.3) |
| tests — everything else | 3,882 | shrinks with what it tests; regression tests stay |
| vendored tomlkit | 6,187 | load-bearing; keep, never edit |
| prose (commands, agents, README, guides) | 5,623 | largest *surviving* area — heavy restatement |
| hooks runtime | 3,252 | **all deleted** (§9.3) |
| scripts — surviving | 1,747 | the amendment engine, validator, resolver |
| scripts — deleted with their features | 1,138 | scaffold, check_design, languages, bump_version |
| scripts — deleted with the hooks | 404 | `justdoit.py`, `justdoit_smoketest.py` (§9.3) |
| schemas | 1,344 | v1 spec + two validator-report schemas (423) die |

**Prose outweighs surviving code** — 5,623 lines against 1,747 of scripts. That is the
finding most likely to be overlooked, because prose feels free. It is not: flw's three CRITICALs were *all* prose
drift — a command referencing a deleted script, a hardcoded allow-list contradicting the
schema, a mislabelled namespace. Stale prose fails exactly like stale code, but nothing
type-checks it.

### 17.2 The five rules

**1. Delete, never deprecate.** No compat shims, no "legacy" branches, no fields kept
"just in case". v3 reads a v1/v2 spec exactly once — as *input to `init`* — and never as a
maintained format. One-way migration, not dual support.

**2. One mechanism per job.** Every duplicate found so far: two runner allow-lists (one
already drifted), four report directories, two report-naming schemes, the same "Plugin
root / Project root" preamble in seven command files. Each collapses to one. The largest
pair — `--justdoit` and `mode = "trusted"` reaching one identical floor — resolves by
deleting both (§9.3).

**3. No feature without a consumer.** `metric`/`threshold`/`baseline` were read by
nothing. `interface` was written once and never checked again. Before anything survives
into v3, name the code that reads it — and if the answer is "a human, maybe", it is prose,
not schema.

**4. Prose is footprint.** Shared fragments included once; skills point at schemas rather
than restating them. §9.3 already removes the worst offender — a "Shell hygiene" preamble
in nine files and a `--justdoit` block in four, none of which described the *work*.
Target: the skill set reads as five procedures, not five procedures wrapped in five
copies of the same preamble.

**5. Tests follow their subject.** Tests for deleted features are deleted with them. But
the regression tests for **real, reproduced bugs in surviving code are permanent** — the
vendored-import ordering, the `resolve_delta` bare-script crash, the CAS ordering. Those
encode expensive lessons and cost nothing to carry. (The shell-wrapper-bypass test goes
with its subject; its lesson — *verify via the invocation the caller actually uses* —
survives in the other three.)

### 17.3 Shaky things, named

"Robust good stuff only" means naming what is *not* robust rather than letting it ride:

- ~~**`--justdoit`'s teardown**~~ **— resolved by §9.3.** It depended on
  turn-structure behaviour no automated test could exercise; `justdoit_smoketest.py`
  (260 lines) existed solely because the thing was untestable, and was a *guided* test
  needing a human to drive it. With no auto-approve floor to relax, the flag, the lock,
  the Stop-hook teardown and the smoke harness all go, and nothing replaces them.
- ~~**The shell parser.**~~ **— resolved by §9.3.** 3,252 lines fail-open-parsing a
  Turing-complete language, with a CRITICAL bypass found in it days ago. It was the
  largest robustness question in the plan and the answer is deletion, not a rewrite:
  `design.md`'s own preferred successor — a declaration-based allowlist — is a better
  denial layer, and v3 wants no denial layer at all.
- **Stage auto-detection** in review: five heuristic signals with a "prefer the latest"
  tiebreak. Either the user says which stage, or it is inferred from the newest version
  type — which is a fact, not a guess.
- **Report-name collision counters** (`_1`, `_2`, …): machinery for a rare case. Version
  and timestamp are already unique.
- **`_best_effort_danger_scan`**: an approximate net under an approximate parser. Its
  existence is honest; its necessity is a symptom of the bullet above.

### 17.4 What is *not* cut

- **Vendored tomlkit** (6,187 lines). Byte-preserving amendment is flow's best property
  and `tomllib` cannot write. Load-bearing, kept, never edited locally.
- **The contract, and versioned records beside it.** The whole reason v3 reuses v2's core
  rather than starting from flw.
- **Regression tests for real bugs.** See rule 5.
- **Interview depth.** §3's principle bites here: as enforcement thins (§15's honest
  admission), the interview becomes the primary quality mechanism. `/flow:spec` gets
  *more* rigorous, not leaner. Thrifty mode reduces **turns and restatement, never
  scrutiny** — the questions asked are the same, the medium is a file instead of a
  conversation.
- **The judgment in a delta.** §5.4's work order is drafted by flow and finished by a
  human. Automating that away is the most tempting piece of over-formalisation in the
  whole design and the one that would do the most damage: a derived work order for a
  re-spec that reuses half of what it deletes would be confidently wrong, and wrong in a
  way that only surfaces after the demolition.
- **Rules where the honest answer is "it depends".** This design has repeatedly tried to
  harden contextual observations into laws — that deltas are derivable, that the
  quick_fix boundary is mechanical, that the lower layer is the harder one. Each was a
  real observation and a false rule. The tell is a sentence that would be more useful with
  *often* in it, written without one. §3's determinism principle is the general form; this
  is the specific failure mode it exists to catch.

### 17.5 The target

No line count is set as a goal — that invites the wrong optimisation. The measurable
targets are structural:

- every surviving field, script and schema has a named consumer
- no rule, list or preamble stated in more than one place
- nothing whose correctness cannot be tested ships without its approximate nature stated
- the five skills read as five procedures

flw reached 40% of flow's surface by deleting less than this plan does, and it was
*more* capable for its purpose. That is the evidence the direction is right.

---

## 18. Open questions

Updated 2026-08-22, after the build and the first real runs. Struck items are settled;
what settled them is named, so a reader can check rather than take it on trust.

### Answered

- ~~**Map format and refresh rule.**~~ There is no stored map. `flw scout` regenerates in
  under a second and its output is never written down — a published A/B test (N=438) found
  static repo overviews do not improve agent performance, and LLM-generated ones slightly
  hurt. Staleness was the entire risk and the answer was to keep no artifact.
- ~~**Does `init` on an existing codebase run research first?**~~ Yes, and it became its
  own skill. `flw-research` writes `.flw/config.toml` and `.flw/extensions/*.md`, never
  `specs/`.
- ~~**`flow doctor` exit semantics.**~~ As leaned: a broken link is an error, an override
  and an orphan are reported. An absent host is `·`, not a fault — it prints
  `not installed` and exits 0.
- ~~**Partial-delta semantics.**~~ Moot. Deltas are gone, `applied` is gone, and flw
  records no notion of done. Execute checks the tree before starting rather than consulting
  a flag.
- ~~**Does a skill resolve its own directory through the symlink?**~~ Split verdict, §9.4.
  Bash yes, the agent's file-reading tool no. Absolute paths from `~/.flw/root`.

### Still open

- **Does a large `modify` that reconceives without removing need its own signal?** (§5.4)
  Unchanged: the narrow middle is resolved by asking, and whether that stays comfortable is
  a question for use.
- **Where does model-selection guidance live?** *"Spec on Opus, then a fresh Sonnet session
  for execute"* is real operational advice and still lives nowhere.
- **Does a ranked structural scout escape the negative result that sank prose overviews?**
  The artifact type is untested rather than disproven, and no benchmark measures repository
  orientation independently of downstream task success. Validating it would mean building
  the evaluation.
- **Does `flw-execute` survive a cold reader on a version file it did not write?** It has
  run once, inside flw's own repository, by an agent with full context.

### Opened by building it

- **flw's own artifacts get mistaken for the user's.** `~/.flw` made every home directory
  look like a project root; a skills directory would have been read as evidence a host
  exists. Two instances, both fixed, and the class is worth watching: *when flw checks for
  something, it must check for something flw did not put there.*
- **No host but Claude Code has loaded the skills.** Codex and OpenCode support is designed
  and untested, and the symlink findings above are one host's behaviour.
- **The `[tests] yours` path has never been exercised.** Every check declared so far has
  been runnable. A sandbox where part of the suite cannot run — the case that motivated the
  design — remains hypothetical.
