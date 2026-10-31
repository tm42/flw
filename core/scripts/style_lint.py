"""Check prose files against the mechanical half of flw's writing style.

Document geometry and nothing else: a fence with no language, a heading past the
depth the style allows, the trailing spaces that become a `<br>` in a file.
Measured across 107 markdown files an agent wrote, untagged fences ran at 19.6%
and every finding was real.

A vocabulary half stood here too, checked against the agent's own replies rather
than against a file, and it is gone. Not because it was wrong — five words carried
92% of the violations across 109,344 words of agent prose — but because the corpus
it read was one machine's session store, which no clone has, so the figure could
not be re-taken anywhere else. The vocabulary rules live in the style file and in
`flw-style`, which reads the agent's own recent turns out of context rather than
off disk, and so works on every host.

The word rules never ran against a file and that half of the split survives it:
the same words in a hand-written document are almost always right. "Partial and
honest beats complete and late" uses `honest` precisely, and a table row reading
`break it, security, robustness, what if` is quoting a user, not making an
evaluative claim. Six of six `honest`/`genuinely` hits in flw's own docs were
legitimate.

Nothing here judges the prose rules. A checker that guesses at "one idea per
sentence" produces noise that teaches people to ignore it.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

MD_SUFFIXES = {".md", ".markdown"}
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".flw"}
# The style file states its bans by quoting the words, so every vocabulary rule
# fires on it. It is the one file that cannot be checked against itself.
SKIP_FILES = {"terse_prose.md"}

FENCE = re.compile(r"^\s*```(.*)$")
# The trailing pair that becomes a `<br>` where nobody asked for one.
TRAILING_PAIR = re.compile(r"\S  +$")

Rule = tuple[str, re.Pattern[str], str]

# --- files: geometry only -------------------------------------------------- #

FILE_RULES: tuple[Rule, ...] = (
    # "Maximum depth is `###`."
    ("heading-depth", re.compile(r"^#{4,}\s"), "a heading deeper than ###"),
    # "Never do this in a file — two trailing spaces become a <br> there."
    (
        "trailing-spaces",
        TRAILING_PAIR,
        "two trailing spaces, which become a <br> in a file",
    ),
)

def findings(path: Path, text: str) -> list[tuple[int, str, str]]:
    """(line, rule, what is wrong) for one file, in file order.

    Fenced blocks are skipped: a shell transcript is not prose, and the style
    exempts a fence from the geometry rules explicitly.
    """
    is_md = path.suffix.lower() in MD_SUFFIXES
    out: list[tuple[int, str, str]] = []
    in_fence = False
    for number, line in enumerate(text.split("\n"), start=1):
        fence = FENCE.match(line)
        if fence:
            # "Tag every code fence with its language, `text` when nothing else fits."
            if not in_fence and is_md and not fence.group(1).strip():
                out.append((number, "fence-untagged", "a code fence with no language"))
            in_fence = not in_fence
            continue
        if in_fence or not is_md:
            continue
        for name, pattern, message in FILE_RULES:
            if pattern.search(line):
                out.append((number, name, message))
    return out


def walk(targets: list[Path]) -> tuple[list[Path], list[Path]]:
    """Every markdown and text file under the targets, sorted, and the targets that
    could not be resolved.

    A path named explicitly is read whatever its suffix — someone who names one
    file means that file. Only a directory walk filters.

    The unresolved list is returned as well as printed, because a caller that only
    saw the print reported the run clean at exit 0 over a path it never opened,
    and a project running this in CI against a directory that has since been
    renamed passed on a walk of nothing.

    `os.walk` with an `onerror` callback rather than `rglob`, because rglob
    swallows a PermissionError on a subdirectory and yields nothing for it, and a
    walk that yielded nothing is indistinguishable from a directory holding no
    prose: `chmod 000` on one subdirectory made `style lint .` — a declared check —
    print clean at exit 0. The callback puts that directory in the same list a
    missing target goes in, so the run says what it could not read.
    `core/scripts/scout.py:163` already walks this way here; `Path.walk(on_error=)`
    would be neater and needs 3.12, above this project's 3.11 floor.
    """
    found: list[Path] = []
    missing: list[Path] = []
    for target in targets:
        if target.is_file():
            found.append(target)
            continue
        if not target.is_dir():
            print(f"style lint: no such path: {target}", file=sys.stderr)
            missing.append(target)
            continue

        def refused(error: OSError, named: Path = target) -> None:
            where = Path(error.filename) if error.filename else named
            print(f"style lint: could not read: {where}", file=sys.stderr)
            missing.append(where)

        for parent, dirs, files in os.walk(target, onerror=refused):
            here = Path(parent)
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            if any(part in SKIP_DIRS for part in here.parts):
                continue
            for name in files:
                path = here / name
                if name in SKIP_FILES:
                    continue
                if path.is_file() and path.suffix.lower() in MD_SUFFIXES | {".txt"}:
                    found.append(path)
    return sorted(set(found)), sorted(set(missing))


def report(paths: list[Path], root: Path) -> tuple[list[str], int, int]:
    """One line per finding, how many findings there were, and how many of the
    files could not be read.

    The two counts are separate because they mean different things to the caller:
    a finding is prose that is wrong, and a file that would not open is a file
    nothing was proved about.
    """
    lines: list[str] = []
    total = 0
    unread = 0
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            lines.append(f"{path}: could not be read ({exc.strerror or exc})")
            unread += 1
            continue
        for number, name, message in findings(path, text):
            try:
                shown = path.relative_to(root)
            except ValueError:
                shown = path
            lines.append(f"{shown}:{number}: {name}: {message}")
            total += 1
    return lines, total, unread


def verdict(findings: int, unread: int) -> int:
    """The exit code, and the line that goes with it.

    2 for a target that could not be read, which is what the contract's exit-code
    surface already means for `flw test` with nothing runnable and for a file
    `flw validate` could not check: the run proved nothing. Before this, a walk
    that resolved nothing and a walk that found nothing wrong were the same
    answer, so `style lint no-such-file.md` printed the path and then reported the
    run clean at exit 0.

    A finding still wins over an unreadable target, because prose that is wrong is
    something the run did prove.

    Shared by both entry points rather than written twice, because the CLI wraps
    this engine and the contract also declares the engine itself as a check, so a
    project runs it both ways and must get the same code.
    """
    if findings:
        print(f"\n{findings} finding{'s' if findings != 1 else ''}")
        return 1
    if unread:
        target = "target" if unread == 1 else "targets"
        print(f"style lint: {unread} {target} could not be read — nothing checked there")
        return 2
    print("style lint: clean")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="style_lint",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("paths", nargs="*", default=["."], metavar="PATH")
    args = parser.parse_args(argv[1:])
    targets = [Path(p) for p in (args.paths or ["."])]
    root = Path.cwd()
    paths, missing = walk(targets)
    lines, total, unread = report(paths, root)
    for line in lines:
        print(line)
    return verdict(total, len(missing) + unread)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
