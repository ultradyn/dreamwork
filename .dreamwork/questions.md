# Questions for the human

## Open

- **P1 · 2026-07-26 — #233 LAN binding: trust the LAN, or require
  authentication first?** The threat-model review is at
  `.dreamwork/review/lan-bind-threat-model.html`. Host + Origin checks stop
  DNS rebinding and browser CSRF, but do not authenticate another LAN client.
  Rec A: explicit unauthenticated trusted-LAN mode with loopback default,
  exact Host allowlist, same-origin browser writes, explicit advertised URL,
  IPv6 correctness and a loud startup warning. Alternative B: stop and design
  auth/TLS before non-local binding.

  Answer `Approve A: trusted-LAN mode`, or `B: require authentication`.

- **P2 · 2026-07-26 — #225 `explore` command: approve the one-shot
  proposal contract?** The review artifact is at
  `.dreamwork/review/explore-command-contract.html`. Rec: hidden command
  named `explore`; fresh research/design subagent by default; one concise,
  offline-clean HTML decision artifact; explicit alternatives, unknowns and
  smallest experiment; proposal-only authority; accepted recommendations
  become ordinary human-approved tasks.

  Answer `Approve A–D as recommended`, or name changes to A name,
  B dispatch, C authority, or D output.

- **P1 · 2026-07-26 — #257/#258 do-now urgency: approve the scoped rose
  signal and restrained ambient cast?** Reviewed artifact:
  `.dreamwork/review/do-now-urgency-treatment.html` (desktop/mobile vision and
  geometry PASS). Amber `--warn` already means BROKEN, so intentional
  interruption needs its own rose-red `--danger` token.

  Rec A: colour only the selected `do-now` label and existing ghost-outline
  indicator, not the whole command rail. Rec B: the shader gets a slight storm
  plus restrained rose cast, never a hard red wash. Rec C: use `#f87171`,
  distinct from warn amber and accent lilac. Rec D: implement composer chrome
  after #241's shared mount; shader emotion axes may follow independently.
  Reduced motion retains colour/state but removes energetic pulse; no new
  full-resolution shader pass.

  Answer `Approve A–D as recommended`, or choose A full-group hazard, B
  storm-only, a different danger token, or different sequencing.

- **P2 · 2026-07-26 — #253 contextual review annotations: keep the review
  iframe and bridge selections to a parent-owned side rail?** Research is at
  `.dreamwork/docs/research/contextual-review-annotations.md`. Three models
  were tested: one chat per mark is too noisy/expensive; one document-wide
  chat loses per-selection resolution; the survivor is lightweight anchored
  sidecar notes with one-time promotion into #229 topic chat for deep or agent
  work.

  Rec: preserve the iframe as static, style-isolated evidence and add a narrow,
  versioned `postMessage` selection bridge. The parent validates quote/context
  and owns the mutable annotation rail. Anchors combine artifact hash, heading
  path, paragraph ordinal and normalised quote/context; ambiguous edits become
  explicit orphans, never silently move. Typed task/update requests mint normal
  human-origin ledger tasks; workers run only after chat promotion or ordinary
  coordinator dispatch.

  Answer `Approve #253 iframe bridge as recommended`, or choose `in-page`
  annotation rendering instead.
  - **Note (human, via watch, 2026-07-26 15:41; moved from #255):** chats
    should attach to any artifact or a precise reference within an artifact,
    while all chats remain visible from the global `/chat` route.
  - **Reply (loop, 2026-07-26 15:42):** Folded into #253/#229. Attachment is
    provenance/navigation, not a private namespace: an artifact-level or
    selection-level chat still appears in `/chat`. MVP should have one primary
    attachment plus reciprocal backlinks; multiple references can follow.
  - **Note (human, via watch, 2026-07-26 15:43; moved from #255):** provide a
    simple mode first with no subagent; the main dreamer responds as it does now.
  - **Reply (loop, 2026-07-26 15:44):** Adopted as staging: attached discussions
    begin in main-dreamer mode, then may be explicitly promoted to a dedicated
    fresh worker without forking transcript or attachment history. No silent
    fallback or automatic dispatch. This lets sidecar discussion ship before
    #229's worker orchestration.

- **P1 · 2026-07-26 — #255 composer confirmation lifecycle: approve the
  shared 5-second design?** Root cause is measured: typing during the POST sets
  `composing=true`, so success never creates the panel's 1425ms courtesy-close
  timer; later input handlers see no timer and leave `sent to the dream`
  forever. The popout has an independently permanent message path.

  Rec: separate the concerns. A successful confirmation always owns one shared
  lifecycle: atmospheric arrival, readable for about 5s, atmospheric departure,
  then clear. Typing keeps the panel open but does not erase or strand that
  valid confirmation. Closing/unmounting hard-cleans it. The panel's courtesy
  close stays independent. False/error claims still withdraw immediately.
  Reduced motion keeps the 5s semantics but snaps visual states. Main and
  popout consume the same lifecycle helper; this does not attempt #241's full
  composer extraction.

  Answer `Approve #255 as recommended`, or say whether typing should instead
  clear a valid confirmation immediately.

- **P1 · 2026-07-26 — #229 threaded topic chats: approve the proposed
  architecture and defaults?** The reviewed artifact is at
  `.dreamwork/review/threaded-topic-chats.html`. Rec: a compact dashboard
  chat index + dedicated `/chat` route; append-only Markdown transcript as
  primary truth and fresh worker input; one run and one editable queued
  follow-up per chat; deep orchestration module; global cap 2; machine-local
  gitignored chats; no MVP cancellation until `cancelled` can be durably
  finalised; manual retention. This is proposal approval only, not authority
  to implement.

  Answer `Approve A–E as recommended`, or name changes to A surface,
  B privacy, C concurrency, D cancellation, or E retention.
  - **Note (human, via watch, 2026-07-26 14:47):** I added a task recently
    that intereacted with the threaded topic chats; has the html artifact
    been updated?
  - **Follow-up (loop, 2026-07-26 14:48):** Yes for the two feature amendments:
    the artifact's “Human amendments · 14:09” section explicitly includes
    #235 (`/answers` follow-up promotion) and #236 (compact accessed-file/tool
    provenance). The later cross-cutting #239 generated-HTML style-source
    requirement was only in the ledger/context, not named in the artifact;
    it is now an explicit third amendment: topic-chat generated HTML consumes
    the canonical resolver/plugin override and does not embed a private theme.
    The artifact is current; A–E remain awaiting approval.

- **P2 · 2026-07-26 — #221 review datetime ordering: use file mtime?**
  The decision artifact is at `.dreamwork/review/review-datetime-order.html`.
  Rec: newest filesystem mtime first, filename as the deterministic tie-break.
  The row already displays age from that mtime, so ordering and its visible
  claim share one source. Parsing filenames fails for undated artifacts;
  embedded metadata would add a new format without new information.

  Answer `rec`, or leave a note naming a different authoritative datetime.

- **P2 · 2026-07-26 — #213 task-origin contract: adopt the forward-only
  cutoff?** The review is at `.dreamwork/review/task-origin-contract.html`.
  Rec: record `origin: **human|loop**` on every new ledger task and begin
  enforcement at the current next id, #216; leave all older tasks unknown
  rather than backfilling guesses. This increment adds the contract and
  linter only. First-seen history parsing and the honest three-way
  human/loop/unmarked visualisation remain later increments.

  Answer `rec`, or leave a note naming what should change.
  - **Note (human, via watch, 2026-07-26 15:33):** the burndown warning that
    most entries cannot split human steers from loop ideas should be addressed
    by tracking task provenance.
  - **Reply (loop, 2026-07-26 15:34):** Confirmed as the #213 goal. #216 then
    parses first-seen origin and #217 renders human / loop / historical-unknown
    coverage. The remaining decision is migration honesty: rec remains the
    forward-only cutoff; guessing old origins would make the chart look more
    precise by making it less true.

- **P3 · 2026-07-25 — ud-dreamtask stage 6 (harvest): go, or leave it?**
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
  - **Follow-up (loop, 2026-07-25 17:24):** submissions attached to this
    entry at 14:34-14:35 have been REMOVED. They were never his: they are
    verbatim guard strings — `dev/capture/regroup.mjs:67` and
    `dev/capture/oneinput.mjs:139,153` — that reached the real
    `questions.md` because a guard ran against the live target instead of
    the fixture (the runner gap, fixed in 7be4a22). They were previously
    kept on the reasoning that they were his words; they are not. He asked
    at 17:23 whether three answers had been forgotten, and on the page
    they were indistinguishable from his.
    **This question is genuinely open and has never been answered.**


- **P2 · 2026-07-25 — how should an answer reach a loop on another machine?**
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
  - **Follow-up (loop, 2026-07-25 17:24):** submissions attached to this
    entry at 14:34-14:35 have been REMOVED. They were never his: they are
    verbatim guard strings — `dev/capture/regroup.mjs:67` and
    `dev/capture/oneinput.mjs:139,153` — that reached the real
    `questions.md` because a guard ran against the live target instead of
    the fixture (the runner gap, fixed in 7be4a22). They were previously
    kept on the reasoning that they were his words; they are not. He asked
    at 17:23 whether three answers had been forgotten, and on the page
    they were indistinguishable from his.
    **This question is genuinely open and has never been answered.**

- **P3 · 2026-07-25 — dreamhub URL space: one hub URL, or one per project?
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
  - **Follow-up (loop, 2026-07-25 17:24):** submissions attached to this
    entry at 14:34-14:35 have been REMOVED. They were never his: they are
    verbatim guard strings — `dev/capture/regroup.mjs:67` and
    `dev/capture/oneinput.mjs:139,153` — that reached the real
    `questions.md` because a guard ran against the live target instead of
    the fixture (the runner gap, fixed in 7be4a22). They were previously
    kept on the reasoning that they were his words; they are not. He asked
    at 17:23 whether three answers had been forgotten, and on the page
    they were indistinguishable from his.
    **This question is genuinely open and has never been answered.**

- **P2 · 2026-07-25 — should the PreCompact hook ship, and as a plugin? (#138)**
  This one is here because it was missing. It has been listed as
  awaiting you in `status.json` for hours and was never written down —
  the third time today an ask lived only in a task description
  (also #158, #172). Recording it is the fix; see #181 for the
  mechanism fix.

  **The thing itself**: compaction can drop what the loop knows. The
  loop's answer is to write down before compacting, which currently
  depends on an agent remembering to. Claude Code fires a **PreCompact**
  hook for both manual and automatic compaction, so the write-down could
  be automatic. Verified against the binary (2.1.219) while writing
  `compaction.md`: a hook's stdout is appended to the summariser's focus
  instructions — undocumented, and genuinely useful, because the loop
  could tell the summariser what must survive.

  **Why it needs you and not a rec**: a hook is a line in *your* machine
  config, not project content. It fires on every compaction in that
  project, including sessions that have nothing to do with dreamwork. And
  blocking a compact is a hard skip, not a postponement — a hook that
  fails at the wrong moment removes the compaction rather than delaying
  it.

  Rec: **yes, as an optional plugin, off by default** — same shape as
  `ud-dreamwork-github`, so loading it is a recorded decision in
  DREAMWORK.md rather than something the loop does to your config. Bundle
  it with #156 (the PostToolUse lint hook), since both are the same
  question — may the loop install hooks — and answering once beats twice.

  Answer "ship it", "not yet", or name a different shape.

- **P2 · 2026-07-25 — whose is `ud-dw-generate`? It is untracked in this repo
  and I am not touching it.** An 8KB executable appeared at 16:17: a
  preview-URL minter that reads repo+branch from the cwd, mints a nonce,
  and creates a directory on a server (config outside version control,
  keyed by repo slug; the example names `dd2-data-download-page`).

  Not mine and not the dreamer's — it flagged the same file and left it
  alone, which was right. Two agents have been committing in this tree
  all afternoon; both stage by explicit path, so it has survived, but it
  is not gitignored and one `git add -A` from anywhere would sweep it in.

  **Nothing needs deciding urgently** — it is safe as long as nobody gets
  careless. Say what it is when you get a moment: yours to keep here,
  something that belongs in another repo, or scratch to delete. Until you
  do it stays exactly where it is.

- **P2 · 2026-07-25 — #194: where does an upgrade check get its commit range,
  when the release has no repo?** Your version idea is captured and
  planned (`docs/plans/version-and-upgrade.md`); this is the one fork
  that decides step 4 onward, so I would rather ask than build both.

  The tension is inside the design and it is a real one: the CI
  replacement exists precisely so a **zip carries a hash without carrying
  the repo**. But the upgrade pass then wants every commit between two
  hashes, and `git@github.com:ultradyn/dreamwork.git` is private. So a
  zip-installed target has nothing to diff and no credentials to fetch
  with.

  Two ways out. **(a) Network + auth**: the pass fetches the range from
  GitHub. Real upgrade fidelity, but it puts a credential requirement in
  the startup path of a loop whose whole promise is running unattended,
  and it fails on a plane. **(b) Ship a generated changelog in the
  release**: CI writes the commits between tags into the zip, and the
  subagent reads a local file.

  **Rec: (b).** It removes the auth question rather than answering it,
  works offline, is a few lines of CI, gives the subagent better-shaped
  input than raw commits, and produces a changelog humans want anyway.
  The git path stays available wherever history is actually present —
  a checkout like this one — so (b) costs nothing there.

  Same decision also settles the no-prior-hash fallback: estimating the
  install date from asset mtimes is sound (for both an unzip and a clone,
  mtime really is install time), but turning that date into "the oldest
  plausible hash" needs history or a changelog — the same dependency.

  Answer "changelog", "network", or name a third shape.

  **Not blocking the whole idea** — `bin/ud-dw-githash`, the commit
  trailers and the frontmatter all proceed regardless, and I would start
  with the trailers since every commit written before they exist is one
  the future upgrade pass has to read blind.

## Answered

- **P1 · 2026-07-25 — which "t3 connect" do you mean, and does it change #201?
  (#202)** → resolved (2026-07-26): the linked primary source identifies T3
  Connect precisely. It is Clerk-backed environment discovery/linking plus a
  managed Cloudflare tunnel around an ordinary authenticated T3 Code server;
  it is not a TUI, agent, ACP, or PTY protocol. T3 Code overlaps #201's desired
  user outcome, but Connect itself cannot adopt or stream an existing herdr
  PTY. Keep #201's `/compact` herdr-control increment; before terminal
  rendering, investigate whether T3 Code exposes a supported deep link,
  embedding surface, or adopt-existing-session API. Research and revision-
  pinned first-party citations live at
  `.dreamwork/docs/research/t3-code-connect.md`.
  - **Answer (via watch, 2026-07-26 13:05):** I'm not exactly sure, but
    it's mentioned here and in the T3 code app.
    https://github.com/pingdotgg/t3code/blob/5719e8ac4020dda0e375ef61d044b61f55a0df8a/apps/web/src/cloud/connectOnboarding.ts#L14

- **May I deploy the dashboard?** → yes (2026-07-26): push and deploy as
  needed; neither requires separate confirmation. DREAMWORK.md now carries
  the durable authority, resolving the earlier contradiction. The stale
  live snapshot should be updated immediately.

- **May the dashboard read the session transcript? (#180)** → "Yes the
  dashboard may" via watch (2026-07-25 15:36), with three mitigations
  that are his and are better than the shapes offered:
  **only the last 10-20 lines** (so the bulk of the transcript is never
  read at all, which shrinks the exposure far more than any filter);
  **prefilter into small digestible objects** before ingesting; and a
  **consent gate** — the section blurred with skeleton text beneath,
  and hovering brings previously-invisible copy into focus with
  dreamlike effects, explaining what would be read and offering yes/no.
  Filed as #185, because it is a reusable pattern rather than one
  panel's chrome. His `jq` suggestion is noted in #180 with a
  counter-rec: Python's stdlib json does the same job without adding a
  binary this loop cannot assume exists.

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
