"""Every script must work run directly, not only imported.

This is the regression for a real bug: a fallback import was `except ImportError:
pass`, which left a name undefined. Every test imported the package, so the
fallback branch was never taken and the failure was invisible — until the script
ran the way skills actually run it.

The subprocesses below deliberately run with no repo root on sys.path, which is
what forces the fallback branch. PYTHONPATH is cleared for the same reason.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "core" / "scripts"
SCHEMAS = REPO / "core" / "schemas"


def run_script(name: str, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO,
    )


def test_validate_spec_runs_directly(specs):
    result = run_script(
        "validate_spec.py",
        str(specs / "current.toml"),
        str(SCHEMAS / "spec-v3.schema.json"),
    )
    assert result.returncode == 0, result.stderr
    assert "OK:" in result.stdout


def test_validate_spec_checks_a_version_file(specs):
    result = run_script(
        "validate_spec.py",
        str(specs / "versions" / "v1.0.toml"),
        str(SCHEMAS / "version.schema.json"),
    )
    assert result.returncode == 0, result.stderr


def test_flw_own_specs_validate():
    """The acceptance check: flw validating flw, through the same command line a
    skill uses."""
    for target, schema in (
        (REPO / "specs" / "current.toml", "spec-v4.schema.json"),
        (REPO / "specs" / "versions" / "v1.0.toml", "version.schema.json"),
    ):
        result = run_script("validate_spec.py", str(target), str(SCHEMAS / schema))
        assert result.returncode == 0, result.stderr


def test_budget_runs_directly():
    result = run_script("budget.py")
    assert result.returncode == 0, result.stderr
    assert "SKILL.md" in result.stdout


def test_the_commit_rules_are_written_in_exactly_one_place():
    """One authority, cited rather than restated. A second copy is what drifts,
    and this file exists because the rules previously lived inside one skill
    where nothing outside a flw-execute run could see them."""
    authority = REPO / "core" / "shared" / "commits.md"
    assert authority.is_file()

    # The verb list and the trailer rule are the two passages a restatement
    # would carry. Neither may appear anywhere else that a reader is steered to.
    for phrase in ("robustify", "Co-Authored-By"):
        holders = sorted(
            path.relative_to(REPO).as_posix()
            for path in (REPO / "core").rglob("*.md")
            if phrase in path.read_text()
        )
        assert holders == ["core/shared/commits.md"], (phrase, holders)


def test_every_pointer_at_the_commit_rules_resolves():
    """A rename must not leave a skill citing nothing. Both files that steer a
    reader there name the path, so both are checked against the real file."""
    cited = "$FLW/core/shared/commits.md"
    for rel in ("core/shared/ambient.md", "core/skills/flw-execute/SKILL.md"):
        text = (REPO / rel).read_text()
        assert cited in text, rel
    assert (REPO / "core" / "shared" / "commits.md").is_file()


def test_the_cli_works_as_a_command_not_only_as_an_import(tmp_path):
    """The whole cycle, invoked the way a user invokes it.

    The version guard, the argparse dispatch and the exit-code plumbing all sit
    outside anything an in-process test reaches — and the bug this file exists
    for was exactly that shape.
    """
    fake = tmp_path / "home"
    (fake / ".claude").mkdir(parents=True)
    (fake / ".claude" / "CLAUDE.md").write_text("# Mine\n")
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env |= {"HOME": str(fake), "FLW_HOME": str(fake / ".flw")}

    def flw(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(REPO / "cli" / "flw.py"), *args],
            check=False, capture_output=True, text=True, env=env, cwd=REPO,
        )

    installed = flw("install", "claude-code", "--ambient", "--yes")
    assert installed.returncode == 0, installed.stderr
    assert (fake / ".claude" / "skills" / "flw-spec").is_symlink()

    checked = flw("doctor")
    assert checked.returncode == 0, checked.stdout + checked.stderr

    validated = flw("validate")
    assert validated.returncode == 0, validated.stderr

    removed = flw("uninstall", "claude-code")
    assert removed.returncode == 0, removed.stderr
    assert (fake / ".claude" / "CLAUDE.md").read_text() == "# Mine\n"
    assert not (fake / ".claude" / "skills" / "flw-spec").exists()
