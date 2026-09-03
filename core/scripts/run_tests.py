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
import shlex
import signal
import subprocess
import sys
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


# bash scores a list of commands by its last one, so a separator that makes a
# list would let an earlier failing command pass silently — the tool's own defect
# class, in the one place a user writes the command by hand. `&&` and `||` are
# not separators here: they are what a user writes deliberately, and both carry
# the earlier command's failure forward.
#
# Which is why the `;` is found by tokenising and never by scanning bytes. Two
# of flw's own removal checks are `python3 -c "import …; sys.exit(…)"`, where the
# `;` is inside a quoted argument and separates nothing, and `; }` is the
# terminator bash requires on a brace group — flw's own setup line is
# `test -x … || { … ; }`. Both are correct bash, and a byte scan refuses both.


def _separator(command: str) -> str:
    """Which list-making separator this command holds, named, or empty."""
    if "\n" in command:
        return "a newline"
    lexer = shlex.shlex(command, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        # Unbalanced quotes. bash will fail on it too, loudly and at the site,
        # and refusing here would be a verdict on a reading we cannot stand
        # behind.
        return ""
    for index, token in enumerate(tokens):
        # A `;` closing a brace group, not extending a list.
        if token == ";" and tokens[index + 1 : index + 2] != ["}"]:
            return "a ';'"
    return ""


def _check(source: str, command: str) -> Check:
    found = _separator(command)
    if found:
        raise SystemExit(
            f"error: a {source!r} check holds {found}, which makes it a list bash "
            f"would report only the last command's exit status for: {command!r}"
        )
    return Check(source, command)


def _commands(path: Path, declared: list) -> list[str]:
    """Every success_criteria.tests command, or the entry that is not one, named.

    An entry that is not a table with a string command used to raise KeyError
    out of a comprehension, naming neither the contract nor the entry."""
    commands = []
    for index, entry in enumerate(declared):
        if not isinstance(entry, dict) or not isinstance(entry.get("command"), str):
            raise SystemExit(
                f"error: {path} success_criteria.tests[{index}] is not a table "
                f"with a string command: {entry!r}"
            )
        commands.append(entry["command"])
    return commands


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

    # -A means the contract's full definition of done, so a contract declaring
    # none has nothing to answer with and says so rather than quietly running the
    # branch set instead. With no contract at all there is no such definition to
    # ask for — that call falls back, as the plain call does, and the CLI refuses
    # -A there before reaching here. The fall-through below is the plain call's,
    # where the branch set is what was asked for and an absent one is answered by
    # the contract rather than by silence.
    if full and path.exists() and not declared:
        print(
            f"error: {path} declares no success_criteria.tests, so there is no "
            "full definition of done to run here.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if declared and (full or not branch):
        checks += [_check("contract", c) for c in _commands(path, declared)]
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
    section = config.get("tests", {})
    # A bare string is iterable, so `checks = "make test"` ran nine one-character
    # shells and `checks = "  "` printed `2 passed` at exit 0 having run nothing —
    # the same empty-run-reads-as-a-pass failure this file refuses twice already.
    for key in ("checks", "yours"):
        value = section.get(key)
        if value is None:
            continue
        if not isinstance(value, list) or not all(isinstance(c, str) for c in value):
            raise SystemExit(
                f"error: {path} declares [tests] {key} as "
                f"{type(value).__name__}, not a list of strings"
            )
    return section


def _local_config(root: Path) -> dict:
    # ~/.flw/config.toml (or $FLW_HOME) is the underlay: facts about this machine
    # — a check that cannot run here — that would otherwise have to be repeated
    # in every repo worked in. The project file wins key by key.
    global_path = Path(os.environ.get("FLW_HOME", str(Path.home() / ".flw"))) / "config.toml"
    merged = dict(_tests_section(global_path))
    flw_dir = os.environ.get("FLW_DIR", ".flw")
    merged.update(_tests_section(root / flw_dir / "config.toml"))
    # Same reason _check refuses a separator: `|| exit` attaches to the last
    # command only, so a setup whose first command failed would let every check
    # run in the wrong environment and report a pass.
    found = _separator(str(merged.get("setup", "")))
    if found:
        raise SystemExit(
            f"error: a 'setup' holding {found} would let an earlier failing "
            "command pass silently — join them with && , or call a script"
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
