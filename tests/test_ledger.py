"""The knowledge base — what the project wrote down, made findable.

The corpus boundary is the thing under test here more than any single answer: a
query is only trustworthy if what it read is the same set on every clone.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core" / "scripts"))
import ledger

REPO = Path(__file__).resolve().parent.parent

CONTRACT = """schema_version = 4
spec_version = "0.1.0"
applied = ["first"]

[[final_state.components]]
name = "the thing"
paths = ["src/"]
provides = ["A user can do the thing."]
"""

RECORD = """name = "first"
summary = "the first version"
approach = "why the thing is built this way"
"""


def project(tmp_path: Path) -> Path:
    """A minimal flw project: a contract, one record, and nothing else."""
    (tmp_path / "specs" / "versions").mkdir(parents=True)
    (tmp_path / "specs" / "current.toml").write_text(CONTRACT)
    (tmp_path / "specs" / "versions" / "first-minor.toml").write_text(RECORD)
    return tmp_path


def test_show_on_a_record_that_does_not_parse_reports_the_error(tmp_path):
    """load_records returns the error and nothing read it, so the record was
    dropped from the corpus and a search for a decision it holds answered
    "nothing written down here matches" at exit 0. The name matched — saying
    nothing is called that would be false."""
    root = project(tmp_path)
    (root / "specs" / "versions" / "broken-minor.toml").write_text(
        'name = "broken"\nsummary = "unterminated\n'
    )
    found = ledger.corpus(root)
    assert [r.name for r in found.records if r.error] == ["broken"]

    text, code = ledger.show(found, "broken")
    assert code == 1
    assert "broken-minor.toml" in text and "flw validate" in text


def test_the_corpus_reads_the_contract_and_the_records(tmp_path):
    found = ledger.corpus(project(tmp_path))
    assert found.contract["spec_version"] == "0.1.0"
    assert [r.name for r in found.records] == ["first"]


def test_a_rendered_plan_is_not_read_beside_its_markdown(tmp_path):
    """plans/*.html is the same content in markup. Searching it means searching
    CSS: plans/code-graph-report.html in this repository holds 73 whole-word
    occurrences of `font`."""
    root = project(tmp_path)
    (root / "plans").mkdir()
    (root / "plans" / "design.md").write_text("the markdown says peculiarword")
    (root / "plans" / "design.html").write_text("<p>the markup says peculiarword</p>")

    plans = ledger.corpus(root).plans
    assert [p.name for p in plans] == ["design.md"]


def test_nothing_under_flw_reports_is_read(tmp_path):
    """.flw/reports/ is gitignored, so a corpus that read it would answer one way
    on this machine and another way on a fresh clone. Team configs under
    .flw/reviews/ are tracked and are read."""
    root = project(tmp_path)
    (root / ".flw" / "reports").mkdir(parents=True)
    (root / ".flw" / "reviews").mkdir(parents=True)
    (root / ".flw" / "reports" / "yesterday.md").write_text("a finding nobody specced")
    (root / ".flw" / "reviews" / "eng.toml").write_text(
        'name = "eng"\n[[reviewer]]\nrole = "footprint"\n'
    )

    found = ledger.corpus(root)
    assert [p.name for p in found.reviews] == ["eng.toml"]
    assert not any("reports" in str(p) for p in found.plans)


def test_flw_dir_relocates_the_reviews_directory(tmp_path, monkeypatch):
    """ledger.py reads $FLW_DIR the way run_tests.py reads $FLW_HOME, so a
    renamed per-project directory's reviews are found without importing
    cli/flw.py, and a stale one under the old name is not."""
    root = project(tmp_path)
    monkeypatch.setenv("FLW_DIR", ".cache/flw")
    (root / ".cache" / "flw" / "reviews").mkdir(parents=True)
    (root / ".cache" / "flw" / "reviews" / "eng.toml").write_text(
        'name = "eng"\n[[reviewer]]\nrole = "footprint"\n'
    )
    (root / ".flw" / "reviews").mkdir(parents=True)
    (root / ".flw" / "reviews" / "old.toml").write_text(
        'name = "old"\n[[reviewer]]\nrole = "footprint"\n'
    )

    found = ledger.corpus(root)
    assert [p.name for p in found.reviews] == ["eng.toml"]


def test_a_project_with_a_contract_and_nothing_else_assembles(tmp_path):
    """No plans/, no .flw/. The ordinary shape of a project on the day flw is
    adopted, and it must not need a directory it has no reason to have."""
    found = ledger.corpus(project(tmp_path))
    assert found.plans == {}
    assert found.reviews == {}


def test_a_project_with_no_contract_yet_still_reads_its_records(tmp_path):
    """A contract is a state, not a precondition. flw validate already treats a
    missing one as exit 0."""
    root = project(tmp_path)
    (root / "specs" / "current.toml").unlink()
    found = ledger.corpus(root)
    assert found.contract == {}
    assert [r.name for r in found.records] == ["first"]


def test_a_contract_that_does_not_parse_does_not_stop_the_records(tmp_path):
    """A malformed contract is flw validate's finding to report. Dying here would
    lose the records too, which is the half that would have answered."""
    root = project(tmp_path)
    (root / "specs" / "current.toml").write_text("schema_version = ")
    found = ledger.corpus(root)
    assert found.contract == {}
    assert [r.name for r in found.records] == ["first"]


def test_flws_own_corpus_assembles(tmp_path):
    """The real thing, not a fixture: every tier present and non-empty."""
    found = ledger.corpus(REPO)
    assert found.contract["schema_version"] == 4
    assert len(found.records) > 20
    assert found.plans and found.reviews
    assert all(p.suffix == ".md" for p in found.plans)


# --- matching --------------------------------------------------------------- #


def test_a_term_never_matches_a_longer_word_containing_it():
    """The measurement that decided this: substring `lock` matches 15 of the 26
    records here, through `block` and `blocked_by`. Whole words match 3."""
    match = ledger.pattern("lock")
    assert not match.search("blocked_by")
    assert not match.search("a blocking call")
    assert match.search("do not lock links.toml")


def test_whole_word_matching_holds_on_the_real_record_set():
    """Named records rather than a ratio. The ratio this replaced read 3 < 3.75,
    and the record that recorded the finding used `lock` as a word, took it to
    4 < 4.0 and failed — naming nothing about whole-word matching."""
    found = ledger.corpus(REPO)
    whole = ledger.pattern("lock")
    by_pattern = {r.name for r in found.records if whole.search(ledger._text_of(r.document))}
    by_substring = {
        r.name for r in found.records if "lock" in ledger._text_of(r.document).lower()
    }
    assert "install-robustness" in by_pattern, "the record that decided not to lock"
    # Reached only through `block` and `blocked_by`, which is what the whole-word
    # rule exists to refuse.
    through_block = by_substring - by_pattern
    assert through_block, by_substring
    assert "release-line" in through_block, sorted(through_block)


def test_a_term_matches_its_plural_and_participle_forms():
    assert ledger.pattern("remove").search("the check that keeps it removed")
    assert ledger.pattern("remove").search("removing the hook layer")
    assert ledger.pattern("decisions").search("a decision with one option")
    assert ledger.pattern("check").search("every check it ran passed")


def test_a_term_that_is_already_plural_still_finds_the_singular():
    """`removes` strips to both `remov` and `remove`, and only the second gets
    there. Stripping to the first candidate and stopping missed it."""
    assert ledger.pattern("removes").search("remove the hook layer")


def test_a_quoted_argument_is_a_phrase_that_survives_a_line_break():
    """Prose wraps. A phrase whose words land on two lines is still the phrase."""
    match = ledger.pattern("silent drift")
    assert match.search("no silent drift here")
    assert match.search("no silent\n    drift here")
    assert not match.search("silent, and separately drift")


# --- grouping and order ------------------------------------------------------ #

# Every contract field the search indexes carries the term. The fixture that
# preceded this declared `provides` alone, so five mutations that stopped
# indexing the others left the suite green.
RICHER = """schema_version = 4
spec_version = "0.2.0"
applied = ["1.0", "landed"]
assumptions = ["a peculiarword is assumed to exist"]
open_questions = ["whether the peculiarword is the right shape"]

[[final_state.components]]
name = "the thing"
paths = ["src/peculiarword.py"]
provides = ["A user can peculiarword the thing."]
properties = ["Every peculiarword is idempotent."]
surfaces = ["flw peculiarword [path]"]
implementation = "The peculiarword is a dict, built once per run."

[[final_state.removed]]
statement = "the old peculiarword path"
check = "test ! -e old"
"""


def richer(tmp_path: Path) -> Path:
    """A project with a legacy record, an applied one, and one still in flight."""
    (tmp_path / "specs" / "versions").mkdir(parents=True)
    (tmp_path / "specs" / "current.toml").write_text(RICHER)
    versions = tmp_path / "specs" / "versions"
    versions.joinpath("v1.0.toml").write_text(
        'name = "1.0"\nsummary = "the first peculiarword"\n'
    )
    versions.joinpath("landed-major.toml").write_text(
        'name = "landed"\nsummary = "peculiarword landed"\n'
        'contract_edit = "the contract gains a peculiarword"\n'
        '[[decisions]]\ntopic = "whether to peculiarword"\n'
        'options = ["Do it.", "Do not."]\nchosen = "Do it."\n'
        'rationale = "the peculiarword was worth it"\n'
        '[[dag]]\ngroup = 1\nphase = "build the peculiarword"\n'
        'tasks = [{ id = "t", desc = "build the peculiarword" }]\n'
    )
    versions.joinpath("inflight-minor.toml").write_text(
        'name = "inflight"\nsummary = "peculiarword in flight"\n'
    )
    (tmp_path / "plans").mkdir()
    (tmp_path / "plans" / "design.md").write_text("the peculiarword design, superseded")
    (tmp_path / ".flw" / "reviews").mkdir(parents=True)
    (tmp_path / ".flw" / "reviews" / "team.toml").write_text(
        'name = "team"\n[[reviewer]]\nrole = "lens"\n'
        'perspective = "hunt for a peculiarword"\n'
    )
    return tmp_path


def test_the_groups_print_binding_first(tmp_path):
    """CONTRACT before DECISION, which reverses the draft that called this `why`.
    What is invariant is not which group answers but which groups bind.

    Written out rather than compared against ledger.GROUPS, because a test that reads
    the order from the code under test cannot notice the order changing. Four
    mutations swapping pairs in GROUPS passed against the fixture this replaced,
    which put a hit in only four of the eight."""
    found = ledger.search(ledger.corpus(richer(tmp_path)), ["peculiarword"])
    assert list(found) == [
        "CONTRACT",
        "REMOVED",
        "DECISION",
        "CHANGED",
        "DONE",
        "WHY",
        "REVIEWS",
        "PLANS",
    ]


def test_every_contract_field_the_search_indexes_is_reachable(tmp_path):
    """A word appearing only in an assumption, an open question, a property or a
    surface line is a word the corpus holds. Five mutations that stopped indexing
    one each left the suite green."""
    hits = ledger.search(ledger.corpus(richer(tmp_path)), ["peculiarword"])["CONTRACT"]
    assert {h.label for h in hits} >= {
        "paths",
        "provides",
        "properties",
        "surfaces",
        "implementation",
        "assumption",
        "open question",
    }


def test_a_changed_hit_carries_the_classification(tmp_path):
    """CHANGED prints text CONTRACT already printed. Saying which version
    introduced it, and what kind of change it was, is the whole difference."""
    found = ledger.search(ledger.corpus(richer(tmp_path)), ["peculiarword"])
    changed = found["CHANGED"][0]
    assert changed.source == "landed"
    assert changed.note == "major"


def test_a_record_in_flight_sorts_above_one_the_contract_applied(tmp_path):
    """Written and not yet run is the newest thing there is. It appears in no
    applied list, which a naive ordering reads as `oldest`."""
    found = ledger.search(ledger.corpus(richer(tmp_path)), ["peculiarword"])
    assert [h.source for h in found["WHY"]] == ["inflight", "landed", "1.0"]


def test_a_legacy_record_sorts_below_every_applied_one(tmp_path):
    order = [ledger.recency(n, ["1.0", "landed"]) for n in ("inflight", "landed", "1.0")]
    assert order == sorted(order, reverse=True)


# --- what the report refuses to hide ----------------------------------------- #


def test_a_capped_group_says_how_many_it_did_not_print(tmp_path):
    """A truncated result set that does not announce its truncation reads as a
    complete answer, which is the failure one level up this command prevents."""
    root = project(tmp_path)
    tasks = ", ".join(
        f'{{ id = "t{i}", desc = "peculiarword number {i}" }}' for i in range(ledger.CAP + 3)
    )
    (root / "specs" / "versions" / "many-minor.toml").write_text(
        f'name = "many"\nsummary = "s"\n[[dag]]\ngroup = 1\ntasks = [{tasks}]\n'
    )
    report = ledger.render_search(
        ledger.search(ledger.corpus(root), ["peculiarword"]), ["peculiarword"]
    )
    assert "3 more in DONE" in report
    assert report.count("peculiarword number") == ledger.CAP


def test_a_decision_prints_whole_rather_than_windowed(tmp_path):
    """A paraphrased decision is a decision misrepresented, and truncating the
    reasoning to fit a window paraphrases by omission."""
    root = project(tmp_path)
    rationale = "because " + "the reason runs long " * 40
    (root / "specs" / "versions" / "decided-minor.toml").write_text(
        'name = "decided"\nsummary = "s"\n[[decisions]]\n'
        'topic = "whether to peculiarword"\n'
        'options = ["Do it.", "Do not."]\nchosen = "Do it."\n'
        f'rationale = "{rationale}"\n'
    )
    report = ledger.render_search(
        ledger.search(ledger.corpus(root), ["peculiarword"]), ["peculiarword"]
    )
    assert "chose" in report and "over" in report and "because" in report
    assert "Do not." in report, "the rejected option is the half you need later"
    assert "…" not in report.split("DECISION")[1].split("\n\n")[0]


def test_a_query_matching_nothing_says_so(tmp_path):
    report = ledger.render_search(
        ledger.search(ledger.corpus(project(tmp_path)), ["nothinghere"]), ["nothinghere"]
    )
    assert "nothing written down here matches" in report


def test_terms_are_anded_across_a_whole_document(tmp_path):
    """Two words in one record, one in its summary and one in a task, is a hit.
    Requiring both in the same field would miss the record that discusses both."""
    root = project(tmp_path)
    (root / "specs" / "versions" / "both-minor.toml").write_text(
        'name = "both"\nsummary = "alphaword here"\n'
        '[[dag]]\ngroup = 1\ntasks = [{ id = "t", desc = "betaword there" }]\n'
    )
    (root / "specs" / "versions" / "one-minor.toml").write_text(
        'name = "one"\nsummary = "alphaword only"\n'
    )
    found = ledger.search(ledger.corpus(root), ["alphaword", "betaword"])
    assert {h.source for hits in found.values() for h in hits} == {"both"}


# --- reading one thing by name ----------------------------------------------- #


def test_a_record_is_found_by_name_whatever_its_classification(tmp_path):
    """The reason this is worth a flag: `landed` lives in `landed-major.toml` and
    the suffix is the classification, which is what you were going to ask about."""
    text, code = ledger.show(ledger.corpus(richer(tmp_path)), "landed")
    assert code == 0
    assert text.startswith("landed")
    assert "[major]" in text


def test_a_contract_component_is_found_by_name(tmp_path):
    text, code = ledger.show(ledger.corpus(richer(tmp_path)), "the thing")
    assert code == 0
    assert "src/" in text and "PROVIDES" in text


def test_a_name_nothing_answers_to_exits_one_and_says_where_it_looked(tmp_path):
    """A search with no hits is an answer; a lookup that failed is not."""
    text, code = ledger.show(ledger.corpus(richer(tmp_path)), "never-existed")
    assert code == 1
    assert "version records" in text and "contract components" in text


def test_a_name_that_answers_twice_prints_both(tmp_path):
    """Record names are kebab-case and component names are prose, so this cannot
    happen today. Guessing which was meant is how a lookup starts answering a
    question nobody asked."""
    root = richer(tmp_path)
    (root / "specs" / "versions" / "the thing-minor.toml").write_text(
        'name = "the thing"\nsummary = "a record wearing a component name"\n'
    )
    text, code = ledger.show(ledger.corpus(root), "the thing")
    assert code == 0
    assert "names 2 things" in text
    assert "a record wearing a component name" in text and "PROVIDES" in text


def test_a_record_renders_its_decisions_whole(tmp_path):
    root = project(tmp_path)
    (root / "specs" / "versions" / "decided-minor.toml").write_text(
        'name = "decided"\nsummary = "s"\n[[decisions]]\n'
        'topic = "whether to do it"\noptions = ["Do it.", "Do not."]\n'
        'chosen = "Do it."\nrationale = "the whole reason, verbatim"\n'
    )
    text, _ = ledger.show(ledger.corpus(root), "decided")
    assert "chose" in text and "Do not." in text
    assert "the whole reason, verbatim" in text


def test_flws_own_records_all_render(tmp_path):
    """Every record in this repository, not a fixture: rendering must not depend
    on a field a record happens to carry.

    Asserting what each record carries, not that something came back. `code == 0
    and text.strip()` holds for a two-line output naming the record and its
    filename, so deleting the approach branch or the dag branch from
    render_record left this — the only test that renders the real records —
    green."""
    found = ledger.corpus(REPO)
    for record in found.records:
        text, code = ledger.show(found, record.name)
        assert code == 0 and text.strip(), record.name
        if record.document.get("approach"):
            assert "APPROACH" in text, record.name
        if record.document.get("dag"):
            assert "PLAN" in text, record.name
        if record.document.get("decisions"):
            assert "DECISION" in text, record.name
        if record.document.get("contract_edit"):
            assert "CONTRACT EDIT" in text, record.name


# --- the census -------------------------------------------------------------- #


def test_the_census_counts_what_is_there(tmp_path):
    """The first thing to run in a repository nobody has read."""
    report = ledger.census(ledger.corpus(richer(tmp_path)))
    assert "3 version records" in report
    assert "2 applied" in report
    assert "1 written and not yet run" in report


def test_the_census_lists_the_newest_first(tmp_path):
    """The `newest few` the census promises. Emptying the block passed, and so did
    dropping reverse=True — which lists the oldest records under the heading that
    says newest."""
    report = ledger.census(ledger.corpus(richer(tmp_path)))
    newest = report.split("NEWEST")[1].strip()
    assert newest.startswith("inflight"), newest[:120]
    assert newest.index("landed") < newest.index("1.0")


def test_the_census_names_the_standing_contract_state(tmp_path):
    """Assumptions and open questions are what somebody is about to contradict,
    and what is removed is what they are about to reintroduce."""
    report = ledger.census(ledger.corpus(REPO))
    assert "OPEN QUESTIONS" in report and "REMOVED" in report and "ASSUMPTIONS" in report


def test_the_census_says_how_many_it_did_not_print(tmp_path):
    """Same rule as a search: a list that stops without saying so reads complete."""
    report = ledger.census(ledger.corpus(REPO))
    assert "more removed" in report


def test_a_contract_with_no_open_questions_omits_the_heading(tmp_path):
    """An empty heading reads as a project that answered them all."""
    report = ledger.census(ledger.corpus(project(tmp_path)))
    assert "OPEN QUESTIONS" not in report


def test_the_census_needs_no_contract(tmp_path):
    """A project part way through adopting flw has records and no contract yet."""
    root = richer(tmp_path)
    (root / "specs" / "current.toml").unlink()
    report = ledger.census(ledger.corpus(root))
    assert "no release number" in report
    assert "3 version records" in report


# --- the subcommand ---------------------------------------------------------- #


def run(monkeypatch, root: Path, term=(), show=None) -> int:
    import argparse

    from tests.test_cli import flw

    monkeypatch.chdir(root)
    return flw.ledger(argparse.Namespace(term=list(term), show=show))


def test_the_subcommand_searches_and_exits_zero(tmp_path, monkeypatch, capsys):
    code = run(monkeypatch, richer(tmp_path), term=["peculiarword"])
    assert code == 0
    assert "CONTRACT" in capsys.readouterr().out


def test_a_search_with_no_hits_still_exits_zero(tmp_path, monkeypatch, capsys):
    """Nothing written about it is an answer, and a shell that treats it as a
    failure makes the command unusable in a pipeline."""
    code = run(monkeypatch, richer(tmp_path), term=["nothinghere"])
    assert code == 0
    assert "nothing written down here matches" in capsys.readouterr().out


def test_show_with_an_unknown_name_exits_one_to_stderr(tmp_path, monkeypatch, capsys):
    code = run(monkeypatch, richer(tmp_path), show="never-existed")
    assert code == 1
    assert "never-existed" in capsys.readouterr().err


def test_the_subcommand_with_no_argument_is_the_census(tmp_path, monkeypatch, capsys):
    code = run(monkeypatch, richer(tmp_path))
    assert code == 0
    assert "how it got here" in capsys.readouterr().out


# --- a term the corpus holds is never reported as unwritten ------------------ #
#
# Measured before this: of a 6,322-word vocabulary built out of the corpus, 191
# terms matched a document and printed nothing, because the per-hit filter read
# only the hit's body. A task id is its label and a removal check is its note.

SILENT = """schema_version = 4
spec_version = "0.1.0"
applied = ["one"]
assumptions = ["assumeword is taken for granted"]

[[final_state.components]]
name = "the thing"
paths = ["src/pathword.py"]
provides = ["A user can do the thing."]

[[final_state.removed]]
statement = "the old path"
check = "test ! -e checkword"
"""

SILENT_RECORD = """name = "one"
summary = "s"
[[dag]]
group = 1
phase = "phaseword the phase"
tasks = [{ id = "idword-task", desc = "what the task did" }]
"""


def silent(tmp_path: Path) -> Path:
    (tmp_path / "specs" / "versions").mkdir(parents=True)
    (tmp_path / "specs" / "current.toml").write_text(SILENT)
    (tmp_path / "specs" / "versions" / "one-minor.toml").write_text(SILENT_RECORD)
    (tmp_path / ".flw" / "reviews").mkdir(parents=True)
    (tmp_path / ".flw" / "reviews" / "t.toml").write_text(
        'name = "t"\ndescription = "descword, what this team is for"\n'
        '[[reviewer]]\nrole = "r"\nperspective = "look at things"\n'
    )
    return tmp_path


def test_a_term_found_only_in_a_task_id_is_a_hit(tmp_path):
    """229 task ids in this repository lived in Hit.label and matched nothing.
    They are the most specifically searchable content there is — a task
    description names a file and a line number."""
    found = ledger.search(ledger.corpus(silent(tmp_path)), ["idword-task"])
    assert [h.source for h in found["DONE"]] == ["one"]


def test_a_term_found_only_in_a_removal_check_is_a_hit(tmp_path):
    """A removal check is the command that keeps a thing deleted. Searching for
    it is how you find out the deletion was deliberate."""
    found = ledger.search(ledger.corpus(silent(tmp_path)), ["checkword"])
    assert found["REMOVED"]


def test_a_term_found_only_in_a_component_path_is_a_hit(tmp_path):
    """A path is the most concrete thing a component says, and it appears in no
    other tier — so `flw ledger <a file>` reached nothing at all."""
    found = ledger.search(ledger.corpus(silent(tmp_path)), ["src/pathword.py"])
    assert found["CONTRACT"]


def test_a_term_found_only_in_a_dag_phase_or_a_team_description_is_a_hit(tmp_path):
    """The last two tiers that reached no hit. Both are prose someone wrote about
    the work, which is the whole corpus definition."""
    corpus = ledger.corpus(silent(tmp_path))
    assert ledger.search(corpus, ["phaseword"])["DONE"]
    assert ledger.search(corpus, ["descword"])["REVIEWS"]


def test_a_term_edged_with_punctuation_matches(tmp_path):
    """`\\b` asserts a word character inside the boundary, so a term opening with
    a dot could not match at any position, so `.flw` reached nothing anywhere in
    this repository's corpus. The count that stood here counted itself: it moved
    the moment this version's own record landed."""
    assert ledger.pattern(".flw").search("under .flw/reviews")
    assert ledger.pattern("--all").search("run flw test --all here")
    assert ledger.pattern(".gitignore").search("excluded at .gitignore:9")


def test_the_whole_word_rule_survives_the_lookaround(tmp_path):
    """The reason `\\b` was there. Whichever way the boundary is spelled, a query
    for one word must never match a longer word containing it."""
    assert not ledger.pattern("lock").search("blocked_by")
    assert not ledger.pattern("lock").search("a blocking call")
    assert not ledger.pattern(".flw").search("x.flwy")


def test_an_empty_term_matches_nothing(tmp_path):
    """It compiled to an alternation with an empty branch, matching at every word
    boundary. `flw ledger ""` printed the whole corpus."""
    assert ledger.forms("") == []
    assert ledger.forms("   ") == []
    assert not ledger.pattern("").search("anything at all")
    assert ledger.search(ledger.corpus(silent(tmp_path)), [""]) == {}


def test_an_empty_term_does_not_widen_a_sibling_term(tmp_path):
    """The second half of the damage: search() prints a hit when *any* pattern
    matches, so one empty argument switched the per-hit filter off and every unit
    of every matching document printed."""
    corpus = ledger.corpus(silent(tmp_path))
    assert ledger.search(corpus, ["idword-task", ""]) == {}


def test_a_window_contains_the_term_it_was_searched_for(tmp_path):
    """find() returning -1 — no space in the hundred characters before the match —
    was taken as offset zero, which moved the window past the match and printed a
    body without the term in it.

    The run before the match is unbroken, and the term is edged by `/` rather than
    a space so it is still a whole word. An earlier version of this test padded
    with a word character instead, which the boundary rule correctly refused, so
    it asserted against the no-match line and passed vacuously."""
    root = project(tmp_path)
    (root / "specs" / "versions" / "long-minor.toml").write_text(
        'name = "long"\nsummary = "s"\napproach = "'
        + "z" * 250
        + '/peculiarword and then a tail long enough that the whole field runs past'
        + ' the three hundred characters below which nothing is windowed at all"\n'
    )
    report = ledger.render_search(
        ledger.search(ledger.corpus(root), ["peculiarword"]), ["peculiarword"]
    )
    body = report.split("WHY")[1]
    assert "peculiarword" in body, body
    assert "…" in body, "a truncated window says it was truncated"


def test_an_unbroken_field_is_still_capped(tmp_path):
    """rfind() returning -1 became flat[start:-1] — the whole field minus one
    character. One 200,000-character token printed 2,384 lines and 211,930 bytes
    where a window was documented."""
    root = project(tmp_path)
    (root / "specs" / "versions" / "solid-minor.toml").write_text(
        'name = "solid"\nsummary = "s"\napproach = "peculiarword/' + "z" * 5000 + '"\n'
    )
    report = ledger.render_search(
        ledger.search(ledger.corpus(root), ["peculiarword"]), ["peculiarword"]
    )
    assert "peculiarword" in report, "the fixture must actually match"
    assert len(report) < 1000, len(report)


# --- one bad byte is not a traceback ---------------------------------------- #
#
# UnicodeDecodeError is a ValueError, and the CLI handler catches OSError, so a
# single byte that is not UTF-8 anywhere in the corpus killed search, --show and
# the census alike. The command handles every neighbouring filesystem condition
# correctly — permission denied, a dangling symlink, a directory where a file was
# expected — which is what made this a bug rather than a policy.

BAD = b"a widget note with a \xff bad byte in it\n"


def test_a_plan_that_is_not_utf8_is_still_searched(tmp_path):
    """plans/ is the tier a real project reaches, through a design note carrying a
    latin-1 paste. Skipping the file would lose 28,793 words of this repository's
    corpus for one character; replacement keeps every word around it findable."""
    root = project(tmp_path)
    (root / "plans").mkdir()
    (root / "plans" / "bad.md").write_bytes(BAD)
    found = ledger.search(ledger.corpus(root), ["widget"])
    assert [h.source for h in found["PLANS"]] == ["plans/bad.md"]


def test_a_record_that_is_not_utf8_does_not_stop_the_others(tmp_path):
    """A record that cannot be decoded cannot be parsed either, so it is skipped
    with the rest still searched — the same treatment a TOML syntax error gets."""
    root = project(tmp_path)
    (root / "specs" / "versions" / "bad-minor.toml").write_bytes(BAD)
    found = ledger.corpus(root)
    bad = next(r for r in found.records if r.name == "bad")
    assert bad.document == {} and "does not parse" in bad.error
    assert [r.name for r in found.records if r.error is None] == ["first"]


def test_a_contract_or_a_team_config_that_is_not_utf8_is_skipped(tmp_path):
    """Neither may take the whole query down with it. The records are the half
    that would have answered."""
    root = project(tmp_path)
    (root / ".flw" / "reviews").mkdir(parents=True)
    (root / ".flw" / "reviews" / "bad.toml").write_bytes(BAD)
    (root / "specs" / "current.toml").write_bytes(BAD)
    found = ledger.corpus(root)
    assert found.contract == {} and found.reviews == {}
    assert [r.name for r in found.records] == ["first"]


def test_validate_names_a_file_that_is_not_utf8(tmp_path):
    """flw validate is the command whose entire job is reporting a document it
    cannot read, and it raised out of tomllib instead of naming the path."""
    from core.scripts import validate_spec

    bad = tmp_path / "bad.toml"
    bad.write_bytes(BAD)
    schema = REPO / "core" / "schemas" / "version.schema.json"
    code, messages = validate_spec.validate_file(bad, schema)
    assert code == 1
    assert str(bad) in messages[0] and "does not parse" in messages[0]


def test_a_contract_component_with_no_name_does_not_stop_a_search(tmp_path):
    """A missing name is a shape error flw validate reports by name. Here it must
    not take down the search that was asked for — the census already survived it
    and the other two surfaces did not."""
    root = project(tmp_path)
    (root / "specs" / "current.toml").write_text(
        'schema_version = 4\nspec_version = "0.1.0"\napplied = ["first"]\n'
        '[[final_state.components]]\npaths = ["src/"]\n'
        'provides = ["A user can peculiarword."]\n'
    )
    assert ledger.search(ledger.corpus(root), ["peculiarword"])["CONTRACT"]
    assert ledger.show(ledger.corpus(root), "first")[1] == 0


# --- the subcommand honours the contract ------------------------------------ #


def test_show_with_an_empty_name_exits_one(tmp_path, monkeypatch, capsys):
    """`if args.show:` is falsy on "", so an unset variable fell through to the
    census and reported success. The contract is verbatim: a name that resolves
    to no record or component exits 1."""
    assert run(monkeypatch, richer(tmp_path), show="") == 1
    out = capsys.readouterr()
    assert "how it got here" not in out.out, "the census must not answer a lookup"
    assert "nothing here is called" in out.err


def test_a_search_and_a_show_both_name_the_root(tmp_path, monkeypatch, capsys):
    """project_root walks upward, so a command issued from the wrong directory is
    answered by an ancestor. The component provides that a user is told which root
    a command resolved to; only the census did."""
    root = richer(tmp_path)
    (root / "src" / "deep").mkdir(parents=True)
    monkeypatch.chdir(root / "src" / "deep")
    import argparse

    from tests.test_cli import flw

    flw.ledger(argparse.Namespace(term=["peculiarword"], show=None))
    assert f"root: {root}" in capsys.readouterr().out

    flw.ledger(argparse.Namespace(term=[], show="landed"))
    assert f"root: {root}" in capsys.readouterr().out


def test_the_census_names_the_root_once(tmp_path, monkeypatch, capsys):
    """The line moved out of census() when the handler grew one, so that there is
    one place it comes from."""
    root = richer(tmp_path)
    run(monkeypatch, root)
    out = capsys.readouterr().out
    # The path, not the label: census printed the bare path, so counting the
    # label alone stayed at 1 while the path appeared twice.
    assert out.count(str(root)) == 1, out[:200]


def test_the_no_match_line_ends_with_a_newline(tmp_path):
    """Every other output path does, and the CLI prints with end="", so a search
    with no hits left the prompt on the answer's line."""
    report = ledger.render_search(
        ledger.search(ledger.corpus(project(tmp_path)), ["nothinghere"]), ["nothinghere"]
    )
    assert report.endswith("\n")


def test_the_census_counts_records_that_exist(tmp_path):
    """A contract naming a record with no file printed a count larger than the set
    it had just described. flw validate names the missing record; the census said
    nothing and its own arithmetic disagreed."""
    root = richer(tmp_path)
    (root / "specs" / "current.toml").write_text(
        (root / "specs" / "current.toml").read_text().replace(
            'applied = ["1.0", "landed"]', 'applied = ["1.0", "landed", "vanished"]'
        )
    )
    report = ledger.census(ledger.corpus(root))
    assert "3 version records — 2 applied" in report


# --- what the first pass at these fixes still got wrong ---------------------- #


def test_a_window_keeps_the_match_when_the_last_space_precedes_it(tmp_path):
    """rfind gives the LAST space in the range, which can sit before the match —
    so the tail retreated past it and the body ended before it began. Handling
    the -1 sentinel on both sides did not cover this; the tail must be floored at
    the match. The realistic shape is a long URL with the term inside it."""
    root = project(tmp_path)
    url = "https://example.invalid/" + "a" * 60 + "/peculiarword/" + "b" * 200
    (root / "specs" / "versions" / "url-minor.toml").write_text(
        f'name = "url"\nsummary = "s"\napproach = "The slash was settled. See {url}"\n'
    )
    report = ledger.render_search(
        ledger.search(ledger.corpus(root), ["peculiarword"]), ["peculiarword"]
    )
    assert "peculiarword" in report.split("WHY")[1]


def test_an_empty_show_name_is_refused_before_either_lookup(tmp_path):
    """Two fixes in one version collided. `--show ""` reaching show() is right;
    a nameless contract component not raising is right. Together the empty name
    resolved to the nameless component and reported success — which is what the
    first fix existed to stop."""
    root = project(tmp_path)
    (root / "specs" / "current.toml").write_text(
        'schema_version = 4\nspec_version = "0.1.0"\napplied = ["first"]\n'
        '[[final_state.components]]\npaths = ["src/"]\nprovides = ["it works"]\n'
    )
    text, code = ledger.show(ledger.corpus(root), "")
    assert code == 1, text
    assert "nothing here is called" in text


def test_an_empty_record_name_is_refused_too(tmp_path):
    """The other route to the same place: parse_record_filename("-minor.toml")
    returns ("", "minor"), so a record file named that way answers to "" as well."""
    root = project(tmp_path)
    (root / "specs" / "versions" / "-minor.toml").write_text('name = ""\nsummary = "s"\n')
    assert ledger.show(ledger.corpus(root), "  ")[1] == 1


def test_a_config_that_is_not_utf8_names_the_file_rather_than_raising(tmp_path):
    """The third copy of the guard this version widened twice. _section_config runs
    before the corpus is built, so the two guards inside ledger.py are never reached —
    flw ledger, flw validate and flw test all died on one byte in .flw/config.toml."""
    import pytest

    from tests.test_cli import flw

    (tmp_path / ".flw").mkdir()
    (tmp_path / ".flw" / "config.toml").write_bytes(b'[paths]\nspecs = "sp\xe9cs"\n')
    with pytest.raises(SystemExit) as raised:
        flw._section_config(tmp_path, "paths")
    assert "config.toml" in str(raised.value) and "does not parse" in str(raised.value)
