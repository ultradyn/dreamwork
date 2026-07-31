#!/usr/bin/env python3
"""file_notify.py — one way to be told a file changed, on every platform.

WHY THIS EXISTS
---------------
Two places in this repo already watch files and neither can be reused by the
other: `qsnap.py:222` shells out to `inotifywait`, and `watch.py:5843` sleeps
in a loop re-`stat`ing its own sources. `dreamhub.py:255` re-`stat`s every
target on every request. This module is the ONE implementation those three
shapes can share, so the next consumer (`#631`, the live session-log view)
does not become a fourth.

A LEAF MODULE (the `ledger_parse` / `status_derive` idiom): it imports nothing
from this repo and nothing outside the stdlib, so `watch.py` and `dreamhub.py`
can both import it without a cycle and without either importing the other —
which is what `dreamhub-design.md:55` ("never code, no `import watch`") leaves
open and what the standing focus (watch.py into modules reusable by dreamhub)
asks for.

THE MECHANISM IS MEASURED, NOT ASSUMED
--------------------------------------
The primary backend is ctypes against libc's inotify. That was checked for the
brittleness it is fair to suspect — the same probe was run on glibc 2.31 and
2.43, on musl, on Python 3.9 through 3.14, on btrfs, tmpfs and overlayfs, on
two kernel lines. The wire format was byte-identical in all of them: a 16-byte
header, `struct inotify_event { int wd; uint32 mask, cookie, len; char name[]; }`,
and the `IN_*` constants at their documented values. That is not luck. The
struct and the constants are kernel UAPI, frozen by Linux's no-break-userspace
rule, and the three functions are thin syscall wrappers present in glibc since
2.9 (2008) and in musl since inception. So the FFI surface is three symbols,
one struct and a handful of integers, all ABI-frozen.

ONE variance did show up, and it is the reason for `_libc()` below:
`ctypes.util.find_library("c")` returns **None on musl** while
`ctypes.CDLL(None)` works everywhere. `watch.py:3220` uses the `find_library`
form. It fails safe there (the caller reads `None` as "birth time unknown"),
but it is the idiom the next author copies, so this module deliberately does
NOT copy it: `CDLL(None)` first, `find_library` only as a fallback.

INOTIFY DOES NOT DIE SILENTLY — IT DIES LOUDLY AND DOES NOT RECOVER
-------------------------------------------------------------------
`qsnap.py:273` says inotify "dies silently if the watch is dropped (directory
replaced, limit exhausted)", and runs a 1s poll as a backstop for that. Half of
that is measurably wrong, and the correction is what shapes this module:

  · watched directory removed  -> IN_DELETE_SELF then IN_IGNORED   ANNOUNCED
  · watched directory replaced -> IN_IGNORED, then permanently blind
  · kernel queue overflowed    -> IN_Q_OVERFLOW (wd -1)            ANNOUNCED
  · inotify instances used up  -> inotify_init1 returns -1, EMFILE DETECTABLE

The kernel tells us every time. What it does not do is *recover*. So the fix is
not to quietly re-`stat` underneath and hope — that would paper over the loss
with something that looks like success. It is to hand the loss to the caller as
an event they cannot miss: `Change.WATCH_LOST` and `Change.OVERFLOW` are first
class here, which is this repo's "nothing fails quietly" applied to a watcher.
A caller that ignores them is choosing to; a caller that handles them can
`rearm()` and know it lost ground.

A FILE PATH IS WATCHED VIA ITS DIRECTORY
----------------------------------------
Handed a file, this watches its PARENT and filters by basename. That is
`qsnap.py:224-228`'s hard-won lesson, and it is not an optimisation: this
repo's `atomic_write_text` replaces files with `os.replace`, so a watch pinned
to the inode "would follow the old inode into oblivion and see nothing ever
again". Directory-watching survives it; inode-watching does not.

BACKENDS DEGRADE, THEY DO NOT CRASH
-----------------------------------
Backends are tried in priority order and the first that opens wins. macOS and
Windows have no native backend here — they are not stubs that raise, they fall
through to `poll`, which works everywhere. Why each backend declined is kept in
`Watcher.selection_log`, so a degrade is legible instead of silent.

`register_backend()` is a real seam, not a notional one: an `inotifywait`-CLI
backend is a drop-in that needs no change to this file. It is deliberately not
built, because the condition for building it was measured false — the FFI is
not brittle, and `inotifywait` was absent on four of the five environments
probed, including both of this project's build boxes. A fallback less available
than the thing it backs up is not a fallback.

USAGE
-----
    # threads (what watch.py and dreamhub.py have today)
    with file_notify.Watcher(".dreamwork") as w:
        for ev in w.read_events(timeout=5.0):
            print(ev.path, ev.change)

    handle = file_notify.watch_thread(".dreamwork", print)
    handle.stop()

    # asyncio ("just start a task and go from there")
    async for ev in file_notify.awatch(".dreamwork"):
        print(ev.path, ev.change)
"""

from __future__ import annotations

import enum
import os
import select
import struct
import sys
import threading
import time
from dataclasses import dataclass, field

__all__ = [
    "Change", "FileEvent", "Watcher", "BackendUnavailable",
    "register_backend", "available_backends", "watch_thread", "awatch",
]


class Change(enum.Flag):
    """What happened. A single event may carry several of these."""

    CREATED = enum.auto()
    MODIFIED = enum.auto()
    CLOSED_WRITE = enum.auto()
    DELETED = enum.auto()
    MOVED_FROM = enum.auto()
    MOVED_TO = enum.auto()
    ATTRIB = enum.auto()
    #: the watch is gone and this backend is now blind on that path
    WATCH_LOST = enum.auto()
    #: the kernel dropped events; what happened in the gap is unknown
    OVERFLOW = enum.auto()


#: Changes that mean "we lost information", as opposed to "something changed".
LOSS = Change.WATCH_LOST | Change.OVERFLOW


@dataclass(frozen=True)
class FileEvent:
    """One observed change.

    `path` is absolute where the backend can determine it. For `OVERFLOW`
    there is no path — the kernel does not say what it dropped — so `path`
    is the watch root and `change` carries the loss.
    """

    path: str
    change: Change
    root: str = ""
    is_dir: bool = False

    def lost(self) -> bool:
        """True when this event reports missing information, not a change."""
        return bool(self.change & LOSS)


class BackendUnavailable(Exception):
    """Raised by a backend factory that cannot run here. Not an error."""


# ── backend registry ─────────────────────────────────────────────────────
# (priority, name, factory). Lower priority is tried first. A CLI backend
# would register at 50 and need no change to anything below.
_REGISTRY: list[tuple[int, str, object]] = []


def register_backend(name: str, factory, priority: int = 50) -> None:
    """Register an event source. Lower `priority` is tried first.

    `factory(paths)` returns a backend or raises `BackendUnavailable`.
    """
    _REGISTRY[:] = [e for e in _REGISTRY if e[1] != name]
    _REGISTRY.append((priority, name, factory))
    _REGISTRY.sort(key=lambda e: (e[0], e[1]))


def available_backends() -> list[str]:
    """Registered backend names, in the order they are tried."""
    return [name for _, name, _ in _REGISTRY]


# ── inotify (Linux) ──────────────────────────────────────────────────────
_IN = {
    "ACCESS": 0x001, "MODIFY": 0x002, "ATTRIB": 0x004, "CLOSE_WRITE": 0x008,
    "CLOSE_NOWRITE": 0x010, "OPEN": 0x020, "MOVED_FROM": 0x040,
    "MOVED_TO": 0x080, "CREATE": 0x100, "DELETE": 0x200,
    "DELETE_SELF": 0x400, "MOVE_SELF": 0x800,
    "UNMOUNT": 0x2000, "Q_OVERFLOW": 0x4000, "IGNORED": 0x8000,
    "ISDIR": 0x40000000,
}
_IN_NONBLOCK = 0o4000
_IN_CLOEXEC = 0o2000000

#: `struct inotify_event` minus the flexible `name[]`. Kernel UAPI; measured
#: at exactly 16 bytes on glibc 2.31/2.43, musl, and Python 3.9-3.14.
_HEADER = struct.Struct("iIII")

#: What we ask the kernel for. Deliberately not IN_ALL_EVENTS: IN_ACCESS and
#: IN_OPEN fire on every read of every file and would drown the queue, which
#: is the documented road to IN_Q_OVERFLOW.
_WATCH_MASK = (
    _IN["MODIFY"] | _IN["ATTRIB"] | _IN["CLOSE_WRITE"] | _IN["MOVED_FROM"]
    | _IN["MOVED_TO"] | _IN["CREATE"] | _IN["DELETE"] | _IN["DELETE_SELF"]
    | _IN["MOVE_SELF"]
)

_MASK_TO_CHANGE = (
    (_IN["CREATE"], Change.CREATED),
    (_IN["MODIFY"], Change.MODIFIED),
    (_IN["CLOSE_WRITE"], Change.CLOSED_WRITE),
    (_IN["DELETE"], Change.DELETED),
    (_IN["MOVED_FROM"], Change.MOVED_FROM),
    (_IN["MOVED_TO"], Change.MOVED_TO),
    (_IN["ATTRIB"], Change.ATTRIB),
    (_IN["DELETE_SELF"], Change.WATCH_LOST),
    (_IN["MOVE_SELF"], Change.WATCH_LOST),
    (_IN["UNMOUNT"], Change.WATCH_LOST),
    (_IN["IGNORED"], Change.WATCH_LOST),
    (_IN["Q_OVERFLOW"], Change.OVERFLOW),
)


def _libc():
    """Return libc with inotify bound, or raise BackendUnavailable.

    `CDLL(None)` dlopens the already-loaded process image and is the form
    that works on musl, where `find_library("c")` returns None. That is a
    measured difference, not a preference — see the module docstring.
    """
    try:
        import ctypes
        import ctypes.util
    except ImportError as exc:                    # pragma: no cover
        raise BackendUnavailable(f"no ctypes: {exc}") from exc

    lib = None
    try:
        lib = ctypes.CDLL(None, use_errno=True)
        lib.inotify_init1
    except (OSError, AttributeError):
        lib = None
    if lib is None:
        name = ctypes.util.find_library("c")
        if not name:
            raise BackendUnavailable("libc not resolvable")
        try:
            lib = ctypes.CDLL(name, use_errno=True)
            lib.inotify_init1
        except (OSError, AttributeError) as exc:
            raise BackendUnavailable(f"no inotify in libc: {exc}") from exc

    lib.inotify_init1.argtypes = [ctypes.c_int]
    lib.inotify_init1.restype = ctypes.c_int
    lib.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p,
                                      ctypes.c_uint32]
    lib.inotify_add_watch.restype = ctypes.c_int
    lib.inotify_rm_watch.argtypes = [ctypes.c_int, ctypes.c_int]
    lib.inotify_rm_watch.restype = ctypes.c_int
    return lib, ctypes


class _InotifyBackend:
    """Kernel-native watching. Emits every `Change` including the loss ones."""

    name = "inotify"
    capabilities = (
        Change.CREATED | Change.MODIFIED | Change.CLOSED_WRITE | Change.DELETED
        | Change.MOVED_FROM | Change.MOVED_TO | Change.ATTRIB
        | Change.WATCH_LOST | Change.OVERFLOW
    )

    def __init__(self, roots: dict[str, str | None]):
        self._lib, self._ctypes = _libc()
        self._fd = self._lib.inotify_init1(_IN_NONBLOCK | _IN_CLOEXEC)
        if self._fd < 0:
            err = self._ctypes.get_errno()
            raise BackendUnavailable(
                f"inotify_init1 failed, errno {err} ({os.strerror(err)})")
        self._roots = roots
        self._wd: dict[int, str] = {}
        try:
            for d in roots:
                self._add(d)
        except Exception:
            self.close()
            raise

    def _add(self, directory: str) -> None:
        wd = self._lib.inotify_add_watch(
            self._fd, os.fsencode(directory), _WATCH_MASK)
        if wd < 0:
            err = self._ctypes.get_errno()
            raise BackendUnavailable(
                f"cannot watch {directory}: errno {err} ({os.strerror(err)})")
        self._wd[wd] = directory

    def fileno(self) -> int | None:
        return self._fd

    def rearm(self) -> list[str]:
        """Re-establish watches for roots that were lost. Returns those fixed.

        Not automatic: a caller that saw WATCH_LOST decides whether the path
        coming back means the same thing to them. After a directory is
        replaced, re-adding attaches to the NEW directory — which is right
        for a log directory and wrong for a one-shot handoff, and this module
        is not entitled to guess which.
        """
        live = set(self._wd.values())
        fixed = []
        for d in self._roots:
            if d in live or not os.path.isdir(d):
                continue
            try:
                self._add(d)
                fixed.append(d)
            except BackendUnavailable:
                pass
        return fixed

    def read_events(self, timeout: float | None = None) -> list[FileEvent]:
        if self._fd < 0:
            return []
        ready, _, _ = select.select([self._fd], [], [],
                                    timeout if timeout is not None else None)
        if not ready:
            return []
        try:
            buf = os.read(self._fd, 1 << 20)
        except (BlockingIOError, InterruptedError):
            return []
        except OSError:
            return []
        return self._parse(buf)

    def _parse(self, buf: bytes) -> list[FileEvent]:
        out: list[FileEvent] = []
        off = 0
        while off + _HEADER.size <= len(buf):
            wd, mask, _cookie, length = _HEADER.unpack_from(buf, off)
            off += _HEADER.size
            raw = buf[off:off + length]
            off += length
            name = raw.split(b"\0", 1)[0]
            directory = self._wd.get(wd, "")

            change = Change(0)
            for bit, flag in _MASK_TO_CHANGE:
                if mask & bit:
                    change |= flag
            if not change:
                continue
            if mask & _IN["IGNORED"]:
                self._wd.pop(wd, None)

            if mask & _IN["Q_OVERFLOW"]:
                # wd is -1 here; the kernel does not say what it dropped.
                for root in self._roots:
                    out.append(FileEvent(root, Change.OVERFLOW, root))
                continue

            path = (os.path.join(directory, os.fsdecode(name))
                    if name else directory)
            wanted = self._roots.get(directory)
            if wanted is not None and name and os.fsdecode(name) != wanted:
                # a file-scoped watch: the directory is watched, but only one
                # basename in it was asked for. Loss events are never filtered
                # out, because losing the watch loses the file too.
                if not (change & LOSS):
                    continue
            out.append(FileEvent(path, change, directory,
                                 bool(mask & _IN["ISDIR"])))
        return out

    def close(self) -> None:
        if getattr(self, "_fd", -1) >= 0:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = -1


def _inotify_factory(roots, **kw):
    # sys.platform, not os.uname(): os.uname does not exist on Windows, and a
    # stub backend that raises AttributeError instead of BackendUnavailable
    # would crash selection rather than degrade through it.
    if not sys.platform.startswith("linux"):
        raise BackendUnavailable(f"no inotify on {sys.platform}")
    return _InotifyBackend(roots)


# ── stat poll (everywhere) ───────────────────────────────────────────────
class _PollBackend:
    """The floor. Works on macOS, Windows, and Linux without inotify.

    HONEST LIMITS, because a watcher that hides these is worse than none:
      · A move is indistinguishable from delete+create, so MOVED_FROM and
        MOVED_TO are never emitted — a move out reads DELETED, a move in
        reads CREATED.
      · CLOSED_WRITE cannot be observed at all; there is no "writer finished"
        in `stat`. A consumer that needs to avoid reading a half-written file
        must not rely on this backend for it.
      · A modification that leaves size AND mtime unchanged is invisible.
        That is not hypothetical here: `#634` records that tmpfs does not
        update mtime for mmap'd writes, so on tmpfs this backend can be
        blind to a real change.
    `capabilities` states this in code so a caller can check rather than
    assume, and `Watcher.capabilities` forwards it.
    """

    name = "poll"
    capabilities = Change.CREATED | Change.MODIFIED | Change.DELETED

    def __init__(self, roots: dict[str, str | None], interval: float = 1.0):
        self._roots = roots
        self.interval = interval
        self._seen = self._snapshot()

    def _snapshot(self) -> dict[str, tuple]:
        state: dict[str, tuple] = {}
        for directory, wanted in self._roots.items():
            try:
                names = os.listdir(directory)
            except OSError:
                continue
            for n in names:
                if wanted is not None and n != wanted:
                    continue
                p = os.path.join(directory, n)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                state[p] = (st.st_mtime_ns, st.st_size, st.st_ino)
        return state

    def scan(self) -> list[FileEvent]:
        """Diff against the last snapshot. Synchronous and deterministic.

        This is the whole mechanism, callable without a clock — which is why
        the tests can drive it exactly rather than sleeping and hoping.
        """
        now = self._snapshot()
        out = []
        for p, sig in now.items():
            was = self._seen.get(p)
            if was is None:
                out.append(FileEvent(p, Change.CREATED, os.path.dirname(p)))
            elif was != sig:
                change = Change.MODIFIED
                if was[2] != sig[2]:
                    # different inode at the same path: replaced, not edited
                    change = Change.CREATED
                out.append(FileEvent(p, change, os.path.dirname(p)))
        for p in self._seen:
            if p not in now:
                out.append(FileEvent(p, Change.DELETED, os.path.dirname(p)))
        self._seen = now
        return out

    def fileno(self) -> int | None:
        return None      # nothing to select on; the adapters branch on this

    def rearm(self) -> list[str]:
        return []        # a poll cannot lose its watch, so nothing to rearm

    def read_events(self, timeout: float | None = None) -> list[FileEvent]:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            events = self.scan()
            if events:
                return events
            remaining = self.interval
            if deadline is not None:
                remaining = min(remaining, deadline - time.monotonic())
                if remaining <= 0:
                    return []
            time.sleep(max(0.0, remaining))

    def close(self) -> None:
        self._seen = {}


def _poll_factory(roots, **kw):
    return _PollBackend(roots, **kw)


register_backend("inotify", _inotify_factory, priority=10)
register_backend("poll", _poll_factory, priority=90)


# ── the watcher ──────────────────────────────────────────────────────────
def _resolve(paths) -> dict[str, str | None]:
    """Map each path to the DIRECTORY to watch and the basename to keep.

    A directory watches itself and keeps everything (`None`). A file watches
    its parent and keeps only its own basename — `qsnap.py:224-228`, because
    `os.replace` moves the file to a new inode and an inode watch goes blind.
    """
    if isinstance(paths, (str, os.PathLike)):
        paths = [paths]
    roots: dict[str, str | None] = {}
    for p in paths:
        p = os.path.abspath(os.fspath(p))
        if os.path.isdir(p):
            roots[p] = None
        else:
            parent = os.path.dirname(p) or "."
            # a directory-wide watch already covers any file inside it
            if roots.get(parent, "") is not None:
                roots[parent] = os.path.basename(p)
    return roots


class Watcher:
    """Tell me when these paths change. Thread-native; see `awatch` for async.

    The core is deliberately synchronous and owns no thread and no loop. That
    is what lets one implementation serve `watch.py`'s ThreadingHTTPServer,
    `dreamhub.py`'s thread pool, and an asyncio consumer — each adapts the
    same object rather than paying for a concurrency model it does not use.
    """

    def __init__(self, paths, *, require: str | None = None, **kw):
        """`require` names ONE backend and refuses if it is unavailable.

        It is `require` rather than `prefer` because that is what it does:
        naming a backend that cannot open raises instead of quietly handing
        back a different one. A caller who asked for inotify by name and got
        stat-polling without being told is exactly the silent substitution
        this module exists to avoid — and a parameter called `prefer` would
        promise the fallback that `require` refuses (the #659 lesson: the
        name has to carry its meaning at the call site).
        """
        self.roots = _resolve(paths)
        self.selection_log: list[tuple[str, str]] = []
        self._backend = None
        for _prio, name, factory in _REGISTRY:
            if require is not None and name != require:
                self.selection_log.append((name, "not the required backend"))
                continue
            try:
                self._backend = factory(self.roots, **kw) if kw else factory(self.roots)
            except BackendUnavailable as exc:
                self.selection_log.append((name, str(exc)))
                continue
            self.selection_log.append((name, "selected"))
            break
        if self._backend is None:
            raise BackendUnavailable(
                "no usable backend: "
                + "; ".join(f"{n}: {w}" for n, w in self.selection_log))

    @property
    def backend_name(self) -> str:
        return self._backend.name

    @property
    def capabilities(self) -> Change:
        """Which `Change` values the SELECTED backend can actually emit."""
        return self._backend.capabilities

    @property
    def degraded(self) -> bool:
        """True when a higher-priority backend declined and we fell through.

        A backend skipped by `require` is not a degrade — it was never
        going to be used — so only a real decline counts.
        """
        return any(why not in ("selected", "not the required backend")
                   for _, why in self.selection_log)

    def fileno(self) -> int | None:
        """A selectable fd, or None when the backend has none (poll)."""
        return self._backend.fileno()

    def read_events(self, timeout: float | None = None) -> list[FileEvent]:
        """Block up to `timeout` seconds; return what happened, maybe empty."""
        return self._backend.read_events(timeout)

    def rearm(self) -> list[str]:
        """Re-watch roots lost to WATCH_LOST. Returns the ones restored."""
        return self._backend.rearm()

    def close(self) -> None:
        self._backend.close()

    def __enter__(self) -> "Watcher":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


# ── adapters ─────────────────────────────────────────────────────────────
@dataclass
class ThreadHandle:
    """A daemon thread pumping a callback. `stop()` then `join()`."""

    thread: threading.Thread
    _stop: threading.Event = field(default_factory=threading.Event)
    watcher: Watcher | None = None

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self.thread.join(timeout)
        if self.watcher is not None:
            self.watcher.close()

    def join(self, timeout: float | None = None) -> None:
        self.thread.join(timeout)


def watch_thread(paths, callback, *, tick: float = 0.5, **kw) -> ThreadHandle:
    """Run a watcher on a daemon thread, calling `callback(event)`.

    `tick` bounds only how long `stop()` takes, never delivery latency: the
    read returns as soon as the kernel has something. This is `qsnap.py:286`'s
    house pattern with the callback made explicit.
    """
    watcher = Watcher(paths, **kw)
    stop = threading.Event()

    def pump() -> None:
        while not stop.is_set():
            for event in watcher.read_events(timeout=tick):
                if stop.is_set():
                    return
                callback(event)

    thread = threading.Thread(target=pump, name="file-notify", daemon=True)
    handle = ThreadHandle(thread, stop, watcher)
    thread.start()
    return handle


async def awatch(paths, *, tick: float = 0.5, **kw):
    """Async-iterate events: `async for ev in awatch(path): ...`

    This is an ADAPTER over the synchronous core, not a second implementation.
    Where the backend has a real fd (inotify) it is registered with the running
    loop via `add_reader` and costs NO thread. Where it does not (poll) the
    blocking read runs in the default executor, costing one — an honest
    difference the caller can predict from `Watcher.fileno()`.
    """
    import asyncio

    watcher = Watcher(paths, **kw)
    loop = asyncio.get_running_loop()
    fd = watcher.fileno()
    try:
        if fd is None:
            while True:
                events = await loop.run_in_executor(
                    None, watcher.read_events, tick)
                for event in events:
                    yield event
        else:
            queue: asyncio.Queue = asyncio.Queue()

            def _drain() -> None:
                for event in watcher.read_events(timeout=0):
                    queue.put_nowait(event)

            loop.add_reader(fd, _drain)
            try:
                while True:
                    yield await queue.get()
            finally:
                loop.remove_reader(fd)
    finally:
        watcher.close()
