# Draft durability status — what `#269` actually guarantees (empirical)

**Model:** Grok 4.5 (xAI) · lane `draftcheck` · 2026-07-29  
**Authority:** observation + cited production lines. Where a comment claims X and
behaviour differs, behaviour wins. Comments are not evidence.

**Method:** own `watch.py` on **:39897** against a copy of `dev/capture/fixture`;
typed real text through Playwright; **killed pid 1614177 by exact pid**, started
pid **1673912** on the same port; reopened the same Chromium profile; read the
fields. :35110 (pid 1542866) was never touched. Both test pids killed by exact
pid; nothing left on 39897. Full `just test` not run.

---

## Headline

**The human was right.** Typed text in the **review-dock answer box**, the
**questions-page answer/note boxes**, and the **command composer** survives a
real `watch.py` process restart, a page reload, and a route change. The
coordinator's "restart can lose what he typed" caution was wrong for those
boxes.

**What is not durable:** `#askbox` (`/answers`) and the popout `#ptext`. Those
are the remaining *box* gaps. The design's IndexedDB / cross-tab / 30-day GC
work is still open as an *upgrade*, not as the acute feature.

**Storage shipped today: `localStorage`, not IndexedDB.**

---

## 1. Does typed text survive a `watch.py` process restart?

**Yes — for covered boxes.** Server-side state is irrelevant: drafts live in
the browser.

| Box | Survived kill+restart of watch.py? | Evidence |
|---|---|---|
| Review-dock answer (`#qdock textarea[id^="qi"]`) | **Yes** | After restart, box held `draftcheck-q: questions-page answer mid-thought` (last write to that question's key) |
| Command composer (`#cmdtext`) | **Yes** | After restart + reopen, box held `draftcheck-cmd: do-now half-typed composer thought` byte-identical |
| Questions-page `qi*` | **Yes** | After restart, first open card held the same restored draft |
| `#askbox` | **N/A — never stored** | Empty after restart (and never written during phase 1) |

Process evidence: pid **1614177** (`python3 watch.py --target /tmp/draftcheck-269/target --port 39897`) SIGTERM'd; port free; pid **1673912** served the same target; :35110 stayed pid **1542866** throughout.

**Why a server restart cannot wipe a stored draft:** keys are in origin
`localStorage`. A generation bump that triggers `location.reload()` still reloads
into the same origin and `restoreAnswerDrafts` / `restoreDraft` refill the boxes.
What a restart *can* lose is only text that was **never written** — which, for
covered boxes, is nothing after the first `input` event (no debounce window).

---

## 2. When is a draft written? Debounce?

**On every `input` event. No debounce.**

| Surface | Trigger | Debounce? | Lines |
|---|---|---|---|
| Answer / note (`textarea` id `qi[oa]\d+`) | delegated `document` `input` → `dwDraft.save(title, value)` | **None** | comment 4660–4661, 5448–5449; handler 5450–5458 |
| Composer `#cmdtext` | panel `input` → `saveDraft()` | **None** (comment: deliberately) | 6824–6828 |

Empirical: keys present in `localStorage` within ~200 ms of the last keystroke,
with no wait:

```
dw:adraft:/tmp/draftcheck-269/target:<question title> → {"t":"…"}
dw:draft:/tmp/draftcheck-269/target → {"t":"…","k":"add-idea"}
```

**Implication for the human's correction:** there is no "last few seconds" loss
window on covered boxes. "Durable" here means durable after the first character
reaches `input`, not "durable except a debounce tail."

Empty value removes the key (deleting his words is his act): answer path
4689–4691; composer 6526–6528.

---

## 3. Which boxes are covered?

| Box | Covered? | Key shape | Notes |
|---|---|---|---|
| Review-dock answer | **Yes** | `dw:adraft:<target>:<title>` | `#269` acute; landed `0366706` |
| Questions-page answer / note (`qi[oa]\d+`) | **Yes** | same | Same delegated handler + `restoreAnswerDrafts` on every `setContent` |
| Comment / follow-up path | **Yes** (same box) | same | Mode switches answer↔note in one textarea; send clears via `sendComment` 3571 |
| Command composer `#cmdtext` | **Yes** | `dw:draft:<target>` | `#163`; kind travels in payload |
| `/answers` `#askbox` | **No** | — | **FINDING** — typed text never appears in any `dw:*` key |
| Popout `#ptext` | **No** | — | **FINDING** — separate form; no `saveDraft` / `dwDraft` call |

Restore entry points for answer drafts: `restoreAnswerDrafts` 4717–4731, called
from review-dock `replaceWith` path 4781 and from `setContent` 4835 (every
navigate / non-review tick). Composer restore: `restoreDraft` 6539 on open
6838.

---

## 4. Reload, route change, re-render?

| Event | Covered boxes survive? | Evidence |
|---|---|---|
| Full page reload | **Yes** | Empirical phase 1: dock + composer after `goto` reload |
| Route change (`/review` → `/questions` → `/review`) | **Yes** | Empirical: dock refilled after round-trip |
| Live re-render (tick / `#qdock` `replaceWith`) | **Yes** | Code 4776–4781 + guard `dev/capture/reviewdraft.mjs` MODE 2 (node-tag identity); `#118` in-memory snapshot is the primary path, storage is backstop when memory is gone |
| Process restart | **Yes** | Empirical phase 2 (this doc §1) |

Comments claim all three (4662–4664, 4708–4716); behaviour matches.

---

## 5. What clears a draft? Failed send?

**Clears only on durable success** (and when he empties the box).

| Event | Answer/note (`dwDraft`) | Composer |
|---|---|---|
| Successful answer POST | `dwDraft.clear` after `res.ok` | — |
| Successful comment/note POST | `dwDraft.clear` after `res.ok` | — |
| Successful `/command` | — | `clearDraft()` after `r.ok` |
| Failed / rejected POST | **kept** (return before clear) | **kept** (no `clearDraft`) |
| Close / blur | **kept** | **kept** (panel lives outside `#view`) |
| Empty the box by hand | key removed (`value` falsy) | key removed |

Lines: answer clear 3523–3527 (failed path returns at 3523); comment 3567–3571;
composer 6908–6915 and 6531–6533.

Guards that already assert both directions: `dev/capture/reviewdraft.mjs`
(rejected keeps, success clears), `dev/capture/draft.mjs` (same for composer).
Not re-run here; policy is clear from production control flow.

Standing rule holds: a draft must not reappear as a thought he already sent;
a failed send must not erase it.

---

## 6. `localStorage` or IndexedDB?

**Shipped: `localStorage`.**

| Mechanism | Used for drafts today? | Lines |
|---|---|---|
| `localStorage` | **Yes** — both answer and composer | 4690–4691, 4698, 4704, 6526–6528, 6543, 6537 |
| IndexedDB | **No** for drafts | IDB helper exists ~2323+ for other UI state, not for `dw:adraft` / `dw:draft` |

`#269`'s design (and his C1/C2 answers at 01:12) specified **IndexedDB**,
cross-tab *offer-to-load* (not last-write-wins under focus), and **30-day GC**.
None of that is the shipped acute path. Remaining design value is the
**upgrade + uncovered boxes**, not inventing durability from zero.

---

## Per box × per event matrix

| | Type (`input`) | Reload | Route change | Tick re-render | Process restart | Failed send | Success send |
|---|---|---|---|---|---|---|---|
| Review dock answer | save | restore | restore | restore | restore | keep | clear |
| Questions `qi*` | save | restore | restore | restore | restore | keep | clear |
| Composer `#cmdtext` | save | restore on open | panel not rebuilt | n/a | restore on open | keep | clear |
| `#askbox` | **none** | empty | empty | empty | empty | n/a | n/a |
| Popout `#ptext` | **none** | empty | n/a | n/a | empty | n/a | n/a |

---

## Ledger correction for `#269`

**Status class: (b) partly shipped** — not "designed but not implemented," and
not fully satisfied.

| Piece | State |
|---|---|
| Acute: answer box survives reload / autoreload | **Shipped** `0366706` / merge `e383492`; `dwDraft` + `restoreAnswerDrafts` + `reviewdraft.mjs` |
| Composer durability | **Shipped** earlier as `#163`; same rules |
| Write on every input, no debounce | **Shipped** (both surfaces) |
| Clear only on durable success | **Shipped** |
| Process restart survival | **Shipped as a consequence of browser storage** (verified here) |
| `#askbox` / `#ptext` consumers | **Open** |
| Project-partitioned **IndexedDB** store, dual-read migration off localStorage | **Open** (design landed `e7d0b24`) |
| Cross-tab coherence (C1 = R1 offer-to-load) | **Open** (answered 01:12; not built) |
| 30-day idle GC (C2) | **Open** (answered 01:12; not built) |
| One deep `DraftStore` module every later field consumes | **Open** |

**What the open entry should say now (suggested wording for the coordinator):**

> `#269` — **partly shipped.** Acute localStorage durability is live for
> per-question answer/note boxes (`dw:adraft:<target>:<title>`, `0366706`) and
> the command composer (`dw:draft:<target>`, `#163`): save on every `input` with
> no debounce; restore after reload / route change / re-render; clear only on
> durable success. **Empirically survives a real `watch.py` process restart**
> (draftcheck 2026-07-29). Storage is **localStorage, not IndexedDB**. Still
> open: IndexedDB store + dual-read migration, cross-tab R1 offer, 30-day GC,
> deep module, and binding **`#askbox`** and **`#ptext`** (neither persists
> today). C1/C2 design answers are in; build grant is separate.

**Authorised remaining work:** not (a) entirely open, not (c) already
satisfied — **(b) the design remainder + two uncovered boxes**. Do not re-file
"drafts can be lost on restart" for the review dock or composer; that claim is
false.

---

## Discrepancies (comment vs behaviour)

None material on the acute path. Comments at 4649–4683 accurately describe
localStorage, no debounce, restore-after-render, clear-on-success. The only
ledger-level discrepancy was **task status**, not runtime behaviour: the open
entry still reads as if the feature were mostly unbuilt, while acute durability
has been live since `0366706`.

---

## Safety / hygiene

- :35110 never contacted; pid 1542866 still listening at end of run  
- Own servers: 1614177 then 1673912 on :39897, both killed by exact pid  
- No `pkill -f`; no heartbeat / monitors / `just deploy` / full `just test`  
- `attn` never used  
- Write surface: this file + `doc-map.md` row only  
