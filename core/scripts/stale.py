"""Which of the project's own documents are spent, and which nobody has read.

flw writes four kinds of document and could close none of them. A review report
is spent the moment a record fixes what it found, and nothing read that back: the
next round was told to read past reports first, so a finding a record had already
overturned came back as live. A knowledge file knows when the code moved under it.
An extension and a note carry no revision by design, so neither can ever say it
drifted.

This is the fold and not a fifth reader. Each store keeps its own lint — `ledger`
holds the extension text and lints it, `knowledge` measures its own files against
the revisions they record, `store` lints the notes — and the only thing here that
nothing else does is list the reports directory, which `ledger.corpus` documents
why it excludes.

**It deletes nothing.** A reports directory is gitignored in most projects, so a
wrong deletion is unrecoverable rather than a revert, and this cannot tell a spent
report from one whose citation it merely failed to parse. flw already draws that
line elsewhere: it stages files and leaves the commit to the user.

Nothing here reaches into `cli`. Every path and setting the fold needs is handed
in, because the import chain runs one way — `validate_spec <- ledger <- store <-
knowledge` — and this module sits above all of it.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

import knowledge
import ledger
import store as note_store
from ledger import WIDTH, _capped

# Where reports live when a project has not said otherwise. Kept as a second
# alternation whatever the project declares, because a project that has moved its
# reports directory still holds records citing the old one.
DEFAULT_REPORTS = ".flw/reports"


def citation(reports_dir: str = DEFAULT_REPORTS) -> re.Pattern[str]:
    """A report path as a record writes it, in `sources` or in prose.

    Built from the directory the fold was handed rather than hardcoded, because
    `[paths] reports` is configurable and a matcher that is not saw every citation
    in such a project as unread — the whole directory, counted as nobody having
    read it.

    The character class after the directory is what a report name is made of: an
    ISO stamp, the lens name, and the `:14` a record sometimes appends to cite one
    line of one. The directory itself reaches the pattern escaped, because a
    project may name it anything and a `.` or `+` in it would otherwise match
    something else.

    A declared directory contributes a pattern only when it is relative and stays
    inside the root. `[paths] reports` is taken raw at `cli/flw.py`, unlike
    `[paths] flw`, which the contract refuses when absolute — so `root / reports_dir`
    discards the root for an absolute value, and a pattern built from a
    machine-specific absolute path matches nothing any record would ever spell.
    Such a project folds on the default alone. Bounding the setting itself is a
    separate change.
    """
    directories = [DEFAULT_REPORTS]
    given = reports_dir.strip().rstrip("/")
    inside = given and not Path(given).is_absolute() and ".." not in Path(given).parts
    if inside and given != DEFAULT_REPORTS:
        directories.append(given)
    body = "|".join(re.escape(d) for d in directories)
    return re.compile(rf"[\w./-]*(?:{body})/[A-Za-z0-9T:._-]+")


# The mark flw-spec writes above a report's own heading: one line naming the
# record specced from it, in backticks.
BACKTICKED = re.compile(r"`([^`]+)`")


@dataclass(frozen=True)
class Reports:
    """One reports directory, split three ways. Counts, and the names behind them."""

    directory: Path
    spent: list[str] = field(default_factory=list)
    unread: list[str] = field(default_factory=list)
    dead: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.spent) + len(self.unread)


def record_names(records: list) -> set[str]:
    """Every record's identity, for reading the mark a report carries."""
    return {r.name for r in records if r.name}


def cited(records: list, pattern: re.Pattern[str] | None = None) -> set[str]:
    """Every report name a record points at, from both places it can point from.

    Both, because a record carries `sources` where it has one and prose where it
    does not, and every record written before that field existed falls to prose. A
    `:14` line anchor is stripped, because it cites a line of a report rather than
    a different report, and a match with no `.md` in it is dropped as an artifact
    of reading prose with a pattern.
    """
    matcher = pattern or citation()
    found: set[str] = set()
    for record in records:
        declared = record.document.get("sources", [])
        given = [s for s in declared if isinstance(s, str)]
        try:
            given += matcher.findall(record.path.read_text(errors="replace"))
        except OSError:
            pass
        for one in given:
            name = one.split("/")[-1].split(":")[0]
            if name.endswith(".md"):
                found.add(name)
    return found


def marked(directory: Path, names: set[str]) -> set[str]:
    """Report names carrying a record's name on the line above their own heading.

    Strictly that line: a report's own title routinely names the record whose work
    it reviewed — `# Adversarial pass — \\`opening-is-one-call\\`` — and that is the
    report of a record rather than a report a record acted on. Reading headings too
    marked 20 of the 66 reports here instead of 3.
    """
    found: set[str] = set()
    for path in sorted(directory.glob("*.md")):
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        first = next((line for line in text.splitlines() if line.strip()), "")
        if first.lstrip().startswith("#"):
            continue
        if any(t in names for t in BACKTICKED.findall(first)):
            found.add(path.name)
    return found


def reports(
    directory: Path, records: list, reports_dir: str = DEFAULT_REPORTS
) -> Reports:
    """Split the reports directory into spent, unread, and dead citations.

    Both directions, because neither is complete on its own. A record can name a
    report that has since been deleted, and a report can carry a record's name
    whose prose never names its path — of the three reports marked here, two are
    cited by no record's prose at all.

    A name a record cites with no file behind it is a dead citation and is counted
    as neither: reports get deleted informally, so a citation is not evidence that
    a file exists.
    """
    if not directory.is_dir():
        return Reports(directory)
    on_disk = {path.name for path in directory.glob("*.md")}
    names = cited(records, citation(reports_dir))
    spent = (names & on_disk) | marked(directory, record_names(records))
    return Reports(
        directory,
        spent=sorted(spent),
        unread=sorted(on_disk - spent),
        dead=sorted(names - on_disk),
    )


@dataclass(frozen=True)
class Knowledge:
    """The knowledge store's own check, counted rather than listed."""

    files: int = 0
    changed: list[str] = field(default_factory=list)
    orphaned: list[str] = field(default_factory=list)
    malformed: list[str] = field(default_factory=list)
    unstamped: list[str] = field(default_factory=list)
    unverifiable: list[str] = field(default_factory=list)


def knowledge_state(
    stores: list[tuple[Path, Path]], members: dict[str, Path]
) -> Knowledge:
    """`flw know --check`'s rows, folded to counts.

    The primitives rather than the CLI's row builder: this needs how many files
    the code has moved under, and that handler renders one line per file. It is
    the same four measurements — `concepts`, `load`, `changed`, `orphans`.

    The state decides which list a file lands in, rather than one state being
    tested and the other two falling through. `Diff.state` is one of four words
    and `system_state` returns the same four, so testing only for `changed` sent
    `unverifiable` to no row at all. That is never one file: a rebase, a squash or
    a force-push invalidates every stamp in the store at once, so the whole store
    read as clean on exactly the run where a reader most needed telling.
    """
    files = 0
    changed: list[str] = []
    orphaned: list[str] = []
    malformed: list[str] = []
    unstamped: list[str] = []
    unverifiable: list[str] = []
    by_state = {"changed": changed, "unstamped": unstamped, "unverifiable": unverifiable}
    for owner, store in stores:
        if not store.is_dir():
            continue
        expected = dict(knowledge.orphans(store, owner))
        for path in knowledge.concepts(store):
            files += 1
            concept = knowledge.load(path, store, owner)
            where = f"{owner.name}/{concept.rel}"
            if path in expected:
                orphaned.append(where)
            elif not concept.listable:
                malformed.append(f"{where} — {concept.problems[0]}")
            elif "unstamped" in concept.problems:
                unstamped.append(where)
            elif concept.level == "System":
                per_member = knowledge.changed_system(concept, members)
                row = by_state.get(knowledge.system_state(per_member))
                if row is not None:
                    row.append(where)
            else:
                diff = knowledge.changed(concept)
                row = by_state.get(diff.state)
                if row is changed:
                    # The one state that carries a measurement. An unverifiable
                    # file carries none, because the revision it names is gone and
                    # there is nothing left to diff it against.
                    changed.append(f"{where} — {diff.summary()}")
                elif row is not None:
                    row.append(where)
    return Knowledge(files, changed, orphaned, malformed, unstamped, unverifiable)


def _rows(lines: list[str], label: str, count: int, entries: list[str], gloss: str = "") -> None:
    """One store's row: the number first, then a capped sample of what is behind it."""
    if not entries:
        return
    suffix = f"  {knowledge.DASH} {gloss}" if gloss else ""
    lines.append(f"  {label}  ({count}){suffix}")
    lines.extend(_capped(entries, label))
    lines.append("")


def render(
    root: Path,
    found: Reports,
    know: Knowledge,
    markers: list,
    note_claims: list[str],
    note_count: int,
) -> str:
    """One block, a row per store. Nothing here is a verdict and nothing is a failure."""
    lines = [f"  root: {root}", ""]

    if found.directory.is_dir():
        lines.append(
            f"REPORTS  ({found.total})  {knowledge.DASH} "
            f"{len(found.spent)} spent, {len(found.unread)} nobody has read"
        )
        lines.append("")
        _rows(lines, "unread", len(found.unread), found.unread)
        _rows(
            lines,
            "dead citations",
            len(found.dead),
            found.dead,
            "a record names it and no file is there",
        )
    else:
        lines += [f"REPORTS  {knowledge.DASH} no {found.directory.name}/ directory", ""]

    if know.files:
        lines.append(f"KNOWLEDGE  ({know.files})")
        lines.append("")
        _rows(lines, "changed under", len(know.changed), know.changed)
        _rows(lines, "orphaned", len(know.orphaned), know.orphaned)
        _rows(lines, "malformed", len(know.malformed), know.malformed)
        _rows(lines, "unstamped", len(know.unstamped), know.unstamped)
        _rows(
            lines,
            "unverifiable",
            len(know.unverifiable),
            know.unverifiable,
            "the revision it records is no longer in the repository",
        )
    else:
        lines += [f"KNOWLEDGE  {knowledge.DASH} no store", ""]

    shown = [f"{m.path.name}:{m.line}  {m.text}" for m in markers]
    lines.append(f"EXTENSIONS  ({len(shown)})")
    lines.append("")
    _rows(
        lines,
        "claims with no revision",
        len(shown),
        shown,
        "a countable in a store that carries none",
    )

    lines.append(f"NOTES  ({note_count})")
    lines.append("")
    _rows(lines, "claims with no revision", len(note_claims), note_claims)

    lines.append(
        textwrap.fill(
            "Nothing here is a failure and nothing was deleted. A report nobody has "
            "read is a backlog item with a decision attached rather than refuse, and "
            "the reports directory is gitignored in most projects, so removing one is "
            "unrecoverable.",
            width=WIDTH,
            initial_indent="  ",
            subsequent_indent="  ",
        )
    )
    return "\n".join(lines) + "\n"


def fold(
    root: Path,
    *,
    specs_dir: str = "specs",
    reports_dir: str = ".flw/reports",
    knowledge_stores: list[tuple[Path, Path]] | None = None,
    members: dict[str, Path] | None = None,
    notes: list | None = None,
) -> str:
    """Every store, read once, rendered as one block.

    The caller resolves the paths and settings, because each of them comes from a
    configuration merge that belongs to the CLI: `[paths] reports`, `[knowledge]
    dir`, `[project] roots` and `[kb] category`.
    """
    corpus = ledger.corpus(root, specs_dir)
    found = reports((root / reports_dir), corpus.records, reports_dir)
    know = knowledge_state(knowledge_stores or [], members or {})
    markers = ledger.extension_markers(corpus)
    given = notes or []
    return render(root, found, know, markers, note_store.unrevisioned(given), len(given))
