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
import ledger
import stale

CONTRACT = """schema_version = 4
spec_version = "0.1.0"
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
    root = project(
        tmp_path,
        first='summary = "s"\nsources = [".flw/reports/2026-09-03T2050-process.md"]\n',
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


# --- a project that has none of this ----------------------------------------- #


def test_a_project_with_no_reports_directory_folds_to_nothing(tmp_path):
    root = project(tmp_path, first='summary = "s"\n')
    found = fold(root)
    assert (found.spent, found.unread, found.dead, found.total) == ([], [], [], 0)


def test_the_whole_fold_runs_over_a_project_with_no_stores_at_all(tmp_path):
    """The exit-0 case the contract names: no reports directory, no knowledge
    store, no notes. It prints what it can rather than refusing."""
    root = project(tmp_path, first='summary = "s"\n')
    text = stale.fold(root)
    assert "no reports/ directory" in text
    assert "no store" in text
    assert "Nothing here is a failure" in text


def test_an_empty_knowledge_store_counts_no_files(tmp_path):
    root = project(tmp_path, first='summary = "s"\n')
    (root / ".flw" / "knowledge").mkdir(parents=True)
    assert stale.knowledge_state([(root, root / ".flw" / "knowledge")], {}).files == 0


def test_a_knowledge_file_describing_a_path_that_is_gone_is_orphaned(tmp_path):
    """No VCS needed for this one, and none is used: it is one stat per file."""
    root = project(tmp_path, first='summary = "s"\n')
    store = root / ".flw" / "knowledge"
    store.mkdir(parents=True)
    (store / "src").mkdir()
    (store / "src" / "engine.md").write_text(
        '+++\ntype = "area"\ndescription = "the engine"\nrevision = "abc1234"\n+++\n# src/engine\n'
    )
    state = stale.knowledge_state([(root, store)], {})
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
    state = stale.knowledge_state([(root, root / ".flw" / "knowledge")], {})
    assert state.files == 1
    assert state.unverifiable == [f"{root.name}/src/src.md"]
    assert state.changed == []
    assert "unverifiable  (1)" in stale.render(
        root, stale.Reports(root / ".flw" / "reports"), state, [], [], 0
    )


# --- the extension and note halves are folded, not re-implemented ------------- #


def test_the_extension_markers_reach_the_block(tmp_path):
    root = project(tmp_path, first='summary = "s"\n')
    directory = root / ".flw" / "extensions"
    directory.mkdir(parents=True)
    (directory / "shared.md").write_text("**Python 3.11 is the floor**, for `tomllib`.\n")
    text = stale.fold(root)
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
    text = stale.fold(root, notes=notes)
    assert "NOTES  (1)" in text
    assert "flw/counts — e.g. core/scripts/scout.py:478" in text
