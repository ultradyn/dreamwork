# Backlog re-rank — 2026-07-31 (#590)

`[lane-590rerank]`, read-only. Pinned to HEAD `e0aa3fee` (main checkout `master`
at dispatch), 147 open tasks at the time of writing — **the DB moved under me**
while this ran: the initial pull returned 148 (`#592` included); a re-check
minutes later showed `#592` had landed (`f56cbba9`, already handed off) and
dropped to 147. `#592` is therefore **not** in the table below — it is no
longer open. This is the same live-repo caveat the 2026-07-31 state audit
recorded; treat every count here as "as of `e0aa3fee` ± a few commits", not
as a frozen ground truth.

**No task priorities were changed by this lane.** Every "proposed" value
below is a recommendation for the coordinator to apply, not something this
lane wrote to the store.

## The focus, briefly

Max, 2026-07-31 (`DREAMWORK.md`, *Current focus*): make `watch.py` modular
and reusable by dreamhub, extract the UI into a frontend built and served by
`watch.py`/dreamhub, compatible with Claude design tooling — for long-term
maintainability. Explicitly **non-exclusive**: *"current focus does not
imply exclusivity, but we should prioritize related tasks within
orchestration budgets."* Dogfooding the loop and dreamhub's login+taskboard
end-state are named as goals worth outranking focus-work when a task
unblocks that longer arc rather than merely serving the focus.

## Method

Read every open task's full body (not just its title — several titles
undersell the task badly), cross-referenced every `blocked_on` against its
target's live state, read the 2026-07-31 state and visual audits, checked
`.dreamwork/docs/plans/` for existing designs, and spot-verified claims
against `git log` / `handoffs.md` / `questions.md` rather than trusting a
task body's own progress notes. **VERIFIED** below means I read the commit,
the file, or the current `questions.md` text myself. **INFERRED** means I am
reasoning from a task's own internal notes without independently checking
the underlying commit — flagged as such every time it matters.

Excluded from re-ranking entirely (currently in flight, per dispatch):
`#591`, `#595`, `#597`, `#598`, `#600`, `#611`, `#612`, `#613`, `#614`. They
appear once, at the end of §1, unchanged, for completeness.

---

## 1. Full priority table

### 1a. Focus-core — watch.py modularity, frontend extraction, doc reference

| id | cur | prop | reason |
|---|---|---|---|
| #368 | P2 | **P1** | *Mover.* This is the task Max named directly (`#275` body, 2026-07-29 05:54): *"watch.py should be refactored into modules and then they can be imported to use in dreamhub."* Both preconditions its own body names — `#352` (landed) and "the CLI existing" (`#294`+`#497`, both landed) — are now satisfied. See §2. |
| #124 | P2 | **P1** | *Mover.* The concrete current seam of the same initiative; plan already refreshed and re-scoped to "next demand-driven seam," zero blockers, ready today. Near-duplicate of `#368` — see §4. |
| #133 | P3 | P3 | Explicitly sequenced *inside* `#124`'s server-core seam ("do it inside `#124`'s server-core seam") — correctly waits for that seam to exist. |
| #148 | P3 | P3 | Deliberately deferred by its own text: "extract when a batch would have used it (`#124`)" — correct as-is. |
| #602 | P2 | P2 | Cheap, high-leverage doc-navigability fix for the reference the whole extraction has to keep honest; its own text already states it serves the focus. Candidate for top-ten (see §6) without needing a priority bump. |
| #615 | P2 | P2 | Explicitly gated on `#613` (in flight) settling its hierarchy/bookmark model first — correctly not startable yet. |

### 1b. Dogfooding / loop-process integrity

Max: dogfooding is a goal, not a side effect. This cluster is almost
entirely findings from lane dogfood reports (`lane-586routes`,
`lane-592lint`) plus the coordinator's own self-audit — exactly the
mechanism he asked for.

| id | cur | prop | reason |
|---|---|---|---|
| #607 | P1 | P1 | Verification-integrity bug: briefs point at the skill-dir `lint.py` symlink, so a lane fixing `lint.py` itself verifies against the unfixed copy. Correctly P1 already — it can make a real fix read as failed. |
| #608 | P1 | P1 | The red-proof recipe's snapshot-order bug can convert a correct fix into a silent no-op that still passes `cmp`. Arguably the single highest-leverage bug in the backlog (it is "the single most-repeated instruction in the whole loop," per its own text). Correctly P1. |
| #587 | P2 | **P1** | *Mover.* Same class as `#607`/`#608`: the absolute-inbox lint regex checks the wrong thing, so every brief has to invent a fake `.../inbox.md` to pass a check about a real convention. Cheap, mechanical, and it is already visibly teaching lanes the wrong lesson (cited by `#586`'s own brief). See §2. |
| #606 | P2 | **P1** | *Mover.* Coordinator gate + lane fleet contend for one machine; guard verdicts are load-sensitive with nothing sequencing them. The doc's own words: *"a load-induced FAIL that gets waved through as flaky is how a real regression eventually gets waved through too."* Same soundness risk as `#607`/`#608`, just at the infra layer. See §2. |
| #589 | P1 | P1 | Makes the dogfood-report obligation an enforced dispatch-time duty rather than an unenforced preference. Correctly P1 — this very lane's dispatch prompt already carries the obligation it asks to standardize, which is weak evidence it is working piecemeal but not yet systematized (SKILL.md / file-formats.md / lint still need it). |
| #593 | P2 | P2 | Three concrete brief-template gaps from one lane's report (absolute `--target`, which tree to commit `handoffs.md` in, a channel for "your prediction was wrong"). Real, cheap, correctly P2. |
| #594 | P2 | P2 | Found a real hollow-test pattern (`/chat-reply` fixed, `/decide` is the named suspect) — a genuine verification-coverage gap, correctly P2. |
| #605 | P3 | P3 | Coordinator's own dogfood item (nohup masks a background-job's real exit). Procedural, self-correctable, no evidence it has recurred. P3 is right. |
| #609 | P3 | P3 | Small annotation fix to the brief template (`Lane-owns:` doesn't say `handoffs.md` means "main checkout, master"). Cheap, low blast radius. |
| #610 | P3 | P3 | Lint-report footers pointing at undocumented rows in `file-formats.md`. Cosmetic paper cut, correctly low. |
| #576 | P2 | P2 | **VERIFIED landed-not-folded**, see §5 — recommend fold, not a priority change. |

### 1c. Visual-audit follow-ups (not in flight)

| id | cur | prop | reason |
|---|---|---|---|
| #596 | P1 | P1 | D4: `/research` heading regression. Cheap, well-scoped, already correctly P1 — a shipped surface visibly wrong. |
| #599 | P2 | P2 | D6: burndown tip paints over a live head line at 88% opacity. Same family as `#604`'s O5 — see §4. |
| #601 | P3 | P3 | D8: chat heading wrap drops project chrome 7.4px. Overlaps `#604`'s O1 — see §4 (fixing O1 likely fixes D8 for free). |
| #603 | P2 | P2 | Process fix for the next visual lane (stale Playwright root, tool-naming, route-list derivation, disclosure trap). Real leverage, but lower stakes than `#607`/`#608` (wasted calls, not silently wrong verdicts) — P2 is the right tier. |
| #604 | P3 | P3 | Batched polish (O1–O6, O8), correctly P3 as a batch; O1 specifically pairs with `#601` (see §4). |

### 1d. Major approved/near-approved features (blocked-on cleared or clearing)

| id | cur | prop | reason |
|---|---|---|---|
| #254 | P1 | P1 | **Mover (unblock, no priority change)** — implementation already authorised 2026-07-29 01:01, queued behind a dead "mistperf" lane. See §2/§3. |
| #373 | P1 | P1 | **Mover (unblock, no priority change)** — both named blockers (`#294`, `#346`) landed. See §2/§3. Real, large, Max-approved feature; a clean example of "non-exclusive" (see §6). |
| #465 | P1 | P1 | **VERIFIED** genuinely still open: his Q1 (repo-local vs global hook install) is unanswered as of this read (`questions.md:70-98`). Correctly P1 — it is a live containment gap. |
| #269 | P1 | **P3** | *Mover (demote).* Acute data-loss bug is fixed and shipped (`0366706`/`e383492`, `e7d0b24`, `36a1594`/`ca799f5`) — state audit's own §1.5 finding, independently confirmed by reading the body. Remaining scope (cross-tab, 30-day GC) is explicitly "seams only." See §2. |
| #262 | P0 | P0 (flag) | Its stated goal — durable witnessing before `200` — reads as already achieved by `#263`'s landed lane E (`_send_receipt` only issues `202` after a journal commit, `503` otherwise). **INFERRED, not verified against the live handler** — recommend the coordinator re-check before touching priority. See §5. |
| #263 | P1 | P1 | Enormous body, last dated entries 2026-07-29; lanes A/B/C/D/F/H read as complete, lane G's status is not confirmed in the text I read and no worktree is currently active for it. Recommend a status check before further scheduling; leaving priority as-is pending that. |
| #281 | P1 | P1 | Correctly P1 — real, human-prioritised dashboard feature; body says "in progress" but no active worktree exists for it today (not in the in-flight list) — likely a stale progress marker, worth a status ping, not a priority change. |
| #282, #328, #344 | P1/P2/P2 | unchanged | All correctly gated on `#281` (open, not landed) — not stale. |
| #448 | P2 | P2 | Survey done; feature blocked on `#294`, which is now **landed** — body text is stale (still reads "blocked-on: #294") though the DB `blocked_on` column itself was empty. Effectively ready to design against structured data now; flagged in §3 as an additional soft-stale case. |
| #418 | P2 | P2 | Correctly sequenced after `#281` (open) and `#294` (landed) — not stale, `#281` is the live gate. |
| #566 | P3 | P3 | Real correctness bug on the `/tasks` surface (badge reads a retired field) — small, correctly P3. |

### 1e. Composer platform / keyboard / mount-contract cluster

| id | cur | prop | reason |
|---|---|---|---|
| #241 | P2 | **P1** | *Mover.* Blocks two P1 tasks (`#257`, `#259`) while itself sitting at P2 — a blocker should not rank below its dependents. Already unblocked (its own body: "`#238` LANDED"). See §2. |
| #257 | P1 | P1 | Blocked on `#241`; raising `#241` (above) is the fix rather than demoting this. Real safety-signalling UI (danger treatment for `do-now`), correctly P1 once unblocked. |
| #259 | P1 | P1 | Same as `#257` — blocked on `#241`, correctly P1 once that lands. |
| #240 | P2 | P2 | Blocked on `#241` (open) — correct. |
| #99 | P2 | P2 | Real, concrete drift report (composer/popout diverged four times); correctly P2, depends on `#161`+`#164`. |
| #161, #164 | P2/P2 | unchanged | `#164` depends on `#161`; both correctly P2, no blocking gap. |
| #170, #183 | P2/P2 | unchanged | Composer-row plan items, correctly P2, no dependency issues found. |
| #162, #167, #168, #176 | P3 | unchanged | Minor composer polish/ideas, correctly low priority. |
| #159 | P3 | P3 | Narrow motion-verification task (only the arrival half remains) — correctly P3. |
| #227, #228 | P2/P2 | unchanged | Space-opens-composer and settings unification; `#227` should probably land with or after `#228`'s server-side settings contract (implied by its own text) — no priority change, just a sequencing note. |
| #297 | P2 | P2 | Legitimate motion-contract gap across many disclosure surfaces; correctly P2, non-trivial scope (needs a real inventory). |
| #322 | P2 | P2 | Body says "touches `watch.py` (held by an agent right now), filed not started," dated 2026-07-27 — that condition is stale (no exclusive hold exists today; many lanes touch `watch.py` via worktrees). Not a `blocked_on`-column case so it didn't show up in the structured stale-block check, but it is the same shape — flagged in §3. |
| #451 | P2 | P2 | Real, well-scoped dashboard feature (authorisation-ask queue). No change. |
| #573 | P2 | P2 | Depends on `#584`'s settings backend (open, blocked on his Q1-Q4) — correctly sequenced. |
| #574, #580, #588 | P3/P2/P2 | unchanged | Posture-dock polish items; `#580` and `#485` (§1h) overlap — see §4. |

### 1f. Topic-chat cluster (dependent on `#373`)

| id | cur | prop | reason |
|---|---|---|---|
| #230, #235, #236 | P2 each | unchanged | Correctly gated on `#373` (open) — state audit already confirmed this is the live gate, not a dead one. Once `#373` starts (see §2/§6), these become genuinely near. |

### 1g. Security / hub architecture

| id | cur | prop | reason |
|---|---|---|---|
| #275 | P2 | P2 (flag) | **VERIFIED** all six of its own escalated questions are now answered or redirected into successor tasks (`#359` open, `#360` landed-design). Recommend fold — see §5. Left at P2 pending that decision, not demoted. |
| #276 | P2 | P2 | **Mover (unblock, no priority change)** — `#233` landed. See §3. Not focus-adjacent, no priority reason to raise. |
| #358 | P2 | P2 | Real, deliberately research-only (no implementation authorised) — correctly P2, no change. |
| #359 | P2 | P2 | The live half of what `#275` split into (hosted SaaS product) — correctly open, unblocked, no change. |
| #485 | P2 | P2 | Its own body flags the overlap with `#445`'s already-settled field — see §4 (near-duplicate of `#580`). |

### 1h. Visual / shader / motion-flourish ideas (creative backlog)

None of these touch the focus; none are blocked on anything stale. Left
unchanged — burying them would misread "non-exclusive" the other direction.

| id | cur | prop | reason |
|---|---|---|---|
| #73, #92, #100, #114, #171, #178, #180, #186, #187, #211 | P3 each | unchanged | Small, self-contained visual/UX ideas, no dependencies, no urgency signal. |
| #98, #122, #169, #173, #182, #185, #189, #196, #200, #201, #204, #205, #207 | P2 each | unchanged | Larger or more load-bearing ideas (motion-contract extensions, a11y, reliability) but none touch the focus or have a stale block. `#189` is a real bug (silent Wayland degradation) worth keeping at P2. |
| #237 | P2 | P2 | Explicitly model-gated ("MODEL GATE: … only with an Opus 5 agent") — an untracked precondition, same shape as `#285`/`#322`; flagged in §3, priority correct as parked. |
| #280, #295 | P2 each | unchanged | Shader-registry design and dithering — `#295` is approved-with-amendments and ready; `#280` correctly waits on `#228`. |
| #338 | P2 | P2 | Method/tooling idea (bundle `use-igcs`), valuable but not focus-adjacent, no change. |
| #492 | P3 | P3 | His own words: *"planned for MUCH LATER — file and park."* Correctly parked. |
| #493 | P2 | P2 | Design delivered; implementation gated on `#500` (open, P3) — correctly sequenced. |
| #500 | P3 | P3 | First slice landed; remainder explicitly gated on his activation grant — correctly low and parked. |
| #578, #579, #581, #582 | P2/P3/P2/P3 | unchanged | Small, well-scoped UI ideas, no issues found. |
| #561, #568 | P2/P3 | unchanged | An open provenance mystery (benign effect) and a small motion-check gap; both correctly triaged already. |
| #572 | P2 | P2 | One fork left (Q2), correctly P2, nearly done. |

### 1i. Reliability / infra papercuts

| id | cur | prop | reason |
|---|---|---|---|
| #319 | P2 | P2 | Real hygiene fix, correctly P2, deliberately deferred from `#203`. |
| #341 | P2 | P2 | Latent (not active) reliability bug, correctly P2 per its own re-triage note. |
| #345 | P2 | P2 | Real test-flakiness-under-load bug; same family as `#606` (both about verification integrity under contention) but scoped to one guard rather than the whole gate — correctly P2, no reason to match `#606`'s bump since its blast radius is narrower. |
| #354 | P2 | P2 | Increment 1 (the actual memory bug) landed; increment 2 (Range) is optional and correctly deferred. |
| #355, #356 | P3 each | unchanged | Both explicitly measured as low-urgency with a stated re-trigger condition — correctly P3. |
| #50, #80 | P2/P3 | unchanged | `#50` genuinely gated on more dreamtask use accruing (in progress by nature); `#80` is a simple human-pick, correctly low. |

### 1j. Meta / process (not dogfooding-specific)

| id | cur | prop | reason |
|---|---|---|---|
| #152, #215 | P3 each | unchanged | Both explicitly self-describe as deliberately-deferred-with-a-trigger; correct as-is. |
| #193 | P2 | P2 | Real gap (a blocked errand is invisible to the human), correctly P2. |
| #194 | P2 | P2 | Partially landed (githash + frontmatter); remainder correctly sequenced behind an open design question. |
| #242, #244, #243, #246 | P2 each | unchanged | `#243` correctly blocked on `#244` (open); rest are independent, no issues found. |
| #253, #256 | P2 each | unchanged | `#256` correctly blocked on `#239` (open); no stale blocks. |
| #265 | P2 | P2 | Correctly blocked on `#225` (open, not landed). |
| #285 | P2 | P2 | Blocked in-body on an external, untracked precondition ("after dd2 is fixed") — flagged in §3, priority unaffected since it is genuinely not actionable yet. |
| #286 | P2 | P2 | Design-only increment authorised, correctly P2. |
| #375, #378, #393, #407 | P3/P3/P2/P3 | unchanged | Small, well-scoped findings, no issues. |
| #438 | P2 | P2 | Brainstorm was scheduled "after 21:00 2026-07-28" — **3 days overdue** and no `questions.md` entry exists for it at all (unlike every other human-blocked item). Worth resurfacing to him; not a priority change, a scheduling gap. See §3. |

### In-flight (excluded from re-rank, listed for completeness)

| id | cur | note |
|---|---|---|
| #591 | P1 | G2 ruling (component tree vs derived design surface) — gates `#613`/`#614`'s eventual component work. |
| #595, #597 | P1/P2 | D1/D2 sideways-scroll + D5 scrollbar-gutter snap. |
| #598 | P2 | D3 raw-404 fix. |
| #600 | P2 | D7/D9 review-artifact amber verdict + narrow-width drop. |
| #611, #612 | P2/P2 | Lint-report silence + fold-prompt-quote-length fixes. |
| #613, #614 | P1/P1 | Session-log streaming view design; websocket/delta transport plan. Both explicitly load-bearing for the focus's component-surface question (`#591`). |
| #590 | P1 | This task — closes on this document's commit. |

---

## 2. The movers

Everything proposed to change, with the argument, in one place.

| id | change | argument |
|---|---|---|
| **#368** | P2 → **P1** | The task Max named directly as one of two routes to the product goal (`#275` body, verbatim quote in §1a). Both of its own stated preconditions — `#352` and "the CLI existing" (`#294`, `#497`) — are landed. **VERIFIED** via direct DB lookup on `#352`/`#294`/`#497` state. |
| **#124** | P2 → **P1** | The live, concrete seam of the same initiative, plan refreshed, zero blockers, ready today. Recommend treating `#124` and `#368` as one initiative going forward (see §4) rather than raising both independently and letting them drift apart. |
| **#241** | P2 → **P1** | Currently blocks two P1 tasks (`#257` danger-treatment, `#259` Shift+Tab cycling) while sitting at P2 itself — the classic "blocker ranked below its dependents" smell. Already unblocked (`#238` landed per its own text). Raising the blocker is cleaner than demoting two already-correctly-scoped P1s. |
| **#587** | P2 → **P1** | Same class as the already-P1 `#607`/`#608`: a lint rule that checks the wrong thing, so every brief has to fabricate a workaround to pass it. Cheap, mechanical, already visibly teaching the wrong lesson to lanes. |
| **#606** | P2 → **P1** | The coordinator's own gate is load-sensitive with nothing sequencing it against the lane fleet — the same soundness risk `#607`/`#608` exist to close, just at the infrastructure layer. Its own text: a load-induced FAIL waved through as flaky is how a real regression eventually gets waved through too. |
| **#269** | P1 → **P3** | Acute data-loss bug shipped across three landings (`0366706`/`e383492`, `e7d0b24`, `36a1594`/`ca799f5` — **VERIFIED** these commits exist in `git log`). Remaining scope (cross-tab focus-wins, 30-day GC) is explicitly "seams only" in the task's own final note. Matches state audit §1.5's independent read. |
| **#254** | P1 unblock only | Implementation authorised 2026-07-29 01:01 ("Approve I1" → "yes"), currently queued behind a "mistperf" lane that **no longer exists** (`git log --all --grep mistperf` and `git branch -a \| grep mist` both return nothing — **VERIFIED**, matches state audit §1.2). Recommend the coordinator clear the stale sequencing note so this P1 becomes genuinely pickable. |
| **#373** | P1 unblock only | Both named blockers (`#294`, `#346`) are landed (**VERIFIED** via DB lookup). State audit already flagged this; independently confirmed here. A large, real, Max-approved feature that has been invisible to selection for no good reason. |
| **#276, #249** | unblock only, no priority change | `#233` and `#245` respectively are landed (**VERIFIED**). Neither is focus-adjacent, so no priority argument beyond clearing the stale gate. |
| **#342** | unblock only, no priority change | `#294` (its named blocker) is landed, **and** the design has landed, three questions have been answered, and two implementation lanes have already merged — the `blocked_on` column is triply stale. Remaining scope ("the tick-consume habit") is small and not yet even filed as its own increment; flagged, not escalated. |

---

## 3. Blocked-and-stale

The brief named five candidates; all five verified, plus one new
numerically-blocked case and three informally-blocked (untracked
precondition) cases found by walking every `blocked_on` value against its
target's live state, and every "blocked-on: human" sentinel against
`questions.md`.

### Confirmed stale (named blocker has landed) — all VERIFIED via direct DB lookup

| id | `blocked_on` says | actual state | consequence |
|---|---|---|---|
| #276 | #233 | **landed** | LAN bearer-token design is startable now. |
| #249 | #245 | **landed** | Dev-overlay sampling cadence controls startable now. |
| #368 | #352 | **landed** | See §2 — also raised in priority. |
| #373 | #294, #346 (body) | **both landed** | See §2 — already P1, now genuinely pickable. |
| #254 | "blocked-on: human" | **already answered** 2026-07-29 01:01; the real gate was a dead lane name ("mistperf") | See §2. |
| **#342 (new)** | #294 | **landed**, and superseded further — design, Q1-Q3, and two implementation lanes have all landed since | Nearly-done task reads as fully blocked; only a small named remainder ("tick-consume habit") is actually left, unfiled. |

### Genuinely still blocked-on-human (not stale — checked and confirmed live)

- **#465** — his Q1 (repo-local vs global hook install) is unanswered as of `questions.md:70-98`, read directly. Correctly P1, correctly blocked.
- **#584** — his Q1-Q4 on the persistent-settings design are unanswered as of the same read (`questions.md`, the `#571`/user-settings entry, ~lines 40-68). Correctly blocked.
- **#438** — brainstorm was scheduled for "after 21:00 2026-07-28," now **three days overdue**, and unlike every other human-blocked item, **no `questions.md` entry exists for it at all**. This is a different failure mode from the five above — not a resolved blocker nobody re-checked, but a promised conversation that was never actually opened. Worth resurfacing as a real question rather than leaving it as a body-text note nobody sees.

### Informally blocked (untracked precondition, not a `blocked_on` value — same shape, different mechanism)

- **#322** — body says "touches `watch.py` (held by an agent right now)," dated 2026-07-27. No exclusive hold exists today (many lanes touch `watch.py` concurrently via worktrees). Stale, but invisible to a `blocked_on` scan since it was never encoded there.
- **#285** — blocked in-body on "after dd2 is fixed," an external tool with no ledger id at all. Cannot be checked or cleared by this audit; worth either giving it a real `blocked_on` or checking dd2's status directly.
- **#237** — explicitly model-gated ("only with an Opus 5 agent"), same untracked-precondition shape. Not urgent to fix (correctly parked), but worth noting as a third instance of the same pattern.
- **#448** — body prose says "blocked-on: #294," `#294` is now landed, but the DB's own `blocked_on` column was empty the whole time — the block was never machine-readable in the first place, so it wasn't caught by a `blocked_on` scan and isn't "stale" in the strict sense, just stale prose.

---

## 4. Duplicates and near-duplicates

| pair | verdict | argument |
|---|---|---|
| **#124 / #368** | **Near-duplicate — same underlying work.** | `#124` is "break up `watch.py`," `#368` is "break the large Python files into a modular, testable codebase" — both cite the identical `watch.py` 8647-line measurement, both reference `#425`'s symlink-migration constraint, and `#124`'s own body already recommends "the next demand-driven seam" as its remaining scope, which is precisely `#368`'s starting increment. Recommend treating `#368` as the authoritative task (it carries Max's direct quote and the CLI/SQLite sequencing) and folding `#124`'s remaining recommendation into it as the first concrete increment, rather than running two lanes with two plans against the same file. |
| **#601 / #604 (O1)** | **Overlapping — same component, same fix.** | `#601` (D8: chat heading wrap drops project chrome 7.4px) and `#604`'s bundled O1 (chat heading is the full title at heading weight, truncated) are the same surface. The visual audit itself says fixing O1's shape (shorten the heading, full title stays in the body) "also makes D8 disappear." Recommend whoever takes `#601` pull O1 out of `#604`'s batch and fix both together. |
| **#599 / #604 (O5)** | **Same family, not identical.** | `#599` (burndown tip paints over a live head line) and O5 (the column-inspector plate lands on the section label) are both "a `.bd*` overlay plate sits somewhere it shouldn't." Not the same defect — different elements, different fix — but worth the same lane doing both since they're adjacent code and adjacent visual real estate. |
| **#580 / #485** | **Overlapping scope, already flagged by #485's own text.** | `#485` (free-text subagent-policy field, persistence level) explicitly says the field itself was already settled by `#445`'s Q3 ruling, and what's new in `#485` is only the host-vs-worker *persistence level*. `#580` (free-text subagent-policy entry with cycling placeholders) reads as the same field's UI-polish half. Recommend sequencing them as one lane: `#485` settles placement, `#580` supplies the placeholder copy, built together rather than as two separate dashboard touches on the same control. |
| **#587 / #593 / #609** | **Cluster, not duplicates.** | All three are brief/lint-template correctness bugs found by the same `lane-592lint` dogfood report, touching overlapping files (the brief template, `lint.py`'s inbox regex). Different specific bugs, same natural batch — recommend one lane, not three. |
| **#603 / #593** | **Companion, not duplicate.** | Both are "fix the brief template" tasks, but from different lanes about different gaps (`#603` visual-lane-specific: stale screenshot root, tool naming; `#593` general: absolute `--target`, tree ambiguity, falsifiable-brief feedback). They'll touch the same template file — worth sequencing together to avoid two lanes editing it in parallel, not worth merging into one task. |
| **#605 / #606** | **Related, not duplicate.** | Both concern the coordinator's own gate-running process (`#605`: background-job tracking mechanics; `#606`: CPU contention causing false failures) but are genuinely different bugs with different fixes. Fine as two tasks; note them as siblings for whoever picks either up. |

---

## 5. Dead or superseded

Conservative — recommendations, not actions taken.

- **`#576`** — **VERIFIED landed, not folded.** Its exact ask ("cross-check
  every id in a Pending landed entry against a Folded entry") is what
  commit `e55f148c` implements (`git show --stat` confirms it touches
  `lint.py`+`test_lint.py` with the born-red test described), authored
  2026-07-31 07:18, and the state audit's own §1.6 independently confirms
  the gap it closed. Same shape as `#592`/`#586` (done, awaiting fold) —
  recommend folding it the same way rather than leaving it open.

- **`#275`** — **VERIFIED all six of its own escalated questions are
  answered or redirected.** Q1 split into `#359` (open, SaaS) and `#360`
  (landed design, self-hosted); Q2 redirected to `#360`; Q3/Q5/Q6 answered
  2026-07-29 05:54 per `questions.md`'s own record inside the body. Nothing
  in `#275`'s own text names a remaining open call on `#275` itself.
  Recommend folding it as superseded-by-split into `#359`/`#360`, not
  dropping — the research it produced is real and cited by both
  successors.

- **`#262`** — **INFERRED, not independently verified against the live
  handler — flagged for the coordinator to check, not asserted.** Its
  stated goal ("durably witnessed before `200`") reads as already delivered
  by `#263`'s landed lane E: `_send_receipt` only issues `202` after a
  journal commit succeeds, and refuses to mint a receipt-less `202`
  (`503` instead) on failure — exactly the shape `#262` asks for. I did not
  re-read the current `watch.py` handler myself to confirm this holds on
  master today; recommend a quick check (does `/command`, `/ask`, etc. ever
  return `200`/`202` without a prior journal commit?) before folding or
  dropping. If confirmed, this is a P0 that has been silently satisfied for
  two days.

No other candidates met the bar for this section — several tasks look
"maybe stale" on a title read (`#205`'s heartbeat-into-monitor idea reads
partially answered; `#338`'s IGC-bundling idea reads partially done
elsewhere) but their own bodies still name live, unresolved scope, so they
stay in the open backlog unchanged.

---

## 6. The top ten, ordered

Excludes the nine in-flight tasks by construction (they're already being
worked). Deliberately **not** all focus-work — three of ten are focus-core;
the rest are either process-integrity fixes that protect every future
lane's verification, or already-approved features that were invisible to
selection only because of a stale gate. That mix is the honest read of
"non-exclusive": the focus should win ties and orchestration budget, not
crowd out ready, approved, high-value work that has nothing to do with it.

1. **`#368`** — the named enabling task for the entire focus; both its own
   preconditions are now landed. Nothing else on this list unblocks the
   product goal as directly.
2. **`#124`** — the concrete next seam of the same initiative, ready today;
   recommend running it as `#368`'s first increment rather than a separate
   lane (§4).
3. **`#607`** — a verification-integrity bug that can make a correct fix
   read as failed, for every lane that touches a skill-dir-symlinked tool.
4. **`#608`** — the red-proof recipe bug that can turn a correct fix into a
   silent no-op certified as byte-identical. Same tier as `#607`, arguably
   worse (it certifies the wrong thing rather than merely confusing).
5. **`#587`** — cheap, mechanical, already visibly teaching lanes to invent
   workarounds instead of following the real convention.
6. **`#606`** — the coordinator's own gate is load-sensitive with nothing
   sequencing it against the lane fleet it runs beside most nights; the
   failure mode is a real regression waved through as flaky.
7. **`#254`** — fully authorised, zero design cost remaining, blocked only
   on a dead lane name nobody re-checked. Converts to real progress
   immediately.
8. **`#465`** — a live containment gap (a lane silently editing the main
   checkout) stays open until he answers one narrow question (repo-local
   vs global hook). Cheap ask, high safety value.
9. **`#373`** — large, real, Max-approved feature, both blockers landed.
   The clearest non-exclusivity case on this list: nothing about it serves
   the focus, and it belongs near the top anyway because it was only
   invisible by accident.
10. **`#602`** — cheap index for the design reference that the whole
    frontend extraction has to keep honest; directly serves the focus at
    near-zero cost, a good low-risk companion to `#368`/`#124`.

---

## Dogfood report

Friction with the loop itself, not with the task.

1. **The ledger is genuinely live during a read-only audit.** My first full
   pull returned 148 open tasks including `#592`; a later targeted re-check
   (needed anyway, to verify `#592`'s referenced commit) showed it had
   landed in between and dropped the open count to 147. Nothing broke — I
   caught it because I happened to re-query that id — but a lane doing a
   large read-only sweep with no re-check habit would silently report a
   stale count as current. Worth a line in whatever briefs commission
   full-backlog reads: re-verify open/landed state for any id you're about
   to make a strong claim about, immediately before writing the claim, not
   only at the start of the read.
2. **`blocked_on` staleness is easy to find but expensive to find
   completely.** The five named cases plus the one I found (`#342`) were
   all reachable by the same mechanical check (numeric `blocked_on` →
   target state), but the three "informal block" cases (`#322`, `#285`,
   `#237`) are only visible by reading full bodies, because nothing in the
   schema distinguishes "blocked on a task id" from "blocked on a sentence
   in the body." If this class of finding is valuable enough to ask for
   again, it might be worth a convention: any body sentence of the shape
   "blocked on/gated on/waiting on X" outside the `blocked_on` column
   should get a lightweight tag lint can at least count, even if it can't
   verify the referent.
3. **No other friction.** The subagent-protocol handshake, the read-only
   constraint, the exclusion list for in-flight tasks, and the doc-map
   registration convention were all clear and cost nothing to follow.
