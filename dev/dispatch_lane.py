#!/usr/bin/env python3
"""Validate and record a Dreamwork lane prompt, then exec its runner.

The exact prompt bytes read here are appended as one argv item.  Validation is
therefore on the string this wrapper hands to the runner, rather than on a file
the coordinator merely intended to expand.  It cannot prove that a downstream
wrapper preserves that argv unchanged; post-launch inspection is a separate
mechanism with a shorter observation window.

The corpus copy and its hash receipt are intentionally uncommitted.  They make
the validated input available at the merge gate; they do not guarantee that a
coordinator will preserve or commit it.  Every receipt governs its brief; the
task cutoff only grandfathers historical briefs that predate receipts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dreamwork_db import Access, DatabaseError, StoreSpec, open_database  # noqa: E402
from dreamwork_db.tasks import TaskRepository  # noqa: E402
import lane_liveness  # noqa: E402
from lane_liveness import LivenessUnknown, pid_matches_lane  # noqa: E402
from worktree_paths import worktree_roots  # noqa: E402


CONTRACT_PATH = ROOT / "briefs" / "boilerplate.md"
REVIEW_FRAME_PATH = ROOT / "briefs" / "review-frame.md"
INTEGRITY_START_TASK = 766
_TASK_HEAD = re.compile(r"^# [^\n]*?#(\d+)\b", re.MULTILINE)
_BRANCH_LINE = re.compile(
    r"^Branch:\s+`?([A-Za-z0-9][A-Za-z0-9._-]*)`?\s*$", re.MULTILINE
)
_BASE_SHA_LINE = re.compile(r"^Base sha: ([0-9a-f]{7,40})$", re.MULTILINE)
_WORKTREE_LINE = re.compile(r"^Worktree:\s+(.+?)\s*$", re.MULTILINE)
_RECEIPT = re.compile(r"([0-9a-f]{64})  ([^/\n]+\.md)\n?\Z")
_LEDGER_GET = re.compile(r"\bledger\.py\s+get\s+(\d+)\b")
_BARE_TASK_CITE = re.compile(r"(?<![\w])#(\d+)\b")
_MARKDOWN_TASK = re.compile(r"^- \*\*#(\d+)\*\*", re.MULTILINE)
COORDINATOR_INBOX_PREFIX = (
    "Coordinator inbox — ABSOLUTE path, append your completion summary here "
    "when you finish: "
)
ALLOW_PIPED_STDOUT_ENV = "DREAMWORK_ALLOW_PIPED_STDOUT"
LANE_ID_ENV = "DREAMWORK_LANE_ID"
LANE_ROLE_ENV = "DREAMWORK_LANE_ROLE"


class DispatchFault(Exception):
    """An input could not be evaluated or did not carry the contract."""


def validate_stdout() -> None:
    """Refuse peer-backed stdout that could silently kill the exec'd runner."""
    try:
        mode = os.fstat(sys.stdout.fileno()).st_mode
    except (OSError, ValueError) as exc:
        raise DispatchFault(f"could not classify stdout: {exc}") from exc
    if os.environ.get(ALLOW_PIPED_STDOUT_ENV) == "1":
        return
    if stat.S_ISFIFO(mode):
        raise DispatchFault(
            "stdout is a pipe whose reader can close early and kill the runner with SIGPIPE; "
            "redirect to a regular file, or explicitly allow the pipe with "
            f"{ALLOW_PIPED_STDOUT_ENV}=1"
        )
    if stat.S_ISSOCK(mode):
        raise DispatchFault(
            "stdout is a socket whose peer can close early and kill the runner with SIGPIPE; "
            "redirect to a regular file, or explicitly allow the socket with "
            f"{ALLOW_PIPED_STDOUT_ENV}=1"
        )


def _briefs_dir() -> Path:
    """Locate the main checkout's corpus from this interpreter's worktree."""
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(ROOT),
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise DispatchFault(f"could not determine brief corpus: could not run git: {exc}") from exc
    common_dir_text = result.stdout.strip()
    if result.returncode != 0:
        detail = result.stderr.strip() or f"git exited {result.returncode}"
        raise DispatchFault(f"could not determine brief corpus: {detail}")
    if "\n" in common_dir_text or not common_dir_text:
        raise DispatchFault(
            "could not determine brief corpus: git returned no unique common directory"
        )
    common_dir = Path(common_dir_text)
    if not common_dir.is_absolute():
        raise DispatchFault(
            "could not determine brief corpus: git returned a relative common directory "
            f"despite --path-format=absolute: {common_dir_text}"
        )
    if common_dir.name != ".git" or not common_dir.is_dir():
        raise DispatchFault(
            "could not determine brief corpus: git common directory is not a checkout .git "
            f"directory: {common_dir}"
        )
    return common_dir.parent / ".dreamwork" / "docs" / "briefs"


def _read(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise DispatchFault(f"could not read {label} {path}: {exc}") from exc


def _fence_at(text: str, offset: int) -> str | None:
    """Return the Markdown fence enclosing offset, if there is one."""
    active: str | None = None
    for line in text[:offset].splitlines():
        stripped = line.lstrip()
        marker = "```" if stripped.startswith("```") else (
            "~~~" if stripped.startswith("~~~") else None
        )
        if marker is None:
            continue
        if active is None:
            active = marker
        elif active == marker:
            active = None
    return active


def validate_prompt(prompt: str, contract: str, coordinator_inbox: Path) -> None:
    if not prompt:
        raise DispatchFault("prompt is empty; no dispatch was attempted")
    if not contract:
        raise DispatchFault(
            "standing contract file briefs/boilerplate.md is empty; "
            "the assertion examined no rules"
        )

    occurrence = prompt.find(contract)
    if occurrence < 0:
        raise DispatchFault(
            "standing contract from briefs/boilerplate.md is missing or altered; "
            "append that file verbatim to the prompt"
        )
    if prompt.find(contract, occurrence + 1) >= 0:
        raise DispatchFault(
            "standing contract appears more than once; cannot classify which copy "
            "is instruction rather than quoted material"
        )
    if _fence_at(prompt, occurrence) is not None:
        raise DispatchFault(
            "standing contract appears inside a fenced quotation, not as lane instructions"
        )
    if prompt[occurrence + len(contract) :].strip():
        raise DispatchFault(
            "standing contract is not the final prompt section; append "
            "briefs/boilerplate.md verbatim after task-specific text"
        )

    inbox_lines = [
        line for line in prompt[:occurrence].splitlines()
        if line.startswith("Coordinator inbox")
    ]
    expected = f"{COORDINATOR_INBOX_PREFIX}{coordinator_inbox}"
    if inbox_lines != [expected]:
        raise DispatchFault(
            "task-specific head must contain exactly this unambiguous coordinator "
            f"inbox instruction: {expected}"
        )


def _resolve_commit(revision: str, label: str) -> str:
    result = subprocess.run(
        [
            "git", "-C", str(ROOT), "rev-parse", "--verify", "--end-of-options",
            f"{revision}^{{commit}}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    resolved = result.stdout.strip()
    if result.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", resolved):
        detail = result.stderr.strip() or f"git exited {result.returncode}"
        raise DispatchFault(f"{label} {revision!r} does not resolve to a commit: {detail}")
    return resolved


def validate_base_sha(prompt_head: str, branch: str) -> None:
    """Require the named base to resolve to this lane branch's actual branch point."""
    base_lines = [line for line in prompt_head.splitlines() if line.startswith("Base sha:")]
    matches = _BASE_SHA_LINE.findall(prompt_head)
    if not base_lines:
        raise DispatchFault(
            "task-specific head is missing required 'Base sha: <git revision>' line"
        )
    if len(base_lines) != 1 or len(matches) != 1:
        raise DispatchFault(
            "task-specific head must contain exactly one 'Base sha: <git revision>' line; "
            "the revision must be 7-40 lowercase hexadecimal characters"
        )

    stated = _resolve_commit(matches[0], "Base sha")
    branch_commit = _resolve_commit(branch, "Branch")
    result = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "master", branch_commit],
        capture_output=True,
        text=True,
        check=False,
    )
    branch_point = result.stdout.strip()
    if result.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", branch_point):
        detail = result.stderr.strip() or f"git exited {result.returncode}"
        raise DispatchFault(
            f"could not determine branch point of master and {branch!r}: {detail}"
        )
    if stated != branch_point:
        raise DispatchFault(
            f"Base sha {matches[0]!r} resolves to {stated}, but does not match "
            f"branch point {branch_point} of master and {branch!r}"
        )


def _ledger_ids(dreamwork_dir: Path) -> set[int]:
    """Read all durable task ids in one query, without waiting on a lock."""
    store = dreamwork_dir / "ledger.sqlite3"
    if store.is_file():
        try:
            spec = StoreSpec(
                store,
                repositories={"tasks": TaskRepository},
                busy_timeout_ms=0,
            )
            with open_database(spec, access=Access.READ) as database:
                open_ids, landed_ids = database.tasks.ids_by_state()
            return {int(task_id) for task_id in open_ids + landed_ids}
        except DatabaseError as exc:
            raise OSError(f"could not query ledger store {store}: {exc}") from exc

    ledger = dreamwork_dir / "tasks.md"
    try:
        text = ledger.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise OSError(f"could not read ledger {ledger}: {exc}") from exc
    if "## Open" not in text or "## Recently landed" not in text:
        raise OSError(f"ledger {ledger} has no readable task sections")
    return {int(match) for match in _MARKDOWN_TASK.findall(text)}


def primary_task_state(task_id: int, dreamwork_dir: Path) -> str | None:
    """The primary task's state ('open'/'landed'), or None when it cannot be told.

    The one record-vs-head supersession signal a dispatcher can detect without
    reading prose (#1125): if the task a brief targets has already LANDED, the
    record moved past the head's premise of open work, and landing is terminal,
    so the head is stale by construction.  Measured against the live store, every
    broader signal is wallpaper -- a bare-citation-to-landed check fires 71 times
    on a single brief (lesson authority, not live premises), and "the record moved
    since the head was written" fires on 77% of dispatches because the normal task
    lifecycle moves the record constantly.  Neither a head render-timestamp nor a
    note timestamp exists in any rendered record, so a timestamp compare is not
    even computable.  Primary-landed is the rare, unambiguous, detectable case.

    Reads the store only (the source of truth); a markdown-only or unreadable
    store returns None, which the caller treats as fail-safe (#136: present-but-
    unreadable is not a verdict, and a dispatch may never be refused on a probe
    that did not run).  Silent on None: ``ledger_reference_reports`` already
    warns when the store cannot be read, so a second DID-NOT-RUN line is noise.
    """
    store = dreamwork_dir / "ledger.sqlite3"
    if not store.is_file():
        return None
    try:
        spec = StoreSpec(
            store,
            repositories={"tasks": TaskRepository},
            busy_timeout_ms=0,
        )
        with open_database(spec, access=Access.READ) as database:
            open_ids, landed_ids = database.tasks.ids_by_state()
    except Exception:
        return None
    if str(task_id) in landed_ids:
        return "landed"
    if str(task_id) in open_ids:
        return "open"
    return None


def ledger_reference_reports(prompt_head: str, dreamwork_dir: Path) -> list[str]:
    """Classify unresolved ledger references without blocking a dispatch."""
    command_ids = {int(match) for match in _LEDGER_GET.findall(prompt_head)}
    citation_ids = {int(match) for match in _BARE_TASK_CITE.findall(prompt_head)}
    if not command_ids and not citation_ids:
        return []
    try:
        known_ids = _ledger_ids(dreamwork_dir)
    # This advisory is the last step before exec.  Core names supported store
    # failures, but an unknown/malformed schema can still raise outside that
    # ladder; no probe failure is allowed to stop the dispatch route.
    except Exception as exc:
        return [
            "dispatch ledger reference check DID NOT RUN: "
            f"{exc}; launch allowed"
        ]

    reports = [
        "dispatch ledger reference report: "
        f"ledger.py get {task_id} names #{task_id}, which does not exist; "
        "launch allowed because instruction and quotation are not reliably distinguishable"
        for task_id in sorted(command_ids - known_ids)
    ]
    unresolved_cites = citation_ids - known_ids
    if unresolved_cites:
        names = ", ".join(f"#{task_id}" for task_id in sorted(unresolved_cites))
        reports.append(
            "dispatch ledger reference report: unresolved bare citation(s) "
            f"{names}; launch allowed because prose may cite lessons or retired tasks"
        )
    return reports


def _identity(prompt: str) -> tuple[int, str]:
    task = _TASK_HEAD.search(prompt)
    branches = _BRANCH_LINE.findall(prompt)
    if task is None:
        raise DispatchFault(
            "validated prompt has no task id in its first-level heading; "
            "cannot name the brief corpus artifact"
        )
    if len(branches) != 1:
        raise DispatchFault(
            "validated prompt has no unique 'Branch: <lane>' line; "
            "cannot name the brief corpus artifact without risking a collision"
        )
    return int(task.group(1)), branches[0]


def _worktree(prompt_head: str) -> Path:
    matches = _WORKTREE_LINE.findall(prompt_head)
    if len(matches) != 1:
        raise DispatchFault("task-specific head must name exactly one 'Worktree: <path>'")
    worktree = Path(matches[0])
    if not worktree.is_absolute() or not worktree.is_dir():
        raise DispatchFault(f"target worktree is not an existing absolute directory: {worktree}")
    return worktree.resolve()


def _lock_record(path: Path) -> tuple[dict, os.stat_result]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            inode = os.fstat(handle.fileno())
            record = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DispatchFault(f"cannot classify existing lane lock {path}: {exc}") from exc
    required = {"pid", "task", "lane", "brief", "identity"}
    if not isinstance(record, dict) or not required.issubset(record):
        raise DispatchFault(f"cannot classify existing lane lock {path}: missing lane identity")
    return record, inode


def acquire_lane_lock(worktree: Path, task: int, lane: str, prompt_path: Path) -> Path:
    """Atomically claim a worktree, replacing only a proven-stale claim."""
    lock_dir = worktree / ".dreamwork"
    try:
        lock_dir.mkdir(exist_ok=True)
    except OSError as exc:
        raise DispatchFault(f"could not create lane lock directory {lock_dir}: {exc}") from exc
    lock_path = lock_dir / "lane.lock"
    identity = str(worktree / f".{lane}-lane-identity")
    record = {
        "pid": os.getpid(),
        "task": task,
        "lane": lane,
        "brief": str(prompt_path.resolve()),
        "identity": identity,
    }

    while True:
        temp_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=lock_dir,
                    prefix=".lane.lock.", delete=False) as handle:
                temp_name = handle.name
                json.dump(record, handle, sort_keys=True)
                handle.write("\n")
            os.link(temp_name, lock_path)
            return lock_path
        except FileExistsError:
            existing, inode = _lock_record(lock_path)
            try:
                live = pid_matches_lane(existing["pid"], existing["identity"])
            except LivenessUnknown as exc:
                raise DispatchFault(f"cannot determine liveness of lane lock {lock_path}: {exc}") from exc
            if live:
                raise DispatchFault(
                    f"worktree {worktree} already has live lane {existing['lane']!r}: "
                    f"pid {existing['pid']}, task #{existing['task']}, brief {existing['brief']}"
                )
            try:
                current = lock_path.stat()
                if (current.st_dev, current.st_ino) == (inode.st_dev, inode.st_ino):
                    lock_path.unlink()
            except FileNotFoundError:
                pass
            except OSError as exc:
                raise DispatchFault(f"could not retire stale lane lock {lock_path}: {exc}") from exc
        except OSError as exc:
            raise DispatchFault(f"could not acquire lane lock {lock_path}: {exc}") from exc
        finally:
            if temp_name is not None:
                try:
                    Path(temp_name).unlink()
                except FileNotFoundError:
                    pass


def _write_exclusive(path: Path, content: str) -> None:
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except (OSError, UnicodeError) as exc:
        raise DispatchFault(f"could not write {path}: {exc}") from exc


def _supervise_review_runner(
        runner: list[str], prompt: str, runner_log: Path) -> None:
    """Fork the reviewer, tee its output to ``runner_log``, and record its exit.

    Runs in the detached child (session leader, lane lock held, cwd at the
    review worktree) AFTER the parent-child handshake pipe's write end has been
    closed — so the dispatcher's ``_pipe_drain`` has already returned and the
    launch is confirmed detached (#876). The supervisor forks the reviewer as
    a grandchild whose stdout and stderr are replaced by a pipe the supervisor
    reads; the supervisor tees the pipe to ``runner_log``. When the grandchild
    exits the supervisor writes ``_runner_exit_path_for(runner_log)`` — an
    atomic JSON object recording the integer ``runner_exit`` and the log path —
    and then itself exits with the same code.
    """
    read_fd, write_fd = os.pipe()
    grandchild = os.fork()
    if grandchild == 0:
        # Grandchild: replace stdout/stderr with the pipe, then exec the reviewer.
        os.close(read_fd)
        os.dup2(write_fd, 1)
        os.dup2(write_fd, 2)
        os.close(write_fd)
        try:
            os.execvp(runner[0], [*runner, prompt])
        except OSError as exc:
            sys.stderr.write(f"exec {runner[0]!r}: {exc}\n")
            os._exit(127)
        os._exit(127)  # unreachable
    # Supervisor: tee the grandchild's output to runner_log AND this process's
    # own stdout/stderr (so a coordinator-redirected launcher streams it too).
    os.close(write_fd)
    runner_log.parent.mkdir(parents=True, exist_ok=True)
    out_paths = [fd for fd in (1, 2) if _fd_ok(fd)]
    try:
        with runner_log.open("wb", buffering=0) as log:
            while True:
                try:
                    chunk = os.read(read_fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                log.write(chunk)
                for fd in out_paths:
                    try:
                        os.write(fd, chunk)
                    except OSError:
                        pass
    except OSError:
        pass  # the log file itself is the fallback record; review_status names it
    os.close(read_fd)
    _, status = os.waitpid(grandchild, 0)
    runner_exit = os.waitstatus_to_exitcode(status)
    exit_path = _runner_exit_path_for(runner_log)
    _write_runner_exit(exit_path, runner_exit, str(runner_log))
    os._exit(runner_exit)


def _runner_exit_path_for(runner_log: Path) -> Path:
    """Derive the ``.runner.exit.json`` path beside a ``.runner.log`` (#1214)."""
    return runner_log.with_name(runner_log.name[:-len(".runner.log")] + ".runner.exit.json")


def _write_runner_exit(exit_path: Path, runner_exit: int, runner_log: str) -> None:
    """Atomically record the supervisor's observation of the runner's exit.

    Mirrors ``_write_json_atomic``'s rename pattern but is called from the
    supervisor after the fork, so it avoids the fsync-then-tempfile helper
    (which assumes a long-lived parent) and writes the temp file beside the
    target then renames. The integer ``runner_exit`` is the only field a
    consumer needs to decide terminal-vs-unobserved; ``runner_log`` repeats the
    log path so the verdict is recoverable from this record alone.
    """
    try:
        exit_path.parent.mkdir(parents=True, exist_ok=True)
        temp = exit_path.with_name(f".{exit_path.name}.{os.getpid()}.tmp")
        with temp.open("x", encoding="utf-8") as handle:
            json.dump(
                {"runner_exit": runner_exit, "runner_log": runner_log},
                handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, exit_path)
    except OSError:
        # The review ran and its exit was observed; a failure to persist the
        # witness must not invert that. The log file itself is the fallback
        # record, and review_status names both. Drop silently rather than
        # masking the real exit with a different one.
        pass


def _fd_ok(fd: int) -> bool:
    """True when ``fd`` is open and not a pipe/socket (tee target safety)."""
    try:
        mode = os.fstat(fd).st_mode
    except OSError:
        return False
    return not (stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode))


def _launch_detached(
        worktree: Path, task: int, lane: str, prompt_path: Path,
        runner: list[str], prompt: str, *, cwd: Path | None = None,
        child_env: dict[str, str] | None = None,
        runner_log: Path | None = None) -> int:
    """Fork, setsid, acquire the lane lock, and exec the runner (#876).

    All validation has already run in the parent; this is the LAST step. The
    child becomes a new session leader (``setsid``) so anything that reaps the
    launching process — the harness's background-command bookkeeping — cannot
    reach the lane. That is the mechanism that killed six lanes in one sweep on
    2026-08-01: ``os.execvp`` replaced the launcher WITH the runner, so the
    harness-tracked background command WAS the lane.

    The lane lock is acquired IN THE CHILD so its recorded pid is the runner's,
    not the dispatcher's — the dispatcher exits immediately, and a lock holding
    a dead pid would let a second dispatch through (#869, #876). A close-on-exec
    pipe confirms every child-side step succeeded before the parent exits 0:
    without it, a lock refusal or exec failure would read as a silent launch.

    When ``runner_log`` is given (the review path, #1214) the child does not
    exec directly: it becomes a SUPERVISOR (``_supervise_review_runner``) that
    forks the runner as a grandchild, captures its stdout+stderr to
    ``runner_log``, and observes its exit. The lock therefore records the
    supervisor's pid, which is live exactly while the review runs; the #876
    detach invariant is unchanged (the grandchild survives the dispatcher's
    exit inside the supervisor's session).
    """
    read_fd, write_fd = os.pipe()
    os.set_inheritable(read_fd, False)
    os.set_inheritable(write_fd, False)
    pid = os.fork()
    if pid == 0:
        # Child: new session leader, then claim the worktree, then become the runner.
        os.close(read_fd)
        try:
            os.setsid()
        except OSError as exc:
            _pipe_write(write_fd, f"setsid: {exc}\n")
            os._exit(126)
        if cwd is not None:
            try:
                os.chdir(cwd)
            except OSError as exc:
                _pipe_write(write_fd, f"cwd {cwd}: {exc}\n")
                os._exit(126)
        if child_env:
            os.environ.update(child_env)
        try:
            acquire_lane_lock(worktree, task, lane, prompt_path)
        except DispatchFault as exc:
            _pipe_write(write_fd, f"{exc}\n")
            os._exit(2)
        if runner_log is not None:
            # Review path (#1214): capture the runner rather than exec'ing it
            # directly. The supervisor forks the real reviewer as a grandchild,
            # tees its stdout+stderr to runner_log, waits, and writes the exit
            # to runner_exit_path before itself exiting. The dispatcher never
            # observes a byte of this; the launcher exit is still 0 at the
            # parent-close, so #876's detach invariant is unchanged.
            #
            # The supervisor does NOT exec, so the close-on-exec that closed
            # this pipe's write end in the work-lane path never fires. Close
            # it explicitly: every setup step that could fail (setsid, cwd,
            # lock) has succeeded, so the parent's _pipe_drain may proceed and
            # confirm the launch. A grandchild exec failure is caught by the
            # spawn-time liveness probe, not by this pipe — same safety net.
            os.close(write_fd)
            _supervise_review_runner(runner, prompt, runner_log.resolve())
            os._exit(0)  # unreachable; _supervise… exits
        try:
            os.execvp(runner[0], [*runner, prompt])
        except OSError as exc:
            _pipe_write(write_fd, f"exec {runner[0]!r}: {exc}\n")
            os._exit(127)
        os._exit(127)  # unreachable; exec replaced us or raised
    # Parent: confirm the child launched, then exit. The child is detached and
    # survives this exit — that is the whole point (#876).
    os.close(write_fd)
    failure = _pipe_drain(read_fd)
    os.close(read_fd)
    if failure:
        os.waitpid(pid, 0)
        print(f"dispatch refused: {failure}", file=sys.stderr)
        return 2
    return 0


def _review_runner(runner: list[str]) -> list[str]:
    """Accept only the read-only reviewer recipe, never a write-capable mode."""
    if runner and runner[0] == "--":
        runner = runner[1:]
    executable = Path(runner[0]).name if runner else ""
    if executable != "ccc" or runner[1:] != [
            "--permission-mode", "plan", "@cx-reviewer"]:
        raise DispatchFault(
            "review launch requires ccc --permission-mode plan @cx-reviewer; "
            "reviewers read and report, so extra controls and write-capable "
            "permission modes are refused"
        )
    return runner


def _review_lane_name(branch: str, round_num: int) -> str:
    return f"{branch}-review-r{round_num}"


def _git_result(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=False
        )
    except OSError as exc:
        raise DispatchFault(f"could not run git {' '.join(args)}: {exc}") from exc


def _registered_branch_worktree(root: Path, branch: str) -> tuple[Path | None, bool]:
    """Return branch's registered worktree and whether its block is detached."""
    result = _git_result(root, "worktree", "list", "--porcelain")
    if result.returncode:
        raise DispatchFault(
            "could not inspect registered worktrees: "
            + (result.stderr.strip() or f"git exited {result.returncode}")
        )
    for block in result.stdout.strip().split("\n\n"):
        lines = block.splitlines()
        path_line = next((line for line in lines if line.startswith("worktree ")), None)
        branch_line = f"branch refs/heads/{branch}"
        if branch_line in lines:
            return (Path(path_line.removeprefix("worktree ")).resolve()
                    if path_line else None, "detached" in lines)
    return None, False


def _write_json_atomic(path: Path, record: dict[str, object], *, create: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(record, indent=2, sort_keys=True) + "\n"
    if create:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        return
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def launch_review(prompt_path: Path, branch: str, round_num: int,
                  runner: list[str]) -> int:
    """Persist, attach, record, and launch one read-only review attempt."""
    try:
        runner = _review_runner(runner)
        validate_stdout()
        if not branch or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", branch):
            raise DispatchFault(
                "--review-branch <name> is required and must be one safe path component"
            )
        if round_num < 1:
            raise DispatchFault("--review-round must be a positive integer")
        prompt = _read(prompt_path, "review prompt")
        review_frame = _read(REVIEW_FRAME_PATH, "review frame")
        coordinator_root = _coordinator_root()
        pinned_sha = _resolve_pinned_sha(branch, coordinator_root)
        if pinned_sha is None:
            raise DispatchFault(
                f"could not resolve branch {branch!r} to a commit; a review worktree "
                "cannot be created without the exact pinned sha"
            )
        prompt = _inject_pinned_sha(prompt, review_frame, pinned_sha)
        persisted = persist_review_prompt(
            prompt, branch, round_num, review_frame=review_frame, pinned_sha=pinned_sha
        )
        review_lane = _review_lane_name(branch, round_num)
        worktree = worktree_roots(coordinator_root.resolve())[0] / review_lane
        existing, detached = _registered_branch_worktree(coordinator_root, review_lane)
        if existing is not None or detached:
            raise DispatchFault(
                f"review branch {review_lane} already has registered worktree "
                f"{existing}; choose the next --review-round rather than reusing an attempt"
            )
        branch_ref = _git_result(
            coordinator_root, "show-ref", "--verify", f"refs/heads/{review_lane}"
        )
        if branch_ref.returncode == 0:
            raise DispatchFault(
                f"review branch {review_lane} already exists; choose the next "
                "--review-round rather than detaching or moving it"
            )
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        attempt_id = f"{review_lane}-{digest[:16]}"
        attempt_path = persisted.with_name(
            persisted.name[:-len(".prompt.md")] + ".launch.json"
        )
        # #1214: the runner's output is captured beside the dispatch artifacts
        # so a completed review's verdict is recoverable from the record alone.
        # The supervisor (_supervise_review_runner) tees to this path; the
        # sibling .runner.exit.json carries the observed exit.
        runner_log = persisted.with_name(
            persisted.name[:-len(".prompt.md")] + ".runner.log"
        )
        record: dict[str, object] = {
            "attempt_id": attempt_id,
            "branch": branch,
            "round": round_num,
            "review_lane": review_lane,
            "pinned_sha": pinned_sha,
            "prompt_sha256": digest,
            "prompt_bytes": len(prompt.encode("utf-8")),
            "prompt": str(persisted.resolve()),
            "worktree": str(worktree.resolve()),
            "permission_mode": "plan",
            "state": "prepared; reviewer not attempted",
            "runner_exit": None,
            "runner_log": str(runner_log.resolve()),
            "runs": 0,
        }
        _write_json_atomic(attempt_path, record, create=True)
        worktree.parent.mkdir(parents=True, exist_ok=True)
        added = _git_result(
            coordinator_root, "worktree", "add", "-q", "-b", review_lane,
            str(worktree), pinned_sha,
        )
        registered, detached = _registered_branch_worktree(coordinator_root, review_lane)
        if (added.returncode != 0 or registered != worktree.resolve() or detached):
            record["state"] = "worktree creation refused: attached branch not verified"
            _write_json_atomic(attempt_path, record)
            detail = added.stderr.strip() or f"git exited {added.returncode}"
            raise DispatchFault(
                f"attached review worktree creation failed: {detail}; registered="
                f"{registered}; detached={detached}"
            )
        record["state"] = "unverified attempt: reviewer result not yet observed"
        record["runs"] = 1
        _write_json_atomic(attempt_path, record)
        result = _launch_detached(
            worktree, 0, review_lane, persisted, runner, prompt,
            cwd=worktree,
            child_env={LANE_ROLE_ENV: "reviewer", LANE_ID_ENV: secrets.token_hex(16)},
            runner_log=runner_log.resolve(),
        )
        if result == 0:
            settle = float(os.environ.get("REVIEW_RUNNER_SETTLE", "0.3"))
            if settle > 0:
                time.sleep(settle)
            # The runner is a grandchild of the dispatcher (#1214 supervisor),
            # so a single probe can race the fork/exec under load. Probe a few
            # times with short sleeps: the first succeeds when the runner is
            # ready, retries cover the launch window. A real reviewer runs for
            # minutes, so production hits on the first probe.
            probes = int(os.environ.get("REVIEW_RUNNER_PROBES", "10"))
            present = False
            examined = 0
            for _ in range(max(1, probes)):
                present, examined, _ = _review_lane_live(review_lane, coordinator_root)
                if present:
                    break
                time.sleep(0.05)
            if not present:
                record["state"] = (
                    "spawn failed: dispatcher exit=0 but no reviewer runner "
                    "holds the review worktree cwd"
                )
                _write_json_atomic(attempt_path, record)
                print(
                    "review launch refused: dispatcher exited 0 but no reviewer "
                    f"runner holds {worktree.resolve()} as cwd; examined={examined}",
                    file=sys.stderr,
                )
                return 3
            record["state"] = (
                "spawned: reviewer present in review worktree (cwd-containment); "
                "runner exit observed on completion via .runner.exit.json"
            )
            _write_json_atomic(attempt_path, record)
            print(
                f"review launched: branch={branch}; review_lane={review_lane}; "
                f"worktree={worktree.resolve()}; attempt={attempt_id}; "
                f"permission_mode=plan; cwd-containment examined={examined}; "
                f"runner_log={runner_log.resolve()}; "
                "runner exit observed on completion via .runner.exit.json"
            )
        else:
            record["state"] = f"launch refused: dispatcher exited {result}"
            _write_json_atomic(attempt_path, record)
        return result
    except (DispatchFault, OSError) as exc:
        print(f"review launch refused: {exc}", file=sys.stderr)
        return 2


def _pipe_write(fd: int, message: str) -> None:
    try:
        os.write(fd, message.encode("utf-8", "replace"))
    except OSError:
        pass


def _pipe_drain(fd: int) -> str:
    chunks = bytearray()
    while True:
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        chunks.extend(chunk)
    return chunks.decode("utf-8", "replace").strip()


def _verify_pair(brief: Path, receipt: Path) -> None:
    if not brief.is_file():
        raise DispatchFault(
            f"integrity receipt {receipt.name} exists but brief artifact "
            f"{brief.name} is absent"
        )
    if not receipt.is_file():
        raise DispatchFault(
            f"brief artifact {brief.name} has no dispatch-time integrity receipt "
            f"{receipt.name}"
        )
    recorded = _read(receipt, "integrity receipt")
    match = _RECEIPT.fullmatch(recorded)
    if match is None or match.group(2) != brief.name:
        raise DispatchFault(
            f"integrity receipt {receipt.name} is unclassifiable; expected "
            "'<sha256>  <brief-name>.md'"
        )
    try:
        actual = hashlib.sha256(brief.read_bytes()).hexdigest()
    except OSError as exc:
        raise DispatchFault(f"could not read brief artifact {brief}: {exc}") from exc
    if actual != match.group(1):
        raise DispatchFault(
            f"brief artifact {brief.name} changed after dispatch-time persistence "
            f"(recorded {match.group(1)}, found {actual})"
        )


def persist_prompt(prompt: str, briefs_dir: Path | None = None) -> Path:
    """Write the exact validated prompt and a dispatch-time hash receipt."""
    if briefs_dir is None:
        briefs_dir = _briefs_dir()
    task, lane = _identity(prompt)
    brief = briefs_dir / f"{task}-{lane}.md"
    receipt = brief.with_suffix(".sha256")
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    expected_receipt = f"{digest}  {brief.name}\n"

    try:
        briefs_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DispatchFault(f"could not create brief corpus {briefs_dir}: {exc}") from exc

    if brief.exists() or receipt.exists():
        _verify_pair(brief, receipt)
        if _read(brief, "brief artifact") != prompt:
            raise DispatchFault(
                f"brief corpus name {brief.name} already belongs to another dispatch"
            )
        return brief

    _write_exclusive(brief, prompt)
    try:
        _write_exclusive(receipt, expected_receipt)
        _verify_pair(brief, receipt)
    except DispatchFault:
        for path in (brief, receipt):
            try:
                path.unlink()
            except OSError:
                pass
        raise
    return brief


# --- Review dispatch: liveness + sha pin (#1056) ---------------------------
#
# A review dispatched against a still-working lane freezes a mid-flight commit
# and reports fixed findings as unfixed: the lane commits throughout its work
# (that is the point of small increments), so commit presence carries no
# information about completion.  Two halves, both named in the filing:
#
# 1. PROCESS ABSENCE, not commit presence.  Before persisting a review, scan
#    for a live RUNNER process whose cwd is inside the branch's worktree.  This
#    WARNS rather than refuses — a genuinely hung lane must still be reviewable,
#    and a refuse with no escape hatch gets worked around (worse than a warning,
#    #1056 Direction 2).  The sha pin below is the always-on backstop, so a
#    coordinator that proceeds past the warn still leaves staleness discoverable.
#    Reads /proc/<pid>/cwd NEVER argv: a ccc runner's argv embeds the whole
#    brief, so any argv search for a path matches the lane itself (#729 trap,
#    bitten four times this session).  Reuses lane_liveness's classifier
#    (_is_lane_runner, _ancestor_pids, read_proc_cwd) so this cannot diverge
#    from the lock/cwd channels; #1113 relocates that logic but re-exports the
#    old names, so importing from lane_liveness works either way.
# 2. PIN THE SHA.  Capture git rev-parse <branch> at dispatch, inject it into
#    the prompt head, and record it in the receipt.  Then a mid-flight commit
#    produces a VISIBLE mismatch (the reviewer states the sha it reviewed; the
#    receipt records what was pinned) instead of a silently stale verdict.
#    Liveness can race; a sha mismatch is discovered every time, after the fact.


def _coordinator_root() -> Path:
    """The main checkout root (parent of its .dreamwork dir)."""
    return _briefs_dir().parent.parent.parent


def _worktrees_for_branch(branch: str, coordinator_root: Path) -> tuple[Path, ...]:
    """Canonical worktree paths for ``branch`` under both worktree roots.

    A path that does not exist is still returned: a reaped worktree has no live
    runner, so the scan examines it and finds nothing (#136 — no lane / lane
    live / lane finished are distinct, and "worktree exists" collapses them).
    """
    roots = worktree_roots(coordinator_root.resolve())
    return tuple(root / branch for root in roots)


def _resolve_pinned_sha(branch: str, coordinator_root: Path) -> str | None:
    """``git rev-parse <branch>`` at dispatch; None if it cannot be resolved.

    A review from a different machine, or of a branch not present in this
    checkout, resolves nothing — the pin is best-effort and the caller warns
    that the backstop is absent for that dispatch rather than refusing.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(coordinator_root), "rev-parse", "--verify", branch],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha if re.fullmatch(r"[0-9a-f]{7,40}", sha) else None


_PINNED_SHA_LINE = (
    "Review sha (pinned at dispatch, #1056): {sha} — "
    "review THIS commit; state the sha you actually reviewed in your verdict, "
    "and report (do not silently resolve) any mismatch with the branch tip.\n\n"
)


def _inject_pinned_sha(prompt: str, review_frame: str, sha: str | None) -> str:
    """Insert the pinned-sha line into the prompt head, before the review frame.

    The review frame must remain the final prompt section (validate_review_prompt
    enforces that), so the line is inserted immediately before it, never after.
    Returns the prompt unchanged when there is no sha or no frame to anchor to.
    """
    if not sha:
        return prompt
    idx = prompt.find(review_frame)
    if idx < 0:
        return prompt
    return prompt[:idx] + _PINNED_SHA_LINE.format(sha=sha) + prompt[idx:]


def _review_lane_live(
        branch: str, coordinator_root: Path, *,
        process_entries: list[str] | None = None,
        read_cwd=None, read_cmdline=None, skip_pids: set[int] | None = None,
) -> tuple[bool, int, tuple[Path, ...]]:
    """Whether a live lane runner's cwd is inside ``branch``'s worktree (#1056).

    Process absence, not commit presence.  A live runner is a known RUNNER
    process (ccc/claude/grok/codex via lane_liveness._is_lane_runner) holding a
    worktree as its cwd — the same notion the lock/cwd channels use, reused so
    this cannot diverge.  Reads /proc/<pid>/cwd (never argv); excludes self and
    ancestors (lane_liveness._ancestor_pids, #729); returns the count of
    processes examined so "probed nothing" cannot read as "found none" (#868).

    Returns ``(live, examined, worktrees)``: live is True only when a
    non-ancestor runner's cwd is inside one of the branch's worktree paths.
    A liveness check cannot prove a lane is *done*, only that no runner is
    present (#651) — the caller words its message as the latter.
    """
    candidates = _worktrees_for_branch(branch, coordinator_root)
    cand = tuple(str(p) for p in candidates)
    try:
        entries = process_entries if process_entries is not None else os.listdir("/proc")
    except OSError as exc:
        raise DispatchFault(
            f"could not scan for a live review lane: cannot enumerate /proc: {exc}"
        ) from exc
    pids = [int(entry) for entry in entries if entry.isdigit()]
    cwd_reader = read_cwd or lane_liveness.read_proc_cwd
    cmd_reader = read_cmdline or (lambda pid: Path("/proc/%d/cmdline" % pid).read_bytes())
    skip = skip_pids if skip_pids is not None else lane_liveness._ancestor_pids()
    examined = 0
    for pid in pids:
        if pid in skip:
            continue
        examined += 1
        cwd = cwd_reader(pid)
        if cwd is None or cwd.endswith(" (deleted)"):
            continue
        if not any(cwd == c or cwd.startswith(c + os.sep) for c in cand):
            continue
        try:
            if lane_liveness._is_lane_runner(cmd_reader(pid)):
                return True, examined, candidates
        except OSError:
            continue
    return False, examined, candidates


# --- #1207: consume runner_exit=null so a dead review is not "still thinking" -
#
# launch_review records "runner_exit": null and "spawned: ... runner exit not
# observed", and nothing ever changes them — the detached runner's exit is
# genuinely never observed (#1093).  That null is honest and must NOT be
# fabricated (#1177).  The defect is that NOTHING CONSUMES it: a review whose
# runner died producing nothing reads identically to one still thinking (both
# show the null state, a clean worktree, and "(no review decisions)").
#
# The consumer re-probes the SAME cwd-containment channel launch_review trusted
# at spawn.  A live runner still holding the worktree is "in-progress" (still
# thinking — benign); a runner that is GONE while runner_exit is still null is
# "runner-absent" — the dispatch recorded no outcome and the review is no longer
# progressing.  That is the readable alarm the durable record could not express.
# It does NOT fire on a legitimately slow review (the runner is present) and it
# does NOT require the coordinator to remember a step (it is a read-only probe).
# See #1207's IGC grid: a pure timer false-positives under load, a launcher wait
# serialises dispatch, and a reviewer-written terminal marker still needs
# liveness to tell slow from dead — liveness is the necessary core either way.

_REVIEW_CATEGORY_IN_PROGRESS = "in-progress"
_REVIEW_CATEGORY_RUNNER_ABSENT = "runner-absent"
_REVIEW_CATEGORY_UNKNOWN = "unknown"
_REVIEW_CATEGORY_TERMINAL = "terminal"


def _read_runner_exit(record: dict) -> dict | None:
    """Read the supervisor's ``.runner.exit.json`` for a review dispatch (#1214).

    Returns the parsed ``{"runner_exit", "runner_log"}`` object when the file
    exists and parses as a dict carrying an integer ``runner_exit``; otherwise
    ``None``. A missing or unreadable record is the honest "not observed" case
    — it must NOT be promoted to a success, so this helper returns None and the
    caller falls through to the liveness probe (which keeps ``runner-absent``
    as the unobserved alarm).
    """
    runner_log = record.get("runner_log")
    if not isinstance(runner_log, str) or not runner_log:
        return None
    exit_path = _runner_exit_path_for(Path(runner_log))
    try:
        parsed = json.loads(exit_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if (not isinstance(parsed, dict)
            or not isinstance(parsed.get("runner_exit"), int)):
        return None
    log = parsed.get("runner_log")
    if not isinstance(log, str) or not log:
        log = runner_log
    return {"runner_exit": parsed["runner_exit"], "runner_log": log}


def classify_review_dispatch(
        record: dict, coordinator_root: Path, *,
        process_entries: list[str] | None = None,
        read_cwd=None, read_cmdline=None, skip_pids: set[int] | None = None,
) -> tuple[str, str]:
    """Make a review dispatch's ``runner_exit: null`` readable (#1207).

    Returns ``(category, detail)``:

    * ``in-progress`` — a live runner still holds the review worktree; the
      review is still thinking.  Benign: this MUST NOT fire for a slow review.
    * ``runner-absent`` — ``runner_exit`` is null AND no live runner holds the
      worktree.  The dispatch recorded no outcome and the runner that was
      present at spawn is gone; this is the alarm a dead review now expresses.
    * ``unknown`` — the probe examined 0 processes (#868): no verdict on
      whether a runner is present, never an all-clear.
    * ``terminal`` — ``runner_exit`` was observed (non-null); not the defect.

    Read-only: it never writes ``runner_exit`` or any state.  The launcher's
    null is honest (#1177); this consumes it rather than corrupting it.
    Resolves ``/proc/<pid>/cwd`` (never argv) via ``_review_lane_live``, so the
    #729 self-match trap does not apply.

    #1214: before the liveness probe, it first reads the supervisor's
    ``.runner.exit.json`` (whose path is the launch record's ``runner_log``
    with its suffix swapped).  A present, well-formed exit record is an
    OBSERVED outcome and returns ``terminal`` naming the runner log the verdict
    is recoverable from — converting incident A (a finished review read as
    absent) into a direct pointer.  A missing or unreadable exit record falls
    through to the liveness probe, so an unobserved outcome stays unobserved
    (``runner-absent``) rather than being silently promoted to success.
    """
    runner_exit = record.get("runner_exit")
    observed = _read_runner_exit(record)
    if observed is not None:
        return (_REVIEW_CATEGORY_TERMINAL,
                f"runner exit observed ({observed['runner_exit']}) via "
                f".runner.exit.json; verdict recoverable from "
                f"{observed['runner_log']}")
    if runner_exit is not None:
        return (_REVIEW_CATEGORY_TERMINAL,
                f"runner_exit observed ({runner_exit}); state: {record.get('state', '?')}")
    review_lane = record.get("review_lane")
    if not review_lane:
        return (_REVIEW_CATEGORY_UNKNOWN,
                "record carries no review_lane; cannot probe liveness")
    try:
        live, examined, _ = _review_lane_live(
            review_lane, coordinator_root,
            process_entries=process_entries, read_cwd=read_cwd,
            read_cmdline=read_cmdline, skip_pids=skip_pids,
        )
    except (DispatchFault, OSError) as exc:
        return (_REVIEW_CATEGORY_UNKNOWN,
                f"liveness probe did not run: {exc}; no verdict (#868)")
    if examined == 0:
        return (_REVIEW_CATEGORY_UNKNOWN,
                "liveness probe examined 0 processes; no verdict on runner "
                "presence (#868) — not an all-clear")
    if live:
        return (_REVIEW_CATEGORY_IN_PROGRESS,
                f"reviewer runner present in {review_lane} worktree; review "
                "still in progress")
    return (_REVIEW_CATEGORY_RUNNER_ABSENT,
            f"runner gone from {review_lane} worktree; runner_exit never "
            "observed; the dispatch recorded no outcome — the review is no "
            "longer progressing (a dead review, or one whose verdict landed "
            "elsewhere; check inbox/ledger reviews)")


def review_status() -> int:
    """Print the liveness classification of every launched review (#1207).

    Scans ``review-dispatches/*.launch.json`` (the launch witness, not the
    persist-only ``.json`` receipt) and classifies each via
    ``classify_review_dispatch``.  A review whose runner is gone while
    ``runner_exit`` is still null is the alarm this loop could not previously
    express; it is printed so a dead review no longer reads as benign.

    Only the ``.launch.json`` files carry ``runner_exit``; a review persisted
    with ``--review-prompt`` but never launched has no ``.launch.json`` and is
    not in scope here.
    """
    coordinator_root = _coordinator_root()
    dispatches_dir = _briefs_dir().parent.parent / "review-dispatches"
    launches = sorted(dispatches_dir.glob("*.launch.json")) if dispatches_dir.is_dir() else []
    if not launches:
        print("review status: no launched review dispatches found")
        return 0
    counts: dict[str, int] = {}
    lines: list[str] = []
    for path in launches:
        record = None
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            category, detail = _REVIEW_CATEGORY_UNKNOWN, f"unreadable launch record: {exc}"
        else:
            if not isinstance(parsed, dict):
                category, detail = (
                    _REVIEW_CATEGORY_UNKNOWN,
                    f"launch record is valid JSON but not an object "
                    f"({type(parsed).__name__}); cannot classify",
                )
            else:
                record = parsed
                category, detail = classify_review_dispatch(record, coordinator_root)
        counts[category] = counts.get(category, 0) + 1
        attempt_id = record.get("attempt_id", path.stem) if isinstance(record, dict) else path.stem
        branch = record.get("branch", "?") if isinstance(record, dict) else "?"
        round_num = record.get("round", "?") if isinstance(record, dict) else "?"
        lines.append(f"{attempt_id}  {category}  {branch} r{round_num}  — {detail}")
    summary = ", ".join(f"{counts[k]} {k}" for k in sorted(counts))
    print(f"review status: classified {len(launches)} dispatch(es): {summary}")
    for line in lines:
        print(line)
    return 0


# --- Review dispatch persistence (#1112) -----------------------------------
#
# Lane dispatches are bound at three points: brief.py emits frame.md,
# validate_prompt requires boilerplate.md, and persist_prompt writes a receipt.
# Review dispatches had none of it — the coordinator hand-wrote each prompt and
# concatenated briefs/review-frame.md by convention (#1109 measured this).  The
# functions below mirror the lane path so the review frame is bound by
# construction and a guard can read the receipt.
#
# Receipts live in .dreamwork/review-dispatches/ — a SIBLING of launch-attempts/,
# not a discriminated kind within it.  check_brief_dispatch_coverage scans
# launch-attempts/ and assumes every JSON record there carries the lane keys
# (task_id, lane, prompt_sha256); adding review records to that directory would
# silently break that scan.  Location discrimination is also what keeps the lint
# check from reporting lane receipts as review prompts missing the frame.


def validate_review_prompt(prompt: str, review_frame: str) -> None:
    """Require briefs/review-frame.md verbatim, once, unfenced, as final section.

    Mirrors ``validate_prompt`` for lanes: the frame must occur exactly once,
    outside any fenced quotation, and nothing may follow it.  A frame inside a
    code fence is quoted material, not instruction; a frame that is not last
    leaves room for task-specific text to override it silently.
    """
    if not prompt:
        raise DispatchFault("review prompt is empty; no dispatch was attempted")
    if not review_frame:
        raise DispatchFault(
            "review frame file briefs/review-frame.md is empty; "
            "the assertion examined no rules"
        )
    occurrence = prompt.find(review_frame)
    if occurrence < 0:
        raise DispatchFault(
            "review frame from briefs/review-frame.md is missing or altered; "
            "append that file verbatim to the review prompt"
        )
    if prompt.find(review_frame, occurrence + 1) >= 0:
        raise DispatchFault(
            "review frame appears more than once; cannot classify which copy "
            "is instruction rather than quoted material"
        )
    if _fence_at(prompt, occurrence) is not None:
        raise DispatchFault(
            "review frame appears inside a fenced quotation, not as review instructions"
        )
    if prompt[occurrence + len(review_frame):].strip():
        raise DispatchFault(
            "review frame is not the final prompt section; append "
            "briefs/review-frame.md verbatim after task-specific review text"
        )


def persist_review_prompt(
    prompt: str, branch: str, round_num: int, *,
    review_frame: str | None = None,
    dispatches_dir: Path | None = None,
    pinned_sha: str | None = None,
) -> Path:
    """Write a validated review dispatch prompt and its JSON receipt (#1112).

    Returns the path of the persisted ``.prompt.md``.  The companion ``.json``
    carries branch, round, the prompt digest, the frame digest, and the
    pinned review sha (#1056) so a guard can verify the frame that was
    validated at persistence time and compare the pinned sha to the sha a
    reviewer later states it reviewed.

    Idempotent: re-persisting the identical prompt for the same branch/round is
    a no-op (returns the existing path); a byte mismatch is a refusal.
    """
    if review_frame is None:
        review_frame = _read(REVIEW_FRAME_PATH, "review frame")
    validate_review_prompt(prompt, review_frame)
    if dispatches_dir is None:
        dreamwork_dir = _briefs_dir().parent.parent
        dispatches_dir = dreamwork_dir / "review-dispatches"
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    stem = f"{branch}-r{round_num}-{digest[:16]}"
    prompt_path = dispatches_dir / f"{stem}.prompt.md"
    receipt_path = dispatches_dir / f"{stem}.json"
    record = {
        "branch": branch,
        "round": round_num,
        "prompt_sha256": digest,
        "prompt_bytes": len(prompt.encode("utf-8")),
        "frame_sha256": hashlib.sha256(review_frame.encode("utf-8")).hexdigest(),
        "pinned_sha": pinned_sha,
    }
    try:
        dispatches_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DispatchFault(
            f"could not create review dispatch directory {dispatches_dir}: {exc}"
        ) from exc
    if prompt_path.exists():
        existing = _read(prompt_path, "review dispatch prompt")
        if existing != prompt:
            raise DispatchFault(
                f"review dispatch name {prompt_path.name} already belongs to another dispatch"
            )
        return prompt_path
    _write_exclusive(prompt_path, prompt)
    try:
        _write_exclusive(receipt_path, json.dumps(record, indent=2, sort_keys=True) + "\n")
    except DispatchFault:
        for path in (prompt_path, receipt_path):
            try:
                path.unlink()
            except OSError:
                pass
        raise
    return prompt_path


def verify_pending(briefs_dir: Path | None = None) -> int:
    """Verify every governed brief/receipt pair before the merge-gate commit."""
    if briefs_dir is None:
        briefs_dir = _briefs_dir()
    governed = {
        path for path in briefs_dir.glob("*.md")
        if (match := re.match(r"(\d+)", path.name))
        and int(match.group(1)) >= INTEGRITY_START_TASK
    }
    receipts = set(briefs_dir.glob("*.sha256"))
    governed.update(
        brief for receipt in receipts
        if (brief := receipt.with_suffix(".md")).is_file()
    )
    if not governed and not receipts:
        raise DispatchFault(
            "DID NOT VERIFY: no governed brief artifacts or integrity receipts were found"
        )

    faults: list[str] = []
    for brief in sorted(governed):
        try:
            _verify_pair(brief, brief.with_suffix(".sha256"))
        except DispatchFault as exc:
            faults.append(str(exc))
    for receipt in sorted(receipts):
        brief = receipt.with_suffix(".md")
        if not brief.is_file():
            faults.append(
                f"integrity receipt {receipt.name} has no brief artifact "
                f"{brief.name}"
            )
    if faults:
        raise DispatchFault("; ".join(faults))
    return len(governed)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="validate, record, and dispatch a lane prompt, or verify its record"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prompt", type=Path)
    mode.add_argument("--verify-pending", action="store_true")
    mode.add_argument("--review-prompt", type=Path,
                      help="validate and persist a review dispatch prompt (#1112)")
    mode.add_argument(
        "--launch-review", type=Path,
        help="create an attached review branch/worktree, record the attempt, "
             "and launch a plan-mode reviewer (#1163)")
    mode.add_argument(
        "--review-status", action="store_true",
        help="classify every launched review dispatch by re-probing runner "
             "liveness, so a runner that died producing nothing is reported "
             "runner-absent instead of reading as benign (#1207)")
    parser.add_argument(
        "--prepare",
        action="store_true",
        help="validate and persist --prompt without requiring its not-yet-created branch",
    )
    parser.add_argument("--review-branch",
                        help="branch under review (review modes only)")
    parser.add_argument("--review-round", type=int, default=1,
                        help="review round number (review modes only, default 1)")
    parser.add_argument("runner", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.verify_pending:
        if args.runner:
            print("brief integrity check refused: runner is invalid in verify mode", file=sys.stderr)
            return 2
        try:
            count = verify_pending()
        except DispatchFault as exc:
            print(f"brief integrity check failed: {exc}", file=sys.stderr)
            return 2
        print(f"brief integrity verified: {count} governed brief(s) matched receipts")
        return 0

    if args.launch_review:
        return launch_review(
            args.launch_review, args.review_branch, args.review_round, args.runner
        )

    if args.review_status:
        if args.runner:
            print("review status refused: runner is invalid in review-status mode",
                  file=sys.stderr)
            return 2
        return review_status()

    if args.review_prompt:
        if args.runner:
            print("review dispatch refused: runner is invalid in review-prompt mode", file=sys.stderr)
            return 2
        branch = args.review_branch
        if not branch or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", branch):
            print(
                "review dispatch refused: --review-branch <name> is required "
                "and must be one safe path component",
                file=sys.stderr,
            )
            return 2
        try:
            prompt = _read(args.review_prompt, "review prompt")
            review_frame = _read(REVIEW_FRAME_PATH, "review frame")
            coordinator_root = _coordinator_root()
            # #1056: pin the review to an explicit sha and check the lane is
            # finished by process absence, not commit presence.  A lane commits
            # throughout its work, so commit presence carries no information
            # about completion; a review dispatched mid-flight freezes a
            # mid-flight commit and reports fixed findings as unfixed.
            pinned_sha = _resolve_pinned_sha(branch, coordinator_root)
            if pinned_sha is None:
                print(
                    f"review dispatch warning: could not resolve sha for branch "
                    f"{branch}; the pinned-sha backstop is ABSENT for this "
                    f"dispatch — a mid-flight commit would not be detectable (#1056)",
                    file=sys.stderr,
                )
            prompt = _inject_pinned_sha(prompt, review_frame, pinned_sha)
            live, examined, worktrees = _review_lane_live(
                branch, coordinator_root)
            if live:
                present = ", ".join(str(p) for p in worktrees if p.is_dir()) or str(worktrees[0])
                print(
                    f"review dispatch warning: a live lane runner is present in "
                    f"{present} (branch {branch}); the lane may still be "
                    f"committing — examined {examined} process(es), #1056. "
                    f"Dispatch proceeds (warn, not refuse): the pinned sha is "
                    f"the backstop. Re-dispatch once the lane exits for a clean verdict.",
                    file=sys.stderr,
                )
            elif examined == 0:
                print(
                    f"review dispatch warning: liveness scan examined 0 "
                    f"processes for branch {branch} — NO VERDICT on whether a "
                    f"lane is live (#868); the pinned sha is the backstop (#1056)",
                    file=sys.stderr,
                )
            persist_review_prompt(prompt, branch, args.review_round,
                                  review_frame=review_frame, pinned_sha=pinned_sha)
        except DispatchFault as exc:
            print(f"review dispatch refused: {exc}", file=sys.stderr)
            return 2
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        print(
            f"review dispatch persisted: branch={branch}; round={args.review_round}; "
            f"digest={digest}; pinned_sha={pinned_sha}; "
            f"exact prompt bytes preserved"
        )
        return 0

    runner = args.runner
    if runner and runner[0] == "--":
        runner = runner[1:]
    if not runner and not args.prepare:
        print("dispatch refused: runner command is missing", file=sys.stderr)
        return 2

    try:
        if not args.prepare:
            validate_stdout()
        prompt = _read(args.prompt, "prompt")
        contract = _read(CONTRACT_PATH, "standing contract")
        briefs_dir = _briefs_dir()
        coordinator_inbox = briefs_dir.parent.parent / "inbox.md"
        validate_prompt(prompt, contract, coordinator_inbox)
        prompt_head = prompt[:prompt.find(contract)]
        task, branch = _identity(prompt)
        worktree = _worktree(prompt_head)
        if not args.prepare:
            validate_base_sha(prompt_head, branch)
        for report in ledger_reference_reports(prompt_head, briefs_dir.parent.parent):
            print(report, file=sys.stderr)
        # #1125: the one head-vs-record supersession signal a dispatcher can
        # detect.  Landing is terminal, so a brief for a LANDED task is stale by
        # construction -- the record moved past its premise of open work.  This
        # is the contradicted state worth blocking on (#136); open and unreadable
        # both proceed, the latter silently because ledger_reference_reports
        # already names a store that could not be read.
        state = primary_task_state(task, briefs_dir.parent.parent)
        if state == "landed":
            raise DispatchFault(
                f"task #{task} is LANDED; this dispatch targets already-resolved "
                f"work. The record moved past this head's premise of open work, "
                f"and landing is terminal, so the head is stale by construction. "
                f"This names the task's STATE, not the head's full claims (#651): "
                f"a landed record does not prove every sentence in the head wrong, "
                f"only that the task it targets is done. Re-read "
                f"`ledger.py get {task}` and, if follow-up is genuinely needed, "
                f"file it as a new task rather than re-dispatching the resolved one."
            )
        try:
            persist_prompt(prompt, briefs_dir)
        except DispatchFault as exc:
            raise DispatchFault(f"could not persist validated brief: {exc}") from exc
    except DispatchFault as exc:
        print(f"dispatch refused: {exc}", file=sys.stderr)
        return 2

    if args.prepare:
        print("dispatch prepared: exact validated brief and digest persisted; runner not attempted")
        return 0

    try:
        # Fresh per dispatch, then stable because the detached child inherits
        # it across exec. Never reuse a coordinator's own lane identity.
        os.environ[LANE_ID_ENV] = secrets.token_hex(16)
        return _launch_detached(worktree, task, branch, args.prompt, runner, prompt)
    except OSError as exc:
        print(f"dispatch refused: could not launch detached runner {runner[0]!r}: {exc}",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
