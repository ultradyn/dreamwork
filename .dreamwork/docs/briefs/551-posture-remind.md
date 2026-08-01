# Brief #551 — posture section: 'remind' link-btn replacing the ambient override note

**Task** (ledger #551, origin human, receipt 1beb8f1b): Max via watch
do-next 19:15:40 — *"delegate to subagent: Posture section needs a
'remind' link-btn that will send a reminder message to the main
dreamwork agent. That reminder message should contain the posture and a
reminder of where to look for the meaning of each choice (how to
interpret posture settings). The 'override' text doesn't seem useful
unless there's a change pending, so replace the ambient 'override' with
the 'remind' link-btn. Once pressed, there should be visual confirmation
and the user should not be able to retrigger it for at least 10s."*

## Scope

Two parts, one lane, both in `watch.py` (plus one guard + tests):

### 1. Client — the `#posture-src` slot

Today `.posture-head` carries the `posture` label and a `#posture-src`
div whose text is one of three states (`paintPostureSelection`
watch.py:5489-5502 @ dc739001; initial render `posturePicker` watch.py:5760-5768 @ dc739001):

- **armed** (a posture change is pending): `arming override…`
- **ambient, file source**: `override · .dreamwork/posture`
- **ambient, derived**: `derived from run mode · pick a stop to override`

The steer's ruling: the ambient text is not useful; only the armed
state earns words. So:

- **Armed state: unchanged.** While the shared 10s arm is live, the slot
  keeps `arming override…` exactly as today.
- **Both ambient states: replaced by a 'remind' link-btn** — a
  `<button type="button">` (actions are buttons, not anchors) styled as
  the dim-link idiom already in the panel family (cf. the
  `all N reviews →` line at watch.py:4063 @ dc739001; spare, lowercase-leaning
  voice). Label: `remind`.
- **On press**: POST `/remind` (part 2). On a 202 `ok` response, visual
  confirmation in the slot (e.g. `sent · the loop has been reminded` —
  match the panel voice) and the button **cannot be retriggered for at
  least 10s** (disabled, visibly at rest — not pointer-events trickery).
  After the cooldown the slot returns to `remind`.
- **The cooldown/confirmation state lives in module-scope JS**, exactly
  like `postArmTimer`/`postArmUntil` (watch.py:5504-5520 @ dc739001) — never read
  back from the DOM. The dashboard live re-renders `posturePicker` from
  data; a re-render mid-cooldown must repaint the confirming/disabled
  state, not resurrect a clickable `remind`.
- **transitions.md — read it first.** The ambient↔armed swap, the
  press→confirmation change, and the cooldown→ready return are all
  transitions: they arrive and depart, reusing an existing idiom.
  `transitions.md` is **coordinator-owned**: do not edit it; FLAG any
  proposed text in your final report.

### 2. Server — `POST /remind`

- New `_handle_remind(self)` beside `_handle_posture`
  (watch.py:14786), registered in `WRITE_ROUTE_HANDLERS`
  (watch.py:14927). E2's every-write-route-commits-a-receipt test
  derives from those keys, so the table entry IS the receipt coverage;
  `do_POST` preflight (Host/Origin, bounded body, #199 witness) comes
  free.
- Body: no schema — `{}`. A non-empty body that is not JSON is
  `_reject("malformed_json")` (the `_handle_deploy` shape,
  watch.py:14908-14911).
- The message is **composed server-side** (the client sends nothing but
  the press). It contains, in one short paragraph:
  - **which target** — the repo path or `_target_id(target)`, because
    the coordinator inbox is shared across every dreamwork target on
    this host and a posture without its project is ambiguous;
  - **the resolved posture** — `resolve_posture(target)`
    (watch.py:13574): pace, asking, delegation with its label
    (`lint.delegation_posture` via the `_posture_vocab()` lazy import),
    delivery, orchestration, and source (`override · .dreamwork/posture`
    / `derived from run mode`);
  - **the where-to-look pointer** — the meaning of each choice lives in
    `SKILL.md` § *"Run mode (#290) and posture (#445)"*; the stop
    vocabularies in `lint.py` (`POSTURE_STOPS_*`); the run-mode
    derivation in `lint.derive_posture`.
- Delivery: `relay.relay("coord", body, sender="watch")` — `relay.py`
  sits at repo root; import it lazily mirroring `_posture_vocab()`
  (watch.py:425). relay appends a clock-stamped
  `[watch YYYY-MM-DD HH:MM]` line to
  `~/.cache/agent-comms/ud-dreamwork/coord-inbox.md`, which the
  coordinator's monitor tails — **the append IS the delivery**; do not
  also write a watch-events.log line.
- **Test seam**: `relay.relay` takes `inbox_dir=` — the handler resolves
  the inbox dir through a module-level override (the
  optional-callable/dir pattern at watch.py:11073) so tests redirect it
  and never touch the real inbox.
- Response: `_send_receipt(json.dumps({"ok": True, ...})`, …)` naming
  what was sent (the posture point), so the receipt body is informative.

## Hard contracts (all were bugs before)

- **Red-first per part.** Name the production line each check depends
  on, sabotage it, watch the named check fail, cp-restore byte-identical
  (never `git checkout`). The coordinator runs the *independent* red at
  the merge gate on a line you did NOT inject. Assert preconditions your
  check depends on at runtime (e.g. the fixture's posture source really
  is what the assertion assumes) — never a literal tuned to today's
  fixture.
- **pytest** (wherever write routes are covered — test_watch.py /
  test_user_events.py): POST `/remind` → 202 + `ok`; the redirected
  inbox file contains the target id, all five axes, and the SKILL.md
  pointer; a malformed non-empty body → durable rejected receipt. Assert
  the seam redirected (the real `~/.cache/agent-comms` path never
  appears in the test's writes).
- **Browser guard** `dev/capture/remindbtn.mjs` (new, own fixture
  server): ambient slot shows the `remind` button; click → exactly ONE
  POST `/remind` observed; confirmation visible; control disabled; a
  second click inside 10s sends NO second request; after the cooldown
  the control is armed again. (Waiting out a real 10s is fine; guards
  already wait longer for less.) Solo runs only:
  `DREAMWORK_GUARDS="remindbtn" DREAMWORK_HUB_GUARDS= just guards <port>`
  after `ss -ltn` shows your chosen 39890-39899 port free. Record the
  port.
- **Guard registration is coordinator-owned** (`justfile`
  DEFAULT_GUARDS, #377): you author and prove the guard; the coordinator
  adds `remindbtn` to DEFAULT_GUARDS in the merge commit. Name this in
  your handoffs line so the merge doesn't forget it — an unregistered
  guard gates nothing and lint will red on the orphan.
- **watch-design.md is coordinator-owned.** Do not edit it. Write the
  design-record paragraph for this change (the slot's three-state
  contract, the link-btn idiom, the 10s no-retrigger, the route) in the
  file's voice into your final report as a FLAG; the coordinator lands
  it in the merge gate.
- **NEVER `read_file` an image** (glm-5.2 API 400 kills the lane).
  Screenshots go to your scratch outdir; the coordinator renders the
  visual verdict.
- **ONE `.dreamwork/handoffs.md` `## Pending` line** appended before your
  final commit (#398 obligation): id, sha, date, lane name, what landed,
  red proofs, the DEFAULT_GUARDS reminder, flags.
- **Commit with `git commit --only <paths>`**; new files need
  `git add <file>` first. Never `just test` / full suite; never attn;
  never `pkill -f`.

## Lane-owns declaration

You own: the posture client region of `watch.py` (`posturePicker`,
`paintPostureSelection`, the `.posture*` CSS, the new module-scope
cooldown state), the new `_handle_remind` handler + its
`WRITE_ROUTE_HANDLERS` entry, your new test additions, one guard file
`dev/capture/remindbtn.mjs`, and your handoffs line.

You do NOT own: `watch-design.md`, `transitions.md`, `justfile`,
`lint.py`, `file-formats.md`, `relay.py` (it already does everything you
need — if you believe it doesn't, FLAG instead of editing), any other
region of `watch.py`.

**Fleet**: no other lane is in flight; merges should be clean, but keep
edits tight to the named regions anyway.

## Report shape

Final report: commits; red-proof evidence per part (what you sabotaged,
which named check failed, restore verification); pytest and solo-guard
verdict lines; the FLAG paragraphs for watch-design.md (and
transitions.md if any); the port used; the exact message format the
route composes (so the coordinator can recognise it in its inbox); any
deviation from this brief with the reason.
