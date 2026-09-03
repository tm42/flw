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
true at; the check is `git diff --numstat <revision> -- <path>` in that file's
own repository — the revision against the working tree, so an uncommitted edit
counts — and what it reports is how much moved, not whether the claim survived. `3 files · +41 −12` tells a reader what a classifier would have
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

# The frontmatter value this module is allowed to touch. Everything else in the
# block is the author's, byte for byte — which is why the match stops at the
# closing quote or brace and not at the end of the line: a trailing comment on
# the revision line is the author's too. Leading whitespace is captured and
# kept rather than matched away, so an indented key is rewritten in place
# instead of being duplicated at the block's own margin.
REVISION = re.compile(
    r"^([ \t]*)revision[ \t]*=[ \t]*(?:\"[^\"\n]*\"|'[^'\n]*'|\{[^}\n]*\})",
    re.MULTILINE,
)
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
    # By name.
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


def _reachable(root: Path, given: Path) -> list[Path]:
    """Where a relative argument could mean, in the order it is tried.

    The working directory first and the root second, so that both `flw know
    src/engine.py` from inside a repository and `flw know api/orders.py --root
    shop` from its parent name the file the caller meant.
    """
    return [given] if given.is_absolute() else [Path.cwd() / given, root / given]


def under(root: Path, given: Path) -> Path | None:
    """`given` relative to `root` and in the code, or None. Never raises.

    Existence is part of the question, not a check after it: from a parent,
    every member joins with every relative path, so a candidate that is not on
    disk would put the caller's path under whichever member came first.
    """
    root = root.resolve()
    for candidate in _reachable(root, given):
        resolved = candidate.resolve()
        if not resolved.exists():
            continue
        try:
            rel = resolved.relative_to(root)
        except ValueError:
            continue
        return rel if rel != Path() else Path(".")
    return None


def member_for(root: Path, members: dict[str, Path], given: Path) -> Path:
    """Which declared member a path names, seen from the parent.

    The working-directory form first and alone: when `<cwd>/given` exists the
    caller meant that file, and reading the same string under each member would
    answer with somewhere else entirely — which is how `flw know .` from a
    parent answered with the first member declared. Only when the cwd form does
    not exist is the string tried under the members, and then several members
    holding it is an ambiguity to name rather than a race declaration order
    settles.
    """
    roots = [path for path in members.values() if path.is_dir()]
    here = given if given.is_absolute() else Path.cwd() / given
    if here.exists():
        owners = [path for path in roots if under(path, here) is not None]
    else:
        owners = [path for path in roots if (path / given).exists()]
    if not owners:
        raise Refused(f"{given} is under no repository {root.name} declares")
    if len(owners) > 1:
        names = ", ".join(sorted(path.name for path in owners))
        raise Refused(
            f"{given} is under more than one repository {root.name} declares: "
            f"{names}. Name the one you mean with --root."
        )
    return owners[0]


def relative_to_root(root: Path, given: Path) -> Path:
    """`under`, with the two refusals told apart.

    A path outside the root is a typo or the wrong `--root`; a path that is not
    in the code is a typo or a rename that already orphaned its knowledge.
    """
    found = under(root, given)
    if found is not None:
        return found
    root = root.resolve()
    if any(candidate.resolve().exists() for candidate in _reachable(root, given)):
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
    """(exit code, stdout — or, when it failed, what git said). Every git call
    in this module goes through here.

    One function, so a test replaces one thing and no test in the suite runs
    git. Git is hardcoded for now because it is what the first system to use
    this store runs; a second VCS is two config keys later and not a redesign.

    A failure carries stderr rather than the empty stdout it also has, because
    a refusal that quotes git sends the reader where the problem is; discarding
    it sent them to look for a HEAD the repository does not have.
    """
    try:
        done = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
        )
    except OSError as exc:  # git absent, cwd gone
        return 127, str(exc)
    return done.returncode, done.stdout if done.returncode == 0 else done.stderr


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
    """`git diff --numstat <revision> -- <rel>`, summed, plus untracked paths.

    The revision against the working tree and not against HEAD, so an
    uncommitted edit under the path counts and the answer is right while the
    tree is dirty — which is the state a checkout is in for the whole of a
    working session. A file the tree has gained since the revision and the
    VCS does not ignore is a change too, even though `git diff` alone does not
    see it: `git ls-files --others --exclude-standard -- <rel>` finds it, and
    each line is one more changed file with no insertions or deletions, the
    way a binary file's `-\t-` row already counts as one change with no
    lines. `--exclude-standard` is what keeps an ignored store from counting
    itself — the project's own ignore rules decide, not a second policy here.

    No output from either call is current; any output is changed. There is no
    classification: a function-body edit and a new directory both count, and
    the numbers say which it was. A diff that cannot run — not a repository, a
    hash gone after a rebase — is unverifiable, and the file is read
    normally. A failed ls-files call adds nothing: the diff already ran and
    stands on its own.

    `--end-of-options` because the revision comes out of a file's frontmatter,
    which anyone with write access to the store authors: without it a value
    beginning with `-` reaches git as an option and steers the command that is
    supposed to be reading it.
    """
    code, out = git(["diff", "--numstat", "--end-of-options", revision, "--", rel.as_posix()], cwd)
    if code != 0:
        return Diff("unverifiable")
    lines = [line for line in out.splitlines() if line.strip()]
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
    files = len(lines)

    untracked_code, untracked_out = git(
        ["ls-files", "--others", "--exclude-standard", "--", rel.as_posix()], cwd
    )
    if untracked_code == 0:
        untracked = [line for line in untracked_out.splitlines() if line.strip()]
        files += len(untracked)
        if untracked and not first:
            first = untracked[0]

    if files == 0:
        return Diff("current")
    return Diff("changed", files, insertions, deletions, first)


def changed(concept: Concept) -> Diff:
    """One file's staleness. `system.md` goes through `changed_system` instead."""
    if concept.level == "System":
        raise Refused(
            f"{concept.root}: a directory named system has no store — its "
            "repository file and the system file share a name"
        )
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
        said = out.strip().splitlines()
        detail = f": {said[0]}" if said else ""
        raise Refused(
            f"{root}: git rev-parse HEAD failed{detail}; nothing was written"
        )
    return out.strip().splitlines()[0]


def dirty(root: Path, rel: Path) -> bool:
    """Whether the mirrored path has uncommitted changes in its own repository.

    A stamp records HEAD, so a dirty mirror means the file was read against a
    tree that HEAD does not describe. It is a warning and not a refusal: a
    checkout at work is dirty most of the time, and refusing would stop
    research on it for a stamp that is wrong by exactly what the warning names.
    """
    code, out = git(["status", "--porcelain", "--", rel.as_posix()], root)
    return code == 0 and bool(out.strip())


def _rewrite(block: str, line: str) -> str:
    """`block` with its `revision` value replaced, or the line inserted.

    Inserted before the first table header rather than at the very end of the
    block: a file whose frontmatter ends in `[[connects]]` would otherwise get
    its revision keyed inside that table, which parses as a different document.
    """
    if REVISION.search(block):
        return REVISION.sub(lambda m: m.group(1) + line, block, count=1)
    lines = block.splitlines()
    cut = next((i for i, text in enumerate(lines) if TABLE.match(text)), len(lines))
    while cut > 0 and not lines[cut - 1].strip():
        cut -= 1
    return "\n".join([*lines[:cut], line, *lines[cut:]])


def _revision_value(concept: Concept, members: dict[str, Path], resolve) -> str | dict:
    """What this file's `revision` should now be: a string, or a member table.

    For `system.md` every declared member is re-stamped from its own
    repository, and every key naming no declared member is left exactly as it
    is — the store reports an undeclared key and never rewrites one.
    """
    if concept.level != "System":
        return resolve(concept.root)

    known = members_by_basename(members)
    table = concept.revision if isinstance(concept.revision, dict) else {}
    values: dict[str, str] = {}
    for key, value in table.items():
        values[key] = resolve(known[key]) if key in known else str(value)
    for name, path in known.items():
        values.setdefault(name, resolve(path))
    return values


def _revision_line(value: str | dict) -> str:
    if isinstance(value, dict):
        body = ", ".join(f'{key} = "{item}"' for key, item in value.items())
        return f"revision = {{ {body} }}"
    return f'revision = "{value}"'


def _dirty_subject(concept: Concept, members: dict[str, Path]) -> str:
    """What to name in the warning: the mirrored path, or the dirty members.

    Empty when nothing is dirty. A repository file and `system.md` both mirror
    a whole tree, so naming `.` would tell the reader nothing — the repository
    or the member is what they would go and look at.
    """
    if concept.level == "System":
        names = [
            name
            for name, path in members_by_basename(members).items()
            if dirty(path, Path("."))
        ]
        return ", ".join(sorted(names))
    rel = mirror(concept.store, concept.root, concept.path)
    if not dirty(concept.root, rel):
        return ""
    return concept.root.name if rel == Path(".") else rel.as_posix()


def _read_for_stamp(path: Path) -> tuple[str, bool]:
    """(text with LF endings, whether the file was CRLF).

    Read without newline translation so the endings survive the round trip:
    a stamp writes one value and may not reformat the rest of the file, and
    line endings are part of the rest of the file.
    """
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            raw = handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise Refused(f"{path}: cannot read: {exc}") from None
    crlf = "\r\n" in raw
    return (raw.replace("\r\n", "\n"), crlf) if crlf else (raw, False)


def _stamped(path: Path, store: Path, root: Path, members: dict[str, Path], resolve):
    """(text to write, whether it was CRLF, what is dirty) for one file.

    Every refusal a stamp can raise happens here, before anything is written —
    so a batch that fails has changed nothing, and neither has a file whose
    rewritten block would no longer say what was written into it.
    """
    text, crlf = _read_for_stamp(path)
    match = FRONTMATTER.match(text)
    if not match:
        raise Refused(f"{path}: no +++ frontmatter block to stamp")
    block = match.group(1)
    try:
        tomllib.loads(block)
    except ValueError as exc:
        raise Refused(f"{path}: the +++ block does not parse: {exc}") from None

    concept = load(path, store, root)
    value = _revision_value(concept, members, resolve)
    rewritten = _rewrite(block, _revision_line(value))
    # The one check that catches a spelling the line-level rewrite could not
    # see — a [revision] section, or a revision inside a [[connects]] table —
    # each of which parsed before and says something else after. The file is
    # refused and left exactly as it was.
    try:
        after = tomllib.loads(rewritten)
    except ValueError as exc:
        raise Refused(f"{path}: stamping it would break the +++ block: {exc}") from None
    if after.get("revision") != value:
        raise Refused(
            f"{path}: stamping it would not set the top-level revision — the "
            "block spells it somewhere this cannot reach; nothing was written"
        )
    return (
        text[: match.start(1)] + rewritten + text[match.end(1) :],
        crlf,
        _dirty_subject(concept, members),
    )


def stamp_all(
    items: list[tuple[Path, Path, Path, dict[str, Path]]],
) -> list[tuple[Path, str]]:
    """Stamp files spanning several stores. (path, store, root, members) each.

    Returns (path, what is dirty) per file, the second empty when the mirror is
    clean. A textual edit of one value, never a re-serialisation: the rest of
    the block is the author's comments, key order and spacing, and a round trip
    through tomllib would silently reflow all three.

    Every HEAD the whole batch needs is resolved before the first write, one
    per repository — otherwise a rev-parse that failed on the fourth file
    reported "nothing was written" having already written three. Which is the
    ordinary shape here: from a parent, `system.md` needs every member's HEAD.
    """
    heads: dict[Path, str] = {}

    def resolve(repo: Path) -> str:
        if repo not in heads:
            heads[repo] = head(repo)
        return heads[repo]

    prepared = [
        (path, *_stamped(path, store, root, members, resolve))
        for path, store, root, members in items
    ]
    written: list[tuple[Path, str]] = []
    for path, text, crlf, subject in prepared:
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text.replace("\n", "\r\n") if crlf else text)
        written.append((path, subject))
    return written


def stamp(
    paths: list[Path], store: Path, root: Path, members: dict[str, Path]
) -> list[tuple[Path, str]]:
    """`stamp_all` for the files of one store. See it for what a stamp does."""
    return stamp_all([(path, store, root, members) for path in paths])


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
    # A store declared as `.` is the repository, so the walk would otherwise
    # write a listing into .git/ and every other dot-directory in the tree.
    inside = (
        p
        for p in store.rglob("*")
        if p.is_dir()
        and not any(part.startswith(".") for part in p.relative_to(store).parts)
    )
    for directory in sorted({store, *inside}):
        target = directory / INDEX
        content = _listing(store, directory, root)
        try:
            unchanged = target.is_file() and target.read_text(encoding="utf-8") == content
        except UnicodeDecodeError:
            # This read only asks whether the file already says what we are
            # about to write. Nothing may trust an index.md, so one that cannot
            # be read is overwritten rather than reported — and it used to
            # traceback out of the walk, leaving every store's listing unwritten.
            unchanged = False
        if unchanged:
            continue
        target.write_text(content, encoding="utf-8")
        written.append(target)
    return written


# --- the fold ---------------------------------------------------------------- #


@dataclass(frozen=True)
class Edge:
    source: str
    to: str
    how: str


def node_of(store: Path, root: Path, path: Path) -> str:
    """A concept file's node name: a repo basename, or basename/area-path."""
    level = level_of(store, root, path)
    if level in ("System", "Repository"):
        return root.name
    return f"{root.name}/{mirror(store, root, path).as_posix()}"


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
                    Edge(node, to.strip(), str(table.get("how", "")).strip())
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


def _col(text: str, width: int) -> str:
    """Left-aligned in `width`, always followed by at least one space.

    `ljust` alone lets a value exactly as wide as its column run into the next
    one, which is how `unverifiable` — twelve characters in a twelve-wide
    status column — printed with the detail glued to it.
    """
    return f"{text:<{width - 1}} "


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
    system: Concept | None,
    members: list[tuple[str, Concept | None, str]],
    changes: dict[str, Diff],
    where: str,
) -> str:
    """A parent's orientation: the system file, then one head per member.

    The one place a reader meets a whole system, and where most work stops —
    which is why it prints descriptions and edges and never a body.
    """
    lines = [f"system: {name} {DASH} {len(members)} roots {DASH} {where}"]
    if system is not None:
        lines += _wrap(system.description, "  ", "  ")
    lines.append("")
    for member, concept, reason in members:
        if concept is None:
            lines.append(f"  {_col(member, 10)}({reason})")
            continue
        lines += _wrap(concept.description, f"  {_col(member, 10)}", " " * 12)
        lines += _edge_lines(concept, " " * 12)
    lines.append("")
    count = len([c for _, c, _ in members if c is not None])
    noun = "file" if count == 1 else "files"
    moved = len([d for d in changes.values() if d.state == "changed"])
    lines.append(
        f"{count} repo {noun}, each in its own repo's store {DASH} {moved} changed"
    )
    return "\n".join(lines) + "\n"


def render_repo_orientation(
    name: str, concept: Concept | None, diff: Diff, where: str
) -> str:
    """A repository standing alone: its own file, and nothing walked upward.

    Nothing looks for a parent that claims this repository. Standing inside a
    member, flw sees that member alone; the system is seen by naming its root.
    """
    if concept is None:
        return f"repo: {name} {DASH} {where}\n\n0 repo files {DASH} 0 changed\n"
    lines = [f"repo: {name} {DASH} {where}"]
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
            f"  {_col(concept.rel, 27)}{_col(SHORT[concept.level], 7)}"
            f"{_col(revision or '—', 10)}{_walk_status(diff, revision)}"
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
            f"  {_col(row.root, 10)}{_col(row.file, 27)}"
            f"{_col(row.state, 12)}{row.detail}".rstrip()
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
        lines.append(f"  {_col(edge.source, 12)}{_col(_arrow(edge.how), 13)}{edge.to}")
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
    for heading, group in (("in", inbound), ("out", outbound)):
        for i, edge in enumerate(group):
            label = heading if i == 0 else ""
            lines.append(
                f"  {_col(label, 6)}{_col(edge.source, 10)}"
                f"{_col(_arrow(edge.how), 12)}{edge.to}"
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
