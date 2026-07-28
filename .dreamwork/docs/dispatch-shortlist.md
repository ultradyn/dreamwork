# Dispatch shortlist — #437

A ranked shortlist of **startable** open tasks for the coordinator, answering:
**given these files are already owned by live lanes, what should go out next, and
what would it own?** Built 2026-07-28 ~20:14 against the live ledger and
`status.json`, using only the production parsers (`watch.parse_ledger`,
`watch.ledger_entries`, `watch.entry_origins`).

Overwrite target for `#437`. Not a census — the census
(`.dreamwork/docs/open-task-census.md`, `#420`) is the inventory; this is the
dispatch view on top of it.

---

## Preconditions (asserted)

| check | expression | value | assert |
|---|---|---|---|
| `## Open` heading matches | `len(re.findall(r'^## Open\s*$', text, re.M))` | **1** | == 1 ✓ |
| `## Recently landed` heading matches | `len(re.findall(r'^## Recently landed\s*$', text, re.M))` | **1** | == 1 ✓ |
| Open precedes landed | `open_match.start() < landed_match.start()` | **True** | ✓ |
| Open id count | `len(watch.parse_ledger(text)[0])` | **144** | — |
| Landed id count | `len(watch.parse_ledger(text)[1])` | **186** | — |
| Open entries | `len(watch.ledger_entries(open_text))` where `open_text` is the slice between the two headings | **144** | == open id set size ✓ |
| Parser agreement | `set(ids from ledger_entries(open_text)) == parse_ledger open` | **True** (0 disagreement) | ✓ |
| Live lanes | `len(status.json["dreamers"])` | **3** | — |
| Explicit `blocked-on: **human**` markers | count of open entries matching that marker | **1** (`#417`) | almost none yet, as the brief said |

Every count below is derived the same way. No literal open/landed totals are
trusted from earlier docs — the census said 139/175 a few hours ago; the live
pair is **144 / 186**.

---

## Live lanes (from `status.json` `dreamers` at run time)

| lane | task | model | owns |
|---|---|---|---|
| `fold` | `#432` (fold half) | glm52 | `dev/capture/above_fold.mjs`, `dev/capture/devoverlay.mjs`, `justfile` **DEFAULT_GUARDS** |
| `reload` | `#426` | glm52 | `.dreamwork/docs/reload-signal-design.md`, `.dreamwork/docs/doc-map.md`, `watch.py`, `test_watch.py`, `file-formats.md`, `dev/deploy_state.py`, `.dreamwork/review/src/426-reload-signal.html` |
| `shortlist` | `#437` (this job) | grok | `.dreamwork/docs/dispatch-shortlist.md`, `.dreamwork/docs/doc-map.md` |

Anything that needs `watch.py`, `test_watch.py`, `file-formats.md`, or
`dev/deploy_state.py` **conflicts with reload**. Anything that needs
`above_fold.mjs` / `devoverlay.mjs` / the DEFAULT_GUARDS line **conflicts with
fold**. `doc-map.md` is dual-claimed by reload and shortlist (accepted risk for
a row-append file). Soft conflict: two lanes editing different *regions* of
`justfile` (deploy recipe vs DEFAULT_GUARDS) will merge, but two writers is
still a real cost — call it out.

---

## Census findings — verified vs carried

Built on `.dreamwork/docs/open-task-census.md` (`#420`) rather than redoing it.
What still holds, what moved:

| census claim | now | verdict |
|---|---|---|
| 139 open / 175 landed | **144 open / 186 landed** (`len(parse_ledger…)`) | **moved** — ledger grew; do not reuse the old numbers |
| 10 stale-blocker entries (`#172 #218 #241 #242 #244 #249 #276 #333 #337 #360`) | 8 still open; **`#172` and `#218` have landed** | **partially verified** — remaining 8 still have targets in the landed set |
| `#419` as cheap structural unblock | `#419` is **landed** | **spent** — marker exists; only **1** open entry carries `blocked-on: **human**` (`#417`), so the marker is still almost unused |
| `#218` as cheap startable | **landed** | **spent** |
| `#415` as cheap startable | lint-local half landed with `#402b`; remainder filed as `#427` which **landed** (`30ed49d` multi-sha hand-offs in `watch.py`) | **spent as dispatch** — entry may still sit open pending fold, but there is nothing left to own |
| `#392` as startable | `#392a` landed; **`#392b` remains** and needs `file-formats.md` | **half spent** — remainder conflicts with reload |
| `#402` as startable | `#402b` (id vocabulary) landed; remainder is `dreamers` shape + `awaiting_human` derivation | **half spent** — remainder still worth dispatching |
| Human-blocked bucket A (`#264 #275 #294 #346 #353`) | still prose-gated / on his desk | **carried** — not re-litigated; excluded from shortlist |
| Answered-but-unprocessed (`#254 #367 #371 #50`) | `#254` startable for implementation; `#367` open for **2b** awaiting ruling; `#371` is **not** build-startable (second gate of `#263`, not just Q2); `#50` authorised for a **plan**, "later" | **verified with corrections** — `#371` is the important one the census over-read |
| Exclude `#263` lanes E, G, H | second-gate ask still on his desk; status forbids building them | **verified and excluded** |

---

## Ranked shortlist (12)

Ranking: higher priority first; within a band, **human origin outranks loop**;
within that, prefer a file set that is free *right now* over one that waits on
a live lane. "Inferred" ownership means the entry did not name the paths and
they were derived from the described surface.

### 1. `#431` — `just deploy`'s `pkill -f` kills the shell that mentions the snapshot

- **Priority / origin:** P1 · `loop`
- **Owns (stated/inferred):** `justfile` `deploy` recipe (the `pkill -f "$(basename "$snap")"` line). Prefer a **pid kill** using the listening-pid idiom already used nearby; do **not** take `dev/deploy_state.py` while reload holds it — a justfile-only pattern fix (`pkill -f "^python3 .*<snap>"`) is enough for one increment if pid plumbing would pull `deploy_state.py`.
- **Live conflicts:** **soft** with `fold` on `justfile` (fold owns DEFAULT_GUARDS, not the deploy recipe). No hard conflict with reload if `deploy_state.py` is left alone.
- **Size:** **one ~15 min increment** — single recipe change + a red that reproduces "caller cmdline contains the basename".
- **Startable:** **yes.** No human gate, no open task blocker.
- **Why now:** it killed the coordinator's own shell mid-deploy today (exit 144); half-finished deploy is the one recipe that leaves **his** dashboard down.

### 2. `#405` — dispatch should default to a worktree when files conflict

- **Priority / origin:** P1 · `loop`
- **Owns (stated):** `SKILL.md` (subagent / dispatch section); the brief-template rule that `.dreamwork/inbox.md` and `.dreamwork/handoffs.md` must be **absolute paths into the main checkout** when the lane is in a worktree. Possibly a short note in `CLAUDE.md` if the standing preference is restated there — keep it one-file if possible.
- **Live conflicts:** **none** of the three live ownership sets.
- **Size:** **one increment** for the written default + absolute-path brief rule; a **second** increment (or pre-dispatch check) to verify `just guards` / `just deploy` behaviour inside a worktree before a batch depends on it. Seam: docs/default first, worktree-guard verification second.
- **Startable:** **yes.**
- **Why now:** the session's binding constraint was file contention managed by declining dispatches; the standing rule already says worktrees, and first use (`.worktrees/verify-392a`) already proved the red can live off the live tree.

### 3. `#288` — prevent isolated agents from killing protected live services

- **Priority / origin:** P0/P1 · `loop`
- **Owns (inferred):** a design doc under `.dreamwork/docs/plans/` (or research) + optional bounded falsification prototype **outside** the live dashboard identity. **No** host/service/sandbox/deployment change authorised — design + prototype only (his `"rec"` 2026-07-28 01:26).
- **Live conflicts:** **none** if it stays design/prototype and does not edit `watch.py`.
- **Size:** **needs splitting** — (1) written design that answers tool-routing + supervised recovery + same-PID/health invariants; (2) bounded prototype. Seam is design freeze before any prototype code. Read `#358` (head/body) alongside, do not build `#358`.
- **Startable:** **yes** for the design increment. Not authorised to deploy.
- **Why now:** a guard-only subagent already killed `:35110` once; the approval is live and the threat is not theoretical.

### 4. `#254` — render review notes and loop replies as threaded conversation

- **Priority / origin:** P1 · `human`
- **Owns (stated + inferred):** implementation of the landed design at `.dreamwork/docs/plans/note-reply-threading-254.md` — primarily **`watch.py`** / note-render path, `test_watch.py`, possibly `watch-design.md` and transitions for arrival of a branch. Design artifact already at `.dreamwork/review/note-reply-threading-254.html`.
- **Live conflicts:** **hard with reload** (`watch.py`, `test_watch.py`). Dispatch only after reload frees them, or into a worktree with absolute inbox/handoff paths (`#405`).
- **Size:** **needs splitting** — design already landed design-only; R1/R2/R3 are answered so implementation is unblocked. Seam: parser recognition of `Reply (loop, …)` and rooting rules first; UI indentation/single-depth second; transitions third.
- **Startable:** **yes**, subject to the design's own scope (chronology, single inset depth, no root → stay top-level). The body still says "answer now open" in one place — that is **stale**; answers are in `## Answered`.
- **Why now:** human origin, P1, answered-but-unprocessed class — the card he filed this about still renders flat.

### 5. `#333` — `states.mjs` is the sixth holder of the forbidden count idiom

- **Priority / origin:** P2 · `loop`
- **Owns (stated):** `dev/capture/states.mjs` (convert the three `uniq(…).length >= 6` assertions to `between()` with vacuity preconditions). `transitions.md` doc half is **already done**. Leave the `<= 3` reduced-motion non-animation count alone.
- **Live conflicts:** **none** with fold (fold owns `above_fold` / `devoverlay`, not `states.mjs`) or reload.
- **Size:** **one increment**, red-first. Read `#414` first — it changed what the right mid-flight idiom is.
- **Startable:** **yes.** Blocker `#324` is landed (re-verified: `#324 ∈ landed`).
- **Why now:** last live count-idiom instances in `dev/capture/`; unblocked stale-blocker the census found and nobody re-triaged.

### 6. `#414` — motion guards depend on frame rate without saying so

- **Priority / origin:** P2 · `loop`
- **Owns (stated):** `dev/capture/confirmation.mjs` (precondition already in), `dev/capture/prominence.mjs` (unguarded `size >= 6`), and preferably a shared mid-frame helper if one is extracted (e.g. near `dev/capture/dom.mjs` or the `travel()` pattern in `reviewsplit.mjs`). **Formulation change**: count frames strictly between ends, not distinct values.
- **Live conflicts:** **none** of the live ownership sets. Do not register new DEFAULT_GUARDS lines (fold owns that list) unless necessary — these guards already exist.
- **Size:** **one increment** for prominence + aligning confirmation to the mid-frame rule; optional second increment to sweep any remaining `new Set(…).size >= N` if a helper lands.
- **Startable:** **yes.**
- **Why now:** same failure shape as `#428` (suite red under load, green alone); fixing the assertion is cheaper than waiting for a quiet machine.

### 7. `#241` — extract one composer mount contract

- **Priority / origin:** P2 · `human`
- **Owns (inferred):** `watch.py` composer mount surface (main document / Document PiP / `window.open` fallback without duplicating vocabulary, plugin refresh, drafts, submission witness, keyboard, transitions). Likely `watch-design.md` for the contract text. **Prerequisite to `#240`**; natural first of the composer cluster (`#241` → `#242` / `#244`).
- **Live conflicts:** **hard with reload** (`watch.py`).
- **Size:** entry says **~30 min** — one increment if the contract is extraction-only; split if PiP and `window.open` each need guards.
- **Startable:** **yes.** Blocker `#238` landed.
- **Why now:** human origin, unblocked composer-cluster head; the other two want this contract first.

### 8. `#337` — `do next` should fall back to `add idea` after submitting

- **Priority / origin:** P2 · `human`
- **Owns (stated/inferred):** `watch.py` (command-kind default after submit), possibly a small transition touch. Related idiom `#300` morphs run-mode descriptions through one popover.
- **Live conflicts:** **hard with reload** (`watch.py`).
- **Size:** **one increment** (~the size of a default-restore + guard).
- **Startable:** **yes.** Blocker `#336` landed.
- **Why now:** human UX; unblocked stale-blocker; independent of the composer-mount cluster so it can follow `#241` or run after reload without waiting on `#241`.

### 9. `#402` (remainder) — `dreamers` shape + derive `awaiting_human`

- **Priority / origin:** P2 · `loop`
- **Owns (remainder after `#402b`):** `status_sync.py` / `test_status_sync.py` (prune `dreamers` by the same live-pgrep test as `current_task_ids`; derive `awaiting_human` from `watch.parse_open_questions`). The `dreamers` row in `file-formats.md` + matching `lint.py` check if not already covered by `#402b`'s vocabulary work — **that half conflicts with reload**.
- **Live conflicts:** **`file-formats.md` / possibly `lint.py` with reload** if the format row is still missing; `status_sync.py` itself is **free**.
- **Size:** **split:** (a) `status_sync.py` prune + `awaiting_human` derivation (free files, one increment); (b) `file-formats.md` + `lint.py` contract row after reload. Seam is exactly that split — `#402b` already proved withholding lint from a format change is how the tools disagree by construction, so (b) must be same-commit format+lint.
- **Startable:** **yes** for (a) now; (b) after reload or with reload's consent on those files.
- **Why now:** a stale `dreamers` entry manufactures file contention; the dashboard reported ownership that had already landed, and the coordinator declined real work because of it.

### 10. `#360` — self-hosted remote Dreamhub auth on ssh, not a hosted IdP

- **Priority / origin:** P2 · `human`
- **Owns (inferred):** design + implementation around `dreamhub.py` / LAN auth path, plan under `.dreamwork/docs/plans/`, review artifact. His 14:53 ruling: reverse proxy acceptable; local Caddy satisfies self-hosted. **Public/WAN serving stays forbidden.** Status notes this supersedes `#276`'s bearer token if the ssh-issued session lands — prefer this over starting `#276` in parallel.
- **Live conflicts:** **none** of the three live sets (dreamhub is free). Stay off `watch.py`.
- **Size:** **needs splitting** — design/plan increment (session key issue, Caddy boundary, revocation) then implementation increments. Do not start code before the design increment freezes the boundary.
- **Startable:** **yes.** Blocker `#233` landed; Q2 settled.
- **Why now:** human origin; both blockers gone; LAN auth is the path he actually wants (ssh, not Cloudflare Access).

### 11. `#428` — guard suite fails under concurrent lanes and passes alone

- **Priority / origin:** P2 · `loop`
- **Owns (inferred):** a measurement write-up under `.dreamwork/docs/measurements/` (failure rates alone vs under load, N runs each). Code ownership only if the experiment names a fix — and that fix is likely `#414`'s mid-frame reformulation rather than a new guard.
- **Live conflicts:** **none** for the experiment itself. **Do not run `just test` while other lanes need 39890–39899** (standing rule; this brief forbids it too). Coordinator-owned suite runs only.
- **Size:** **one measurement increment**; any code fix is `#414` or a follow-up filed from the numbers.
- **Startable:** **yes** as measurement, when the machine is idle. Not startable as "another lane running the full suite beside fold/reload".
- **Why now:** third instance today, all frame-sampling assertions; numbers decide whether `#414` is the whole answer.

### 12. `#416` — a mitigation record is a claim about system state, and nothing re-checks it

- **Priority / origin:** P3 · `loop`
- **Owns (stated):** a **dated audit report** (e.g. `.dreamwork/docs/measurements/` or a short doc), not a tool, not edits to his configs. Check the four unchecked mitigations named in the entry; report hold/false; **ask before repairing**.
- **Live conflicts:** **none.**
- **Size:** **one short increment** (read-only checks + write-up).
- **Startable:** **yes.**
- **Why now:** cheap trust repair; one of three checked mitigations was already false when last looked; an unexamined mitigation list is how the next investigation gets lied to.

---

## Ruled out as not-startable (for this shortlist)

| entry | why |
|---|---|
| **`#263` lanes E, G, H** | Second gate is his; ask is on his desk; **building any of them is forbidden**. Lanes A–D/F are already done or complete; the entry stays open as the umbrella, not as a dispatch of E/G/H. |
| **`#421`** | Artifact live; **remaining work is his A/B/C/D ruling**, then `DREAMWORK.md` + `file-formats.md` + `lint.py`. Human decision. |
| **`#417`** | Explicit `blocked-on: **human**` — only entry carrying the `#419` marker. |
| **`#367` increment 2b** | Previews landed; **2b (strip below the cliff) awaits his ruling** on the artifact. Earlier increments are done. |
| **`#371`** | Census called it unprocessed-answer; the entry **corrected itself**: Q2 yes is not authority to build short-body policy — that sits behind `#263`'s **second gate**. Not startable as implementation. |
| **`#346` `#353` `#264` `#294` `#275`** | Live on his desk / schema-ruling chain. |
| **`#281`** | Twelve increments blocked on his design ruling; design-phase only. |
| **`#249`** | Startable in principle (blocker `#245` landed) but **owns `devoverlay.mjs` → hard conflict with fold**. Queue behind fold, do not dual-write. |
| **`#436`** | Blocked on nothing logically, but **owns `file-formats.md` + `above_fold.mjs` → conflicts both reload and fold**. Multi-increment retrofit (11 rebuildable, 12 exempt). After both lanes free. |
| **`#392b`** | Format time-in-entry; **`file-formats.md` held by reload**. |
| **`#415`** | No remaining work to dispatch — lint half closed with `#402b`; `watch.py` half landed as `#427`. Fold the entry; do not re-dispatch. |
| **`#276`** | Unblocked, but **`#360` supersedes** if ssh session lands; starting both is duplicate LAN-auth design. Prefer `#360`. |
| **`#50`** | "rec go" but **"later"**; authorised for a **plan**, not a build sprint tonight. |
| **`#274`** | P0/P1 and real, but needs a durable idempotency design across submit paths and almost certainly `watch.py` — **too large and too contended for a cold dispatch tonight**. File a split before a lane. |

Hidden human blockers found in prose (not just the marker): `#421` (ruling), `#417` (marker), `#367` 2b (artifact ruling), `#371` (second gate), `#263` E/G/H (second gate), `#281` (design ruling), `#346`/`#353` (S1–S4 / schema), `#264`/`#294`/`#275` (desk).

---

## What to dispatch first, and what can run in parallel

### First dispatch

**`#431`** if you accept a soft `justfile` adjacency with fold; otherwise **`#405`**.

`#431` is the sharper "why now": it is P1, one increment, and it is a deploy footgun that already fired. `#405` is the structural pick that makes every later conflict cheaper (worktree instead of decline).

### Parallel-safe groupings (file sets disjoint)

**Triple A — free right now, no hard live conflict:**

| task | file set |
|---|---|
| `#333` | `dev/capture/states.mjs` |
| `#405` | `SKILL.md` (+ brief absolute-path rule) |
| `#414` | `dev/capture/prominence.mjs`, `dev/capture/confirmation.mjs` |

These three sets are pairwise disjoint and miss every path in `status.json` `dreamers`.

**Triple B — add a fourth cheap lane if capacity allows:**

| task | file set |
|---|---|
| `#416` | new measurement/audit doc only |
| `#288` | new plan/research doc only (design increment) |
| `#402`(a) | `status_sync.py`, `test_status_sync.py` only — **not** `file-formats.md` |

Still disjoint from Triple A and from each other.

**Serial behind reload** (do not parallelise with `#426`): `#254`, `#241`, `#337`, `#392b`, `#402`(b), anything else that needs `watch.py` / `file-formats.md`.

**Serial behind fold:** `#249` (`devoverlay.mjs`), `#436` (`above_fold.mjs` + format).

**Human-origin pair once reload frees `watch.py`:** `#241` then `#337` (disjoint *intent*, same file — serial on `watch.py`, not parallel), or `#241` in a worktree while `#360` runs on `dreamhub.py` in another:

| task | file set |
|---|---|
| `#241` (worktree) | `watch.py`, `watch-design.md` |
| `#360` | `dreamhub.py`, plan/artifact under `.dreamwork/docs/` |

Disjoint. That is the human-origin parallel pair.

---

## Method notes

- Parsers: `import watch` → `parse_ledger`, `ledger_entries`, `entry_origins` only. No second ledger reader.
- Open section isolated by the line-anchored `## Open` / `## Recently landed` headings (preconditions above); `ledger_entries` run on that slice so landed prose cannot contribute heads.
- Stale-blocker targets re-checked with `id ∈ landed` from `parse_ledger`, not from memory.
- Ownership "inferred" means the entry described a surface and the paths were taken from that surface's real code location; prefer stated paths when the entry names them.
- This document does not modify the ledger, `questions.md`, or `status.json`.
