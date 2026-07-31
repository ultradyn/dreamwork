# ud-dreamwork state audit — 2026-07-31 ~15:57 AEST

**Snapshot caveat:** this repo is live — the coordinator kept committing while this audit ran
(open-task count moved 119 → 120 → 121 mid-audit; HEAD moved `70737d9d` → `a2487003` → `0ad7ce65`
→ `80efbb3a`, and a fresh worktree `.worktrees/lane-586routes` appeared). All counts below are
pinned to **HEAD `80efbb3a`** (`#586 brief: give the lane an absolute own-inbox path`), open
count **121**, landed **355**, read via `python3 $SKILL/dev/ledger.py count` and
`python3 $SKILL/lint.py --target .` (both read-only, `$SKILL=/home/xertrov/.claude-p/skills/ud-dreamwork`).

---

## 1. Discrepancies (highest value — read this section first)

### 1.1 The "5 unanswered questions" figure overstates what's actually waiting on Max — only 1 of 5 is
Ledger warning line reports "5 unanswered questions" (count of top-level entries under `## Open` in
`.dreamwork/questions.md`, via `watch.parse_open_questions`). Read individually (`.dreamwork/questions.md:3-152`):

| # | Entry | Real status |
|---|---|---|
| #572 | GitHub PR/comment etiquette | **Answered** (`questions.md:53`, "via watch, 2026-07-31 03:57") but the answer sits under `## Open`, not `## Answered` — this is *also* the "1 unfolded answers" warning (same entry, double-counted across two warning buckets). `lint.py`'s own WARN confirms: *"is under `## Open` and already carries his answer — answered 11.9 hours ago... fold it (#366)"*. Max's answer also raised a genuine new sub-question ("do we want to leak the sequence id though?") that hasn't been replied to. |
| (hand-off backlog) | "are pending hand-offs unmerged?" | **Fully resolved**, self-answered by the loop (`questions.md:60-80`, "Follow-up (loop...)" — no `Answer (via watch...)` tag at all). Explicitly says *"Nothing for you to do here."* Not awaiting Max in any sense. |
| #584 | Persistent user settings Q1-Q4 | **Genuinely open**, awaiting a fresh ruling (`questions.md:82-118`). This is the only one of the 5 that is what the warning implies. |
| #465 | Lane-containment guard consent | Max replied with a **counter-question** (`questions.md:142-143`, "Note (human...) why can't we enable #465 without this? And also, what is 465?", 2026-07-29 05:51), and the loop has **not answered it** — no `Follow-up` after that Note. The ball is in the loop's court, not Max's, and it's been sitting 2 days. |
| (cross-machine answer delivery) | "how should an answer reach a loop on another machine?" | **Explicitly deferred** by Max himself 2026-07-29 (`questions.md:146-151`, *"this should be deferred... revisit once dreamhub is stable"*). Not an open ask. |

**Net: of "5 unanswered questions," genuinely-awaiting-Max = 1 (#584). One is answered-but-unfolded, one is
loop-owes-Max-a-reply (#465), one is fully resolved, one is deliberately parked.**

### 1.2 `blocked_on` in the SQLite store is stale for several tasks whose blockers already landed
`blocked_on` looks like a live dependency field but is written once and not revisited when the blocker
lands. Verified by checking each referenced blocker's own state (`ledger.py get <id>`):

- **#276** ("Add simple bearer-token authentication for LAN clients") lists `blocked on #233`. **#233 is `landed`** (`Allow explicit LAN bind and Host names`). #276 is unblocked and nobody revisited it.
- **#249** ("Add dev-overlay sampling cadence controls") lists `blocked on #245`. **#245 is `landed`** (`Build ud-dreamwork-worktrees plugin`). Unblocked.
- **#368** ("Break the large Python files into a modular, testable codebase") lists `blocked on #352`. **#352 is `landed`** (`Standardize the duplicated ledger parsing before the store migration`). Unblocked.
- **#373** ("Build topic chats v2 on the accepted R1 direction") lists `blocked on #294` and `#346` in its body. **Both are `landed`.** #373 is structurally free to start — it just hasn't been picked up, and downstream #230/#235/#236 (which cite `blocked on #373`) are correctly still gated on #373 itself, not on a dead dependency.
- **#254** body says *"queued behind the mistperf lane which holds watch.py and test_watch.py"* (2026-07-29). `git log --all --grep mistperf` and `git branch -a | grep mist` return **nothing** — that lane no longer exists (landed under another name or abandoned) two days and dozens of merges ago. The literal `blocked_on` DB column for #254 is `"blocked-on: **human**"`, which is also stale — the task's own body shows it was **authorised for implementation 2026-07-29 01:01** ("yes" to Approve I1) and is not actually waiting on Max at all.

None of these are large finds individually, but together they show the `blocked_on` column cannot be
trusted at face value — the body's own chronological narrative (last few bullets) is the only reliable
signal, and it disagrees with the column in at least 5 of the ~20 populated cases checked.

### 1.3 Two registered git worktrees under `/tmp/` are invisible to the usual `.worktrees/` check
`git worktree list` shows `/tmp/gate-260` (detached HEAD `739fc91e`) and `/tmp/gate-504chat` (detached
HEAD `5cea6e0f`) alongside the expected `.worktrees/lane-586routes`. The 2026-07-31 handoff doc explicitly
says *"No live lane worktrees under the usual paths at handoff check"* (`.dreamwork/docs/handoff-2026-07-31.md:59-61`)
— true only because it checked `.worktrees/`, not `/tmp/gate-*`. Verified harmless: both HEAD shas
**are ancestors of master** (`git merge-base --is-ancestor <sha> master` → true for both), and both tasks
(#260, #504) are `landed` in the store. These are stale-but-safe leftover worktrees, not missed work —
worth `git worktree remove`-ing as hygiene, not worth alarm.

### 1.4 `tasks.md` vs `tasks.md.deprecated` — confirmed, not a discrepancy
The audit brief was told `.dreamwork/tasks.md` is now a migration-notice stub. Confirmed directly: it is
literally 5 lines, a `<!--dreamwork-migration-notice-->` comment (`.dreamwork/tasks.md:1-5`). The 9,143-line
`tasks.md.deprecated` is the frozen pre-cutover history lint still cross-checks against git (`lint.py:1394`,
`#323`'s `check_landed_still_open`). Its 7 WARNs (ids 124, 254, 263, 269, 275, 448, 465 — "git already has a
close/merge commit the entry does not name") are **advisory, by design never ERROR**: manually checking all
7 bodies, 5 are legitimate deliberate partials that already say "STAYS OPEN" in their own text (124, 263,
275, 448, 465); the outlier is **#269**, see 1.5.

### 1.5 #269 is functionally complete but still counted as an open P1 human-blocked task
`#269` ("Make every Web UI text draft durable and cross-tab coherent") has landed its acute fix, design,
extraction, and both previously-uncovered boxes (`0366706`, `e7d0b24`, `36a1594`/`ca799f5`). Its own last
body line: *"Cross-tab (C1) and the 30-day GC are seams only"* — i.e. the P1-urgent scope (data loss on
reload) is fully shipped; what remains is optional polish. `blocked_on` still reads `"blocked-on: **human**"`
from an earlier phase. This reads more like a landed task with an unlanded P3 tail than a live P1 blocker —
candidate for the coordinator to re-file the remainder at lower priority and fold the rest.

### 1.6 Handoffs Pending/Folded gap (task's suspicion) — checked, currently clean
`lint.py` reports `handoffs.md 96 pending, 119 folded, 0 malformed` (now **97 pending / 121 folded** per
the `handoffs.md` wc after HEAD moved) with **zero #576 WARNs** — the specific check that flags a Pending
entry whose task is `landed` in the store but has no matching Folded line. This gap was real as of
2026-07-31 07:20 (27 entries, per `questions.md:70-80` and commit `73c53540`), and `#576` (`e55f148c`) closed
the detection going forward; the backlog itself was cleared to 0 the same session. **As of this audit,
zero Pending entries currently lack a Folded counterpart** — the blind spot is closed, not just detected.

### 1.7 `just test` is currently red on master (not a rumor — there's an open P1 bug describing exactly this)
`#586` (open, P1, origin loop): *"The #577 reply composer added /chat-reply to watch's
WRITE_ROUTE_HANDLERS but not to the two places that must move with it, so `just test` aborts at pytest and
the guards never run."* Names two concrete gaps: `dev/reconcile_submissions.py`'s `SUBMISSION_ROUTES` and
`test_user_events_http.py`'s `run_all_routes`. This corroborates the audit brief's warning that the prior
handoff undercounted pre-existing test failures ("claimed one; there are four") — I did not run `just test`
myself (out of scope per protocol), but #586's own text confirms the suite is currently broken by more than
the single known pre-existing failure the 2026-07-31 handoff named. **A fix is already in motion**: two
briefs landed on master for it (`0ad7ce65`, `80efbb3a`) and a worktree `.worktrees/lane-586routes` exists,
currently clean/unstarted (`git -C .worktrees/lane-586routes status` → nothing to commit, 0 commits ahead
of the master commit it was cut from).

---

## 2. Where the repo is up to (themes, last ~2 days of commits)

Reading `git log --oneline -100` and the newest 15 briefs (`.dreamwork/docs/briefs/`, sorted by mtime):

- **Topic-chat surface is the active spine.** #562 (chat unread count + `/chat/<id>` page) → #577
  (reply composer on that page) → #583 (dual-column `/question` focus view) → #586 (fixing the
  route-registration gap #577 left behind). This is a coherent feature arc, each landing gated by an
  independent-red review and a merge-gate guard registration (`chatsurface`, `qdual`).
- **Self-hosting hygiene work interleaved with feature work**, true to the "dreamwork manages its own
  ledger" design: #557/#558 (ledger store projection/origin backfill), #560 (status panel derived from
  store not markdown), #576 (the handoffs-blind-spot fix, see 1.6), #585 (a truncation-guard hardening
  found by #575).
- **Posture/UI polish**: #559 (burndown hover), #565/#569 (posture dock sticky + deploy countdown
  recuse), #567 (deploy runner detached from the server it stops — a self-brick fix), #570 (composer
  manual resize).
- **A design-only doc landed for #571** (persistent user settings) with an IGC narrowing to two tied
  survivors, escalated to Max as `#584`'s Q1-Q4 — still awaiting his ruling (see 1.1).
- **Net direction**: the loop is mid-way through building out its own chat/Q&A dashboard surface while
  simultaneously eating its own dogfood bugs (#576, #585, #586) as they're found — a normal, healthy
  dreamwork cadence, not stalled or thrashing.

---

## 3. The open tasks, categorised

121 open tasks. I did not hand-audit all 121 (would cost more than the report is worth) — I verified
every task with a structured `blocked_on` dependency (~20) and every task `check_landed_still_open`
flagged (7, see 1.4/1.5), which is where nearly all of the non-obvious findings live. The remaining ~95
are P2/P3 ideas/tasks from `origin: unknown` (pre-#216 backlog) or `origin: human`/`loop` with no
blocked_on and no git close/merge hit at all — genuinely nothing blocking them; several are UI/UX
backlog items (composer-row plan items #99/#161/#164/#170/#183, shader/vignette ideas #100/#171/#187,
etc.) that are low-priority and simply not yet reached, not stuck.

**Bucket (b) — blocked on Max, with the specific question:**

| id | title | pri | reasoning |
|---|---|---|---|
| 584 | Persistent user settings Q1-Q4 | P2 | genuinely open, `questions.md` #584 |
| 572 | GitHub PR/comment etiquette | P2 | answered but unfolded (1.1) — action needed is *fold*, not a new ruling |
| 465 | Lane-containment guard consent | P1 | Max asked a counter-question 2 days ago; loop owes him a reply before this can resolve (1.1) |
| 438 | Generic scheduled-tasks facility | P2 | deliberately parked for a brainstorm session scheduled "after 21:00 2026-07-28" — that time is 3 days past with no follow-up; overdue, worth resurfacing |

**Bucket (c) — blocked on other (named) work, blocker still open:**

| id | title | pri | blocked on |
|---|---|---|---|
| 240 | Bring composer/dream field into popouts | P2 | #241 (open) |
| 257 | `do-now` danger/urgency treatment | P1 | #241 (open) |
| 259 | Cycle composer modes with Shift+Tab | P1 | #241 (open) |
| 243 | Sticky animated repository file tree | P2 | #244 (open) |
| 282 | Link task references to hover previews | P1 | #281 (open) |
| 328 | `/tasks2` wide two-pane layout | P2 | #281 (open) |
| 344 | Per-row `/tasks` control | P2 | #281 (open) |
| 230, 235, 236 | subagent checkbox / answers-follow-ups / provenance | P2 | #373 (open — but see 1.2, #373's *own* blockers are landed) |
| 262 | Durably-witnessed Web UI submissions | P0 | #263 (open) |

**Bucket (c′) — blocked_on names a dependency that is stale (already landed); effectively (a):**
276 (was blocked on #233, landed), 249 (was blocked on #245, landed), 368 (was blocked on #352, landed),
373 (was blocked on #294+#346, both landed), 254 (was queued behind a lane that no longer exists,
and separately already carries a 2026-07-29 implementation authorisation). See 1.2 for evidence per id.

**Bucket (d) — probably stale / mostly landed:**

| id | title | pri | reasoning |
|---|---|---|---|
| 269 | Web UI draft durability, cross-tab | P1 | acute scope fully shipped across 3 landings; remainder is optional cross-tab/GC polish (1.5) |

**Bucket (a) — actionable now:** the remaining ~106 tasks, including notably #124 (watch.py
break-up, deliberately re-scoped to demand-driven per its own text, not stuck), #263 (durable
user-event inbox, mid-flight with named remaining phases E4-H), #281 (rich `/tasks` page, P1, several
other tasks queue behind it), #586 (P1, the test-suite fix, already has a worktree spun up — see §4),
#587 (brand new — brief-lint rule tests the filename not absoluteness, landed literally minutes before
this audit closed), and the P2/P3 UI/idea backlog. No blocking evidence found for any of these — full
list is in `dev/ledger.py list --state open --json`.

---

## 4. In progress vs not

- **#586** (P1, route-registry test-suite fix): briefed (`0ad7ce65`, `80efbb3a`), worktree
  `.worktrees/lane-586routes` exists at the commit it was cut from, **zero commits ahead, working tree
  clean** — set up but not yet started. This is very likely the coordinator's next dispatch.
- **#260, #504**: worktrees exist at `/tmp/gate-260` and `/tmp/gate-504chat` but both tasks are already
  `landed` and both worktree HEADs are ancestors of master — **stale leftovers, not in-progress work**
  (1.3).
- **~30 local branches** (`lane-577reply`, `lane-583question`, `fix-271-*`, `pi-agent-*`,
  `prototype/279-jovian*`, `spike/components`, `wt/*`) carry commits not reachable from master
  (`git merge-base --is-ancestor <branch> master` → false for the ones checked). For `lane-577reply` and
  `lane-583question` this is **expected residue**: the repo's convention is fetch-then-cherry-pick from
  independent worktree clones (per the 2026-07-31 handoff, §1 Worktrees), so the content landed under
  different shas (`47ee8731` etc. for #577, `3fb4544c` etc. for #583) while the original branch ref
  stays orphaned. I did not individually diff all ~15 remaining branches (`pi-agent-*`, `wt/254-threading`,
  `wt/294shape`, `wt/324-reporter`, `wt/326-fade`, `wt/335-selfclosed`, `wt/448`, `prototype/279-*`,
  `spike/components`, `fix/268-contextual-plugins`, `fix/291-command-close`) against their task ids' store
  state — that would be the next-cheapest thing to check if "is there abandoned unlanded work sitting in
  a branch" is a live worry; **no evidence either way was gathered for these**, stating that explicitly
  rather than implying they're clean.
- No other worktrees or in-flight lane evidence found. `status.json` (gitignored, live) reports "0
  agent(s)" at read time — consistent with nothing mid-flight beyond the just-created #586 worktree.

---

*Compiled by `[state-audit]`, read-only. All ledger/lint reads via
`$SKILL=/home/xertrov/.claude-p/skills/ud-dreamwork`; no writes made to the target repo.*
