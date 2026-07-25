# Questions for the human

## Open

- **2026-07-25 — the shader's ambient density changed unasked.**
  Fixing the world-space anchoring (#91 item 2, your
  "deterministic across split tabs" ask) required dropping the
  per-viewport normalisation: a pattern that rescales to window height
  cannot be the same dream at the same screen position. So the main
  page's ambient density is now slightly different from what you had
  been looking at. Whisper-level — the dreamer checked 820px and 1300px
  — and one constant reverts it (`WORLD_SCALE`, was `2.3/innerHeight`,
  now `2.3/900`). Raised in chat 2026-07-25 ~08:50 and recorded here
  late, which was my lapse: a judgement call that only lives in chat is
  not recorded. Rec: keep it — it is entailed by what you asked for, and
  the alternative is giving up the shared field.
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
- **2026-07-25 — ud-dreamtask design review (#50).** Rich artifact:
  `.dreamwork/review/ud-dreamtask.html` (garden vs errand side by side,
  the harvest story, the four decisions each beside their alternative).
  Plan behind it: `.dreamwork/docs/plans/ud-dreamtask.md`. Recs:
  standalone before sub-loop; same 4.75m heartbeat regardless of task
  size; `~/.config/dreamwork/tasks/<slug>/` confirmed; guardrails
  inherited by reference, not restated. Build waits on your read.
  - **Follow-up (via watch, 2026-07-25 08:51):** the scroll bar for the .html needs styling too. the way this whole page is laid out is great though.
## Answered

- **Goal hierarchies (#95)** → "rec" via watch (2026-07-25 09:13): all
  three recommendations taken. Session goals do not persist beyond
  status.json — a session goal that outlives its session was a durable
  sub-goal all along, and wrap promotes it into DREAMWORK.md. Selection
  *states* the chain rather than enforcing branch focus, at least first.
  Task `parent` is free text matching DREAMWORK.md headings. Building
  per the stages in `docs/plans/goal-hierarchies.md`.
  - **Note (human, via watch, 2026-07-25 09:13):** "the notes i left
    appear in the design review question text in the webui. they should
    be demarcated as notes in the file if they're appended (or wherever
    they're stored they should have some tag or be oviously user notes,
    not something written by a dreamer)" — became task #109; the file
    half landed in 04968d1 with migration 2026-07-25-11, and the
    rendering half is with the dreamer.
- **Forge presence: three polarities** → "rec" via watch (2026-07-25
  08:48), all three recommendations taken, all three acted on the same
  hour. (a) `ud-dreamwork-github` is loaded for this target; its
  discovery pass wrote `.dreamwork/docs/github-processes.md` and its
  settings (watch all open issues/PRs, no authority lines so read-only,
  auto-progress on) are recorded in DREAMWORK.md. (b) Push policy is now
  session wrap + on ask, in DREAMWORK.md's Autonomy line. (c) A minimal
  `README.md` exists; doc-map records SKILL.md as the harness entry
  point and README.md as the forge one.
- **ud-dreamwork-github design review** → LGTM (2026-07-25 06:54), v1
  built the same morning; the 90s poll became ~5min on his follow-up.
  Detail lives in `docs/plans/ud-dreamwork-github.md` and the plugin's
  own SKILL.md.
- **#36 alignment review shape · #37 roll.py timing · dogfood reflection
  · Task D flow diagram** → all answered and applied 2026-07-25; each
  now lives where it acts (the review routine in SKILL.md, roll.py and
  its migration, `wrap up` and the maintenance rotation). Task D stays
  vetoed — a second copy of the selection ladder would drift, and it
  drifted four times today; revisiting it is task #119.
