"""The fold over the four stores flw writes into.

Most of what `flw stale` prints belongs to a store's own lint and is tested where
that lint lives. What is only here is the report split: which reports a record has
already acted on, which nobody has read, and which names a record cites with no
file behind them. Both directions of that fold matter, because neither is complete
alone — a record can name a report that has since been deleted, and a report can
carry a record's name whose prose never names its path.
"""

from __future__ import annotations

import sys
from pathlib import Path

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
