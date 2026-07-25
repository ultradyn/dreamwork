"""Tests for dreamhub.py.

Every test points `DREAMHUB_HOME` at a tmpdir, so the suite can never read
or write the human's real registry. That is the same reason the guards run
against a copy of a fixture: a test that touches live state is testing the
state.
"""

import json
import os
import sys
import time

import pytest

import dreamhub
from dreamhub import (
    DREAMING,
    MISSING,
    NO_STATUS,
    QUIET,
    STALLED,
    RegistryError,
    add_project,
    age_str,
    find,
    is_target,
    load_registry,
    main,
    normalise,
    probe_disk,
    save_registry,
    slug_for,
    state_for,
)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "dev", "hub"))
import prep  # noqa: E402  — dev/hub/prep.py, the one fixture-ageing rule


@pytest.fixture(autouse=True)
def hub_home(tmp_path, monkeypatch):
    home = tmp_path / "hubhome"
    monkeypatch.setenv("DREAMHUB_HOME", str(home))
    return home


def make_target(root, name, marker=".dreamwork"):
    d = root / name
    d.mkdir(parents=True)
    if marker == ".dreamwork":
        (d / ".dreamwork").mkdir()
    elif marker == "DREAMWORK.md":
        (d / "DREAMWORK.md").write_text("# DREAMWORK.md\n")
    return d


class TestSlug:
    def test_basename_lowercased(self):
        assert slug_for("/home/x/src/Hark", set()) == "hark"

    def test_collision_gets_a_hash_suffix(self):
        a = "/home/x/src/hark"
        b = "/home/x/other/hark"
        first = slug_for(a, set())
        second = slug_for(b, {first})
        assert first == "hark"
        assert second.startswith("hark-") and len(second) == len("hark-") + 6
        assert second != first

    def test_collision_suffix_is_stable_for_a_path(self):
        p = "/home/x/other/hark"
        assert slug_for(p, {"hark"}) == slug_for(p, {"hark"})

    def test_awkward_names_are_sanitised(self):
        assert slug_for("/tmp/My Project (v2)", set()) == "my-project-v2"

    def test_trailing_slash_does_not_produce_an_empty_slug(self):
        assert slug_for("/home/x/src/hark/", set()) == "hark"


class TestNormalise:
    def test_expands_tilde(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        assert normalise("~/src/hark") == str(tmp_path / "src" / "hark")

    def test_relative_becomes_absolute(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert normalise("sub/proj") == str(tmp_path / "sub" / "proj")

    def test_trailing_slash_and_dots_collapse(self, tmp_path):
        p = str(tmp_path / "a" / ".." / "b") + "/"
        assert normalise(p) == str(tmp_path / "b")


class TestIsTarget:
    def test_dreamwork_dir_counts(self, tmp_path):
        assert is_target(str(make_target(tmp_path, "a")))

    def test_dreamwork_md_counts(self, tmp_path):
        assert is_target(str(make_target(tmp_path, "b", "DREAMWORK.md")))

    def test_plain_directory_does_not(self, tmp_path):
        (tmp_path / "plain").mkdir()
        assert not is_target(str(tmp_path / "plain"))


class TestRegistryRoundTrip:
    def test_missing_file_reads_as_empty(self):
        assert load_registry()["projects"] == []

    def test_add_then_load(self, tmp_path):
        t = make_target(tmp_path, "hark")
        reg = load_registry()
        entry, created = add_project(reg, str(t))
        save_registry(reg)
        assert created
        again = load_registry()
        assert [p["slug"] for p in again["projects"]] == ["hark"]
        assert again["projects"][0]["path"] == str(t)
        assert entry["added"]

    def test_saved_file_is_valid_json_with_a_version(self, tmp_path, hub_home):
        t = make_target(tmp_path, "hark")
        reg = load_registry()
        add_project(reg, str(t))
        save_registry(reg)
        data = json.loads((hub_home / "projects.json").read_text())
        assert data["version"] == dreamhub.REGISTRY_VERSION

    def test_save_is_atomic_and_leaves_no_temp_files(self, tmp_path, hub_home):
        reg = load_registry()
        add_project(reg, str(make_target(tmp_path, "hark")))
        save_registry(reg)
        assert sorted(os.listdir(hub_home)) == ["projects.json"]


class TestAdd:
    def test_duplicate_add_is_idempotent(self, tmp_path):
        t = make_target(tmp_path, "hark")
        reg = load_registry()
        add_project(reg, str(t))
        entry, created = add_project(reg, str(t))
        assert not created
        assert len(reg["projects"]) == 1
        assert entry["slug"] == "hark"

    def test_same_project_via_relative_path_is_the_same_entry(
            self, tmp_path, monkeypatch):
        t = make_target(tmp_path, "hark")
        reg = load_registry()
        add_project(reg, str(t))
        monkeypatch.chdir(tmp_path)
        _, created = add_project(reg, "hark")
        assert not created
        assert len(reg["projects"]) == 1

    def test_collision_keeps_both_and_renames_neither(self, tmp_path):
        a = make_target(tmp_path / "one", "hark")
        b = make_target(tmp_path / "two", "hark")
        reg = load_registry()
        add_project(reg, str(a))
        add_project(reg, str(b))
        slugs = [p["slug"] for p in reg["projects"]]
        assert slugs[0] == "hark"          # the incumbent is untouched
        assert slugs[1] != "hark"
        assert len(set(slugs)) == 2

    def test_slug_survives_the_project_it_collided_with_being_removed(
            self, tmp_path):
        """A slug recomputed on READ is a function of the whole list, so
        removing the incumbent silently renames the survivor — every link,
        bookmark and log line that named it now points somewhere else.
        Storing it at add time is what makes that impossible."""
        add_project(r := load_registry(), str(make_target(tmp_path / "one",
                                                          "hark")))
        add_project(r, str(make_target(tmp_path / "two", "hark")))
        save_registry(r)
        survivor = load_registry()["projects"][1]["slug"]
        assert survivor != "hark"
        assert main(["remove", "hark"]) == 0
        assert load_registry()["projects"] == [
            p for p in r["projects"] if p["slug"] == survivor]

    def test_slug_does_not_depend_on_position_in_the_list(self, tmp_path):
        """The same recompute-on-read bug, seen from the other side: a
        reordered registry must read back identically."""
        add_project(r := load_registry(), str(make_target(tmp_path / "one",
                                                          "hark")))
        add_project(r, str(make_target(tmp_path / "two", "hark")))
        save_registry(r)
        before = {p["path"]: p["slug"] for p in load_registry()["projects"]}
        r["projects"].reverse()
        save_registry(r)
        after = {p["path"]: p["slug"] for p in load_registry()["projects"]}
        assert before == after

    def test_non_target_is_rejected(self, tmp_path):
        (tmp_path / "plain").mkdir()
        with pytest.raises(RegistryError, match="not a dreamwork target"):
            add_project(load_registry(), str(tmp_path / "plain"))

    def test_non_target_accepted_with_force(self, tmp_path):
        (tmp_path / "plain").mkdir()
        reg = load_registry()
        entry, created = add_project(reg, str(tmp_path / "plain"), force=True)
        assert created and entry["slug"] == "plain"

    def test_missing_directory_is_rejected_even_with_force(self, tmp_path):
        with pytest.raises(RegistryError, match="not a directory"):
            add_project(load_registry(), str(tmp_path / "nope"), force=True)


class TestFind:
    def test_by_slug_and_by_path(self, tmp_path):
        t = make_target(tmp_path, "hark")
        reg = load_registry()
        add_project(reg, str(t))
        assert find(reg, "hark")["path"] == str(t)
        assert find(reg, str(t))["slug"] == "hark"
        assert find(reg, "nope") is None


class TestCorruptRegistry:
    """A writer that treats corruption as 'empty' rewrites the file and
    destroys it. Readers degrade; writers refuse."""

    def test_reader_degrades(self, hub_home):
        hub_home.mkdir(parents=True)
        (hub_home / "projects.json").write_text("{ this is not json")
        assert load_registry()["projects"] == []

    def test_writer_refuses(self, hub_home):
        hub_home.mkdir(parents=True)
        (hub_home / "projects.json").write_text("{ this is not json")
        with pytest.raises(RegistryError, match="refusing to overwrite"):
            load_registry(strict=True)

    def test_unknown_version_refuses(self, hub_home):
        hub_home.mkdir(parents=True)
        (hub_home / "projects.json").write_text(
            '{"version": 99, "projects": []}')
        with pytest.raises(RegistryError, match="version"):
            load_registry(strict=True)

    def test_corrupt_add_leaves_the_file_untouched(self, tmp_path, hub_home):
        hub_home.mkdir(parents=True)
        raw = "{ this is not json"
        (hub_home / "projects.json").write_text(raw)
        t = make_target(tmp_path, "hark")
        assert main(["add", str(t)]) == 1
        assert (hub_home / "projects.json").read_text() == raw


class TestCli:
    def test_add_list_remove(self, tmp_path, capsys):
        t = make_target(tmp_path, "hark")
        assert main(["add", str(t)]) == 0
        assert main(["list"]) == 0
        assert "hark" in capsys.readouterr().out
        assert main(["remove", "hark"]) == 0
        assert main(["list"]) == 0
        assert "no projects registered" in capsys.readouterr().out

    def test_remove_by_path(self, tmp_path):
        t = make_target(tmp_path, "hark")
        main(["add", str(t)])
        assert main(["remove", str(t)]) == 0
        assert load_registry()["projects"] == []

    def test_remove_unknown_is_an_error(self, capsys):
        assert main(["remove", "ghost"]) == 1
        assert "no project" in capsys.readouterr().err

    def test_add_non_target_reports_and_does_not_register(
            self, tmp_path, capsys):
        (tmp_path / "plain").mkdir()
        assert main(["add", str(tmp_path / "plain")]) == 1
        assert "not a dreamwork target" in capsys.readouterr().err
        assert load_registry()["projects"] == []

    def test_bare_invocation_prints_help(self, capsys):
        assert main([]) == 0
        assert "dreamhub" in capsys.readouterr().out


# ------------------------------------------------------- the disk probe

@pytest.fixture
def hubfix(tmp_path):
    """The frozen fixture, copied and aged, plus its registry.

    Aged rather than frozen because a state that means "how long since"
    cannot be pinned to a wall clock — see dev/hub/prep.py.
    """
    dst = prep.prepare(str(tmp_path / "targets"))
    return prep.registry_for(dst)


def row_for(reg, slug, now=None):
    entry = next(p for p in reg["projects"] if p["slug"] == slug)
    return probe_disk(entry, now=now)


class TestAgeStr:
    @pytest.mark.parametrize("secs,out", [
        (0, "0s"), (45, "45s"), (60, "1m"), (1500, "25m"),
        (3600, "1h"), (10800, "3h"), (86400 * 2, "2d"), (None, ""),
    ])
    def test_vocabulary(self, secs, out):
        assert age_str(secs) == out


class TestStateFor:
    def test_thresholds(self):
        assert state_for(0) == DREAMING
        assert state_for(dreamhub.DREAMING_S - 1) == DREAMING
        assert state_for(dreamhub.DREAMING_S) == QUIET
        assert state_for(dreamhub.QUIET_S - 1) == QUIET
        assert state_for(dreamhub.QUIET_S) == STALLED
        assert state_for(None) == NO_STATUS


class TestProbeDisk:
    def test_fresh_target_is_dreaming_and_carries_its_facts(self, hubfix):
        r = row_for(hubfix, "fresh")
        assert r["state"] == DREAMING
        assert r["age_from"] == "last_tick"
        assert r["port"] == 39801
        assert r["task"].startswith("#96")
        assert r["goal"]
        assert [a["name"] for a in r["agents"]] == [
            "dreamer-hubbuild", "dreamer-thread"]
        assert "dreamhub.py" in r["agents"][0]["owns"]
        assert r["queue"] == {"in_progress": 2, "pending": 23}
        assert r["note"] is None

    def test_quiet_target(self, hubfix):
        r = row_for(hubfix, "quiet")
        assert r["state"] == QUIET
        assert r["age_str"] == "25m"

    def test_stalled_target_never_watched_has_no_port(self, hubfix):
        r = row_for(hubfix, "stalled")
        assert r["state"] == STALLED
        assert r["port"] is None

    def test_target_that_never_ticked(self, hubfix):
        r = row_for(hubfix, "nostatus")
        assert r["state"] == NO_STATUS
        assert r["age"] is None and r["age_str"] == ""
        assert "has not ticked" in r["note"]

    def test_half_written_status_does_not_crash_and_stays_live(self, hubfix):
        """status.json is rewritten every tick, so the hub WILL read one
        mid-write. Reporting that target as 'no status' would be a lie that
        flickers once a tick — it is dreaming harder than any other row."""
        r = row_for(hubfix, "torn")
        assert r["state"] == DREAMING
        assert r["age_from"] == "file"
        assert "unreadable" in r["note"]
        assert r["task"] is None       # the contents really are lost
        assert r["port"] == 39804

    def test_deleted_directory_shows_as_missing_not_absent(self, hubfix):
        r = row_for(hubfix, "gone")
        assert r["state"] == MISSING
        assert "gone" in r["note"]

    def test_every_registry_entry_produces_exactly_one_row(self, hubfix):
        rows = [probe_disk(p) for p in hubfix["projects"]]
        assert len(rows) == len(hubfix["projects"])
        assert [r["slug"] for r in rows] == [
            p["slug"] for p in hubfix["projects"]]

    def test_probe_never_raises_on_junk(self, tmp_path):
        d = tmp_path / "junk" / ".dreamwork"
        d.mkdir(parents=True)
        for body in ["", "null", "[]", '"a string"', "{", '{"agents": 3}',
                     '{"agents": [1, 2]}', '{"last_tick": 12345}',
                     '{"queue": "soon"}', '{"agents": {"a": 1}}',
                     '{"agents": [{"owns": 5}]}',
                     '{"agents": [{"owns": "watch.py"}]}',
                     '{"agents": [{}]}', '{"queue": [1, 2]}',
                     '{"last_tick": null}', '{"last_tick": "not a date"}']:
            (d / "status.json").write_text(body)
            r = probe_disk({"slug": "junk", "path": str(tmp_path / "junk")})
            assert r["state"] in (DREAMING, QUIET, STALLED, NO_STATUS)
            assert isinstance(r["agents"], list)

    def test_status_without_a_last_tick_falls_back_to_the_file(self, tmp_path):
        d = tmp_path / "notick" / ".dreamwork"
        d.mkdir(parents=True)
        (d / "status.json").write_text('{"task": "something"}')
        r = probe_disk({"slug": "notick", "path": str(tmp_path / "notick")})
        assert r["age_from"] == "file"
        assert r["state"] == DREAMING
        assert r["task"] == "something"
        assert "no readable last_tick" in r["note"]

    def test_a_future_last_tick_does_not_go_negative(self, tmp_path):
        """Clock skew between machines is real (the NTP mitigation exists
        because of it); an age of -40s must not render as 'stalled'."""
        d = tmp_path / "skew" / ".dreamwork"
        d.mkdir(parents=True)
        (d / "status.json").write_text(
            '{"last_tick": "2099-01-01T00:00:00+10:00"}')
        r = probe_disk({"slug": "skew", "path": str(tmp_path / "skew")})
        assert r["age"] == 0.0
        assert r["state"] == DREAMING


class TestPrep:
    def test_ages_are_relative_to_now_not_to_the_fixture(self, tmp_path):
        """The fixture must read the same in ten years as it does today.

        A fixture frozen to a wall-clock timestamp is `dreaming` on the day
        it is written and a permanent red light by the weekend, and a guard
        whose false reds train you to ignore it is worse than no guard.
        """
        expected = {"fresh": DREAMING, "quiet": QUIET, "stalled": STALLED,
                    "torn": DREAMING, "nostatus": NO_STATUS, "gone": MISSING}
        for label, when in [("today", time.time()),
                            ("ten-years", time.time() + 10 * 365 * 86400)]:
            dst = prep.prepare(str(tmp_path / label), now=when)
            got = {p["slug"]: probe_disk(p, now=when)["state"]
                   for p in prep.registry_for(dst)["projects"]}
            assert got == expected, label

    def test_prep_leaves_the_repo_fixture_untouched(self, tmp_path):
        before = open(os.path.join(prep.FIXTURE, "fresh", ".dreamwork",
                                   "status.json"), encoding="utf-8").read()
        prep.prepare(str(tmp_path / "a"))
        after = open(os.path.join(prep.FIXTURE, "fresh", ".dreamwork",
                                  "status.json"), encoding="utf-8").read()
        assert before == after

    def test_torn_is_not_repaired_by_prep(self, tmp_path):
        dst = prep.prepare(str(tmp_path / "a"))
        raw = open(os.path.join(dst, "torn", ".dreamwork", "status.json"),
                   encoding="utf-8").read()
        with pytest.raises(ValueError):
            json.loads(raw)
