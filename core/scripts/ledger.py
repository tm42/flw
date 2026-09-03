#!/usr/bin/env python3
"""The project's own knowledge base: what has been written down, made findable.

flw accumulates reasoning as a byproduct of being used — a decision with the
options it beat, a task description naming the file it changed, an approach
saying what the work was deliberately not — and until this, nothing read any of
it back. A settled decision that cannot be found is a decision that gets made
again, differently.

This reads what was written *about* the work. It never reads the work: `flw
scout` ranks source files and `grep` exists.

Stdlib only, and nothing is written or cached. The corpus parses in well under a
second, and an index on disk is a second copy that goes stale.
"""

from __future__ import annotations

import functools
import os
import re
import textwrap
import tomllib
from dataclasses import dataclass
from pathlib import Path

from validate_spec import LEGACY_NUMBER, Record, load_records


@dataclass(frozen=True)
class Corpus:
    """Everything a query may read, and nothing else.

    The boundary is the whole guarantee: these five tiers, and nothing else under
    the project. It is bounded by directory rather than by what the VCS tracks, so
    an uncommitted file inside one of them is read — the contract carries that as
    an open question. `contract` is empty for a project that has none yet, which
    is an ordinary state rather than a fault.
    """

    root: Path
    contract: dict
    records: list[Record]
    reviews: dict[Path, dict]
    extensions: dict[Path, str]
    plans: dict[Path, str]


def corpus(root: Path, specs_dir: str = "specs") -> Corpus:
    """Assemble the corpus for one project.

    Five tiers, and the exclusions matter as much as the inclusions.

    `plans/` means `plans/*.md`. The rendered `.html` beside the markdown says
    the same thing in markup: `plans/code-graph-report.html` alone holds 73
    whole-word occurrences of `font`, so a query for `font` would print CSS.

    Nothing under `.flw/` is read except `reviews/` and `extensions/`. Review
    *reports* live in `.flw/reports/`, which this repository gitignores. A report's
    durable half is copied into a version record's `approach` when the version is
    specced, so what survives is already here.

    Extensions are read from this root and no higher. The chain a skill obeys runs
    from every project root at or above the resolved one, but the corpus is bounded
    by the project directory and a parent root is not under it — so a convention at
    a parent binds every skill here and stays invisible to this search. The spec
    run's reconciliation reads the whole chain, which is where that gap is covered.
    """
    specs = root / specs_dir

    contract: dict = {}
    contract_file = specs / "current.toml"
    if contract_file.exists():
        try:
            contract = tomllib.loads(contract_file.read_text())
        except (tomllib.TOMLDecodeError, UnicodeDecodeError):
            # A malformed contract is validate's finding to report, not this
            # command's to die on. Searching the records without it beats a
            # traceback where an answer was asked for.
            contract = {}

    versions = specs / "versions"
    records = load_records(versions) if versions.is_dir() else []

    flw_dir = os.environ.get("FLW_DIR", ".flw")
    reviews: dict[Path, dict] = {}
    for path in sorted((root / flw_dir / "reviews").glob("*.toml")):
        try:
            reviews[path] = tomllib.loads(path.read_text())
        except (tomllib.TOMLDecodeError, UnicodeDecodeError):
            continue

    extensions = {
        path: path.read_text(errors="replace")
        for path in sorted((root / flw_dir / "extensions").glob("*.md"))
    }

    plans = {
        path: path.read_text(errors="replace")
        for path in sorted((root / "plans").glob("*.md"))
    }

    return Corpus(
        root=root,
        contract=contract,
        records=records,
        reviews=reviews,
        extensions=extensions,
        plans=plans,
    )


# --- matching --------------------------------------------------------------- #


def forms(term: str) -> list[str]:
    """One word, and the handful of shapes English writes it in.

    Not stemming. This expands a term outward; it never reduces two words to a
    shared root, because a root is where a search starts matching things nobody
    asked about. Measured on this repository's records: substring `lock` matches
    16 of 27 — through `block` and `blocked_by` — and whole words with these
    forms match 4.
    """
    word = term.lower().strip()
    if not word:
        # An empty term compiled to an alternation with an empty branch, which
        # matched at every word boundary: `flw ledger ""` printed the whole corpus,
        # and `flw ledger lock ""` printed every unit of every lock-mentioning
        # document because search() prints a hit when *any* pattern matches it.
        return []
    bases = {word}
    for suffix in ("ing", "ed", "es", "s"):
        # `ss` guards `pass` and `class`, which are not plurals of anything. Every
        # candidate base is kept rather than the first: `removes` strips to both
        # `remov` and `remove`, and only the second reaches `remove` itself.
        if word.endswith(suffix) and len(word) - len(suffix) >= 3 and not word.endswith("ss"):
            bases.add(word[: -len(suffix)])
    # Expand the stripped bases, not the word itself once it has been stripped:
    # `removes` is already a form, and re-suffixing it only yields `removeses`.
    expand = bases - {word} or {word}
    out = {word} | expand
    for base in expand:
        if base.endswith("e"):
            # The silent e survives the plural and is dropped before a vowel, so
            # `remove` needs both spellings generated.
            out |= {base + "s", base + "d", base[:-1] + "ing"}
        elif base.endswith(("s", "x", "z", "ch", "sh")):
            out |= {base + "es", base + "ed", base + "ing"}
        else:
            out |= {base + "s", base + "ed", base + "ing"}
    return sorted(out)


# `\b` asserts a word character on the inside of the boundary, so a term edged
# with punctuation can never match — `.flw`, `--all` and `.gitignore` each reached
# nothing. Lookaround asserts only that no word character abuts, which still
# refuses `lock` inside `blocked_by`.
EDGE_L = r"(?<!\w)"
EDGE_R = r"(?!\w)"

# Matches at no position, for a term with no forms to look for.
NEVER = re.compile(r"(?!)")


@functools.lru_cache(maxsize=256)
def pattern(term: str) -> re.Pattern[str]:
    """A term as a whole-word matcher. An argument with a space in it is a phrase.

    Cached because search() and render_search() each build the patterns for the
    same terms. The saving is small and measured: 54.8us to compile against 0.5us
    to look up, one hit per term in a command that runs one query and exits. It is
    here because two call sites build the same thing, not for the pathological
    term length the first version of this docstring cited.
    """
    if " " in term.strip():
        # Prose wraps, so the gap between a phrase's words is any run of
        # whitespace rather than the single space the user typed.
        words = r"\s+".join(re.escape(w) for w in term.split())
        return re.compile(rf"{EDGE_L}{words}{EDGE_R}", re.IGNORECASE)
    found = forms(term)
    if not found:
        return NEVER
    alternatives = "|".join(re.escape(form) for form in found)
    return re.compile(rf"{EDGE_L}(?:{alternatives}){EDGE_R}", re.IGNORECASE)


# --- what a query reads, and what it prints --------------------------------- #

GROUPS = (
    # Binding, then what settled it, then what happened, then what was reasoned.
    # The order is the whole design: it does the work a relevance score would,
    # without inventing a score there is no ground truth to tune.
    "CONTRACT",
    "REMOVED",
    # Binding because a human wrote it, not because a schema checked it. In the
    # first band because a skill reads an extension and obeys it, and the failure
    # this group exists for is a reader finding the contract's sentence and
    # missing the extension that contradicts it.
    "CONVENTIONS",
    "DECISION",
    "CHANGED",
    "DONE",
    "PLANNED",
    "WHY",
    "REVIEWS",
    "PLANS",
)


# Printed under the group's heading. Only one group has ever needed one: an
# extension sits beside the contract in the first band and a reader has to be told
# that it binds for a different reason, or the two read as one authority.
GROUP_NOTE = {
    "CONVENTIONS": "prose a human made binding here. Not a contract sentence, and"
    " nothing validates it.",
}


def decision_parts(decision: dict) -> tuple[tuple[str, str], ...]:
    """A decision as chose / over / because, which is how it was written.

    One builder for both readers: the search prints a decision through `Hit.parts`
    and `--show` prints it through `render_record`, and the two rendered it
    separately and byte-identically until they were joined.
    """
    chosen = decision.get("chosen", "")
    return (
        ("chose", chosen),
        *(("over", o) for o in decision.get("options", []) if o != chosen),
        ("because", decision.get("rationale", "")),
    )


@dataclass(frozen=True)
class Hit:
    """One unit of prose that matched, and where it came from."""

    group: str
    source: str
    label: str
    text: str
    note: str = ""
    parts: tuple[tuple[str, str], ...] = ()

    @property
    def searchable(self) -> str:
        """Everything a query may match, which is more than what gets windowed.

        `source` is in here because a record's name reaches no other tier: it is
        in the document the AND runs over and in no hit, so `flw ledger <record>`
        found the record and then printed nothing from it.
        """
        return f"{self.source}\n{self.label}\n{self.text}\n{self.note}"


@dataclass(frozen=True)
class Document:
    """The unit the AND applies across, and the hits it can print.

    Terms are ANDed over a whole document rather than over each unit, so a query
    for two words finds the record that discusses both even where one is in a
    decision and the other in a task description.
    """

    text: str
    key: tuple
    hits: list[Hit]


def _text_of(value) -> str:
    """Every string anywhere inside a parsed document, for the AND test."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(_text_of(v) for v in value.values())
    if isinstance(value, list):
        return "\n".join(_text_of(v) for v in value)
    return ""


def recency(name: str, applied: list[str]) -> tuple[int, tuple]:
    """Newest first, over a record set that carries two orderings and a third state.

    A record the contract has applied is placed by its position in `applied`,
    which is the only thing that can order a named record — `stale-claims` has no
    number. The legacy records sit before the anchor, are named in `applied`
    nowhere, and order by the number in their filename. A record in neither is in
    flight: written and not yet run, so newer than everything.
    """
    if name in applied:
        return (2, (applied.index(name),))
    if LEGACY_NUMBER.match(name):
        return (1, tuple(int(part) for part in name.split(".")))
    return (3, ())


def built(name: str, applied: list[str]) -> bool:
    """Whether a record's work has landed, over the same three states recency() sorts.

    Applied is the ordinary yes. Legacy is also yes: those records shipped before
    the applied list existed and no list will ever name them, so testing `in
    applied` alone drops them — 9 records carrying 78 of this repository's 524
    task descriptions, which would fall out of both the built and the planned
    count rather than into one of them.
    """
    return name in applied or bool(LEGACY_NUMBER.match(name))


def documents(corpus_: Corpus) -> list[Document]:
    """The corpus as things that match, each carrying the units it would print."""
    applied = list(corpus_.contract.get("applied", []))
    out: list[Document] = []

    contract_hits: list[Hit] = []
    final_state = corpus_.contract.get("final_state", {})
    for component in final_state.get("components", []):
        where = f"current.toml · {component.get('name', '')}"
        for path in component.get("paths", []):
            # A path is the most concrete thing a component says. Without this
            # `flw ledger core/scripts/scout.mjs` reaches nothing, because a path
            # appears in no other tier.
            contract_hits.append(Hit("CONTRACT", where, "paths", path))
        for key in ("provides", "properties", "surfaces"):
            for line in component.get(key, []):
                contract_hits.append(Hit("CONTRACT", where, key, line))
        if component.get("implementation"):
            contract_hits.append(
                Hit("CONTRACT", where, "implementation", component["implementation"])
            )
    for line in corpus_.contract.get("assumptions", []):
        contract_hits.append(Hit("CONTRACT", "current.toml", "assumption", line))
    for line in corpus_.contract.get("open_questions", []):
        contract_hits.append(Hit("CONTRACT", "current.toml", "open question", line))
    for entry in final_state.get("removed", []):
        contract_hits.append(
            Hit("REMOVED", "current.toml", "", entry.get("statement", ""), entry.get("check", ""))
        )
    if contract_hits:
        out.append(Document(_text_of(corpus_.contract), (0, ()), contract_hits))

    for record in corpus_.records:
        document = record.document
        hits: list[Hit] = []
        for decision in document.get("decisions", []):
            parts = decision_parts(decision)
            # The topic is the most searchable line a decision has — it is the
            # question somebody would type. Matching only the body missed it.
            body = "\n".join([decision.get("topic", "")] + [v for _, v in parts])
            hits.append(
                Hit("DECISION", record.name, decision.get("topic", ""), body, parts=parts)
            )
        if document.get("contract_edit"):
            # The classification prints on every CHANGED hit because this group's
            # whole reason to exist beside CONTRACT is saying which version
            # introduced a sentence and what kind of change it was.
            hits.append(
                Hit("CHANGED", record.name, "", document["contract_edit"], record.classification or "")
            )
        # A task from a record nobody has run describes work that does not exist.
        # Printed under DONE it answered "is this written?" with yes: a search for
        # a function named only in an unrun record's dag came back under that
        # heading with nothing saying the record had not run.
        task_group = "DONE" if built(record.name, applied) else "PLANNED"
        for group in document.get("dag", []):
            # The phase rides in `note`: it is the last thing a record writes
            # that reached no hit, and printing it says which phase a task
            # belonged to, which the id alone does not.
            phase = group.get("phase", "")
            for task in group.get("tasks", []):
                hits.append(
                    Hit(task_group, record.name, task.get("id", ""), task.get("desc", ""), phase)
                )
        if document.get("summary"):
            hits.append(Hit("WHY", record.name, "summary", document["summary"]))
        if document.get("approach"):
            hits.append(Hit("WHY", record.name, "", document["approach"]))
        out.append(Document(_text_of(document), recency(record.name, applied), hits))

    for path, config in corpus_.reviews.items():
        where = str(path.relative_to(corpus_.root))
        hits = []
        if config.get("description"):
            # A team's own description says what the team is for, and it reached
            # no hit: only each reviewer's perspective did.
            hits.append(
                Hit("REVIEWS", where, config.get("name", ""), config["description"])
            )
        hits += [
            Hit("REVIEWS", where, reviewer.get("role", ""), reviewer.get("perspective", ""))
            for reviewer in config.get("reviewer", [])
        ]
        if hits:
            out.append(Document(_text_of(config), (0, ()), hits))

    for path, text in corpus_.extensions.items():
        where = str(path.relative_to(corpus_.root))
        reader = "every skill" if path.stem == "shared" else path.stem
        out.append(
            Document(text, (0, ()), [Hit("CONVENTIONS", where, "", text, reader)])
        )

    for path, text in corpus_.plans.items():
        where = str(path.relative_to(corpus_.root))
        out.append(Document(text, (0, ()), [Hit("PLANS", where, "", text)]))

    return out


def search(corpus_: Corpus, terms: list[str]) -> dict[str, list[Hit]]:
    """Every hit, by group, newest first within each."""
    patterns = [pattern(term) for term in terms]
    found: dict[str, list[tuple[tuple, Hit]]] = {name: [] for name in GROUPS}
    for document in documents(corpus_):
        if not all(p.search(document.text) for p in patterns):
            continue
        for hit in document.hits:
            # The whole hit, not its body. A task id is the label and a removal
            # check is the note, so filtering on `text` alone reported that
            # nothing was written about 191 of 6,322 terms taken from the corpus.
            if any(p.search(hit.searchable) for p in patterns):
                found[hit.group].append((document.key, hit))
    for hits in found.values():
        hits.sort(key=lambda pair: pair[0], reverse=True)
    return {name: [hit for _, hit in found[name]] for name in GROUPS if found[name]}


# --- printing --------------------------------------------------------------- #

CAP = 5
WIDTH = 88


def window(text: str, patterns: list[re.Pattern[str]]) -> str:
    """The match with enough around it to read, not the field it sits in.

    An `approach` runs to 1,201 words at its longest, and printing one whole to
    show a match in its third paragraph buries the other groups below the fold.
    """
    flat = " ".join(text.split())
    if len(flat) <= 300:
        body, lead, tail = flat, "", ""
    else:
        first = min(
            (m.start() for m in (p.search(flat) for p in patterns) if m), default=0
        )
        start = max(0, first - 100)
        end = min(len(flat), first + 200)
        if start:
            # -1 means no space in the rest of the string, not offset zero.
            # Taken as an offset it collapsed start to 0 and printed a body
            # without the match in it.
            space = flat.find(" ", start, first)
            start = space + 1 if space != -1 else start
        if end < len(flat):
            # rfind gives the LAST space in the range, which can sit before the
            # match — the tail then retreats past it and the body ends before it
            # begins. -1 has the same effect from the other direction: it became
            # flat[start:-1], the whole field minus one character, and one
            # 200,000-character token printed 2,384 lines. Floor at the match.
            space = flat.rfind(" ", start, end)
            end = space if space > first else end
        body, lead, tail = flat[start:end], "… " if start else "", " …"
    return textwrap.fill(
        lead + body + tail, width=WIDTH, initial_indent="    ", subsequent_indent="    "
    )


def render_hit(hit: Hit, patterns: list[re.Pattern[str]]) -> str:
    """A hit's body. Structured where it was written structured, windowed otherwise.

    A decision prints whole and verbatim — chose, what it was chosen over, and the
    rationale entire. A paraphrased decision is a decision misrepresented, and
    truncating the reasoning to fit a window paraphrases by omission.
    """
    if not hit.parts:
        return window(hit.text, patterns)
    lines = []
    for label, value in hit.parts:
        if not value:
            continue
        lines.append(
            textwrap.fill(
                value,
                width=WIDTH,
                initial_indent=f"    {label:<9}",
                subsequent_indent=" " * 13,
            )
        )
    return "\n".join(lines)


def render_search(found: dict[str, list[Hit]], terms: list[str]) -> str:
    """The report for a term query."""
    if not found:
        quoted = " ".join(repr(t) for t in terms)
        return f"nothing written down here matches {quoted}.\n"

    patterns = [pattern(term) for term in terms]
    lines: list[str] = []
    for name in GROUPS:
        hits = found.get(name)
        if not hits:
            continue
        lines.append(name)
        if name in GROUP_NOTE:
            lines.append(f"  ({GROUP_NOTE[name]})")
        for hit in hits[:CAP]:
            head = f"  {hit.source}"
            if hit.label:
                head += f" · {hit.label}"
            if hit.note:
                head += f"   [{hit.note}]"
            lines.append(head)
            lines.append(render_hit(hit, patterns))
        if len(hits) > CAP:
            # A truncated result set that does not say it was truncated reads as
            # a complete answer, which is the failure one level up that this
            # command exists to prevent.
            rest = len(hits) - CAP
            lines.append(
                f"    … {rest} more in {name}. Narrow with another term, or read one"
                " whole with flw ledger --show <name>."
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# --- reading one thing whole ------------------------------------------------- #


def _paragraphs(text: str) -> str:
    """Prose as it was written, wrapped. A record's `approach` has paragraphs and
    they carry the argument's structure; reflowing them into one block loses it."""
    out = []
    for block in text.strip().split("\n\n"):
        flat = " ".join(block.split())
        if not flat:
            continue
        out.append(textwrap.fill(flat, width=WIDTH, initial_indent="  ", subsequent_indent="  "))
    return "\n\n".join(out)


def render_record(record: Record) -> str:
    """One version record, as prose rather than as TOML.

    `cat` on this file prints 255 lines with the approach as a single unwrapped
    string. The rendering is the point: names do not map to filenames — this
    record is in `<name>-<classification>.toml` and the suffix is the
    classification, which is what you were about to ask the record about.
    """
    document = record.document
    head = record.name
    if record.classification:
        head += f"   [{record.classification}]"
    lines = [head, f"  {record.path.name}"]
    trail = []
    if document.get("base"):
        trail.append(f"after {document['base']}")
    if document.get("spec_version"):
        trail.append(f"specced against {document['spec_version']}")
    if document.get("release_line") is not None:
        trail.append(f"moves to release line {document['release_line']}")
    if trail:
        lines.append("  " + " · ".join(trail))
    if document.get("summary"):
        lines += ["", _paragraphs(document["summary"])]
    if document.get("approach"):
        lines += ["", "APPROACH", _paragraphs(document["approach"])]
    for decision in document.get("decisions", []):
        lines += ["", "DECISION", f"  {decision.get('topic', '')}"]
        # render_hit never touches `patterns` when `parts` is set, so there is
        # nothing to pass. The block it produces was written twice, identically.
        lines.append(render_hit(Hit("DECISION", "", "", "", parts=decision_parts(decision)), []))
    if document.get("dag"):
        lines += ["", "PLAN"]
        for group in document["dag"]:
            lines.append(f"  {group.get('group', '?')}. {group.get('phase', '')}".rstrip())
            for task in group.get("tasks", []):
                lines.append(
                    textwrap.fill(
                        task.get("desc", ""),
                        width=WIDTH,
                        initial_indent=f"     {task.get('id', '')} — ",
                        subsequent_indent=" " * 7,
                    )
                )
    if document.get("contract_edit"):
        lines += ["", "CONTRACT EDIT", _paragraphs(document["contract_edit"])]
    return "\n".join(lines) + "\n"


def render_component(component: dict) -> str:
    """One contract component: what somebody about to touch that code needs.

    Five of them sit nested three levels into the contract file, which is why
    finding one by name is worth a flag.
    """
    lines = [component.get("name", ""), "  current.toml"]
    for path in component.get("paths", []):
        lines.append(f"    {path}")
    for key in ("provides", "properties", "surfaces"):
        entries = component.get(key, [])
        if not entries:
            continue
        lines += ["", f"{key.upper()}  ({len(entries)})"]
        for entry in entries:
            lines.append(
                textwrap.fill(entry, width=WIDTH, initial_indent="  - ", subsequent_indent="    ")
            )
    if component.get("implementation"):
        lines += ["", "IMPLEMENTATION", _paragraphs(component["implementation"])]
    return "\n".join(lines) + "\n"


def show(corpus_: Corpus, name: str) -> tuple[str, int]:
    """One record or one contract component, by name.

    Record names are kebab-case and component names are prose with spaces, so the
    two namespaces cannot collide today. If one ever does, both print: guessing
    which was meant is how a lookup starts answering a question nobody asked.
    """
    wanted = name.strip().lower()
    if not wanted:
        # Refused before either lookup rather than after. A contract component
        # with no name reads back as the empty name — which this version taught
        # the ledger to survive — so `flw ledger --show "$NAME"` with NAME unset resolved to
        # it and reported success. A record file called `-minor.toml` is the
        # same route through the record list.
        return _missing(name, corpus_), 1
    records = [r for r in corpus_.records if r.name.lower() == wanted]
    unreadable = [r for r in records if r.error]
    if unreadable:
        # The name matched, so answering "nothing here is called that" would be
        # false: the record is there and could not be read. `flw validate` is
        # what reports it in full.
        return (
            "\n".join(f"{r.path}: {r.error}" for r in unreadable)
            + "\n\n`flw validate` reports what is wrong with it.",
            1,
        )
    components = [
        c
        for c in corpus_.contract.get("final_state", {}).get("components", [])
        if c.get("name", "").lower() == wanted
    ]
    found = [render_record(r) for r in records] + [render_component(c) for c in components]
    if found:
        note = ""
        if len(found) > 1:
            note = (
                f"{name!r} names {len(found)} things — a record and a contract "
                "component. Both follow.\n\n"
            )
        return note + "\n".join(found), 0
    return _missing(name, corpus_), 1


def _missing(name: str, corpus_: Corpus) -> str:
    seen = len(corpus_.contract.get("final_state", {}).get("components", []))
    return (
        f"nothing here is called {name!r}. Looked in {len(corpus_.records)} version "
        f"records and {seen} contract components; `flw ledger` with no argument lists "
        "what there is."
    )


# --- what is here at all ----------------------------------------------------- #


def _capped(entries: list[str], what: str) -> list[str]:
    """The first few, and an honest count of the rest."""
    lines = [
        textwrap.fill(entry, width=WIDTH, initial_indent="  - ", subsequent_indent="    ")
        for entry in entries[:CAP]
    ]
    if len(entries) > CAP:
        lines.append(f"    … {len(entries) - CAP} more {what}.")
    return lines


def census(corpus_: Corpus) -> str:
    """What the record set contains, for somebody who has not read any of it.

    The first thing to run in a repository nobody has read, so it says what each
    tier *is* rather than naming flw's fields: an agent landing here has no
    reason to know what an `approach` or a `contract_edit` is.
    """
    contract = corpus_.contract
    applied = list(contract.get("applied", []))
    components = contract.get("final_state", {}).get("components", [])
    removed = contract.get("final_state", {}).get("removed", [])

    legacy = [r for r in corpus_.records if r.name not in applied and LEGACY_NUMBER.match(r.name)]
    flight = [
        r for r in corpus_.records if r.name not in applied and not LEGACY_NUMBER.match(r.name)
    ]
    decisions = sum(len(r.document.get("decisions", [])) for r in corpus_.records)

    def task_count(records: list[Record]) -> int:
        return sum(
            len(group.get("tasks", []))
            for r in records
            for group in r.document.get("dag", [])
        )

    # Two counts rather than one, over the same predicate the search classifies
    # by. One number under "what was built" counted every record's tasks, so a
    # plan nobody had run was reported as work that existed.
    done = task_count([r for r in corpus_.records if built(r.name, applied)])
    planned = task_count([r for r in corpus_.records if not built(r.name, applied)])

    release = contract.get("spec_version", "no release number")
    kinds = [
        ("what is true now", f"release {release}, {len(components)} components"),
        (
            "how it got here",
            # Records that exist, not names in the list: a contract naming a
            # record with no file printed a count larger than the set it had
            # just described, and said nothing about the gap flw validate reports.
            f"{len(corpus_.records)} version records — "
            f"{sum(1 for r in corpus_.records if r.name in applied)} applied"
            + (f", {len(legacy)} predating the count" if legacy else "")
            + (f", {len(flight)} written and not yet run" if flight else ""),
        ),
        ("what was settled", f"{decisions} decisions, each with what it beat"),
        ("what was built", f"{done} task descriptions"),
    ]
    if planned:
        kinds.append(("what is planned", f"{planned} task descriptions, in records nobody has run"))
    if corpus_.extensions:
        kinds.append(
            (
                "what binds unvalidated",
                (
                    f"{len(corpus_.extensions)} extensions — prose this repo made"
                    " binding, read by the skills and checked by nothing"
                ),
            )
        )
    if corpus_.reviews:
        kinds.append(("how it reviews itself", f"{len(corpus_.reviews)} team configs"))
    if corpus_.plans:
        kinds.append(
            ("design notes", f"{len(corpus_.plans)} files in plans/ — not validated, may be superseded")
        )

    lines = [""]
    for label, value in kinds:
        # Wrapped rather than padded: the record count grows and this line is the
        # one that outgrows a terminal first.
        lines.append(
            textwrap.fill(
                value,
                width=WIDTH,
                initial_indent=f"  {label:<22} ",
                subsequent_indent=" " * 25,
            )
        )

    newest = sorted(corpus_.records, key=lambda r: recency(r.name, applied), reverse=True)[:CAP]
    if newest:
        lines += ["", "NEWEST"]
        for record in newest:
            state = record.classification or "legacy"
            if record.name not in applied:
                state += " · not yet run" if not LEGACY_NUMBER.match(record.name) else ""
            summary = record.document.get("summary", "")
            lines.append(
                textwrap.fill(
                    f"{record.name}  [{state}]  {summary}",
                    width=WIDTH,
                    initial_indent="  ",
                    subsequent_indent="    ",
                )
            )

    for heading, entries in (
        ("ASSUMPTIONS", list(contract.get("assumptions", []))),
        ("OPEN QUESTIONS", list(contract.get("open_questions", []))),
        ("REMOVED", [entry.get("statement", "") for entry in removed]),
    ):
        if entries:
            lines += ["", f"{heading}  ({len(entries)})"] + _capped(entries, heading.lower())

    lines += [
        "",
        "  flw ledger <term>     search all of it, grouped by what kind of thing matched",
        "  flw ledger --show <name>  one record or component, whole",
    ]
    return "\n".join(lines) + "\n"
