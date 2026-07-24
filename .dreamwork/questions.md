# Questions for the human

## Open

- **2026-07-25 — forge presence changes two polarities.** The skill now
  lives at github.com/ultradyn/dreamwork (private, pushed on your ask).
  (a) DREAMWORK.md's Don't-load for `ud-dreamwork-github` said revisit
  on forge presence — load it for this target now? (Its tick-carried
  ~5min check would watch the repo's issues/PRs once any exist.)
  (b) Standing push policy: tonight's push was one-time explicit;
  should the loop now push each landed increment (or per-session), or
  stay commit-only-push-on-ask? Rec: (a) yes, load; (b) push at
  session wrap + on ask, not per-increment.

- **2026-07-25 — daemon-mode brainstorm (#96).** Big idea mapped at
  `.dreamwork/docs/plans/daemon-mode.md`: aggregator-first rec
  (dreamhub `/` list + `/{project}/` proxy over existing watch
  instances, zero loop changes), then supervisor daemon; needs-Max
  decisions listed (bg runtime, lifecycle authority, exposure,
  channels, PWA-vs-Tauri). Brainstorm with you before any plan.
- **2026-07-25 — goal-hierarchies design review (#95).** Incubation
  plan at `.dreamwork/docs/plans/goal-hierarchies.md`: one goal tree
  (DREAMWORK.md nested Goals → session goal → task goal metadata),
  active chain stated at task start, scope gate = "name the chain".
  Three open questions with recs (session-goal persistence via
  wrap-time promotion; state-only vs enforced branch focus; free-text
  parent names). Build waits on your read.
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
