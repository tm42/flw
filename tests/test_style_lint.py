"""The style checker — two rule sets, and the boundary between them.

The boundary is the whole design. One rule set over both corpora was measured at
33 findings of which 17 were false, so vocabulary never reads a file and geometry
never reads a reply. Most of what follows tests that boundary rather than the
patterns, because a pattern that fires on the wrong corpus is the failure this
file exists to catch.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core" / "scripts"))
import style_lint

REPO = Path(__file__).resolve().parent.parent


def _file(text: str, name: str = "note.md") -> list[tuple[int, str, str]]:
    return style_lint.findings(Path(name), text)


def _rules(found: list[tuple[int, str, str]]) -> set[str]:
    return {name for _, name, _ in found}


# --- files: geometry, and nothing else ------------------------------------- #


def test_untagged_fence_is_a_finding():
    found = _file("text\n\n```\nls\n```\n")
    assert _rules(found) == {"fence-untagged"}
    assert found[0][0] == 3


def test_tagged_fence_is_not():
    assert _file("text\n\n```sh\nls\n```\n") == []


def test_heading_past_three_hashes():
    assert "heading-depth" in _rules(_file("#### too deep\n"))
    assert _file("### deep enough\n") == []


def test_trailing_spaces_in_a_file():
    assert "trailing-spaces" in _rules(_file("a line  \nanother\n"))


def test_vocabulary_never_reads_a_file():
    """The 52% false-positive rate that produced the split, in one line each.

    Every string here appeared in flw's own documents and every one is correct
    prose: a quoted user phrase, `honest` as a predicate, a documented symbol.
    """
    for text in (
        "| break it, security, robustness, what if | `adversarial` |\n",
        "partial and honest beats complete and late\n",
        "Anything genuinely open goes in the record.\n",
        "`✗` is a failure — a link that is dangling or stale\n",
        "✅ \"A user can recover a note deleted in the last 30 days.\"\n",
    ):
        assert _file(text) == [], text


def test_geometry_only_applies_to_markdown():
    assert _file("#### not a heading here\n", name="script.py") == []


def test_fenced_content_is_skipped():
    assert _file("```text\n#### inside a fence\n```\n") == []


def test_the_style_file_is_never_walked(tmp_path):
    """It states its bans by quoting them, so it cannot be checked against itself."""
    (tmp_path / "terse_prose.md").write_text("#### deep\n")
    (tmp_path / "other.md").write_text("#### deep\n")
    assert style_lint.walk([tmp_path]) == [tmp_path / "other.md"]


# --- replies: vocabulary and reply-only geometry --------------------------- #


def test_banned_words_are_findings_in_a_reply():
    found = style_lint.reply_findings(
        "Great question — this is a robust and elegant fix.\n"
        "We can utilise sufficient context regarding it. 🎉\n"
        "Let me know if you need anything else.\n"
    )
    assert {r for r, hits in found.items() if hits} >= {
        "reaction-opener",
        "evaluative",
        "plain-word",
        "closing-offer",
    }
    assert "emoji" not in found, "the emoji rule was deleted; the 🎉 must not fire"


def test_a_hit_is_labelled_with_the_word_not_the_rule():
    """A pattern with alternated groups used to label one hit `plain-word`."""
    hits = style_lint.reply_findings("we utilise sufficient context regarding it")[
        "plain-word"
    ]
    assert [h.split(":")[0] for h in hits] == ["utilise", "sufficient", "regarding"]


def test_the_words_the_style_names_are_all_caught():
    """Three of them were named by the style and matched by no pattern.

    `honestly` fired and `honest` did not; `properly` was in the style's
    evaluative sentence and in no rule. Measured in main-agent replies: honest
    37, properly 10, really 5, quite 2, outside inline code spans.
    """
    for text, rule in (
        ("the honest answer is no", "qualifier"),
        ("we should really do this", "qualifier"),
        ("it is quite small", "qualifier"),
        ("it does not work properly", "evaluative"),
    ):
        assert style_lint.reply_findings(text)[rule], text


def test_honest_fires_attributively_and_not_as_a_predicate():
    """The predicate use is a claim the style permits, and 3 of 12 sampled were it."""
    assert style_lint.reply_findings("the honest option")["qualifier"]
    assert style_lint.reply_findings("the numbers stay honest")["qualifier"] == []


def test_a_word_inside_backticks_is_quoted_not_used():
    """25 of 44 measured false positives were exactly this — a reply reporting
    this checker's own output trips the rules it is reporting on."""
    assert style_lint.reply_findings("the `robust` rule fired twice")["evaluative"] == []
    assert style_lint.reply_findings("the robust rule fired twice")["evaluative"]


def test_an_untagged_fence_in_a_reply_is_a_finding():
    """The only rule both sets run: a reply is written, so it takes a tag too."""
    assert style_lint.reply_findings("text\n\n```\nls\n```\n")["fence-untagged"]
    assert style_lint.reply_findings("text\n\n```sh\nls\n```\n")["fence-untagged"] == []


def test_over_120_columns():
    found = style_lint.reply_findings("x" * 121 + "\n")
    assert len(found["over-120"]) == 1
    assert found["over-120"][0].startswith("121 cols")
    assert style_lint.reply_findings("x" * 120 + "\n")["over-120"] == []


def test_a_bullet_over_120_columns_is_still_too_wide():
    """own_block was built for missing-two-spaces and swallowed the width check
    with it: 892 of the 1,048 dropped over-120 lines were bullets."""
    for line in ("- " + "x" * 130, "| " + "x" * 130, "> " + "x" * 130):
        assert style_lint.reply_findings(line + "\n")["over-120"], line[:4]


def test_missing_two_spaces_only_inside_a_paragraph():
    text = "first line of prose\nsecond line of prose\n"
    assert len(style_lint.reply_findings(text)["missing-two-spaces"]) == 1
    kept = "first line of prose  \nsecond line of prose\n"
    assert style_lint.reply_findings(kept)["missing-two-spaces"] == []


def test_a_bullet_is_its_own_block():
    """Counting bullets as paragraph-internal lines overstated this by 26%."""
    text = "- one bullet\n- two bullets\n- three bullets\n"
    assert style_lint.reply_findings(text)["missing-two-spaces"] == []


def test_a_table_row_and_a_quote_are_their_own_blocks():
    assert style_lint.reply_findings("| a | b |\n| c | d |\n")["missing-two-spaces"] == []
    assert style_lint.reply_findings("> quoted\n> more\n")["missing-two-spaces"] == []


# --- transcripts ----------------------------------------------------------- #


def _record(text: str, **extra) -> str:
    record = {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }
    record.update(extra)
    return json.dumps(record) + "\n"


def test_recent_replies_skips_subagents(tmp_path):
    """A dispatched agent does not receive the output style, so its prose is not
    evidence: measured at 6.18 announcements per 10,000 words against 2.29."""
    path = tmp_path / "s.jsonl"
    path.write_text(
        _record("mine")
        + _record("a sidechain", isSidechain=True)
        + _record("a named agent", agentName="reviewer")
        + _record("mine too")
    )
    assert style_lint.recent_replies(path, 10) == ["mine", "mine too"]


def test_read_replies_counts_what_it_skipped(tmp_path):
    """A transcript of nothing but dispatched replies and one holding nothing are
    different answers: the first means flw is about to read someone else's session."""
    path = tmp_path / "s.jsonl"
    path.write_text(
        _record("theirs", agentName="reviewer")
        + _record("theirs too", agentName="reviewer")
    )
    assert style_lint.read_replies(path, 10) == ([], 2)

    empty = tmp_path / "e.jsonl"
    empty.write_text(json.dumps({"type": "user"}) + "\n")
    assert style_lint.read_replies(empty, 10) == ([], 0)


def test_asking_for_no_replies_returns_none(tmp_path):
    """replies[-0:] is every reply, so --last 0 used to read the whole transcript."""
    path = tmp_path / "s.jsonl"
    path.write_text("".join(_record(str(n)) for n in range(5)))
    assert style_lint.read_replies(path, 0) == ([], 0)


def test_recent_replies_takes_the_last_n(tmp_path):
    path = tmp_path / "s.jsonl"
    path.write_text("".join(_record(str(n)) for n in range(5)))
    assert style_lint.recent_replies(path, 2) == ["3", "4"]


def test_recent_replies_survives_a_malformed_line(tmp_path):
    path = tmp_path / "s.jsonl"
    path.write_text(_record("kept") + '{"type":"assistant" broken\n')
    assert style_lint.recent_replies(path, 10) == ["kept"]


def test_transcripts_are_matched_by_their_own_cwd(tmp_path):
    """Not by reconstructing the host's directory naming, which is not ours."""
    home = tmp_path / "home"
    project = tmp_path / "work"
    project.mkdir()
    directory = home / ".claude" / "projects" / "whatever-mangling"
    directory.mkdir(parents=True)
    (directory / "match.jsonl").write_text(
        json.dumps({"type": "assistant", "cwd": str(project)}) + "\n"
    )
    (directory / "other.jsonl").write_text(
        json.dumps({"type": "assistant", "cwd": str(tmp_path / "elsewhere")}) + "\n"
    )
    found = style_lint.session_transcripts(project, home=home)
    assert [p.name for p in found] == ["match.jsonl"]


def test_a_transcript_naming_the_project_after_another_cwd_still_matches(tmp_path):
    """A session that started in a parent directory names it first. 31 of 476
    transcripts hold more than one distinct cwd, so the first is not the answer."""
    home = tmp_path / "home"
    project = tmp_path / "work"
    project.mkdir()
    directory = home / ".claude" / "projects" / "whatever-mangling"
    directory.mkdir(parents=True)
    (directory / "later.jsonl").write_text(
        json.dumps({"type": "assistant", "cwd": str(tmp_path / "elsewhere")})
        + "\n"
        + json.dumps({"type": "assistant", "cwd": str(project)})
        + "\n"
    )
    found = style_lint.session_transcripts(project, home=home)
    assert [p.name for p in found] == ["later.jsonl"]


def test_transcripts_come_back_newest_first(tmp_path):
    """The caller takes the first that holds prose, so the order is the answer.

    Nothing asserted this: deleting `reverse=True` left the whole suite green
    while flw style check read the oldest matching session instead of this one.
    """
    home = tmp_path / "home"
    project = tmp_path / "work"
    project.mkdir()
    directory = home / ".claude" / "projects" / "whatever-mangling"
    directory.mkdir(parents=True)
    record = json.dumps({"type": "assistant", "cwd": str(project)}) + "\n"
    for name, mtime in (("older.jsonl", 1_000_000), ("newer.jsonl", 2_000_000)):
        path = directory / name
        path.write_text(record)
        os.utime(path, (mtime, mtime))
    found = style_lint.session_transcripts(project, home=home)
    assert [p.name for p in found] == ["newer.jsonl", "older.jsonl"]


def test_the_cap_counts_matches_not_candidates(tmp_path):
    """Capping candidates meant the newest 40 files on the whole machine, so a day
    in another repository made this project's transcripts unreadable."""
    home = tmp_path / "home"
    project = tmp_path / "work"
    project.mkdir()
    directory = home / ".claude" / "projects" / "whatever-mangling"
    directory.mkdir(parents=True)
    for n in range(style_lint.MATCH_CAP + 5):
        (directory / f"other{n:03}.jsonl").write_text(
            json.dumps({"type": "assistant", "cwd": str(tmp_path / "elsewhere")}) + "\n"
        )
    (directory / "mine.jsonl").write_text(
        json.dumps({"type": "assistant", "cwd": str(project)}) + "\n"
    )
    found = style_lint.session_transcripts(project, home=home)
    assert [p.name for p in found] == ["mine.jsonl"]


def test_no_transcript_directory_is_not_an_error(tmp_path):
    assert style_lint.session_transcripts(tmp_path, home=tmp_path / "nothing") == []


# --- the repository itself ------------------------------------------------- #


def test_the_shipped_style_file_has_the_rules_the_checker_claims():
    """A rule whose sentence has left the style file is a rule nobody agreed to."""
    text = (REPO / "core" / "styles" / "terse_prose.md").read_text()
    for phrase in ("Tag every code fence with its language",):
        assert phrase in text, phrase


def test_the_three_narrowed_words_are_in_neither_rule_set():
    """`clean`, `actually` and `surface` are narrowed in the style, so no pattern
    may ban them.

    The first two were 240 of roughly 356 measured vocabulary violations precisely
    because both have uses the style permits. `surface` joined them at 260 uses in
    166,185 words, against a contract with a field of that name. A pattern that
    reintroduces any of the three puts the checker back at odds with the sentence
    it is supposed to enforce.
    """
    patterns = " ".join(
        p.pattern for _, p, _ in style_lint.REPLY_RULES + style_lint.FILE_RULES
    )
    assert "clean" not in patterns
    assert "actually" not in patterns
    assert "surface" not in patterns


def test_the_style_file_still_narrows_them():
    """The other half of the same guard: the sentence must keep permitting them."""
    text = (REPO / "core" / "styles" / "terse_prose.md").read_text()
    assert "*actually*" in text
    assert "*clean* as a claim about quality" in text
    assert "*surface* as a verb" in text
