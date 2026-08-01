"""Lock-safe live git-status polling.

The poller deliberately refuses to run without an event-backed index.lock
guard.  A sampling watcher cannot guarantee that it saw a short-lived lock.
"""

from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from pathlib import Path
import struct
import subprocess
from typing import Mapping


STATUS_SECONDS = 10.0
PR_SECONDS = 60.0
CI_SECONDS = 120.0

_IN_CREATE = 0x00000100
_IN_MOVED_TO = 0x00000080
_IN_Q_OVERFLOW = 0x00004000
_EVENT = struct.Struct("iIII")


class LockSafetyError(RuntimeError):
    """The poll could not prove that it left index.lock alone."""


class IndexLockAppeared(LockSafetyError):
    """An index.lock creation was observed while the poll ran."""


class GitStatusError(RuntimeError):
    """The read-only status command failed."""


@dataclass(frozen=True)
class PollCadence:
    """Three deliberately separate clocks; PR/CI execution belongs to the plugin."""

    status_seconds: float = STATUS_SECONDS
    pr_seconds: float = PR_SECONDS
    ci_seconds: float = CI_SECONDS

    def due(self, ages: Mapping[str, float], *, pr_exists: bool, pr_draft: bool) -> tuple[str, ...]:
        due = []
        if ages.get("status", float("inf")) >= self.status_seconds:
            due.append("status")
        if ages.get("pr", float("inf")) >= self.pr_seconds:
            due.append("pr")
        if pr_exists and not pr_draft and ages.get("ci", float("inf")) >= self.ci_seconds:
            due.append("ci")
        return tuple(due)


@dataclass(frozen=True)
class GitStatus:
    lines: tuple[str, ...]

    @property
    def dirty(self) -> bool:
        return any(not line.startswith("## ") for line in self.lines)


def _git_dir(repo: Path) -> Path:
    marker = repo / ".git"
    if marker.is_dir():
        return marker.resolve()
    try:
        line = marker.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise GitStatusError(f"cannot resolve git directory for {repo}: {exc}") from exc
    if not line.startswith("gitdir: "):
        raise GitStatusError(f"cannot resolve git directory for {repo}")
    return (repo / line.removeprefix("gitdir: ")).resolve()


class _IndexLockGuard:
    """Detect every queued lock creation; fail closed if inotify cannot judge."""

    def __init__(self, git_dir: Path):
        self.git_dir = git_dir
        self.lock = git_dir / "index.lock"
        self.fd = -1

    def __enter__(self) -> "_IndexLockGuard":
        libc = ctypes.CDLL(None, use_errno=True)
        try:
            init = libc.inotify_init1
            add = libc.inotify_add_watch
        except AttributeError as exc:
            raise LockSafetyError("cannot guard index.lock: inotify is unavailable") from exc
        init.argtypes = [ctypes.c_int]
        init.restype = ctypes.c_int
        add.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        add.restype = ctypes.c_int
        self.fd = init(os.O_NONBLOCK | os.O_CLOEXEC)
        if self.fd < 0:
            self._raise_errno("initialize inotify")
        if add(self.fd, os.fsencode(self.git_dir), _IN_CREATE | _IN_MOVED_TO) < 0:
            self.close()
            self._raise_errno(f"watch {self.git_dir}")
        self._drain()
        if self.lock.exists():
            self.close()
            raise IndexLockAppeared(f"index.lock appeared during git status poll: {self.lock}")
        return self

    def _raise_errno(self, action: str) -> None:
        err = ctypes.get_errno()
        raise LockSafetyError(f"cannot guard index.lock ({action}): {os.strerror(err)}")

    def _drain(self) -> bool:
        appeared = False
        while True:
            try:
                data = os.read(self.fd, 64 * 1024)
            except BlockingIOError:
                return appeared
            except OSError as exc:
                raise LockSafetyError(f"cannot read index.lock guard: {exc}") from exc
            if not data:
                return appeared
            offset = 0
            while offset < len(data):
                _, mask, _, length = _EVENT.unpack_from(data, offset)
                offset += _EVENT.size
                name = data[offset:offset + length].split(b"\0", 1)[0]
                offset += length
                if mask & _IN_Q_OVERFLOW:
                    raise LockSafetyError("cannot prove index.lock absence: inotify queue overflowed")
                appeared = appeared or name == b"index.lock"

    def assert_clean(self) -> None:
        if self.lock.exists() or self._drain():
            raise IndexLockAppeared(f"index.lock appeared during git status poll: {self.lock}")

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def _status_argv(git: str, repo: Path) -> list[str]:
    return [git, "--no-optional-locks", "-C", str(repo), "status",
            "--porcelain=v1", "--branch", "--untracked-files=all"]


def poll(repo: str | Path, *, git: str = "git", timeout: float = 5.0) -> GitStatus:
    """Run one read-only status poll, guarded against even transient index.lock."""

    root = Path(repo).resolve()
    # This process may be the long-lived server.  Set its environment, not
    # only a one-off child's, so every descendant inherits the mitigation.
    os.environ["GIT_OPTIONAL_LOCKS"] = "0"
    env = os.environ.copy()
    with _IndexLockGuard(_git_dir(root)) as guard:
        try:
            result = subprocess.run(
                _status_argv(git, root), capture_output=True, text=True,
                timeout=timeout, check=False, env=env,
            )
        finally:
            guard.assert_clean()
    if result.returncode != 0:
        raise GitStatusError(result.stderr.strip() or f"git status exited {result.returncode}")
    return GitStatus(tuple(result.stdout.splitlines()))
