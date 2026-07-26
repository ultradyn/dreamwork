# #271 · Cross-browser note propagation (read-only diagnosis)

**Date:** 2026-07-26  
**Agent:** grok-sugar-vesi-x6tv  
**Authority:** diagnosis only — no source fix  
**Status:** diagnosis supported by fixture repro

## Symptom (human)

Two browsers open the same Dreamwork dashboard. A note posted in one does not appear promptly in the other; a later full refresh shows it.

## Live-update path (source)

| Step | Seam | Location |
|------|------|----------|
| 1 | Client `setTimeout(tick, 2000)` | `watch.py` PAGE JS `tick()` |
| 2 | `GET /mtime` → `"<GENERATION> <watched_mtime>"` | `do_GET` `/mtime`; `watched_mtime(target)` walks `DREAMWORK.md`, `.git/logs/HEAD`, all of `.dreamwork/` (files **and** dirs) |
| 3 | If generation changed → `location.reload()` | new server process |
| 4 | If mtime string changed and `Date.now() >= holdRerenderUntil` → `GET /data.json` → `setData` | `collect(target)` re-reads `questions.md` |
| 5 | Re-render **only** for some views | `if (dashboard) setContent(buildDashboard)`; `else if (questions) …`; `else if (answers) …` — **no `review` or `file` branch** |
| 6 | Note write | `POST /comment` → `append_comment` → rewrite `.dreamwork/questions.md` under `ANSWER_LOCK` |

Sender-side only: `holdRerenderUntil = Date.now() + 1600` after local morph (`sendComment` / `sendAnswer`). Does not affect other browsers.

`_send` sets `Content-Type` + `Content-Length` only — **no** `Cache-Control`, `ETag`, or `Last-Modified`.

## Fixture setup (disposable; not live 35110/35111)

- Target: `/tmp/dreamwork-271-fixture` (one open question, probe review artifact)
- Server: `python3 watch.py --target /tmp/dreamwork-271-fixture --port 39950` (pid ~403702)
- Repro script: `/tmp/dreamwork-271-repro.mjs`
- Evidence: `/tmp/dreamwork-271-evidence/results.json` (+ screenshots)

## Browser processes

Two separate Playwright `chromium.launch()` calls (`distinctLaunch=true`). API `browser.process()` unavailable in this Playwright build (pid fields null). Observed two distinct headless_shell zygote trees during the run, e.g.:

- zygote ppid chain under chrome-headless-shell pid **442788**
- zygote ppid chain under chrome-headless-shell pid **442845**

Browser A: posts note via `fetch('/comment')` on `/questions`.  
Browser B: long-lived `/questions` page **and** long-lived `/review?p=probe.html&q=<title>` dock.

## Timeline (wall clock)

| Event | Result |
|-------|--------|
| POST A | `200` `{"ok": true}` in ~197ms |
| Server `data.json` | `follows=1`, text `cross-browser note marker 1785057268633` |
| `/mtime` | mtime field advanced (`…7238…` → `…7273…`); generation stable |
| B `/questions` DOM | note visible at **+0.821s** |
| B `/review` `#qdock` live | **never** within ~10s of samples every 0.5s |
| B `/review` network during wait | **5× `/mtime` (200)**, **1× `/data.json` (200)** — poll and data fetch both happened |
| B `/review` hard reload | note **visible** |
| Cache headers on GET | `cache-control` / `etag` / `last-modified` all **null** for `/mtime`, `/data.json`, `/` |

## Ranked falsifiable hypotheses

| Rank | Hypothesis | Prediction | Verdict |
|------|------------|------------|---------|
| **H1** | **`tick()` does not re-render `/review` dock after `setData`** | Review page fetches new `/data.json` but `#qdock` stays stale until reload; `/questions` updates within one poll | **CONFIRMED** |
| H2 | Pure ≤2s poll lag | Both routes show note within ~2–3s | **REFUTED** for review (questions yes; review never live) |
| H3 | HTTP cache of `/mtime` or `/data.json` | No `/data.json` after post, or stale body | **REFUTED** (fresh 200 `/data.json` on review; questions used same payload successfully) |
| H4 | `watched_mtime` / fs timestamp does not move on note write | `/mtime` unchanged | **REFUTED** (mtime advanced) |
| H5 | Server write/generation split or wrong process | POST ok but `/data.json` lacks follow | **REFUTED** |
| H6 | Sender `holdRerenderUntil` blocks other browser | B delayed ~1.6s then updates | **REFUTED** (local only; B questions at 0.8s) |
| H7 | Coarse fs timestamps hide rapid sequential writes | Second write invisible until unrelated touch | **Not needed** for this symptom; not observed |

## Smallest candidate seam (fix later — not done here)

**Client `tick()` re-render switch** in `watch.py` PAGE JS (~3460–3462):

```js
if (view.name === 'dashboard') setContent(buildDashboard(data));
else if (view.name === 'questions') setContent(buildQuestions(data));
else if (view.name === 'answers') setContent(buildAnswers(data));
// missing: review (and file if live file content should track disk)
```

`buildReview` already builds the dock from `d.questions_open` (`buildReview` ~1975–1988). Data is loaded; DOM is not rebuilt on tick for that route.

Minimal fix shape (for a later implementer): after `setData`, also rebuild review via `setContent(await buildCurrent())` or an explicit `buildReview` + dock-preserving restore (iframe `src` / focus / compose text — same `#118` discipline as cards). Prefer reusing `buildCurrent` so file/review stay aligned with navigate.

## Distinction: lag vs bug vs design

| Observation | Classification |
|-------------|----------------|
| Cross-browser note on `/questions` in ~0.8–2s | **Design / expected poll lag** |
| Cross-browser note on `/review` dock never until full reload, despite successful `/data.json` fetch | **Bug** (incomplete tick re-render matrix) |
| Missing cache headers | **Hardening gap**, not root cause of this repro |

Human path that matches the bug: review dock (`/review?p=…&q=…`) open in second browser — exactly the #229 review workflow surface.

## Secondary notes

- Dashboard first-paint probe did not surface the marker string in `document.body.innerText` in this fixture (likely collapsed / summary-only card chrome). Not used as primary evidence; `/questions` and server JSON are definitive.
- No Cache-Control is still worth a later tiny harden (`no-store` on `/mtime` and `/data.json`) so heuristic caches cannot invent a cousin of this bug.
- Live 35110/35111 were not touched; fixture only.

## Recommended red-first guard (later)

Two Playwright browser processes, fixture server, B on `/review?p=…&q=…`, A `POST /comment`, assert within 3s that `#qdock` text contains marker **without** reload. Current code must go **red**. Pair with `/questions` control that goes green within 3s.

## Conclusion

**Diagnosis:** Not multi-process watch confusion, not mtime granularity, not poll period alone. The live tick **does** discover the note (mtime + `/data.json`) on the review route, but **does not call `setContent` for `view.name === 'review'`**, so the dock stays frozen until hard refresh. That is the smallest seam and matches the human “later refresh shows it” report.

No source changes made under this grant.
