"""The knowledge store — a system's architecture, in the shape of its code.

One store per project root, mirroring that root: a directory `D` at path `P` is
described by `<store>/P/D.md`, a file by `<store>/<path>.md`, the repository
itself by `<store>/<basename>.md`, and the parent of a multi-repo system by
`system.md`. Nothing is indexed, registered or named with a slug, so the answer
to "what describes this path" is a walk up the mirror and never a lookup.

OKF-shaped rather than OKF-conformant. The Open Knowledge Format prescribes a
directory of markdown, path as identity, `type` and `description`, a reserved
`index.md` and links as the graph — all structure, and all of it kept. It also
prescribes YAML, and the stdlib has no YAML reader while the note store already
reads `+++` TOML, so this imports that one function and flw gains no second
dialect. Nothing else is shared with the note store: its renderers take a note
with a cost and an age and cap at CAP, which is the listing this store never
prints at any opening.

Staleness is a git diff and never a judgment. A file records the revision it was
true at; the check is `git diff --numstat <revision> HEAD -- <path>` in that
file's own repository, and what it reports is how much moved, not whether the
claim survived. `3 files · +41 −12` tells a reader what a classifier would have
been guessing at. Every git call goes through `git()` so a test replaces one
function and no test runs git.
"""

from __future__ import annotations

import re
import subprocess
import textwrap
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from store import FRONTMATTER, _frontmatter

# Reserved by OKF and never a concept: a generated listing nothing may trust.
INDEX = "index.md"
SYSTEM = "system.md"

# `type` restates the file's position. Accepted because OKF names it, and
# `--check` reports a disagreement rather than either side winning silently.
SHORT = {"System": "system", "Repository": "repo", "Area": "area", "Module": "module"}

WIDTH = 70

# The frontmatter line this module is allowed to touch. Everything else in the
# block is the author's, byte for byte.
REVISION = re.compile(r"^revision[ \t]*=.*$", re.MULTILINE)
TABLE = re.compile(r"^[ \t]*\[")

DASH = "·"
ARROW = "→"


class Refused(Exception):
    """An input flw was given and could not use. The CLI prints it and exits 1.

    Raised rather than returned so that no caller can carry on with a value it
    was never handed — the exit-1 cases are all inputs, and an input that could
    not be used has no answer to return.
    """


# --- reading one file ------------------------------------------------------- #


@dataclass
class Concept:
    """One knowledge file, read. Nothing here raises on a bad file."""

    path: Path
    store: Path
    root: Path
    level: str
    meta: dict = field(default_factory=dict)
    body: str = ""
    # By name, in the order they are reported: unreadable, malformed, missing
    # type, missing description, type disagrees with position, unstamped.
    problems: list[str] = field(default_factory=list)

    @property
    def rel(self) -> str:
        return self.path.relative_to(self.store).as_posix()

    @property
    def type(self) -> str:
        value = self.meta.get("type")
        return value.strip() if isinstance(value, str) else ""

    @property
    def description(self) -> str:
        value = self.meta.get("description")
        return value.strip() if isinstance(value, str) else ""

    @property
    def revision(self) -> str | dict:
        value = self.meta.get("revision")
        if isinstance(value, str):
            return value.strip()
        return value if isinstance(value, dict) else ""

    @property
    def measured(self) -> str:
        value = self.meta.get("measured")
        return value.strip() if isinstance(value, str) else ""

    @property
    def connects(self) -> list[dict]:
        value = self.meta.get("connects")
        return [t for t in value if isinstance(t, dict)] if isinstance(value, list) else []

    @property
    def listable(self) -> bool:
        """Whether orientation and index.md may print it.

        Unstamped is the one problem that does not hide a file: it says nobody
        has recorded when the claim was true, not that the claim is unreadable.
        """
        return not [p for p in self.problems if p != "unstamped"]


def level_of(store: Path, root: Path, path: Path) -> str:
    """The level a knowledge file's position gives it.

    Position, never the declared `type` — the two are compared, and a reader
    that trusted the declaration would have nothing left to compare against.
    """
    rel = path.relative_to(store)
    if rel.parent == Path("."):
        if rel.name == SYSTEM:
            return "System"
        return "Repository" if rel.stem == root.name else "Module"
    return "Area" if rel.stem == rel.parent.name else "Module"


def mirror(store: Path, root: Path, path: Path) -> Path:
    """The code path a knowledge file describes, relative to its root.

    `.` for the repository file and for `system.md`: one mirrors the whole tree
    and the other mirrors a parent that is not a repository at all.
    """
    level = level_of(store, root, path)
    rel = path.relative_to(store)
    if level in ("System", "Repository"):
        return Path(".")
    if level == "Area":
        return rel.parent
    return rel.with_suffix("")


def load(path: Path, store: Path, root: Path) -> Concept:
    """One knowledge file. Every defect degrades the record and none raises."""
    level = level_of(store, root, path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # As store.walk already treats a note: one file flw cannot decode must
        # not cost the reader the store, and must not be dropped silently.
        return Concept(path, store, root, level, problems=["unreadable"])

    meta, body, malformed = _frontmatter(text)
    problems: list[str] = []
    if malformed:
        problems.append("malformed")
    concept = Concept(path, store, root, level, meta=meta, body=body, problems=problems)
    if not concept.type:
        problems.append("missing type")
    elif concept.type != level:
        problems.append("type disagrees with position")
    if not concept.description:
        problems.append("missing description")
    if not concept.revision:
        problems.append("unstamped")
    return concept


# --- the walk --------------------------------------------------------------- #


def candidates(root: Path, store: Path, rel: Path) -> list[Path]:
    """Every knowledge file that could describe `rel`, nearest first.

    Missing is normal and most of these will not exist: the store is sparse by
    design, so the walk is a filter over candidates rather than a lookup.
    """
    found: list[Path] = []
    if (root / rel).is_file():
        found.append(store / (rel.as_posix() + ".md"))
        current = rel.parent
    else:
        current = rel
    while current != Path("."):
        found.append(store / current / f"{current.name}.md")
        current = current.parent
    found.append(store / f"{root.name}.md")
    return found


def walk(root: Path, store: Path, rel: Path) -> list[Path]:
    """The candidates that exist, nearest first. Print them reversed."""
    return [c for c in candidates(root, store, rel) if c.is_file()]


def relative_to_root(root: Path, given: Path) -> Path:
    """`given` as a path under `root`, or a refusal.

    Read against the working directory first and against the root second, so
    that both `flw know src/engine.py` from inside a repository and `flw know
    api/orders.py --root shop` from its parent name the file the caller meant.

    A path outside the root is a typo or the wrong `--root`; a path that is not
    in the code is a typo or a rename that already orphaned its knowledge.
    """
    root = root.resolve()
    reachable = [given] if given.is_absolute() else [Path.cwd() / given, root / given]
    outside = False
    for candidate in reachable:
        resolved = candidate.resolve()
        if not resolved.exists():
            continue
        try:
            rel = resolved.relative_to(root)
        except ValueError:
            outside = True
            continue
        return rel if rel != Path() else Path(".")
    if outside:
        raise Refused(f"{given} is not under {root}")
    raise Refused(f"{given} is not in the code under {root}")


def concepts(store: Path) -> list[Path]:
    """Every concept file in a store, outermost first.

    Depth before name, so a store's own file leads and each directory's file
    leads its children — the order a reader descends in, not the order bytes
    sort in, under which `api/api.md` precedes `shop.md`.
    """
    if not store.is_dir():
        return []
    found = [p for p in store.rglob("*.md") if p.is_file() and p.name != INDEX]
    return sorted(found, key=lambda p: (len(p.relative_to(store).parts), p.relative_to(store).as_posix()))


# --- the diff --------------------------------------------------------------- #


def git(args: list[str], cwd: Path) -> tuple[int, str]:
    """(exit code, stdout). Every git call in this module goes through here.

    One function, so a test replaces one thing and no test in the suite runs
    git. Git is hardcoded for now because it is what the first system to use
    this store runs; a second VCS is two config keys later and not a redesign.
    """
    try:
        done = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
        )
    except OSError as exc:  # git absent, cwd gone
        return 127, str(exc)
    return done.returncode, done.stdout


@dataclass(frozen=True)
class Diff:
    """What moved under a path since a revision. `state` is the whole verdict."""

    state: str  # current | changed | unstamped | unverifiable
    files: int = 0
    insertions: int = 0
    deletions: int = 0
    first: str = ""

    def summary(self) -> str:
        noun = "file" if self.files == 1 else "files"
        # U+2212, the minus sign: this is a count, not a hyphenated word.
        return f"{self.files} {noun} {DASH} +{self.insertions} −{self.deletions}"


def numstat(revision: str, cwd: Path, rel: Path) -> Diff:
    """`git diff --numstat <revision> HEAD -- <rel>`, summed.

    No output is current; any output is changed. There is no classification: a
    function-body edit and a new directory both count, and the numbers say
    which it was. A diff that cannot run — not a repository, a hash gone after
    a rebase — is unverifiable, and the file is read normally.
    """
    code, out = git(["diff", "--numstat", revision, "HEAD", "--", rel.as_posix()], cwd)
    if code != 0:
        return Diff("unverifiable")
    lines = [line for line in out.splitlines() if line.strip()]
    if not lines:
        return Diff("current")
    insertions = deletions = 0
    first = ""
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added, removed, path = parts[0], parts[1], parts[2]
        # A binary file's counts are `-`, which is a real change with no lines.
        insertions += int(added) if added.isdigit() else 0
        deletions += int(removed) if removed.isdigit() else 0
        first = first or path
    return Diff("changed", len(lines), insertions, deletions, first)


def changed(concept: Concept) -> Diff:
    """One file's staleness. `system.md` goes through `changed_system` instead."""
    if concept.level == "System":
        raise ValueError("system.md is checked per member; use changed_system")
    if "unstamped" in concept.problems:
        return Diff("unstamped")
    return numstat(str(concept.revision), concept.root, mirror(concept.store, concept.root, concept.path))


def members_by_basename(members: dict[str, Path]) -> dict[str, Path]:
    """`[project.roots]` keyed the way `system.md` keys it.

    The store reads the values only: a node and a revision key are the member
    directory's basename, so renaming the config key does not orphan a store.
    """
    return {path.name: path for path in members.values()}


def changed_system(concept: Concept, members: dict[str, Path]) -> dict[str, Diff]:
    """One diff per declared member, run in that member's own repository.

    `system.md` sits in a parent that is not a repository and spans several that
    are, so the one revision it carries is a table and the check is per member.
    """
    table = concept.revision if isinstance(concept.revision, dict) else {}
    found: dict[str, Diff] = {}
    for name, path in members_by_basename(members).items():
        revision = table.get(name)
        if not isinstance(revision, str) or not revision.strip():
            found[name] = Diff("unstamped")
            continue
        found[name] = numstat(revision.strip(), path, Path("."))
    return found


def undeclared_members(concept: Concept, members: dict[str, Path]) -> list[str]:
    """Revision keys naming no declared member. Reported, never rewritten."""
    table = concept.revision if isinstance(concept.revision, dict) else {}
    known = members_by_basename(members)
    return sorted(key for key in table if key not in known)


def system_state(per_member: dict[str, Diff]) -> str:
    """One word for a file whose check ran several times."""
    states = {d.state for d in per_member.values()}
    for state in ("changed", "unstamped", "unverifiable"):
        if state in states:
            return state
    return "current"


# --- stamping --------------------------------------------------------------- #


def head(root: Path) -> str:
    """The revision to record. Short, because it is read by people."""
    code, out = git(["rev-parse", "--short", "HEAD"], root)
    if code != 0 or not out.strip():
        raise Refused(f"{root}: git rev-parse HEAD failed; nothing was written")
    return out.strip().splitlines()[0]


def _rewrite(block: str, line: str) -> str:
    """`block` with its `revision` line replaced, or the line inserted.

    Inserted before the first table header rather than at the very end of the
    block: a file whose frontmatter ends in `[[connects]]` would otherwise get
    its revision keyed inside that table, which parses as a different document.
    """
    if REVISION.search(block):
        return REVISION.sub(lambda _: line, block, count=1)
    lines = block.splitlines()
    cut = next((i for i, text in enumerate(lines) if TABLE.match(text)), len(lines))
    while cut > 0 and not lines[cut - 1].strip():
        cut -= 1
    return "\n".join([*lines[:cut], line, *lines[cut:]])


def _revision_line(concept: Concept, members: dict[str, Path]) -> str:
    """The `revision = …` line this file should now carry.

    For `system.md` an inline table: every declared member re-stamped from its
    own repository, every key naming no declared member left exactly as it is.
    """
    if concept.level != "System":
        return f'revision = "{head(concept.root)}"'

    known = members_by_basename(members)
    table = concept.revision if isinstance(concept.revision, dict) else {}
    values: dict[str, str] = {}
    for key, value in table.items():
        values[key] = head(known[key]) if key in known else str(value)
    for name, path in known.items():
        values.setdefault(name, head(path))
    body = ", ".join(f'{key} = "{value}"' for key, value in values.items())
    return f"revision = {{ {body} }}"


def stamp(paths: list[Path], store: Path, root: Path, members: dict[str, Path]) -> list[Path]:
    """Write the current HEAD into `revision` in each named file, and nothing else.

    A textual edit of one line, never a re-serialisation: the rest of the block
    is the author's comments, key order and spacing, and a round trip through
    tomllib would silently reflow all three.
    """
    written: list[Path] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise Refused(f"{path}: cannot read: {exc}") from None
        match = FRONTMATTER.match(text)
        if not match:
            raise Refused(f"{path}: no +++ frontmatter block to stamp")
        block = match.group(1)
        try:
            tomllib.loads(block)
        except ValueError as exc:
            raise Refused(f"{path}: the +++ block does not parse: {exc}") from None

        concept = load(path, store, root)
        # head() raises before anything is written, so a repository with no HEAD
        # leaves every named file exactly as it was.
        line = _revision_line(concept, members)
        path.write_text(text[: match.start(1)] + _rewrite(block, line) + text[match.end(1) :])
        written.append(path)
    return written


# --- orphans and the generated listing --------------------------------------- #


def orphans(store: Path, root: Path) -> list[tuple[Path, Path]]:
    """(concept file, the code path it expected) for every mirror that is gone.

    The rename case, and it needs no VCS: one stat per file.
    """
    missing: list[tuple[Path, Path]] = []
    for path in concepts(store):
        expected = root / mirror(store, root, path)
        if not expected.exists():
            missing.append((path, expected))
    return missing


def _listing(store: Path, directory: Path, root: Path) -> str:
    """One directory's index.md: its concepts, then its subdirectories."""
    rel = directory.relative_to(store)
    title = store.name if rel == Path(".") else rel.as_posix()
    lines = [
        f"# {title}",
        "",
        "Generated by `flw know --reindex`. Nothing may trust it: a reader that doubts one",
        "reads the directory.",
        "",
    ]
    for path in sorted(directory.glob("*.md")):
        if path.name == INDEX or not path.is_file():
            continue
        concept = load(path, store, root)
        if not concept.listable:
            continue
        lines.append(f"- [{path.name}]({path.name}) — {concept.description}")
    for child in sorted(p for p in directory.iterdir() if p.is_dir()):
        own = child / f"{child.name}.md"
        entry = f"- [{child.name}/]({child.name}/)"
        if own.is_file():
            concept = load(own, store, root)
            if concept.listable:
                entry = f"{entry} — {concept.description}"
        lines.append(entry)
    return "\n".join(lines) + "\n"


def reindex(store: Path, root: Path) -> list[Path]:
    """Rewrite every index.md under the store. Returns only what actually moved.

    Written by this and by nothing else, and nothing may trust one: a reader
    that doubts a listing reads the directory, so a stale one costs a directory
    read and never a wrong answer.
    """
    written: list[Path] = []
    if not store.is_dir():
        return written
    for directory in sorted({store, *(p for p in store.rglob("*") if p.is_dir())}):
        target = directory / INDEX
        content = _listing(store, directory, root)
        if target.is_file() and target.read_text(encoding="utf-8") == content:
            continue
        target.write_text(content)
        written.append(target)
    return written


# --- the fold ---------------------------------------------------------------- #


@dataclass(frozen=True)
class Edge:
    source: str
    to: str
    how: str
    carries: str


def node_of(store: Path, root: Path, path: Path) -> str:
    """A concept file's node name: a repo basename, or basename/area-path."""
    level = level_of(store, root, path)
    if level in ("System", "Repository"):
        return root.name
    rel = path.relative_to(store)
    tail = rel.parent if level == "Area" else rel.with_suffix("")
    return f"{root.name}/{tail.as_posix()}"


def fold(stores: list[tuple[Path, Path]]) -> tuple[list[Edge], set[str], int]:
    """(edges, the nodes some file describes, how many files carried an edge).

    Nobody authors this and nothing can drift from it: it is every `connects`
    table in every store, read on the spot. A `to` that names no file is still
    a node — counted as undescribed rather than hidden, because a seam nobody
    wrote up is exactly what a reader wants to be told about.
    """
    edges: list[Edge] = []
    described: set[str] = set()
    carriers = 0
    for root, store in stores:
        for path in concepts(store):
            concept = load(path, store, root)
            if "unreadable" in concept.problems:
                continue
            node = node_of(store, root, path)
            described.add(node)
            found = False
            for table in concept.connects:
                to = table.get("to")
                if not isinstance(to, str) or not to.strip():
                    continue
                edges.append(
                    Edge(
                        node,
                        to.strip(),
                        str(table.get("how", "")).strip(),
                        str(table.get("carries", "")).strip(),
                    )
                )
                found = True
            carriers += 1 if found else 0
    edges.sort(key=lambda e: (e.source, e.to, e.how))
    return edges, described, carriers


def touching(edges: list[Edge], node: str) -> tuple[list[Edge], list[Edge]]:
    """(inbound, outbound) for one node. Both directions, never one."""
    return (
        [e for e in edges if e.to == node],
        [e for e in edges if e.source == node],
    )


def nodes_of(edges: list[Edge]) -> set[str]:
    return {e.source for e in edges} | {e.to for e in edges}


def require_node(edges: list[Edge], described: set[str], node: str) -> None:
    """Refuse a node no file names or reaches.

    A filter that silently returns nothing reads exactly like a part with no
    edges, and the two are the opposite answers to the question being asked.
    """
    if node not in nodes_of(edges) | described:
        raise Refused(f"no knowledge file names or reaches the node {node!r}")


# --- rendering --------------------------------------------------------------- #


def _wrap(text: str, first: str, rest: str) -> list[str]:
    if not text:
        return []
    return textwrap.fill(
        text, width=WIDTH, initial_indent=first, subsequent_indent=rest
    ).splitlines()


def _edge_lines(concept: Concept, indent: str) -> list[str]:
    lines = []
    for table in concept.connects:
        to = str(table.get("to", "")).strip()
        if not to:
            continue
        how = str(table.get("how", "")).strip()
        carries = str(table.get("carries", "")).strip()
        detail = ", ".join(p for p in (how, carries) if p)
        lines.append(f"{indent}{ARROW} {to}" + (f" ({detail})" if detail else ""))
    return lines


def render_orientation(
    name: str,
    system: Concept,
    members: list[tuple[str, Concept | None]],
    changes: dict[str, Diff],
) -> str:
    """A parent's orientation: the system file, then one head per member.

    The one place a reader meets a whole system, and where most work stops —
    which is why it prints descriptions and edges and never a body.
    """
    lines = [f"system: {name} {DASH} {len(members)} roots {DASH} {system.path}"]
    lines += _wrap(system.description, "  ", "  ")
    lines.append("")
    for member, concept in members:
        if concept is None:
            lines.append(f"  {member.ljust(10)}(no store)")
            continue
        lines += _wrap(concept.description, f"  {member.ljust(10)}", " " * 12)
        lines += _edge_lines(concept, " " * 12)
    lines.append("")
    count = len([c for _, c in members if c is not None])
    noun = "file" if count == 1 else "files"
    moved = len([d for d in changes.values() if d.state == "changed"])
    lines.append(
        f"{count} repo {noun}, each in its own repo's store {DASH} {moved} changed"
    )
    return "\n".join(lines) + "\n"


def render_repo_orientation(name: str, concept: Concept, diff: Diff) -> str:
    """A repository standing alone: its own file, and nothing walked upward.

    Nothing looks for a parent that claims this repository. Standing inside a
    member, flw sees that member alone; the system is seen by naming its root.
    """
    lines = [f"repo: {name} {DASH} {concept.path}"]
    lines += _wrap(concept.description, "  ", "  ")
    lines += _edge_lines(concept, "  ")
    lines.append("")
    moved = 1 if diff.state == "changed" else 0
    lines.append(f"1 repo file {DASH} {moved} changed")
    return "\n".join(lines) + "\n"


def _walk_status(diff: Diff, revision: str) -> str:
    """The status column, which is the number and never a verdict."""
    if diff.state == "changed" and diff.files:
        detail = f"changed since {revision}: {diff.summary()}"
        return f"{detail} {DASH} e.g. {diff.first}" if diff.first else detail
    return diff.state


def render_walk(
    label: str,
    rel: Path,
    found: list[tuple[Concept, Diff]],
    total: int,
    full: bool,
) -> str:
    """The walk, outermost first — the order a reader takes them in."""
    lines = [
        (
            f"{label} {DASH} {rel.as_posix()} {DASH} "
            f"{len(found)} of {total} levels have knowledge"
        ),
        "",
    ]
    for concept, diff in found:
        revision = concept.revision if isinstance(concept.revision, str) else ""
        lines.append(
            f"  {concept.rel.ljust(27)}{SHORT[concept.level].ljust(7)}"
            f"{(revision or '—').ljust(10)}{_walk_status(diff, revision)}"
        )
        lines += _wrap(concept.description, "    ", "    ")
        lines += _edge_lines(concept, "    ")
        if full and concept.body.strip():
            lines.append("")
            lines += [
                f"    {line}" if line.strip() else ""
                for line in concept.body.strip().splitlines()
            ]
        lines.append("")
    noun = "file" if len(found) == 1 else "files"
    moved = len([d for _, d in found if d.state == "changed"])
    footer = f"{len(found)} {noun} {DASH} {moved} changed"
    if found and not full:
        footer = f"{footer} {DASH} --full for bodies"
    lines.append(footer)
    return "\n".join(lines) + "\n"


@dataclass
class Row:
    root: str
    file: str
    state: str
    detail: str = ""


def render_check(header: str, rows: list[Row], notes: list[str]) -> str:
    """The whole store, writing nothing, exit 0 whatever it finds.

    The four counted states partition the rows, so the footer adds up; anything
    else a file can be — malformed, unverifiable, a missing field — is appended
    only when the store actually holds one.
    """
    lines = [header, ""]
    for row in rows:
        lines.append(
            f"  {row.root.ljust(10)}{row.file.ljust(27)}"
            f"{row.state.ljust(12)}{row.detail}".rstrip()
        )
    lines.append("")
    counted = dict.fromkeys(("changed", "unstamped", "current", "orphan"), 0)
    others: dict[str, int] = {}
    for row in rows:
        if row.state in counted:
            counted[row.state] += 1
        else:
            others[row.state] = others.get(row.state, 0) + 1
    noun = "file" if len(rows) == 1 else "files"
    footer = (
        f"{len(rows)} {noun} {DASH} {counted['changed']} changed {DASH} "
        f"{counted['unstamped']} unstamped {DASH} {counted['current']} current "
        f"{DASH} {counted['orphan']} orphans"
    )
    for state, count in sorted(others.items()):
        footer = f"{footer} {DASH} {count} {state}"
    lines.append(footer)
    if notes:
        lines.append("")
        lines += [f"  {note}" for note in notes]
    return "\n".join(lines) + "\n"


def _arrow(how: str) -> str:
    return f"──{how}──▶"


def render_map(name: str, edges: list[Edge], described: set[str], carriers: int) -> str:
    noun = "file" if carriers == 1 else "files"
    lines = [f"{name} {DASH} folded from {carriers} concept {noun}", ""]
    for edge in edges:
        lines.append(f"  {edge.source.ljust(12)}{_arrow(edge.how).ljust(13)}{edge.to}")
    lines.append("")
    everything = nodes_of(edges)
    undescribed = len(everything - described)
    edge_noun = "edge" if len(edges) == 1 else "edges"
    node_noun = "node" if len(everything) == 1 else "nodes"
    footer = f"{len(edges)} {edge_noun} {DASH} {len(everything)} {node_noun}"
    if undescribed:
        footer = f"{footer} {DASH} {undescribed} undescribed"
    lines.append(footer)
    return "\n".join(lines) + "\n"


def render_node(node: str, inbound: list[Edge], outbound: list[Edge]) -> str:
    lines = [""]
    for i, edge in enumerate(inbound):
        label = "in" if i == 0 else ""
        lines.append(
            f"  {label.ljust(6)}{edge.source.ljust(10)}"
            f"{_arrow(edge.how).ljust(12)}{edge.to}"
        )
    for i, edge in enumerate(outbound):
        label = "out" if i == 0 else ""
        lines.append(
            f"  {label.ljust(6)}{edge.source.ljust(10)}"
            f"{_arrow(edge.how).ljust(12)}{edge.to}"
        )
    if inbound:
        sources = sorted({e.source for e in inbound})
        lines.append("")
        lines.append(
            f"changing {node}'s inbound contract touches: {', '.join(sources)}"
        )
    return "\n".join(lines) + "\n"


def render_mermaid(edges: list[Edge]) -> str:
    ids: dict[str, str] = {}
    for node in sorted(nodes_of(edges)):
        ids[node] = "n" + re.sub(r"\W", "_", node)
    lines = ["graph LR"]
    for node, ident in ids.items():
        lines.append(f'  {ident}["{node}"]')
    for edge in edges:
        label = f"|{edge.how}|" if edge.how else ""
        lines.append(f"  {ids[edge.source]} -->{label} {ids[edge.to]}")
    return "\n".join(lines) + "\n"


def render_dot(edges: list[Edge]) -> str:
    lines = ["digraph knowledge {", "  rankdir=LR;"]
    for edge in edges:
        label = f' [label="{edge.how}"]' if edge.how else ""
        lines.append(f'  "{edge.source}" -> "{edge.to}"{label};')
    lines.append("}")
    return "\n".join(lines) + "\n"
