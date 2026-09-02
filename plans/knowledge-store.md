# Knowledge shaped like code

A third prose store: what a system is built of and how its parts connect, written once by
an expensive survey, stored in the shape of the code it describes, stamped with the
revision it was true at, and corrected one file at a time. Design with diagrams, worked
sessions and man pages: `https://claude.ai/code/artifact/0fdde36e-f460-4d23-aead-13579971bd5d`.
Reviewed 2026-09-02 (`.flw/reports/2026-09-02T1136-knowledge-design.md`, six findings, all
folded). This file is what `flw-spec` reads; the artifact is what a person reads.

## What it is for

One expensive read of a system — the compose file, one transaction traced end to end,
the literals two repos both hardcode — paid once and reused by every later session. A
later session updates what it finds wrong cheaply and never re-runs the survey.

**The bar.** Knowledge is architecture: what the parts are, what each is for, what crosses
between them. Not measured trivia — "the language server misses callers through dynamic
imports" is a `flw kb` note, not knowledge. A store that takes everything is read by nobody.

**The test a file must pass.** It earns its tokens only by removing more code reading than
it costs. This is also the sparseness rule: a folder gets a file when reading it removes
reading, not when the folder exists. Prose in the skill plus a toy example; no guardrail.

## Three stores, one sorting question

| store | holds | wrong when | read |
|---|---|---|---|
| `.flw/extensions/` | conventions, rules | a human changes their mind | always, at opening |
| the knowledge store | architecture, edges | the structure changes | by location, on demand |
| `flw kb` | portable measured craft | rarely | by search terms |

**Does a commit make it wrong?** Yes → knowledge, stamped. Only a decision makes it wrong →
extension. Same line research already draws — records what IS, what MUST BE is the user's —
read one level down. Most of what research writes into `shared.md` today is knowledge under
this rule; extensions shrink to conventions, which is right for a file read at every opening.

## Shape

**One store per repo**, at that repo's `[knowledge] dir`, defaulting to `<flw dir>/knowledge`
and so already inside whatever the repo ignores once the flw directory is — research
proposes, the user confirms. Not committed for now; the config
key keeps the move cheap. The parent of a multi-repo system is a root like any other and
holds a store containing `system.md` and nothing else.

**The store mirrors the code.** A directory `D` at path `P` gets `<store>/P/D.md`; a
directory holds the file describing itself plus subdirectories for its children. The one
exception is the store root, named for what it is: `system.md` at the parent,
`<repo-basename>.md` in a repo. Reserved and never a concept, per OKF: `index.md`, the
generated listing.

**Four levels.** System (the parent, only with several roots); repo (what it owns, its
outward edges — the most valuable file); area (a folder that is a real unit — most of the
store, five to thirty per repo); module (a single file — rare, usually zero). `type` names
the level; the file's position says the same thing, and `--check` reports a disagreement.

**Sparse.** A repo of 1,800 files gets perhaps forty knowledge files. Missing is normal.

## Format

OKF-shaped, TOML-serialised. The Open Knowledge Format v0.2 (Google Cloud, Apache 2.0)
prescribes a directory of markdown with frontmatter, path as identity, `type` and
`description`, `index.md` and `log.md` reserved, links as the graph — all structure, none
of it syntax. flw keeps the structure and writes the frontmatter as `+++` TOML, the dialect
the note store already uses, read by `core/scripts/store.py`'s `_frontmatter` with
`tomllib`. No second dialect, no new parser. If OKF tooling ever matters, flat keys plus
lists of flat tables convert to YAML mechanically.

```toml
+++
type = "Repository"          # required: System | Repository | Area | Module
description = "one or two sentences — the head; nothing longer is printed by a listing"
revision = "4a91c2e"         # required; opaque, from the declared command
measured = "compose up, one POST, read ui's console"   # optional, wanted

[[connects]]                 # optional, free text, one table per outward edge
to = "ui"                    # a node name — a repo basename, or basename/area-path
how = "http"
carries = "OrderStatus enum"
+++
Body: the architecture in prose. Every edge above also appears as a markdown link here,
inside this store; an edge to another repo is text, never a path into a sibling.
```

Five fields, three required. `type` restates position — accepted because OKF names it;
`flw know --check` reports a disagreement. OKF's `stale_after` is not used: time cannot
know whether anything changed.

Malformed frontmatter is handled as the note store handles it: the file reads as body with
no frontmatter and `--check` reports it; nothing raises. Missing `type` or `description` is
reported and the file left out of listings and orientation; missing `revision` is
`unstamped` and read normally; a file that is not UTF-8 is `unreadable`, reported by
`--check` and skipped by the walk and the fold, as `store.walk` already does for notes.

## Reading it

Nothing is printed at any skill's opening. `flw context` prints no knowledge, deliberately.
Orientation is a command a skill runs when it needs one.

**Three tiers.** Orientation — system and repo descriptions and edges, one line per repo,
where most work stops. Heads — one area's description and edges, enough to decide whether
it is involved. Bodies — the prose, opened only where the change lands. The four-repo
toggle: four summaries, two bodies, zero code files opened before knowing where to look.

**The walk**, for repo root `R`, store `K`, path `p` relative to `R`:

```text
candidates(p):
  if p is a file:                yield K/p + ".md"          # module level, rare
  for each ancestor P/D of p, nearest first:
                                 yield K/P/D.md             # area level
  yield K/basename(R) + ".md"                               # repo level
walk(p)  = [c for c in candidates(p) if c exists]           # missing is normal
print(p) = reversed(walk(p))                                # outermost first
```

A `p` outside `R` or absent from the code is exit 1: a typo, or a rename that already
orphaned its knowledge.

**Resolution.** A store belongs to a root, resolved as `flw context` resolves one. A repo
with no `[project.roots]`: its own file. A parent with `[project.roots]`: `system.md` plus
each member's repo file from that member's store. A member, standing inside it: its own file
only — no reverse lookup, drive from the system root with `--root <parent>`, the consequence
`multi-root-projects.md` §5 already accepted.

From a parent, a `PATH` under a declared member walks that member's store rooted at the
member and ends at `system.md`; a `PATH` under no member is exit 1. `--check` and
`--reindex` from a parent cover `system.md` and every member's store. A root with no
`[knowledge] dir`, or a `dir` not on disk, prints `no store` and exits 0 — a state, not a
fault, the reading `flw context` already takes — so a skill may run `flw know` on every
run without guarding it.

**Search.** `index.md` to descend, grep over `description` to find, `flw map` for edges.
No embeddings: the corpus is a few thousand tokens of summaries, so grep returns
architectural units rather than lines. The sparseness rule is what makes this the whole
answer.

**Where each skill enters.** Spec has no path — orientation across the declared roots, then
heads. Execute has the record's paths — walk up, bodies where the work lands. Review has a
diff — walk up from changed paths.

## Staleness

Any change under the mirrored path since the recorded revision, quantified. Git only for
now — it is what is used where this first runs; another VCS means two commands become
config keys later, not a design change.

A file records `revision = "<git rev-parse HEAD>"` when written or stamped. A check runs
`git diff --numstat <revision> HEAD -- <path>` in that file's repo: no output is `current`;
any output is `changed`, with files, insertions and deletions summed from the numstat lines
— the reader's proxy for how much could have moved. There is no classification: a
function-body edit and a new directory both count, and the numbers say which it was.

```text
services/order/order.md    area   8be0117   changed since: 3 files · +41 −12
backend.md                 repo   1f4ac02   changed since: 38 files · +2,410 −611
```

`system.md` sits in a parent that is not a repo and spans several that are. It carries one
hash per member, keyed by the member's directory basename and matched to `[project.roots]`
by value — `revision = { backend = "1f4ac02", ui = "3c81d90" }` — and is checked in each
member's repo and reported per member.

A walk checks what it prints; orientation does not (a repo file mirrors `.`, and diffing
the whole tree per orientation is the one slow case); `--check` does all. A diff that fails
— not a git repo, a hash gone after a rebase — is `unverifiable`, read normally: a warning,
not a passed check.

**Orphans need no VCS.** A concept file whose mirrored path no longer exists is listed with
the path it expected. This is the rename case, and it is a `stat` per file.

**`--stamp PATH…`** rewrites `revision` in the named files to the current HEAD of their
repo, per member for `system.md`, keyed by the member's directory basename. Re-stamping is:
re-read the file against the code, then `--stamp`. One command, hard to skip. Three edges,
each decided: a file with no `revision` gets one inserted at the end of its block, and a
file with no parseable block is refused with the path named; a stamp whose `rev-parse`
fails changes nothing and exits 1 naming the path; in `system.md`, a key naming no declared
member is reported by `--check` and left alone by `--stamp`, and a declared member with no
key is `unstamped` for that member and `--stamp` adds it.

**Changed warns; it never stops.** The agent in front of the number decides.

## Writing

Research populates: parent pass first (topology, shared literals, one trace), then per
member. Written to disk and reviewed per level, not shown in one block. `--reindex` at the
end.

Execute re-stamps, at each phase boundary, the files whose paths this phase changed —
re-read, then `--stamp` — because a run that builds something has falsified the file
describing that part. This is the commoner trigger.

Any skill may correct one file it finds wrong and re-stamp it. One sentence in each
`SKILL.md`, not a rule in `context.md`, because a permission in the shared file reads as
permission to write anything.

`index.md` is written only by `flw know --reindex`, and **nothing may trust it** — a
consumer that doubts one reads the directory, as OKF permits. A stale listing costs a reader
one directory read.

A seam under design is not knowledge — it does not exist yet. A cross-repo change gets one
plan at the parent, cited by path in every record's `approach`, reviewed before any repo
executes. When it lands, the seam moves into the repo-level files.

## Commands

Two, not one. Both use exit 0 and 1 only; 2 stays scoped to `flw test` and `flw validate`.

```text
flw know [PATH] [--root DIR] [--full] [--check | --reindex | --stamp PATH…]
  no PATH      orientation
  PATH         the walk, heads only; --full for bodies
  --check      changed, orphaned, malformed, unstamped; writes nothing; exit 0 even when
               everything is changed
  --reindex    rewrite every index.md
  --stamp      write the current HEAD into revision for the named files; per member for
               system.md. The two modes that write.
  exit 0       whenever it ran, `no store` included; exit 1 for an input it could not
               use — no root, a PATH not in the code or under no member, --full or
               --stamp without a path

flw map [NODE] [--root DIR] [--format text|mermaid|dot]
  folds connects: from every file under the root; NODE restricts to edges touching it,
  both directions; a target no file describes is counted, not hidden
```

Output samples, options and examples: Appendices A and B of the artifact.

## Samples

What the commands print, in the shape the tests hold them to. The three-store fixture is
the toy example at `core/skills/flw-research/references/knowledge-example/`: a parent
`acme` with members `shop` and `worker`.

```text
$ flw know                                      # from the parent

system: acme · 2 roots · ~/work/acme/.flw/knowledge/system.md
  One shop, one worker. The shop takes orders over HTTP; the worker
  fulfils them from a queue the shop writes.

  shop      Serves the storefront and the order API. Writes each order
            to the fulfilment queue.
            → worker (queue, Order)
  worker    Drains the fulfilment queue and marks orders shipped
            through the shop's API.
            → shop (http, OrderStatus)

2 repo files, each in its own repo's store · 0 changed

$ flw know api/orders.py --root shop            # a walk

shop · api/orders.py · 2 of 3 levels have knowledge

  shop.md                    repo   1f4ac02   current
    Serves the storefront and the order API. Writes each order to the
    fulfilment queue.
    → worker (queue, Order)

  api/api.md                 area   8be0117   changed since 8be0117: 3 files · +41 −12 · e.g. api/orders.py
    The order API. OrderStatus is a string enum that crosses to the
    worker unchanged.
    → worker (queue, Order)

2 files · 1 changed · --full for bodies

$ flw know --check                              # from the parent

knowledge: 2 roots, one store each · 4 files

  acme      system.md                  current     shop 1f4ac02 · worker 3c81d90
  shop      shop.md                    current
  shop      api/api.md                 changed     3 files · +41 −12 · since 8be0117
  worker    worker.md                  unstamped

4 files · 1 changed · 1 unstamped · 2 current · 0 orphans

$ flw map                                       # from the parent

acme · folded from 3 concept files

  shop        ──queue──▶   worker
  shop/api    ──queue──▶   worker
  worker      ──http──▶    shop

3 edges · 3 nodes

$ flw map worker

  in    shop      ──queue──▶  worker
        shop/api  ──queue──▶  worker
  out   worker    ──http──▶   shop

changing worker's inbound contract touches: shop, shop/api
```

## Config

```toml
# <repo>/.flw/config.toml
[knowledge]
dir = ".flw/knowledge"       # the only key, defaulting to <flw dir>/knowledge — the
                             # flw directory being .flw/ unless [paths] flw or $FLW_DIR
                             # says otherwise (the flw-dir-setting record). Git is assumed.

# <parent>/.flw/config.toml — the project-roots record, not this one
[project.roots]          # a map, not a list: multi-root-projects.md:168
be = "./backend"         # the knowledge store reads the values only; node
ui = "./ui"              # names are directory basenames
```

## Skills

| file · section | gains |
|---|---|
| `context.md` · new section | the three stores and the sorting question; the walk-up; that `flw context` prints none of it |
| `flw-research` · §1 | with roots declared, survey every member, parent first; the parent gets a `shared.md` as well as `system.md` |
| `flw-research` · §4 | the tree, per level; sparseness sentence; `--reindex`; the toy example at `references/knowledge-example/`; a note in kb's repo root that describes how the system is built moves to the tree |
| `flw-spec` · amend step 3 | orientation, heads for the parts named, `flw map <node>` at a seam; a cross-repo change gets one plan at the parent |
| `flw-execute` · §2 | `flw know <path>` per path the record names; the plan the record cites |
| `flw-execute` · §3 | re-read and `--stamp` the files whose paths the phase changed, then `--reindex`; the report lists them |
| `flw-review` · §3 | the orchestrator passes `flw know` heads for the scope as an eighth thing |
| all four | one sentence: a skill that finds a file wrong may rewrite and re-stamp it |

## Records

1. **project-roots** `-minor` — `[project.roots]` as a map; `flw context` prints members
   under `root:` with whether each exists; `flw doctor` one line per member. Not the
   member-prefixed contract paths; the rest of Part B stays unbuilt.
2. **knowledge-store** `-minor`, four phases — the toy example first, because it is the
   three-store fixture every later test reads; the module `core/scripts/knowledge.py`
   (walk, the git diff runner and its summing, orphan check, stamp, listing writer, fold;
   frontmatter through `store.py`'s reader; pure functions, tests alongside); the two commands, each declaring its surface line in
   the contract in the same step as its parser; the prose in the table above plus the toy example; the
   contract — a new component `the knowledge store` with paths `core/scripts/knowledge.py`
   and `tests/test_knowledge.py`, its format and config keys as `surfaces`.
3. **declaration-records** `-minor`, independent — one sentence in `flw-execute` §1: a
   record whose `approach` declares existing code is expected to be built; run its checks,
   apply the edit, append to `applied`. This is the promotion path for a repo that starts
   from a feature-scoped first contract.

## Tests

Git calls go through one function that tests replace with a fixture returning canned numstat
output or a failure; no test runs git. Walk order and
misses; malformed frontmatter reads as body and is reported, missing required fields are
reported by name; no output → `current`, any output → `changed` with the right sums, a failing
diff → `unverifiable`, `system.md` checked per member; `--stamp` rewrites only `revision` and
only in named files; orphans per file after a directory
rename; `--reindex` shape and idempotence; the fold against a three-store fixture, `NODE`
both directions, undescribed targets counted; each resolution row; the existing two-way
surface drift test picks up both subcommands.

## Decided

- stale warns, never stops — the agent decides
- edges are free text; structure encouraged, not enforced
- sparseness is prose plus a toy example; no cap, no linter
- what changes when the store is committed is deferred
- two commands, not one
- one store per repo, mirror rooted at the repo, parent holds `system.md`
- OKF field names; `revision`, `connects`, `measured` as extensions
- `+++` TOML frontmatter read by the note store's reader — OKF-shaped, not OKF-conformant
- `flw kb` stays a separate store; the frontmatter reader is shared code, nothing else is
- any change under the path counts, quantified as files and lines; no classifier, no globs
- git only for now; another VCS is two config keys later
- `log.md` dropped; no `structural` default and no `structural` key at all

## Not built, on purpose

Full Part B — one contract across several roots, member-prefixed component paths, and the
coordinated retraction a seam change after one repo landed would need. `flw seam`. Vector
search. Ambient printing of any of this.

**The doubt carried forward.** With `index.md` generated and every edge a body link, a
reader with no flw installed has orientation and the graph. Both commands are conveniences
over a store that is already readable, and neither has been measured against reading the
files directly.
