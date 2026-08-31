"""The TypeScript scout — pins the fixes this version makes to scout.mjs.

Skipped by name when this repo's own `typescript` devDependency (declared in
package.json, for exactly this purpose — the scout cannot be exercised without
a TypeScript parser) is not installed, so `pytest -q` reports skips rather than
failures for a contributor who never ran `npm install`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCOUT_MJS = REPO / "core" / "scripts" / "scout.mjs"
TYPESCRIPT = REPO / "node_modules" / "typescript"
NODE = shutil.which("node")


def _typescript_resolves() -> bool:
    if NODE is None or not TYPESCRIPT.exists():
        return False
    probe = subprocess.run([NODE, "-e", "require.resolve('typescript')"], cwd=REPO, capture_output=True, check=False)
    return probe.returncode == 0


pytestmark = pytest.mark.skipif(
    not _typescript_resolves(),
    reason="typescript not installed — run `npm install` at the repo root",
)
# .venv/ and node_modules/ are gitignored, so `git worktree add` does not
# materialise them: a fresh worktree skips this file silently and hands back
# both declared checks until you run `uv venv .venv && uv pip install
# --python .venv/bin/python pytest ruff` and `npm install`.


def build(root: Path, files: dict[str, str]) -> Path:
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    (root / "node_modules").symlink_to(REPO / "node_modules", target_is_directory=True)
    return root


def run(root: Path, budget: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run([NODE, str(SCOUT_MJS), str(root), str(budget)], capture_output=True, text=True, check=False)


def test_a_reexport_barrel_ranks_the_definer_not_the_barrel(tmp_path):
    """Reproduced for the spec on a seven-file repo: five importers going
    through a barrel used to give the barrel the whole score. Resolving edges
    by name through `definers`, the way scout.py does, routes it to core.ts."""
    build(
        tmp_path,
        {
            "src/core.ts": "export class CoreThingHere {\n  run() {}\n}\n",
            "src/barrel.ts": 'export { CoreThingHere } from "./core";\n',
            **{
                f"src/user{i}.ts": (
                    'import { CoreThingHere } from "./barrel";\nconst x = new CoreThingHere();\n'
                )
                for i in range(1, 6)
            },
        },
    )
    out = run(tmp_path).stdout
    assert "src/core.ts" in out
    assert "src/barrel.ts" not in out


def test_a_specifier_ranks_the_module_not_a_definition_of_that_name(tmp_path):
    """An import carrying no definition name — a namespace import — produced no
    edge at all, so the module it names was invisible to the ranking while an
    unrelated file exporting a symbol of the same name was not."""
    build(
        tmp_path,
        {
            "src/config.ts": "export const VALUE = 1;\n",
            "src/shim.ts": "export class config {}\n",
            **{
                f"src/user{i}.ts": (
                    'import * as config from "./config";\nconsole.log(config);\n'
                )
                for i in range(1, 4)
            },
        },
    )
    out = run(tmp_path).stdout
    assert "src/config.ts" in out
    assert "src/shim.ts" not in out


def test_a_nested_file_reports_its_top_level_directory(tmp_path):
    """DIRECTORIES used to slice two path segments, so a/b/two.ts was reported
    as its own directory holding one file instead of falling under `a`."""
    build(
        tmp_path,
        {
            "root.ts": "export class Root {}\n",
            "a/one.ts": "export class One {}\n",
            "a/b/two.ts": "export class Two {}\n",
        },
    )
    out = run(tmp_path).stdout
    assert "a/b" not in out
    assert "2 files" in out


def test_an_unreadable_directory_does_not_abort_the_scan(tmp_path):
    """A network mount that timed out mid-walk took down a whole run in the
    Python scout; the same fix now applies here. The scan survives and says
    so on a nonzero exit that cli/flw.py's returncode==2 check does not
    mistake for the missing-typescript case."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root ignores directory permissions")
    build(
        tmp_path,
        {
            "app/core.ts": "export class Engine {}\n",
            "mnt/keep.ts": "export class Mounted {}\n",
        },
    )
    (tmp_path / "mnt").chmod(0o000)
    try:
        result = run(tmp_path)
    finally:
        (tmp_path / "mnt").chmod(0o755)
    assert "Mounted" not in result.stdout
    assert "app" in result.stdout
    assert result.returncode not in (0, 2)


def test_a_tsconfig_path_alias_is_not_reported_as_an_external_dependency(tmp_path):
    """scout.mjs classified any non-relative specifier as a third-party
    package, so a bare specifier aliasing this project's own top-level `shared`
    directory was reported as a dependency of the project on itself."""
    build(
        tmp_path,
        {
            "shared/util.ts": "export class Util {}\n",
            "main.ts": 'import { Util } from "shared/util";\nimport lodash from "lodash";\nconst u = new Util();\n',
        },
    )
    out = run(tmp_path).stdout
    external = out.split("EXTERNAL DEPENDENCIES", 1)[1].split("\n\n", 1)[0]
    assert "lodash" in external
    assert "shared" not in external


def test_a_tsconfig_star_alias_resolves_to_the_file_it_names(tmp_path):
    """The test above covers the baseUrl-relative form, `shared/util`, which the
    top-level-directory rule already handled and which never exercises `@/`. A
    `paths` alias is a different mechanism: `@` names no directory, so `@/lib`
    was reported as a third-party package and the import resolved to nothing —
    which in a tree where two files export `Props`, as React components
    routinely do, left the edge going to both."""
    build(
        tmp_path,
        {
            "tsconfig.json": '{"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["src/*"]}}}\n',
            "src/lib/types.ts": "export interface Props { id: string }\n",
            "src/other/types.ts": "export interface Props { name: string }\n",
            "main.ts": (
                'import { Props } from "@/lib/types";\n'
                'import lodash from "lodash";\n'
                'export const p: Props = { id: String(lodash) };\n'
            ),
        },
    )
    out = run(tmp_path).stdout
    assert "src/lib/types.ts" in out
    assert "src/other/types.ts" not in out
    external = out.split("EXTERNAL DEPENDENCIES", 1)[1].split("\n\n", 1)[0]
    assert "lodash" in external
    assert "@/" not in external


def test_a_name_exported_by_every_package_edges_only_to_the_one_imported(tmp_path):
    """`export interface Props` per component is ordinary React, so twenty
    components sharing the name ranked within 3% of each other whether or not
    anything imported them. The import names one module and the edge is that
    module's."""
    build(
        tmp_path,
        {
            "src/alpha/config.ts": "export interface Config { a: string }\n",
            "src/beta/config.ts": "export interface Config { b: string }\n",
            "src/gamma/config.ts": "export interface Config { c: string }\n",
            "src/main.ts": (
                'import { Config } from "./alpha/config";\n'
                'export const c: Config = { a: "x" };\n'
            ),
        },
    )
    out = run(tmp_path).stdout
    assert "src/alpha/config.ts" in out
    assert "src/beta/config.ts" not in out
    assert "src/gamma/config.ts" not in out


def test_a_missing_typescript_does_not_quote_a_path_that_does_not_exist(tmp_path):
    """The module-resolution error carried a `Require stack:` naming
    <root>/noop.js, a file createRequire needs a path for and never opens, so
    the reader was sent looking for it. The remedy is cli/flw.py's to print,
    because only the caller reads the lock file and knows the package manager."""
    (tmp_path / "app.ts").write_text("export class A {}\n")
    (tmp_path / "node_modules").mkdir()
    result = run(tmp_path)
    assert result.returncode == 2
    assert "Cannot find module 'typescript'" in result.stderr
    assert str(tmp_path) in result.stderr
    assert "noop.js" not in result.stderr
    assert "Require stack" not in result.stderr
    assert "install" not in result.stderr


def test_typescript_7_is_refused_by_name(tmp_path):
    """7.0.2's main entry exports only version and versionMajorMinor; the
    compiler API this scout uses moved under ./unstable/*. Refused rather than
    crashed, naming the version found and what it needs."""
    (tmp_path / "app.ts").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "app.ts").write_text("export class A {}\n")
    fake_ts = tmp_path / "node_modules" / "typescript"
    fake_ts.mkdir(parents=True)
    (fake_ts / "package.json").write_text('{"name": "typescript", "version": "7.0.2", "main": "index.js"}\n')
    (fake_ts / "index.js").write_text('module.exports = { version: "7.0.2" };\n')
    result = run(tmp_path)
    assert result.returncode == 2
    assert "7.0.2" in result.stderr
    assert "5.x or 6.x" in result.stderr


def test_a_definition_reached_through_depended_on_files_outranks_a_flat_one(tmp_path):
    """Ten importers each side, so a ranking that counted importers would tie.
    The depended-on file is named last alphabetically on purpose: at DAMPING zero
    every rank is equal and the stable sort falls back to walk order, so a test
    naming them the other way round would pass against a broken ranking."""
    files = {
        "src/zeta.ts": "export class TransactionLedger { run() { return 1; } }\n",
        "src/alpha.ts": "export class BackgroundJobRunner { run() { return 1; } }\n",
    }
    for i in range(10):
        files[f"src/mid{i}.ts"] = (
            f"import {{ TransactionLedger }} from './zeta';\n"
            f"export class MidPoint{i} {{ use() {{ return TransactionLedger; }} }}\n"
        )
        files[f"src/leaf{i}.ts"] = (
            f"import {{ BackgroundJobRunner }} from './alpha';\n"
            f"export const leaf{i} = BackgroundJobRunner;\n"
        )
        files[f"src/top{i}.ts"] = (
            f"import {{ MidPoint{i} }} from './mid{i}';\nexport const top{i} = MidPoint{i};\n"
        )
    out = run(build(tmp_path, files), budget=80).stdout
    assert out.index("src/zeta.ts") < out.index("src/alpha.ts")


def test_the_ranking_runs_until_it_stops_moving(tmp_path):
    """A chain: link0 imports link1 imports link2 ... so link7 is what the whole
    chain rests on, and rank reaches it only by flowing the full length. Stop
    after one iteration and every file ties. link7 sorts last alphabetically, so
    the tie cannot produce the expected order by accident."""
    files = {}
    for i in range(8):
        body = f"export class ChainLinkNumber{i} {{ run() {{ return {i}; }} }}\n"
        if i < 7:
            body = (
                f"import {{ ChainLinkNumber{i + 1} }} from './link{i + 1}';\n"
                f"const _use{i} = ChainLinkNumber{i + 1};\n"
            ) + body
        files[f"src/link{i}.ts"] = body
    out = run(build(tmp_path, files), budget=40).stdout
    # link0 imports link1 and nothing imports link0, so it is not in the section.
    assert out.index("src/link7.ts") < out.index("src/link2.ts")


def test_a_specifier_import_is_shown_as_its_own_row(tmp_path):
    """A namespace import names no export, so without a row of its own the file
    ranks with nothing printed under it."""
    files = {
        "src/helpers.ts": "export class HelperThingHere { run() { return 1; } }\n",
        "src/a.ts": "import * as helpers from './helpers';\nexport const useA = helpers;\n",
        "src/b.ts": "import * as helpers from './helpers';\nexport const useB = helpers;\n",
    }
    out = run(build(tmp_path, files), budget=40).stdout
    assert "src/helpers.ts" in out
    assert "helpers   2 files" in out
