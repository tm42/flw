"""Fixtures: a specs/ directory shaped exactly like a real one."""

from __future__ import annotations

from pathlib import Path

import pytest

CONTRACT = '''\
schema_version = 3
spec_version = "1.0"

# DO NOT REFLOW: this comment has  double  spaces and a trailing tab.\t
assumptions = ["the fixture is enough contract to work against"]

[final_state]
removed = [{ statement = "the thing that used to be here", check = "test ! -e gone" }]

[[final_state.components]]
name     = "alpha"
paths    = ["src/alpha.py"]
provides = ["a user can alpha"]

[[final_state.components]]
name     = "beta"
paths    = ["src/beta.py"]
provides = ["a user can beta", "a user can beta twice"]
implementation = "One file, no framework."

[success_criteria]
tests = [{ command = "true" }]
criteria = """
The fixture behaves.
Second line, kept to prove multi-line strings round-trip.
"""
'''

FIRST_VERSION = '''\
spec_version = "1.0"
name         = "1.0"
summary      = "the fixture's first contract"

[[dag]]
group = 1
phase = "build"
tasks = [{ id = "build-it", desc = "build the fixture" }]
'''


@pytest.fixture(autouse=True)
def _isolated_flw_home(tmp_path, monkeypatch):
    """No test reads the machine's own ~/.flw/config.toml or its $FLW_DIR.

    `_local_config` merges the config file underneath the project's, so a
    developer who uses the feature flw ships — `[tests] yours`, declared once
    for this machine — turned the suite red with a diff pointing at a fixture
    and nothing pointing at their home directory. `$FLW_DIR` is the same shape
    of leak one release later: every fixture writes a literal `.flw/`, so with
    the setting in force 48 tests looked for a directory nothing had written.
    """
    monkeypatch.setenv("FLW_HOME", str(tmp_path / "flw-home"))
    monkeypatch.delenv("FLW_DIR", raising=False)


@pytest.fixture
def specs(tmp_path: Path) -> Path:
    """A specs/ directory at version 1.0."""
    specs_dir = tmp_path / "specs"
    (specs_dir / "versions").mkdir(parents=True)
    (specs_dir / "current.toml").write_text(CONTRACT)
    (specs_dir / "versions" / "v1.0.toml").write_text(FIRST_VERSION)
    return specs_dir
