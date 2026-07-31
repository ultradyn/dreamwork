# Lane #725 report — a title can embed a condition that later becomes false

**Verdict: SHIPPED.** The lint check landed. The `retitle` verb was evaluated and
deliberately not built (argued below).

## What changed and why

A new lint check, `check_title_blocked_claim`, in `lint.py` (138 lines including
docstring), plus 12 tests in `test_lint.py` (`TestTitleBlockedClaim`), plus one
line added to the `TestLedgerSkipsAreReported.EXPECTED` skip list.

The check finds an OPEN entry whose **title** contains the claim idiom "blocked on"
while its **`blocked_on` field is empty**. `list` prints titles (`_list_line` joins
`#id  state  — title`) and does NOT print `blocked_on` — only `get` does. So a title
that embeds a blocked-ness claim misleads exactly where a correction appended
underneath is invisible. The fix is either to retitle (the claim is stale) or to
set `blocked_on` (the claim is current but was never recorded).

**WARN, not ERROR** — same reasoning as `check_landed_still_open`: a stale title
was true when filed and rotted when the ruling landed. The check names the id and
the offending title fragment so the coordinator can act.

The check is mode-dependent on "what counts as empty blocked_on":
- **store mode**: the `blocked_on` column is NULL or whitespace
- **markdown mode**: no `blocked-on: **…**` marker in the metadata chain

## The measurement (before building anything)

Measured on 170 open titles via `store_records` against the live store
(`/home/xertrov/.llm-general/skills/ud-dreamwork/.dreamwork/ledger.sqlite3`):

| pattern | open titles matched | with EMPTY blocked_on |
|---|---|---|
| `blocked` (bare, case-insensitive) | 6 | 6 |
| `blocked on` (claim idiom, case-insensitive) | **3** | **3** |
| `BLOCKED` (caps) | 1 | 1 |
| `waiting on` | 1 | 1 |
| `pending his` | 0 | 0 |
| `queued behind` | 0 | 0 |

**The claim idiom "blocked on" catches exactly three and zero false-positives.**
The three are the known instances — and a third the brief did not name:

- **#630**: "Build the derived component surface + bundle step (the #591 survivor) — blocked on his G2 ruling" — `blocked_on=None`
- **#631**: "Build the live session-log view (the #613 design) — blocked on his three design calls" — `blocked_on=None` (body records "UNBLOCKED 2026-07-31 19:05"; title never amended)
- **#641**: "Implement the phased push transport, phases 0-3 — BLOCKED on the #614 wire-protocol ruling" — `blocked_on=None`

Bare "blocked" catches those three PLUS three legitimate descriptions:
- #193 "A blocked errand is invisible" — a description, not a claim
- #623 "Playwright MCP output roots point at a retired worktree, and file:// is blocked" — a description
- #725 (this task's own title) — a description

The brief's named false-positive — "Fix the `blocked_on` writer" — uses the
UNDERSCORE form, which "blocked on" (space) does not match. Verified by test.

**Widening to "waiting on" / "pending his" / "queued behind" was measured and
refused.** "waiting on" matches #188 ("Review rows show who they are waiting on"
— a feature description, not a claim). "pending his" and "queued behind" match
zero. Adding a pattern that catches zero real claims and one description is #707's
false-attribution hazard with no payoff (#590: a non-zero count is a question).

The live check output against the main checkout's store:
```
WARN  tasks.md  #630's title claims blocked-ness ("Build the derived component surface + bundle step (the #591 survivor) — …") ...
WARN  tasks.md  #631's title claims blocked-ness ("Build the live session-log view (the #613 design) — blocked on his three…") ...
WARN  tasks.md  #641's title claims blocked-ness ("Implement the phased push transport, phases 0-3 — BLOCKED on the #614 wi…") ...
clean (3 warning(s))
```

## Why no `retitle` verb

The brief said: build the check first, and the verb "only if it falls out
cheaply." The check is the class-finder — it would have caught both (now three)
without anyone looking. The verb fixes one instance at a time, and the WARN
already names exactly what to do ("Retitle it, or set blocked_on to match the
claim"). The defect data is 3 known instances the coordinator can retitle by hand
in seconds. Building a `retitle <id> --why` verb would be ~40 lines in
`dev/ledger.py` (following #627's `unblock`/`reprioritise` shape), and while the
brief's `--why`-mandatory precedent (#627) is clear, the verb does not "fall out"
of the check — it is a separate deliverable for a problem the check already
solves by naming. Per #612 (volume: land the fewest lines that carry the meaning),
I did not build it.

## Red-proof

### Direction 1 — the check CATCHES the defect

Injected via `dev/redproof.py begin lint.py`, sabotaged the claim-match line:

```python
TITLE_BLOCKED_CLAIM = re.compile(r"\bblocked on\b", re.IGNORECASE)
_REDPROOF_NEVER_MATCH = re.compile(r"(?!x)x")  # SABOTAGE: matches nothing
```
and changed the check to use `_REDPROOF_NEVER_MATCH` instead of
`TITLE_BLOCKED_CLAIM`. Result: **5 tests RED** on the discriminating message:

```
FAILED test_a_title_claim_with_empty_blocked_on_warns
FAILED test_case_insensitive_BLOCKED_matches
FAILED test_store_mode_title_claim_empty_blocked_on_warns
FAILED test_store_mode_whitespace_blocked_on_still_warns
FAILED test_coverage_row_when_claim_is_backed
```

The discriminating assertion names the id and the offending title fragment:
`any("#1" in d and "blocked on his ruling" in d for d in warns)`. The negative
tests (descriptions don't trip, backed claims clean) stayed green — silence is
their correct outcome, so they cannot mask a sabotaged check.

Restored via `dev/redproof.py restore lint.py` — verified clean, 12 passed.
The production line the red targets: `TITLE_BLOCKED_CLAIM.search(title)` in
`check_title_blocked_claim`.

`redproof.py check` output:
```
history: examined 3 commit(s) since f054e8824345 (master) against 1 injected path(s); read 3 blob(s), 0 holding a recorded injection.
check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits:
  lint.py (sha 81e060aaf83d, hint: '_REDPROOF_NEVER_MATCH = re.compile(r"(?!x)x")  # SABOTAGE: matches nothing')
```

### Direction 2 — the false-green the check does NOT close

**Named and pinned**, not fixed. A title claiming blocked-ness where `blocked_on`
is genuinely NON-empty but names an already-LANDED blocker passes this check
silently — the field is populated, so the check stays quiet. This is #590's
stale-blocker case. The test `test_a_stale_nonempty_blocker_passes_silently`
constructs exactly this (title "blocked on his ruling", `blocked_on="#999"`) and
asserts the check is silent, with a message that names the gap: closing it needs
#590's blocker-landing audit (is #999 landed?), not a title check that cannot
judge it.

The brief's other two Direction-2 candidates were checked and are NOT
false-greens of this check specifically:
- **"a title saying unblocked"** — "unblocked" does not match "blocked on", so it
  is correctly silent (no blocked-ness claim).
- **"a claim in the BODY's first line rather than the title"** — the check
  governs TITLES (what `list` prints), so a body-only claim is out of scope. A
  body claim is a different defect surface (it is not what the coordinator scans),
  and catching it would be a different check.

## Cited issues, with relied-on lines

- **#627** — the writer precedent and mandatory `--why`. Relied-on line:
  *"Two verbs — reprioritise <id> <band> --why and unblock <id> --why … --why is
  MANDATORY (argparse refuses without it, verified at the gate) and lands in the
  task's own history like fold, which is the property that makes the verb safe
  rather than convenient."* This is the precedent I followed in deciding the
  retitle verb's shape (and in deciding not to build it without the check).
- **#707** — every widening multiplies false attribution. Relied-on line:
  *"CARE REQUIRED ON (1) … widening a pattern that feeds an automatic correlation
  makes FALSE ATTRIBUTION possible where before there was only silence."* This
  governed my substring choice: "blocked on" over bare "blocked".
- **#590** — a non-zero count is a QUESTION. Relied-on line: *"A non-zero count
  is a question, not a verdict (#590)."* (cited from #707's body, which is the
  form the rule travels in). This governed my measurement: I reported the count
  for each candidate pattern rather than trusting a "looks right".
- **#136** — "this task is blocked" and "this task's title once said it was
  blocked" must not render identically. Relied-on line: *"present-but-unparseable
  is a fault and must look like one; genuinely empty is #141's calm grey."* This
  is the distinction the check enforces: a title SAYING blocked while the field
  says nothing is the fault, not the calm grey.
- **#612** — volume. Relied-on line: *"land your change as the fewest lines that
  carry the meaning."* This governed not building the retitle verb.

## Verification

- `python3 -m pytest test_lint.py` — **534 passed** (was 522 at dispatch; +12
  new tests), 0 failed.
- `python3 lint.py` — **clean (6 warning(s))**, all 6 the expected store WARNs in
  a worktree (#611). My check correctly appears in the skip row alongside its
  sibling `check_human_blocker`.
- Non-UI lane, **no browser guards** run (coordinator owns the suite; ports busy).
- 2 commits at HEAD: `15aed97b`, `b53c82e5`, `337a23ba` (rebased onto `f054e882`).

## Out of scope (named, not fixed)

1. **#590's stale-blocker case** (Direction 2 above). A populated `blocked_on`
   naming a landed blocker passes this check. Closing it needs the
   blocker-landing audit — "is #999 landed?" — which is #590's job, not a title
   check's. Filed as a known gap; the test pins it.
2. **#631's title** is still wrong in the live store. This check reports it; the
   coordinator can retitle it (or set `blocked_on`) at fold. The check is the
   finder, not the fixer.

## Rebase

Rebased onto local `master` at `f054e8824345b3b29e6c5c6fa598955a9a292916` (was
`1ab60a3c` at dispatch). No conflicts; no conflict markers. Append-only files
untouched. HEAD is `15aed97bc8e92d4574e78f92922a058e589365ee`.

## Dogfood report

The brief was excellent — the measurement instruction ("count how many trip it
before believing the check") is exactly right, and the answer was decisive. Two
minor frictions:

1. **The brief named #630 and #641 but not #631.** The measurement found #631 as
   a third instance with the identical shape — its body even records "UNBLOCKED
   2026-07-31 19:05" while the title still says "blocked on his three design
   calls". This is the argument for measuring over trusting the named examples:
   the brief's two were drawn from memory, and the measurement found the third
   for free.
2. **The store-mode test fixture took three iterations to get right.** The
   `store_entries` projection returns the verbatim body for headed entries (the
   import shape), so updating only the `title` column doesn't change what
   `ledger_view` reads — both the title column AND the body's head line must
   carry the claim. This is not a bug in either piece (real defect data carries
   it in both), but it is a subtlety a future store-mode test author will hit.
   Not worth a lessons entry — the test docstring now names it.
