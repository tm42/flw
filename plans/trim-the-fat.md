# Trim the fat: expandable primitives, not shipped special cases

One sweep. Every part of the package is assessed by one question, and the answer decides
whether it is cut, kept, or turned into a primitive with a declared extension point.

> **Does core ship a primitive that a project can extend, or a special case that only the
> checkout's author can change?**

A special case in core has to be edited inside flw to serve a repository flw's author never
saw. A primitive is a contract plus one shipped instance, and a local agent writes the next
instance into the project's own `.flw/`, once, when that project needs it.

This is not a rule against shipping code. It is a rule about where a second instance goes.

**Revision history.** The first draft of this plan carried six items. A review at `a8b73ec`
found that three of them were wrong: item 4 reversed a recorded decision whose rationale names
the thing the draft missed, item 5 deleted a protocol four live readers depend on, and item 6's
own go/no-go check fails. All three are now under "Assessed and kept", with the evidence, so a
later round does not re-propose them. Item 3 was wrong in the other direction and got smaller.

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
a `[scout] scanners` key and the lookup that reads it, about 60 lines. Everything else is
subtraction.

---

## 1. The scout becomes a primitive with a registry

**Today it is two shipped special cases.** `core/scripts/scout.py` ranks Python,
`core/scripts/scout.mjs` ranks TypeScript, and `cli/flw.py:2727-2767` holds the second one after the
other with the TypeScript branch hardcoded: four glob patterns, a `shutil.which("node")`
check, a `node_modules` exclusion, a package-manager guess across four lock files, and two
error messages naming `typescript`. A repository in a third language gets
`error: no Python or TypeScript found` and a pointer to `aider --show-repo-map`. Adding Go
means editing flw.

Its cost: `scout.mjs` 531 lines, `tests/test_scout_mjs.py` 397 lines and 17 tests — the only
skips in the 856-test suite, skipped wherever the `typescript` package is absent, which is
every fresh clone — plus `package.json`, which exists for nothing else and says so in its own
description, plus `node_modules/`.

**The contract already exists, unnamed.** `scout.mjs` is a subprocess taking
`<root> <budget>`, printing a finished ranking section to stdout, and exiting 0 for a ranking,
2 for "the parser this language needs is not installed here", 3 for a walk that hit an
unreadable directory. Nothing is passed back as data: the two reports are concatenated.
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

### The clause that is not satisfied today

**Neither scanner refuses.** On an empty directory `core/scripts/scout.py <dir> 20` prints
`no python found` and exits 0; `scout.mjs` prints `0 ts files (0 test), 0 exported definitions`
and exits 0. Whether a language is present at all is decided in the CLI — `engine.sources(root)`
at `cli/flw.py:2718` and an rglob over four extensions at `:2727-2732` — which cannot answer for
a language the CLI has never heard of. So each scanner gains exit 1 for "this repository holds
no file of my language", and both CLI gates go. That also removes a duplication the comment at
`:2713-2717` already records: the rglob "cost most of the run and answered differently",
because it descends into directories the engine prunes.

### Six things an implementer would otherwise guess

- **The built-in always runs, first, and is never listed.** This settles three questions at
  once. It needs no path spelling inside the checkout, so "relative to the root, not absolute,
  no `..`" can be the rule for every entry a project writes; the project's list adds scanners
  rather than replacing them, so registering a Go scanner never silently stops Python being
  ranked; and it stays in-process, so `unread_by_scouts` at `cli/flw.py:2661-2680` keeps
  reading `scout.SKIP`. `[tests] checks` works the other way — the project's list is the whole
  list — because a check list is the definition of done and wholly the project's, while a
  scanner list is a capability set that a project gains nothing by subtracting from.
- **An entry declares its suffixes**, as a table of a path and its extensions.
  `unread_by_scouts` counts suffixes in the fixed `CODE_EXTENSIONS` allowlist at
  `cli/flw.py:2653-2658`, which omits `.py` and `.ts` by construction. Once the CLI no longer
  knows which languages ran, a bare path leaves a registered Go scanner's `.go` files in that
  count and the line reads `16 .go not read` about files it just ranked.
- **A registered path that is missing, unreadable, not executable, absolute or holding a `..`
  component** is named on stderr and not run, and the run continues with the scanners that
  work.
- **`flw scout` exits** 0 when any scanner ranked something and 1 when none did. A scanner's 2
  is named and does not by itself fail a run another scanner ranked, which is what the CLI does
  today. Exit 3 prints its section and is reported; `scout.mjs:250` sets it and the CLI inspects
  only returncode 2, so that state is silent today.
- **A path argument reads no project config.** `cli/flw.py:2692-2694` resolves it with no
  project lookup and `specs/current.toml:150` forbids walking upward, so only the built-in runs
  there.
- **The package-manager guess** across four lock files at `cli/flw.py:2745-2762` moves into the
  worked example. Only a Node scanner needs it, and the CLI cannot guess for a language it does
  not know.

### Edits beyond the obvious, found by review

- `tests/test_scout.py:614-617`, `test_scout_mjs_has_no_nul_byte`, opens
  `core/scripts/scout.mjs` by path and fails once the file moves.
- `specs/current.toml:239` lists `core/scripts/scout.mjs` in a component's `paths`, `:322`
  lists `package.json` in another's. `flw validate` does not check that a declared path
  exists, so both drift silently rather than fail — which is why they need naming here.
- `specs/current.toml:308` describes the `typescript` devDependency, the skip-by-name and the
  TypeScript-7 refusal. `:256` says "files in languages neither scout parses" and `:285`
  "Both scouts rank the file that defines an imported name".
- `cli/flw.py:4315` says "Python and TypeScript only" in `scout --help`, `:4339` opens the
  TypeScript epilog, and `:2778` and `:2784` are the two sentences naming both languages.
- `core/skills/flw-research/SKILL.md:115-118` — "The scout's external-dependency list for
  TypeScript" and "the scout only reads two languages".
- `plans/backlog/typescript-scout-unmeasured.md` and `plans/backlog/index.md:22` describe a
  shipped file; retire or rewrite both.
- `core/scripts/ledger.py:343` is a comment naming the path.
- `.gitignore` keeps `node_modules/` and `package-lock.json`; harmless once gone, so leave
  them or drop them, but say which.

**Lost.** TypeScript stops working out of the box. A TS repository needs one research run
before `flw scout` covers it. Accepted: the five projects that use flw hold 5 TypeScript files
between them — 4 in `apps/mortgauge`, 1 in `punto`, 0 in the other three — and the cost today
is 928 lines, a devDependency and every clone's test run reporting skips.

**The alternative, for the second review to weigh.** Keep `scout.mjs` in `core/scripts/` as a
second shipped instance the registry discovers by default, and drop only its tests and the
devDependency. That keeps TypeScript working with no research run, at 531 lines in core and a
default that cannot be reproduced in a clone's tests.

## 2. `flw stale` is a fold over four hand-written readers; the primitive is already elsewhere

**The primitive is a stamped document plus a diff**, and `flw know --check` / `--owed` is it:
a file carries the revision it was true at, and a command says what moved since. That is used
— `--owed` 79 invocations, `--check` 33.

`core/scripts/stale.py` applies the same idea to four more stores, and each needed its own
bespoke reader: review reports by filename stamp, extension claims by a regex for countables,
notes by frontmatter, records by citation. None of it is extensible — a project with its own
kind of document cannot add a reader without editing flw. Run here today it prints 57 unread
review reports, 35 dead citations, 8 knowledge files, 4 extensions with 6 undated claims, and
exits 0. `plans/design-the-loop.md` §4.3 records the same finding from the other side:
`flw know --check`, `flw stale` and `flw validate` all exit 0 over files that disagree with
the tree.

**Correction to the first draft.** "Nothing consumes the result" is wrong. `flw-research`'s
re-check mode documents `flw stale`'s output as its input:
`core/skills/flw-research/references/recheck.md:14` — "`flw stale` is what produces such a
list"; `:38` — "Take the paths. From the ask, or from `flw stale`, or — given neither — from
`flw know --check`"; `:69`; and `core/skills/flw-research/SKILL.md:320`. The mode survives
because the `flw know --check` fallback at `:38-39` already covers the knowledge-file case,
which is the only case with a reader. The three prose sites become two: the ask, or
`flw know --check`.

Removed:

- `core/scripts/stale.py` — 565 lines
- `tests/test_stale.py` — 852 lines, 46 tests
- `stale()` at `cli/flw.py:4023` — 71 lines — and its parser block at `cli/flw.py:4546`
- `cli/flw.py:2816-2820` and `:2875`, which resolve and pass `[paths] reports` only to feed
  the validate rule below
- the `flw stale [--root PATH] [--owed]` surface line in the contract
- `flw validate`'s sources rule at `core/scripts/validate_spec.py:524-535`, which refuses an
  unapplied record whose prose cites a report path and carries no `sources` list. It refuses
  that only so `stale.py:103` can read the list.
- `DEFAULT_REPORTS` at `validate_spec.py:306` and `citation()` at `:309`, plus the
  `reports_dir` parameter on `check_version` (`:413`) and `validate_file` (`:728`). Traced:
  `:339` and `:342` are inside `citation()` and go with it; once the rule at `:524-535` is
  gone, nothing in either function reads `reports_dir`. No reader survives.
- `tests/test_validate_spec.py:493`, `:501`, `:524`, `:550` test the sources rule directly —
  `:550` asserts flw's own records are never refused by it — and `tests/test_cli.py:3755`
  asserts "no sources field" in stderr. `tests/test_cli.py:4434`, `:4459` and `:4490-4495`
  drive `flw stale` through `main()`.
- the `Specced as` marking rule at `core/skills/flw-spec/SKILL.md:259-265` — the mark,
  whose only reader is `stale.py:46`, and the instruction at `:263-265` to name those report
  paths in the record's `sources` field, which nothing reads after this
- the `flw stale` lines in `core/shared/context.md:55`, `README.md:56`, `docs/install.md:85`,
  `recheck.md:11-14`, `:38`, `:69` and `flw-research/SKILL.md:320`

**Stays, and this is a hard constraint.** The `sources` key in
`core/schemas/version.schema.json:57`. That schema sets `additionalProperties: false` at `:7`
and 10 records under `specs/versions/` carry `sources`, so removing the key makes
`flw validate` refuse ten applied records. It becomes a key the schema accepts and nothing
reads, and its description says so.

**Lost.** The one command that folds every store's staleness into one answer, and the
report-to-record mapping. `plans/design-the-loop.md` §6.2 treats `flw stale --owed` as the
answer to "is the loop closed", so this closes that design off rather than deferring it. That
is the real cost, accepted rather than overlooked: if staleness is ever wanted with teeth, the
way back is a check in `[tests] checks` that exits non-zero, not a reporting command that
exits 0.

## 3. `flw style check` and the transcript half of the linter

**The first draft had this backwards.** It claimed neither style command gates anything.
`specs/current.toml` declares `.venv/bin/python core/scripts/style_lint.py .` in
`[success_criteria] tests`, and `.flw/config.toml` has no `checks` key on purpose — its comment
says every contract check runs here — so `flw style lint` runs on every `flw test`. Reading
the module, the two halves are not alike:

- **`FILE_RULES` stays.** Two geometry rules: a heading deeper than `###`, and trailing double
  spaces that become a `<br>` in a file. `style_lint.py:6-9` records them as measured with
  every finding real. They run anywhere, need nothing installed, and gate every `flw test`.
  Keeping them keeps the declared check, so no edit to `success_criteria` is needed.
- **`REPLY_RULES` and the transcript reader go.** `style_lint.py:243-435` —
  `reply_findings`, `session_transcripts`, `read_replies`, `recent_replies`, `verdict`, about
  255 lines — read one machine's session store, which no clone has. `style_lint.py:316` says
  so itself: "the corpus is one machine's session store, so the figure cannot be re-taken
  anywhere else". Nothing gates on it.

Removed:

- `style_lint.py:243-435` and `REPLY_RULES` at `:73`
- `style_check()` at `cli/flw.py:1254` — 111 lines — and the `style check` parser entry
- `tests/test_style_lint.py`: the 11 tests covering the transcript half, of 39
- `tests/test_cli.py:4532`, `:4546`, `:4561`, `:4573` — four `style check` tests
- `core/skills/flw-style/SKILL.md:12` and `:51`
- `specs/current.toml:80`, the property that `flw style check` names the directory it read,
  and `:308`'s sentence about the checker banning a narrower word list than the style file
  names, with the two tests holding that gap open from both sides

**Stays.** `core/styles/terse_prose.md`, `flw style install`, `flw style uninstall`,
`flw style lint` with its handler at `cli/flw.py:1230`, `specs/current.toml:193` (the property
that `flw style lint` exits 2 on a target it could not read), and the `flw-style` skill, whose
`SKILL.md:111` pointer at `flw style lint` survives because the command does.

**Lost.** The vocabulary and shape rules, which were never enforced against files by design
and could only ever run on the machine that wrote the prose.

**The extension point that replaces it.** A project wanting more mechanical prose enforcement
adds its own command to `[tests] checks`, which is already flw's primitive for "run this and
report". Nothing in core needs to know what the rules are.

---

## Assessed and kept, because each is already the primitive

- **`core/schemas/spec-v3.schema.json`** — proposed for deletion in the first draft and wrong.
  `tests/conftest.py:10` declares `schema_version = 3`, and the `specs` fixture built from it
  is used by 20 tests in `tests/test_validate_spec.py`, 2 in `tests/test_direct_run.py` and 1
  in `tests/test_cli.py`; `tests/test_direct_run.py:40` passes the schema by path. The
  decision is already recorded in `specs/versions/v4.0.toml`, with the rationale "dropping 3
  makes every contract flw did not write fail on a key it never heard of, and
  tests/conftest.py declares schema_version = 3, so the whole fixture suite is a live v3
  consumer". The criterion agrees: v3 is the only second instance of the dispatch primitive at
  `validate_spec.py:699`, so deleting it leaves one entry and nothing testing that dispatch
  works at all.
- **`docs/measuring.md`** — proposed for deletion in the first draft and wrong. Four live
  readers: `core/scripts/store.py:73` cites its protocol, `README.md:134` and `docs/layout.md:32` list it,
  and
  `plans/backlog/store-holds-every-body-in-memory.md:14`,
  `plans/backlog/scout-at-monorepo-scale.md:14` and
  `plans/backlog/unwritten-note-offers.md:13` depend on it. It is itself a primitive — a fixed
  corpus plus a fixed command set, with two seeded generators deliberately kept out of
  `core/scripts/` — and it is the method behind the sourcing rule the contract now binds.
- **`flw sync`** — proposed for deletion in the first draft, and its own go/no-go check fails.
  `doctor` points at it three times: `cli/flw.py:1625` (a stale link), `:1637` (not linked
  here), `:1654` ("`flw sync` will adopt it"), with `tests/test_cli.py:371`, `:753`, `:870`
  asserting that text. `update()` exits 1 without pulling when there is no upstream and names
  `flw sync` as the local half. `specs/current.toml:130`, `:131`, `:143` are properties
  describing it. It is the only link repair that does not pull.
- **`flw add` / `flw remove` / `flw list` and `~/.flw/bundles.toml`** — 39 code sites in
  `cli/flw.py`, 28 tests, `docs/extending.md` (135 lines), an override branch in `discover()`
  at `cli/flw.py:220-250`, an orphan branch in `doctor` at `:1619`. No bundle is registered on
  the author's machine. It is the expandable primitive for skills: core ships five, a user
  registers their own bundle without editing the checkout. Unused is not the criterion.
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

1. Item 1 — removes the only test skips, so every later run is unconditional.
2. Item 2 — the largest, and the only one reaching into `flw validate`.
3. Item 3.

Items 2 and 3 both touch `specs/current.toml`, so apply each contract edit on its own and read
`git diff specs/current.toml` by itself at each step.

## What must stay green at every step

- `flw validate` exits 0 over the contract and all 77 records, the ten carrying `sources`
  included.
- `.venv/bin/pytest` passes, and after item 1 reports no skips.
- `flw test --no-stream` passes, which includes `style_lint.py .` — so item 3 must leave that
  command working, not merely leave the file present.
- `flw doctor` reports no orphans and no stale links.
- `flw know --check` reports changed only for files this sweep's own commits falsified, each
  corrected and re-stamped under the correction carve-out at the commit that falsified it, not
  before it. Seven of the eight stamped files will read changed, not two: `cli/cli.md:19` and
  `:50` name `style_lint` and `scout.mjs`, `tests/tests.md:23` lists `test_stale.py` and
  `test_style_lint.py`, `core/scripts/scripts.md:73`, `:83` and `:95` name `scout.mjs`,
  `stale.py` and `style_lint.py`, `core/skills/skills.md:47` names `flw style check`,
  `core/shared/shared.md` covers `context.md`, `specs/specs.md` carries the record count, and
  `flw.md:27` says `node_modules/` exists so `core/scripts/scout.mjs` can be exercised. Only
  `core/schemas/schemas.md` is untouched, because its `:19` claim that `spec-v3.schema.json` is
  kept stays true.
- Byte budgets in `core/scripts/budget.py` all under ceiling. Item 1 adds a sentence to
  `flw-research/SKILL.md` at 19,401 / 21,000 and removes two others from it; item 2 removes
  `:259-265` from `flw-spec/SKILL.md`, which at 20,430 / 21,000 is the tightest file in the
  package, so that is where the tightest one gains room.

## Totals, if everything lands

About 2,393 lines of code and tests deleted against roughly 60 added for the scanner registry,
plus 531 relocated from shipped code to reference material. Around 118 tests gone from 856 — 17 + 46 + 39 in the three
dedicated files, plus about 16 scattered through `tests/test_cli.py`,
`tests/test_validate_spec.py` and `tests/test_scout.py`. Two
subcommands removed from 19 — `flw stale` and `flw style check`. One devDependency,
`package.json` and `node_modules/` gone. Zero skips in a fresh clone's test run. One capability
moves from shipped to extensible: ranking a language other than Python becomes something a
project sets up once, in any language, instead of something only flw's author can add.
