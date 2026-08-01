#!/usr/bin/env python3
"""Record and report the most recent full ``just test`` attempt.

This is instrumentation, not a gate.  A RUNNING receipt is persisted before
the subprocess starts so a killed runner cannot leave the prior pass looking
like the current attempt.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
from typing import Any, Sequence


SCHEMA_VERSION = 1
DEFAULT_RECORD = Path(".dreamwork/suite-baseline.json")
COMMAND = ("just", "test")
UNKNOWN = "UNKNOWN"

PYTEST_OUTCOME = re.compile(
    r"(?P<count>\d+) (?P<kind>passed|failed|skipped|errors?|xfailed|xpassed|deselected)\b"
)
PYTEST_COLLECTED = re.compile(r"collected (?P<count>\d+) items?", re.IGNORECASE)
PYTEST_COLLECTION_ERROR = re.compile(r"^_+ ERROR collecting .+ _+$", re.MULTILINE)
LINT_CLEAN = re.compile(r"^clean \((?P<warnings>\d+) warning\(s\)\)$", re.MULTILINE)
GUARD_ACCOUNTING = re.compile(
    r"guards: (?P<executed>\d+) of (?P<expected>\d+) registered guard\(s\) "
    r"ran and judged"
)
GUARD_RESULT = re.compile(r"^  (?P<state>PASS|FAIL) (?P<name>[A-Za-z0-9_-]+)(?:\s|$)", re.MULTILINE)
DEFAULT_GUARDS = re.compile(r'^\s*DEFAULT_GUARDS="(?P<names>[^"]*)"', re.MULTILINE)
HUB_GUARDS = re.compile(r'^\s*HUB_GUARDS=\$\{DREAMWORK_HUB_GUARDS-"(?P<names>[^"]*)"\}', re.MULTILINE)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _atomic_write(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _load(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{path} is not a suite-baseline schema version {SCHEMA_VERSION} receipt")
    return data


def _git(repo: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _tree_clean(repo: Path, record: Path) -> bool:
    status = _git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    if status is None:
        return False
    try:
        record_rel = record.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        record_rel = None
    rows = [row for row in status.splitlines() if row != f"?? {record_rel}"]
    return not rows


def _component(state: str = "NOT RUN") -> dict[str, Any]:
    return {
        "state": state,
        "executed": 0,
        "expected": None,
        "outcomes": {},
    }


def _guard_roster(repo: Path) -> tuple[list[str], list[str]]:
    try:
        text = (repo / "justfile").read_text(encoding="utf-8")
    except OSError:
        return [], []
    default = DEFAULT_GUARDS.search(text)
    hub = HUB_GUARDS.search(text)
    return (
        default.group("names").split() if default else [],
        hub.group("names").split() if hub else [],
    )


def _pytest_component(output: str) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for match in PYTEST_OUTCOME.finditer(output):
        kind = match.group("kind")
        kind = "errors" if kind in {"error", "errors"} else kind
        counts[kind] = max(counts.get(kind, 0), int(match.group("count")))
    collection_errors = len(PYTEST_COLLECTION_ERROR.findall(output))
    if collection_errors:
        counts["collection_errors"] = collection_errors
    executed = sum(counts.get(kind, 0) for kind in ("passed", "failed", "skipped", "xfailed", "xpassed"))
    executed += max(0, counts.get("errors", 0) - collection_errors)
    collected = [int(match.group("count")) for match in PYTEST_COLLECTED.finditer(output)]
    expected: int | None = max(collected) if collected else (executed or None)
    if not counts:
        return _component()
    complete = expected is not None and executed == expected and counts.get("errors", 0) == 0
    passed = complete and counts.get("failed", 0) == 0
    return {
        "state": "PASS" if passed else ("FAIL" if complete else "INCOMPLETE"),
        "executed": executed,
        "expected": expected,
        "outcomes": counts,
    }


def _lint_component(output: str) -> dict[str, Any]:
    match = LINT_CLEAN.search(output)
    if match is None:
        return _component()
    return {
        "state": "PASS",
        "executed": 1,
        "expected": 1,
        "outcomes": {"warnings": int(match.group("warnings"))},
    }


def _guard_components(repo: Path, output: str) -> tuple[dict[str, Any], dict[str, Any]]:
    browser, hub = _guard_roster(repo)
    results = {match.group("name"): match.group("state") for match in GUARD_RESULT.finditer(output)}
    accounting = list(GUARD_ACCOUNTING.finditer(output))
    all_judged = bool(accounting and int(accounting[-1].group("executed")) == int(accounting[-1].group("expected")))

    def one(names: list[str]) -> dict[str, Any]:
        seen = {name: results[name] for name in names if name in results}
        expected = len(names) if names else None
        complete = expected is not None and len(seen) == expected and all_judged
        state = "PASS" if complete and "FAIL" not in seen.values() else ("FAIL" if seen else "NOT RUN")
        if seen and not complete and state != "FAIL":
            state = "INCOMPLETE"
        return {
            "state": state,
            "executed": len(seen),
            "expected": expected,
            "outcomes": {
                "passed": sum(value == "PASS" for value in seen.values()),
                "failed": sum(value == "FAIL" for value in seen.values()),
                "judged": len(seen) if all_judged else None,
            },
        }

    return one(browser), one(hub)


def _analyse(repo: Path, output: str) -> dict[str, dict[str, Any]]:
    pytest = _pytest_component(output)
    lint = _lint_component(output)
    browser, hub = _guard_components(repo, output)
    return {"pytest": pytest, "lint": lint, "browser_guards": browser, "hub_guards": hub}


def _eligible(receipt: dict[str, Any], returncode: int) -> bool:
    return bool(
        returncode == 0
        and receipt["starting_sha"] not in {None, UNKNOWN}
        and receipt["starting_sha"] == receipt["ending_sha"]
        and receipt["tree_clean_at_start"]
        and receipt["tree_clean_at_end"]
        and all(part["state"] == "PASS" for part in receipt["components"].values())
        and all(part["expected"] not in {None, 0} for part in receipt["components"].values())
        and all(part["executed"] == part["expected"] for part in receipt["components"].values())
    )


def run(repo: Path, record: Path) -> int:
    repo = repo.resolve()
    record = record if record.is_absolute() else repo / record
    prior = _load(record)
    starting_sha = _git(repo, "rev-parse", "HEAD") or UNKNOWN
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "started_at": _now(),
        "finished_at": None,
        "starting_sha": starting_sha,
        "ending_sha": None,
        "tree_clean_at_start": _tree_clean(repo, record),
        "tree_clean_at_end": None,
        "command": list(COMMAND),
        "state": "RUNNING",
        "returncode": None,
        "components": {name: _component() for name in ("pytest", "lint", "browser_guards", "hub_guards")},
        "last_full_pass": prior.get("last_full_pass") if prior else None,
    }
    interrupted = False
    process: subprocess.Popen[str] | None = None

    def stop(signum: int, _frame: object) -> None:
        nonlocal interrupted
        interrupted = True
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)

    old_handlers = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
    output_parts: list[str] = []
    try:
        _atomic_write(record, receipt)
        process = subprocess.Popen(
            list(COMMAND), cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, start_new_session=True,
        )
        if interrupted and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            output_parts.append(line)
        returncode = process.wait()
    finally:
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)

    receipt["finished_at"] = _now()
    receipt["ending_sha"] = _git(repo, "rev-parse", "HEAD") or UNKNOWN
    receipt["tree_clean_at_end"] = _tree_clean(repo, record)
    receipt["returncode"] = returncode
    receipt["components"] = _analyse(repo, "".join(output_parts))
    if interrupted:
        receipt["state"] = "INTERRUPTED"
    elif _eligible(receipt, returncode):
        receipt["state"] = "PASS"
        receipt["last_full_pass"] = {
            "finished_at": receipt["finished_at"],
            "sha": receipt["ending_sha"],
            "components": receipt["components"],
        }
    else:
        receipt["state"] = "FAIL" if any(
            part["state"] == "FAIL" for part in receipt["components"].values()
        ) else "INCOMPLETE"
    _atomic_write(record, receipt)
    return returncode if returncode != 0 else (0 if receipt["state"] == "PASS" else 1)


def _fraction(part: dict[str, Any]) -> str:
    expected = part.get("expected")
    return f"{part.get('executed', 0)}/{expected if expected is not None else UNKNOWN}"


def _attempt_line(receipt: dict[str, Any] | None) -> str:
    if receipt is None:
        return "full-suite last attempt: NOT RUN — no attempt receipt"
    state = receipt.get("state", UNKNOWN)
    sha = receipt.get("starting_sha") or UNKNOWN
    parts = receipt.get("components", {})
    pytest = parts.get("pytest", _component())
    lint = parts.get("lint", _component())
    browser = parts.get("browser_guards", _component())
    hub = parts.get("hub_guards", _component())
    errors = pytest.get("outcomes", {}).get("collection_errors", 0)
    return (
        f"full-suite last attempt: {state} at {sha} — "
        f"pytest {_fraction(pytest)} outcomes, collection errors {errors}; "
        f"lint {_fraction(lint)} {lint.get('state', UNKNOWN)}; "
        f"browser guards {_fraction(browser)} {browser.get('state', UNKNOWN)}; "
        f"hub guards {_fraction(hub)} {hub.get('state', UNKNOWN)}"
    )


def format_status(receipt: dict[str, Any] | None) -> str:
    last = receipt.get("last_full_pass") if receipt else None
    last_line = (
        f"last full pass: {last['sha']} at {last['finished_at']}"
        if isinstance(last, dict) and last.get("sha") and last.get("finished_at")
        else "last full pass: UNKNOWN — no eligible completed pass recorded"
    )
    return f"{_attempt_line(receipt)}\n{last_line}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("verb", choices=("run", "status"))
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    args = parser.parse_args(argv)
    record = args.record if args.record.is_absolute() else args.repo / args.record
    if args.verb == "run":
        return run(args.repo, args.record)
    try:
        receipt = _load(record)
    except ValueError as exc:
        print(f"suite-baseline: {exc}", file=sys.stderr)
        return 2
    print(format_status(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
