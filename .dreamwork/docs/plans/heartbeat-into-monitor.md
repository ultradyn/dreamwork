# One watcher, one wake path — rolling the heartbeat into the monitor (#205)

Human-proposed 2026-07-25 17:45 ("roll the heartbeat tool into the
monitor for webui / dreamhub messages... then we can control when the
heartbeat triggers more readily, too"). He suspected the combined shape
already existed in ez-feedback-pipeline. It does, and it is better than
what this target runs. Read, not reinvented — per the ledger's note.

## The reference implementation, located

`sshr-xgame/src/ez-feedback-pipeline/backend/ezfb/watch.py` — the whole
design is `run_watch()` (line ~510) and four constants (~342-371):

- **The heartbeat is a timeout on the receive, not a second process.**
  `_receive_with_timeout(ws, heartbeat_s)`: an event arriving wakes the
  consumer; 285s of nothing emits `HEARTBEAT beat=N idle=Ns`. One loop,
  so "the loop controls when the heartbeat triggers" falls out for free.
- **A tick line is deliberately unlike an event line** (`heartbeat_line`
  docstring): consumers grep EVENT, and a heartbeat that looked like one
  would make "still alive, nothing happened" indistinguishable from
  "something happened".
- **A quiet limit.** After `HEARTBEAT_LIMIT = 7` consecutive quiet beats
  (~33 min) the beating STOPS and `on_quiet` fires once — "past that
  nobody is coming, and holding a cache warm indefinitely is pure waste;
  the watch itself keeps running, so no event is missed." ezfb's CLI uses
  the seam to compact the host agent.
- **Any traffic resets both** beats and quiet.
- Reconnect machinery (terminal-vs-transient, backoff with floor and cap,
  healthy-session ladder reset) — not needed for local file tails, but
  the *naming* of states is worth stealing.

## What this target runs today, and why it is worse

Three independent monitors: `heartbeat 4.75m` (fires regardless of
whether anything happened), a tail on `watch-events.log`, a tail on
`coord-inbox.md`. Today the timer fired ~40 times and most arrived
mid-increment or mid-steer, where the right action was nothing — the
loudest input and the least informative. Worse, SKILL.md carries a
standing warning that an unarmed events tail silently loses a `do now:`;
three things to arm is three chances to arm two.

## The build

One vendored, stdlib-only `dreamwatch.py` (sibling to `heartbeat.py`,
same #125 reasoning), run under a SINGLE Monitor invocation:

1. Tails N sources (watch-events.log, coord-inbox.md; later dreamhub and
   gh cursors) with a poll timeout equal to the heartbeat interval.
2. Source line → emitted with its source named (the EVENT form).
3. Timeout → `tick n=N idle=Ns` (the non-event form; the flow prompt
   stays in the line as it does today).
4. N consecutive quiet ticks → ONE `going-quiet` line, then silence;
   tailing continues, any event resumes ticking. The going-quiet line is
   the `on_quiet` seam — and the natural place to tell the agent to run
   #200's self-audit, which is ezfb's compact-the-host use almost
   verbatim.
5. Interval, limit, and schedule live in DREAMWORK.md's Routines line
   (his "patterns and schedules"), read at arm time.

Then: initialization.md arms ONE monitor instead of three; SKILL.md's
unarmed-tail warning becomes "if the watcher is not armed, nothing is" —
a single truth instead of a checklist.

## Constraints that must survive into the code as comments

- **The interval has a ceiling: the prompt-cache TTL.** 4.75m sits under
  the usual 5-minute TTL and that is why the loop is cheap. Backoff and
  schedules may LENGTHEN silence only past the quiet limit, where the
  cache is already forfeit — never stretch the beating interval past the
  TTL and pay full price on every tick. State it in the file; do not
  discover it on a bill.
- **Going quiet must be loud once.** One line announcing it; a watcher
  that just stops ticking is indistinguishable from a dead one (#144's
  lesson, and ezfb prints the RECONNECT/HEARTBEAT state for the same
  reason).
- **A tick must never look like an event** — ezfb's rule, verbatim.
- The watcher itself never parses event contents (parse is the step
  submissions.log exists to survive; same posture here).

## Open, in order of consequence

1. Does the harness Monitor re-arm the same way across session restarts
   for one long-lived process as it does for `heartbeat`? (heartbeat.py
   answered this once; check its notes before assuming.)
2. Migration shape: existing targets have three monitors documented in
   initialization.md — the change is a migration entry (arm-one instead
   of arm-three) plus the SKILL.md warning rewrite, same commit.
3. Whether coord-inbox tailing stays here or moves to relay.py's
   write-then-wake (#150 audited it) — do not build both.
