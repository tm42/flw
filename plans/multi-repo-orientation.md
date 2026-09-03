### Orienting across several entangled repos

Written 2026-08-25. The shape this is written for: several repos that form one system — a datastore backend, a
runtime image, a tooling backend that pulls from the runtime, and a UI that configures the runtime, writes to the
datastore, and displays results. Four is the worked example; any system with those boundaries has the same problem,
whatever its repos are called. The question is how an agent comes to understand them *as a system*, what flw
contributes today, what the agent does unaided, and what neither covers.

---

### 1. What Claude Code gives natively

No persistent index, per-session or otherwise. The whole native inventory:

- `--add-dir` / `/add-dir` — extra roots in one session. `claude --help` notes these contribute their `CLAUDE.md`
  files too. Each added root may raise a trust prompt.
- The `CLAUDE.md` hierarchy plus `@path` imports — the only durable cross-repo memory, and it is prose you maintain
  by hand.
- The `LSP` tool — `goToDefinition`, `findReferences`, `workspaceSymbol`, `incomingCalls`. Scoped to a configured
  language server and effectively one workspace; it does not cross an HTTP boundary and does not reliably span
  added directories. `flw-research` §3 records a measured 1-of-8 recall on a symbol reached through a dynamic
  import.
- The `Explore` subagent, `Grep`, `Glob`, `Read` — re-derived from scratch every session.

Every session pays full re-orientation cost. That is the state of the art, not a gap being worked around.

---

### 2. What flw has today

**`flw scout`** — `core/scripts/scout.py` (stdlib `ast`) and `core/scripts/scout.mjs` (loads `typescript` from the
target repo's own `node_modules`). PageRank over the resolved import graph, damping 0.85, iterated to a tolerance of
1e-6 scaled by 1/n, capped at 200 iterations as a non-settling-graph backstop. Roughly 85–90% of imports resolve;
`sys.path` manipulation and dynamic imports do not and never will. Nothing is cached and nothing is written.

Sections it prints: `ENTRY POINTS`, `BUILT ON` (product code only — counting test dependencies puts the test runner
on top), `PACKAGES`, `DEPENDS ON` (package-to-package with import counts), `CYCLES` (Tarjan SCCs between packages),
`MOST DEPENDED ON` (files ranked, with the names other files import from each).

Design decisions worth carrying into any successor:

- **Rank over imports, not name references.** Name-reference ranking surfaced a pytest fixture, `close()` and
  `_utcnow()` on a real repo, because `.get()` on a dict is indistinguishable from a call to your class's `get`.
- **Resolve an edge to the file that *defines* the imported name**, never through the module specifier — so a
  re-export barrel takes none of the score passing through it. This is a partial answer to the barrel problem that
  every off-the-shelf indexer leaves open; it fixes ranking, not bundling or side-effect ordering.
- **Exclude vendored code** using github-linguist's `vendor.yml` patterns. Measured need: a vendored copy of
  `tomlkit` took half the top ten, because a library's modules import each other heavily and that looks exactly like
  a well-factored core.
- **A package is a directory declaring itself one** — `__init__.py`, `pyproject.toml`, `package.json`; the repo root
  is not a candidate. `parts[0]` reported every service of a monorepo as one node.
- **Adopt no off-the-shelf indexer.** Serena took ~11h on LLVM's 7,749 files; CodeGraph OOM'd at 44% on 137k files.
- **Persist the command, not the output.** One published A/B test (Evaluating AGENTS.md, N=438) found static prose
  repo overviews do not help and LLM-generated ones slightly hurt.

**`flw-research`** — reads how a repo actually works and writes it into that repo's own flw configuration, under one
rule: *code reads it → `.flw/config.toml`; an agent reads it → `.flw/extensions/<skill>.md`*. A command written as
prose gets reconstructed on every run and drifts; a command in config is run, not remembered.

**The limits, both documented in flw's own text:**

- Scout is single-root by construction. `cli/flw.py:1699` deliberately does not walk upward for an explicit path.
  Four repos means four invocations and four unrelated maps.
- A third language is invisible rather than degraded — the `scout` parser's description (`cli/flw.py:1919`) says a Go
  service in a mixed monorepo produces no edges at all while the header confidently counts the others.
- `flw-research` §2 states the seam problem outright: "a service that calls another over HTTP has no import edge, so
  the boundary between two services is invisible to the scout and it will report them as unrelated," followed by the
  grep list — route decorators, request and response models, generated OpenAPI or protobuf, client wrappers built
  around another service's base URL.
- `nearest_project()` (`cli/flw.py:1588`) resolves to the first `specs/` or `.flw/` at or above cwd, so one project
  is one root. Four repos either get forced under a common parent or get four disconnected research runs with
  nothing joining them.

**The workaround that needs no code change:** put the four checkouts under one parent, `.flw/` and `specs/` at the
parent. All four become one flw project with one contract and one version history — which is correct, because a
change to the config format is one change across four repos, not four changes. `[tests] checks` is a flat list of
commands each run in its own shell, so per-repo entries are `cd runtime && make test`.

---

### 3. What the agent does unaided

**The one idea it works from.** Four repos are a system only where a literal is duplicated across two of them. An
endpoint path, a table name, an env var, a topic, an image tag, a JSON field, a status enum — both sides hardcode
the same string, and nothing in either repo's type system checks that they match. Everything else is inside a box.

That makes the system map mechanically findable: it is the set of strings appearing in more than one repo. Grep for
duplicates first; read code second.

**What it reads first, and what it skips.** Not source, and not READMEs — read each README and then discount it,
because it is the file that goes stale first and the one most likely to be believed. The high-signal files are the
ones that must be correct or nothing runs locally:

- `docker-compose.yml`, k8s manifests, `.env.example`, `Procfile`, `Tiltfile`. A compose file names every service,
  its ports, and which env var in service A holds the URL of service B. It is the system diagram, machine-readable,
  and kept current by the fact that people run it.
- CI workflows — what gets built, in what order, against which other repo's fixtures or images.
- Manifests (`package.json`, `pyproject.toml`, `go.mod`) — do any two repos share a package? A generated client or a
  shared types package is a hard edge, versioned, and the version skew between repos is a bug list.
- Migration directories and any `.proto`, `openapi.yaml`, or JSON Schema. Where these exist the contract is already
  written down and nobody should be reverse-engineering it from handlers.

Fifteen files across four repos, and that is usually 70% of the topology before a single implementation file opens.

**The duplicate-literal sweep**, run from the parent holding all four checkouts:

```bash
# the wiring: which env vars each repo reads
grep -rhoE '\b[A-Z][A-Z0-9_]{3,}(_URL|_HOST|_ENDPOINT|_URI|_DSN|_BUCKET|_TOPIC)\b' . \
  --include=*.py --include=*.ts --include=*.tsx --include=*.go --include=*.yml | sort | uniq -c | sort -rn
```

```bash
# server side: routes registered
grep -rnE '@(app|router|blueprint)\.(get|post|put|patch|delete)|(app|router)\.(get|post|put|patch|delete)\(' \
  --include=*.py --include=*.ts

# client side: paths requested
grep -rnE '(fetch|axios|httpx|requests|client)\.[a-z]+\(\s*[`"'"'"']' --include=*.ts --include=*.tsx --include=*.py
```

Intersect the two sets by hand. Three outcomes, all findings: a route with no caller (dead, or called from somewhere
not yet grepped), a call with no route (broken, or built by string concatenation), and a matched pair — one confirmed
edge with a `file:line` on each side.

Same move for the datastore: table and collection names from the migrations, grepped across the other three repos. A
repo naming a table without going through the datastore's own client is a coupling nobody documented.

**The trace.** Pick one concrete transaction and follow it end to end, all four repos, one hop at a time: user
changes a setting in the UI → request → datastore write → runtime reads it → tooling pulls the result → UI renders
it.

This is the step that produces understanding, and four repo summaries do not substitute for it. A summary per repo
lets every seam stay vague, because each side gets described in its own vocabulary and the mismatch never surfaces. A
trace forces every hop to resolve to a specific function receiving a specific payload, and it fails loudly at exactly
the hop that was got wrong — which is the hop worth knowing about. Ten to twenty files, chosen by the trace rather
than by importance heuristics.

**Running it beats reading it.** `docker compose up`, `curl` one endpoint, read what the other three services log.
Ten seconds of real request logs settles what an hour of reading only guesses at: the actual payload shape, the
actual auth header, whether that middleware fires, which of two code paths is live.

Git history is the other empirical source, and specifically the correlation across repos:

```bash
for r in */; do git -C "$r" log --since=6.months --date=short --format="%ad ${r%/} %s"; done | sort
```

Days where two repos both have commits are almost always a seam change, and the pair of diffs shows both sides of a
contract that no file states. That is how to find the edges the compose file does not cover.

**Splitting the work — and the split that fails.** The obvious split is one subagent per repo. It fails predictably:
four agents each return a competent description of their own box, none can see a seam, and the lead gets four
vocabularies to reconcile with no ground truth. Repo boundaries are the wrong cut lines, because the boundary is the
thing under investigation.

Cut by **seam** or by **trace** instead — each agent gets two repos and one question:

- "UI ↔ datastore: for every write the UI makes, name the endpoint, the handler `file:line`, the request model, and
  the table it lands in."
- "tooling ↔ runtime: what does tooling pull, from which endpoint, and what constructs that URL."
- one on the trace, spanning all four, whose job is to report the hop where it lost the thread.

Every agent returns `file:line` on both sides of each edge plus the shared literal, and is told explicitly to report
"could not resolve" rather than describe what a function probably does — otherwise the result is a plausible seam map
with no ground truth in it, which is worse than a partial one because it reads identically.

**What gets written down.** One file at the parent, a table rather than prose, because prose about an API drifts
silently while a path plus a symbol fails under grep:

`ds/`, `rt/`, `tl/` and `ui/` below stand for the four repos; substitute your own.

```text
edge                  literal            producer                      consumer
ui→datastore          POST /v1/configs   ds/api/routes.py:88           ui/src/api/configs.ts:24
runtime→datastore     table configs      ds/migrations/003_cfg.sql:1   rt/store/loader.go:61
tooling→runtime       RUNTIME_BASE_URL   rt/server/main.go:30          tl/client/pull.py:17
```

Written as it goes, not at the end — four complex repos exceed what fits in context, and the failure mode is quiet:
the agent stays fluent while the details it cites turn into reconstructions.

**Where this goes wrong:**

- **Over-trusting greppable structure.** A route assembled by string concatenation, a field name pulled from config,
  a dispatch table built at import time — invisible to the sweep, and the sweep's output looks complete either way.
  The trace catches some; nothing catches all.
- **Matching names that are not the same thing.** `user_id` in the UI and `user_id` in the datastore can be
  different ID spaces with a translation in between. The method finds the pair and says nothing about whether the
  values are compatible.
- **A caller proving a callee exists.** It does not. Dead client code calling a renamed route greps identically to a
  live edge; only running it or checking the server side separates them.
- **No intra-repo ranking without a tool.** The fallback is churn —
  `git log --since=6.months --format= --name-only | grep . | sort | uniq -c | sort -rn | head -30` — plus entry
  points and directory shape.

---

### 4. The comparison

They are not competing, and the overlap is smaller than it looks. Scout does one thing no hand method can do.
`flw-research` is roughly the unaided procedure, minus three techniques, plus the two disciplines the agent most
lacks. Neither has a cross-repo model.

**Scout beats the hand method on exactly one question, decisively.** Churn ranking and import ranking answer
different questions, and for orientation churn is not a weak proxy — it is often inverted. A stable core that all
four services import has low churn precisely because it is stable, so `git log | uniq -c | sort -rn` buries it under
whatever is being actively worked on this month. Scout's PageRank puts it first. Churn is a worse fallback than
section 3 implies.

`PACKAGES` / `DEPENDS ON` / `CYCLES` are not reachable by grep at any effort level worth spending. Package-to-package
edges with import counts, and strongly-connected components between them, are the finding for any one of the four
repos that is internally large.

The cost difference is categorical: ~1s and zero tokens, identical output every run, versus 15–30 tool calls whose
coverage depends on which grep patterns occurred to the agent that session.

**The hand method covers what scout structurally cannot, and that is most of the problem.** Scout is single-root and
import-based; every seam between the four repos is invisible to it, and the system is at least four roots and
probably three languages.

| Question | Answered by |
|---|---|
| what is central inside one repo | scout |
| what talks to what across four | duplicate-literal sweep |
| which of those edges is live | running it, logs |
| what shape the payload really is | trace, or logs |
| what the deploy topology is | compose, k8s, CI |

One of five. Scout is the best available answer to its row and silent on the other four.

**`flw-research` against the unaided procedure.** Same shape — orient, probe, verify, write — and its §2 already
names the HTTP blind spot with a grep list. That is the duplicate-literal sweep arrived at from the other direction:
its version is targeted by framework and therefore cleaner where the frameworks are known; the literal sweep is
string matching and therefore covers table names, env vars, topic names and image tags in languages nobody wrote a
pattern for.

Three things `flw-research` has that the agent does not do naturally, and they are the valuable part:

- **Commands persist as data, not prose** — `[tests] setup/checks/yours` in `config.toml`, run verbatim, with the
  stated reason that a command written as a sentence gets reconstructed and drifts. The unaided approach persists
  nothing; everything derived dies with the context window and the next session re-greps from zero.
- **Verify one graph edge** (§3) — test the reference tool against `grep` ground truth before trusting it, with the
  measured 1-of-8 LSP recall miss as the reason. The agent flags LSP recall as a risk and then proposes no
  mechanism; it would have used LSP and been quietly wrong.
- **Name the gap instead of filling it** — "an unrun probe is a gap, not a default." The direct counter-measure to
  the failure mode section 3 lists last and has nothing to do about.

Three things the agent does that `flw-research` does not say to do:

- **The end-to-end trace.** Its probes are per-repo and per-question; nothing forces one transaction to resolve at
  every hop. That is the step converting four descriptions into one model, and it is missing.
- **Start it and read the logs.** Its "run the cheap ones" is scoped to check commands — finding out what executes
  in this session, not learning topology from real traffic.
- **Deployment topology and cross-repo commit correlation.** Its probe list has Makefile, justfile, CI, manifests,
  tox, CONTRIBUTING — no compose or k8s, which for a four-service system is the highest-signal file in the tree. Its
  git step reads one repo's log for durable conventions; commits landing the same day in two repos as a seam
  detector is a different use of history and is not there.

**The gap is in the middle.** Scout produces a durable-but-single-repo artifact regenerated on demand. The sweep
produces cross-repo edges and writes them nowhere. `flw-research` has the discipline to persist things and no
cross-repo place to persist them to.

**One ordering note.** `flw-research` says run scout before opening any file, and for a single unfamiliar repo that
is right. For N>1 roots the order inverts: read compose and the manifests first, because "what talks to what" has to
be settled before "what is central here" is even a well-posed question per repo.

---

### 5. Additional notes

**Seams the sweep should look for beyond HTTP and SQL.** Each is a duplicated literal with no compile-time check,
and each breaks silently:

- **Auth and identity** — JWT claim names, scope strings, audience values. Very commonly the first thing to break
  across repos and the last to be noticed, because a 403 reads as a permissions problem rather than a contract one.
- **Metric and log field names** — dashboards and alerts are a consumer of the runtime's output with no code edge at
  all. Renaming a field breaks a dashboard in a fifth repo that nobody scouted.
- **Object storage layout** — bucket names and key prefixes shared between the runtime that writes and the tooling
  that pulls.
- **Feature flag keys, cron schedule names, queue and topic names, image tags and registry paths.**
- **Status and enum values crossing the wire as strings** — the UI switching on `"running"` while the runtime emits
  `"in_progress"` is a class of bug that types on both sides do nothing to prevent.

**False positives, and how to cut them.** A naive duplicate-string intersection returns `id`, `error`, `name` and
every HTTP verb. Filters that work: a minimum length of about 4–6 characters; discard anything appearing in *all* N
repos (generic by definition — a real seam is usually a pair, occasionally a triple); prefer strings matching a
shape — leading `/`, `SCREAMING_SNAKE`, `snake_case` table-like, `dotted.path`; and rank by rarity, since the
strongest signal is a long odd string appearing in exactly two repos.

**Prior art worth naming.** Consumer-driven contract testing (Pact and its kin) exists precisely because this seam
has no compile-time check, and it solves the problem the right way round: the contract becomes a generated,
executable artifact instead of a document someone maintains. Where any pair of the four repos talks over a
hand-written HTTP interface, generating a contract — OpenAPI plus a generated client, or a pact — converts a
grep-discovered edge into a checked one, and converts scout from blind to useful on that pair, because a generated
client gives real import edges to rank.

**Generated versus hand-written is the risk axis.** Worth recording per edge alongside the `file:line` pair. A
generated client is trustworthy and self-verifying; a hand-written `fetch` with a template-literal URL is where the
next outage comes from. A seam table sorted by "hand-written first" is a work list, not just a map.

**Version skew of shared packages.** If two repos depend on the same generated client or types package, record the
version each pins, from the lockfiles rather than the manifests. Skew is a seam break that greps clean on both
sides — identical literals, different meanings — and is invisible to every technique in section 3.

**Making the seam table verifiable rather than merely written.** The table's whole value is that each row is a claim
a machine can recheck: the literal still appears in both files, at or near the recorded lines. A script that re-greps
every row and fails on a vanished side turns the document into a check, and it drops straight into `[tests] checks`
as a command — exactly flw's "commands are data, prose is for judgment" split.

This creates one real tension with flw's "nothing is cached, nothing is written" stance, and it should be resolved
rather than glossed: *discovery* output must not be stored, because it regenerates in a second and a stale overview
rides in every request; a *verification expectation* must be stored, because there is nothing to check against
otherwise. They are different artifacts. The recorded seam table is closer to a test fixture than to a repo map, and
the honest framing is that it lives in the repo for the same reason a golden file does.

**How far the AGENTS.md A/B result actually transfers.** The N=438 finding is about static prose overviews of a repo
the agent can already see — the overview competes with `grep`, and loses. A cross-repo seam table is different in
kind: the agent cannot derive it by any local operation, because the other three repos are outside the root it is
reasoning about, and re-deriving it costs 15–30 tool calls rather than one. The finding argues against persisting
scout output and does not transfer to persisting seam edges. Worth keeping the distinction explicit, because
"persist the command, not the output" is otherwise a rule that would forbid the one artifact most worth having.

**Context budget, which is the real constraint.** Four complex repos do not fit. The artifacts are the compression:
scout output is roughly 40–60 lines per repo, and a seam table is roughly 20 lines, so the whole system model is a
few hundred lines against four codebases. That is the argument for the artifact over holding it in context, and it
is also why the split-by-seam subagent topology works — the ICs hold repo content, the lead holds only the
artifacts.

**Rough cost of a first pass**, for judging whether to do it: `flw scout` ×4 at ~1s each and zero tokens; the compose
and manifest read at ~15 files; the sweep at ~10 greps; the trace at 15–20 file reads. Call it 60–80 tool calls for a
first system model, most of them cheap. The trace dominates the token cost and is the part worth spending on.

**Where LSP fits, honestly.** Intra-repo at best. It will not cross a service boundary because there is no edge to
follow, `workspaceSymbol` across added directories is unreliable, and the recorded 1-of-8 recall on dynamic imports
means a silent empty result is indistinguishable from a symbol nobody calls. Use it for a targeted question inside
one repo after the seam map exists, never as an orientation tool, and check it against `grep` once before believing
it — which is `flw-research` §3 applied to a tool rather than a repo.

---

### 6. Proposed changes, ordered by payoff over effort

**1. Add the trace and the deployment-topology read to `flw-research` §2.** Prose edit, no code. Two probes: "follow
one complete user-facing transaction end to end and record where you lost it" and "read compose, k8s manifests and
`.env.example` before anything else when the system spans more than one root". Largest gap-to-effort ratio here.

**2. Add cross-repo commit correlation to the history probe**, one command and two sentences of why.

**3. A seam mode for scout, over N roots, matching duplicated literals rather than parsing.**

```text
flw seam <root>...     # print the edge table: literal, producer file:line, consumer file:line
flw seam --verify      # re-grep every recorded edge; non-zero exit when a side has vanished
```

Build it as a separate mode rather than an extension of the import graph, for a specific reason: string matching
needs no parser, so it covers Go, Rust, SQL and YAML on day one, while the import ranker is Python and TypeScript and
will stay that way. The heterogeneity that makes scout weakest on a four-repo system is exactly what a
literal-matcher is indifferent to. Discovery output stays unwritten like everything else scout prints; only
`--verify` reads a stored expectation, and that file is a fixture, not an overview.

**4. Decide whether flw acquires a multi-root project shape.** Today the parent-directory workaround gets there with
no code change and is probably right for a while. The question it defers: does a version file describe a change to
one repo or to the system? For four repos entangled at the API, the system is the honest unit — but that makes
`nearest_project()`'s single-root assumption load-bearing in a place it was not designed for, and it should be a
deliberate decision rather than an accident of directory layout.

---

### 7. Open questions

- Whether the duplicate-literal method's precision holds up on a real four-repo system, or whether the filters in
  section 5 leave a signal-to-noise ratio too poor to use unattended. Untested; it is a design sketch, not a
  measured result.
- Whether a seam table stays current in practice, or whether `--verify` merely converts silent staleness into a
  failing check that people learn to ignore. The second is a real risk for any generated-and-committed artifact.
- Whether ranking should be attempted across repos at all once seam edges exist — a PageRank over the union graph
  would name the system's true centre, and it is not obvious that the number would mean anything, because an
  import edge and an HTTP edge are not the same unit of dependency and summing them asserts they are.
