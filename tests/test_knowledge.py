"""The knowledge store — a mirror of the code, a git diff, and a fold nobody authors.

Every test reads the shipped toy example at
`core/skills/flw-research/references/knowledge-example/`: a parent `acme` with
members `shop` and `worker`, the seam declared from both sides. It is the fixture
and the documentation at once, so a change that breaks the shape a first survey
imitates breaks this suite too.

No test runs git. Every git call in the module goes through one function, and the
tests that need a diff replace it with canned numstat output or a failure.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))
import knowledge

REPO = Path(__file__).resolve().parent.parent
TOY = REPO / "core" / "skills" / "flw-research" / "references" / "knowledge-example"
ACME = TOY / "acme"

# `git diff --numstat` for the shop's api/ — three files, +41 −12, the plan's
# Samples line. Tab-separated, because that is what git emits.
NUMSTAT = "20\t5\tapi/orders.py\n15\t4\tapi/models.py\n6\t3\tapi/routes.py\n"


@pytest.fixture(autouse=True)
def _default_flw_dir(monkeypatch):
    """The toy's directories are literally `.flw/`, so no $FLW_DIR may leak in."""
    monkeypatch.delenv("FLW_DIR", raising=False)


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


def test_the_diff_runs_against_the_mirrored_path_in_the_file_s_own_repo(monkeypatch):
    shop = ACME / "shop"
    store = store_of(shop)
    calls = canned(monkeypatch, {"diff": (0, "")})

    knowledge.changed(knowledge.load(store / "api" / "api.md", store, shop))
    args, cwd = calls[0]
    assert args == ["diff", "--numstat", "8be0117", "HEAD", "--", "api"]
    assert cwd == shop

    knowledge.changed(knowledge.load(store / "shop.md", store, shop))
    assert calls[1][0][-1] == "."


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
    assert [cwd for _, cwd in calls] == [ACME / "shop", ACME / "worker"]
    assert calls[0][0][2] == "1f4ac02"
    assert calls[1][0][2] == "3c81d90"
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

    assert knowledge.stamp([path], store, shop, {}) == [path]
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


def test_the_toy_folds_to_the_plan_s_sample_exactly():
    edges, described, carriers = knowledge.fold(stores_of(ACME))
    assert knowledge.render_map("acme", edges, described, carriers) == (
        "acme · folded from 3 concept files\n"
        "\n"
        "  shop        ──queue──▶   worker\n"
        "  shop/api    ──queue──▶   worker\n"
        "  worker      ──http──▶    shop\n"
        "\n"
        "3 edges · 3 nodes\n"
    )


def test_a_node_folds_in_both_directions_and_names_what_a_change_touches():
    edges, _, _ = knowledge.fold(stores_of(ACME))
    inbound, outbound = knowledge.touching(edges, "worker")
    assert knowledge.render_node("worker", inbound, outbound) == (
        "\n"
        "  in    shop      ──queue──▶  worker\n"
        "        shop/api  ──queue──▶  worker\n"
        "  out   worker    ──http──▶   shop\n"
        "\n"
        "changing worker's inbound contract touches: shop, shop/api\n"
    )


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
