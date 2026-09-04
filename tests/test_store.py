"""The note store — freeform markdown, two roots, and nothing that can refuse a file.

What is under test more than any single answer: that no hand-written file can break a
command. The whole store is parsed on every query, so a note nobody validated has to
degrade a surface rather than raise.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))
import flw
import store

TODAY = date(2026, 8, 31)


def _tags(args) -> list[str]:
    """The tags the handler acts on: the parent's, then the subparser's."""
    return [*args.tag, *(getattr(args, "sub_tag", None) or [])]


def home(tmp_path: Path) -> Path:
    # exist_ok: a test that plants something in the store before the write has
    # to build the directory itself, and _write calls this again on the way in.
    (tmp_path / "flw-home" / "kb").mkdir(parents=True, exist_ok=True)
    return tmp_path / "flw-home"


def note(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def walk(tmp_path: Path, project=None, category="") -> list[store.Note]:
    return store.walk(home(tmp_path), project, project_category=category)


# --- the walk, and where a category comes from ----------------------------- #


def test_both_roots_are_read_and_each_hit_names_its_own(tmp_path):
    hm = home(tmp_path)
    note(hm / "kb", "python/unions.md", "+++\ntitle = 'unions'\n+++\nbody")
    project = tmp_path / "proj"
    note(project, "plans/notes/ci.md", "the runner has no network")

    found = store.walk(hm, project, project_category="proj")
    assert {n.root_name for n in found} == {store.MACHINE, store.PROJECT}


def test_the_category_is_the_directory_and_nesting_is_a_path(tmp_path):
    hm = home(tmp_path)
    note(hm / "kb", "python/pandas/groupby.md", "x")
    note(hm / "kb", "python/unions.md", "x")

    assert {n.category for n in store.walk(hm, None)} == {"python", "python/pandas"}


def test_a_note_at_the_project_root_takes_the_projects_own_category(tmp_path):
    """`plans/notes/ci.md` has no directory beneath the root, so it takes the name
    the project is known by — the same rule the machine root has nothing to apply."""
    project = tmp_path / "proj"
    note(project, "plans/notes/ci.md", "x")
    note(project, "plans/notes/python/uv.md", "x")

    found = store.walk(home(tmp_path), project, project_category="acme-billing")
    assert {n.slug: n.category for n in found} == {
        "ci": "acme-billing",
        "uv": "python",
    }


def test_plans_above_notes_is_not_read(tmp_path):
    """plans/*.md belongs to flw ledger. Reading it here would put a reviewed
    design document and a scribble about a flaky runner in one result set."""
    project = tmp_path / "proj"
    note(project, "plans/design-memory.md", "a reviewed design")
    note(project, "plans/notes/ci.md", "a scribble")

    found = store.walk(home(tmp_path), project, project_category="proj")
    assert [n.slug for n in found] == ["ci"]


# --- nothing about the format can refuse a file ---------------------------- #


def test_a_note_with_no_frontmatter_is_a_valid_note(tmp_path):
    hm = home(tmp_path)
    note(hm / "kb", "python/unions.md", "# discriminated unions need a Literal\n\nbody")

    found = store.walk(hm, None)[0]
    assert found.title == "discriminated unions need a Literal"
    assert found.description == ""
    assert found.age(TODAY) == "undated"


def test_a_malformed_block_reads_as_frontmatterless_and_breaks_nothing_else(tmp_path):
    """One hand-written typo must not cost the reader every other note. The store
    is parsed in full on every command, including the opening read three skills
    make before they start work."""
    hm = home(tmp_path)
    note(hm / "kb", "python/broken.md", "+++\ntitle = not quoted\n+++\n# still readable")
    note(hm / "kb", "python/fine.md", "+++\ntitle = 'fine'\n+++\nbody")

    found = {n.slug: n for n in store.walk(hm, None)}
    assert found["broken"].malformed is not None
    assert found["broken"].title == "still readable"
    assert found["fine"].title == "fine"
    assert store.search(list(found.values()), ["readable"])


def test_a_file_that_is_not_utf8_is_skipped_rather_than_raised(tmp_path):
    hm = home(tmp_path)
    (hm / "kb" / "python").mkdir(parents=True)
    (hm / "kb" / "python" / "bytes.md").write_bytes(b"\xff\xfe not utf-8")
    note(hm / "kb", "python/fine.md", "body")

    assert [n.slug for n in store.walk(hm, None)] == ["fine"]


# --- resolution ------------------------------------------------------------ #


def test_the_title_ignores_a_heading_inside_a_fence(tmp_path):
    """Measured on this repository: of eight files under plans/, one opens with an
    `###` and has its first `#` inside a ```bash fence."""
    hm = home(tmp_path)
    note(
        hm / "kb",
        "flw/orientation.md",
        "### Orienting across repos\n\n```bash\n# the wiring: which env vars each repo reads\n```\n",
    )

    assert store.walk(hm, None)[0].title == "orientation"


def test_a_fenced_heading_does_not_hide_a_real_one_after_it(tmp_path):
    hm = home(tmp_path)
    note(hm / "kb", "flw/x.md", "```\n# fenced\n```\n\n# real\n")

    assert store.walk(hm, None)[0].title == "real"


def test_the_date_has_no_mtime_fallback(tmp_path):
    """git sets mtime to checkout time, so in a fresh clone every note would read
    as written today. `undated` is true; an mtime age is false in the one
    direction that hurts."""
    hm = home(tmp_path)
    note(hm / "kb", "python/x.md", "body")

    found = store.walk(hm, None)[0]
    assert found.updated is None
    assert "undated" in found.stamp(TODAY)


def test_the_age_and_the_size_are_printed_together(tmp_path):
    hm = home(tmp_path)
    note(hm / "kb", "python/x.md", "+++\nupdated = 2026-03-16\n+++\n" + "x" * 2048)

    stamp = store.walk(hm, None)[0].stamp(TODAY)
    assert "written 2026-03-16 · 168 days ago" in stamp
    assert "512 tokens" in stamp


def test_identity_is_the_filename_not_the_title(tmp_path):
    """Editing a title cannot orphan a reference to the note."""
    hm = home(tmp_path)
    note(hm / "kb", "python/pydantic-unions.md", "+++\ntitle = 'something else'\n+++\n")

    assert store.walk(hm, None)[0].slug == "pydantic-unions"


# --- filters --------------------------------------------------------------- #


def test_a_category_filter_is_a_prefix(tmp_path):
    hm = home(tmp_path)
    note(hm / "kb", "python/unions.md", "x")
    note(hm / "kb", "python/pandas/groupby.md", "x")
    note(hm / "kb", "rust/traits.md", "x")

    found = store.filtered(store.walk(hm, None), category="python")
    assert {n.slug for n in found} == {"unions", "groupby"}


def test_filters_are_anded(tmp_path):
    hm = home(tmp_path)
    note(hm / "kb", "a/one.md", "+++\ntags = ['x']\ntype = 'gotcha'\n+++\n")
    note(hm / "kb", "a/two.md", "+++\ntags = ['x']\ntype = 'decision'\n+++\n")

    found = store.filtered(store.walk(hm, None), tags=["x"], type_="gotcha")
    assert [n.slug for n in found] == ["one"]


def test_the_projects_category_sorts_first_and_never_filters(tmp_path):
    """A note about pydantic is as relevant inside the billing repo as outside it.
    Hiding it because a directory name did not match is the failure this exists to
    avoid."""
    hm = home(tmp_path)
    for i in range(3):
        note(hm / "kb", f"python/unions{i}.md", "peculiarword")
    project = tmp_path / "proj"
    note(project, "plans/notes/ci.md", "peculiarword")

    # The project's category is named to lose both tiebreaks: `zeta` sorts after
    # `python`, and one note against three loses on size. Only the rule puts it
    # first, so deleting the rule fails this rather than passing on the tiebreak.
    found = store.walk(hm, project, project_category="zeta")
    grouped = store.group(store.search(found, ["peculiarword"]), project_category="zeta")
    assert [name for name, _ in grouped] == ["zeta", "python"]
    assert sum(len(notes) for _, notes in grouped) == 4


# --- the parser: a filter means the same thing on either side of the verb --- #


def test_a_filter_before_the_verb_is_not_dropped():
    """A subparser parses into a fresh namespace and copies every key over the
    parent's, so without SUPPRESS this became an untagged full-store search in the
    default shape — exit 0, no warning, on the composition the help recommends."""
    parser = flw.build_parser()

    before = parser.parse_args(["kb", "-T", "-t", "python", "search", "foo"])
    after = parser.parse_args(["kb", "search", "foo", "-T", "-t", "python"])

    # The tags after the verb land under their own dest and the handler unions
    # the two, so what must match on both sides is the effective set.
    assert _tags(before) == _tags(after) == ["python"]
    assert before.tree is after.tree is True
    assert before.term == after.term == ["foo"]


def test_a_bare_kb_carries_the_same_filter_defaults():
    args = flw.build_parser().parse_args(["kb"])
    assert args.tag == [] and args.term == [] and args.stats is False


def test_shapes_are_mutually_exclusive():
    parser = flw.build_parser()
    for pair in (["-T", "-s"], ["-s", "-p"], ["-T", "-p"]):
        try:
            parser.parse_args(["kb", *pair])
        except SystemExit as exc:
            assert exc.code == 2
        else:  # pragma: no cover - the guard is the assertion
            raise AssertionError(f"{pair} parsed, and one shape means one")


# --- show ------------------------------------------------------------------ #


def test_a_bare_slug_in_two_categories_prints_both(tmp_path):
    """Guessing which was meant is how a lookup starts answering a question
    nobody asked."""
    hm = home(tmp_path)
    note(hm / "kb", "python/gotchas.md", "the python one")
    note(hm / "kb", "rust/gotchas.md", "the rust one")

    text, code = store.show(store.walk(hm, None), "gotchas", TODAY)
    assert code == 0
    assert "the python one" in text and "the rust one" in text
    assert "2 notes are called" in text


def test_a_category_qualified_slug_prints_one(tmp_path):
    hm = home(tmp_path)
    note(hm / "kb", "python/gotchas.md", "the python one")
    note(hm / "kb", "rust/gotchas.md", "the rust one")

    text, code = store.show(store.walk(hm, None), "python/gotchas", TODAY)
    assert code == 0
    assert "the python one" in text and "the rust one" not in text


def test_a_slug_that_resolves_to_nothing_exits_1(tmp_path):
    text, code = store.show(store.walk(home(tmp_path), None), "absent", TODAY)
    assert code == 1
    assert "absent" in text


# --- the ceiling ----------------------------------------------------------- #


def test_search_caps_the_categories_as_well_as_the_hits_inside_them(tmp_path):
    """Categories are freeform, so a per-category cap alone bounds nothing: at
    ~316 chars a windowed hit and five per category, eighteen matching categories
    is ~7,110 tokens — an answer larger than the skill that asked for it."""
    hm = home(tmp_path)
    for i in range(12):
        note(hm / "kb", f"cat{i:02d}/note.md", "peculiarword")

    found = store.search(store.walk(hm, None), ["peculiarword"])
    rendered = store.render_search(store.group(found), ["peculiarword"], TODAY)

    assert rendered.count("peculiarword") <= (store.CATEGORY_CAP + 1) * store.CAP
    assert "more in 7 categories" in rendered
    assert "-c <category>" in rendered


def test_a_category_prints_at_most_cap_hits_and_says_how_many_it_found(tmp_path):
    hm = home(tmp_path)
    for i in range(9):
        note(hm / "kb", f"python/note{i}.md", "peculiarword")

    found = store.search(store.walk(hm, None), ["peculiarword"])
    rendered = store.render_search(store.group(found), ["peculiarword"], TODAY)
    assert f"… {9 - store.CAP} more in python." in rendered


# --- the shapes ------------------------------------------------------------ #


def test_stats_counts_per_category_per_tag_per_type_per_root(tmp_path):
    hm = home(tmp_path)
    note(hm / "kb", "python/a.md", "+++\ntags = ['pydantic']\ntype = 'gotcha'\n+++\n")
    note(hm / "kb", "python/b.md", "+++\ntags = ['pydantic']\ntype = 'decision'\n+++\n")
    project = tmp_path / "proj"
    note(project, "plans/notes/ci.md", "x")

    rendered = store.render_stats(store.walk(hm, project, project_category="proj"))
    assert "machine-wide" in rendered and "2 notes · 1 category" in rendered
    assert "pydantic 2" in rendered
    assert "this repository" in rendered


def test_a_tree_carries_the_description_and_a_bare_title_is_visible_without_one(tmp_path):
    hm = home(tmp_path)
    note(hm / "kb", "python/a.md", "+++\ntitle = 'one'\ndescription = 'what it settles'\n+++\n")
    note(hm / "kb", "python/b.md", "+++\ntitle = 'two'\n+++\n")

    rendered = store.render_tree(store.group(store.walk(hm, None)), TODAY)
    assert "what it settles" in rendered
    assert "two" in rendered


def test_paths_prints_one_path_per_line(tmp_path):
    hm = home(tmp_path)
    note(hm / "kb", "python/a.md", "x")
    note(hm / "kb", "python/b.md", "x")

    lines = store.render_paths(store.walk(hm, None)).splitlines()
    assert len(lines) == 2 and all(line.endswith(".md") for line in lines)


def test_notes_within_a_category_are_most_recently_updated_first(tmp_path):
    hm = home(tmp_path)
    note(hm / "kb", "python/old.md", "+++\nupdated = 2026-01-01\n+++\n")
    note(hm / "kb", "python/new.md", "+++\nupdated = 2026-08-01\n+++\n")
    note(hm / "kb", "python/never.md", "body")

    (_, notes), = store.group(store.walk(hm, None))
    assert [n.slug for n in notes] == ["new", "old", "never"]


# --- config ---------------------------------------------------------------- #


def test_the_project_category_defaults_to_the_directory_name(tmp_path, monkeypatch):
    monkeypatch.setattr(flw, "FLW_HOME", home(tmp_path))
    project = tmp_path / "acme-billing"
    project.mkdir()
    assert flw._kb_category(project) == "acme-billing"


def test_the_project_category_is_overridable(tmp_path, monkeypatch):
    monkeypatch.setattr(flw, "FLW_HOME", home(tmp_path))
    project = tmp_path / "proj"
    (project / ".flw").mkdir(parents=True)
    (project / ".flw" / "config.toml").write_text('[kb]\ncategory = "acme-billing"\n')
    assert flw._kb_category(project) == "acme-billing"


def test_a_config_that_does_not_parse_stops_rather_than_defaulting(tmp_path, monkeypatch):
    """A defective config that silently falls back to defaults is a config that lies."""
    monkeypatch.setattr(flw, "FLW_HOME", home(tmp_path))
    project = tmp_path / "proj"
    (project / ".flw").mkdir(parents=True)
    (project / ".flw" / "config.toml").write_text("[kb\ncategory =")
    try:
        flw._kb_category(project)
    except SystemExit as exc:
        assert "does not parse" in str(exc)
    else:  # pragma: no cover - the guard is the assertion
        raise AssertionError("a broken config parsed")


def test_an_absent_store_is_a_state_and_not_a_fault(tmp_path):
    """The ordinary shape on the day flw is installed: nothing written yet."""
    assert store.walk(tmp_path / "nowhere", None) == []
    assert store.render_stats([]) == "no notes in either root."


def test_a_note_argparse_namespace_reaches_the_handler(tmp_path, monkeypatch, capsys):
    """The handler, end to end, against a store on disk."""
    hm = home(tmp_path)
    note(hm / "kb", "python/unions.md", "+++\ntitle = 'unions'\n+++\npeculiarword")
    project = tmp_path / "proj"
    (project / ".flw").mkdir(parents=True)
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(project)

    args = flw.build_parser().parse_args(["kb", "search", "peculiarword"])
    assert args.handler(args) == 0
    assert "unions" in capsys.readouterr().out


def test_a_bare_kb_prints_the_counts_not_the_contents(tmp_path, monkeypatch, capsys):
    """The cheapest thing to type must not be the most expensive thing to run."""
    hm = home(tmp_path)
    for i in range(20):
        note(hm / "kb", f"cat{i:02d}/note.md", "x" * 400)
    project = tmp_path / "proj"
    (project / ".flw").mkdir(parents=True)
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(project)

    args = flw.build_parser().parse_args(["kb"])
    assert args.handler(args) == 0
    out = capsys.readouterr().out
    assert "20 notes · 20 categories" in out
    assert "note" not in out.replace("20 notes", "")


def test_show_reaches_the_handler_and_a_missing_slug_exits_1(tmp_path, monkeypatch, capsys):
    hm = home(tmp_path)
    note(hm / "kb", "python/unions.md", "the body")
    project = tmp_path / "proj"
    (project / ".flw").mkdir(parents=True)
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(project)

    parser = flw.build_parser()
    args = parser.parse_args(["kb", "show", "unions"])
    assert args.handler(args) == 0
    assert "the body" in capsys.readouterr().out

    args = parser.parse_args(["kb", "show", "absent"])
    assert args.handler(args) == 1


def test_here_and_global_are_mutually_exclusive_and_each_reads_one_root(tmp_path):
    hm = home(tmp_path)
    note(hm / "kb", "python/machine.md", "x")
    project = tmp_path / "proj"
    note(project, "plans/notes/local.md", "x")

    only_here = store.walk(hm, project, project_category="proj", here=True)
    only_global = store.walk(hm, project, project_category="proj", globally=True)
    assert [n.slug for n in only_here] == ["local"]
    assert [n.slug for n in only_global] == ["machine"]

    try:
        flw.build_parser().parse_args(["kb", "--here", "--global"])
    except SystemExit as exc:
        assert exc.code == 2
    else:  # pragma: no cover - the guard is the assertion
        raise AssertionError("--here and --global parsed together")


def test_an_unfiled_note_at_the_machine_root_is_named_rather_than_dropped(tmp_path):
    """Only reachable by hand — the write path always takes a category. It reads
    rather than vanishing, because a note the store silently ignores is worse than
    one filed oddly."""
    hm = home(tmp_path)
    note(hm / "kb", "loose.md", "x")

    assert store.walk(hm, None)[0].category == store.UNFILED


# --- writing --------------------------------------------------------------- #


def _write(tmp_path, monkeypatch, argv, body="a measured thing\n"):
    """Run `flw kb write` with a body on stdin, from inside a project."""
    import io

    hm = home(tmp_path)
    project = tmp_path / "proj"
    (project / ".flw").mkdir(parents=True)
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(project)
    monkeypatch.setattr(sys, "stdin", io.StringIO(body))
    args = flw.build_parser().parse_args(argv)
    return args.handler(args), hm, project


def test_a_write_stamps_the_date_and_prints_the_path_and_the_size(tmp_path, monkeypatch, capsys):
    code, hm, _ = _write(
        tmp_path, monkeypatch,
        ["kb", "write", "python", "unions need a Literal", "-d", "an Enum picks variant one"],
    )
    assert code == 0
    written = hm / "kb" / "python" / "unions-need-a-literal.md"
    assert written.exists()
    text = written.read_text()
    assert 'title       = "unions need a Literal"' in text
    assert "updated     = " in text
    out = capsys.readouterr().out
    assert str(written) in out and "tokens" in out


def test_here_writes_into_the_project_and_takes_no_category(tmp_path, monkeypatch):
    code, _, project = _write(
        tmp_path, monkeypatch,
        ["kb", "write", "--here", "the CI runner has no network", "-d", "no egress at all"],
    )
    assert code == 0
    assert (project / "plans" / "notes" / "the-ci-runner-has-no-network.md").exists()


def test_here_with_a_category_is_refused_rather_than_silently_discarded(tmp_path, monkeypatch, capsys):
    code, _, _ = _write(
        tmp_path, monkeypatch,
        ["kb", "write", "--here", "python", "a title", "-d", "a description"],
    )
    assert code == 1
    assert "one argument" in capsys.readouterr().err


def test_a_missing_description_refuses_the_write(tmp_path, monkeypatch, capsys):
    code, hm, _ = _write(tmp_path, monkeypatch, ["kb", "write", "python", "a title"])
    assert code == 1
    assert "-d/--description is required" in capsys.readouterr().err
    assert not list((hm / "kb").rglob("*.md"))


def test_a_dangling_symlink_at_the_notes_path_is_refused(tmp_path, monkeypatch, capsys):
    """walk() skips a path that is not is_file(), so the caller's slug refusal
    cannot see this one. Writing through it created the file it pointed at,
    outside the store entirely."""
    hm = home(tmp_path)
    (hm / "kb" / "python").mkdir(parents=True)
    outside = tmp_path / "elsewhere" / "does-not-exist.yml"
    outside.parent.mkdir()
    (hm / "kb" / "python" / "a-title.md").symlink_to(outside)

    code, _, _ = _write(
        tmp_path, monkeypatch, ["kb", "write", "python", "a title", "-d", "a description"]
    )

    assert code == 1
    assert "already holds something flw did not write" in capsys.readouterr().err
    assert not outside.exists()


def test_a_symlink_to_an_unreadable_file_is_refused_and_that_file_survives(
    tmp_path, monkeypatch, capsys
):
    """The other shape walk() skips: is_file() passes and read_text raises, so
    the note is invisible to the store and the write lands on the user's file."""
    hm = home(tmp_path)
    (hm / "kb" / "python").mkdir(parents=True)
    outside = tmp_path / "elsewhere" / "app.conf"
    outside.parent.mkdir()
    outside.write_bytes(b"BINARY\xff\xfe CONFIG\n")
    before = outside.read_bytes()
    (hm / "kb" / "python" / "a-title.md").symlink_to(outside)

    code, _, _ = _write(
        tmp_path, monkeypatch, ["kb", "write", "python", "a title", "-d", "a description"]
    )

    assert code == 1
    assert "already holds something flw did not write" in capsys.readouterr().err
    assert outside.read_bytes() == before


def test_a_readable_note_at_the_path_is_still_the_slug_refusal(tmp_path, monkeypatch, capsys):
    """The two refusals are separate and must stay separate: this one names the
    slug and tells the user to edit the note, and it is the one that fires for
    every path the store can actually read."""
    hm = home(tmp_path)
    note(hm / "kb", "python/a-title.md", "+++\ntitle = \"a title\"\n+++\n\nbody\n")

    code, _, _ = _write(
        tmp_path, monkeypatch, ["kb", "write", "python", "a title", "-d", "a description"]
    )

    assert code == 1
    err = capsys.readouterr().err
    assert "already holds that slug" in err
    assert "flw did not write" not in err


def test_an_empty_body_is_refused_and_names_stdin(tmp_path, monkeypatch, capsys):
    """An agent's stdin is an empty non-tty, so a generated command line missing its
    `< note.md` would otherwise write frontmatter and no body, stamp updated, print a
    path and exit 0 — and the slug refusal would then block the retry."""
    code, hm, _ = _write(
        tmp_path, monkeypatch,
        ["kb", "write", "python", "a title", "-d", "a description"],
        body="",
    )
    assert code == 1
    err = capsys.readouterr().err
    assert "the note is empty" in err and "< note.md" in err
    assert not list((hm / "kb").rglob("*.md"))


def test_an_existing_slug_in_the_target_category_is_refused(tmp_path, monkeypatch, capsys):
    """The file is there, so read it and edit it rather than writing a
    near-duplicate beside it."""
    code, hm, _ = _write(
        tmp_path, monkeypatch, ["kb", "write", "python", "unions", "-d", "first"]
    )
    assert code == 0
    capsys.readouterr()

    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO("second body"))
    args = flw.build_parser().parse_args(["kb", "write", "python", "unions", "-d", "second"])
    assert args.handler(args) == 1
    assert "already holds that slug" in capsys.readouterr().err
    assert "first" in (hm / "kb" / "python" / "unions.md").read_text()


def test_the_same_stem_in_another_category_is_not_a_collision(tmp_path, monkeypatch):
    code, hm, _ = _write(
        tmp_path, monkeypatch, ["kb", "write", "python", "gotchas", "-d", "the python one"]
    )
    assert code == 0

    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO("the rust body"))
    args = flw.build_parser().parse_args(["kb", "write", "rust", "gotchas", "-d", "the rust one"])
    assert args.handler(args) == 0
    assert (hm / "kb" / "rust" / "gotchas.md").exists()


def test_near_duplicates_reach_stderr_and_the_write_still_happens(tmp_path, monkeypatch, capsys):
    """An agent cannot be asked a question mid-run, so the names land in the tool
    result where it reads them rather than blocking."""
    code, hm, _ = _write(
        tmp_path, monkeypatch,
        ["kb", "write", "python",
         "discriminated unions need a Literal, not an Enum", "-d", "one"],
    )
    assert code == 0
    capsys.readouterr()

    import io

    # The shorter title, whose every term the existing note carries. ANDing is
    # directional: a title that adds a word to an existing one is not warned
    # about, which is the price of not naming 54 notes out of 156.
    monkeypatch.setattr(sys, "stdin", io.StringIO("another body"))
    args = flw.build_parser().parse_args(
        ["kb", "write", "python", "discriminated unions need a Literal", "-d", "two"]
    )
    assert args.handler(args) == 0
    err = capsys.readouterr().err
    assert "already written" in err and "discriminated" in err
    assert (hm / "kb" / "python" / "discriminated-unions-need-a-literal.md").exists()


def test_a_missing_type_or_tags_says_what_the_note_will_lack(tmp_path, monkeypatch, capsys):
    code, _, _ = _write(
        tmp_path, monkeypatch, ["kb", "write", "python", "a title", "-d", "a description"]
    )
    assert code == 0
    err = capsys.readouterr().err
    assert "--type" in err and "--tags" in err and "flw kb -s" in err


def test_type_and_tags_are_emitted_when_given(tmp_path, monkeypatch):
    code, hm, _ = _write(
        tmp_path, monkeypatch,
        ["kb", "write", "python", "unions", "-d", "d", "--type", "gotcha",
         "--tags", "pydantic, validation"],
    )
    assert code == 0
    text = (hm / "kb" / "python" / "unions.md").read_text()
    assert 'type        = "gotcha"' in text
    assert 'tags        = ["pydantic", "validation"]' in text


def test_a_written_note_reads_back_through_the_walk(tmp_path, monkeypatch):
    """The write path and the read path agree, which is the only thing that makes
    either useful."""
    code, hm, project = _write(
        tmp_path, monkeypatch,
        ["kb", "write", "python/pandas", "groupby beats merge", "-d", "for this shape",
         "--type", "gotcha", "--tags", "pandas"],
    )
    assert code == 0

    found = store.walk(hm, project, project_category="proj")
    assert len(found) == 1
    note_ = found[0]
    assert note_.category == "python/pandas"
    assert note_.title == "groupby beats merge"
    assert note_.description == "for this shape"
    assert note_.type == "gotcha" and note_.tags == ["pandas"]
    assert note_.updated is not None


def test_the_write_help_carries_the_five_rules_and_the_type_versus_tag_test(capsys):
    """They live here and nowhere else at runtime. A rule in a design document is
    read by nobody."""
    parser = flw.build_parser()
    try:
        parser.parse_args(["kb", "write", "--help"])
    except SystemExit:
        pass
    # Flattened, because where argparse wraps a line is not what is under test.
    out = " ".join(capsys.readouterr().out.split())
    assert "could not have been derived" in out
    assert "not what was concluded" in out
    assert "never overwritten" in out
    assert "hint to verify" in out
    assert "never an instruction" in out
    assert "if your tag is `gotcha` you meant a type" in out


def test_the_title_becomes_the_slug_and_the_slug_is_the_identity(tmp_path, monkeypatch):
    code, hm, _ = _write(
        tmp_path, monkeypatch,
        ["kb", "write", "python", "Field(discriminator=…) needs a Literal!", "-d", "d"],
    )
    assert code == 0
    assert (hm / "kb" / "python" / "field-discriminator-needs-a-literal.md").exists()


# --- lint ------------------------------------------------------------------- #


def test_lint_reports_undescribed_and_undated(tmp_path):
    hm = home(tmp_path)
    note(hm / "kb", "python/bare.md", "no frontmatter at all")
    # Dated ahead, so this one trips no check at all: a note written today has
    # today's mtime, which is exactly what edited-since-stamped looks at.
    note(hm / "kb", "python/full.md",
         "+++\ntitle = 't'\ndescription = 'd'\nupdated = 2099-01-01\n+++\nbody")

    report = store.lint(store.walk(hm, None), TODAY)
    assert "undescribed  (1)" in report and "python/bare" in report
    assert "undated  (1)" in report
    assert "python/full" not in report


def test_lint_names_a_block_that_did_not_parse_with_its_error(tmp_path):
    hm = home(tmp_path)
    note(hm / "kb", "python/broken.md", "+++\ntitle = not quoted\n+++\nbody")

    report = store.lint(store.walk(hm, None), TODAY)
    assert "unparseable frontmatter  (1)" in report
    assert "python/broken" in report


def test_lint_reports_a_stem_in_more_than_one_category(tmp_path):
    hm = home(tmp_path)
    note(hm / "kb", "python/gotchas.md", "x")
    note(hm / "kb", "rust/gotchas.md", "x")

    report = store.lint(store.walk(hm, None), TODAY)
    assert "ambiguous slugs  (1)" in report
    assert "gotchas: python, rust" in report


def test_lint_reports_near_duplicates_by_the_write_paths_own_search(tmp_path):
    """The write path only covers notes written through the command, and writing
    the file directly is the point — so the same search runs again over the whole
    store."""
    hm = home(tmp_path)
    note(hm / "kb", "python/a.md",
         "+++\ntitle = 'discriminated unions need a Literal'\n+++\nx")
    note(hm / "kb", "python/b.md",
         "+++\ntitle = 'discriminated unions need a Literal, not an Enum'\n+++\nx")

    report = store.lint(store.walk(hm, None), TODAY)
    assert "near-duplicates" in report
    assert "python/a  ~  python/b" in report


def test_lint_reports_a_pair_once_rather_than_from_both_ends(tmp_path):
    hm = home(tmp_path)
    note(hm / "kb", "python/a.md",
         "+++\ntitle = 'pydantic discriminated unions'\n+++\nx")
    note(hm / "kb", "python/b.md",
         "+++\ntitle = 'pydantic discriminated unions, restated'\n+++\nx")

    report = store.lint(store.walk(hm, None), TODAY)
    assert report.count("near-duplicates  (1)") == 1


def test_edited_since_stamped_fires_under_the_machine_root(tmp_path):
    hm = home(tmp_path)
    written = note(hm / "kb", "python/x.md",
                   "+++\ntitle = 't'\ndescription = 'd'\nupdated = 2020-01-01\n+++\nbody")
    assert written.stat().st_mtime > 0  # today, by construction

    report = store.lint(store.walk(hm, None), TODAY)
    assert "edited since stamped  (1)" in report
    assert "stamped 2020-01-01" in report


def test_edited_since_stamped_does_not_fire_in_the_project_root(tmp_path):
    """git sets mtime to checkout time, so a clone taken minutes ago would report
    every note in the project root — and a check that fires on everything is a
    check nobody reads."""
    project = tmp_path / "proj"
    note(project, "plans/notes/x.md",
         "+++\ntitle = 't'\ndescription = 'd'\nupdated = 2020-01-01\n+++\nbody")

    report = store.lint(store.walk(home(tmp_path), project, project_category="proj"), TODAY)
    assert "edited since stamped" not in report


def test_a_clean_store_says_so_rather_than_printing_nothing(tmp_path):
    hm = home(tmp_path)
    written = note(hm / "kb", "python/x.md",
                   "+++\ntitle = 't'\ndescription = 'd'\nupdated = 2099-01-01\n+++\nbody")
    assert written.exists()

    report = store.lint(store.walk(hm, None), TODAY)
    assert report == "1 notes, nothing to report."


def test_lint_exits_0_with_findings_present(tmp_path, monkeypatch, capsys):
    """flw validate exits 1 because a malformed record blocks a run. Nothing
    downstream breaks because a note is old, and the cheapest way to green a red
    note check is `rm`."""
    hm = home(tmp_path)
    note(hm / "kb", "python/bare.md", "no frontmatter")
    project = tmp_path / "proj"
    (project / ".flw").mkdir(parents=True)
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(project)

    args = flw.build_parser().parse_args(["kb", "lint"])
    assert args.handler(args) == 0
    assert "undescribed" in capsys.readouterr().out


def test_lint_reads_both_roots_from_inside_a_project(tmp_path, monkeypatch, capsys):
    hm = home(tmp_path)
    note(hm / "kb", "python/machine.md", "no frontmatter")
    project = tmp_path / "proj"
    (project / ".flw").mkdir(parents=True)
    note(project, "plans/notes/local.md", "no frontmatter either")
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(project)

    args = flw.build_parser().parse_args(["kb", "lint"])
    assert args.handler(args) == 0
    out = capsys.readouterr().out
    assert "python/machine" in out and "proj/local" in out


def test_lint_on_an_empty_store_is_a_state_and_not_a_fault(tmp_path, monkeypatch, capsys):
    hm = home(tmp_path)
    project = tmp_path / "proj"
    (project / ".flw").mkdir(parents=True)
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(project)

    args = flw.build_parser().parse_args(["kb", "lint"])
    assert args.handler(args) == 0
    assert "no notes in either root" in capsys.readouterr().out


# --- what flw itself writes, read back by flw itself ----------------------- #


def test_a_quote_in_the_description_round_trips_through_the_parser(tmp_path, monkeypatch):
    """The note flw writes must parse as the note flw reads. Interpolating free
    text into a TOML basic string produced a block tomllib refused, so the
    description the command required came back as no description at all."""
    code, hm, project = _write(
        tmp_path, monkeypatch,
        ["kb", "write", "python", "pydantic discriminators",
         "-d", 'Field(discriminator="kind") needs a Literal, not an Enum.'],
    )
    assert code == 0

    found = store.walk(hm, project, project_category="proj")[0]
    assert found.malformed is None
    assert found.description == 'Field(discriminator="kind") needs a Literal, not an Enum.'
    assert found.updated is not None


def test_a_backslash_and_a_newline_survive_the_round_trip(tmp_path, monkeypatch):
    """A newline was worse than a broken parse: it injected whatever keys followed
    it, so a crafted title wrote a note counted under a type and a tag nobody set."""
    code, hm, project = _write(
        tmp_path, monkeypatch,
        ["kb", "write", "windows", 'set it to C:\\prog\\helper.exe',
         "-d", 'first line\nsecond line, and a " quote'],
    )
    assert code == 0

    found = store.walk(hm, project, project_category="proj")[0]
    assert found.malformed is None
    assert found.title == "set it to C:\\prog\\helper.exe"
    assert "\n" in found.description
    assert found.type == "" and found.tags == []


def test_a_quote_in_a_tag_or_a_type_round_trips(tmp_path, monkeypatch):
    code, hm, project = _write(
        tmp_path, monkeypatch,
        ["kb", "write", "python", "a title", "-d", "a description",
         "--type", 'go"tcha', "--tags", 'a"b, c\\d'],
    )
    assert code == 0

    found = store.walk(hm, project, project_category="proj")[0]
    assert found.malformed is None
    assert found.type == 'go"tcha'
    assert found.tags == ['a"b', "c\\d"]


# --- the category cannot climb out of the store ---------------------------- #


def test_a_category_that_climbs_out_is_refused(tmp_path, monkeypatch, capsys):
    """joinpath does not resolve `..`, so an unchecked category wrote the note
    outside the store — over any .md the user could write, at exit 0, and absent
    from every read surface afterwards."""
    outside = tmp_path / "othertree"
    outside.mkdir()
    (outside / "README.md").write_text("# Someone else's project\n")

    code, _, _ = _write(
        tmp_path, monkeypatch,
        ["kb", "write", "../../othertree", "README", "-d", "one line"],
    )
    assert code == 1
    assert "cannot climb out of the store" in capsys.readouterr().err
    assert (outside / "README.md").read_text() == "# Someone else's project\n"


def test_category_parts_drops_empty_and_dot_components():
    assert store.category_parts("python/pandas") == ["python", "pandas"]
    assert store.category_parts("python/") == ["python"]
    assert store.category_parts("./python") == ["python"]
    assert store.category_parts("/etc/passwd") == ["etc", "passwd"]
    assert store.category_parts("") == []
    assert store.category_parts(".") == []
    for climbing in ("..", "../x", "python/../../x"):
        try:
            store.category_parts(climbing)
        except ValueError as exc:
            assert climbing in str(exc)
        else:  # pragma: no cover - the guard is the assertion
            raise AssertionError(f"{climbing!r} was accepted")


def test_respelling_the_category_does_not_defeat_the_slug_refusal(tmp_path, monkeypatch, capsys):
    """`python/` and `./python` name the directory `python`, resolved to the same
    file, and matched neither spelling walk derives — so the refusal passed and
    the existing note's body was destroyed at exit 0."""
    import io

    code, hm, _ = _write(
        tmp_path, monkeypatch, ["kb", "write", "python", "quoting", "-d", "first"]
    )
    assert code == 0
    capsys.readouterr()

    for respelling in ("python/", "./python"):
        monkeypatch.setattr(sys, "stdin", io.StringIO("OVERWRITTEN"))
        args = flw.build_parser().parse_args(
            ["kb", "write", respelling, "quoting", "-d", "second"]
        )
        assert args.handler(args) == 1, respelling
        assert "already holds that slug" in capsys.readouterr().err

    assert "first" in (hm / "kb" / "python" / "quoting.md").read_text()


def test_a_slug_taken_in_the_other_root_does_not_refuse_a_machine_write(tmp_path, monkeypatch):
    """The two roots share category names by construction, so comparing the
    category alone refused a machine-wide write by naming a project note at a path
    it was never going to touch."""
    project = tmp_path / "proj"
    note(project, "plans/notes/python/uv.md", "the project's note about uv")

    code, hm, _ = _write(
        tmp_path, monkeypatch, ["kb", "write", "python", "uv", "-d", "how uv makes a venv"]
    )
    assert code == 0
    assert (hm / "kb" / "python" / "uv.md").exists()
    assert "the project's note about uv" in (
        project / "plans" / "notes" / "python" / "uv.md"
    ).read_text()


# --- the machine-wide store does not need a project ------------------------ #


def test_the_store_reads_outside_any_project(tmp_path, monkeypatch, capsys):
    """A session in a repository flw has never been run on is the case the
    machine-wide store exists for."""
    hm = home(tmp_path)
    note(hm / "kb", "python/unions.md", "+++\ntitle = 'unions'\n+++\npeculiarword")
    nowhere = tmp_path / "nowhere"
    nowhere.mkdir()
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(nowhere)

    args = flw.build_parser().parse_args(["kb", "search", "peculiarword"])
    assert args.handler(args) == 0
    assert "unions" in capsys.readouterr().out


def test_a_machine_wide_write_outside_any_project_succeeds(tmp_path, monkeypatch):
    import io

    hm = home(tmp_path)
    nowhere = tmp_path / "nowhere"
    nowhere.mkdir()
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(nowhere)
    monkeypatch.setattr(sys, "stdin", io.StringIO("a measured thing"))

    args = flw.build_parser().parse_args(["kb", "write", "python", "a title", "-d", "d"])
    assert args.handler(args) == 0
    assert (hm / "kb" / "python" / "a-title.md").exists()


def test_here_outside_a_project_is_refused_and_says_what_to_do(tmp_path, monkeypatch, capsys):
    import io

    hm = home(tmp_path)
    nowhere = tmp_path / "nowhere"
    nowhere.mkdir()
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(nowhere)
    monkeypatch.setattr(sys, "stdin", io.StringIO("body"))

    args = flw.build_parser().parse_args(["kb", "write", "--here", "a title", "-d", "d"])
    assert args.handler(args) == 1
    assert "no specs/ or .flw/" in capsys.readouterr().err


def test_lint_outside_any_project_reads_the_machine_root(tmp_path, monkeypatch, capsys):
    hm = home(tmp_path)
    note(hm / "kb", "python/bare.md", "no frontmatter")
    nowhere = tmp_path / "nowhere"
    nowhere.mkdir()
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(nowhere)

    args = flw.build_parser().parse_args(["kb", "lint"])
    assert args.handler(args) == 0
    assert "undescribed" in capsys.readouterr().out


# --- -p is the shape for piping, so stdout is paths and nothing else ------- #


def test_paths_puts_only_paths_on_stdout(tmp_path, monkeypatch, capsys):
    hm = home(tmp_path)
    note(hm / "kb", "python/a.md", "x")
    project = tmp_path / "proj"
    (project / ".flw").mkdir(parents=True)
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(project)

    args = flw.build_parser().parse_args(["kb", "-p"])
    assert args.handler(args) == 0
    captured = capsys.readouterr()
    assert [line for line in captured.out.splitlines() if line] == [
        str(hm / "kb" / "python" / "a.md")
    ]
    assert "root:" in captured.err


def test_the_resolved_category_is_printed_where_the_root_is(tmp_path, monkeypatch, capsys):
    """Three skills open with `flw kb -c <the project's category>`. Without this
    the only name an agent can guess is the directory's, and with [kb] category
    set that guess returns `no notes.` at exit 0."""
    hm = home(tmp_path)
    project = tmp_path / "proj"
    (project / ".flw").mkdir(parents=True)
    (project / ".flw" / "config.toml").write_text('[kb]\ncategory = "acme-billing"\n')
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(project)

    args = flw.build_parser().parse_args(["kb"])
    assert args.handler(args) == 0
    assert "category: acme-billing" in capsys.readouterr().err


# --- filters that compose across the verb ---------------------------------- #


def test_tags_on_both_sides_of_the_verb_are_unioned_not_replaced():
    """action='append' with a SUPPRESS default starts the subparser's list from
    empty, so copying it over the parent's replaced the tags rather than adding
    to them: the split form returned what one tag alone returns."""
    parser = flw.build_parser()
    split = parser.parse_args(["kb", "-t", "macos", "search", "proxy", "-t", "python"])
    together = parser.parse_args(["kb", "search", "proxy", "-t", "macos", "-t", "python"])

    assert sorted(_tags(split)) == sorted(_tags(together)) == ["macos", "python"]


def test_a_split_tag_filter_ands_both_tags_end_to_end(tmp_path, monkeypatch, capsys):
    hm = home(tmp_path)
    note(hm / "kb", "python/both.md", "+++\ntags = ['python', 'macos']\n+++\nproxy")
    note(hm / "kb", "python/one.md", "+++\ntags = ['python']\n+++\nproxy")
    project = tmp_path / "proj"
    (project / ".flw").mkdir(parents=True)
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(project)

    args = flw.build_parser().parse_args(
        ["kb", "-t", "macos", "search", "proxy", "-t", "python", "-p"]
    )
    assert args.handler(args) == 0
    out = capsys.readouterr().out
    assert "both.md" in out and "one.md" not in out


def test_a_repeated_tag_ands_rather_than_honouring_the_first(tmp_path, monkeypatch):
    hm = home(tmp_path)
    note(hm / "kb", "a/both.md", "+++\ntags = ['x', 'y']\n+++\nbody")
    note(hm / "kb", "a/one.md", "+++\ntags = ['x']\n+++\nbody")

    found = store.filtered(store.walk(hm, None), tags=["x", "y"])
    assert [n.slug for n in found] == ["both"]


def test_here_before_the_verb_and_global_after_it_are_refused(tmp_path, monkeypatch, capsys):
    """argparse enforces a mutually exclusive group per parser, so one on each
    side passes both groups; walking with both then skipped every root and
    answered nothing at exit 0."""
    hm = home(tmp_path)
    note(hm / "kb", "python/a.md", "proxy")
    project = tmp_path / "proj"
    (project / ".flw").mkdir(parents=True)
    note(project, "plans/notes/b.md", "proxy")
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(project)

    args = flw.build_parser().parse_args(["kb", "--here", "search", "proxy", "--global"])
    assert args.handler(args) == 1
    assert "opposites" in capsys.readouterr().err


def test_a_category_prefix_stops_at_a_path_separator(tmp_path):
    """-c python must not catch a category named pythonista."""
    hm = home(tmp_path)
    note(hm / "kb", "python/unions.md", "x")
    note(hm / "kb", "python/pandas/groupby.md", "x")
    note(hm / "kb", "pythonista/style.md", "x")

    found = store.filtered(store.walk(hm, None), category="python")
    assert {n.slug for n in found} == {"unions", "groupby"}


# --- an empty answer says which emptiness it is ---------------------------- #


def test_an_empty_store_and_an_excluding_filter_read_differently(tmp_path, monkeypatch, capsys):
    """`flw kb -s -t nosuchtag` said "no notes in either root" while both roots
    held notes."""
    hm = home(tmp_path)
    note(hm / "kb", "python/a.md", "+++\ntags = ['python']\n+++\nbody")
    project = tmp_path / "proj"
    (project / ".flw").mkdir(parents=True)
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(project)
    parser = flw.build_parser()

    args = parser.parse_args(["kb", "-s", "-t", "nosuchtag"])
    assert args.handler(args) == 0
    filtered_out = capsys.readouterr().out
    assert "nothing matched" in filtered_out
    assert "1 note that your filters excluded" in filtered_out

    for md in (hm / "kb").rglob("*.md"):
        md.unlink()
    args = parser.parse_args(["kb", "-s", "-t", "nosuchtag"])
    assert args.handler(args) == 0
    assert "no notes in either root." in capsys.readouterr().out


def test_nothing_matched_names_the_three_cases():
    one = store.Note(path=Path("a.md"), root=Path("/"), root_name=store.MACHINE,
                     category="python", body="x")
    assert store.nothing_matched([one], [one], True) == ""
    assert store.nothing_matched([], [], False) == "no notes in either root."
    assert store.nothing_matched([], [], True) == "no notes in either root."
    assert store.nothing_matched([], [one], False) == "no notes."
    assert "filters excluded" in store.nothing_matched([], [one], True)


# --- the duplicate check fires on duplicates ------------------------------- #


def test_two_notes_sharing_only_a_stopword_are_not_near_duplicates(tmp_path):
    """ORing the title's terms over whole bodies named most of the store. `lint`'s
    own argument, about mtime, is the one that applies: a check that fires on
    everything is a check nobody reads."""
    hm = home(tmp_path)
    note(hm / "kb", "python/uv.md",
         "+++\ntitle = 'uv makes a venv without pip'\n+++\n"
         "uv resolves from the lockfile only.")
    note(hm / "kb", "docker/layers.md",
         "+++\ntitle = 'a COPY invalidates every layer below it'\n+++\n"
         "The build cache is dropped without warning when a file above changes.")

    report = store.lint(store.walk(hm, None), TODAY)
    assert "near-duplicates" not in report


def test_a_title_of_only_short_words_matches_nothing(tmp_path):
    """The length floor's job changed with the AND. Under OR it kept stopwords from
    matching everything; under AND extra terms only narrow, so what it still
    guarantees is this: a title with no word over three characters yields no terms
    and is compared against nothing, rather than against every note holding `a`."""
    hm = home(tmp_path)
    note(hm / "kb", "python/a.md", "+++\ntitle = 'one of the two'\n+++\na body")
    note(hm / "kb", "python/b.md", "+++\ntitle = 'all of the ten'\n+++\na body")
    notes = store.walk(hm, None)

    assert store.near_duplicates(notes, "one of the two") == []
    assert "near-duplicates" not in store.lint(notes, TODAY)


def test_the_write_warning_uses_the_same_narrowed_search(tmp_path, monkeypatch, capsys):
    hm = home(tmp_path)
    note(hm / "kb", "docker/layers.md",
         "+++\ntitle = 'a COPY invalidates every layer below it'\n+++\n"
         "The cache is dropped without warning.")
    project = tmp_path / "proj"
    (project / ".flw").mkdir(parents=True)
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(project)

    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO("uv resolves from the lockfile"))
    args = flw.build_parser().parse_args(
        ["kb", "write", "python", "uv makes a venv without pip", "-d", "one line"]
    )
    assert args.handler(args) == 0
    assert "already written" not in capsys.readouterr().err


# --- a file it could not read says so -------------------------------------- #


def test_lint_names_a_file_it_could_not_decode(tmp_path):
    """`flw kb search encoding` returned `nothing matched.` at exit 0 while the
    word sat in a latin-1 file in the store."""
    hm = home(tmp_path)
    (hm / "kb" / "hand").mkdir(parents=True)
    (hm / "kb" / "hand" / "latin1.md").write_bytes(
        "+++\ntitle = 'x'\n+++\ncaf\u00e9 encoding\n".encode("latin-1")
    )
    note(hm / "kb", "hand/fine.md", "+++\ntitle = 'fine'\ndescription = 'd'\nupdated = 2099-01-01\n+++\nbody")

    skipped: list = []
    notes = store.walk(hm, None, skipped=skipped)
    assert [n.slug for n in notes] == ["fine"]
    assert len(skipped) == 1 and "latin1.md" in str(skipped[0][0])

    report = store.lint(notes, TODAY, skipped=skipped)
    assert "unreadable  (1)" in report
    assert "latin1.md" in report and "codec" in report


def test_an_unreadable_file_is_named_by_lint(tmp_path):
    hm = home(tmp_path)
    locked = note(hm / "kb", "hand/locked.md", "+++\ntitle = 'x'\n+++\nbody")
    locked.chmod(0o000)
    try:
        skipped: list = []
        notes = store.walk(hm, None, skipped=skipped)
        if not skipped:  # pragma: no cover - a filesystem that ignores mode bits
            return
        report = store.lint(notes, TODAY, skipped=skipped)
        assert "unreadable" in report and "locked.md" in report
    finally:
        locked.chmod(0o644)


def test_a_read_verb_says_how_many_it_skipped(tmp_path, monkeypatch, capsys):
    hm = home(tmp_path)
    (hm / "kb" / "hand").mkdir(parents=True)
    (hm / "kb" / "hand" / "latin1.md").write_bytes(
        "+++\ntitle = 'x'\n+++\ncaf\u00e9 encoding\n".encode("latin-1")
    )
    project = tmp_path / "proj"
    (project / ".flw").mkdir(parents=True)
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(project)

    args = flw.build_parser().parse_args(["kb", "search", "encoding"])
    assert args.handler(args) == 0
    err = capsys.readouterr().err
    assert "1 note could not be read" in err
    assert "flw kb lint names them all" in err


def test_a_walk_with_no_skipped_list_behaves_exactly_as_before(tmp_path):
    hm = home(tmp_path)
    (hm / "kb" / "hand").mkdir(parents=True)
    (hm / "kb" / "hand" / "bad.md").write_bytes(b"\xff\xfe not utf-8")
    note(hm / "kb", "hand/fine.md", "body")

    assert [n.slug for n in store.walk(hm, None)] == ["fine"]


def test_lint_on_a_store_of_only_unreadable_files_still_reports(tmp_path):
    hm = home(tmp_path)
    (hm / "kb" / "hand").mkdir(parents=True)
    (hm / "kb" / "hand" / "bad.md").write_bytes(b"\xff\xfe not utf-8")

    skipped: list = []
    notes = store.walk(hm, None, skipped=skipped)
    assert notes == []
    assert "unreadable  (1)" in store.lint(notes, TODAY, skipped=skipped)


# --- a title in any script --------------------------------------------------- #


def test_a_non_latin_title_produces_a_stem_that_carries_it():
    assert store.slug("Кэш прокси всегда пустой") == "кэш-прокси-всегда-пустой"
    assert store.slug("日本語のノート") == "日本語のノート"
    assert store.slug("Таймаут соединения 30 секунд") == "таймаут-соединения-30-секунд"


def test_an_ascii_title_slugs_as_it_did_except_for_the_underscore():
    assert store.slug("unions need a Literal") == "unions-need-a-literal"
    assert store.slug("Field(discriminator=…) needs a Literal!") == (
        "field-discriminator-needs-a-literal"
    )
    # `_` is a word character, so it survives where it used to become `-`.
    assert store.slug("a_b c") == "a_b-c"


def test_two_non_latin_titles_in_one_category_do_not_collide(tmp_path, monkeypatch):
    import io

    hm = home(tmp_path)
    project = tmp_path / "proj"
    (project / ".flw").mkdir(parents=True)
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(project)
    parser = flw.build_parser()

    for title in ("Кэш прокси всегда пустой", "Логи ротируются раз в сутки"):
        monkeypatch.setattr(sys, "stdin", io.StringIO("измерено"))
        args = parser.parse_args(["kb", "write", "ru", title, "-d", "одна строка"])
        assert args.handler(args) == 0, title

    written = sorted(p.name for p in (hm / "kb" / "ru").glob("*.md"))
    assert written == ["кэш-прокси-всегда-пустой.md", "логи-ротируются-раз-в-сутки.md"]


def test_a_title_with_no_word_characters_still_gets_a_stem():
    assert store.slug("!!! ???") == "note"


# --- a search must exclude, not merely return ------------------------------ #


def test_a_search_excludes_a_note_that_does_not_match(tmp_path):
    """Replacing store.search's body with `return list(notes)` passed 387 tests:
    no test ever gave it a note that should not match."""
    hm = home(tmp_path)
    note(hm / "kb", "python/hit.md", "the body says peculiarword")
    note(hm / "kb", "python/miss.md", "the body says something else entirely")

    found = store.search(store.walk(hm, None), ["peculiarword"])
    assert [n.slug for n in found] == ["hit"]


def test_two_terms_are_anded_across_a_note(tmp_path):
    """Changing search's all() to any() also passed 387 tests, and no test
    anywhere passed two terms."""
    hm = home(tmp_path)
    note(hm / "kb", "python/both.md", "peculiarword and alsopeculiar in one note")
    note(hm / "kb", "python/one.md", "peculiarword by itself")

    found = store.search(store.walk(hm, None), ["peculiarword", "alsopeculiar"])
    assert [n.slug for n in found] == ["both"]


def test_the_handler_searches_rather_than_printing_the_store(tmp_path, monkeypatch, capsys):
    """Deleting the search call from the handler passed 387 tests, because the
    handler test put one note in the store and asserted it came back."""
    hm = home(tmp_path)
    note(hm / "kb", "python/hit.md", "+++\ntitle = 'the hit'\n+++\npeculiarword")
    note(hm / "kb", "python/miss.md", "+++\ntitle = 'the miss'\n+++\nsomething else")
    project = tmp_path / "proj"
    (project / ".flw").mkdir(parents=True)
    monkeypatch.setattr(flw, "FLW_HOME", hm)
    monkeypatch.chdir(project)

    args = flw.build_parser().parse_args(["kb", "search", "peculiarword"])
    assert args.handler(args) == 0
    out = capsys.readouterr().out
    assert "the hit" in out and "the miss" not in out


# --- the shape three skills run at their opening --------------------------- #


def test_render_index_caps_and_says_how_many_it_did_not_print(tmp_path):
    """`flw kb -c <category>` is what three skills run at their opening, and the
    string did not appear in this file."""
    hm = home(tmp_path)
    for i in range(9):
        note(hm / "kb", f"python/note{i}.md",
             f"+++\ntitle = 'note {i}'\nupdated = 2026-0{i + 1}-01\n+++\nbody")

    rendered = store.render_index(store.group(store.walk(hm, None)), TODAY)
    assert "9 notes" in rendered
    assert rendered.count("note ") >= store.CAP
    assert f"… {9 - store.CAP} more notes." in rendered


def test_render_index_on_one_category_prints_it_whole_when_it_fits(tmp_path):
    hm = home(tmp_path)
    note(hm / "kb", "python/a.md", "+++\ntitle = 'the only one'\n+++\nbody")

    rendered = store.render_index(store.group(store.walk(hm, None)), TODAY)
    assert "1 note" in rendered and "the only one" in rendered
    assert "more notes." not in rendered


def test_the_duplicate_index_matches_the_reference_search(tmp_path):
    """lint reaches its pairs through an inverted index; the write path runs the
    patterns directly. They must be the same answer, or `flw kb lint` and the
    warning `flw kb write` prints disagree about what a duplicate is."""
    import itertools
    import random

    words = [
        "resolver", "lockfile", "venv", "proxy", "egress", "keychain",
        "discriminator", "literal", "enum", "autovacuum", "pagerank",
        "symlink", "barrel", "transitive", "damping",
    ]
    rng = random.Random(11)
    hm = home(tmp_path)
    for i in range(60):
        title = " ".join(rng.sample(words, rng.randint(2, 5)))
        body = " ".join(rng.choice(words) for _ in range(40))
        note(hm / "kb", f"c{i % 5}/n{i:02d}.md",
             f"+++\ntitle = \"{title}\"\n+++\n{body}\n")
    notes = store.walk(hm, None)

    # The reference: every title against every other note, patterns run directly.
    reference = set()
    for one, other in itertools.permutations(notes, 2):
        if other in store.near_duplicates([other], one.title):
            reference.add(
                tuple(sorted((f"{one.category}/{one.slug}", f"{other.category}/{other.slug}")))
            )

    indexed = {tuple(line.split("  ~  ")) for line in store._duplicate_pairs(notes)}
    assert indexed == {tuple(sorted(pair)) for pair in reference}
    assert indexed, "the corpus produced no pairs, so this proved nothing"


def test_searchable_is_built_once_and_kept(tmp_path):
    hm = home(tmp_path)
    note(hm / "kb", "python/a.md", "+++\ntitle = 't'\n+++\nthe body")
    found = store.walk(hm, None)[0]

    assert found._searchable is None
    first = found.searchable
    assert found._searchable == first
    assert found.searchable is first


# --- a note that cites something it cannot date ------------------------------ #
#
# `updated` is a date, and a date cannot be diffed against: two commits land on one
# day and the second is what moved the line the note cites. So a note carrying a
# measurement and no `revision` has nothing for a check to measure it against, and
# that is what lint reports — the shape of the claim, never its truth.


def linted(tmp_path: Path, *notes: tuple[str, str]) -> str:
    hm = home(tmp_path)
    for rel, text in notes:
        note(hm / "kb", rel, text)
    return store.lint(store.walk(hm, None))


ROW = "claims with no revision to date them"


def test_a_note_citing_a_path_and_line_with_no_revision_is_reported(tmp_path):
    report = linted(
        tmp_path,
        (
            "flw/counts.md",
            (
                "+++\ntitle = 'counts'\nupdated = 2026-09-02\n+++\n"
                "The row is built at `core/scripts/scout.py:478`.\n"
            ),
        ),
    )
    assert ROW in report
    assert "flw/counts — e.g. core/scripts/scout.py:478" in report


def test_a_note_carrying_a_revision_is_not_reported(tmp_path):
    """The negative that makes the row actionable: recording the revision the
    measurement was taken at is what takes a note off the list."""
    report = linted(
        tmp_path,
        (
            "flw/counts.md",
            (
                "+++\ntitle = 'counts'\nrevision = 'f5d11a6'\n+++\n"
                "The row is built at `core/scripts/scout.py:478`.\n"
            ),
        ),
    )
    assert ROW not in report


def test_a_note_with_no_countable_claim_is_not_reported(tmp_path):
    report = linted(
        tmp_path,
        (
            "flw/prose.md",
            (
                "+++\ntitle = 'prose'\n+++\n"
                "A call reached through the module is counted on the module's own row.\n"
            ),
        ),
    )
    assert ROW not in report


def test_a_bare_count_with_no_revision_is_reported(tmp_path):
    report = linted(
        tmp_path,
        ("flw/counts.md", "+++\ntitle = 'counts'\n+++\nThe sweep found 9 call sites.\n"),
    )
    assert "flw/counts — e.g. 9" in report


def test_an_updated_date_is_not_a_revision(tmp_path):
    """`updated` is the field a note already carries, and reading it as a revision
    would report the store clean while every citation in it is undatable."""
    hm = home(tmp_path)
    note(hm / "kb", "flw/counts.md", "+++\ntitle = 'c'\nupdated = 2026-09-02\n+++\nat x.py:1\n")
    assert store.walk(hm, None)[0].revision == ""


def test_a_note_root_reached_through_a_symlink_still_walks(tmp_path):
    """The negative half of the record that resolved the knowledge store's
    comparisons: `walk` needs no resolve, because `path.parent.relative_to(root)`
    derives both sides from the root it was handed and `rglob` never leaves it.
    Nothing hands `walk` an outside path — `flw kb show` addresses by slug — so
    resolving here would be defensive code for an input that cannot occur."""
    hm = home(tmp_path)
    real = tmp_path / "elsewhere" / "kb"
    note(real, "python/unions.md", "+++\ntitle = 'unions'\n+++\nbody")
    (hm / "kb").rmdir()
    try:
        (hm / "kb").symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("this platform cannot create a symlink")

    found = store.walk(hm, None)
    assert [(n.slug, n.category) for n in found] == [("unions", "python")]
