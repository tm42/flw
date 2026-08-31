"""The CLI, driven against a fake HOME.

Every test here covers something that would otherwise go wrong quietly: an
install that looks complete and is not, a doctor that reports OK on a broken
link graph, an uninstall that leaves a fragment of flw in the user's own
instructions file. None of it is visible without checking.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("flw_cli", REPO / "cli" / "flw.py")
flw = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = flw
_spec.loader.exec_module(flw)


SKILL = "---\nname: {name}\ndescription: {name}, for a test.\n---\n\nDo the thing.\n"

# The real one, captured before the `home` fixture patches it away.
REAL_PRESENT = flw.present


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A fake HOME with flw's state redirected into it.

    cwd moves too: `doctor`'s extensions section is project-scoped, so a test
    left standing in flw's own checkout would report on flw's own extensions.

    Every host counts as present by default. `present()` consults PATH and the
    host's own config directory, so without this the suite would test one thing
    on a machine with Codex installed and another on a machine without it.
    Tests that care about absence override it.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(flw, "present", lambda host: True)
    fake = tmp_path / "home"
    fake.mkdir()
    monkeypatch.setenv("HOME", str(fake))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake))
    monkeypatch.setattr(flw, "FLW_HOME", fake / ".flw")
    monkeypatch.setattr(flw, "ROOT_POINTER", fake / ".flw" / "root")
    monkeypatch.setattr(flw, "BUNDLES", fake / ".flw" / "bundles.toml")
    monkeypatch.setattr(flw, "LINKS", fake / ".flw" / "links.toml")
    monkeypatch.setattr(flw, "STYLE", fake / ".flw" / "style.toml")
    monkeypatch.setattr(flw, "AMBIENT", fake / ".flw" / "ambient.toml")
    monkeypatch.setattr(flw, "STYLES_DIR", fake / ".flw" / "styles")
    return fake


@pytest.fixture
def bundle(tmp_path):
    """A bundle carrying one new skill and one that shadows a core skill."""

    def build(*names: str) -> Path:
        root = tmp_path / "bundle"
        for name in names:
            directory = root / "skills" / name
            directory.mkdir(parents=True)
            (directory / "SKILL.md").write_text(SKILL.format(name=name))
        return root

    return build


def install(*hosts: str, ambient: bool = False, dry: bool = False) -> int:
    return flw.install(
        argparse.Namespace(hosts=list(hosts), dry_run=dry, ambient=ambient, yes=True)
    )


def doctor() -> int:
    return flw.doctor(argparse.Namespace(verbose=False))


def uninstall(*hosts: str) -> int:
    return flw.uninstall(argparse.Namespace(hosts=list(hosts), dry_run=False))


def sync(*, dry: bool = False, yes: bool = True) -> int:
    return flw.sync(argparse.Namespace(dry_run=dry, yes=yes))


def style_install(name: str | None = None, *hosts: str, yes: bool = True) -> int:
    return flw.style_install(
        argparse.Namespace(name=name, host=list(hosts), dry_run=False, yes=yes)
    )


def style_uninstall(*hosts: str) -> int:
    return flw.style_uninstall(argparse.Namespace(host=list(hosts), dry_run=False))


def style_install_dry(name: str | None = None, *hosts: str) -> int:
    return flw.style_install(
        argparse.Namespace(name=name, host=list(hosts), dry_run=True, yes=True)
    )


def update(*, yes: bool = False, dry: bool = False) -> int:
    return flw.update(argparse.Namespace(yes=yes, dry_run=dry))


def fake_checkout(monkeypatch, home, shipped: str | None = None) -> Path:
    """A directory that passes update's `.git` guard.

    `shipped` plants a stand-in for flw's own style file, so a test can move
    that source without editing the one in flw's repository.
    """
    repo = home / "repo"
    (repo / ".git").mkdir(parents=True, exist_ok=True)
    if shipped is not None:
        source = repo / "core" / "styles" / "terse_prose.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(shipped)
    monkeypatch.setattr(flw, "checkout", lambda: repo)
    return repo


def fake_pull(monkeypatch, home, shipped: str | None = None):
    """The pull and upstream lookup are faked so the test needs no real remote."""
    fake_checkout(monkeypatch, home, shipped)

    def fake_git(*args):
        if args and args[0] == "pull":
            return SimpleNamespace(returncode=0, stdout="already up to date\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="origin/main\n", stderr="")

    monkeypatch.setattr(flw, "git", fake_git)


# --- link planning ------------------------------------------------------- #


def test_two_link_sets_serve_three_hosts(home):
    """OpenCode reads Claude Code's skill directory and Codex's, so installing
    all three must not create a third."""
    link_into, covered = flw.plan_roots(list(flw.HOSTS))

    assert set(link_into) == {"claude-code", "codex"}
    assert covered["opencode"] == home / ".claude" / "skills"


def test_a_host_installed_alone_gets_its_own_root(home):
    link_into, covered = flw.plan_roots([flw.BY_NAME["opencode"]])
    assert link_into["opencode"] == home / ".config" / "opencode" / "skills"
    assert covered == {}


# --- install ------------------------------------------------------------- #


def test_install_links_every_skill_and_records_it(home, capsys):
    assert install() == 0
    capsys.readouterr()

    # Every skill flw knows about, not a hardcoded list — adding one to core/
    # should not require editing a test to keep it installed.
    expected = sorted(s.name for s in flw.discover()[0])
    assert "flw-spec" in expected and "flw-execute" in expected

    for root in (home / ".claude" / "skills", home / ".agents" / "skills"):
        links = sorted(p.name for p in root.iterdir())
        assert links == expected
        assert all((root / name).is_symlink() for name in links)

    assert flw.ROOT_POINTER.read_text().strip() == str(flw.checkout())
    assert {link["skill"] for link in flw.read_links()} == set(expected)


def test_a_dry_run_writes_nothing(home, capsys):
    assert install(dry=True) == 0
    capsys.readouterr()
    assert not (home / ".claude").exists()
    assert not flw.ROOT_POINTER.exists()
    assert flw.read_links() == []


def test_an_interrupted_install_over_claims_rather_than_under_claims(
    home, monkeypatch, capsys
):
    """The record is written before the symlink it describes, not after — so
    an interruption leaves the record naming a path with nothing there yet,
    which `sync` classifies as missing and repairs.

    The opposite order — creating the link, then recording it — would instead
    leave that same symlink real on disk and named nowhere: doctor can only
    ever call that untracked, not missing, because nothing in the record
    points at it to compare against. This test pins both halves: what the
    order used here leaves behind, and what the reverse would leave instead.
    """
    calls = {"n": 0}
    real_symlink_to = Path.symlink_to

    def flaky(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("simulated interruption")
        return real_symlink_to(self, *args, **kwargs)

    monkeypatch.setattr(Path, "symlink_to", flaky)
    with pytest.raises(OSError):
        install("claude-code")
    capsys.readouterr()

    root = home / ".claude" / "skills"
    on_disk = {p.name for p in root.iterdir() if p.is_symlink()}
    recorded_names = {link["skill"] for link in flw.read_links()}

    interrupted = recorded_names - on_disk
    assert interrupted, "the interrupted skill should be recorded with nothing on disk"

    # The interruption also happened before ROOT_POINTER was written, which is
    # a separate concern from what this test pins; set it as a later
    # successful run would, so `doctor` below reports only on the links.
    flw.ROOT_POINTER.write_text(f"{flw.checkout()}\n")

    assert sync() == 0
    capsys.readouterr()
    assert doctor() == 0

    # Manufacture what the reverse order would have left behind instead: a
    # real symlink with no record naming it.
    orphan = root / "an-unrecorded-skill"
    orphan.symlink_to(flw.discover()[0][0].path, target_is_directory=True)
    doctor()
    out = capsys.readouterr().out
    assert "an-unrecorded-skill" not in {link["skill"] for link in flw.read_links()}
    assert "points into flw but was not created by it" in out


def test_installing_one_host_does_not_forget_another(home, capsys):
    install("claude-code")
    install("codex")
    capsys.readouterr()

    roots = {Path(link["path"]).parent for link in flw.read_links()}
    assert roots == {home / ".claude" / "skills", home / ".agents" / "skills"}


def test_install_refuses_to_replace_a_real_directory(home, capsys):
    squatter = home / ".claude" / "skills" / "flw-spec"
    squatter.mkdir(parents=True)
    (squatter / "SKILL.md").write_text("someone else's skill")

    install("claude-code")
    assert "will not replace it" in capsys.readouterr().err
    assert not squatter.is_symlink()
    assert (squatter / "SKILL.md").read_text() == "someone else's skill"


# --- bundles and overrides ------------------------------------------------ #


def test_a_bundle_skill_shadowing_core_is_reported_not_hidden(home, bundle, capsys):
    flw.add(argparse.Namespace(path=str(bundle("flw-spec", "team-review")), name=None))
    install()
    out = capsys.readouterr().out

    assert "override: flw-spec from [bundle] shadows [core]" in out
    target = (home / ".claude" / "skills" / "flw-spec").resolve()
    assert target.parent.parent.name == "bundle"


def test_removing_a_bundle_unlinks_its_skills(home, bundle, capsys):
    flw.add(argparse.Namespace(path=str(bundle("team-review")), name=None))
    install()
    assert (home / ".claude" / "skills" / "team-review").is_symlink()

    flw.remove(argparse.Namespace(name="bundle"))
    capsys.readouterr()

    assert not (home / ".claude" / "skills" / "team-review").exists()
    assert (home / ".claude" / "skills" / "flw-spec").is_symlink()
    assert doctor() == 0


def test_a_bundle_without_a_skills_directory_is_refused(home, tmp_path, capsys):
    (tmp_path / "not-a-bundle").mkdir()
    assert (
        flw.add(argparse.Namespace(path=str(tmp_path / "not-a-bundle"), name=None)) == 1
    )
    assert "has no skills/ directory" in capsys.readouterr().err


# --- doctor --------------------------------------------------------------- #


def test_doctor_is_clean_after_install(home, capsys):
    install()
    capsys.readouterr()
    assert doctor() == 0
    assert "OK" in capsys.readouterr().out


def test_doctor_catches_a_deregistered_bundle(home, bundle, capsys):
    """The case that used to report OK.

    Deregistering a bundle by hand left its links pointing at a path flw no
    longer knew. Ownership inferred from the disk made them invisible rather
    than broken — so doctor passed an install where a core skill was shadowed,
    then abandoned, and linked nowhere.
    """
    flw.add(argparse.Namespace(path=str(bundle("flw-spec", "team-review")), name=None))
    install()
    flw.BUNDLES.write_text("# emptied by hand\n")
    capsys.readouterr()

    assert doctor() == 1
    out = capsys.readouterr().out
    assert "team-review — orphan" in out
    assert "flw-spec — stale" in out
    assert "Run `flw sync`" in out
    assert "flw-spec — stale" in out


def test_doctor_catches_a_dangling_link(home, bundle, capsys, tmp_path):
    path = bundle("team-review")
    flw.add(argparse.Namespace(path=str(path), name=None))
    install()
    (path / "skills" / "team-review" / "SKILL.md").unlink()
    (path / "skills" / "team-review").rmdir()
    capsys.readouterr()

    assert doctor() == 1
    assert "dangling" in capsys.readouterr().out


def test_doctor_catches_a_link_deleted_behind_its_back(home, capsys):
    install()
    (home / ".claude" / "skills" / "flw-spec").unlink()
    capsys.readouterr()

    assert doctor() == 1
    assert "recorded, but nothing is there now" in capsys.readouterr().out


def test_doctor_catches_a_hijacked_link(home, bundle, capsys):
    install()
    link = home / ".claude" / "skills" / "flw-spec"
    link.unlink()
    link.symlink_to(bundle("elsewhere") / "skills" / "elsewhere")
    capsys.readouterr()

    assert doctor() == 1
    assert "points at" in capsys.readouterr().out


def test_doctor_reports_a_missing_pointer(home, capsys):
    install()
    flw.ROOT_POINTER.unlink()
    capsys.readouterr()

    assert doctor() == 1
    assert (
        "every skill will stop and ask you to run `flw install`"
        in capsys.readouterr().out
    )


# --- ordinary filesystem conditions --------------------------------------- #


def test_a_malformed_links_record_names_the_file_instead_of_raising(home, capsys):
    flw.FLW_HOME.mkdir(parents=True, exist_ok=True)
    flw.LINKS.write_text('[[link]]\nskill = "flw-spec"\ntarget = "/tmp/x"\n')  # no path

    with pytest.raises(SystemExit) as exit_info:
        doctor()
    assert str(flw.LINKS) in str(exit_info.value)
    assert "path" in str(exit_info.value)


def test_a_corrupt_root_pointer_names_the_path_instead_of_raising(home, capsys):
    flw.FLW_HOME.mkdir(parents=True, exist_ok=True)
    flw.ROOT_POINTER.mkdir()  # a directory where the pointer file belongs

    # Through `main`, not `doctor` directly: it is main's OSError boundary
    # that turns this into a message rather than a traceback, and calling
    # doctor() here without pytest.raises would itself fail the test if that
    # boundary were missing or too broad.
    assert flw.main(["flw", "doctor"]) == 1
    err = capsys.readouterr().err
    assert str(flw.ROOT_POINTER) in err
    assert err.startswith("error:")


# --- sync ------------------------------------------------------------------ #


def test_sync_restores_a_missing_link(home, capsys):
    install()
    (home / ".claude" / "skills" / "flw-spec").unlink()
    capsys.readouterr()

    assert sync() == 0
    out = capsys.readouterr().out
    assert "flw-spec — relinked (missing, was " in out
    assert " → " in out, "the line should say what it replaced"
    assert (home / ".claude" / "skills" / "flw-spec").is_symlink()
    assert doctor() == 0


def test_sync_repoints_a_hijacked_link(home, bundle, capsys):
    install()
    link = home / ".claude" / "skills" / "flw-spec"
    elsewhere = bundle("elsewhere") / "skills" / "elsewhere"
    link.unlink()
    link.symlink_to(elsewhere)
    capsys.readouterr()

    assert sync() == 0
    out = capsys.readouterr().out
    assert "flw-spec — relinked (points elsewhere, was " in out
    assert link.resolve() != elsewhere.resolve()
    assert doctor() == 0


def test_sync_removes_a_dangling_and_an_orphaned_link(home, bundle, capsys):
    path = bundle("team-review")
    flw.add(argparse.Namespace(path=str(path), name=None))
    install()
    (path / "skills" / "team-review" / "SKILL.md").unlink()
    (path / "skills" / "team-review").rmdir()
    capsys.readouterr()

    assert sync() == 0
    out = capsys.readouterr().out
    assert "team-review — removed (dangling, was " in out
    assert not (home / ".claude" / "skills" / "team-review").exists()
    assert not any(link["skill"] == "team-review" for link in flw.read_links())


def test_sync_removes_an_orphaned_link_from_a_deregistered_bundle(home, bundle, capsys):
    flw.add(argparse.Namespace(path=str(bundle("team-review")), name=None))
    install()
    flw.BUNDLES.write_text("# emptied by hand\n")
    capsys.readouterr()

    assert sync() == 0
    out = capsys.readouterr().out
    assert "team-review — removed (orphaned, was " in out
    assert not (home / ".claude" / "skills" / "team-review").exists()
    assert doctor() == 0


def test_sync_links_a_skill_new_since_install(home, bundle, capsys):
    flw.add(argparse.Namespace(path=str(bundle("team-review")), name=None))
    install("claude-code")
    # A skill added after install: simulate by removing its link and record,
    # as if it had not existed at install time.
    link = home / ".claude" / "skills" / "team-review"
    link.unlink()
    flw.write_links([lk for lk in flw.read_links() if lk["skill"] != "team-review"])
    capsys.readouterr()

    assert sync() == 0
    out = capsys.readouterr().out
    assert "team-review — linked" in out
    assert (home / ".claude" / "skills" / "team-review").is_symlink()
    assert doctor() == 0


def test_sync_adopts_an_unrecorded_link_so_uninstall_can_reach_it(home, capsys):
    """The state a race between two installs leaves behind: the symlink is
    real, but the second write won and forgot it. Being unreachable by
    uninstall is the damage adoption undoes — that is the point of the test,
    not merely that the record and disk agree afterwards.
    """
    install("claude-code")
    flw.write_links([lk for lk in flw.read_links() if lk["skill"] != "flw-spec"])
    capsys.readouterr()

    assert sync() == 0
    out = capsys.readouterr().out
    assert "flw-spec — adopted" in out
    assert any(lk["skill"] == "flw-spec" for lk in flw.read_links())

    uninstall("claude-code")
    capsys.readouterr()
    assert not (home / ".claude" / "skills" / "flw-spec").exists()


def test_sync_leaves_a_foreign_symlink_alone(home, bundle, capsys):
    """A symlink at a known skill's path but pointing somewhere outside the
    checkout is not flw's to adopt — the additive rule protects a user's own
    file at that name, and `blocked_by` still refuses to touch it."""
    install("claude-code")
    link = home / ".claude" / "skills" / "flw-spec"
    elsewhere = bundle("elsewhere") / "skills" / "elsewhere"
    link.unlink()
    link.symlink_to(elsewhere)
    flw.write_links([lk for lk in flw.read_links() if lk["skill"] != "flw-spec"])
    capsys.readouterr()

    assert sync() == 0
    out = capsys.readouterr().out
    assert "flw-spec — adopted" not in out
    assert "flw-spec — a symlink flw did not create is already there" in out
    assert not any(lk["skill"] == "flw-spec" for lk in flw.read_links())
    assert link.resolve() == elsewhere.resolve()


def test_sync_leaves_a_present_but_unrecorded_host_untouched(home, monkeypatch, capsys):
    install("claude-code")
    capsys.readouterr()

    assert sync() == 0
    out = capsys.readouterr().out
    assert "codex: present here but not recorded" in out
    assert not (home / ".agents" / "skills").exists()


def test_sync_dry_run_writes_nothing(home, capsys):
    install()
    (home / ".claude" / "skills" / "flw-spec").unlink()
    before = flw.read_links()
    capsys.readouterr()

    sync(dry=True)
    capsys.readouterr()

    assert not (home / ".claude" / "skills" / "flw-spec").exists()
    assert flw.read_links() == before


def test_sync_offers_and_refreshes_a_style_behind_its_source(home, capsys, monkeypatch):
    source = install_mine(home)
    capsys.readouterr()

    source.write_text("## Mine\n\nWrite even more briefly.\n")
    monkeypatch.setattr("builtins.input", lambda *a: "y")
    sync(yes=False)
    out = capsys.readouterr().out
    assert "does not match" in out and "refreshed" in out

    installed = (home / ".claude" / "output-styles" / "mine.md").read_text()
    assert "even more briefly" in installed


def test_sync_declining_the_style_refresh_leaves_it_byte_identical(
    home, capsys, monkeypatch
):
    source = install_mine(home)
    installed_path = home / ".claude" / "output-styles" / "mine.md"
    before = installed_path.read_text()
    capsys.readouterr()

    source.write_text("## Mine\n\nWrite even more briefly.\n")
    monkeypatch.setattr("builtins.input", lambda *a: "n")
    sync(yes=False)
    capsys.readouterr()

    assert installed_path.read_text() == before


def test_sync_adopts_a_digest_when_the_body_still_matches(home, capsys):
    install_mine(home)
    flw.write_style(
        [
            {k: v for k, v in entry.items() if k != "installed_sha"}
            for entry in flw.read_style()
        ]
    )
    capsys.readouterr()

    assert sync() == 0
    capsys.readouterr()

    entry = flw.read_style()[0]
    body = flw.style_body((home / ".claude" / "output-styles" / "mine.md").read_text())
    assert entry["installed_sha"] == flw.style_digest(body)


def test_sync_does_not_guess_a_digest_when_the_bodies_already_differ(home, capsys):
    source = install_mine(home)
    flw.write_style(
        [
            {k: v for k, v in entry.items() if k != "installed_sha"}
            for entry in flw.read_style()
        ]
    )
    source.write_text("## Mine\n\nWrite even more briefly.\n")
    capsys.readouterr()

    sync(dry=True)
    capsys.readouterr()

    assert flw.read_style()[0].get("installed_sha") is None


# --- update calls sync ----------------------------------------------------- #


def test_doctor_points_at_sync_for_a_skill_missing_from_a_root(home, capsys):
    install()
    (home / ".claude" / "skills" / "flw-spec").unlink()
    flw.write_links([lk for lk in flw.read_links() if lk["skill"] != "flw-spec"])
    capsys.readouterr()

    assert doctor() == 1
    out = capsys.readouterr().out
    assert "flw-spec — not linked here. Run `flw sync`." in out


def test_update_still_offers_the_style_refresh_through_sync(home, capsys, monkeypatch):
    source = install_mine(home)
    capsys.readouterr()

    source.write_text("## Mine\n\nWrite even more briefly.\n")
    fake_pull(monkeypatch, home)
    update(yes=True)
    out = capsys.readouterr().out
    assert "does not match" in out and "refreshed" in out


# --- the ambient block ---------------------------------------------------- #


def test_the_ambient_block_round_trips_exactly(home, capsys):
    """flw is a guest in the user's own instructions file. Removal has to be
    exact or the feature is worse than doing it by hand."""
    instructions = home / ".claude" / "CLAUDE.md"
    instructions.parent.mkdir(parents=True)
    original = "# Mine\n\nSomething I wrote, with  odd  spacing.\n"
    instructions.write_text(original)

    install("claude-code", ambient=True)
    after_install = instructions.read_text()
    assert original in after_install
    assert flw.BEGIN in after_install

    uninstall("claude-code")
    capsys.readouterr()
    assert instructions.read_text() == original


def test_a_crlf_instructions_file_keeps_its_line_endings(home, capsys):
    """Assert on bytes: a test that reads both sides with read_text cannot
    observe this bug at all, because the newline translation it is testing
    for happens on both reads."""
    instructions = home / ".claude" / "CLAUDE.md"
    instructions.parent.mkdir(parents=True)
    original = b"# Mine\r\n\r\nSomething I wrote, with CRLF endings.\r\n"
    instructions.write_bytes(original)

    install("claude-code", ambient=True)
    capsys.readouterr()
    after_install = instructions.read_bytes()
    assert after_install.startswith(original)
    assert flw.BEGIN.encode() in after_install

    uninstall("claude-code")
    capsys.readouterr()
    assert instructions.read_bytes() == original


def test_reinstalling_the_ambient_block_replaces_rather_than_repeats(home, capsys):
    instructions = home / ".claude" / "CLAUDE.md"
    instructions.parent.mkdir(parents=True)
    instructions.write_text("# Mine\n")

    install("claude-code", ambient=True)
    install("claude-code", ambient=True)
    capsys.readouterr()

    assert instructions.read_text().count(flw.BEGIN) == 1


def test_a_file_without_the_block_is_untouched_by_uninstall(home, capsys):
    instructions = home / ".claude" / "CLAUDE.md"
    instructions.parent.mkdir(parents=True)
    instructions.write_text("# Mine, and flw never touched it\n")

    install("claude-code")
    uninstall("claude-code")
    capsys.readouterr()

    assert instructions.read_text() == "# Mine, and flw never touched it\n"


# --- uninstall ------------------------------------------------------------ #


def test_uninstall_leaves_nothing(home, capsys):
    install(ambient=True)
    uninstall()
    capsys.readouterr()

    leftovers = [p for p in home.rglob("*") if p.is_file() or p.is_symlink()]
    assert leftovers == [], [str(p) for p in leftovers]


def test_uninstalling_one_host_leaves_the_other_installed(home, capsys):
    install()
    uninstall("claude-code")
    capsys.readouterr()

    assert not (home / ".claude" / "skills" / "flw-spec").exists()
    assert (home / ".agents" / "skills" / "flw-spec").is_symlink()
    assert flw.ROOT_POINTER.exists(), "the pointer goes only when the last link does"


# --- update --------------------------------------------------------------- #


def test_update_names_a_missing_upstream_rather_than_blaming_a_rebase(
    home, tmp_path, monkeypatch, capsys
):
    """A checkout with no upstream fails the pull AND the rebase, for the same
    reason. Reported naively that reads as "your rebase conflicted", which is a
    diagnosis unrelated to what happened."""
    repo = tmp_path / "clone"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setattr(flw, "checkout", lambda: repo)

    assert flw.update(argparse.Namespace()) == 1
    err = capsys.readouterr().err
    assert "no upstream branch" in err
    assert "flw sync" in err


def test_update_refuses_outside_a_checkout(home, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(flw, "checkout", lambda: tmp_path / "not-a-repo")
    assert flw.update(argparse.Namespace()) == 1
    assert "not a git checkout" in capsys.readouterr().err


# --- update: offering a style refresh ------------------------------------- #


def test_update_offers_to_refresh_a_style_that_has_fallen_behind(
    home, capsys, monkeypatch
):
    styles = home / ".flw" / "styles"
    styles.mkdir(parents=True)
    source = styles / "mine.md"
    source.write_text("## Mine\n\nWrite briefly.\n")
    style_install("mine", "claude-code")
    capsys.readouterr()

    source.write_text("## Mine\n\nWrite even more briefly.\n")
    fake_pull(monkeypatch, home)
    monkeypatch.setattr("builtins.input", lambda *a: "y")
    update()
    out = capsys.readouterr().out
    assert "does not match" in out and "refreshed" in out

    installed = (home / ".claude" / "output-styles" / "mine.md").read_text()
    assert "even more briefly" in installed


def install_mine(home, body: str = "## Mine\n\nWrite briefly.\n") -> Path:
    """A style of the user's own, installed on claude-code. Every refresh test
    needs one: flw's shipped source lives in the repository and a test that
    moved it would edit the checkout it is running from."""
    styles = home / ".flw" / "styles"
    styles.mkdir(parents=True, exist_ok=True)
    source = styles / "mine.md"
    source.write_text(body)
    style_install("mine", "claude-code")
    return source


def test_a_source_that_moved_on_reports_the_copy_untouched(home, capsys, monkeypatch):
    source = install_mine(home)
    capsys.readouterr()

    source.write_text("## Mine\n\nWrite even more briefly.\n")
    fake_pull(monkeypatch, home)
    update(dry=True)

    assert "the source moved on" in capsys.readouterr().out


def test_a_hand_edited_copy_is_reported_as_edited_here(home, capsys, monkeypatch):
    """The body comparison alone cannot tell this from the case above, and the
    two want opposite answers: one refresh loses nothing, the other discards
    work the user did by hand."""
    install_mine(home)
    installed = home / ".claude" / "output-styles" / "mine.md"
    installed.write_text(installed.read_text() + "\nA rule I added myself.\n")
    capsys.readouterr()

    doctor()
    assert "was edited after flw wrote it" in capsys.readouterr().out

    fake_pull(monkeypatch, home)
    update(dry=True)
    assert "a refresh discards that" in capsys.readouterr().out


def test_an_entry_with_no_recorded_digest_admits_it_cannot_tell(
    home, capsys, monkeypatch
):
    """Records written before flw kept a digest. The offer still stands; the
    verdict is the one thing it cannot supply."""
    source = install_mine(home)
    flw.write_style(
        [
            {k: v for k, v in entry.items() if k != "installed_sha"}
            for entry in flw.read_style()
        ]
    )
    source.write_text("## Mine\n\nWrite even more briefly.\n")
    capsys.readouterr()

    doctor()
    assert "no record of what it wrote" in capsys.readouterr().out

    fake_pull(monkeypatch, home)
    update(dry=True)
    assert "which one moved is unknown" in capsys.readouterr().out


def test_a_refresh_records_what_it_wrote_so_the_next_run_is_quiet(
    home, capsys, monkeypatch
):
    source = install_mine(home)
    source.write_text("## Mine\n\nWrite even more briefly.\n")
    fake_pull(monkeypatch, home)
    update(yes=True)
    capsys.readouterr()

    update(yes=True)
    out = capsys.readouterr().out
    assert "does not match" not in out
    body = flw.style_body(source.read_text())
    assert flw.read_style()[0]["installed_sha"] == flw.style_digest(body)

    doctor()
    assert "✓ claude-code: mine" in capsys.readouterr().out


def test_declining_the_refresh_leaves_the_file_untouched(home, capsys, monkeypatch):
    styles = home / ".flw" / "styles"
    styles.mkdir(parents=True)
    source = styles / "mine.md"
    source.write_text("## Mine\n\nWrite briefly.\n")
    style_install("mine", "claude-code")
    capsys.readouterr()

    installed_path = home / ".claude" / "output-styles" / "mine.md"
    before = installed_path.read_text()

    source.write_text("## Mine\n\nWrite even more briefly.\n")
    fake_pull(monkeypatch, home)
    monkeypatch.setattr("builtins.input", lambda *a: "n")
    update()
    capsys.readouterr()

    assert installed_path.read_text() == before
    doctor()
    assert "is behind" in capsys.readouterr().out


def test_yes_refreshes_the_style_without_prompting(home, capsys, monkeypatch):
    styles = home / ".flw" / "styles"
    styles.mkdir(parents=True)
    source = styles / "mine.md"
    source.write_text("## Mine\n\nWrite briefly.\n")
    style_install("mine", "claude-code")
    capsys.readouterr()

    source.write_text("## Mine\n\nWrite even more briefly.\n")
    fake_pull(monkeypatch, home)
    monkeypatch.setattr(
        "builtins.input",
        lambda *a: (_ for _ in ()).throw(AssertionError("should not prompt with -y")),
    )
    update(yes=True)

    installed = (home / ".claude" / "output-styles" / "mine.md").read_text()
    assert "even more briefly" in installed


def test_dry_run_update_refreshes_nothing(home, capsys, monkeypatch):
    styles = home / ".flw" / "styles"
    styles.mkdir(parents=True)
    source = styles / "mine.md"
    source.write_text("## Mine\n\nWrite briefly.\n")
    style_install("mine", "claude-code")
    capsys.readouterr()

    installed_path = home / ".claude" / "output-styles" / "mine.md"
    before = installed_path.read_text()

    source.write_text("## Mine\n\nWrite even more briefly.\n")
    fake_pull(monkeypatch, home)
    monkeypatch.setattr(
        "builtins.input",
        lambda *a: (_ for _ in ()).throw(AssertionError("dry-run should not prompt")),
    )
    update(dry=True)

    assert installed_path.read_text() == before


def test_each_host_refreshes_from_its_own_recorded_source(home, capsys, monkeypatch):
    """One host on flw's shipped style, one on a style of the user's, both
    behind. Each entry in the record carries its own source, and a refresh that
    resolved the source once for the run would put flw's text into both."""
    repo = fake_checkout(monkeypatch, home, "## Shipped\n\nFlw's own rule.\n")
    shipped = repo / "core" / "styles" / "terse_prose.md"
    styles = home / ".flw" / "styles"
    styles.mkdir(parents=True)
    mine = styles / "mine.md"
    mine.write_text("## Mine\n\nMy own rule.\n")

    style_install(None, "claude-code")
    style_install("mine", "codex")
    capsys.readouterr()

    shipped.write_text("## Shipped\n\nFlw's own rule, refreshed.\n")
    mine.write_text("## Mine\n\nMy own rule, refreshed.\n")
    fake_pull(monkeypatch, home)
    update(yes=True)

    installed = (home / ".claude" / "output-styles" / "flw-terse.md").read_text()
    agents = (home / ".codex" / "AGENTS.md").read_text()
    assert "Flw's own rule, refreshed." in installed
    assert f"installed by flw from {shipped}" in installed
    assert "My own rule, refreshed." in agents
    assert "Flw's own rule" not in agents


def test_a_missing_installed_file_is_not_offered_a_refresh(home, capsys, monkeypatch):
    styles = home / ".flw" / "styles"
    styles.mkdir(parents=True)
    source = styles / "mine.md"
    source.write_text("## Mine\n\nWrite briefly.\n")
    style_install("mine", "claude-code")
    capsys.readouterr()

    (home / ".claude" / "output-styles" / "mine.md").unlink()
    source.write_text("## Mine\n\nWrite even more briefly.\n")

    fake_pull(monkeypatch, home)
    monkeypatch.setattr(
        "builtins.input",
        lambda *a: (_ for _ in ()).throw(AssertionError("must not prompt to refresh a missing file")),
    )
    update()
    out = capsys.readouterr().out
    assert "is behind" not in out


def test_refresh_never_touches_the_selected_style(home, capsys, monkeypatch):
    styles = home / ".flw" / "styles"
    styles.mkdir(parents=True)
    source = styles / "mine.md"
    source.write_text("## Mine\n\nWrite briefly.\n")
    style_install("mine", "claude-code")
    capsys.readouterr()

    settings = home / ".claude" / "settings.json"
    before = settings.read_text()

    source.write_text("## Mine\n\nWrite even more briefly.\n")
    fake_pull(monkeypatch, home)
    update(yes=True)

    assert settings.read_text() == before


def test_refresh_rewrites_the_tagged_block_for_a_host_without_a_style_slot(
    home, capsys, monkeypatch
):
    """The block is the user's instructions file, so the refresh has to leave
    everything above it byte-identical — the blank line install puts between
    their text and flw's included."""
    styles = home / ".flw" / "styles"
    styles.mkdir(parents=True)
    source = styles / "mine.md"
    source.write_text("## Mine\n\nWrite briefly.\n")

    instructions = home / ".codex" / "AGENTS.md"
    instructions.parent.mkdir(parents=True)
    instructions.write_text("# My own notes\n\nkeep this line.\n")
    style_install("mine", "codex")
    capsys.readouterr()

    before = instructions.read_text()
    assert "Write briefly." in before
    head = before[: before.index(flw.STYLE_BEGIN)]

    source.write_text("## Mine\n\nWrite even more briefly.\n")
    fake_pull(monkeypatch, home)
    update(yes=True)

    after = instructions.read_text()
    assert "even more briefly" in after
    assert flw.STYLE_BEGIN in after and flw.STYLE_END in after
    assert after[: after.index(flw.STYLE_BEGIN)] == head


def test_reinstalling_a_block_does_not_creep_up_the_file(home, capsys):
    """strip_block eats the blank separator, because uninstall must leave the
    file as it found it. Install and refresh both rewrite in place, so each one
    would otherwise pull the block a line closer to the user's own text."""
    styles = home / ".flw" / "styles"
    styles.mkdir(parents=True)
    (styles / "mine.md").write_text("## Mine\n\nWrite briefly.\n")

    instructions = home / ".codex" / "AGENTS.md"
    instructions.parent.mkdir(parents=True)
    instructions.write_text("# My own notes\n\nkeep this line.\n")

    style_install("mine", "codex")
    once = instructions.read_text()
    style_install("mine", "codex")
    capsys.readouterr()

    assert instructions.read_text() == once
    assert once.startswith("# My own notes\n\nkeep this line.\n\n" + flw.STYLE_BEGIN)


def test_a_host_is_not_covered_by_a_root_with_a_broken_skill(home, capsys):
    """"Covered" has to mean every skill, not at least one. Otherwise a host
    reads ✓ in the same output where two of its skills are red."""
    install("claude-code")
    (home / ".claude" / "skills" / "flw-spec").unlink()
    capsys.readouterr()

    assert doctor() == 1
    assert "claude-code: not installed" in capsys.readouterr().out


def test_uninstalling_a_host_does_not_unlink_a_root_another_host_owns(home, capsys):
    """OpenCode READS Claude Code's and Codex's skill directories. Iterating
    every root a host reads meant `flw uninstall opencode` unlinked both of
    them and took the root pointer with it, so every host stopped resolving flw
    — from a command that should have removed nothing at all."""
    install()
    uninstall("opencode")
    capsys.readouterr()

    assert (home / ".claude" / "skills" / "flw-spec").is_symlink()
    assert (home / ".agents" / "skills" / "flw-spec").is_symlink()
    assert flw.ROOT_POINTER.exists()
    assert doctor() == 0


def test_uninstalling_opencode_alone_removes_its_own_root(home, capsys):
    install("opencode")
    assert (home / ".config" / "opencode" / "skills" / "flw-spec").is_symlink()

    uninstall("opencode")
    capsys.readouterr()
    assert not (home / ".config" / "opencode" / "skills" / "flw-spec").exists()


# --- extensions ----------------------------------------------------------- #


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A project with a .flw/extensions/ directory, and cwd inside it."""
    root = tmp_path / "project"
    extensions = root / ".flw" / "extensions"
    extensions.mkdir(parents=True)
    monkeypatch.chdir(root)
    return extensions


def test_doctor_says_which_skill_reads_an_extension(home, project, capsys):
    install("claude-code")
    (project / "flw-spec.md").write_text("Components map to services/.\n")
    capsys.readouterr()

    assert doctor() == 0
    assert "✓ flw-spec.md — read by flw-spec" in capsys.readouterr().out


def test_doctor_catches_an_extension_no_skill_will_ever_read(home, project, capsys):
    """The whole reason the path is fixed rather than configured. `spec.md`
    looks right, the skill is named `flw-spec`, and nothing would ever say so:
    the file just sits there being read by nobody."""
    install("claude-code")
    (project / "spec.md").write_text("Never read by anything.\n")
    capsys.readouterr()

    assert doctor() == 1
    out = capsys.readouterr().out
    assert "✗ spec.md — read by nobody: no installed skill is named 'spec'" in out
    assert "skills here: " in out and "flw-spec" in out.split("skills here: ")[1]


def test_doctor_names_the_right_reason_for_a_non_markdown_extension(home, project, capsys):
    install("claude-code")
    (project / "flw-spec.txt").write_text("Wrong suffix.\n")
    capsys.readouterr()

    assert doctor() == 1
    assert "a .md file named for its skill" in capsys.readouterr().out


def test_doctor_names_the_right_reason_for_a_directory(home, project, capsys):
    install("claude-code")
    (project / "flw-spec.md").mkdir()
    capsys.readouterr()

    assert doctor() == 1
    assert "a file, not a directory" in capsys.readouterr().out


def test_doctor_reads_a_bundle_skills_extension(home, project, bundle, capsys):
    """Extensions are matched against every installed skill, not core's three."""
    flw.add(argparse.Namespace(path=str(bundle("teamlint")), name=None))
    install("claude-code")
    (project / "teamlint.md").write_text("Ours runs from the poetry venv.\n")
    capsys.readouterr()

    assert doctor() == 0
    assert "✓ teamlint.md — read by teamlint" in capsys.readouterr().out


def test_doctor_outside_a_project_says_nothing_about_extensions(home, tmp_path, monkeypatch, capsys):
    """doctor is an install check; the extensions section is project-scoped.
    Run from somewhere with no project it must stay silent, not crash on the
    project_root() that test and validate correctly die on."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    install("claude-code")
    capsys.readouterr()

    assert doctor() == 0
    assert "extensions:" not in capsys.readouterr().out


def test_doctor_says_nothing_when_the_extensions_directory_is_empty(home, project, capsys):
    install("claude-code")
    capsys.readouterr()

    assert doctor() == 0
    assert "extensions:" not in capsys.readouterr().out


# --- host presence -------------------------------------------------------- #


def only_present(monkeypatch, *names: str) -> None:
    monkeypatch.setattr(flw, "present", lambda host: host.name in names)


def test_install_skips_a_host_that_is_not_on_this_machine(home, monkeypatch, capsys):
    """The first real install created ~/.agents/skills on a machine with no
    Codex. resolve_hosts([]) returned every known host unconditionally, so flw
    invented a directory for a host that was not there."""
    only_present(monkeypatch, "claude-code")
    install()
    out = capsys.readouterr().out

    assert "codex: not on this machine — skipping" in out
    assert (home / ".claude" / "skills" / "flw-spec").is_symlink()
    assert not (home / ".agents").exists()


def test_naming_a_host_installs_it_even_when_absent(home, monkeypatch, capsys):
    """Explicit intent overrides detection — installing ahead of a host, or into
    an image that will have one, is legitimate."""
    only_present(monkeypatch)
    install("codex")
    capsys.readouterr()

    assert (home / ".agents" / "skills" / "flw-spec").is_symlink()


def test_no_hosts_present_says_what_to_do_instead(home, monkeypatch, capsys):
    only_present(monkeypatch)
    assert install() == 1
    err = capsys.readouterr().err
    assert "none of the known hosts are installed here" in err
    assert "flw install claude-code" in err


def test_uninstall_still_reaches_a_host_that_is_gone(home, monkeypatch, capsys):
    """The case that produced this fix: Codex was installed, flw linked into it,
    then Codex was removed. Filtering uninstall by presence would strand those
    links forever."""
    only_present(monkeypatch, "claude-code", "codex")
    install()
    only_present(monkeypatch, "claude-code")
    capsys.readouterr()

    uninstall("codex")
    assert not (home / ".agents" / "skills" / "flw-spec").exists()
    assert (home / ".claude" / "skills" / "flw-spec").is_symlink()


def test_presence_ignores_the_skills_directory_flw_itself_creates(home, monkeypatch):
    """A skills dir is flw's own output. Treating it as evidence would make
    every install self-justifying: install once by accident, and the host looks
    present forever after."""
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(flw, "present", REAL_PRESENT)
    codex = flw.BY_NAME["codex"]
    (home / ".agents" / "skills").mkdir(parents=True)
    assert not flw.present(codex)

    (home / ".codex").mkdir()
    assert flw.present(codex)


# --- the writing style ---------------------------------------------------- #


def test_the_style_block_and_the_ambient_block_are_independent(home, capsys):
    """They share one file. Removing either must leave the other byte-identical,
    which is the whole reason the style got its own tag pair."""
    instructions = home / ".codex" / "AGENTS.md"
    instructions.parent.mkdir(parents=True)
    original = "# Mine\n"
    instructions.write_text(original)

    install("codex", ambient=True)
    style_install(None, "codex")
    both = instructions.read_text()
    assert flw.BEGIN in both and flw.STYLE_BEGIN in both

    style_uninstall("codex")
    ambient_only = instructions.read_text()
    assert flw.STYLE_BEGIN not in ambient_only
    assert flw.BEGIN in ambient_only

    uninstall("codex")
    capsys.readouterr()
    assert instructions.read_text() == original


def test_the_style_round_trips_out_of_a_host_with_a_style_slot(home, capsys):
    style_install(None, "claude-code")
    written = home / ".claude" / "output-styles" / "flw-terse.md"
    assert written.is_file()
    assert "keep-coding-instructions: true" in written.read_text()
    assert json.loads((home / ".claude" / "settings.json").read_text())[
        "outputStyle"
    ] == "flw-terse"

    style_uninstall("claude-code")
    capsys.readouterr()
    assert not written.exists()
    assert not (home / ".claude" / "settings.json").exists()


def test_uninstalling_puts_back_the_style_that_was_selected_before(home, capsys):
    settings = home / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"outputStyle": "mine", "theme": "dark"}))

    style_install(None, "claude-code")
    assert json.loads(settings.read_text())["outputStyle"] == "flw-terse"

    style_uninstall("claude-code")
    capsys.readouterr()
    restored = json.loads(settings.read_text())
    assert restored == {"outputStyle": "mine", "theme": "dark"}


def test_an_unknown_style_name_is_an_error_not_a_fallback(home, capsys):
    """Falling back to the shipped style would install something the user did
    not name, and say nothing."""
    with pytest.raises(SystemExit) as exit_info:
        style_install("nope", "claude-code")
    assert "nope" in str(exit_info.value)
    assert not (home / ".claude" / "output-styles").exists()


def test_a_named_style_comes_from_the_styles_directory(home, capsys):
    styles = home / ".flw" / "styles"
    styles.mkdir(parents=True)
    (styles / "mine.md").write_text("## Mine\n\nWrite briefly.\n")

    style_install("mine", "claude-code")
    written = home / ".claude" / "output-styles" / "mine.md"
    assert "Write briefly." in written.read_text()
    assert "name: mine" in written.read_text()


def test_doctor_reports_a_style_that_has_fallen_behind_its_source(home, capsys):
    styles = home / ".flw" / "styles"
    styles.mkdir(parents=True)
    source = styles / "mine.md"
    source.write_text("## Mine\n\nWrite briefly.\n")

    install("claude-code")
    style_install("mine", "claude-code")
    capsys.readouterr()
    doctor()
    assert "✓ claude-code: mine" in capsys.readouterr().out

    source.write_text("## Mine\n\nWrite even more briefly.\n")
    doctor()
    out = capsys.readouterr().out
    assert "is behind" in out


def test_doctor_says_the_style_is_not_installed_when_it_is_not(home, capsys):
    install("claude-code")
    capsys.readouterr()
    doctor()
    assert "not installed — `flw style install`" in capsys.readouterr().out


def test_install_names_the_style_without_installing_it(home, capsys):
    install("claude-code")
    out = capsys.readouterr().out
    assert "`flw style install`" in out
    assert not (home / ".claude" / "output-styles").exists()


def test_uninstalling_the_style_leaves_nothing(home, capsys):
    install(ambient=True)
    style_install()
    style_uninstall()
    uninstall()
    capsys.readouterr()

    leftovers = [p for p in home.rglob("*") if p.is_file() or p.is_symlink()]
    assert leftovers == [], [str(p) for p in leftovers]


# --- the style: install adds, uninstall removes only what it made ------------ #


def test_reinstalling_still_puts_back_the_style_that_was_selected_before(home, capsys):
    """The second install is the normal case — it is how a changed style file is
    picked up — and select_style reports nothing when the key already names it."""
    settings = home / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"outputStyle": "mine", "theme": "dark"}))

    style_install(None, "claude-code")
    style_install(None, "claude-code")
    style_uninstall("claude-code")
    capsys.readouterr()

    assert json.loads(settings.read_text()) == {"outputStyle": "mine", "theme": "dark"}


def test_install_refuses_to_overwrite_a_style_file_flw_did_not_write(home, capsys):
    written = home / ".claude" / "output-styles" / "flw-terse.md"
    written.parent.mkdir(parents=True)
    written.write_text("MY OWN STYLE\n")

    style_install(None, "claude-code")
    capsys.readouterr()

    assert written.read_text() == "MY OWN STYLE\n"
    assert flw.read_style() == []


def test_uninstall_keeps_a_settings_file_that_was_there_before(home, capsys):
    settings = home / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text("{}")

    style_install(None, "claude-code")
    style_uninstall("claude-code")
    capsys.readouterr()

    assert settings.is_file()
    assert json.loads(settings.read_text()) == {}


def test_installing_a_second_style_removes_the_one_it_replaces(home, capsys):
    styles = home / ".flw" / "styles"
    styles.mkdir(parents=True)
    (styles / "mine.md").write_text("## Mine\n\nWrite briefly.\n")

    style_install(None, "claude-code")
    style_install("mine", "claude-code")
    capsys.readouterr()

    directory = home / ".claude" / "output-styles"
    assert sorted(p.name for p in directory.iterdir()) == ["mine.md"]


def test_a_settings_file_that_is_not_an_object_is_left_alone(home, capsys):
    """Valid JSON, so the decode guard does not fire. settings.get would raise
    half way through an install that has already written the style file."""
    settings = home / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text("[1, 2, 3]")

    assert style_install(None, "claude-code") == 0
    capsys.readouterr()

    assert settings.read_text() == "[1, 2, 3]"
    written = home / ".claude" / "output-styles" / "flw-terse.md"
    assert written.is_file()
    assert [Path(e["path"]) for e in flw.read_style()] == [written]


def test_a_style_name_cannot_escape_the_styles_directory(home, capsys):
    """The file has to exist, or `no style named` fires and the test passes
    without the validation it is there to pin."""
    styles = home / ".flw" / "styles"
    styles.mkdir(parents=True)
    (styles.parent / "evil.md").write_text("## Evil\n")

    with pytest.raises(SystemExit) as exit_info:
        style_install("../evil", "claude-code")
    assert "may hold only" in str(exit_info.value)
    assert not (home / ".claude" / "evil.md").exists()


def test_a_style_record_survives_a_crash_after_the_file_is_written(
    home, capsys, monkeypatch
):
    """An unrecorded file is one uninstall cannot remove, and doctor reports it
    as absent while it sits in the host's directory."""

    def boom(*args, **kwargs):
        raise RuntimeError("settings blew up")

    monkeypatch.setattr(flw, "select_style", boom)
    with pytest.raises(RuntimeError):
        style_install(None, "claude-code")
    capsys.readouterr()

    written = home / ".claude" / "output-styles" / "flw-terse.md"
    assert written.is_file()
    assert [Path(e["path"]) for e in flw.read_style()] == [written]

    style_uninstall("claude-code")
    capsys.readouterr()
    assert not written.exists()


def test_a_dry_run_of_the_style_writes_nothing(home, capsys):
    style_install_dry(None, "claude-code")
    capsys.readouterr()

    assert not (home / ".claude" / "output-styles").exists()
    assert not (home / ".flw" / "style.toml").exists()


def test_declining_the_prompt_records_no_block(home, capsys, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *args: "n")
    instructions = home / ".codex" / "AGENTS.md"
    instructions.parent.mkdir(parents=True)
    instructions.write_text("# Mine\n")

    flw.style_install(
        argparse.Namespace(name=None, host=["codex"], dry_run=False, yes=False)
    )
    capsys.readouterr()

    assert instructions.read_text() == "# Mine\n"
    assert flw.read_style() == []


def test_doctor_reports_drift_on_a_block_host_too(home, capsys):
    styles = home / ".flw" / "styles"
    styles.mkdir(parents=True)
    source = styles / "mine.md"
    source.write_text("## Mine\n\nWrite briefly.\n")

    install("codex")
    style_install("mine", "codex")
    capsys.readouterr()
    assert doctor() == 0

    source.write_text("## Mine\n\nWrite even more briefly.\n")
    assert doctor() != 0
    assert "is behind" in capsys.readouterr().out


def test_doctor_reports_an_installed_style_that_has_been_deleted(home, capsys):
    install("claude-code")
    style_install(None, "claude-code")
    (home / ".claude" / "output-styles" / "flw-terse.md").unlink()
    capsys.readouterr()

    assert doctor() != 0
    assert "nothing is there now" in capsys.readouterr().out


def test_an_unreadable_style_record_does_not_crash_the_cli(home, capsys):
    state = home / ".flw" / "style.toml"
    state.parent.mkdir(parents=True)
    state.write_text('[[host]]\nhost = "claude-code"\nname = "mine"\n')

    assert doctor() != 0
    assert "unreadable record" in capsys.readouterr().out
    assert style_uninstall("claude-code") == 0
    capsys.readouterr()


def test_a_style_name_with_a_quote_is_refused_before_it_breaks_the_record(home):
    styles = home / ".flw" / "styles"
    styles.mkdir(parents=True)
    (styles / 'a"b.md').write_text("## Quoted\n")

    with pytest.raises(SystemExit) as exit_info:
        style_install('a"b', "claude-code")
    assert "may hold only" in str(exit_info.value)


def test_the_style_record_round_trips_a_path_holding_a_quote(home):
    """Names are validated, paths are not — a home directory with a quote in it
    would otherwise emit TOML that every later flw command fails to parse,
    including plain `flw install`."""
    quoted = str(home / 'it"s' / "flw-terse.md")
    flw.write_style(
        [
            {
                "host": "claude-code",
                "name": "flw-terse",
                "source": quoted,
                "path": quoted,
                "created": True,
            }
        ]
    )
    assert [e["path"] for e in flw.read_style()] == [quoted]


def test_uninstall_keeps_an_instructions_file_that_was_there_before(home, capsys):
    """A file holding only whitespace is still the user's. Ownership is recorded
    at install time, never inferred from what is left after the block goes."""
    instructions = home / ".codex" / "AGENTS.md"
    instructions.parent.mkdir(parents=True)
    instructions.write_text("\n\n")

    install("codex", ambient=True)
    uninstall("codex")
    capsys.readouterr()

    assert instructions.is_file()


def test_uninstall_removes_an_instructions_file_flw_created(home, capsys):
    install("codex", ambient=True)
    instructions = home / ".codex" / "AGENTS.md"
    assert instructions.is_file()

    uninstall("codex")
    capsys.readouterr()
    assert not instructions.exists()


def test_doctor_says_when_a_style_is_installed_but_not_selected(home, capsys, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *args: "n")
    install("claude-code")
    flw.style_install(
        argparse.Namespace(name=None, host=["claude-code"], dry_run=False, yes=False)
    )
    capsys.readouterr()

    assert doctor() == 0
    out = capsys.readouterr().out
    assert "installed but not selected" in out
    assert "✓ claude-code: flw-terse" not in out


def test_install_warns_when_a_project_settings_file_wins(home, capsys, tmp_path):
    """~/.claude/settings.json loses to .claude/settings.local.json in the project
    flw is run from, so writing the key there can be a silent no-op."""
    local = tmp_path / ".claude"
    local.mkdir()
    (local / "settings.local.json").write_text(json.dumps({"outputStyle": "theirs"}))

    style_install(None, "claude-code")
    assert "settings.local.json selects theirs, which wins" in capsys.readouterr().out


def test_writing_the_key_keeps_the_files_own_indentation(home, capsys):
    settings = home / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text('{\n    "theme": "dark"\n}\n')

    style_install(None, "claude-code")
    capsys.readouterr()
    assert '\n    "theme": "dark"' in settings.read_text()


def test_renaming_the_style_still_puts_back_what_the_user_had(home, capsys):
    """On a rename select_style reports the name flw itself wrote at the first
    install, so the live key is not evidence of the user's own choice."""
    settings = home / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"outputStyle": "mine", "theme": "dark"}))
    styles = home / ".flw" / "styles"
    styles.mkdir(parents=True)
    (styles / "custom.md").write_text("## Custom\n\nWrite briefly.\n")

    style_install(None, "claude-code")
    style_install("custom", "claude-code")
    style_uninstall("claude-code")
    capsys.readouterr()

    assert json.loads(settings.read_text()) == {"outputStyle": "mine", "theme": "dark"}


def test_install_will_not_replace_a_symlink_it_did_not_create(home, capsys):
    """It would then be recorded as flw's, so uninstall would delete the user's
    own link."""
    theirs = home / "my-flw-spec"
    theirs.mkdir()
    root = home / ".claude" / "skills"
    root.mkdir(parents=True)
    (root / "flw-spec").symlink_to(theirs, target_is_directory=True)

    install("claude-code")
    capsys.readouterr()

    assert (root / "flw-spec").resolve() == theirs
    assert "flw-spec" not in {link["skill"] for link in flw.read_links()}

    uninstall("claude-code")
    capsys.readouterr()
    assert (root / "flw-spec").is_symlink()


def test_a_style_opening_with_a_horizontal_rule_keeps_its_top(home, capsys):
    styles = home / ".flw" / "styles"
    styles.mkdir(parents=True)
    (styles / "mine.md").write_text("---\n\n## Mine\n\nRule one.\n\n---\n\nRule two.\n")

    style_install("mine", "claude-code")
    capsys.readouterr()

    written = (home / ".claude" / "output-styles" / "mine.md").read_text()
    assert "## Mine" in written and "Rule one." in written


def test_uninstall_removes_an_instructions_file_the_style_created(home, capsys):
    style_install(None, "codex")
    instructions = home / ".codex" / "AGENTS.md"
    assert instructions.is_file()

    style_uninstall("codex")
    capsys.readouterr()
    assert not instructions.exists()


def test_the_shadow_warning_survives_a_subdirectory(home, capsys, tmp_path, monkeypatch):
    local = tmp_path / ".claude"
    local.mkdir()
    (local / "settings.local.json").write_text(json.dumps({"outputStyle": "theirs"}))
    deep = tmp_path / "one" / "two"
    deep.mkdir(parents=True)
    monkeypatch.chdir(deep)

    style_install(None, "claude-code")
    assert "settings.local.json selects theirs, which wins" in capsys.readouterr().out


def test_a_hand_edited_record_survives_a_write_instead_of_vanishing(home, capsys):
    """Both state files. Dropping a broken entry would take the user's own text
    with it, and doctor's "unreadable record" is what tells them to fix it."""
    state = home / ".flw" / "style.toml"
    state.parent.mkdir(parents=True)
    state.write_text('[[host]]\nname = "mine"\npath = "/nowhere"\n')

    assert style_uninstall("claude-code") == 0
    capsys.readouterr()
    kept = flw.read_style()
    assert len(kept) == 1
    assert (kept[0]["name"], kept[0]["path"]) == ("mine", "/nowhere")
    assert "host" not in kept[0]

    (home / ".flw" / "ambient.toml").write_text('[[host]]\nhost = "codex"\n')
    install("claude-code", ambient=True)
    capsys.readouterr()
    assert {e.get("host") for e in flw.read_ambient()} == {"codex", "claude-code"}


def test_a_global_paths_specs_applies_where_a_project_declares_none(tmp_path, monkeypatch):
    """The contract declares ~/.flw/config.toml and the project's merged key by
    key. run_tests.py does that for [tests]; nothing did it for [paths], so a
    machine-wide specs directory was documented, silent and ignored."""
    home = tmp_path / "home" / ".flw"
    home.mkdir(parents=True)
    (home / "config.toml").write_text('[paths]\nspecs = "contracts"\n')
    monkeypatch.setattr(flw, "FLW_HOME", home)

    project = tmp_path / "proj"
    project.mkdir()
    assert flw._specs_dir(project) == "contracts"


def test_a_project_paths_specs_wins_over_the_global_one(tmp_path, monkeypatch):
    """Project overlay, global underlay — the order the contract states."""
    home = tmp_path / "home" / ".flw"
    home.mkdir(parents=True)
    (home / "config.toml").write_text('[paths]\nspecs = "contracts"\n')
    monkeypatch.setattr(flw, "FLW_HOME", home)

    project = tmp_path / "proj"
    (project / ".flw").mkdir(parents=True)
    (project / ".flw" / "config.toml").write_text('[paths]\nspecs = "mine"\n')
    assert flw._specs_dir(project) == "mine"


# --- the CLI's declared surface cannot drift from the parser --------------- #


def _declared_surface(specs_path: Path) -> dict[tuple[str, ...], set[str]]:
    """Parse the contract's `flw <name> [flags...]` lines into the same shape
    `_parser_surface` builds from `build_parser()`, so the two can be diffed.

    `-h`/`--help` is argparse's, not flw's, and is excluded on both sides.
    """
    contract = tomllib.loads(specs_path.read_text())
    cli = next(
        c for c in contract["final_state"]["components"] if c["name"] == "the flw CLI"
    )
    declared: dict[tuple[str, ...], set[str]] = {}
    for line in cli["surfaces"]:
        if not line.startswith("flw "):
            continue
        tokens = line.split()[1:]
        path = []
        i = 0
        while i < len(tokens) and not tokens[i].startswith(("[", "<")):
            path.append(tokens[i])
            i += 1
        flags: set[str] = set()
        for token in tokens[i:]:
            if not token.startswith("[-"):
                continue
            flags.update(token.strip("[]").split("|"))
        declared[tuple(path)] = flags
    return declared


def _parser_surface(parser: argparse.ArgumentParser) -> dict[tuple[str, ...], set[str]]:
    """(command path -> flags) for every leaf subcommand build_parser() has."""
    result: dict[tuple[str, ...], set[str]] = {}

    def walk(p: argparse.ArgumentParser, prefix: tuple[str, ...]) -> None:
        has_sub = False
        for action in p._actions:
            if isinstance(action, argparse._SubParsersAction):
                has_sub = True
                for name, sub in action.choices.items():
                    walk(sub, prefix + (name,))
        # A parent that dispatches without a subcommand is itself a command the CLI
        # accepts, so the contract has to declare it. `flw kb` is one — bare, it
        # prints the store's counts. `flw style` is not: it has no handler and
        # errors without a verb. Recording leaves alone made a whole surface
        # invisible to a check whose job is that none are.
        if not has_sub or "handler" in p._defaults:
            result[prefix] = {
                s
                for a in p._actions
                for s in a.option_strings
                if s not in ("-h", "--help")
            }

    walk(parser, ())
    return result


def test_the_cli_surface_matches_the_parser_in_both_directions():
    declared = _declared_surface(REPO / "specs" / "current.toml")
    actual = _parser_surface(flw.build_parser())

    for path, flags in declared.items():
        name = " ".join(("flw",) + path)
        assert path in actual, f"{name} is declared but the parser has no such command"
        missing = flags - actual[path]
        assert not missing, (
            f"{name} declares {sorted(missing)}, which the parser does not accept"
        )

    for path, flags in actual.items():
        name = " ".join(("flw",) + path)
        assert path in declared, f"{name} exists in the parser but is not declared"
        extra = flags - declared[path]
        assert not extra, (
            f"{name} accepts {sorted(extra)}, which the contract does not declare"
        )


# --- what flw refuses to write over ----------------------------------------- #
#
# The additive rule the contract states: flw never overwrites a file it did not
# write and never deletes one it did not create. install enforced it; sync,
# remove and style install each had a path around it.


def test_sync_will_not_write_over_a_file_it_did_not_create(home, bundle, capsys):
    """The path install refuses three ways. sync used to unlink and symlink over
    it, so a file that existed nowhere else was gone with nothing reporting it."""
    flw.add(argparse.Namespace(path=str(bundle("team-review")), name=None))
    install("claude-code")
    link = home / ".claude" / "skills" / "team-review"
    link.unlink()
    flw.write_links([lk for lk in flw.read_links() if lk["skill"] != "team-review"])
    link.write_text("IRREPLACEABLE")
    capsys.readouterr()

    assert sync() == 0
    assert link.read_text() == "IRREPLACEABLE"
    assert "not replacing it" in capsys.readouterr().out


def test_sync_will_not_replace_a_symlink_it_did_not_create(home, bundle, tmp_path, capsys):
    flw.add(argparse.Namespace(path=str(bundle("team-review")), name=None))
    install("claude-code")
    mine = tmp_path / "my-own-skill"
    mine.mkdir()
    link = home / ".claude" / "skills" / "team-review"
    link.unlink()
    flw.write_links([lk for lk in flw.read_links() if lk["skill"] != "team-review"])
    link.symlink_to(mine, target_is_directory=True)
    capsys.readouterr()

    assert sync() == 0
    assert link.resolve() == mine.resolve()
    assert "not replacing it" in capsys.readouterr().out


def test_remove_leaves_a_path_the_user_replaced_with_a_file(home, bundle, capsys):
    flw.add(argparse.Namespace(path=str(bundle("team-review")), name=None))
    install("claude-code")
    link = home / ".claude" / "skills" / "team-review"
    link.unlink()
    link.write_text("MINE NOW")
    capsys.readouterr()

    assert flw.remove(argparse.Namespace(name="bundle")) == 0
    assert link.read_text() == "MINE NOW"


def test_install_does_not_adopt_a_symlink_it_did_not_create(home, capsys):
    """Same target, so it looked like flw's own. Recording it as flw's is what
    let uninstall delete a link the user made."""
    skills = home / ".claude" / "skills"
    skills.mkdir(parents=True)
    target = flw.checkout() / "core" / "skills" / "flw-spec"
    (skills / "flw-spec").symlink_to(target, target_is_directory=True)
    capsys.readouterr()

    install("claude-code")
    assert "flw will not replace it" in capsys.readouterr().err
    uninstall()
    assert (skills / "flw-spec").is_symlink(), "uninstall deleted the user's own link"


def test_style_install_keeps_a_hand_edited_copy_unless_told_otherwise(
    home, monkeypatch, capsys
):
    """`doctor` reports this state as something to decide. One command should not
    discard what another asks about."""
    style_install(None, "claude-code")
    installed = home / ".claude" / "output-styles" / "flw-terse.md"
    installed.write_text("---\nname: flw-terse\n---\n\nMY OWN EDIT\n")
    monkeypatch.setattr("builtins.input", lambda *_: "n")
    capsys.readouterr()

    style_install(None, "claude-code", yes=False)
    assert "MY OWN EDIT" in installed.read_text()
    assert "was edited after flw wrote it" in capsys.readouterr().err


def test_a_block_is_replaced_where_it_stands():
    """Appending carried anything below the block above it. The contract says
    what lies outside the markers is the user's and is never touched."""
    block = flw.wrap("OLD", flw.BEGIN, flw.END)
    text = "ABOVE\n\n" + block + "\nBELOW\n"
    out = flw.replace_block(text, flw.wrap("NEW", flw.BEGIN, flw.END), flw.BEGIN, flw.END)

    assert out.index("ABOVE") < out.index(flw.BEGIN) < out.index("BELOW")
    assert "NEW" in out and "OLD" not in out
    assert flw.replace_block(out, flw.wrap("NEW", flw.BEGIN, flw.END), flw.BEGIN, flw.END) == out


def test_a_bundle_name_holding_a_quote_is_still_readable(home, bundle):
    """An f-string emitted TOML that every later flw command failed to parse,
    including the remove that would have cleared it."""
    flw.add(argparse.Namespace(path=str(bundle("team-review")), name='ev"il'))
    assert [b["name"] for b in flw.read_bundles()] == ['ev"il']
    assert flw.remove(argparse.Namespace(name='ev"il')) == 0


def test_sync_will_not_relink_over_a_file_the_user_put_at_a_recorded_path(home, capsys):
    """The hole the choke point found. The path is recorded, so sync called it
    "missing" — a verdict that fires for anything which is not a symlink — and
    unlinked whatever stood there. The record says flw made a symlink here; it
    does not say flw made this file."""
    link = home / ".claude" / "skills" / "flw-spec"
    install("claude-code")
    link.unlink()
    link.write_text("MINE NOW")
    capsys.readouterr()

    assert sync() == 0
    assert link.read_text() == "MINE NOW"
    assert "not replacing it" in capsys.readouterr().out
    assert any(e["skill"] == "flw-spec" for e in flw.read_links()), "the record was dropped"


def test_sync_will_not_remove_a_file_the_user_put_at_an_orphaned_path(home, bundle, capsys):
    """The removal branch. Its path comes from the record, so it never asked
    whether the thing standing there now is still a link flw made."""
    flw.add(argparse.Namespace(path=str(bundle("team-review")), name=None))
    install("claude-code")
    flw.BUNDLES.write_text("# emptied by hand\n")
    link = home / ".claude" / "skills" / "team-review"
    link.unlink()
    link.write_text("MINE NOW")
    capsys.readouterr()

    assert sync() == 0
    assert link.read_text() == "MINE NOW"
    assert "not replacing it" in capsys.readouterr().out


def test_sync_survives_a_link_that_points_elsewhere_and_whose_skill_is_gone(
    home, bundle, tmp_path, capsys
):
    """Found while writing the tests above: this pair was classified "points
    elsewhere", sent to the relink branch, and raised KeyError looking up a skill
    that no longer exists."""
    flw.add(argparse.Namespace(path=str(bundle("team-review")), name=None))
    install("claude-code")
    link = home / ".claude" / "skills" / "team-review"
    mine = tmp_path / "somewhere-else"
    mine.mkdir()
    link.unlink()
    link.symlink_to(mine, target_is_directory=True)
    flw.BUNDLES.write_text("# emptied by hand\n")
    capsys.readouterr()

    assert sync() == 0
    assert not link.exists()


def test_validate_opens_a_record_whose_name_does_not_start_with_v(
    home, tmp_path, monkeypatch, capsys
):
    """Since 5.0 a record is addressed by a name, so globbing `v*.toml` skips
    every record named after what it does. A file validate never opens is a file
    it reports as fine: `sync-guard-minor.toml` and `test-reporting-major.toml`
    were both unchecked in flw's own tree when this was found."""
    root = tmp_path / "named"
    versions = root / "specs" / "versions"
    versions.mkdir(parents=True)
    (root / "specs" / "current.toml").write_text(
        'schema_version = 3\nspec_version = "1.0"\n'
        'assumptions = ["one is enough"]\n\n'
        "[final_state]\n\n"
        "[[final_state.components]]\n"
        'name     = "alpha"\n'
        'paths    = ["src/alpha.py"]\n'
        'provides = ["a user can alpha"]\n\n'
        "[success_criteria]\n"
        'tests = [{ command = "true" }]\n'
        'criteria = "The fixture behaves."\n'
    )
    (versions / "sync-guard-minor.toml").write_text(
        'name    = "sync-guard"\n'
        'summary = "a record the old glob could not see"\n'
        'notes   = "no such field, so this fails the schema and nothing else"\n'
    )
    monkeypatch.chdir(root)

    assert flw.validate(argparse.Namespace(path=None)) != 0
    assert "sync-guard-minor.toml" in capsys.readouterr().err


# --- shape-independence: a run says which project it resolved to ---------- #


def test_flw_test_prints_the_root_it_resolved(tmp_path, capsys, monkeypatch):
    """project_root walks upward and stops at $HOME, so a directory with neither
    specs/ nor .flw/ is answered by an ancestor's checks. Thirty service repos
    under one parent is the shape that makes that routine."""
    parent = tmp_path / "work"
    (parent / ".flw").mkdir(parents=True)
    (parent / ".flw" / "config.toml").write_text('[tests]\nchecks = ["true"]\n')
    inner = parent / "svc-nobody-onboarded"
    inner.mkdir()
    monkeypatch.setenv("FLW_HOME", str(tmp_path / "no-global"))

    assert flw.test(argparse.Namespace(path=str(inner), all=False, timeout=30, stream=False)) == 0
    assert f"root: {parent}" in capsys.readouterr().out


def test_flw_test_all_refuses_a_directory_with_no_contract(tmp_path, capsys, monkeypatch):
    """-A is the contract's full definition of done, and returning 0 having never
    looked for a contract reports a completeness nothing established."""
    root = tmp_path / "configured"
    (root / ".flw").mkdir(parents=True)
    (root / ".flw" / "config.toml").write_text('[tests]\nchecks = ["true"]\n')
    monkeypatch.setenv("FLW_HOME", str(tmp_path / "no-global"))

    args = argparse.Namespace(path=str(root), all=True, timeout=30, stream=False)
    assert flw.test(args) == 2
    assert "no contract at" in capsys.readouterr().err

    args.all = False
    assert flw.test(args) == 0


def test_flw_validate_in_a_repo_with_no_contract_is_not_an_error(tmp_path, capsys, monkeypatch):
    """run_tests.py calls local checks with no specs/ a normal, supported state,
    and flw-research produces exactly that. Nothing is wrong there."""
    root = tmp_path / "configured"
    (root / ".flw").mkdir(parents=True)
    (root / ".flw" / "config.toml").write_text('[tests]\nchecks = ["true"]\n')
    monkeypatch.setenv("FLW_HOME", str(tmp_path / "no-global"))
    monkeypatch.chdir(root)

    assert flw.validate(argparse.Namespace(path=None)) == 0
    out = capsys.readouterr().out
    assert "no contract at" in out
    assert "validated per part" in out


# --- shape-independence: the scout says what it did not read -------------- #


def test_scout_names_the_languages_it_did_not_parse(tmp_path, capsys):
    """A ranking of two Python scripts beside sixteen Rust files is correct about
    the two and silent about the rest, and exits 0 — which is what covered looks
    like to a reader who is told to read the output before opening a file."""
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "deploy.py").write_text("from tools.fix import go\n\ngo()\n")
    (tmp_path / "tools" / "fix.py").write_text("def go():\n    return 1\n")
    (tmp_path / "src").mkdir()
    for i in range(5):
        (tmp_path / "src" / f"m{i}.rs").write_text("pub fn f() {}\n")

    assert flw.scout(argparse.Namespace(path=str(tmp_path), budget=20)) == 0
    assert "not read: 5 .rs" in capsys.readouterr().out


def test_unread_counting_is_relative_to_the_root_not_absolute(tmp_path):
    """The parts are taken relative to root: an absolute path under a dotted
    directory — ~/.cache, a job scratch tree — has a dotted part in it, and
    filtering on absolute parts skips every file in the tree."""
    root = tmp_path / ".cache" / "repo"
    root.mkdir(parents=True)
    (root / "main.rs").write_text("fn main() {}\n")
    (root / ".git").mkdir()
    (root / ".git" / "hidden.rs").write_text("fn x() {}\n")

    assert flw.unread_by_scouts(root, {"node_modules"}) == {".rs": 1}


def _no_stdin(monkeypatch):
    """stdin that cannot answer, as a CI job, a script or an agent has.

    Reproduces the shape rather than closing the real one: `input()` raises
    EOFError either way, and a test that redirected sys.stdin would still
    leave builtins.input reading from the terminal fd.
    """

    def raise_eof(*_):
        raise EOFError("EOF when reading a line")

    monkeypatch.setattr("builtins.input", raise_eof)


def test_a_prompt_with_no_stdin_declines_and_says_why(capsys, monkeypatch):
    _no_stdin(monkeypatch)
    assert flw.confirm("  write it? [y/N] ") is False
    assert "no terminal on stdin — declined" in capsys.readouterr().out


def test_the_ambient_offer_declines_on_no_stdin_and_the_install_still_finishes(
    home, capsys, monkeypatch
):
    """The CRITICAL. Before confirm(), this raised EOFError uncaught out of
    main() — a traceback and exit 1 for every non-interactive caller. The
    ambient block is an optional extra, so declining it must not cost the
    install that was asked for."""
    _no_stdin(monkeypatch)
    code = flw.install(
        argparse.Namespace(hosts=[], dry_run=False, ambient=True, yes=False)
    )
    out = capsys.readouterr().out

    assert code == 0
    assert "no terminal on stdin — declined" in out and "skipped" in out
    assert not (home / ".claude" / "CLAUDE.md").exists()
    # The work that was actually asked for happened anyway.
    assert sorted(p.name for p in (home / ".claude" / "skills").iterdir())


def test_the_style_offer_declines_on_no_stdin_and_writes_the_file_anyway(
    home, capsys, monkeypatch
):
    install()
    capsys.readouterr()
    _no_stdin(monkeypatch)

    assert style_install(yes=False) == 0
    out = capsys.readouterr().out
    assert "no terminal on stdin — declined" in out

    # Selecting is what was declined; writing the style is not.
    assert (home / ".claude" / "output-styles" / "flw-terse.md").exists()
    settings = home / ".claude" / "settings.json"
    assert not settings.exists() or "outputStyle" not in settings.read_text()


def test_the_overwrite_offer_declines_on_no_stdin_and_keeps_the_file(
    home, capsys, monkeypatch
):
    install()
    install_mine(home)
    installed = home / ".claude" / "output-styles" / "mine.md"
    capsys.readouterr()

    # flw wrote it, then someone edited it. doctor reports that as something to
    # decide, so style_install asks before discarding it.
    installed.write_text("## Mine\n\nEdited by hand.\n")
    before = installed.read_text()
    _no_stdin(monkeypatch)
    style_install("mine", "claude-code", yes=False)

    assert "no terminal on stdin — declined" in capsys.readouterr().out
    assert installed.read_text() == before


def test_the_refresh_offer_declines_on_no_stdin_and_leaves_the_copy(
    home, capsys, monkeypatch
):
    source = install_mine(home)
    installed = home / ".claude" / "output-styles" / "mine.md"
    before = installed.read_text()
    capsys.readouterr()

    source.write_text("## Mine\n\nWrite even more briefly.\n")
    _no_stdin(monkeypatch)
    assert sync(yes=False) == 0

    assert "no terminal on stdin — declined" in capsys.readouterr().out
    assert installed.read_text() == before


def test_every_prompt_goes_through_confirm():
    """The four sites are one function so they cannot drift apart. A fifth
    offer added with a bare input() would be unguarded again, and nothing but
    this notices — the crash only shows up without a terminal."""
    source = (REPO / "cli" / "flw.py").read_text()
    calls = [
        ln.strip()
        for ln in source.splitlines()
        if "input(" in ln and not ln.lstrip().startswith("#")
    ]
    assert calls == ['return input(prompt).strip().lower() in ("y", "yes")']


def test_ctrl_c_exits_one_with_a_line_rather_than_a_traceback(capsys, monkeypatch):
    """Separate from confirm(): Ctrl-C ends the command, it does not decline an
    offer and carry on. main() caught OSError only, deliberately, so this was a
    traceback."""
    monkeypatch.setattr(flw, "build_parser", lambda: _interrupting_parser())
    assert flw.main(["flw"]) == 1
    assert "interrupted" in capsys.readouterr().err


def _interrupting_parser():
    def handler(_args):
        raise KeyboardInterrupt

    parser = argparse.ArgumentParser()
    parser.set_defaults(handler=handler)
    return parser


def test_the_interpreter_guard_exits_one_not_two(tmp_path):
    """2 already means "this run proved nothing" for `flw test` and `flw
    validate`. The guard refuses to run, which is what 1 names, and it fires
    ahead of every subcommand — so on an old interpreter any command could
    return a code the contract scopes to two of them."""
    source = (REPO / "cli" / "flw.py").read_text()
    guard = source[: source.index("import argparse")]
    assert "raise SystemExit(1)" in guard and "SystemExit(2)" not in guard
