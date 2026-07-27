# #367 — two-line tab geometry (measurement for increment 2)

**Status:** measurement only. Nothing is built. Increment 2's builder starts from
these numbers rather than a hope.

**Date:** 2026-07-28  
**Why owed:** M3 (2026-07-28 05:35) overrode one-line ~12-character builder
truncation in favour of **two-line tabs at a smaller text size, up to ~6 words,
nobody truncates.** Every prior geometry number (613.5px `.read`, 506px slack at
1280, 16px outside gutter, rail/strip cliff at ~780) was measured against a
**one-line** tab. A two-line tab is taller and possibly wider. This document is
the re-measure.

**Reproduce:**

```bash
node dev/capture/marktab-geometry.mjs
# writes .dreamwork/docs/measurements/367-tabs/ + prints the table
```

No server, no port. The script copies
`.dreamwork/review/review-essential-marks.html` to `/tmp` and drives Playwright
against a `file://` URL. Prototype CSS is injected only into that copy.

---

## How each number was obtained

| Quantity | Method |
|---|---|
| Tab font vs body font | `getComputedStyle` on a `.marktab` probe and on `body`. Asserted `body − tab > 0.5px` at runtime (measured gap **2.56px**: body 13.12px, tab 10.56px = `.66rem`). |
| Two-line width | Binary search for the **minimum width** at which a `Range` over the full label yields **≤2 distinct line tops**. Floor is the widest single word (no hyphenation, `hyphens:none`, `word-break:normal`). Height is `getBoundingClientRect` of that layout. |
| Page geometry | `getBoundingClientRect` on `.wrap` and the first `.read` at each viewport. Slack right of `.read` = `wrap.right − read.right`. Outside gutter = `viewport − wrap.right`. |
| Remaining in wrap | `slackRightOfRead − 4px gap − tabWidth`. Negative means the tab does not fit inside `.wrap`. |
| Past page edge | tab's right edge (`read.right + 4 + tabWidth`) `>` viewport. |
| Vertical collision | Two identical two-line tabs stacked flush; min top-to-top gap = measured tab height (**32.3px**). Compared to real section-top gaps and the densest block-top gap in this artifact. |
| Strip stress | Flex row of N two-line pills at the worst-case width inside `.wrap` at 700px; count flex rows and total height. |
| Sanity | Absurdly long label must widen the tab by >20px vs worst6. **It did** (+398px). |

### Prototype tab CSS (measure-only, not shipping)

```css
.marktab {
  font-size: .66rem;      /* body is .82rem */
  line-height: 1.25;
  padding: .28em .55em;
  /* width = measured min for ≤2 lines; no max-width; no truncation */
  white-space: normal;
  hyphens: none;
  word-break: normal;
}
```

### What would have made this report "does not fit"

- **Width / rail:** `remainingInWrap < 0` at a viewport the design still calls
  "rail" (≥780 under the old cliff), **or** the tab's right edge past the
  viewport (clipped). **Both fire for the worst-case tab at 780.**
- **Height:** any realistic pair of mark sites whose top-to-top gap is
  **&lt; 32.3px**. **Fires** for a section and its first `p.read` in this
  artifact (29.2px).
- **Strip:** soft-cap **7** worst-case two-line pills cannot stay on one row
  inside `.wrap` at 700 without truncation. **Fires** (3 rows, ~214px tall).

A green outcome on every row would have been: worst-case tab ≤96px (the old
budget), height small enough that densest block gaps clear it, and seven pills
in one strip row. That is **not** what was measured.

---

## Labels used (worst case, justified)

| key | label | words | why |
|---|---|---:|---|
| **worst6** | `reproducibility measurement against wrap geometry slack` | 6 | Long unhyphenated mono tokens drawn from this feature's own vocabulary (measurement, wrap, geometry). Width-stress case for ~6 words. |
| ruling6 | `two-line tabs at smaller text size` | 6 | From M3's ruling language — typical careful author length. |
| author6 | `flags mark a height not structure` | 6 | From the plan/artifact thesis sentence. |
| hisAsk6 | `pointer labels at the most important` | 6 | From his original ask, truncated only to six words for the cap he set. |
| short / one | `the cliff` / `ask` | 2 / 1 | SVG mock controls. |
| absurd | 32-word deliberately long string | 32 | Sanity only — must move width. |

**Why worst6 is worst, not merely long:** in monospace, width is dominated by
the longest tokens, not word count. `reproducibility` alone is a **~105px**
word-floor. A six-word label of short words (`sometimes they are quite long
reviews`) measures only **~126px**. Reporting only the short-word average would
have understated the rail cliff by ~50px.

No builder truncation was applied. No character cap was reintroduced.

---

## Label metrics (viewport-independent rem)

| key | words | lines | width px | height px | single-line width | tab fs | body fs | gap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **worst6** | 6 | 2 | **180.0** | **32.3** | 353.8 | 10.56 | 13.12 | 2.56 |
| ruling6 | 6 | 2 | 117.4 | 32.3 | 223.2 | 10.56 | 13.12 | 2.56 |
| author6 | 6 | 2 | 129.9 | 32.3 | 217.0 | 10.56 | 13.12 | 2.56 |
| hisAsk6 | 6 | 2 | 123.8 | 32.3 | 235.6 | 10.56 | 13.12 | 2.56 |
| short | 2 | 2* | 43.4 | 32.3 | 67.6 | 10.56 | 13.12 | 2.56 |
| one | 1 | 1 | 31.3 | 19.1 | 30.3 | 10.56 | 13.12 | 2.56 |
| absurd | 32 | 2 | 578.0 | 32.3 | 1131.7 | 10.56 | 13.12 | 2.56 |

\*Short labels under the *minimum* two-line packing shrink toward the word floor
and wrap; a one-line short tab would be wider (~68px) and shorter (~19px). The
design-critical row is **worst6**.

**Old one-line budget for comparison:** the plan's SVG assumed a **96px** flag.
Worst-case two-line is **~1.9× wider** and **~1.7× taller** than a 19px one-liner.

---

## Per-viewport table (worst6 tab = 180 × 32.3)

| viewport | tab w | tab h | slack right of `.read` | remaining in wrap after tab | outside gutter | verdict |
|---:|---:|---:|---:|---:|---:|---|
| 1280 | 180 | 32.3 | 506.5 | **322.5** | 80 | fits inside `.wrap` |
| 1120 | 180 | 32.3 | 474.5 | 290.5 | 16 | fits inside `.wrap` |
| 960 | 180 | 32.3 | 314.5 | 130.5 | 16 | fits inside `.wrap` |
| 860 | 180 | 32.3 | 214.5 | 30.5 | 16 | fits inside `.wrap` (tight) |
| 840 | 180 | 32.3 | 194.5 | 10.5 | 16 | fits inside `.wrap` (very tight) |
| 830 | 180 | 32.3 | 184.5 | **0.5** | 16 | fits inside `.wrap` by half a pixel |
| **820** | 180 | 32.3 | 174.5 | **−9.5** | 16 | **not inside `.wrap`**; still on page via outside gutter |
| **810** | 180 | 32.3 | 164.5 | −19.5 | 16 | **DOES NOT FIT — past page edge** |
| **780** | 180 | 32.3 | 134.5 | −49.5 | 16 | **DOES NOT FIT — past page edge** (old cliff) |
| 700 | — | — | 54.5 | — | 16 | strip mode (see strip) |
| 480 | — | — | 0 | — | 16 | strip mode |

`.read` stayed **~613.5px** wherever the wrap was wide enough; outside gutter is
**16px** from 1120 down — both reconfirm prior measurements.

---

## Answers to the five sub-questions

### 1. Width — how wide is a two-line ~6-word tab?

**180px** for the worst realistic 6-word label at `.66rem` / line-height 1.25 with
no truncation and no hyphenation. Typical authored 6-word labels land
**117–130px**. Single-line natural width of the worst case is **354px** (so
two-line packing saves ~174px of width at the cost of height).

### 2. The 506px budget — how much does the widest tab consume?

At 1280: **180 / 506.5 ≈ 35.5%** of the empty wrap; **322.5px still spare**.

The tab **stops fitting inside `.wrap`** between **830 and 820px** viewport
(remaining +0.5 → −9.5). It **clips past the page edge** by **810** and is
badly clipped at the old **780** cliff (remaining −49.5; only 16px outside
gutter exists to absorb overflow).

So: the 506px budget is generous on a wide monitor and **gone before 780** for
the worst-case two-line tab.

### 3. Height and vertical collision (priority — nobody had looked)

| measure | value |
|---|---|
| Two-line tab height | **32.3px** (one-line control: 19.1px) |
| Min top-to-top gap before overlap | **32.3px** (flush stack gap = 0) |
| Section-top gaps in this artifact | **329–929px** — none collide |
| Densest block-top pair in this artifact | **section#long → p.read = 29.2px** |
| Collision possible in this doc? | **Yes**, if both a section and its first
  reading paragraph are marked |

**What that means for real documents:** marks on **section** (or other
sparse block) tops do not collide — gaps are hundreds of pixels, matching the
"blocks run far apart" intuition. Marks on **adjacent** elements (section +
its first `p.read`, consecutive short paragraphs, a callout under a heading)
**can** sit 29px apart, which is **3px tighter than the tab is tall**. Two-line
tabs therefore introduce a real vertical-collision regime the one-line design
never measured.

The plan's "blocks run 614–1120px" was about **horizontal** block width
variation, not vertical spacing. Vertical density is a different axis, and it
is the one that bites.

### 4. The cliff — does 780 still hold?

**No, not for the worst-case two-line tab.**

| presentation boundary | viewport (worst6 180px tab) |
|---|---|
| Fits fully inside `.wrap` | **≥ ~830px** |
| On page but past wrap (uses outside gutter) | **~820px only** (narrow band) |
| Clips past page edge | **≤ ~810px** |
| Old cliff (780) | **clips** — confirmed in screenshot |

The 780 cliff was calibrated for a **96px** one-line flag (134px slack at 780 ≥
96). A 180px two-line tab needs ~184px of slack (tab + 4px gap) and does not
have it until ~830. **The rail/strip boundary moves up by ~50px** if the rail
must keep the worst-case tab fully inside `.wrap` with no truncation.

Typical 117–130px labels would put the wrap-fit cliff nearer **~780–800** —
closer to the old number — but the measurement that decides the cliff is the
**worst** case he authorised (~6 words, no truncation), not the average.

### 5. The strip below the cliff — does ~6 words at two lines work?

**Partially, and the soft cap matters.**

At **700px** (`.wrap` = 668px), two-line pills sized to the same widths:

| label set | N=3 | N=5 | N=7 (soft cap) |
|---|---|---|---|
| worst6 (180px) | **1 row**, ~67px tall | **2 rows**, ~140px | **3 rows**, ~214px |
| ruling6 (117px) | **1 row**, ~67px | **2 rows**, ~96px | **2 rows**, ~140px |

- **3 marks** of even the worst label fit one strip row — the mock's "four short
  pills" shape still works for a small set.
- **5–7 marks** force a **multi-row strip** once labels are two-line and untruncated.
  At soft-cap 7 with worst6 the strip is **~214px** tall — a second chrome block
  under the top rail, not a compact row.
- Truncation is **not available** (his ruling). "Shrink it" is not a measurement
  answer. The strip **needs its own design answer** for the 5–7 band: multi-row
  wrap, horizontal scroll, fewer visible pills + overflow menu, or accept a tall
  strip. That choice is his, not this measurement's.

---

## Screenshots (looked at, not only captured)

All under `.dreamwork/docs/measurements/367-tabs/`.

### `wide-tab-1280.png`

**Measured:** 180×32.3 tab in 506px slack, 322px spare.  
**Seen:** A lavender two-line postit sits cleanly in the empty wrap to the right
of the reading column. It **reads as one label** (not two stacked captions) and
as a **flag at a height**, not a sidebar. The metaphor holds at full width. Text
is fully visible; nothing clips.

### `wide-tab-cliff-780.png`

**Measured:** remaining −49.5px; past page edge.  
**Seen:** The same tab is **cut off by the right edge of the viewport** —
`reproducibility measure` / `against wrap slac` with the final letters gone. It
still *tries* to be a postit but fails as UI: a clipped flag is worse than no
flag. This is the screenshot that kills "780 still works for two-line ~6 words."

### `vertical-collision-min-gap-1280.png`

**Measured:** two tabs stacked flush; gap = 0; each 32.3px tall.  
**Seen:** Two identical two-line tabs form a **continuous double block** — more
like a short stacked chip than two separate lawyer flags. At min gap they do
**not** read as two independent postits; the eye groups them as one chrome
mass. A little air (even ~8–12px) would probably restore "two flags"; flush does
not.

### `vertical-real-sections-1280.png`

**Measured:** section gaps 329px+.  
**Seen:** Tabs at `#long`, `#findings`, `#geometry` sit as **separate flags** at
distinct heights. This is the good case — sparse marks look like the metaphor.
No sidebar effect.

### `strip-below-cliff-700.png`

**Measured:** three worst/ruling/author pills in one row at 700.  
**Seen:** A usable strip under the top rail: three two-line pills + `‹ 1 of 3 ›`.
Labels remain readable as single labels. The strip is **noticeably taller** than
a one-line pill row would be — it steals a chunk of vertical reading space but
still reads as chrome, not content. This is the *three-mark* happy path; it is
**not** evidence that seven marks fit.

---

## Absurd-label sanity

| | width |
|---|---:|
| worst6 | 180.0 |
| absurd (32 words) | 578.0 |
| delta | **+398** |

`moved: true`. The script is measuring the tab, not a fixed container.

---

## What this does **not** decide (his call)

Reporting only — no cap, no truncation reintroduced:

1. **Whether the rail/strip cliff moves from 780 to ~830** (or whether the rail
   may use the 16px outside gutter and clip-avoid only past-page, accepting
   past-wrap at 820).
2. **What the strip does at 5–7 two-line marks** (multi-row, scroll, overflow
   control, or live with a tall strip).
3. **Whether authors may mark two elements closer than ~33px** (builder warn?
   allow overlap? offset tabs horizontally?).
4. **Whether "smaller text size" stays at `.66rem`** — smaller still would
   recover width and height but is a product choice.

---

## Raw data

- Script: `dev/capture/marktab-geometry.mjs`
- JSON dump: `.dreamwork/docs/measurements/367-tabs/raw-numbers.json`
- Screenshots: `.dreamwork/docs/measurements/367-tabs/*.png`

Sub-pixel widths can drift ~1–3px between runs (font raster); the cliff
boundary and the collision regime do not.

---

## Confidence / not reached

- **High confidence:** width table, 780 clip (screenshot + numbers), vertical
  min-gap = tab height, section gaps safe, densest block gap unsafe, absurd
  sanity, font-size precondition.
- **Medium:** exact strip pill height (~67px in flex stress vs ~32px rail tab)
  — multi-row *counts* are solid; absolute strip chrome height may shift with
  final padding/border choices.
- **Not a product decision:** any "so build X" conclusion. Measurement stops at
  the number and the place it fails.
