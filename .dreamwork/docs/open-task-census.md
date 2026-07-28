# Open-task census — #420

A read-only scan of `.dreamwork/tasks.md` and `.dreamwork/questions.md` for the
coordinator, asked for at 15:25 (`/answers`) because the ledger is over 250,000
characters and nobody has a view of it. Every count below is **derived at runtime**
by `/tmp/census/numbers.py` (not committed — read-only job), which imports `watch`
and uses **only** the production parser (`parse_ledger`, `ledger_entries`,
`parse_open_questions`, `parse_answered`) per the brief's hardest rule. The
literal "138 open entries" in the brief and in `#420`'s own body is **already
stale** — the live count is **139**.

## Summary (read this in under two minutes)

- **139 open / 175 landed.** `parse_ledger` and `ledger_entries` agree on all 139
  ids (0 disagreement). `## Open` and `## Recently landed` each match exactly once.
- **Priority:** P1-or-hotter **24** (P1 20, P0/P1 3, P0 1) · P2 84 · P3 31.
  Type is **freeform prose, not a closed vocabulary** — 80 distinct spellings
  (`idea` 31, `task` 14, `bug` 7, `feature` 4, …). Any "count by type" is a guess.
- **The whole ledger is 3 days old** (oldest open is `#50`, first-seen 2026-07-25).
  Age is not the staleness axis here; **premise** is.
- **Blocking posture (manually verified, not regex-trusted):**
  - **5 live on his desk** — `#264 #275 #294 #346 #353`.
  - **4 he already ruled on, sitting unprocessed** — `#254 #367 #371 #50`. This is
    the live cost, and it is `#419`'s "answered-but-unfolded" half, not the
    "#264-no-question" half.
  - **24 task-blocked** (target still open) · **10 task-blocked whose target has
    LANDED** (the `#252` "blocker cleared, nobody noticed" class).
  - **99 startable now.**
- **Section 3 (highest value):** the `#264` failure mode — blocked on him with no
  question — is largely **closed**, because filing `#419` and the `#264` question
  fixed it. The live cost moved one door over: **answered-but-unprocessed**. One
  clean ambiguity remains (`#353`).
- **Ledger-vs-reality:** **10 stale blockers** (most consequential: the
  composer cluster `#244/#242/#241` behind landed `#238`; `#360`/`#276` behind
  landed `#233`; `#218` behind landed `#217`). `#172` is the brief's specimen and
  is **in progress right now** (grok, `.worktrees/172`).
- **Recommended next five** at the foot. The cheap structural unblock is `#419`.

---

## 1. The shape of the backlog, in derived numbers

Method: `import watch`; `parse_ledger(text)` for open/landed; `ledger_entries`
restricted to the open section for per-entry bodies; `lint._metadata_clause` for
the `·`-chain; `task_origins.py --json` for first-seen ages.

**Open vs landed (parser cross-check, the brief's mandatory line):**

```
## Open heading matches:           1   (assert == 1)  ✓
## Recently landed heading matches: 1   (assert == 1)  ✓
parse_ledger open ids:    139
ledger_entries open ids:  139
agreement: entries-only = 0, parser-only = 0   ← "parse_ledger and my own reader
                                                  agree on all 139 ids"
```

**By priority band** (robust reader: handles `P1`, `**P1**`, `P0/P1`, `P0`):

| band | count |
|---|---|
| P0 | 1 |
| P0/P1 | 3 |
| P1 | 20 |
| P2 | 83 |
| P2 (unmarked — absent means P2) | 1 |
| P3 | 31 |

**P1-or-hotter: 24.**

**By type:** the type token is the first non-`P`/non-`origin:`/non-`owner:`
token in the metadata chain. It is **freeform prose**: **80 distinct spellings**
across 139 entries. The common nouns are `idea` (31), `task` (14), `bug` (7),
`feature` (4), `chore` (3) — but most entries carry a bespoke slash-phrase
(`loop-tooling/durability`, `dashboard/consistency`, `security architecture/research`).
**There is no closed type vocabulary to count against**, so any "N bugs, M
features" summary would be inventing a taxonomy the ledger does not keep. This is
itself a finding: type is unstructured, which is the cheaper half of why `#346`'s
schema work wants a strict shape.

**By age of oldest mention** (first-sight in git, via `task_origins.py`):

| age band | count |
|---|---|
| 0–1 days | 53 |
| 2–3 days | 86 |
| ≥7 days | 0 |

Oldest open: `#50`, first-seen 2026-07-25 (3 days ago). **The ledger began three
days ago**, so nothing is "old" in wall-clock terms; staleness here is about
**premise** (a blocker cleared, a neighbour landed), and that is what §4 measures.

*Confidence: high on open/landed and priority (parser-supplied); medium on type
(the 80-spelling count is exact, but the "first non-P token" rule is mine, not
the parser's — a different rule would group slightly differently. The
freeform-not-closed conclusion does not depend on the rule.)*

---

## 2. What is actually blocked, and on what

A regex (`awaiting|blocked on|gated on|needs his|his ruling|…`) found 17
"human-blocked" candidates. **I read all 17 bodies.** Most regex hits are false
positives — prose *describing* `awaiting_human` as a field/mechanism (e.g. `#402`,
`#193`, `#188`) or quoting another task's blocker (`#415` quotes `#367`'s state).
After manual review, the honest classification is:

**A. Live on his desk — 5 entries** (a human decision is the current blocker):

`#264` (task-transition boundary), `#275` (public Dreamhub auth, six calls),
`#294` (SQLite ledger migration — bundled into the `#264` ruling),
`#346` (task-store entity schema, S1–S4), `#353` (normalise the Markdown ledger,
"S1/S2/S4 ruling" — see §3).

**B. He already ruled; the entry sits unprocessed — 4 entries** (the
`#419` "answered-but-unfolded" half):

`#254` (R1 ruled 2026-07-27 23:38 — "give the loop a resolution tag"),
`#367` (2b ruled 2026-07-28 15:11 — "C, with a collapsible index"),
`#371` (Q2 ruled 2026-07-28 05:43 — "yes, keep a partial witness"; the entry
still says "blocked on #263 Q2"), `#50` ("UNBLOCKED 02:53 — he answered rec go").

**C. Task-blocked, target still open — 24 entries.** These chain through the
live-on-his-desk set: `#357 → #346`, `#342 → #294`, `#287 → #294`, `#373 → #294`,
`#262 → #263`, `#419 → #264`, etc. The full transitive graph roots at `#264`/`#294`.

**D. Task-blocked, but the target has LANDED — 10 entries** (the `#252` "blocker
cleared and nobody noticed" class):

`#172 #218 #241 #242 #244 #249 #276 #333 #337 #360`

These are the most actionable stale findings — see §4.

**E. Startable now — 99 entries** (neither human-blocked nor task-blocked by an
open target). This is the answer to *"what could be happening and is not"*.

*How I decided, and confidence:* a regex proposed candidates; I confirmed each by
reading the body and checking the cited target's open/landed status through
`parse_ledger`. **High confidence on D** (machine-verified: target id ∈ landed
set). **Medium confidence on A/B** — these are prose judgements. `#353` is the
shakiest (§3). The `#283` index-lock case I classified as **neither**: it is
waiting on a real-world event (a `pi` restart + quiet window), not a human
decision; he already ruled "close after quiet window" (22:58) and the closing
condition was tested at 10:10 and is genuinely not yet met.

---

## 3. Blocked-on-human with no question — the `#264` failure mode, re-measured

This is the section the brief calls the highest-value, because `#264` was blocked
on a ruling with **no question filed** and he found out by being unable to act.
`#419` is the invariant; this census is that invariant measured by hand, once,
before the check exists.

There are **3 open questions** and **52 answered** in `questions.md` (via
`parse_open_questions` / `parse_answered`). Cross-checking every blocked-on-human
entry against them:

| entry | open-q names it? | answered-q names it? | verdict |
|---|---|---|---|
| `#264` | ✅ (the `#264` ratify question) | ✅ | **covered** |
| `#275` | ✅ (the six-calls question) | ✅ | **covered** |
| `#294` | ✅ (named in the `#264` question) | ✅ | **covered** |
| `#346` | ✅ (named in the `#264` question) | ✅ (entity-schema ask, answered) | **covered** |
| `#353` | ❌ | ❌ | **the one clean ambiguity** |

**`#353` is the single clean `#264`-class candidate.** Its body says *"do not
start without his ruling on S1/S2/S4 — the entries are his call"*, and **no
question in `questions.md` names `#353`**. The ruling it waits on (S1–S4) is the
*same* ruling `#346` waits on, and that ruling **is** pending in the open `#264`
question — so `#353` is transitively covered, but a reader landing on `#353`
alone cannot tell. That is precisely the ambiguity `#419` exists to kill, and it
is medium-confidence: if you read the `#264` question as covering S1–S4 for the
whole `#346`/`#353`/`#294` chain, there is no gap; if you read each entry as
needing its own named question, `#353` is the gap.

**The live cost has moved one door over.** The four entries in bucket B
(`#254 #367 #371 #50`) each have an **answered** question and **no open** one,
because he ruled and the loop has not yet folded/built. That is `#419`'s reverse
direction — *"an answered-but-unfolded entry that has sat unprocessed is also a
stall he cannot see"* — and it is the more populated failure today. `#371` is the
clearest instance: its body still says *"blocked on #263 Q2"* when Q2 was
answered "yes" at 05:43.

**Net for `#419`:** the no-question half is essentially closed (one ambiguity,
`#353`); the answered-but-unprocessed half is open and carries four entries.
Whoever builds `#419`'s check should cover **both** directions, and the four
entries above are the ready-made red fixtures for the answered half.

*Confidence: high on the question-coverage facts (parser-supplied); medium on the
`#353` verdict (depends on whether S1–S4 is read as one ruling or several).*

---

## 4. Entries the ledger and reality disagree about

Two kinds, both real today.

### 4a. Claimed open, blocker already cleared (the `#252` class) — 10 entries

Each says `blocked on #N` / `after #N` where `#N` is in the **landed** set
(machine-verified through `parse_ledger`). These read as blocked but are
startable now:

| entry | says it's behind | but `#N` is | note |
|---|---|---|---|
| `#360` | `#233` base LAN mode | **landed** | self-hosted ssh auth; premise cleared |
| `#276` | `#233` | **landed** | bearer-token LAN auth |
| `#337` | `#336` | **landed** | `do next` → `add idea` fallback |
| `#333` | `#324` | **landed** | the sixth `states.mjs` count-idiom holder |
| `#249` | `#245` (and `#228`) | **landed** | dev-overlay sampling cadence |
| `#244` | `#238` | **landed** | repo-browser visibility — **composer cluster** |
| `#242` | `#238` | **landed** | link changed files from commits |
| `#241` | `#238` | **landed** | extract one composer mount contract |
| `#218` | `#217` | **landed** | filed-to-landed median (`ledger_series`) |
| `#172` | queued after `#217` | **landed** | project identity in title — **in progress now** |

The composer cluster (`#244/#242/#241` behind `#238`) is the most consequential:
three queued UI tasks whose prerequisite landed and nobody re-triaged them.

### 4b. Genuinely unstarted, but a NEIGHBOUR landed and can be mistaken for it

**`#172` is the brief's specimen, confirmed.** `#153` (browser-tab title) and
`#318` (`TITLE_ROUTE` route omission) both landed last night and both touch the
title — so title work *did* land, just not the half he can see (project identity
in the visible title section). His *"I thought we already did last night"* is
exactly a neighbouring landing reading as the wrong thing being done. (It is also
**live right now**: grok in `.worktrees/172`, dispatched 15:17.)

*Confidence: high — 4a is machine-verified (target id ∈ landed set); 4b is read
from the entry bodies and matches `parse_ledger`'s open/landed verdict.*

---

## 5. Duplicates and overlaps (by symbol, not by words)

The brief's rule: overlap on the same **function/file/surface**, because the
words diverge while the symbol does not. Walking backticked identifiers and paths
shared across ≥3 open entries, the loud ones are `watch.py` (22 entries touch it),
`questions.md` (13), `file-formats.md` (11), `transitions.md` (11) — those are
*shared infrastructure*, not duplicates. The genuine overlap pairs:

- **`#176` vs `#322`** — both are "paste images into the composer/answer boxes."
  `#176` (P3, 90m) is the original and the bigger surface (binary upload,
  storage decision, `human_block()` rewrite); `#322` (P2, human add-idea) is a
  restatement of the composer half. Same surface, different priority — `#322`
  should fold into `#176` or name it.
- **`#98` vs `#281`** — both put the task queue on the dashboard. `#98` (P2,
  "show the open queue") is a one-liner idea; `#281` (P1, the rich `/tasks`
  page, **in progress**) subsumes it. `#98` is arguably obsolete.
- **`#235` vs `#373`** — both promote `/answers` follow-ups into topic chats.
  `#373` (P1, topic chats v2) is the build; `#235` (P2) is the specific
  follow-up-promotion behaviour inside it, and already says `blocked on #373`.
  Not a duplicate — a parent/child — but worth noting `#235` cannot start
  before `#373`, which itself waits on `#294`/`#346`.

The `#412`-vs-`#331` shape (new work filed when an open task already covered it
better) did **not** recur in a clean way: I found no pair where one entry is
strictly dominated by another on the *same symbol*. The closest is `#176`/`#322`.

*Confidence: medium. Symbol-sharing is machine-found, but "duplicate" is a
judgement — `#98`/`#281` could be read as a sequence rather than a duplicate.
Read each pair before folding anything; that is the coordinator's call, not this
report's.*

---

## 6. Stale entries (premise superseded)

Beyond the 10 cleared-blockers in §4a:

- **`#371`** — body says *"blocked on #263 Q2"*; Q2 was answered "yes" at 05:43.
  The blocker is gone; the entry is now startable (build the policy half) but
  reads as blocked.
- **`#367`** — increment 2b was ruled at 15:11; the entry still reads as
  "awaiting his ruling." Build is unblocked.
- **`#254`** — R1 ruled 23:38 ("give the loop a resolution tag"); implementation
  is unblocked, entry reads as gated on R1/R2/R3.
- **`#50`** — body literally says *"UNBLOCKED 2026-07-28 02:53"*; it is
  authorisable for a plan and reads as open-but-gated.
- **`#283`** — *not* stale in the bad sense: it correctly stays open pending a
  `pi` restart + quiet window (its own closing condition, tested 10:10, not met).
  Worth listing because a naive "open for >2 days" groomer would flag it.

No open entry references a `.py`/`.mjs` path that no longer exists (checked:
every backticked source path with a `/` resolves in the worktree).

*Confidence: high.*

---

## 7. Recommended next five

Ranked, one sentence each. Excludes the 10 in-progress/live lanes
(`#172 #264 #269 #281 #294 #354 #367 #392 #405 #420`).

1. **`#419`** — design the `blocked-on: **human**` marker + the lint check, and
   make the check cover **both** directions (no-question *and*
   answered-but-unprocessed). **This is the cheap structural unblock**: it is
   P1 loop-integrity, it is what this census measured by hand, and the four
   answered-but-unprocessed entries (`#254 #367 #371 #50`) are its ready red
   fixtures. Fixes the whole classification problem rather than one instance.
2. **`#402`** — `status_sync.py` prune `dreamers`, derive `awaiting_human` from
   `parse_open_questions`, and fix the `pgrep` pattern that silently zeroed
   `current_task_ids`. The dashboard reported "stalled" while the loop was doing
   its most productive work; a ready red exists (reinstate a landed lane's
   entry). P2 reliability, but it is the thing that makes every other dispatch
   decision distrustworthy.
3. **`#218`** — filed-to-landed median via `ledger_series`. **Cheap (20m) and its
   blocker (`#217`) already landed** — a §4a stale-blocker, startable today, and
   it is the kind of small unblock the coordinator systematically under-picks.
4. **`#415`** — widen the hand-off `sha` grammar to accept a run of shas (and the
   increment-vs-close distinction). P3, but the cheap red is already in the entry
   (today's `#411` line, pre-normalisation) and it is the *third* narrow-grammar
   defect today. Quick, honest, unblocks future two-commit lanes.
5. **`#392`** — question age is measured from midnight (wrong by up to a day),
   found by the coordinator looking at the deployed page. P2 correctness with a
   clear fix surface and a measurable failure (the `data-ct` resolves to
   midnight local; a `git log -S` on the headline gives the real time).

`#218` and `#415` are the two *cheap and unblock something else* picks the brief
asked for; `#419` is the structural one.

---

## On the review artifact

**Not built, deliberately.** The census is a coordinator working document, not a
proposal. The two things in it he should *rule on* (`#264` boundary, `#275` auth)
already ship their own review artifacts (`task-transition-boundary.html`,
`hub-public-auth.html`) and have open questions; the answered-but-unprocessed
cluster (`#254 #367 #371 #50`) needs **folding/building**, not a new proposal;
and `#419` will carry its own artifact when it is worked. A review artifact for
the census itself would be noise, and his rule is that *a review request* ships
one — not that every document is one.

## On verification

`python3 lint.py` and `python3 -m pytest -q -p no:randomly` are run below. **I did
not run `just test`** — it binds guard ports 39890–39899 and at least two other
lanes need them (the brief says so, and `#172`/a status_sync lane are live). That
is correct here, not a gap.

## Which section I trust least

**§2 bucket A/B (the human-blocked classification) and §3's `#353` verdict.**
Everything machine-derived (open/landed sets, cleared blockers, parser
agreement, age) is high-confidence; the human-blocked call is a prose judgement
per entry, and `#353` hinges on whether "S1–S4" is read as one ruling covering
the `#346`/`#353`/`#294` chain (no gap) or as needing a per-entry question (gap).
Treat bucket A/B as a shortlist to re-read, not a verdict.
