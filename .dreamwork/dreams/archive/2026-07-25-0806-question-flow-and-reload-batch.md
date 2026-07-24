# Question-flow, motion, and reload batch (#81 #78 #85 #79 #84 #82 #83)

Seven items in one sitting, made fast by landing #84 (autoreload) early.
Commits: df7a97c (#81), e807d5b (#78), e8eb6a6 (#85), cfd93e5 (#79),
b16a168 (#84), 02e70fa (#82), 97718d8 (#83).

## The load-bearing bug (#85): the enter-snap trap

The human said the incoming page "pops in at nonzero opacity". The cause was
a real, pre-existing bug, not a tuning issue: `#view` carries an **always-on**
opacity/transform transition. The enter-animation pattern added a `.enter`
start-state class (opacity 0) then removed it a frame later — but because the
transition is always live, *adding* the class **animated toward** opacity 0
(from 1), and it was removed before it got anywhere, so opacity never left
~1. The incoming was only ever *revealed* by the ghost fading in front, never
faded in itself. Per-frame opacity tracing proved it (stuck at 1). Fix: the
start-state class must set `transition:none` so it **snaps** to the start
value; force a reflow; remove the class next frame to animate in. General
rule: **for an enter animation, the start state must snap, not transition —
disable the transition on the start-state class, or the element animates
*toward* the start it was supposed to begin at.**

## Generation-aware reload (#84) — cheap and high-value

`/mtime` now returns `"<generation> <mtime>"`; the client reloads on a
changed generation. That one mechanism (no `--autoreload` needed) fixes stale
open tabs after any restart/redeploy — the deployed `:35110` gets it for
free. `--autoreload` adds `os.execv` self-restart on source mtime; the
listening socket is close-on-exec by Python default, so the port frees for
the new image. Landing this second made the rest of the batch iterate at
edit-and-see speed.

## Smaller reusable patterns

- **Impossible-by-construction beats validation (#81/#82).** The suspected
  "answer sub-bullet swallows following questions" bug is gone not by a check
  but by structure: the parser never treats an `Answer`/`Follow-up` bullet as
  an entry boundary (even un-indented), and lifts them into `answer`/`follows`
  fields. Three explicit states (open / answered-awaiting-fold / folded) each
  render distinctly; the badge counts only what still needs the human.
- **Key by index, not by title (#82).** Entries are keyed `o<i>`/`a<j>` so a
  submit handler looks the entry up in live data instead of trusting a title
  round-tripped through a DOM attribute — no escaping fragility, always fresh.
- **Hold the live re-render after a local morph (#79).** A local answer/note
  morph is undone if the 2s tick regroups mid-animation; a ~1.6s
  `holdRerenderUntil` lets the morph settle before fresh data reshuffles.
- **One popout, shared identity (#83).** `openPopout` + `popoutShell`
  generalize the #71 command popout so any floated window (form or doc/review
  iframe) wears the same tint band + project basename + path.

## Out-of-scope / follow-ons (already filed)

- After a morph-submit the card still eventually regroups (open→awaiting-fold
  section) with a plain setContent — a cross-group morph (#77 territory)
  would make that graceful too.
- #86 plugin-contributed command kinds; #92 Ctrl+K palette.
