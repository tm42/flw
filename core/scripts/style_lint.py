"""Check prose against the mechanical half of flw's writing style.

Two rule sets, because two corpora break differently and mixing them produced a
checker with a 52% false-positive rate.

FILE_RULES is document geometry: a fence with no language, a heading past the
depth the style allows, the trailing spaces that become a `<br>` in a file.
Measured across 107 markdown files an agent wrote, untagged fences ran at 19.6%
and every finding was real.

REPLY_RULES is vocabulary and shape, checked against what the agent said rather
than what it wrote to disk. Measured across 109,344 words of agent prose against
88,618 words from subagents that never load the style, these words are genuinely
overused: emoji at ten times the rate in prose the style never reached, and five
words carrying 92% of the vocabulary violations.

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
import re
import sys
from pathlib import Path

MD_SUFFIXES = {".md", ".markdown"}
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".flw"}
# The style file states its bans by quoting the words, so every vocabulary rule
# fires on it. It is the one file that cannot be checked against itself.
SKIP_FILES = {"terse_prose.md"}

WRAP_COLUMNS = 120

FENCE = re.compile(r"^\s*```(.*)$")
_HEADING = re.compile(r"^#{1,6}\s")
_BULLET = re.compile(r"^\s*([-*+]|\d+[.)])\s")
_QUOTE = re.compile(r"^\s*>")

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
    (
        "qualifier",
        re.compile(r"\b(inherently|genuinely|honestly)\b", re.IGNORECASE),
        "a qualifier that changes nothing when removed",
    ),
    # "No evaluative words without a measurement behind them."
    (
        "evaluative",
        re.compile(
            r"\b(robust|elegant|elegantly|dramatically|significantly|seamlessly)\b",
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
    # "No emoji."
    (
        "emoji",
        re.compile(
            "[\U0001f300-\U0001faff\U0001f000-\U0001f0ff"
            "\U00002600-\U000026ff\U00002700-\U000027bf]"
        ),
        "an emoji",
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


def walk(targets: list[Path]) -> list[Path]:
    """Every markdown and text file under the targets, sorted.

    A path named explicitly is read whatever its suffix — someone who names one
    file means that file. Only a directory walk filters.
    """
    found: list[Path] = []
    for target in targets:
        if target.is_file():
            found.append(target)
            continue
        if not target.is_dir():
            print(f"style lint: no such path: {target}", file=sys.stderr)
            continue
        for path in sorted(target.rglob("*")):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.name in SKIP_FILES:
                continue
            if path.is_file() and path.suffix.lower() in MD_SUFFIXES | {".txt"}:
                found.append(path)
    return sorted(set(found))


def report(paths: list[Path], root: Path) -> tuple[list[str], int]:
    """One line per finding, and how many there were."""
    lines: list[str] = []
    total = 0
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            lines.append(f"{path}: could not be read ({exc.strerror or exc})")
            continue
        for number, name, message in findings(path, text):
            try:
                shown = path.relative_to(root)
            except ValueError:
                shown = path
            lines.append(f"{shown}:{number}: {name}: {message}")
            total += 1
    return lines, total


def reply_findings(text: str) -> dict[str, list[str]]:
    """{rule: examples} for one reply. The count is len() of each list.

    Two geometry rules apply to a reply and to nothing else: a file must NOT
    carry the trailing spaces, and a file's width is the reader's to choose.
    They are also the only two rules measurement found the agent breaking at
    volume — 36.7% of replies over 120 columns, 63.1% of the lines that need the
    trailing pair lacking it.

    A paragraph is consecutive prose lines. A bullet, a quote and a table row are
    each their own block and do not reflow into a neighbour, so a missing pair on
    one of them is not a finding — counting them overstated this by 26%.
    """
    out: dict[str, list[str]] = {"over-120": [], "missing-two-spaces": []}
    in_fence = False
    paragraph: list[str] = []

    def flush() -> None:
        if len(paragraph) >= 2:
            for line in paragraph[:-1]:
                if not line.endswith("  "):
                    out["missing-two-spaces"].append(line.strip()[:60])
        paragraph.clear()

    for line in text.split("\n"):
        if FENCE.match(line):
            in_fence = not in_fence
            flush()
            continue
        if in_fence:
            continue
        for name, pattern, _ in REPLY_RULES:
            # group(0), not findall: a pattern with alternated groups returns a
            # tuple of mostly empty strings and the label comes out as the rule
            # name instead of the word that tripped it.
            for hit in pattern.finditer(line):
                out.setdefault(name, []).append(
                    f"{hit.group(0).strip()}: {line.strip()[:52]}"
                )
        stripped = line.strip()
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
        if len(line) > WRAP_COLUMNS:
            out["over-120"].append(f"{len(line)} cols: {stripped[:52]}")
    flush()
    return out


def session_transcripts(root: Path, home: Path | None = None) -> list[Path]:
    """Every transcript whose own records say it ran in `root`, newest first.

    Found by reading each candidate's `cwd` rather than by reconstructing the
    host's directory-naming scheme, which is undocumented and not ours. Empty
    when nothing matches, which is the honest answer for a host that keeps no
    transcript or keeps it somewhere else.

    A list rather than one path because several sessions run against one project
    and the newest is often one that has not said anything yet. The caller takes
    the first that actually holds prose.
    """
    base = (home or Path.home()) / ".claude" / "projects"
    matched: list[Path] = []
    if not base.is_dir():
        return matched
    candidates = sorted(
        base.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    wanted = str(root.resolve())
    for path in candidates[:40]:
        try:
            with path.open(encoding="utf-8", errors="replace") as handle:
                for _ in range(200):
                    line = handle.readline()
                    if not line:
                        break
                    if '"cwd"' not in line:
                        continue
                    try:
                        cwd = json.loads(line).get("cwd")
                    except json.JSONDecodeError:
                        continue
                    if cwd and str(Path(cwd).resolve()) == wanted:
                        matched.append(path)
                    break
        except OSError:
            continue
    return matched


def recent_replies(path: Path, last: int) -> list[str]:
    """The last `last` replies the main agent wrote, oldest first.

    Sidechain and named-agent records are a subagent's, and a subagent never
    receives the host's output style, so counting its prose here would measure
    something the style never reached.
    """
    replies: list[str] = []
    try:
        handle = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return replies
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
    return replies[-last:]


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
    lines, total = report(walk(targets), root)
    for line in lines:
        print(line)
    if total:
        print(f"\n{total} finding{'s' if total != 1 else ''}")
        return 1
    print("style lint: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
