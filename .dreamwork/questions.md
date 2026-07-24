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
  - **Follow-up (in-session, 2026-07-25 ~10:55):** a third polarity rides
    along — `doc-map.md` records "no public-facing README by design
    (skills are consumed in-harness, not browsed on a forge)", which the
    push made half-true. Same answer probably settles it: (c) does the
    repo want a README? Rec: yes but minimal — what the skill is, how to
    install it, where SKILL.md starts — while SKILL.md stays the entry
    point for the harness.

- **2026-07-25 — daemon-mode: stage-1 build go? (#96).** Brainstorm
  round complete — all five needs-Max decisions answered in-session
  (~09:45) and folded into `.dreamwork/docs/plans/daemon-mode.md`:
  herdr-preferred adapter runtime, web lifecycle rec, ssh swarm,
  channel plugins (+Discord/Teams, clawq as reference), PWA yes /
  Tauri deferred, metadreamer integrated. Remaining: a go on stage 1
  (dreamhub aggregator) — say the word and it gets a detailed plan +
  fresh dreamer.
  - **Follow-up (in-session, 2026-07-25 ~10:10):** a go was started
    then explicitly retracted ("please hold") — dreamhub is ON HOLD;
    do not plan or build until Max re-opens it.
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
