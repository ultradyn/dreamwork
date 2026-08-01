#!/usr/bin/env python3
"""#842 — ingest the live-voice-dictation plan as a v005 hierarchy.

The plan at ``~/.claude-p/plans/delightful-munching-barto.md`` is already
decomposed: a 13-row task table (A-M), a four-layer blocking map (the natural
epic boundary), and four durable rulings.  This script turns that decomposition
into one milestone, four epics, thirteen tasks, eleven task->task ``depends``
edges, and one group->task ``task_group_dependency`` edge (the React #630 gate)
— the first real content through v005 (#841).

LANES DO NOT WRITE THE LIVE LEDGER.  This script is driven against a COPY:

    python3 dev/ingest_plan_hierarchy.py --ledger <copy-of-ledger.sqlite3>

``--ledger`` here is the SQLite store file (not ``tasks.md``); the coordinator
runs it once against live after reviewing the printed tree.

Idempotency model — atomic + refuse-on-prior-success:

  * The whole ingestion is ONE transaction (``store.transaction()``).  Any
    failure rolls every group, task, membership, and edge back, so a half-run
    leaves a clean store and a re-run starts fresh.
  * Before creating anything, the script looks for a milestone whose title
    matches ``MILESTONE_TITLE``.  Finding one means a prior run SUCCEEDED, so
    it refuses rather than filing a second copy.  That is the "explicitly
    refuse to double-ingest" arm: detection is by milestone title, because the
    milestone is the first row created and the last to survive a commit.

The two ``depends`` and ``task_group_dependency`` homes are kept distinct on
purpose (#841 §4, #440): task->task edges live in v001's ``depends`` (which has
no public write verb — work-hierarchy.md §7 — so this script reaches the
session directly), and only edges with a group endpoint go in
``task_group_dependency``.  Getting this backwards is refused by the schema's
third CHECK, which is the point.
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

# Run as `python3 dev/ingest_plan_hierarchy.py` from the repo root: sys.path[0]
# is `dev/`, so add the root for `import dreamwork_db`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dreamwork_db import (  # noqa: E402
    Access, Conflict, NotFound, ValidationError, open_database,
)
from dreamwork_db.store import dreamwork_store_spec  # noqa: E402

MILESTONE_TITLE = "Live voice dictation"
ACTOR = "coordinator"

# --- the four durable rulings, quoted verbatim from the plan ---------------
# These are embedded into task bodies so Max's decisions are not lost.  The
# verbatim phrases are load-bearing for the red-proof (direction 2: "titles
# ingested but rulings dropped").
RULING_OPTIN = (
    "Ruling (opt-in/provider chooser): Never spend his plan silently. The"
    " opt-in prompt doubles as the provider chooser — \"we will want to add"
    " support for other speech-to-text services in the future, like xAI's"
    " Grok\". So the module is a provider registry, not an OpenAI client."
)
RULING_OPTIONAL_DEPS = (
    "Ruling (optional deps): Use mature dependencies, but they must be"
    " optional: check whether installed, fail gracefully, never block"
    " deployment on a machine without them, never required for core"
    " functionality. If they are absent, the feature is simply not offered —"
    " voice is not core, so its absence is a normal state, not a degraded one"
    " and not an error."
)
RULING_SIGNIN = (
    "Ruling (sign-in): Both sign-in paths. Show the user \"either do this or"
    " do this\"; use device code for the OAuth path. Codex's own"
    " implementation is readable at ~/src/codex, so implement the device-code"
    " UX directly rather than shelling out."
)
RULING_USAGE = (
    "Ruling (usage): No usage cap — assume it comes out of the ChatGPT"
    " subscription. But do log session minutes and be able to display voice"
    " statistics. Add an off-by-default option to save the raw audio clips."
)

# --- the plan, as data ------------------------------------------------------
# Each task: key, title, type, priority, epic, body.  Edges are listed
# separately so they can be asserted as a SET (a count is not membership, #702).
EPIC_VOICE = "voice/ package (Layer 1)"
EPIC_WATCH = "watch.py speech-token route (Layer 2)"
EPIC_WEBUI = "Web UI dictation (Layer 3)"
EPIC_HUB = "Dreamhub sign-in and stats (Layer 4)"

TASKS: list[dict] = [
    dict(key="A", epic=EPIC_VOICE, type="task", pri="P1",
         title=("voice/credentials.py: discover ChatGPT-plan and API-key"
               " credentials from codex, opencode, pi and env — read-only,"
               " never refreshed"),
         body=(
             "Source: delightful-munching-barto.md task A (Layer 1, voice/).\n\n"
             "discover() -> list[Credential] from codex, opencode, pi, env."
             " READ-ONLY, always: Dreamwork never writes to a discovered"
             " credential file, and never refreshes a token (refresh tokens"
             " rotate; refreshing ~/.codex/auth.json behind Codex's back"
             " would break Codex's own login). On expiry, return a Credential"
             " in an expired state carrying the exact remedy sentence"
             " ('run: codex login'). expires_at normalised to SECONDS always"
             " (opencode stores ms; the Codex JWT stores seconds inside a"
             " base64 claim — one normalisation point, one test per source).\n\n"
             + RULING_OPTIONAL_DEPS)),
    dict(key="B", epic=EPIC_VOICE, type="task", pri="P1",
         title=("voice/providers: a speech-provider registry, with"
               " openai_realtime minting realtime transcription sessions"
               " over stdlib urllib"),
         body=(
             "Source: task B (Layer 1). Blocked on A.\n\n"
             "Provider Protocol + registry (register/lookup/rank)."
             " openai_realtime.mint() ~30 lines of urllib.request against"
             " POST /v1/realtime/client_secrets; returns SpeechSession"
             " (provider-neutral: ws_url, subprotocols, session, expires_at)."
             " Stdlib only, so watch.py and dreamhub.py keep their stdlib"
             " contracts.\n\n"
             + RULING_OPTIN)),
    dict(key="C", epic=EPIC_VOICE, type="task", pri="P1",
         title=("voice/consent.py: opt-in before Dreamwork ever spends his"
               " plan, and the same prompt chooses the provider"),
         body=(
             "Source: task C (Layer 1). Blocked on B.\n\n"
             "Opt-in state + chosen provider. The opt-in prompt IS the provider"
             " chooser.\n\n"
             + RULING_OPTIN)),
    dict(key="D", epic=EPIC_WATCH, type="task", pri="P1",
         title=("watch.py POST /speech-token: mint an ephemeral session so"
               " the long-lived token never reaches the browser"),
         body=(
             "Source: task D (Layer 2). Blocked on C.\n\n"
             "One handler + one line in WRITE_ROUTE_HANDLERS (watch.py:6213) —"
             " the documented idiom, which enrols the route in the E2 receipt"
             " test and replay dedup. POST not GET: _preflight only validates"
             " Origin on writes, and a GET that mints a credential would be"
             " reachable cross-origin. Refuses unless consent is recorded."
             " Availability state folds into /data.json, not a new endpoint.")),
    dict(key="E", epic=EPIC_VOICE, type="task", pri="P2",
         title=("voice/capture.py + cli.py: terminal dictation, so the stack"
               " is exercisable before React lands"),
         body=(
             "Source: task E (Layer 1). Blocked on B.\n\n"
             "capture.py: OPTIONAL deps (websockets, sounddevice), imported"
             " lazily inside functions, never at module import. probe() reports"
             " {available, missing, hint}. `import voice` must succeed on a"
             " machine with neither. When probe() reports unavailable, the"
             " feature is not offered at all.\n\n"
             + RULING_OPTIONAL_DEPS
             + "\n\nCLI-first ruling: a terminal dictation path lands before"
               " React so the stack is exercisable now.")),
    dict(key="F", epic=EPIC_VOICE, type="task", pri="P2",
         title=("voice/usage.py: log session minutes and characters;"
               " file-formats section and lint check in the same commit"),
         body=(
             "Source: task F (Layer 1). Blocked on B.\n\n"
             "Append-only JSONL at .dreamwork/voice/usage.jsonl:"
             " {started, seconds, provider, model, chars, source}. Loop-written"
             " and tool-parsed => file-formats.md section + lint.py check_* in"
             " the same commit (CLAUDE.md:118-119).\n\n"
             + RULING_USAGE)),
    dict(key="G", epic=EPIC_VOICE, type="idea", pri="P3",
         title=("voice: an off-by-default option to keep the raw audio of"
               " every clip recorded"),
         body=(
             "Source: task G (Layer 1, type idea). Blocked on F.\n\n"
             "Raw audio saving OFF by default; when enabled, WAV under"
             " .dreamwork/voice/clips/ (gitignored). Loop-written and"
             " tool-parsed => file-formats.md section + lint.py check in the"
             " same commit. Ships with a `Needs: consent` git trailer.\n\n"
             + RULING_USAGE)),
    dict(key="H", epic=EPIC_WEBUI, type="task", pri="P2",
         title=("Command composer dictation mode: mic button, enlarged field,"
               " live transcript (React-gated, like #823)"),
         body=(
             "Source: task H (Layer 3). Blocked on React conversion #630 —"
             " exact precedent is #823 (a composer feature Max personally"
             " gated on this migration). This task is a member of an epic that"
             " carries a task_group_dependency edge needing task #630, so the"
             " block is structural and inherited by every task in this epic"
             " (the case flat v004 could not express).\n\n"
             "Caveat worth a ruling before H starts: the composer is in no"
             " named phase of component-transition.md; it lives outside #view"
             " in client/command.js. Components: MicButton, DictationField,"
             " LiveTranscript. Dictated text goes through DraftStore exactly"
             " like typed text ('his typed words are never lost').")),
    dict(key="I", epic=EPIC_WEBUI, type="task", pri="P2",
         title=("Live 60fps mirrored voice spectrum canvas, without disturbing"
               " #dreambg's frame tally"),
         body=(
             "Source: task I (Layer 3). Blocked on H.\n\n"
             "One AudioContext({sampleRate:24000}) serves both paths (Nyquist"
             " 12kHz, no resampling). Analyser fftSize:2048, draw ~0-5kHz,"
             " symmetric about the mid-line. #dreambg's frame tally is a"
             " standing invariant (transitions.md:702): run only while"
             " recording. Measure per-frame cost against dissolveperf.mjs"
             " before shipping. Reduced motion changes timing, never function.")),
    dict(key="J", epic=EPIC_WEBUI, type="task", pri="P2",
         title=("dev/capture/dictation.mjs: a dictation guard driven by"
               " Chromium's fake media device"),
         body=(
             "Source: task J (Layer 3). Blocked on H.\n\n"
             "Registered in justfile:293 AND dev/capture/README.md or"
             " lint.check_guards_registered (lint.py:2687). Chromium needs"
             " --use-fake-ui-for-media-stream + --use-fake-device-for-media-stream"
             " and context.grantPermissions(['microphone']) — no precedent in"
             " this repo. Fake device emits a deterministic tone =>"
             " deterministic spectrum => a real assertion, not 'the canvas"
             " exists'.")),
    dict(key="K", epic=EPIC_HUB, type="task", pri="P2",
         title=("Dreamhub sign-in: implement OpenAI's device-code flow"
               " natively (per ~/src/codex/.../device_code_auth.rs), with"
               " loopback PKCE as the second option"),
         body=(
             "Source: task K (Layer 4). Blocked on the hub gaining a write"
             " surface — dreamhub.py has no do_POST today.\n\n"
             "FINDING: no task in the ledger represents 'hub write surface',"
             " so this blocker cannot be expressed as a task_group_dependency"
             " edge (the needs endpoint must exist — FK enforced). It is"
             " recorded here in prose and in the task body, not as a graph"
             " edge. When such a task is filed, add the edge then.\n\n"
             + RULING_SIGNIN)),
    dict(key="L", epic=EPIC_HUB, type="task", pri="P3",
         title=("Dreamhub voice statistics: minutes and sessions per project,"
               " read from the usage log"),
         body=(
             "Source: task L (Layer 4). Blocked on F (usage log) and K"
             " (sign-in).\n\n"
             "A voice-statistics panel reading usage.py across registered"
             " projects — the hub's existing job (aggregate read-only view),"
             " needs no new authority.")),
    dict(key="M", epic=EPIC_VOICE, type="idea", pri="P3",
         title=("voice/providers/xai_grok.py: add Grok STT as a second"
               " provider (he is already using it via hark)"),
         body=(
             "Source: task M (Layer 1, type idea). Blocked on B.\n\n"
             "Stub + registry entry now; implement when Grok STT is available."
             " The provider registry is the hedge for the undocumented OpenAI"
             " realtime entitlement: a second provider is a configuration"
             " change, not a rewrite.\n\n"
             + RULING_OPTIN)),
]

# task->task edges (v001 `depends`).  (dependent, needs) by task key.
# Source: the plan table's "blocked on" column, excluding the two external
# blockers (H->#630 is a group edge; K->hub-write-surface has no task endpoint).
TASK_EDGES: list[tuple[str, str]] = [
    ("B", "A"),
    ("C", "B"),
    ("D", "C"),
    ("E", "B"),
    ("F", "B"),
    ("G", "F"),
    ("I", "H"),
    ("J", "H"),
    ("L", "F"),
    ("L", "K"),
    ("M", "B"),
]

# group->task edges (task_group_dependency).  The Web-UI epic needs task #630
# (the React umbrella).  This is the case flat v004 could not express.
REACT_GATE_TASK = 630
GROUP_TASK_EDGES: list[tuple[str, int]] = [
    (EPIC_WEBUI, REACT_GATE_TASK),
]

EPIC_DESCRIPTIONS = {
    EPIC_VOICE: (
        "Layer 1 of the plan — the voice/ Python package. NOT BLOCKED. "
        "Naming follows the unprefixed domain-noun convention of user_events/ "
        "and session_log/. Stdlib-only policy core, so watch.py and "
        "dreamhub.py can import it without breaking their stdlib contracts."),
    EPIC_WATCH: (
        "Layer 2 of the plan — the watch.py POST /speech-token route. NOT "
        "BLOCKED. One handler plus one line in WRITE_ROUTE_HANDLERS."),
    EPIC_WEBUI: (
        "Layer 3 of the plan — the command composer dictation UI. BLOCKED on "
        "the React conversion (#630), exact precedent #823. This epic carries "
        "a task_group_dependency edge needing task #630; every task in it "
        "inherits the block."),
    EPIC_HUB: (
        "Layer 4 of the plan — Dreamhub sign-in and voice statistics. BLOCKED "
        "on the hub gaining a write surface (no do_POST today). That blocker "
        "has no task endpoint and so cannot be a graph edge; it is recorded "
        "in the task bodies."),
}


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _find_milestone(store) -> int | None:
    """Return the id of a milestone titled MILESTONE_TITLE, or None."""
    row = store.groups._session.execute(
        "SELECT id FROM task_group"
        " WHERE kind = 'milestone' AND title = ?",
        (MILESTONE_TITLE,),
    ).fetchone()
    return None if row is None else int(row[0])


def ingest(store, *, at: str | None = None,
           react_gate_task: int = REACT_GATE_TASK) -> dict:
    """Run the ingestion inside the caller's transaction.

    Returns a dict describing everything created (ids by key).  Raises on any
    failure; the caller's transaction context rolls the whole run back.

    ``react_gate_task`` is the task id the Web-UI epic depends on (the real
    React umbrella #630 in production; tests pass a placeholder they filed).
    """
    at = at or _now()
    existing = _find_milestone(store)
    if existing is not None:
        raise Conflict(
            f"refusing to double-ingest: milestone {MILESTONE_TITLE!r} already"
            f" exists as group #{existing}. A prior run succeeded; re-running"
            " would create a second copy."
        )

    created: dict = {"groups": {}, "tasks": {}, "edges": []}

    # 1. milestone + four epics (parented to the milestone)
    milestone_id = store.groups.create(
        kind="milestone", title=MILESTONE_TITLE,
        description=(
            "Live voice dictation for Dreamwork. A mic button in the command"
            " composer that opens a dictation mode: enlarged input, live"
            " transcript, and a 60fps mirrored frequency spectrum. Audio never"
            " touches a Dreamwork server — the browser streams straight to the"
            " provider; Dreamwork only mints an ephemeral token server-side."
            "  Ingested from ~/.claude-p/plans/delightful-munching-barto.md"
            " (#842). Four epics = the plan's four layers; 13 tasks A-M."
        ),
        actor=ACTOR, at=at,
    )
    created["groups"]["__milestone__"] = milestone_id

    epic_ids: dict[str, int] = {}
    for title in (EPIC_VOICE, EPIC_WATCH, EPIC_WEBUI, EPIC_HUB):
        epic_ids[title] = store.groups.create(
            kind="epic", title=title,
            description=EPIC_DESCRIPTIONS[title],
            actor=ACTOR, at=at, parent_id=milestone_id,
        )
    created["groups"]["__epics__"] = epic_ids

    # 2. file the 13 tasks, capturing AUTOINCREMENT ids by key
    for spec in TASKS:
        new_id = store.tasks.file(
            spec["title"], spec["body"],
            priority=spec["pri"], type=spec["type"], origin="human",
            actor=ACTOR, at=at,
        )
        created["tasks"][spec["key"]] = new_id

    # 3. memberships: each task joins its epic AND the milestone (so the
    #    milestone's subtree rollup sees every task directly and per-epic).
    for spec in TASKS:
        tid = created["tasks"][spec["key"]]
        store.groups.add_task(epic_ids[spec["epic"]], tid, actor=ACTOR, at=at)
        store.groups.add_task(milestone_id, tid, actor=ACTOR, at=at)

    # 4. task->task edges in v001's `depends` (no public write verb — #841 §7)
    session = store.groups._session
    for dependent_key, needs_key in TASK_EDGES:
        dependent = created["tasks"][dependent_key]
        needs = created["tasks"][needs_key]
        session.execute(
            "INSERT OR IGNORE INTO depends (task, needs) VALUES (?, ?)",
            (dependent, needs),
        )
        created["edges"].append(
            ("depends", dependent_key, dependent, needs_key, needs))

    # 5. group->task edges (task_group_dependency): the React gate.  The gate
    #    task id comes from the parameter (real #630 in production; a
    #    placeholder in tests) — GROUP_TASK_EDGES names only WHICH epics carry
    #    a gate, keeping it the single declarative source of that fact.
    for epic_title, _default_gate in GROUP_TASK_EDGES:
        eid = epic_ids[epic_title]
        dep_id, status = store.groups.add_dependency(
            dependent_group_id=eid, needs_task_id=react_gate_task,
            actor=ACTOR, at=at,
        )
        created["edges"].append(
            ("task_group_dependency", epic_title, eid, react_gate_task, dep_id))

    return created


def render_tree(store, created: dict) -> str:
    """Human-readable view of the ingested tree for coordinator review."""
    lines: list[str] = []
    mid = created["groups"]["__milestone__"]
    epic_ids = created["groups"]["__epics__"]

    def _task_line(tid: int, indent: str) -> str:
        row = store.groups._session.execute(
            "SELECT id, type, priority, state, title FROM task WHERE id = ?",
            (tid,),
        ).fetchone()
        return (f"{indent}- task #{row[0]} [{row[1]}/{row[2]}/{row[3]}]"
                f" {row[4]}")

    lines.append(f"milestone #{mid} {MILESTONE_TITLE}")
    for title in (EPIC_VOICE, EPIC_WATCH, EPIC_WEBUI, EPIC_HUB):
        eid = epic_ids[title]
        lines.append(f"  epic #{eid} {title}")
        children = store.groups.children(eid)
        member_ids = [c.id for c in children if c.kind == "task"]  # none — tasks are members not children
        # tasks are members, not child groups; list by membership
        tids = [int(r[0]) for r in store.groups._session.execute(
            "SELECT task_id FROM task_group_member WHERE group_id = ?"
            " ORDER BY task_id", (eid,),
        ).fetchall()]
        for tid in tids:
            lines.append(_task_line(tid, "    "))

    lines.append("")
    lines.append("Dependency edges:")
    # depends
    dep_rows = store.groups._session.execute(
        "SELECT task, needs FROM depends ORDER BY task, needs"
    ).fetchall()
    # map id->key
    id_to_key = {v: k for k, v in created["tasks"].items()}
    for task_id, needs_id in dep_rows:
        tk = id_to_key.get(task_id, "?")
        nk = id_to_key.get(needs_id, "?")
        # only show the ones we created (live store has 23 others)
        if tk != "?" and nk != "?":
            lines.append(f"  depends:   task {tk}(#{task_id}) -> {nk}(#{needs_id})")
    # task_group_dependency (ours)
    for epic_title, gate_task_id in GROUP_TASK_EDGES:
        eid = epic_ids[epic_title]
        lines.append(
            f"  group dep: epic #{eid} ({epic_title}) needs task #{gate_task_id}"
            f" (React gate)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--ledger", required=True,
                   help="path to the ledger SQLite store (a COPY from live)")
    p.add_argument("--dry-run", action="store_true",
                   help="open READ-only and print what would be created;"
                        " does not write")
    args = p.parse_args(argv)

    path = Path(args.ledger)
    if not path.exists():
        sys.stderr.write(f"ingest: store not found at {path}\n")
        return 1

    spec = dreamwork_store_spec(path)
    if args.dry_run:
        # A dry run cannot show AUTOINCREMENT ids without writing; it reports
        # the structure (groups, edge sets, ruling presence) instead.
        with open_database(spec, access=Access.READ) as store:
            existing = _find_milestone(store)
            if existing is not None:
                sys.stderr.write(
                    f"ingest: milestone already exists as #{existing};"
                    " dry-run would refuse (prior run succeeded)\n")
                return 2
        sys.stdout.write(_dry_run_report() + "\n")
        return 0

    try:
        with open_database(spec, access=Access.WRITE) as store:
            with store.transaction() as tx:
                created = ingest(tx, react_gate_task=REACT_GATE_TASK)
        # Re-open READ to render the committed tree for review.
        with open_database(spec, access=Access.READ) as store:
            sys.stdout.write(render_tree(store, created) + "\n")
            _print_progress(store, created)
        return 0
    except Conflict as exc:
        sys.stderr.write(f"ingest: {exc}\n")
        return 2
    except (NotFound, ValidationError) as exc:
        sys.stderr.write(f"ingest: {exc}\n")
        return 1


def _dry_run_report() -> str:
    lines = ["DRY RUN — structure that would be created:"]
    lines.append(f"  milestone: {MILESTONE_TITLE}")
    for title in (EPIC_VOICE, EPIC_WATCH, EPIC_WEBUI, EPIC_HUB):
        lines.append(f"    epic: {title}")
    lines.append(f"  tasks: {len(TASKS)} (keys {[t['key'] for t in TASKS]})")
    lines.append(f"  depends edges (task->task): {len(TASK_EDGES)}")
    for d, n in TASK_EDGES:
        lines.append(f"    {d} -> {n}")
    lines.append(f"  group->task edges: {len(GROUP_TASK_EDGES)}")
    for epic, gate in GROUP_TASK_EDGES:
        lines.append(f"    epic '{epic}' needs task #{gate}")
    lines.append("  rulings embedded verbatim in task bodies: C, E, F, G, K, M")
    return "\n".join(lines)


def _print_progress(store, created: dict) -> None:
    """Report progress() for the milestone — the partial-forever case."""
    mid = created["groups"]["__milestone__"]
    from dreamwork_db.groups import EmptyGroup
    try:
        prog = store.groups.progress(mid)
        sys.stdout.write(
            f"\nprogress(milestone #{mid}):"
            f" {prog.completed_count}/{prog.total_count} landed,"
            f" completed={prog.completed},"
            f" empty_group_ids={list(prog.empty_group_ids)}\n"
        )
    except EmptyGroup as exc:
        sys.stdout.write(f"\nprogress(milestone #{mid}): EmptyGroup — {exc}\n")
    # blockers on the web-ui epic to show the inherited #630 gate
    epic_ids = created["groups"]["__epics__"]
    eid = epic_ids[EPIC_WEBUI]
    blockers = store.groups.blockers(group_id=eid)
    sys.stdout.write(
        f"blockers(epic #{eid} {EPIC_WEBUI}):\n"
        + "".join(f"  {b}\n" for b in blockers)
        + ("  (none)\n" if not blockers else "")
    )


if __name__ == "__main__":
    sys.exit(main())
