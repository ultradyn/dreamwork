#!/usr/bin/env python3
"""relay — append a coordinator message to a subagent's inbox, safely.

    python3 relay.py <agent-name> < message.txt
    printf '%s' "$body" | python3 relay.py dreamer-thread

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

WHAT THIS DOES NOT DO: wake the agent. The inbox is durable, not delivered
— a dreamer reads it between increments, so an agent that has gone idle
never sees it. Write with this, then send a message through the harness to
wake it. Durability and delivery are different problems (#144, #150).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

INBOX_DIR = Path.home() / ".cache/agent-comms/ud-dreamwork"


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


def relay(
    agent: str, body: str, *, stamp: str | None = None, inbox_dir: Path | None = None
) -> Path:
    path = inbox_for(agent, inbox_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = f"[coordinator {stamp or now_stamp()}]"
    # Leading blank line so entries never run together, and exactly one
    # trailing newline so the next append starts clean.
    path.open("a", encoding="utf-8").write(f"\n{header} {body.strip()}\n")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="relay",
        description="Append a timestamped coordinator message to a subagent's inbox. Body comes from stdin.",
    )
    ap.add_argument("agent", help="subagent name, e.g. dreamer-thread")
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

    path = relay(
        args.agent, body, inbox_dir=Path(args.dir).expanduser() if args.dir else None
    )
    print(f"relayed to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
