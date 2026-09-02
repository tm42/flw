#!/usr/bin/env python3
"""Every file a run loads unconditionally, checked against a byte ceiling. Stdlib only.

Nothing in flw measured what a run loads, and `core/skills/flw-execute/SKILL.md` grew
past 19,000 bytes without anything noticing until a user read a run and called it
verbose. Two ceilings: 20,000 bytes for a `SKILL.md`, since that is what a run loads by
naming the skill, and 10,000 for `core/shared/context.md` and
`core/styles/terse_prose.md`, which every skill's opening reads whether or not it names
one. A reference under `references/`, read only when something in the skill sends a
reader to it, carries no ceiling here — a budget on a file read once in ten runs would
price the wrong thing.

Bytes rather than tokens: a token count needs a tokenizer, and flw ships none as a
runtime dependency. Measured 2026-09-02 across these files with `cl100k_base` as a proxy
for the real tokenizer, the ratio is 4.10 to 4.33 bytes per token — close enough that a
byte ceiling holds as a token ceiling too, without tying the check to one vendor's
tokenizer.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILL_CEILING = 20_000
SHARED_CEILING = 10_000


def targets() -> list[tuple[Path, int]]:
    """Every file a run loads unconditionally, paired with its ceiling.

    The skill list comes from the glob, not a name typed here, so a fifth skill is
    measured the day it is added rather than the day someone remembers to list it.
    """
    found = [(path, SKILL_CEILING) for path in sorted(REPO.glob("core/skills/*/SKILL.md"))]
    found += [
        (REPO / "core" / "shared" / "context.md", SHARED_CEILING),
        (REPO / "core" / "styles" / "terse_prose.md", SHARED_CEILING),
    ]
    return found


def report(files: list[tuple[Path, int]]) -> tuple[str, list[Path]]:
    """One line per file — size, ceiling, headroom — and which ones are over."""
    lines = []
    over = []
    for path, ceiling in files:
        size = path.stat().st_size
        headroom = ceiling - size
        if headroom < 0:
            over.append(path)
        lines.append(
            f"{'OVER' if headroom < 0 else 'OK':>4}  {path.relative_to(REPO)}  "
            f"{size} / {ceiling}  ({headroom:+d})"
        )
    return "\n".join(lines), over


def main() -> int:
    text, over = report(targets())
    print(text)
    if over:
        names = ", ".join(str(path.relative_to(REPO)) for path in over)
        print(f"\nover budget: {names}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
