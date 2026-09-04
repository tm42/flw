"""Check prose against the mechanical half of flw's writing style.

Two rule sets, because two corpora break differently and mixing them produced a
checker with a 52% false-positive rate.

FILE_RULES is document geometry: a fence with no language, a heading past the
depth the style allows, the trailing spaces that become a `<br>` in a file.
Measured across 107 markdown files an agent wrote, untagged fences ran at 19.6%
and every finding was real.

REPLY_RULES is vocabulary and shape, checked against what the agent said rather
than what it wrote to disk. Measured across 109,344 words of agent prose against
88,618 words from subagents that never load the style, five words carry 92% of the
vocabulary violations. There was an emoji rule here on the strength of a tenfold
difference between those two corpora; re-measured over 276,281 words it was counting
`\u2713` and `\u2717`, which flw itself prints, and neither corpus held a single
pictographic emoji. The style file still says "No emoji." and no pattern enforces it.

The same words in a hand-written document are almost always right — "partial and
honest beats complete and late" uses `honest` precisely, and a table row reading
`break it, security, robustness, what if` is quoting a user, not making an
evaluative claim. So the word rules never run against a file. Six of six
`honest`/`genuinely` hits in flw's own docs were legitimate, which is the whole
reason for the split.

Nothing here judges the prose rules. A checker that guesses at "one idea per
sentence" produces noise that teaches people to ignore it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

MD_SUFFIXES = {".md", ".markdown"}
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".flw"}
# The style file states its bans by quoting the words, so every vocabulary rule
# fires on it. It is the one file that cannot be checked against itself.
SKIP_FILES = {"terse_prose.md"}

WRAP_COLUMNS = 120
# How many of this project's transcripts to collect, and how far into each to
# look for the cwd record that identifies it.
MATCH_CAP = 40
CWD_SCAN_LINES = 200

FENCE = re.compile(r"^\s*```(.*)$")
_HEADING = re.compile(r"^#{1,6}\s")
_BULLET = re.compile(r"^\s*([-*+]|\d+[.)])\s")
_QUOTE = re.compile(r"^\s*>")
_CODE_SPAN = re.compile(r"`[^`\n]*`")

Rule = tuple[str, re.Pattern[str], str]

# --- files: geometry only -------------------------------------------------- #

FILE_RULES: tuple[Rule, ...] = (
    # "Maximum depth is `###`."
    ("heading-depth", re.compile(r"^#{4,}\s"), "a heading deeper than ###"),
    # "Never do this in a file — two trailing spaces become a <br> there."
    (
        "trailing-spaces",
        re.compile(r"\S  +$"),
        "two trailing spaces, which become a <br> in a file",
    ),
)

# --- replies: vocabulary and shape ----------------------------------------- #

REPLY_RULES: tuple[Rule, ...] = (
    # "Cut every qualifier that changes nothing when removed."
    # `honest` only where it modifies a noun. The predicate use is a claim the
    # style permits -- "the staleness numbers stay honest" -- and 3 of 12 sampled
    # hits were that, against 9 of the attributive tic the rule is aimed at.
    (
        "qualifier",
        re.compile(
            r"\b(inherently|genuinely|honestly|really|quite)\b"
            r"|\b(?:the|a|an|this|that|one|its|their|our|my|more|most|only|same"
            r"|another|no)\s+honest\b(?=\s+\w)",
            re.IGNORECASE,
        ),
        "a qualifier that changes nothing when removed",
    ),
    # "No evaluative words without a measurement behind them."
    (
        "evaluative",
        re.compile(
            r"\b(robust|elegant|elegantly|dramatically|significantly|seamlessly|properly)\b",
            re.IGNORECASE,
        ),
        "an evaluative word with no measurement behind it",
    ),
    # "Use the plain word when there is one."
    (
        "plain-word",
        re.compile(r"\b(utilis|utiliz)e?[sd]?\b|\bsufficient(ly)?\b|\bregarding\b",
                   re.IGNORECASE),
        'a longer word where a plain one exists — use, enough, about',
    ),
    # "No balanced aphorisms."
    (
        "aphorism",
        re.compile(r"\bis not [^.,;:]{1,40}, it(?:'s| is)\b", re.IGNORECASE),
        'a balanced aphorism — "X is not Y, it is Z"',
    ),
    # "Do not connect them with a participle tail."
    (
        "participle-tail",
        re.compile(r", (ensuring|allowing|enabling|leveraging) ", re.IGNORECASE),
        "a participle tail; give the clause a verb that commits",
    ),
    # "Reaction openers." / "Closing offers." / "Announcements."
    (
        "reaction-opener",
        re.compile(
            r"(?im)^\s*(great question|good catch|you'?re absolutely right)\b"
        ),
        "a reaction opener",
    ),
    ("closing-offer", re.compile(r"(?i)\blet me know if\b"), "a closing offer"),
    (
        "announcement",
        re.compile(r"(?im)^\s*(let me |i'?ll start by |i'?m going to )"),
        "an announcement of what you are about to do",
    ),
    # "Writing about your own writing."
    (
        "signpost",
        re.compile(r"(?im)^\s*(two|three|four|five) things:"),
        "a signpost; say the things",
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


def reply_findings(text: str) -> dict[str, list[str]]:
    """{rule: examples} for one reply. The count is len() of each list.

    Two geometry rules invert against a file: a file must NOT carry the trailing
    spaces, and a file's width is the reader's to choose. They are also the only
    two rules measurement found the agent breaking at volume — 36.7% of replies
    over 120 columns, 63.1% of the lines that need the trailing pair lacking it.

    A paragraph is consecutive prose lines. A bullet, a quote and a table row are
    each their own block and do not reflow into a neighbour, so a missing pair on
    one of them is not a finding — counting them overstated this by 26%. Width is
    checked before that branch, because a bullet still has to fit the terminal:
    892 of the 1,048 over-120 lines the branch used to swallow were bullets.

    The vocabulary rules read the line with its inline code spans removed. A word
    inside backticks is being quoted rather than used, and 25 of 44 measured false
    positives were exactly that — a reply reporting this checker's own output.

    fence-untagged is the one rule both sets run. The style asks for a language tag
    wherever a fence is written, and a reply is written.
    """
    # Every rule gets a key whether it fired or not, so a caller can ask about
    # one without knowing whether it hit. style_check skips the empty ones.
    out: dict[str, list[str]] = {name: [] for name, _, _ in REPLY_RULES}
    out.update({"over-120": [], "missing-two-spaces": [], "fence-untagged": []})
    in_fence = False
    paragraph: list[str] = []

    def flush() -> None:
        if len(paragraph) >= 2:
            for line in paragraph[:-1]:
                if not line.endswith("  "):
                    out["missing-two-spaces"].append(line.strip()[:60])
        paragraph.clear()

    for line in text.split("\n"):
        fence = FENCE.match(line)
        if fence:
            if not in_fence and not fence.group(1).strip():
                out["fence-untagged"].append(line.strip()[:52] or "```")
            in_fence = not in_fence
            flush()
            continue
        if in_fence:
            continue
        probe = _CODE_SPAN.sub(" ", line)
        for name, pattern, _ in REPLY_RULES:
            # group(0), not findall: a pattern with alternated groups returns a
            # tuple of mostly empty strings and the label comes out as the rule
            # name instead of the word that tripped it.
            for hit in pattern.finditer(probe):
                out[name].append(
                    f"{hit.group(0).strip()}: {line.strip()[:52]}"
                )
        stripped = line.strip()
        if len(line) > WRAP_COLUMNS:
            out["over-120"].append(f"{len(line)} cols: {stripped[:52]}")
        own_block = (
            not stripped
            or stripped.startswith("|")
            or _HEADING.match(line)
            or _BULLET.match(line)
            or _QUOTE.match(line)
        )
        if own_block:
            flush()
            continue
        paragraph.append(line)
    flush()
    return out


def session_transcripts(root: Path, base: Path) -> list[Path]:
    """Every transcript under `base` whose own records say it ran in `root`, newest
    first.

    `base` is handed in rather than derived from HOME, because which directory a
    host writes transcripts to is a fact about the host and the CLI is the only
    part of flw that holds those. This engine reads whatever directory it is
    given.

    Found by reading each candidate's `cwd` rather than by reconstructing the
    host's directory-naming scheme, which is undocumented and not ours. Empty
    when nothing matches, which is the answer for a directory that is absent,
    unreadable, or holds no session that ran here.

    A list rather than one path because several sessions run against one project
    and the newest is often one that has not said anything yet. The caller takes
    the first that actually holds prose.

    The cap counts matches rather than candidates. Capping candidates meant the
    newest 40 files across every project on the machine, so a day spent in
    another repository pushed this project's transcripts out of the window and
    the command reported it as the host keeping none. Reading all of them to
    find 40 costs about 0.1s over 477 files.
    """
    matched: list[Path] = []
    if not base.is_dir():
        return matched
    candidates = sorted(
        base.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    wanted = str(root.resolve())
    for path in candidates:
        try:
            with path.open(encoding="utf-8", errors="replace") as handle:
                for _ in range(CWD_SCAN_LINES):
                    line = handle.readline()
                    if not line:
                        break
                    if '"cwd"' not in line:
                        continue
                    try:
                        cwd = json.loads(line).get("cwd")
                    except json.JSONDecodeError:
                        continue
                    # Not `break` on any cwd record: a session that started in a
                    # parent directory names it first and this project later, and
                    # 31 of 476 transcripts hold more than one distinct cwd.
                    if cwd and str(Path(cwd).resolve()) == wanted:
                        matched.append(path)
                        break
        except OSError:
            continue
        if len(matched) >= MATCH_CAP:
            break
    return matched


def read_replies(path: Path, last: int) -> tuple[list[str], int]:
    """The last `last` main-agent replies, oldest first, and how many were skipped
    for being a dispatched agent's.

    A dispatched agent does not receive the host's output style: measured over
    this project's transcripts, its prose breaks `announcement` at 6.18 per 10,000
    words against the main agent's 2.29. So counting it here would measure
    something the style never reached. `isSidechain` is checked too and fires in
    none of 298 transcripts, so the name is doing all the work.

    The skipped count is the second return value because a transcript holding
    nothing but dispatched replies and one holding nothing at all are different
    answers. The first means flw is reading someone else's session and must say
    so; the second means a session that has not spoken yet, and moving on is
    right.
    """
    replies: list[str] = []
    dispatched = 0
    if last <= 0:
        # replies[-0:] is every reply, so asking for none used to return all.
        return replies, dispatched
    try:
        handle = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return replies, dispatched
    with handle:
        for line in handle:
            if '"assistant"' not in line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") != "assistant":
                continue
            if record.get("isSidechain") or record.get("agentName"):
                dispatched += 1
                continue
            content = (record.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            text = "\n".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ).strip()
            if text:
                replies.append(text)
    return replies[-last:], dispatched


def recent_replies(path: Path, last: int) -> list[str]:
    """The replies alone, for a caller that does not need to know what was skipped."""
    return read_replies(path, last)[0]


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
