#!/usr/bin/env python3
"""Validate a Dreamwork lane prompt, then replace this process with its runner.

The exact prompt bytes read here are appended as one argv item.  Validation is
therefore on the string this wrapper hands to the runner, rather than on a file
the coordinator merely intended to expand.  It cannot prove that a downstream
wrapper preserves that argv unchanged; post-launch inspection is a separate
mechanism with a shorter observation window.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = ROOT / "briefs" / "boilerplate.md"


class DispatchFault(Exception):
    """An input could not be evaluated or did not carry the contract."""


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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="validate a lane prompt and exec the runner with it as one argv item"
    )
    parser.add_argument("--prompt", required=True, type=Path)
    parser.add_argument("runner", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
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
