# Questions for the human

## Open

- **2026-07-25 — may the dashboard read the session transcript? (#180).**
  You asked for a live stream of the dreamer's own events, scanned from
  the most recent session jsonl. Filed and specified — but one thing in
  it is yours to decide before anyone builds it.

  **The transcript contains everything**: your prompts, the agent's
  reasoning, and full tool inputs and outputs — file contents, command
  lines, whatever happened to be in the environment. Showing only
  "description lines" is a filter applied *after* the server has read
  and parsed the lot, so it is a promise about what is displayed, not
  about what is exposed. `watch.py` is localhost-only, which narrows
  this considerably; it does not settle it.

  Two shapes, and they differ in what exists rather than in what shows:

  - **Server reads the raw transcript, filters on the way out.**
    Simplest, and the whole file passes through a process that serves a
    browser.
  - **The loop writes derived event lines into the target, and the
    server only ever sees those.** More moving parts, and the raw
    transcript never enters the server at all. Also fixes the other
    problem — the transcript lives outside `--target`, and
    `resolve_confined` is load-bearing, so the first shape needs that
    gate widened.

  Rec: the second, because it answers the exposure question and the
  confinement question with one decision. But it is your data and your
  machine, and the first is materially less work.

- **2026-07-25 — ud-dreamtask stage 6 (harvest): go, or leave it?**
  Stages 1-5 shipped: the skill exists, is installed and indexed, walks
  its own procedure, and `newerrand.py` creates a dreamstate so an
  opening never hand-writes `questions.md`/`status.json` by hand.

  **Stage 6 is the only thing left and it is deliberately gated**,
  because it is the one part that reaches back into ud-dreamwork:
  dreamwork's init would read PAST dreamstates, so lessons an errand
  learned surface in the garden that spawned it. That means editing
  `initialization.md`, a migration, and probably `file-formats.md` and
  `lint.py` — new surface in the core loop, not in the sibling.

  Rec: **yes, but later.** The value is real (an errand's lessons
  currently die with its archive) and nothing else is blocked on it.
  But it widens the core loop's init, and today already added a linter
  step there. A week of using dreamtask will say more about what is
  worth harvesting than a design conversation will now.

  Answer "go" to plan it, or leave it and it stays parked.
  - **Note (human, via watch, 2026-07-25 14:34):** a note routed by the
    mode group
  - **Answer (via watch, 2026-07-25 14:34):** an answer routed by the
    mode group
  - **Follow-up (loop, 2026-07-25 14:35):** the 14:34-14:35 submissions on this entry
    read as UI tests, not answers — "traced answer for the regroup", "a
    note routed by the mode group". NOT folded, and this question stays
    OPEN. Recorded rather than deleted because they are his words and
    because a later reader would otherwise find an entry that looks
    resolved and is not.


- **2026-07-25 — how should an answer reach a loop on another machine?**
  You said "defer publishing repo for a bit", which answers an open
  question belonging to the dreamwork instance on **x-game**
  (`~/src/ez-feedback-pipeline`), not to this one: *"Publish the repo, so
  `npx skills add` works?"* — the single open entry in its
  `questions.md`.

  I asked in chat whether to append it there over ssh or leave it to you,
  and then failed to record the ask — so this entry exists partly as the
  fix for that. I have not touched that file: writing into another
  agent's live state uninvited is the thing this loop keeps telling
  dreamers not to do.

  **The narrow question**: shall I append your answer to x-game's
  `questions.md` over ssh, or will you drop it into that dashboard?

  **The general one, which is worth more**: there is currently no way for
  an answer you give in one place to reach a loop somewhere else. Today
  that is a one-line ssh append; with dreamhub and the ssh swarm it
  becomes routine, and it is exactly the surface where a wrong write
  corrupts another loop's record of what you want. Worth deciding as a
  rule rather than per-incident. Related: #96 stage 2+, #144, #150.
  - **Answer (via watch, 2026-07-25 14:34):** traced answer for the
    regroup
  - **Follow-up (loop, 2026-07-25 14:35):** the 14:34-14:35 submissions on this entry
    read as UI tests, not answers — "traced answer for the regroup", "a
    note routed by the mode group". NOT folded, and this question stays
    OPEN. Recorded rather than deleted because they are his words and
    because a later reader would otherwise find an entry that looks
    resolved and is not.

- **2026-07-25 — dreamhub URL space: one hub URL, or one per project?
  (#96).** Your `daemon-mode.md` sketch was `/` lists projects and
  `/{project}/…` reverse-proxies to that project's watch. The stage-1
  plan ships **origin-per-project** instead — the hub lists and links
  out, each project keeps its own port and its own URLs.

  Why, measured rather than argued: the watch page is root-absolute in
  three places, and only two of them can be patched from outside. The
  fetches and `pushState` can be shimmed; `routeOf()`/`isInternal()`
  compare `location.pathname` against string literals inside a
  generated JS string and cannot be reached. So under a path prefix a
  deep link renders the **wrong view, silently** — the worst available
  failure. `ssh -L` also gives a local port per remote project, so
  origin-per-project survives all the way into the swarm stage, and the
  prefix work belongs to #124's server-core seam where those three
  sites are being touched anyway.

  **Not blocking** — the build proceeds on the rec. Answer only if you
  want the single-URL bookmark badly enough to serialise stage 1 behind
  a `watch.py` change. Full reasoning:
  `.dreamwork/docs/plans/dreamhub-stage1.md`.
  - **Answer (via watch, 2026-07-25 14:35):** traced answer for the
    regroup
  - **Follow-up (loop, 2026-07-25 14:35):** the 14:34-14:35 submissions on this entry
    read as UI tests, not answers — "traced answer for the regroup", "a
    note routed by the mode group". NOT folded, and this question stays
    OPEN. Recorded rather than deleted because they are his words and
    because a later reader would otherwise find an entry that looks
    resolved and is not.

## Answered

- **What should the dashboard be called? (#172, #153)** → `(4) dreamwork
  · <status> · <extra>` via watch (2026-07-25 15:30). **The app name
  comes back**: #153 had dropped it on the argument that the favicon
  carries identity, and the answer settles it the other way. The layout
  principle stands separately — invariants (repo, branch) anchor hard
  right so a changing page title cannot shove them.

  Two things arrived with the answer and are now tasks. He asked what
  the `(4)` meant, and it was WRONG (#181): the count came from
  `status.json`'s `awaiting_human`, a list the coordinator maintains by
  hand, which had drifted from `questions.md`'s actual open count. A
  hand-maintained count is a claim; it now derives from the file he can
  look at. And the favicon is "too slow and does not look smooth" —
  which is #153's one-frame-per-second choice, correct for a hidden tab
  and wrong for the one he is watching (#182).

- **Should `/file` reflow markdown? (#158)** → "I think rec still
  though. i agree with only reflowing .md or similar. not source code"
  via watch (2026-07-25 15:23). Rec taken: `.md` and similar prose
  formats reflow at `/file`, source code stays verbatim, and the #102
  rule is rewritten in the same commit so the next reader sees it was
  reconsidered rather than forgotten. He noted `file-formats.md` needs
  it too — same case, same fix. He also added an idea with it, now
  #178: a pretty-print toggle for JSON, with syntax highlighting as a
  bonus. That is the right shape for a format that is neither prose nor
  code — reformatting it is a VIEW, so it gets a control rather than a
  default.

- **A goal the loop folded in on its own: "nothing fails quietly"** →
  "yes that sounds right" via watch (2026-07-25 14:20). Confirmed and
  kept in DREAMWORK.md's Goals. He added an idea with it, now #156: a
  PostToolUse hook that lints `questions.md` on edit, with error
  messages that say where the problem is, what it is, what was expected,
  and a brief description of the spec. That fires EARLIER than anything
  the loop has — at the moment of the malformed write, while the agent
  that made it can still fix it — and it bundles with #138, since both
  are Claude Code hooks and neither should ship alone.

- **Daemon mode: stage-1 build go? (#96)** → "go" via watch (2026-07-25
  10:48): the hold is lifted. Stage 1 is the dreamhub aggregator, per
  `docs/plans/daemon-mode.md` with its five in-session decisions
  (herdr-preferred adapter runtime, web lifecycle, ssh swarm, channel
  plugins, PWA yes / Tauri deferred, metadreamer integrated). Next: a
  detailed stage-1 plan, then a fresh dreamer. Note the earlier
  retraction is now spent — this is a second, deliberate go, so treat
  the plan as the thing being approved and check back before the build
  widens beyond stage 1.

- **ud-dreamtask design review (#50)** → "rec lgtm" via watch
  (2026-07-25 10:47): all four recommendations taken — standalone
  before sub-loop, the same 4.75m heartbeat regardless of task size,
  `~/.config/dreamwork/tasks/<slug>/`, and guardrails inherited by
  reference rather than restated. Unblocked; build per
  `docs/plans/ud-dreamtask.md`. The 08:51 follow-up (artifact
  scrollbars) landed with the artifacts' own scrollbar rules.

- **The shader's ambient density changed unasked** → "rec" via watch
  (2026-07-25 10:33): keep it. The world-space anchoring he asked for
  (deterministic across split tabs) is incompatible with a pattern that
  rescales to window height, so `WORLD_SCALE` stays at the constant
  `2.3/900`. No code change — the answer confirms what shipped.

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
- **Four early asks, all applied (2026-07-25)** — the alignment-review
  shape (#36), roll.py timing (#37), the dogfood reflection, and Task D's
  flow diagram. each
  now lives where it acts (the review routine in SKILL.md, roll.py and
  its migration, `wrap up` and the maintenance rotation). Task D stays
  vetoed — a second copy of the selection ladder would drift, and it
  drifted four times today; revisiting it is task #119.
