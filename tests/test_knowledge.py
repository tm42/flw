"""The knowledge store — a mirror of the code, a git diff, and a fold nobody authors.

Every test reads the shipped toy example at
`core/skills/flw-research/references/knowledge-example/`: a parent `acme` with
members `shop` and `worker`, the seam declared from both sides. It is the fixture
and the documentation at once, so a change that breaks the shape a first survey
imitates breaks this suite too.

Every git call in the module goes through one function, and almost every test that
needs a diff replaces it with canned numstat output or a failure. One test is the
exception, and runs `git()` itself — see it for why.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core" / "scripts"))
import knowledge

REPO = Path(__file__).resolve().parent.parent

# The name test_cli.py loads it under, and reused when it already has: two
# module objects for one file are two sets of module constants, and a fixture
# that patches FLW_HOME on one leaves the other reading the machine's.
flw = sys.modules.get("flw_cli")
if flw is None:
    _spec = importlib.util.spec_from_file_location("flw_cli", REPO / "cli" / "flw.py")
    flw = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = flw
    _spec.loader.exec_module(flw)

TOY = REPO / "core" / "skills" / "flw-research" / "references" / "knowledge-example"
ACME = TOY / "acme"

# `git diff --numstat` for the shop's api/ — three files, +41 −12, the plan's
# Samples line. Tab-separated, because that is what git emits.
NUMSTAT = "20\t5\tapi/orders.py\n15\t4\tapi/models.py\n6\t3\tapi/routes.py\n"


def store_of(root: Path) -> Path:
    return root / ".flw" / "knowledge"


@pytest.fixture
def acme(tmp_path: Path) -> Path:
    """A writable copy, for the tests that stamp, reindex or rename."""
    target = tmp_path / "acme"
    shutil.copytree(ACME, target)
    return target


def members_of(parent: Path) -> dict[str, Path]:
    return {"shop": parent / "shop", "worker": parent / "worker"}


def canned(monkeypatch, answers):
    """Replace the one git function. `answers` maps a leading arg to (code, out)."""
    calls: list[tuple[list[str], Path]] = []

    def fake(args: list[str], cwd: Path) -> tuple[int, str]:
        calls.append((args, cwd))
        for key, value in answers.items():
            if key in " ".join(args):
                return value
        return 0, ""

    monkeypatch.setattr(knowledge, "git", fake)
    return calls


# --- the one test that runs git ---------------------------------------------- #


def test_git_itself_picks_stderr_on_failure(tmp_path):
    """Every other test in this file replaces `git()` with `canned` or a direct
    `setattr`, so nothing ever ran its body: the choice between stdout and
    stderr on a failing call was held only by a docstring, and a mutation
    swapping it back to stdout left the rest of the suite green. This is the
    one exception to "no test runs git" — against a directory that is not a
    repository, where a present git exits non-zero with `fatal:` on stderr."""
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH")
    code, out = knowledge.git(["rev-parse", "--short", "HEAD"], tmp_path)
    assert code != 0
    assert "fatal:" in out


# --- reading one file ------------------------------------------------------- #


def test_the_repo_file_is_the_basename_and_position_names_the_level():
    shop, worker = ACME / "shop", ACME / "worker"
    assert knowledge.level_of(store_of(ACME), ACME, store_of(ACME) / "system.md") == "System"
    assert knowledge.level_of(store_of(shop), shop, store_of(shop) / "shop.md") == "Repository"
    assert (
        knowledge.level_of(store_of(shop), shop, store_of(shop) / "api" / "api.md") == "Area"
    )
    assert (
        knowledge.level_of(store_of(shop), shop, store_of(shop) / "api" / "orders.py.md")
        == "Module"
    )
    assert knowledge.level_of(store_of(worker), worker, store_of(worker) / "worker.md") == (
        "Repository"
    )


def test_the_toy_reads_with_one_problem_and_it_is_the_deliberate_one():
    for root in (ACME, ACME / "shop"):
        for path in knowledge.concepts(store_of(root)):
            assert knowledge.load(path, store_of(root), root).problems == []

    worker = ACME / "worker"
    concept = knowledge.load(store_of(worker) / "worker.md", store_of(worker), worker)
    assert concept.problems == ["unstamped"]
    # Unstamped is the one problem that does not hide a file.
    assert concept.listable


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("+++\ntype = 'Repository'\ndescription = 'x'\nrevision = '1'\n+++\nbody\n", []),
        ("+++\nthis is not toml\n+++\nbody\n", ["malformed", "missing type",
                                                "missing description", "unstamped"]),
        ("+++\ndescription = 'x'\nrevision = '1'\n+++\n", ["missing type"]),
        ("+++\ntype = 'Repository'\nrevision = '1'\n+++\n", ["missing description"]),
        ("+++\ntype = 'Repository'\ndescription = 'x'\n+++\n", ["unstamped"]),
        ("+++\ntype = 'Area'\ndescription = 'x'\nrevision = '1'\n+++\n",
         ["type disagrees with position"]),
    ],
)
def test_every_problem_is_reported_by_name_and_none_of_them_raises(
    tmp_path, text, expected
):
    root = tmp_path / "repo"
    store = store_of(root)
    store.mkdir(parents=True)
    path = store / "repo.md"
    path.write_text(text)
    assert knowledge.load(path, store, root).problems == expected


def test_a_file_that_is_not_utf8_is_unreadable_and_skipped(tmp_path):
    root = tmp_path / "repo"
    store = store_of(root)
    store.mkdir(parents=True)
    path = store / "repo.md"
    path.write_bytes(b"+++\ntype = 'Repository'\n+++\n\xff\xfe not utf-8\n")

    concept = knowledge.load(path, store, root)
    assert concept.problems == ["unreadable"]
    assert not concept.listable


def test_a_malformed_block_reads_as_a_file_with_no_frontmatter(tmp_path):
    """The note store's reading, unchanged: one hand-written typo must not be
    able to break every command over the store."""
    root = tmp_path / "repo"
    store = store_of(root)
    store.mkdir(parents=True)
    path = store / "repo.md"
    path.write_text("+++\nnot = = toml\n+++\nthe body survives\n")

    concept = knowledge.load(path, store, root)
    assert "malformed" in concept.problems
    assert "the body survives" in concept.body


# --- the walk --------------------------------------------------------------- #


def test_the_walk_is_three_candidates_and_two_of_them_exist():
    shop = ACME / "shop"
    store = store_of(shop)
    found = knowledge.candidates(shop, store, Path("api/orders.py"))
    assert found == [
        store / "api" / "orders.py.md",
        store / "api" / "api.md",
        store / "shop.md",
    ]
    assert knowledge.walk(shop, store, Path("api/orders.py")) == [
        store / "api" / "api.md",
        store / "shop.md",
    ]


def test_a_directory_walks_from_itself_and_the_root_walks_to_the_repo_file():
    shop = ACME / "shop"
    store = store_of(shop)
    assert knowledge.walk(shop, store, Path("api")) == [
        store / "api" / "api.md",
        store / "shop.md",
    ]
    assert knowledge.walk(shop, store, Path(".")) == [store / "shop.md"]


def test_a_path_outside_the_root_is_refused_and_so_is_one_not_in_the_code(tmp_path):
    shop = ACME / "shop"
    with pytest.raises(knowledge.Refused, match="not under"):
        knowledge.relative_to_root(shop, tmp_path)
    with pytest.raises(knowledge.Refused, match="not in the code"):
        knowledge.relative_to_root(shop, Path("api/nothing.py"))
    assert knowledge.relative_to_root(shop, shop / "api" / "orders.py") == Path(
        "api/orders.py"
    )


def test_concepts_lead_with_the_store_s_own_file_and_never_with_a_subdirectory():
    """Depth before name: sorted by bytes, `api/api.md` precedes `shop.md`, which
    is the reverse of the order a reader descends in."""
    shop = ACME / "shop"
    assert [p.name for p in knowledge.concepts(store_of(shop))] == ["shop.md", "api.md"]


def test_index_md_is_reserved_and_never_a_concept():
    shop = ACME / "shop"
    assert (store_of(shop) / "index.md").is_file()
    assert knowledge.INDEX not in [p.name for p in knowledge.concepts(store_of(shop))]


# --- the diff --------------------------------------------------------------- #


def test_no_output_is_current_and_any_output_is_changed_with_the_right_sums(monkeypatch):
    shop = ACME / "shop"
    store = store_of(shop)

    canned(monkeypatch, {"diff": (0, "")})
    concept = knowledge.load(store / "shop.md", store, shop)
    assert knowledge.changed(concept) == knowledge.Diff("current")

    canned(monkeypatch, {"diff": (0, NUMSTAT)})
    concept = knowledge.load(store / "api" / "api.md", store, shop)
    diff = knowledge.changed(concept)
    assert (diff.state, diff.files, diff.insertions, diff.deletions) == (
        "changed", 3, 41, 12,
    )
    assert diff.first == "api/orders.py"
    assert diff.summary() == "3 files · +41 −12"


def test_an_untracked_path_alone_turns_current_into_changed_and_names_it(monkeypatch):
    shop = ACME / "shop"
    store = store_of(shop)
    canned(monkeypatch, {"diff": (0, ""), "ls-files": (0, "api/new.py\n")})
    concept = knowledge.load(store / "api" / "api.md", store, shop)
    diff = knowledge.changed(concept)
    assert (diff.state, diff.files, diff.insertions, diff.deletions) == (
        "changed", 1, 0, 0,
    )
    assert diff.first == "api/new.py"
    assert diff.summary() == "1 file · +0 −0"


def test_untracked_paths_beside_a_numstat_add_to_the_file_count_only(monkeypatch):
    shop = ACME / "shop"
    store = store_of(shop)
    canned(monkeypatch, {"diff": (0, NUMSTAT), "ls-files": (0, "api/new.py\n")})
    concept = knowledge.load(store / "api" / "api.md", store, shop)
    diff = knowledge.changed(concept)
    assert (diff.state, diff.files, diff.insertions, diff.deletions) == (
        "changed", 4, 41, 12,
    )
    # The numstat already found a first file; the untracked one only pads the count.
    assert diff.first == "api/orders.py"


def test_an_ignored_untracked_path_never_reaches_the_count(monkeypatch):
    """--exclude-standard is what keeps a gitignored store from counting itself —
    git filters it out before this module ever sees a line for it."""
    shop = ACME / "shop"
    store = store_of(shop)
    calls = canned(monkeypatch, {"diff": (0, ""), "ls-files": (0, "")})
    concept = knowledge.load(store / "api" / "api.md", store, shop)
    assert knowledge.changed(concept) == knowledge.Diff("current")
    ls_files_args = next(args for args, _ in calls if "ls-files" in args)
    assert "--exclude-standard" in ls_files_args


def test_a_failed_ls_files_call_leaves_the_numstat_s_answer_standing(monkeypatch):
    shop = ACME / "shop"
    store = store_of(shop)
    canned(
        monkeypatch,
        {"diff": (0, NUMSTAT), "ls-files": (128, "fatal: not a git repository")},
    )
    concept = knowledge.load(store / "api" / "api.md", store, shop)
    diff = knowledge.changed(concept)
    assert (diff.state, diff.files, diff.insertions, diff.deletions) == (
        "changed", 3, 41, 12,
    )


def test_the_diff_runs_against_the_mirrored_path_in_the_file_s_own_repo(monkeypatch):
    shop = ACME / "shop"
    store = store_of(shop)
    calls = canned(monkeypatch, {"diff": (0, "")})

    knowledge.changed(knowledge.load(store / "api" / "api.md", store, shop))
    args, cwd = calls[0]
    # No HEAD: the revision is compared against the working tree, so an
    # uncommitted edit under api/ counts.
    assert args == ["diff", "--numstat", "--end-of-options", "8be0117", "--", "api"]
    assert cwd == shop

    knowledge.changed(knowledge.load(store / "shop.md", store, shop))
    diffs = [args for args, _ in calls if "diff" in args]
    assert diffs[1][-1] == "."


def test_a_diff_that_cannot_run_is_unverifiable_and_never_a_failure(monkeypatch):
    shop = ACME / "shop"
    store = store_of(shop)
    canned(monkeypatch, {"diff": (128, "")})
    concept = knowledge.load(store / "shop.md", store, shop)
    assert knowledge.changed(concept).state == "unverifiable"


def test_an_unstamped_file_is_never_diffed(monkeypatch):
    worker = ACME / "worker"
    store = store_of(worker)
    calls = canned(monkeypatch, {"diff": (0, NUMSTAT)})
    assert knowledge.changed(knowledge.load(store / "worker.md", store, worker)).state == (
        "unstamped"
    )
    assert calls == []


def test_system_md_is_checked_once_per_member_in_that_member_s_own_directory(monkeypatch):
    store = store_of(ACME)
    calls = canned(monkeypatch, {"diff": (0, "")})
    concept = knowledge.load(store / "system.md", store, ACME)

    per_member = knowledge.changed_system(concept, members_of(ACME))
    assert {name: d.state for name, d in per_member.items()} == {
        "shop": "current", "worker": "current",
    }
    diffs = [(args, cwd) for args, cwd in calls if "diff" in args]
    assert [cwd for _, cwd in diffs] == [ACME / "shop", ACME / "worker"]
    assert diffs[0][0][3] == "1f4ac02"
    assert diffs[1][0][3] == "3c81d90"
    assert knowledge.system_state(per_member) == "current"


def test_a_declared_member_with_no_revision_key_is_unstamped_for_that_member(monkeypatch):
    store = store_of(ACME)
    canned(monkeypatch, {"diff": (0, "")})
    concept = knowledge.load(store / "system.md", store, ACME)
    members = {**members_of(ACME), "billing": ACME / "billing"}

    per_member = knowledge.changed_system(concept, members)
    assert per_member["billing"].state == "unstamped"
    assert knowledge.system_state(per_member) == "unstamped"


def test_a_revision_key_naming_no_declared_member_is_reported_and_left_alone():
    store = store_of(ACME)
    concept = knowledge.load(store / "system.md", store, ACME)
    assert knowledge.undeclared_members(concept, members_of(ACME)) == []
    assert knowledge.undeclared_members(concept, {"shop": ACME / "shop"}) == ["worker"]


# --- stamping --------------------------------------------------------------- #


def test_stamp_rewrites_revision_and_leaves_every_other_byte_alone(acme, monkeypatch):
    shop = acme / "shop"
    store = store_of(shop)
    path = store / "shop.md"
    before = path.read_text()
    canned(monkeypatch, {"rev-parse": (0, "abc1234\n")})

    assert knowledge.stamp([path], store, shop, {}) == [(path, "")]
    after = path.read_text()
    assert after == before.replace('revision = "1f4ac02"', 'revision = "abc1234"')


def test_stamp_inserts_a_missing_revision_above_the_first_table(acme, monkeypatch):
    """`[[connects]]` is the common shape, and a revision appended at the very
    end of the block would land inside that table and parse as a different key."""
    worker = acme / "worker"
    store = store_of(worker)
    path = store / "worker.md"
    canned(monkeypatch, {"rev-parse": (0, "3c81d90\n")})

    knowledge.stamp([path], store, worker, {})
    concept = knowledge.load(path, store, worker)
    assert concept.revision == "3c81d90"
    assert concept.problems == []
    assert concept.connects == [{"to": "shop", "how": "http", "carries": "OrderStatus"}]


def test_stamp_refuses_a_file_with_no_parseable_block_and_names_the_path(tmp_path):
    root = tmp_path / "repo"
    store = store_of(root)
    store.mkdir(parents=True)
    plain = store / "repo.md"
    plain.write_text("# no frontmatter here\n")
    with pytest.raises(knowledge.Refused, match="no \\+\\+\\+ frontmatter"):
        knowledge.stamp([plain], store, root, {})

    broken = store / "broken.md"
    broken.write_text("+++\nnot = = toml\n+++\nbody\n")
    with pytest.raises(knowledge.Refused, match="does not parse"):
        knowledge.stamp([broken], store, root, {})


def test_a_stamp_whose_rev_parse_fails_changes_nothing_and_names_the_path(
    acme, monkeypatch
):
    shop = acme / "shop"
    store = store_of(shop)
    path = store / "shop.md"
    before = path.read_text()
    canned(monkeypatch, {"rev-parse": (128, "")})

    with pytest.raises(knowledge.Refused, match="rev-parse"):
        knowledge.stamp([path], store, shop, {})
    assert path.read_text() == before


def test_stamping_system_md_re_stamps_every_member_and_keeps_an_undeclared_key(
    acme, monkeypatch
):
    store = store_of(acme)
    path = store / "system.md"
    heads = {str(acme / "shop"): "aaa1111", str(acme / "worker"): "bbb2222"}

    def fake(args, cwd):
        if args[0] == "rev-parse":
            return 0, heads[str(cwd)] + "\n"
        return 0, ""

    monkeypatch.setattr(knowledge, "git", fake)
    path.write_text(
        path.read_text().replace(
            'revision = { shop = "1f4ac02", worker = "3c81d90" }',
            'revision = { shop = "1f4ac02", billing = "old0000", worker = "3c81d90" }',
        )
    )

    knowledge.stamp([path], store, acme, members_of(acme))
    concept = knowledge.load(path, store, acme)
    # Order preserved, the two declared members re-stamped, the third untouched.
    assert concept.revision == {
        "shop": "aaa1111", "billing": "old0000", "worker": "bbb2222",
    }


def test_a_declared_member_missing_from_the_table_is_added_by_stamp(acme, monkeypatch):
    store = store_of(acme)
    path = store / "system.md"
    path.write_text(
        path.read_text().replace(
            'revision = { shop = "1f4ac02", worker = "3c81d90" }',
            'revision = { shop = "1f4ac02" }',
        )
    )

    def fake(args, cwd):
        return (0, "new0000\n") if args[0] == "rev-parse" else (0, "")

    monkeypatch.setattr(knowledge, "git", fake)
    knowledge.stamp([path], store, acme, members_of(acme))
    assert knowledge.load(path, store, acme).revision == {
        "shop": "new0000", "worker": "new0000",
    }


# --- orphans and the generated listing --------------------------------------- #


def test_a_renamed_directory_yields_one_orphan_per_file(acme):
    shop = acme / "shop"
    assert knowledge.orphans(store_of(shop), shop) == []

    (shop / "api").rename(shop / "http")
    missing = knowledge.orphans(store_of(shop), shop)
    assert [p.name for p, _ in missing] == ["api.md"]
    assert missing[0][1] == shop / "api"


def test_a_listing_that_cannot_be_read_is_overwritten_rather_than_fatal(acme):
    """The comparison read sat outside every guard, so one non-UTF-8 index.md
    tracebacked out of the walk and no listing in any store was rewritten. The
    contract says nothing may trust an index.md, so a corrupt one is replaced."""
    shop = acme / "shop"
    store = store_of(shop)
    listing = store / "index.md"
    listing.write_bytes(b"# Index\n\n\xff\xfe not utf-8\n")

    assert listing in knowledge.reindex(store, shop)
    assert "not utf-8" not in listing.read_text(encoding="utf-8")


def test_the_toy_s_index_is_exactly_what_reindex_writes_and_a_second_run_is_a_no_op(acme):
    shop = acme / "shop"
    store = store_of(shop)
    before = (store / "index.md").read_text()

    written = knowledge.reindex(store, shop)
    # The shipped listing is already right, so only the one it does not have moves.
    assert written == [store / "api" / "index.md"]
    assert (store / "index.md").read_text() == before
    assert knowledge.reindex(store, shop) == []


def test_a_listing_names_each_concept_and_each_subdirectory_with_its_description(acme):
    shop = acme / "shop"
    listing = (store_of(shop) / "index.md").read_text()
    assert (
        "- [shop.md](shop.md) — Serves the storefront and the order API. "
        "Writes each order to the fulfilment queue." in listing
    )
    assert (
        "- [api/](api/) — The order API. OrderStatus is a string enum that "
        "crosses to the worker unchanged." in listing
    )


def test_a_subdirectory_with_no_concept_file_is_listed_by_name_alone(acme):
    shop = acme / "shop"
    store = store_of(shop)
    (store / "ui").mkdir()
    knowledge.reindex(store, shop)
    assert "- [ui/](ui/)\n" in (store / "index.md").read_text()


def test_a_file_with_a_problem_other_than_unstamped_is_left_out_of_the_listing(acme):
    shop = acme / "shop"
    store = store_of(shop)
    (store / "ui").mkdir()
    (store / "ui" / "ui.md").write_text("+++\ndescription = 'no type here'\n+++\n")
    knowledge.reindex(store, shop)

    root_listing = (store / "index.md").read_text()
    assert "- [ui/](ui/)\n" in root_listing
    assert "no type here" not in root_listing
    assert "ui.md" not in (store / "ui" / "index.md").read_text()


def test_an_unstamped_file_is_still_listed(acme):
    worker = acme / "worker"
    store = store_of(worker)
    knowledge.reindex(store, worker)
    assert "- [worker.md](worker.md) — Drains the fulfilment queue" in (
        store / "index.md"
    ).read_text()


# --- the fold ---------------------------------------------------------------- #


def stores_of(parent: Path) -> list[tuple[Path, Path]]:
    return [(path, store_of(path)) for path in members_of(parent).values()]


def test_a_target_no_file_describes_is_counted_and_never_hidden(acme):
    """A seam nobody wrote up is exactly what a reader wants to be told about."""
    worker = acme / "worker"
    path = store_of(worker) / "worker.md"
    path.write_text(
        path.read_text().replace(
            '[[connects]]\nto = "shop"',
            '[[connects]]\nto = "billing"\nhow = "http"\ncarries = "Invoice"\n\n'
            '[[connects]]\nto = "shop"',
        )
    )

    edges, described, carriers = knowledge.fold(stores_of(acme))
    rendered = knowledge.render_map("acme", edges, described, carriers)
    assert "worker      ──http──▶    billing" in rendered
    assert "4 edges · 4 nodes · 1 undescribed" in rendered


def test_a_node_no_file_names_or_reaches_is_an_error():
    edges, described, _ = knowledge.fold(stores_of(ACME))
    knowledge.require_node(edges, described, "shop/api")
    with pytest.raises(knowledge.Refused, match="no knowledge file names"):
        knowledge.require_node(edges, described, "billing")


def test_the_fold_reads_one_store_as_readily_as_a_system():
    shop = ACME / "shop"
    edges, described, carriers = knowledge.fold([(shop, store_of(shop))])
    assert [(e.source, e.to) for e in edges] == [("shop", "worker"), ("shop/api", "worker")]
    assert described == {"shop", "shop/api"}
    assert carriers == 2


def test_mermaid_and_dot_carry_the_same_edges_as_the_text():
    edges, _, _ = knowledge.fold(stores_of(ACME))
    mermaid = knowledge.render_mermaid(edges)
    assert "graph LR" in mermaid
    assert 'nshop_api["shop/api"]' in mermaid
    assert "nshop -->|queue| nworker" in mermaid

    dot = knowledge.render_dot(edges)
    assert dot.startswith("digraph knowledge {")
    assert '"shop/api" -> "worker" [label="queue"];' in dot


# --- the two commands --------------------------------------------------------- #


def run(argv: list[str]) -> int:
    """Through the parser, so the tests exercise the surface the contract declares."""
    args = flw.build_parser().parse_args(argv)
    return args.handler(args)


def test_orientation_from_the_parent_is_the_plan_s_sample(capsys, monkeypatch):
    canned(monkeypatch, {"diff": (0, "")})
    assert run(["know", "--root", str(ACME)]) == 0
    where = flw.tilde(store_of(ACME) / "system.md")
    assert capsys.readouterr().out == (
        f"system: acme · 2 roots · {where}\n"
        "  One shop, one worker. The shop takes orders over HTTP; the worker\n"
        "  fulfils them from a queue the shop writes.\n"
        "\n"
        "  shop      Serves the storefront and the order API. Writes each order\n"
        "            to the fulfilment queue.\n"
        "            → worker (queue, Order)\n"
        "  worker    Drains the fulfilment queue and marks orders shipped\n"
        "            through the shop's API.\n"
        "            → shop (http, OrderStatus)\n"
        "\n"
        "2 repo files, each in its own repo's store · 0 changed\n"
    )


def test_the_walk_from_a_member_is_the_plan_s_sample(capsys, monkeypatch):
    canned(monkeypatch, {"ls-files": (0, ""), "-- api": (0, NUMSTAT), "diff": (0, "")})
    assert run(["know", "api/orders.py", "--root", str(ACME / "shop")]) == 0
    assert capsys.readouterr().out == (
        "shop · api/orders.py · 2 of 3 levels have knowledge\n"
        "\n"
        "  shop.md                    repo   1f4ac02   current\n"
        "    Serves the storefront and the order API. Writes each order to the\n"
        "    fulfilment queue.\n"
        "    → worker (queue, Order)\n"
        "\n"
        "  api/api.md                 area   8be0117   changed since 8be0117: "
        "3 files · +41 −12 · e.g. api/orders.py\n"
        "    The order API. OrderStatus is a string enum that crosses to the\n"
        "    worker unchanged.\n"
        "    → worker (queue, Order)\n"
        "\n"
        "2 files · 1 changed · --full for bodies\n"
    )


def test_check_from_the_parent_is_the_plan_s_sample(capsys, monkeypatch):
    canned(monkeypatch, {"ls-files": (0, ""), "-- api": (0, NUMSTAT), "diff": (0, "")})
    assert run(["know", "--check", "--root", str(ACME)]) == 0
    assert capsys.readouterr().out == (
        "knowledge: 3 roots, one store each · 4 files\n"
        "\n"
        "  acme      system.md                  current     "
        "shop 1f4ac02 · worker 3c81d90\n"
        "  shop      shop.md                    current\n"
        "  shop      api/api.md                 changed     "
        "3 files · +41 −12 · since 8be0117\n"
        "  worker    worker.md                  unstamped\n"
        "\n"
        "4 files · 1 changed · 1 unstamped · 2 current · 0 orphans\n"
    )


def test_map_and_a_node_are_the_plan_s_samples(capsys, monkeypatch):
    canned(monkeypatch, {"diff": (0, "")})
    assert run(["map", "--root", str(ACME)]) == 0
    assert capsys.readouterr().out == (
        "acme · folded from 3 concept files\n"
        "\n"
        "  shop        ──queue──▶   worker\n"
        "  shop/api    ──queue──▶   worker\n"
        "  worker      ──http──▶    shop\n"
        "\n"
        "3 edges · 3 nodes\n"
    )

    assert run(["map", "worker", "--root", str(ACME)]) == 0
    assert capsys.readouterr().out == (
        "\n"
        "  in    shop      ──queue──▶  worker\n"
        "        shop/api  ──queue──▶  worker\n"
        "  out   worker    ──http──▶   shop\n"
        "\n"
        "changing worker's inbound contract touches: shop, shop/api\n"
    )


# --- each resolution row ------------------------------------------------------ #


def test_a_member_standing_inside_itself_sees_its_own_file_alone(capsys, monkeypatch):
    """No reverse lookup: the system is seen by naming its root, never by
    walking upward from a member looking for a parent that claims it."""
    canned(monkeypatch, {"diff": (0, "")})
    assert run(["know", "--root", str(ACME / "shop")]) == 0
    out = capsys.readouterr().out
    assert out.startswith("repo: shop · ")
    assert "worker" not in out.splitlines()[0]
    assert out.endswith("1 repo file · 0 changed\n")


def test_from_a_parent_a_path_under_a_member_ends_at_system_md(capsys, monkeypatch):
    canned(monkeypatch, {"diff": (0, "")})
    assert run(["know", "api/orders.py", "--root", str(ACME)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("shop · api/orders.py · 3 of 4 levels have knowledge")
    listed = [line.split()[0] for line in out.splitlines() if line.startswith("  ")]
    assert [name for name in listed if name.endswith(".md")] == [
        "system.md", "shop.md", "api/api.md",
    ]


def test_from_a_parent_a_path_under_no_member_is_refused(capsys, tmp_path, monkeypatch):
    canned(monkeypatch, {"diff": (0, "")})
    (tmp_path / "elsewhere.py").write_text("x = 1\n")
    assert run(["know", str(tmp_path / "elsewhere.py"), "--root", str(ACME)]) == 1
    assert "under no repository acme declares" in capsys.readouterr().err


def test_check_and_reindex_from_a_parent_cover_every_member_s_store(
    acme, capsys, monkeypatch
):
    canned(monkeypatch, {"diff": (0, "")})
    assert run(["know", "--check", "--root", str(acme)]) == 0
    assert [line.split()[0] for line in capsys.readouterr().out.splitlines()
            if line.startswith("  ")] == ["acme", "shop", "shop", "worker"]

    assert run(["know", "--reindex", "--root", str(acme)]) == 0
    out = capsys.readouterr().out
    # The shop's own listing ships correct, so only the three it does not have move.
    assert "3 listings rewritten" in out
    for expected in (
        "acme/.flw/knowledge/index.md",
        "shop/.flw/knowledge/api/index.md",
        "worker/.flw/knowledge/index.md",
    ):
        assert expected in out


# --- what it refuses, and what it does not ------------------------------------ #


def test_a_root_with_no_store_says_so_and_exits_0(tmp_path, capsys, monkeypatch):
    """A missing [knowledge] key and a missing directory read the same. Three
    skills run this on every run, and every repository has no store until
    research writes one."""
    monkeypatch.setenv("HOME", str(tmp_path))
    root = tmp_path / "work"
    (root / ".flw").mkdir(parents=True)

    assert run(["know", "--root", str(root)]) == 0
    assert capsys.readouterr().out == "no store\n"

    (root / ".flw" / "config.toml").write_text('[knowledge]\ndir = ".flw/gone"\n')
    assert run(["know", "--root", str(root)]) == 0
    assert capsys.readouterr().out == "no store\n"

    assert run(["map", "--root", str(root)]) == 0
    assert capsys.readouterr().out == "no store\n"


def test_the_knowledge_dir_is_read_from_the_project_file_and_never_the_machine_s(
    tmp_path, capsys, monkeypatch
):
    """The same exception [project.roots] takes: where one repository keeps its
    architecture is a fact about that repository, not about the machine."""
    monkeypatch.setenv("HOME", str(tmp_path))
    home = tmp_path / "flw-home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("FLW_HOME", str(home))
    (home / "config.toml").write_text('[knowledge]\ndir = "docs/arch"\n')

    root = tmp_path / "work"
    (root / ".flw" / "knowledge").mkdir(parents=True)
    (root / "docs" / "arch").mkdir(parents=True)

    assert flw.knowledge_dir(root) == root / ".flw" / "knowledge"
    assert run(["know", "--root", str(root)]) == 0
    assert capsys.readouterr().out.startswith("repo: work · (work.md not written)")


def test_no_root_is_the_one_thing_orientation_refuses(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    empty = tmp_path / "nothing"
    empty.mkdir()
    assert run(["know", "--root", str(empty)]) == 1
    assert "no specs/" in capsys.readouterr().err
    assert run(["map", "--root", str(empty)]) == 1
    assert "no specs/" in capsys.readouterr().err


def test_full_and_stamp_with_no_path_are_refused(capsys, monkeypatch):
    canned(monkeypatch, {"diff": (0, "")})
    assert run(["know", "--full", "--root", str(ACME)]) == 1
    assert "give it a path to walk from" in capsys.readouterr().err

    assert run(["know", "--stamp", "--root", str(ACME)]) == 1
    assert "was given none" in capsys.readouterr().err


def test_a_path_not_in_the_code_is_refused(capsys, monkeypatch):
    canned(monkeypatch, {"diff": (0, "")})
    assert run(["know", "api/nothing.py", "--root", str(ACME / "shop")]) == 1
    assert "not in the code" in capsys.readouterr().err


def test_a_stamp_whose_repo_has_no_head_changes_nothing_and_exits_1(
    acme, capsys, monkeypatch
):
    path = store_of(acme / "shop") / "shop.md"
    before = path.read_text()
    canned(monkeypatch, {"rev-parse": (128, "")})

    assert run(["know", "--stamp", str(path), "--root", str(acme)]) == 1
    assert "rev-parse" in capsys.readouterr().err
    assert path.read_text() == before


def test_stamp_from_a_parent_reaches_a_file_in_any_member_s_store(
    acme, capsys, monkeypatch
):
    canned(monkeypatch, {"rev-parse": (0, "ff00aa1\n")})
    path = store_of(acme / "worker") / "worker.md"
    assert run(["know", "--stamp", str(path), "--root", str(acme)]) == 0
    assert "1 file stamped" in capsys.readouterr().out
    assert knowledge.load(path, store_of(acme / "worker"), acme / "worker").revision == (
        "ff00aa1"
    )


def test_a_file_in_no_store_cannot_be_stamped(acme, capsys, monkeypatch):
    canned(monkeypatch, {"rev-parse": (0, "ff00aa1\n")})
    assert run(["know", "--stamp", str(acme / "worker" / "drain.py"),
                "--root", str(acme)]) == 1
    assert "is in no store" in capsys.readouterr().err


def test_the_map_orders_edges_by_name_and_not_by_declaration(acme, capsys, monkeypatch):
    """`[project.roots]` is a table a person writes in whatever order suits them,
    and the map is a document read top to bottom. `edges.sort` is what makes the
    two independent, and a fixture declaring shop first cannot show it."""
    (acme / ".flw" / "config.toml").write_text(
        '[project.roots]\nworker = "./worker"\nshop   = "./shop"\n'
    )
    canned(monkeypatch, {"diff": (0, "")})

    assert run(["map", "--root", str(acme)]) == 0
    assert capsys.readouterr().out == (
        "acme · folded from 3 concept files\n"
        "\n"
        "  shop        ──queue──▶   worker\n"
        "  shop/api    ──queue──▶   worker\n"
        "  worker      ──http──▶    shop\n"
        "\n"
        "3 edges · 3 nodes\n"
    )


def test_a_node_no_file_names_exits_1(capsys, monkeypatch):
    canned(monkeypatch, {"diff": (0, "")})
    assert run(["map", "billing", "--root", str(ACME)]) == 1
    assert "no knowledge file names" in capsys.readouterr().err


def test_check_exits_0_even_when_everything_is_changed(acme, capsys, monkeypatch):
    canned(monkeypatch, {"diff": (0, NUMSTAT)})
    assert run(["know", "--check", "--root", str(acme)]) == 0
    assert "3 changed" in capsys.readouterr().out


def test_check_names_a_revision_key_that_no_declared_member_matches(
    acme, capsys, monkeypatch
):
    canned(monkeypatch, {"diff": (0, "")})
    path = store_of(acme) / "system.md"
    path.write_text(path.read_text().replace(' }', ', billing = "old0000" }'))

    assert run(["know", "--check", "--root", str(acme)]) == 0
    assert "carries 'billing', which [project.roots] does not declare" in (
        capsys.readouterr().out
    )


def test_full_prints_the_body_the_head_alone_does_not(capsys, monkeypatch):
    canned(monkeypatch, {"diff": (0, "")})
    assert run(["know", "api/orders.py", "--full", "--root", str(ACME / "shop")]) == 0
    out = capsys.readouterr().out
    assert "`OrderStatus` is a string enum" in out
    assert "--full for bodies" not in out


def test_an_orphan_is_reported_with_the_path_it_expected(acme, capsys, monkeypatch):
    canned(monkeypatch, {"diff": (0, "")})
    (acme / "shop" / "api").rename(acme / "shop" / "http")

    assert run(["know", "--check", "--root", str(acme)]) == 0
    out = capsys.readouterr().out
    assert "api/api.md                 orphan      expected api" in out
    assert "1 orphans" in out


def test_the_other_formats_are_reachable_from_the_command(capsys, monkeypatch):
    canned(monkeypatch, {"diff": (0, "")})
    assert run(["map", "--format", "mermaid", "--root", str(ACME)]) == 0
    assert "graph LR" in capsys.readouterr().out

    assert run(["map", "worker", "--format", "dot", "--root", str(ACME)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("digraph knowledge {")
    # The NODE filter reaches every format, not only the text one.
    assert '"shop/api" -> "worker"' in out
    assert '"shop" -> "worker"' in out


# --- what a stamp may and may not do ------------------------------------------ #


def test_a_stamp_on_a_dirty_mirror_is_written_and_says_which_path(
    acme, capsys, monkeypatch
):
    """Refusing would stop research on any checkout with local changes, which is
    most of them. The stamp is written and the line says what it is wrong by."""
    shop = acme / "shop"
    canned(monkeypatch, {"rev-parse": (0, "abc1234\n"),
                         "status": (0, " M api/orders.py\n")})
    path = store_of(shop) / "api" / "api.md"

    assert run(["know", "--stamp", str(path), "--root", str(acme)]) == 0
    assert (
        "api has uncommitted changes; recorded HEAD, re-stamp once they are "
        "committed"
    ) in capsys.readouterr().out
    assert knowledge.load(path, store_of(shop), shop).revision == "abc1234"


def test_a_dirty_repository_file_names_the_repository_and_not_a_dot(
    acme, capsys, monkeypatch
):
    """The Area case above mirrors `api/`, where `rel == Path(".")` is
    unreachable. A repository file mirrors the whole tree, so this is the case
    `_dirty_subject`'s `rel == Path(".")` branch actually exists for."""
    shop = acme / "shop"
    canned(monkeypatch, {"rev-parse": (0, "abc1234\n"),
                         "status": (0, " M api/orders.py\n")})
    path = store_of(shop) / "shop.md"

    assert run(["know", "--stamp", str(path), "--root", str(acme)]) == 0
    out = capsys.readouterr().out
    assert "shop has uncommitted changes" in out
    assert ". has uncommitted changes" not in out


def test_a_stamp_on_a_clean_mirror_carries_no_warning(acme, capsys, monkeypatch):
    canned(monkeypatch, {"rev-parse": (0, "abc1234\n"), "status": (0, "")})
    path = store_of(acme / "shop") / "shop.md"

    assert run(["know", "--stamp", str(path), "--root", str(acme)]) == 0
    assert "uncommitted" not in capsys.readouterr().out


def test_a_system_stamp_names_only_the_member_whose_tree_is_dirty(
    acme, capsys, monkeypatch
):
    def fake(args: list[str], cwd: Path) -> tuple[int, str]:
        joined = " ".join(args)
        if "rev-parse" in joined:
            return 0, "abc1234\n"
        if "status" in joined:
            return (0, " M drain.py\n") if cwd.name == "worker" else (0, "")
        return 0, ""

    monkeypatch.setattr(knowledge, "git", fake)
    path = store_of(acme) / "system.md"

    assert run(["know", "--stamp", str(path), "--root", str(acme)]) == 0
    out = capsys.readouterr().out
    assert "worker has uncommitted changes" in out
    assert "shop has uncommitted" not in out


def test_a_batch_resolves_every_head_before_it_writes_anything(
    acme, capsys, monkeypatch
):
    """`nothing was written` was true of one file and false of every file before
    it — and from a parent, system.md needs every member's HEAD."""
    shop, worker = acme / "shop", acme / "worker"

    def fake(args: list[str], cwd: Path) -> tuple[int, str]:
        if "rev-parse" in " ".join(args):
            if cwd == worker:
                return 128, "fatal: ambiguous argument 'HEAD'\n"
            return 0, "abc1234\n"
        return 0, ""

    monkeypatch.setattr(knowledge, "git", fake)
    first = store_of(shop) / "shop.md"
    second = store_of(worker) / "worker.md"
    before = (first.read_text(), second.read_text())

    assert run(["know", "--stamp", str(first), str(second), "--root", str(acme)]) == 1
    err = capsys.readouterr().err
    assert str(worker) in err
    assert "ambiguous argument" in err
    assert "nothing was written" in err
    assert (first.read_text(), second.read_text()) == before


def test_a_refusal_quotes_what_git_said_rather_than_replacing_it(acme, monkeypatch):
    """git absent from PATH is an OSError, and the reader needs its text: the bare
    `rev-parse failed` sent them looking for a HEAD the repository does have."""
    def fake(args: list[str], cwd: Path) -> tuple[int, str]:
        return 127, "[Errno 2] No such file or directory: 'git'"

    monkeypatch.setattr(knowledge, "git", fake)
    shop = acme / "shop"
    with pytest.raises(knowledge.Refused) as raised:
        knowledge.stamp([store_of(shop) / "shop.md"], store_of(shop), shop, {})
    assert "No such file or directory: 'git'" in str(raised.value)


@pytest.mark.parametrize(
    ("spelling", "block"),
    [
        ("a [revision] section", '[revision]\nshop = "old0000"\n'),
        ("a revision inside [[connects]]",
         '[[connects]]\nto = "worker"\nrevision = "old0000"\n'),
    ],
)
def test_a_spelling_the_rewrite_cannot_reach_is_refused_and_nothing_written(
    tmp_path, monkeypatch, spelling, block
):
    """Each of these parsed before the rewrite and said something else after, and
    each was reported as `1 file stamped`."""
    root = tmp_path / "repo"
    store = store_of(root)
    store.mkdir(parents=True)
    path = store / "repo.md"
    text = f'+++\ntype = "Repository"\ndescription = "x"\n{block}+++\nbody\n'
    path.write_text(text)
    canned(monkeypatch, {"rev-parse": (0, "abc1234\n")})

    with pytest.raises(knowledge.Refused):
        knowledge.stamp([path], store, root, {})
    assert path.read_text() == text, spelling


def test_an_indented_revision_key_is_stamped_in_place_and_keeps_its_indentation(
    tmp_path, monkeypatch
):
    """An indented `revision = "…"` used to parse, then read back as a duplicate
    key after the rewrite inserted an unindented one — refused with a message
    that sent the reader looking for a break the block never had. It is
    admitted outright now, at the indentation the author gave it."""
    root = tmp_path / "repo"
    store = store_of(root)
    store.mkdir(parents=True)
    path = store / "repo.md"
    text = (
        '+++\ntype = "Repository"\ndescription = "x"\n'
        '  revision = "old0000"\n+++\nbody\n'
    )
    path.write_text(text)
    canned(monkeypatch, {"rev-parse": (0, "abc1234\n"), "status": (0, "")})

    knowledge.stamp([path], store, root, {})
    assert '  revision = "abc1234"\n' in path.read_text()


def test_a_stamp_keeps_a_trailing_comment_and_crlf_line_endings(
    tmp_path, monkeypatch
):
    """Both were promised by the docstring and neither survived: `.*$` swallowed
    the comment, and the write translated the endings."""
    root = tmp_path / "repo"
    store = store_of(root)
    store.mkdir(parents=True)
    path = store / "repo.md"
    text = (
        '+++\r\ntype = "Repository"\r\ndescription = "x"\r\n'
        'revision = "old0000"  # stamped by hand\r\n+++\r\nbody\r\n'
    )
    path.write_bytes(text.encode())
    canned(monkeypatch, {"rev-parse": (0, "abc1234\n"), "status": (0, "")})

    knowledge.stamp([path], store, root, {})
    after = path.read_bytes().decode()
    assert after == text.replace("old0000", "abc1234")


# --- names the CLI accepts ---------------------------------------------------- #


def test_reindex_writes_no_listing_into_a_dot_directory(acme, capsys, monkeypatch):
    """A `[knowledge] dir` of `.` makes the repository the store, and the walk
    would otherwise write index.md into .git/."""
    canned(monkeypatch, {"diff": (0, "")})
    hidden = store_of(acme / "shop") / ".git"
    hidden.mkdir()

    assert run(["know", "--reindex", "--root", str(acme)]) == 0
    assert not (hidden / "index.md").exists()
    assert (store_of(acme / "shop") / "index.md").is_file()


def test_a_knowledge_dir_that_is_absolute_is_refused_naming_file_and_key(
    tmp_path, monkeypatch
):
    root = tmp_path / "repo"
    (root / ".flw").mkdir(parents=True)
    config = root / ".flw" / "config.toml"
    config.write_text(f'[knowledge]\ndir = "{tmp_path / "elsewhere"}"\n')

    with pytest.raises(SystemExit) as raised:
        flw.knowledge_dir(root)
    assert str(config) in str(raised.value)
    assert "[knowledge] dir" in str(raised.value)


def test_a_knowledge_dir_of_dot_is_refused_naming_file_and_key(tmp_path):
    """`.` would put a generated index.md into every directory of the source
    tree on --reindex, spared only by the dot-directory skip that also spares
    `.git/` — the refusal is what should have stopped it."""
    root = tmp_path / "repo"
    (root / ".flw").mkdir(parents=True)
    config = root / ".flw" / "config.toml"
    config.write_text('[knowledge]\ndir = "."\n')

    with pytest.raises(SystemExit) as raised:
        flw.knowledge_dir(root)
    assert str(config) in str(raised.value)
    assert "[knowledge] dir" in str(raised.value)


def test_a_knowledge_dir_that_leaves_the_root_is_refused_naming_file_and_key(
    tmp_path,
):
    root = tmp_path / "repo"
    (root / ".flw").mkdir(parents=True)
    config = root / ".flw" / "config.toml"
    config.write_text('[knowledge]\ndir = "../outside"\n')

    with pytest.raises(SystemExit) as raised:
        flw.knowledge_dir(root)
    assert str(config) in str(raised.value)
    assert "[knowledge] dir" in str(raised.value)


def test_a_knowledge_dir_nested_under_the_root_is_still_accepted(tmp_path):
    root = tmp_path / "repo"
    (root / ".flw").mkdir(parents=True)
    config = root / ".flw" / "config.toml"
    config.write_text('[knowledge]\ndir = "docs/arch"\n')

    assert flw.knowledge_dir(root) == root / "docs" / "arch"


# --- what the walk answers from a parent -------------------------------------- #


def test_a_dot_from_the_parent_is_the_orientation(acme, capsys, monkeypatch):
    canned(monkeypatch, {"diff": (0, "")})
    monkeypatch.chdir(acme)

    assert run(["know", "."]) == 0
    assert capsys.readouterr().out.startswith("system: acme · 2 roots")


def test_a_path_under_no_member_is_refused_rather_than_read_as_the_first(
    acme, capsys, monkeypatch
):
    """`flw know .flw` from the parent answered with `shop`: the cwd form existed,
    and the member-relative form was tried anyway."""
    canned(monkeypatch, {"diff": (0, "")})
    monkeypatch.chdir(acme)

    assert run(["know", ".flw"]) == 1
    assert "is under no repository acme declares" in capsys.readouterr().err


def test_a_path_more_than_one_member_holds_is_refused_naming_them(
    acme, capsys, monkeypatch
):
    canned(monkeypatch, {"diff": (0, "")})
    for member in ("shop", "worker"):
        (acme / member / "README.md").write_text("# read me\n")
    monkeypatch.chdir(acme.parent)

    assert run(["know", "README.md", "--root", str(acme)]) == 1
    err = capsys.readouterr().err
    assert "under more than one repository acme declares: shop, worker" in err


def test_a_member_relative_path_still_answers_from_the_parent(
    acme, capsys, monkeypatch
):
    canned(monkeypatch, {"-- api": (0, NUMSTAT), "diff": (0, "")})
    monkeypatch.chdir(acme)

    assert run(["know", "api/orders.py"]) == 0
    assert capsys.readouterr().out.startswith("shop · api/orders.py ·")


def test_a_path_beside_a_whole_store_mode_is_refused_rather_than_dropped(
    acme, capsys, monkeypatch
):
    """`flw know nonexistent/path --check` exited 0 for a path that alone is 1."""
    canned(monkeypatch, {"diff": (0, "")})

    assert run(["know", "nonexistent/path", "--check", "--root", str(acme)]) == 1
    assert "--check reads the whole store" in capsys.readouterr().err

    assert run(["know", "--full", "--reindex", "--root", str(acme)]) == 1
    assert "--reindex reads the whole store" in capsys.readouterr().err


# --- three listings that said less than they knew ------------------------------ #


def test_a_member_with_no_store_still_counts_its_levels(acme, capsys, monkeypatch):
    canned(monkeypatch, {"diff": (0, "")})
    shutil.rmtree(store_of(acme / "shop"))

    # Three candidates under shop and system.md above them. Computed inside the
    # store guard, this printed `1 of 1 levels` for system.md alone.
    assert run(["know", "api/orders.py", "--root", str(acme)]) == 0
    assert "1 of 4 levels have knowledge" in capsys.readouterr().out


def test_a_parent_with_no_store_of_its_own_walks_a_member_s(acme, capsys, monkeypatch):
    canned(monkeypatch, {"-- api": (0, NUMSTAT), "diff": (0, "")})
    shutil.rmtree(store_of(acme))

    assert run(["know", "api/orders.py", "--root", str(acme)]) == 0
    assert "shop · api/orders.py · 2 of 3 levels" in capsys.readouterr().out


def test_orientation_says_why_a_member_has_no_head_rather_than_no_store(
    acme, capsys, monkeypatch
):
    canned(monkeypatch, {"diff": (0, "")})
    shutil.rmtree(acme / "worker")
    shutil.rmtree(store_of(acme / "shop"))

    assert run(["know", "--root", str(acme)]) == 0
    out = capsys.readouterr().out
    assert "shop      (no store)" in out
    assert "worker    (missing)" in out

    (store_of(acme / "shop")).mkdir(parents=True)
    (store_of(acme / "shop") / "shop.md").write_text("+++\nnot toml\n+++\n")
    assert run(["know", "--root", str(acme)]) == 0
    assert "shop      (malformed)" in capsys.readouterr().out


def test_check_counts_the_stores_it_read_and_not_the_members_declared(
    acme, capsys, monkeypatch
):
    canned(monkeypatch, {"diff": (0, "")})
    shutil.rmtree(acme / "worker")

    assert run(["know", "--check", "--root", str(acme)]) == 0
    assert capsys.readouterr().out.startswith("knowledge: 2 roots, one store each")


def test_a_directory_named_system_is_refused_naming_the_collision(
    tmp_path, capsys, monkeypatch
):
    """Its repository file and the system file share a name by the mirror rule, so
    either reading is wrong for one of the two directories."""
    canned(monkeypatch, {"diff": (0, "")})
    root = tmp_path / "system"
    store = store_of(root)
    store.mkdir(parents=True)
    (store / "system.md").write_text(
        '+++\ntype = "Repository"\ndescription = "x"\nrevision = "abc1234"\n+++\n'
    )

    assert run(["know", "--root", str(root)]) == 1
    assert "a directory named system has no store" in capsys.readouterr().err


# --- what the four records claimed, pinned ------------------------------------ #


def test_a_declared_knowledge_dir_is_where_the_store_is_actually_read_from(
    acme, capsys, monkeypatch
):
    """The machine's value being ignored is pinned above; this is the other half —
    `flw_dir(root) / "knowledge"` in place of the declared-or-default expression
    reads a directory the project put nothing in."""
    canned(monkeypatch, {"diff": (0, "")})
    shop = acme / "shop"
    (shop / ".flw" / "config.toml").write_text('[knowledge]\ndir = "docs/arch"\n')
    (shop / "docs" / "arch").mkdir(parents=True)
    shutil.copy(store_of(shop) / "shop.md", shop / "docs" / "arch" / "shop.md")
    shutil.rmtree(store_of(shop))

    assert run(["know", "--root", str(shop)]) == 0
    out = capsys.readouterr().out
    assert "docs/arch/shop.md" in out
    assert "Serves the storefront" in out


def test_a_module_file_mirrors_the_file_it_describes_and_orphans_with_it(
    acme, capsys, monkeypatch
):
    """The toy holds no `<path>.md`, so `mirror`'s with_suffix("") was unpinned —
    and a real `flw know src/engine.py` said `current` for a changed file, which
    is the one verdict the store must not give."""
    shop = acme / "shop"
    store = store_of(shop)
    path = store / "api" / "orders.py.md"
    path.write_text(
        '+++\ntype = "Module"\ndescription = "One order, start to finish."\n'
        'revision = "8be0117"\n+++\nbody\n'
    )

    assert knowledge.mirror(store, shop, path) == Path("api/orders.py")
    assert knowledge.node_of(store, shop, path) == "shop/api/orders.py"

    calls = canned(monkeypatch, {"-- api/orders.py": (0, NUMSTAT), "diff": (0, "")})
    assert run(["know", "api/orders.py", "--root", str(shop)]) == 0
    out = capsys.readouterr().out
    assert "api/orders.py.md           module" in out
    assert "changed since 8be0117" in out
    assert ["diff", "--numstat", "--end-of-options", "8be0117", "--", "api/orders.py"] in [
        a for a, _ in calls
    ]

    (shop / "api" / "orders.py").rename(shop / "api" / "purchases.py")
    assert knowledge.orphans(store, shop) == [(path, shop / "api" / "orders.py")]


def test_check_prints_a_row_for_a_file_it_could_not_use_and_counts_it_apart(
    acme, capsys, monkeypatch
):
    """The four counted states partition the rows, so anything else a file can be
    is appended to the footer only when the store actually holds one."""
    canned(monkeypatch, {"diff": (0, "")})
    store = store_of(acme / "shop")
    (store / "shop.md").write_text("+++\nthis is not toml\n+++\nbody\n")
    (store / "api" / "api.md").write_text(
        '+++\ntype = "Area"\nrevision = "8be0117"\n+++\nbody\n'
    )

    assert run(["know", "--check", "--root", str(acme)]) == 0
    out = capsys.readouterr().out
    assert "  shop      shop.md                    malformed" in out
    assert "  shop      api/api.md                 missing description" in out
    assert out.rstrip().endswith("· 1 malformed · 1 missing description")


def test_orientation_counts_what_changed_and_says_why_a_member_is_absent(
    acme, capsys, monkeypatch
):
    canned(monkeypatch, {"diff": (0, NUMSTAT)})
    worker = store_of(acme / "worker") / "worker.md"
    worker.write_text(
        worker.read_text().replace(
            "description = ", "revision = \"3c81d90\"\nnot_a_description = ", 1
        )
    )

    assert run(["know", "--root", str(acme)]) == 0
    out = capsys.readouterr().out
    assert "1 changed" in out
    assert "worker    (missing description)" in out


def test_a_type_that_disagrees_with_position_hides_the_file_like_a_missing_one(
    acme, capsys, monkeypatch
):
    """`Concept.listable` excludes every problem but `unstamped`, and a
    disagreeing `type` is one more of those — the whole reason the field is
    declared as well as derived. Nothing at the command level held it before."""
    canned(monkeypatch, {"diff": (0, "")})
    shop = acme / "shop"
    store = store_of(shop)
    path = store / "shop.md"
    path.write_text(path.read_text().replace('type = "Repository"', 'type = "Area"'))

    assert run(["know", "--check", "--root", str(acme)]) == 0
    out = capsys.readouterr().out
    assert "  shop      shop.md                    type disagrees with position" in out
    assert out.rstrip().endswith("1 type disagrees with position")

    assert run(["know", "--root", str(acme)]) == 0
    assert "shop      (type disagrees with position)" in capsys.readouterr().out

    knowledge.reindex(store, shop)
    assert "shop.md" not in (store / "index.md").read_text()


def test_a_binary_file_counts_as_a_file_and_adds_no_lines(monkeypatch):
    """`-\t-\tpath` is a real change with no line counts, and int() on it raises."""
    canned(monkeypatch, {"diff": (0, NUMSTAT + "-\t-\tapi/logo.png\n")})
    diff = knowledge.numstat("8be0117", ACME / "shop", Path("api"))
    assert (diff.files, diff.insertions, diff.deletions) == (4, 41, 12)


def test_a_system_stamp_moves_every_declared_member_through_the_command(
    acme, capsys, monkeypatch
):
    """system.md carries one revision per member, each read in that member's own
    repository — `{}` in place of the members reaches none of them."""
    def fake(args: list[str], cwd: Path) -> tuple[int, str]:
        if "rev-parse" in " ".join(args):
            return 0, ("aaa1111\n" if cwd.name == "shop" else "bbb2222\n")
        return 0, ""

    monkeypatch.setattr(knowledge, "git", fake)
    path = store_of(acme) / "system.md"

    assert run(["know", "--stamp", str(path), "--root", str(acme)]) == 0
    concept = knowledge.load(path, store_of(acme), acme)
    assert concept.revision == {"shop": "aaa1111", "worker": "bbb2222"}
