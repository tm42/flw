### What a skill reads, and from where

Written 2026-09-01, from field feedback on a six-repo work setup where sessions start in the parent directory holding
the checkouts and that parent is not itself a repo. It follows `plans/multi-repo-orientation.md` (2026-08-25) and
settles the question that plan left open in §6.4 — *"decide whether flw acquires a multi-root project shape"* — rather
than restating it.

Four gaps, one subject. Everything here is about what a skill or an agent loads at the start of a piece of work, and
which directory it loads it from.

1. **The root is discovered, never given.** A session rooted at the parent resolves every skill to the parent, while
   the task plainly names a child.
2. **Extensions do not compose, and they are locked to skills.** Nearest wins with no merge, and a convention shared
   by all four skills has to be written four times or read by one.
3. **Nothing loads context outside a skill invocation.** Work flw has no skill for gets no extension, no note store
   and no contract.
4. **Nothing crosses a repo boundary.** No project shape spans roots, no command finds seams, and the note store's
   project half is scoped to one root.

The order matters more than the list. The first two are prose and small code; they make the third cheap and the fourth
several times cheaper.

---

## Part A — the reading surface

### 1. How resolution works today

`nearest_project()` (`cli/flw.py:1976`) walks up from a starting directory and returns the first one holding `specs/`
or `.flw/`. It stops at `$HOME`, because `flw install` writes `~/.flw` — without that guard every home directory looks
like a project, and `flw scout` once walked all of `$HOME` into a network mount and hung.

`core/shared/context.md` states the same rule in prose, and *that sentence* is what the four skills act on. There is
no code path a skill goes through: it reads a file at a path it computes from that sentence. Which means changing how
skills resolve a root is a prose edit — no code, no schema, no release.

**Commands already take a path, inconsistently.**

| command | with an explicit path | where |
|---|---|---|
| `flw scout <path>` | that directory, literally; documented as *"you scout a tree, and `flw scout ./` must not walk upward"* | `cli/flw.py:2241` |
| `flw test <path>` | walks **upward** from it, so a directory with no `.flw/` is answered by an ancestor | `cli/flw.py:2007` |
| `flw validate <target>` | explicit targets, no walk | — |
| `flw doctor` | install-scoped; its extension report uses `nearest_project()` and takes no path | `cli/flw.py:1506` |

`flw test` prints `root:` on every run for exactly this reason.

**What merges.** Config merges on one axis: `_local_config()` (`core/scripts/run_tests.py:122`) reads
`~/.flw/config.toml` as an underlay beneath the project's, key by key. That is machine scope, not directory scope.
Extensions merge on none. Checks already fan out, because `[tests] checks` is a flat list of shell commands each run
in its own shell at the project root, so `cd ds && make test` works today.

### 2. Change 1 — the root is an input

**The commands mostly have it.** The one gap is `flw doctor <path>`, so the extension report can be aimed at one repo
while driving from the parent. `flw test`'s upward walk from an explicit path should **stay**: it exists for
`flw test src/` inside a project, which is a normal thing to type and would start erroring. Record it as a deliberate
difference from `scout` so nobody fixes it later.

**The skills have nothing.** One paragraph in `core/shared/context.md`, inherited by all four:

> **The project root is an input, not a discovery.** If the request names a repository, a directory or a file, the
> project root is the nearest directory at or above *that* holding `specs/` or `.flw/`. Only when the request names
> nothing does the walk start from `$PWD`. Say which root you resolved to, once, before doing anything with it.

**The rule the design hangs on: whoever resolves a root states it.** An agent that infers a root can infer wrongly,
and the failure is silent — work specced against the wrong contract reads exactly like work specced against the right
one.

**Rejected: an `FLW_PROJECT` environment variable.** It pins the root for a long session in one export, and it is
hidden state that outlives the task that set it — the next request names a different repo and silently gets the pinned
one. Stating the root per invocation costs one line and cannot go stale.

### 3. Change 2 — extensions chain, and stop being skill-only

Two changes to one mechanism.

**They chain by directory.** Read every `.flw/extensions/<name>.md` from the outermost project root down to the
nearest, in that order, so the nearest overrides. Contract and config stay nearest-wins: a contract is one document,
and concatenating two produces something nobody reviewed and nothing can validate.

**They stop being skill-only.** Reserve one filename — `.flw/extensions/shared.md`, matching the vocabulary
`core/shared/` already uses — read by every skill *and* printed by a bare `flw context`. Today a convention that
applies to all four skills must be written into four files or read by one; this is the same duplication the opening
steps have, and the same rule against it (design-v3 §17.2 rule 2, one mechanism per job).

**This does not weaken `flw doctor`.** `report_extensions` rejects any filename that is not an installed skill's name,
and the source says why: *"Only possible to catch because the filename is fixed — a configurable path could point
anywhere, so there would be nothing to compare against."* One reserved name keeps that property exactly; an unknown
filename is still read by nobody.

**Read order is a matrix.** For each level of the root chain, `shared.md` first, then the skill's own. Nearer level
beats farther, skill-specific beats shared. State it once and precisely, because it is easy to implement backwards.

**Why this also fixes Codex.** flw extensions are read by the *skill*, with its own file-reading tool, at a path the
skill computes. They never pass through the host's instruction loader, so whether Codex resolves nested `AGENTS.md`
is irrelevant to them. Doing the layering inside flw makes the behaviour identical on every host instead of inheriting
each host's answer.

**The limit.** An extension is read at a skill's opening step and nowhere else — which is what change 3 fixes, and why
`ambient.md` exists for the always-on layer (`plans/design-posture.md:66`).

### 4. Change 3 — `flw context`

The opening reads are duplicated prose across four `SKILL.md` files: `flw-spec` and `flw-execute` do three reads,
`flw-review` does two and deliberately skips the note store because it reviews nothing and hands the store to its
reviewers instead. Four copies of an instruction drift, and a command written as prose gets reconstructed wrongly —
flw's own stated reason for putting commands in config.

```text
flw context              # context.md, resolved root and chain, shared.md, kb listing, contract shape
flw context flw-spec     # the above plus flw-spec's own extension chain
```

**It prints `core/shared/context.md` first, as its preamble.** Without that the opening is still two calls and the
claim below is false. Say it explicitly, because the naming invites the mistake — an opening step that reads
`core/shared/context.md` *and* runs `flw context` has two different things called context in one paragraph.

**"Contract shape" is component names plus their `paths`, and nothing else.** Measured on flw's own contract: names
plus paths is ~163 tokens, names plus paths plus `provides` is ~3,011, the whole file 7,829. The narrow reading is
what makes an always-available invocation affordable, and a skill needing a component's `provides` reads the
contract itself.

**`flw context flw-review` omits the kb listing.** `flw-review`'s opening deliberately skips the note store, because
a read there is paid by the one context that produces no findings and reaches none of the ones that do. A command
printing it unconditionally erases that. One special case, stated here rather than discovered later.

One call replaces three. It is testable, host-independent, and its printed root header makes *"say which root you
resolved to"* mechanical rather than a rule an agent must remember. The extension chain and the note-store chain
become implementation details instead of instructions someone has to follow correctly.

**Bare `flw context`, with no skill named, is the answer to gap 3** — orientation for work flw has no skill for.
Three things invoke it: the four skills' opening steps, you typing it, and one line in `ambient.md` — **conditional,
not unconditional.** Ambient is installed into the host's top-level instructions, so it is always on and pays on
every session; the line says *run `flw context` before working in a flw project*, never *run it at session start*.

**Command first, skill maybe never.** `flw-prepare` as a fifth skill costs a ~4k-token `SKILL.md` loaded in every host
and one more document to keep from drifting. Do not pay that before knowing what judgment it holds that the command
does not. The lane is right, though — `flw-research` *writes* config and extensions, recording what is; this reads
what was recorded, and they are not the same skill.

**`context` beats `prepare` as a name** for the same reason flw rejects "harden" in a commit subject: it names what
the thing produces, not an intention.

---

## Part B — the project shape

### 5. Change 4 — one project, several roots

The project directory holds `specs/` and `.flw/` as today. Its config names its members:

```toml
[project.roots]
ds = "../datastore"
rt = "../runtime"
tl = "./tooling"       # a child is fine, just not required
ui = "./ui"

[tests]
checks = [
  "cd ds && flw test",   # delegate: run whatever ds declares for itself
  "cd ui && npm test",
]
```

A map, not a list, because the name is used in contract paths. Values are relative to the project directory; absolute
is allowed but discouraged.

**The hard part is not the declaration.** Standing inside `../datastore`, nothing reachable by walking upward says it
belongs to a project somewhere else.

| approach | cost |
|---|---|
| back-pointer — the member's config names its project | two files that can disagree; drift is the default outcome |
| registry — `~/.flw` records memberships | machine-local state describing repo content; breaks on a fresh clone |
| **no reverse lookup** — you drive from the project root | free, because change 1 already requires the caller to state the root |

**Take the third.** This is the reason to land change 1 first: it does not merely precede multi-root, it removes most
of its difficulty. The consequence to accept knowingly is that bare `flw test` inside `../datastore` gets datastore's
answer, not the system project's — correct, not a limitation.

### 6. What it does to each artifact

**Component paths gain a member prefix.** Components already carry path lists relative to the project root
(`["cli/"]`, `["core/skills/", …]`). Under `[project.roots]` the first segment is a member name and resolves through
the map: `["ds/api/routes.py", "ui/src/api/configs.ts"]`. This converges with the seam table
`multi-repo-orientation.md` §3 sketched months earlier using exactly those `ds/` `rt/` `tl/` `ui/` prefixes — designed
independently, wanting the same notation. It also keeps `flw-review`'s narrowed dispatch working unchanged, since
intersecting a scope with a component's `paths` is still string prefixes.

**Checks delegate rather than restate.** `cd ds && flw test` runs whatever `ds` declares for itself, so a member's
checks live in one place and the system project never carries a stale copy.

| thing | effect |
|---|---|
| `flw validate` | none — one contract and its records, however many roots |
| `flw scout` | stays single-root; six invocations with explicit paths, ~1s and zero tokens each |
| `flw doctor` | grows most: the extension chain per level, plus one line per declared root saying whether it resolves |
| `flw kb` | see §7 — categories already work, the project note root does not |

---

## Part C — knowledge and the map

### 7. The knowledge system

**Two stores, deliberately disjoint**, and `flw kb`'s own help says so. `flw ledger` reads the contract, the version
records, the review team configs and `plans/*.md` — everything agreed or reviewed. `flw kb` reads unvalidated notes,
under two roots: `~/.flw/kb/` follows the machine, `<project>/plans/notes/` follows the repository. Every kb surface
prints age and size, because a note is a hint to verify rather than a fact to act on.

**The map adds a third kind of artifact, so the sorting rule for cross-repo work is:**

- **re-greppable → fixture.** The seam table. `file:line` on both sides and a command that rechecks it.
- **measured and not re-derivable → kb note.** *"The LSP returned 1 of 8 real callers for a symbol reached through
  `sys.path.insert` plus a dynamic import."*
- **agreed → version record.** *"The system contract holds seams only."* It has a rationale and belongs in
  `decisions`.

**Multi-root breaks one half of the store.** Categories are fine with no code change: `-c` is a prefix match, so
naming them `work/ds` and `work/rt` means `-c work` sees all six and `-c work/ds` sees one. The project note root is
not fine: `roots(flw_home, project_root)` (`core/scripts/store.py:192`) takes one project root, so a note written
inside `ds` lands in `ds/plans/notes/` and is invisible from the system project. It needs the same chain the
extensions need, and should land in the same change.

The stopgap until then is writing cross-repo notes machine-wide. They are visible everywhere; they also follow the
laptop rather than the repo, so a colleague cloning gets nothing.

**Where the built-in host memory fits, for non-engineering work.** They are not competing.

| | flw kb | host memory |
|---|---|---|
| loaded | on query, one command | automatically, every session |
| scope | machine-wide, all projects, all hosts | one project directory, one host |
| holds | measurements | who you are, preferences, guidance |
| has | categories, tags, search, age and size | a flat index and links |

The dividing question is **did I measure it, or do I prefer it.** *"lazy.nvim over packer, because the config stays in
one file"* is memory. *"nvim 0.11's `vim.lsp.config` silently ignores a `cmd` that is not a list — three servers
failed to start with no error"* is a kb note in category `nvim`. kb's write gate rejects the first outright: it wants
what was measured, because a conclusion goes stale silently and a measurement does not.

The tiebreaker for anyone working across hosts: host memory does not travel to Codex, kb does.

### 8. The multi-repo map

Three layers, three mechanisms, because they have different costs and different lifetimes.

| layer | how | stored |
|---|---|---|
| topology | agent reads compose, k8s manifests, CI, `.env.example` — ~15 files | no |
| seams | `flw seam` prints candidates, agent classifies direction | yes, as a fixture |
| internals | `flw scout <root>`, once per repo | never |

**Topology cannot be a command:** flw is stdlib-only and the stdlib has no YAML parser. It stays a probe list in
`flw-research`, and for N>1 roots it runs *first* — "what talks to what" has to be settled before "what is central
here" is a well-posed question per repo.

**`flw seam` finds candidates and stops.** Index string literals of four or more characters plus SCREAMING_SNAKE
identifiers per root; keep those appearing in at least two roots and not in all of them; rank by rarity times shape
(leading `/`, dotted path, snake_case table-like). Report co-occurrence only — **do not classify producer versus
consumer.** Direction requires knowing what a route decorator means as against what a fetch call means, that is
language-specific, and flw commands are language-agnostic on purpose. The agent turns candidates into rows.

String matching rather than parsing is the point: it covers Go, Rust, SQL and YAML on day one, while scout's import
ranker is Python and TypeScript and will stay that way. The heterogeneity that makes scout weakest on a six-repo
system is what a literal matcher is indifferent to.

**Why the table is stored when scout output is not.** The AGENTS.md A/B result (N=438) says static prose overviews of
a repo the agent can already see lose to grep. A seam row is not that: the other repos are outside the root being
reasoned about, so no local operation derives it, and re-deriving costs 15–30 tool calls instead of one. And a row is
machine-recheckable — `--verify` re-greps every row and fails when a side has vanished. It is a fixture, closer to a
golden file than to a repo map.

**How this gets used.** Six `/flw-research` runs today, one per repo, plus `flw scout` per repo: that is the
internals and the how-this-place-works layers, and it works now. The cross-repo layer becomes **a seventh
`flw-research` run at the system project** — the same lane, because research records what *is* and a seam map is a
fact rather than a decision. It needs `[project.roots]` to have somewhere to write, the §6.1 and §6.2 prose edits
(the trace, deployment topology, cross-repo commit correlation — its probe list has Makefile, justfile, CI, manifests,
tox and CONTRIBUTING and *no compose or k8s*), and `flw seam` for the candidates. No new skill.

### 9. Two contracts, not one

The obvious reading of "one project spanning six repos" is that six repos get one contract. That is wrong here, and
the distinction matters more than the mechanism.

- **A repo contract** describes that repo: its components, its surfaces, its checks. Most changes are one repo's, and
  `nearest_project()` from inside it finds it with no configuration at all.
- **A system contract** describes the **seams**: edges between members, shared literals, version skew between
  generated clients. Its components cross roots, its paths are member-prefixed, its checks re-grep edges and delegate
  the rest.

They do not overlap, because a system contract that restates a member's internals duplicates a document that already
exists and will drift from it. Keeping it to seams is what makes two contracts coherent rather than contradictory —
the same discipline as `provides` being what a *user* can do rather than what a class is.

`multi-repo-orientation.md` §6.4 asked whether the honest unit is the repo or the system. The answer is both, at
different scopes, and the seam is the line between them.

---

### 10. Edge cases

**Resolution**

- **A member lives at `~/repo`.** The upward walk breaks at `$HOME` before testing it. Not a new bug, but declared
  members make it reachable, because the project points at the member directly instead of walking to it.
- **The agent picks the wrong root.** A request naming two repos, or a file that exists in three. Nothing prevents
  this; printing the root is the only mitigation, which is why it is a rule.
- **`flw test src/` inside a project** still walks up, still works — the reason `flw test`'s walk is kept.
- **Relative member paths resolved from the wrong base.** `ds = "../datastore"` is relative to *the project
  directory*, never to `$PWD`. Implementing it from the current directory works whenever you happen to be standing in
  the right place and silently points elsewhere otherwise. The most likely implementation bug here.
- **Absolute member paths** break on clone, and fail as a missing directory rather than an error anyone reads.
- **A member is a symlink.** `resolve()` follows it, so two declared names can land on one directory — harmless for
  reading, a duplicate in any fan-out.

**Extensions and context**

- **Parent and child disagree.** Nearest wins, matching the config underlay; both are read, only the conflict is
  overridden.
- **An extension tries to waive a Rule.** It cannot, at any level. `context.md` already says so — and a file that
  looks global is more tempting to use for exactly that.
- **A deep tree makes a long chain.** Three or four files per skill invocation, all paid in tokens every time. No cap
  is proposed, because a cap that silently drops the outermost file is worse than a long chain; doctor printing the
  chain is the pressure valve.
- **`shared.md` has no owner, so it grows.** A file every skill reads and no skill is responsible for is the natural
  dumping ground. Doctor printing its size is the cheapest brake.
- **`shared.md` gets confused with `ambient.md`.** Ambient is always-on, host-installed and per-machine — how you work
  anywhere. Shared is per-repo and loads on demand — how *this place* works. They will blur unless written down.
- **The read-order matrix implemented backwards.** Shared beating skill-specific, or farther beating nearer, produces
  a chain that looks right and applies the wrong rule.
- **`flw context` in a project with no contract.** Local checks and no `specs/` is a normal supported state; the
  command must print what exists and say what does not, never error.

**Multi-root**

- **A member declares nothing to run.** `cd ds && flw test` exits 2 — the run proved nothing — which the parent reads
  as a failed check. That is the right reading.
- **Bare `flw test` inside a member** runs the member's own checks, not the system's. Correct, and it looks like a bug
  the first time.
- **A member belongs to two projects.** Nothing prevents it, since membership is read only from the project side.
  Either a feature or an unnoticed way to have two contracts claiming the same files. Untested.
- **A declared member is missing.** Every path through it resolves to nothing and a review scoped to it comes back
  empty, which reads exactly like a clean review. Doctor must fail on this, not warn.
- **A single-root project has a directory named `ds/`.** Then `paths = ["ds/"]` is ambiguous between a member prefix
  and a plain directory.
- **A reviewer's scope.** Under multi-root it must be member-qualified, or two members with a `src/api/` each produce
  a review of the wrong one.
- **A note written inside a member** lands in that member's `plans/notes/` and is invisible from the system project
  until the store's project root chains.

---

### 11. Order of work

**Part A — the reading surface.** Small, and each leaves the tree working. Steps 2 and 4 are one change split
across two commits rather than two independent ones: step 2 is inert for the skills by design, and step 4 is what
makes it live.

1. **The root-as-input paragraph** in `core/shared/context.md`, plus "say which root you resolved to" in each skill's
   opening step. Prose, no code, no schema. Fixes the reported failure on its own.
2. **The extension chain and `shared.md`, in code only.** `project_chain()` beside `nearest_project()`, one
   reserved filename, `report_extensions` walking the chain and printing sizes, tests, one contract edit.
   **No `SKILL.md` is touched here.** The chain exists, doctor reports it, and the skills go on reading the nearest
   extension until step 4 switches them over in one move. Writing the read-order matrix into four openings as prose
   would be writing something step 4 deletes — and worse, `nearest_project()` stops at the first hit, so a skill
   executing a chain in prose has to walk above its own root itself, at every open, in all four skills, until the
   command lands.
3. **`flw context [skill] [path]`.** Declare the surface line in the CLI component at spec time, not after the work —
   flw's contract claims its own surface is complete, so a version that waits deadlocks against its own check. It
   happened on 4.2 and again on `knowledge-base`.
4. **The four opening steps call it**, plus the conditional line in `ambient.md`. This is the only edit the four
   `SKILL.md` files take, and it replaces their opening reads rather than adding to them.
5. **`flw doctor <path>`.** A few lines, and it makes 1–4 checkable from the parent.

**Part B — the project shape.**

6. **`[project.roots]`** — config schema, member-prefixed paths, doctor's per-root line, the note store's project root
   taking the chain, and §9's decision written into whichever contract gets it. The only real work in this document.

**Part C — the map.**

7. **`flw-research` §6.1 and §6.2 prose edits** — the trace, deployment topology, cross-repo commit correlation.
8. **`flw seam`** — candidates across N roots, plus `--verify` re-grepping a recorded table.

---

### 12. Still undecided

- **Whether a member may belong to two projects.** Allowed by construction. Feature or silent double-claim, and there
  is no evidence yet.
- **Where `[tests] yours` belongs.** A check that cannot run on this machine is machine scope today. Six members give
  six other places it could be declared, and no data on which one people reach for.
- **Whether validation should check member prefixes.** `flw validate` could refuse a path whose first segment is not a
  declared root, catching a renamed member immediately — or it could be noise for a single-root project. The schema
  has to distinguish those cases first.
- **Whether `flw context` prints extension contents or paths by default.** Contents is one call instead of
  several; paths is fewer tokens when a skill already holds the file. Now a question about the extension files alone:
  `context.md` is settled as the preamble and contract shape as names plus paths. Probably contents with a `--paths`
  flag, but it should be measured rather than guessed.
- **Whether `shared.md` needs a declared size cap**, or whether doctor printing its size is enough pressure.
- **Whether `flw-prepare` ever becomes a skill.** Only if steps 1–5 leave judgment unclaimed.
- **Whether the duplicate-literal seam method works at all.** Carried forward unresolved from
  `multi-repo-orientation.md` §7 — a design sketch, never measured. A six-repo setup would be its first test.
