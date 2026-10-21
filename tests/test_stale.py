"""The fold over the four stores flw writes into.

Most of what `flw stale` prints belongs to a store's own lint and is tested where
that lint lives. What is only here is the report split: which reports a record has
already acted on, which nobody has read, and which names a record cites with no
file behind them. Both directions of that fold matter, because neither is complete
alone — a record can name a report that has since been deleted, and a report can
carry a record's name whose prose never names its path.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core" / "scripts"))
import knowledge
import ledger
import stale

CONTRACT = """schema_version = 4
spec_version = "0.1"
applied = ["first"]

[[final_state.components]]
name = "the thing"
paths = ["src/"]
provides = ["A user can do the thing."]
"""


def project(tmp_path: Path, **records: str) -> Path:
    (tmp_path / "specs" / "versions").mkdir(parents=True)
    (tmp_path / "specs" / "current.toml").write_text(CONTRACT)
    for name, body in records.items():
        stem = name.replace("_", "-")
        (tmp_path / "specs" / "versions" / f"{stem}-minor.toml").write_text(
            f'name = "{stem}"\n{body}'
        )
    return tmp_path


def report(root: Path, name: str, text: str = "# a review\n") -> Path:
    directory = root / ".flw" / "reports"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(text)
    return directory


def fold(root: Path) -> stale.Reports:
    return stale.reports(root / ".flw" / "reports", ledger.corpus(root).records)


# --- a report a record has acted on ------------------------------------------ #


def test_a_report_named_in_sources_is_spent(tmp_path):
    """The fixture names the report by its bare filename, which no citation pattern
    reaches, so `sources` is the only route to spent. Written the obvious way — the
    full path in the field — the field could be deleted from `cited()` and this test
    still passed, because the pattern matched that same line as the record's raw
    text. `sources` is the field this record and its two neighbours are the first
    to use, so it is worth holding before it carries weight."""
    root = project(
        tmp_path,
        first='summary = "s"\nsources = ["2026-09-03T2050-process.md"]\n',
    )
    report(root, "2026-09-03T2050-process.md")
    found = fold(root)
    assert found.spent == ["2026-09-03T2050-process.md"]
    assert found.unread == []


def test_a_report_named_only_in_prose_is_spent(tmp_path):
    """Every record written before `sources` existed cites its reports in
    `approach` and nowhere else, so the fold has to work retroactively."""
    root = project(
        tmp_path,
        first='summary = "s"\napproach = "read .flw/reports/2026-08-31T1205-eng.md first"\n',
    )
    report(root, "2026-08-31T1205-eng.md")
    assert fold(root).spent == ["2026-08-31T1205-eng.md"]


def test_a_line_anchor_cites_a_line_of_a_report_not_another_report(tmp_path):
    root = project(
        tmp_path,
        first='summary = "s"\napproach = "see .flw/reports/2026-08-22T1959-final.md:14"\n',
    )
    report(root, "2026-08-22T1959-final.md")
    found = fold(root)
    assert found.spent == ["2026-08-22T1959-final.md"]
    assert found.dead == []


def test_a_match_with_no_md_in_it_is_dropped(tmp_path):
    """Reading prose with a pattern produces artifacts. `.flw/reports/` at the end
    of a sentence yields the directory itself, which names no report."""
    root = project(
        tmp_path, first='summary = "s"\napproach = "past reports are in .flw/reports/."\n'
    )
    report(root, "2026-08-31T1205-eng.md")
    found = fold(root)
    assert found.spent == []
    assert found.dead == []
    assert found.unread == ["2026-08-31T1205-eng.md"]


def test_a_name_with_no_file_behind_it_is_a_dead_citation(tmp_path):
    """Counted as neither spent nor open. Reports get deleted informally, so a
    citation is not evidence a file exists, and calling one spent would report a
    directory as read that nobody can now read."""
    root = project(
        tmp_path, first='summary = "s"\napproach = "see .flw/reports/2026-08-23T1336-eng.md"\n'
    )
    report(root, "2026-08-31T1205-eng.md")
    found = fold(root)
    assert found.dead == ["2026-08-23T1336-eng.md"]
    assert found.spent == []
    assert found.unread == ["2026-08-31T1205-eng.md"]
    assert found.total == 1


# --- what is not a citation -------------------------------------------------- #


def test_a_path_inside_a_dag_description_is_not_a_citation(tmp_path):
    """A task describing a fixture writes a report path and cites nothing. `y.md`
    was one of this repository's ten dead citations for exactly this reason, and
    `mark-what-is-spent-minor.toml:33` had already named it as an artifact to
    drop."""
    root = project(
        tmp_path,
        first=(
            'summary = "s"\n\n'
            "[[dag]]\ngroup = 1\nphase = \"p\"\n"
            'tasks = [ { id = "t", desc = "a fixture carrying .flw/reports/y.md" } ]\n'
        ),
    )
    report(root, "2026-08-31T1205-eng.md")
    found = fold(root)
    assert found.dead == []
    assert found.spent == []
    assert found.unread == ["2026-08-31T1205-eng.md"]


def test_a_directory_merely_ending_in_the_declared_one_is_not_it(tmp_path):
    """The prefix class absorbed whatever preceded the name, so `previews` ended in
    `reviews` and matched. `plans/notes/` against a project declaring `notes` is the
    same shape, and the contract declares `notes/` as the project note store."""
    assert stale.citation("reviews").findall("docs/previews/X.md") == []
    assert stale.citation("notes").findall("plans/notes/2026-09-04T1200-eng.md") == []
    assert stale.citation("reviews").findall("see reviews/2026-09-04T1200-eng.md") == [
        "reviews/2026-09-04T1200-eng.md"
    ]


def test_a_record_naming_a_report_in_prose_is_still_a_citation(tmp_path):
    """The half that must survive both changes: `approach` is a prose field and a
    path at the start of its own token is a citation."""
    root = project(
        tmp_path,
        first=(
            'summary = "s"\n'
            'approach = "read .flw/reports/2026-08-31T1205-eng.md first"\n'
            'contract_edit = "see .flw/reports/2026-09-01T0900-eng.md"\n'
        ),
    )
    report(root, "2026-08-31T1205-eng.md")
    report(root, "2026-09-01T0900-eng.md")
    assert fold(root).spent == [
        "2026-08-31T1205-eng.md",
        "2026-09-01T0900-eng.md",
    ]


# --- a project that moved its reports directory ------------------------------ #


def moved(root: Path, directory: str, name: str) -> Path:
    """A reports directory somewhere other than the default, with one report in
    it. The fold is handed the directory string exactly as `[paths] reports` gives
    it to the CLI."""
    where = root / directory
    where.mkdir(parents=True, exist_ok=True)
    (where / name).write_text("# a review\n")
    return where


def test_a_citation_naming_the_configured_directory_is_spent(tmp_path):
    """The finding: with the matcher hardcoded to .flw/reports this reported 0
    spent and 1 nobody has read, for a report the record names in its own prose."""
    root = project(
        tmp_path, first='summary = "acted on reviews/2026-09-04T1200-eng.md"\n'
    )
    where = moved(root, "reviews", "2026-09-04T1200-eng.md")
    found = stale.reports(where, ledger.corpus(root).records, "reviews")
    assert found.spent == ["2026-09-04T1200-eng.md"]
    assert found.unread == []


def test_the_default_directory_still_matches_in_such_a_project(tmp_path):
    """A project that moved its reports directory still holds records citing the
    old location, so the default stays as a second alternation."""
    root = project(
        tmp_path, first='summary = "acted on .flw/reports/2026-09-04T1200-eng.md"\n'
    )
    where = moved(root, "reviews", "2026-09-04T1200-eng.md")
    found = stale.reports(where, ledger.corpus(root).records, "reviews")
    assert found.spent == ["2026-09-04T1200-eng.md"]


def test_a_directory_name_with_a_regex_metacharacter_is_escaped(tmp_path):
    """A project may name the directory anything. Unescaped, `a.c` would match
    `abc` as well, and the fold's value is that a spent report is one a record
    actually acted on."""
    pattern = stale.citation("a.c")
    assert pattern.findall("abc/2026-09-04T1200-eng.md") == []
    assert pattern.findall("a.c/2026-09-04T1200-eng.md") == [
        "a.c/2026-09-04T1200-eng.md"
    ]


def test_an_absolute_reports_directory_folds_on_the_default_alone(tmp_path):
    """`[paths] reports` is taken raw, so `root / reports_dir` discards the root
    for an absolute value and no record would ever spell the result."""
    pattern = stale.citation("/var/reports")
    assert pattern.pattern == stale.citation().pattern


def test_fold_carries_the_declared_directory_into_the_matcher(tmp_path):
    """`fold` takes the directory twice — once to list and once to match — and
    dropping the second left every test green while a project that moved its
    reports directory read every citation as unread."""
    root = project(
        tmp_path, first='summary = "acted on reviews/2026-09-04T1200-eng.md"\n'
    )
    moved(root, "reviews", "2026-09-04T1200-eng.md")
    text = stale.fold(root, exclude=".flw", reports_dir="reviews")
    assert "1 spent, 0 nobody has read" in text


# --- the mark a report carries ----------------------------------------------- #


def test_a_report_carrying_a_records_name_is_spent(tmp_path):
    """The half the citation regex cannot reach: this record's prose names the
    report by its bare filename, so no path pattern finds it."""
    root = project(tmp_path, mark_what_is_spent='summary = "s"\n')
    report(
        root,
        "2026-09-03T2050-process.md",
        "Specced as `mark-what-is-spent` under specs/versions/.\n\n# flw-review\n",
    )
    assert fold(root).spent == ["2026-09-03T2050-process.md"]


def test_a_heading_naming_the_record_the_review_was_of_is_not_the_mark(tmp_path):
    """`# Adversarial pass — \\`opening-is-one-call\\`` is a report OF that record's
    work, which is the opposite relationship. Reading headings marked 20 of flw's
    66 reports instead of 3."""
    root = project(tmp_path, opening_is_one_call='summary = "s"\n')
    report(root, "2026-09-01T2321-eng.md", "# Adversarial pass — `opening-is-one-call`\n")
    assert fold(root).spent == []


def test_a_backticked_name_that_is_no_record_marks_nothing(tmp_path):
    root = project(tmp_path, first='summary = "s"\n')
    report(root, "2026-09-01T2321-eng.md", "Run `flw test` before reading this.\n\n# eng\n")
    assert fold(root).spent == []


def test_a_first_line_mentioning_a_record_without_the_mark_is_not_the_mark(tmp_path):
    """Any first line carrying a backticked record name counted, so a report
    opening with an instruction read as marked in a project holding a record of
    that name. The mark is the sentence flw-spec writes, not any sentence."""
    root = project(tmp_path, flw_test='summary = "s"\n')
    report(root, "2026-09-01T2321-eng.md", "Run `flw-test` before reading this.\n\n# eng\n")
    found = fold(root)
    assert found.spent == []
    assert found.unread == ["2026-09-01T2321-eng.md"]


def test_the_extensions_header_counts_files_and_the_row_counts_lines(tmp_path):
    """`EXTENSIONS (n)` counted marker lines while REPORTS, KNOWLEDGE and NOTES
    each counted documents, and it repeated the row's own number one line above
    it. flw ledger printed 4 extensions in the repository where flw stale printed
    2."""
    root = project(tmp_path, first='summary = "s"\n')
    directory = root / ".flw" / "extensions"
    directory.mkdir(parents=True)
    (directory / "shared.md").write_text("**Python 3.11 is the floor**, for `tomllib`.\n")
    (directory / "flw-spec.md").write_text("# no countable here\n")
    (directory / "flw-execute.md").write_text("# nor here\n")
    text = stale.fold(root, exclude=".flw")
    assert "EXTENSIONS  (3)" in text
    assert "claims with no revision  (1)" in text


def test_a_record_whose_sources_is_not_a_list_does_not_raise(tmp_path):
    """flw validate refuses such a record, but this command does not validate
    first and the contract says it exits 1 only for a bad --root."""
    root = project(tmp_path, first='summary = "s"\nsources = 7\n')
    report(root, "2026-08-31T1205-eng.md")
    found = fold(root)
    assert found.unread == ["2026-08-31T1205-eng.md"]


def test_a_broken_symlink_in_an_extension_still_prints_every_block(tmp_path):
    """The whole command, not the corpus: one unreadable extension exited 1 with
    no output whatever."""
    root = project(tmp_path, first='summary = "s"\n')
    directory = root / ".flw" / "extensions"
    directory.mkdir(parents=True)
    (directory / "gone.md").symlink_to("/nonexistent/gone.md")
    text = stale.fold(root, exclude=".flw")
    for block in ("REPORTS", "KNOWLEDGE", "EXTENSIONS  (0)", "NOTES"):
        assert block in text


# --- a project that has none of this ----------------------------------------- #


def test_a_project_with_no_reports_directory_folds_to_nothing(tmp_path):
    root = project(tmp_path, first='summary = "s"\n')
    found = fold(root)
    assert (found.spent, found.unread, found.dead, found.total) == ([], [], [], 0)


def test_the_whole_fold_runs_over_a_project_with_no_stores_at_all(tmp_path):
    """The exit-0 case the contract names: no reports directory, no knowledge
    store, no notes. It prints what it can rather than refusing."""
    root = project(tmp_path, first='summary = "s"\n')
    text = stale.fold(root, exclude=".flw")
    assert "no reports/ directory" in text
    assert "no store" in text
    assert "Nothing here is a failure" in text


def test_an_empty_knowledge_store_counts_no_files(tmp_path):
    root = project(tmp_path, first='summary = "s"\n')
    (root / ".flw" / "knowledge").mkdir(parents=True)
    assert stale.knowledge_state([(root, root / ".flw" / "knowledge")], {}, exclude=".flw").files == 0


def test_a_knowledge_file_describing_a_path_that_is_gone_is_orphaned(tmp_path):
    """No VCS needed for this one, and none is used: it is one stat per file."""
    root = project(tmp_path, first='summary = "s"\n')
    store = root / ".flw" / "knowledge"
    store.mkdir(parents=True)
    (store / "src").mkdir()
    (store / "src" / "engine.md").write_text(
        '+++\ntype = "area"\ndescription = "the engine"\nrevision = "abc1234"\n+++\n# src/engine\n'
    )
    state = stale.knowledge_state([(root, store)], {}, exclude=".flw")
    assert state.files == 1
    assert state.orphaned == [f"{root.name}/src/engine.md"]
    assert state.changed == []


# --- a stamp the repository can no longer resolve ---------------------------- #

GIT = shutil.which("git")


def stamped_repo(root: Path) -> None:
    """A repository with one stamped knowledge file, then a replaced history.

    The stamp is taken from a real commit and then that commit is put out of
    reach, which is what a rebase, a squash or a force-push does to every stamp
    in a store at once. Replacing `.git` outright rather than expiring the reflog
    and garbage-collecting: the state under test is that the revision cannot be
    resolved, and this reaches it in two `git init`s rather than a `gc`.
    """
    ident = [
        "-c", "user.email=flw@example.invalid",
        "-c", "user.name=flw",
        "-c", "commit.gpgsign=false",
    ]

    def run(*args):
        return subprocess.run(
            [GIT, *ident, *args], cwd=root, capture_output=True, text=True, check=True
        )

    (root / "src").mkdir()
    (root / "src" / "engine.py").write_text("x = 1\n")
    store = root / ".flw" / "knowledge"
    store.mkdir(parents=True)
    (store / "src").mkdir()
    # An Area file repeats its directory name, so this one mirrors src/.
    file = store / "src" / "src.md"

    subprocess.run([GIT, "init", "--initial-branch=main", str(root)],
                   capture_output=True, check=True)
    file.write_text(
        '+++\ntype = "Area"\ndescription = "the source"\nrevision = "0000000"\n+++\n'
        "# src\n"
    )
    run("add", "-A")
    run("commit", "-m", "first")
    revision = run("rev-parse", "--short", "HEAD").stdout.strip()
    file.write_text(
        f'+++\ntype = "Area"\ndescription = "the source"\nrevision = "{revision}"\n+++\n'
        "# src\n"
    )
    run("add", "-A")
    run("commit", "-m", "stamped")

    shutil.rmtree(root / ".git")
    subprocess.run([GIT, "init", "--initial-branch=main", str(root)],
                   capture_output=True, check=True)
    run("add", "-A")
    run("commit", "-m", "history replaced")


@pytest.mark.skipif(GIT is None, reason="git not on PATH")
def test_a_stamp_the_repository_cannot_resolve_reaches_its_own_row(tmp_path):
    """The finding: `knowledge_state` tested for `changed` and let the other two
    states fall through, so a store whose every stamp had gone unverifiable read
    byte for byte like a store where everything was current \u2014 on the run right
    after the rewrite, which is the run a reader most needs told about."""
    root = project(tmp_path, first='summary = "s"\n')
    stamped_repo(root)
    state = stale.knowledge_state([(root, root / ".flw" / "knowledge")], {}, exclude=".flw")
    assert state.files == 1
    assert state.unverifiable == [f"{root.name}/src/src.md"]
    assert state.changed == []
    assert "unverifiable  (1)" in stale.render(
        root, stale.Reports(root / ".flw" / "reports"), state, [], [], 0
    )


# --- every branch of the knowledge fold ------------------------------------- #


def concept(store: Path, rel: str, body: str) -> None:
    path = store / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def test_each_knowledge_state_reaches_its_own_row(tmp_path):
    """Only `orphaned` was held. Deleting the changed, malformed or unstamped
    branch left the suite green, and the unverifiable branch is newer than every
    test that touched this function."""
    root = project(tmp_path, first='summary = "s"\n')
    store = root / ".flw" / "knowledge"
    for name in ("orphan", "malformed", "unstamped", "unverifiable"):
        (root / name).mkdir()
    concept(
        store,
        "orphan/orphan.md",
        '+++\ntype = "Area"\ndescription = "gone"\nrevision = "abc1234"\n+++\n# orphan\n',
    )
    (root / "orphan").rmdir()
    concept(store, "malformed/malformed.md", '+++\ntype = "Module"\n+++\n# malformed\n')
    concept(
        store, "unstamped/unstamped.md", '+++\ntype = "Area"\ndescription = "d"\n+++\n# u\n'
    )
    concept(
        store,
        "unverifiable/unverifiable.md",
        '+++\ntype = "Area"\ndescription = "d"\nrevision = "abc1234"\n+++\n# v\n',
    )

    state = stale.knowledge_state([(root, store)], {}, exclude=".flw")
    assert state.files == 4
    assert state.orphaned == [f"{root.name}/orphan/orphan.md"]
    assert state.malformed and state.malformed[0].startswith(f"{root.name}/malformed")
    assert state.unstamped == [f"{root.name}/unstamped/unstamped.md"]
    # No repository here, so the diff cannot run and every stamped file is
    # unverifiable — which is exactly the state that reached no row before.
    assert state.unverifiable == [f"{root.name}/unverifiable/unverifiable.md"]
    assert state.changed == []


def test_a_knowledge_file_the_code_has_moved_under_reaches_the_changed_row(tmp_path, monkeypatch):
    """The `changed` branch, which carries a measurement where the other three
    carry only a name. Stubbed at knowledge.numstat rather than run against a real
    repository, the way test_knowledge.py cans every other diff."""
    root = project(tmp_path, first='summary = "s"\n')
    store = root / ".flw" / "knowledge"
    (root / "src").mkdir()
    concept(
        store,
        "src/src.md",
        '+++\ntype = "Area"\ndescription = "d"\nrevision = "abc1234"\n+++\n# src\n',
    )
    monkeypatch.setattr(
        knowledge, "numstat", lambda *a, **k: knowledge.Diff("changed", 3, 41, 12)
    )
    state = stale.knowledge_state([(root, store)], {}, exclude=".flw")
    assert state.changed == [f"{root.name}/src/src.md — 3 files · +41 −12"]
    assert state.unverifiable == []


# --- the extension and note halves are folded, not re-implemented ------------- #


def test_the_extension_markers_reach_the_block(tmp_path):
    root = project(tmp_path, first='summary = "s"\n')
    directory = root / ".flw" / "extensions"
    directory.mkdir(parents=True)
    (directory / "shared.md").write_text("**Python 3.11 is the floor**, for `tomllib`.\n")
    text = stale.fold(root, exclude=".flw")
    assert "EXTENSIONS  (1)" in text
    assert "shared.md:11" not in text
    assert "shared.md:1  3.11" in text


def test_a_note_with_no_revision_reaches_the_block(tmp_path):
    """`stale` calls `store.unrevisioned` rather than parsing what `store.lint`
    renders, so the count in the block and the row in the lint cannot disagree."""
    import store as note_store

    root = project(tmp_path, first='summary = "s"\n')
    home = tmp_path / "flw-home"
    (home / "kb" / "flw").mkdir(parents=True)
    (home / "kb" / "flw" / "counts.md").write_text(
        "+++\ntitle = 'counts'\n+++\nThe row is built at `core/scripts/scout.py:478`.\n"
    )
    notes = note_store.walk(home, None)
    text = stale.fold(root, exclude=".flw", notes=notes)
    assert "NOTES  (1)" in text
    assert "flw/counts — e.g. core/scripts/scout.py:478" in text


# --- flw stale --owed --------------------------------------------------------- #
#
# Red only on what is never true in the middle of a normal flw-execute run. The
# fixtures are real repositories, because the row under test is a reading of git
# history and a canned answer would hold only the parsing.

if "flw_cli" in sys.modules:
    flw = sys.modules["flw_cli"]
else:
    import importlib.util

    _spec = importlib.util.spec_from_file_location(
        "flw_cli", Path(__file__).resolve().parent.parent / "cli" / "flw.py"
    )
    flw = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = flw
    _spec.loader.exec_module(flw)

OWED_CONTRACT = """schema_version = 4
spec_version = "0.1"
applied = [{applied}]

[[final_state.components]]
name = "the thing"
paths = ["src/"]
provides = ["A user can do the thing."]

[[final_state.components]]
name = "the surface"
paths = ["plans/"]
provides = ["A user can read the plans."]
"""

needs_git = pytest.mark.skipif(GIT is None, reason="git not on PATH")


def contract(root: Path, *applied: str) -> None:
    (root / "specs" / "versions").mkdir(parents=True, exist_ok=True)
    names = ", ".join(f'"{n}"' for n in applied)
    (root / "specs" / "current.toml").write_text(OWED_CONTRACT.format(applied=names))


def record(root: Path, name: str) -> None:
    (root / "specs" / "versions").mkdir(parents=True, exist_ok=True)
    (root / "specs" / "versions" / f"{name}-minor.toml").write_text(
        f'name = "{name}"\nsummary = "s"\n'
    )


def commit(root: Path, message: str, files: dict[str, str] | None = None) -> None:
    """Write each file, then commit everything."""
    for rel, text in (files or {}).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    ident = ["-c", "user.email=flw@example.invalid", "-c", "user.name=flw", "-c", "commit.gpgsign=false"]
    if not (root / ".git").exists():
        subprocess.run([GIT, "init", "--initial-branch=main", str(root)], capture_output=True, check=True)
    for args in (["add", "-A"], ["commit", "-m", message]):
        subprocess.run([GIT, *ident, *args], cwd=root, capture_output=True, text=True, check=True)


def landed(root: Path, *applied: str) -> Path:
    """A repository whose last commit applied these names."""
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "x.py").write_text("x = 0\n")
    contract(root, *applied)
    commit(root, "land")
    return root


def run_owed(root: Path, capsys, *extra: str) -> tuple[int, str]:
    code = flw.main(["flw", "stale", "--root", str(root), *extra])
    return code, capsys.readouterr().out


def short(root: Path) -> str:
    return subprocess.run(
        [GIT, "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


@needs_git
def test_owed_an_unapplied_record_and_an_unstamped_file_are_listed_not_red(tmp_path, capsys):
    """The deadlock regression. Both are true in the middle of every flw-execute
    run, so a declared --owed that failed on either would stop the run that clears
    them."""
    root = landed(tmp_path, "first")
    record(root, "next")
    concept(
        root / ".flw" / "knowledge",
        "src/src.md",
        '+++\ntype = "Area"\ndescription = "d"\n+++\n# src\n',
    )
    code, out = run_owed(root, capsys, "--owed")
    assert code == 0
    assert "record not yet applied: next" in out
    assert f"unstamped knowledge file {root.name}/src/src.md" in out


@needs_git
def test_owed_a_retired_record_is_reported_as_retired_rather_than_owed(tmp_path, capsys):
    """The design turned and the record will never land, so counting it as work
    owed leaves a backlog nobody intends to clear."""
    root = landed(tmp_path, "first")
    record(root, "dead-end")
    (root / "specs" / "versions" / "first-minor.toml").write_text(
        'name = "first"\nsummary = "s"\nretires = ["dead-end"]\n'
    )
    code, out = run_owed(root, capsys, "--owed")
    assert code == 0
    assert "record retired: dead-end" in out
    assert "record not yet applied: dead-end" not in out


@needs_git
def test_owed_an_unapplied_records_retires_entry_is_ignored(tmp_path, capsys):
    """Gated on `applied`, so a draft nobody reviewed cannot empty the backlog and
    two parallel spec sessions cannot each retire the other's record."""
    root = landed(tmp_path, "first")
    record(root, "dead-end")
    (root / "specs" / "versions" / "draft-minor.toml").write_text(
        'name = "draft"\nsummary = "s"\nretires = ["dead-end"]\n'
    )
    code, out = run_owed(root, capsys, "--owed")
    assert code == 0
    assert "record not yet applied: dead-end" in out
    assert "record retired: dead-end" not in out


@needs_git
def test_owed_a_component_commit_with_nothing_in_flight_is_red(tmp_path, capsys):
    root = landed(tmp_path, "first")
    commit(root, "unagreed work", {"src/x.py": "x = 1\n"})
    code, out = run_owed(root, capsys, "--owed")
    assert code == 1
    assert f"commit {short(root)} after first landed: unagreed work" in out


@needs_git
def test_plain_stale_on_a_red_owed_project_still_exits_0(tmp_path, capsys):
    root = landed(tmp_path, "first")
    commit(root, "unagreed work", {"src/x.py": "x = 1\n"})
    code, _ = run_owed(root, capsys)
    assert code == 0


@needs_git
def test_owed_the_same_commit_with_a_record_in_flight_is_listed(tmp_path, capsys):
    root = landed(tmp_path, "first")
    record(root, "next")
    commit(root, "agreed work", {"src/x.py": "x = 1\n"})
    code, out = run_owed(root, capsys, "--owed")
    assert code == 0
    assert f"commit {short(root)} after first landed" in out


@needs_git
def test_owed_a_commit_confined_to_plans_is_not_counted(tmp_path, capsys):
    root = landed(tmp_path, "first")
    commit(root, "a design", {"plans/design.md": "# design\n"})
    code, out = run_owed(root, capsys, "--owed")
    assert code == 0
    assert "commit" not in out


@needs_git
def test_owed_a_commit_mixing_plans_with_a_component_is_counted(tmp_path, capsys):
    root = landed(tmp_path, "first")
    commit(root, "both", {"plans/design.md": "# design\n", "src/x.py": "x = 1\n"})
    code, _ = run_owed(root, capsys, "--owed")
    assert code == 1


def test_owed_with_no_git_repository_has_no_attribution_row(tmp_path, capsys):
    """Other rows still work: the unapplied record is listed."""
    (tmp_path / "src").mkdir()
    contract(tmp_path, "first")
    record(tmp_path, "next")
    assert stale.unattributed(tmp_path, {"applied": ["first"]}, "specs/current.toml", []) is None
    code, out = run_owed(tmp_path, capsys, "--owed")
    assert code == 0
    assert "commit" not in out
    assert "record not yet applied: next" in out


@needs_git
def test_two_names_sharing_one_landing_commit_resolve_to_it(tmp_path, capsys):
    root = landed(tmp_path, "first", "second")
    head = subprocess.run(
        [GIT, "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert stale.landing(root, "specs/current.toml", "first") == head
    assert stale.landing(root, "specs/current.toml", "second") == head
    code, _ = run_owed(root, capsys, "--owed")
    assert code == 0


def test_owed_a_malformed_knowledge_file_is_red(tmp_path, capsys):
    (tmp_path / "src").mkdir()
    contract(tmp_path, "first")
    concept(tmp_path / ".flw" / "knowledge", "src/src.md", '+++\ntype = "Area"\n+++\n# src\n')
    code, out = run_owed(tmp_path, capsys, "--owed")
    assert code == 1
    assert f"malformed knowledge file {tmp_path.name}/src/src.md" in out


@needs_git
def test_owed_the_execute_step_5_window_counts_the_new_name_as_in_flight(tmp_path, capsys):
    """flw-execute appends the name to applied before the commit that carries it.
    In that window nothing is unapplied, but git finds no landing for the new
    name, so the walk passes over it and the phase commits stay listed."""
    root = landed(tmp_path, "first")
    commit(root, "phase work", {"src/x.py": "x = 1\n"})
    contract(root, "first", "second")
    record(root, "second")
    code, out = run_owed(root, capsys, "--owed")
    assert code == 0
    assert "after first landed: phase work" in out


def test_owed_reads_components_under_final_state_not_a_top_level_key(tmp_path, monkeypatch):
    """The first measurement read a top-level `components` and reported the
    opposite of the truth."""
    answers = {
        "log -S": (0, "abc\n"),
        "log --relative": (0, "\x00abc1234 wrong place\nsrc/x.py\n"),
    }

    def canned(args, cwd):
        key = "log -S" if "-S" in args else "log --relative"
        return answers[key]

    monkeypatch.setattr(knowledge, "git", canned)
    top_level = {"applied": ["first"], "components": [{"paths": ["src/"]}]}
    assert stale.unattributed(tmp_path, top_level, "specs/current.toml", []).commits == []
    nested = {"applied": ["first"], "final_state": {"components": [{"paths": ["src/"]}]}}
    assert stale.unattributed(tmp_path, nested, "specs/current.toml", []).commits == [
        ("abc1234", "wrong place")
    ]


# --- a verdict with nothing behind it ---------------------------------------- #
#
# landing() drives every attribution row, so a name it cannot find means --owed
# reports nothing however much drift is in the history.


def single_quoted(root: Path, *applied: str) -> None:
    """The same contract, quoted the way TOML also permits."""
    (root / "specs" / "versions").mkdir(parents=True, exist_ok=True)
    names = ", ".join(f"'{n}'" for n in applied)
    (root / "specs" / "current.toml").write_text(OWED_CONTRACT.format(applied=names))


@needs_git
def test_owed_finds_a_landing_however_the_contract_quotes_the_name(tmp_path, capsys):
    """TOML reads 'x' and "x" as one value and the schema accepts both, so a
    pickaxe on the double-quoted form alone exited 0 over a drift commit that was
    sitting right there. Two trees identical but for the quote character."""
    for quoting, write in (("double", contract), ("single", single_quoted)):
        root = tmp_path / quoting
        (root / "src").mkdir(parents=True)
        (root / "src" / "x.py").write_text("x = 0\n")
        write(root, "first")
        commit(root, "land")
        commit(root, "drift", {"src/x.py": "x = 1\n"})

        code, out = run_owed(root, capsys, "--owed")
        assert code == 1, quoting
        assert "drift" in out, quoting


@needs_git
def test_a_contract_quoted_both_ways_in_its_history_resolves_to_the_oldest(tmp_path):
    """The report's suggested fix was two pickaxe calls concatenated, keeping
    found[-1]. Over two newest-first lists that is the oldest of the second call
    rather than the oldest overall, which is exactly this history."""
    root = tmp_path / "both"
    (root / "src").mkdir(parents=True)
    (root / "src" / "x.py").write_text("x = 0\n")
    single_quoted(root, "first")
    commit(root, "land, single-quoted")
    oldest = subprocess.run(
        [GIT, "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()
    contract(root, "first", "second")
    commit(root, "requote and apply another")

    assert stale.landing(root, "specs/current.toml", "first") == oldest


@needs_git
def test_a_record_name_containing_a_dot_is_not_read_as_a_pattern(tmp_path):
    """A legacy record is named 4.2, and an unescaped dot matches any character —
    so the pickaxe would answer about "4x2" as readily as about the real name."""
    root = tmp_path / "legacy"
    (root / "src").mkdir(parents=True)
    (root / "src" / "x.py").write_text("x = 0\n")
    contract(root, "4x2")
    commit(root, "a name that only an unescaped dot would match")

    assert stale.landing(root, "specs/current.toml", "4.2") is None


def test_a_system_file_whose_project_declares_no_members_is_unverifiable(tmp_path):
    """system_state takes an empty map through its three-way loop and answers
    "current", which by_state has no row for — so the file was counted in `files`
    and listed under nothing. A diff with nothing to run over is the word the
    contract already has."""
    store = tmp_path / "parent" / ".flw" / "knowledge"
    concept(
        store,
        "system.md",
        '+++\ntype = "System"\ndescription = "d"\n\n[revision]\nds = "abc1234"\n+++\n# system\n',
    )
    found = stale.knowledge_state([(tmp_path / "parent", store)], {}, exclude=".flw")
    assert found.files == 1
    assert found.unverifiable == ["parent/system.md"]
    assert found.changed == []
