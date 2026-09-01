---
name: flw-spec
description: Author or amend a project's flw contract — the versioned statement of what exists when the work is done, what a user can do with it, and how you will know it works. Use when starting a project, when requirements or architecture change, or when a correction needs recording. Interview-driven; nothing is inferred silently.
argument-hint: "[plan path] [--thrifty]"
---

# flw-spec — author or amend the contract

## Start here, silently

One command, no narration — do not announce it, do not report it, just run it and begin.
The user asked for the work, not for a description of you preparing to do it.

```sh
flw context flw-spec
```

It prints everything this skill opens with: the shared context, the project root it
resolved and where that came from, this repo's extensions from the outermost project root
inward, the note store listing for this project's category, and the contract's components
with the paths each one covers. Everything below assumes it.

**If the request names a repository, a directory or a file, pass it** —
`flw context flw-spec --root <that path>`. The rule and its reason are in the shared
context the command just printed; this is the only part of it the command cannot tell you,
because you have to call it first.

**Every extension it printed is part of your instructions from here on.**

**If `flw` is not on PATH:** run it out of the checkout — `<interpreter> "$FLW/cli/flw.py"
context flw-spec` — where `$FLW` is the absolute path in `${FLW_HOME:-$HOME/.flw}/root`.
It must be an absolute path: a skill folder is installed as a symlink, and the file-reading
tool collapses `..` lexically before the filesystem resolves it, landing somewhere that
does not exist. If that pointer is missing you may be inside flw's own checkout, so walk up
from the project root for a directory holding both `core/skills/` and `cli/flw.py`.
Nothing → stop and say to run `flw install`.

## Lane

This skill decides **what to build** and writes it down. It writes no implementation code
and runs no tests — that is `flw-execute`.

## Two modes

| | when |
|---|---|
| **first contract** | `specs/current.toml` does not exist |
| **amend** | it does |

If the request is "set up flw", ask which they mean before doing either — installing the
skills into a host is `flw install` and is not this skill's job.

**Project root, when there is no project yet.** The usual rule finds the nearest directory
holding `specs/` or `.flw/`, and a new project has neither. Use `$PWD`, say which
directory you are about to create `specs/` in, and get a yes before writing. Do not guess
upward.

The script under `core/scripts/` takes explicit file and schema paths and walks nothing,
so reaching for it instead of `flw validate` produces a usage error rather than a
validation.

---

## First contract

1. **The plan goes on disk first.** No contract without one — but there are three ways in,
   and only the first is common:
   - **A file** — read it.
   - **In conversation** — ask for a kebab-case name, write `<root>/plans/<name>.md`, read
     it back, require an explicit yes.
   - **Nothing yet** — interview one into existence *before* touching the contract. What
     is being built, for whom, what would make it a failure. Keep it short; it is a plan,
     not a design document. Then write it and read it back as above.

   **Say which the contract is about.** For a directory that already has code, "what is
   true when the work is done" can mean the code as it stands, or the code once the
   planned work lands. Those are different documents. Ask; do not pick.
2. **Look before declaring.** For each component you are about to propose, search the repo
   for the names and symbols it would introduce, and surface every hit. A component that
   already exists under another name is the failure being prevented.
3. **Interview**, section by section, confirming each before the next. Read
   `$FLW/core/schemas/spec-v4.schema.json` for what each field means, and
   `$FLW/core/skills/flw-spec/references/good-contract.md` for what a good one looks
   like. Drive out what the user
   has not said: scale, encoding, concurrency, failure model, deployment, runtime floor,
   edge cases, security, re-runability. "Doesn't matter here" is a valid answer — record it
   as an assumption so it surfaces if it later does.

   Ask, per component, what about it would still be true if it were rewritten by someone
   who never saw the code, and what would break someone else if it changed — the same
   question `Amending` step 2 asks below, which states the rule for `properties` and
   `surfaces` in full. A first contract declares `schema_version = 4`.
4. **Show the whole contract** as one block, get an explicit lock, then write two files:
   `specs/current.toml` and `specs/versions/<name>-minor.toml`, named by the same rule
   step 5 states below — never `v1.0.toml`, which is a legacy number carrying no
   classification, so nothing downstream can move `spec_version` by it. The first version
   file has no `base` — there is no predecessor.
5. **`flw validate`.** Fix and re-run.

---

## Amending

1. **Read the contract and the version files it has not applied.** State back what the
   contract currently claims, in three lines. A record the `applied` list does not name is
   work in flight — someone else's, possibly — and worth knowing about before you add
   another.
2. **Interview the change, not the contract.** Answer *what* and *why* at the level of
   requirements, architecture and design. Lean on the language already there; do not
   re-interview what still holds. If a surviving part no longer fits a new decision,
   surface it — an unreconciled conflict there breeds the next round.

   For a touched component, ask what about it would still be true if it were rewritten by
   someone who never saw the code, and what would break someone else if it changed. The
   first goes in `properties`, the second in `surfaces` — a mechanism nobody outside
   touches is not a surface, a statement that cannot be false is not a property, and a
   property that restates a `provides` sentence is a duplicate rather than a second
   reader's version of it.
   **Search the note store once the interview names the change**, with its own terms —
   the library, the failure, the component. Titles read at the opening were read against
   nothing; this is where you know the subject.

   **This skill has no write moment, and that is deliberate.** The interview already
   records a decision and its rationale in the version file's `decisions`, which
   `flw validate` enforces and `flw ledger` reads. A note here would be a second copy of
   a ledger record, which is what the two stores staying separate exists to prevent.

3. **Read the code. This is a step, not an aside, and it comes before you edit anything.**
   Find what already exists that this touches. Decide what survives, what is recycled out
   of the thing being deleted, and what order stops the tree being broken in between. That
   knowledge is in neither contract version and nowhere else — and finding it sometimes
   changes what the contract should say, which is why it precedes the edit rather than
   following it.

   **If the interview settles nothing** — the contract already says what they asked for, or
   the thing they want changed lives somewhere else — say so and stop. Write no edit and
   no version file. A version whose diff is empty is worse than no version.

   **What this skill may edit is `specs/`.** Not `.flw/config.toml`, not
   a Makefile. If the thing that is wrong is a local test invocation or a project
   principle, name the file and hand it back.
4. **Draft the exact contract edit** — the sentences the contract gains, loses or
   replaces, and where each goes. Do not edit `specs/current.toml`: the edit goes into the
   version file's `contract_edit`, applied by `flw-execute` when the run it describes
   finishes, not now.
5. **Write `specs/versions/<name>-minor.toml` or `specs/versions/<name>-major.toml`.**
   Read `$FLW/core/schemas/version.schema.json` for the shape.
   - `name` is the record's identity and matches the filename without the suffix. `base`
     is the record the contract had last applied when you started, and `contract_edit`
     carries the text drafted in step 4. The suffix is `-major` when a behaviour someone
     relied on now works differently, and `-minor` when a capability arrives and nothing
     that worked before changed, along with corrections, refinements and internal
     deletion. Judge it by what *this change* does rather than by
     the contract's contents: a contract can carry a long `final_state.removed` list and
     still be taking a minor change, because those removals happened in earlier versions.
     The contract moves when `flw-execute` finishes this version's run, which is when the
     name joins `applied`.
   - **This classification is flw's default, not law.** A project may replace it in
     `.flw/extensions/flw-spec.md` — the file `flw context flw-spec` already printed. What a
     project usually redefines: what major and minor mean for it, and where 1.0 sits,
     which in a service is often whatever reached production. A project also scopes its
     versions by where `specs/` lives — `nearest_project()` resolves the nearest one, so a
     feature inside a larger service gets its own contract and its own numbering by
     holding its own `specs/` directory.
   - **`release_line`, when this record moves the product to a new line** — 1 being
     whatever reached production. Declaring it restarts the count, so the release this
     record produces is `1.0.0` and the next minor is `1.0.1`. A record that is not
     moving the line omits the field entirely. The contract carries no separate key for
     it: the line is the first part of `spec_version`, so there is one place it can be
     read and nothing to disagree with.
   - **Name it for what it does**, in kebab-case: `add-build-posture`, `version-names`.
     The name never changes afterwards. That is the whole point of it — two people
     speccing at once pick different names the way they pick different branch names, and
     neither has to be renumbered when it lands. A number would have to be, and rewriting
     a record's identity at merge means the file in git is not the file anyone reviewed.
   - `approach` carries step 4's reasoning. Write only what stops being true once the work
     lands — if a sentence would still hold afterwards, it belongs in the contract. Its
     most valuable use is negative: saying what the work is *not*, so nobody solves the
     wrong problem correctly.
   - `dag` only if the work needs ordering. `decisions` only if a fork was settled.
   - A one-line correction is a four-line file. Do not pad it.
   - **Speccing from a review report**: carry the report's coverage line — what it read and
     what it did not — and any measurement it made into `approach`. A number is the part of
     a report that cannot be re-derived by reading, so it is the part most worth carrying;
     the report itself is scaffolding once this happens.
   - **A version that adds a subcommand declares it in the contract now, not at the end.**
     Write the `flw <name> [flags...]` line into the CLI component's `surfaces` at spec
     time, exactly as the parser will accept it, and say in `approach` that you did.
     `flw-execute` moves the contract only after the checks pass, and a project whose
     contract claims its own surface is complete has a check that fails until the two
     agree — so a version that waits deadlocks against itself. flw hit this on 4.2 and
     again on `knowledge-base`.
6. **Show the user the version file and let them edit it.** A plan accepted as drafted is
   how a re-spec becomes a demolition nobody sanctioned.
7. **`flw validate`.**

---

## Thrifty mode

On `--thrifty`, `[interview] mode = "thrifty"`, or a request that plainly says it —
*"don't make me sit through an interview"* — skip the conversation. Write the draft and
**stop**. The user edits the file. Next invocation, re-read, `flw validate`, and ask only
about what is still open.

**Markers go inside the values, not in comments.** Required fields have a minimum length,
so a TOML comment cannot hold one and the draft would not validate:

```toml
criteria = "TODO(flw): what does a human have to check beyond the tests?"
```

`flw validate` finds every `TODO(flw)` and reports the draft as unfinished, which is how
one never ships by accident. Print the same list yourself and stop there.

**Thrifty subtracts the conversation, not the steps.** The plan still goes on disk first —
that rule has no exception, so if there is no plan, spend your one question there. Reading
the code before an amend still happens; it is not conversation. What thrifty removes is
the section-by-section confirmation and the final lock.

**Amending thriftily** writes the version file as a draft and puts an unambiguous edit
into `contract_edit`, not into the contract. Anything genuinely open goes in the version
file's `approach` as a marker, not into `current.toml` — a contract of record with `TODO`
in it is worse than an unfinished draft beside it.

A marker is what you write instead of guessing.

## Optional: a second read

For a large or intricate contract, offer to run the critic in
`$FLW/core/skills/flw-spec/references/spec-critic.md`. It finds the semantic gaps
validation structurally cannot —
a requirement with no component, an assumption relied on but never stated, drift from the
plan. Skip it for small ones; do not manufacture ceremony.

## Rules

1. **No silent inference.** If the user has not said it, ask or mark it.
2. **Edit the contract, do not rewrite it.** The diff is the review surface.
3. **Open questions go in `open_questions`, not into assumed answers** — and an amend
   that settles one removes it. A question the contract still asks after the answer
   shipped reads as live and is not.
4. **Validate before declaring done.**
