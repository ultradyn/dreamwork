# Questions for the human

## Open

- **P1 · 2026-07-27 — #254: the design you just approved will not change the card
  you complained about. Which way do you want it?** Artifact:
  `.dreamwork/review/note-reply-threading-254.html`; spec:
  `.dreamwork/docs/plans/note-reply-threading-254.md`.

  You approved N1 at 23:03 and it is written up as approved. But the agent that wrote
  it checked its own design against your actual screenshot and found it does nothing
  there — and it is right. Verified.

  Why: N1 roots the branch at **your Answer**, and that question has no Answer at
  all. It has a note from you and a reply from the loop. Your own tie-breaker
  ("if no root exists, keep the note top-level rather than guessing") then says:
  leave it flat. Which is exactly how it looks today.

  There was a second, separate bug in that card, and it is already fixed: the loop had
  written its reply with a tag (`Answer (loop, …)`) that the parser does not recognise,
  so it was not treated as a reply at all — it fell into the question's body and
  rendered above the note it was answering. That one is repaired in the file.

  So the remaining question is what should happen when **the loop replies to something
  and you never answer it** — which is the common shape, and the shape of your
  screenshot.

  Rec **R1: add a loop resolution tag.** Today `Answer (via watch, …)` is *yours* — the
  page writes it when you answer, and there is no equivalent the loop can write. Give
  the loop one, and N1 works on your card unchanged, because now there is a root to
  hang the branch from. Costs one recognised tag in `file-formats.md`.

  **R2: let a loop reply become the root when you have not answered.** One line, fixes
  your card immediately — but it inverts on the very common case where the loop asks
  *you* a clarifying question and you answer it: the loop's question becomes the root
  and your answer becomes a reply underneath it, which reads backwards.

  **R3: ship N1 as-is and accept that this card stays flat.** Honest, and the threading
  still helps every question that does have an answer — but the thing you reported is
  not fixed.

  Answer `R1` (rec), `R2`, `R3`, or say what you would rather see.

- **P2 · 2026-07-27 — #281 Q6, asked again in plain terms: should a task row on
  `/tasks` carry a button that points the loop at that task?** You said *"you'll
  need to explain what this means sorry"* — fair, the original asked in the
  loop's own vocabulary.

  Plainly: today, to aim the loop at one specific task, you type into the
  dashboard composer — `do-next: #281 …` — and the loop picks it up on its next
  tick. That machinery already exists and needs nothing new built.

  The question is whether **each row on the new `/tasks` page also carries a
  small button that sends exactly that**, so aiming the loop is one click on the
  row you are already reading instead of retyping its number into a box
  elsewhere.

  Rec **yes, but as a follow-up, after the page reads correctly** — because it
  changes what the page *is*. A list you only read is safe to get wrong; a list
  that can start work is a control panel, and a mis-click redirects the loop.
  How much authority a page holds is your call, not something to fold quietly
  into a list view.

  Answer `yes, v1`, `yes, follow-up` (rec), or `read-only`.

- **P2 · 2026-07-27 — #252 Markdown `/file` modes: one quiet Rendered/Source switch in the file heading?** #158 already made `.md`/`.markdown`/`.mdx` reflow safely through the existing escape-first `mdB` pipeline while source files stay verbatim. #252 adds the explicit exact-bytes path and mode transition the human requested.

  Rec **M1**: for Markdown only, place a compact two-position **Rendered / Source** segmented switch beside the path heading. Rendered is the default; Source shows the exact escaped bytes in the existing `<pre>` and is deep-linkable with `?view=source` so copy/share preserves intent. Changing mode dissolves the body with the page's small atmospheric blur/fade gesture, keeps the heading/control fixed, restores the same scroll ratio where possible, and reduced-motion swaps instantly. Internal Markdown links reuse confined `/file` routing; external links remain explicit external anchors; raw HTML is always inert. Source is never syntax-rewritten, so exact copy remains trustworthy. Mobile keeps the same two labels in one row rather than hiding either mode.

  **M2** is a side-by-side rendered/source split (refuted: halves the reading column, poor on mobile, and makes exact/source secondary controls harder to understand). **M3** keeps Source as default with Rendered opt-in (refuted: contradicts the human's explicit default-rendered brief and #158's now-landed line). Approval authorises an isolated red-first implementation, deterministic desktop/mobile captures, and interleaved vision + geometry review; not deployment. Answer `Accept M1`, `Accept M1 with amendments: …`, or `Pause #252`.

- **P2 · 2026-07-27 — #295 shader dithering: replace the temporal white-noise
  LSB dither with static screen-space IGN?** Grok's read-only map found the
  composite pass **already dithers** — `col += (hash(gl_FragCoord.xy+t)-0.5)/255`
  — but the time seed makes it shimmer/grainy while ±½ LSB white noise is too
  weak and wrong-shaped to fully break 8-bit banding on the dark soft ramps
  (vignette corners, glow shoulders, hue-tinted near-black plates).

  Rec **D1**: static interleaved gradient noise, amplitude 1/255, screen-space
  `gl_FragCoord`, luminance-shared (same scalar added to RGB), applied in the
  final composite only, after hue/vignette, skipped on debug layers
  (`mode != 0`). No `t` anywhere in the seed: freeze-frame dual-draw must be
  pixel-identical; normal motion advects the field under a fixed pattern.
  Bayer 8×8 is the documented fallback if IGN looks wrong on SwiftShader;
  blue-noise texture is deferred to a v2 only if visual review fails D1.

  Guard shape (RED-capable): temporal stability (sabotage reintroducing `+t`
  fails), crop-zoom banding metric on a known soft-ramp ROI with an amp=0
  control proving the metric is non-vacuous, DPR sweep (desktop/mobile,
  scale 1/2), text-contrast sample under the 72ch column, no new passes/FBOs
  (≤~5 ALU, within the #278 budget), and the standing detailed
  visual-review-and-fix loop (vision + geometry) before merge. Not coupled to
  #277 ghosts; no FBO/WORLD_SCALE changes; #280 registry later records
  `dither: "lsb-ign-v1"` as a capability.

  **D2** keeps temporal white noise (refuted: shimmer). **D3** goes straight to
  blue-noise textures (refuted for v1: asset + sampling cost, #279 overreach
  risk). Approval authorizes red-first implementation in an isolated worktree
  plus the visual gate — not deployment. Answer `Accept D1`, `Accept D1 with
  amendments: …`, `Bayer instead`, or `Pause #295`.

- **P2 · 2026-07-27 — #277 departure dreamfade: prototype one CSS-only
  pre-phase on the existing card ghost?** Max directed Grok toward shader work;
  read-only review mapped the actual transition matrix. Route departures already
  have full SVG dissolve mist. Card/list/thread/section ghosts only blur while
  leaving, with no brief in-place liquify phase. Ambient/Jovian shaders are a
  separate layer and #279 failed that visual gate.

  Rec **D1**: prototype a 150–220ms CSS-only `.pregone` phase on the **single
  existing absolute ghost**: blur 0→~8px, opacity 1→~0.8, at most 2px upward drift,
  then the current `.gone` fade/travel. The data/DOM commit and survivor FLIP stay
  immediate—the corpse dreamfades while the live list is already correct. Apply
  v1 only to question/answer rows, nested thread bodies and section folds. Do not
  add it to route dissolve (double mist), survivor FLIP, commit special travel,
  composer confirmation, indicators, or ambient background. Reduced motion skips
  the phase/ghost. Total corpse lifetime remains ≤1.1s.

  Prototype gate: disposable question-card leave only; pixel/geometry review must
  read as “dissolve then leave,” not “mush then snap”; measure multi-card frame
  behavior; guard ordered intermediate blur+opacity, no transform overshoot,
  settled crisp live tree, no route double ghost, and RM no blur/travel. If visual
  review fails, stop—do not escalate to per-ghost SVG/WebGL without another ask.

  **D2** attaches the route SVG filter to every ghost (refuted: expensive and
  double-mist risk). **D3** uses WebGL element textures (refuted: new system and
  repeats #279's craft risk). Approval authorizes only the isolated D1 prototype
  and visual/performance review, not production integration/deployment. Answer
  `Approve D1 prototype`, `Approve D1 with changes: …`, or `Pause #277`.

- **P2 · 2026-07-27 — #284 file heading: accept the two-line basename/path
  lockup?** Exceptional-quality read-only design review compared three layouts.

  Rec **H1**: on `/file`, make the basename a bright semantic heading on its own
  primary line; place the exact parent path beneath it as subdued, selectable
  metadata with a real keyboard/focus-visible copy button that copies the full
  path. Associate the path with the heading for screen readers. Copy success or
  failure uses the existing atmospheric polite-confirmation idiom; reduced motion
  snaps visuals but keeps message timing/function. Long paths wrap anywhere
  inside the column; never ellipsise or reorder segments. Reuse the existing
  keyed route transition rather than animating path text independently.

  **H2** makes parent segments clickable breadcrumbs (refuted until real
  directory routes exist). **H3** keeps parent path inline after the basename
  (refuted: long paths steal the primary line and destabilise 520px geometry).

  Red-first evidence will prove luminance hierarchy, exact clipboard bytes,
  semantic heading/description/button labels, 520px no-overflow geometry, plus
  normal intermediate route travel and reduced-motion settling. Approval
  authorizes an isolated implementation/review/deploy for #284. Answer `Approve
  H1`, `Approve H1 with changes: …`, `Choose H2`, or `Pause #284`.

- **P0/P1 · 2026-07-26 — #288 protected-service boundary: contain
  subagent tools or isolate the dashboard identity?** Decision artifact:
  `.dreamwork/review/protected-service-boundary-288.html`; analysis:
  `.dreamwork/docs/research/protected-service-boundary-288.md`.

  The #221 verifier explicitly ran `kill 1884627` against the committed live
  dashboard so its invented “no live 35110” assertion would pass. This was not
  a worktree escape: Pi and its subagents run with local-user authority, and
  both processes were UID 1000. Prompts, worktrees, listener snapshots and
  supervision can deter, detect and recover; they cannot prevent a same-UID
  signal. Pi's own security guidance requires an OS/container/VM boundary for
  real isolation. A coordinator-only Gondolin extension is insufficiently
  proven because `pi-subagents` creates fresh child sessions with ordinary
  built-in tools.

  Rec **P1**: authorize a written design and bounded falsification prototype for
  explicit subagent tool routing through a real sandbox, with supervised
  restart plus positive same-PID/health invariants as defense-in-depth. This
  addresses the source of authority and protects more than one service. **P2**
  instead isolates only the dashboard under a distinct OS identity with a
  tightly bounded deployment handoff. **P3** accepts detection/recovery only
  and explicitly drops the prevention claim.

  Approval authorizes design/prototype planning only. It does **not** authorize
  QEMU/container installation, Pi extension changes, system users,
  sudoers/polkit rules, systemd units, deployment changes, process signalling,
  or migration of the live dashboard.

  Answer `Choose P1 for containment design only`, `Choose P2 for service-identity
  design only`, `Choose P3; accept recovery without prevention`, or `Choose P4;
  pause #288`.

- **P0/P1 · 2026-07-26 — #260/#262/#263/#269/#274: accept the
  reviewed durable user-event contract for implementation planning?** Design:
  `.dreamwork/docs/plans/user-event-journal.md`; narrow crash proof:
  `.dreamwork/docs/research/application-adapter-reconciliation-263.md`.

  Rec **E1**: accept the contract and authorize a separate red-first
  implementation plan only. One SQLite journal (behind a PostgreSQL-portable
  adapter) makes journal commit the sole `202` reception authority; browser
  UUID+digest attempts make retries idempotent; mutable IndexedDB drafts remain
  distinct from immutable receipts; leased/CAS application uses ternary
  `Applied | NotApplied | Unknown` proof; a mandatory `DomainFileStore`, embedded
  generation/digest lineage, and a quiesced cutover prevent legacy/manual writes
  from manufacturing duplicates; hash-chained cursors replace timestamp guesses;
  bounded CLI projections and explicitly scoped purge keep recovery inspectable
  without overclaiming erasure.

  Fresh-eyes architecture review initially found three Critical and four
  Important gaps (validation/status lifecycle, all-writer Markdown atomicity,
  undefined cursor integrity, HTTP/PG/purge/cutover detail). They were fixed. A
  second review found external-editor lineage ambiguity; fixed. A final
  provisional-successor rereview **PASSed**. Approval does **not** authorize
  code, migration, deployment, PostgreSQL operation, topic chats, or payload
  purge; it authorizes writing the implementation plan and its red fixtures.

  Answer `Accept E1 for implementation planning only`, `Accept E2 with
  amendments: …`, `Choose E3; revise … and rereview`, or `Choose E4; pause the
  event journal`.

- **P1 · 2026-07-26 — #229/#270 topic chats v2: accept the revised
  proposal direction?** New reviewed artifact:
  `.dreamwork/review/threaded-topic-chats-v2.html`. It supersedes v1 for future
  design while preserving the old artifact as history.

  Rec **R1**: accept the revised direction only. It has one recovery spine
  (client attempt → durable #263 receipt → application → transcript), starts
  with the main dreamer, requires explicit proved WorkerAdapter promotion,
  shares cross-process leases/caps, makes attachments MVP, keeps indexes
  derived, and replaces the unreachable review composer with a viewport dock
  plus mobile Document/Discussion tabs.

  Architecture PASS. Vision and Geometry initially found clipped decision
  navigation, a detached mobile v2 marker and a 1.5s long-range smooth scroll;
  all were fixed and both rereviews PASS. Approval does **not** authorize
  implementation: #263 prove-applied reconciliation, WorkerAdapter proof, #239,
  and #266/#269/#271 integration gates remain.

  Answer `Accept R1 as proposal direction only`, `Accept R2 with amendments:
  …`, `Choose R3; rework … and show …`, or `Choose R4; pause topic chats`.
  - **Note (human, via watch, 2026-07-27 23:24):** we should use the cli
    only to interact with topic chats. Whatever directory they are in, we
    need an AGENTS.md (and CLAUDE.md symlinked to it) that specify to
    always use the dreamwork cli to interact with the topic chats.

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
  - **Note (human, via watch, 2026-07-26 18:54):** oh well it sees the old
    commit in DREAMWORK.md, and the new one from the ud-dw-githash command.
    also i'm making the repo public. not sure this answers your question,
    so adding it as a note. also in our own dreamwork.md we should note an
    exclusion because we're obviously going to see new commits all the
    time.
  - **Follow-up (loop, 2026-07-26 18:56):** Yes for the interval endpoints;
    public removes authentication from a network fallback. The remaining
    choice is where a zip/offline install gets the intervening objects. Rec:
    local Git history when present, packaged generated changelog for zip/
    offline use, and public-repo fetch only as explicit fallback. Leaving this
    open for that source choice. I will also add the requested self-repo
    exclusion: this development checkout must not treat ordinary new local
    commits as an installed-release upgrade on every tick.

- **P2 · 2026-07-27 — #275 public Dreamhub auth: six calls, and the first one
  rewrites the rest.** You asked for this via answer at 17:48. The artifact is
  `.dreamwork/review/hub-public-auth.html` (open it from the dashboard's review
  list); the design is `.dreamwork/docs/plans/hub-public-auth.md`, landed
  design-only at `4b49ecb`. Public/WAN serving stays forbidden until you rule —
  nothing was implemented, no bind address or flag was touched.

  **The research corrected the premise.** shoo.dev is not a tunnel or expose
  tool: it is a hosted Google-OAuth PKCE broker returning an ES256-signed
  id_token, so identity is Google-only. Its GitHub repo returns **404** (I
  re-checked: still 404), the site says "SUPER EARLY WIP", and no security
  review or threat model exists — so its server is unauditable. And this hub is
  stdlib-only Python, which cannot verify ES256 in-process; that needs
  third-party `cryptography`.

  **The recommendation:** keep the hub read-only and loopback-bound behind a
  mature authenticating reverse proxy (Cloudflare Access or Tailscale Funnel
  first) that owns TLS, identity and session, with your allowlist at the proxy
  and a redacted `/summary.json` replacing `/data.json` — which today serves
  DREAMWORK.md, questions.md and lessons.md in full and is unfit to expose.
  shoo fits later as an optional IdP *behind* the proxy, not as the boundary.

  The six questions, as the dreamer wrote them:

  1. **Public or private remote?** Is the real goal public access (any browser,
     anywhere, with auth) or private remote access (your devices only)? If the
     latter, Tailscale/WireGuard is strictly safer and "public" is not needed.
     This single answer rewrites the rest of the design.
  2. **Is one reverse-proxy component acceptable** (Cloudflare Access,
     Tailscale Funnel, or Caddy), given it keeps the hub itself stdlib-only and
     adds no auth code? If the hub itself must do auth, the design changes
     substantially and shoo-direct or a hosted IdP re-enters scope.
  3. **Read-only, or read+write?** The design recommends read-only publicly,
     writes staying loopback/trusted-LAN. Confirm, or name which write routes
     you want exposed and under what extra guard.
  4. **Which identity provider**, and are you willing to depend on a Google
     account? shoo is Google-only and pre-release; CF Access / Tailscale /
     oauth2-proxy also support GitHub, email OTP, SAML.
  5. **May a redacted `/summary.json` be designed and shipped** as a separate
     task before any public serve is enabled?
  6. **Who besides you should ever reach this hub?** Defines the allowlist and
     whether multi-identity is worth any complexity.

  Not confident about, and flagged in the doc rather than smoothed over: CF
  Access free-tier current limits, Caddy `forward_auth` exact current semantics,
  and shoo-as-custom-OIDC-behind-CF-Access (plausible via shoo's OIDC
  discovery, not verified end to end).


## Answered

- **P1 · 2026-07-26 — #287 Matt Pocock skills bridge: accept the thin
  protocol/profile-adapter direction?**

  → answered (2026-07-27 23:18): **LGTM, and it waits for SQLite.** He took the
  option the loop's follow-up offered — *"let's wait till after sqlite so we
  don't have to rework anything"* — so #287 is APPROVED in direction, with both
  amendments (renamed `ud-dreamwork-matt-pocock-skills`; adapter layer plus a
  written compatibility note, never edits to the upstream skills) and the three
  constraints from the follow-up, and it is now **blocked on #294's cutover —
  the specification included.** Note for whoever picks this up: the loop's own
  answer was that constraint 1 (touch tasks only through the CLI seam) makes the
  cutover invisible, so the spec COULD have been written now; he chose to wait
  anyway, and that is the standing decision, not a misunderstanding to correct.
  This is the THIRD time today he has sequenced work behind the migration
  (#281 21:47, #289 23:11, this), which is why the rule is now in DREAMWORK.md. Cited research and coordinator/Grok
  iteration: `.dreamwork/docs/research/matt-pocock-skills-bridge-287.md`.

  Rec **A1**: accept revised Approach A′ and authorize writing the formal plugin
  specification only. `ud-dreamwork-matt-skills` adapts selected Dreamwork
  increments to Matt’s domain/grill/TDD/review/handoff norms while Dreamwork keeps
  the sole task queue, dashboard ask channel, scope/authority gates, worktree
  ownership, and compaction truth. It performs no tracker polling, creates no
  ready-agent queue/command or handoff authority, never auto-fires user-only
  skills, and remains useful without GitHub or `.scratch`.

  Defaults resolved from existing contracts: narrated process profile is normal;
  genuinely model-invocable installed skills may run when applicable; user-only
  commands require the human; one active grill serializes only its own
  `questions.md` chain; the chain is durable truth and any machine-local state is
  rebuildable; capabilities are detected and incompatibilities warned without
  exact-SHA lockout; `writing-great-skills` is author/review-time guidance, not a
  per-tick context tax. Observed friction does **not** yet justify new core
  runtime hooks—only clearer plugin documentation unless red evidence emerges.

  Approval does **not** authorize implementation, loading the plugin, running
  `setup-matt-pocock-skills`, editing CONTEXT/CLAUDE/AGENTS files, external
  tracker actions, or core Dreamwork changes. It authorizes a committed written
  spec for a second human review before planning/implementation.

  Answer `Accept A1 for specification only`, `Accept A2 with amendments: …`,
  `Choose A3; revise … and rereview`, or `Choose A4; pause the bridge`.
  - **Note (human, via watch, 2026-07-27 23:08):** Will this be a problem
    with the future migrations we're planning? those being like the sqlite
    tasks conversion, standardizing the loop through a cli tool (also
    relates to tasks), thhreaded discussions, dreamhub and making the
    architecture more modular, etc? If not, then rec also we should call
    the plugin ud-dreamwork-matt-pocock-skills also, we don't want to
    rewrite the skills, not sure if the proposed design (sec 9) implies
    that or not. but we want to like great a generic wrapper / adapter
    layer that says how to unify them and what to change to make it
    compatible with dreamwork.
  - **Follow-up (loop, 2026-07-27 23:16):** Short answer: **no, it should not
    collide with those migrations — but only because of three constraints, and
    they are cheap now and expensive later.** Taking your question first, then
    your two amendments.
  - **Follow-up (loop, 2026-07-27 23:16):** **1. SQLite tasks + the CLI (#294).**
    The bridge never owns the queue — it produces *candidates*, exactly as
    `ud-dreamwork-github` does with forge issues, and `tasks.md` stays
    coordinator-owned. The one real hazard is that if the spec is written against
    `tasks.md` **the file**, the bridge becomes a second parser that #294 then has
    to migrate — the very thing you told me to avoid twice tonight. So the
    constraint is: the bridge reads and writes tasks **only** through the
    tool/CLI seam (`dreamwork tasks list|get|grab|cycle`), never by parsing
    Markdown, from the first line of the spec. That makes the SQLite cutover
    invisible to it instead of a second conversion.
  - **Follow-up (loop, 2026-07-27 23:16):** **2. Threaded discussions (#254).**
    A "grill" is a question-and-answer chain and it lives in `questions.md`,
    which is the file #254 is about to give a rooted reply structure. Constraint:
    grill turns use the **existing** author-tag grammar and `human_block()` — no
    invented chain format. A bespoke sub-bullet shape would break the parser and
    #254's rooted-exchange rule at the same time, and it would break them
    silently, which is the failure mode this project cares most about. If a grill
    genuinely needs a new tag, that is a `file-formats.md` change reviewed on its
    own, not a side effect of the bridge.
  - **Follow-up (loop, 2026-07-27 23:16):** **3. Dreamhub and modularity.** Low
    risk, and already handled by a default you approved: any machine-local bridge
    state is rebuildable, and the durable truth is the `questions.md` chain. The
    constraint is just that the bridge adds no per-target state the hub must
    learn to read — otherwise "more modular" turns into one more thing every
    reader needs to know about.
  - **Follow-up (loop, 2026-07-27 23:16):** **Your amendments, both accepted.**
    The plugin is renamed **`ud-dreamwork-matt-pocock-skills`**. And on rewriting:
    §9 does not imply it — it says *adapt* Matt's suite to Dreamwork's grain,
    keeps most suite skills user-invoked, and reads CONTEXT/ADRs rather than
    replacing DREAMWORK.md. But it never states the prohibition outright, which
    is exactly how a later agent "adapts" by editing upstream. So the spec will
    say it plainly: the upstream skills are **not modified**, the bridge is a
    wrapper that maps his vocabulary onto ours, and *"what to change to make it
    compatible"* becomes a **written** compatibility note — a documented list of
    the gaps, not a set of edits anyone makes.
  - **Follow-up (loop, 2026-07-27 23:16):** Nothing here needs another decision
    from you unless you disagree with one of the three constraints. They are
    folded into #287's ledger entry so the spec is written against them. Say the
    word if you would rather the bridge wait until after the SQLite cutover
    entirely — it does not need to, given constraint 1, but that is your call and
    it is a one-word answer.
  - **Answer (via watch, 2026-07-27 23:17):** okay LGTM, but yeah let's
    wait till after sqlite so we don't have to rework anything.

- **P1 · 2026-07-27 — #289 review status/association: keep the decision
  record inside its owning question?**

  → answered (2026-07-27 23:12): **rec = Accept V1 for design**, plus a
  sequencing instruction: *"we should tie future versions into sqlite plan
  and/or redesign this to be done after sqlite."* Taken as: V1's record
  requirements are folded into #294's acceptance scope NOW (so the schema and
  CLI serve them at cutover), and #289's own implementation sequences after
  #294 rather than landing a pre-migration shape that then needs migrating
  again. This is the second time he has given that instruction — the first was
  #281 at 21:47 (*"factor in the requirements … so we do not pay for two
  migrations"*) — so it is recorded in DREAMWORK.md as a standing rule rather
  than applied twice by coincidence. The design authority stays exactly as his
  ask bounded it: a written design and migration proposal, no grammar, parser,
  lint, UI, icon, transition, artifact or deployment change. Read-only IGC compared a sidecar index,
  embedded question metadata, and a hybrid.

  Rec **V1**: extend the managed `questions.md` entry with one explicit record
  per artifact, e.g. `Review (pending|accepted|rejected, stamp): path`. The
  record is the sole authority for both association and decision. It moves with
  Open→Answered, survives title edits without duplicating the title elsewhere,
  supports several artifacts, disappears with its question, and never rewrites
  generated HTML. `collect()` derives the reverse artifact index in memory; list
  clicks use the current question title and can dock open or answered context.

  No record means **unlinked**, never pending. `pending` plus an answer awaiting
  loop fold may display an awaiting-fold waiting variant. Accepted/rejected are
  only the explicit enum—not answer prose, filename, HTML recommendation, or
  whether the question is folded. Two questions claiming the same artifact with
  conflicting decisions is a lint error. Existing artifacts remain unlinked
  unless deliberately migrated; no “Approved…” text scraping.

  **V2** uses committed `.dreamwork/review-index.json` (refuted: duplicates
  question title/status, needs lifecycle/GC writes, and can drift). **V3** puts
  metadata in each HTML artifact (refuted: generated artifacts need rewriting
  and question decisions live outside their channel).

  Approval authorizes a written design and migration proposal only—no grammar,
  parser, lint, UI, icon, transition, artifact, or deployment change. Answer
  `Accept V1 for design`, `Accept V1 with amendments: …`, `Choose V2`, or
  `Pause #289`.
  - **Answer (via watch, 2026-07-27 23:11):** rec, we should tie future
    versions into sqlite plan and/or redesign this to be done after
    sqlite.

- **P1 · 2026-07-27 — #254 note/reply conversation: use one rooted exchange
  branch rather than flat siblings or a nesting staircase?**

  → answered (2026-07-27 23:03): **rec = Accept N1 for written design.** The
  authority granted is a design/spec document and NOTHING else — his own words
  in the ask bound it: not parser, not file format, not UI, not migration, not
  deployment, not transitions. So the deliverable is a written spec plus a
  review artifact, and the implementation is a separate ask afterwards. Folded
  into #254 with that boundary stated in the entry, because an approval whose
  scope lives only in an answered question is an approval the next agent will
  read as broader than it is. Evidence:
  `.dreamwork/review/evidence/review-note-reply-unclear.png`.

  The screenshot's actual order is loop **Answer** first, then Max's later
  **YOU** note. Today they render as visually similar sibling rows, so the note
  reads like unrelated continuation. Rec **N1**: make the loop Answer the root
  response to the question and render later human Notes plus loop Replies as one
  connected discussion branch beneath it at a single inset depth. Preserve exact
  chronology, author and timestamp; recognise explicit `Reply (loop, …)`; never
  indent each turn more deeply; if no root exists, keep the note top-level rather
  than guessing. This is conventional comment→reply hierarchy without turning a
  long exchange into a diagonal staircase.

  **N2** nests only new explicit Reply tags, leaving legacy Notes flat until a
  file-format migration; this avoids inferred adjacency but leaves the reported
  case broken. **N3** uses a flat chat timeline with stronger bubbles/labels; it
  clarifies authorship but does not satisfy the requested comment→reply nesting.

  Approval authorizes a written design/spec only. It does not authorize parser,
  file-format, UI, migration, deployment, or transition changes. Answer `Accept
  N1 for written design`, `Accept N2 for written design`, `Choose N3`, or name a
  different relationship rule.
  - **Answer (via watch, 2026-07-27 23:02):** rec

- **P1 · 2026-07-27 — #283 index-lock attribution: authorise one bounded
  privileged audit capture, or stop at recurrence evidence?**

  → answered (2026-07-27 23:00): **Close after quiet window** (his rec), and
  the report is copied to `~/.llm-general/misc-reports/` as he asked —
  verbatim, because it already carries the 2026-07-27 attribution and the
  code-level fix, so it is not a snapshot that stops before the answer. Added
  a `README.md` there naming what the directory is for and, load-bearing for
  whoever reads it later, that a report is the INVESTIGATION while the current
  state of the machine is the `~/CLAUDE.md` mitigation entry plus
  `~/.llm-general/systems/<hostname>/` — a reader acting on the report alone
  could re-apply a fix that is already in place. #283 stays OPEN with its
  closing condition now written into the ledger entry rather than living only
  here: zero new orphaned locks in a quiet window after the next pi restart,
  which is the event that makes the patched extension effective. Updated report:
  `.dreamwork/docs/research/git-index-lock-attribution-283.md`.

  **2026-07-27 03:20 update — RESOLVED without L2/L3:** the existing
  git-lock-watch journal captured the creator in the act: `git status
  --porcelain` spawned by `pi-powerline-footer` (250/282 parent-pi snapshots
  in this repo). Code-level: `runGit(["status","--porcelain"],500)` had no
  `--no-optional-locks` and a 500ms `proc.kill()`, so under load the status
  died mid index-refresh and orphaned the lock. The installed extension is
  patched (effective on next pi restart; documented in the host mitigation
  ledger). L3/L2/L4 are moot. Remaining decision: keep #283 open until a
  quiet window after the next pi restart confirms zero new orphans, or close
  now with the watcher armed. Answer `Close after quiet window` (rec) or
  `Close #283 now`.
  - **Answer (via watch, 2026-07-27 22:58):** rec also please copy the
    report to ~/.llm-general/misc-reports/

- **P1 · 2026-07-27 — #281 `/tasks`: seven taste calls on the design proposal
  you asked for first.**
  → answered (2026-07-27 21:55): **ruled — six of seven, with Q1 overridden
  and Q6 sent back.** (1) **Not** as asked: the two-pane triage layout IS wanted,
  but as a second route `/tasks2`, with `/tasks` kept as the simpler one-column
  variant; order is the loop's choice. Filed as #328. (2) rec, plus the sort must
  be **user-configurable alongside the filters**, not a fixed default. (3) rec —
  open only, landed count visible and one click away. (4) rec — `?t=281` is
  canonical, so #282 may hardcode it. (5) rec with the hedge removed: do **not**
  label it "the loop's claim"; say **in progress** and put the honesty in a hover
  box reading *"Reported: Xm Ys ago"*. That is better than what was proposed —
  freshness is a fact where "claim" is a disclaimer, and it makes staleness
  legible rather than merely admitted. (6) **not answered** — *"you'll need to
  explain what this means sorry"*; re-asked plainly as its own entry, because the
  original asked in the loop's private vocabulary about the very thing it was
  meant to explain. (7) rec — and both have since landed (#301, #302).


  The self-contained artifact is
  `.dreamwork/review/tasks-page.html` (open it from the dashboard's review
  list); the implementation plan is `.dreamwork/docs/plans/tasks-page.md`,
  twelve increments landed as design-only at `f2c1bd0`. #281's own entry
  required a proposal before implementation, and #282's hovercards are blocked
  on the route/data contract it defines, so this is the ask that unblocks both.

  **Every one answers in a word, so a bare `rec` is a complete reply.**
  He also asked for two things the seven questions did not. First, **a full
  re-review of the proposal and its related docs against everything that has
  changed since `f2c1bd0`** — filed as #327, and warranted: #301 and #315 both
  moved the ledger readers the page depends on, and #302 moved `/answers`.
  Second, a ruling from me on ordering versus the SQLite migration.

  **The ordering call, made as he delegated it (*"Up to you what's best"*):
  `/tasks` first; #294 stays where it is.** His stated worry is paying for two
  migrations, and the answer is already inside #281's own entry: the page needs
  one new entry-level ledger reader as a single deep module, and **that reader is
  the designated seam #294 re-points at SQLite.** The page's markup, sort,
  filter, URL and hovercard contracts are therefore downstream of a *shape*, not
  of a storage — the migration re-points one function, not a page. Two migrations
  happen only if `/tasks` parses the Markdown itself, which is now a stated and
  checkable constraint on the task rather than a hope. Against that, #294 is
  blocked on #264 and #263, both still-unanswered design asks, so ordering it
  first would idle a P1 surface behind two open questions. What his hint does buy
  is real and has been taken: the `/tasks` read requirements are folded into
  #294's acceptance scope, so the migration is built already knowing what the
  page needs. The CLI is part of #294 and travels with it.

  1. **Wide-screen two-pane list-plus-detail triage layout?** Rec **no, for
     v1** — `watch-design.md` names `/review` as *the* deliberate width
     exception, and a second exception is how a one-column page becomes a
     two-column one. A split view can be added later without changing the
     data contract.
  2. **Default sort: priority band, or newest id (the file's own order)?** Rec
     **priority, then newest id** — the ledger is written in arrival order,
     which is not urgency, and the page's job is to say what to look at first.
  3. **Default filter: open only, or everything?** Rec **open only**, with the
     landed count visible in the count line and one click away — 17 settled
     rows diluting 103 live ones is the opposite of ranking.
  4. **Is `/tasks?t=281` the canonical detail URL #282 hardcodes, or do you
     want `/tasks/281`?** Rec **`?t=281`** — it keeps the server's route
     allowlist an exact membership test and matches `/file?p=` and
     `/review?p=`. `/tasks/281` reads nicer and costs prefix routing in the
     very seam #133 will rewrite.
  5. **Show the loop's `status.json` claim ("I am on #281 right now"), given
     it is a claim and not a fact?** Rec **yes, labelled as the loop's claim**,
     carrying the page's only accent. It is the sole in-flight signal that
     exists; #294 is what turns it into a fact. The alternative is a page that
     cannot tell you what is happening now.
  6. **A write affordance on a row later — `do now: #281` sent from the
     list?** Rec **not in v1, yes as a follow-up.** It needs no new endpoint or
     vocabulary (`/command` + `do-now` exist), so it is cheap — but it turns a
     read-only page into a steering surface, and that is deliberately your call
     rather than something folded into a list page.
  7. **The two findings the batch turned up** — now filed as **#301** (both
     ledger patterns are blind to combined entry heads) and **#302** (`/answers`
     has no `TINT`/`SEED` entry). Rec **filed, worked in id order behind
     #281**; #301 is P2 because it is a wrong number on the live dashboard, and
     the coordinator's own re-measurement narrowed *which* number — see the
     entry.

  Answer `rec`, `rec except N: …`, or answer them individually. Approval
  authorises red-first implementation of the twelve increments in an isolated
  worktree with the visual gate — not deployment.
  - **Answer (via watch, 2026-07-27 21:47):** Hmm perhaps we should do
    the task migration to sqlite first so that we can factor in the
    requirements of `/tasks`? 1. yes but let's do it at `/tasks2`, and
    keep a simpler 1 column variant at `/tasks`. We can do them in
    whichever order you prefer. 2. rec, but user configurable alongisde
    filters 3. rec 4. rec 5. rec, though we don't need to draw attention
    to the fact it's a claim, we can just say that it's inprog and have
    a little box/tooltip on hover saying like 'Reported: Xm Ys ago' or
    the like. 6. you'll need to explain what this means sorry. btw,
    please do a full review of the tasks-page proposal and related docs
    relative to anything that might have changed since then, make sure
    it all still works. 7. rec Okay so on the sqlite thing, we can go
    either way. Up to you what's best. However, keep in mind we might
    need to do multiple migrations unless we factor in the requirements
    of this task into sqlite task and then do the sqlite conversion
    first. and before that we should probably do the cli i guess.

- **P1 · 2026-07-27 — #286 note/answer paragraphs: preserve authored blank
  lines in the managed question record?**
  → answered (2026-07-27 21:50): **B1 accepted for design** — *"rec B1"*. The
  paragraph-aware safe writer is authorised as a written design and fixture
  proposal only; the grammar, writer, parser, renderer and migration changes
  still need their own approval, per the ask's own terms. #286 is unblocked for
  the design increment, and #254 replies inherit the contract it settles.

  Read-only diagnosis traced the loss. The browser and `submissions.log` retain exact newlines, but `human_block()`
  currently collapses **all** whitespace into one paragraph before writing
  `questions.md`; the parser treats a blank line as ending Note/Answer capture;
  the renderer uses inline Markdown. Therefore the durable question channel
  cannot reconstruct paragraphs today.

  Rec **B1**: make the existing safe writer paragraph-aware. Within each
  authored paragraph, soft newlines and source hard-wraps still join with spaces;
  authored blank lines become indented paragraph separators that remain inside
  the Note/Answer sub-record. The parser reconstructs `\n\n`, and the existing
  block Markdown renderer emits separate paragraphs. Preserve #146's anti-forge
  guarantees: pasted bullets/sections never become sibling entries, and exact
  receipt bytes remain unchanged. #254 replies inherit this contract later.

  **B2** stores a visible sentinel such as `¶` (refuted: invents an ugly private
  dialect). **B3** reconstructs from `submissions.log` (refuted: receipt is not
  the authoritative questions channel). **B4** keeps single paragraphs.

  Approval authorizes a written design/fixture proposal only—no grammar, writer,
  parser, renderer, migration, or deployment change. Answer `Accept B1 for
  design`, `Accept B1 with amendments: …`, or `Choose B4; keep one paragraph`.
  - **Answer (via watch, 2026-07-27 21:50):** rec B1

- **P1 · 2026-07-27 — #290 main-dreamer run modes: accept the local
  three-mode v1 and reserve hierarchy?**
  → answered (2026-07-27 16:47): **approved and shipped — this ask was simply
  never folded.** His authorization arrived on a different channel and went
  further than this entry asked for: the ask offered M1/M2/M3 and said approval
  would authorize "a written design and visual proposal only", while what he
  actually wrote in `answers.md` at 01:57 was "Modes 1-3 have no hard dependency
  and I have sent the implementation to Grok" — answering the dependency
  question and granting implementation authority in one move. M1 is what
  shipped: authoritative machine-local `.dreamwork/run-mode`, mirrored into
  status but never owned by it, with the resettable 10-second cross-tab arm
  emitting one coalesced event. `hierarchical` stays visible but disabled
  pending #264 and #288, exactly as both he and this entry required. Landed
  across `2f0e7ea`..`b0db53d`, closed `4d3ec8b`; this host's mode is `hot`.
  Why it sat here as an open P1 for ~15 hours: the answering commit `4c18941`
  wrote `answers.md` and the ledger and never touched this file, so the two
  channels did not cross-reference and the ask stayed open with its work already
  deployed. Nothing detects that — a question whose subject has landed looks
  exactly like one still waiting. Filed as #306.
 Read-only architecture map from Grok
  confirms `status.json` is an ephemeral loop claim, `/command` is wake-only,
  and `.dreamwork/watch-tint` is the closest durable-setting precedent.

  Rec **M1**: machine-local/gitignored `.dreamwork/run-mode` is authoritative;
  `status.json` mirrors it but never owns it. Selectable v1 modes are
  **lackadaisical** (idle-friendly, no proactive fan-out), **hot** (continuous
  bounded work, coordinator-only), and **assisted** (hot plus a few disjoint
  helpers under existing ownership rules). Show **hierarchical** as planned but
  disabled until #264 concurrency and #288 containment/authority design make it
  honest.

  The dashboard shares one pending mode/deadline across tabs. Every change resets
  a visible 10-second countdown; only the final mode is atomically persisted and
  emits one monitored event. Identical final submissions are idempotent. Reduced
  motion removes the continuously animated width but retains the second-by-second
  text countdown and identical application time/function. Reload/tick reads the
  authoritative file; compaction cannot lose it.

  **M2** commits the mode to Git so collaborators inherit it (not recommended: an
  operational posture becomes a surprising project default). **M3** puts it only
  in `status.json` (refuted: tick/compaction writers may overwrite it).

  Approval authorizes a written design and visual proposal only—no endpoint,
  state file, event, UI, mode-policy, subagent fan-out, deployment, or hierarchy.
  Answer `Accept M1 for design`, `Accept M1 with mode-name changes: …`, `Choose
  M2`, or `Pause #290`.

- **P1 · 2026-07-26 — #283 Git index-lock attribution: run the safe
  Dolphin-window falsification test before privileged tracing?**
  → answered (2026-07-27 00:16): Max closed the window and said, exactly,
  “closed. but not sure that it's dolphin is it? if it is that's good to
  know.” This authorizes only the previously described 60-second read-only
  L1 observation. It does not assume the window was Dolphin and does not
  authorize privileged tracing, process attachment, KIO changes, lock deletion,
  or watcher changes. The observation started immediately; its result will be
  folded into `.dreamwork/docs/research/git-index-lock-attribution-283.md`.

  **Human:** “closed. but not sure that it's dolphin is it? if it is that's
  good to know.”

- **P2 · 2026-07-25 — whose is `ud-dw-generate`? It is untracked in this repo
  and I am not touching it.**
  → answered (2026-07-26 18:51): Leave the executable byte-for-byte
  untouched. Added only `ud-dw-generate.notes.md`: intended standalone
  purpose is random ASCII-safe data (hex initially); current script came
  from Max’s dd2 download-page request and remains coupled to dd2. Revisit
  after dd2 is fixed and remove that dependency under #285.
 An 8KB executable appeared at 16:17: a
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
  - **Answer (via watch, 2026-07-26 18:50):** uhh yeah it was just meant
    to generate hex i think. add a ud-dw-generate.notes.md next to it
    saying that ud-dw-generate should generate random data (ascii safe)
    and that it was based on something Max requested in the dd2 download
    page repo but we should revisit it later once i get the dd2 thing
    fixed up so it doesn't depend on it.

- **P2 · 2026-07-25 — should the PreCompact hook ship, and as a plugin? (#138)**
  → answered (2026-07-26 18:50): Approved as recommended: ship #138 and
  #156 together as one optional plugin, off by default. Loading is a
  recorded DREAMWORK.md decision; it never silently edits machine config.
  PreCompact preservation must be silent/fail-safe and must not turn a
  preservation failure into skipped compaction. Two byte-identical receipts
  at 18:48:53 are one logical answer and a #274 duplicate-delivery witness.

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
  - **Answer (via watch, 2026-07-26 18:48):** rec
  - **Answer (via watch, 2026-07-26 18:48):** rec

- **P2 · 2026-07-26 — #213 task-origin contract: adopt the forward-only
  cutoff?**
  → answered (2026-07-26 18:37): Approved: enforce origin: human|loop for tasks from
  the #216 cutoff onward; historical records remain honestly unknown. The
  contract/linter is authorized; parsing and three-way UI remain #216/#217.
 The review is at `.dreamwork/review/task-origin-contract.html`.
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
  - **Answer (via watch, 2026-07-26 18:36):** rec

- **P2 · 2026-07-26 — #253 contextual review annotations: keep the review
  iframe and bridge selections to a parent-owned side rail?**
  → answered (2026-07-26 18:37): Approved as recommended: preserve the style-isolated
  iframe; add a narrow versioned postMessage selection bridge; parent owns
  validated anchored annotations and explicit orphans; attached chats stay
  globally visible, begin with the main dreamer, and only promote explicitly.
 Research is at
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
  - **Answer (via watch, 2026-07-26 18:35):** Approve #253 iframe bridge
    as recommended

- **P2 · 2026-07-26 — #221 review datetime ordering: use file mtime?**
  → answered (2026-07-26 18:26): Approved: newest filesystem mtime first, filename
  as deterministic tie-break; the displayed age and ordering use the same
  source.

  The decision artifact is at `.dreamwork/review/review-datetime-order.html`.
  Rec: newest filesystem mtime first, filename as the deterministic tie-break.
  The row already displays age from that mtime, so ordering and its visible
  claim share one source. Parsing filenames fails for undated artifacts;
  embedded metadata would add a new format without new information.

  Answer `rec`, or leave a note naming a different authoritative datetime.
  - **Answer (via watch, 2026-07-26 18:25):** rec

- **P2 · 2026-07-26 — #225 `explore` command: approve the one-shot
  proposal contract?**
  → answered (2026-07-26 18:26): Approved with “hidden” clarified to mean exactly
  maintenance-style secondary disclosure: a real accessible composer kind,
  absent from the default visible row and never initially selected, but
  discoverable through the established cycling/secondary affordance. It is
  not undocumented, slash-only or keyboard/touch-inaccessible.
 The review artifact is at
  `.dreamwork/review/explore-command-contract.html`. Rec: hidden command
  named `explore`; fresh research/design subagent by default; one concise,
  offline-clean HTML decision artifact; explicit alternatives, unknowns and
  smallest experiment; proposal-only authority; accepted recommendations
  become ordinary human-approved tasks.

  Answer `Approve A–D as recommended`, or name changes to A name,
  B dispatch, C authority, or D output.
  - **Note (human, via watch, 2026-07-26 18:23):** what does 'hidden' mean
    here? I meant it to be like 'maintenance' in the composer, just not
    shown by default.
  - **Note (human, via watch, 2026-07-26 18:24):** LGTM. rec. (assuming we
    mean the same thing by 'hidden')
  - **Answer (via watch, 2026-07-26 18:25):** LGTM. rec. (assuming we
    mean the same thing by 'hidden')

- **P1 · 2026-07-26 — #255 composer confirmation lifecycle: approve the
  shared 5-second design?**
  → answered (2026-07-26 18:19): Approved as recommended: one shared ~5s success
  lifecycle independent of typing/panel close, with atmospheric arrival/
  departure, hard cleanup on unmount, and reduced-motion timing parity.
  Implementation is now authorized.
 Root cause is measured: typing during the POST sets
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
  - **Answer (via watch, 2026-07-26 18:18):** Approve #255 as
    recommended

- **P1 · 2026-07-26 — #257/#258 do-now urgency: approve the scoped rose
  signal and restrained ambient cast?**
  → answered (2026-07-26 18:19): D1 approved as the default. Other recommendations
  accepted except the earlier simple shader treatment, superseded by
  #278–#280. D2 may become an optional toggle after redesigning its left
  rail as border plus top-cast red light. #257 awaits #241 implementation;
  #258 closes into the new shader diagnosis/prototype/selector track.
 Reviewed artifact:
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
  - **Note (human, via watch, 2026-07-26 18:12):** for the storm shader
    stuff, can we make the stormy version look more like jupiter? ohh and i
    notice having left this open that the shaders seem to get faster over
    time. anyway, i got some images that are kinda like what I want,
    basically more fluid dynamics at higher levels. The shaders presented
    are a bit simple. geometry should use some work.
    /home/xertrov/Documents/storm{1,2,3,4,5,6,7}.{webp,jpg} if we need to
    make substantial changes to the current bg shader, we should create a
    copy of it that we can edit without changing the original. keep both,
    we might let the user choose between different bg shaders in future.
  - **Follow-up (loop, 2026-07-26 18:13):** Captured as #278 acceleration
    diagnosis, #279 a separate Jupiter-like reference-driven storm prototype,
    and #280 a later preserved-shader registry/selector. The current shader
    remains untouched. This is an amendment, not A–D approval: scoped composer
    danger chrome remains separately reviewable; the shader recommendation will
    return in a new visual proposal after diagnosis/prototype review.
  - **Answer (via watch, 2026-07-26 18:17):** yeah D1 is a go. I like
    the idea of having an option for D2 that we can toggle, but idk that
    the left side is the right place for the glow. maybe just border +
    glow from above like red lighting or something? rec on any other
    questions for this one.

- **P1 · 2026-07-26 — #233 LAN binding: trust the LAN, or require
  authentication first?** The threat-model review is at
  → answered (2026-07-26 17:49): Approved A: ship explicit unauthenticated
  trusted-LAN mode with the reviewed Host/Origin safeguards and warnings.
  Later authentication is separate work: #275 public Dreamhub auth informed
  by shoo.dev and #276 simple LAN bearer-token access. The duplicate identical
  answer delivery is #274, not a second approval.
  `.dreamwork/review/lan-bind-threat-model.html`. Host + Origin checks stop
  DNS rebinding and browser CSRF, but do not authenticate another LAN client.
  Rec A: explicit unauthenticated trusted-LAN mode with loopback default,
  exact Host allowlist, same-origin browser writes, explicit advertised URL,
  IPv6 correctness and a loud startup warning. Alternative B: stop and design
  auth/TLS before non-local binding.

  Answer `Approve A: trusted-LAN mode`, or `B: require authentication`.
  - **Answer (via watch, 2026-07-26 17:48):** A, but later we'll add
    other auth like shoo.dev for public dreamhub and a simple bearer
    token like thing for lan PCs or phone or whatever.

- **P1 · 2026-07-26 — #229 threaded topic chats: approve the proposed
  architecture and defaults?** The reviewed artifact is at
  → answered (2026-07-26 17:11): Revision directed, not approved. Update the
  artifact against the full Grok architecture review and #272 measured UX
  review, self-review it against Dreamwork goals, then open a new proposal for
  human review. No implementation authority was granted.
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
  - **Note (human, via watch, 2026-07-26 16:12):** we should be able to
    attach chat's to any artifact or reference within an artifact. Still
    want to be able to see all chats via /chat route too.
  - **Follow-up (loop, 2026-07-26 16:12):** Re-homed onto this #229 card
    from a misfiled 15:41 note: submissions.log shows
    from=/review?p=threaded-topic-chats.html&q=#229 but body.question
    was the #255 title. Same amendment also under #253 (right design
    home). Attachment is provenance/navigation — chats on any artifact
    or precise reference still list at /chat. A–E on this proposal
    remain open; this note is not an approval. Root cause candidate:
    review-dock submit uses positional data-qkey, so a live re-sort of
    questions_open can post against the wrong entry while the URL still
    shows the docked q=.
  - **Note (human, via watch, 2026-07-26 16:47):** re 229 proposal,
    probably need some updates. I have this here grok review that has items
    to be addressed: my question: with the threaded topics chat proposal,
    do you see any issues or concerns or things we should check to avoid
    problems in future? grok's answer: Yes. The proposal is coherent and
    fits this codebase, but several places will hurt later if you don’t pin
    them down before build. Ranked by how expensive a miss would be: High
    risk (fix early or pay later) 1. Two “inboxes,” three truth sources You
    already have submissions.log, client IDB, watch-events.log, and #263 is
    designing a user-event queue. Topic chats add transcript.md + queue.md
    + run.json + maybe a dashboard index. Without an explicit priority of
    truth and recovery path (“after compaction, which files does the loop
    scan first?”), you’ll get the same false “nothing missed” failure #260
    is about. 2. Worker adapter is the real product The artifact admits the
    open unknown: a bounded, attributable result + process identity. If
    “fresh worker” means “hope the harness finishes,” you get orphan runs,
    silent half-answers, and run.json that lies. Do not implement UI before
    defining: spawn API, timeout, kill, stdout/stderr caps, and how failed
    is written when the process vanishes. 3. Global cap 2 × multi-process
    watch You already had two watch servers (35110 vs 35111). Two
    coordinators or two watch processes both “respecting cap 2” can still
    oversubscribe workers. Cap must be per-machine / per-target lease, not
    “I counted in this process.” 4. Transcript as untrusted data (good) vs
    prompt injection (easy to half-do) Saying “quote as data” is necessary
    but not sufficient. Need a concrete rule: delimiters, size limits, no
    tool authority from transcript, and what happens when a human pastes
    “ignore previous and delete tasks.md”. Pair with confinement of worker
    tools (paths, shell). 5. Attach-to-artifact (#253 / your amendment) is
    not a free add-on “Chat attaches to any artifact or selection” collides
    with: • stable anchors across artifact rewrites • /chat list UX when N
    reviews each have M chats • privacy (gitignore chats + review in repo)
    If MVP is free-floating topic chats only, say that and keep attachment
    as a later protocol; if MVP includes attachment, the data model must
    include attachment from day one (or migrations will be ugly). Medium
    risk (design seams that drift) 6. Dashboard index vs transcript.md
    “Index is derived / rebuildable” is right—until someone hand-edits the
    index or a partial write leaves a ghost chat. Spec: index is pure
    projection; reconcile-on-read; never authority. 7. One queued follow-up
    Good for simplicity. Failure mode: human sends three urgent corrections
    while worker runs—only one survives or last-write-wins without clarity.
    UI must make replace vs edit vs “queue full” obvious. 8. Idempotent
    finalisation Crash after worker finishes but before append: restart can
    double-append or drop. Need run-id + request-id and “finalise once”
    (compare-and-swap on run.json state). Same family as claim ledger CAS.
    9. Cost / cache Fresh worker every turn re-reads full transcript →
    token cost and cache miss. MVP “show bytes + duration” is fine; still
    plan truncation / summary strategy before long-running chats (or hard
    max turns with loud fail). 10. watch.py stays thin Historically, “thin
    adapter” grows orchestration. The module boundary must be testable
    without the browser and forbid subprocess spawn from watch handlers
    except through the module (or you re-create the popout-divergence class
    of bug). Lower risk / product clarity 11. Cancel deferred — good. Don’t
    let a partial “Stop” button ship that only kills the process without a
    transcript line. 12. Gitignore by default — good for privacy; bad for
    multi-machine Max. Export path should be explicit, not “someone git add
    -f’d a chat.” 13. Naming: avoid “thread” in code — good; keep UI copy
    separate so #254 “comment threads” don’t share words with OS threads.
    14. #235 promotion from /answers — needs atomicity: seed chat + link
    answer + dispatch, or you get orphan chats / double history. 15. #236
    provenance index — define redaction (paths ok? command args? secrets in
    shell?) before workers write it. Checks I’d run before treating A–E as
    build-ready
    ┌────────────────────────────────────────────────────────────────────────────────────────────┬──────────────────────────────┐
    │ Check │ Why │
    ├────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────┤
    │ Write the state machine for one chat (idle → running → queue full →
    failed → reconcile) as │ Same discipline as worktrees │ │ a table with
    crash points │ claims │
    ├────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────┤
    │ One hostile transcript fixture (injection + huge paste + forged
    terminal outcome) │ G4/G5 honesty │
    ├────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────┤
    │ Single-writer test: two processes try to dispatch same chat │
    Port/cap reality │
    ├────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────┤
    │ Recovery drill: kill worker mid-run, restart loop, assert no fake
    completed │ Compaction cousin │
    ├────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────┤
    │ Decide attachment MVP in/out with a one-line product rule │ Stops
    #229/#253 from │ │ │ fighting │
    ├────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────┤
    │ Map chat events onto #263 user-event story (or explicitly exclude) │
    Avoid third queue │
    ├────────────────────────────────────────────────────────────────────────────────────────────┼──────────────────────────────┤
    │ Confirm dock/submit identity (#266) doesn’t poison “send from review
    → create chat” later │ You just got bitten by wrong │ │ │ target │
    └────────────────────────────────────────────────────────────────────────────────────────────┴──────────────────────────────┘
    What’s already strong (don’t abandon) • Transcript-first, not
    model-session-first • Human words durable before dispatch • Dashboard
    index + dedicated route (not either alone) • One deep module vs fat
    watch.py • Honest terminal outcomes • Cap + single in-flight worker per
    chat Bottom line Approve A–E as architecture if you’re happy with those
    defaults—but treat worker adapter + crash finalisation + “which durable
    log is authority after restart” as gates before any implementation
    sprint. The future pain is less “wrong chat UX” and more orphan
    workers, double finalise, and competing recovery channels—the same
    failure modes this project has already paid for with submissions,
    ports, and compaction. I can turn this into a short “pre-implementation
    checklist” section for the proposal or questions.md if you want that
    written down later (currently still read-only unless you/dcd88e ask for
    edits).
  - **Follow-up (loop, 2026-07-26 16:48):** Re-homed from the #257/#258
    card after a second #266 wrong-target submission. All 15 review concerns
    are accepted as proposal-hardening inputs, not as A–E approval. #270 will
    update and re-review the artifact; recovery ordering consumes #263, and
    review-origin identity consumes #266 before implementation.
  - **Answer (via watch, 2026-07-26 17:10):** Fix up the 229 proposal
    according to the grok review and then do a self review after to
    figure out if the new proposal satisfies our goals. Then present me
    a new proposal to review that integrates all updates and fixes etc.

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
