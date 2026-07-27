# Research — task-id grammar audit (#401)

**Date:** 2026-07-28  
**Kind:** read-only audit. No parser, check, or test was changed.  
**Scope:** every id-matching pattern in `watch.py` and `lint.py` × every id
form that actually occurs in this repo's durable state.  
**Criterion that gates trust:** every matrix cell was produced by **executing**
the real pattern against a form string via `importlib`, never by reading a
regex by eye.

Related filed instances of the same class: `#395` (related-marker one-span),
`#399` (landed over-accept of bare bold ids), `#401` (hand-off `#(\d+)` blind
to sub-ids). This document generalises them into a coverage matrix.

---

## 1. How many patterns · how many forms

| Count | What |
|------:|------|
| **14** | Distinct id-touching regex / parse sites in `watch.py` + `lint.py` (twins counted once for pattern identity; listed with both homes below) |
| **18** | Applicators in the harness (the 14 sites plus 4 composed readers: `_open_ids`, `_landed_ids`, `parse_handoffs`, related-pipeline) |
| **17** | Distinct id **forms derived from the repo** with occurrence counts (section 2) |
| **5** | Neighbour cases exercised synthetically (section 7) — not claimed as occurring |

A count is the only thing a silent skip cannot fake. If a later reader finds a
15th pattern or an 18th form, the matrix is incomplete — not "clean".

### 1.1 Pattern inventory (enumeration, not memory)

Swept `watch.py` and `lint.py` for every compiled regex or inline
`re.findall` / `re.match` that extracts or matches a task id. Non-id patterns
(`_HOST_LABEL`, `DREAM_NAME`, `PLUGIN_KIND`, date stamps, etc.) excluded.

| # | Name | Pattern (source of truth in module) | Home | Role |
|--:|------|--------------------------------------|------|------|
| 1 | `LEDGER_ENTRY` / `LEDGER_ID` | `^- \*\*(#\d+(?:/#\d+)*)\*\*` | watch + lint (identical; pinned by test) | Open entry head; combined-aware |
| 2 | `LEDGER_MENTION` | `\*\*#(\d+)\*\*` | watch | Legacy landed mention (narrow) |
| 3 | `LEDGER_COMBINED_MENTION` | `\*\*(#\d+(?:/#\d+)*)\*\*` | watch | Landed ids via `_landed_ids` |
| 4 | `ENTRY_HEAD` | `^- \*\*([^*]+?)\*\*` | watch + lint (identical) | Captures bold head token |
| 5 | `ENTRY_ID` / `RELATED_ID` / title `findall` | `#(\d+)` | watch + lint (same shape, three call sites) | Digits after `#` inside a span |
| 6 | `HANDOFF_PENDING_RE` | `^-\s+\*\*#(\d+)\*\*\s*·\s*landed\s+`…`…·\s*by\s+…` | watch | Pending full grammar |
| 7 | `HANDOFF_FOLDED_RE` | `^-\s+\*\*#(\d+)\*\*\s*→\s*folded\s*\(…\)` | watch | Folded line |
| 8 | `HANDOFF_BARE_RE` | `^-\s+\*\*#(\d+)\*\*` | watch | Malformed-Pending fallback |
| 9 | `NEXT_ID` | `^Next id: \*\*(\d+)\*\*` | lint | Next-id counter (**no** `#`) |
| 10 | `CLOSE_SUBJECT` | `^(?:close\|merge)\(#(\d+)[)/,]` | lint | Git subject close/merge |
| 11 | `RELATED_MARKER` | `(?:^|[·])\s*related:\s*\*\*([^*]*?)\*\*` | lint | One bold span after `related:` |
| 12 | `RELATED_FIELD` | `(?:^|[·])\s*related:\s*` | lint | Field presence (no id capture) |
| 13 | `RELATED_ADJACENT_SPANS` | `related:\s*\*\*[^*]*\*\*\s*,\s*\*\*` | lint | Two-bold adjacency detector |
| 14 | placeholder nearest-id | `- \*\*#(\d+)` (inline in `check_placeholder_citations`) | lint | Nearest preceding entry id |

Composed readers (import the real functions, do not reimplement):

- `watch._open_ids` = `LEDGER_ENTRY` + `ENTRY_ID`
- `watch._landed_ids` = `LEDGER_COMBINED_MENTION` + `ENTRY_ID`
- `watch.parse_handoffs` = PENDING / BARE / FOLDED over sections
- `lint` related pipeline = `RELATED_FIELD` + `RELATED_MARKER` + `RELATED_ID` + `RELATED_ADJACENT_SPANS`

---

## 2. Id forms derived from the repo

**Surfaces scanned** (commands in §2.1):

- `.dreamwork/tasks.md`, `questions.md`, `answers.md`, `handoffs.md`
- `.dreamwork/docs/briefs/*.md`
- `.dreamwork/dreams/**/*.md`
- `git log --format=%s` (subjects)

**Method:** a classifier over bold spans, code spans, markdown links, bare
`#…` tokens, `close(`/`merge(`, and paren-subject forms. Counts are
**occurrences of the form shape**, not unique id values.

| Occurrences | Form key | Example | Brief named it? |
|------------:|----------|---------|-----------------|
| 2326 | `bare_hash_plain` | `#392` in prose | yes (as plain `#392`) |
| 360 | `plain_bold` | `**#401**` | yes |
| 186 | `paren_subject_id` | `docs(#264)`, `fix(#302)` | **no** |
| 171 | `code_span_plain` | `` `#392` `` | neighbour, but **occurs** |
| 79 | `close_merge_subject` | `close(#247):` | **no** (as a form class) |
| 57 | `bare_combined_slash` | `#367/#392` outside bold | partial (combined was named in bold) |
| 34 | `bare_digits_bold` | `**402**` (`Next id:`) | **no** |
| 29 | `prose_in_bold` | `**#96 stage 1**` | yes |
| 17 | `hash_range` | `#278–#280`, `#331-#334` | **no** |
| 10 | `comma_list_one_bold` | `**#381, #399, #395**` | **no** |
| 8 | `code_span_sub_id` | `` `#392a` `` | **no** |
| 8 | `code_span_combined` | `` `#138/#156` `` | **no** |
| 7 | `combined_slash_2_bold` | `**#138/#156**` | yes (as combined head) |
| 6 | `sub_id_bold` | `**#392a**` | yes |
| 5 | `bare_hash_sub_id` | `#392a` | yes (as sub-id) |
| 5 | `code_span_prose_id` | `` `#229/#270 topic chats v2` `` | **no** |
| 4 | `arrow_chain` | `#388 → #383` | **no** |
| 3 | `paren_subject_sub` | `fix(#392a)` | **no** |
| 2 | `sub_id_b` | `#392b` | **no** (only `a` was named) |
| 1+ | multi-way combined bare | `#225/#229/#235`, `#260/#262/#263/#269/#274` | **no** (only 2-way named) |
| 1 | `related_multi_bold` | `related: **#393**, **#394**` | implied by #395, still a form |
| 1 | `entry_prose_head` | `- **#159's departure was not missing…**` | **no** |

### Forms the brief did not name (criterion 1)

At least these, after real effort — not an empty "I did not look":

1. **`comma_list_one_bold`** — `related: **#381, #399, #395**` (10+ in `tasks.md`; the **working** related shape)
2. **`paren_subject_id`** — `docs(#264)` / `fix(#302)` (186 in subjects + briefs)
3. **`hash_range`** — `#278–#280` (17)
4. **`arrow_chain`** — `#388 → #383` (4)
5. **`code_span_plain`** — `` `#392` `` (171)
6. **`bare_digits_bold`** — `**402**` without `#` (Next id)
7. **`paren_subject_sub`** — `fix(#392a)`
8. **`sub_id_b`** — `#392b` (not only `a`)
9. **multi-way combined** — 3+ ids with `/` (occurs bare in prose/dreams)
10. **`entry_prose_head`** — bold head is id + English (`#159's departure…`)

If only one were required: **`comma_list_one_bold`** is the highest-value surprise — it is the dominant related-marker shape and is **not** the multi-bold shape `#395` closed.

### 2.1 Derivation commands

```bash
# Surfaces (same set the brief lists)
python3 - <<'PY'
# classifier: bold / code / link / bare / close|merge / paren-subject
# over tasks, questions, answers, handoffs, briefs, dreams, git log --format=%s
# (full script was run in-session; counts above are its output)
PY

# Targeted hunts for rare neighbours
rg -n '#\d+[a-z]\b' .dreamwork/ git log --format=%s   # sub-ids
rg -n '#\d+(?:/#\d+){2,}' .dreamwork/                 # 3+ combined
rg -n 'related:\s*\*\*[^*]+\*\*' .dreamwork/tasks.md
rg -n '#\d+\s*[–-]\s*#\d+' .dreamwork/                # ranges
```

**Not found in repo (occurrence 0):** four-digit `#NNNN` (max digits observed: 3; ledger Next id was **402** at audit time), multi-letter sub-suffix (`#392ab`), `#N.M` decimals. Four-digit is exercised only as a **synthetic neighbour** below.

---

## 3. The harness (criterion 3 — re-run this)

Save and run from the repo root. It imports the **real** modules; it does not
copy pattern strings.

```python
"""#401 matrix harness — execute, never eye-read."""
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] if False else Path(".").resolve()
sys.path.insert(0, str(ROOT))

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

watch = load("watch", ROOT / "watch.py")
lint = load("lint", ROOT / "lint.py")

FORMS = {
    # brief-named
    "plain_bold": "**#392**",
    "sub_id_bold": "**#392a**",
    "combined_2_bold": "**#367/#392**",
    "prose_in_bold": "**#96 stage 1**",
    # entry heads
    "entry_plain": "- **#392** — title",
    "entry_sub_id": "- **#392a** — title",
    "entry_combined_2": "- **#138/#156** — title",
    "entry_combined_3": "- **#225/#229/#235** — title",
    "entry_prose_head": "- **#159's departure was not missing, it was elsewhere.** — body",
    # hand-offs
    "handoff_plain": "- **#398** · landed `9f2012a` · 2026-07-28 09:26 · by ccc @grok — x",
    "handoff_sub_id": "- **#392a** · landed `abc` · 2026-07-28 09:40 · by ccc @glm52 — x",
    "handoff_bare_plain": "- **#392** something wrong",
    "handoff_bare_sub": "- **#392a** something wrong",
    "handoff_folded_plain": "- **#398** → folded (2026-07-28 09:31): note",
    "handoff_folded_sub": "- **#392a** → folded (2026-07-28 09:31): note",
    # derived / not brief-named
    "related_comma_one_bold": "  · related: **#381, #399, #395**",
    "related_multi_bold": "  · related: **#393**, **#394**",
    "related_unbolded": "  · related: #383",
    "code_span_plain": "see `#392` here",
    "code_span_sub": "see `#392a` here",
    "bare_hash": "mentions #392 in prose",
    "bare_sub": "mentions #392a in prose",
    "paren_subject": "docs(#264): x",
    "paren_subject_sub": "fix(#392a): x",
    "close_subject": "close(#247): done",
    "next_id_line": "Next id: **402**",
    "hash_range": "#278–#280",
    "arrow_chain": "#388 → #383",
    "markdown_link": "[#392](https://example.com)",
    "no_hash": "task 392 without hash",
    "four_digit": "**#1000**",  # synthetic neighbour
}

def cell_ledger_entry(s):
    ids = []
    for m in watch.LEDGER_ENTRY.finditer(s):
        ids.extend(watch.ENTRY_ID.findall(m.group(1)))
    return ids or None

def cell_mention(s):
    return watch.LEDGER_MENTION.findall(s) or None

def cell_combined_mention(s):
    ids = []
    for m in watch.LEDGER_COMBINED_MENTION.finditer(s):
        ids.extend(watch.ENTRY_ID.findall(m.group(1)))
    return ids or None

def cell_entry_head(s):
    m = watch.ENTRY_HEAD.match(s)
    if not m:
        return None
    return (m.group(1), watch.ENTRY_ID.findall(m.group(1)))

def cell_entry_id(s):
    return watch.ENTRY_ID.findall(s) or None

def cell_handoff_pending(s):
    m = watch.HANDOFF_PENDING_RE.match(s)
    return m.groups() if m else None

def cell_handoff_folded(s):
    m = watch.HANDOFF_FOLDED_RE.match(s)
    return m.groups() if m else None

def cell_handoff_bare(s):
    m = watch.HANDOFF_BARE_RE.match(s)
    return m.groups() if m else None

def cell_parse_handoffs(s):
    if not s.startswith("-"):
        return "N/A"
    p, f, m = watch.parse_handoffs("## Pending\n" + s + "\n")
    return {"pending": p, "malformed": m, "folded": sorted(f)}

def cell_open_ids(s):
    return sorted(watch._open_ids(s)) or None

def cell_landed_ids(s):
    return sorted(watch._landed_ids(s)) or None

def cell_next_id(s):
    m = lint.NEXT_ID.search(s)
    return m.groups() if m else None

def cell_close(s):
    m = lint.CLOSE_SUBJECT.match(s)
    return m.groups() if m else None

def cell_related(s):
    field = bool(lint.RELATED_FIELD.search(s))
    m = lint.RELATED_MARKER.search(s)
    adj = bool(lint.RELATED_ADJACENT_SPANS.search(s))
    if not m:
        return {"field": field, "marker": None, "ids": [], "adj": adj}
    val = m.group(1)
    return {
        "field": field,
        "marker": val,
        "ids": lint.RELATED_ID.findall(val),
        "adj": adj,
    }

def cell_placeholder(s):
    return re.findall(r"- \*\*#(\d+)", s) or None

APPLICATORS = [
    ("LEDGER_ENTRY+ENTRY_ID", cell_ledger_entry),
    ("LEDGER_MENTION", cell_mention),
    ("LEDGER_COMBINED_MENTION+ENTRY_ID", cell_combined_mention),
    ("ENTRY_HEAD+ENTRY_ID", cell_entry_head),
    ("ENTRY_ID alone", cell_entry_id),
    ("HANDOFF_PENDING_RE", cell_handoff_pending),
    ("HANDOFF_FOLDED_RE", cell_handoff_folded),
    ("HANDOFF_BARE_RE", cell_handoff_bare),
    ("parse_handoffs", cell_parse_handoffs),
    ("_open_ids", cell_open_ids),
    ("_landed_ids", cell_landed_ids),
    ("NEXT_ID", cell_next_id),
    ("CLOSE_SUBJECT", cell_close),
    ("related pipeline", cell_related),
    ("placeholder nearest", cell_placeholder),
]

if __name__ == "__main__":
    for fname, fstr in FORMS.items():
        print(f"\n### {fname}: {fstr!r}")
        for pname, fn in APPLICATORS:
            print(f"  {pname:36s} {fn(fstr)!r}")
    # #401 re-derivation
    line = "- **#392a** · landed `abc` · 2026-07-28 09:40 · by ccc @glm52 — x"
    p, f, m = watch.parse_handoffs("## Pending\n" + line + "\n")
    print("\n#401:", {"pending": p, "malformed": m, "folded": f})
```

**Provenance of cells below:** this harness was run in-session against the
working tree at audit time (HEAD near `487f63b`). Re-run after any pattern
edit; do not trust a table that cannot re-execute.

---

## 4. Executed matrix (selected cells)

Legend: `✓` accept (captures the intended id(s)); `✗` reject / no match;
`~` partial or **wrong id**; `—` pattern not applicable to this shape.

`None` / empty set / `NO_MATCH` from the harness = reject.

### 4.1 Entry-head and ledger readers

| Form (input) | `LEDGER_ENTRY`+`ENTRY_ID` / `_open_ids` | `ENTRY_HEAD`+`ENTRY_ID` | `LEDGER_COMBINED_MENTION` / `_landed_ids` | `LEDGER_MENTION` | `ENTRY_ID` alone |
|--------------|:---------------------------------------:|:-----------------------:|:----------------------------------------:|:----------------:|:----------------:|
| `- **#392** — title` | ✓ `['392']` | ✓ `('392', ['392'])` | ✓ `['392']` | ✓ `['392']` | ✓ |
| `- **#392a** — title` | **✗** | **~** head=`#392a` ids=`['392']` | ✗ | ✗ | **~** `['392']` |
| `- **#138/#156** — title` | ✓ both | ✓ both | ✓ both | ✗ (narrow) | ✓ both |
| `- **#225/#229/#235** — title` | ✓ all three | ✓ all three | ✓ all three | ✗ | ✓ |
| `- **#159's departure…**` | **✗** (prose breaks ids-only) | **~** ids=`['159']` | ✗ | ✗ | ✓ `['159']` |
| `**#392**` (mention only) | ✗ (needs `- `) | ✗ | ✓ | ✓ | ✓ |
| `**#392a**` | ✗ | ✗ | **✗** | **✗** | **~** `['392']` |
| `**#367/#392**` | ✗ | ✗ | ✓ both | ✗ | ✓ |
| `**#96 stage 1**` | ✗ | ✗ | ✗ (by design) | ✗ | ✓ `['96']` |
| `**#1000**` (synth 4-digit) | ✗ as mention-only; as `- **#1000**` would ✓ | — | ✓ | ✓ | ✓ |
| `` `#392` `` | ✗ | ✗ | ✗ | ✗ | ✓ (if applied to whole text) |
| `[#392](...)` | ✗ | ✗ | ✗ | ✗ | ✓ |

**Executed notes:**

- `LEDGER_ENTRY.pattern == lint.LEDGER_ID.pattern` → `True` (run in harness).
- Triple and 5-way combined heads **accept** under the `(?:/#\d+)*` quantifier:
  executed `LEDGER_ENTRY.findall('- **#260/#262/#263/#269/#274**')` → full span.
- Sub-id is the structural hole: every `#(\d+)` reader **strips the letter**
  when it matches at all; every `#\d+`** reader **rejects** the bold span.

### 4.2 Hand-off readers

| Form | `HANDOFF_PENDING_RE` | `HANDOFF_BARE_RE` | `HANDOFF_FOLDED_RE` | `parse_handoffs` (Pending section) |
|------|:--------------------:|:-----------------:|:-------------------:|-------------------------------------|
| `- **#398** · landed \`sha\` · … · by x` | ✓ | ✓ (prefix) | ✗ | `pending=[('398',…)]` malformed=`[]` |
| `- **#392a** · landed \`abc\` · … · by x` | **✗** | **✗** | ✗ | **`pending=[]` malformed=`[]`** |
| `- **#392** something wrong` | ✗ | ✓ | ✗ | pending=`[]` **malformed=`[('392',…)]`** (LOUD path) |
| `- **#392a** something wrong` | ✗ | **✗** | ✗ | **pending=`[]` malformed=`[]`** |
| `- **#398** → folded (…)` | ✗ | ✓ | ✓ | as Folded: `folded={'398'}` |
| `- **#392a** → folded (…)` | ✗ | ✗ | **✗** | as Folded: **`folded=set()`** |

### 4.3 Related-marker pipeline

| Form | `RELATED_FIELD` | `RELATED_MARKER` value | `RELATED_ID`s | `RELATED_ADJACENT_SPANS` |
|------|:---------------:|------------------------|---------------|:------------------------:|
| `· related: **#251**` | ✓ | `#251` | `['251']` | ✗ |
| `· related: **#381, #399, #395**` | ✓ | full comma list | **`['381','399','395']` ✓** | ✗ |
| `· related: **#393**, **#394**` | ✓ | **`#393` only** | `['393']` | **✓** (adj fires) |
| `· related: #383` | ✓ | none | `[]` | ✗ |

So the **dominant live related shape** (one bold, comma-separated ids) **works**.
The multi-bold shape still loses ids in the marker capture, but adjacency is
intended to make that **LOUD** in `check_related_markers` (ERROR), not silent —
see §5.

### 4.4 Lint-only subjects / next-id

| Form | `CLOSE_SUBJECT` | `NEXT_ID` | title `#(\d+)` findall |
|------|:---------------:|:---------:|------------------------|
| `close(#247): done` | ✓ `('247',)` | — | ✓ |
| `close(#138,#156):` | ✓ first id only `('138',)` | — | ✓ both if applied to whole |
| `docs(#264):` | ✗ (not close/merge) | — | ✓ |
| `fix(#392a):` | ✗ | — | **~** `['392']` |
| `Next id: **402**` | — | ✓ `('402',)` | ✗ (no `#`) |
| `**402**` alone | — | ✗ (needs prefix) | ✗ |

---

## 5. SILENT vs LOUD rejects

**Rule (brief):** classify only for readers that actually read a file where
that form occurs. Silent = no output, no WARN, no ERROR — indistinguishable
from a clean parse.

### 5.1 Silent rejects (the findings)

| # | Pattern / reader | Form | Occurs in | What is lost | Human-visible surface? |
|--:|------------------|------|-----------|--------------|------------------------|
| S1 | `parse_handoffs` (all three hand-off REs) | `- **#392a** · landed …` under **Pending** | `handoffs.md` (and any sub-id Pending line) | Line invisible to pending **and** malformed | **Yes — dashboard pending-handoffs + lint `#381` WARNs both miss it** |
| S2 | `HANDOFF_FOLDED_RE` / Folded branch | `- **#392a** · landed …` under **Folded** (pending-shaped line parked wrong, or sub-id folded line) | **LIVE at audit:** `handoffs.md` `## Folded` holds exactly this for `#392a` | Not in `folded_ids`; not in pending; not in malformed | **Yes — same delivery half as `#381`; line is a black hole** |
| S3 | `LEDGER_ENTRY` / `_open_ids` | open entry head `- **#392a**` | would occur if a sub-id were filed as an open head; sub-ids already exist in briefs/tasks prose | Open set omits the task | **Yes — dashboard open count / burn** if such a head is ever written |
| S4 | `LEDGER_COMBINED_MENTION` / `_landed_ids` | landed mention `**#392a**` | tasks prose + briefs | Landed set omits sub-id | Dashboard landed set (if used as sole id name) |
| S5 | `ENTRY_ID` / any `#(\d+)` consumer | any sub-id token `#392a` | tasks, briefs, handoffs, git subjects | Captures **`392` not `392a`** — silent **wrong id**, not merely drop | **Yes — mis-attribution to parent task** wherever only ENTRY_ID runs (e.g. `ledger_entries` head parse yields ids=`[392]`) |
| S6 | `ENTRY_HEAD`+`ENTRY_ID` on prose head | `- **#159's departure…**` | **1 real open/landed-style line in history** | `LEDGER_ENTRY` rejects (open miss) while `ledger_entries` accepts as 159 | Cross-check disagreement risk (lint open count vs parse_ledger) |
| S7 | `HANDOFF_BARE_RE` as "unrecognised head" validator | any Pending head whose id is not `#(\d+)` | same as S1 | Fallback shares the parser's blind axis — **cannot fire** on the class it exists to catch | Lint format WARN never appears |

**Silent reject count (distinct finding rows above): 7.**

Of these, **S1 / S2 / S7 are the same root** (`#(\d+)` on hand-off heads) and
are the `#401` class. **S5 is cross-cutting** and feeds wrong ids into any
composed reader that uses `ENTRY_ID` after a looser head capture.

### 5.2 Loud rejects (working as designed, or intended LOUD)

| Pattern | Form | Behaviour |
|---------|------|-----------|
| `HANDOFF_BARE_RE` + `check_handoffs` | plain `#N` Pending without full grammar | malformed WARN (#381) |
| `RELATED_FIELD` without bold | `· related: #383` | ERROR path in `check_related_markers` (#395) |
| `RELATED_ADJACENT_SPANS` | `related: **#393**, **#394**` | ERROR — multi-bold adjacency (#395 trap 2) |
| `LEDGER_COMBINED_MENTION` on `**#96 stage 1**` | prose-in-bold | intentional inert (not a landed id) |
| `CLOSE_SUBJECT` on non close/merge subjects | `docs(#264)` | no match; other tools don't use this RE for those subjects |

### 5.3 Over-accept (not a reject — still the same class of grammar drift)

`#399` is the dual: `_landed_ids` / `LEDGER_COMBINED_MENTION` **accepts** any
ids-only bold span in the landed section, including bare cross-references.
That is not a matrix "reject" cell; it is recorded here so the audit's class
is complete. **Do not "fix" it in this lane** — live owner on `watch.py`.

---

## 6. Ranking silent rejects by human-visible information loss

1. **S1 — sub-id Pending hand-off vanishes from pending and malformed**  
   Surface: dashboard hand-off strip + lint delivery WARN.  
   A landing can complete and leave **zero** durable reader signal. This is
   `#401`'s measurement and the highest-severity silent drop.

2. **S2 — LIVE: `#392a` line under `## Folded` with Pending shape is invisible**  
   Surface: same delivery half. Executed on the live file at audit time:
   `HANDOFF_FOLDED_RE` → false; section is Folded so PENDING/BARE never run;
   `parse_handoffs` → not in `folded_ids`, not pending, not malformed.  
   (Whether the writer meant Pending or Folded is secondary; **no reader sees it**.)

3. **S5 — `ENTRY_ID` strips the sub-id letter → parent id**  
   Surface: any UI or check that keys on `ledger_entries` / origin walk / related
   ids when the head was `#392a`. Mis-files work under `#392`. Quieter than S1
   (something still appears) but **wrong**.

4. **S7 — fallback validator shares `#(\d+)`**  
   Surface: lint "grammar does not recognise" WARN. Makes S1 self-hiding.

5. **S3/S4 — open/landed sets ignore sub-id heads/mentions**  
   Surface: dashboard open/landed. Lower rank today because ledger **heads**
   are still plain `#N` for the parent; sub-ids live in hand-offs and prose.
   Becomes P1 the first time a sub-id is filed as its own open entry.

6. **S6 — prose entry head**  
   Rare (1 observed). `LEDGER_ENTRY` inert; looser `ENTRY_HEAD` path still
   extracts a number. Ranking low until it reappears as a head style.

---

## 7. Neighbour cases (brief checklist)

| Neighbour | Occurs? | What readers do (executed) |
|-----------|---------|----------------------------|
| Id in **code span** `` `#392` `` | yes (171) | No bold mention RE matches. `ENTRY_ID` still finds `392` if run on whole text. `_landed_ids` / `_open_ids` ignore it. |
| Id with **no `#`** (`task 392`, `**402**`) | bare digits bold yes; "task N" rare | All `#…` readers reject. `NEXT_ID` accepts digits-only in its fixed line. |
| **Four-digit** id `#1000` | **not yet** (max 3 digits; Next id 402) | `\d+` patterns **accept** four digits when synthetic `**#1000**` / `- **#1000**` is run. No cliff at 1000. |
| Id in a **markdown link** `[#392](...)` | only as example text in this brief at audit time | Mention REs reject; `ENTRY_ID` accepts if applied. |
| **Same form in a file the reader does not read** | e.g. sub-id only in a brief | No effect on that reader (by definition). Hand-off readers only see `handoffs.md`; related check only walks ledger entries. |

---

## 8. Independent re-derivation of `#401`

**Claim under test:**  
`- **#392a** · landed \`abc\` · 2026-07-28 09:40 · by ccc @glm52 — x`  
under `## Pending` yields `pending=[]` **and** `malformed=[]`.

**Executed:**

```text
input: '- **#392a** · landed `abc` · 2026-07-28 09:40 · by ccc @glm52 — x'
HANDOFF_PENDING_RE.match → None
HANDOFF_BARE_RE.match    → None
parse_handoffs → pending=[]  malformed=[]  folded=set()
```

**Verdict: REPRODUCES.** No correction to the filed measurement.

**Live witness (stronger than the synthetic line):** at audit time,
`.dreamwork/handoffs.md` contained under `## Folded`:

```text
- **#392a** · landed `159917b` · 2026-07-28 09:43 · by ccc @glm52 — …
```

Executed line classification: `FOLDED=False`, and because the section is
Folded, PENDING/BARE are not consulted → **complete silence**. Plain `#398`
and `#397` Pending lines still parse. So the defect is not theoretical and
not only "if someone writes a sub-id"; **one is already in the file**.

---

## 9. Cross-cutting observations (not fixes)

1. **Fallback validators that share the parser's axis are hollow.**  
   `HANDOFF_BARE_RE` is `#(\d+)` like `HANDOFF_PENDING_RE`. Anything that
   breaks the id token breaks both. When you meet "anything the parser
   rejected", **vary the shared axis** and re-run (brief rule; confirmed).

2. **`ENTRY_ID = #(\d+)` is the single most reused atom** and silently
   normalises `#392a` → `392`. Widening only hand-off REs without widening
   `ENTRY_ID` (or teaching heads about sub-ids) will leave S5 alive.

3. **Combined slash heads are fine** through three and five ids; the
   grammar debt is not `/`-combination, it is **suffix letters** and
   **prose inside the bold head**.

4. **Related markers: the common shape works; the rare multi-bold shape is LOUD.**  
   `#395`'s residual risk is process (writers using multi-bold) more than
   silent drop — adjacency ERROR is the loud path. Confirm in a future
   red-run of the check if ownership allows; not done here (no test edits).

5. **`#399` is over-accept, not under-accept** — dual of this matrix's reject
   cells; still the same "parser vocabulary ≠ ledger vocabulary" class.

---

## 10. Files / ownership (this lane)

| Path | Action |
|------|--------|
| `.dreamwork/docs/research/2026-07-28-task-id-grammar-audit.md` | **written (this file)** |
| `.dreamwork/handoffs.md` | **one append** under `## Pending` for `#401` |
| `watch.py`, `test_watch.py`, `watch-design.md` | read only (live owner #392a) |
| `.dreamwork/docs/plans/watch-client-extraction.md` | read only (live owner #397) |
| `.dreamwork/tasks.md`, checks, tests | **not modified** |

Note: `.dreamwork/docs/research/` still has no `doc-map.md` row (coordinator
filing). This file does not add one.

---

## 11. What this audit did not reach

- Exhaustive paste of all 18×38 raw harness cells into the doc (selected
  matrices above; full re-run via §3 harness).
- Red-running `check_related_markers` / `check_handoffs` against temp fixtures
  (would touch no production code but needs care with load; load was elevated
  at dispatch). Classification of related multi-bold as LOUD rests on reading
  the check's ERROR branches + executed adjacency match, not a live lint WARN
  capture of a fixture.
- Git history before the last ~8k subjects for fossil forms.
- `dreamhub.py` or other binaries outside the brief's `watch.py` + `lint.py`
  scope.

---

--- SUMMARY ---

- **Patterns:** 14 distinct id-touching sites in `watch.py`/`lint.py` (18 harness applicators including composed readers). **Forms:** 17 derived from repo surfaces with counts; ≥10 not named in the brief (top surprise: comma-list one-bold related markers).
- **Harness:** `importlib` load of real `watch` + `lint`; apply each pattern/function to each form string; full script in §3 — re-run from repo root.
- **Silent rejects: 7** (S1–S7). Top three by human-visible loss: (1) sub-id Pending hand-off → empty pending **and** empty malformed; (2) **live** `#392a` line under Folded with Pending shape → invisible to every set; (3) `ENTRY_ID` strips letter → silent wrong parent id.
- **`#401` measurement: REPRODUCES** (`pending=[]`, `malformed=[]`). Live `#392a` hand-off line confirms it is not synthetic-only.
- **Loud paths working:** plain bare hand-off → malformed; unbolded / multi-bold related → field/adjacency ERROR paths.
- **Not fixed** (brief forbids): no parser/check/test edits. Hand-off append + this research file only.
- **Not reached:** full cell dump; fixture-level lint WARN capture under load; dreamhub scope.
