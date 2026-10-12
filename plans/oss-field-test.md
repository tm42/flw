# Field test: flw against code it did not write

Every review flw has had was flw reading flw. 76 reports on disk, four lenses on its own code, five on its own method, none with any outside code in scope. This plan puts flw's three discovery commands against five third-party checkouts and says, per test, what would count as a failure.

## The fixtures

Cloned blobless and single-branch under `~/_projects/oss-fixtures/`, outside this repository. Revisions are recorded so every number below can be re-taken.

```text
pandas          1633b5447e  2026-10-10  1,544 .py
django          dab0a5c47f  2026-10-09  2,933 .py
asgi/starlette  96d5023     2026-10-09     84 .py
asgi/uvicorn    31e3e00     2026-10-10     84 .py
asgi/httpx      b5addb6     2026-02-23     60 .py
```

`asgi/` carries a hand-written `.flw/config.toml` declaring the three members under `[project.roots]`, because that declaration is the user's statement and not something a survey infers. Everything else in those directories is flw-research's to write. `flw context --root ~/_projects/oss-fixtures/asgi` resolves all three members today.

These are third-party checkouts, so they are read and never run: no build tool, no test runner, no interpreter invoked from inside one of them. flw's own code runs with the fixture as an argument.

## T1 — `flw scout` on pandas

`flw scout ~/_projects/oss-fixtures/pandas` — the path is positional; scout has no `--root`

Measures wall time, the share of imports the header says resolved, and whether the top 20 are files a pandas contributor would name.

Passes if it finishes under ten seconds, resolves at least 85% of imports — the figure `flw scout --help` commits to — and ranks `pandas/core/frame.py`, `series.py` or `generic.py` near the top.

Fails if the top 20 is mostly `__init__.py` and `api.py`. pandas re-exports its whole public surface through those, and scout's edge runs from the importing file to the file that defines the imported name, so a re-export shell can collect the rank that belongs to the module behind it. That is the specific wrongness to look for, and it would be a finding about scout rather than about pandas.

## T2 — `/flw-research` on the ASGI trio

`/flw-research --root ~/_projects/oss-fixtures/asgi`

This is the real test. uvicorn serves a starlette application over ASGI and httpx talks to it over HTTP, so the two seams that define the system have no import edge at all and scout structurally cannot see either. The skill's step 2 says to grep for them instead, trace one transaction end to end, and record where the trace was lost.

Passes if `system.md` names at least one of the two seams with a path on both sides, and if the report's `Undetermined:` line is not empty. A trace that resolved every hop across three unfamiliar repositories on the first pass is the suspicious outcome rather than the good one.

Fails if the tree restates each repository's README, or if a seam is claimed with a path on one side only.

## T3 — the knowledge-store bar on django

`/flw-research --root ~/_projects/oss-fixtures/django`

The skill's own bar is five to thirty files per repository, with "a repository of 1,800 files gets perhaps forty" as its worked case. Django is 2,933 files.

Passes if the tree lands between five and thirty files and three files picked at random each remove more code reading than they cost.

One caveat specific to this test: django's layout is in the training corpus, so a model can write a plausible tree without reading anything. Check one claim in one file against the code at `dab0a5c47f` before believing the tree. T1, T2 and T4 do not have this problem, because they measure flw's machinery rather than a model's recall.

## T4 — scout's negative answer, optional

A Rust or Go checkout — `astral-sh/ruff` or `prometheus/prometheus`, neither cloned yet. `flw scout --help` claims it names what it did not read rather than confidently reporting a ranking over zero edges. Five minutes to find out whether it does.

## What this plan does not do

It runs none of the project's own checks, writes no record, and changes nothing in flw. Each test produces either a pass or a finding, and a finding becomes a record through `flw-spec` the usual way.

## T1 result, at pandas `1633b5447e`

Three findings. The ranking underneath them is good: positions 5 through 11 are `core/dtypes/dtypes.py`, `core/indexes/base.py`, `core/dtypes/common.py`, `core/series.py`, `_config/config.py`, `core/indexes/datetimes.py` and `util/_decorators.py`, which is the list a pandas contributor would write. 2.78 seconds over 1,544 files and 294,031 lines, so the time criterion passed with room.

**An imported name resolves to any in-repo definition of that name, whatever module the import actually named.** `asv_bench/benchmarks/series_methods.py` ranks second at 0.0520, labelled `Any 167 files`. Line 285 of that file is `class Any:`, a benchmark fixture. Only 21 files in pandas do `from typing import ... Any`, so the 167 is not the typing count either — it is every importer of a name spelled `Any`, all of their rank handed to one benchmark. Any repository with a short common word defined anywhere gets a benchmark or a test file in its top three.

**`pandas/__init__.py` ranks first at 0.0677.** This is consistent with the documented rule, because `--help` sends a plain module import to the module's own file and 1,002 files import `pandas`. It is still the wrong answer for orientation: a package `__init__.py` will top the ranking in every Python repository laid out this way, and `--help`'s "what a high rank does not mean" paragraph does not warn about it.

**No resolution rate is printed.** `--help` commits to "roughly 85-90% of imports to resolve" and the header reports file counts, lines and definitions but never the share that resolved. A repository where it resolved 40% is indistinguishable from one where it resolved 90%, which is the one number that says whether to trust the ranking.

Also worth a line: 1,156 of the 1,544 files are tests, and `asv_bench/benchmarks` ranks third in PACKAGES at 0.076, above every pandas package except `core/dtypes` and `core`.

## T2 result, at starlette `96d5023` · uvicorn `31e3e00` · httpx `b5addb6`

Run by a fresh agent with no flw context of its own, which is the condition the skill is written for. 16 files written, nothing in the three checkouts executed, every invocation handed back as `[tests] yours`. The skill got the agent to a correct and reasonably deep understanding of a system it had never seen, and the findings below are about where it had to work around the instructions rather than against them.

The premise in T2 above is wrong and is left standing so the correction is visible: the three repos do share Python import edges. 6 starlette to httpx, 11 uvicorn to httpx2, 2 httpx to uvicorn — `httpx/tests/conftest.py:17-18` imports `uvicorn.config.Config` and `uvicorn.server.Server` and subclasses the latter, and `starlette/starlette/testclient.py:27` tries `import httpx2 as httpx` and falls back. The ASGI seam itself has no import edge, so the test still measures what it was built to measure.

There are three seams, not two. ASGI over a socket, from `uvicorn/uvicorn/protocols/http/h11_impl.py:405` to `starlette/starlette/applications.py:92`. ASGI in-process, through `httpx/httpx/_transports/asgi.py`, which is the transport starlette's own `TestClient` wraps. HTTP over a socket, where `httpx/tests/conftest.py:224` subclasses `uvicorn.server.Server` and runs it on a thread.

**Scout ranks the file that serves every HTTP request fourteenth.** In uvicorn, `uvicorn/config.py` ranks first at 0.0940 and `uvicorn/protocols/http/h11_impl.py` ranks fourteenth at 0.0161, re-taken here with `flw scout uvicorn -n 300`. The cause is at `uvicorn/uvicorn/config.py:53-75`: four dicts of `"module:Class"` strings resolved by `import_from_string`, so no import statement exists and PageRank sees the registry as the dependency and the implementation as a leaf. T1's artifact was a name collision; this one is resolution through data, and both are the same limit — scout trusts the import graph and nothing in its output says where the import graph is not the real graph. `--help`'s "what a high rank does not mean" paragraph covers neither case.

**The route-decorator grep the skill prescribes finds nothing in starlette.** `grep -rn "@app\.route\|@router\.get\|@app\.get" starlette --include="*.py"` returns 0 hits, because current starlette registers routes as `Route` and `Mount` objects passed to the application. That bullet is written for FastAPI and Express. What found the ASGI seam was the duplicated-literal sweep in the same step, run verbatim: the starlette-and-uvicorn intersection minus httpx came back as the ASGI protocol vocabulary and nothing else — `http.request`, `http.response.start`, `http.disconnect`, the `lifespan.*` and `websocket.*` families, and the scope keys. The sharper rule the skill does not state is that in an N-repo system the pairwise intersections minus the full intersection are where the seams are; the three-way intersection is HTTP header names and environ keys and is near-useless.

**`flw-research` on a declared multi-root project files notes under a different category per member, and says nothing about it.** `_kb_category` at `cli/flw.py:2860` reads `[kb] category` and falls back to the resolved root's directory name. Creating a member `.flw/config.toml` — which the survey must do, because the store is per member — makes that member a project root, so a note written from inside it is filed under `starlette` where one written at the parent is filed under `asgi`. The store does not hide them, because the resolved category sorts first and never filters, but an explicit `-c` splits them and nothing warns that the survey introduced the split. The fix is one key: the same `[kb] category` in the parent and each member config. The skill documents the key and never connects it to the multi-root case.

**`pytest --collect-only` is execution, and the skill calls it free.** Step 2 says "Most runners will enumerate without running … and that costs nothing." Collection imports every test module and runs every `conftest.py` and module-scope fixture. All three members set `filterwarnings` in `pyproject.toml`, so collection can also fail on a warning raised at import.

**`[tests] yours` records a command and nothing about why it is there.** A later reader seeing an entry cannot tell "this session was forbidden to run it" from "this needs hardware we do not have" from "this hung last time", and those have different consequences. The run put its reason in a TOML comment it invented.

**`flw know --stamp` advises a commit that must never happen.** The only uncommitted change in each member is the `.flw/` the survey wrote, and committing that into a third-party checkout is the one thing not to do. So the stamp printed `recorded HEAD, re-stamp once they are committed` and the advice is permanently untakeable, which leaves `flw know --check` reporting all three repository files as `changed · 14 files · +0 −0 · since 31e3e00` — falsified with an empty diff, because the untracked `.flw/` counts in the file total and contributes no lines. The skill predicts this failure in its own text and its remedy does not reach a store that is deliberately never committed.

**`flw kb search` prints the resolved root's category on the line above its no-match message.** The run passed `-c flw`, read `category: asgi`, concluded the flag was ignored, and stopped searching. The flag works — `flw kb search --global -c prose-lint emoji` returns the note and `-c flw emoji` excludes it — so the finding is the header, which invites that inference at the exact moment it is most costly. The second half stands on its own: the message says "check the category and tag names above" and nothing above lists them, and there is no surface for discovering what categories exist.

**`flw doctor` takes a member on faith.** It prints `starlette: …/starlette — exists` and nothing else: not whether the member has its own config, store or extensions, and no member-level problems. In a project whose whole shape is `[project.roots]`, the parent is checked and the members are counted.

Smaller: `flw know --stamp` prints `httpx, starlette, uvicorn has uncommitted changes`; a generated `index.md` row for a directory holding only subdirectories carries no description; `flw scout -n` is a total line budget rather than a per-section count, so the default of 20 prints one file in `MOST DEPENDED ON` — the section the skill sends a reader there for.

Two steps produced nothing a later reader uses. The compose and k8s read, which the skill promotes to the front for a multi-repo system, found one file across three checkouts and no topology, because a library does not ship the topology of a system someone builds with it. And the cross-repo churn pass, offered as a seam-change detector on days where two repos both have commits, cannot work on three independently released upstreams where a same-day commit is coincidence.

The run's own account of its method: every hop is read, nothing was run, and a declared version constraint was not treated as a passing test. It caught one case of a caller not proving a callee — `httpx/tests/conftest.py:230` overrides `install_signal_handlers`, which uvicorn 0.54.0 replaced with `capture_signals` at `uvicorn/uvicorn/server.py:329` — and it says it cannot promise there is no second one.

Last, the fixture itself is not internally consistent, and that is worth recording before T2 is re-run. starlette 1.7.0 and uvicorn 0.54.0 want `httpx2`; the httpx checkout is 0.28.1 and provides `httpx`. uvicorn's `dev` group lists `httpx2` alone, so its 11 httpx2-importing test modules cannot run against this parent at all. A re-run either pins three revisions that resolve against each other or keeps these and treats the skew as part of what the survey had to discover.

### T2, three findings added after the full report arrived

**The skill never says to create a member `.flw/` directory.** It says the store is per member and the survey is one pass per member, which together require one, but no instruction covers creating it — in a third-party checkout, three times. The run created three and said that had it been wrong about that, nothing in the skill would have stopped it. The paragraph that does cover creating a flw directory is written for the single-root case and is dead when the parent already has one.

**The ignore-lines instruction has no target here.** The parent is not a git repository at all: `git -C . rev-parse --show-toplevel` returns `fatal: not a git repository`. So there is no parent ignore file, and the three places the skill says assume the store is ignored are assuming something that cannot be arranged. In the members the file exists and belongs to upstream. The line a user would add to each of `starlette/.gitignore`, `uvicorn/.gitignore` and `httpx/.gitignore` is `.flw/` — one line rather than the skill's two, because none of the three ignores any part of a flw directory.

**The parent's `flw-spec.md` was wasted.** The skill's table assigns it "where the work lives, what the core modules are, where a new thing goes". At a parent that holds nothing but `.flw/`, with all code upstream in the members, the honest answer to the first and third is that there is none. 2,316 bytes of which the useful part restates what the knowledge store says one level down. The run would delete it.

Also worth a line, on the surfaces: `flw know` takes `--root` and `flw scout` takes its path positionally, which is the inconsistency rather than scout being wrong. And `core/skills/flw-research/references/knowledge-example/` does not cover either case this survey hit — a member whose store runs to six files, or a package with four interchangeable implementations of one job, where the line between the repository file and an area file is a judgment the example does not illustrate.

The one decision the run would most want a human to overturn: it put the per-member review conventions in the parent's `shared.md` rather than one file per member, on the skill's own argument that writing it once above beats writing it into six repos that then drift. It first checked that all three declared members nest under the parent on disk, by running `flw context flw-review` from inside `starlette/` and seeing the parent's four files, so the parent file does reach them.

One line in the other direction, for whichever record takes the research gaps: the base-URL-client grep the same step prescribes did earn its place, where the route-decorator grep beside it did not. It found `"http://testserver"` in all three repositories, which is how the run learned that `starlette/starlette/testclient.py:387` and the uvicorn and httpx test suites hardcode one base URL against in-process transports — a shared literal of a different kind from the protocol vocabulary, and one the run says it would otherwise have missed. The third seam, `httpx.ASGITransport`, was found by accident while checking why the three-way intersection held `http.response.start` at all, and no instruction pointed at it.

### Where the T2 findings went

The instruction-level findings above are specced as `say-what-the-survey-creates` under specs/versions/: the uninstructed member flw directories, the note category that splits with them, test collection being called free, `[tests] yours` recording no reason, the ignore lines with no file to go in, and the pairwise-intersection rule that found the ASGI seam. That record pays for its additions with the two passes this test showed produce nothing, because `core/skills/flw-research/SKILL.md` is 20,853 bytes against a 21,000 ceiling.

The CLI findings are not specced and are named in that record's "what this does not do": `flw doctor` taking a member on faith, `flw kb search`'s header and its no-match message, `flw know` taking `--root` where `flw scout` is positional, and the `--stamp` grammar. The `know --check · +0 −0` finding is specced separately, in `a-verdict-needs-a-measurement`.

The T1 findings are specced as `scout-says-what-resolved`.
