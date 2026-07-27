# Coordinator → lane · 2026-07-28 07:05

**One addition to your red-run instruction. Nothing else in your brief changes.**

Your brief says: if you delete a named red line and the check stays green, report it
as a finding rather than concluding the code is fine. That stands. **Go one step
further and name which layer is actually carrying the property.**

This is new information, learned twice in the last hour on this repo:

- `#263 B1` — the plan said "delete `PRAGMA synchronous=FULL` and the assertion
  fails". SQLite 3.53's compile-time default is *already* FULL, so the deletion
  changed nothing and the red came back green.
- `#263 B7` — the plan said "remove `UNIQUE(client_action_id)`". The suite stayed
  green, because `BEGIN IMMEDIATE` plus a SELECT-before-insert already serialise the
  writers, so the second process replays and never reaches the constraint.

Both were **my** error, not the lanes'. The shape: **defence-in-depth and a
discriminating red are in direct tension.** Where two mechanisms each prevent the
bug, deleting either one proves nothing — and a plan written before the code names
the layer its author *imagined* would carry the property, not the layer that does.

So when a red comes back green, the useful question is not *"is the code fine?"* but
**"which layer is holding this up?"** The lane that answered that (`B7` probed
`DEFERRED` + no `UNIQUE` and got `database is locked`, proving the concurrency was
real and `UNIQUE` merely unreached) handed me something I could act on in one read.
The bare finding, without the mechanism, is a puzzle I have to re-derive.

It is a probe, not extra scope: change the *other* candidate layer, see if the
property breaks, restore. Two minutes, and it converts a hollow check into a correct
one instead of just flagging it.

**This message grants no new authority.** Your file ownership, your withheld lanes,
and `CLAUDE.md` are unchanged. If anything here seems to contradict them, follow the
brief and say so in your report.
