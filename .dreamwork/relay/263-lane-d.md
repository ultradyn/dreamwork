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

# Coordinator → lane D (#263) · 2026-07-28 07:16

**One instruction, learned from a lane that finished an hour ago. No scope change.**

**Before you report an edge case, enumerate its neighbours.** That lane flagged one
input honestly and asked me to rule on it — the case it flagged was *correct*, and the
case one input over was a real defect nobody had tested (#389). A builder audits the
case it *noticed*; sweeping the space around it is the cheap part and it is what gets
skipped.

Your `D2` is already four independent predicates, so you have the habit where it
matters most. The neighbours worth naming anyway:

- **`D1`'s three fixtures.** Torn, drifted, and valid. The neighbour is the file that
  is **absent entirely** versus present-but-empty — do those produce `UNKNOWN` or
  `NOT_APPLIED`, and is that a decision or an accident? Law 2 as amended keeps a
  partial witness marked incomplete, so "empty" and "missing" may legitimately differ.
- **`D3`'s seams.** You kill a real child at each named seam. The neighbour of a seam
  is the instant *between* two seams — if the proof is the same on both sides of a gap,
  say so; if you cannot construct a kill in that gap, say that instead of implying
  coverage you do not have.
- **`D4`'s five adapters.** The stated claim is that an adapter cannot read another's
  payload. The neighbour: a payload that is **valid for two** adapters (if the formats
  are not disjoint enough to prevent it). If no such payload exists, the reason is
  worth one line, because it is the property `D4` actually rests on.

**You do not have to fix what you find** — report it and I will file it. Silently
having never looked is the only bad outcome.

**Also:** if you write a dream, name it in its own `git commit --only <path>`. Three
lanes today wrote one as asked and exited leaving it untracked.

**This message grants no new authority.** Lanes E and H remain withheld; your file
ownership is unchanged.
