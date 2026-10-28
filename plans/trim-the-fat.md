# Trim the fat: expandable primitives, not shipped special cases

One sweep. Every part of the package is assessed by one question, and the answer decides
whether it is cut, kept, or turned into a primitive with a declared extension point.

> **Does core ship a primitive that a project can extend, or a special case that only the
> checkout's author can change?**

A special case in core has to be edited inside flw to serve a repository flw's author never
saw. A primitive is a contract plus one shipped instance, and a local agent writes the next
instance into the project's own `.flw/`, once, when that project needs it.

This is not a rule against shipping code. It is a rule about where a second instance goes.

## Why now, and what the evidence is worth

Measured 2026-10-28 over 552 Claude Code session transcripts under `~/.claude/projects`
(1.42 GB), counting `flw <subcommand>` inside the `"command"` field of Bash tool calls — real
invocations, not mentions in prose:

```text
grep -rhaoE '"command":"[^"]*' --include='*.jsonl' . \
  | grep -oE '\bflw (install|uninstall|style|sync|update|doctor|context|add|remove|list|test|scout|validate|ledger|kb|know|map|stale|version)\b' \
  | sort | uniq -c | sort -rn
```

Outside flw's own checkout — five projects: `agentic/harness`, `apps/mortgauge`, `data`,
`data/flat-hunt`, `punto` — seven subcommands have ever run: `validate` 153, `context` 142,
`test` 86, `know` 41, `kb` 14, `ledger` 4, `scout` 3. Inside flw's own checkout the work
commands that do not recur are `stale` 21, `style check` 25, `style lint` 24, `map` 6.

**What the figure cannot tell you.** It covers Claude Code only. `~/.codex/sessions` holds 3
files and `~/.local/share/opencode` holds 1, so the other two hosts carry no usable history,
and flw is installed into all three. A command this corpus never saw may be in daily use from
a Codex session. So usage is supporting evidence here and never the only reason: each item
below is argued from what it costs and what consumes its output.

## What this sweep adds

One mechanism, because the primitive question turns the scout from a cut into a contract:
a `[scout] scanners` key and the lookup that reads it. Everything else in the sweep is
subtraction.

---

## 1. The scout becomes a primitive with a registry

**Today it is two shipped special cases.** `core/scripts/scout.py` ranks Python,
`core/scripts/scout.mjs` ranks TypeScript, and `cli/flw.py:2718-2790` runs them one after the
other with the TypeScript branch hardcoded: four glob patterns, a `shutil.which("node")`
check, a `node_modules` exclusion, a package-manager guess across four lock files, and two
error messages naming `typescript` by name. A repository in any third language gets
`error: no Python or TypeScript found` and a pointer to `aider --show-repo-map`. Adding Go
means editing flw.

Its cost: `scout.mjs` 531 lines, `tests/test_scout_mjs.py` 397 lines and 17 tests — the only
skips in the 856-test suite, skipped wherever the `typescript` package is absent, which is
every fresh clone — plus `package.json`, which exists for nothing else and says so in its own
description, plus `node_modules/`.

**The contract already exists, unnamed.** `scout.mjs` is a subprocess taking
`<root> <budget>`, printing a finished ranking section to stdout, and exiting 0 for a
ranking, 2 for "the parser this language needs is not installed here", 3 for a walk that hit
an unreadable directory. Nothing is passed back as data: the two reports are concatenated.
Naming that contract is the whole change.

**A scanner is:** an executable file, invoked as `<scanner> <root> <budget>`, printing one
ranking section to stdout, exiting 0 when it ranked something, 1 when it refused, 2 when the
language's own parser is missing from the target repo, 3 when it ranked but could not read
part of the tree. It loads the target repository's own parser and brings no dependency of its
own — the reasoning `scout.mjs:8-11` already states, and the reason the Python scanner uses
stdlib `ast`.

**Registered as** `[scout] scanners`, a list of paths relative to the project root, read from
the project's config file only and never from the machine's, on the same reasoning as
`[project] roots`, `[knowledge] dir` and `[spec] areas`: which languages a repository is
written in is a fact about that repository.

**Core ships one instance:** the Python scanner, because it needs nothing installed anywhere
and it is flw's own language.

**TypeScript becomes the worked example.** `scout.mjs` moves to
`core/skills/flw-research/references/scout-example/`, beside `knowledge-example/`, which is
already the pattern: reference material a survey reads before writing its own. It stops being
shipped code, so its 17 tests go with it, and `package.json` and `node_modules/` go. A
TypeScript repository gets a scanner by having `/flw-research` copy and register that example
— once, in that repository.

`flw scout` with files it has no scanner for says how many and of what extension, and names
the example to imitate. That replaces `cli/flw.py:2771-2790`, where the same sentence is
hardcoded to two languages.

**Lost.** TypeScript stops working out of the box. A TS repository needs one research run
before `flw scout` covers it. Accepted: the five projects that use flw hold 5 TypeScript
files between them — 4 in `apps/mortgauge`, 1 in `punto`, 0 in the other three — and the cost
today is 928 lines, a devDependency and every clone's test run reporting skips.

**The alternative, for the review to weigh.** Keep `scout.mjs` in `core/scripts/` as a second
shipped instance that the registry discovers by default, and drop only its tests and the
devDependency. That keeps TypeScript working with no research run, at 531 lines in core and a
default that cannot be reproduced in a clone's tests.

## 2. `flw stale` is a fold over four hand-written readers; the primitive is already elsewhere

**The primitive is a stamped document plus a diff**, and `flw know --check` / `--owed` is it:
a file carries the revision it was true at, and a command says what moved since. That is used
— `--owed` 79 invocations, `--check` 33.

`core/scripts/stale.py` applies the same idea to four more stores, and each needed its own
bespoke reader: review reports by filename stamp, extension claims by a regex for countables,
notes by frontmatter, records by citation. None of it is extensible — a project with its own
kind of document cannot add a reader without editing flw — and nothing consumes the result.
Run here today it prints 57 unread review reports, 35 dead citations, 8 knowledge files, 4
extensions with 6 undated claims, and exits 0. Nothing branches on any of it.
`plans/design-the-loop.md` §4.3 records the same finding from the other side: `flw know
--check`, `flw stale` and `flw validate` all exit 0 over files that disagree with the tree.

Removed:

- `core/scripts/stale.py` — 565 lines
- `tests/test_stale.py` — 852 lines, 46 tests
- `stale()` at `cli/flw.py:4023` — 71 lines — and its parser block at `cli/flw.py:4546`
- the `flw stale [--root PATH] [--owed]` surface line in the contract
- `flw validate`'s sources rule at `core/scripts/validate_spec.py:524-535`, which refuses an
  unapplied record whose prose cites a report path and carries no `sources` list. It refuses
  that only so `stale.py:103` can read the list.
- `DEFAULT_REPORTS` at `validate_spec.py:306` and `citation()` at `:309`, once the rule above
  and `stale.py` are gone. `validate_spec.py:339`, `:413` and `:728` also pass
  `DEFAULT_REPORTS`, so trace each before deleting the constant.
- the `Specced as` marking rule at `core/skills/flw-spec/SKILL.md:255-262`, which writes a
  mark whose only reader is `stale.py:46`
- the `flw stale` lines in `core/shared/context.md:92`, `README.md:55` and `docs/install.md:85`

**Stays, and this is a hard constraint.** The `sources` key in
`core/schemas/version.schema.json:57`. That schema sets `additionalProperties: false` at `:7`
and 10 records under `specs/versions/` carry `sources`, so removing the key makes
`flw validate` refuse ten applied records. It becomes a key the schema accepts and nothing
reads, and its description says so.

**Lost.** The one command that folds every store's staleness into one answer, and the
report-to-record mapping. `plans/design-the-loop.md` §6.2 treats `flw stale --owed` as the
answer to "is the loop closed", so this closes that design off rather than deferring it. That
is the real cost of this cut, accepted rather than overlooked: if staleness is ever wanted
with teeth, the way back is a check in `[tests] checks` that exits non-zero, not a reporting
command that exits 0.

## 3. `flw style lint` and `flw style check` are a frozen partial copy of the style file

**The primitive is the prose.** `core/styles/terse_prose.md` is read by every agent in every
session and is the extension point already: a project installs its own style by name, under
`~/.flw/styles/<name>.md`.

`core/scripts/style_lint.py` is a fixed set of regex rules that reimplements part of that file
and cannot be extended from a project. It is also partial on purpose: its evaluative-word
rules deliberately never run against files, only against session transcripts, so that rule
class is unenforced in every repository. `flw style check` reads one machine's session store,
which no clone has. Neither gates anything — both print and exit.

Removed:

- `core/scripts/style_lint.py` — 454 lines
- `tests/test_style_lint.py` — 484 lines, 39 tests
- `style_check()` in `cli/flw.py` — 111 lines — and the `style lint` and `style check` parser
  entries
- the two surface lines in the contract
- `core/skills/flw-style/SKILL.md:51` and `:111`, the two sentences pointing at them

**Stays.** `core/styles/terse_prose.md`, `flw style install`, `flw style uninstall`, and the
`flw-style` skill. The style is the part of flw that runs in every session. The skill finds
its own instances of a failure the user just named by reading its own output; lines 51 and 111
are pointers, not the mechanism.

**The extension point that replaces it.** A project that wants mechanical prose enforcement
adds its own command to `[tests] checks`, which is already flw's primitive for "run this and
report". Nothing in core needs to know what the rules are.

## 4. `core/schemas/spec-v3.schema.json` — the primitive is fine, the instance is dead

The dispatch table at `core/scripts/validate_spec.py:690` keyed on `schema_version` is the
expandable primitive, one entry per schema, and it stays. The v3 instance has no live
document: no contract anywhere declares `schema_version = 3` and flw's own declares 4.

Removed: the file (125 lines), the dispatch entry, and `tests/test_validate_spec.py:205`,
which exists to explain why the file stays. `expected_schema()` then names 4 as the only
known version, and its error message for an unknown one must still read correctly with a
one-element list.

## 5. `docs/measuring.md` — 217 lines

Prose about measuring flw, which is the material already removed from `README.md`. Remove the
file and any pointer to it.

## 6. `flw sync` as a subcommand

4 invocations, all inside flw's own checkout. The 195-line `sync()` function stays, because
`update()` is "pull, then sync" and calls it — what goes is the top-level entry point, its
parser block and its contract surface line.

**Check before cutting.** `update()`'s no-upstream branch prints a message pointing at
`flw sync` as the local half without pulling. If that is the only way to repair an install
whose remote is unreachable, the subcommand earns its place and this item is dropped.

---

## Assessed and kept, because each is already the primitive

- **`flw add` / `flw remove` / `flw list` and `~/.flw/bundles.toml`** — 39 code sites in
  `cli/flw.py`, 28 tests, `docs/extending.md` (135 lines), an override branch in `discover()`
  at `cli/flw.py:220-250`, an orphan branch in `doctor` at `:1619`. No bundle is registered on
  the author's machine and `~/.flw/bundles.toml` does not exist. It is the expandable
  primitive for skills: core ships five, a user registers their own bundle without editing the
  checkout. Unused is not the criterion.
- **`core/reviews/*.toml` and `core/schemas/review.schema.json`** — 201 lines. Core ships
  `quick.toml` and `eng.toml`, a project copies one into `.flw/reviews/` and edits it, and
  `flw validate <config>` checks it. Already a contract plus two instances.
- **`[tests] setup` / `checks` / `yours`** — the primitive for "what counts as done here",
  read as data and run verbatim. It is what items 2 and 3 fall back to.
- **`flw map`** — 51 lines in `cli/flw.py` and four prose sites, 6 invocations. It folds the
  seams the knowledge store declares, so it reads a store that is itself the primitive. Too
  small to pay for the churn.
- **`flw ledger`** — `core/scripts/ledger.py` 929 lines, `tests/test_ledger.py` 1,197 lines,
  91 tests, 18 invocations of which 4 are outside flw. The largest body after the CLI and its
  tests, and the weakest "kept" on this list: it reads four fixed document kinds and a project
  cannot add a fifth. Kept now because `flw-spec` step 3 depends on it to find whether a
  decision was already settled. Re-measure after this sweep rather than cutting blind.

## Assessed and closed as refused

- **`flw kb lint`'s nine unbuilt rows**, `plans/backlog/note-store-deferred-half.md`. Each row
  is another hardcoded check over a note format that is already open — every frontmatter key
  is optional, which is the primitive. Nine more rows is nine more special cases. Refused
  rather than deferred; the backlog item is closed. No code changes.

## Order

Item 2 and item 4 both touch `core/scripts/validate_spec.py`, so do 2 before 4 and re-read
`expected_schema()` after.

1. Item 1 — removes the only test skips, so every later run is unconditional.
2. Item 2 — the largest, and the only one reaching into `flw validate`.
3. Item 4.
4. Item 3.
5. Item 5.
6. Item 6, if its check passes.

## What must stay green at every step

- `flw validate` exits 0 over the contract and all 77 records, the ten carrying `sources`
  included.
- `.venv/bin/pytest` passes, and after item 1 reports no skips.
- `flw test --no-stream` passes.
- `flw doctor` reports no orphans and no stale links.
- `flw know --check` reports 0 changed. Every item deletes files the knowledge store
  describes, so `core/scripts/scripts.md` and `tests/tests.md` need rewriting under the
  correction carve-out, not a new survey.
- Byte budgets in `core/scripts/budget.py` all under ceiling. Items 1, 2 and 3 remove prose
  from `flw-research/SKILL.md`, `flw-spec/SKILL.md` and `flw-style/SKILL.md`, so all three
  gain headroom — item 1 adds a sentence to `flw-research` about writing a scanner, and that
  file is the tightest in the package.

## Totals, if everything lands

2,876 lines of code and tests deleted against roughly 60 added for the scanner registry; 102
tests gone from 856; 4 subcommands and 1 subcommand entry point removed from 19; one
devDependency and `node_modules/` gone; 0 skips in a fresh clone's test run. One capability
moves from shipped to extensible: ranking a language other than Python is now something a
project sets up once, in any language, instead of something only flw's author can add.
