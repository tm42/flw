---
name: flw-research
description: Bring flw to a repo you did not set up. Read how the place actually works — how it is tested, what it is built on, where the work lives, what its conventions are — and write that into the repo's own flw configuration. Use when starting flw on an existing codebase, or when a repo has changed enough that what was recorded is stale.
argument-hint: "[path]"
---

# flw-research — learn a repo, write it down

## Start here, silently

One command, no narration — do not announce it, do not report it, just run it and begin.
The user asked for the work, not for a description of you preparing to do it.

```sh
flw context flw-research
```

It prints everything this skill opens with: the shared context, the project root it
resolved and where that came from, this repo's extensions from the outermost project root
inward, the note store listing for this project's category, and the contract's components
with the paths each one covers. Everything below assumes it.

**If the request names a repository, a directory or a file, pass it** —
`flw context flw-research --root <that path>`. The rule and its reason are in the shared
context the command just printed; this is the only part of it the command cannot tell you,
because you have to call it first.

**Every extension it printed is part of your instructions from here on.**

**If `flw` is not on PATH:** run it out of the checkout — `<interpreter> "$FLW/cli/flw.py"
context flw-research` — where `$FLW` is the absolute path in `${FLW_HOME:-$HOME/.flw}/root`.
It must be an absolute path: a skill folder is installed as a symlink, and the file-reading
tool collapses `..` lexically before the filesystem resolves it, landing somewhere that
does not exist. If that pointer is missing you may be inside flw's own checkout, so walk up
from the project root for a directory holding both `core/skills/` and `cli/flw.py`.
Nothing → stop and say to run `flw install`.

## Lane

This skill writes **what is true about this repo**, into this repo's flw configuration.

It does not decide what to build. It never touches `specs/` — not the contract, not a
version file. If what you learn suggests the contract is wrong, say so and hand it to
`flw-spec`.

**Three destinations, and the rules that decide between them:**

> **Code reads it → config. An agent reads it → prose.**
> **Does a commit make it wrong? → the knowledge store. Only a decision does? → an extension.**

| | |
|---|---|
| `.flw/config.toml` | `[tests]` — the check commands, the setup line, what cannot run here. `run_tests.py` reads these as data and runs them verbatim |
| `.flw/extensions/<skill name>.md` | how the place works, in prose, for the skill that needs it |
| `.flw/extensions/shared.md` | the same, for what every skill needs — one file, not four |
| `<flw dir>/knowledge/` | what the parts are, what each is for, what crosses between them — mirroring the code, stamped with the revision it was true at |

A command written as prose gets reconstructed on every run, and it drifts — `make style`
becomes `ruff check .` because that is what the agent already knows. A command in config
is run, not remembered.

The second rule is the same line read one level down. Most of what research used to write
into `shared.md` is architecture, and architecture goes stale on a commit rather than on a
decision — so it belongs in the store, where a diff can say how much moved. What is left in
an extension is conventions, which is what a file read at every opening should hold.

**A knowledge file `flw know` returned that the code has already falsified is yours to
correct.** Rewrite that one file and `flw know --stamp` it, and name it in step 5's
`Wrote:` line. That one file — a survey rewrites the tree, a correction does not. The
trigger is what a diff shows, not what you judge.

## 1. Orient

```sh
flw scout
```

Around a second, nothing written, nothing cached. `flw scout --help` says what the
ranking means, what a high rank does not mean, which languages are covered, and what each
section answers — read it there rather than reconstructing it here.

**Read the output before reading any file.** It exists so that the files you then open are
the ones that matter.

For a repo in a language it does not cover, `aider --show-repo-map` prints a map and exits
without an API key — say that rather than reading a hundred files, and record which you
used.

**Do not paste the scout output into an extension.** It regenerates in a second, and the
one published A/B test of static repo overviews found they did not help. Record the
command; the orientation is not an artifact.

**More than one root inverts this order.** For a system spanning several repos, read the
deployment topology first and scout each root after: what talks to what has to be settled
before what is central *here* is even a well-posed question, and a per-repo ranking read
first lets every seam between them stay vague.

**With `[project.roots]` declared, the survey is every member and the parent pass comes
first.** One pass over the topology, the shared literals and one transaction traced end to
end, then one pass per member. The parent gets `system.md`, which is read by declaration and
so reaches every member wherever it sits.

**A parent `shared.md` reaches only members that nest under it.** Extensions are read by
filesystem ancestry and `[project.roots]` does not require nesting — a member declared as
`../datastore` is a sibling, and no session inside it reads a line the parent wrote. So
write a convention at the parent only when every declared member resolves under the parent's
own directory. Otherwise say the convention has to go into each member, and say why, rather
than writing one file that `flw doctor` will report as live and nobody will read.

## 2. Probe

Find out how the place actually runs. Read first — `Makefile`, `justfile`, CI workflow,
`pyproject.toml`, `package.json` scripts, `tox.ini`, `CONTRIBUTING.md`. Those state
intent. Then **run the cheap ones** to find out what is true here.

Add `docker-compose.yml`, k8s manifests and `.env.example` to that first read, and put
them ahead of the rest when the system spans more than one repo. A compose file names
every service, its ports, and which environment variable in one holds the URL of another —
the system diagram, machine-readable, kept current by the fact that people run it. Read
each `README` and then discount it: it is the file that goes stale first and the one most
likely to be believed.

- **How is it tested?** The real invocation, including whatever must precede it. `pytest`
  is a guess; `poetry run pytest -n 4` is an answer, and so is `cargo test --workspace`.
- **How many tests, and how long?** This decides whether a targeted set is worth having.
  Most runners will enumerate without running — `pytest --collect-only -q | tail -1`,
  `cargo test -- --list`, `go test -list . ./...` — and that costs nothing.
- **What is the setup line?** Activation, environment, whatever must come first.
- **What is it built on?** The scout's external-dependency list for TypeScript; the
  manifest for everything else — `pyproject.toml`, `Cargo.toml`, `go.mod`, `pom.xml`.
  What a repo imports says what it is, and the scout only reads two languages: when it
  says what it did not read, the manifest is where the rest of the answer is.
- **What the ranking structurally cannot see.** A service that calls another over HTTP has
  no import edge, so the boundary between two services is invisible to the scout and it
  will report them as unrelated. Grep for it directly: route decorators and the paths they
  register, request and response models, generated OpenAPI or protobuf files, and client
  wrappers built around another service's base URL — `@app.route`, `@router.get`,
  `express.Router()`, an `httpx.AsyncClient` or `axios.create` holding a base URL. Naming
  frameworks here is fine, because this is prose you apply with judgment, which is exactly
  why it is not in the scout.
- **What runs here and what does not?** The question that matters most in a restricted
  session. Try each check once. Anything that cannot run is not a failure and not a
  mystery — it is `[tests] yours`.
- **Recent history.** `git log --oneline -30` and the most-changed files. Read it for what
  is durable — a migration in progress, a convention in commit messages — and do not
  record the log itself. Last week's commits are stale next week and nothing says so.
  **Churn is not a ranking substitute and is often inverted**: a stable core everything
  imports has low churn *because* it is stable, so most-changed puts this month's work on
  top and buries what the repo rests on. Across several repos it answers a different
  question and answers it well — days where two repos both have commits are almost always
  a seam change, and the pair of diffs shows both sides of a contract no file states:
  `for r in */; do git -C "$r" log --since=6.months --date=short --format="%ad ${r%/} %s"; done | sort`
- **Conventions.** How errors are handled, where new code goes, how modules are named,
  what the tests look like. Take these from reading the top-ranked files, not from a
  style guide nobody follows.

**Across repos, grep for the duplicated literal.** Two repos are one system only where
they both hardcode the same string — an endpoint path, a table name, an environment
variable, a topic, an image tag, a status enum — and nothing in either type system checks
that the two still agree. That makes the map mechanically findable rather than a matter of
reading well:

```sh
# every quoted literal of some length, per root, and which appear in more than one
grep -rhoE '"[^"]{6,60}"' repo-a repo-b --include=*.py --include=*.ts --include=*.go \
  | sort -u > /tmp/a-b.txt
```

Order what comes back by rarity and stop reading when it stops paying: a long odd string
in exactly two repos is the strongest signal, and `id`, `error` and every HTTP verb sink to
the bottom on their own. This is the same discovery as the framework greps above from the
other side — theirs is cleaner where the framework is known, this one covers table names,
queue topics and image tags in languages nobody wrote a pattern for. Beyond HTTP and SQL,
the literals that break silently are JWT claim names and scope strings, metric and log
field names consumed by a dashboard in a repo nobody scouted, bucket names and key
prefixes, feature-flag keys, and status values crossing the wire as strings.

**Then trace one transaction end to end**, every repo, one hop at a time: a user changes a
setting, a request goes out, something is written, another service reads it, a result comes
back. This is the step that produces understanding, and a summary per repo does not
substitute for it — each side gets described in its own vocabulary and the mismatch never comes
to light. A trace forces every hop to resolve to a named function receiving a named
payload, and it fails loudly at exactly the hop that was got wrong, which is the hop worth
knowing about. **Record where you lost it.** That is the finding, not a failure of the
method.

Where it can be run, run it: `docker compose up`, one `curl`, and read what the other
services log. Ten seconds of real requests settles the payload shape, the auth header and
which of two code paths is live — all things reading only guesses at.

**Say what you could not determine.** A probe that did not run is a gap, not a default.
Guessing here is worse than leaving it out, because a wrong recorded command is followed
confidently by every later run.

Two traps specific to the sweep. A caller does not prove a callee exists — dead client code
calling a renamed route greps identically to a live edge, and only running it separates
them. And a matched name is not a matched meaning: `user_id` on both sides can be two ID
spaces with a translation between them.

**Search the store before you write anything.** The survey has just told you what this
repository is built on and how it is tested; those are the terms. A note about this
toolchain written in another repository is the case the store exists for.

## 3. Verify one graph edge

If you are going to record a way of finding references — an LSP, `gtags`, anything — **test
it once against ground truth before recording it.**

Pick a function you can see is called from several places. Ask the tool. Count the real
call sites with `grep`. Record whether they agreed.

This is not ceremony. Measured on a real repo, an LSP returned **1 of 8** real callers for
a symbol reached through a dynamic import — and a reference tool that silently returns
nothing looks exactly like a symbol nobody calls. That is how working code gets deleted.

Record the disagreement if you find one. A tool with a known blind spot is usable; a tool
with an unknown one is not.

## 4. Write it

**Project root, when there is no flw directory yet.** The usual rule finds the nearest
directory holding `specs/` or `.flw/`, and a repo nobody set up has neither — which is the
only kind of repo this skill exists for. Use `$PWD`, say which directory you are about to
create `.flw/` in, and get a yes before writing. Do not guess upward. There is no
subcommand for it: the skill creates the directory, the way `flw-spec` creates `specs/`.

**Config first.** `.flw/config.toml` (or the directory `flw doctor` names), `[tests]`:
`setup`, `checks` for the working set, `yours` for what this session cannot run. Only
commands, only what you verified.

**Read that file before writing it, and edit `[tests]` in place.** Nothing outside
`[tests]` is yours to touch. This skill is meant to be re-run when a repo has changed enough
that what was recorded is stale, and a re-run that writes the file fresh drops the report
path, the interview mode and the note-store category the user chose. Leave every key you
did not measure exactly as you found it.

**Propose the ignore lines in the same block.** Nothing creates them, and three places
here assume the reports directory and the knowledge store are ignored — so without them a
review that was told to change nothing leaves ` M .flw/knowledge/…` and `?? .flw/reports/`
in the user's tree. Show the lines beside the config, in whatever file this VCS ignores
with, and let the user take them:

```text
.flw/reports/
.flw/knowledge/
```

Read the ignore file first and propose only what is missing from it, and follow
`[knowledge] dir` when the store is not at the default.

**Then the extensions**, each holding only what its readers need. Do not restate across
them: a fact every skill needs goes in `shared.md` once, not into three files.

| File | What belongs in it |
|---|---|
| `shared.md` | what every skill here needs whatever it is doing — how the place is laid out, what it is for, the conventions that are not one skill's business |
| `flw-execute.md` | how tests and checks are actually invoked; what is normally handed back; what a commit looks like here |
| `flw-spec.md` | where the work lives, what the core modules are, where a new thing goes |
| `flw-review.md` | the conventions and standards a reviewer should judge against |

**Which directory each file goes in.** Extensions are read from every project root at or
above the one being worked in, so a convention belongs at the level it is true of. A repo's
own quirks go in that repo; something every checkout under a parent directory obeys goes in
the parent, which needs only a `.flw/` to become a level. Writing it once above beats
writing it into six repos that then drift — but only where those repos are genuinely under
it on disk, which a declared member need not be.

**Then the knowledge tree**, at `<flw dir>/knowledge/`, mirroring the code: the repository
file first — what it owns and its outward edges, the most valuable file in the store — then
an area file per folder that is a real unit. Five to thirty per repository, and a module
file for a single source file is rare. With `[project.roots]` declared, `system.md` at the
parent comes out of the parent pass, before any member.

`core/skills/flw-research/references/knowledge-example/` is the shape to imitate: a parent
and two members, five files, the seam declared from both sides. Read it before writing the
first file rather than inventing a layout.

**Propose `[knowledge] dir` from what the repo already ignores.** The default is the flw
directory's `knowledge/`, which is already inside whatever ignores the flw directory. A
repository that keeps its architecture somewhere else says so with one key, and the user
confirms it — it is a fact about that repository, so it is read from the project's config
file and never from the machine's.

**Write and review per level, not in one block.** The repository file, shown and agreed;
then the areas, shown and agreed. A tree delivered whole is a tree nobody reads.

**The bar, and it is the sparseness rule too.** A file earns its tokens only by removing
more code reading than it costs. A folder gets a file when reading it removes reading, not
when the folder exists — a repository of 1,800 files gets perhaps forty. Missing is normal;
nothing checks this and nothing will.

**`flw know --stamp <file>` for every file you write**, so it carries the revision it was
true at, and `flw know --reindex` once after that. A file with no revision is read normally
and reports as `unstamped`, which is a claim nobody can date.

**The stamp follows the commit**, as `flw-execute` says for the same reason. A stamp
records HEAD, so stamping before the files are committed records the revision from before
they existed, and the next skill's first read reports them falsified by the flw setup
itself — measured once as `changed since 587b0d5: 10 files · +169 −0`, the diff being this
survey. Propose the commit, and stamp after the user makes it.

**A `flw kb` note in this repo's own root that describes how the system is built moves into
the tree**, once, as part of this survey. kb is addressed by topic and gated on
portability; architecture is addressed by path and goes stale on a commit, and a note that
is really a repository file is in the store that cannot tell it has rotted.

**Show the user everything before writing.** These files become instructions to every later
run, so a wrong line is a wrong instruction repeated silently. One block, their edits,
their yes.

**Where something should bind rather than merely describe** — a rule the project should
hold to, not just a habit it has — say so and hand it over. That belongs in the contract,
as an assumption or a component's `implementation` note, and it is `flw-spec`'s to write.
Research records what **is**. What **must be** is the user's.

**Then offer a note.** One sentence decides whether there is one: *write it only if it
was measured, and the next agent, in a repository that does not hold this one's history,
could not get it faster than measuring it again.* That scope clause is what makes the
answer ever yes here — most of what this skill learns is a fact about this repository,
and a fact about this repository goes in the extension, not the store. What passes is
craft: step 3's graph edge, a toolchain's measured blind spot, a proxy's real rules.

If it is yes, read `flw kb write --help` first, then say what you would write. It is an
offer the run declines by doing nothing.

## 5. Report

```text
flw-research — <repo>
  Scouted:     <n> files · <what it is, in one line>
  Wrote:       <files>
  Tests:       <n> checks · <n> handed back as yours
  Undetermined: <what you could not settle, or nothing>
```

Then run `flw doctor`, which will tell you whether the extensions you just wrote are
actually read by an installed skill. A file named for a skill that does not exist is read
by nobody and looks fine forever.

## Rules

1. **Never write `specs/`.** Not the contract, not a version file. That is `flw-spec`.
2. **Record what you verified.** An unrun probe is a gap you name, not a default you guess.
3. **Commands go in config, prose in extensions.** Nothing that runs lives in a sentence.
4. **Show before writing.** These are instructions to every later run.
5. **The orientation is not an artifact.** Record the command, never its output.
