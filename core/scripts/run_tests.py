"""Run a project's declared tests. Stdlib only.

flw asserts nothing about whether work is done — no flag, no verdict. This runs
what a project declared, reports what happened, and hands back anything it could
not run. The exit code answers one question: did something I actually ran fail.

Checks come from three places and the split is deliberate. The **contract** carries
the definition of done, which is portable and part of the agreement. **.flw/config.toml**
carries how to invoke things on this machine and which narrower set is worth
running while you work — local facts, committed with the branch that needs them.

    [tests] checks               this branch's targeted set   (flw test)
    success_criteria.tests       the definition of done       (flw test -A)
    final_state.removed[].check  a deleted thing is really gone   (always)

Commands run through bash, explicitly rather than through /bin/sh: `source` is
not POSIX and a venv activation is the common case. There is no runner
allow-list. v2 had one and its own docstring admitted `python -m` executes
arbitrary code — restricting the runner cannot restrict what the runner does. The
commands come out of files in the project, at the same trust level as a Makefile.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

SETUP_FAILED = 125  # non-zero, so a failing setup fails the check; never read back


@dataclass
class Check:
    source: str
    command: str


@dataclass
class Result:
    check: Check
    code: int
    output: str
    seconds: float

    @property
    def state(self) -> str:
        # No exit code identifies a check this session cannot run. 127 is bash's
        # "command not found", which fires for an absent binary and also for
        # `npm run <script>` whose devDependency is missing, while `cargo <sub>`
        # returns 101 for both an absent subcommand and a compile failure. What
        # cannot run here is declared in [tests] yours; nothing is inferred.
        return "pass" if self.code == 0 else "fail"


def _parse_toml(path: Path) -> dict:
    """A file that fails to parse dies here, named, rather than in a traceback
    that a caller checking only the exit code would read as "something failed"."""
    try:
        return tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise SystemExit(f"error: {path} does not parse: {exc}") from None


def _check(source: str, command: str) -> Check:
    # bash reports only the last line's exit status, so a multi-line command
    # would let an earlier failing line pass silently — the version's own
    # defect class, in the one place a user writes the command by hand.
    if "\n" in command:
        raise SystemExit(
            f"error: a {source!r} check spans more than one line, which bash would "
            f"report only the last line's exit status for: {command!r}"
        )
    return Check(source, command)


def collect(root: Path, specs: Path, full: bool) -> list[Check]:
    # A contract is optional. `flw-research` configures a repo it did not spec —
    # local [tests] checks and no specs/ at all is a normal, supported state, and
    # reading the contract unconditionally made `flw test` die there with a
    # traceback instead of running the checks the user had just declared.
    path = specs / "current.toml"
    contract = _parse_toml(path) if path.exists() else {}
    local = _local_config(root)

    checks: list[Check] = []
    declared = contract.get("success_criteria", {}).get("tests", [])
    branch = local.get("checks", [])

    # -A means the contract's full definition of done. With no contract there is
    # no such thing, so it falls back to the branch set rather than to silence —
    # returning nothing here would turn a crash into an empty run that reports
    # "nothing to do" for a project that had just declared what to do.
    if (full or not branch) and declared:
        checks += [_check("contract", d["command"]) for d in declared]
    else:
        checks += [_check("branch", c) for c in branch]

    for removal in contract.get("final_state", {}).get("removed", []):
        if removal.get("check"):
            checks.append(_check("removed", removal["check"]))

    return checks


def _tests_section(path: Path) -> dict:
    if not path.exists():
        return {}
    config = _parse_toml(path)
    # The section was called [gates] until the rename. Silently returning {} for a
    # file that plainly declares commands is the empty-run-reads-as-a-pass failure
    # this tool already shipped once, so say it instead.
    if "gates" in config and "tests" not in config:
        raise SystemExit(f"error: {path} still says [gates] — rename it to [tests]")
    return config.get("tests", {})


def _local_config(root: Path) -> dict:
    # ~/.flw/config.toml (or $FLW_HOME) is the underlay: facts about this machine
    # — a check that cannot run here — that would otherwise have to be repeated
    # in every repo worked in. The project file wins key by key.
    global_path = Path(os.environ.get("FLW_HOME", str(Path.home() / ".flw"))) / "config.toml"
    merged = dict(_tests_section(global_path))
    flw_dir = os.environ.get("FLW_DIR", ".flw")
    merged.update(_tests_section(root / flw_dir / "config.toml"))
    # Same reason _check refuses a multi-line command: `|| exit` attaches to the
    # last line only, so a setup whose first line failed would let every check run
    # in the wrong environment and report a pass.
    if "\n" in str(merged.get("setup", "")):
        raise SystemExit(
            "error: a 'setup' spanning more than one line would let an earlier "
            "failing line pass silently — join the lines with && , or call a script"
        )
    return merged


def run_one(check: Check, root: Path, setup: str, timeout: int, stream: bool) -> Result:
    command = f"{setup} || exit {SETUP_FAILED}\n{check.command}" if setup else check.command
    started = time.monotonic()
    process = subprocess.Popen(
        ["bash", "-c", command],
        cwd=root,
        # No stdin: a command that prompts should fail fast rather than hang
        # forever in a session where nobody can answer it.
        stdin=subprocess.DEVNULL,
        # Merged, so the tail of a failure reads in the order it happened.
        stdout=None if stream else subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        # Its own process group. A timeout that kills only bash leaves whatever
        # bash forked — a test runner, a dev server, whatever holds the port —
        # running after flw has told the user the check ended.
        start_new_session=True,
    )
    try:
        out, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        process.communicate()
        return Result(check, 1, f"timed out after {timeout}s", timeout)
    return Result(check, process.returncode, out or "", time.monotonic() - started)


# --no-stream captures to a pipe, and a tool that colours anyway sends its escapes
# straight into the report an agent reads and into .flw/reports/. pytest and ruff
# drop colour on a non-tty, which is why flw's own suite never produced one.
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def report(results: list[Result], skipped: list[str]) -> None:
    width = min(max((len(r.check.command) for r in results), default=0), 52)
    mark = {"pass": "✓", "fail": "✗"}

    for r in results:
        secs = f"{r.seconds:>6.1f}s"
        print(f"  {mark[r.state]} {r.check.command:<{width}}  {secs}  [{r.check.source}]")
        if r.state == "fail":
            # All of it. Six lines was a bet that the useful part is at the end,
            # and for a pytest failure the assertion is at the top.
            for line in ANSI.sub("", r.output).strip().splitlines():
                print(f"      {line}")

    for command in skipped:
        print(f"  → {command:<{width}}            [yours]")

    passed = sum(1 for r in results if r.state == "pass")
    failed = sum(1 for r in results if r.state == "fail")
    yours = len(skipped)

    parts = [f"{passed} passed"]
    if failed:
        parts.append(f"{failed} failed")
    if yours:
        parts.append(f"{yours} for you")
    print(f"\n  {' · '.join(parts)}")

    if failed:
        # Again, together, at the end: printed where they happened, the failures
        # of a twenty-check run are somewhere up the scrollback and the summary
        # says only how many.
        print("\n  failed:")
        for r in results:
            if r.state == "fail":
                print(f"    ✗ {r.check.command}  [{r.check.source}]")

    if yours:
        print("\n  → run `flw test` in your own shell for the rest")
