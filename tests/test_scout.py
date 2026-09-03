"""The scout — orientation to a repo nobody has read.

Every assertion here stands for something measured on a real repository during
the research that produced this tool, not for a property that seemed desirable.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core" / "scripts"))
import scout as engine

from tests.test_cli import flw


def write(root: Path, files: dict[str, str]) -> Path:
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    return root


def scores(out: str) -> dict[str, float]:
    """The file scores printed under MOST DEPENDED ON. A file line carries two
    leading spaces and its rank; a definition line carries six and a count."""
    found: dict[str, float] = {}
    for line in out.split("MOST DEPENDED ON", 1)[1].splitlines():
        if not line.strip() or line.startswith("      "):
            continue
        path, _, score = line.strip().rpartition("   ")
        found[path] = float(score)
    return found


# --- vendored code -------------------------------------------------------- #


def test_vendored_code_is_excluded_before_ranking(tmp_path):
    """Measured: a vendored copy of tomlkit took half the top ten on a real repo.
    A library's modules import each other heavily, which is indistinguishable
    from a well-factored core once you are only counting edges."""
    write(
        tmp_path,
        {
            "app/core.py": "class Engine:\n    pass\n",
            "app/run.py": "from app.core import Engine\n",
            "vendor/lib/a.py": "class Widget:\n    pass\n",
            "vendor/lib/b.py": "from vendor.lib.a import Widget\n",
            "vendor/lib/c.py": "from vendor.lib.a import Widget\n",
        },
    )
    out = engine.scout(tmp_path)
    assert "Engine" in out
    assert "Widget" not in out
    assert "vendor" not in out


@pytest.mark.parametrize(
    "path",
    ["node_modules/x/a.py", "third_party/a.py", "dist/a.py", "app/api_pb2.py"],
)
def test_the_linguist_patterns_are_honoured(path):
    assert engine.is_vendored(path), path


def test_ordinary_paths_are_not_mistaken_for_vendored():
    for path in ["app/core.py", "src/builder.py", "outbox/send.py", "distiller.py"]:
        assert not engine.is_vendored(path), path


# --- ranking -------------------------------------------------------------- #


def test_imports_outrank_a_name_that_merely_collides(tmp_path):
    """The finding that set the design. Ranking over name references put a pytest
    fixture, close() and _utcnow() on top, because `.get()` on a dict cannot be
    told apart from a call to your own class's `get`. Imports are unambiguous."""
    write(
        tmp_path,
        {
            "app/models.py": "class InvoiceRecord:\n    def get(self):\n        pass\n",
            "app/noise.py": "class Other:\n    def get(self):\n        pass\n",
            "app/one.py": "from app.models import InvoiceRecord\nd = {}\nd.get('a')\n",
            "app/two.py": "from app.models import InvoiceRecord\nd = {}\nd.get('b')\n",
            "app/three.py": "from app.models import InvoiceRecord\nd = {}\nd.get('c')\n",
        },
    )
    out = engine.scout(tmp_path)
    assert "InvoiceRecord" in out
    top = out[out.index("MOST DEPENDED ON") :].splitlines()
    first = next(line for line in top if line.strip() and "MOST DEPENDED" not in line)
    assert "get" not in first


def test_a_definition_reached_through_depended_on_files_outranks_a_flat_one(tmp_path, monkeypatch):
    """Transitivity, not popularity: both definitions have exactly ten importers,
    and what separates them is that one set of importers is itself depended on.
    With damping at zero there is no transitivity left and the two tie exactly."""
    files = {
        "app/deep.py": "class Deep:\n    pass\n",
        "app/plain.py": "class Plain:\n    pass\n",
        "app/top.py": "".join(f"from app.hub{i} import Hub{i}\n" for i in range(10)),
    }
    for i in range(10):
        files[f"app/hub{i}.py"] = f"from app.deep import Deep\n\n\nclass Hub{i}:\n    pass\n"
        files[f"app/leaf{i}.py"] = "from app.plain import Plain\n"
    write(tmp_path, files)

    ranked = scores(engine.scout(tmp_path, budget=200))
    assert ranked["app/deep.py"] > ranked["app/plain.py"]

    monkeypatch.setattr(engine, "DAMPING", 0.0)
    flat = scores(engine.scout(tmp_path, budget=200))
    assert flat["app/deep.py"] == flat["app/plain.py"]


def test_an_import_that_resolves_to_nothing_does_not_divide_the_rank(tmp_path):
    """A file importing one local name and twenty from elsewhere gives that name
    the same score as a file importing nothing else."""
    stdlib = "".join(
        f"import {m}\n"
        for m in (
            "os", "sys", "json", "re", "io", "csv", "abc", "ast", "cmath", "copy",
            "enum", "glob", "gzip", "hmac", "math", "time", "uuid", "zlib", "stat",
            "html",
        )
    )
    write(
        tmp_path,
        {
            "app/a.py": "class A:\n    pass\n",
            "app/b.py": "class B:\n    pass\n",
            "app/one.py": "from app.a import A\n",
            "app/two.py": stdlib + "from app.b import B\n",
        },
    )
    ranked = scores(engine.scout(tmp_path))
    assert ranked["app/a.py"] == ranked["app/b.py"]


def test_the_printed_ranking_is_converged(tmp_path, monkeypatch):
    """The iteration stops when the ranking stops moving, so running it longer
    must change nothing the scout prints."""
    files = {"app/core.py": "class Engine:\n    pass\n\n\nclass Row:\n    pass\n"}
    for i in range(12):
        files[f"app/user{i}.py"] = f"from app.core import Engine\n\n\nclass User{i}:\n    pass\n"
    files["app/top.py"] = "".join(f"from app.user{i} import User{i}\n" for i in range(12))
    write(tmp_path, files)

    before = engine.scout(tmp_path, budget=200)
    monkeypatch.setattr(engine, "MAX_ITERATIONS", engine.MAX_ITERATIONS * 2)
    assert engine.scout(tmp_path, budget=200) == before


def test_a_file_importing_a_name_it_defines_does_not_rank_itself(tmp_path):
    """A self-edge is rank the file hands to itself every iteration, and without
    the guard it takes the whole ranking."""
    write(
        tmp_path,
        {
            "app/core.py": "from app.core import Engine\n\n\nclass Engine:\n    pass\n",
            "app/other.py": "class Other:\n    pass\n",
            "app/use.py": "from app.other import Other\n",
        },
    )
    ranked = scores(engine.scout(tmp_path))
    assert "app/core.py" not in ranked
    assert "app/other.py" in ranked


def test_a_module_import_ranks_the_module_not_a_definition_of_that_name(tmp_path):
    """`import X` recorded the bare module root and matched it against
    definition names. Measured on the stdlib: typing.py defines the deprecated
    shim `re`, so all 218 files writing `import re` pointed at typing.py."""
    write(
        tmp_path,
        {
            "app/config.py": "VALUE = 1\n",
            "app/shim.py": "class config:\n    pass\n",
            "app/one.py": "import app.config\n",
            "app/two.py": "import app.config\n",
            "app/three.py": "import app.config\n",
        },
    )
    out = engine.scout(tmp_path)
    assert "app/config.py" in out
    assert "app/shim.py" not in out


def test_a_relative_import_resolves_through_the_importing_files_package(tmp_path):
    """`from . import config` names a submodule of the importing file's own
    package. Resolved by name instead, it lands on whatever file defines a
    symbol called `config`."""
    write(
        tmp_path,
        {
            "app/__init__.py": "",
            "app/config.py": "VALUE = 1\n",
            "app/shim.py": "class config:\n    pass\n",
            "app/one.py": "from . import config\n",
            "app/two.py": "from . import config\n",
        },
    )
    out = engine.scout(tmp_path)
    assert "app/config.py" in out
    assert "app/shim.py" not in out


def test_an_import_that_resolves_to_nothing_is_not_an_edge(tmp_path):
    """`import os` must not reach a local class called `os`."""
    write(
        tmp_path,
        {
            "app/shim.py": "class os:\n    pass\n",
            "app/one.py": "import os\n",
            "app/two.py": "import os\n",
        },
    )
    assert "app/shim.py" not in engine.scout(tmp_path)


def test_tests_are_counted_but_never_ranked(tmp_path):
    write(
        tmp_path,
        {
            "app/core.py": "class Engine:\n    pass\n",
            "tests/test_core.py": "from app.core import Engine\n\n\ndef helper():\n    pass\n",
        },
    )
    out = engine.scout(tmp_path)
    assert "(1 test)" in out
    assert "helper" not in out


def test_a_repo_checked_out_under_a_directory_named_tests_still_ranks(tmp_path):
    """is_test used to run on the absolute path, so a repo checked out anywhere
    under a `test/` or `tests/` directory classified every file as a test and
    ranked nothing. pytest's own tmp_path is named test_something0 per test, not
    `tests`, so the existing suite never exercised this — the fixture has to
    create the directory itself."""
    root = tmp_path / "tests"
    write(
        root,
        {
            "app/core.py": "import requests\n\nclass Engine:\n    pass\n",
            "app/run.py": (
                "import argparse\n\nfrom app.core import Engine\n\n"
                'if __name__ == "__main__":\n    pass\n'
            ),
        },
    )
    out = engine.scout(root)
    # is_test is consulted at four call sites and each fails differently: the
    # ranking empties, the header calls every file a test, BUILT ON reports a
    # stdlib-only project, and ENTRY POINTS disappears. One assertion each.
    assert "Engine" in out
    assert "(0 test)" in out
    assert "requests" in out
    assert "ENTRY POINTS" in out


# --- degenerate trees ----------------------------------------------------- #


def test_a_tree_with_no_python_says_so(tmp_path):
    write(tmp_path, {"README.md": "# nothing here\n"})
    assert engine.scout(tmp_path) == "no python found"


def test_a_file_that_does_not_parse_is_skipped_not_fatal(tmp_path):
    write(
        tmp_path,
        {
            "app/broken.py": "def (((\n",
            "app/core.py": "class Engine:\n    pass\n",
            "app/run.py": "from app.core import Engine\n",
        },
    )
    assert "Engine" in engine.scout(tmp_path)


def test_a_repo_with_no_imports_at_all_still_reports(tmp_path):
    """PageRank over a graph with no edges is all-dangling. It must not divide by
    zero or leak rank; there is simply nothing to rank."""
    write(tmp_path, {"a.py": "class A:\n    pass\n", "b.py": "class B:\n    pass\n"})
    out = engine.scout(tmp_path)
    assert "2 python files" in out


# --- silent drops ----------------------------------------------------------- #


def test_a_file_with_a_utf8_bom_is_ranked(tmp_path):
    """CPython imports a BOM-prefixed file fine; reading with plain utf-8 raised
    and dropped it from the graph with no mention."""
    write(tmp_path, {"app/run.py": "from app.core import Engine\n"})
    (tmp_path / "app" / "core.py").write_bytes(b"\xef\xbb\xbf" + b"class Engine:\n    pass\n")
    assert "Engine" in engine.scout(tmp_path)


def test_a_file_that_fails_to_parse_is_counted_in_the_header(tmp_path):
    """Dropped from the analysis with no mention meant a tree where everything
    failed to parse reported `no python found` — the live case being an
    interpreter older than the target repo."""
    write(tmp_path, {"app/broken.py": "def (((\n", "app/core.py": "class Engine:\n    pass\n"})
    out = engine.scout(tmp_path)
    assert "1 failed to parse" in out


def test_a_from_import_marks_an_entry_point_by_its_module_root(tmp_path):
    """The entry-point cues were checked against imported *names*, which for
    `from click import command` holds `command` rather than `click`, so this
    form never marked an entry point."""
    write(tmp_path, {"app/cli.py": "from click import command\n\n@command()\ndef main():\n    pass\n"})
    out = engine.scout(tmp_path)
    assert "ENTRY POINTS" in out
    assert "click" in out


def test_a_definition_in_any_branch_the_walk_descends_is_found(tmp_path):
    """parse walks statement children rather than every AST node, which is 39%
    of the time on the CPython stdlib. The saving is only sound if the walk
    reaches every field that can hold a definition, so there is one here per
    field it extends from: orelse, a handler body, finalbody, and a match case."""
    write(
        tmp_path,
        {
            "app/core.py": (
                "import sys\n"
                "if sys.version_info >= (3, 12):\n"
                "    pass\n"
                "else:\n"
                "    class ElseEngine:\n"
                "        pass\n"
                "try:\n"
                "    pass\n"
                "except ValueError:\n"
                "    class HandlerEngine:\n"
                "        pass\n"
                "finally:\n"
                "    class FinallyEngine:\n"
                "        pass\n"
                "match sys.argv:\n"
                "    case []:\n"
                "        class MatchEngine:\n"
                "            pass\n"
                "    case _:\n"
                "        pass\n"
            ),
            "app/run.py": (
                "from app.core import ElseEngine, HandlerEngine\n"
                "from app.core import FinallyEngine, MatchEngine\n"
            ),
        },
    )
    out = engine.scout(tmp_path)
    for name in ("ElseEngine", "HandlerEngine", "FinallyEngine", "MatchEngine"):
        assert name in out


def test_dangling_mass_is_spread_evenly_not_leaked(tmp_path):
    """Pins the accumulate-then-spread rewrite of the dangling case by result,
    not by timing: most files here import nothing local. PageRank is a
    probability distribution, so total rank must still sum to 1 after every
    iteration whether it is spread node-by-node or accumulated into one scalar
    first — a bug in the rewrite would leak or double-count rank instead."""
    write(
        tmp_path,
        {
            "app/hub.py": "class Hub:\n    pass\n",
            "app/a.py": "from app.hub import Hub\n",
            "app/b.py": "class Standalone:\n    pass\n",
            "app/c.py": "class Lonely:\n    pass\n",
            "app/d.py": "class Isolated:\n    pass\n",
        },
    )
    facts = engine.parse(tmp_path)
    files = list(facts.defs)
    definers: dict = {}
    for path, here in facts.defs.items():
        for name, _, _ in here:
            definers.setdefault(name, []).append(path)
    out: dict = {}
    for src, seen in facts.imports.items():
        for _, name in seen:
            for dst in definers.get(name, []):
                if dst != src:
                    out.setdefault(src, []).append(dst)
    rank = engine.pagerank(files, out)
    assert sum(rank.values()) == pytest.approx(1.0)


# --- the command ---------------------------------------------------------- #


def run(path: Path, budget: int = 20) -> int:
    return flw.scout(argparse.Namespace(path=str(path), budget=budget))


def test_the_command_scouts_a_python_tree(tmp_path, capsys):
    write(
        tmp_path,
        {
            "app/core.py": "class Engine:\n    pass\n",
            "app/run.py": "from app.core import Engine\n",
        },
    )
    assert run(tmp_path) == 0
    assert "Engine" in capsys.readouterr().out


def test_a_missing_directory_refuses_with_one(tmp_path, capsys):
    """The scout's other refusal, and the one no test reached: it exited 2,
    which the contract's exit-code surface scopes to flw test and flw validate."""
    assert run(tmp_path / "not-here") == 1
    assert "no such directory" in capsys.readouterr().err


def test_neither_language_present_names_the_fallback(tmp_path, capsys):
    """Refusing is fine; refusing without saying what to do instead is not. The
    scout covers two languages because their parsers are already in a repo of
    that language, and the user needs to be told where to go for a third."""
    write(tmp_path, {"main.go": "package main\n"})
    # 1, not 2: the contract scopes 2 to flw test and flw validate, where it
    # means the run proved nothing. A refusal is what 1 already means.
    assert run(tmp_path) == 1
    err = capsys.readouterr().err
    assert "no Python or TypeScript" in err
    assert "aider --show-repo-map" in err


def test_an_unreadable_directory_does_not_kill_the_scan(tmp_path, monkeypatch):
    """A network mount that timed out mid-walk took down a whole run. One bad
    directory must cost you that directory, not the scout."""
    write(
        tmp_path,
        {
            "app/core.py": "class Engine:\n    pass\n",
            "app/run.py": "from app.core import Engine\n",
            "mnt/keep.py": "class Mounted:\n    pass\n",
        },
    )
    real = os.walk

    def exploding(top, **kwargs):
        for parent, dirs, files in real(top, **kwargs):
            if parent.endswith("/mnt"):
                if kwargs.get("onerror"):
                    kwargs["onerror"](TimeoutError("Operation timed out"))
                continue
            yield parent, dirs, files

    monkeypatch.setattr(engine.os, "walk", exploding)
    out = engine.scout(tmp_path)
    assert "Engine" in out
    assert "Mounted" not in out


def test_a_symlinked_directory_is_not_followed(tmp_path):
    """A link pointing at its own ancestor makes the walk never terminate."""
    write(
        tmp_path,
        {
            "app/core.py": "class Engine:\n    pass\n",
            "app/run.py": "from app.core import Engine\n",
        },
    )
    (tmp_path / "app" / "loop").symlink_to(tmp_path, target_is_directory=True)
    assert "Engine" in engine.scout(tmp_path)


# --- orientation beyond ranking ------------------------------------------- #


def test_entry_points_are_reported(tmp_path):
    """"How do I run this" is the question a stranger asks before "what is
    central", and no ranking answers it."""
    write(
        tmp_path,
        {
            "app/cli.py": "import argparse\n\nif __name__ == '__main__':\n    pass\n",
            "app/core.py": "class Engine:\n    pass\n",
        },
    )
    out = engine.scout(tmp_path)
    assert "ENTRY POINTS" in out
    assert "app/cli.py" in out
    assert "argparse" in out


def test_third_party_dependencies_say_what_it_is_built_on(tmp_path):
    write(
        tmp_path,
        {
            "app/scrape.py": "import playwright\nfrom bs4 import BeautifulSoup\nimport os\n",
        },
    )
    out = engine.scout(tmp_path)
    assert "playwright" in out
    assert "bs4" in out
    assert "  os " not in out  # stdlib is not a dependency


def test_a_projects_own_namespace_packages_are_not_dependencies(tmp_path):
    """Measured on a real repo: `sources` and `data` were reported as
    third-party because neither carried __init__.py. A project cannot be a
    dependency of itself."""
    write(
        tmp_path,
        {
            "sources/base.py": "class ProfileSource:\n    pass\n",
            "pipeline/run.py": "from sources.base import ProfileSource\nimport requests\n",
        },
    )
    out = engine.scout(tmp_path)
    built = out.split("BUILT ON", 1)[1].split("\n\n", 1)[0]
    assert "requests" in built
    assert "sources" not in built


def test_test_only_dependencies_are_not_what_it_is_built_on(tmp_path):
    """pytest topped the list on a real repo, burying what the product uses."""
    write(
        tmp_path,
        {
            "app/core.py": "import flask\n",
            "tests/test_core.py": "import pytest\nimport hypothesis\n",
        },
    )
    out = engine.scout(tmp_path)
    assert "flask" in out
    assert "pytest" not in out
    assert "hypothesis" not in out


def test_a_stdlib_only_project_says_so(tmp_path):
    write(tmp_path, {"app/core.py": "import json\nimport pathlib\n"})
    assert "stdlib only" in engine.scout(tmp_path)


def test_a_monorepos_services_are_packages_and_their_parent_is_not(tmp_path):
    """`parts[0]` put every service under `services/` and reported one node
    named after the directory holding them — wrong exactly where the reader
    most needs it right. One package is marked by pyproject.toml, one by
    package.json and one by __init__.py, so no single marker carries the test."""
    write(
        tmp_path,
        {
            "services/alpha/pyproject.toml": "[project]\nname = \"alpha\"\n",
            "services/alpha/core.py": "class Alpha:\n    pass\n",
            "services/beta/package.json": "{\"name\": \"beta\"}\n",
            "services/beta/use.py": "from services.alpha.core import Alpha\n",
            "services/gamma/__init__.py": "",
            "services/gamma/edge.py": "from services.alpha.core import Alpha\n",
        },
    )
    out = engine.scout(tmp_path)
    listed = out.split("PACKAGES", 1)[1].split("\n\n", 1)[0]
    assert "services/alpha" in listed
    assert "services/beta" in listed
    assert "services/gamma" in listed
    assert "  services " not in listed
    depends = out.split("DEPENDS ON", 1)[1].split("\n\n", 1)[0]
    assert "services/beta -> services/alpha   1 import" in depends


def test_a_mutual_import_between_packages_is_reported_as_a_cycle(tmp_path):
    """Between packages the components are few and small. The same section at
    file level prints one giant component on any real repo, which is why the
    cycles are reported here and not there."""
    write(
        tmp_path,
        {
            "services/alpha/pyproject.toml": "[project]\nname = \"alpha\"\n",
            "services/alpha/core.py": (
                "from services.beta.util import Helper\n\n\nclass Alpha:\n    pass\n"
            ),
            "services/beta/pyproject.toml": "[project]\nname = \"beta\"\n",
            "services/beta/util.py": (
                "from services.alpha.core import Alpha\n\n\nclass Helper:\n    pass\n"
            ),
        },
    )
    cycles = engine.scout(tmp_path).split("CYCLES", 1)[1]
    # Size and edges rather than a member list: at 88 packages the names said
    # only that the service was interconnected, and the edges say where to look.
    assert "2 packages in one cycle, 2 edges" in cycles
    assert "services/alpha -> services/beta   1 import" in cycles
    assert "services/beta -> services/alpha   1 import" in cycles


def test_a_single_flat_package_is_not_reported_as_a_finding(tmp_path):
    """One unnamed package named `.` is noise, not orientation."""
    write(
        tmp_path,
        {
            "core.py": "class Engine:\n    pass\n",
            "run.py": "from core import Engine\n",
        },
    )
    assert "PACKAGES" not in engine.scout(tmp_path)


# --- scout.mjs is a text file ---------------------------------------------- #


def test_scout_mjs_has_no_nul_byte():
    """A literal NUL makes the file binary to git and to grep, so the contract's
    own removal check — a grep — cannot see anything in it."""
    mjs = Path(__file__).resolve().parent.parent / "core" / "scripts" / "scout.mjs"
    assert b"\x00" not in mjs.read_bytes()


def test_the_ranking_iterates_until_the_movement_falls_below_the_tolerance(tmp_path, monkeypatch):
    """The iteration cap is a safety limit; the tolerance is what decides when to
    stop. Tightening it must change nothing, which is false of a tolerance loose
    enough to stop the loop after one pass."""
    files = {}
    for i in range(8):
        body = f"class ChainLinkNumber{i}:\n    pass\n"
        if i:
            body = f"from app.link{i-1} import ChainLinkNumber{i-1}\n\n\n" + body
        files[f"app/link{i}.py"] = body
    root = write(tmp_path, files)
    shipped = engine.scout(root, budget=40)
    monkeypatch.setattr(engine, "TOLERANCE", engine.TOLERANCE / 1000)
    assert engine.scout(root, budget=40) == shipped


def test_a_src_layout_module_import_resolves_under_the_src_root(tmp_path):
    """`import mypkg.core` in a src layout means src/mypkg/core.py. The scan root
    holds no package of that name, so resolving against it alone drops the edge
    and the file never ranks."""
    write(
        tmp_path,
        {
            "src/mypkg/__init__.py": "",
            "src/mypkg/core.py": "class CoreThingHere:\n    pass\n",
            "src/mypkg/app.py": "import mypkg.core\n",
        },
    )
    out = engine.scout(tmp_path)
    assert "src/mypkg/core.py" in out


def test_a_module_import_is_shown_as_its_own_row(tmp_path):
    """A module import names no definition, so without a row of its own the file
    ranks with a bare filename and nothing under it."""
    write(
        tmp_path,
        {
            "app/config.py": "class Settings:\n    pass\n",
            "app/a.py": "import app.config\n",
            "app/b.py": "import app.config\n",
        },
    )
    out = engine.scout(tmp_path)
    assert "app/config.py" in out
    assert "app.config   2 files" in out


# --- one name, many definers ----------------------------------------------- #


def test_a_name_defined_in_every_package_edges_only_to_the_one_imported(tmp_path):
    """Measured in a twelve-package monorepo where each package carries its own
    `config.py` defining `Config`: importing four things printed seven package
    edges, a cycle over all twelve packages, and ten identical `Config 33 files`
    rows. The import names one module and the edge belongs to that one."""
    files = {
        "packages/gateway/__init__.py": "",
        "packages/gateway/main.py": "from packages.alpha.config import Config\n",
    }
    for name in ("alpha", "beta", "gamma"):
        files[f"packages/{name}/__init__.py"] = ""
        files[f"packages/{name}/config.py"] = "class Config:\n    pass\n"
    write(tmp_path, files)

    out = engine.scout(tmp_path)
    assert "packages/alpha/config.py" in out
    assert "packages/beta/config.py" not in out
    assert "packages/gamma/config.py" not in out
    depends = out.split("DEPENDS ON", 1)[1].split("\n\n", 1)[0]
    assert "packages/gateway -> packages/alpha   1 import" in depends
    assert "packages/beta" not in depends
    assert "CYCLES" not in out


def test_a_package_deep_under_the_root_is_still_importable_by_its_own_name(tmp_path):
    """The upstream half of the same defect: source roots were found by looking
    one directory below the scan root, so a package at `libs/core/src/mono_core`
    was known only as `libs.core.src.mono_core` — a name no import can spell,
    which is why every absolute import in a monorepo fell through to matching by
    definition name. Two packages define `Ledger`, so a target that does not
    resolve is a target that cannot tell them apart."""
    write(
        tmp_path,
        {
            "libs/core/src/mono_core/__init__.py": "",
            "libs/core/src/mono_core/models.py": "class Ledger:\n    pass\n",
            "libs/extra/src/mono_extra/__init__.py": "",
            "libs/extra/src/mono_extra/models.py": "class Ledger:\n    pass\n",
            "app/use.py": "from mono_core.models import Ledger\n",
        },
    )
    out = engine.scout(tmp_path)
    depends = out.split("DEPENDS ON", 1)[1].split("\n\n", 1)[0]
    assert "app -> libs/core/src/mono_core   1 import" in depends
    assert "mono_extra" not in depends


def test_a_reexport_barrel_ranks_the_definer_not_the_barrel(tmp_path):
    """The fallback to every definer is what keeps this true: a barrel defines
    nothing, so preferring the module the import named matches nothing there and
    the edge still reaches the definition. Preferring only the named module —
    dropping the fallback — ranks nothing at all."""
    files = {
        "app/__init__.py": "",
        "app/core.py": "class CoreThingHere:\n    pass\n",
        "app/barrel.py": "from app.core import CoreThingHere\n",
    }
    for i in range(5):
        files[f"app/user{i}.py"] = "from app.barrel import CoreThingHere\n"
    write(tmp_path, files)

    ranked = scores(engine.scout(tmp_path))
    assert "app/core.py" in ranked
    assert "app/barrel.py" not in ranked


# --- the budget bounds the whole output -------------------------------------- #


def wide_repo(root: Path, packages: int = 30) -> Path:
    """Enough packages that the sections above the ranking overflow on their own.

    Each package imports the next, so PACKAGES, DEPENDS ON and the ranking all
    have more to say than any small budget can hold.
    """
    files = {}
    for i in range(packages):
        files[f"pkg{i}/pyproject.toml"] = f'[project]\nname = "pkg{i}"\n'
        nxt = (i + 1) % packages
        files[f"pkg{i}/mod.py"] = (
            f"from pkg{nxt}.mod import Thing{nxt}\n\n\nclass Thing{i}:\n    pass\n"
        )
    return write(root, files)


def content_lines(out: str) -> int:
    """Every line the budget is spent on: not the header, headings, or blanks."""
    body = [
        line
        for line in out.split("\n")[1:]
        if line.strip()
        and line.startswith(" ")
        and "past the budget" not in line
    ]
    return len(body)


@pytest.mark.parametrize("budget", [1, 4, 12, 40])
def test_the_budget_bounds_the_whole_output(tmp_path, budget):
    """It used to guard MOST DEPENDED ON alone, which is the last of six sections,
    so a field run of -n 12 produced 177 lines."""
    out = engine.scout(wide_repo(tmp_path), budget)
    assert content_lines(out) <= budget


def test_the_ranking_is_reached_at_every_budget(tmp_path):
    """The section the flag was named for. Sections above it used to crowd it out
    entirely; a rotation in printed order would reach it last."""
    for budget in (1, 2, 3, 5, 20):
        out = engine.scout(wide_repo(tmp_path), budget)
        assert "MOST DEPENDED ON" in out, budget


def test_every_section_with_content_gets_a_line_before_any_gets_a_second(tmp_path):
    """A small -n must not answer `what depends on what` with a bare heading."""
    out = engine.scout(wide_repo(tmp_path), 4)
    for heading in ("PACKAGES", "DEPENDS ON", "MOST DEPENDED ON"):
        assert heading in out, heading
        after = out.split(heading, 1)[1].lstrip("\n")
        assert after.startswith("  "), heading


def test_a_truncated_section_says_it_was_truncated(tmp_path):
    """A truncated answer that does not admit it reads as a complete one."""
    out = engine.scout(wide_repo(tmp_path), 6)
    assert "past the budget" in out


def test_a_giant_component_prints_its_size_not_its_members(tmp_path):
    out = engine.scout(wide_repo(tmp_path, packages=30), 200)
    assert "30 packages in one cycle" in out
    assert " <-> " not in out


def test_allocate_serves_the_named_section_first():
    """Printed order is unchanged; only the order of the rotation moves."""
    sections = [("A", ["a1", "a2"]), ("B", ["b1", "b2"])]
    assert engine.allocate(sections, 1, first="B")[1:3] == ["B", "b1"]
    assert engine.allocate(sections, 1, first="A")[1:3] == ["A", "a1"]
    both = engine.allocate(sections, 2, first="B")
    assert both.index("A") < both.index("B")
