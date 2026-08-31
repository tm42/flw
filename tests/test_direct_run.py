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
