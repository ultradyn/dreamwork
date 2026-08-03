#!/usr/bin/env python3
"""Turn one human-authored brief core into a checked, supervised lane launch."""

from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
from typing import Sequence

# Direct script execution puts dev/ rather than the repo root on sys.path.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from worktree_paths import lane_worktree_path  # noqa: E402

from brief import BriefFault, build as build_brief, substantive_lines  # noqa: E402


LANE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
ATTEMPT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
TASK_HEAD_RE = re.compile(r"^# [^\n]*?#(\d+)\b", re.MULTILINE)
BRANCH_RE = re.compile(r"^Branch:\s+(\S+)\s*$", re.MULTILINE)
BASE_RE = re.compile(r"^Base sha:\s+([0-9a-f]{40})\s*$", re.MULTILINE)
OWNS_RE = re.compile(r"^Lane-owns:\s+(.+?)\s*$", re.MULTILINE)
INBOX_PREFIX = (
    "Coordinator inbox — ABSOLUTE path, append your completion summary here "
    "when you finish: "
)
NATIVE_INHERITED_SANDBOX_AGENTS = frozenset({"@opus5"})

# #1117: after dispatch confirms the runner exec'd, a short settle hedges the
# window before the detached child's /proc/<pid>/cwd is observable. The cwd is
# set at exec (which dispatch waited for), so this covers only kernel bookkeeping
# latency — too short and a healthy runner reads as dead; too long and every
# dispatch pays. 0.3s is a cheap hedge; LAUNCH_RUNNER_SETTLE overrides it (tests
# use 0, since a fake runner's cwd is set at fork).
_RUNNER_SETTLE_SECONDS = 0.3


class LaunchFault(Exception):
    pass


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        return exc.errno != errno.ESRCH
    return True


def _gate_in_flight(main: Path) -> tuple[bool, str]:
    """Return whether the main-owned gate breadcrumb blocks dispatch."""
    path = main / ".dreamwork" / "gate-in-flight.json"
    if not path.is_file():
        return False, f"breadcrumb={path}; state=absent"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        pid = int(record.get("pid", 0))
        phase = str(record.get("phase", ""))
        scratch = str(record.get("gate_worktree", ""))
    except (OSError, UnicodeError, ValueError, TypeError):
        return True, f"breadcrumb={path}; state=unreadable"
    state = "LIVE" if _pid_alive(pid) else "DEAD"
    return True, (
        f"breadcrumb={path}; state={state}; pid={pid}; phase={phase or 'UNKNOWN'}; "
        f"gate_worktree={scratch or 'UNKNOWN'}"
    )


def _try_repo_state_lock(main: Path):
    path = main / ".git" / "dreamwork-repo-state.lock"
    handle = path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


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


def _native_reach_fault(agent: str, coordinator_root: Path, worktree: Path) -> str | None:
    """Refuse known native aliases whose inherited sandbox excludes the lane."""
    if agent not in NATIVE_INHERITED_SANDBOX_AGENTS:
        return None
    # The sandbox contract is expressed in caller-visible path names.  abspath
    # normalizes ``..`` and trailing slashes without changing symlink identity.
    root = Path(os.path.abspath(coordinator_root))
    target = Path(os.path.abspath(worktree))
    if target.is_relative_to(root):
        return None
    return (
        f"native agent {agent} inherits the coordinator sandbox rooted at {root}, but "
        f"worktree {target} is outside that root; use @glm52 or @cx-coder, which receive "
        f"their own lane sandbox, or extend the native sandbox to include {target.parent}; "
        "interpreter availability was not checked"
    )


def _lane_runner_present(lane_path: Path) -> tuple[bool, int]:
    """Whether a known lane-runner process holds ``lane_path`` as its cwd.

    #1117: dispatch confirms a runner exec'd, but a runner that exec'd and died
    one millisecond later is indistinguishable from a healthy one on the
    dispatcher's exit-0 alone. The spawn lands in ``cwd=lane_path`` (#1093), so a
    live runner's ``/proc/<pid>/cwd`` IS the lane worktree. This reads
    ``/proc/<pid>/cwd`` only — NEVER argv: a ``ccc`` runner's argv embeds the
    entire brief, so any argv path search matches the lane's own command line
    (four separate tools hit that trap in one session). A process is classified
    as a runner via ``lane_liveness._is_lane_runner`` (argv[0] basename, the
    notion #1084 landed — reused, not re-derived), and self/ancestors are
    excluded via ``lane_liveness._ancestor_pids`` (#729: a probe that counts its
    own process tree always succeeds).

    Returns ``(present, examined)``. ``examined`` is the count of live cwds the
    probe read, so "examined 0" (#868: a probe that examined nothing) cannot read
    as "examined everything and found none". A hit proves a runner PROCESS exists
    in the worktree; it cannot prove useful lane work (#651).
    """
    # Lazy import: lane_liveness lives at the repo root (on sys.path via the
    # launcher's REPO_ROOT insert, or PYTHONPATH for subprocess tests). It is
    # NOT edited here — #1113 owns that seam; this reuses it (#1084).
    from lane_liveness import _ancestor_pids, _is_lane_runner, read_proc_cwd

    lane = str(lane_path.resolve())
    ancestors = _ancestor_pids()
    examined = 0
    try:
        entries = os.listdir("/proc")
    except OSError:
        return False, 0
    for entry in entries:
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid in ancestors:
            continue
        cwd = read_proc_cwd(pid)
        if cwd is None:
            continue
        examined += 1
        if cwd.endswith(" (deleted)"):
            continue
        if not (cwd == lane or cwd.startswith(lane + os.sep)):
            continue
        try:
            raw = Path("/proc/%d/cmdline" % pid).read_bytes()
        except OSError:
            continue
        if _is_lane_runner(raw):
            return True, examined
    return False, examined


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


def _core_and_owns(head: str, task: int) -> tuple[str, list[str]]:
    """Strip the human envelope; ``brief.py`` owns every generated field."""
    headings = TASK_HEAD_RE.findall(head)
    if headings != [str(task)]:
        raise LaunchFault(
            f"human-authored input must contain one first-level task heading for "
            f"#{task}; found {headings!r}"
        )
    matches = OWNS_RE.findall(head)
    if len(matches) != 1:
        raise LaunchFault(
            "human-authored input must contain exactly one bare `Lane-owns:` line; "
            f"found {len(matches)}"
        )
    owns = [part.strip().strip("`") for part in matches[0].split(",")
            if part.strip().strip("`")]
    if not owns:
        raise LaunchFault("human-authored `Lane-owns:` line names no paths")
    lines = head.splitlines()
    core = "\n".join(
        line for index, line in enumerate(lines)
        if index != 0 and not OWNS_RE.fullmatch(line)
    ).strip()
    return core, owns


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


def _brief_faults(prompt: str, core: str, contract: str, task: int, lane: str,
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
    substance = core.strip()
    if len(re.findall(r"[A-Za-z0-9]+", substance)) < 3:
        faults.append(
            "human-authored core has no substantive task content "
            f"(examined {len(substance.encode('utf-8'))} UTF-8 byte(s))"
        )
    # The word-count bar above passes on a placeholder: `TODO: describe the
    # defect` is four words (#881, measured against this function).  A brief
    # whose whole core is a fill-in dispatches a lane that looks briefed and is
    # not, so require at least one line that is neither blank, nor a heading,
    # nor fill-in.  Line-shaped on purpose — a SENTENCE mentioning TODO is a
    # sentence, and the only such lines in 40 real brief heads were prose.
    elif not substantive_lines(substance):
        faults.append(
            "human-authored core is entirely placeholder — every "
            f"line of the {len(substance.encode('utf-8'))} UTF-8 byte(s) examined is "
            "blank, a bare heading, or a fill-in (TODO, <describe …>, [fill in])"
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
           *, resume: str | None = None, base: str | None = None) -> int:
    repo_text = _git_text(Path.cwd(), "rev-parse", "--show-toplevel")
    if not repo_text:
        return _refuse("selection", ["current directory is not a git checkout"],
                       f"cwd={Path.cwd()}", "worktree=none; branch=none")
    repo = Path(repo_text).resolve()
    try:
        main = _main_checkout(repo)
    except LaunchFault as exc:
        return _refuse("selection", [str(exc)], f"repo={repo}", "worktree=none; branch=none")
    # #1151: a round-2+ lane continues an existing ref, not master. ``base`` is
    # the explicit ref to continue (a branch, tag, or sha); ``None`` keeps the
    # historical "base on master" behaviour. The ref is resolved to a sha ONCE
    # and that sha is what the worktree is created on AND what the record states,
    # so the recorded ``base_sha`` is the commit the worktree is really on — not
    # master's sha, which was true for one second and then false for the round.
    # A ref that does not resolve is REFUSED, never silently based on master:
    # that indistinguishable-from-success failure is the prose workaround's
    # whole hazard, reproduced inside the tool would be no gain.
    base_ref = base or "master"
    base_sha = _git_text(main, "rev-parse", "--verify", f"{base_ref}^{{commit}}")
    current = _git_text(main, "branch", "--show-current")
    lane_path = lane_worktree_path(main, lane)
    inbox = main / ".dreamwork" / "inbox.md"
    retained = "worktree=none; branch=none"

    gate_blocks, gate_detail = _gate_in_flight(main)
    if gate_blocks:
        return _refuse(
            "gate-in-flight",
            [
                "dispatch remains refused for the whole live gate interval; "
                "the shared brief corpus is still the gate lint subject"
            ],
            gate_detail,
            retained,
        )

    selection: list[str] = []
    if task <= 0:
        selection.append("task id must be a positive integer")
    if not LANE_RE.fullmatch(lane) or lane in {".", ".."}:
        selection.append("lane must be one safe branch/path component")
    if not agent.startswith("@") or len(agent) < 2:
        selection.append("agent must be supplied explicitly as an @alias")
    if current != "master":
        selection.append(f"main checkout must have local master checked out; current={current or 'UNKNOWN'}")
    if not base_sha:
        if base is None:
            selection.append(f"main checkout has no resolvable {base_ref}^{{commit}}")
        else:
            selection.append(
                f"--base {base!r} did not resolve to a commit in {main}; refusing "
                "rather than creating a lane on a ref the launcher could not verify "
                "(a typo must refuse, not silently base on master)"
            )
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

    reach_fault = _native_reach_fault(agent, repo, lane_path)
    if reach_fault:
        return _refuse(
            "agent-worktree-reach", [reach_fault],
            f"agent={agent}; check=abspath containment; coordinator root={os.path.abspath(repo)}; "
            f"worktree={os.path.abspath(lane_path)}; interpreter availability not checked",
            retained,
        )
    if agent in NATIVE_INHERITED_SANDBOX_AGENTS:
        print(
            f"agent-worktree reach: verified check=abspath containment; agent={agent}; "
            "unchecked=interpreter availability, actual lane work"
        )
    else:
        print(
            f"agent-worktree reach: agent={agent} is not in the measured native-inherited registry; "
            "worktree reach was not checked; unchecked=interpreter availability, actual lane work"
        )

    try:
        core, owns = _core_and_owns(head, task)
        prompt = build_brief(
            task, lane, owns, core,
            ledger=main / ".dreamwork" / "tasks.md",
            frame_path=repo / "briefs" / "frame.md",
            boilerplate_path=contract_path,
            prepared_worktree=lane_path,
            prepared_base_sha=base_sha,
            prepared_checkout=main,
        )
    except (BriefFault, LaunchFault) as exc:
        return _refuse(
            "brief-generation", [str(exc)],
            f"task={task}; lane={lane}; authored input={head_path}", retained,
        )
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    faults = _brief_faults(prompt, core, contract, task, lane, base_sha, inbox)
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
        repo_state_lock = _try_repo_state_lock(main)
        if repo_state_lock is None:
            return _refuse(
                "worktree-preflight",
                ["repository-state mutex is busy; a gate may be selecting or advancing master"],
                f"base={base_sha}; lock={main / '.git' / 'dreamwork-repo-state.lock'}",
                retained,
            )
        locked_base = _git_text(main, "rev-parse", "--verify", f"{base_ref}^{{commit}}")
        locked_current = _git_text(main, "branch", "--show-current")
        gate_blocks, gate_detail = _gate_in_flight(main)
        if locked_base != base_sha or locked_current != "master" or gate_blocks:
            repo_state_lock.close()
            reasons = []
            if locked_base != base_sha:
                reasons.append(
                    f"base ref {base_ref} moved from selected {base_sha} to {locked_base or 'UNREADABLE'}"
                )
            if locked_current != "master":
                reasons.append(f"main checkout moved to {locked_current or 'DETACHED'}")
            if gate_blocks:
                reasons.append("a gate breadcrumb appeared before worktree creation")
            return _refuse(
                "worktree-preflight", reasons,
                f"selected-base={base_sha}; locked-base={locked_base or 'UNREADABLE'}; {gate_detail}",
                retained,
            )
        record = {
            "attempt_id": attempt_id, "task_id": task, "lane": lane, "agent": agent,
            "base_sha": base_sha, "base_ref": base_ref,
            "prompt_sha256": digest, "prompt_bytes": len(prompt.encode("utf-8")),
            "head": str(head_path.resolve()), "worktree": str(lane_path.resolve()),
            "state": "prepared; runner not attempted", "runner_exit": None, "runs": 0,
        }
        try:
            _write_record(attempt_path, record, create=True)
        except OSError as exc:
            repo_state_lock.close()
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
            repo_state_lock.close()
            retained = f"attempt={attempt_id} preserved; registered worktree={registered.get(lane, 'none')}; branch={lane if _git_text(main, 'show-ref', '--verify', f'refs/heads/{lane}') else 'none'}"
            return _refuse("worktree-creation", reasons,
                           f"git worktree list entries={len(registered)}; expected={lane_path.resolve()}", retained)
        repo_state_lock.close()
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

    # The runner is detached by dispatch_lane.py (fork/setsid/execvp): the
    # dispatcher returns 0 once the child confirms exec, NOT when the runner
    # exits. So the dispatcher's exit code is the LAUNCH status, and the
    # runner's own exit is never observed here. Recording dispatch's 0 as
    # "runner result verified: exit 0" minted a green-faced lie one second
    # after spawn (#1093). Spawn the dispatcher in the lane's worktree so the
    # detached runner inherits that worktree as its cwd — a brief that says
    # "work in a clone" does not move the process, and /proc/<pid>/cwd is where
    # a process was launched, not where its brief points it (#1093).
    if not lane_path.is_dir():
        record["state"] = f"launch refused: lane worktree {lane_path} is not a directory"
        try:
            _write_record(attempt_path, record)
        except OSError:
            pass
        return _refuse(
            "runner-cwd",
            [f"lane worktree {lane_path} is not a directory; refusing to spawn a "
             "runner that would inherit the main checkout as its cwd"],
            f"worktree={lane_path}; attempt={attempt_id}", retained,
        )
    command = [sys.executable, str(Path(__file__).with_name("dispatch_lane.py")),
               "--prompt", str(prompt_path), "--", "ccc", *runner_args, agent]
    print(
        f"launching governed runner: dispatcher=dispatch_lane.py; cwd={lane_path.resolve()}; "
        f"agent={agent}; attempt={attempt_id}"
    )
    # Inherit the launcher's regular-file stdout/stderr. Capturing here would
    # manufacture the pipe hazard that dispatch_lane correctly refuses.
    result = subprocess.run(command, cwd=lane_path)
    record["runner_exit"] = None
    if result.returncode == 0:
        # #1117: dispatch confirmed the runner exec'd, but a runner that exec'd
        # and died one millisecond later is indistinguishable from a healthy one
        # on dispatcher-0 alone. The spawn lands in cwd=lane_path (#1093), so a
        # live runner's /proc/<pid>/cwd IS the worktree: settle, then probe for a
        # known runner process holding that cwd. This moves "worktree reach" out
        # of the unchecked list into a measured result, keeping #136's three
        # states (not attempted / attempted and gone / attempted and present)
        # distinguishable. A failed check fails the launch (exit 3) and records
        # it — an unobserved result is the defect this closes.
        settle = float(os.environ.get("LAUNCH_RUNNER_SETTLE", _RUNNER_SETTLE_SECONDS))
        if settle > 0:
            time.sleep(settle)
        present, examined = _lane_runner_present(lane_path)
        if present:
            record["state"] = (
                "spawned: runner present in worktree (cwd-containment); runner "
                "exit not observed; exact brief bytes preserved"
            )
        else:
            record["state"] = (
                "spawn failed: dispatcher exit=0 but no lane runner found in "
                "worktree (cwd-containment); runner exit not observed; exact "
                "brief bytes preserved"
            )
        try:
            _write_record(attempt_path, record)
        except OSError as exc:
            print(
                f"UNVERIFIED ATTEMPT: attempt={attempt_id}; dispatcher returned 0 but the "
                f"spawn record could not be persisted: {exc}; exact brief bytes are preserved "
                f"and only --resume {attempt_id} with the identical digest is allowed",
                file=sys.stderr,
            )
            return 2
        if present:
            print(
                f"runner spawned: attempt={attempt_id}; dispatcher exit=0; runner "
                f"detached; runner present in worktree (cwd-containment, examined "
                f"{examined}); runner exit not observed; unchecked=runner exit, "
                "interpreter availability, lane work"
            )
            return 0
        # The runner exec'd (dispatch confirmed) but no runner process holds the
        # worktree cwd now: it may have exec'd and died instantly. Reported as a
        # launch failure (exit 3) so downstream automation acts on it, not by
        # hand-probing /proc — which is how three silent non-starts were found.
        print(
            f"runner spawned: attempt={attempt_id}; dispatcher exit=0; runner "
            f"detached; no lane runner in worktree (cwd-containment, examined "
            f"{examined}); runner exit not observed; unchecked=runner exit, "
            "interpreter availability, lane work",
            file=sys.stderr,
        )
        print(
            f"REFUSE phase=spawn-containment: dispatcher exit=0 but no lane "
            f"runner process holds the worktree cwd; the runner may have exec'd "
            f"and exited immediately; probe the worktree by hand",
            file=sys.stderr,
        )
        return 3
    record["state"] = (
        f"launch refused: dispatcher exited {result.returncode}; runner not confirmed "
        "spawned; exact brief bytes preserved"
    )
    try:
        _write_record(attempt_path, record)
    except OSError as exc:
        print(
            f"UNVERIFIED ATTEMPT: attempt={attempt_id}; dispatcher returned {result.returncode} "
            f"but the spawn record could not be persisted: {exc}; exact brief bytes are "
            f"preserved and only --resume {attempt_id} with the identical digest is allowed",
            file=sys.stderr,
        )
        return 2
    print(f"REFUSE phase=runner-launch: dispatcher exited {result.returncode}; runner not confirmed spawned", file=sys.stderr)
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
    parser.add_argument("--base", metavar="REF",
                        help="base the lane on an existing ref instead of master "
                             "(a branch to continue, a tag, or a sha); a ref that "
                             "does not resolve is refused, never silently based on "
                             "master, and the recorded base_sha is the commit the "
                             "worktree is really on")
    parser.add_argument("--resume", metavar="ATTEMPT_ID")
    args, runner_args = parser.parse_known_args(argv)
    return launch(args.task, args.lane, args.agent, args.head, runner_args,
                  resume=args.resume, base=args.base)


if __name__ == "__main__":
    raise SystemExit(main())
