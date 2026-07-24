# Questions for the human

## Open

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
- **2026-07-25 — goal-hierarchies design review (#95).** Rich artifact:
  `.dreamwork/review/goal-hierarchies.html` (the tree, a worked chain
  from this morning's own work, the three decisions side by side with
  their alternatives). Plan behind it:
  `.dreamwork/docs/plans/goal-hierarchies.md`. Recs: session goals don't
  persist (wrap-time promotion into DREAMWORK.md instead); state the
  chain rather than enforcing branch focus, at least first; free-text
  parent names matching DREAMWORK.md headings. Build waits on your read.
  - **Follow-up (via watch, 2026-07-25 08:50):** the diagram here is
    really nice, we should be sure to remember it. / oh also note this
    text box scroll bar needs styling. *(Left on the ud-dreamtask card;
    moved here, since the diagram is this entry's artifact. Both acted
    on: the idiom is recorded in `watch-design.md` under review
    artifacts, and the scrollbar is task #101.)*
- **2026-07-25 — ud-dreamtask design review (#50).** Rich artifact:
  `.dreamwork/review/ud-dreamtask.html` (garden vs errand side by side,
  the harvest story, the four decisions each beside their alternative).
  Plan behind it: `.dreamwork/docs/plans/ud-dreamtask.md`. Recs:
  standalone before sub-loop; same 4.75m heartbeat regardless of task
  size; `~/.config/dreamwork/tasks/<slug>/` confirmed; guardrails
  inherited by reference, not restated. Build waits on your read.
  - **Follow-up (via watch, 2026-07-25 08:51):** the scroll bar for the .html needs styling too. the way this whole page is laid out is great though.
## Answered

- **Forge presence: three polarities** → "rec" via watch (2026-07-25
  08:48), all three recommendations taken, all three acted on the same
  hour. (a) `ud-dreamwork-github` is loaded for this target; its
  discovery pass wrote `.dreamwork/docs/github-processes.md` and its
  settings (watch all open issues/PRs, no authority lines so read-only,
  auto-progress on) are recorded in DREAMWORK.md. (b) Push policy is now
  session wrap + on ask, in DREAMWORK.md's Autonomy line. (c) A minimal
  `README.md` exists; doc-map records SKILL.md as the harness entry
  point and README.md as the forge one.
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
