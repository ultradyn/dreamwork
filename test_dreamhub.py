"""Tests for dreamhub.py.

Every test points `DREAMHUB_HOME` at a tmpdir, so the suite can never read
or write the human's real registry. That is the same reason the guards run
against a copy of a fixture: a test that touches live state is testing the
state.
"""

import contextlib
import http.server
import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

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


# ------------------------------------------------------- the live probe

class StubWatch:
    """A stdlib stand-in for a watch instance, so the live probe can be
    tested against every way a port can misbehave.

    Deliberately not `watch.py`: the hub must not import it (that would
    couple it to a 3000-line owned file and break the single-file deploy
    snapshot), and the failures being tested here — 404, garbage, slow —
    are ones a healthy watch never produces.
    """

    def __init__(self, mtime="1 100.0", open_questions=4, mtime_status=200,
                 data_body=None, delay=0.0):
        self.mtime = mtime
        self.open_questions = open_questions
        self.mtime_status = mtime_status
        self.data_body = data_body
        self.delay = delay
        self.hits = []
        stub = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                stub.hits.append(self.path)
                if stub.delay:
                    time.sleep(stub.delay)
                if self.path == "/mtime":
                    if stub.mtime_status != 200:
                        self.send_error(stub.mtime_status)
                        return
                    body = stub.mtime
                elif self.path == "/data.json":
                    body = (stub.data_body if stub.data_body is not None
                            else json.dumps(
                                {"open_questions": stub.open_questions,
                                 "target": "/somewhere"}))
                else:
                    self.send_error(404)
                    return
                raw = body.encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


@contextlib.contextmanager
def stub_watch(**kw):
    s = StubWatch(**kw)
    try:
        yield s
    finally:
        s.close()


def free_port():
    """A port nothing is listening on — connection refused, the common case
    of a project whose watch simply is not running."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def live_row(port, cache=None, timeout=1.5, slug="p"):
    row = {"slug": slug, "port": port}
    return dreamhub.probe_live(row, {} if cache is None else cache, timeout)


class TestProbeLive:
    def test_up_reports_the_count_from_data_json(self):
        with stub_watch(open_questions=7) as s:
            r = live_row(s.port)
        assert r["watch"] == dreamhub.UP
        assert r["open_questions"] == 7
        assert r["watch_url"].endswith(f":{s.port}/")

    def test_data_json_is_refetched_only_when_mtime_changes(self):
        """The reuse contract: /mtime is tiny and /data.json is not, so a
        hub polling every 2s must cost a running watch almost nothing."""
        cache = {}
        with stub_watch() as s:
            live_row(s.port, cache)
            live_row(s.port, cache)
            live_row(s.port, cache)
            assert s.hits.count("/data.json") == 1
            s.mtime = "1 200.0"
            r = live_row(s.port, cache)
            assert s.hits.count("/data.json") == 2
            assert r["open_questions"] == 4

    def test_a_restarted_watch_invalidates_the_cache(self):
        """The generation half of /mtime: a rebuilt server means the shell
        changed, and a cache keyed only on mtime would serve the old data."""
        cache = {}
        with stub_watch(mtime="1 100.0") as s:
            live_row(s.port, cache)
            s.mtime, s.open_questions = "2 100.0", 9
            assert live_row(s.port, cache)["open_questions"] == 9

    def test_connection_refused_is_down_not_an_error(self):
        r = live_row(free_port())
        assert r["watch"] == dreamhub.DOWN
        assert r["open_questions"] is None    # unknown, never a second count
        assert "just watch" in r["live_note"]

    def test_404_on_mtime_is_unreadable(self):
        with stub_watch(mtime_status=404) as s:
            r = live_row(s.port)
        assert r["watch"] == dreamhub.UNREADABLE
        assert "404" in r["live_note"]
        assert r["open_questions"] is None

    def test_garbage_data_json_does_not_crash(self):
        with stub_watch(data_body="<html>not json at all</html>") as s:
            r = live_row(s.port)
        assert r["watch"] == dreamhub.UNREADABLE
        assert r["open_questions"] is None

    def test_data_json_that_is_a_list_is_unreadable(self):
        with stub_watch(data_body="[1, 2, 3]") as s:
            r = live_row(s.port)
        assert r["watch"] == dreamhub.UNREADABLE

    def test_a_count_that_is_not_a_number_reads_as_unknown(self):
        with stub_watch(data_body='{"open_questions": "lots"}') as s:
            r = live_row(s.port)
        assert r["watch"] == dreamhub.UP
        assert r["open_questions"] is None

    def test_slow_project_times_out_rather_than_hanging(self):
        with stub_watch(delay=2.0) as s:
            t0 = time.time()
            r = live_row(s.port, timeout=0.3)
            elapsed = time.time() - t0
        assert r["watch"] == dreamhub.TIMEOUT
        assert elapsed < 1.5, f"took {elapsed:.2f}s — the timeout did not bite"

    def test_no_port_means_never_watched(self):
        r = dreamhub.probe_live({"slug": "p", "port": None}, {})
        assert r["watch"] == dreamhub.NEVER_WATCHED
        assert r["watch_url"] is None
        assert r["open_questions"] is None


class TestProbeAll:
    def test_one_slow_project_does_not_delay_the_others(self, tmp_path):
        """The classic aggregator failure. A hard timeout alone is not
        enough — serial polling still costs N x timeout, so a page with a
        few dead ports becomes unusable exactly when it is most needed.

        This goes through `probe_all` on purpose. An earlier version of this
        test built its own thread pool and passed on a serial `probe_all`,
        which is the same bug as testing a page by reading its source.
        """
        with stub_watch(delay=3.0) as slow, stub_watch(open_questions=2) as ok:
            reg = {"version": 1, "projects": []}
            for i in range(6):
                d = tmp_path / f"p{i}" / ".dreamwork"
                d.mkdir(parents=True)
                (d / "watch-port").write_text(
                    str(ok.port if i == 5 else slow.port))
                reg["projects"].append(
                    {"slug": f"p{i}", "path": str(tmp_path / f"p{i}")})
            t0 = time.time()
            rows = dreamhub.probe_all(reg, {}, timeout=0.4)
            elapsed = time.time() - t0
        assert elapsed < 1.2, f"{elapsed:.2f}s — the probes ran serially"
        assert [r["watch"] for r in rows].count(dreamhub.TIMEOUT) == 5
        assert rows[-1]["open_questions"] == 2

    def test_every_entry_still_produces_a_row(self, hubfix):
        rows = dreamhub.probe_all(hubfix, {}, timeout=0.4)
        assert [r["slug"] for r in rows] == [
            p["slug"] for p in hubfix["projects"]]
        for r in rows:
            assert r["watch"] in (dreamhub.UP, dreamhub.DOWN,
                                  dreamhub.TIMEOUT, dreamhub.UNREADABLE,
                                  dreamhub.NEVER_WATCHED)

    def test_a_worker_that_raises_takes_down_only_its_own_row(self,
                                                              monkeypatch):
        rows = [{"slug": "a", "port": 1}, {"slug": "b", "port": 2}]

        def boom(row, cache, timeout):
            if row["slug"] == "a":
                raise RuntimeError("kaboom")
            row["watch"] = dreamhub.UP
            return row

        monkeypatch.setattr(dreamhub, "probe_live", boom)
        out = [dreamhub._probe_live_safe(r, {}, 0.1) for r in rows]
        assert out[0]["watch"] == dreamhub.UNREADABLE
        assert "kaboom" in out[0]["live_note"]
        assert out[1]["watch"] == dreamhub.UP


# ------------------------------------------------- the render and server

def rows_for(hubfix, cache=None):
    return dreamhub.probe_all(hubfix, {} if cache is None else cache,
                              timeout=0.3)


class TestRender:
    """These assert on GENERATED SOURCE, which is exactly what they can do
    and exactly what they cannot: nothing here proves the page renders. That
    is dev/hub/hub.mjs's job, and this class must never be mistaken for it
    (#117)."""

    def test_a_row_per_registry_entry(self, hubfix):
        rows = rows_for(hubfix)
        html = dreamhub.render_page(rows)
        assert html.count('class="row"') == len(hubfix["projects"])
        for p in hubfix["projects"]:
            assert f'data-slug="{p["slug"]}"' in html

    def test_every_state_reaches_the_page(self, hubfix):
        html = dreamhub.render_page(rows_for(hubfix))
        for state in [DREAMING, QUIET, STALLED, NO_STATUS, MISSING]:
            assert f">{state}<" in html

    def test_the_down_row_shows_a_command_and_does_not_link_a_dead_port(
            self, hubfix):
        """The stage-1 lifecycle boundary, in one assertion: the hub says
        what to run and the human runs it."""
        rows = rows_for(hubfix)
        fresh = next(r for r in rows if r["slug"] == "fresh")
        assert fresh["watch"] != dreamhub.UP        # nothing on :39801
        html = dreamhub.render_row(fresh)
        assert "127.0.0.1:39801" not in html
        assert "--target" in html and "watch.py" in html

    def test_a_loop_waiting_on_him_says_so_above_its_task(self, hubfix):
        """A row reading `quiet` over a loop that has stopped for HIM is the
        most expensive wrong impression this page can give: he walks away.
        It sits above the task because what it is doing matters less than
        the fact that it stopped."""
        quiet = next(r for r in rows_for(hubfix) if r["slug"] == "quiet")
        assert len(quiet["awaiting_human"]) == 2
        html = dreamhub.render_row(quiet)
        assert "waiting on you" in html
        assert "+1 more" in html
        assert html.index("waiting on you") < html.index('class="task"')

    def test_a_loop_waiting_on_nothing_says_nothing(self, hubfix):
        fresh = next(r for r in rows_for(hubfix) if r["slug"] == "fresh")
        assert fresh["awaiting_human"] == []
        assert "waiting on you" not in dreamhub.render_row(fresh)

    def test_awaiting_human_survives_a_junk_value(self, tmp_path):
        d = tmp_path / "j" / ".dreamwork"
        d.mkdir(parents=True)
        for body in ['{"awaiting_human": "a string"}',
                     '{"awaiting_human": 3}',
                     '{"awaiting_human": [1, {"a": 2}]}']:
            (d / "status.json").write_text(body)
            row = probe_disk({"slug": "j", "path": str(tmp_path / "j")})
            assert isinstance(row["awaiting_human"], list)
            dreamhub.render_row(row)          # must not raise

    def test_the_missing_row_offers_no_command_it_cannot_honour(self,
                                                                hubfix):
        """Found by looking at the render, not by an assertion: a directory
        that is gone was being offered a command to start a dashboard in it.
        He will run it before he re-reads the state beside it."""
        gone = next(r for r in rows_for(hubfix) if r["slug"] == "gone")
        html = dreamhub.render_row(gone)
        assert "--target" not in html
        assert "directory is gone" in html

    def test_notes_are_additive_not_a_priority_list(self, hubfix):
        """The mid-write row has something to say from the disk AND from the
        network; an elif drops one of them silently."""
        torn = next(r for r in rows_for(hubfix) if r["slug"] == "torn")
        html = dreamhub.render_row(torn)
        assert "unreadable" in html          # why it has no task
        assert "--target" in html            # and how to get its dashboard

    def test_a_port_that_answers_badly_does_not_say_no_dashboard(self):
        with stub_watch(mtime_status=404) as s:
            row = probe_disk({"slug": "x", "path": "/nope"})
            row["port"] = s.port
            dreamhub.probe_live(row, {})
            row["state"] = QUIET          # not missing, so notes are rendered
        html = dreamhub.render_row(row)
        assert "no dashboard" not in html
        assert "404" in html

    def test_an_up_row_links_out_to_its_own_origin(self):
        """Origin-per-project, the one deviation from daemon-mode.md: the
        hub links out rather than proxying, so every absolute URL on the
        target's page is already correct."""
        with stub_watch(open_questions=3) as s:
            row = dreamhub.probe_disk({"slug": "x", "path": "/nope"})
            row["port"] = s.port
            dreamhub.probe_live(row, {})
        html = dreamhub.render_row(row)
        assert f'href="http://127.0.0.1:{s.port}/"' in html
        assert "3 open questions" in html

    def test_an_unknown_count_says_unknown_not_zero(self, hubfix):
        html = dreamhub.render_page(rows_for(hubfix))
        assert "questions unknown" in html
        assert "0 open questions" not in html

    def test_target_text_is_escaped(self, tmp_path):
        """Every string on this page came out of somebody else's repo."""
        d = tmp_path / "evil" / ".dreamwork"
        d.mkdir(parents=True)
        (d / "status.json").write_text(json.dumps({
            "task": '<script>alert("xss")</script>',
            "last_tick": "2026-07-25T12:00:00+10:00",
            "agents": [{"name": "<img src=x onerror=1>",
                        "owns": ["</div><b>oops"]}]}))
        row = probe_disk({"slug": "<b>evil</b>", "path": str(tmp_path/"evil")})
        dreamhub.probe_live(row, {})
        html = dreamhub.render_row(row)
        assert "<script>" not in html
        assert "<img src=x" not in html
        assert "</div><b>oops" not in html
        assert "&lt;script&gt;" in html

    def test_an_empty_registry_says_so(self):
        html = dreamhub.render_page([])
        assert "No projects registered" in html
        assert "dreamhub add" in html

    def test_the_columns_are_labelled_not_the_gaps(self, hubfix):
        html = dreamhub.render_page(rows_for(hubfix))
        head = html.split('id=\'rows\'')[1]
        assert head.index("project") < head.index('class="row"')
        assert head.index("last tick") < head.index('class="row"')

    def test_the_fragment_and_the_page_use_one_renderer(self, hubfix):
        """A second renderer is a second set of rules about what a stalled
        project looks like, and they only agree on the day they are
        written."""
        rows = rows_for(hubfix)
        now = time.time()
        assert dreamhub.render_rows(rows, now) in dreamhub.render_page(
            rows, now)


class TestServer:
    @pytest.fixture
    def hub(self, hubfix, hub_home):
        hub_home.mkdir(parents=True, exist_ok=True)
        dreamhub.save_registry(hubfix)
        httpd = dreamhub.serve(0)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
        httpd.shutdown()
        httpd.server_close()

    def get(self, url):
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read().decode()

    def test_binds_localhost_only(self, hub):
        assert hub.startswith("http://127.0.0.1:")

    def test_index_renders_every_row(self, hub, hubfix):
        code, body = self.get(hub + "/")
        assert code == 200
        assert body.count('class="row"') == len(hubfix["projects"])

    def test_hub_json_shape(self, hub, hubfix):
        _, body = self.get(hub + "/hub.json")
        data = json.loads(body)
        assert data["generated"]
        assert [p["slug"] for p in data["projects"]] == [
            p["slug"] for p in hubfix["projects"]]
        for p in data["projects"]:
            for k in ("slug", "path", "state", "watch", "open_questions",
                      "agents", "age_str"):
                assert k in p, k

    def test_rows_fragment_is_the_page_body(self, hub):
        _, page = self.get(hub + "/")
        _, frag = self.get(hub + "/rows")
        assert frag.count('class="row"') == page.count('class="row"')
        assert "<!doctype" not in frag.lower()

    def test_unknown_path_404s(self, hub):
        with pytest.raises(urllib.error.HTTPError) as e:
            self.get(hub + "/nope")
        assert e.value.code == 404

    def test_the_hub_writes_nothing_outside_its_own_home(self, hub, hubfix,
                                                         tmp_path):
        """The checkable form of 'no writes to any target'."""
        targets = tmp_path / "targets"
        before = {str(p): p.stat().st_mtime
                  for p in targets.rglob("*") if p.is_file()}
        self.get(hub + "/")
        self.get(hub + "/hub.json")
        after = {str(p): p.stat().st_mtime
                 for p in targets.rglob("*") if p.is_file()}
        assert before == after

    def test_port_zero_binds_an_ephemeral_port(self, hub_home):
        """`port or hub_port()` reads 0 as absent and binds a random
        persisted port instead. It succeeds almost every time and collides
        just often enough to look like flakiness — this suite spent one
        run of it before the cause was found."""
        hub_home.mkdir(parents=True, exist_ok=True)
        httpd = dreamhub.serve(0)
        try:
            bound = httpd.server_address[1]
            assert bound != 0
            assert not (hub_home / "port").exists(), (
                "binding an ephemeral port must not mint a persisted one")
        finally:
            httpd.server_close()

    def test_port_persists_across_calls(self, hub_home):
        hub_home.mkdir(parents=True, exist_ok=True)
        first = dreamhub.hub_port()
        assert 3000 <= first < 63000
        assert dreamhub.hub_port() == first
        assert (hub_home / "port").read_text().strip() == str(first)

    def test_port_in_use_names_the_port(self, hub_home, capsys):
        hub_home.mkdir(parents=True, exist_ok=True)
        httpd = dreamhub.serve(0)
        port = httpd.server_address[1]
        try:
            assert dreamhub.main(["serve", "--port", str(port)]) == 1
            assert str(port) in capsys.readouterr().err
        finally:
            httpd.server_close()


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
