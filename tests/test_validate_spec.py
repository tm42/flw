"""The validator, and the shipped data it validates.

These exercise `core/scripts/validate_spec.py` against real inputs — the review
configs flw ships, the schemas it calls the authority on shape, and hand-built
configs that should be refused. Everything here has fixed behaviour: a change
that breaks one of these broke the validator or the data, not the wording.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.scripts.validate_spec import (
    check_chain,
    check_contract,
    check_review,
    check_version,
    expected_release,
    load_records,
    parse_record_filename,
    validate,
)

REPO = Path(__file__).resolve().parent.parent

REVIEWS = REPO / "core" / "reviews"


def shape() -> dict:
    import json

    return json.loads((REPO / "core" / "schemas" / "review.schema.json").read_text())


def check(config: dict) -> list[str]:
    return [str(e) for e in validate(config, shape(), root=shape())]


@pytest.mark.parametrize("name", ["quick", "eng"])
def test_the_shipped_configs_validate(name):
    config = tomllib.loads((REVIEWS / f"{name}.toml").read_text())
    assert check(config) == []
    assert check_review(config, f"{name}.toml") == []


@pytest.mark.parametrize("name", ["quick", "eng"])
def test_every_shipped_reviewer_has_a_real_perspective(name):
    """The failure this guards is silent: a reviewer with a thin perspective
    dispatches, costs a context, and returns nothing anyone can act on."""
    config = tomllib.loads((REVIEWS / f"{name}.toml").read_text())
    for reviewer in config["reviewer"]:
        assert len(reviewer["perspective"].split()) > 40, reviewer["role"]


GRANTS_EXECUTION = ("you may run", "you may execute", "targeted probe", "attack it")


@pytest.mark.parametrize("name", ["quick", "eng"])
def test_probes_and_the_perspective_agree(name):
    """The bug this catches shipped once.

    quick's correctness told the reviewer "you may run something to confirm a
    finding" while carrying no `probes` key. The skill says a reviewer without it
    reads and does not execute — so whoever dispatched had to either violate the
    skill or hand a reviewer a verbatim instruction it was not allowed to follow.
    A permission granted in prose and withheld structurally is worse than either.
    """
    config = tomllib.loads((REVIEWS / f"{name}.toml").read_text())
    for reviewer in config["reviewer"]:
        prose_grants = any(
            phrase in reviewer["perspective"].lower() for phrase in GRANTS_EXECUTION
        )
        assert prose_grants == bool(reviewer.get("probes")), (
            f"{name}:{reviewer['role']} — perspective "
            f"{'grants' if prose_grants else 'does not grant'} execution but probes is "
            f"{reviewer.get('probes', False)}"
        )


def test_at_least_one_lens_probes():
    """An adversarial lane that only ever reads decays into opinion."""
    for name in ("quick", "eng"):
        config = tomllib.loads((REVIEWS / f"{name}.toml").read_text())
        assert any(r.get("probes") for r in config["reviewer"]), name


def test_a_reviewer_without_a_perspective_is_refused():
    config = {
        "name": "broken",
        "description": "x",
        "reviewer": [{"role": "correctness"}],
    }
    assert any("perspective" in e for e in check(config))


def test_an_unknown_effort_is_refused():
    config = {
        "name": "broken",
        "description": "x",
        "reviewer": [{"role": "r", "perspective": "p", "effort": "maximum"}],
    }
    assert any("effort" in e for e in check(config))


def test_a_config_naming_itself_something_else_is_caught():
    """The filename is how the team is invoked, so a mismatch means one of them
    is a typo and the team is reachable under a name its own file denies."""
    config = tomllib.loads((REVIEWS / "eng.toml").read_text())
    errors = check_review(config, "engineering.toml")
    assert any("filename says 'engineering'" in e for e in errors)


def test_two_reviewers_with_one_role_are_caught():
    """The role is what a finding is attributed to in the report."""
    config = {
        "name": "broken",
        "description": "x",
        "reviewer": [
            {"role": "correctness", "perspective": "a"},
            {"role": "correctness", "perspective": "b"},
        ],
    }
    assert any("appears more than once" in e for e in check_review(config, "broken.toml"))


def test_an_unknown_key_is_refused():
    """additionalProperties is false everywhere, so a typo'd key fails loudly
    rather than being silently ignored at dispatch."""
    config = {
        "name": "broken",
        "description": "x",
        "reviewer": [{"role": "r", "perspective": "p", "model": "opus"}],
    }
    assert any("unexpected property 'model'" in e for e in check(config))


# --- the contract chain ---------------------------------------------------- #


def test_a_marker_is_found_inside_a_value():
    """Required fields have minLength 1, so a TOML comment cannot hold a marker.
    It has to be found inside the value itself or thrifty guesses one, which is
    the one thing it exists to prevent."""
    from core.scripts.validate_spec import check_markers

    found = check_markers({"success_criteria": {"criteria": "TODO(flw): what else?"}})
    assert found == ["success_criteria.criteria: unresolved — what else?"]


def test_the_contract_schema_does_not_describe_deleted_architecture():
    """context.md calls the schemas the authority on shape. This one's top-level
    description still described specs/deltas/ and specs/ledger.toml, so a cold
    agent starting a new project would build what flw deleted — and a new project
    has no removal check to catch it."""
    import json

    text = json.dumps(
        json.loads((REPO / "core" / "schemas" / "spec-v4.schema.json").read_text())
    )
    assert "ledger" not in text
    assert "specs/deltas" not in text


# --- the two schema versions ----------------------------------------------- #


def contract_shape(name: str) -> dict:
    import json

    return json.loads((REPO / "core" / "schemas" / name).read_text())


def test_a_v4_component_may_declare_properties_and_surfaces(specs):
    """The two keys 4.0 exists to add. Nothing else asserts they are accepted —
    the shipped contract carries both, so dropping either from the schema fails
    only where a test happens to validate that one file."""
    contract = tomllib.loads((specs / "current.toml").read_text())
    contract["schema_version"] = 4
    contract["spec_version"] = "0.1.0"
    component = contract["final_state"]["components"][0]
    component["properties"] = ["A refusal that cannot fire is reported, not skipped."]
    component["surfaces"] = ["~/.flw/root — one line, the checkout path."]

    schema = contract_shape("spec-v4.schema.json")
    assert [str(e) for e in validate(contract, schema, root=schema)] == []


def test_a_v4_component_still_refuses_a_key_the_schema_does_not_name(specs):
    """additionalProperties stays false through the bump. Two keys were added by
    hand, so a third arriving by typo has to fail rather than be ignored."""
    contract = tomllib.loads((specs / "current.toml").read_text())
    contract["schema_version"] = 4
    contract["final_state"]["components"][0]["surfacez"] = ["typo"]

    schema = contract_shape("spec-v4.schema.json")
    errors = [str(e) for e in validate(contract, schema, root=schema)]
    assert any("unexpected property 'surfacez'" in e for e in errors)


def test_a_v3_contract_resolves_to_v3_when_handed_the_v4_schema(specs):
    """The reason spec-v3.schema.json stays on disk. `flw validate` now names the
    v4 schema for every contract, so a v3 one reaching it must be redirected by
    its own schema_version — and be told which schema answered."""
    from core.scripts.validate_spec import resolve_schema

    contract = tomllib.loads((specs / "current.toml").read_text())
    assert contract["schema_version"] == 3

    resolved, note = resolve_schema(
        contract, REPO / "core" / "schemas" / "spec-v4.schema.json"
    )
    assert resolved.name == "spec-v3.schema.json"
    assert "using spec-v3.schema.json" in note


# --- v4.1: the validator reports every record it was given ------------------ #


def test_an_unknown_schema_version_is_reported_not_a_traceback(specs):
    """Before this, resolve_schema raised SystemExit from inside validate_file —
    one contract with a bad schema_version killed the whole run with every
    version file unchecked and nothing saying they were skipped."""
    from core.scripts.validate_spec import validate_file

    (specs / "current.toml").write_text(
        (specs / "current.toml").read_text().replace("schema_version = 3", "schema_version = 99")
    )
    code, messages = validate_file(specs / "current.toml", REPO / "core" / "schemas" / "spec-v4.schema.json")
    assert code == 1
    assert any("unknown schema_version" in m for m in messages)


def test_the_remaining_targets_still_validate_after_one_fails(specs, monkeypatch, capsys):
    """cli.flw.validate() is the caller: it must carry on to the next target
    rather than dying on the first bad schema_version, and still exit non-zero."""
    from tests.test_cli import flw

    (specs / "current.toml").write_text(
        (specs / "current.toml").read_text().replace("schema_version = 3", "schema_version = 99")
    )
    monkeypatch.chdir(specs.parent)
    code = flw.validate(SimpleNamespace(path=None))
    out = capsys.readouterr()
    assert code != 0
    assert "unknown schema_version" in out.out + out.err
    assert any("v1.0.toml" in line for line in (out.out + out.err).splitlines())


# --- what the hosts require ------------------------------------------------ #


def test_every_skill_has_frontmatter_the_hosts_can_read():
    for path in sorted((REPO / "core" / "skills").iterdir()):
        text = (path / "SKILL.md").read_text()
        assert text.startswith("---\n"), path.name
        head = text.split("---", 2)[1]
        assert f"name: {path.name}" in head, path.name
        assert "description:" in head, path.name


# --- flw-spec writes the format the validator accepts ----------------------- #


def test_flw_spec_step_5_names_no_field_the_schema_rejects():
    """The defect this record exists to fix: flw-spec once told authors to write
    a `kind` field version.schema.json no longer accepted. Locks the two
    together so the next format change fails here instead of shipping."""
    import json
    import re

    schema = json.loads((REPO / "core" / "schemas" / "version.schema.json").read_text())
    allowed = set(schema["properties"])

    skill = (REPO / "core" / "skills" / "flw-spec" / "SKILL.md").read_text()
    step_5 = skill.split("5. **Write `<specs>/versions/", 1)[1].split("\n6. ", 1)[0]

    named = set(re.findall(r"`(\w+)` (?:is|carries|only if)\b", step_5))
    assert named, "the extraction pattern found nothing — it is stale, not the skill"
    assert named <= allowed, f"step 5 names {named - allowed}, which the schema rejects"


# --- lineage and dag integrity ---------------------------------------------- #
#
# Every check below was reachable by hand and pinned by nothing: a mutation run on
# 2026-08-25 disabled each one in turn and the suite stayed green. The contract
# names two of these failures directly — "a file numbered against its own
# contents, a dag that cannot be walked".


def version(**fields) -> dict:
    return {"spec_version": "1.1", "summary": "a change", **fields}


def test_a_dag_cycle_is_caught():
    errors = check_version(
        version(
            dag=[
                {
                    "group": 1,
                    "tasks": [
                        {"id": "a", "desc": "a", "depends_on": ["b"]},
                        {"id": "b", "desc": "b", "depends_on": ["a"]},
                    ],
                }
            ]
        ),
        "v1.1.toml",
    )
    assert any("cycle" in e for e in errors), errors


def test_a_depends_on_naming_no_task_is_caught():
    errors = check_version(
        version(
            dag=[{"group": 1, "tasks": [{"id": "a", "desc": "a", "depends_on": ["ghost"]}]}]
        ),
        "v1.1.toml",
    )
    assert any("ghost" in e for e in errors), errors


def test_a_duplicate_task_id_is_caught():
    errors = check_version(
        version(
            dag=[
                {
                    "group": 1,
                    "tasks": [{"id": "a", "desc": "one"}, {"id": "a", "desc": "two"}],
                }
            ]
        ),
        "v1.1.toml",
    )
    # Not `"a" in e`: the duplicated id is the letter a, so that passes on any
    # error text containing it — including one that names no id at all, which is
    # the whole point of the message.
    assert any("'a' is used more than once" in e for e in errors), errors


def test_a_duplicate_component_name_is_caught():
    errors = check_contract(
        {
            "final_state": {
                "components": [
                    {"name": "alpha", "paths": ["a"], "provides": ["a"]},
                    {"name": "alpha", "paths": ["b"], "provides": ["b"]},
                ]
            }
        }
    )
    assert any("alpha" in e for e in errors), errors


def test_a_versions_directory_with_no_records_is_caught(tmp_path):
    empty = tmp_path / "versions"
    empty.mkdir()
    assert any("no version files" in e for e in check_chain(empty))




# --- the reports a record came from ----------------------------------------- #
#
# `check_version` reads identity and dag integrity; the document's shape is the
# schema's. These go through the schema, which is the half `sources` changed.


def record_shape() -> dict:
    import json

    return json.loads(
        (REPO / "core" / "schemas" / "version.schema.json").read_text()
    )


def against_schema(document: dict) -> list[str]:
    shape_ = record_shape()
    return [str(e) for e in validate(document, shape_, root=shape_)]


def test_a_record_may_name_the_reports_it_came_from():
    """`sources` is optional, so every record written before it existed still
    validates, and a record that carries it is not a new kind of record."""
    doc = version(name="marked", sources=[".flw/reports/2026-09-03T2050-process.md"])
    assert against_schema(doc) == []


def test_a_record_with_no_sources_still_validates():
    assert against_schema(version(name="unmarked")) == []


def test_sources_must_hold_strings_and_not_be_empty():
    """An empty list says the record was specced from no report, which is what
    omitting the field already says. Two spellings of one state is one too many."""
    empty = against_schema(version(name="marked", sources=[]))
    assert any("sources" in e for e in empty), empty
    wrong = against_schema(version(name="marked", sources=[3]))
    assert any("sources" in e for e in wrong), wrong


def test_an_unknown_field_beside_sources_is_still_refused():
    """additionalProperties stays false: adding one property does not open the
    document, and a typo'd `source` must not read as `sources`."""
    errors = against_schema(version(name="marked", source=[".flw/reports/x.md"]))
    assert any("unexpected property 'source'" in e for e in errors), errors


# --- identity and the applied list ------------------------------------------ #
#
# A record is addressed by a name it keeps, and the order versions landed in is
# the contract's `applied` list. There is no chain: a `base` pointer gives each
# record exactly one predecessor, which two people speccing in parallel from the
# same contract cannot both have.


def applied(specs, *names) -> None:
    line = "applied = [" + ", ".join(repr(n).replace("'", '"') for n in names) + "]\n"
    text = (specs / "current.toml").read_text()
    (specs / "current.toml").write_text(text.replace("\n", "\n" + line, 1))


def record(specs, filename, name, **fields) -> None:
    body = f'name = "{name}"\nsummary = "a change"\n'
    for key, value in fields.items():
        body += f'{key} = {value}\n' if isinstance(value, int) else f'{key} = "{value}"\n'
    (specs / "versions" / filename).write_text(body)


def test_a_record_name_disagreeing_with_its_filename_is_caught():
    """The filename is the identity, so nothing can tell which side is the typo."""
    errors = check_version({"name": "add-posture", "summary": "s"}, "add-postures.toml")
    assert any("add-posture" in e and "add-postures" in e for e in errors), errors


def test_a_legacy_numbered_filename_still_matches_its_name():
    assert check_version({"name": "4.6", "summary": "s"}, "v4.6.toml") == []


def test_a_name_beginning_with_v_keeps_its_own_first_letter():
    """The legacy prefix is stripped only when a digit follows it. Stripping it
    unconditionally turned a record called version-names into ersion-names."""
    assert check_version(
        {"name": "version-names", "summary": "s"}, "version-names-major.toml"
    ) == []


def test_a_contract_that_is_not_utf8_is_named_rather_than_a_traceback(specs):
    """The command whose whole job is naming a document it cannot read printed
    `OK:` for the file asked about and then a traceback naming no path at all.
    validate_file, read_flw_text and read_host_text already closed this; this
    reader was missed."""
    (specs / "current.toml").write_bytes(b'spec_version = "\xff\xfe1.0"\n')
    errors = check_chain(specs / "versions")
    assert any("current.toml" in e and "cannot be read" in e for e in errors), errors


def test_two_records_sharing_a_name_are_caught(specs):
    """The collision the whole change exists to make impossible to miss: two
    people speccing in parallel and both claiming one identity."""
    record(specs, "one.toml", "same-name")
    record(specs, "two.toml", "same-name")
    errors = check_chain(specs / "versions")
    assert any("same-name" in e and "cannot share" in e for e in errors), errors


def test_an_applied_name_with_no_record_is_caught(specs):
    """The contract claiming a version nothing accounts for. This is the check
    that caught a real one on 2026-08-25, when a run moved the contract and left
    the record untracked."""
    applied(specs, "1.0", "gone-missing")
    errors = check_chain(specs / "versions")
    assert any("gone-missing" in e for e in errors), errors


def test_a_record_no_applied_list_names_is_a_version_in_flight(specs):
    """flw-spec wrote the record, flw-execute has not run it yet. Not an error —
    this is the ordinary state of every version between its spec and its run."""
    record(specs, "in-flight.toml", "in-flight", base="1.0")
    applied(specs, "1.0")
    text = (specs / "current.toml").read_text()
    (specs / "current.toml").write_text(text.replace('spec_version = "1.0"', 'spec_version = "0.1.0"'))
    assert check_chain(specs / "versions") == []


def test_an_applied_name_with_no_record_is_reported_once_for_the_directory(
    specs, monkeypatch, capsys
):
    """One fact about the directory, reported once — not once per version file
    under a filename it has nothing to do with."""
    from tests.test_cli import flw

    applied(specs, "1.0", "gone-missing")
    record(specs, "other.toml", "other")
    monkeypatch.chdir(specs.parent)
    flw.validate(SimpleNamespace(path=None))
    lines = capsys.readouterr().err.splitlines()
    assert sum("gone-missing" in line for line in lines) == 1


def test_a_record_filename_without_a_classification_is_refused():
    """The release number moves by this suffix, so a record that omits it is a
    number nobody will remember to bump."""
    errors = check_version({"name": "add-thing", "summary": "s"}, "add-thing.toml")
    assert any("major or minor" in e for e in errors), errors


def test_a_classification_suffix_is_not_part_of_the_name():
    """Reclassifying during an interview renames the file. If the suffix were in
    the name, that would move the record's identity and every applied entry
    naming it."""
    assert check_version({"name": "add-thing", "summary": "s"}, "add-thing-minor.toml") == []
    assert check_version({"name": "add-thing", "summary": "s"}, "add-thing-major.toml") == []


def test_a_name_that_itself_ends_in_minor_is_parsed_from_the_right():
    assert parse_record_filename("fix-minor-major.toml") == ("fix-minor", "major")
    assert check_version({"name": "fix-minor", "summary": "s"}, "fix-minor-major.toml") == []


def test_a_legacy_numbered_record_needs_no_classification():
    assert parse_record_filename("v4.6.toml") == ("4.6", None)
    assert check_version({"name": "4.6", "summary": "s"}, "v4.6.toml") == []


def test_a_major_record_moves_the_release_number_to_the_next_whole(specs):
    record(specs, "big-change-major.toml", "big-change")
    applied(specs, "1.0", "big-change")
    records = {"big-change": {"classification": "major"}}
    assert expected_release(["1.0", "big-change"], records) == "0.2.0"


def test_a_minor_record_moves_only_the_second_half(specs):
    records = {"small": {"classification": "minor"}}
    assert expected_release(["1.0", "small"], records) == "0.1.1"


def test_a_fold_with_no_line_declared_stays_on_the_zero_line(specs):
    """No record has ever declared release_line, so the product is not real yet
    and the fold's leading part stays 0 no matter how many major and minor
    records land."""
    records = {"big-change": {"classification": "major"}, "small": {"classification": "minor"}}
    assert expected_release(["1.0", "big-change", "small"], records) == "0.2.1"


def test_a_declared_line_restarts_major_and_minor_at_zero(specs):
    """1.0.0 regardless of what preceded it on line 0 — the record that declares
    the line does not also get its own classification's bump."""
    records = {"reach-production": {"classification": "major", "release_line": 1}}
    assert expected_release(["4.7", "reach-production"], records) == "1.0.0"


def test_a_minor_after_the_line_moves_only_the_last_part(specs):
    records = {
        "reach-production": {"classification": "major", "release_line": 1},
        "small-fix": {"classification": "minor"},
    }
    assert expected_release(["4.7", "reach-production", "small-fix"], records) == "1.0.1"


def test_a_major_after_the_line_moves_the_middle_part(specs):
    records = {
        "reach-production": {"classification": "major", "release_line": 1},
        "big-change": {"classification": "major"},
    }
    assert expected_release(["4.7", "reach-production", "big-change"], records) == "1.1.0"


def test_a_release_number_nobody_moved_is_caught(specs):
    """The number is folded from the records rather than remembered, because a
    number a human has to remember to bump is a number that drifts."""
    record(specs, "big-change-major.toml", "big-change")
    applied(specs, "1.0", "big-change")
    errors = check_chain(specs / "versions")
    assert any("add up to '0.2.0'" in e for e in errors), errors


def test_a_release_number_that_matches_its_records_is_clean(specs):
    record(specs, "big-change-major.toml", "big-change")
    applied(specs, "1.0", "big-change")
    text = (specs / "current.toml").read_text()
    (specs / "current.toml").write_text(text.replace('spec_version = "1.0"', 'spec_version = "0.2.0"'))
    assert check_chain(specs / "versions") == []


def test_a_release_number_disagreeing_with_the_folded_three_part_number_is_caught(specs):
    """The disagreement check must not regress to comparing two parts now that
    the fold returns three."""
    record(specs, "reach-production-major.toml", "reach-production", release_line=1)
    applied(specs, "4.7", "reach-production")
    text = (specs / "current.toml").read_text()
    (specs / "current.toml").write_text(text.replace('spec_version = "1.0"', 'spec_version = "1.1.0"'))
    errors = check_chain(specs / "versions")
    assert any("add up to '1.0.0'" in e for e in errors), errors


def test_a_release_number_is_not_guessed_when_a_record_is_missing(specs):
    """An applied name with no file is already an error of its own. Reporting a
    second one about a number computed from a gap would send the reader at the
    wrong thing."""
    applied(specs, "1.0", "vanished")
    errors = check_chain(specs / "versions")
    assert any("vanished" in e for e in errors), errors
    assert not any("add up to" in e for e in errors), errors


# --- the fold works for a project that is not flw --------------------------- #
#
# Every project flw-spec has ever written to has an applied list opening with a
# legacy <major>.<minor> record, because that is the only project flw has run
# against long enough to carry one. Nothing else does: expected_release returned
# None for any applied list without one, including a first record declaring
# release_line, so no newly-adopted project ever had its release number checked.


def test_a_project_with_no_legacy_record_still_folds():
    """The case every project adopting flw today is in: flw-spec writes only
    named records, so nothing in `applied` will ever match LEGACY_NUMBER."""
    records = {"only-record": {"classification": "minor"}}
    assert expected_release(["only-record"], records) == "0.0.1"


def test_a_first_record_declaring_a_line_reaches_it_with_no_anchor():
    """The documented way to start a product at 1.0.0. Before this fix the old
    guard's `or major is None` returned None here instead, because major had
    never been set by a preceding legacy entry."""
    records = {"go-live": {"classification": "major", "release_line": 1}}
    assert expected_release(["go-live"], records) == "1.0.0"


def test_two_records_declaring_a_line_are_caught(specs):
    """expected_release's fold keeps only the last release_line it sees, so a
    second declaration silently won over the first with nothing reported."""
    record(specs, "go-live-major.toml", "go-live", release_line=1)
    record(specs, "go-live-again-major.toml", "go-live-again", release_line=2)
    applied(specs, "go-live", "go-live-again")
    errors = check_chain(specs / "versions")
    assert any(
        "go-live" in e and "go-live-again" in e and "both declare" in e for e in errors
    ), errors


def test_flws_own_applied_list_still_folds_to_its_declared_release():
    """The real chain anchors on a legacy 4.0 entry, which the fold already
    handled before this change. Guards that seeding major/minor at 0 instead of
    None, and refusing a second release_line, left that path's result alone.

    Against the declared number rather than a literal: a literal fails on every
    release, which trains a reader to edit the test rather than read it, and the
    invariant being guarded is that the two agree — not what either one is."""
    assert check_chain(REPO / "specs" / "versions") == []
    contract = tomllib.loads((REPO / "specs" / "current.toml").read_text())
    records = {}
    for path in (REPO / "specs" / "versions").glob("*.toml"):
        record = tomllib.loads(path.read_text())
        records[record["name"]] = {
            "classification": "major" if path.stem.endswith("-major") else "minor",
            "release_line": record.get("release_line"),
        }
    folded = expected_release(contract["applied"], records)
    assert folded is not None, "the real chain must fold, not return None"
    assert folded == contract["spec_version"]


# --- one walk, read by validation and by the knowledge base ----------------- #
#
# check_chain used to open every file itself. It reads through load_records now,
# which keeps the parsed document as well, so the knowledge base does not walk
# the same directory a second time and reach a different answer.


def test_the_walk_keeps_the_document_not_just_the_name(specs):
    """check_chain wants the name and the classification. The knowledge base wants
    the summary, the approach, the dag and the decisions, which is everything the
    old walk read and threw away."""
    record(specs, "kept-minor.toml", "kept", approach="what the walk keeps")
    found = {r.name: r for r in load_records(specs / "versions")}
    assert found["kept"].document["approach"] == "what the walk keeps"
    assert found["kept"].classification == "minor"
    assert found["kept"].error is None


def test_the_walk_names_a_legacy_record_by_its_bare_number(specs):
    """v1.0.toml is the record named 1.0. The fold reads applied entries, which
    carry the bare number, so a walk keying on the filename would miss every
    legacy record."""
    assert "1.0" in {r.name for r in load_records(specs / "versions")}


def test_a_file_that_does_not_parse_keeps_its_name_and_says_why(specs):
    """The fold still needs its classification: an unreadable file is one the
    release number must not silently skip over. So it comes back with the
    filename half intact and the document empty."""
    (specs / "versions" / "broken-major.toml").write_text('name = "broken"\nsummary = ')
    broken = next(r for r in load_records(specs / "versions") if r.name == "broken")
    assert broken.classification == "major"
    assert broken.document == {}
    assert "does not parse" in broken.error


def test_the_walk_returns_records_in_filename_order(specs):
    """Not an aesthetic point: check_chain reports a duplicate name against the
    second file it saw, so an unordered walk names a different file each run."""
    record(specs, "b-minor.toml", "b")
    record(specs, "a-minor.toml", "a")
    names = [r.path.name for r in load_records(specs / "versions")]
    assert names == sorted(names)
