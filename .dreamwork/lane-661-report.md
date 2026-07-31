# Lane 661 report — derive the summary posture key list, don't restate it

**Branch:** `cx-661postkeys` · **Commits:** `1ca0d102`, `0e3cd231`
**Files touched (5):** `dev/capture/posturekeys.mjs` (new), `dev/capture/summaryjson.mjs`, `test_posturekeys.py` (new), `test_watch.py`, `lint.py`

---

## The defect, in one sentence

`dev/capture/summaryjson.mjs` restated the sorted `_summary_posture` key list as a literal; `#510` shipped orchestration without widening the literal, the guard stayed stale until `b9248b11` repaired it hours later in the 13:33 suite, and nothing kept the literal in step — so the next person to widen the projection re-arms the same trap until the browser guard happens to run.

## The fix, and which way I went

This is the `#596` family: a hand-maintained list kept in step with a source of truth by hand, with nothing to diff them. `#596`'s fix was to diff the route tables against the route set (the `table_keys` scan in `2d4bc243`); the analogous fix here is to derive the expected posture key set from `lint.POSTURE_AXES` (the closed-set source of truth every recognised posture axis must be listed in) plus `source`, and compare it against the served key set.

**The judgement call the brief asked for:** I went with **derive the expected set from `lint.POSTURE_AXES`** (the projection's *axis vocabulary* source) and compare against the **served** keys from `watch.summary()`. The two sides come from genuinely independent declarations — `_summary_posture`'s tuple in `watch.py` and `POSTURE_AXES` in `lint.py` — so the comparison is not a tautology. They agree because both were kept in step; the new check is what keeps them so. One shape across three surfaces (guard, pytest, extractor), not a second (#440 avoided).

### Three pieces

1. **`dev/capture/posturekeys.mjs`** (new library) — the extractor. Reads `POSTURE_AXES` out of `lint.py`, with a **cardinality precondition** (≥3 axes) so a broken parse — regex drifted, the tuple rewritten to a call, single-quoted names — throws rather than returning a silently-empty set (`#671`).
2. **`dev/capture/summaryjson.mjs`** — the browser guard's posture check now derives `EXPECTED_POSTURE` from the extractor instead of restating the literal, and **names a missing/unexpected key** in the failure (`notes.push('posture keys MISSING …')` / `… UNEXPECTED …`) rather than a bare "mismatch".
3. **`test_watch.py`** — a pytest invariant (`test_summary_posture_keys_match_posture_axes_plus_source`) that derives the served keys from `watch.summary()` and the expected keys from `lint.POSTURE_AXES`, asserting both the equality *and* its preconditions (POSTURE_AXES ≥3, `source` not an axis). **This is the binding check — it runs every `just test`, unlike the browser guard.**
4. **`test_posturekeys.py`** (new) — node-level exercise of the extractor against real `lint.py`, a widened fixture, and three malformed inputs that must throw. A **partial answer to `#651`** (nothing checks that a guard's own extractor is honest): it pins the extractor the guard depends on, not the guard's wiring of it.
5. **`lint.py`** — registered `posturekeys` in `NOT_GUARDS` (it's a shared library like `outdir`/`serve`/`dom`, not a guard), restoring the census to "85 guard(s) registered, each with a file".

### What `#596`'s shape I copied actually was

The `2d4bc243` review commit turned `table_keys` from a regex into a **depth-1 scan that skips comments and strings and fails loud on desync**, so a genuinely missing route can't read green via a `//` comment or a template string. The lesson I'm carrying from it: **the header's claim-list is not the assertion-list** (`lessons.md:3280`) — I read the guard's `ok()` calls, not its header. The old posture check's header said "posture carries only the five axes + source"; the assertion was a `JSON.stringify` equality against a literal — and the literal was the thing that drifted.

## Red-proof, both directions

### Direction 1 — the defect reproduced, then caught

`python3 dev/redproof.py begin watch.py` → injected: added `"focus"` to `_summary_posture`'s tuple in `watch.py` (widening the *projection* without widening `POSTURE_AXES` — the exact `#510` trap). Ran the new pytest invariant:

```
FAILED test_watch.py::TestPosture::test_summary_posture_keys_match_posture_axes_plus_source
- AssertionError: Lists differ:
-   ['asking', 'delegation', 'delivery', 'focus', 'orchestration', 'pace', 'source']
- != ['asking', 'delegation', 'delivery', 'orchestration', 'pace', 'source']
- First differing element 3: 'focus' / 'orchestration'
- summary posture keys drifted from POSTURE_AXES+source — the projection
- (_summary_posture) and the closed set (lint.POSTURE_AXES) must widen together.
```

The discriminating message **names the key** (`focus`), not just "mismatch" — as the brief required. Restored by `python3 dev/redproof.py restore watch.py` (recorded injection sha `af82f2e164d7`, restored & verified byte-identical). The pre-existing `test_collect_and_summary_expose_orchestration` also failed on the same injection (it reads `summary(d)["posture"]["orchestration"]`, unaffected, but the invariant is the new binding check).

### Direction 2 — the tautology trap (the real work of this task)

The brief's sharpest warning: a guard that derives *both sides* of its comparison from the same source asserts nothing. I constructed it and confirmed it reads green while wrong:

```
// If EXPECTED were derived from _summary_posture's OWN tuple (the projection source):
TAUTOLOGY guard (derive both from projection): GREEN (WRONG — orchestration missing, not flagged)
REAL guard (expected from POSTURE_AXES):       RED (caught missing orchestration)
```

My design derives the two sides from **independent** sources — served keys from `watch.summary()` (which calls `_summary_posture`), expected keys from `lint.POSTURE_AXES` (a separately-maintained closed set) — so it is not a tautology. The two other direction-2 vectors the brief named:
- **A key present but carrying a wrong value** — my check is a key-*set* check and would not catch e.g. `orchestration: null`. The existing `test_collect_and_summary_expose_orchestration` covers the value for orchestration specifically; a general value-level invariant is out of scope here.
- **A key added to the projection but never plumbed to the page** — the browser guard reads the *served* key set (`Object.keys(summary.posture)`), so a projection key that never reaches the page is caught as MISSING (the guard and the pytest both read the served side, not the projection source).

## Verification — quoted verbatim

**`redproof.py check` (hand-off gate):**
```
history: examined 2 commit(s) since f1f588b73d9b (master) against 1 injected path(s); read 2 blob(s), 0 holding a recorded injection.
check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits:
  watch.py (sha af82f2e164d7, hint: '"focus", "source")}')
```

**`node --check`:** both `summaryjson.mjs` and `posturekeys.mjs` — OK.

**`pytest test_posturekeys.py`:** `3 passed in 1.91s`.

**`pytest test_watch.py -k "summary or posture"`:** `66 passed, 424 deselected in 8.89s`.

**`pytest test_lint.py`:** `535 passed` (after the `NOT_GUARDS` registration; was 1 fail before it).

**`python3 lint.py` (worktree bar):**
```
…
  OK    justfile         85 guard(s) registered, each with a file
  OK    justfile         guard runner compares executed vs registered and fails on a gap
…
clean (6 warning(s))
```
6 warnings — the worktree bar (`#611`); no ERRORs. The main checkout's 2-warning bar is unreachable here (`#756`, the `briefs/boilerplate.md` lane is live).

### The browser guard was NOT run against a live browser

`#666`: browser guards return a WRONG answer under load, and the coordinator is running pytest suites right now. **I did not bind any port and did not run the browser suite.** My evidence is the node-level extractor exercise (`test_posturekeys.py`), the derived-guard logic simulation, and the pytest invariant. **A coordinator browser-suite run of `summaryjson` is owed** — the guard's own wiring (deriving `EXPECTED_POSTURE` and comparing against the served keys) is verified by `node --check` + logic, not by a live fetch.

## What this guard would still miss

The honest answer the brief asked for:
1. **Wrong values, not wrong keys** — a key-set check says nothing about values. `orchestration: null` would pass. (Partially covered by the orchestration-specific value test; not generally.)
2. **The browser guard still has to run** — deriving makes it self-updating so it's correct *whenever* it runs, but if the browser suite never runs, neither does the guard. The pytest invariant is what makes this check run on every `just test`; the guard is defense-in-depth for the served shape.
3. **A drift between the extractor's regex and `POSTURE_AXES`'s actual form** — if someone reformats `POSTURE_AXES` across lines with a `)` inside a string (unlikely but possible), `[^)]*` spans wrong. The cardinality precondition (≥3) catches a total break; a partial one is not covered. `#651` remains open: this pins the *extractor*, not every guard's extractor.

## DOGFOOD REPORT

Friction with this brief and the loop:

- **The brief's direction-1 framing was slightly off, and catching that was the value of running it.** The brief implied the OLD guard stayed *green* on a widened projection. It would not have — a literal compared against a widened served set goes RED. The actual `#510`/`b9248b11` defect was that the literal *lagged* (had 4 axes, projection had 5) and the guard **wasn't run during the window**, so the lag was invisible until the 13:33 suite. The fix (deriving) helps because the guard is correct whenever it runs — no literal to forget to update. I demonstrated this honestly rather than performing a misleading "old guard green" show; the real proof is "new check red, naming the key, on the same input."
- **`redproof.py` is good and I'd use it again, but `forget` for an unused begin is friction.** I `begin`-ed the guard file intending to inject the old-literal shape in-place, then realised a logic simulation was cleaner than reverting-and-reapplying a 5-line block. I had to `forget` the unused begin. A `begin` that's never restored or forgotten leaves an armed entry that `check` refuses on — correct behaviour, but a lane could trip on it. (Not a bug; just a thing to know.)
- **`test_lint.py` catching the unregistered library was the most useful single test.** I added `posturekeys.mjs` to `dev/capture/` and the guards-registered census immediately flagged it as an unregistered guard. This is exactly the "registration is not execution" discipline working. The fix (add to `NOT_GUARDS` with a reason) took one edit. No friction — praise.
- **The 6-warning worktree lint bar (`#611`) is well-documented and the brief stated it correctly.** No surprise there.
- **One small brief nit:** the brief says "read the guard's assertions, not its header comment — `lessons.md:3280`". The line number is right and the lesson is exactly on point, but the lesson is filed under a different heading than I expected to grep for; `python3 dev/lessons_index.py --act red-proof` did *not* surface it (it's a `#505` lesson, not a red-proof one). I found it by line number as the brief said. The lessons index by-act slicing is useful but incomplete — a cross-cutting lesson like "header ≠ assertion" lives under the act that *found* it, not the acts that *need* it.
