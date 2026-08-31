"""Rank a Python repo by what the rest of it depends on. Stdlib only.

The problem is orientation, not lookup. Lookup — "who calls this symbol" — needs
a symbol name, and an agent that has never opened the repo does not have one.
This produces the nouns.

The method is aider's repo map, with two deliberate divergences. Aider ranks over
*name references* because tree-sitter across 130 languages cannot resolve imports
uniformly. Python's `ast` can, and measured on a real repo the difference is
total: ranking by name put a pytest fixture, `close()` and `_utcnow()` on top,
because `.get()` on a dict is indistinguishable from a call to your class's `get`.
Ranking by import put the actual domain types on top. Imports are explicit,
unambiguous and resolvable, so they are the edges.

Aider's weight heuristics are the second divergence, and they are not here.
Measured over three repositories, a long-multiword bonus fired on 75-94% of edges
on a real project tree and so cancelled — every edge is divided by its source's
total outgoing weight — changing at most one entry in twenty. They exist to
suppress generic names like `get` and `close`, which collide when you rank name
references; nobody writes `from x import get`, so the problem does not arise here.

Nothing is cached and nothing is written. The output is regenerated on demand
because it costs a fraction of a second, and because the one published A/B test
of static repo overviews (N=438) found they did not improve agent performance —
so an overview that lives on disk and rides in every request buys staleness and a
context tax for a benefit nobody has demonstrated.
"""

from __future__ import annotations

import ast
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

DAMPING = 0.85

# The iteration runs until the ranking stops moving: total movement across all
# nodes below a threshold scaled to one node's share of the ranking, 1/n.
TOLERANCE = 1e-6
# A safety limit and not a tuning parameter — it bounds a graph that never
# settles, and cannot change a ranking that has already converged.
MAX_ITERATIONS = 200

SKIP = {".venv", "venv", ".git", "__pycache__", ".tox", ".mypy_cache", ".ruff_cache"}

# Borrowed from github-linguist's vendor.yml, which runs against every repository
# on GitHub. Measured need: a vendored copy of tomlkit took half the top ten on a
# real repo, because a library's modules import each other heavily and that is
# indistinguishable from a well-factored core.
VENDORED = re.compile(
    r"(^|/)("
    r"vendors?|(3rd|third)[-_]?party|node_modules|bower_components|"
    r"dist|build|out|coverage|migrations|site-packages|eggs|\.eggs|"
    r"tests?/fixtures|specs?/fixtures|testdata"
    r")(/|$)",
    re.IGNORECASE,
)
GENERATED = re.compile(r"(_pb2(_grpc)?\.py|_pb\.py|\.generated\.py|\.g\.py)$")

# A package is a directory that declares itself one. `parts[0]` reported every
# service of a monorepo as a single node named after the directory holding them,
# which is wrong exactly where the reader most needs it right. The repository
# root is not a candidate: a package.json there says the repo is a package, not
# where the boundaries inside it fall.
PACKAGE_MARKERS = ("__init__.py", "pyproject.toml", "package.json")


def _package_of(root: Path, path: Path, cache: dict[Path, str]) -> str:
    """The nearest ancestor below `root` carrying a marker, or failing that the
    first path segment — a tree with no markers still has directories."""
    here = path.parent
    walked: list[Path] = []
    while here != root:
        if here in cache:
            found = cache[here]
            break
        if any((here / m).exists() for m in PACKAGE_MARKERS):
            found = here.relative_to(root).as_posix()
            break
        walked.append(here)
        here = here.parent
    else:
        parts = path.relative_to(root).parts
        found = parts[0] if len(parts) > 1 else "."
    for seen in walked:
        cache[seen] = found
    return found


def _components(graph: dict[str, set[str]]) -> list[list[str]]:
    """Strongly connected components, Tarjan, iterative — a deep package graph
    would otherwise hit the recursion limit."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on: set[str] = set()
    stack: list[str] = []
    found: list[list[str]] = []
    counter = 0
    for start, kin in graph.items():
        if start in index:
            continue
        index[start] = low[start] = counter
        counter += 1
        stack.append(start)
        on.add(start)
        work = [(start, iter(kin))]
        while work:
            node, kids = work[-1]
            descended = False
            for kid in kids:
                if kid not in index:
                    index[kid] = low[kid] = counter
                    counter += 1
                    stack.append(kid)
                    on.add(kid)
                    work.append((kid, iter(graph.get(kid, ()))))
                    descended = True
                    break
                if kid in on:
                    low[node] = min(low[node], index[kid])
            if descended:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[node])
            if low[node] == index[node]:
                group = []
                while True:
                    top = stack.pop()
                    on.discard(top)
                    group.append(top)
                    if top == node:
                        break
                found.append(group)
    return found


def is_vendored(rel: str) -> bool:
    return bool(VENDORED.search(rel) or GENERATED.search(rel))


def is_test(path: Path) -> bool:
    return any(p in {"tests", "test"} for p in path.parts) or path.name.startswith(
        "test_"
    )


def sources(root: Path) -> list[Path]:
    """Walk rather than rglob, for two reasons both learned the hard way.

    Pruning: rglob descends into node_modules and then discards it. Walking lets
    the excluded directory never be entered at all.

    Survival: one unreadable directory kills an rglob outright. A network mount
    that times out mid-scan took down a whole run — os.walk's onerror lets the
    scan skip it and carry on, which is what a user with a cloud drive needs.
    """
    found: list[Path] = []
    for parent, dirs, files in os.walk(root, onerror=lambda _: None):
        here = Path(parent)
        rel_dir = here.relative_to(root).as_posix()
        dirs[:] = [
            d
            for d in dirs
            if d not in SKIP
            and not is_vendored(f"{rel_dir}/{d}".lstrip("./"))
            and not (here / d).is_symlink()  # a self-referential link never ends
        ]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = here / name
            if is_vendored(path.relative_to(root).as_posix()):
                continue
            found.append(path)
    return found


@dataclass
class Facts:
    """What one pass over the tree learns. Ranking is only part of orientation."""

    defs: dict[Path, list[tuple[str, int, str]]] = field(default_factory=dict)
    # keyed by (the module the import named, the name), because the module is
    # what tells two files defining the same name apart.
    imports: dict[Path, dict[tuple[str | None, str], int]] = field(default_factory=dict)
    modules: dict[Path, dict[str, int]] = field(default_factory=dict)
    module_files: dict[str, Path] = field(default_factory=dict)
    lines: dict[Path, int] = field(default_factory=dict)
    entries: dict[Path, list[str]] = field(default_factory=dict)
    external: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    unparsed: int = 0


def _module_root(name: str) -> str:
    return name.split(".")[0]


def _source_roots(root: Path, files: list[Path]) -> list[Path]:
    """Where an absolute import starts counting from: the scan root, plus the
    parent of every topmost package in the tree, because `import pkg` means the
    directory holding `pkg`.

    Derived from the files rather than by looking one level below the root,
    which found nothing in a monorepo whose packages sit at `libs/*/src/*`:
    every module was then known only as `libs.core.src.mono_core`, a name no
    import can spell, so every absolute import missed and fell through to
    matching by definition name instead.

    Shallow roots come first, because `_module_names` lets the last one win the
    package a file sits in and the deepest is the one a relative import means.
    """
    packages = {p.parent for p in files if p.name == "__init__.py"}
    roots = {root}
    for pkg in packages:
        top = pkg
        while top != root and top.parent in packages:
            top = top.parent
        if top != root:
            roots.add(top.parent)
    return sorted(roots, key=lambda p: (len(p.parts), p))  # a set iterates arbitrarily


def _module_names(
    root: Path, files: list[Path]
) -> tuple[dict[str, Path], dict[Path, str]]:
    """Dotted module name -> the file that is that module, and each file -> the
    package it sits in.

    A module import resolves by module path and never by definition name.
    Matching `import X` against whatever file defines a symbol called `X` is how
    all 218 stdlib files writing `import re` pointed at typing.py, which defines
    a deprecated shim of that name.
    """
    modules: dict[str, Path] = {}
    package: dict[Path, str] = {}
    for base in _source_roots(root, files):  # the deepest comes last and wins below
        for path in files:
            try:
                rel = path.relative_to(base)
            except ValueError:
                continue
            parts = list(rel.parts)
            init = parts[-1] == "__init__.py"
            parts = parts[:-1] if init else [*parts[:-1], parts[-1][:-3]]
            if not parts:
                continue
            modules.setdefault(".".join(parts), path)
            package[path] = ".".join(parts if init else parts[:-1])
    return modules, package


def _resolve_relative(pkg: str, level: int, module: str) -> str | None:
    """`from ..a import b` inside package `p.q`: one dot is the package itself,
    each further dot drops a segment. Returns None when it walks off the top."""
    parts = pkg.split(".") if pkg else []
    if level - 1 > len(parts):
        return None
    base = parts[: len(parts) - (level - 1)] if level > 1 else parts
    if module:
        base = [*base, *module.split(".")]
    return ".".join(base) if base else None


def _is_main_guard(test: ast.expr) -> bool:
    """`if __name__ == "__main__":`, decided against the parsed tree rather
    than raw text, which also matches inside a comment or a docstring."""
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    left, right = test.left, test.comparators[0]
    names = {n.id for n in (left, right) if isinstance(n, ast.Name)}
    consts = {c.value for c in (left, right) if isinstance(c, ast.Constant)}
    return "__name__" in names and "__main__" in consts


def _statement_children(node: ast.AST) -> list[ast.stmt]:
    """Imports and definitions are statements and can appear nowhere else, so
    walking only body/orelse/finalbody/handlers/cases loses nothing they hold —
    what it skips is every expression node. Measured on the CPython 3.12 stdlib:
    5.48s to 3.34s of ast.walk time, output identical."""
    kids: list[ast.stmt] = []
    kids.extend(getattr(node, "body", None) or [])
    kids.extend(getattr(node, "orelse", None) or [])
    kids.extend(getattr(node, "finalbody", None) or [])
    for handler in getattr(node, "handlers", None) or []:
        kids.extend(handler.body)
    for case in getattr(node, "cases", None) or []:
        kids.extend(case.body)
    return kids


def parse(root: Path) -> Facts:
    facts = Facts()
    files = sources(root)
    # A top-level import is local when the tree itself provides it — otherwise it
    # is stdlib or a real dependency, and telling those apart says what a project
    # is built on, which no amount of ranking conveys.
    # Any directory in the tree that holds Python is this project's own, whether
    # or not it carries __init__.py — namespace packages are ordinary now, and
    # without this a project's own top-level packages are reported as third-party
    # dependencies of itself.
    local = {p.stem for p in files}
    for path in files:
        local.update(path.relative_to(root).parts[:-1])

    modules, package = _module_names(root, files)

    for path in files:
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            tree = ast.parse(text)
        except (SyntaxError, ValueError, OSError, RecursionError, MemoryError):
            facts.unparsed += 1
            continue
        here: list[tuple[str, int, str]] = []
        seen: dict[tuple[str | None, str], int] = defaultdict(int)
        mods: dict[str, int] = defaultdict(int)
        roots: set[str] = set()  # imported module roots, for entry-point cues only
        pkg = package.get(path, "")
        marks: list[str] = []
        has_main = False

        # Test dependencies are not what a project is built on. Counting them puts
        # pytest at the top of the list and buries what the product actually uses.
        product = not is_test(path.relative_to(root))

        stack = list(tree.body)
        while stack:
            node = stack.pop()
            stack.extend(_statement_children(node))
            if isinstance(node, ast.ClassDef):
                here.append((node.name, node.lineno, ""))
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                args = ", ".join(a.arg for a in node.args.args if a.arg != "self")
                here.append((node.name, node.lineno, f"({args})"))
            elif isinstance(node, ast.If) and _is_main_guard(node.test):
                has_main = True
            elif isinstance(node, ast.ImportFrom):
                base = _module_root(node.module or "")
                if node.level:
                    target = _resolve_relative(pkg, node.level, node.module or "")
                else:
                    target = node.module or None
                for alias in node.names:
                    # `from . import config` names a submodule, not a definition.
                    sub = f"{target}.{alias.name}" if target else ""
                    if sub in modules:
                        mods[sub] += 1
                    else:
                        seen[(target, alias.name)] += 1
                if base and node.level == 0:
                    roots.add(base)
                    if (
                        product
                        and base not in local
                        and base not in sys.stdlib_module_names
                    ):
                        facts.external[base] += 1
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    base = _module_root(alias.name)
                    roots.add(base)
                    if alias.name in modules:
                        mods[alias.name] += 1
                    if (
                        product
                        and base not in local
                        and base not in sys.stdlib_module_names
                    ):
                        facts.external[base] += 1

        if has_main:
            marks.append("__main__")
        for cue in ("argparse", "click", "typer"):
            if cue in roots or any(name == cue for _, name in seen):
                marks.append(cue)

        facts.defs[path] = here
        facts.imports[path] = dict(seen)
        facts.modules[path] = dict(mods)
        facts.lines[path] = text.count("\n") + 1
        if marks:
            facts.entries[path] = marks

    # A file that failed to parse is not a node in the graph, so a module import
    # resolving to one is an edge to nothing rather than a KeyError.
    facts.module_files = {name: p for name, p in modules.items() if p in facts.defs}
    return facts


def pagerank(nodes: list[Path], out: dict[Path, list[Path]]) -> dict[Path, float]:
    """Power iteration. networkx would do this in one line and cost a dependency.

    Every edge weighs the same, so an importer's rank divides evenly across what
    it imports, and an import that resolves to nothing in the repository does not
    divide it at all.
    """
    if not nodes:
        return {}
    n = len(nodes)
    rank = dict.fromkeys(nodes, 1.0 / n)
    for _ in range(MAX_ITERATIONS):
        nxt = dict.fromkeys(nodes, (1 - DAMPING) / n)
        dangling = 0.0
        for src in nodes:
            edges = out.get(src)
            if not edges:  # dangling: accumulate, spread evenly once below
                dangling += rank[src]
                continue
            share = DAMPING * rank[src] / len(edges)
            for dst in edges:
                nxt[dst] += share
        if dangling:
            spread = DAMPING * dangling / n
            for node in nodes:
                nxt[node] += spread
        moved = sum(abs(nxt[node] - rank[node]) for node in nodes)
        rank = nxt
        if moved < TOLERANCE / n:
            break
    return rank


def scout(root: Path, budget: int = 20) -> str:
    facts = parse(root)
    files = list(facts.defs)
    if not files:
        if facts.unparsed:
            plural = "s" if facts.unparsed != 1 else ""
            return f"no python found ({facts.unparsed} file{plural} failed to parse)"
        return "no python found"

    definers: dict[str, list[Path]] = defaultdict(list)
    for path, here in facts.defs.items():
        for name, _, _ in here:
            definers[name].append(path)

    # One edge per imported name that resolves, all weighing the same. A file
    # importing one local name and twenty from elsewhere gives that name the
    # same score as a file importing nothing else.
    out: dict[Path, list[Path]] = defaultdict(list)
    importers: dict[tuple[Path, str], set[Path]] = defaultdict(set)
    incoming: dict[Path, int] = defaultdict(int)
    for src, seen in facts.imports.items():
        for target, name in seen:
            candidates = definers.get(name, [])
            # The definer in the module the import named, and every definer only
            # when none matches. The fallback is what keeps a re-export barrel
            # taking none of the score: a barrel defines nothing, so nothing
            # matches there and the edge reaches the real definition instead.
            named = facts.module_files.get(target) if target else None
            if named is not None and named in candidates:
                candidates = [named]
            for dst in candidates:
                if dst != src:
                    out[src].append(dst)
                    importers[(dst, name)].add(src)
                    incoming[dst] += 1
    # A module import names no definition, so it would rank a file and leave it
    # with nothing printed under it. Counted separately and shown as its own row,
    # in the same unit as a definition's: how many files import this thing.
    as_module: dict[tuple[Path, str], set[Path]] = defaultdict(set)
    for src, mods in facts.modules.items():
        for name in mods:
            dst = facts.module_files.get(name)
            if dst is None or dst == src:
                continue
            out[src].append(dst)
            incoming[dst] += 1
            as_module[(dst, name)].add(src)

    rank = pagerank(files, out)
    named: dict[Path, list[tuple[str, int]]] = defaultdict(list)
    for (path, name), who in importers.items():
        named[path].append((name, len(who)))
    for (path, name), who in as_module.items():
        named[path].append((name, len(who)))

    code = [p for p in files if not is_test(p.relative_to(root))]
    loc = sum(facts.lines[p] for p in code)
    header = (
        f"{len(files)} python files ({len(files) - len(code)} test) · "
        f"{loc:,} lines of code · {sum(len(v) for v in facts.defs.values())} definitions"
    )
    if facts.unparsed:
        header += f" · {facts.unparsed} failed to parse"
    lines = [header]

    # Entry points first. "How do I run this" is the question a stranger asks
    # before "what is central", and ranking cannot answer it.
    entries = sorted(
        ((p, m) for p, m in facts.entries.items() if not is_test(p.relative_to(root))),
        key=lambda kv: -facts.lines[kv[0]],
    )
    if entries:
        lines += ["", "ENTRY POINTS"]
        for path, marks in entries[:6]:
            rel = str(path.relative_to(root))
            lines.append(f"  {rel:<40} {facts.lines[path]:>5} lines   {', '.join(marks)}")

    lines += ["", "BUILT ON"]
    if facts.external:
        ranked = sorted(facts.external.items(), key=lambda kv: -kv[1])
        for name, count in ranked[:10]:
            lines.append(f"  {name:<40} {count:>5} imports")
    else:
        lines.append("  stdlib only — no third-party imports")

    # A single unnamed package is not a finding; skip the section entirely.
    cache: dict[Path, str] = {}
    package_of = {path: _package_of(root, path, cache) for path in code}
    packages: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for path in code:
        key = package_of[path]
        packages[key] += rank[path]
        counts[key] += 1
    if len(packages) > 1:
        ranked_pkgs = sorted(packages.items(), key=lambda kv: -kv[1])
        floor = ranked_pkgs[0][1] * 0.01
        lines += ["", "PACKAGES"]
        for name, score in ranked_pkgs:
            if score < floor and len(lines) > 18:
                break
            lines.append(f"  {name:<26} {counts[name]:>4} files   {score:.3f}")

    # Who uses whom across packages, which the per-file ranking never states.
    pkg_edges: dict[tuple[str, str], int] = defaultdict(int)
    for src, dsts in out.items():
        if src not in package_of:
            continue
        for dst in dsts:
            if dst not in package_of:
                continue
            pair = (package_of[src], package_of[dst])
            if pair[0] != pair[1]:
                pkg_edges[pair] += 1
    if pkg_edges:
        ordered = sorted(pkg_edges.items(), key=lambda kv: (-kv[1], kv[0]))
        lines += ["", "DEPENDS ON"]
        for (a, b), count in ordered[:20]:
            lines.append(f"  {a} -> {b}   {count} import{'s' if count != 1 else ''}")
        if len(ordered) > 20:
            lines.append(f"  … {len(ordered) - 20} more package edges not shown")

        # Only components of two or more, and only between packages: the same
        # section at file level prints one giant component on any real repo.
        graph: dict[str, set[str]] = {}
        for a, b in pkg_edges:
            graph.setdefault(a, set()).add(b)
            graph.setdefault(b, set())
        cycles = [group for group in _components(graph) if len(group) > 1]
        if cycles:
            lines += ["", "CYCLES"]
            for group in cycles:
                members = sorted(group)
                shown = " <-> ".join(members[:8])
                if len(members) > 8:
                    shown += f" <-> … {len(members) - 8} more"
                lines.append(f"  {shown}")
                inside = sorted(
                    ((a, b, n) for (a, b), n in pkg_edges.items() if a in group and b in group),
                    key=lambda t: (-t[2], t[0]),
                )
                for a, b, n in inside[:10]:
                    lines.append(f"      {a} -> {b}   {n} import{'s' if n != 1 else ''}")
                if len(inside) > 10:
                    lines.append(f"      … {len(inside) - 10} more edges inside this cycle")

    # PageRank orders the files. Within a file the names are ordered by how many
    # files import each — a plain count, which needs no weights to be comparable.
    depended = sorted(
        (p for p in files if incoming[p] and not is_test(p.relative_to(root))),
        key=lambda p: -rank[p],
    )
    if depended:
        lines += ["", "MOST DEPENDED ON"]
        printed = 0
        for path in depended:
            if printed >= budget:
                break
            lines.append(f"\n  {path.relative_to(root)}   {rank[path]:.4f}")
            printed += 1
            for name, count in sorted(named[path], key=lambda kv: (-kv[1], kv[0]))[:4]:
                if printed >= budget:
                    break
                sig = next((s for n, _, s in facts.defs[path] if n == name), "")
                plural = "s" if count != 1 else ""
                lines.append(f"      {name}{sig}   {count} file{plural}")
                printed += 1

    return "\n".join(lines)


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    print(scout(target, int(sys.argv[2]) if len(sys.argv) > 2 else 20))
