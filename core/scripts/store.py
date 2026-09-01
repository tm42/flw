"""The note store — what an agent worked out, kept where the next one will find it.

Two roots and no index. `~/.flw/kb/` follows the machine; `<project>/plans/notes/`
follows the repository. Both are walked and parsed on every query, which is what buys
the store having no cache, no database and nothing on disk that can go stale against
the files.

A note is a markdown file. Nothing about the format can refuse one: no frontmatter is
valid, and a `+++` block tomllib rejects is read as a note with no frontmatter rather
than raised. That matters more than it looks — the whole store is parsed for every
command, so one hand-written typo would otherwise break every `flw kb` on the machine,
including the opening read three skills make before they start work.

The matcher comes from the ledger unchanged. A note has no structured parts, so it takes
the same `window()` path `plans/*.md` takes there, and a second whole-word matcher would
be a second thing that can disagree about what a word is.
"""

from __future__ import annotations

import json
import re
import textwrap
import tomllib
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from ledger import CAP, WIDTH, _capped, forms, pattern, window

MACHINE = "machine-wide"
PROJECT = "this repository"

# The store root under $FLW_HOME, and the project's, relative to its root.
STORE_DIR = "kb"
PROJECT_STORE = ("plans", "notes")

WORD = re.compile(r"\w+")
FRONTMATTER = re.compile(r"\A\+\+\+[ \t]*\n(.*?)\n\+\+\+[ \t]*\n?", re.DOTALL)
HEADING = re.compile(r"^#[ \t]+(.+?)\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")

# A category with no directory beneath its root. Only reachable by hand: the write
# path always takes a category, and --here resolves to the project's own name.
UNFILED = "(unfiled)"


def _tokens(chars: int) -> str:
    """Size as the thing the reader is actually spending, at four chars a token."""
    n = chars // 4
    return f"{n / 1000:.1f}k tokens" if n >= 1000 else f"{n} tokens"


@dataclass
class Note:
    path: Path
    root: Path
    root_name: str
    category: str
    body: str
    meta: dict = field(default_factory=dict)
    # tomllib's error text when the +++ block did not parse. The note still reads.
    malformed: str | None = None
    # Built on first use and kept. lint compares every note against every other, so
    # rebuilding this per comparison joined the same strings 4,995,000 times over a
    # 1,000-note store — 16 of that run's 31 seconds, before any matching happened.
    _searchable: str | None = field(default=None, repr=False, compare=False)

    @property
    def slug(self) -> str:
        return self.path.stem

    @property
    def title(self) -> str:
        declared = self.meta.get("title")
        if isinstance(declared, str) and declared.strip():
            return declared.strip()
        heading = _first_heading(self.body)
        if heading:
            return heading
        return self.slug.replace("-", " ")

    @property
    def description(self) -> str:
        value = self.meta.get("description")
        return value.strip() if isinstance(value, str) else ""

    @property
    def type(self) -> str:
        value = self.meta.get("type")
        return value.strip() if isinstance(value, str) else ""

    @property
    def tags(self) -> list[str]:
        value = self.meta.get("tags")
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [t for t in value if isinstance(t, str)]
        return []

    @property
    def updated(self) -> date | None:
        """Frontmatter only. mtime is never a date source — a checkout rewrites it,
        and a stale note reading as fresh is worse than one reading as undated."""
        value = self.meta.get("updated")
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value.strip()[:10])
            except ValueError:
                return None
        return None

    @property
    def size(self) -> int:
        return len(self.body)

    def age(self, today: date | None = None) -> str:
        when = self.updated
        if when is None:
            return "undated"
        # The local date, because "168 days ago" is what the reader's calendar
        # says and not what UTC says at 23:30 their time.
        days = ((today or datetime.now().astimezone().date()) - when).days
        if days < 0:
            return f"written {when.isoformat()}"
        unit = "day" if days == 1 else "days"
        return f"written {when.isoformat()} · {days} {unit} ago"

    def stamp(self, today: date | None = None) -> str:
        """Age and size together, which is what makes `show` a decision."""
        return f"{self.age(today)} · {_tokens(self.size)}"

    @property
    def searchable(self) -> str:
        if self._searchable is None:
            parts = [self.title, self.description, self.type, " ".join(self.tags), self.body]
            self._searchable = "\n".join(p for p in parts if p)
        return self._searchable

    @property
    def words(self) -> set[str]:
        r"""Every whole word in the note, casefolded.

        The matcher bounds a term with `(?<!\w)` and `(?!\w)` and ignores case, so a
        single-word term matches exactly when one of its forms *is* one of these —
        which is what lets the duplicate check use set membership instead of running
        a regex over every note for every other note.
        """
        return set(WORD.findall(self.searchable.casefold()))


def _first_heading(body: str) -> str | None:
    """The first `#` outside a fenced block.

    Measured on this repository: of eight markdown files under plans/, one opens with
    an `###` and has its first `#` inside a ```bash fence, so a naive scan titles that
    note with a shell comment.
    """
    fence: str | None = None
    for line in body.splitlines():
        marker = FENCE.match(line)
        if fence is not None:
            if marker and line.strip().startswith(fence):
                fence = None
            continue
        if marker:
            fence = marker.group(1)
            continue
        found = HEADING.match(line)
        if found:
            return found.group(1).strip()
    return None


def _frontmatter(text: str) -> tuple[dict, str, str | None]:
    """(meta, body, malformed). A block that does not parse yields no meta and the
    whole file as body — the note reads exactly as one written without frontmatter."""
    match = FRONTMATTER.match(text)
    if not match:
        return {}, text, None
    try:
        return tomllib.loads(match.group(1)), text[match.end() :], None
    except ValueError as exc:  # TOMLDecodeError is one
        return {}, text, str(exc)


def roots(flw_home: Path, project_root: Path | None) -> list[tuple[Path, str]]:
    found = [(flw_home / STORE_DIR, MACHINE)]
    if project_root is not None:
        found.append((project_root.joinpath(*PROJECT_STORE), PROJECT))
    return found


# What a walk could not read, and why. Returned rather than raised: one bad file
# must not cost the reader the store. Returned rather than dropped: a note that is
# in the store, matches a query and never surfaces, with nothing anywhere saying
# why, is the failure `flw kb lint` exists to prevent.
Skipped = list[tuple[Path, str]]


def walk(
    flw_home: Path,
    project_root: Path | None,
    project_category: str = "",
    here: bool = False,
    globally: bool = False,
    skipped: Skipped | None = None,
) -> list[Note]:
    """Every note under both roots. Nothing here may raise on one bad file.

    Pass a list as `skipped` to be told what could not be read; omit it and the
    behaviour is exactly as before.
    """
    notes: list[Note] = []
    for root, name in roots(flw_home, project_root):
        if here and name != PROJECT:
            continue
        if globally and name != MACHINE:
            continue
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                # One unreadable file must not cost the reader every other note —
                # but it is named, not swallowed.
                if skipped is not None:
                    skipped.append((path, str(exc)))
                continue
            meta, body, malformed = _frontmatter(text)
            relative = path.parent.relative_to(root).as_posix()
            if relative == ".":
                # No directory beneath the root: the project's store takes the
                # project's own name, the machine's has nothing to take.
                relative = project_category if name == PROJECT else ""
            notes.append(
                Note(
                    path=path,
                    root=root,
                    root_name=name,
                    category=relative or UNFILED,
                    body=body,
                    meta=meta,
                    malformed=malformed,
                )
            )
    return notes


def filtered(
    notes: list[Note],
    category: str = "",
    tags: list[str] | None = None,
    type_: str = "",
) -> list[Note]:
    """ANDed. The category is a prefix, so -c python catches python/pandas."""
    out = notes
    if category:
        prefix = category.strip("/")
        out = [
            n
            for n in out
            if n.category == prefix or n.category.startswith(prefix + "/")
        ]
    for tag in tags or []:
        out = [n for n in out if tag in n.tags]
    if type_:
        out = [n for n in out if n.type == type_]
    return out


def _by_recency(notes: list[Note]) -> list[Note]:
    """Most recently updated first; undated last, then by slug so it is stable."""
    return sorted(
        notes,
        key=lambda n: (n.updated is None, -(n.updated.toordinal() if n.updated else 0), n.slug),
    )


def group(notes: list[Note], project_category: str = "") -> list[tuple[str, list[Note]]]:
    """By category, the project's first, then the rest by size then name."""
    buckets: dict[str, list[Note]] = {}
    for note in notes:
        buckets.setdefault(note.category, []).append(note)
    ordered = sorted(
        buckets.items(),
        key=lambda kv: (kv[0] != project_category, -len(kv[1]), kv[0]),
    )
    return [(name, _by_recency(items)) for name, items in ordered]


def search(notes: list[Note], terms: list[str]) -> list[Note]:
    """Terms ANDed across a whole note. A note is one document and its terms are
    rarely adjacent, so this never matches within a line."""
    patterns = [pattern(t) for t in terms]
    return [n for n in notes if all(p.search(n.searchable) for p in patterns)]


# The project's category, then this many more. Categories are freeform, so a cap on
# hits inside one bounds nothing: at ~316 chars a windowed hit and five per category,
# eighteen matching categories is ~7,110 tokens — an answer larger than the skill that
# asked for it.
CATEGORY_CAP = 4


def _headline(note: Note, today: date | None = None) -> str:
    bits = [note.type, note.stamp(today)] if note.type else [note.stamp(today)]
    return f"{note.title}  ({' · '.join(bits)})"


def render_search(
    grouped: list[tuple[str, list[Note]]],
    terms: list[str],
    today: date | None = None,
) -> str:
    if not grouped:
        return "nothing matched."
    patterns = [pattern(t) for t in terms]
    shown = grouped[: CATEGORY_CAP + 1]
    rest = grouped[CATEGORY_CAP + 1 :]
    lines: list[str] = []
    for name, notes in shown:
        root_names = sorted({n.root_name for n in notes})
        lines.append(f"{name}  ·  {', '.join(root_names)}")
        for note in notes[:CAP]:
            lines.append(f"  {_headline(note, today)}")
            lines.append(window(note.searchable, patterns))
            lines.append(f"    {note.path}")
        if len(notes) > CAP:
            lines.append(f"    … {len(notes) - CAP} more in {name}.")
        lines.append("")
    if rest:
        total = sum(len(n) for _, n in rest)
        names = ", ".join(name for name, _ in rest[:CAP])
        lines.append(
            f"… {total} more in {len(rest)} categories ({names}). "
            f"Narrow with -c <category>."
        )
    return "\n".join(lines).rstrip()


def render_tree(
    grouped: list[tuple[str, list[Note]]], today: date | None = None
) -> str:
    lines: list[str] = []
    for name, notes in grouped:
        count = f"{len(notes)} note" + ("" if len(notes) == 1 else "s")
        lines.append(f"{name}{' ' * max(1, 58 - len(name))}{count}")
        for note in notes:
            lines.append(f"  {_headline(note, today)}")
            if note.description:
                lines.append(
                    textwrap.fill(
                        note.description,
                        width=WIDTH,
                        initial_indent="    ",
                        subsequent_indent="    ",
                    )
                )
        lines.append("")
    return "\n".join(lines).rstrip() or "no notes."


def render_index(
    grouped: list[tuple[str, list[Note]]], today: date | None = None
) -> str:
    """One category's contents, capped. What `flw kb -c <category>` prints."""
    lines: list[str] = []
    for name, notes in grouped:
        count = f"{len(notes)} note" + ("" if len(notes) == 1 else "s")
        lines.append(f"{name}{' ' * max(1, 58 - len(name))}{count}")
        lines.extend(_capped([_headline(n, today) for n in notes], "notes"))
        lines.append("")
    return "\n".join(lines).rstrip() or "no notes."


def render_stats(notes: list[Note]) -> str:
    """What a bare `flw kb` prints: the shape of the store, not its contents."""
    if not notes:
        return "no notes in either root."
    lines: list[str] = []
    for root_name in (MACHINE, PROJECT):
        here = [n for n in notes if n.root_name == root_name]
        if not here:
            continue
        cats = sorted({n.category for n in here})
        plural = "category" if len(cats) == 1 else "categories"
        lines.append(
            f"{root_name}{' ' * max(1, 18 - len(root_name))}"
            f"{len(here)} notes · {len(cats)} {plural}"
        )
        tags: dict[str, int] = {}
        types: dict[str, int] = {}
        for note in here:
            for tag in note.tags:
                tags[tag] = tags.get(tag, 0) + 1
            if note.type:
                types[note.type] = types.get(note.type, 0) + 1
        for label, counts in (("tags", tags), ("types", types)):
            if not counts:
                continue
            ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
            head = " · ".join(f"{k} {v}" for k, v in ranked[:CAP])
            tail = f" · … {len(ranked) - CAP} more" if len(ranked) > CAP else ""
            lines.append(f"  {label}   {head}{tail}")
    return "\n".join(lines)


def render_paths(notes: list[Note]) -> str:
    return "\n".join(str(n.path) for n in notes)


def nothing_matched(notes: list[Note], everything: list[Note], narrowed: bool) -> str:
    """Which emptiness this is, or "" when the answer is not empty.

    An empty store and a filter that matched nothing printed the same line, so
    `flw kb -s -t nosuchtag` said "no notes in either root" while both roots held
    notes. Naming the difference is what tells a reader whether to write a note or
    to fix the query — and three skills open with `flw kb -c <category>`, where a
    wrong category name is the likeliest reason for an empty answer.
    """
    if notes:
        return ""
    if not everything:
        return "no notes in either root."
    if not narrowed:
        return "no notes."
    held = len(everything)
    return (
        f"nothing matched. The store holds {held} "
        + ("note" if held == 1 else "notes")
        + " that your filters excluded — check the category and tag names above."
    )


def show(notes: list[Note], name: str, today: date | None = None) -> tuple[str, int]:
    """One note whole. A bare slug in two categories prints both rather than
    guessing which was meant — guessing is how a lookup starts answering a
    question nobody asked."""
    wanted = name.strip().removesuffix(".md")
    if "/" in wanted:
        category, _, slug = wanted.rpartition("/")
        matches = [n for n in notes if n.slug == slug and n.category == category]
    else:
        matches = [n for n in notes if n.slug == wanted]
    if not matches:
        return f"no note called {name!r} in either root.", 1
    blocks = []
    for note in matches:
        blocks.append(
            f"{note.category}/{note.slug}  ·  {note.root_name}\n"
            f"{note.path}\n"
            f"{note.stamp(today)}\n"
            + ("-" * WIDTH)
            + f"\n{note.body.strip()}"
        )
    if len(matches) > 1:
        head = (
            f"{len(matches)} notes are called {wanted!r}. "
            f"Name one as <category>/{wanted} for a single answer.\n"
        )
        return head + ("\n\n".join(blocks)), 0
    return blocks[0], 0


# --- writing ---------------------------------------------------------------- #

# Unicode word characters, not [^a-z0-9]+. That stripped every character outside
# ASCII, so `Кэш прокси всегда пустой` became `note.md` and the next Russian title
# in that category was refused as a duplicate of it, naming an unrelated note to go
# and edit. The stem is the note's identity, and for any script but Latin it carried
# none of the title. ASCII titles slug identically except that `_` survives.
SLUG_STRIP = re.compile(r"[^\w]+")



def category_parts(category: str) -> list[str]:
    """A category as path components, or a ValueError naming what is wrong.

    `joinpath` does not resolve `..`, so an unchecked category escapes the store:
    `flw kb write '../../othertree' README` wrote the note over a real README.md
    beside the root, at exit 0, and every read surface then reported the store as
    not holding it. An absolute category was already harmless — an empty leading
    component is dropped — so this refuses the two that are not.

    It is also what the taken-slug refusal must compare against. `python/` and
    `./python` name the directory `python` and did not match the category `walk`
    derives from the path, so the refusal passed and the existing note's body was
    overwritten at exit 0.
    """
    parts = [part for part in category.split("/") if part and part != "."]
    if any(part == ".." for part in parts):
        raise ValueError(f"a category cannot climb out of the store: {category!r}")
    return parts


def slug(title: str) -> str:
    """A filename from a title. Identity is this stem, never re-derived after."""
    made = SLUG_STRIP.sub("-", title.strip().casefold()).strip("-")
    return made or "note"


def title_terms(title: str) -> list[str]:
    """The words of a title worth matching on.

    The length floor keeps a title of only short words from being compared against
    everything holding `a`. Under the AND it does not otherwise narrow much: extra
    terms only ever restrict.
    """
    return [w for w in SLUG_STRIP.sub(" ", title.casefold()).split() if len(w) > 3]


def near_duplicates(notes: list[Note], title: str) -> list[Note]:
    """What already matches the title's terms.

    This only covers notes written through the command, and writing the file
    directly is the point — so the same search runs again in `flw kb lint`, over
    the whole store.
    """
    terms = title_terms(title)
    if not terms:
        return []
    patterns = [pattern(t) for t in terms]
    # all(), not any() — which is what search() does and what "by the write path's
    # own search" reads as. ORing matched a note that shared one word of a title
    # anywhere in its body, so over a 156-note store built from this repository's
    # own prose, "uv makes a venv without pip" named 54 of 156 as already written
    # and lint reported 7,898 of 12,090 possible pairs. The colliding words were
    # `with`, `need`, `only` and `than`: stopwords of four and five letters, which
    # the length floor below is exactly long enough to admit.
    return [n for n in notes if all(p.search(n.searchable) for p in patterns)]


def write(
    root: Path,
    category: str,
    title: str,
    description: str,
    body: str,
    type_: str = "",
    tags: list[str] | None = None,
    today: date | None = None,
) -> tuple[Path, str]:
    """Emit one note, and never over anything already at its path.

    Every other refusal is the caller's and is made before this is reached. This
    one cannot be: the caller reads the store through `walk`, and `walk` skips a
    path that fails `is_file()` or `read_text` — which is exactly a dangling
    symlink and a symlink to a file that is not UTF-8. Those are the two shapes
    that arrive here with something already at the path, and writing through
    either one replaced a file outside the store.
    """
    when = today or datetime.now().astimezone().date()
    # json.dumps, not an f-string: a JSON string literal is a valid TOML basic
    # string for every input, and the free-text fields are free text. An
    # unescaped `"` in a description — `Field(discriminator="kind") needs a
    # Literal` — wrote a block tomllib then refused, so the note flw had just
    # written read back as one with no frontmatter and the description the
    # command required was gone. A newline injected whatever keys followed it.
    meta = [
        f"title       = {json.dumps(title)}",
        f"description = {json.dumps(description)}",
    ]
    if type_:
        meta.append(f"type        = {json.dumps(type_)}")
    if tags:
        rendered = ", ".join(json.dumps(t) for t in tags)
        meta.append(f"tags        = [{rendered}]")
    meta.append(f"updated     = {when.isoformat()}")

    path = root.joinpath(*category_parts(category)) / f"{slug(title)}.md"
    # is_symlink() as well as exists(), because a dangling symlink is not
    # exists() and writing through one creates the file it points at, which is
    # anywhere at all rather than anywhere in the store.
    if path.exists() or path.is_symlink():
        raise ValueError(f"{path} already holds something flw did not write")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "+++\n" + "\n".join(meta) + "\n+++\n\n" + body.strip() + "\n"
    path.write_text(text, encoding="utf-8")
    return path, _tokens(len(text))


# --- lint ------------------------------------------------------------------- #


def _duplicate_pairs(notes: list[Note]) -> list[str]:
    """Every pair where one note's title terms all appear in the other.

    The same answer `near_duplicates` gives, reached by an inverted index rather
    than by running each title's patterns over every other note. That was
    4,995,000 regex searches over a 1,000-note store and 15.2 seconds; the index
    is bounded by the store's vocabulary, which grows far slower than its note
    count. `_duplicates_match_the_reference` in the suite pins the two together.
    """
    postings: dict[str, set[int]] = {}
    for i, note_ in enumerate(notes):
        for word in note_.words:
            postings.setdefault(word, set()).add(i)

    def matching(term: str) -> set[int]:
        found: set[int] = set()
        for form in forms(term):
            found |= postings.get(form, set())
        return found

    seen: set[tuple[str, str]] = set()
    pairs: list[str] = []
    for i, note_ in enumerate(notes):
        terms = title_terms(note_.title)
        if not terms:
            continue
        hits = set.intersection(*(matching(t) for t in terms))
        for j in sorted(hits - {i}):
            other = notes[j]
            pair = tuple(
                sorted((f"{note_.category}/{note_.slug}", f"{other.category}/{other.slug}"))
            )
            if pair in seen:
                continue
            seen.add(pair)
            pairs.append(f"{pair[0]}  ~  {pair[1]}")
    return pairs


def lint(notes: list[Note], today: date | None = None, skipped: Skipped | None = None) -> str:
    """Pruning without flw making a judgment call. It reports; an agent or a human
    fixes — the same lane as flw-review and flw doctor.

    Every check is mechanical and deterministic. Nothing here is a verdict: a note
    is not broken for being old, and the cheapest way to green a failing note check
    is to delete notes.
    """
    if not notes and not skipped:
        return "no notes in either root."

    rows: list[tuple[str, list[str]]] = []

    rows.append(
        ("unreadable", [f"{path} — {error}" for path, error in skipped or []])
    )

    rows.append(
        ("undescribed", [
            f"{n.category}/{n.slug}" for n in notes if not n.description
        ])
    )
    rows.append(("undated", [f"{n.category}/{n.slug}" for n in notes if n.updated is None]))
    rows.append(
        ("unparseable frontmatter", [
            f"{n.category}/{n.slug} — {n.malformed}" for n in notes if n.malformed
        ])
    )

    stems: dict[str, list[Note]] = {}
    for note_ in notes:
        stems.setdefault(note_.slug, []).append(note_)
    rows.append(
        ("ambiguous slugs", [
            f"{slug_}: " + ", ".join(sorted(n.category for n in found))
            for slug_, found in sorted(stems.items())
            if len(found) > 1
        ])
    )

    rows.append(("near-duplicates", _duplicate_pairs(notes)))

    # Under the machine-wide root only. §4 refuses mtime as an age source because
    # git sets it to checkout time, and the project root is versioned by
    # definition: a clone taken minutes ago would report every note in it, and a
    # check that fires on everything is a check nobody reads.
    stale: list[str] = []
    for note_ in notes:
        if note_.root_name != MACHINE or note_.updated is None:
            continue
        try:
            touched = datetime.fromtimestamp(
                note_.path.stat().st_mtime
            ).astimezone().date()
        except OSError:
            continue
        if touched > note_.updated:
            stale.append(
                f"{note_.category}/{note_.slug} — stamped {note_.updated}, "
                f"edited {touched}"
            )
    rows.append(("edited since stamped", stale))

    lines: list[str] = []
    for name, found in rows:
        if not found:
            continue
        lines.append(f"{name}  ({len(found)})")
        lines.extend(_capped(sorted(found), name))
        lines.append("")
    if not lines:
        return f"{len(notes)} notes, nothing to report."
    lines.append(
        "Nothing here is broken. `edited since stamped` runs under ~/.flw/kb/ only, "
        "because a versioned root reports every note in a fresh clone."
    )
    return "\n".join(lines)
