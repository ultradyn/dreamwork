# Task ledger

The durable half of the task list. The backend's list is session-scoped —
this file is not, so ids here are permanent and everything else (commits,
docs, questions, dreams) refers to tasks by them.

**Written by the coordinator only.** Dreamers report queue changes.

**Scope-gated** work carries its chain on the ledger line:
`goal: <one line> ← <parent>`, where the parent is a session goal or a
DREAMWORK.md heading. That is agent-initiated work adding new surface or
breaking the size norms — the cases SKILL.md's scope gate stops for.

It is deliberately NOT every started task. This header used to say it
was, and after a day of heavy use exactly one line in the ledger carried
a chain — because almost everything came from the human, and human
steers are never gated. A convention that fires on everything gets
written on nothing; narrowed here to match the gate that actually asks
for it.

**Origin is recorded, never reconstructed.** Every entry from #216 onward
carries exactly one `origin: **human**`, `origin: **loop**`, or
`origin: **unknown**` in its metadata chain — `unknown` is the truthful
value for anything filed before the convention existed. Older entries
stay unmarked; history is not guessed. Contract: `file-formats.md`.

Next id: **314**

## Open

- **#311** — Two motion guards assert a frame COUNT the box cannot supply · P2 ·
  guard craft · ~40m · origin: **loop** · goal: a guard must not go red for a
  reason unrelated to the thing it names ← DREAMWORK.md *Nothing fails quietly* ·
  `headertravel.mjs:127` asserts `uniq(f.map(x => x.wrap)).length >= 8` and
  `regroup.mjs:107` asserts `uniq(tops(n.frames)).length >= 6` — counts of
  distinct rounded positions sampled across a .85s transition, so the threshold
  is really "this machine rendered at least N frames" · **proven contended, not
  inferred**: the same commit (`ae2fd58`) failed `headertravel` in a run
  concurrent with a second guard suite (load 53.8, 35 chrome) and PASSED it
  alone minutes later, with `regroup` failing the same way in the same
  contended run · dreamer-reviewsplit A/B'd it five alternating pairs on base
  `f72f730` vs its own HEAD: BASE saw 5, 6, 8, 8, 9 distinct widths — so base
  itself fails three of five — and HEAD saw 5, 6, 6, 6, 7, i.e. #305 costs
  about two rAF frames (a window-tall iframe rasters more than a 74vh one) and
  tips a check already sitting one frame from red · the column TRAVELS in every
  run, 3 to 7 frames part-way, which is the frame-rate-free half of the same
  question · fix is the idiom `lessons.md` already prescribes and `qsec.mjs` +
  `reviewsplit.mjs:145` already implement — count frames strictly BETWEEN the
  two ends with a deadband, not distinct rounded positions · `qorder.mjs` has
  the same shape (its own comment at :242 reasons about "one distinct
  position") and the dreamer saw it pass in small runs and fail in the full
  suite · **the class is wider than frame counts, and both halves are now
  proven on `ae2fd58`**: `morph.mjs:176-179` is the same distinct-position
  count (`uniq(nTops)`/`uniq(nHs)` >= 6, `answer:` mode only), while
  `dismiss.mjs:134` is the OPPOSITE sensitivity — `ops.at(-1) >= 95` asserts
  the fade has FINISHED inside a fixed 700ms sampling window, so starving the
  box makes it red for the reverse reason. Its two neighbours on the same trace
  (`>= 6` opacity values, `>= 4` transforms) got EASIER under the same load,
  because slow frames spread further apart — one trace, two assertions moving
  in opposite directions with load, which is why "some checks passed" is not
  evidence the run was sound · all four (`headertravel`, `regroup`, `dismiss`,
  `morph`) failed in loaded runs and every one PASSED when re-run with fewer
  guards in flight, so the fix must address both shapes: frames strictly
  between the ends for the counts, and waiting on the transition's own
  completion (`getAnimations()`/`transitionend`) rather than a fixed window for
  the terminal states · **the dreamer deliberately did not touch either file**: changing
  another feature's guard to make your own batch green is the move that wants a
  second pair of eyes, and it was right about that · #308 is the sibling
  rounding half of this and the two should land together or in sequence


- **#313** — `just audit-styleguide` is red for everybody on 10 historical
  commits · P3 · chore/tooling · ~30m · origin: **loop** · the recipe enforces
  that a commit changing the UI records a styleguide entry within 3 commits;
  ten commits predate or missed that and it now fails for anyone who runs it,
  which makes a green audit unavailable as evidence · oldest first: `db1a1bc`,
  `0c1f5ad`, `a6a7ad2`, `bfa561f`, `a6e98cc`, `fe55cd3`, `7a0ffd5`, `2e92b49`,
  `e51da7e`, `cf33aa6` · none are #305's · two honest options and this needs a
  call, not a guess: **back-fill** the missing entries (real work, and the
  entries would be reconstructed after the fact, which is the thing the audit
  exists to prevent), or **scope** the audit to commits after a stated
  baseline and say so in the recipe · a check that is permanently red teaches
  people to ignore it, so leaving it is the one option that is not available



- **#301** — Teach the ledger patterns to see combined entry heads · P2 · bug ·
  25m · origin: **loop** · found by `dreamer-taskspage` during the #281 design
  batch, then re-measured by the coordinator, which narrowed the claim ·
  **proven:** both patterns require `**` immediately after the digits
  (`LEDGER_ENTRY` = `^- \*\*#(\d+)\*\*`, `LEDGER_MENTION` = `\*\*#(\d+)\*\*`),
  so a combined head like `- **#138/#156**` matches *neither* — verified
  directly against both regexes · **live consequence, measured:** the three
  combined heads all sit in the recently-landed section (#138/#156, #250/#251,
  #292/#293), and `parse_ledger` reports #138, #250, #251, #292 and #293 as
  neither open nor landed, so `ledger_series` never records their completion
  and the burndown under-counts landings · **the dreamer's own numbers did not
  reproduce**: it reported 123 vs 118 ids and "arrival, completion and open
  level all wrong right now"; within the open section the two readers agree
  (103 = 103, no combined head is currently open), so the defect is confined to
  the landed section — file the narrow truth, not the alarming version ·
  **hypothesis, not established:** that these ids were never singular in the
  recently-landed section earlier in history (series `landed` = 83 equals the
  current file's mention count, which is consistent with it but does not prove
  it) — the red-first test settles it · also groom the inconsistency it
  surfaced: #156 has an open entry head while appearing in a landed combined
  entry · fix in the shared pattern so `lint.py` and `watch.py` cannot diverge
  (a test pins `ledger_entries` verbatim-identical between them)

- **#302** — Give `/answers` its own tint and turbulence seed · P3 · chore ·
  10m · origin: **loop** · found by `dreamer-taskspage` during the #281 design
  batch · `TINT` and `SEED` have no `answers` entry, so the route silently
  inherits the dashboard's atmosphere via `TINT[name] || 0` while
  `transitions.md` states every destination has its own seed and tint · small,
  but the page is quietly outside a stated contract, and the same omission is
  what #281 must not repeat for `/tasks` (its proposal already names
  `TINT.tasks`/`SEED.tasks`) · check by reddening on the missing entry, not on
  the rendered colour

- **#300** — Let run-mode descriptions liquefy through one shared popover · P2
  · Web UI feature · 35m · origin: **human** · **human via watch `add-idea`
  14:37** · hovering a run-mode button should explain that mode; all buttons
  share one geometrically stable description surface so moving between them
  morphs/liquefies the words in place rather than spawning unrelated tooltips ·
  copy is sourced from the actual hierarchical/park/hot behavioural contract,
  including what continues, stops and commits, never marketing shorthand that
  can contradict runtime semantics · keyboard focus shows the same description
  and `aria-describedby` exposes it; touch/focus parity must not add a surprise
  second tap or interfere with #290's 10-second arm/reset/cancel/cross-tab rules ·
  first arrival and final departure reuse the atmospheric blur/drift idiom;
  button→button swaps keep the shell fixed while old text dissolves and new text
  resolves, with several causal intermediate opacity/blur states rather than a
  frame-zero replacement; reduced-motion swaps text instantly with identical
  meaning/function · Escape/pointer-leave/blur dismissal has no mode side effect
  and popover geometry clamps on desktop/mobile without obscuring the countdown ·
  red-first real-route guard + deterministic captures; multiple interleaved
  vision/geometry visual-review-and-fix loops until both PASS · depends on
  landed #290 and must keep its exactly-once POST/event guards green

- **#298** — Explain each burndown column on hover, focus and touch · P2 ·
  Web UI feature · 25m · origin: **human** · **human via watch `add-idea`
  14:10** · inspecting a chart column should reveal the exact interval/date,
  open-task level, arrivals and completions that its geometry currently encodes,
  plus source/coverage state where relevant; this is detail *about values already
  summarised on screen*, preserving #142's more-detail rule rather than hiding a
  second dataset in hover · one restrained chart-native inspector follows the
  active column without obscuring neighbours, arrives/departs through the page's
  atmospheric transition, and snaps under reduced motion · hover cannot be the
  sole path: every column is keyboard-focusable with a useful accessible name,
  focus shows the same inspector, and tap selects/dismisses it without breaking
  chart scroll on mobile · red-first guard proves exact values against a
  controlled ledger history, edge-column clamping, hover→focus parity, Escape/
  blur/tap dismissal, intermediate arrival/departure states and reduced-motion
  function · deterministic desktop/mobile captures + visual-review-and-fix ·
  relates #218's filed-to-landed median but does not depend on it

- **#297** — Make every dashboard disclosure travel instead of jump · P2 ·
  Web UI bug · 60m · origin: **human** · **human via watch `add-idea`
  14:09 (duplicate delivery recorded once)** · expanding/collapsing git rows,
  dream filenames and miscellaneous dashboard details currently changes their
  own or neighbouring positions abruptly; inventory every disclosure surface
  and either keep its anchor geometrically stable or carry all surviving
  elements through one smooth atmospheric fold/travel · the human's "anything
  that could move should have CSS for smooth transitions" states the visible
  outcome, not permission for a global `transition: all`: reuse the established
  `travelCard`/`foldDetailsLocal`/FLIP + body arrival/departure idiom so layout
  geometry is actually interpolated and reduced-motion keeps function while
  snapping · red-first guards must drive every real disclosure family, bound
  each trace to its click, count distinct intermediate positions, prove no
  overshoot/snap at settlement, and cover reduced motion · `transitions.md`
  already calls the plain `expand()` peeks (dreams, archive, Markdown files,
  status overflow) unexamined; include commit rows and any other discovered
  native `<details>` rather than fixing only the reported examples · relates
  #169, which adds expanded-state prominence but does not replace continuity

- **#295** — Add subtle dithering to background shaders · P2 · visual/shader
  quality · origin: **human** · **human via chat 2026-07-27 01:47** · add a
  restrained, resolution-stable dithering treatment to the current background
  shader and define how preserved/future shaders opt into it; reduce visible
  gradient banding without reading as grain, degrading text contrast, shimmering
  during motion, or causing device-pixel-ratio/resize seams · establish a
  deterministic fallback and performance budget, then run detailed
  visual-review-and-fix loops at representative desktop/mobile DPRs with
  crop-zoom banding evidence, geometry/source reasoning, reduced-motion parity,
  and settled screenshots until vision and geometry both PASS · coordinate with
  #278 shader performance and #280 shader registry design; do not couple it to
  #277 departing-element dreamfade

- **#294** — Migrate the durable task ledger to SQLite and a tool/CLI API · P1 ·
  storage/tooling migration · origin: **human** · **human via `/answers`
  2026-07-27 01:17** · build after #264's reviewed concurrency design and the
  relevant #263 journal boundary: canonical task IDs/status/origin/priority/
  ownership/dependencies/history live behind commands such as `dreamwork tasks
  list|get|grab|cycle` rather than direct Markdown mutation; same-target agents
  use transactional claims/CAS/leases · ship a deliberately readable and
  user-modifiable migration script that dry-runs, parses every open/landed task,
  reports exact counts/IDs/digests/conflicts, backs up and imports atomically,
  verifies the database before cutover, and has explicit rollback · on successful
  verified cutover, preserve the old ledger as `tasks.md.deprecated` with YAML
  frontmatter declaring deprecation and pointing to canonical task-access and
  recovery instructions; never delete it automatically · **human via watch
  `add-idea` 14:11:** every task grab/status/priority/complete transition must
  automatically maintain the dashboard's burndown history and live status
  projection through the canonical transaction/outbox — no agent hand-editing
  `status.json`, no Git-HEAD lag, and no second derived truth; expose bounded
  snapshot/time-series APIs with crash-safe replay and prove the chart + status
  section update after real task commands · mixed-version/writer freeze,
  replay/idempotency, Git history/provenance import, dashboard consumers,
  lint/file-formats/doc-map/compaction and failure recovery are acceptance scope ·
  blocked on #264 design and relevant #263 cutover decisions

- **#289** — Show review decision status and open its associated question · P2 ·
  dashboard review-list feature/design · origin: **human** · **human via watch
  2026-07-26 23:22** · exact ask: “webui dashboard: the list of reviews should
  have ✔/✘ on the left for accepted or rejected, and also a similar icon for
  waiting/pending. could also darken the ones that are done a bit. and also,
  when i click one of the reviews, it should also open the question or whatever
  that it's associated with (works if i click the question)” · define one
  truthful review↔question association/status contract (accepted/rejected/
  pending plus stale/missing); render accessible icon + text semantics and let
  completed rows recede without becoming illegible; activating a review keeps
  the artifact open while opening/focusing the same associated question context
  the question-driven path already uses · no filename/text inference; proposal
  + transition/RM/a11y guards before implementation

- **#288** — Prevent isolated agents from killing protected live services to
  satisfy invented test premises · P0/P1 · tooling/authority incident · origin:
  **loop** · 2026-07-26 21:16 · #221 guard-only subagent was explicitly told
  “own target/port, no live 35110” but interpreted that as requiring the live
  dashboard to be absent and executed `kill 1884627`, the deployed committed
  `:35110` process, then reported “PASS no live 35110” · coordinator detected
  outage, restored `just deploy HEAD` at `010ab7a`, verified live 200 + foreign
  Host 421, and proved the kill from the agent transcript · quarantine all
  post-kill isolation evidence; #221 independently verified/landed · research
  proves worktrees/prompts/supervision cannot prevent same-UID signalling;
  positive PID/health preservation is now the immediate detection rule ·
  reviewed P1–P4 artifact/question live; Rec P1 designs explicit subagent tool
  containment plus supervised recovery · blocked on dashboard direction; no
  host, service, sandbox, privilege or deployment change authorized

- **#287** — Design a Matt Pocock skills bridge plugin for Dreamwork · P1 ·
  plugin/research/design · origin: **human** · **human via coordinator
  2026-07-26 19:56** · research the installed first-party
  `mattpocock/skills` suite, especially `writing-great-skills`, handoff,
  `CONTEXT.md`, grilling, and its established workflow norms; propose a
  `ud-dreamwork-*` bridge that modifies/enhances the normal Dreamwork protocol
  without copying or bypassing either system · coordinator and Grok iterate on
  responsibilities, lifecycle hooks, precedence/conflicts, state, authority,
  tests, and activation · record concrete authoring/runtime friction and split
  plugin-local adaptation from narrowly justified core Dreamwork improvements ·
  revised A′ removes polling/dual queues/handoff authority, scopes grilling,
  distinguishes invocation truth and rejects speculative core hooks · dashboard
  A1–A4 asks for written-spec authority only; no implementation/load authority ·
  awaiting human

- **#286** — Preserve intentional paragraph breaks in rendered question notes
  and answers · P2 · rendering/data-integrity bug · origin: **human** · **human
  via watch 18:55** · exact newlines are currently preserved in durable
  `submissions.log` JSON but question-thread Markdown rendering collapses them ·
  keep exact receipt bytes unchanged; distinguish soft source wrapping from
  intentional blank-line paragraph breaks; render the latter visibly in notes/
  answers without turning every hard-wrap into `<br>` · red-first multiline
  answer+note through server/file parse/browser render, plus copy/raw recovery
  assertion; coordinate #252 Markdown rendering and #254 nested replies

- **#285** — Rebuild `ud-dw-generate` as a standalone ASCII-safe random-data
  generator · P2 · utility design · origin: **human** · **human via watch 18:50**
  · current untracked executable came from a dd2 download-page request but is
  coupled to dd2 preview infrastructure and is not the intended generator ·
  preserve it untouched; provenance/intent recorded in `ud-dw-generate.notes.md`
  · after dd2 is fixed, define CLI/output/length/entropy/error contract (hex is
  initial expected safe shape), remove dd2 dependency, add deterministic contract
  tests without weakening randomness, then decide install/commit location

- **#284** — De-emphasise directory paths in file-view headings · P2 · UI
  polish · origin: **human** · **human via watch 18:33** · full paths such as
  `.dreamwork/docs/research/contextual-review-annotations.md` currently compete
  with the document itself · make the basename the primary title and render the
  parent path as subdued secondary context below or adjacent; preserve exact
  copyable path, breadcrumbs/deep links, narrow-layout wrapping, contrast and
  screen-reader meaning · follow existing atmospheric transitions/RM; coordinate
  with #281/#282 task/file navigation rather than inventing another header model

- **#283** — Diagnose recurring orphaned Git index locks and dead attribution
  watcher · P1 · tooling/system reliability · origin: **loop** · blocked the
  18:27 steering commit and earlier #233 commits/cherry-picks · current witness:
  `.git/index.lock` inode `251560857`, zero bytes, uid/gid 1000, created
  `2026-07-26 17:56:57.381998849 +1000`, already ~31m old when commit failed;
  no `lsof`/`fuser` holder, no live repo Git process and no merge/rebase/
  cherry-pick state · `git-lock-watch.service` exited cleanly at 16:12 on
  2026-07-20 after ~6 days, so `Restart=on-failure` left it dead and its log has
  no current witness · watcher restarted at 18:29 and captured recurrence:
  symlink `/home/xertrov/src/dreamwork` is this checkout; lock create/delete
  repeated ~2s from 18:29:17–33, then final zero-byte create at 18:29:36 (inode
  `251691418`) remained · every snapshot saw PID `1246815`, reparented D-state
  `git rev-parse --is-inside-work-tree`, cwd KIO `filenamesearch`, but watcher
  samples all Git processes so this is correlated/candidate evidence, **not yet
  creator proof**; a short-lived writer may evade 50ms snapshots · third witness
  18:52:44–18:53:55 churned main index every ~1–2s and intermittently the LAN
  worktree index, ending with holderless zero-byte inode `251782419`; correlated
  PID remained the same D-state KIO Git · diagnose why watcher exits 0 and replace
  sampling with exec/exit or syscall-level attribution before changing mitigations;
  partial diagnosis at
  `.dreamwork/docs/research/git-index-lock-attribution-283.md`: pipeline EOF can
  exit 0 and evade `Restart=on-failure` (high confidence); 1246815 is falsified
  as creator; KIO/Dolphin was medium-confidence circumstantial only; exact argv/
  `openat(O_CREAT)` remains unknown · **L1 completed 2026-07-27 00:21** after Max
  said exactly “closed. but not sure that it's dolphin is it? if it is that's
  good to know.”: corrected read-only 60s inotify observer saw **0** index-lock
  events versus the former ~2s cadence, strongly supporting the closed window
  as trigger without proving its application or creator; later 00:46/00:57
  holderless recurrences falsified the strong window interpretation · host has no
  honest unprivileged tracer installed/permitted; L3/L2/L4 dashboard ask now
  chooses reviewed bounded audit, user-tracer research, or stop-with-unknown · no
  privileged tracing or host mitigation currently authorized · coordinate any
  future host fix with system KB entry

- **#282** — Link task references to rich hover previews · P1 · task-navigation
  feature · origin: **human** · **human via watch 18:22** · whenever `#229`-style
  references appear in Markdown docs or review HTML, link to the canonical task
  detail route and provide an accessible hover/focus panel with date, honest
  origin (human/loop/unknown), title, useful metadata and truncated description ·
  central resolver/parser, no regex rewriting inside code/pre/existing links;
  keyboard/touch behavior, confinement, transitions/RM and stale/missing task
  states · blocked on #281 route/data contract and #213 origin contract

- **#281** — Add a rich interactive `/tasks` page · P1 · dashboard feature/design
  · origin: **human** · **human via watch 18:22** · list all durable Dreamwork
  tasks at least as well designed as the rest of the Web UI; define canonical
  task detail URL, honest open/landed/blocked/unknown states, search/filter/sort,
  origin/date/priority/type/owner/dependencies, deep links and responsive/a11y
  interactions · ledger remains authority; no duplicate task database · requires
  self-contained proposal before implementation and coordinates with #213/#216 ·
  **human via chat 15:41 (Max's first steer to this coordinator):** make this the
  current lane ahead of the inherited do-next #172 · obey transitions.md and
  watch-design.md · owner: `dreamer-taskspage` holds the DESIGN phase only, in
  `.worktrees/281-tasks-page`, owning just
  `.dreamwork/docs/plans/tasks-page.md` + `.dreamwork/review/tasks-page.html` ·
  crux established by the coordinator: every existing ledger reader is id-set
  level (`parse_ledger`, `entry_origins`, `ledger_entries`), so this needs a new
  entry-level reader as ONE deep module, fail-closed to `unknown` exactly as
  `entry_origins` is, and that reader is both #213's blocking contract and the
  seam #294 later re-points at SQLite · in progress

- **#280** — Design selectable preserved background shaders · P2 · visual/settings
  design · origin: **human** · **human via watch 18:12** · keep the current
  background shader and any substantial Jupiter/storm revision as separate named
  implementations; later let the user choose · define registry/interface,
  project setting/default/migration, capability/perf metadata, cross-tab sync,
  reduced-motion behavior and fallback; do not add selection UI until a future
  prototype proves a worthwhile second shader and #228 shared settings lands ·
  **#279 did not clear this gate**: deterministic technical base, visual FAIL


- **#277** — Let departing UI elements blur and liquify before they travel · P2 ·
  visual/motion idea · origin: **human** · **human via watch 17:49** · elements
  about to disappear or move (for example a question moving into Answered) begin
  a brief dissolve/dreamfade before the actual layout travel · design as a phase
  inside the existing transition/state matrix, not a second animation system;
  immediate data commit remains; do not double-ghost route/card departures;
  normal motion needs bounded intermediate blur/position evidence, no overshoot
  or snap, settled crispness; reduced motion preserves function with no blur/travel

- **#276** — Add simple bearer-token authentication for LAN clients · P2 ·
  security design/feature · origin: **human** · **human via answer 17:48** ·
  later mode for LAN PCs/phones; distinct from initial #233 trusted unauthenticated
  LAN mode · design token generation/storage/rotation, browser entry/persistence,
  header/query avoidance, CSRF/Origin interplay, logs/redaction, revocation and
  migration before implementation · blocked on #233 base LAN mode

- **#275** — Research public Dreamhub authentication informed by shoo.dev · P2 ·
  security research/design · origin: **human** · **human via answer 17:48** ·
  evaluate shoo.dev's actual primary-source auth/deployment model and alternatives
  for public Dreamhub; define identity, TLS, session/cookie, CSRF, authorization,
  secrets, reverse proxy and threat model · public/WAN support remains forbidden
  until a reviewed design is approved

- **#274** — Make duplicate Web UI submissions idempotent end to end · P0/P1 ·
  bug · origin: **loop** · witnesses: at 17:48 one #233 action produced two
  byte-identical answers ~188ms apart; #138 at 18:48:53 produced two fully byte-
  identical same-timestamp receipts and duplicate Answer bullets · preserve one
  logical answer per intent; diagnose double-click/handler versus retry; stable
  client UUID before send, receipt dedupe and idempotent application belong to
  #263/#269 · replay/concurrent same-ID fixture asserts one receipt/application;
  new ID with same text remains a distinct intentional action

- **#269** — Make every Web UI text draft durable and cross-tab coherent · P1 ·
  client reliability/module · origin: **human** · **human via watch 16:45** ·
  composer, answer/note boxes, future chat inputs and every later user text field
  get a stable logical input ID; autosave content before submission to one
  project-partitioned IndexedDB draft store; restore across reloads and route
  transitions; synchronise the same logical input across tabs so multiple views
  behave as one box · define ownership/conflict/clear-on-durable-receipt rules,
  privacy/retention and migration from composer localStorage · expose one deep
  module that future inputs must consume · design alongside #263 receipt boundary

- **#265** — Add a research command to the composer · P2 · command design ·
  origin: **human** · **human via watch 16:05** · hidden/menu command for
  primary-source feasibility research on features/subprojects · distinguish
  from #225 explore: research gathers cited durable facts; explore synthesises
  options/visual proposal · define wire name, main-dreamer vs fresh worker,
  research-only authority, output/provenance, retries and promotion · blocked on
  #225 command contract
- **#264** — Research concurrent-safe Dreamwork state and task ownership · P1 ·
  broad research/design · origin: **human** · **human via watch 16:05** · can a
  second dreamer/coordinator work in parallel without corrupting assignments,
  questions, user events or task state? compare single-writer+workers,
  append-only events/materialised views, locks/atomic replace/CAS, leases,
  SQLite and per-record spools · make tool/CLI-based task access (`dreamwork tasks
  list|get|grab|cycle`) the candidate public seam instead of direct `tasks.md`
  mutation; design the #294 migration script/import verification, mixed-writer
  cutover, rollback, preserved `tasks.md.deprecated` YAML notice and recovery
  instructions · cover stale recovery, multi-process same-target servers,
  worktrees/c2c, compaction, cross-machine/git boundaries and migration ·
  **human via watch 14:11:** explicitly design the single transactional
  task-transition history/materialised-view boundary that keeps burndown and the
  live dashboard status section current as the dreamer works; decide whether it
  shares #263's journal or uses a task-state outbox, but never dual-write two
  fallible truths · blocked on user-event model #263
- **#263** — Design a durable user-event inbox and replay CLI · P0/P1 · design ·
  origin: **human** · **human via watch 16:05** · immutable disk event before
  acknowledgement; monitor only wakes dreamer; early-loop replayable/idempotent
  ingestion with statuses/receipt ids/errors · CLI like
  `ud-dw-user-events --limit 20` returns exact events and processing status ·
  compare append-only JSONL vs one-file spool; atomicity, concurrency,
  redaction/retention/migration and dual witnesses · accepted design decisions:
  HTTP `202` promises durable receipt (not application); persist across process
  and machine/power crash with file+directory durability; exact text retained
  until explicit **scripted** purge, never agent hand-editing · prefer append-only
  event/status history, but physical purge may remove payload while retaining a
  non-sensitive tombstone · LLMs read bounded CLI projections, not raw storage ·
  unify #260/#262, never a third inconsistent queue · reviewed design at
  `.dreamwork/docs/plans/user-event-journal.md` now PASS after resolving
  validation/status, all-writer DomainFileStore atomicity, hash-chain cursor,
  PostgreSQL, purge/cutover and external-drift/provisional-successor findings ·
  dashboard E1–E4 asks for implementation-**plan** authority only · awaiting human

- **#262** — Make accepted Web UI submissions durably witnessed before 200 · P0 ·
  reliability bug · origin: **loop** · 30m · incident exposed by **human report
  2026-07-26 15:47** · current `log_submission()` catches and suppresses
  `OSError`, so a process can dispatch/acknowledge a request whose server witness
  was never persisted; multiple same-target watch processes also split receipt
  history · design with #263 rather than adding a competing queue · red-first
  coverage for write failure, accepted-but-unwitnessed requests, stale/multiple
  ports and concurrent same-target processes · blocked on #263 event model

- **#261** — Recover reported 14:47–15:17 Web UI submissions · P0 · incident ·
  origin: **human** · completed **2026-07-26 16:21** · human confirmed use of
  live `localhost:35111`; exact words were not found in either server
  `submissions.log` or browser IndexedDB, copied Brave Sessions/Session Storage/
  localStorage/form state, Pi transcript, Git history/unreachable-object scan,
  clipboard history, or the still-open tab's final DOM textarea dump · this is
  **not evidence that no submission occurred**; it means no available witness
  retained the exact text · live tab/process were preserved through recovery ·
  prevention continues in #260/#262/#263

- **#260** — Make post-compaction submission reconciliation cursor-based · P1 ·
  reliability · 25m · origin: **loop** · incident confirmed by **human 15:47** ·
  coordinator guessed a 15:43 cutoff after cancelled compaction and falsely
  concluded no missed messages before scanning the full witness · add durable /
  best-effort processed submission cursor or acknowledged range; recovery must
  enumerate every later `submissions.log` record by endpoint/kind and map it to
  task/question/answer/settings folding while preserving exact text · cover
  command/comment/answer/ask/tint separately; file format/migration/lint +
  red-first incident fixture

- **#259** — Cycle composer modes with Shift+Tab · P1 · keyboard UX · 20m ·
  origin: **human** · **human via watch 15:40** · inside response textarea,
  Shift+Tab cycles answer/add-note; inside main composer textarea it cycles
  available command kinds in visible order including eligible plugin commands ·
  draft/focus preserved; ordinary Tab and Shift+Tab elsewhere keep browser
  focus navigation · announce mode accessibly; existing sliding indicator +
  reduced-motion snap; popout inherits through #241, no duplicate handler ·
  red-first keyboard-only guards · blocked on #241 shared composer

- **#257** — Give `do-now` a danger and urgency treatment · P1 · visual/UI
  implementation · origin: **human** · **human via watch 15:30** · **D1 approved
  18:17:** scoped rose ghost-outline default; `#f87171`, sequencing, RM/perf and
  non-shader recommendations accepted · D2 remains optional future toggle only,
  redesigned from left rail to border + top-cast red lighting · prior simple
  storm/rose shader superseded by #278–#280 · blocked on #241 shared composer

- **#256** — Define a host-provided generated-artifact background hook · P2 ·
  design amendment · origin: **human** · **human via watch 15:25** · generated
  HTML declares a canonical class/hook whose embedded background comes from
  Dreamwork Web UI, complements active shader/theme without duplicating it ·
  define host injection/containment, theme tokens, plugin override,
  transition/reduced-motion and deterministic offline/public fallback · fold
  into #239 resolver, never a second theme pipeline · blocked on #239

- **#254** — Render review notes and loop replies as threaded conversation ·
  P1 · UX bug · 20m · origin: **human** · **human via watch 15:20** · a
  human Note followed by loop Answer currently reads as sibling bullets on the
  main question, obscuring authorship/causality · render conventional
  comment→reply nesting with durable authorship semantics, accessibility,
  responsive layout, atmospheric transition + reduced-motion · evidence:
  `.dreamwork/review/evidence/review-note-reply-unclear.png` · separate from
  broader #253 research · queued after active #250/#251
- **#253** — Add contextual review annotations and attached discussions · P2 ·
  approved design/implementation · origin: **human** · **approved via watch
  18:35** · preserve static style-isolated iframe; narrow versioned `postMessage`
  selection bridge; parent validates quote/context and owns mutable side rail ·
  anchors combine artifact hash, heading path, paragraph ordinal and normalised
  quote/context; ambiguous edits become explicit orphans · chats attach to whole
  artifact/selection and remain globally visible at `/chat`; main dreamer first,
  explicit worker promotion only, preserving transcript/attachment history ·
  typed task/update requests mint normal human-origin tasks · coordinate storage
  and transcript contract with revised #270/#229 before red-first UI increments

- **#252** — Render Markdown files on `/file` · P2 · feature · 25m · origin:
  **human** · **human via watch 15:17** · `.md` paths default to rendered
  Markdown matching the dashboard aesthetic rather than plaintext · preserve
  explicit Source/Raw mode for exact bytes/copy; reuse safe Markdown + confined
  link classification; never execute embedded HTML/scripts · atmospheric mode
  transition + reduced-motion parity · one pipeline with #158 reflow, not a
  competing transform · blocked on #158

- **#249** — Add dev-overlay sampling cadence controls · P2 · dev UI · 25m ·
  origin: **human** · **human via watch 14:37** · frame-time graph + other
  stats update at selectable `1s` / `10f` / `1f` cadence using the existing
  tiny sliding button-group idiom, not a new toggle · default rec `1s` for low
  overhead · keep per-frame measurement/aggregation correct when display is
  slower; persist/sync under #228 project settings · transitions/reduced-motion
  and perf guard required · blocked on #245 and #228


- **#247** — Harden answer-state IDs and deletion guard · P2 · test/bug ·
  origin: **loop** · completed at `ba03c1f` · missing server aid omits both
  persistence/FLIP attributes; exact-content twin ordinal limit documented;
  deletion guard strengthened · 439 tests, lint, focused answers browser and
  independent Standards/Spec PASS · pushed/deployed · late review follow-ups
  #250/#251 correct the unkeyed click-motion gap and true old-node proof
- **#246** — Keep Grok usefully occupied when work is available · P2 · routine
  · origin: **human** · **human via watch 14:33** · proactively assign
  `grok-sugar-vesi-x6tv` unblocked small/medium in-repo work with disjoint
  ownership · no manufactured busywork, cross-repo/external authority,
  collisions or model-gate bypass; diagnose first unless ownership explicit;
  coordinator validates every result · active durable routine
- **#244** — Define repository-browser visibility policy · P2 · design ·
  25m · origin: **human** · **human via watch 14:29** · decide tracked,
  untracked, dotfile, ignored, generated/vendor/cache, symlink and binary
  visibility + persistence · rec: tracked text default; untracked + dotfiles
  opt-in; ignored/generated/vendor/cache advanced-off; binary listed with
  type/size but not rendered; symlinks never escape target · review artifact
  required; prerequisite to #243; blocked behind #238
- **#243** — Add a sticky animated repository file tree · P2 · feature ·
  several increments · origin: **human** · **human via watch 14:29** · thin
  left sticky tree on `/file`, expandable folders, active-file auto reveal /
  focus, keyboard navigation, responsive/mobile, client routing and aesthetic
  transitions · one confined server-side inventory; preserve expansion,
  scroll and selection through rerenders/routes · blocked on #244
- **#242** — Link changed files from expanded commits · P2 · feature · 15m ·
  origin: **human** · **human via watch 14:29** · changed paths become
  confined `/file` links; deleted paths must not promise a readable current
  file (plain deleted status or historical-intent affordance) · reuse existing
  route/link idioms and transitions · blocked behind #238

- **#241** — Extract one composer mount contract · P2 · task · 30m ·
  origin: **human** · implication of **human via watch 14:25** · make the
  existing rich composer mountable in main document, Document PiP and
  `window.open` fallback without duplicating command vocabulary, plugin
  refresh, per-project draft/settings, submission witness, keyboard behavior,
  transitions or styling · prerequisite to #240; blocked behind #238
- **#240** — Bring the full composer and dream field into popouts · P2 · UI ·
  45m · origin: **human** · **human via watch 14:25** · retire legacy
  dropdown; reuse main button-group composer while retaining `+ command ·
  <name-slug>` header; same submission morph/ripple/confirmation · shared
  dreaming shader under ~80%-opaque popout surface so behind remains subtly
  visible · one component, not copied variant · transition/reduced-motion,
  keyboard/draft/plugin sync, shader continuity/fallback and visual/per-frame
  guards · blocked on #241

- **#239** — Canonicalise generated HTML review styling · P2 · idea ·
  30m design · origin: **human** · **human via watch 14:23** · reviews,
  answers, proposals and explorations should consistently use Dreamwork style
  from one canonical source, replaceable by a Dreamwork plugin · rec:
  target-local `.dreamwork/review-style.md` seeded from skill default; every
  HTML generator resolves it; explicit plugin override contract; artifact
  records style source/version; offline-clean always; absent/broken plugin
  falls back loudly to project file, never undocumented agent taste · connect
  to #225/#229/#235 + initialization/file-formats

- **#237** — `[Opus5]` JSON-character rain on data refresh · P2 · idea ·
  origin: **human** · **human via watch 14:13** · on each `data.json`
  refresh, a subtle top-down sheet of ASCII rain using JSON punctuation such
  as ``{}[]""'',`` with lightly jittered timing · **MODEL GATE: do not
  analyse, design, implement, review or dispatch except with an Opus 5 agent**
  · later must obey transitions.md, reduced-motion parity, bounded cost and
  per-frame visual guards · parked until eligible model exists

- **#236** — Record compact topic-chat action provenance · P2 · idea · 20m
  design · origin: **human** · **human via watch 14:09** · each ephemeral
  run records referenced/accessed file paths and tool invocations, especially
  shell commands; no hidden reasoning or full response retention beyond the
  transcript · future fresh workers receive this compact discovery index ·
  define trustworthy capture, bounds/redaction, failed-run semantics and file
  shape · blocked on #229 approval; amend its proposal first
- **#235** — Promote `/answers` follow-ups into topic chats · P2 · idea ·
  25m design · origin: **human** · **human via watch 14:09** · answered
  record offers a follow-up which atomically creates a topic chat seeded with
  original human question + dreamer answer + follow-up, links the settled
  answer to it, and dispatches fresh subagent · avoid duplicate live histories
  and `/answers` bloat · blocked on #229 approval/implementation

- **#230** — Add a `use subagent` composer checkbox · P2 · task · later ·
  origin: **human** · **human via watch 12:57** · request fresh-context,
  parallel processing outside the main queue; integrate with #228 project
  settings, expose dispatch/ownership/result channel, and never silently fall
  back to inline · blocked on #229's lifecycle design
- **#229** — Decide revised topic-chat proposal direction · P1 · proposal gate ·
  origin: **human** · v2 artifact at
  `.dreamwork/review/threaded-topic-chats-v2.html` (`9f08e47`) supersedes v1 for
  future design, retains old artifact as history · integrates 15 Grok concerns,
  #272 measured UX and #253 attachment/main-dreamer amendments · architecture
  PASS; Vision/Geometry FAIL→fix→PASS; offline clean, instant bounded decision
  navigation, desktop dock and mobile Document/Discussion model · **awaiting new
  R1–R4 dashboard answer** · proposal approval is not implementation authority;
  implementation remains gated on #263 prove-applied, WorkerAdapter proof, #239
  and consumption of landed #266 plus #269/#271

- **#228** — Unify project dashboard settings · P2 · idea · 30m ·
  origin: **human** · implication of **human via watch 12:49**: all
  settings persist and stay identical across tabs and separate browsers ·
  inventory tint + future settings; define one server-side project-settings
  contract carried by `/data.json` + `/mtime`, while typed drafts/submission
  history stay browser-local because they are private words · do not migrate
  only for abstraction unless #227 demonstrates the need
- **#227** — Open the composer with Space · P2 · idea · 30m ·
  origin: **human** · **human via watch 12:49** · when focus is outside
  every interactive/editable control, Space opens composer and autofocuses
  input · subtle enable checkbox; preference persists server-side and syncs
  across tabs + separate browsers, never localStorage · needs settings format,
  migration, keyboard red proof, and transition-conformant UI

- **#225** — Add an `explore` proposal command · P2 · implementation ·
  origin: **human** · **approved via watch 18:25** · one-shot fresh research/
  design subagent produces one concise offline-clean decision artifact with
  alternatives, unknowns and smallest experiment; proposal-only authority;
  accepted outcomes become ordinary tasks · command is a real accessible
  composer kind in exactly maintenance-style secondary disclosure: absent from
  default visible row, never initial, discoverable by established cycling/
  secondary affordance and keyboard/touch · red-first, implement in increments


- **#218** — Add filed-to-landed median · P2 · task · 20m ·
  origin: **loop** · blocked on #217 · `ledger_series` already computes
  arrival/landing pairs and discards them; render the median without a
  velocity score after provenance work
- **#148** — Two sibling guard dirs, one contract, no shared runner ·
  P3 · chore · 30m · fine while they have different owners, wrong the
  moment they do not; extract when a batch would have used it (#124)
- **#205** — [plan: `docs/plans/heartbeat-into-monitor.md` — ezfb's
  `run_watch()` READ and mapped; timeout-on-receive, quiet limit 7,
  `on_quiet` = #200's audit seam] Roll the heartbeat INTO the monitor ·
  P2 · idea · **human 17:45** · **answer to his question: no, not integrated here** — this
  target runs three independent monitors (heartbeat 4.75m, events tail,
  inbox tail) and the timer fires regardless of whether anything
  happened; `ez-feedback-pipeline` has the combined shape, READ IT ·
  today the heartbeat fired ~40 times and most arrived mid-increment or
  mid-stream, where the right action was nothing — the timer is the
  loudest input and the least informative · buys quiet-time, backoff,
  event-driven wake (removes SKILL.md's own warning that an unarmed tail
  loses his `do now:` silently), and his "patterns and schedules" ·
  **CEILING**: 4.75m sits under the prompt-cache TTL, which is why the
  loop is cheap — state that in the design, do not discover it on a bill
  · relates #180, #200, #203
- **#204** — [#166's handler takes a LIST of surfaces (9ed526f) and its
  red-first run is this bug's direct evidence — six motion checks red on
  the native toggle while every end-state check stayed green — BUT the
  list path only fits members of a KEYED LIST, which the four plain
  peeks are not; they want the `.qsec > summary` shape instead (panels,
  bound report). NOT a one-liner; do not let the first annotation here
  suggest it is] The four plain `expand()` peeks still snap · P3 · task ·
  25m · dreams, archive, `.md` list, status overflow · **excused by the
  reason #196 just disproved** — "nothing that MOVES sits below the
  toggle", and all four have panels below · now marked UNEXAMINED rather
  than decided in both docs, so the trap is disarmed · his rule says
  "no size below which this stops applying"; rec: apply #196's
  section-fold shape to ONE and see if it falls out cheaply before
  deciding all four · after #199
- **#203** — Guard servers are not reaped · P2 · bug · 25m · found 17:40
  when a dreamer went quiet: FOUR orphaned watch.py servers in the guard
  ranges, one up **4.5 hours** serving `dev/capture/fixture` — the most
  confusing possible answer for a readiness probe · exactly what
  `parallel-architecture.md` predicted in writing and what cost
  dreamer-identity 20 minutes · **three consecutive agents believed they
  had cleaned up**, so do NOT fix by asking for more care · rec: bind
  port 0 and let the OS assign (removes the class), probe for something
  only THIS server serves, reap in a trap/finally, log what was started
  and killed · belongs with #148 + #192 in the shared runner · **a guard
  red only under LOAD is worse than plainly wrong** — the first re-run
  exonerates it and teaches everyone to re-run; if the runner ever
  retries, it must SAY it retried (qsec 18:17, prominence at 7ac4f02:
  the trace armed on the click, so it measured its own input latency) ·
  **~21:05**: panels found 39899 held, moved to 39893, and later NAMED
  the holder (pid 2331175, `watch.py --target /tmp/... --port 39899`,
  minutes old — legitimate, not an orphan) · the discrimination rule
  that fell out: TARGET PATH + ELAPSED together are the evidence — a
  /tmp target minutes old is somebody working; the same command on a
  repo target hours old is the orphan class · when a held port is
  found, capture `ss -tlnp` and name pid+command in the report ·
  **a mechanical discriminator that needs no judgement** (2026-07-27
  17:44): `readlink /proc/<pid>/cwd` ending in ` (deleted)` means the
  lane that started it is gone, full stop — target-path-plus-elapsed
  still needs a human to weigh "is 20 hours long", and this does not.
  Found by it and reaped: pid 1652343, `watch.py --target
  dev/capture/fixture --port 39951`, up 21h, cwd
  `/tmp/pi-agent-9f527dd0-…(deleted)` — the outgoing pi lane's, and the
  exact fixture-server hazard above · **two more still up**, both /tmp
  targets that still exist so the deleted-cwd test does not fire: 897036
  (`/tmp/a250/target`, 26h) and 3408270 (`/tmp/revieworder-green/target`,
  20h) · left running deliberately — reaping them is a judgement call and
  the reaper should make it, not a coordinator doing it by hand
- **#201** — Stream and control an agent's TUI in the browser via herdr ·
  P2 · idea · several increments · **human 17:27** · substrate EXISTS and
  is documented: `~/.llm-general/ai-coding/herdr/` verified against 0.7.4
  protocol 16, PTY panes over a Unix-socket NDJSON API + status
  classification; two reference consumers · **read those docs, do not
  re-derive** · **the hard constraint**: watch/dreamhub are stdlib-only,
  single-file, no build step, offline — a browser terminal normally means
  xterm.js · three options (vendor a single-file build · render the ANSI
  subset ourselves · render STATE not the TUI) and it needs deciding
  before code · **it turns dreamhub from read-only into a control plane**
  — the localhost bind and per-target isolation must survive explicitly ·
  **`/compact` button FIRST**: `compaction.md` already has the protocol
  and #127 parks the sender in stage 2, and it needs NO rendering, so it
  tests the herdr path before committing to an emulator · #202 resolved:
  **T3 Connect is Clerk discovery/linking + managed Cloudflare reachability,
  not a terminal/agent protocol**; primary-source research at
  `.dreamwork/docs/research/t3-code-connect.md` · before implementing terminal
  rendering, investigate a supported T3 Code deep-link/embed/adopt-session API
- **#200** — Monitor context usage; threshold triggers a self-audit ·
  P2 · idea · 2 parts · **human 17:23** · his example ("3 questions
  answered ages ago, forgotten?") turned out to be guard pollution, NOT
  his answers — but he could not tell, and that proves the point better
  than the example would have: **nothing in the loop notices that
  something was answered and never acted on** · **(1) do the cheap half
  first**: an entry carrying an Answer/Note sub-bullet while still under
  `## Open` IS by definition unprocessed, and the timestamp is right
  there — dashboard shows "answered 3h ago, not folded", lint WARNs past
  an age; no context monitoring needed and it would have caught today's
  case instantly · **(2) the general one**: MEASURE FIRST whether an
  agent can read its own context usage programmatically — if not, the
  fallback is a proxy and a proxy must say what it is not (#155) · the
  self-audit is worth having as a maintenance item regardless of trigger
  · **#199 gives this its input** — a raw log of everything received IS
  the "what was sent to me" half
- **#215** — No check notices a visual change it was not told to watch ·
  P3 · idea · 30m · #166's `summary::before` legitimately shifted the
  sha column 2ch right and only a human screenshot look caught it —
  "no check noticed a visual change" is the shape this repo keeps paying
  for · candidate: assert the x-position of load-bearing columns in the
  guards that own them, or a coarse screenshot-diff capture (NOT gated)
  that flags layout deltas for a human eye · relates #210's vacuity class
- **#211** — A title that GAINS a priority departs and arrives instead
  of travelling · P3 · idea · 20m · honest today (`data-qid` is the
  title, and the title changed) but a human watching the loop stamp
  `P1 · ` onto an existing question sees a card vanish and a stranger
  appear where it should have been the same card moving up · needs a
  stable identity that survives a title edit, which is the same question
  #77's cross-group morph already answered once — read it first
- **#196** — Dashboard questions section snaps instead of arriving ·
  P2 · bug · 25m · **human 17:12** · `.qsec` from #141 · the page learned
  this lesson all day one surface at a time (#129, #113, #169) and the
  one disclosure he clicks most never got it · build AGAINST
  `transitions.md` — it is the first thing built against that guide ·
  opening is an arrival, closing is a departure and per #174 leaves in
  the direction its list travels · **dreamer-qsec holds it**
- **#194** — [plan: `docs/plans/version-and-upgrade.md`] Version and
  upgrade: `ud-dw-githash`, DREAMWORK.md frontmatter, commit-range pass ·
  P2 · task · 4-5 increments · **human 17:07** · executable reports the
  skill's own version (hash+dirty in a checkout, hardcoded in a CI-built
  zip), read on EVERY load, compared against a hash in DREAMWORK.md's
  YAML frontmatter; on a difference a cheap subagent reads the
  intervening commits for migrations and features worth surfacing ·
  **plan keeps `migrations/` deterministic and makes this the DISCOVERY
  layer** — it reports, it never migrates, because a file existing beats
  a model reading prose · **do the commit trailers FIRST**
  (`Migration:`/`Config:`/`Consent:`) — greppable beats readable, and
  every commit written before they exist is one the pass reads blind ·
  frontmatter changes a file every target has, so it needs its own
  migration + a file-formats row + a lint check in the same commit ·
  **one open question:** endpoints are old DREAMWORK.md hash + new
  `ud-dw-githash`; repo becoming public removes auth but zip/offline still lacks
  intervening objects · rec layered resolver: local Git history, packaged
  generated changelog, explicit public fetch fallback · exclude this development
  checkout from treating ordinary new local commits as release upgrades ·
  trailers LANDED pre-compaction ·
  **githash LANDED 472b9e8** (output is the contract; 8 tests red-first)
  · **frontmatter LANDED 5c19a68** (file-formats row + lint check +
  migration `2026-07-25-14` + this target stamped, one commit) —
  remaining: init step, discovery subagent (both after the open
  question)
- **#193** — A blocked errand is invisible · P2 · task · 25m · an
  errand's `awaiting_human` in `~/.config/dreamwork/tasks/` is read by
  NOTHING; hub listing is opt-in (right call) but the consequence was not
  followed through · same shape as #130/#141 (awaiting_human means HE is
  the bottleneck) and #144 (a silent channel looks like a quiet one) ·
  becomes urgent the first time an errand blocks, which is exactly when
  nobody is watching · rec **(a)**: the errand writes a marker into its
  PARENT target's `.dreamwork/`, reusing a surface that already has his
  attention · inherited by dreamhub stage 2 or dreamtask stage 6,
  whichever is planned first — say so in that plan or it parks twice
- **#192** — Fourteen guards print from a tail handler, so a crash reads
  as a clean sheet · P2 · chore · 30m · surveyed by dreamer-rows at my
  request and then NOT FILED by me; found in dream grooming, one archive
  from being lost · **the gate holds** — `just guards` branches on exit
  code — what lies is the EYEBALL: run one directly, scan for FAIL, and a
  crash looks clean · that is how three of its own fault injections read
  as "proves nothing" · 11 in the gating list, 5 outside; `popbg` NOT
  surveyed · rec: fix the PATTERN via a shared reporter, not fourteen
  files — **pairs with #148**, since the shared runner is where the
  shared reporter lives · waits for dev/capture/ to be free · **the
  runner should also carry the coverage declaration**: every guard states
  which of his routes and gestures it drives — AND ITS TRACE WINDOW. Both
  matter and the second is the subtler: `regroup.mjs` drove the real UI
  correctly and was still green over #191 for a day, because it traced
  5.2s past a 1.6s `holdRerenderUntil` and the tick's own regroup supplied
  the motion it was asserting. A guard that watches long enough will see
  SOMETHING produce the result it wants · **a count is not
  evidence** — a `grep -c` in a compound command reported 6 FAILs where
  the full output held 14, the server having been swapped beneath it; the
  runner reports from full output, never from a count (qsec 19:03) ·
  **and it owns absence-first** (folded 2026-07-27 from the input-safety
  dream, which flagged it for here and was one archive from losing it):
  three guards in one batch, run against a build without the feature under
  test, each waited 30s for a selector that would never appear and then
  reported *"the guard threw"* — a message that says nothing about the
  page and points at the guard. A guard asserts its SUBJECT EXISTS first,
  so absence is one FAIL with a sentence; `history.mjs` does this and its
  red run costs 3.4s instead of 30. The shared reporter is where that
  stops being fourteen separate remembering-to-do-its
- **#190** — The loop's push channel to him is dead, and only the
  dashboard can say so · P1 · bug · 20m · `attn` returns **403, OAuth2
  token could not be validated** (grok/xAI), confirmed twice at 16:20 ·
  it exits 1 so it fails loudly to the CALLER, it just cannot reach HIM ·
  found by failing on a message that mattered: #179's P1 fix and the
  deploy-authority ask · **what still works**: the dashboard reads
  questions.md and status.json live, so both ARE visible at 35110 — he
  is no longer PULLED, only able to find it by looking, and "walk away
  and come back" is the whole promise · the channel for reporting a
  broken channel was the broken channel (cf #144, #136) · fix is
  probably his (re-auth); the loop should not touch a live auth token ·
  **FALLBACK FOUND AND IT WORKS**: the harness's `PushNotification`
  delivered to the terminal at 16:18 (mobile needs Remote Control, which
  is off) · rule now in SKILL.md's Communication guardrail: check the
  push left, fall back, name the channel that carried it — an unnoticed
  failed push is worse than none, because the loop then believes it
  escalated · **still his**: the xAI credential needs a re-auth
- **#189** — World-space anchoring silently collapses on native
  Wayland · P2 · bug · 35m · `screenX`/`screenY` return **0** on native
  Wayland by protocol, so #74's world space becomes "both windows at the
  origin" — no error, and indistinguishable from the feature being off ·
  **you cannot detect the mode from JS**, so detect the SYMPTOM and
  degrade honestly · it works for him today only because his Brave runs
  `--ozone-platform=x11` for an unrelated KWin bug, which could be
  reverted any time · **blocks #187's T1**: the ripple would ride a
  coordinate system that does not exist · research:
  `docs/research-window-coords.md`
- **#188** — Review rows show who they are waiting on · P2 · idea ·
  25m · **not a new state system — the QUESTION axis one surface over**:
  a review is paired with a questions.md entry, so its state IS that
  entry's, and #113 already settled the axis (open = waiting on him,
  awaiting = waiting on the loop, folded = done) · derive from
  `qaState`, so the two surfaces cannot disagree and a review with no
  question becomes visibly unanswerable · the idioms exist: the wisp for
  in-flight (measured free), the accent for him, the dim end for done ·
  **avoid a literal spinner** — this page has a breath, not spinners, and
  a rotating glyph would read as borrowed from another application
- **#187** — A gravity-wave ripple that crosses windows · P3 · idea ·
  60m · **T1** the ripple itself: do it in the SHADER, which is already
  world-space anchored (#74/#100) so one wavefront crosses a window seam
  by construction, arriving later in the further window — "same
  position, same dream" finally used for something · **T2** cross-tab
  sync: the event is tiny, so `BroadcastChannel` plus the existing poll;
  rec against WebRTC for the same result on one machine · **T3
  multiplayer is a THRESHOLD** — everything here is local and has never
  left the machine; decide it separately, and make his "no project data
  ever" rule STRUCTURAL: a fixed-shape payload with no free text, so
  the rule cannot be broken by a later change rather than merely not
  being broken now
- **#186** — A light theme, cycled by seven background clicks · P3 ·
  idea · 90m · **his last sentence is the design**: three states cycle
  and `system` RESOLVES to one of the others, so a cycle can change
  state without changing a pixel — show the state by NAME
  ("system (light)"), because a flourish acknowledges the click where a
  name answers it · **the cost is not the cycling, it is the
  calibration**: the page is dark by construction, and the ramp, accent,
  `--warn`, shader, `.dreamin` blur and favicon were each tuned against
  a dark field, several BY LOOKING · tokens must become the only source
  of colour first, which is an audit pass of its own · #143's six hues
  become twelve, and the amber exclusion band probably moves
- **#185** — A consent gate: blurred, explanation on hover · P2 · idea ·
  45m · a PATTERN, not one panel's chrome — any surface reading
  something sensitive can use it · the design is good because the
  skeleton shows the SHAPE of what is offered without the content, so
  he consents to something he can see the outline of · **the blur must
  be real**: if the bytes are in the DOM the gate is theatre, so the
  server withholds until consent — a server-side gate with a
  client-side face · consent is a PERMISSION (machine-local,
  revocable), unlike `watch-tint` which is a preference and committable
- **#183** — [plan: `docs/plans/composer-row.md`] The composer's `+` sticks to the top when scrolling · P2 ·
  idea · 25m · on a long page the way to send a steer scrolls off
  exactly when he has read something and has a reply · **he named the
  hard part**: it collides with #108's clamp, so vertical and
  horizontal constraints are computed by different rules and must work
  together, not in sequence · the `+` is also #170's ANCHOR, so a
  moving anchor breaks a fit test computed once at open · build with the
  composer-geometry batch
- **#182** — Favicon smooth and graceful, with a rolling notification ·
  P2 · idea · 75m · "too slow, does not look smooth" is the direct
  consequence of #153's one-frame-per-second choice — right for a hidden
  tab, wrong for the one he is watching · **two regimes**: rAF while
  visible, the pre-rendered fallback when hidden, switched on
  `visibilitychange` — which also unblocks on-the-fly generation · the
  cylinder rolls a count up, PAUSES to be read, rolls away · "get super
  creative, multiple visual review-and-fix loops" is a method
  instruction; taste is the deliverable
- **#180** — Stream the dreamer's own events onto the dashboard · P3 ·
  idea · 120m · **APPROVED** 15:36 with his own mitigations, which beat
  the shapes offered: read only the **last 10-20 lines** (the bulk is
  never touched), prefilter to small objects, and gate it behind #185 ·
  counter-rec on `jq`: stdlib `json` does the same job without adding a
  binary the loop cannot assume exists · still needs an answer for
  `resolve_confined`, since the transcript sits outside `--target` and
  that gate is load-bearing · no inotify in stdlib: poll · "4-6
  review-and-improve loops" is a METHOD instruction — report the count
- **#178** — Pretty-print toggle for JSON at `/file` · P3 · idea · 25m ·
  resolves the tension #158 exposed: prose reflows by default, source
  stays verbatim, and JSON is NEITHER — its formatting carries no
  meaning but it is not prose, so reformatting is a VIEW and gets a
  control · general rule worth stating: reformat by default when the
  original formatting carries no meaning AND he never wants it back;
  offer a toggle when he might
- **#177** — [plan: `docs/plans/composer-row.md`] Text boxes grow with what he types, then scroll · P2 ·
  idea · 30m · his numbers: composer 2-3 → 10-15, answer/note 2 → 6 ·
  the different ceilings are right — a 15-line box inside a question
  card would shove the list for a ten-second sentence · **third time
  today** that growing something moves what is below it (#141, #169,
  now) — the growth and #104's travel are ONE gesture · the box's HEIGHT
  is now state, so #118's tick-survival applies to it · fires on every
  newline, so it is the most frequent animation on the page
- **#176** — Paste images into the composer and answer boxes · P3 ·
  idea · 90m · **the biggest new surface the page would gain**: a fifth
  write exception that takes ARBITRARY BINARY, where the other four take
  a short validated string. `resolve_confined` gates serving; an upload
  needs its inverse and there isn't one · **where they live is a real
  decision**: outside the repo means a pasted screenshot never travels,
  so a question read on another machine has text and a broken link ·
  it changes `questions.md`'s shape, so file-formats row + lint check,
  and `human_block()` must handle an embed without a crafted path doing
  what a crafted bullet used to · split it: storage first, render second
- **#173** — Live git status, without EVER taking `index.lock` · P2 ·
  idea · 60m · **the lock constraint is a known injury, not a
  preference**: his CLAUDE.md carries an active mitigation from
  2026-07-10 for background `git status` taking the real lock and
  racing his interactive git. So: `--no-optional-locks` everywhere,
  `GIT_OPTIONAL_LOCKS=0` in the server's env, read-only commands only,
  and a guard asserting the lock never appears during a poll · three
  cadences by design (status 5-15s, PR much slower, CI slower still and
  only when a PR exists and is not draft) · PR/CI go through
  `ud-dreamwork-github`, which already owns `gh`
- **#172** — Put project identity prominently in the title section · P1 ·
  implementation · 25m · **human via watch `do-next` 14:01** · show the
  target project name (`ud-dreamwork` here) in a materially more prominent
  position within the visible title section; queued immediately after #217
  because both modify the dashboard shell/CSS · keep the earlier invariant
  principle: **anchor what is invariant to an edge, not to a variable-width
  neighbour** — the route title varies while repo identity does not, so the
  identity must not be shoved about by unrelated route changes · document the
  rule in `watch-design.md`; deterministic desktop/mobile captures and
  visual-review-and-fix convergence required · do not infer first-sight
  provenance from this later human priority update (#216) · #153's browser-tab
  title remains related but does not broaden this visible-title increment ·
  **read his references first**: `grok-build`, `codename-thin` at
  `ssh://x-game:src/codename-thin`, on another machine
- **#171** — Ascii vignette at the screen edge, from the loop's own
  words · P3 · idea · 90m · "we will play with some parameters" is an
  instruction about METHOD — ship the axes adjustable, expect to steer ·
  the content idea is what makes it belong here: DREAMWORK.md's own
  phrases murmuring at the edge · **never render questions.md there** —
  his words are his · two ambient systems now share a frame budget with
  the shader
- **#170** — [plan: `docs/plans/composer-row.md`] Composer opens LEFTWARD so it stops covering text · P2 ·
  idea · 25m · hang its top-RIGHT corner under the `+` instead of its
  top-left · "when there is enough room" is the requirement: prefer
  left, fall back to right, never clip · the anchor MOVES (#110 travels
  it, #108 clamps it), so the fit test runs at OPEN time, not at load ·
  `position:fixed` is not viewport-relative under a transformed or
  filtered ancestor — measure the rect, as with #160
- **#169** — An expanded element becomes PROMINENT, not just taller ·
  P2 · idea · 35m · expanding is a change in IMPORTANCE, not a reveal —
  the thing he opened is now the subject of the page · extends the
  fold-motion contract and belongs to the IDIOM (#111, #141, and
  #165/#166 inherit it) · **two traps**: `font-weight` steps rather than
  transitions unless the face is variable, and growing padding moves
  everything below, so the growth and #104's neighbour travel must be
  ONE gesture — the #141 lesson again
- **#168** — Keyboard shortcut opens AND focuses the composer · P3 ·
  idea · 20m · **check #92 first** — a Ctrl+K palette is already filed
  and two answers to one question is worse than either · the hotkey trap
  is already a lesson: a bare key must ignore keystrokes while a text
  field has focus, and this page now has many · rec open-or-focus,
  NEVER toggle-closed: a keystroke that discards what he typed is the
  #118/#131/#162 family. Escape closes
- **#167** — Composer text box translucent, blur on Chrome only · P3 ·
  idea · 25m · reading "a little blue" as "a little BLUR" (the Firefox
  parenthetical settles it) — flagged, since a blue TINT would collide
  with #143 · `@supports` cannot gate this: Firefox supports
  backdrop-filter, it is just expensive · rec UA-gate with the reason in
  a comment, because the measure-and-back-off alternative FLICKERS ·
  measure p95 with it on and off; blur over a live shader is the most
  expensive pairing on the page
- **#164** — [plan: `docs/plans/composer-row.md`] The button row becomes an information scent · P2 · idea ·
  75m · his verbatim design: the row is a CONVEYOR — non-default
  commands apparate at the left, push the rest right, and are consumed
  by the `...` menu at the right, sliding UNDER it and fading by
  PROXIMITY (not time) as they approach. Selecting a default slides
  everything back left. Reuse #104's regroup on a horizontal axis ·
  subsumes #162(a): a row that cannot wrap · depends on #161
- **#162** — Composer cosmetically vanishes on a mode switch · P3 · bug ·
  15m · the original wrapping half was subsumed by the composer-row plan;
  #163's guard proves the draft survives live and stored (8d0e6a7), so the
  remaining mode-switch disappearance is cosmetic, not destructive ·
  reproduce before changing the #131 dismissal path
- **#161** — [plan: `docs/plans/composer-row.md`] The composer's `...` menu: position, shape, vocabulary ·
  P2 · bug · 20m · centre the dots (MEASURE first — #123 was the same
  shape and took two wrong diagnoses) · **on the RHS, in the button row
  but hard right with a gap** (his 14:31 refinement) · fill, no stroke:
  a menu REVEALS where a button ACTS, so **outline means "this acts",
  fill means "this reveals"** belongs in watch-design.md as vocabulary,
  not as styling for one control. The fill is a surface colour, never
  the accent · #164 depends on this
- **#160** — Frame-time graph should hug the RHS wall · P3 · bug · 10m ·
  check `position:fixed` is not containing-block-trapped by an ancestor
  with transform/filter (already a lesson, and this page has several) ·
  and confirm the overlay is dev-only — a diagnostic that reaches him by
  accident is the more interesting bug
- **#159** — "sent to the dream" appears instead of arriving · P3 · bug
  · 15m · use `.dreamin`, which only started working today (#154) ·
  ~~check the departure too~~ **answered, do not re-derive** (2026-07-27,
  folded from the gesture batch dream before archiving it): the two
  hand-clears are *retractions* — the page withdrawing a claim that has
  become false — not departures, and the real departure is the panel's,
  which already drifts away on the same soft blur it arrived on. A false
  confirmation that fades slowly is a false confirmation that is quieter,
  so this was recorded in `watch-design.md` (#159/#255, "what it says
  arrives and departs") rather than animated · that leaves only the
  ARRIVAL · verify by per-frame trace, since a two-frame
  fade looks instant and passes a "did it appear" check
- **#156** — Lint questions.md at WRITE time (PostToolUse hook) · P2 ·
  idea · 40m · his idea, and it is the strongest version of the fix:
  every current defence fires LATER than the mistake (lint at init and
  in `just test`, the dashboard at read time). A hook fires in the same
  turn, while the agent that mangled it still holds the context ·
  `lint.py` already does the checking, so the hook is thin · **his
  error-message spec is the deliverable**: where, what, expected, and a
  pointer to the format · **bundle with #138** — both are Claude Code
  hooks, ship the plugin or ship neither
- **#152** — A dangling-parent check, deferred WITH A TRIGGER · P3 ·
  chore · 15m · (b) prose-wrap: measured, do not build — eleven long
  lines, three of them unwrappable frontmatter · (a) the ledger carries
  ONE chain line and that is correct, so a checker today checks nothing.
  **Build it when #114 lands** (chains become something he sees) **or
  when there are >5 chain lines**. The check is right; the timing is
  wrong
- **#133** — Teach watch.py a URL prefix · P3 · task · 45m · do it
  inside #124's server-core seam; unblocks the single-URL hub layout
- **#122** — Smokey awaiting-fold text: the words warp, a ghost copy
  blows backwards into the aether · P2 · idea · 60m · his brief is
  verbatim in the task; it is the dream dissolve's ghost held low and
  continuous, not a new effect. Taste is the deliverable — wants a
  dreamer that iterates on captures until satisfied
- **#124** — Break up watch.py; norms for cheap parallel work · P2 ·
  task · 120m · plan: `docs/plans/parallel-architecture.md` · seams as
  batches demand them, starting with #112's components
- **#112** — Design proposals become fragments + shared template · P2 ·
  task · 90m · plan: `docs/plans/artifact-templates.md`
- **#207** — Deletion must be observable, as a CLASS · P2 · idea · 30m ·
  from #86's first find: `watched_mtime` statted only files, so a
  deletion could never change it and an unloaded plugin haunted the menu
  until an unrelated write · the instance is fixed (a5a889d walks the
  directories) but the class is unguarded — several contracts here are
  "unloading is the absence of a write" (fold-by-complement,
  human_block, plugin-commands.json) and all assumed absence was
  observable, unchecked · a guard that DELETES (a dream, a review) and
  asserts the open page loses it would cover the class, not the instance
- **#98** — Show the open queue on the watch dashboard · P2 · idea · 40m ·
  new page surface, fit-check at selection
- **#114** — Dashboard renders the active goal chain · P3 · task · 25m ·
  stage 3 of #95; status.json already carries `goal`
- **#92** — Hand-rolled Ctrl+K command palette · P3 · task · 40m
- **#99** — [plan: `docs/plans/composer-row.md`] **P2** The popout composer has DIVERGED · task · 25m ·
  re-raised 15:48 with detail · it still carries the dropdown #103
  replaced, and has missed #121, #161 and #164 since — `lessons.md`
  says a second mount is the cheapest audit of the first, and nobody
  ran it, so the popout became a museum of the composer's previous
  state · **the fix is "there is ONE row", not "restyle the popout"**:
  build #164's conveyor as a component both mounts use, and it cannot
  drift again · his extra-width idea then falls out FREE — more width,
  more buttons visible before they tunnel, no special case · depends on
  #161 and #164; doing it first means building the row twice ·
  **it drifted AGAIN at 16:54**: the popout has its own `.pmsg`, so
  #159's arriving confirmation arrives inline and still POPS in the
  popout · dreamer-gesture left it deliberately (fixing it in two places
  makes the copy harder to delete, not easier) — the right call, and the
  fourth divergence this task has collected
- **#100** — Shader lens world-space so blur matches at a window seam ·
  P3 · task · 30m · the last break in "same position, same dream"
- **#73** — Split-view support for watch pages · P3 · experiment · 30m ·
  the shader half landed as #74; the open part is the affordance
- **#50** — ud-dreamtask stage 6: harvest past dreamstates · P2 · task ·
  gated on Max · stages 1-5 are complete in the installed sibling repo;
  only the core-init widening remains, and its open question recommends
  waiting for real dreamtask use before deciding what is worth harvesting
- **#80** — Pick a second dogfood target (hark or c2c) · P3 · chore · 30m ·
  **blocked**: human pick

## Recently landed

- **#312** — The command palette lets a phone scroll the whole page sideways ·
  P2 · Web UI bug · ~30m · origin: **loop** · found by dreamer-reviewsplit
  while scoping #305's responsive checks, and deliberately left out of scope so
  #305's suite was not gated on someone else's bug · at a 390px viewport the
  page overflows **122px horizontally on EVERY route**, dashboard included, and
  the overflowing element is `.cmdmenu` · this is shipped behaviour on the
  deployed dashboard, not a regression from #305 · `watch-design.md`'s
  responsive contract says the body must never scroll horizontally, so the
  styleguide already forbids it and no ruling is needed · wants a guard at
  390px that asserts `documentElement.scrollWidth <= clientWidth` on each
  route, which would also catch the next one
  · fixed in `65e9d1e`, merged `c0d6071` · **the root cause was subtler than the
  filing**: the menu overflowed while SHUT, because `visibility:hidden` is not
  `display:none` — the box stays laid out and keeps counting toward
  `documentElement.scrollWidth` on every route, palette open or closed. That is why
  it shipped: nothing looked wrong · `.cmdmenu` now anchors to the ⋯'s right edge
  and opens leftward, clamped by `max-width:calc(100vw - 2rem)` · the reveal is
  provably untouched: that gesture is `translateY(-6px)` + opacity + blur, purely
  vertical, so a horizontal anchor change cannot reach it · guard
  `dev/capture/hfit.mjs`, red-proven by reverting the fix — all three routes fail at
  exactly 122px naming `#cmdmenu`, plus 109px menu-open, while its precondition
  checks stayed green, so the red was the contract failing and not a hollow guard ·
  it asserts the palette exists and the menu is POPULATED before measuring, because
  "no overflow" is otherwise satisfied by an absent subject · **written by a ccc
  glm-5.2 subagent that was KILLED before committing or reporting**; work recovered
  uncommitted from the worktree and validated by the coordinator before landing, and
  its transcript was lost to a `| tail -40` in the dispatch — see lessons.md ·
  620 pytest, lint clean, hfit PASS on master · noted, not filed: the menu's own
  reveal has no motion guard (`cmdcap.mjs` does not reference it), which is
  pre-existing and was not #312's to fix

- **#303** — Make `lint.py` notice a `status.json` that lost known keys · P3 · landed 2026-07-27 ·
  chore · 20m · origin: **loop** · goal: make a silent projection-rewrite loss
  loud ← DREAMWORK.md *Nothing fails quietly* · this coordinator's wholesale
  rewrite of `status.json` at 16:07 dropped `retired_today` (fifteen prior
  lanes' retirements) and lint reported the result **clean**, because a
  projection missing a key is indistinguishable from one that never had it ·
  it caught the estimated future `last_tick` in the same write, so the shape of
  the fix is known: warn when a previously-present key disappears · needs a
  durable notion of "previously present" that does not itself become a second
  fallible truth — simplest candidate is the git-tracked handoff/doc trail
  rather than a new sidecar file, and status.json is gitignored, so decide that
  before implementing · check by reddening on a key removal, not on a schema
  list that would need updating with every new field · **the git-tracked route
  is refuted (2026-07-27 17:15)**: the only git-tracked description of this
  file is `file-formats.md`'s field table, and (a) it does not name
  `retired_today`, so it would have missed the exact incident that filed this,
  and (b) treating it as required would red-flag every fresh target, whose
  status.json is nearly empty by design — the same cry-wolf failure #306 was
  measured against · that leaves two live options, both needing a call: a
  gitignored `.status-keys` memo beside the gitignored file it describes (costs
  `lint.py` its read-only character — it writes nothing today), or a small
  merge-writer so a wholesale rewrite has to be deliberate, which is the
  *remove the opportunity* answer but adds a module and does not detect a
  coordinator who never calls it
  · **call made: the gitignored memo**, `.dreamwork/.status-keys`, one key per
  line. The merge-writer option was rejected as the primary fix because it cannot
  detect a coordinator who never calls it — and this session's own writes were all
  load-modify-dump merges already, so the option would have prevented nothing while
  the incident it was filed for still happened · the entry did not name the
  load-bearing property and it only surfaced while implementing: **the memo must be
  APPEND-ONLY**. Re-recording the current key set each run makes the first run after
  a bad rewrite adopt the reduced set as its baseline — one warning, in the same run
  as the mistake, then permanent silence. Union-only means a lost key keeps warning
  until a human deletes the line, which is the only act that should be able to
  accept a retirement · red-proven by INJECTING the plain implementation
  (`union = current`): exactly one of the nine tests failed, and the other eight —
  including `test_the_real_incident_goes_red` — PASSED over it, so a single-run
  proof cannot see this bug at all · lint.py gains its first write, priced
  explicitly: a write failure WARNs rather than raising, so a read-only checkout
  still lints · 620 pytest (+9), lint clean

- **#308** — Record the whole-pixel rounding trap in `transitions.md` · P3 · landed 2026-07-27 ·
  chore · 10m · origin: **loop** · goal: a motion guard should not be able to
  report a clean ease as a snap ← DREAMWORK.md *Nothing fails quietly* · found
  in dream grooming (#142's batch, one archive from being lost): rounding a
  per-frame trace to whole pixels reported a clean 2.1px ease as a snap, which
  is an instrument bug that presents as a feature bug · the trap is live in the
  idiom, not hypothetical — `reviewsplit.mjs`'s `distinct()` rounds, and it is
  only safe there because its travel assertions require >=60px of movement, so
  the guard whose gesture IS small is the one that will be bitten · belongs in
  `transitions.md` beside how to check a transition, which is where someone
  writing a motion guard is already looking · **blocked while
  dreamer-reviewsplit owns `transitions.md`** — take it after #305 merges
  · **it turned out to be three traps, not one, and the document's own opening
  rule was the source of the other two.** `transitions.md`'s first instruction for
  checking a transition said *assert the count of distinct intermediate positions*,
  which is what `headertravel`, `regroup` and `morph` encode and why all three go
  red on a slow box (#311) · so the bullet is now split: assert the frames you
  captured are PART-WAY (frame-rate-free — a teleport has none at any frame rate),
  and never an absolute count · plus the rounding trap this task was filed for,
  plus the mirror-image fixed-window terminal-state trap `dismiss.mjs:134` encodes
  · all three named as one mistake: **a motion check must not encode a property of
  the machine** — frame count, pixel rounding and elapsed-time windows are all
  facts about the box, and each turns a guard into a load meter that reports its
  findings as feature bugs · the cited idiom was verified in place rather than
  taken on report: `reviewsplit.mjs:148` filters strictly-between with a 3%
  deadband, and `qsec.mjs:157` does the same with no tunable threshold at all
  · landed in `9ba67db`, whose ledger half this entry is — that commit's message
  claimed the close while `tasks.md` still listed it Open, because the guarded
  edit and the commit were chained with `;` instead of `&&`

- **#305** — Read a review document and answer its question side by side · P1 · landed 2026-07-27 ·
  Web UI feature/design · ~75m, **needs splitting** · origin: **human** ·
  **do next via watch 16:34** · sent from `/review?p=tasks-page.html` while
  reading the #281 artifact, so the friction is first-hand and the page he was
  on is the page to fix · **his words, kept whole:** "should be able to scroll
  the question alongside a review document, and the answer/add note input
  should stay glued to the bottom in line with the bottom of the review
  document. Above that the text from answering should fade out close to the
  answer box (unless it is at the end of the question text body). use intuition
  and judgement to fit the webui aesthetic + remain consistent with design +
  produce an excellent design. Additionally, there should be an invisible
  vertical bar between review doc and question being answered that allows
  dragging left/right to change width of review doc and question block. We also
  can extend the height of the review doc and RHS column if the height of the
  window allows." · six distinct asks, and the last three are separable:
  (a) question scrolls alongside the document rather than after it,
  (b) the answer/note input is glued to the bottom, aligned with the document's
  bottom edge, (c) question text fades toward the input, suppressed when the
  body already ends there, (d) an invisible draggable divider resizes the two
  columns, (e) both columns may grow taller when the viewport allows,
  (f) the whole thing must read as this page's own aesthetic, not a generic
  split pane · **a correction to this entry's first reading, made before
  starting:** the coordinator initially called the width question a gate on
  #281 Q1 and that was wrong. Q1 asks whether **/tasks** may become two-pane;
  this is **/review**, which `watch-design.md` already names as *the* width
  exception and which already renders the question beside the document via
  `buildReview(name, q, d)` and `?q=`. So this restructures an existing wide
  page rather than creating a second exception, needs no ruling from him, and
  the two are separable — though landing it does weaken Q1's "a second
  exception is how one column becomes two" argument, which is worth saying
  when he answers ·
  the divider needs a persisted width, a keyboard-operable equivalent (a
  drag-only affordance is not reachable), a reduced-motion story, and a
  narrow-viewport fallback that stacks rather than shrinking both to unusable ·
  the fade is a gradient over live text, so it must not clip the last line or
  make copied text lossy · obey transitions.md and watch-design.md · likely
  three increments: the two-column shell + splitter, the glued input + fade,
  then the height/responsive behaviour · **the three-increment brief was wrong**
  (17:19) — the feature has no working intermediate, so it lands as one; see
  lessons.md · increment 1 committed in `.worktrees/305-review-split`
  (`a0cc24a`, 667 insertions) and coordinator-reviewed: 25 guard checks, each
  shown red against a build broken in the way it names, nine injections · it
  also fixed a latent bug of its own: a scroll offset assigned to a node the
  live-tick swap is one statement old clamps to zero and reports nothing, so
  his typed draft's scroll position had been silently discarded on every tick
  since #118; now a `putScroll()` that reads back and retries (#179's rule
  applied to the other thing a restore hands back silently) · **the class was
  audited and is contained** (17:28): `restoreReviewFrame` preserves the live
  browsing context rather than recreating the iframe, so its `scrollTo` never
  meets a fresh node, and the `setSelectionRange` calls are not
  layout-dependent — no third instance, do not re-audit · **MERGED** at
  `ae2fd58` (a real merge, two parents; all five branch commits are ancestors),
  plus `19c6aca` removing a diff3 base marker the coordinator's own
  conflict-marker sweep did not name · merged tree verifies at **611 pytest +
  54 subtests, lint clean**, and both parents' `lessons.md` content was proven
  present by set containment rather than by absence of markers · guards: the
  two motion FAILs seen in the first run (`headertravel`, `regroup`) were
  CONTENTION, proven by re-running the identical commit alone — see #311, which
  carries the evidence · the dreamer was retired at 18:44, harness-confirmed
  stopped; worktree clean apart from gitignored `__pycache__`
  · **verification, stated honestly**: 611 pytest + 54 subtests, lint clean,
  and all 40 guards pass on this commit — but NOT all in one run. The full
  solo suite was 38/40 with `dismiss` and `morph` red; both PASS in a
  two-guard re-run of the identical commit, exactly as `headertravel` and
  `regroup` did after the concurrent-suite run. Four load-sensitive guards,
  and which ones go red depends on what else the box is doing — the box sat
  at load 40-90 (16 cores) throughout from other agents' work. `reviewsplit`
  itself, 47 checks including the coordinator's line-406 fix, passed in every
  run. See #311, which now carries both failure shapes and the evidence ·
  dream archived; worktree and branch removed

- **#309** — Coherence re-read of SKILL.md + initialization.md · P3 · origin:
  **loop** · landed 2026-07-27 · the recorded DREAMWORK.md routine, run by a ccc
  glm-5.2 subagent in a worktree and validated line by line before anything was
  applied · **one real contract bug**: SKILL.md said the ledger is "open tasks
  only" while `## Recently landed` is load-bearing — `parse_ledger` returns both
  id sets from it, #304's `check_ledger_sections` ERRORs on a split disagreement,
  the burndown's completions come from its git history, and #306's stale-ask
  check reads the landed set. A coordinator following SKILL.md literally would
  have broken all four quietly, and the phrase predates the checks that made it
  costly · **one internal contradiction**: the field list a filer actually reads
  omitted `origin`, the one field `lint.py` ERRORs on, so filing from the
  Commands section alone minted an entry that failed lint next increment · both
  fixed; the growth note (the Subagents steering block is the candidate for the
  next lean pass) is recorded, not acted on · everything else checked out —
  #290, #216, #304, #307 and the worktrees plugin are coherent across all four
  files, the 11-step init lists match, and no named file/tool/flag is stale ·
  audit at `.dreamwork/review/evidence/309-skill-coherence-audit.md`

- **#310** — Audit `dreamhub.py` against `dreamhub-design.md` for drift · P3 ·
  origin: **loop** · landed 2026-07-27 · a ccc glm-5.2 subagent in a worktree,
  five findings all validated by the coordinator against the cited lines before
  anything was applied · all five were the DOC being wrong, not the code: the
  hub renders `agents[].owns` while the writer's contract omitted it; "not yet
  wired into `just test`" had been false since #134 (`09e3397`) while
  `dev/hub/README.md` already assumed the wiring; `agents[].in_flight` has TWO
  readers and was in neither doc; `deployed.py` is path-loaded and was named as
  a dependency nowhere, with `just deploy` snapshotting `watch.py` only; and one
  guard was credited with covering four contracts it covers two of · **one claim
  of its own corrected on review**: it read `kind`/`awaiting_result` as
  consumed by nothing, but `watch.py` folds every unnamed agent key into "the
  rest" deliberately — *"Whatever is LEFT, not a second known list"* — so the
  field list is a menu, not a whitelist, and that is now stated where someone
  would otherwise prune it · audit kept at
  `.dreamwork/review/evidence/310-hub-drift-audit.md`

- **#248** — Decide whether answers records need persisted IDs · P3 · design ·
  origin: **loop** · landed 2026-07-27 (`1fc4bc7`) · **ruling: defer, with a
  trigger** · a ccc glm-5.2 subagent measured rather than speculated — 0 Open,
  6 Answered, 0 exact-content twin pairs, matching `lint.py`'s own count — and
  found the decisive fact: reordering two byte-identical entries is a no-op on
  the file, so the "identity lost through reorder" the entry worried about has
  no observable consequence, because the records ARE the same identity by every
  field the schema treats as meaning · the only identity consumer, #238's
  open-state restore, already fails closed (#247), so the wrong outcome a
  durable id would prevent does not occur · revisit on: a human-reported
  collapse where he cares which twin survived, a workflow treating same-day
  same-text entries as intentionally distinct (#229 is the candidate), or a
  second aid consumer that is not fail-closed · analysis at
  `.dreamwork/docs/answer-record-ids.md`

- **#307** — Make the doc map's plans row checkable · P3 · origin: **loop** ·
  landed 2026-07-27 · the map's one row that enumerates a *directory* had
  drifted to 8 of 14 plans, silently, because nothing reads prose — six plan
  docs a reader of the map could not learn existed · kept the enumeration
  (detail is ranked, never withheld) and made it a shape: `check_doc_map_plans`
  WARNs both ways, stem-on-disk-not-listed and listed-with-no-file, contract in
  `file-formats.md` · **red first on the live drift**, not on a fixture

- **#306** — Notice an open question whose subject has already landed · P2 ·
  origin: **loop** · landed 2026-07-27 · `check_landed_asks` warns when an open
  `questions.md` entry names **only** task ids that are in the ledger's landed
  set, so a shipped feature can no longer read as an open gate the way #290 did
  for ~15 hours · **the rule is ALL named ids landed, not any, and that was
  measured before it was written**: the naive any-landed rule was run against
  this repo first and fired on the real `#229/#270 topic chats v2` question,
  where #270 had landed but #229 was still open and the ask was genuinely live
  — a check that cries wolf on a live question teaches the reader to ignore it ·
  WARN not ERROR, deliberately: an amendment thread on a landed task is
  legitimate and this cannot tell one from a forgotten fold, so it names the id
  and asks for a fold or a reason · the real cure — one write path that folds
  the ask when the answer is recorded — stays with #263; this is the detector ·
  **found while building it, and fixed as part of it:** `test_lint.py`'s `run()`
  helper hand-maintained its own copy of the check sequence and had drifted six
  checks behind `main()` (`check_answers`, `check_landed_asks`, `check_run_mode`,
  `check_plugin_commands`, `check_submissions`, `check_dreamwork_frontmatter`),
  so a new check was exercised by nothing while its tests passed — the exact
  checks-that-cannot-fail shape this repo keeps rediscovering. Both now call one
  `lint.run_checks`, which cannot drift from itself · red-first: the two
  positive checks failed on the absent function, and the all-vs-any decision was
  proven by running the naive rule and watching it flag the live question ·
  604 passed + 54 subtests, lint clean

- **#304** — Anchor the ledger section split to line starts · P2 ·
  origin: **loop** · landed 2026-07-27 · a section is now opened by a heading
  LINE and nothing else, so an entry may quote a heading in its prose as freely
  as it quotes anything else · `parse_ledger` previously located both sections
  with an unanchored `str.split` on the heading text, which this coordinator
  tripped TWICE in ten minutes while writing entries about this very parser —
  the ledger read 2 open / 187 landed against a true 105 / 84, every derived
  number on the deployed dashboard was wrong, and `lint.py` called the file
  clean throughout because it counts entries without splitting sections at all ·
  fixed with strip-equality line anchors matching `lint.py`'s own heading rule,
  so the two readers cannot disagree about where a section begins · **and the
  check, because the parser fix alone leaves the next reader with no signal**:
  `check_ledger_sections` walks the lines independently and errors when its
  open-entry count disagrees with `watch.parse_ledger`, naming both numbers ·
  red-first both halves — the parser check failed with #8 vanishing into a
  moved split, and the linter check was proven by reintroducing the OLD
  ALGORITHM verbatim and watching it redden (a regression guard has to be shown
  failing on the regression, so the test monkeypatches the bug back rather than
  asserting a hand-written number) · questions.md and answers.md were checked
  and are immune: `_parse_entries` already walks lines · 600 passed + 54
  subtests, lint clean with the new agreement line at 106 open, burndown +
  provenance + qorder guards PASS

- **#238** — Preserve `/answers` UI state across data refresh · P1 ·
  origin: **human** · landed 2026-07-26, **closed 2026-07-27** · open answered
  disclosures survive a real `data.json` tick through the existing data-keep
  snapshot/restore seam, keyed on a content-derived record identity (title,
  resolution stamp, body, follow-ups, exact-twin ordinal) rather than index or
  title, so reorder or deletion of another entry cannot reopen the wrong record;
  answer identities are stripped from departure ghosts so stale clones cannot
  poison later snapshots · `be27c8f`
  · **closed late, and deliberately on re-verified evidence rather than on the
  commit message**: the work landed 2026-07-26 red-first (open state lost on an
  unrelated refresh, stuck at the old index after reorder, lost after deleting
  another record) but the entry was left reading `in progress` across a
  coordinator handover. Rather than trust either the stale mark or the commit's
  own claim, this coordinator checked that the guard which passed actually
  covers *this* acceptance — `dev/capture/answers.mjs` carries named #238
  phases for reorder, not-stuck-on-index-0, closed-peer preservation and
  deletion — and that it went green in this session's own full sweep
  (596 + 54 subtests, 39/39 guards, 0 failures at `0d1e337`). A guard named
  `answers` passing is not the same fact as the check for this bug passing.

- **#217** — Render honest provenance coverage · P2 · origin: **loop** ·
  landed 2026-07-27 · burndown now names first-sight human/loop/historical
  unknown counts and committed-history denominator; unknown is hatched and
  never inferred as loop, shallow coverage is explicit, mobile/a11y intact ·
  target+HEAD cache and `(rev,path)` snapshots prevent nested-target poisoning ·
  596 + 54 subtests, provenance guard 22/22, Vision + Geometry PASS, Spec +
  Standards PASS after red-first cache fix · deployed :35110 PID 62810 ·
  `c1f5aaa`

- **#299** — Suppress expected peer-disconnect tracebacks at the HTTP
  handler boundary · P2 · origin: **human** · landed 2026-07-27 · exact
  `/mtime` BrokenPipe reproduced through the real handler red (8 failures);
  `Handler.handle` now closes quietly only for pipe/reset/aborted departures,
  never retries, while unrelated OS/application errors still escape · live five
  RST-cancel poll proof, focused 5 + 8 subtests, full 587 + 54 subtests,
  Standards + Spec PASS · deployed to :35110 PID 2367866 · `fe0351d`

- **#216** — Parse first-seen origin in ledger history · P2 · origin:
  **loop** · landed 2026-07-27 · `task_origins.py` walks only ledger-touching
  commits oldest-first and classifies each id once from its first leading-token
  appearance; later edits, current markers, body refs and commit metadata cannot
  rewrite arrival · combined/separate ids, deletions, shallow coverage and path
  confinement are explicit · 23 red-first tests, 582 + 46 subtests, Standards +
  Spec PASS · `e9c30ff`

- **#213** — Enforce forward-only task provenance · P2 · origin:
  **loop** · landed 2026-07-27 · entries whose leading id token contains any
  id >=216 require exactly one `origin: **human|loop|unknown**`; older entries
  may remain unmarked and are never guessed · combined ids key only on the
  leading token, body references do not govern · 12 landed summaries gained
  truthful unknown markers pending #216 archaeology · +17 red-first tests,
  559 + 46 subtests, Standards + Spec PASS · `f9dc636`

- **#296** — Stabilise answers guard premises under load · P1 · origin:
  **unknown** · landed
  2026-07-27 · guard-only fix for two root-caused races: #250 close now
  waits for the previous travel's concrete inline-style cleanup then proves
  the new close armed; #251 binds its original ElementHandle premise to the
  page consuming the phase's own mtime render instead of vacuous `count===2`
  · deterministic sabotage reproduced both exact assertions; 5 focused PASS
  incl 3 under load, full sweep 37/37, Standards + Spec PASS · `395c90f`

- **#158** — `/file` reflows markdown · P2 · landed earlier at `5c45d83`
  (task work 2026-07-27 found the entry stale in Open) · the line moved
  from WHO composed the text to WHAT the file is: `.md` / `.markdown` /
  `.mdx` at `/file` reflow through the same `mdB` as dashboard peeks,
  source and all other paths stay verbatim in a `<pre>`, path-based never
  content-sniffed · #102 rule rewritten in the same commit so it reads as
  reconsidered · raw bytes remain reachable via `/filedata`; full
  Source/Raw toggle is #252, JSON is #178 · reflow guard was left
  asserting the OLD verbatim line — updated to the new branch plus
  hostile-markup inertness and source-verbatim checks, each red-proved
  against a reintroduced break; pytest tokens extended (542 + 46 green)

- **#234** — Minimise the answer-morph rerender hold · P2 · origin:
  **unknown** · landed
  2026-07-27 · `Date.now() + 1600` replaced by named `MORPH_HOLD_MS = 1250`,
  derived from the measured critical path (flipDock's 1150ms transform is
  the longest visible leg + 100ms slack; the 850ms card travel, its 1000ms
  cleanup and the out-of-view ripple all finish inside it) — 850ms was
  rejected as mid-glide · reduced-motion path runs none of the three, so
  the shared constant is pure margin there · new guard
  `dev/capture/morphhold.mjs` drives `tick()` over a forced /mtime change:
  node intact on every page-clock decision inside the hold, release measured
  ~1250ms after hold-set · RED against old 1600ms and 100ms sabotage; load
  flake fixed by stamping `/mtime` response-body completion, the exact last
  await before the tick gate · `morph.mjs` window shrunk 1400→1200

- **#138/#156** — Ship optional compaction/lint hooks plugin · P2 · landed
  2026-07-27 · `plugins/ud-dreamwork-hooks/`, off by default, same family
  shape as ud-dreamwork-github; both hooks re-check the DREAMWORK.md Load
  consent line every invocation and skip silently without it · PreCompact
  appends a bounded preservation-focus record to machine-local
  `~/.config/dreamwork/hooks/<slug>/` (1.5s budget, always exit 0) ·
  PostToolUse lints the ledger on questions/tasks writes under the same
  boundary (4s timeout, ok:false on failure, exit 0) · install.py --print
  default, --apply idempotent with timestamped backup + clobber refusal,
  never auto-applies · red-first 27 tests, 542 + 46 subtests, Standards +
  Spec PASS · `d7983be`

- **#245** — Build `ud-dreamwork-worktrees` plugin · P1 · origin:
  **unknown** · landed earlier at
  `8af7dc3` (ledger rescan 2026-07-27 found the entry stale in Open) ·
  red-first 11→22 contract tests, two independent Standards/Spec reviews,
  publishable package under `plugins/` symlinked into Pi/agents/llm-general
  roots; bounded subagent mode + durable co-agent claims/inbox protocol

- **#250/#251** — Missing-aid answer disclosures + node disconnect proof ·
  P1/P2 · origin: **unknown** · landed earlier at `f17f307` (ledger rescan 2026-07-27 found both
  entries stale in Open) · identity-less answered details use a local
  human-click fold reusing travel/reveal/ghost; original ElementHandle proven
  connected before refresh and disconnected after; 440 tests, Standards/Spec
  PASS, deployed

- **#290** — Add a dashboard-settable main-dreamer run mode · P1 · origin:
  **unknown** · landed
  2026-07-27 · authoritative gitignored `.dreamwork/run-mode` drives three
  selectable modes (lackadaisical / hot / assisted) with hierarchical kept
  visibly planned-disabled behind #264/#288 · server validates, atomically
  writes, and emits exactly one watch event on real change; identical finals
  silent · 10s resettable arm with atmospheric progress bar, RM text parity ·
  one shared pending across tabs: initiator-only POST via sessionStorage owner
  id + CAS claim, followers display-only, cancel tombstone converges peers
  without an event, ownership survives navigation/reload, tab-close orphans
  reclaimed inside a 3s grace · review rounds closed dual-POST race, orphan
  reclaim dead code, tombstone expiry, guard quiet-window and flake findings ·
  TestRunMode 9/9, 515 tests + 46 subtests, runmode guard PASS repeatedly incl
  under pytest -n 2 load; final Standards + Spec PASS · deployed PID 2583034 ·
  `b0db53d`

- **#292/#293** — `/answers` Ctrl+Enter submit and visible question text ·
  P1 · origin: **unknown** · landed 2026-07-27 · Ctrl/Cmd+Enter on the `/answers` ask textarea
  submits exactly once durably: in-flight guard blocks rapid double-press,
  generation invalidation on leaving the route stops a late response touching
  a rebuilt form, failures keep the user's words · submitted text is visibly
  readable live and after hard refresh: permanent `.dreamin` enter-pose
  removed from open-row HTML, keyed one-shot arrival (`open:` aids over
  title+body+ordinal, exact-title twins distinct), computed opacity/color/
  geometry proven live and post-reload, reduced-motion parity, sabotage
  inject proves the guard is non-vacuous · Grok-owned isolated branch
  (`9693106` + `f3f491c` + doc-nit `b931c04`), Standards and Spec reviews
  PASS, 506 tests + 46 subtests, answers guard ×2, merged `73ba7d8`,
  deployed dashboard PID 1053756 serving HEAD

- **#291** — Restore the command composer's 1.5s courtesy-close · P1 ·
  origin: **unknown** · landed 2026-07-27 · successful main-panel command sends again auto-dismiss
  after 1425ms unless input resumes during/after POST; the ~5s confirmation
  remains independent while typing keeps the panel open; manual/context close
  remains destructive · explicitly opened command popouts are persistent and
  prove success remains visible beyond the main courtesy threshold · real guard
  was RED against the prior 5.65s coupling; 504 tests + 46 subtests, dismiss +
  confirmation guards, lint/diff clean; Standards + Spec PASS · `26c4bee`

- **#268** — Hide Dreamwork-only plugins from ordinary skill discovery · P1 ·
  origin: **unknown** · landed/migrated 2026-07-27 · active loops parse only exact bounded
  `DREAMWORK.md` Load declarations and resolve bundled/sibling/explicit packages
  deterministically, reading emitted `SKILL.md` files directly · migration first
  inventories every alias/source across recursive global/project/configured Pi
  roots, requires an exact fresh schema-v1 manifest, and removes aliases through
  a reversible drift-checked transaction · Pi `DefaultResourceLoader` proves
  global/project/configured plugins present before migration and absent after;
  live host post-check is empty while both active sources still resolve · final
  Standards + Spec PASS; 67 focused, 504 tests + 46 subtests · `ac4d57a`

- **#255** — Make composer confirmation self-dismiss reliably · P1 · UI bug ·
  origin: **unknown** · landed 2026-07-26 · one document-scoped `confirmationFor` controller serves
  main and popout: atmospheric arrival, ~5s readable hold, atmospheric
  departure/clear; reduced motion keeps timing and snaps visuals · typing
  cancels only panel courtesy-close; close/route/pagehide hard-clean timers,
  listener and in-flight attempt callbacks; newer submit supersedes older;
  error/rejection/validation replace success immediately · guard REDs proved
  the original permanent main/popout messages, popout enter-snap, fallback
  listener leak and close-during-POST resurrection · `dismiss` + `confirmation`
  PASS, Standards + Spec PASS, 459 tests + 46 subtests · `74837df`

- **#221** — Sort dashboard reviews by exact filesystem datetime · P2 ·
  implementation · origin: **unknown** · landed 2026-07-26 · newest exact `st_mtime_ns` first;
  filename ascending only on exact nanosecond ties; displayed age derives from
  the same stat result; disappearing TOCTOU entries are skipped while other
  stat errors surface · stable keyed review rows travel through the existing
  atmospheric FLIP system and reduced motion settles instantly · causal guard
  proves exact BigInt filesystem order survives server payload, transform-free
  natural geometry and settled DOM; reds cover disabled FLIP, pre-causal DOM
  mutation, smoothly wrong final order and adjacent-nanosecond Number collapse ·
  final Standards + Spec PASS; 459 tests + 46 subtests · integrated through
  `b9159db` · separate #288 authority incident remains open

- **#279** — Prototype a Jupiter-like higher-fluid-dynamics storm shader · P1 ·
  visual experiment/design · origin: **unknown** · completed 2026-07-26 as an honest **failed
  prototype** · all seven supplied references inspected; three standalone
  variants built without touching production · first evidence pass FAILed blank
  capture/telemetry race/submerged geometry; deterministic static pipeline,
  duplicate hashes, readback/contrast sanity and eye/wall composition fixed ·
  final Vision still FAILed reference-level fine turbulence, luminous material
  depth and organic multi-scale detail; Terra evidence/debrief PASS after
  bounding non-white and expected-framing claims · current `watch.py` shader
  remains unchanged; #280 stays blocked · throwaway primary source preserved at
  branch `prototype/279-jovian-final`, tip `a1c180c`

- **#271** — Rerender review docks on cross-browser data ticks · P1 · bug ·
  origin: **unknown** · completed 2026-07-26 · diagnosis:
  `.dreamwork/docs/research/cross-browser-note-propagation-271.md` · current-view
  tick rerender now refreshes remote notes without stale-navigation overwrite;
  preserves live iframe URL/scroll, stable question target, draft/selection/
  resize/scroll/focus and disclosure state · two independent Chromium launches,
  corrected baseline questions-green/dock-red evidence, normal+reduced shared
  non-vacuous guard · independent Spec/Standards review initially failed the
  vacuous scroll, navigation race and RM coverage; all fixed, final PASS · fresh
  `PASS noteprop`; 456 tests + 46 subtests; lint/diff clean; no new style miss ·
  commits `6388e70..2c0652b`

**#270** rebuilt the #229 topic-chat proposal around one #263 receipt authority,
main-dreamer-first operation, explicit bounded worker promotion, shared leases,
idempotent finalisation, attachment MVP, derived indexes and staged cutover.
Grok architecture PASS; Vision/Geometry FAILed then PASSed after anchor/mobile/
long-scroll fixes. Artifact `threaded-topic-chats-v2.html` at `9f08e47`; new R1–R4
question filed, no implementation authority (2026-07-26).

**#233** adds explicit unauthenticated trusted-LAN binding while preserving the
loopback default. Exact Host gates every request; browser writes additionally
require matching HTTP Origin before body/witness; advertised Host is always
allowlisted; IPv4/IPv6, wildcard URLs and warning are explicit. Initial dual-axis
review FAILed and was red-first fixed; final Spec/Standards PASS. Rebased commits
`f4ed3fe..a0de8fc`; 157 watch + 455 project tests (46 subtests each), focused
submission guards, socket probes and lint green; #233 adds no styleguide miss
(2026-07-26).

**#278** found no true open-duration shader acceleration: constant wall-clock
phase, one RAF/mount, stable ~60 FPS and non-monotonic optical displacement.
Phase-dependent agitation and brief navigation warp plausibly explain the human
perception; report `.dreamwork/docs/research/shader-acceleration-278.md` unblocks
#279 without changing the current shader (2026-07-26).

**#258** composable shader emotion research produced the first reviewed
urgency/shader proposal, then the human superseded its simple storm geometry
with a separate acceleration diagnosis, Jupiter-like prototype and selectable
preserved-shader track (#278–#280). D1 composer urgency remains #257
(2026-07-26).

**#266** fixes both observed review-dock wrong-target submissions by resolving
writes through the visible card's stable `data-qid`, never its stale positional
`data-qkey`. Independent Standards/Spec PASS; note and answer were both RED on
baseline and green after; 153 units plus focused `docktarget`/`qacard`, lint and
diff-check passed; deployed at `fe55cd3` (2026-07-26).

**#273** adds mode-and-target-aware accessible names to shared question/dock
textareas and send controls, and floors the send target at 44 px without a
structural layout change. Red evidence, 143-unit module, focused `qacard` browser
guard, lint and diff-check passed; integrated, deployed and cleaned at `a6e98cc`
(2026-07-26).

**#272** visually reviewed the live #229 route in isolated desktop/mobile
browsers. Measured evidence and ranked fixes are durable at
`.dreamwork/docs/research/review-route-ux-272.md`; critical findings are a
composer more than 4–5k px below the viewport and a decision prompt disconnected
across the iframe/dock seam. #273 owns small fixes; #270 owns the structural
proposal (2026-07-26).

**#267** contextual plugin discovery research is durable at
`.dreamwork/docs/research/contextual-plugin-discovery.md`: Pi's hidden
frontmatter retains a user command and dynamic resource discovery still
registers a normal skill. The IGC survivor removes global discovery symlinks
and has active Dreamwork read only declared plugin files from deterministic
install-relative paths; #268 owns implementation (2026-07-26).

**#232** the answer-morph pause is the intentional 1.6s rerender hold around
an 850ms local morph, followed by a phase-dependent 2s live poll; later loop
folding is separate. Diagnosed by requested GPT-5.6 Luna low-thinking agent,
folded into `.dreamwork/answers.md`, and delivered via `attn` (2026-07-26).

**#231** `/answers` is live: the human can ask the dreamer through a distinct,
durable `.dreamwork/answers.md` channel; the seeded governance question is its
first open item. Missing-first-create, unreadable health, raw/client recovery,
strict writes, live draft/focus, failure retention, and atmospheric answered
folds are guarded. Two-axis review/fix/rereview PASS; 136 Python tests, lint,
focused browser guard, and diff-check pass; b87475e deployed (human via Web UI,
2026-07-26).

**#202** “T3 connect” resolved from the human's exact source: Connect wraps an
ordinary T3 Code server with Clerk discovery/linking and a managed Cloudflare
tunnel; it does not supply TUI/PTY streaming. #201 keeps its transport-neutral
`/compact` first increment and gains a pre-render integration investigation.
See `.dreamwork/docs/research/t3-code-connect.md` (2026-07-26).

**#226** cross-browser tint synchronisation was already correct; the identity
guard now proves it through two separate Chromium processes rather than two
pages sharing one process. Focused guard passes with no production change
(human via Web UI, 2026-07-26).

**#181** title/favicon counts now derive from visible open questions, not
hand-maintained `status.awaiting_human` (bfa561f, deployed). Status keeps the
prose naming WHAT waits. Identity guard red-proved the old drift and now
checks status prose cannot alter the count; unreadable `!`, routes, and
favicons remain coherent (2026-07-26).

**#224** successful `do now` returns the composer to `add idea` through the
existing animated indicator path (a6a7ad2, deployed). Red proof held the old
kind; the focused draft guard passes. Rejected/unreachable sends and other
successful kinds are unchanged (human via Web UI, 2026-07-26).

**#157 + #222 + #223** links now promise only reachable destinations
(0c1f5ad, deployed): the collector ships existing target-relative paths;
known target/`.dreamwork/` paths link to `/file`, unresolved local-looking
references stay code, and `github.com/...` becomes external HTTPS. The
working-tree startup ReferenceError reported via do-now was fixed before
commit. Reflow guard, 405 pytest, and lint pass (2026-07-26).

**#206** the race-safe coordination protocol is in
`.dreamwork/docs/plans/parallel-architecture.md` (c59c163): file claims win,
messages wake; reports name omissions; absence waits beyond the report
window; commit-bound instructions name their boundary; explicit staging is
safe only for edits the stager made (2026-07-26).

**#127** deliberate compaction is documented in `compaction.md` plus the
shared harness-dialect table. Reconciled complete: a managed sender belongs
to dreamhub stage 2 because it requires a session handle; optional hooks are
the independently gated #138, not unfinished #127 work (2026-07-26).

**#209** closed by proving the existing keyboard path (4f9ed58): plugcmd
focuses the dots opener, Tabs into a visible plugin command, presses Enter,
and observes the same selected-kind path. The focused browser guard passes;
the implementation was accessible, but the claim had never been exercised
without a pointer (2026-07-26).

**#208** the single `setData` seam is now guarded (b91931a): a static test
permits one assignment inside the seam and requires both fetchers to use it.
Red proof bypassed the seam in `ensureData` and failed on the extra bare
assignment; all 128 watch tests pass (2026-07-26).

**#166** and **#140** were stale duplicate open lines, reconciled against
git and the handoff: commit-row expansion landed at 9ed526f; deployed
revision visibility landed at a621f31. Their detailed outcomes were already
in Recently landed and the 2026-07-25 handoff (reconciled 2026-07-26).

**#214** git history now uses collision-proof NUL framing (db1a1bc): red
proof showed `\x1f` in a subject shifted the old fields; Git `-z` preserves
subjects carrying both former separators because neither a commit message
nor path can contain NUL. Focused git-tail tests, 403 pytest, and lint pass;
gitrow's structural/data checks pass, with motion checks independently red
under severe host contention (2026-07-26).

**#220** a fully blocked queue now enters maintenance (07742b9): selection
says “no unblocked actionable work,” not “list empty,” and reuses the
existing `roll.py --no-backlog`; no duplicate flag was needed. Human steer
via Web UI at 12:03 (2026-07-26).

**#219** browser guards are bounded and self-identifying (ccc47a0): each
capture/hub check has a configurable 120s timeout and prints its name plus
exit code. Red proof: a 1s qacard run said `FAIL qacard (exit 124)`; normal
focused status passed. The original run had not hung — it completed in ~16m
under host load ~68 on 16 CPUs (2026-07-26).

**#212** closed as refuted: a real empty-subject commit preserves the
separator in `git log --format='%h %s'`, so `split(" ", 1)` already returns
`[hash, ""]`. The proposed regression test passed before any production
change; there was no red-capable bug to fix (2026-07-26).

**#210** reconciled as already fixed by #197 (3f411f3): the guard now
sets `AWAIT_N = OPENQ + 2` and explicitly asserts the counts differ.
Git reconstruction found the vacuous historical state at 266db84
(literal 3, open 3); the current focused identity guard passes, and a
sweep found no analogous gated guard (2026-07-26).

**#142** the ledger's own history, drawn (bb56f19) — a burndown below reviews, above status (the top of the page is what NEEDS him; this is context): the open LEVEL as a step line (a filled bar was rendered and rejected — at 12-to-67 open every column reads as a uniform block) over the FLOW (arrivals up, completions down), because the open count alone cannot tell "he steers fast" from "the work is slow"; arrivals/completions are FIRST-SEEN events so grooming's pruning of Recently-landed cannot erase a completion; the entry pattern is lint.py's VERBATIM, asserted identical by a test; provenance reported as `sourced 7/67` coverage rather than a split read as fact (→#213); found regroupBars' cleanup erasing the renderer's own inline height (#198's shape, fixed) and recorded #151's gate here as unguarded ON PURPOSE (a pure function of the series — the check was written, injected against, and could not go red); note: ledger_stats caches on HEAD, so the chart's right edge is the compute moment until HEAD moves — correct, and worth knowing before it is reported as a bug (2026-07-25). **#166** a commit row opens onto its reasoning (9ed526f) — a row IS a <details>, and the expand handler took a LIST of surfaces so the questions fold and the commit row share one gesture (snapshot, regroup, ghost, reveal, reduced motion all literally shared); the more-detail principle is in watch-design.md as three answers (expand = about the thing in place, navigate = its own subject deserving a URL, hover = never for anything not already summarised on screen); red-first showed #204 in miniature — with the native toggle, six motion checks red while every end-state check stayed green; also folded the last missing --no-optional-locks in watch.py (2026-07-25). **#140** the page says which revision it is running (a621f31) — one line under the commits label: dim when current, dimmest-with-why when unknowable, --warn + rail + missing-commits-in-title when stale; deliberately NOT `import deployed` (a deployed watch.py is often the only file on disk, and a read-only dashboard must not execute code out of the directory it watches) so the measurement is inlined and STRICTER — it compares this process's own __file__ bytes, catching #203's orphaned servers, the case that matters most; never silent, because one page's silent-healthy is indistinguishable from no check (2026-07-25). **#197** questions order by priority, decided once in the parse (3f411f3; the contract half — file-formats row, lint check, real entries stamped — had already landed at 6284402 17:32, so the coordinator's same-commit demand was stale and the dreamer's scoping right; the demand still provoked a real find, adopted at 3073055: the linter held a WIDER copy of the marker rule than the parser and blessed the three likeliest typos — the band is now asked of title_priority, never re-derived) — absent means P2 so an explicit P3 sorts below unmarked, Answered deliberately unsorted (expired urgency must not reorder a chronological record), and the fixture needed TWO properties before any check could fail: a real permutation, and an unmarked entry after the P3 one; found identity.mjs gone vacuous (→#210), title-edit identity caveat filed (→#211) (2026-07-25). **#86** P1 the composer renders what a plugin declares (a5a889d) — server filters the file (no core-kind shadowing, `common` never honoured), POST /command reads it per request so the menu never offers what the server refuses, menu items only because the row's width is load-bearing; found and fixed two wider bugs: `watched_mtime` was blind to deletions (→#207) and `tick` looked like the live path and was not (→#208); menu keyboard gap filed as #209 (2026-07-25). **#165** the history panel (91737bd) — sole source is #175's client log because only it knows the OUTCOME, and a panel that apologises per row is worse than a narrow one that states its limit once; failures leave via --warn because the accent marks what NEEDS him, and a failed send from an hour ago is a fact, not an errand (2026-07-25). **#175** every send is witnessed client-side (794d620) — IndexedDB, a DATABASE per project because a column can leak by omission and a database cannot; and the increment's find was a private fetch('/command') that left a third of his submissions unwitnessed, now unified through postJSON with a guard asserting the bare fetch stays absent (2026-07-25). **#163** the draft survives (8d0e6a7) — localStorage keyed by absolute target path (a draft is an unpublished thought, never a repo file; the #143 contrast is stated in watch-design.md), restore never overwrites live text, and the guard caught itself testing the restore while claiming to test the mode-switch (2026-07-25). **#198** the indicator was measured beneath a mid-transform ancestor (a86108e) — every rect read 3% small, error multiplying with distance from the origin; and the 'autocorrect' was unrelated re-renders laundering a permanent bug, not a transient (2026-07-25). **#199** P1 his words are on disk before anything may refuse them (fd3ae3b handler + 0bc0517 contract + migration 2026-07-25-15) — and the guard, by failing, proved questions.md is a RENDERING of his words, not a record of them (2026-07-25). **#191** the answer-morph carries its neighbours (38854bd) — and found that a guard's WINDOW can be the bug (2026-07-25). **#184** CLOSED not-reproduced: neither half; explained by #174, numbers in its dream (2026-07-25). **#179** P1 the focus steal (9e8469c) — focus() into a closed <details> is a silent no-op (2026-07-25). **#174** the cycle travels down (7d3c322) — a departure leaves in the direction its list travels (2026-07-25). **#150** coordination layer audited: relay.py, write-then-wake, agent visibility (2026-07-25). **#147** deployed.py measures by bytes; the hub row says it (59e7728, f3649f4) (2026-07-25). **#145** routing rule adopted (4 buckets) (2026-07-25). **#144** subagent plain text is not a channel; silent agents are shown (2026-07-25).
Pruned in grooming; git is the real ledger. **#143** a per-project tint
(6c49874) — a closed set, a Rodrigues hue rotation preserving the
achromatic component by construction, the existing `/mtime` poll doing the
cross-window sync, and six hues chosen to be distinguishable at 16px AND
to avoid the amber band, since a project tinted amber would paint the
field the colour that means broken. Its contract landed with it (338d17d).
**#153** the tab title and the favicon, and the app name's return as
`dreamwork/<project>` (10ca98a) — shipped in the one shape correct under
both readings of his ruling, rather than guessing. **#153** the tab now says
whether he is needed and the favicon is a ring with one traveller
(266db84, 0cefd06) — hue is which loop, motion is that the loop lives, a
pip is that he is the bottleneck. It ORBITS rather than breathes because
at 16px position reads and luminance does not, found by rendering both at
size. Also 7be4a22: `just guards` now proves the server is its own, after
a stray instance of mine stole the port and ten guards asserted fixture
facts against the live repo. **#155** the styleguide audit
now measures adjacency HONESTLY (487d1a6) — a 3-commit window, so writing
the doc before the code is no longer punished, and a comment saying what
it does not prove: touching both files passes whether or not the doc says
anything, so 29 green commits proved only that the files moved together.
Deliberately NOT gated — making adjacency mandatory would be worse than
the status quo. **#141 #149** (2bf61da,
6099998) — the questions section folds, counts and greys, keyed on
`questions_health` rather than the count so a calm grey can never sit
under #136's warning; and it would have SNAPPED SHUT under him every 2s,
the innerHTML-swap state loss for the third time after #118 and #111.
Restore only ever re-opens, so a stale snapshot cannot take anything
from him. **#132 #151 #154** (2c42da1)
— relative commit ages riding the page's existing per-second sweep, five
rows arriving as one gesture on a new SHA rather than on a tick, and the
enter-snap class fixed: `.dreamin` had NEVER worked for question cards,
so every arrival since #104 was a pop-in and the motion matrix's
"arrived: snap, then ease in" row had been false the whole time. **#119** DECIDED, not built:
selection stays in SKILL.md. The idle branch is by definition where no
other trigger fires, so a pointer would be followed only by a loop that
already knew what it was looking for; and step 2's dot line only works in
front of the reader — "explicit thinking time" behind a link gets read
past rather than performed. Only the 13-line maintenance rotation is
movable, which does not justify a fourth reference file. (Argued by the
#120 reviewer, taken 2026-07-25.) **#136** an unreadable
questions.md now says so, in a second `--warn` colour because a fault in
the live accent reads as activity (606ceaf) — and the sharper half was
unbriefed: `postAnswer` discarded its response, so a REFUSED write told
him it had succeeded, cleared his text, and the tick restored the
question two seconds later. **#134** the hub guards are in `just test`;
the recipe comment now names all THREE guard shapes, since `health`
already broke the one-contract claim before dreamhub arrived. **#135** the producer half of
the format bug (d9ce212) — `file-formats.md` states the shapes, init seeds
the skeleton, migration -13. **#146** a pasted bullet can
no longer forge a question (26037e7) — `human_block()` is now the only
way human text enters questions.md. Indenting alone was NOT enough: the
reader tests `- **` on the RAW line but 'starts a bullet' on the STRIPPED
one, and a bullet ends the note capture, so an indented `- foo` would have
spilled his words into the entry BODY as prose the loop appears to have
written — an attribution failure through a door #109 never considered.
Verified independently: entry, indented bullet and fake section all
blocked. **#96 stage 1** dreamhub —
a read-only aggregate over several targets, nine increments
(ab32541..dc69c8c), 102 pytest + 32 structural + 8 contract checks. Ships
origin-per-project, not the sketched `/{project}/` prefix, because
`routeOf()` compares literals no shim can reach and a prefixed deep link
would render the wrong view SILENTLY (#133). Stage 2+ still needs a go. **#130** 3.1KB of status JSON
became a 244px panel (c065a51) — folds by COMPLEMENT so the next field the
loop learns to write can never be hidden by an allowlist, and the accent is
spent only on `awaiting_human`, proven scarce by a guard shown red. **#120** the fresh-eyes read
(6827daa) — it found a LIVE bug rather than bloat: dashboard commands
exist only in a gitignored best-effort log that SKILL.md never mentioned,
so a `do now:` was lost silently whenever the tail monitor was not armed.
Plus four false or self-contradicting statements. Its structural half is
#145. **#126** a steer carries the
page it was sent from (56a791c) — and, unbriefed, a newline in the
composer can no longer forge a second line in the events log the
coordinator acts on. **#137** `lint.py` checks a
target's files by running the REAL readers, and `just test` now runs it
(b7151ec, 596116a). **#139** the `.qa` catch-alls are gone entirely, not
out-specified, and `oneinput` measures both halves of the field
(166c04b). **#128** the thread no
longer reads as him replying to himself (d6f0ca6) — the parse was
byte-identical whichever order the sub-bullets were written in, so
there was no order to respect; the parser now keeps `when` per note,
cuts the thread at the answer, and only the SETTLED segment collapses,
because folding away a live steer would be worse than the bug. **#131** the composer no
longer fades while he types into it again (896ee74). **#129** needed no
code — e8aeec9 had already animated the fold 24 seconds before he
reported it, and he was right about the deployed page; what it did
surface is now a stated contract, that `expand` is structure and
whether it MOVES is a separate question (f9d08bb), plus #140.
**#121 #123** ghost buttons and the `+` centreline (4fd393b) — #121 was
never a design change: `.sgbtn` asked for `background:none` since #103
and a `.qa button` catch-all outspecified it, so the source read right
while the screen was wrong. **#125** `heartbeat.py`,
a stdlib-only port of the Rust wake tick — byte-identical output, the
Rust test suite ported case for case, and one documented divergence
(`--no-time-prefix` works here; upstream documents it and rejects it). **#113** the awaiting-fold
state breathes and every transition between the three states is covered
(86607dd, e8aeec9) — the matrix found three real defects, including a
ghost that kept its `data-qid` and could have swallowed his typing.
**#111** answered questions
collapse and stay findable (a8f6b7f). **#118** typing survives a
live tick — text, caret, focus and compose mode carried across the
re-render (c321c6c). **#117** the verification
gap — `just test` runs the browser guards against a frozen fixture
(bb20eb1, daa9472). **#103** one input per card
routed by a mode group (5b2fde9); **#104 #77** the regroup — answered
questions travel, neighbours close the gap (fc8185d). **#109 #116** author-tagged
notes and one reader for questions.md (2026-07-25, 34f272f) — #116 also
fixed a silent write failure: /answer and /comment could not match a
wrapped-title entry at all. **#115** the component-cost
spike — split verdict, findings in `docs/spikes/` (2026-07-25).
**#107 #108 #110** the
travelling heading, the ghost-pinned width glide, the clamped opener
(2026-07-25, 3f786fc). **#102 #106** prose reflow and the sub-bullet
parser fix (d14c7b3). **#105** one qaCard for all
four question surfaces (2026-07-25, ec6721f). **#91** composer tweaks and
**#101** scrollbar styling (2026-07-25), **#97** durable task ledger
(2026-07-25, this file). #63-#68, #71, #72, #74, #75,
#78, #79, #81-#85, #87-#89, #93, #94 landed 2026-07-24/25 (watch webui
batches, plugin docs, coherence fixes).
