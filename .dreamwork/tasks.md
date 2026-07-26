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

Next id: **285**

## Open

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
  creator proof**; a short-lived writer may evade 50ms snapshots · diagnose why
  watcher exits 0; improve attribution to capture exec/exit or syscall-level
  creator before changing mitigations; coordinate host fix with system KB entry

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
  self-contained proposal before implementation and coordinates with #213/#216

- **#280** — Design selectable preserved background shaders · P2 · visual/settings
  design · origin: **human** · **human via watch 18:12** · keep the current
  background shader and any substantial Jupiter/storm revision as separate named
  implementations; later let the user choose · define registry/interface,
  project setting/default/migration, capability/perf metadata, cross-tab sync,
  reduced-motion behavior and fallback; do not add selection UI until #279 proves
  a worthwhile second shader and #228 shared settings lands

- **#279** — Prototype a Jupiter-like higher-fluid-dynamics storm shader · P1 ·
  visual experiment/design · origin: **human** · **human via watch 18:12** · use
  `/home/xertrov/Documents/storm{1,2,3,4,5,6,7}.{webp,jpg}` as visual references;
  current presented storm is too simple and geometry needs work · create a copy/
  separate implementation so the current background remains unchanged; establish
  intended bands/vortices/depth/scale, deterministic render and perf breakpoint;
  run visual+geometry review/fix and present a new proposal before product wiring ·
  blocked on #278 timebase diagnosis so the prototype does not inherit acceleration

- **#278** — Diagnose background shader acceleration over time · P1 · visual/perf
  bug · origin: **human** · **human observed via watch 18:12** · shader appears to
  get faster the longer the page stays open · reproduce with a long deterministic
  frame/time trace; distinguish absolute-time growth, accumulated warp/twist,
  multiple animation loops, timestamp units and re-render/reset behavior; measure
  displacement/phase velocity at fixed intervals; diagnose before fix and preserve
  the existing visual baseline

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

- **#274** — Make duplicate Web UI submissions idempotent end to end · P0/P1 · bug ·
  origin: **loop** · 25m · at 17:48 one human #233 action produced two byte-identical
  `/answer` receipts and two identical question bullets in the same second ·
  preserve one exact answer; diagnose double-click/client handler versus retry;
  stable client action UUID before send, server receipt dedupe and idempotent
  application belong to #263/#269 · red fixture must replay/concurrently submit
  same ID and assert one receipt/application while a new ID with same text remains
  a distinct intentional action

- **#271** — Make notes appear promptly across open dashboard browsers · P1 · bug ·
  25m · origin: **human** · **human via watch 16:58** · observed symptom only:
  with two browsers open to the same Dreamwork dashboard page, a note posted in
  one does not appear in the other immediately, but does appear after a later
  refresh · reproduce across separate browser processes, measure `/mtime` and
  data fetch/rerender behavior, distinguish stale server generation/port from
  polling or cache behavior, then red-first fix · align live propagation with
  #269 cross-tab drafts without conflating received notes with unsent text

- **#270** — Harden and re-review the #229 topic-chat proposal · P1 ·
  architecture/review · origin: **human** · **human revision directive via watch
  17:10** · active now · update artifact against the full Grok architecture
  review preserved in the answered #229 thread and measured UX review at
  `.dreamwork/docs/research/review-route-ux-272.md` · define one recovery
  authority/order, bounded worker adapter, per-target cross-process lease,
  transcript confinement, attachment MVP/atomic promotion, derived index,
  queue-full semantics, idempotent finalisation, privacy/export and provenance
  redaction; also propose viewport-bounded sticky header/thread/composer dock,
  decision navigation, mobile Document/Discussion model, #254 nesting and global
  composer treatment with transitions/RM · retain transcript-first/simple-mode
  strengths · self-review against Dreamwork goals, independently visually review,
  then present a **new** review artifact/question · no implementation authority ·
  design consumes #263; implementation remains blocked on #266

- **#269** — Make every Web UI text draft durable and cross-tab coherent · P1 ·
  client reliability/module · origin: **human** · **human via watch 16:45** ·
  composer, answer/note boxes, future chat inputs and every later user text field
  get a stable logical input ID; autosave content before submission to one
  project-partitioned IndexedDB draft store; restore across reloads and route
  transitions; synchronise the same logical input across tabs so multiple views
  behave as one box · define ownership/conflict/clear-on-durable-receipt rules,
  privacy/retention and migration from composer localStorage · expose one deep
  module that future inputs must consume · design alongside #263 receipt boundary

- **#268** — Hide Dreamwork-only plugins from ordinary skill discovery · P1 ·
  plugin integration · 25m · origin: **human** · **human via watch 16:27** ·
  apply the #267 survivor across `ud-dreamwork-*`: plugins should not appear as
  user-invocable/general model skills when Dreamwork is inactive, but the active
  loop must still resolve and load them predictably · preserve install/update
  compatibility, explicit file-based fallback and tests · blocked on #267

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
  SQLite and per-record spools · cover stale recovery, multi-process same-target
  servers, worktrees/c2c, compaction, cross-machine/git boundaries and migration
  · blocked on user-event model #263
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
  unify #260/#262, never a third inconsistent queue · next-up

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

- **#255** — Make composer confirmation self-dismiss reliably · P1 · UI bug ·
  20m · origin: **human** · **approved via watch 18:18** · `sent to the dream`
  can remain indefinitely if user types during POST or closes/reopens composer ·
  implement one shared success lifecycle: atmospheric arrival, readable ~5s,
  atmospheric departure then clear, independent of typing/open state; hard-clean
  on close/unmount; false/error claims withdraw immediately; RM keeps timing/
  function without movement/blur · main/popout share helper; red-first timing +
  intermediate-motion guard · unblocked, next after current LAN/doc checkpoint

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

- **#251** — Prove old answer node disconnects after deletion refresh · P2 ·
  test · origin: **loop** · completed with #250 at `f17f307` · original
  ElementHandle is proven connected before refresh and disconnected after;
  evaluation errors fail closed · same-aid new survivor stays open · PASS
- **#250** — Preserve motion for missing-aid answer disclosures · P1 · bug ·
  origin: **loop** · completed at `f17f307` · identity-less answered details
  use a local human-click fold reusing travel/reveal/ghost without persistence
  key; normal open/close prove >2 intermediate card heights + following-marker
  positions; reduced-motion function preserved · behavioral RED against old
  `watch.py`; 440 tests, browser/lint/diff and Standards/Spec PASS · deployed

- **#249** — Add dev-overlay sampling cadence controls · P2 · dev UI · 25m ·
  origin: **human** · **human via watch 14:37** · frame-time graph + other
  stats update at selectable `1s` / `10f` / `1f` cadence using the existing
  tiny sliding button-group idiom, not a new toggle · default rec `1s` for low
  overhead · keep per-frame measurement/aggregation correct when display is
  slower; persist/sync under #228 project settings · transitions/reduced-motion
  and perf guard required · blocked on #245 and #228

- **#248** — Decide whether answers records need persisted IDs · P3 · design ·
  20m · origin: **loop** · late #238 review · exact-content twins cannot
  retain distinct identity through reorder without a durable file-format id;
  evaluate whether real workflows justify migration rather than solving a
  semantically invisible distinction by default
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
- **#245** — Build `ud-dreamwork-worktrees` plugin · P1 · plugin · origin:
  **human** · **do next via watch 14:33** · completed at `8af7dc3` after
  red-first 11→22 contract tests and two independent Standards/Spec reviews ·
  publishable source package under `plugins/`; symlinked into Pi, agents and
  llm-general skill roots; loaded by explicit human request · bounded
  subagent mode + same-host durable co-agent claims/inbox protocol; machine-local
  runtime state, status projection, disjoint ownership, receipt/review,
  scratch-safe cleanup and cross-host boundary all documented · PASS

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

- **#238** — Preserve `/answers` UI state across data refresh · P1 · bug ·
  20m · origin: **human** · **do next via watch 14:16** · open answered
  disclosures close after `data.json` refresh; diagnose with requested c2c
  helper `grok-sugar-vesi-x6tv` and red-first browser guard · preserve every
  human-controlled `/answers` state through keyed snapshot/restore, smoothly
  and on the same logical record despite duplicate titles/reorder/deletion ·
  obey transitions.md · in progress

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

- **#234** — Minimise the answer-morph rerender hold · P2 · bug · 20m ·
  origin: **human** · **human via watch 14:05** · reduce the current
  `Date.now() + 1600` toward 850ms, choosing the shortest reasonable value
  that cannot let `/mtime` replacement interrupt answer/note morphs · measure
  CARD travel, lifted hero/cleanup and relevant guard window; red-prove early
  release rather than assuming CARD_MS is the whole critical path · research:
  1150ms `flipDock` transform + ~1000ms card cleanup make 850ms unsafe; use a
  forced-mtime race to choose a named ~1200–1300ms hold or event completion ·
  stale #233 LAN dependency removed · queued after active #250/#251 correction

- **#233** — Allow explicit LAN bind and Host names · P1 · task · 30m
  design + increments · origin: **human** · **do next via chat 13:55** ·
  **approved A via watch 17:48:** explicit unauthenticated trusted-LAN mode;
  loopback default, exact bind/Host allowlist, same-origin browser writes,
  advertised URL, IPv6 correctness and loud warning per reviewed threat model ·
  Host/Origin are safeguards, not auth · later public auth #275 and LAN bearer
  token #276 are separate and do not expand this increment · docs/migration/TDD
  first · existing `.worktrees/lan-bind` plan now unblocked

- **#230** — Add a `use subagent` composer checkbox · P2 · task · later ·
  origin: **human** · **human via watch 12:57** · request fresh-context,
  parallel processing outside the main queue; integrate with #228 project
  settings, expose dispatch/ownership/result channel, and never silently fall
  back to inline · blocked on #229's lifecycle design
- **#229** — Propose threaded topic chats with ephemeral agents · P1 · task ·
  origin: **human** · **do next via watch 12:57** · self-contained HTML
  proposal integrated with dream dashboard: durable per-topic chat log as the
  primary input; one fresh ephemeral agent per turn; in-flight lock + queued
  follow-up; optional interrupt analysis; dashboard placement and UI; failure,
  recovery, privacy, concurrency, cost, state machine, and smallest staged
  build · proposal only, no implementation authority · artifact complete and
  visually reviewed at `.dreamwork/review/threaded-topic-chats.html` · awaiting
  A–E approval in questions.md · **human amendment (re-homed 16:12 onto this
  card after #266 misfile):** chats attach to any artifact or precise reference
  within one, and remain listed on the global `/chat` route · also under #253

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

- **#221** — Sort dashboard reviews by datetime · P2 · implementation · 15m ·
  origin: **human** · **approved via watch 18:25** · sort review artifacts by
  newest filesystem `mtime`; filename is deterministic tie-break; displayed age
  and ordering share this source · red-first undated artifact + equal-mtime guard


- **#218** — Add filed-to-landed median · P2 · task · 20m ·
  origin: **loop** · blocked on #217 · `ledger_series` already computes
  arrival/landing pairs and discards them; render the median without a
  velocity score after provenance work
- **#217** — Render honest provenance coverage · P2 · task · 25m ·
  origin: **loop** · blocked on #216 · draw human/loop/unmarked rather
  than implying the historical unknown remainder is loop-originated;
  keep explicit coverage copy and update watch-design.md plus a red-first
  browser guard
- **#216** — Parse first-seen origin in ledger history · P2 · task · 20m ·
  origin: **loop** · blocked on #213 · preserve human/loop/unknown at
  first sight; a later edit must never retroactively classify an arrival

- **#138** — Ship a PreCompact hook so the write-down is automatic ·
  P2 · task · 60m · **scope gate applies**: Claude Code-specific
  machinery in a harness-portable skill, and it touches his own config
  — rec is an optional plugin, but confirm before building. A hook
  fires AT compaction, so it guarantees the write-down and cannot buy
  landing time; stdout becomes summariser instructions, so it must be
  silent by construction
- **#148** — Two sibling guard dirs, one contract, no shared runner ·
  P3 · chore · 30m · fine while they have different owners, wrong the
  moment they do not; extract when a batch would have used it (#124)
- **#158** — `/file` reflows markdown · P2 · bug · 25m · **APPROVED**
  2026-07-25 15:23 ("rec still... only reflowing .md or similar. not
  source code") · replaces the #102 rule, which drew its line at WHO
  COMPOSED the text where the useful line is WHAT IT IS · rewrite the
  rule in the same commit so it reads as reconsidered, not forgotten ·
  pairs with #178, same route
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
  found, capture `ss -tlnp` and name pid+command in the report
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
- **#213** — Enforce forward-only task provenance · P2 · implementation · 20m ·
  **approved via watch 18:36** · record `origin: **human|loop**` on every task
  from cutoff #216 onward; historical tasks remain unknown rather than guessed ·
  first increment adds the ledger contract and linter only; first-seen parsing
  remains #216 and honest human/loop/historical-unknown UI remains #217 ·
  red-first linter fixtures must prove new missing/invalid origin fails while
  old unmarked entries and explicit unknown coverage remain accepted
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
  **one open question** (zip has no repo, repo is private — rec: ship a
  generated changelog in the release) · trailers LANDED pre-compaction ·
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
  runner reports from full output, never from a count (qsec 19:03)
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
- **#172** — Heading row: repo identity, and where invariants sit ·
  P3 · idea · 25m · his layout principle is the firm half and it
  generalises — **anchor what is INVARIANT to an edge, not to a
  variable-width neighbour**: the page title varies per route, the repo
  name never does, so hard-right it and it stops being shoved about by a
  change unrelated to it. Worth a `watch-design.md` rule, since #110
  animates travel and anything that need not move should not · the name
  ("dreamwork watch") is OPEN and his — and #153 independently dropped
  the app name from the tab title, so put the two to him together ·
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
  check the departure too · verify by per-frame trace, since a two-frame
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
