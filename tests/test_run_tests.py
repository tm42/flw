"""The check runner: what it collects, what it runs, what it hands back.

Every test here covers something that would otherwise go wrong quietly — a source
skipped, a check that cannot run reported as a failure, or a setup command that
silently did not apply.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import signal
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # Registered before exec: these use `from __future__ import annotations`, and
    # @dataclass resolves its string annotations through sys.modules.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


engine = _load("flw_run_tests", REPO / "core" / "scripts" / "run_tests.py")
flw = _load("flw_cli", REPO / "cli" / "flw.py")


CONTRACT = """\
schema_version = 3
spec_version = "1.0"
assumptions = []

[final_state]
removed = [
  { statement = "the old thing", check = "test ! -e old_thing" },
  { statement = "a conceptual removal with no check" },
]

[[final_state.components]]
name = "a"
paths = ["a.py"]
provides = ["a user can a"]

[success_criteria]
tests = [{ command = "true" }]
criteria = "it works"
"""

@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "current.toml").write_text(CONTRACT)
    return tmp_path


def collect(root: Path, full: bool = True) -> list:
    return engine.collect(root, root / "specs", full=full)


# --- what gets collected -------------------------------------------------- #


def test_both_sources_are_collected(project):
    assert [(c.source, c.command) for c in collect(project)] == [
        ("contract", "true"),
        ("removed", "test ! -e old_thing"),
    ]


def test_a_removal_without_a_check_contributes_nothing(project):
    assert all("conceptual" not in c.command for c in collect(project))


def test_the_branch_set_replaces_the_contract_tests(project):
    """`[tests] checks` is this branch's targeted set. -A is the contract's
    definition of done. Removal checks run either way."""
    (project / ".flw").mkdir()
    (project / ".flw" / "config.toml").write_text(
        '[tests]\nchecks = ["pytest tests/unit", "ruff check ."]\n'
    )
    narrow = [(c.source, c.command) for c in collect(project, full=False)]
    assert narrow == [
        ("branch", "pytest tests/unit"),
        ("branch", "ruff check ."),
        ("removed", "test ! -e old_thing"),
    ]
    assert ("contract", "true") in [(c.source, c.command) for c in collect(project, full=True)]


# --- what happens when they run ------------------------------------------- #


def test_a_passing_check_is_timed_and_reported(project):
    result = engine.run_one(engine.Check("contract", "true"), project, "", 10, stream=False)
    assert result.state == "pass"
    assert result.seconds >= 0


def test_a_missing_command_is_a_failure_not_a_hand_back(project):
    """No exit code identifies a check this session cannot run. 127 is bash's
    "command not found", which an absent binary returns and `npm run <script>`
    also returns when a devDependency is missing; `cargo <sub>` returns 101 for an
    absent subcommand and for a compile failure alike. What cannot run here is
    declared in [tests] yours."""
    result = engine.run_one(
        engine.Check("contract", "definitely-not-a-real-command"), project, "", 10, stream=False
    )
    assert result.code == 127
    assert result.state == "fail"


def test_setup_is_prepended_so_a_venv_activation_persists(project):
    """Each check runs in its own shell, so `source` in one does not reach the
    next. Prepending is what makes a venv work at all."""
    result = engine.run_one(
        engine.Check("contract", "test \"$FLW_PROBE\" = yes"), project,
        "export FLW_PROBE=yes", 10, stream=False,
    )
    assert result.state == "pass"


def test_bash_is_explicit_so_source_works(project):
    """/bin/sh is dash on Debian and has no `source`. Running through bash
    explicitly is what stops a venv line failing on Linux and passing on macOS."""
    # Asserting the interpreter, not a feature of it: /bin/sh on macOS is bash,
    # so `[[ ]]` and `source` both work there and the test could not fail on the
    # machine it runs on.
    result = engine.run_one(
        engine.Check("contract", 'test "$0" = bash'), project, "", 10, stream=False
    )
    assert result.state == "pass", "not running under bash"


def test_a_hung_check_times_out_rather_than_hanging(project):
    result = engine.run_one(engine.Check("contract", "sleep 30"), project, "", 1, stream=False)
    assert result.state == "fail"
    assert "timed out" in result.output


def test_a_timeout_kills_what_the_check_forked(project, tmp_path):
    """The test above passes with a plain process.kill(), because bash execs a
    single simple command in place and killing bash kills the sleep. This is the
    case the process group exists for and the comment at run_tests.py:154 names:
    whatever bash forked — a runner, a dev server, whatever holds the port.

    Elapsed time is the assertion, not the child's pid, and that is measured
    rather than chosen. --no-stream captures to a pipe, and a surviving
    grandchild inherits the write end, so process.kill() leaves communicate()
    blocking on EOF until that child exits by itself — 31s for the 30s sleep
    below. By the time run_one returns, the pid is gone either way and a pid
    check passes against both. What the mutant actually breaks is the timeout:
    a 1s deadline that returns after 31.
    """
    pidfile = tmp_path / "child.pid"
    started = time.monotonic()
    result = engine.run_one(
        engine.Check("contract", f"sleep 30 & echo $! > {pidfile}; sleep 30"),
        project, "", 1, stream=False,
    )
    elapsed = time.monotonic() - started

    assert result.state == "fail" and "timed out" in result.output
    assert elapsed < 10, (
        f"the 1s timeout took {elapsed:.1f}s: the check's forked child outlived "
        "it and held the output pipe open"
    )
    pid = int(pidfile.read_text().strip())
    try:
        os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def test_a_prompting_check_fails_instead_of_hanging(project, tmp_path):
    """stdin is closed, so a command that asks a question in an agent session
    fails fast rather than waiting for an answer nobody can give.

    fd 0 is a held-open FIFO with nothing in it for the duration, because under
    pytest fd 0 is already not a terminal: `read` returns at once whether the
    guard is there or not, so without this the test passed with stdin inherited.
    Asserting the elapsed time is what separates failing from hanging — run_one
    returns "fail" for a timeout too.
    """
    fifo = tmp_path / "held"
    os.mkfifo(fifo)
    # O_RDWR so opening it does not block waiting for a writer.
    held = os.open(fifo, os.O_RDWR)
    saved = os.dup(0)
    try:
        os.dup2(held, 0)
        result = engine.run_one(
            engine.Check("contract", "read -r line"), project, "", 2, stream=False
        )
    finally:
        os.dup2(saved, 0)
        os.close(saved)
        os.close(held)
    assert result.state == "fail"
    assert result.seconds < 1, "it hung until the timeout rather than failing fast"


def test_checks_run_from_the_project_root_not_the_cwd(project, monkeypatch):
    (project / "marker").write_text("")
    monkeypatch.chdir(sys.prefix)
    result = engine.run_one(engine.Check("contract", "test -e marker"), project, "", 10, stream=False)
    assert result.state == "pass"


# --- the CLI around it ----------------------------------------------------- #


def run_cli(root: Path, full: bool = False) -> int:
    return flw.test(
        argparse.Namespace(path=str(root), all=full, timeout=30, stream=False)
    )


# --- shape-independence: captured output carries no terminal escapes ------ #


def test_ansi_escapes_do_not_reach_a_captured_report(project, capsys):
    """--no-stream captures to a pipe. cargo fmt --check colours its diff anyway,
    and that is the mode agents read and the text that lands in .flw/reports/."""
    result = engine.run_one(
        engine.Check("contract", r"printf '\033[31m-red\033[m\n'; exit 1"),
        project, "", 10, stream=False,
    )
    assert "\033[31m" in result.output, "the fixture must actually emit escapes"
    engine.report([result], [])
    printed = capsys.readouterr().out
    assert "-red" in printed
    assert "\033[" not in printed


def test_a_failing_check_exits_one(project, capsys):
    (project / "old_thing").write_text("still here")
    assert run_cli(project, full=True) == 1
    assert "1 failed" in capsys.readouterr().out


def test_everything_passing_exits_zero(project, capsys):
    assert run_cli(project, full=True) == 0
    assert "2 passed" in capsys.readouterr().out


def test_a_project_declaring_nothing_is_a_usage_error(tmp_path, capsys):
    """Reporting an empty run as green is how "everything passed" stops meaning
    anything, and it is the state every project starts in."""
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "current.toml").write_text(
        CONTRACT.replace('tests = [{ command = "true" }]\n', "").replace(
            '  { statement = "the old thing", check = "test ! -e old_thing" },\n', ""
        )
    )
    assert run_cli(tmp_path, full=True) == 2
    assert "Nothing to run" in capsys.readouterr().err


def test_checks_the_agent_cannot_run_are_handed_back(project, capsys, monkeypatch):
    """The sandbox case: declared, not run here, listed for the human. A branch
    run passes; -A does not, because a declared hand-back is the only kind there
    is now and the full definition of done was still not demonstrated."""
    monkeypatch.setenv("FLW_HOME", str(project / "no-global"))
    (project / ".flw").mkdir()
    (project / ".flw" / "config.toml").write_text(
        '[tests]\nchecks = ["true", "test ! -e old_thing"]\nyours = ["true"]\n'
    )
    assert run_cli(project) == 0
    out = capsys.readouterr().out
    assert "1 for you" in out
    assert "run `flw test` in your own shell" in out
    assert run_cli(project, full=True) == 2


def test_a_project_with_no_contract_still_runs_its_own_checks(tmp_path):
    """The state flw-research leaves a repo in: local [tests] checks, no specs/
    at all. Reading the contract unconditionally killed `flw test` there with a
    traceback instead of running the checks just declared."""
    (tmp_path / ".flw").mkdir()
    (tmp_path / ".flw" / "config.toml").write_text(
        '[tests]\nchecks = ["pytest tests/ -q", "ruff check ."]\n'
    )
    found = engine.collect(tmp_path, tmp_path / "specs", full=True)
    assert [c.command for c in found] == ["pytest tests/ -q", "ruff check ."]


def test_no_contract_and_no_local_config_collects_nothing(tmp_path):
    """Nothing to run is exit 2 at the CLI, not a crash and not a pass."""
    assert engine.collect(tmp_path, tmp_path / "specs", full=True) == []


# --- v4.1: a failing setup fails every check rather than skipping them ---- #


def test_a_broken_setup_fails_with_its_own_error_text(project, monkeypatch):
    """A setup line naming a command bash cannot find exits before the check runs.
    What the reader needs is the setup's error, not the check's silence."""
    monkeypatch.setenv("FLW_HOME", str(project / "no-global"))
    result = engine.run_one(
        engine.Check("contract", "true"), project, "definitely-not-a-real-setup-command", 10,
        stream=False,
    )
    assert result.state == "fail"
    assert "not-a-real-setup-command" in result.output


def test_a_broken_setup_fails_every_check_at_the_cli(project, capsys, monkeypatch):
    monkeypatch.setenv("FLW_HOME", str(project / "no-global"))
    (project / ".flw").mkdir()
    (project / ".flw" / "config.toml").write_text(
        '[tests]\nsetup = "definitely-not-a-real-setup-command"\n'
    )
    assert run_cli(project, full=True) == 1
    assert "2 failed" in capsys.readouterr().out


# --- v4.1: an unparseable contract is named, not a traceback ------------- #


def test_an_unparseable_contract_is_a_named_error_not_a_traceback(tmp_path):
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "current.toml").write_text("not = [valid toml")
    with pytest.raises(SystemExit, match="does not parse"):
        engine.collect(tmp_path, tmp_path / "specs", full=True)


# --- v4.1: the global config underlay ------------------------------------ #


def test_a_global_yours_applies_where_no_project_config_exists(project, monkeypatch, tmp_path):
    home = tmp_path / "home"
    (home).mkdir()
    (home / "config.toml").write_text('[tests]\nyours = ["true"]\n')
    monkeypatch.setenv("FLW_HOME", str(home))
    assert engine._local_config(project) == {"yours": ["true"]}


def test_a_project_key_wins_over_a_global_key_of_the_same_name(project, monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.toml").write_text('[tests]\nsetup = "from global"\n')
    monkeypatch.setenv("FLW_HOME", str(home))
    (project / ".flw").mkdir()
    (project / ".flw" / "config.toml").write_text('[tests]\nsetup = "from project"\n')
    assert engine._local_config(project)["setup"] == "from project"


def test_flw_dir_relocates_the_project_config(project, monkeypatch, tmp_path):
    """run_tests.py reads $FLW_DIR the way it already reads $FLW_HOME, so a
    renamed per-project directory is found without importing cli/flw.py, and a
    stale one under the old name is not."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("FLW_HOME", str(home))
    monkeypatch.setenv("FLW_DIR", ".cache/flw")
    (project / ".cache" / "flw").mkdir(parents=True)
    (project / ".cache" / "flw" / "config.toml").write_text('[tests]\nsetup = "from relocated"\n')
    (project / ".flw").mkdir()
    (project / ".flw" / "config.toml").write_text('[tests]\nsetup = "from stale default"\n')
    assert engine._local_config(project)["setup"] == "from relocated"


# --- v4.1: yours covering everything is exit 2, not a silent pass -------- #


def test_yours_covering_every_check_exits_two_not_zero(project, capsys, monkeypatch):
    monkeypatch.setenv("FLW_HOME", str(project / "no-global"))
    (project / ".flw").mkdir()
    (project / ".flw" / "config.toml").write_text('[tests]\nyours = ["true", "test ! -e old_thing"]\n')
    assert run_cli(project, full=True) == 2
    assert "nothing left to run" in capsys.readouterr().err


# --- v4.1: a multi-line check is refused, not silently mis-scored -------- #


def test_a_multiline_check_is_refused_by_name(tmp_path):
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "current.toml").write_text(
        '[success_criteria]\ntests = [{ command = "false\\necho x" }]\ncriteria = "x"\n'
    )
    with pytest.raises(SystemExit, match="more than one line"):
        engine.collect(tmp_path, tmp_path / "specs", full=True)


def test_a_setup_spanning_more_than_one_line_is_refused(project):
    """bash reports only the last line's exit status, so `|| exit 125` bound to
    the last line alone. A setup whose venv activation failed let every check run
    against the wrong interpreter and the run reported a pass with exit 0.
    _check refuses this for a check command; setup had no equivalent."""
    (project / ".flw").mkdir()
    (project / ".flw" / "config.toml").write_text(
        '[tests]\nsetup = """source .venv/bin/activate\nexport PYTHONPATH=src"""\n'
        'checks = ["true"]\n'
    )
    with pytest.raises(SystemExit) as caught:
        engine._local_config(project)
    assert "more than one line" in str(caught.value)


# --- what a run reports, and what it calls done ----------------------------- #


def test_a_failure_shows_its_whole_output(project, capsys):
    """Six lines was a bet that the useful part is at the end. For a pytest
    failure the assertion is at the top, which is exactly what got cut."""
    # The lines are generated, not written into the command: report echoes the
    # command above its output, so a check naming them would satisfy the
    # assertions from the echo alone and pin nothing.
    (project / ".flw").mkdir()
    (project / ".flw" / "config.toml").write_text(
        '[tests]\nchecks = ["seq -f \'line-%02g\' 12 ; false"]\n'
    )
    run_cli(project)
    out = capsys.readouterr().out
    assert "line-01" in out, "the head of the output was cut"
    assert "line-12" in out


def test_failures_are_named_again_at_the_end(project, capsys):
    (project / "old_thing").write_text("still here")
    run_cli(project, full=True)
    out = capsys.readouterr().out
    assert "failed:" in out
    assert out.index("1 failed") < out.index("failed:"), "the list belongs after the summary"


BARE_CONTRACT = """\
schema_version = 3
spec_version = "1.0"
assumptions = []

[final_state]
removed = []

[[final_state.components]]
name = "a"
paths = ["a.py"]
provides = ["a user can a"]

[success_criteria]
tests = [__CHECKS__]
criteria = "it works"
"""


def bare(tmp_path: Path, *commands: str) -> Path:
    """A project declaring exactly these checks and no removals, so nothing else
    runs to make the outcome look more productive than it was."""
    root = tmp_path / "bare"
    (root / "specs").mkdir(parents=True)
    declared = ", ".join("{ command = " + repr(c).replace("'", '"') + " }" for c in commands)
    (root / "specs" / "current.toml").write_text(
        BARE_CONTRACT.replace("__CHECKS__", declared)
    )
    return root


def test_a_full_run_that_had_to_hand_a_check_back_is_not_success(tmp_path, capsys, monkeypatch):
    """-A is the contract's full definition of done. A check the project handed
    back means the definition was not demonstrated, whoever is running it: a user
    who can run it declares nothing and still gets 0."""
    root = bare(tmp_path, "true", "test -d specs")
    monkeypatch.setenv("FLW_HOME", str(root / "no-global"))
    (root / ".flw").mkdir()
    (root / ".flw" / "config.toml").write_text('[tests]\nyours = ["test -d specs"]\n')
    assert run_cli(root, full=True) == 2
    assert "not the full definition of done" in capsys.readouterr().err


def test_a_branch_run_that_hands_a_check_back_still_passes(project, capsys, monkeypatch):
    """Declaring one check as unrunnable must not turn every green run red."""
    monkeypatch.setenv("FLW_HOME", str(project / "no-global"))
    (project / ".flw").mkdir()
    (project / ".flw" / "config.toml").write_text(
        '[tests]\nchecks = ["true", "false"]\nyours = ["false"]\n'
    )
    assert run_cli(project) == 0


def test_a_missing_command_is_reported_failed_at_the_cli(tmp_path, capsys, monkeypatch):
    """The guard for deleting automatic detection. A check whose command does not
    exist is a failure and is never printed as handed back — reinstating the 127
    branch fails here by name."""
    root = bare(tmp_path, "definitely-not-a-real-command")
    monkeypatch.setenv("FLW_HOME", str(root / "no-global"))
    assert run_cli(root, full=True) == 1
    out = capsys.readouterr().out
    assert "1 failed" in out
    assert "this one is yours" not in out
