#!/usr/bin/env python3
"""relay — append a coordinator message to a subagent's inbox, safely.

    python3 relay.py <agent-name> < message.txt
    printf '%s' "$body" | python3 relay.py dreamer-thread
    printf '%s' "$body" | python3 relay.py coord --as dreamer-rows

Reads the body from STDIN and never from an argument, which is the whole
point: on 2026-07-25 the coordinator wrote relays through an unquoted shell
heredoc so it could interpolate a timestamp, and every backticked term in
the message — `_parse_entries`, `- **`, `## ` — executed as a command
substitution and was replaced with nothing. The message stayed plausible
and lost its nouns. Needing ONE variable expanded had opted the entire
document into shell expansion.

Stdin cannot be expanded, so the body arrives as written.

It also stamps the header from the system clock. Four consecutive relays
that day carried timestamps in the FUTURE, written by incrementing the
heartbeat interval instead of reading the clock, and dreamers reason about
whether an instruction predates one of their commits. Two different agents
made that mistake within ten minutes of each other, which is what turned it
from carelessness into something worth removing the opportunity for.

It works in BOTH directions, and the reverse is the one that keeps
failing: a dreamer reporting to `coord` passes `--as <its own name>` and
never types a time. Five different agents invented a timestamp on
2026-07-25, the fifth after being warned about the other four in its own
dispatch — so the rule has now lost to the bias five times and the
opportunity is what gets removed.

WHAT THIS SERVES: an Agent-tool dreamer that created its inbox and reads it
between increments. It does not wake that dreamer, so one that has gone idle
never sees the message until the harness wakes it. A ccc lane is different:
it never reads an agent-comms inbox at all. The CLI refuses registered ccc
lanes, and refuses unknown names instead of creating typo-shaped inboxes.
Durability and delivery are different problems (#144, #150).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

INBOX_DIR = Path.home() / ".cache/agent-comms/ud-dreamwork"
REPO_DIR = Path(__file__).resolve().parent


def now_stamp() -> str:
    """From the clock, via the same `date` the rest of the loop uses."""
    out = subprocess.run(
        ["date", "+%Y-%m-%d %H:%M"], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def inbox_for(agent: str, inbox_dir: Path | None = None) -> Path:
    """`dreamer-thread` -> ~/.cache/agent-comms/ud-dreamwork/dreamer-thread-inbox.md"""
    name = agent if agent.endswith("-inbox.md") else f"{agent}-inbox.md"
    return (inbox_dir or INBOX_DIR) / name


def registered_ccc_lanes() -> tuple[dict[str, Path], str | None]:
    """Return lanes marked by lane.lock in registered git worktrees."""
    result = subprocess.run(
        ["git", "-C", str(REPO_DIR), "worktree", "list", "--porcelain"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        return {}, f"git worktree list exited {result.returncode}"

    worktrees = [
        Path(line.removeprefix("worktree "))
        for line in result.stdout.splitlines()
        if line.startswith("worktree ")
    ]
    lanes: dict[str, Path] = {}
    for worktree in worktrees:
        lock = worktree / ".dreamwork" / "lane.lock"
        if not lock.is_file():
            continue
        try:
            record = json.loads(lock.read_text(encoding="utf-8"))
            lane = record["lane"]
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            return {}, f"could not read ccc lane marker {lock}: {exc}"
        if not isinstance(lane, str) or not lane:
            return {}, f"ccc lane marker {lock} has no non-empty lane name"
        lanes[lane] = worktree
    return lanes, None


def relay(
    agent: str,
    body: str,
    *,
    stamp: str | None = None,
    inbox_dir: Path | None = None,
    sender: str = "coordinator",
) -> Path:
    path = inbox_for(agent, inbox_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = f"[{sender} {stamp or now_stamp()}]"
    # Leading blank line so entries never run together, and exactly one
    # trailing newline so the next append starts clean.
    path.open("a", encoding="utf-8").write(f"\n{header} {body.strip()}\n")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="relay",
        description="Append a timestamped coordinator message to a subagent's inbox. Body comes from stdin.",
    )
    ap.add_argument(
        "agent",
        help="whose inbox to write: a subagent name, or `coord` to report to the coordinator",
    )
    ap.add_argument(
        "--as",
        dest="sender",
        default="coordinator",
        help="who is speaking (default: coordinator). A dreamer passes its own name.",
    )
    ap.add_argument(
        "--dir",
        default=None,
        help=f"inbox directory (default {INBOX_DIR})",
    )
    args = ap.parse_args(argv)

    body = sys.stdin.read()
    if not body.strip():
        print("relay: empty body on stdin — nothing written", file=sys.stderr)
        return 2

    inbox_dir = Path(args.dir).expanduser() if args.dir else INBOX_DIR
    target = args.agent.removesuffix("-inbox.md")
    ccc_lanes, classification_fault = registered_ccc_lanes()
    if classification_fault:
        print(
            f"relay: REFUSE {target} is unrecognised because ccc lane discovery failed: "
            f"{classification_fault}",
            file=sys.stderr,
        )
        return 4
    if target in ccc_lanes:
        print(
            f"relay: REFUSE {target} is a ccc lane at {ccc_lanes[target]}; "
            "ccc lanes never read agent-comms inboxes",
            file=sys.stderr,
        )
        return 3
    path = inbox_for(args.agent, inbox_dir)
    if not path.is_file():
        print(
            f"relay: REFUSE {target} is unrecognised; no ccc lane or declared "
            "agent-comms reader matches that name",
            file=sys.stderr,
        )
        return 4

    path = relay(
        args.agent,
        body,
        sender=args.sender,
        inbox_dir=inbox_dir,
    )
    print(f"relayed to declared reader {target} at {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
