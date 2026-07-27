# Dashboard figure audit — 2026-07-28 ~08:30 AEST

**Task:** #392 adjacent measurement (brief `.dreamwork/docs/briefs/392-adj-figure-audit.md`).  
**Target:** live dashboard `http://127.0.0.1:35110` (GET only).  
**Rule:** every expected value is from outside `watch.py` (ledger files, `git`, `pgrep`, wall clock, `ls`). Commands are quoted per row.  
**Seams:** **P** = payload (`/data.json`) vs independent truth · **R** = render (pixels/DOM) vs payload.

**Clock at primary capture:** `date` → `Tue 28 Jul 2026 08:28–08:30 AEST` · `date +%s` ≈ `17851912xx` · UTC was still 2026-07-27 evening.

**Screenshots (this directory):**

| File | Viewport | Route |
|------|----------|-------|
| `2026-07-28-0830-home-1280x900.png` | 1280×900 | `/` |
| `2026-07-28-0830-home-420x900.png` | 420×900 | `/` |
| `2026-07-28-0830-home-1280x900-full.png` | 1280×900 full-page | `/` (burndown + status) |
| `2026-07-28-0830-questions-1280x900.png` | 1280×900 | `/questions` |
| `2026-07-28-0830-questions-420x900.png` | 420×900 | `/questions` |
| `2026-07-28-0830-answers-1280x900.png` | 1280×900 | `/answers` |
| `2026-07-28-0830-answers-420x900.png` | 420×900 | `/answers` |

Playwright import path: `/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs`.

---

## Verdict in one paragraph

**#392 is confirmed live and is a class, not one row.** Every open and answered question age on `/questions` is driven by a **date-only** headline; the client sets `data-ct` to **local midnight** and paints minute- or hour-scale ages (`08h 28m ago`, `03d 08h ago`, …). Independently, open question #367 was first committed at **2026-07-28 07:54:32 +1000** (`git log --reverse -S…`), so at ~08:28 it should read on the order of **~34m**, not **08h 28m**. The same midnight `data-ct` appears on **all 38** `.qage` nodes on the page. **Burndown final open (126)** agrees with the live queue; **mid-series open is +1 high for four consecutive 4h buckets** (reproduced by two counting routes). **Arrived/landed bucket series** does not match a simple open-set diff over `git log` of `tasks.md` — either a different event definition or a second defect; I did not finish a third derivation. Commit ages that carry real git epochs are fine. Counts (open questions, answers, dreams, reviews, queue) are fine.

**Figures checked: 42 · Correct: 28 · Disagree: 10 · Uncertain / incomplete: 4**  
(Open-question `ct` rows are three of the disagrees; the other 35 question ages on the page are the same class and are counted as one class finding plus three mandatory open rows, not 38 separate bugs.)

---

## How question ages are produced (context only — not an expected-value source)

Served HTML (GET `/`) builds the age node from the title date:

```text
const ct = Math.floor(new Date(Y, Mo - 1, D).getTime() / 1000);
// → <span class="age qage" data-ct="${ct}">
```

`/data.json` `questions_open[]` entries have **no `ct` field** — only `title` with `P2 · YYYY-MM-DD — …`. So the payload carries date precision; the page claims sub-day precision. That is the #392 gap between seams.

---

## Table — timestamps first

| # | Figure (where) | Seam | Page / payload shows | Independent expected | Command(s) | Result |
|---|-------------|------|----------------------|----------------------|------------|--------|
| 1 | Open Q #367 age + `data-ct` (`/questions`) | R (+ implied P) | DOM: `08h 28m ago`, `data-ct=1785160800` (screenshot `…-questions-1280x900.png`) | **True filing ≈ 07:54:32 → ~34m at capture**, not ~8h28m. Midnight of 2026-07-28 is `1785160800` and matches the bug. | **Route A:** `git log --reverse --format='%H %ci %ct' -S '#367: what do 5–7 marks become below the cliff' -- .dreamwork/questions.md` → first `d2778ee … 2026-07-28 07:54:32 +1000 1785189272`. **Route B:** `python3 -c "import time; print(int(time.mktime((2026,7,28,0,0,0,-1,-1,-1))))"` → `1785160800` (= page `data-ct`). Age from true ct: `(date+%s - 1785189272)` ≈ 2080s ≈ 34m. | **DISAGREE** (known #392 class) |
| 2 | Open Q “answer reach another machine” age + `data-ct` | R | `03d 08h ago`, `data-ct=1784901600` (midnight 2026-07-25) | Source headline **date-only** `2026-07-25`. True first commit **2026-07-25 12:22:04 +1000** → age style would be **`02d 20h`** at ~08:29, not `03d 08h`. | **Route A:** `git log --reverse --format='%ci %ct' -S 'how should an answer reach a loop on another machine' -- .dreamwork/questions.md` → `2026-07-25 12:22:04 +1000 1784946124`. **Route B:** `rg -n 'how should an answer reach' .dreamwork/questions.md` → headline `P2 · 2026-07-25 —` (no time). Midnight: `time.mktime((2026,7,25,0,0,0,…))` = `1784901600`. | **DISAGREE** |
| 3 | Open Q #275 age + `data-ct` | R | `01d 08h ago`, `data-ct=1785074400` (midnight 2026-07-27) | Headline **date-only** `2026-07-27`. Git first hit for the phrase is **2026-07-26 17:54:58** (title later reworked to 07-27). Either way, midnight-of-headline is not a filing time. | **Route A:** `git log --reverse --format='%ci %ct' -S '#275 public Dreamhub auth' -- .dreamwork/questions.md` → oldest `2026-07-26 17:54:58 +1000 1785052498`. **Route B:** open headline via `rg -n 'P2 · 2026-07-27 — #275' .dreamwork/questions.md` (date only; title wraps one line). | **DISAGREE** (date-only → fine age) |
| 4 | Source precision of all three open headlines | P | Payload titles: `P2 · 2026-07-28|25|27 — …` (no times); no `ct` keys | All three are **date-only** in `questions.md` | `awk '/^## Open$/{p=1;next} /^## /{p=0} p && /^- \\*\\*/{print}' .dreamwork/questions.md \| head` and `python3` parse of `## Open` for `\d{4}-\d{2}-\d{2}` with optional time → time absent on all three. | **CORRECT about source; defect is rendering precision** |
| 5 | Answered-list ages on `/questions` (class sibling) | R | **35** other `.qage` nodes; every one uses midnight `data-ct` for its date (`1785160800` / `1785074400` / `1784988000` / `1784901600`); text always ends in **`08h`** on multi-day ages or **`08h NNm`** on same-day (screenshot DOM extract: 38 total qages) | Answered headlines in `questions.md` are almost all **date-only** (35 date-only, 3 with time in a different part of the line, 11 with no date). Painting `Xh Ym` from midnight is the same class as #392. | **Route A:** Playwright extract of all `[data-ct].qage` on `/questions`. **Route B:** `python3` count of answered headlines matching date-only vs datetime in `.dreamwork/questions.md` `## Answered`. | **DISAGREE (class)** — evidence: `…-questions-1280x900.png` + DOM dump |
| 6 | Commit ages on `/` (first 5) | R + P | e.g. `00m 11s ago` … `06m 21s ago` with `data-ct` = payload `git[].t` | `git log -5 --format='%h %ct %s'` timestamps **match** payload `git[].t` exactly; rendered age ≈ `now - t` | `curl -s http://127.0.0.1:35110/data.json \| python3 -c '…print git…'` and `git log -5 --format='%h %ct %s'`; DOM `data-ct` on `.cage` | **CORRECT** |
| 7 | Dream age `1h old` | P + R | payload `dreams[0].age='1h'`, `mtime=1785185987.3…`; page `…1h old` | `stat` mtime same; wall age ~1.49h at 08:29 → single-unit `1h` is coarse but not the midnight bug | `stat -c '%Y %y' .dreamwork/dreams/2026-07-28-0658-essential-marks-inc1.md` and payload field | **CORRECT** (coarse unit; input is a real mtime) |
| 8 | Review `367-strip-below-cliff.html` age ~34–36m | R | page `34m old` / later `36m old` | `stat` mtime `2026-07-28 07:53` → ~35–37m at capture | `stat -c '%y' .dreamwork/review/367-strip-below-cliff.html` | **CORRECT** (mtime-based, fine enough) |
| 9 | `status.last_tick` age on home (`tick 17m old`) | R + P | payload `last_tick: 2026-07-28 08:13`; page `tick 17m old` at ~08:30 | `(now - mktime(08:13))/60 ≈ 17.6` | `python3 -c "… mktime 2026-07-28 08:13 …"`; also `jq .last_tick .dreamwork/status.json` | **CORRECT** |
| 10 | `generated` freshness | P | e.g. `2026-07-28 08:30:11` | matches `date` at fetch within the same second | `curl -s …/data.json \| jq .generated` && `date '+%Y-%m-%d %H:%M:%S'` | **CORRECT** |

### Open-question `ct` summary (required)

| Question | Source carries | Payload `ct` | Client `data-ct` | Rendered age (~08:28) | Independent true anchor |
|----------|----------------|--------------|------------------|-----------------------|-------------------------|
| #367 cliff | **date only** `2026-07-28` | *(absent)* | midnight `1785160800` | `08h 28m ago` | git first commit **07:54:32** |
| answer→other machine | **date only** `2026-07-25` | *(absent)* | midnight `1784901600` | `03d 08h ago` | git first **12:22:04** on 07-25 |
| #275 auth | **date only** `2026-07-27` | *(absent)* | midnight `1785074400` | `01d 08h ago` | git phrase first **07-26 17:54** / headline date 07-27 |

---

## Table — burndown

| # | Figure | Seam | Page / payload | Independent expected | Command(s) | Result |
|---|--------|------|----------------|----------------------|------------|--------|
| 11 | `burndown.open` | P | `126` | open task bullets under `## Open` = **126** | **Route A:** `python3` count `^- \*\*#(\d+)\*\*` in `## Open` of `.dreamwork/tasks.md`. **Route B:** `awk '/^## Open$/{p=1;next} /^## /{p=0} p && /^- \*\*#[0-9]+\*\*/{c++} END{print c+0}' .dreamwork/tasks.md` | **CORRECT** |
| 12 | `burndown.open` vs queue | P | open 126; queue `{2,124}` | `2+124=126` | `jq '.status.queue' <(curl -s …/data.json)` and same from `.dreamwork/status.json` | **CORRECT** |
| 13 | Last bucket `open` | P | last bucket `open: 126` | same 126 | `jq '.burndown.buckets[-1].open'` | **CORRECT** |
| 14 | `burndown.step` | P + R | `14400`; page copy `every four hours` | 14400s = 4h | `jq .burndown.step`; `python3 -c 'print(14400/3600)'` | **CORRECT** |
| 15 | Bucket count | P | **19** buckets | window `to-from=259380…` / 14400 ≈ 18.01 → **19** left edges including the current partial bucket | `jq '.burndown.buckets\|length'`; `python3` on from/to/step | **CORRECT** (brief said “18”; live is 19 including the live partial) |
| 16 | Mid-series open stock (bucket t0=1785046984, 07-26 16:23) | P | payload `open: 110` | last `tasks.md` commit at/before bucket end (`4282a1f` @ 20:20) has **109** open bullets | **Route A:** `git log --format='%H %ct' -- .dreamwork/tasks.md` then `git show 4282a1f:.dreamwork/tasks.md` + awk open count → **109**. **Route B:** same snap written to `/tmp/tasks-snap.md`, re-count with python `^- \*\*#N\*\*` → **109**. | **DISAGREE (+1 payload)** |
| 17 | Mid-series open stock (t0=1785061384, 1785075784, 1785090184) | P | 108, 109, 109 | independent open counts 107, 108, 108 (always payload = independent + 1) | same dual-route as #16 at each bucket end commit | **DISAGREE (+1 for four buckets)** then re-agrees at t0=1785104584 (`open: 104` both sides) |
| 18 | `burndown.arrived` / `landed` totals | P | 302 / 157; page `302 arrived · 157 landed` | open-set diff over consecutive `git log` commits on `tasks.md` does **not** reproduce per-bucket arrived/landed (many buckets differ by several events; first bucket 63/20 vs ind 52/32) | **Route A:** event reconstruction (id set diff oldest→newest, bucket by commit ct). **Route B:** sum of payload buckets equals payload totals (302/157) — internal consistency only, not independent. | **UNCERTAIN / mismatch** — open stock end is right; event series not independently reproduced. Not confident of the production event definition. |
| 19 | Burndown render vs payload | R | full-page shot: `126 open · 302 arrived · 157 landed · every four hours`; provenance line `human 91 · loop 83 · historical unknown 126` | matches payload fields `open/arrived/landed/step` and `provenance` | visual `…-home-1280x900-full.png` vs `jq .burndown` | **CORRECT (render=payload)** |
| 20 | Provenance totals vs `origin:` tags | P | human 91, loop 83, unknown 126, total 300 | whole-file `origin:**…**` counts only **human 71, loop 83, unknown 11** (sum 165) | `rg -o 'origin: \*\*[^*]+\*\*' .dreamwork/tasks.md \| sort \| uniq -c` | **UNCERTAIN** — not the same statistic as origin tags; likely first-sighting classification over git history. Did not finish an independent first-sighting count. |

---

## Table — counts and anchors

| # | Figure | Seam | Page / payload | Independent expected | Command(s) | Result |
|---|--------|------|----------------|----------------------|------------|--------|
| 21 | `open_questions` / `questions_open` length | P + R | 3; meta `3 open questions`; `OPEN (3)` | 3 open bullets under `## Open` | `awk … Open … /^- \*\*/` on `.dreamwork/questions.md`; page screenshots | **CORRECT** |
| 22 | `answered_entries` length | P | 49 | 49 answered bullets | same awk on `## Answered` of `questions.md` | **CORRECT** |
| 23 | `answers_open` | P + R | `[]` / `OPEN (0)` / `none awaiting the dreamer` | Open section empty | `awk` on `.dreamwork/answers.md` `## Open` → 0 non-empty lines | **CORRECT** |
| 24 | `answers_answered` | P + R | 6; `ANSWERED (6)` | 6 bullets under `## Answered` | awk / visual answers screenshots | **CORRECT** |
| 25 | `dreams` / `dreams_archive` | P + R | 1 / 35 | `ls` 1 active md, 35 archive md | `ls .dreamwork/dreams/*.md \| wc -l`; `ls .dreamwork/dreams/archive/*.md \| wc -l` | **CORRECT** |
| 26 | `reviews` | P + R | 18 | 18 `*.html` in review dir | `ls .dreamwork/review/*.html \| wc -l` | **CORRECT** |
| 27 | `status.queue` | P + R | in_progress 2, pending 124; page `2 in flight · 124 pending` | same in `.dreamwork/status.json`; sum 126 = open tasks | `jq .queue .dreamwork/status.json`; open count above | **CORRECT** (known-good anchor holds) |
| 28 | `status.current_task_ids` | P | `[367, 381]` | both under `## Open` | `rg -n '^\- \*\*#367\*\*\|^\- \*\*#381\*\*' .dreamwork/tasks.md`; `jq .current_task_ids .dreamwork/status.json` | **CORRECT** (known-good anchor holds) |
| 29 | `status.deployed.pid` live | P | `1264649` | live `python3 …watch.py --target …ud-dreamwork --dev` on 35110 | **Route A:** `pgrep -af 'watch.py'`. **Route B:** `ss -ltnp \| rg 35110` → pid 1264649; `os.kill(1264649,0)` | **CORRECT** (known-good anchor holds) |
| 30 | `status.awaiting_human` length vs open questions | P + R | list length **4**; page `4 AWAITING YOU` | status list has 4 strings (#367, #371/#263 Q2, #275, other-machine). **Not** the same as open_questions=3 | `jq '.status.awaiting_human\|length'`; compare to open_questions | **CORRECT as two different figures** (easy to misread as a count bug) |
| 31 | `run_mode` | P + R | `hot`; page RUN MODE hot selected | file `.dreamwork/run-mode` is `hot` | `cat .dreamwork/run-mode` | **CORRECT** |
| 32 | `deployed.rev` (top-level) vs HEAD | P | tracks HEAD short (moved during audit: `06bce76`→`53dae04`→`933e78a`) | `git rev-parse --short HEAD` | not a defect per brief (ledger commits) | **CORRECT / expected** |
| 33 | `git[]` subjects/shas | P | 5 recent commits | match `git log -5` | `git log -5 --format='%h %s'` | **CORRECT** |
| 34 | Answers page ages | R | **no** age nodes (`ages: 0` in extract); titles show date in text only | payload `when` is often a **datetime** (`2026-07-27 11:32`) — coarser display, not false fine precision | Playwright on `/answers`; `jq '.answers_answered[].when'` | **No #392 sibling here** (also no independent age to audit) |
| 35 | Home meta “3 open questions” | R | `3 open questions` | matches payload + ledger | screenshots + counts above | **CORRECT** |
| 36 | Questions 420px | R | `OPEN (3)` and `08h 28m ago` still visible; no clip of the age | same defect as desktop, not a layout truncation of the number | `…-questions-420x900.png` | **layout OK; age still wrong** |

---

## Disagreements — both routes (acceptance criterion 4)

### D1 — Question ages from midnight (class #392) — **CONFIRMED LIVE**

1. **Route A (git first introduction):** open #367 first appears in commit `d2778ee` at **2026-07-28 07:54:32 +1000** (`1785189272`). At wall ~08:28 that is **~34 minutes**, not eight hours.
2. **Route B (source format + midnight math):** headline is `P2 · 2026-07-28 — …` with **no time**; `time.mktime((2026,7,28,0,0,0,…))` = **`1785160800`**, identical to the page’s `data-ct`. Age-from-midnight at the same wall clock is **`08h 28m`**, identical to the painted string.

Same pair of routes applied to the other two open questions (table rows 2–3). Screenshot evidence: `2026-07-28-0830-questions-1280x900.png`, `…-420x900.png`.

**Sibling:** every answered question age on the same page uses the same midnight `data-ct` pattern (38 `.qage` nodes). Systematic tell: multi-day ages all end in **`08h`** at ~08:28 local.

### D2 — Burndown mid-series open stock +1

1. **Route A:** for bucket ending ~07-26 20:23, last touching commit `4282a1f`; `awk` open-section count → **109**.
2. **Route B:** python `^- \*\*#(\d+)\*\*` on the same `git show` blob → **109**.
3. Payload: **110**. Four consecutive buckets show payload = independent + 1; later buckets re-agree (including final 126).

### D3 — Burndown arrived/landed series (definition gap or defect)

1. **Route A:** consecutive open-id set diffs bucketed by commit time disagree with payload `arrived`/`landed` on most buckets.
2. **Route B:** not completed with an alternate event definition (e.g. first-ever id appearance including Recently landed transitions). **Internal** sum of buckets matches payload totals, which only proves self-consistency.

**I am not confident** this is a user-visible bug versus a different (legitimate) arrival definition. Final open stock is trustworthy; event bars may not be.

---

## Known-good anchors (method check)

| Anchor | Result |
|--------|--------|
| queue `{2,124}` and open 126 | **Holds** — both routes |
| `current_task_ids` `[367, 381]` under Open | **Holds** |
| `deployed.pid` `1264649` live watch.py | **Holds** |

If these had failed, the method would be wrong. They did not.

---

## Correct figures (evidence the audit looked)

28 figures measured as **CORRECT**, including: open/answered/answers/dreams/reviews list lengths; queue and current task ids; live pid; commit shas/timestamps and their rendered ages; dream mtime age band; review mtime age band; last_tick age; generated freshness; burndown final open, step, bucket cardinality, and render=payload for the summary line; run_mode; top-level deployed.rev tracking HEAD (allowed).

---

## What I did not reach / not confident about

- Full independent reconstruction of burndown **arrived/landed** and **provenance** (human/loop/unknown) from git first-sightings.
- Whether mid-series open +1 is a counting bug in production or a transient historical format my two counters both miss the same way (both counters agree with each other, which argues against a fluke, but I did not invent a third definition).
- Per-answer `when` datetime accuracy vs submission logs (answers page does not humanize them).
- `linkable_paths` (384) — no quick independent definition without reading production path walkers (would risk circularity).
- Status “4 AWAITING YOU” composition beyond confirming it is `awaiting_human` (4) ≠ `open_questions` (3).

---

## Visual notes (pixels)

- **#392 visible on first open card** at both 1280 and 420: `08h 28m ago` next to today’s date (`…-questions-*.png`).
- Home burndown summary and chart present below the fold (`…-home-1280x900-full.png`); summary numbers match payload.
- Answers page shows `OPEN (0)` as the word **none**, not a blank hole where a number belongs — acceptable.
- No truncated/clipped counts at 420 on the surfaces checked; the false age is fully readable at narrow width (bad number, good layout).

---

## Method hygiene

- Did **not** import or call `watch.py` for expected values.
- Did **not** POST, deploy, pkill, or run `just guards`.
- Files written: this report + PNGs in `.dreamwork/docs/measurements/` only.

---

## Suggested fix shape (finding only — not implemented)

Already framed in #392: date-only sources must not claim minute precision. Either record a real time, derive from the introducing commit, or paint a day-scale age that does not imply `08h 28m` confidence. The red must compare against an **external** filing time, not “two ages differ.”
