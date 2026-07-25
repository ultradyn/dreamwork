"""Tests for dreamhub.py.

Every test points `DREAMHUB_HOME` at a tmpdir, so the suite can never read
or write the human's real registry. That is the same reason the guards run
against a copy of a fixture: a test that touches live state is testing the
state.
"""

import json
import os

import pytest

import dreamhub
from dreamhub import (
    RegistryError,
    add_project,
    find,
    is_target,
    load_registry,
    main,
    normalise,
    save_registry,
    slug_for,
)


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
