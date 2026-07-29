# Brief — lane-493design: design the posture `autonomy` axis (#493)

**Lane-owns:** `.dreamwork/docs/plans/posture-autonomy-axis.md` ONLY (a new
design doc you create; the coordinator commits it). Read-only on everything
else. DESIGN ONLY — no code, no `lint.py`, no `file-formats.md`, no
`watch.py`; the doc itself must say what it does not authorise.

**Model:** llmp-glm-5-2 · **Isolation:** none needed (one new doc).

## The task (#493, his words)

From his #287 OQ4 ruling (2026-07-30 00:20): *"some options would be good,
like adding an autonomy level to posture for maintenance (which is probably
a good thing for us to do anyway; pls add a task)"*, and OQ5: *"probably an
autonomy level thing."* The axis gates two things the rulings parked on it:

- **OQ4:** autonomous dispatch of suite tools (`research`/`code-review`/
  `prototype`) — today flat-off (human-invoked only);
- **OQ5:** the loop self-filing loop-generated `to-spec`/`to-tickets` output
  without a human steer — today a human steer by default.

He also framed it as *"for maintenance"* — the autonomy level likely gates
the whole class of agent-initiated surfaces, not only the bridge's two.

## What to design (house style — follow it exactly)

Read `.dreamwork/docs/plans/delivery-modes.md` and
`.dreamwork/docs/plans/cli-warning-layer.md` for the house style: measured
facts first (READ the posture machinery — `file-formats.md` §1124,
`watch.py`'s posture parse/POST, `.dreamwork/posture` if readable — note
`.dreamwork/posture` is HIS live file: read-only, and prefer citing the
contract over the live values), then the contract, then what it does NOT
authorise, then open calls ONLY where a fork is genuinely his (his standing
rule: if every call has one clearly-superior answer, there are no open
questions), then a verification section naming each check's red line.

The contract questions the doc must settle or escalate:

1. **Axis name and closed set.** `autonomy`? Levels like
   `off | maintenance | full`? Define each level by what it PERMITS, in one
   line each. Absent = safest level (mirror the `delivery` precedent:
   absent = today's behaviour, so a pre-axis posture file is identical).
2. **What each level gates.** The enumerated agent-initiated surfaces:
   OQ4 tool dispatch, OQ5 self-filing, his "maintenance" framing (what IS
   the maintenance class — suite-tool runs? loop housekeeping? say which),
   and anything else the scope gate already governs (read the scope gate
   first — the axis must compose with it, not replace it).
3. **Composition with the existing axes.** `delivery` (RULED, in flight as
   #342 lane B) sets WHEN he is interrupted; `asking` sets how freely the
   loop asks; `autonomy` sets what the loop may DO unasked. State the
   orthogonality argument and any interaction (e.g. does `batched` +
   high-autonomy mean the loop does MORE unobserved?).
4. **Where it lives.** Posture axis (his word) — the doc should confirm the
   fit against the closed-set discipline and say what lands in the
   implementation commit (parser, file-formats row, lint closed-set,
   dashboard control — same shape as `delivery`).

## Acceptance criteria

1. One doc at the owned path, house style, with the "what this does NOT
   authorise" section naming every implementation surface it forbids.
2. Every load-bearing claim measured or cited (posture parse site, scope
   gate site, the two rulings verbatim).
3. Open calls: zero if every fork has a clearly-superior answer; otherwise
   only the genuinely-his forks, each with a rec.
4. The doc states it is design-only and authorises no code.

## Hand-off (#398)

Your final message is the report (the coordinator commits the doc and
writes `.dreamwork/handoffs.md`): what you designed, the open calls (if
any), and anything you deliberately left out.
