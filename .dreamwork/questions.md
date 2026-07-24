# Questions for the human

## Open

- **2026-07-25 — ud-dreamtask design review.** Incubation plan is at
  `.dreamwork/docs/plans/ud-dreamtask.md` with four open design
  questions (composition, heartbeat cadence, state-dir naming, guardrail
  inheritance — recs inline). Build waits on your read; answerable here,
  in-session, or via the watch dashboard.

## Answered

- **ud-dreamwork-github design review** → LGTM via watch (2026-07-25
  06:54), all four recs accepted; "check if anything recently changed is
  relevant" done — writing-plugins contract, bridge pattern, and doc
  single-source rule all post-date the plan and all reinforce it. v1
  built the same morning: `skills/ud-dreamwork-github/SKILL.md`,
  installed + indexed. Dogfood on a real repo is the follow-up task.
  - **Follow-up (in-session, 2026-07-25 07:18):** 90s poll too fast —
    ~5 min, carried by the heartbeat tick flow by default. Applied to
    the plugin SKILL.md same minute.
- **#36 alignment review shape** → Confirmed (2026-07-25): fresh-eyes
  dreamer, not-done-until-clean, rare cadence (marker + commits-since
  trigger). First pass dispatched the same night.
- **#37 roll.py timing** → Default applied (2026-07-25). The idea and its
  prioritization were explicit human steers — *whether* was authorized;
  the silence-default resolved only *when* (built on the next idle tick).
  Shipped with tests, wiring, and a migration entry.
- **Dogfood reflection: standing or one-off?** → Standing (2026-07-25):
  wired into `wrap up` and the maintenance rotation.
- **Task D (flow diagram): do or veto?** → Skipped (2026-07-25): second
  copy of the selection ladder would drift while it's evolving fast.
  Revisit as a `selection.md` reference file once selection stabilizes.
