"""budget.py — a byte ceiling on the files every run loads unconditionally."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core" / "scripts"))
import budget as engine


def _fake_repo(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(engine, "REPO", tmp_path)
    (tmp_path / "core" / "skills" / "alpha").mkdir(parents=True)
    (tmp_path / "core" / "skills" / "beta").mkdir(parents=True)
    (tmp_path / "core" / "shared").mkdir(parents=True)
    (tmp_path / "core" / "styles").mkdir(parents=True)
    (tmp_path / "core" / "skills" / "alpha" / "SKILL.md").write_text("x" * 10)
    (tmp_path / "core" / "skills" / "beta" / "SKILL.md").write_text("x" * 10)
    (tmp_path / "core" / "shared" / "context.md").write_text("x" * 10)
    (tmp_path / "core" / "styles" / "terse_prose.md").write_text("x" * 10)
    (tmp_path / "core" / "shared" / "ambient.md").write_text("x" * 10)
    (tmp_path / "core" / "shared" / "commits.md").write_text("x" * 10)
    return tmp_path


def test_all_under_budget_exits_zero(tmp_path, monkeypatch, capsys):
    _fake_repo(tmp_path, monkeypatch)

    assert engine.main() == 0
    assert "OVER" not in capsys.readouterr().out


def test_a_file_over_its_ceiling_exits_one_and_names_it(tmp_path, monkeypatch, capsys):
    """One assertion pins both ceilings and the whole file list: deleting the
    shared block passed all 638 tests and took the real command from six rows to
    four, at exit 0 both times."""
    repo = _fake_repo(tmp_path, monkeypatch)
    (repo / "core" / "skills" / "alpha" / "SKILL.md").write_text(
        "x" * (engine.SKILL_CEILING + 1)
    )
    (repo / "core" / "styles" / "terse_prose.md").write_text(
        "x" * (engine.SHARED_CEILING + 1)
    )
    (repo / "core" / "shared" / "ambient.md").write_text("x" * (engine.SHARED_CEILING + 1))
    (repo / "core" / "shared" / "commits.md").write_text("x" * (engine.SHARED_CEILING + 1))

    assert engine.main() == 1
    out, err = capsys.readouterr()
    assert "OVER" in out
    for name in (
        "core/skills/alpha/SKILL.md",
        "core/styles/terse_prose.md",
        "core/shared/ambient.md",
        "core/shared/commits.md",
    ):
        assert name in err, name


def test_the_file_list_comes_from_the_glob_not_a_name_typed_here(tmp_path, monkeypatch):
    """A fifth skill is measured the day it is added — nothing here names the
    four that exist when this test was written."""
    repo = _fake_repo(tmp_path, monkeypatch)
    (repo / "core" / "skills" / "gamma").mkdir()
    (repo / "core" / "skills" / "gamma" / "SKILL.md").write_text("x" * 10)

    skills = {
        path.parent.name for path, ceiling in engine.targets() if ceiling == engine.SKILL_CEILING
    }
    assert skills == {"alpha", "beta", "gamma"}
