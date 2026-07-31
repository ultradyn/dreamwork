# Lane 631i2 report — Claude Code record classifier, still dark

**Verdict: LAND.** Branch `glm-631i2` at `04c56a49`, rebased onto master
`64b9eb2b`. 45 passed (34 new + 10 inc-1 + 1 direction-2 closer), lint clean
(6 warnings, the lane bar), redproof check clean.

## What changed and why

New `session_log/claude_code.py` (242 lines) — a pure classifier for one
complete parsed JSONL record. `classify_record(record, *, line, byte, length)
→ Classification` maps a record onto the increment-1 vocabulary **without
building a tree**: one record in, one classification out. The scanner owns
file positions (line/byte/length are passed in, not derived from the record);
the classifier owns the grammar-row decision and fact extraction.

Three outcomes, deliberately distinct:

- **NODE** — content record matching a known §2 row; carries a `kind` from the
  closed vocabulary, `ts`, `ref`, `uuid`, and `ToolFacts` for step.tool.
- **SUPPRESSED** — non-content record (any `type` not in {user, assistant,
  system}); chrome hidden by design (§3). Carries a `reason`, no `kind`.
- **UNCLASSIFIABLE** — content record whose structure matches no known row
  (e.g. system subtype we've never seen, assistant block type we don't
  recognise). Reported, never dropped (#702).

New `test_session_log_claude_code.py` (200 lines) — exact table over every §2
grammar row, both named injections, the #702/#136 distinction tests, and the
direction-2 closer.

## §2 grammar rows covered

| grammar row | discriminator | node kind | covered |
|---|---|---|---|
| user plain-string content | content is str | `turn.user` | ✅ |
| user text-block content | content is [{type:text}] | `turn.user` | ✅ |
| user tool_result content | content is [{type:tool_result}] | `step.tool` | ✅ |
| user isCompactSummary | isCompactSummary=true | `sys.compact` | ✅ |
| user isMeta | isMeta=true | `sys.note` | ✅ |
| assistant text block | block type=text | `step.text` | ✅ |
| assistant tool_use block | block type=tool_use | `step.tool` | ✅ |
| assistant thinking block | block type=thinking | `step.thinking` | ✅ |
| system compact_boundary | subtype=compact_boundary | `page` | ✅ |
| system stop_hook_summary | subtype=stop_hook_summary | `sys.note` | ✅ |
| system turn_duration | subtype=turn_duration | `sys.note` | ✅ |
| system away_summary | subtype=away_summary | `sys.note` | ✅ |
| chrome (all non-content types) | type ∉ {user,assistant,system} | suppressed | ✅ |

All rows covered. None could not be covered.

## How a reader distinguishes suppressed from unclassifiable

A **suppressed** record has `outcome == "suppressed"` and `kind is None` —
the record is non-content chrome, hidden by design. An **unclassifiable**
record has `outcome == "unclassifiable"` and `kind is None` — the record
looks like content but matches no grammar row. Both carry a `reason` string
that names the type/subtype and the decision. They differ on `outcome`, so
they never render identically (#136). The test
`test_suppressed_and_unclassifiable_are_distinct_outcomes` asserts this
directly.

## Red-proof, direction 1 (both injections)

### Injection 1: tool_result classified as a user turn

Sabotaged `_classify_user` to return `Classification(NODE, "turn.user", ...)`
for tool_result content. The test
`test_tool_result_classifies_as_step_not_turn_start` reds on the
discriminating message:

> `AssertionError: tool results are steps, not turn starts`
> `assert 'turn.user' == 'step.tool'`

The parametrized grammar-table test also reds on the `tool_result` row with
the same kind mismatch. Restored via `dev/redproof.py restore`; redproof
check confirms absence from working tree and commits.

### Injection 2: unknown chrome quietly relabelled as sys.note

Sabotaged the chrome branch to return `Classification(NODE, "sys.note", ...)`
for all non-content types. The test
`test_unknown_chrome_is_suppressed_not_relabelled_as_sys_note` reds on:

> `AssertionError: unknown chrome must be suppressed, not emitted as a node`
> `assert 'node' == 'suppressed'`

The assertion that tells "suppressed" from "quietly relabelled" is
`result.outcome == SUPPRESSED` (not NODE) combined with `result.kind is None`.
If the record were silently relabelled as sys.note, `outcome` would be `"node"`
and `kind` would be `"sys.note"` — both assertions would fail. The
`test_known_chrome_is_suppressed` parametrized test (8 chrome types) and
`test_suppressed_and_unclassifiable_are_distinct_outcomes` also red (10 total
failures). Restored via `dev/redproof.py restore`; redproof check confirms
absence.

## Red-proof, direction 2 (false-green)

**Found and closed.** The `_is_text_content` predicate checks whether a user
message's content is a string or a list of text blocks. If it were broken to
accept ANY list (`isinstance(c, list)` without checking block types), every
grammar-table fixture would stay green — because `_is_tool_result` is checked
first and catches tool_result, and no fixture had a user message with a
non-text, non-tool_result block (e.g. an image block).

Demonstrated the false-green: with the broken predicate, a user message
containing `[{"type": "image", ...}]` classifies as `turn.user` (wrong — §2
describes only string/text blocks for user turns), while all existing tests
pass.

**Closed** by adding
`test_user_with_non_text_non_tool_result_block_is_unclassifiable`, which
asserts that an image-block user message is `UNCLASSIFIABLE`. The broken
predicate returns `turn.user` and reds; the correct classifier returns
`unclassifiable` and passes.

## Call-graph verification

Searched for `import session_log` and `from session_log` across all `.py`
files in the worktree: the only match is `test_session_log_model.py`
(increment 1's test). Nothing in production imports `session_log`. The
classifier's only caller is its fixture test. The claim "nothing imports it
yet" is verified.

## Rebase

Master moved from `9c62f384` (base sha) to `64b9eb2b` (#645 increment 5
landed) while I worked. Rebased cleanly — no conflicts, no conflict markers
(grep for all four diff3 forms returned nothing). HEAD is now `04c56a49`,
two commits on top of master.

## Verification evidence

- `just pytest test_session_log_claude_code.py test_session_log_model.py` —
  **45 passed** (34 new + 10 inc-1 + 1 direction-2).
- `python3 lint.py` — **clean (6 warnings)**, the lane bar (#611/#667).
- `python3 dev/redproof.py check` — **clean**, 2 injections registered, all
  restored and absent from working tree and commits.
- No browser guards, no port binding, nothing near `:35110`/`:35113`. Dark
  and server-only.

## Out of scope (reported, not fixed)

1. **§2 vs §3 disagreement on `queue-operation`.** §2's measured table lists
   `queue-operation` under "chrome/meta — mostly hidden" (suppressed). §3
   says "sys.note is the honest bucket for stop_hook_summary, away_summary,
   queue-operation" (visible node). I followed §2 (the grammar the proof
   tests against) and suppressed queue-operation as chrome. If §3 is
   authoritative, this is a one-line change in `_CONTENT_TYPES` handling or a
   special case. The coordinator decides.

2. **§2 notes `turn_duration` and `away_summary` may also appear with
   `isMeta: false` on the record itself** (measured). My classifier checks
   subtype, not isMeta, for system records, so this is handled. Noting it
   for completeness.

3. **`attachment` records have a richer shape than other chrome** — they
   carry `parentUuid`, `isSidechain`, and an `attachment` object with hook
   data. They are suppressed as chrome, which is correct per §2. If they
   ever need to surface (e.g. as sys.note), that is increment 3+'s call.

4. **The classifier does not extract native tool input fields** (Bash
   `command`, Edit/Write `file_path`, Read offset/limit) or
   `toolUseResult.structuredPatch`. These are label-building facts (§7c)
   that increment 3's scanner will extract when composing the tree and
   building bookmarks. Increment 2 extracts only what classification needs:
   tool `name`, `tool_use_id`, `is_error`.

## DOGFOOD REPORT

**The brief was accurate and well-scoped.** The two injections and the
#702/#136 requirements were clear and testable. No friction with the loop's
tooling: `dev/redproof.py` worked flawlessly for both injections, the rebase
was clean, and the lane bar (6 warnings) was stable.

One minor finding: the **§2 vs §3 `queue-operation` disagreement** (out of
scope item 1 above) is a design-doc internal contradiction that cost ~5
minutes of analysis. It doesn't affect this increment (I followed §2), but a
future increment or a lane following §3 literally would diverge. Worth
reconciling in the design doc.

The **real-transcript investigation was genuinely useful** — confirming
`isCompactSummary` is a top-level boolean (not inside `message`), that
`toolUseResult` lives on the user record (not assistant), and that `subtype`
is the system-record discriminator. The brief's instruction to read real
transcripts but not copy them into fixtures was the right balance.
