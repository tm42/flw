"""The style checker — two rule sets, and the boundary between them.

The boundary is the whole design. One rule set over both corpora was measured at
33 findings of which 17 were false, so vocabulary never reads a file and geometry
never reads a reply. Most of what follows tests that boundary rather than the
patterns, because a pattern that fires on the wrong corpus is the failure this
file exists to catch.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core" / "scripts"))
import style_lint

REPO = Path(__file__).resolve().parent.parent


def _file(text: str, name: str = "note.md") -> list[tuple[int, str, str]]:
    return style_lint.findings(Path(name), text)


def _rules(found: list[tuple[int, str, str]]) -> set[str]:
    return {name for _, name, _ in found}


# --- files: geometry, and nothing else ------------------------------------- #


def test_untagged_fence_is_a_finding():
    found = _file("text\n\n```\nls\n```\n")
    assert _rules(found) == {"fence-untagged"}
    assert found[0][0] == 3


def test_tagged_fence_is_not():
    assert _file("text\n\n```sh\nls\n```\n") == []


def test_heading_past_three_hashes():
    assert "heading-depth" in _rules(_file("#### too deep\n"))
    assert _file("### deep enough\n") == []


def test_trailing_spaces_in_a_file():
    assert "trailing-spaces" in _rules(_file("a line  \nanother\n"))


def test_vocabulary_never_reads_a_file():
    """The 52% false-positive rate that produced the split, in one line each.

    Every string here appeared in flw's own documents and every one is correct
    prose: a quoted user phrase, `honest` as a predicate, a documented symbol.
    """
    for text in (
        "| break it, security, robustness, what if | `adversarial` |\n",
        "partial and honest beats complete and late\n",
        "Anything genuinely open goes in the record.\n",
        "`✗` is a failure — a link that is dangling or stale\n",
        "✅ \"A user can recover a note deleted in the last 30 days.\"\n",
    ):
        assert _file(text) == [], text


def test_geometry_only_applies_to_markdown():
    assert _file("#### not a heading here\n", name="script.py") == []


def test_fenced_content_is_skipped():
    assert _file("```text\n#### inside a fence\n```\n") == []


def test_the_style_file_is_never_walked(tmp_path):
    """It states its bans by quoting them, so it cannot be checked against itself."""
    (tmp_path / "terse_prose.md").write_text("#### deep\n")
    (tmp_path / "other.md").write_text("#### deep\n")
    assert style_lint.walk([tmp_path])[0] == [tmp_path / "other.md"]


# --- a target that could not be read is not a target that was clean --------- #


def _lint(argv: list[str]) -> int:
    return style_lint.main(["style_lint", *argv])


def test_a_missing_path_exits_2_and_does_not_print_clean(tmp_path, capsys, monkeypatch):
    """The finding: it printed the path, then reported the run clean at exit 0, so
    a job running this against a renamed directory passed on a walk of nothing."""
    monkeypatch.chdir(tmp_path)
    assert _lint(["no-such-file.md"]) == 2
    captured = capsys.readouterr()
    assert "no such path: no-such-file.md" in captured.err
    assert "clean" not in captured.out


def test_a_file_that_will_not_open_exits_2_and_names_it(tmp_path, capsys, monkeypatch):
    """Named explicitly, so the walk resolves it and `report` is where it fails."""
    unreadable = tmp_path / "locked.md"
    unreadable.write_text("# fine\n")
    unreadable.chmod(0o000)
    monkeypatch.chdir(tmp_path)
    try:
        code = _lint([str(unreadable)])
    finally:
        unreadable.chmod(0o644)
    assert code == 2
    out = capsys.readouterr().out
    assert "locked.md" in out and "could not be read" in out
    assert "clean" not in out


def _unreadable(directory: Path) -> bool:
    """Whether chmod actually took. It does not for root, and not on every
    filesystem, and a test that cannot build its own fixture is a skip."""
    directory.chmod(0o000)
    try:
        list(directory.iterdir())
    except PermissionError:
        return True
    return False


def test_a_directory_that_cannot_be_walked_exits_2_and_is_named(tmp_path, capsys, monkeypatch):
    """rglob swallows a PermissionError on a directory and yields nothing, and a
    walk that yielded nothing is indistinguishable from a directory holding no
    prose. This is the same false green a missing path was fixed for, one level
    up."""
    locked = tmp_path / "docs"
    locked.mkdir()
    (locked / "a.md").write_text("# fine\n")
    if not _unreadable(locked):
        locked.chmod(0o755)
        pytest.skip("chmod cannot make a directory unreadable here")
    monkeypatch.chdir(tmp_path)
    try:
        code = _lint(["docs"])
    finally:
        locked.chmod(0o755)
    assert code == 2
    captured = capsys.readouterr()
    assert "docs" in captured.err
    assert "clean" not in captured.out


def test_an_unreadable_subdirectory_under_the_walk_root_exits_2(tmp_path, capsys, monkeypatch):
    """The case that matters, because `style_lint.py .` is a declared check and any
    subdirectory under it is in the walk. Reproduced at exit 0 before this."""
    (tmp_path / "fine.md").write_text("# fine\n")
    locked = tmp_path / "docs"
    locked.mkdir()
    (locked / "a.md").write_text("# fine\n")
    if not _unreadable(locked):
        locked.chmod(0o755)
        pytest.skip("chmod cannot make a directory unreadable here")
    monkeypatch.chdir(tmp_path)
    try:
        code = _lint(["."])
    finally:
        locked.chmod(0o755)
    assert code == 2
    assert "docs" in capsys.readouterr().err


def test_a_readable_tree_still_walks_every_level(tmp_path, capsys, monkeypatch):
    """The other half of the walk change: nesting, SKIP_DIRS and the suffix filter
    all still hold, and a finding below the root still reaches exit 1."""
    (tmp_path / "fine.md").write_text("# fine\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ok.md").write_text("# also fine\n")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "vendored.md").write_text("#### deep\n")
    monkeypatch.chdir(tmp_path)
    assert _lint(["."]) == 0
    assert "clean" in capsys.readouterr().out

    (tmp_path / "docs" / "deep.md").write_text("#### deep\n")
    assert _lint(["."]) == 1
    assert "1 finding" in capsys.readouterr().out


def test_one_good_target_and_one_missing_still_exits_2(tmp_path, capsys, monkeypatch):
    """A partial walk proves nothing about the target it never opened, so the good
    half must not carry the run to 0."""
    (tmp_path / "fine.md").write_text("# fine\n")
    monkeypatch.chdir(tmp_path)
    assert _lint(["fine.md", "gone.md"]) == 2
    assert "clean" not in capsys.readouterr().out


def test_a_finding_still_exits_1(tmp_path, capsys, monkeypatch):
    (tmp_path / "deep.md").write_text("#### deep\n")
    monkeypatch.chdir(tmp_path)
    assert _lint(["deep.md"]) == 1
    assert "1 finding" in capsys.readouterr().out


def test_a_finding_beats_a_missing_target(tmp_path, capsys, monkeypatch):
    """Prose that is wrong is something the run did prove, so 1 wins over 2."""
    (tmp_path / "deep.md").write_text("#### deep\n")
    monkeypatch.chdir(tmp_path)
    assert _lint(["deep.md", "gone.md"]) == 1


def test_a_clean_run_over_real_targets_still_exits_0(tmp_path, capsys, monkeypatch):
    (tmp_path / "fine.md").write_text("# fine\n")
    monkeypatch.chdir(tmp_path)
    assert _lint([str(tmp_path)]) == 0
    assert "style lint: clean" in capsys.readouterr().out


# --- the repository itself ------------------------------------------------- #


def test_the_shipped_style_file_has_the_rules_the_checker_claims():
    """A rule whose sentence has left the style file is a rule nobody agreed to."""
    text = (REPO / "core" / "styles" / "terse_prose.md").read_text()
    for phrase in ("Tag every code fence with its language",):
        assert phrase in text, phrase


def test_the_three_narrowed_words_are_in_neither_rule_set():
    """`clean`, `actually` and `surface` are narrowed in the style, so no pattern
    may ban them.

    The first two were 240 of roughly 356 measured vocabulary violations precisely
    because both have uses the style permits. `surface` joined them at 260 uses in
    166,185 words, against a contract with a field of that name. The word rules
    that would have banned them are gone, and this stays as the guard against one
    being written back in: a pattern reintroducing any of the three puts the
    checker at odds with the sentence it is supposed to enforce.
    """
    patterns = " ".join(p.pattern for _, p, _ in style_lint.FILE_RULES)
    assert "clean" not in patterns
    assert "actually" not in patterns
    assert "surface" not in patterns


def test_the_style_file_still_narrows_them():
    """The other half of the same guard: the sentence must keep permitting them."""
    text = (REPO / "core" / "styles" / "terse_prose.md").read_text()
    assert "*actually*" in text
    assert "*clean* as a claim about quality" in text
    assert "*surface* as a verb" in text
