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
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dreamwork_db import Access, DatabaseError, StoreSpec, open_database  # noqa: E402
from dreamwork_db.tasks import TaskRepository  # noqa: E402
from lane_liveness import LivenessUnknown, pid_matches_lane  # noqa: E402


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


def _launch_detached(
        worktree: Path, task: int, lane: str, prompt_path: Path,
        runner: list[str], prompt: str) -> int:
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
        try:
            acquire_lane_lock(worktree, task, lane, prompt_path)
        except DispatchFault as exc:
            _pipe_write(write_fd, f"{exc}\n")
            os._exit(2)
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
) -> Path:
    """Write a validated review dispatch prompt and its JSON receipt (#1112).

    Returns the path of the persisted ``.prompt.md``.  The companion ``.json``
    carries branch, round, the prompt digest, and the frame digest so a guard
    can verify the frame that was validated at persistence time.

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
    parser.add_argument(
        "--prepare",
        action="store_true",
        help="validate and persist --prompt without requiring its not-yet-created branch",
    )
    parser.add_argument("--review-branch",
                        help="branch under review (review-prompt mode only)")
    parser.add_argument("--review-round", type=int, default=1,
                        help="review round number (review-prompt mode only, default 1)")
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
            persist_review_prompt(prompt, branch, args.review_round,
                                  review_frame=review_frame)
        except DispatchFault as exc:
            print(f"review dispatch refused: {exc}", file=sys.stderr)
            return 2
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        print(
            f"review dispatch persisted: branch={branch}; round={args.review_round}; "
            f"digest={digest}; exact prompt bytes preserved"
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
