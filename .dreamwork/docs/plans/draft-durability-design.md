# #269 — durable, cross-tab text drafts: one deep module every future input consumes

**Status: design only.** No implementation authority. This document does
not authorise edits to `watch.py`, the composer, answer boxes, IndexedDB
code, or anything behind `#263`'s second gate (lanes E, G, H). Approving
it accepts the **contract and the order**, not any code.

**Origin.** Human, escalated to P0 2026-07-27 21:35 via the composer:
*"draft answers to questions on review pages can be lost… we must have
persistence and never lose work on an autoreload of a page."* Related:
`#163` (composer drafts), `#118` (live box outranks storage), `#446`
(second Answer overwriting the first — same class: his words drop),
`#263` (receipt boundary for clear-on-durable-receipt).

**What already landed (acute half).** `0366706` / merged `e383492`:
`dwDraft` gives the per-question answer box the composer's rules
verbatim — `localStorage` key `dw:adraft:<target>:<title>`, save on every
`input`, restore after every render that recreates the box, clear only on
HTTP-successful send, live box outranks storage, every storage call
wrapped. Guard `dev/capture/reviewdraft.mjs` is in `DEFAULT_GUARDS`.
**The reported loss on review pages is already fixed.** What remains is
the deep module, cross-tab coherence, retention, migration off ad-hoc
keys, and consumers (`#askbox`, `#ptext`, future chat, `#241`'s mounts).

**Goal it serves.** He stops losing typed work, on every surface that
takes text, including surfaces that do not exist yet — without inventing
a second draft policy per surface.

---

## 0 — The recommendation (first, because it decides the rest)

**Do not jump to IndexedDB as the first remaining increment.** The
reported loss was a full-reload hole on the review-dock answer box; that
hole is closed with the same `localStorage` shape the composer has used
since `#163`. IndexedDB buys larger quota and a single object store with
indexes — real, and part of the long-term shape — but it does **not**
stop the loss he already stopped, and it is async in a path that must
never throw while he types.

**What to build next, in order (§7):**

1. **Elevate `dwDraft` into the named module contract** (§5) that every
   later input must consume — still on `localStorage`, same keys for
   answers, same clear-on-success rule. Cost: a rename + one API surface.
   Buy: `#241`, `#177`, `askbox`, `ptext` stop re-deciding the rules.
2. **Bind the two unbound boxes** (`#askbox`, `#ptext`) to that module.
3. **Cross-tab: focus-wins + storage events** (§3) — not last-write-wins
   into a focused field.
4. **Retention + a human-visible "forget"** (§4).
5. **IndexedDB backend behind the same API**, when (and only when) a
   measured reason appears: quota pressure, structured GC, or a consumer
   that needs indexes. Migration from today's keys is written once (§2).
6. **Pluggable receipt witness** for clear-on-durable-receipt — today
   `res.ok`, later `#263`'s receipt when the second gate opens. **Do not
   build lanes E, G, or H here.**

> A design whose first useful increment is three tasks deep has failed
> him. The first useful increment already shipped. The next useful one is
> the module boundary + the two unbound boxes — not a store rewrite.

---

## 1 — The logical input ID

### What identifies "the same box"

A **logical input ID** is a stable string naming *what the draft is for*,
not *which DOM node currently holds it*. Nodes die on every tick
re-render and on every full reload; the ID must not.

```
logicalId  =  kind  +  ":"  +  scopeKey
storageKey =  "dw:draft:v1:"  +  projectTarget  +  ":"  +  logicalId
```

| part | source | stable across | must not be |
|---|---|---|---|
| **`projectTarget`** | `data.target` — the absolute project path from `/data.json` | reloads, routes, tabs on the same checkout | the project *basename* (two checkouts can share one; a draft under the wrong loop is worse than a lost one — already the composer's rule) |
| **`kind`** | closed set, extended only by the module | — | invented per surface |
| **`scopeKey`** | see table below | re-render, re-sort, section re-index (`o3`→`a0`), route change | the positional DOM id (`qi o0`, card index) |

**Closed `kind` set for v1** (extend by adding a row, not by inventing a
key shape elsewhere):

| kind | scopeKey | one box means | consumers today |
|---|---|---|---|
| `composer` | `main` | the command composer for this project | `#cmdtext` (+ `#241` mounts: main, Document PiP, `window.open`) |
| `answer` | the question's **title** (the `data-qid` identity) | his drafted answer to that question | card textareas on `/questions`, dashboard, review dock |
| `note` | the question's **title** | his drafted follow-up note on that question | same box in note mode — **same physical box, different kind** when mode is note (see below) |
| `ask` | `main` | "ask the dreamer" on `/answers` | `#askbox` |
| `popout` | `main` | the popout thought box | `#ptext` |
| `chat` | reserved: conversation id when `#229`/`#253` land | future | none yet |

**Answer vs note.** They share one physical `<textarea>` today (`#103`:
one input per card, mode decides where the text goes). Two honest
options:

- **A (recommended):** one logical id per card for the shared box —
  kind `card` with scopeKey = title — so flipping answer↔note does not
  invent a second draft or drop the first. The *send path* decides
  `/answer` vs `/comment`; the draft is "what is in the box".
- **B:** separate `answer` / `note` kinds keyed by title+mode. Buy:
  a mode flip keeps the other mode's draft. Cost: two stores for one
  box, and a restore must pick a mode — the acute fix already chose A
  in spirit (`dwDraft` keys only by title).

**Recommendation: A.** The box is the unit he types into. Mode is
routing, not identity. Cost of A: a drafted "note" that he never sent
becomes the text of an "answer" if he flips mode — which is exactly how
the live box already behaves, and matching live behaviour is the point.
Buy: one key, no mode-restore puzzle, matches `0366706`.

### When the thing it attaches to no longer exists

| case | rule |
|---|---|
| Question folded / renamed / gone from `questions.md` | Draft **stays in the store** until retention GC or explicit forget. Nothing mounts with that `scopeKey`, so nothing restores it into a wrong box. A restore always requires a live element whose declared logical id matches. |
| Title renamed on disk | Old key is orphaned (same as "gone"). The new title is a new logical id. **Do not** fuzzy-match titles — a wrong restore is worse than a lost draft (the brief's bar). |
| Project path changes (checkout moved) | Partition key changes; old partition is unreachable from the new path. Same as two checkouts: isolation is deliberate. Optional: a one-shot "import drafts from previous path" is out of scope and not recommended. |
| Composer / ask / popout | `scopeKey = main` — the box always exists when that surface mounts; no orphan case. |

**Wrong-box restore is the failure mode that must be structurally
impossible.** The only restore path is:

```
for each mounted element with data-draft-id=L:
    if el.value is non-empty: skip   // live outranks (#118)
    else: el.value = store.get(L) or ''
```

No scan of "similar" titles. No positional fallback. No "best effort"
into the first empty box.

### Cost / buy of this ID shape

| | |
|---|---|
| **Buys** | Same box across reload, route change, second tab, and card re-index; wrong-box restore is impossible by construction; `#241` can mount three composers against one `composer:main` id. |
| **Costs** | Title-as-key means a rename orphans a draft (accepted). Kind set must be extended deliberately. Partition by absolute path means drafts do not follow a moved checkout (accepted — same as today). |

---

## 2 — Where the truth lives

### Today (measured, not assumed)

| surface | store | key | clear on |
|---|---|---|---|
| composer `#cmdtext` | `localStorage` | `dw:draft:<target>` (+ kind in JSON) | successful `/command` (`res.ok`) |
| answer/note card box | `localStorage` via `dwDraft` | `dw:adraft:<target>:<title>` | successful `/answer` or `/comment` |
| `#askbox` | **none** (only in-memory `#118` snapshot across re-render) | — | — |
| `#ptext` | **none** | — | — |
| settings / tint / run-mode arm | various `localStorage` keys | not drafts | n/a |

Record shape today (both draft systems):

```json
{ "t": "<text>", "k": "<optional kind for composer>" }
```

### Target store shape (backend-agnostic record)

The **module** owns the record. The **backend** is swappable
(`localStorage` first, IndexedDB later) without consumers changing.

```
DraftRecord {
  v:        1,                    // schema version
  logicalId: "answer:<title>" | "composer:main" | …,
  project:  "<absolute target path>",
  text:     string,
  updatedAt: number,              // ms since epoch, set on every save
  meta: {                         // optional, never required for restore
    kindHint?: string,            // composer command kind, etc.
    heightPx?: number,            // #177 may store here; draft module does not require it
  },
  tabId?:   string,               // last writer tab (cross-tab, §3)
  seq?:     number,               // monotonic per-tab write counter
}
```

**Project partitioning.** Every key or IDB index is scoped by
`project` (= `data.target`). A read or write with no target yet is a
no-op (composer's existing rule: first fetch has not landed → do not
share an empty key).

**IndexedDB (when introduced), one database:**

| | |
|---|---|
| name | `dreamwork-drafts` |
| version | 1 |
| object store | `drafts` |
| keyPath | `id` = `project + "\0" + logicalId` (one record per logical input per project) |
| indexes | `by_project` (`project`), `by_updated` (`updatedAt`) for GC |

Quota and privacy stay in the browser origin. **Never** write drafts to
the repo, to `questions.md`, or to the server. An unsent draft is a
thought he has not chosen to send (`#163`'s argument, still load-bearing);
`#199` already witnesses everything he *did* send.

### Migration from today's `localStorage`

One-shot, first time the module boots on a page that has a target:

1. Read `dw:draft:<target>` → if present, write record for
   `composer:main` (carry `k` into `meta.kindHint`); **leave the old key
   in place until the first successful clear or the next save through the
   new API**, then delete the old key. Dual-read for one session is safer
   than dual-write forever.
2. Scan `dw:adraft:<target>:`* → for each, write `card:<title>` (or
   `answer:<title>` under option A) with `text` from `t`.
3. After a successful migrate of a key, delete that old key so a second
   tab does not re-migrate a cleared draft.
4. Never migrate a corrupt JSON blob — drop it, log nothing user-visible
   (a toast about "bad draft" is noise; the live box is the truth).

**A draft written by the old code** is therefore either (a) still
readable under the old key by the dual-read path, or (b) already copied
into the new record and the old key removed. There is no window where
the acute fix stops working before the module is online.

### Cost / buy

| | |
|---|---|
| **localStorage-first** | Buys: sync writes in the `input` handler (no promise rejection mid-keystroke); `storage` events for free cross-tab (§3); zero new async surface; matches what already works. Costs: ~5MB quota per origin shared with other keys; no indexes (GC is a linear scan of known prefixes — fine for dozens of drafts, not thousands). |
| **IndexedDB later** | Buys: quota headroom, `by_updated` GC, structured multi-project listing for a future "forget" UI. Costs: async API (save must still never throw into the input path — fire-and-forget with in-memory buffer); more code; private-mode quirks differ by browser. |

---

## 3 — Cross-tab coherence (not last-write-wins on a live field)

He runs several windows per project (`#143` exists because of that).
Two tabs, one logical box: the forbidden design is **last-write-wins into
the field he is typing in** — that is data loss dressed as sync.

### Policy: focus-wins, store is the backstop

1. **A focused element is owned by its tab.** Remote updates **never**
   overwrite `el.value` while `el === document.activeElement` (or while
   the element has a session-local `dirtySinceFocus` flag set by `input`
   since the last focus). The store may still update; the caret does not
   move under him.
2. **An unfocused empty box accepts a remote restore** the same way a
   reload does — storage fills it.
3. **An unfocused non-empty box that differs from the store** does **not**
   auto-clobber. Options when the remote is newer:
   - **R1 (recommended default):** leave the local text; on next focus,
     if store is newer than the last local save *this tab knows about*,
     show a quiet one-line offer: *"updated in another tab — load that
     version?"* with an explicit act. No silent replace.
   - **R2:** always take the newer store when unfocused (closer to LWW,
     still never when focused). Simpler; risks losing an unfocused tab's
     half-finished thought if he typed, blurred, and the other tab saved.
   - **R3:** hard lock / lease via `navigator.locks` or a lock key in
     storage — first focus wins until blur. Correct under contention;
     fails closed when a tab is killed holding the lock (need TTL). Heavier
     than the traffic justifies for text drafts.

**Recommendation: focus-wins + R1.** Cost: a small UI line on conflict
(rare). Buy: he never loses in-progress text to another tab's autosave,
and he never loses a blurred tab's text to silent LWW without a choice.
This is the decision that is genuinely his if he dislikes the offer UI
(§8).

### Mechanism

| layer | mechanism | role |
|---|---|---|
| **persist** | `localStorage` set on every `input` (no debounce — a debounce is a window of loss, already rejected by the acute fix) | truth on disk for reload |
| **notify peers** | `storage` event (same-origin, other tabs only; the writing tab does not receive it) | "the store moved" |
| **optional upgrade** | `BroadcastChannel('dw-drafts')` when on IndexedDB (IDB has no `storage` event) | same notify role |
| **not used** | `navigator.locks` in v1 | reserve for R3 if R1 proves insufficient |

On `storage` / BroadcastChannel message for logical id L:

```
if no mounted el for L: ignore (store is enough)
if el is focused or dirtySinceFocus: ignore apply; optional badge "saved elsewhere"
else if el.value === '' : restore from store
else if store.updatedAt > localSeenAt && el.value !== store.text: offer R1
else: no-op
```

### Failure modes when a tab is suspended or offline

| case | behaviour |
|---|---|
| Tab backgrounded / frozen (mobile) | No `input` events; last save before freeze is in the store. On resume, re-read store for unfocused boxes; focused box keeps its in-memory value (still outranks). |
| Tab crashed | Store has last keystroke that reached `localStorage` (sync). No debounce means that is every keystroke that the event loop delivered. |
| Offline (server down) | Drafts are local-only; offline is irrelevant to the store. Clear-on-receipt does not fire (send fails → draft kept) — already true today. |
| Two tabs type at once into the "same" box | Both save; store ends at last write; **neither focused field is overwritten**; on blur each flushes; the conflict offer (R1) appears if they diverged. No automatic merge of prose (see §6 — CRDT is not worth it). |

### Cost / buy

| | |
|---|---|
| **Buys** | Several views behave as one *store* without becoming one *cursor*; matches `#118` and the composer's two-window comment already in `watch.py`. |
| **Costs** | R1 needs a quiet conflict line (transitions.md — arrive/depart, not snap). R2 is cheaper and slightly more lossy on blur. |

---

## 4 — Clear-on-durable-receipt, and the `#263` dependency

### The rule

> A draft may be dropped **only** when a **pluggable receipt witness**
> says the real write is durable. Close, blur, route change, rejected
> POST, network throw, and "request sent" are **not** witnesses.

This is already the acute fix's contract (`clear` only after `res.ok`).
The design hardens it into a named seam so `#263` can replace the witness
without rewriting every consumer.

### Today's witness (pre-`#263` cutover)

```
witness = (response) => !!(response && response.ok)
```

That is "the HTTP handler returned 2xx after its current write path."
It is **not** `#263`'s immutable receipt. It is the best witness the
server offers today, and it is what the acute fix and the composer use.

### `#263` dependency — named, not built

| fact | detail |
|---|---|
| **What `#263` is** | User-event journal: client attempt → durable receipt → proved domain effect. After `202`, one immutable receipt exists; retries share identity. Plan: `.dreamwork/docs/plans/user-event-journal.md` (+ implementation plan). |
| **Which lanes are the receipt path** | **E** (HTTP cutover / envelope), **G** (related client attempt durability — if present in the plan's lane map), **H** (mixed-version gate). His 05:43 answer: *E and H stay behind a second gate until A–D are proved.* |
| **Gate name** | **`#263` second gate** — human-opened; not opened by "Q2 yes" alone (that amended design only; see ledger notes on `#371`). |
| **What this design must NOT do** | Implement any of lanes E, G, or H; change POST bodies to carry `client_action_id`; add journal tables; refuse writes on version mismatch. |
| **What this design does** | Define `clear(logicalId, witness)` where `witness` is a function or token the *send path* supplies. Today: `if (res.ok) drafts.clear(id)`. After the gate: `if (receipt.accepted) drafts.clear(id, receipt)`. |

### Pluggable receipt seam

```
// consumer (send path) — only place that may clear
const res = await postJSON(...)
if (DraftStore.isDurable(res)) {   // today: res && res.ok
  DraftStore.clear(logicalId)
  // … morph / confirmation …
}

// later, when #263 E is live (NOT in this task):
// DraftStore.isDurable = (res) => res && res.status === 202 && res.receipt_id
```

`isDurable` lives in **one** place. Consumers call `clear` only after it.
The draft module itself never interprets HTTP.

### Cost / buy

| | |
|---|---|
| **Buys** | Clear-on-receipt stays correct across the `#263` cutover without a flag day on every box; failed sends keep text (already proven valuable). |
| **Costs** | Until `#263` E lands, "durable" means "server said 2xx on the current path," which can still disagree with disk in edge cases the journal is meant to close — **that gap is owned by `#263`, not by a second draft design.** |

---

## 5 — Privacy, retention, and "forget this"

Drafts are **his words he has not sent.** Retention is a promise.

| rule | default (recommendation) | why |
|---|---|---|
| **Where** | Browser origin only; never server; never git | `#163`: publishing unsent thought is wrong; `#199` covers what he sent |
| **How long** | Keep while useful; **GC records with `updatedAt` older than 30 days** and no matching mount obligation | Bounds orphan pile after folded questions; 30d is a starting number, not sacred |
| **How much** | No hard cap beyond storage quota; on `QuotaExceededError`, drop oldest by `updatedAt` within the same project first, never throw into `input` | Typing must not break |
| **Forget this box** | Explicit control near the field or in a small drafts inventory: clears that `logicalId` | His act, same as deleting text |
| **Forget all for this project** | One control in project/settings area (coordinates with `#228` only as a *placement* question, not a server setting — drafts stay local) | Machine shared with someone else; or "start clean" |
| **Forget on successful send** | Automatic via §4 | Not retention — receipt |

**Human-visible "forget"** is not a settings deep-link only. At minimum:
emptying the box and blurring does **not** clear the store (he may have
selected-all and panicked); a deliberate "discard draft" does. Empty
string on `input` **does** remove the key today for answers (`dwDraft.save`
with `''`) — keep that: deleting his words in the box is his act, and
keeping a ghost of deleted text would restore it against his will on the
next reload.

### Cost / buy

| | |
|---|---|
| **30-day GC** | Buys: orphaned answer drafts after folds do not live forever. Costs: a very old unsent thought disappears — acceptable if documented; he can lower/raise. **This number is a candidate `#ask`.** |
| **Empty-clears-store** | Buys: matches intent. Costs: accidental select-all+type can wipe store — same as today; undo is not in scope. |

---

## 6 — Failure modes (a store that throws while he types is worse than none)

Every public method of the module is **exception-safe**. Failures degrade
to "no persistence," never to "broken box."

| failure | behaviour |
|---|---|
| `localStorage` / IDB unavailable (private mode, disabled) | save/restore/clear no-op; live box works |
| `QuotaExceededError` | drop oldest project drafts once; retry once; then no-op |
| corrupt JSON / bad `v` | treat as missing; delete bad key; do not restore garbage into a box |
| IDB blocked / versionchange stuck | fall back to in-memory session map for this tab only; optional one-time note in dev log |
| `storage` event with hostile/oversized payload | validate shape; ignore |
| restore into a detached node | no-op |
| concurrent migrate in two tabs | last writer wins on the *new* key; dual-read prevents loss of old key mid-flight |

**No debounce** on save. Confirmed by the acute fix's comment block and
by the loss mode it closed: a reload inside a debounce window is the bug.

---

## 7 — What is NOT worth doing (with reasons)

| temptation | why not |
|---|---|
| **IndexedDB as the first remaining increment** | Reported loss is fixed; IDB does not fix a new one until quota or structure bites. Async store + input path is a footgun. Elevate the API first. |
| **Server-side / repo-side draft store** | Publishes unsent thought; fights `#163`/`#199` split; multi-device sync is a different product (`#228` is for *settings*, which are not drafts). |
| **CRDT / OT merge of concurrent prose** | Cost dwarfs the case rate (two tabs typing the same answer). Focus-wins + R1 offer is enough. |
| **Debounced save "for performance"** | Performance is not the constraint; loss is. `localStorage` set per keystroke is cheap at human typing rates. |
| **Save-on-blur only (+ beforeunload flush)** | Captures *most* idle loss, **misses** the autoreload-mid-sentence case he reported. The acute fix already proved continuous save is the right shape. A blur-only design would be a regression. |
| **Fuzzy title match on restore** | Wrong-box restore is worse than loss. |
| **Clear draft on close / blur / route leave** | The moments he most needs it back (`#163`). |
| **Building `#263` E/G/H "while we are here"** | Behind his second gate; out of ownership; half a receipt system is worse than today's `res.ok` witness. |
| **Per-surface draft helpers that re-encode the rules** | Exactly how composer and answers almost drifted; the module exists so they cannot. |
| **Persisting drafts into `sessionStorage` only** | Dies with the tab; fails the reload case. |

**Honest smaller mechanism check (brief requirement).** Is there a
ten-line save-on-blur that would have been enough? **No** — not for the
reported failure. Autoreload kills the tab mid-sentence without blur.
The ten-line shape that *did* work is what shipped: save on `input`,
restore on every mount, clear on success. The remaining work is
**unifying and extending that shape**, not replacing it with less.

---

## 8 — The seams (named interface)

One module. Working name: **`DraftStore`** (implementation may keep the
`dwDraft` spelling as a façade during migration).

```
DraftStore = {
  // identity
  id(kind, scopeKey) -> logicalId,          // "card:"+title, "composer:main", …

  // lifecycle for a mounted element
  bind(el, logicalId, opts?),               // input→save; optional meta; sets data-draft-id
  unbind(el),                               // remove listeners only; does not clear store

  // direct (used by send paths and tests)
  save(logicalId, text, meta?),
  restore(logicalId, el),                   // no-op if el.value non-empty
  clear(logicalId),                         // ONLY after isDurable(witness)
  get(logicalId) -> DraftRecord | null,

  // receipt seam (§4)
  isDurable(response) -> boolean,           // default: !!response?.ok; replaceable after #263

  // privacy
  forget(logicalId),
  forgetProject(),                          // all drafts for data.target
  gc(maxAgeMs?),                            // default 30d

  // cross-tab
  onRemote(logicalId, cb),                  // storage/BroadcastChannel
  // bind() registers the default focus-wins apply policy
}
```

### What each consumer takes

| consumer | uses | does not re-decide |
|---|---|---|
| **Answer/note boxes** (today's `dwDraft` callers) | `bind(ta, id('card', title))`; `clear` after durable send; `restore` after every DOM commit (`setContent`, review-dock `replaceWith`) | key shape, clear policy, storage backend |
| **Composer** (`#cmdtext`, and **`#241` mount contract**) | `bind(cmdtext, id('composer','main'))`; same clear on durable `/command`; **one logical id shared across main / PiP / `window.open` mounts** so popouts are the same box | draft key per mount (that was the drift `#241` exists to end) |
| **`#177` autogrow** | May put `heightPx` in `meta` via `save`'s meta arg, or keep height in the separate `#118` snapshot — **height is not text**. Draft module does not grow the box; it only must not fight `#118` (restore text first, then height). | whether drafts exist |
| **`#askbox` / `#ptext`** | `bind` with `ask:main` / `popout:main`; clear on durable `/ask` or popout command | inventing a third key scheme |
| **Future chat (`#229`/`#253`)** | `id('chat', conversationId)`; same bind/clear | anything in this file |

`#241`'s contract text should require: *every mount of the composer
calls `DraftStore.bind` with `composer:main` and never implements a
private draft key.* That is the load-bearing sentence for popouts.

---

## 9 — Implementation order (smallest first)

| # | increment | stops / enables | not yet |
|---|---|---|---|
| **0** | **DONE** `dwDraft` for answer boxes + reviewdraft guard | the reported review-page reload loss | module, other boxes, cross-tab UI |
| **1** | Extract `DraftStore` API; route composer + `dwDraft` through it; dual-read old keys; no behaviour change | one policy, one test surface | askbox/ptext |
| **2** | Bind `#askbox` and `#ptext` | the two remaining first-class boxes that still evaporate on reload | cross-tab offer UI |
| **3** | Cross-tab focus-wins + `storage` listener; R1 offer line (or R2 if he picks it) | multi-window coherence | IDB |
| **4** | Retention GC + forget controls | privacy promise is real, not only documented | IDB |
| **5** | IndexedDB backend + migrate; keep API | quota/index headroom | — |
| **6** | Point `isDurable` at `#263` receipts | **blocked on `#263` second gate** (lanes E/G/H); design-only dependency until then | building the journal |

**First useful remaining increment = #1 then #2 in one or two commits.**
Neither needs IndexedDB. Neither needs `#263`. Neither touches lanes E/G/H.

### Proof obligations (when implementation is authorised)

- Red-first: reinstate "no save on input" → reviewdraft (or successor)
  fails mode 1; reinstate "clear on blur" → fails the keep-on-reject case.
- Assert preconditions at runtime (fixture has two different titles;
  restore into title A never equals B's text).
- Drive the **review dock** and the **dashboard**, not only `/questions`
  (`#179`).
- Cross-tab: two pages, focus in A, type in B, assert A's focused value
  unchanged (discriminating; end-state-only is hollow).

---

## 10 — Decisions that are his (and what is not)

| decision | recommendation | needs his ruling? |
|---|---|---|
| Cross-tab when unfocused texts diverge | **R1** — offer, never silent LWW | **Yes** — taste + risk |
| Retention window | **30 days** idle GC | **Yes** — his words, his promise |
| Answer vs note identity | **A** — one card draft | No — matches live box and acute fix |
| localStorage first, IDB later | yes | No — engineering order; IDB stays in the design |
| Clear only on durable witness | yes | No — already his `#163` rule |
| Do not build `#263` E/G/H here | yes | No — his gate |

---

## 11 — Relationship to open tasks (pointers only)

- **`#269`** — this design; acute half landed; remainder tracks the order in §9.
- **`#241`** — composer mount contract **consumes** `DraftStore.bind(composer:main)`.
- **`#177`** — autogrow may store height in `meta` or in `#118`; does not own text durability.
- **`#263`** — receipt witness upgrade only after second gate; reference, do not implement.
- **`#228`** — project settings are server-side and sync; **drafts are not settings**.
- **`#446`** — server/parse data loss on second Answer; different layer (durable file), same moral class.

---

## SUMMARY

- **Logical ID:** `kind:scopeKey` inside project partition `data.target`.
  Cards use title identity (not position). Restore only into a mounted
  element that declares that id; orphans GC by age; never fuzzy-match.
- **Truth:** browser-local; elevate today's `localStorage` into
  `DraftStore`; migrate `dw:draft:` / `dw:adraft:`; IndexedDB is a later
  backend behind the same API, not the first cut.
- **Cross-tab:** focus-wins; store updates always; remote never overwrites
  a focused/dirty field; unfocused conflicts use **R1 (offer)** not LWW.
  Mechanism: `storage` events (BroadcastChannel when on IDB).
- **Clear-on-receipt:** only via `isDurable(response)`; today `res.ok`;
  later `#263` receipt. **Second gate named; lanes E/G/H not built.**
- **Privacy:** local only; empty box clears that draft; 30d GC + explicit forget.
- **Not worth it:** IDB-first, server drafts, CRDT, debounce, blur-only,
  fuzzy restore, building `#263` early.
- **Seams:** `DraftStore` for answer boxes, `#241` composer mounts,
  `#177` (meta only), ask/popout/chat.
- **Order:** acute done → extract API → bind ask/ptext → cross-tab →
  retention → IDB → `#263` witness.
- **His calls:** R1 vs R2 (cross-tab), retention days.

---

*Design only. Implementation requires a separate grant.*
