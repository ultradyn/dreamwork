# Brief — lane-342b: the `delivery` posture axis + per-kind wake routing in watch.py (#342 lane B)

**Lane-owns:** `watch.py`, `test_watch.py`, `file-formats.md`, `lint.py`,
`test_lint.py` — the posture-axis + routing + contract surfaces, all in the
same commits per house rule. Do NOT touch `user_events/` (lane A landed),
`apply.py`, `SKILL.md`, `.dreamwork/tasks.md`, or `watch-design.md` (if the
control seems to need a new token, STOP — reuse an existing one and say so).

**Model:** llmp-glm-5-2 · **Isolation:** worktree (coordinator merge-gates).

## Authority

`.dreamwork/docs/plans/delivery-modes.md` — READ IT FIRST. It is RULED
(2026-07-30 00:23): Q1 the ambiguous class batches as a whole; Q2 a fourth
posture axis `delivery` (`instant`|`batched`) in `.dreamwork/posture`, absent
= `instant`, urgent kinds pre-empt even in batched mode; Q3 the loop gates
urgency, plugins may suggest. Lane A (merged `59527090`) built the journal
read half: `Journal.events_since_cursor(consumer)` in `user_events/sqlite.py`
— you consume its EXISTENCE in tests only; you do not modify it.

## What to build (three surfaces, one policy)

**1 · The `delivery` posture axis.** Fourth axis in `.dreamwork/posture`,
closed set `instant` | `batched`, absent = `instant` (today's behaviour, so a
pre-axis posture file is identical). Mirror the exact contract of
`pace`/`asking`/`delegation` (`file-formats.md` §1124): per-tick re-read,
closed-set lint, `POST /posture` dual-write (file + one events line on real
change). **The `file-formats.md` posture row and the `lint.py` closed-set
widening land in the SAME commit as the parser change** — withholding lint
from a format change is how the tools disagree by construction (#402b).

**2 · Per-kind wake routing.** The receipt commit in `do_POST` stays
UNCONDITIONAL (the E3 invariant). The `watch-events.log` wake line's emission
becomes conditional on (kind, mode): `do-now` and `do-next` emit ALWAYS (even
in batched mode — a `do-now` that does not pre-empt is a `do-now` that lied);
`add-idea`, `maintenance`, plugin kinds, `/answer`, `/comment`, `/ask` emit
only in instant mode. Route at POST time — the handler knows `kind` before it
formats the line (design §"What changes in watch.py's command handlers"); no
journal shape change, no string-parsing `kind` back out of the body. Withheld
wake lines are the whole feature: the item rides the durable receipt and the
tick's cursor read drains it.

**3 · The dashboard control.** A chip beside the existing posture picker
setting `delivery`, behind the SAME shared 10s arm, emitting one
`delivery via watch: <mode>` events line on real change — the ceremony
`run-mode`/`posture` already use, not a second one. **transitions.md governs
its appearance and state changes** — reuse the posture picker's existing
idiom verbatim; authoring a second gesture is the failure CLAUDE.md names.
Read `transitions.md` and the posture-picker code before writing any UI.

## Constraints (hard)

- Red-first, small committed increments, `git commit --only <paths>` (new
  files `git add` first). Every increment's commit states what it is.
- Never `attn`, never `pkill -f`, never touch ports 35110 / 39880-39899.
  Run `pytest test_watch.py test_lint.py` + `python3 lint.py` only (no
  browser guards — they bind the guarded ranges).
- The main checkout's `.dreamwork/posture` is HIS live file — never read it
  for tests; use tmp fixtures. Never write to the main checkout at all.
- Q3: no plugin-self-grant mechanism in this lane. If the policy table wants
  a "suggested urgency" input, that is a NOTE in your report, not code.

## Acceptance criteria (measurable)

1. Posture parse: absent `delivery` → `instant`; `delivery: batched` parses;
   garbage value → lint WARN/ERROR per the existing closed-set idiom, and the
   parser falls back to `instant` (never crashes the tick).
2. Routing tests per kind × mode: with mode=instant, all kinds emit the wake
   line; with mode=batched, ONLY `do-now`/`do-next` emit. Assert the receipt
   commit happened in every case (spy/stub at the seam, and name the
   production line each test reds).
3. `POST /posture` with a `delivery` change dual-writes file + exactly one
   events line; a no-change POST writes neither (mirror the existing axis
   tests).
4. The dashboard control renders beside the posture picker and posts through
   the shared arm (assert in the generated source; the browser guards are
   the coordinator's merge-gate, not yours).
5. `file-formats.md` documents the axis; `lint.py` enforces the closed set;
   both in the parser's commit.
6. Full `pytest test_watch.py test_lint.py -q` green; `python3 lint.py`
   clean on your worktree baseline (the shim/store ERRORs are the documented
   worktree trap — compare against a master baseline, do not "fix" them).

## Hand-off obligation (#398)

Final report: what changed per commit, the red-run evidence (which test
failed on which injection, and the production line named), the per-kind ×
mode matrix as tested, and anything NOT done (the tick-consume loop habit is
the coordinator's, not yours). Commit in your worktree; coordinator merges.
Per #398 the hand-off lands in `.dreamwork/handoffs.md` (the coordinator
writes the main-checkout entry at merge time from your report).
