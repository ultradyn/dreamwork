"""Tests for file_notify.py.

HOW THESE AVOID BEING TIMING-FLAKY, because a file-watcher suite that passes
on a lucky sleep is the characteristic failure of this domain:

  1. NO TEST SLEEPS THEN ASSERTS. Every delivery assertion goes through
     `drain_until`, which blocks in `read_events` and returns the instant the
     kernel has something. The green path costs milliseconds; only a
     genuinely broken watcher pays the timeout. Raising the timeout therefore
     cannot turn a red into a green — it can only make a red slower — which
     is the property a sleep does not have.
  2. ASSERTIONS ARE ON CONTENT, NEVER ON COUNTS OR ARRIVAL. Each one names
     the basename AND the `Change` it expects. A watcher that fires for an
     unrelated reason (the tmpdir itself, a sibling, a stale event) does not
     accidentally satisfy "an event arrived".
  3. THE POLL BACKEND IS DRIVEN WITHOUT A CLOCK. Its whole mechanism is
     `scan()`, so its tests call `scan()` directly and are fully
     deterministic. Nothing waits for a poll interval to elapse. One
     end-to-end test covers the `read_events` wrapper so the deterministic
     tests are not the only thing exercised.
  4. EVERY TEST ASSERTS ITS OWN PRECONDITION (CLAUDE.md: "assert in the check
     the precondition the check depends on"). A test of inotify behaviour that
     silently ran on the poll backend would prove nothing, so each one asserts
     which backend it actually got before asserting what it did.
"""

import os
import struct
import time

import pytest

import file_notify as fn


# ── helpers ──────────────────────────────────────────────────────────────
def drain_until(watcher, predicate, timeout=10.0):
    """Collect events until `predicate(events)` holds, or the deadline passes.

    Deliberately not `sleep(x); read()`. `read_events` wakes on the kernel,
    so a working watcher returns at once and a broken one is the only thing
    that spends the ten seconds.
    """
    deadline = time.monotonic() + timeout
    events = []
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return events
        events.extend(watcher.read_events(timeout=remaining))
        if predicate(events):
            return events


def names(events, change=None):
    return sorted({os.path.basename(e.path) for e in events
                   if change is None or (e.change & change)})


def has(events, basename, change):
    return any(os.path.basename(e.path) == basename and (e.change & change)
               for e in events)


def describe(events):
    return [(os.path.basename(e.path), e.change) for e in events]


def flags_for(events, basename):
    """Every Change bit reported for one basename, OR-ed together."""
    out = fn.Change(0)
    for e in events:
        if os.path.basename(e.path) == basename:
            out |= e.change
    return out


@pytest.fixture
def inotify_watcher(tmp_path):
    """A watcher on tmp_path that is ASSERTED to be the inotify one."""
    w = fn.Watcher(str(tmp_path))
    assert w.backend_name == "inotify", (
        "precondition: these tests describe inotify behaviour, but selection "
        f"chose {w.backend_name!r}; log={w.selection_log}")
    yield w
    w.close()


# ── inotify: the primary rung ────────────────────────────────────────────
class TestInotifyDelivery:
    def test_a_created_file_is_reported_by_its_own_name(
            self, inotify_watcher, tmp_path):
        """Fails if `_InotifyBackend._parse` stops joining the watch
        directory to the event name, or if `_MASK_TO_CHANGE` loses CREATE."""
        (tmp_path / "alpha.txt").write_text("hello")
        events = drain_until(inotify_watcher,
                             lambda e: has(e, "alpha.txt", fn.Change.CREATED))
        assert has(events, "alpha.txt", fn.Change.CREATED), (
            f"no CREATED for alpha.txt; saw {describe(events)}")

    def test_a_file_scoped_watch_never_reports_its_siblings(self, tmp_path):
        """The `_resolve` + `_parse` basename filter.

        Fails if the filter in `_parse` is removed: `noise.txt` then appears
        alongside `only.txt`. This is the discriminating half — asserting
        only that `only.txt` arrives would pass with the filter deleted.
        """
        target = tmp_path / "only.txt"
        target.write_text("start")
        w = fn.Watcher(str(target))
        assert w.backend_name == "inotify", "precondition: inotify selected"
        assert w.roots == {str(tmp_path): "only.txt"}, (
            "precondition: a file must be watched via its parent directory")
        try:
            (tmp_path / "noise.txt").write_text("ignore me")
            target.write_text("changed")
            events = drain_until(
                w, lambda e: has(e, "only.txt", fn.Change.MODIFIED))
            assert has(events, "only.txt", fn.Change.MODIFIED), (
                f"watched file's own change missing; saw {describe(events)}")
            assert "noise.txt" not in names(events), (
                f"sibling leaked through the basename filter: "
                f"{describe(events)}")
        finally:
            w.close()

    def test_an_atomically_replaced_file_is_still_seen(self, tmp_path):
        """Why a file is watched through its DIRECTORY (qsnap.py:224-228).

        `atomic_write_text` writes a temp file and `os.replace`s it over the
        target, giving the target a NEW inode. Fails if `_resolve` is changed
        to hand the file path itself to `inotify_add_watch`: the watch would
        follow the dead inode and this MOVED_TO would never arrive.
        """
        target = tmp_path / "state.json"
        target.write_text("{}")
        w = fn.Watcher(str(target))
        assert w.backend_name == "inotify", "precondition: inotify selected"
        try:
            scratch = tmp_path / "state.json.tmp"
            scratch.write_text('{"new": true}')
            os.replace(scratch, target)
            events = drain_until(
                w, lambda e: has(e, "state.json", fn.Change.MOVED_TO))
            assert has(events, "state.json", fn.Change.MOVED_TO), (
                "an atomic replace of the watched file was not observed; "
                f"saw {describe(events)}")
        finally:
            w.close()

    def test_a_creation_and_a_deletion_do_not_look_the_same(
            self, inotify_watcher, tmp_path):
        """CONSTRUCTED FALSE-GREEN, then closed (direction 2).

        Every other test here asks "did we see KIND for NAME". A `_parse`
        that tagged every event with every flag satisfies all of them at
        once while being useless — you could not tell a delete from a
        create. That version passed the whole suite. This is the assertion
        that discriminates: the kinds must be EXCLUSIVE, not merely present.
        """
        f = tmp_path / "lifecycle.txt"
        f.write_text("x")
        created = drain_until(
            inotify_watcher,
            lambda e: has(e, "lifecycle.txt", fn.Change.CREATED))
        create_flags = flags_for(created, "lifecycle.txt")
        assert create_flags & fn.Change.CREATED, (
            f"precondition: the creation must be seen at all; "
            f"saw {describe(created)}")

        f.unlink()
        deleted = drain_until(
            inotify_watcher,
            lambda e: has(e, "lifecycle.txt", fn.Change.DELETED))
        delete_flags = flags_for(deleted, "lifecycle.txt")
        assert delete_flags & fn.Change.DELETED, (
            f"precondition: the deletion must be seen at all; "
            f"saw {describe(deleted)}")

        assert not (create_flags & fn.Change.DELETED), (
            "a file's CREATION also reported DELETED — the change kinds are "
            f"not discriminated, so no consumer can act on them. "
            f"create carried {create_flags}")
        assert not (delete_flags & fn.Change.CREATED), (
            "a file's DELETION also reported CREATED — the change kinds are "
            f"not discriminated. delete carried {delete_flags}")

    def test_a_deletion_is_reported_as_deleted(
            self, inotify_watcher, tmp_path):
        """Fails if DELETE is dropped from `_WATCH_MASK` or
        `_MASK_TO_CHANGE`."""
        victim = tmp_path / "doomed.txt"
        victim.write_text("x")
        drain_until(inotify_watcher,
                    lambda e: has(e, "doomed.txt", fn.Change.CREATED))
        victim.unlink()
        events = drain_until(inotify_watcher,
                             lambda e: has(e, "doomed.txt", fn.Change.DELETED))
        assert has(events, "doomed.txt", fn.Change.DELETED), (
            f"deletion not reported; saw {describe(events)}")


class TestInotifyLoss:
    """The measured half: inotify announces its own death. Nothing quiet."""

    def test_losing_the_watch_is_an_event_rather_than_a_silence(
            self, tmp_path):
        """Measured: removing a watched directory delivers IN_DELETE_SELF
        (0x400) then IN_IGNORED (0x8000).

        Fails if IGNORED/DELETE_SELF are dropped from `_MASK_TO_CHANGE`, in
        which case the watcher goes blind and says nothing — which is exactly
        the failure `Change.WATCH_LOST` exists to make loud.
        """
        doomed = tmp_path / "watched"
        doomed.mkdir()
        w = fn.Watcher(str(doomed))
        assert w.backend_name == "inotify", "precondition: inotify selected"
        try:
            doomed.rmdir()
            events = drain_until(
                w, lambda e: any(x.change & fn.Change.WATCH_LOST for x in e))
            assert any(e.change & fn.Change.WATCH_LOST for e in events), (
                f"watch loss was silent; saw {describe(events)}")
            assert any(e.lost() for e in events), (
                "FileEvent.lost() must be true for a WATCH_LOST event")
        finally:
            w.close()

    def test_rearm_restores_every_lost_root_not_merely_the_first(
            self, tmp_path):
        """CONSTRUCTED FALSE-GREEN, then closed (direction 2).

        Every other test watches exactly ONE root, so a `rearm` that quietly
        skipped roots whenever more than one was watched passed the entire
        suite. Watching two is the only thing that can see it. Fails if
        `rearm` stops iterating all of `self._roots`.
        """
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir()
        b.mkdir()
        w = fn.Watcher([str(a), str(b)])
        assert w.backend_name == "inotify", "precondition: inotify selected"
        assert set(w.roots) == {str(a), str(b)}, (
            f"precondition: both roots must be watched; got {w.roots}")
        try:
            a.rmdir()
            b.rmdir()
            drain_until(w, lambda e: len(
                [x for x in e if x.change & fn.Change.WATCH_LOST]) >= 2)
            a.mkdir()
            b.mkdir()
            assert sorted(w.rearm()) == sorted([str(a), str(b)]), (
                "rearm must restore EVERY lost root, not just one")
            (a / "in-a.txt").write_text("x")
            (b / "in-b.txt").write_text("x")
            events = drain_until(
                w, lambda e: (has(e, "in-a.txt", fn.Change.CREATED)
                              and has(e, "in-b.txt", fn.Change.CREATED)))
            assert has(events, "in-a.txt", fn.Change.CREATED), (
                f"first root still blind after rearm; saw {describe(events)}")
            assert has(events, "in-b.txt", fn.Change.CREATED), (
                f"second root still blind after rearm; saw {describe(events)}")
        finally:
            w.close()

    def test_rearm_restores_sight_after_the_directory_is_replaced(
            self, tmp_path):
        """Measured: after a replace, inotify is ANNOUNCED-then-blind — a
        write into the replacement produces nothing at all.

        Fails if `_InotifyBackend.rearm` stops re-adding, or if `_parse` stops
        popping the dead wd (then `rearm` believes the root is still live and
        skips it, and the watcher stays blind while looking healthy).
        """
        live = tmp_path / "live"
        live.mkdir()
        w = fn.Watcher(str(live))
        assert w.backend_name == "inotify", "precondition: inotify selected"
        try:
            replacement = tmp_path / "replacement"
            replacement.mkdir()
            os.rename(replacement, live)
            drain_until(
                w, lambda e: any(x.change & fn.Change.WATCH_LOST for x in e))

            # precondition: we really are blind now, or the rearm proves nothing
            (live / "unseen.txt").write_text("a")
            blind = w.read_events(timeout=0.5)
            assert not has(blind, "unseen.txt", fn.Change.CREATED), (
                "precondition failed: the watcher was NOT blind after the "
                f"directory was replaced, so this test cannot show rearm "
                f"fixing anything. saw {describe(blind)}")

            assert w.rearm() == [str(live)], "rearm did not re-watch the root"
            (live / "seen.txt").write_text("b")
            events = drain_until(
                w, lambda e: has(e, "seen.txt", fn.Change.CREATED))
            assert has(events, "seen.txt", fn.Change.CREATED), (
                f"sight not restored after rearm; saw {describe(events)}")
        finally:
            w.close()

    def test_a_queue_overflow_record_is_parsed_as_lost_information(
            self, inotify_watcher, tmp_path):
        """The kernel signals overflow with wd -1 and mask IN_Q_OVERFLOW
        (0x4000) — measured directly by churning 32,868 files past the
        16,384-deep queue. Feeding that exact record to the production
        `_parse` keeps the assertion deterministic and fast while still
        exercising the code that runs.

        Fails if Q_OVERFLOW is dropped from `_MASK_TO_CHANGE`, or if the
        wd -1 record is treated as an ordinary event (it has no path, so it
        would be attributed to whatever directory wd -1 happens to miss).
        """
        record = struct.pack("iIII", -1, 0x4000, 0, 0)
        events = inotify_watcher._backend._parse(record)
        assert events, "an overflow record parsed to nothing at all"
        assert all(e.change & fn.Change.OVERFLOW for e in events), (
            f"overflow not surfaced as OVERFLOW; got {describe(events)}")
        assert all(e.lost() for e in events), (
            "overflow means events were dropped; lost() must be true")
        assert {e.path for e in events} == set(inotify_watcher.roots), (
            "overflow must be attributed to the watch roots, since the "
            "kernel does not say what it dropped")


# ── poll: the floor ──────────────────────────────────────────────────────
class TestPollBackend:
    """Driven through `scan()`: no clock, no sleeping, no interval to race."""

    def _poll(self, path):
        w = fn.Watcher(str(path), require="poll")
        assert w.backend_name == "poll", (
            f"precondition: require='poll' must select poll, got "
            f"{w.backend_name!r}")
        return w

    def test_scan_reports_create_modify_and_delete(self, tmp_path):
        """Fails if `_PollBackend.scan`'s three-way diff loses a branch."""
        w = self._poll(tmp_path)
        try:
            f = tmp_path / "a.txt"
            f.write_text("one")
            assert has(w._backend.scan(), "a.txt", fn.Change.CREATED)

            f.write_text("one-longer")
            assert has(w._backend.scan(), "a.txt", fn.Change.MODIFIED)

            f.unlink()
            assert has(w._backend.scan(), "a.txt", fn.Change.DELETED)

            assert w._backend.scan() == [], (
                "a scan with nothing changed must report nothing")
        finally:
            w.close()

    def test_a_replaced_file_is_created_not_modified(self, tmp_path):
        """Inode-aware diffing. Fails if `scan` compares only (mtime, size):
        an `os.replace` that happens to preserve both then reports MODIFIED,
        or nothing at all, where the file is genuinely a different object."""
        w = self._poll(tmp_path)
        try:
            target = tmp_path / "state.json"
            target.write_text("aaa")
            w._backend.scan()
            old_ino = os.stat(target).st_ino

            scratch = tmp_path / "tmp"
            scratch.write_text("bbb")
            os.replace(scratch, target)
            assert os.stat(target).st_ino != old_ino, (
                "precondition: os.replace must give the path a new inode, "
                "or this test cannot distinguish replace from edit")

            events = w._backend.scan()
            assert has(events, "state.json", fn.Change.CREATED), (
                f"a replaced file must read as CREATED; saw "
                f"{describe(events)}")
        finally:
            w.close()

    def test_a_size_change_is_seen_even_when_the_mtime_did_not_move(
            self, tmp_path):
        """CONSTRUCTED FALSE-GREEN, then closed (direction 2).

        Every other poll test changes size and mtime together, so dropping
        `st_size` from the signature in `_snapshot` passed the whole suite —
        while making the backend blind to any write that lands inside one
        mtime tick. Here the mtime is restored with `os.utime` so SIZE is the
        only thing that moved, which is the only way to pin that field.

        Fails if `_PollBackend._snapshot` stops recording `st_size`.
        """
        w = self._poll(tmp_path)
        try:
            f = tmp_path / "same-mtime.txt"
            f.write_text("aaa")
            w._backend.scan()
            before = os.stat(f)

            f.write_text("aaaaaaaaaaaaaaaaaaaa")
            os.utime(f, ns=(before.st_atime_ns, before.st_mtime_ns))
            after = os.stat(f)
            assert after.st_mtime_ns == before.st_mtime_ns, (
                "precondition: the mtime must be restored exactly, or the "
                "mtime alone would explain the detection")
            assert after.st_size != before.st_size, (
                "precondition: the size must actually differ")
            assert after.st_ino == before.st_ino, (
                "precondition: same inode, or the inode would explain it")

            events = w._backend.scan()
            assert has(events, "same-mtime.txt", fn.Change.MODIFIED), (
                "a size-only change was invisible: the poll signature is not "
                f"tracking st_size. saw {describe(events)}")
        finally:
            w.close()

    def test_capabilities_do_not_claim_what_polling_cannot_see(self, tmp_path):
        """The honesty check. `_PollBackend`'s docstring says it cannot see
        moves or write-completion; this asserts the code agrees, so the
        docstring cannot drift into a lie a caller would act on."""
        w = self._poll(tmp_path)
        try:
            caps = w.capabilities
            assert not (caps & fn.Change.MOVED_TO), (
                "poll cannot distinguish a move from a create; it must not "
                "advertise MOVED_TO")
            assert not (caps & fn.Change.MOVED_FROM)
            assert not (caps & fn.Change.CLOSED_WRITE), (
                "poll cannot observe a writer closing; advertising "
                "CLOSED_WRITE would invite a torn read")
            assert caps & fn.Change.MODIFIED, (
                "poll must still advertise what it CAN do, or callers will "
                "reject the only backend available to them")
        finally:
            w.close()

    def test_no_backend_emits_a_change_it_does_not_advertise(self, tmp_path):
        """CONSTRUCTED FALSE-GREEN, then closed (direction 2).

        `test_capabilities_do_not_claim_what_polling_cannot_see` asserts the
        CONSTANT. Making `_PollBackend.scan` emit MOVED_TO while leaving the
        constant honest broke the contract in the other direction and passed
        the whole suite — the declaration and the behaviour were never
        compared to each other. This compares them, for every backend, so
        `capabilities` is a claim the code has to keep.
        """
        for backend in ("inotify", "poll"):
            w = fn.Watcher(str(tmp_path), require=backend)
            assert w.backend_name == backend, (
                f"precondition: require={backend!r} must select it, got "
                f"{w.backend_name!r}")
            try:
                if backend == "poll":
                    w._backend.interval = 0.02
                (tmp_path / f"{backend}-probe.txt").write_text("x")
                events = drain_until(w, lambda e: bool(e))
                assert events, (
                    f"precondition: the {backend} backend must report "
                    "something, or this proves nothing about what it reports")
                for event in events:
                    assert not (event.change & ~w.capabilities), (
                        f"{backend} emitted {event.change} which is outside "
                        f"its advertised capabilities {w.capabilities}; a "
                        "caller that trusted the declaration would be wrong")
            finally:
                w.close()

    def test_read_events_delivers_end_to_end(self, tmp_path):
        """The deterministic tests above call `scan()` directly, so this is
        the one that proves the production `read_events` wrapper actually
        calls it. Fails if `_PollBackend.read_events` stops invoking `scan`.
        """
        w = self._poll(tmp_path)
        try:
            w._backend.interval = 0.02
            (tmp_path / "late.txt").write_text("x")
            events = drain_until(
                w, lambda e: has(e, "late.txt", fn.Change.CREATED),
                timeout=10.0)
            assert has(events, "late.txt", fn.Change.CREATED), (
                f"poll read_events delivered nothing; saw {describe(events)}")
        finally:
            w.close()


# ── selection, degradation, and the CLI seam ─────────────────────────────
class TestBackendSelection:
    def test_an_unavailable_primary_degrades_to_poll_and_says_why(
            self, tmp_path, monkeypatch):
        """macOS/Windows, and Linux with inotify instances exhausted, all
        arrive here. Fails if `Watcher.__init__` stops catching
        `BackendUnavailable`, or if `selection_log` stops recording the
        reason — a silent degrade is the thing this repo refuses."""
        def broken(roots, **kw):
            raise fn.BackendUnavailable("errno 24 (Too many open files)")

        monkeypatch.setattr(fn, "_REGISTRY",
                            [(10, "inotify", broken)]
                            + [e for e in fn._REGISTRY if e[1] != "inotify"])
        w = fn.Watcher(str(tmp_path))
        try:
            assert w.backend_name == "poll", (
                f"must fall through to the floor, got {w.backend_name!r}")
            assert w.degraded is True, (
                "a fall-through is a degrade and must report itself")
            reasons = dict(w.selection_log)
            assert "Too many open files" in reasons["inotify"], (
                f"the reason for the degrade was lost: {w.selection_log}")
        finally:
            w.close()

    def test_a_third_backend_can_be_added_without_touching_the_module(
            self, tmp_path, monkeypatch):
        """THE CLI SEAM, verified rather than asserted in prose.

        An `inotifywait`-subprocess backend is the human's rung 2. It is not
        built (the brittleness condition measured false), so this proves the
        claim that it WOULD be a drop-in: a backend registered at a priority
        above inotify is selected, with no change to `Watcher` or to either
        built-in backend. Fails if selection stops honouring `_REGISTRY`
        order or stops consulting the registry at all.
        """
        class FakeCli:
            name = "inotifywait-cli"
            capabilities = fn.Change.CREATED | fn.Change.MODIFIED

            def __init__(self, roots):
                self.roots = roots

            def fileno(self):
                return None

            def rearm(self):
                return []

            def read_events(self, timeout=None):
                return [fn.FileEvent("/from/cli", fn.Change.CREATED)]

            def close(self):
                pass

        monkeypatch.setattr(fn, "_REGISTRY", list(fn._REGISTRY))
        fn.register_backend("inotifywait-cli", lambda roots, **kw: FakeCli(roots),
                            priority=5)
        try:
            assert fn.available_backends()[0] == "inotifywait-cli", (
                "priority 5 must sort ahead of inotify's 10; got "
                f"{fn.available_backends()}")
            w = fn.Watcher(str(tmp_path))
            assert w.backend_name == "inotifywait-cli", (
                f"registry order not honoured; got {w.backend_name!r}")
            assert w.read_events(timeout=0)[0].path == "/from/cli", (
                "the registered backend must be the one actually read from")
            w.close()
        finally:
            pass

    def test_no_usable_backend_raises_rather_than_returning_a_dead_watcher(
            self, tmp_path, monkeypatch):
        """Nothing fails quietly: a Watcher that selected nothing must not be
        constructible and then silently deliver no events forever. Fails if
        `Watcher.__init__` drops the final `raise`."""
        def broken(roots, **kw):
            raise fn.BackendUnavailable("nope")

        monkeypatch.setattr(fn, "_REGISTRY",
                            [(10, "inotify", broken), (90, "poll", broken)])
        with pytest.raises(fn.BackendUnavailable) as excinfo:
            fn.Watcher(str(tmp_path))
        assert "inotify" in str(excinfo.value) and "poll" in str(excinfo.value), (
            "the refusal must name every backend it tried and why: "
            f"{excinfo.value}")


# ── adapters ─────────────────────────────────────────────────────────────
class TestAdapters:
    def test_the_thread_adapter_delivers_events_to_its_callback(
            self, tmp_path):
        """Fails if `watch_thread`'s pump stops calling back, or if
        `ThreadHandle.stop` stops joining (the thread would outlive the
        test and leak the watcher's fd)."""
        seen = []
        handle = fn.watch_thread(str(tmp_path), seen.append, tick=0.05)
        try:
            (tmp_path / "threaded.txt").write_text("x")
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                if any(os.path.basename(e.path) == "threaded.txt"
                       for e in list(seen)):
                    break
                time.sleep(0.01)
            assert any(os.path.basename(e.path) == "threaded.txt"
                       for e in list(seen)), (
                f"callback never fired; saw {describe(list(seen))}")
        finally:
            handle.stop()

    def test_stop_joins_the_pump_before_it_returns(self, tmp_path):
        """Separate from the delivery test above, and the separation is the
        point: that test used a 0.05s tick, so the pump exited on its own
        within ~20ms and `not is_alive()` was satisfied whether `stop()`
        joined or not. Two sufficient causes, one assertion — the shape
        lessons.md:336 names. Red-proofing caught it: deleting the join left
        that test GREEN.

        Here the tick is long enough that the pump CANNOT have exited by
        itself, so the only thing that can make it dead is the join. Fails if
        `ThreadHandle.stop` stops joining.
        """
        tick = 1.0
        handle = fn.watch_thread(str(tmp_path), lambda event: None, tick=tick)
        try:
            assert handle.thread.is_alive(), (
                "precondition: the pump thread must be running before we can "
                "show that stop() is what ends it")
            started = time.monotonic()
            handle.stop()
            elapsed = time.monotonic() - started
            assert not handle.thread.is_alive(), (
                f"stop() returned after {elapsed:.3f}s with the pump still "
                f"alive; with a {tick}s tick it cannot have exited on its "
                "own, so stop() skipped its join")
        finally:
            if handle.thread.is_alive():
                handle._stop.set()
                handle.thread.join(5.0)

    def test_the_async_adapter_delivers_over_a_real_event_loop(
            self, tmp_path):
        """`awatch` is the human's "start a task and go from there" form.
        Fails if `add_reader` is not wired (nothing is ever queued) or if the
        generator stops yielding from the queue."""
        import asyncio

        async def scenario():
            got = []

            async def consume():
                async for event in fn.awatch(str(tmp_path)):
                    got.append(event)
                    return

            task = asyncio.create_task(consume())
            await asyncio.sleep(0.1)          # let add_reader register
            (tmp_path / "async.txt").write_text("x")
            await asyncio.wait_for(task, timeout=10.0)
            return got

        got = asyncio.run(scenario())
        assert any(os.path.basename(e.path) == "async.txt" for e in got), (
            f"asyncio adapter delivered nothing useful; saw {describe(got)}")

    def test_the_async_adapter_also_works_without_a_selectable_fd(
            self, tmp_path):
        """The poll backend has no fd, so `awatch` must take its executor
        branch. Fails if `awatch` assumes `fileno()` is always an int —
        `add_reader(None, ...)` raises, and macOS/Windows would be the only
        places anyone noticed."""
        import asyncio

        async def scenario():
            got = []

            async def consume():
                async for event in fn.awatch(str(tmp_path), require="poll",
                                             tick=0.05):
                    got.append(event)
                    return

            task = asyncio.create_task(consume())
            await asyncio.sleep(0.1)
            (tmp_path / "polled.txt").write_text("x")
            await asyncio.wait_for(task, timeout=10.0)
            return got

        got = asyncio.run(scenario())
        assert any(os.path.basename(e.path) == "polled.txt" for e in got), (
            f"poll-backed awatch delivered nothing; saw {describe(got)}")
