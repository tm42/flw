#!/usr/bin/env python3
"""Validate an flw contract or version file against a JSON schema. Stdlib only.

Usage:
    python validate_spec.py <file.toml> <schema.json>

Two documents live under specs/. A contract declares its schema_version and gets
checked for component-name uniqueness. A version file has none, and gets checked
for lineage — its filename against its declared version, its base against the
previous file — plus the integrity of its dag. Validating one version file walks
the whole chain, because there is no index file and a hole in the sequence has
nowhere else to show up.

Exit codes:
    0 — validates
    1 — validation failed (errors printed to stderr)
    2 — usage / file-not-found error

Pattern matching uses re.search semantics: $ anchors end, ^ anchors start.
Schemas relying on full-string match should anchor their patterns with both ^ and $.
"""

from __future__ import annotations

import functools
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Explicit allow-list of supported JSON Schema keywords.
# Any non-$-prefixed key encountered in a schema that is NOT in this set raises
# ValidationError — this stops schema authors from silently relying on keywords
# the validator doesn't actually implement.
ALLOWED_KEYWORDS: frozenset[str] = frozenset(
    {
        # core
        "type",
        "enum",
        "const",
        "required",
        "properties",
        "additionalProperties",
        # string
        "minLength",
        "pattern",
        # numeric
        "minimum",
        # array / object
        "minItems",
        "items",
        # documentation only
        "description",
        "title",
        "default",
    }
)


@dataclass
class ValidationError:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


@functools.cache
def _compile_pattern(pattern: str) -> re.Pattern[str]:
    """Compile and cache a regex pattern. Patterns are deduplicated by string."""
    return re.compile(pattern)


def _type_of(data: Any) -> str:
    if isinstance(data, bool):
        return "boolean"
    if isinstance(data, int):
        return "integer"
    if isinstance(data, float):
        return "number"
    if isinstance(data, str):
        return "string"
    if isinstance(data, list):
        return "array"
    if isinstance(data, dict):
        return "object"
    if data is None:
        return "null"
    return type(data).__name__


def _matches_type(data: Any, type_: str) -> bool:
    if type_ == "object":
        return isinstance(data, dict)
    if type_ == "array":
        return isinstance(data, list)
    if type_ == "string":
        return isinstance(data, str)
    if type_ == "integer":
        return isinstance(data, int) and not isinstance(data, bool)
    if type_ == "boolean":
        return isinstance(data, bool)
    if type_ == "number":
        return isinstance(data, (int, float)) and not isinstance(data, bool)
    if type_ == "null":
        return data is None
    return True


def _resolve_ref(schema: dict, root: dict) -> dict:
    ref = schema["$ref"]
    if not ref.startswith("#/$defs/"):
        raise ValueError(
            f"unsupported $ref form: {ref!r} (only #/$defs/<name> is supported)"
        )
    name = ref[len("#/$defs/") :]
    if name not in root.get("$defs", {}):
        raise ValueError(f"$ref target not found: {ref!r}")
    return root["$defs"][name]


def validate(
    data: Any, schema: dict, path: str = "$", root: dict | None = None
) -> list[ValidationError]:
    root = root if root is not None else schema
    errors: list[ValidationError] = []

    if "$ref" in schema:
        try:
            schema = _resolve_ref(schema, root)
        except ValueError as exc:
            return [ValidationError(path, str(exc))]

    # Reject unknown JSON Schema keywords loudly rather than silently no-op'ing.
    # $-prefixed keywords ($defs, $id, $schema, $comment, $ref) are reserved
    # JSON Schema metadata and are always allowed.
    for key in schema:
        if not key.startswith("$") and key not in ALLOWED_KEYWORDS:
            errors.append(ValidationError(path, f"unsupported schema keyword: {key!r}"))
    if errors:
        return errors

    type_ = schema.get("type")
    if type_ is not None and not _matches_type(data, type_):
        return [ValidationError(path, f"expected {type_}, got {_type_of(data)}")]

    if "enum" in schema and data not in schema["enum"]:
        errors.append(ValidationError(path, f"value {data!r} not in {schema['enum']}"))
    if "const" in schema and data != schema["const"]:
        errors.append(
            ValidationError(path, f"expected const {schema['const']!r}, got {data!r}")
        )

    if isinstance(data, str):
        if "minLength" in schema and len(data) < schema["minLength"]:
            errors.append(
                ValidationError(
                    path, f"string length {len(data)} < minLength {schema['minLength']}"
                )
            )
        if "pattern" in schema and not _compile_pattern(schema["pattern"]).search(data):
            errors.append(
                ValidationError(
                    path,
                    f"string {data!r} does not match pattern {schema['pattern']!r}",
                )
            )

    # Numeric bound, float-safe.
    if (
        isinstance(data, (int, float))
        and not isinstance(data, bool)
        and "minimum" in schema
        and data < schema["minimum"]
    ):
        errors.append(ValidationError(path, f"value {data} < minimum {schema['minimum']}"))

    if isinstance(data, dict):
        for required in schema.get("required", []):
            if required not in data:
                errors.append(
                    ValidationError(path, f"missing required field {required!r}")
                )
        props = schema.get("properties", {})
        for key, value in data.items():
            sub_path = f"{path}.{key}"
            if key in props:
                errors.extend(validate(value, props[key], sub_path, root))
            elif schema.get("additionalProperties") is False:
                errors.append(ValidationError(path, f"unexpected property {key!r}"))

    if isinstance(data, list):
        if "minItems" in schema and len(data) < schema["minItems"]:
            errors.append(
                ValidationError(
                    path, f"array has {len(data)} items, minItems {schema['minItems']}"
                )
            )
        if "items" in schema:
            for i, item in enumerate(data):
                errors.extend(validate(item, schema["items"], f"{path}[{i}]", root))

    return errors


def _find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    """Return a cycle as a node list (first node repeated at both ends), or None.

    Edges point from a task to the tasks it depends_on. A back-edge to a node
    currently on the DFS stack is a cycle.
    """
    color: dict[str, int] = {n: 0 for n in graph}  # 0 white, 1 gray, 2 black
    path: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = 1
        path.append(node)
        for nxt in graph.get(node, []):
            if nxt not in graph:
                continue  # dangling edge — reported by the depends_on check
            if color[nxt] == 1:
                return path[path.index(nxt) :] + [nxt]
            if color[nxt] == 0:
                found = visit(nxt)
                if found:
                    return found
        path.pop()
        color[node] = 2
        return None

    for n in graph:
        if color[n] == 0:
            found = visit(n)
            if found:
                return found
    return None


def check_contract(contract: dict) -> list[str]:
    """Cross-field checks on a contract, once its schema has passed.

    One check, because a contract states a destination rather than a plan: the
    bijections and language profiles v2 checked here were properties of work
    units, and work units live in version files.
    """
    errors: list[str] = []

    # A component's name is its identity — it is how a version file and a human
    # both refer to it. Two components sharing one makes every such reference
    # ambiguous. Checked here because this schema language has no uniqueItems.
    seen: set[str] = set()
    for component in contract.get("final_state", {}).get("components", []):
        name = component.get("name")
        if name in seen:
            errors.append(
                f"final_state.components: {name!r} appears more than once. The name is "
                "how everything else refers to this component, so a duplicate makes "
                "every reference ambiguous."
            )
        seen.add(name)

    return errors


def check_review(config: dict, name: str) -> list[str]:
    """Cross-field checks on a reviewer team.

    A team whose lenses overlap is not an error, but it is waste — every reviewer
    is a fresh context, and two looking for the same thing return the same finding
    twice at double the cost. Duplicate roles are refused because the role is what
    a finding is attributed to in the consolidated report.
    """
    errors: list[str] = []

    stem = name.removesuffix(".toml")
    if config.get("name") and stem and config["name"] != stem:
        errors.append(
            f"name is {config['name']!r} but the filename says {stem!r}; the filename "
            "is how the team is invoked, so they have to agree"
        )

    seen: set[str] = set()
    for reviewer in config.get("reviewer", []):
        role = reviewer.get("role")
        if role in seen:
            errors.append(
                f"reviewer: role {role!r} appears more than once; the role is what "
                "findings are attributed to, so two of them make the report ambiguous"
            )
        seen.add(role)

    return errors


LEGACY_STEM = re.compile(r"^v\d+\.\d+$")
LEGACY_NUMBER = re.compile(r"^\d+\.\d+$")


def parse_record_filename(filename: str) -> tuple[str, str | None]:
    """A record's name and its classification, read off the filename alone.

    `<name>-minor.toml` or `<name>-major.toml`. The classification lives in the
    filename rather than in a field so that a directory listing shows it without
    opening anything, and `name` stays the bare name so that reclassifying a
    change during its interview renames the file and leaves the record's identity
    — and every `applied` entry naming it — untouched.

    A legacy `v<major>.<minor>` stem is its own name and carries no suffix. Those
    records predate the convention and their numbers already say which they were.
    """
    stem = filename.removesuffix(".toml")
    if LEGACY_STEM.match(stem):
        return stem[1:], None
    for suffix in ("-minor", "-major"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)], suffix[1:]
    return stem, None


@dataclass(frozen=True)
class Record:
    """One file under `specs/versions/`, read once for everything that needs it.

    `name` and `classification` come off the filename, which is the record's
    identity. `document` is what parsed, and is empty when `error` says why it
    did not — a caller that only folds a release number still wants the
    classification of a file that does not parse.
    """

    path: Path
    name: str
    classification: str | None
    document: dict
    error: str | None


def load_records(versions_dir: Path) -> list[Record]:
    """Every version record, in filename order, parsed once.

    `check_chain` keeps the name and the classification; the knowledge base keeps
    the document as well. Two separate walks over the same directory is how
    validation and search come to disagree about what the record set contains.
    """
    records: list[Record] = []
    for path in sorted(versions_dir.glob("*.toml")):
        name, classification = parse_record_filename(path.name)
        try:
            with path.open("rb") as handle:
                document = tomllib.load(handle)
        except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
            # An encoding error is not a parse error, but it reaches the caller
            # the same way: the file is here and cannot be read. Both leave the
            # record's filename half intact so the release fold still sees it.
            records.append(Record(path, name, classification, {}, f"does not parse: {exc}"))
            continue
        records.append(Record(path, name, classification, document, None))
    return records


def check_version(record: dict, name: str) -> list[str]:
    """Identity and dag integrity for one version file.

    The filename is the version's identity, so `name` disagreeing with it means
    one of the two is a typo and there is no way to tell which. `base` is checked
    nowhere here: it records the contract state this was specced against, and the
    order versions landed in lives in the contract's `applied` list.
    """
    errors: list[str] = []

    stem, classification = parse_record_filename(name)
    declared = record.get("name")
    if declared and stem and declared != stem:
        errors.append(
            f"name is {declared!r} but the filename says {stem!r}; "
            "one of them is a typo and nothing can tell which"
        )
    if classification is None and not LEGACY_STEM.match(name.removesuffix(".toml")):
        errors.append(
            f"{name} does not say whether the change is major or minor; "
            "a record is stored as <name>-minor.toml or <name>-major.toml, and the "
            "release number the contract carries moves by it"
        )

    tasks = [
        task
        for group in record.get("dag", [])
        if isinstance(group, dict)
        for task in group.get("tasks", [])
        if isinstance(task, dict)
    ]
    ids = {t["id"] for t in tasks if "id" in t}

    for task in tasks:
        for dep in task.get("depends_on", []):
            if dep not in ids:
                errors.append(
                    f"dag: task {task.get('id', '?')!r} depends_on {dep!r}, "
                    "which is not a task id in this dag"
                )

    seen: set[str] = set()
    for task_id in (t["id"] for t in tasks if "id" in t):
        if task_id in seen:
            errors.append(
                f"dag: task id {task_id!r} is used more than once, so depends_on "
                "cannot address either of them"
            )
        seen.add(task_id)

    cycle = _find_cycle({t["id"]: list(t.get("depends_on", [])) for t in tasks if "id" in t})
    if cycle:
        errors.append("dag: dependency cycle: " + " -> ".join(cycle))

    return errors


def expected_release(applied: list, records: dict) -> str | None:
    """The release number the applied records add up to, or None if it cannot be
    computed.

    Folded rather than remembered: each applied record bumps the number by its own
    filename — major gives <line>.<X+1>.0, minor gives <line>.<X>.<Y+1> — starting
    from 0.0.0, or from the last legacy numbered record's own major.minor when the
    applied list opens with one. A record can also declare `release_line`, which
    restarts the fold: the line becomes that value and the major and minor both
    restart at 0, so <release_line>.0.0 does not depend on what preceded it — a
    project's very first record included, since the seed is 0.0.0 and not a value
    that means "unknown". A release number a human has to remember to move is a
    release number that drifts, which is what the deleted bump machinery in
    final_state.removed was about the first time.

    `records` maps an applied name to {"classification": ..., "release_line": ...}
    — read in the same pass that classifies each record, so a file is never
    opened twice for two different facts about it.
    """
    line = 0
    major = 0
    minor = 0
    for entry in applied:
        if LEGACY_NUMBER.match(entry):
            major_s, _, minor_s = entry.partition(".")
            major, minor = int(major_s), int(minor_s)
            continue
        info = records.get(entry)
        if info is None:
            return None
        release_line = info.get("release_line")
        if release_line is not None:
            line, major, minor = release_line, 0, 0
            continue
        classification = info.get("classification")
        major, minor = (major + 1, 0) if classification == "major" else (major, minor + 1)
    return f"{line}.{major}.{minor}"


def check_chain(versions_dir: Path) -> list[str]:
    """Every name the contract says was applied has a record, and no two records
    share a name.

    There is no chain any more. A `base` pointer chain gives each record exactly
    one predecessor, which is precisely what two people speccing in parallel from
    the same contract cannot both have. The order versions landed in is the
    contract's `applied` list, written by flw-execute when a run finishes.
    """
    files = load_records(versions_dir)
    if not files:
        return [f"{versions_dir} has no version files"]

    errors: list[str] = []
    names: dict[str, Path] = {}
    release_lines: dict[str, int | None] = {}

    for record in files:
        if record.error:
            errors.append(f"{record.path.name}: {record.error}")
            continue
        declared = record.document.get("name")
        if not declared:
            # A missing name is a schema failure, reported against the file itself.
            continue
        if declared in names:
            errors.append(
                f"{record.path.name}: name {declared!r} is already used by "
                f"{names[declared].name}; a name is a record's identity and two "
                "records cannot share one"
            )
        names[declared] = record.path
        # Read alongside `name` rather than reopening the file later just to fold
        # the release number.
        release_lines[declared] = record.document.get("release_line")

    contract = versions_dir.parent / "current.toml"
    if contract.exists():
        document: dict = {}
        try:
            with contract.open("rb") as handle:
                document = tomllib.load(handle)
        except tomllib.TOMLDecodeError:
            pass
        applied = document.get("applied", [])
        for entry in applied:
            if entry not in names:
                errors.append(
                    f"current.toml says {entry!r} was applied, but no record in "
                    f"{versions_dir.name}/ carries that name"
                )

        records = {
            record.name: {
                "classification": record.classification,
                "release_line": release_lines.get(record.name),
            }
            for record in files
        }

        # release_line restarts the fold, so the last declaration in applied order
        # wins and an earlier one is silently overwritten rather than reported.
        # One lineage reaches a new line once; a second declaration is a mistake,
        # not a second real move.
        lined = [entry for entry in applied if records.get(entry, {}).get("release_line") is not None]
        if len(lined) > 1:
            errors.append(
                f"{lined[0]!r} and {lined[1]!r} both declare release_line; a lineage "
                "moves to a new line once, and the fold keeps only the last "
                "declaration it sees, silently dropping the earlier one"
            )

        expected = expected_release(applied, records)
        declared_release = document.get("spec_version")
        if expected and declared_release and declared_release != expected:
            errors.append(
                f"current.toml is at {declared_release!r} but the applied records add up "
                f"to {expected!r}; the release number moves by each record's filename, so "
                "one of them was not moved when its run finished"
            )

    return errors


UNRESOLVED = "TODO(flw)"


def check_markers(document: dict, path: str = "") -> list[str]:
    """Find thrifty-mode markers left unresolved.

    Required fields with a minimum length cannot hold a TOML comment, so a
    thrifty draft parks its open questions inside the values themselves. That
    makes the draft structurally valid, which is what lets it be validated at
    all — and it means the only thing standing between a placeholder and a
    shipped contract is noticing it. So this notices.
    """
    found: list[str] = []
    if isinstance(document, dict):
        for key, value in document.items():
            found += check_markers(value, f"{path}.{key}" if path else key)
    elif isinstance(document, list):
        for i, value in enumerate(document):
            found += check_markers(value, f"{path}[{i}]")
    elif isinstance(document, str) and UNRESOLVED in document:
        question = document.split(UNRESOLVED, 1)[1].lstrip(": ").strip()
        found.append(f"{path}: unresolved — {question[:90]}")
    return found


SCHEMA_BY_VERSION: dict[int, str] = {
    3: "spec-v3.schema.json",
    4: "spec-v4.schema.json",
}


class SchemaError(Exception):
    """A document names a schema resolve_schema cannot find or does not know."""


def resolve_schema(document: dict, given: Path) -> tuple[Path, str | None]:
    """Pick the schema a contract's own schema_version calls for.

    The validator is hand-rolled — see ALLOWED_KEYWORDS for exactly what it
    implements — so version dispatch cannot live in the schema. It lives here.

    A document with no schema_version is not a contract; version files are the
    other thing this validates. Those get the schema they were given.
    """
    if "schema_version" not in document:
        return given, None

    version = document["schema_version"]
    wanted = SCHEMA_BY_VERSION.get(version) if isinstance(version, int) else None
    if wanted is None:
        known = ", ".join(str(v) for v in sorted(SCHEMA_BY_VERSION))
        raise SchemaError(f"unknown schema_version {version!r} ({type(version).__name__}; known: {known})")
    if given.name == wanted:
        return given, None
    resolved = given.parent / wanted
    if not resolved.exists():
        raise SchemaError(f"schema not found for v{version}: {resolved}")
    return resolved, f"schema_version = {version}; using {wanted}"


def validate_file(path: Path, schema_path: Path) -> tuple[int, list[str]]:
    """(exit code, messages). Shape first, then meaning.

    check_chain is about the versions directory, not about any one file in it,
    so it is not run here — the caller runs it once per directory it validates.
    """
    try:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        # UnicodeDecodeError is a ValueError, not a TOMLDecodeError, so a file
        # that is not UTF-8 used to raise straight out of the command whose whole
        # job is naming a document it cannot read.
        return 1, [f"{path}: does not parse: {exc}"]

    try:
        schema_path, note = resolve_schema(document, schema_path)
    except SchemaError as exc:
        return 1, [f"{path}: {exc}"]
    with schema_path.open() as handle:
        schema = json.load(handle)

    shape = [str(err) for err in validate(document, schema, root=schema)]
    if shape:
        return 1, [f"{path} fails {schema_path.name}:", *[f"  {e}" for e in shape]]

    if "schema_version" in document:
        meaning = check_contract(document)
    elif schema_path.name == "review.schema.json":
        meaning = check_review(document, path.name)
    else:
        meaning = check_version(document, path.name)

    markers = check_markers(document)
    if markers:
        meaning += [
            "still a draft — these were left for you to answer:",
            *[f"  {m}" for m in markers],
        ]

    if meaning:
        return 1, [f"{path}:", *[f"  {m}" for m in meaning]]

    return 0, [f"OK: {path} validates against {schema_path.name}" + (f" ({note})" if note else "")]


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: {argv[0]} <file.toml> <schema.json>", file=sys.stderr)
        return 2

    path, schema_path = Path(argv[1]), Path(argv[2])
    for candidate in (path, schema_path):
        if not candidate.exists():
            print(f"error: not found: {candidate}", file=sys.stderr)
            return 2

    code, messages = validate_file(path, schema_path)
    stream = sys.stderr if code else sys.stdout
    for message in messages:
        print(message, file=stream)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
