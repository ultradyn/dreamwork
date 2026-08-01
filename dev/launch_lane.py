#!/usr/bin/env python3
"""Turn one human-authored brief head into a checked, supervised lane launch."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Sequence


LANE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
ATTEMPT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
TASK_HEAD_RE = re.compile(r"^#(?:\s+Task)?\s+#?(\d+)\b", re.MULTILINE)
BRANCH_RE = re.compile(r"^Branch:\s+(\S+)\s*$", re.MULTILINE)
BASE_RE = re.compile(r"^Base sha:\s+([0-9a-f]{40})\s*$", re.MULTILINE)
INBOX_PREFIX = (
    "Coordinator inbox — ABSOLUTE path, append your completion summary here "
    "when you finish: "
)


class LaunchFault(Exception):
    pass


def _run(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True)


def _relay(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", *args], repo)


def _git_text(repo: Path, *args: str) -> str | None:
    result = _git(repo, *args)
    if result.returncode:
        return None
    return result.stdout.strip()


def _worktrees(repo: Path) -> dict[str, Path] | None:
    result = _git(repo, "worktree", "list", "--porcelain")
    if result.returncode:
        return None
    found: dict[str, Path] = {}
    path: Path | None = None
    branch: str | None = None
    for line in [*result.stdout.splitlines(), ""]:
        if not line:
            if path is not None and branch is not None:
                found[branch.removeprefix("refs/heads/")] = path
            path = branch = None
        else:
            key, _, value = line.partition(" ")
            if key == "worktree":
                path = Path(value).resolve()
            elif key == "branch":
                branch = value
    return found


def _foreground_state() -> bool | None:
    """True means provably foreground; None means there is no observable tty."""
    for fd in (sys.stdin.fileno(), sys.stdout.fileno(), sys.stderr.fileno()):
        try:
            if os.isatty(fd):
                return os.tcgetpgrp(fd) == os.getpgrp()
        except (OSError, ValueError):
            continue
    return None


def _stdout_fault() -> str | None:
    if os.environ.get("DREAMWORK_ALLOW_PIPED_STDOUT") == "1":
        return None
    try:
        mode = os.fstat(sys.stdout.fileno()).st_mode
    except (OSError, ValueError) as exc:
        return f"could not classify stdout: {exc}"
    if stat.S_ISFIFO(mode):
        return (
            "stdout is a pipe whose reader can close early and kill the runner with SIGPIPE; "
            "redirect to a regular file, or explicitly allow the pipe with "
            "DREAMWORK_ALLOW_PIPED_STDOUT=1"
        )
    if stat.S_ISSOCK(mode):
        return (
            "stdout is a socket whose peer can close early and kill the runner with SIGPIPE; "
            "redirect to a regular file, or explicitly allow the socket with "
            "DREAMWORK_ALLOW_PIPED_STDOUT=1"
        )
    return None


def _refuse(phase: str, reasons: Sequence[str], examined: str, retained: str) -> int:
    print(f"REFUSE phase={phase}: {len(reasons)} violation(s)", file=sys.stderr)
    for reason in reasons:
        print(f"- {reason}", file=sys.stderr)
    print(f"examined: {examined}", file=sys.stderr)
    print(f"retained: {retained}", file=sys.stderr)
    print("deliberately did not perform: governed runner launch", file=sys.stderr)
    return 1


def _main_checkout(repo: Path) -> Path:
    common = _git_text(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common:
        raise LaunchFault("could not resolve the repository common directory")
    path = Path(common).resolve()
    if path.name != ".git":
        raise LaunchFault(f"git common directory is not a checkout .git directory: {path}")
    return path.parent


def _assemble(head: str, task: int, lane: str, base_sha: str, lane_path: Path,
              inbox: Path, contract: str) -> str:
    metadata = (
        f"Worktree: {lane_path}\n"
        f"Branch: {lane}\n"
        f"Base sha: {base_sha}\n"
        f"{INBOX_PREFIX}{inbox}\n"
    )
    return f"{head.rstrip()}\n\n{metadata}\n{contract}"


def _fence_at(text: str, offset: int) -> str | None:
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


def _brief_faults(prompt: str, head: str, contract: str, task: int, lane: str,
                  base_sha: str, inbox: Path) -> list[str]:
    faults: list[str] = []
    task_heads = TASK_HEAD_RE.findall(prompt)
    branches = BRANCH_RE.findall(prompt)
    bases = BASE_RE.findall(prompt)
    inbox_lines = [line for line in prompt.splitlines() if line.startswith("Coordinator inbox")]
    expected_inbox = f"{INBOX_PREFIX}{inbox}"
    if task_heads != [str(task)]:
        faults.append(f"final brief must contain one first-level task heading for #{task}; found {task_heads!r}")
    if branches != [lane]:
        faults.append(f"final brief must contain one bare 'Branch: {lane}' line; found {branches!r}")
    if bases != [base_sha]:
        faults.append(f"final brief must contain one bare 'Base sha: {base_sha}' line; found {bases!r}")
    if inbox_lines != [expected_inbox]:
        faults.append(f"final brief must contain exactly this coordinator inbox line: {expected_inbox}")
    occurrence = prompt.find(contract) if contract else -1
    if not contract:
        faults.append("briefs/boilerplate.md is empty; no standing rules were examined")
    elif occurrence < 0 or prompt.find(contract, occurrence + 1) >= 0:
        faults.append("canonical boilerplate must occur exactly once")
    elif _fence_at(prompt, occurrence) is not None:
        faults.append("canonical boilerplate is inside a fenced quotation, not lane instructions")
    elif prompt[occurrence + len(contract):].strip():
        faults.append("canonical boilerplate must be the final brief section")
    human_lines = head.splitlines()
    substance_lines = [
        line for line in (human_lines[1:] if human_lines else [])
        if not line.startswith(("Branch:", "Base sha:", "Worktree:", "Coordinator inbox"))
    ]
    substance = "\n".join(substance_lines).strip()
    if len(re.findall(r"[A-Za-z0-9]+", substance)) < 3:
        faults.append(
            "human-authored head has no substantive task content after its heading "
            f"(examined {len(substance.encode('utf-8'))} UTF-8 byte(s))"
        )
    return faults


def _record_path(main: Path, attempt_id: str) -> Path:
    return main / ".dreamwork" / "launch-attempts" / f"{attempt_id}.json"


def _write_record(path: Path, record: dict[str, object], *, create: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(record, indent=2, sort_keys=True) + "\n"
    if create:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        return
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _read_record(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LaunchFault(f"could not read attempt record {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LaunchFault(f"attempt record {path} is not a JSON object")
    return value


def _reap(repo: Path, lane_path: Path) -> subprocess.CompletedProcess[str]:
    return _run([sys.executable, str(Path(__file__).with_name("reap.py")), str(lane_path)], repo)


def _abort_created(repo: Path, lane_path: Path, lane: str, phase: str, reason: str,
                   examined: str, attempt_id: str) -> int:
    """Retire only the worktree created by this invocation, through reap.py."""
    cleanup = _reap(repo, lane_path)
    _relay(cleanup)
    worktrees = _worktrees(repo) or {}
    retained = (
        f"attempt={attempt_id} preserved; worktree="
        f"{worktrees.get(lane, 'none')}; "
        "branch retained"
    )
    reasons = [reason, f"dev/reap.py cleanup exited {cleanup.returncode}"]
    return _refuse(phase, reasons, examined, retained)


def launch(task: int, lane: str, agent: str, head_path: Path, runner_args: Sequence[str],
           *, resume: str | None = None) -> int:
    repo_text = _git_text(Path.cwd(), "rev-parse", "--show-toplevel")
    if not repo_text:
        return _refuse("selection", ["current directory is not a git checkout"],
                       f"cwd={Path.cwd()}", "worktree=none; branch=none")
    repo = Path(repo_text).resolve()
    try:
        main = _main_checkout(repo)
    except LaunchFault as exc:
        return _refuse("selection", [str(exc)], f"repo={repo}", "worktree=none; branch=none")
    base_sha = _git_text(main, "rev-parse", "--verify", "master^{commit}")
    current = _git_text(main, "branch", "--show-current")
    lane_path = main / ".worktrees" / lane
    inbox = main / ".dreamwork" / "inbox.md"
    retained = "worktree=none; branch=none"

    selection: list[str] = []
    if task <= 0:
        selection.append("task id must be a positive integer")
    if not LANE_RE.fullmatch(lane) or lane in {".", ".."}:
        selection.append("lane must be one safe branch/path component")
    if not agent.startswith("@") or len(agent) < 2:
        selection.append("agent must be supplied explicitly as an @alias")
    if not base_sha or current != "master":
        selection.append(f"main checkout must have local master checked out; current={current or 'UNKNOWN'}")
    try:
        head = head_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        selection.append(f"could not read human-authored head {head_path}: {exc}")
        head = ""
    contract_path = repo / "briefs" / "boilerplate.md"
    try:
        contract = contract_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        selection.append(f"could not read canonical boilerplate {contract_path}: {exc}")
        contract = ""
    if selection:
        return _refuse("selection", selection, f"task={task}; lane={lane}; agent={agent}; base={base_sha or 'UNKNOWN'}", retained)

    stdout_fault = _stdout_fault()
    if stdout_fault:
        return _refuse("output-safety", [stdout_fault], "stdout file type", retained)

    foreground = _foreground_state()
    if foreground is True:
        return _refuse(
            "background-check",
            ["launch-lane is running in the foreground; rerun it with stdout/stderr redirected to a regular file and '&'"],
            "controlling tty foreground process group", retained,
        )
    if foreground is None:
        print("background-check: no controlling tty was observable; launch-lane cannot prove shell job placement")

    prompt = _assemble(head, task, lane, base_sha, lane_path, inbox, contract)
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    faults = _brief_faults(prompt, head, contract, task, lane, base_sha, inbox)
    if faults:
        return _refuse("brief-validation", faults,
                       f"exact final brief digest={digest}; head={head_path}; UTF-8 bytes={len(prompt.encode('utf-8'))}", retained)

    attempt_id = f"{task}-{lane}-{digest[:16]}"
    attempt_path = _record_path(main, resume or attempt_id)
    worktrees = _worktrees(main)
    if worktrees is None:
        return _refuse("worktree-preflight", ["git worktree list could not be read"],
                       f"base={base_sha}; attempt={attempt_id}", retained)

    if resume:
        if not ATTEMPT_RE.fullmatch(resume):
            return _refuse("resume", ["attempt id must be one safe filename component"],
                           f"resume={resume!r}; digest={digest}", retained)
        try:
            record = _read_record(attempt_path)
        except LaunchFault as exc:
            return _refuse("resume", [str(exc)], f"resume={resume}; digest={digest}", retained)
        recorded_digest = record.get("prompt_sha256")
        if recorded_digest != digest:
            return _refuse(
                "resume",
                [f"identical-digest retry required: attempt {resume} records {recorded_digest}, final brief is {digest}"],
                f"attempt={resume}; exact final brief bytes={len(prompt.encode('utf-8'))}",
                f"worktree={worktrees.get(lane, 'not registered')}; branch={lane if lane in worktrees else 'unknown'}; attempt record preserved",
            )
        if worktrees.get(lane) != lane_path.resolve():
            return _refuse("resume", ["recorded lane has no matching registered worktree"],
                           f"attempt={resume}; registered={worktrees.get(lane)}; expected={lane_path.resolve()}",
                           "attempt record preserved; no worktree created")
        attempt_id = resume
        retained = f"worktree={lane_path.resolve()}; branch={lane}; attempt={attempt_id} preserved"
    else:
        collisions: list[str] = []
        if lane in worktrees:
            collisions.append(f"branch {lane} already has registered worktree {worktrees[lane]}; use --resume ATTEMPT_ID only for an identical-digest retry")
        if _git_text(main, "show-ref", "--verify", f"refs/heads/{lane}"):
            collisions.append(f"branch {lane} already exists; use --resume ATTEMPT_ID only for an identical-digest retry")
        if attempt_path.exists():
            collisions.append(f"attempt {attempt_id} already exists; use --resume {attempt_id}")
        if collisions:
            return _refuse("worktree-preflight", collisions, f"git worktree list entries={len(worktrees)}; digest={digest}", retained)
        record = {
            "attempt_id": attempt_id, "task_id": task, "lane": lane, "agent": agent,
            "base_sha": base_sha, "prompt_sha256": digest, "prompt_bytes": len(prompt.encode("utf-8")),
            "head": str(head_path.resolve()), "worktree": str(lane_path.resolve()),
            "state": "prepared; runner not attempted", "runner_exit": None, "runs": 0,
        }
        try:
            _write_record(attempt_path, record, create=True)
        except OSError as exc:
            return _refuse("attempt-persistence", [f"could not persist attempt record: {exc}"],
                           f"attempt={attempt_id}; digest={digest}; path={attempt_path}", retained)
        added = _git(main, "worktree", "add", str(lane_path), "-b", lane, base_sha)
        _relay(added)
        registered = _worktrees(main) or {}
        if added.returncode or registered.get(lane) != lane_path.resolve():
            reasons = [f"git worktree add exited {added.returncode}"]
            if registered.get(lane) == lane_path.resolve():
                cleanup = _reap(main, lane_path)
                _relay(cleanup)
                reasons.append(f"partial worktree cleanup via dev/reap.py exited {cleanup.returncode}")
                registered = _worktrees(main) or {}
            record["state"] = "worktree creation refused"
            _write_record(attempt_path, record)
            retained = f"attempt={attempt_id} preserved; registered worktree={registered.get(lane, 'none')}; branch={lane if _git_text(main, 'show-ref', '--verify', f'refs/heads/{lane}') else 'none'}"
            return _refuse("worktree-creation", reasons,
                           f"git worktree list entries={len(registered)}; expected={lane_path.resolve()}", retained)
        retained = f"worktree={lane_path.resolve()}; branch={lane}; attempt={attempt_id} preserved"

    created_here = not bool(resume)

    prompt_path = attempt_path.with_suffix(".prompt.md")
    try:
        if prompt_path.exists():
            existing = prompt_path.read_text(encoding="utf-8")
            if existing != prompt:
                raise LaunchFault("preserved attempt prompt bytes do not match the final brief")
        else:
            with prompt_path.open("x", encoding="utf-8") as handle:
                handle.write(prompt)
                handle.flush()
                os.fsync(handle.fileno())
    except (OSError, UnicodeError, LaunchFault) as exc:
        if created_here:
            return _abort_created(main, lane_path, lane, "attempt-persistence", str(exc),
                                  f"attempt={attempt_id}; digest={digest}", attempt_id)
        return _refuse("attempt-persistence", [str(exc)], f"attempt={attempt_id}; digest={digest}", retained)

    prepared = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("dispatch_lane.py")),
         "--prompt", str(prompt_path), "--prepare"],
        cwd=repo,
    )
    if prepared.returncode:
        if created_here:
            return _abort_created(
                main, lane_path, lane, "governed-prepare",
                f"existing dispatcher validation/persistence exited {prepared.returncode}",
                f"attempt={attempt_id}; digest={digest}; exact final brief={prompt_path}", attempt_id,
            )
        return _refuse(
            "governed-prepare",
            [f"existing dispatcher validation/persistence exited {prepared.returncode}"],
            f"attempt={attempt_id}; digest={digest}; exact final brief={prompt_path}", retained,
        )

    policy = main / ".dreamwork" / "subagent-policy"
    if policy.is_file():
        try:
            policy_text = policy.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(f"subagent policy report unavailable (agent argument unchanged): {exc}")
        else:
            print("subagent policy (reported, not selected):")
            print(policy_text, end="")
    print(f"attempt: {attempt_id}; base={base_sha}; digest={digest}; worktree={lane_path.resolve()}")

    try:
        record = _read_record(attempt_path)
    except LaunchFault as exc:
        if created_here:
            return _abort_created(main, lane_path, lane, "attempt-persistence", str(exc),
                                  f"attempt={attempt_id}; digest={digest}", attempt_id)
        return _refuse("attempt-persistence", [str(exc)],
                       f"attempt={attempt_id}; digest={digest}", retained)
    record["state"] = "unverified attempt: runner result not yet observed; exact brief bytes preserved; resume requires identical digest"
    record["runs"] = int(record.get("runs", 0)) + 1
    record["runner_exit"] = None
    try:
        _write_record(attempt_path, record)
    except OSError as exc:
        if created_here:
            return _abort_created(
                main, lane_path, lane, "attempt-persistence",
                f"could not mark attempt unverified before launch: {exc}",
                f"attempt={attempt_id}; digest={digest}", attempt_id,
            )
        return _refuse("attempt-persistence", [f"could not mark attempt unverified before launch: {exc}"],
                       f"attempt={attempt_id}; digest={digest}", retained)

    command = [sys.executable, str(Path(__file__).with_name("dispatch_lane.py")),
               "--prompt", str(prompt_path), "--", "ccc", *runner_args, agent]
    # Inherit the launcher's regular-file stdout/stderr. Capturing here would
    # manufacture the pipe hazard that dispatch_lane correctly refuses.
    result = subprocess.run(command, cwd=repo)
    record["runner_exit"] = result.returncode
    if result.returncode == 0:
        record["state"] = "runner result verified: exit 0"
        try:
            _write_record(attempt_path, record)
        except OSError as exc:
            print(
                f"UNVERIFIED ATTEMPT: attempt={attempt_id}; runner returned 0 but its result "
                f"could not be persisted: {exc}; exact brief bytes are preserved and only "
                f"--resume {attempt_id} with the identical digest is allowed",
                file=sys.stderr,
            )
            return 2
        print(f"runner result: attempt={attempt_id}; exit=0; verified launch completion")
        return 0
    record["state"] = f"runner result verified: exit {result.returncode}; worktree and exact brief retained"
    try:
        _write_record(attempt_path, record)
    except OSError as exc:
        print(
            f"UNVERIFIED ATTEMPT: attempt={attempt_id}; runner returned {result.returncode} "
            f"but its result could not be persisted: {exc}; exact brief bytes are preserved "
            f"and only --resume {attempt_id} with the identical digest is allowed",
            file=sys.stderr,
        )
        return 2
    print(f"REFUSE phase=runner-result: runner exited {result.returncode}; this is not a successful launch", file=sys.stderr)
    print(f"retained: {retained}; exact brief digest={digest}", file=sys.stderr)
    print(f"retry: --resume {attempt_id} is accepted only with the identical digest", file=sys.stderr)
    print("deliberately did not perform: worktree retirement or corpus identity deletion", file=sys.stderr)
    return result.returncode or 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create, record, and supervise one governed lane launch")
    parser.add_argument("task", type=int)
    parser.add_argument("lane")
    parser.add_argument("agent")
    parser.add_argument("head", type=Path)
    parser.add_argument("--resume", metavar="ATTEMPT_ID")
    args, runner_args = parser.parse_known_args(argv)
    return launch(args.task, args.lane, args.agent, args.head, runner_args, resume=args.resume)


if __name__ == "__main__":
    raise SystemExit(main())
