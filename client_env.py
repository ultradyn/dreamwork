#!/usr/bin/env python3
"""client_env.py — which CLI client runs this loop, and which session it is (#665).

Nothing recorded which session IS the running dreamwork agent. `#613`'s design
measured that gap directly (*"grepped `heartbeat.py`, `status_sync.py`,
`status_derive.py`, `SKILL.md`: no session identity anywhere"*) and it became
his Q3. He answered it on 2026-07-31:

    "for the main dreamwork agent, we can record its session in status.json
    (note: this is easy to detect via env var, but the env var name changes
    per cli client; one of the items on the checklist for adding new client
    support is identifying the best env var to use for session id; other
    similar env vars should be recorded too so we can have the right info
    about subagents or whatever and not get confused)."

He took SELF-REPORT and rejected inference (`#613` had offered "newest
live-mtime jsonl in the client project dir" as option (a); he answered only
option (b)). That is the stronger half: inference is ambiguous the moment two
sessions run at once, and self-report is exact.

This module is the ONE home for the per-client environment surface — which
variable names a client uses, and how to read them. The record it produces
lives under `status.json`'s `agent_session` key (`file-formats.md`).

WHY THIS IS AUTHORED, NOT DERIVED — the deliberate call, because
`status_sync.py` owns the derived fields and the obvious reading is that a
value read out of the environment is "derivable" and belongs there.

The derived side is not defined by "computed rather than typed". It is
defined by a stronger property that every one of its fields has: **the source
is SHARED, so any process that runs the tool computes the same answer.**
`queue` comes from the ledger store, `current_task_ids` and `dreamers` from
the OS process table, `#655`'s pending count from the journal — all on-disk or
kernel state, identical to every reader. That property is what makes
recompute-and-overwrite safe.

**The environment does not have it.** It is process-local and differs per
reader, and it differs precisely in the bit that says whether the reader is
the main agent. Three concrete wrong answers a derived implementation would
produce, none hypothetical:

  1. `status_sync.py` run FROM A LANE would write that lane's environment over
     the main agent's record. Every lane inherits the SAME
     `CLAUDE_CODE_SESSION_ID` (`#652`, measured — one CLI process, lanes are
     Agent-tool subagents of it), so the id would still look right and only
     `is_subagent` would flip. Right-looking and wrong is the worst shape.
  2. `status_derive.status_from_store` runs inside the **watch.py server
     process**, which is launched once and outlives sessions. Its environment
     is a snapshot of whichever session started it, so it would report a dead
     session's id as the live one.
  3. A `just` recipe, a hook or a cron invocation carries no session vars at
     all, so a derived field would have to blank a correct record.

And the refusal contract makes derived actively worse here rather than safer.
`status_sync` on "I could not tell" LEAVES THE FIELD ALONE (`LivenessUnknown`)
— correct for liveness, where the previous value was a hand-written truth a
blind probe must not clobber. For session identity "leave alone" means **keep
the previous CLI session's id**, which is exactly the wrong answer and is
indistinguishable from a fresh one. The refusal contract would preserve the
defect instead of surfacing it.

So the record is written by the main agent, at orient (`initialization.md`
step 7), through this module — mechanically read so it is never hand-typed,
but read by the ONE process entitled to read it. `status_sync` leaves it
alone by construction: `DERIVED` is a three-tuple and `coverage()` subtracts
it, so this key appears in the author-owned list without anyone editing a
literal.

STALENESS, and why orient is the right trigger rather than a recompute: a
session id can only change when the CLI session changes, and a fresh or
resumed session re-runs init — so the record is refreshed exactly when the
thing it names can move. `recorded_at` is written so a human can see the claim
age rather than trust it. NOT MEASURED, and stated rather than assumed:
whether resuming a session mints a new `CLAUDE_CODE_SESSION_ID`. Re-recording
at orient is idempotent and costs nothing, so the procedure is correct either
way; the record is a timestamped claim, not a guarantee.

HONEST ABSENCE. A client that exposes no session-id variable records `null`,
never an inferred guess — the same discipline `#613` used for `system_prompt`,
which is never written to the transcript and so renders absent rather than
invented. Four states are distinguishable from the data alone, with no extra
field, because `note` is present ONLY when something was refused:

  client set, session_id set    resolved.
  client set, session_id null   the client is known and could not supply an
                                id; `note` says whether that is because the
                                client HAS no such var (measured) or because
                                it declares one the environment did not carry
                                (an anomaly worth seeing).
  client null                   nothing here recognised the client; `note`
                                says whether no marker matched or whether
                                markers for several matched at once.
  is_subagent null              this client has no signal that distinguishes a
                                subagent from the main agent. `false` means
                                MEASURED not-a-subagent, and the two must not
                                collapse.

THE TRAP, measured by `#652` and re-verified in this lane's own environment:
`CLAUDE_CODE_SESSION_ID` names the **CLI session**, not the lane. Every
concurrent lane inherits it byte-identically. A session id can therefore never
be used as a lane identity, and nothing here offers it as one — that is the
100role the `is_subagent` bit exists to fill, *"the other similar env vars … so
we can have the right info about subagents or whatever and not get confused"*
half of his answer. For claude-code that role is currently UNFILLED: no
measured variable discriminates the roles (#678), so `is_subagent` records
`null` for this client rather than a confident boolean that would mislabel the
main agent. A future client that does measure a discriminator sets
`subagent_var` and records a real boolean.

THE CEILING, stated rather than papered over: a harness launched as a CHILD of
another (a `ccc` lane spawned from a Claude Code session) inherits the
parent's markers, so a registry keyed on marker presence can report the
parent. The only real defence is the child harness setting its own marker, and
whether it does is a per-client MEASUREMENT — which is why it is an explicit
item on the onboarding checklist (`plans/session-log-view.md` §10) rather than
a guess encoded here. When two registry entries match at once this refuses
(`client: null`) instead of picking one, because "I cannot tell which client"
and "it is this client" must not be the same value.

ADDING A CLIENT: append a `Client` row, and only after MEASURING it. An
unmeasured client is deliberately absent from `CLIENTS` rather than guessed —
`plans/harness-containment.md`'s standing rule for exactly this shape is
*"do not invent a capability matrix"*.

Usage:  python3 client_env.py                     # print the record as JSON
        python3 client_env.py --write --target .  # merge it into status.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

# The status.json write contract — read defensively, and REFUSE rather than
# overwrite a file that could not be read (#402). status.json has several
# readers (lint.py, dreamhub.py) but only two WRITERS that read-modify-write
# it, and this is the other one, so the refusal contract has exactly one home
# and it is reused rather than re-implemented (#655: a hand-rolled replacement
# passed every test its author wrote). Importing status_sync pulls watch.py in
# transitively (~0.3 s); that is affordable for a once-per-session CLI and is
# not a cycle, because watch.py folds unlisted status keys into "the rest"
# (#310) and so never needs to import this.
from status_sync import _read_status

# The one top-level status.json key this module owns (`file-formats.md`).
STATUS_KEY = "agent_session"


class Client(NamedTuple):
    """One MEASURED CLI client's environment surface.

    `detect` is a conjunction: every named variable must be present. A
    conjunction is the more specific test, and specificity is the only thing
    that can disambiguate a child harness from the parent it inherited from.

    `session_id_var` / `subagent_var` are `None` to mean **measured: this
    client has no such variable** — distinct from a client that is simply not
    in the registry, which is absence of measurement.
    """

    name: str
    detect: tuple[str, ...]
    session_id_var: str | None
    subagent_var: str | None


# MEASURED clients only. Order is significance order: the first match wins,
# and a tie refuses. See "ADDING A CLIENT" above before appending a row.
CLIENTS: tuple[Client, ...] = (
    # Claude Code. `CLAUDE_CODE_SESSION_ID` is the session uuid and is the
    # uuid segment of the harness scratchpad path — measured by #652 and
    # re-verified in-lane. `CLAUDECODE=1` is the client marker.
    #
    # `subagent_var` is INTENTIONALLY None: NOTHING in this client's
    # environment distinguishes a subagent from the main agent (#678,
    # measured 2026-07-31). The prior candidate `CLAUDE_CODE_CHILD_SESSION`
    # (#652's measurement, since refuted) is set in BOTH roles — verified in
    # the coordinator's own env AND a real subagent's (lane-664notify) —
    # because a subagent is spawned inside the same CLI process and inherits
    # its environment wholesale. `CLAUDE_PID` shares one value across both
    # roles for the same reason. A registry entry whose `subagent_var` is set
    # in both roles is WORSE than an absent one: it reports a confident
    # boolean that is wrong, and the record is read by the dashboard. `None`
    # says "this client exposes no reliable discriminator" — the same
    # standard `session_id_var=None` already sets for "has no var" — and
    # `is_subagent` is left `None` for this client rather than guessed.
    Client(
        name="claude-code",
        detect=("CLAUDECODE",),
        session_id_var="CLAUDE_CODE_SESSION_ID",
        subagent_var=None,
    ),
)


def _absent(note: str) -> dict:
    """A record that resolved nothing, saying which nothing it was."""
    return {"client": None, "session_id": None, "is_subagent": None,
            "note": note}


def _truthy(raw) -> bool:
    """Is a marker variable asserting its flag?

    PRESENCE is the signal a working discriminator would use: the variable
    is set when the flag is true, absent when it is not. (The concrete
    example is deferred to the per-client measurement — claude-code's
    `CLAUDE_CODE_CHILD_SESSION` is NOT such a discriminator, per #678, and
    naming it here would re-assert the refuted claim.) The falsy literals
    are a defensive read of a case nobody has measured — a client that sets
    `=0` for the parent instead of unsetting it — and it cannot change the
    measured behaviour, only the unmeasured one.
    """
    if raw is None:
        return False
    return raw.strip().lower() not in ("", "0", "false", "no")


def matching_clients(env) -> list:
    """Every registry row whose markers are all present in `env`."""
    return [c for c in CLIENTS if all(v in env for v in c.detect)]


def identify(env=None) -> dict:
    """`{client, session_id, is_subagent}` for `env` (default `os.environ`).

    Never raises and never guesses: an unresolved field is `None` and carries
    a `note` saying why. See the module docstring for the four states.
    """
    env = os.environ if env is None else env
    matched = matching_clients(env)
    if not matched:
        return _absent("no known client marker in the environment; "
                       "see client_env.CLIENTS")
    if len(matched) > 1:
        return _absent("ambiguous: markers for %s are all present, so the "
                       "client cannot be told apart"
                       % ", ".join(c.name for c in matched))
    c = matched[0]
    rec = {"client": c.name, "session_id": None, "is_subagent": None}
    if c.session_id_var is None:
        rec["note"] = "%s exposes no session-id env var" % c.name
    else:
        raw = env.get(c.session_id_var)
        if raw is None:
            rec["note"] = ("%s declares %s but the environment does not "
                           "carry it" % (c.name, c.session_id_var))
        elif raw.strip() == "":
            rec["note"] = "%s is set but empty" % c.session_id_var
        else:
            rec["session_id"] = raw.strip()
    if c.subagent_var is not None:
        rec["is_subagent"] = _truthy(env.get(c.subagent_var))
    return rec


def record(env=None, now=None) -> dict:
    """`identify()` plus `recorded_at`, so the claim carries its own age."""
    rec = identify(env)
    stamp = now if now is not None else datetime.now().astimezone()
    rec["recorded_at"] = stamp.isoformat(timespec="seconds")
    return rec


def describe(rec: dict) -> str:
    """One line for a human, which must not read as success when it resolved
    nothing (#611: a check that examines nothing must not read as passing).
    """
    if rec.get("client") is None or rec.get("session_id") is None:
        return "recorded ABSENT: %s" % rec.get("note", "no reason recorded")
    return ("recorded %s session %s (is_subagent=%s)"
            % (rec["client"], rec["session_id"], rec["is_subagent"]))


def write(target, env=None, now=None) -> tuple[int, str]:
    """Merge the record into `<target>/.dreamwork/status.json`.

    Returns `(rc, message)`. Writes atomically (tmp + `os.replace`, #541) so a
    crash mid-write cannot tear the file, and refuses rather than overwrites a
    status.json that could not be read (#402) — the same contract the other
    writer runs on, imported rather than restated.
    """
    dw = Path(target) / ".dreamwork"
    spath = dw / "status.json"
    if not dw.is_dir():
        return 2, "no .dreamwork directory under %s" % target
    if spath.exists():
        status, why = _read_status(spath)
        if status is None:
            return 1, ("refusing to write agent_session: %s (bytes left "
                       "untouched)" % why)
    else:
        status = {}
    rec = record(env, now)
    status[STATUS_KEY] = rec
    tmp = str(spath) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(status, indent=2) + "\n")
    os.replace(tmp, spath)
    return 0, describe(rec)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Record which CLI client and session runs this loop.")
    ap.add_argument("--target", default=".", help="target project directory")
    ap.add_argument("--write", action="store_true",
                    help="merge the record into .dreamwork/status.json")
    args = ap.parse_args(argv)
    if not args.write:
        print(json.dumps(record(), indent=2))
        return 0
    rc, msg = write(args.target)
    print(msg, file=sys.stdout if rc == 0 else sys.stderr)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
