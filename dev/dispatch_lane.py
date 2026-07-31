#!/usr/bin/env python3
"""Validate and record a Dreamwork lane prompt, then exec its runner.

The exact prompt bytes read here are appended as one argv item.  Validation is
therefore on the string this wrapper hands to the runner, rather than on a file
the coordinator merely intended to expand.  It cannot prove that a downstream
wrapper preserves that argv unchanged; post-launch inspection is a separate
mechanism with a shorter observation window.

The corpus copy and its hash receipt are intentionally uncommitted.  They make
the validated input available at the merge gate; they do not guarantee that a
coordinator will preserve or commit it.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = ROOT / "briefs" / "boilerplate.md"
INTEGRITY_START_TASK = 766
_TASK_HEAD = re.compile(r"^# [^\n]*?#(\d+)\b", re.MULTILINE)
_BRANCH_LINE = re.compile(
    r"^Branch:\s+`?([A-Za-z0-9][A-Za-z0-9._-]*)`?\s*$", re.MULTILINE
)
_RECEIPT = re.compile(r"([0-9a-f]{64})  ([^/\n]+\.md)\n?\Z")


class DispatchFault(Exception):
    """An input could not be evaluated or did not carry the contract."""


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


def validate_prompt(prompt: str, contract: str) -> None:
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


def _write_exclusive(path: Path, content: str) -> None:
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except (OSError, UnicodeError) as exc:
        raise DispatchFault(f"could not write {path}: {exc}") from exc


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
        if brief not in governed:
            faults.append(
                f"integrity receipt {receipt.name} has no governed brief artifact "
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

    runner = args.runner
    if runner and runner[0] == "--":
        runner = runner[1:]
    if not runner:
        print("dispatch refused: runner command is missing", file=sys.stderr)
        return 2

    try:
        prompt = _read(args.prompt, "prompt")
        contract = _read(CONTRACT_PATH, "standing contract")
        validate_prompt(prompt, contract)
        try:
            persist_prompt(prompt)
        except DispatchFault as exc:
            raise DispatchFault(f"could not persist validated brief: {exc}") from exc
    except DispatchFault as exc:
        print(f"dispatch refused: {exc}", file=sys.stderr)
        return 2

    try:
        os.execvp(runner[0], [*runner, prompt])
    except OSError as exc:
        print(f"dispatch refused: could not exec runner {runner[0]!r}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
