# Citation anchoring — #914, #880, #847

Design only (#914). No code, no citation rewritten. Every number below is
followed by the command that produced it, run at `55afc4f6` unless stated.

## 1. The relation, and the verdict

**Not one fix, not three. Two — and the seam is not where the ledger puts it.**

The three entries are usually read as one root (line-anchored citations into a
growing file) with three faces. The root is real. The *populations* are not
shared, and that is what decides the sequencing.

| | #914 | #880 | #847 |
|---|---|---|---|
| subject | `dev/check_watch_citations.py`'s oracle | living prose citations | living prose citations |
| population | **19** frozen historical citations | **551** examined by lint | **348** unqualified `watch.py:N` |
| symptom | false positive, loud | false negative, silent | debt |
| overlap with #914 | — | **none** | **none** |

The measured reason #914 does not overlap the other two: all 19 of its
citations are already revision-pinned, and #847's population is *unqualified by
definition*. The two sets are disjoint by construction.

- **#847 + #880 are one job.** Same corpus, and #847's write is the thing
  #880's check would bind. Doing #847 first rewrites entries that #880 then
  rewrites again — the coordinator's sequencing worry, confirmed.
- **#914 is a separate job whose subject is the instrument, not the corpus.**
  Nothing it touches is a document.

**And #914 is bigger than filed.** The guard is not merely expensive to
satisfy — it is *currently certifying false statements*. See §2.4.

**Sequence: #914 first, then #847+#880 together.** #914 is cheap (no document
changes) and it must go first for a reason beyond cost: while its constant is
stale the guard cannot reach its own assertion at all, so the corpus job would
be working against an instrument that is both blocking and lying.

## 2. Measured facts

### 2.1 The populations

```
$ python3 lint.py | grep 'citation range'
  OK    citation range  551 citation(s) in range across 239 living doc(s)
                        (past-EOF only; wrong-line citations are undetectable)
```

`395` `watch.py:N` citations across `84` tracked docs; `94` in living docs
(27 docs), `301` in historical docs; `348` carry no `@ <rev>` (77 docs, worst:
handoffs.md 54, render-architecture.md 45, 514-wake-semantics-audit.md 25).
Command: a `git ls-files '*.md'` scan applying lint's own `HISTORICAL_DOC_PATHS`
/`HISTORICAL_DOC_PREFIXES` split and `check_watch_citations.CITATION`.

Two brief numbers are stale and I re-derived rather than repeating them:
`503/235` is now `551/239`, and #847's `62 unqualified across 16 documents` is
now `348 across 77` under the whole-corpus reading (`84` under lint's
living-only reading). The population grew while the entries sat.

### 2.2 The guard today

```
$ python3 dev/check_watch_citations.py
PASS: #801's 19 certified +25 watch.py citation(s) resolved (19 pinned to
dc739001); 5 weak not certified; 33 out-of-range; 55 doubly-out-of-range (past
both ends); 104 non-surviving; 6255 base lines, 7100 current lines
```

**The certified population is 19, not 25.** `25` is `DRIFT`, the hand-measured
global offset. The originating dogfood said "DRIFTING 25 CERTIFIED ENTRIES";
the two numbers are unrelated and coincide only because `DRIFT` was bumped
12 → 22 → 25 (`git log -L 56,56:dev/check_watch_citations.py`).

### 2.3 The #914 event, reproduced with the real guard

In a scratch clone (`git clone --local`, `dev/lane_scratch.py measure`), one
line inserted into the `COMMANDS` table at `watch.py:367`:

```
$ python3 $C/dev/check_watch_citations.py --root $C
ERROR population: #801's certified inventory resolved 0 distinctive +25
citation(s); the certified multiset differs from EXPECTED_CERTIFIED_MULTISET
(-(...19 members...))
$ python3 -m pytest test_check_watch_citations.py -q
1 failed, 1 passed
```

**19 → 0 in one step.** It is exact-match, not a tolerance: simulating
`DRIFT ∈ {24, 26, 27}` collapses the certified count to 0 identically, so a
deletion breaks it as surely as an insertion, and by any magnitude.

The compound cost, which the filing does not name: a stale `DRIFT` does not
only produce a false positive, it **disables the real assertion**. `check()`
returns at the multiset comparison, so the pin check below is never reached.
The false positive and a blind window are the same event.

### 2.4 The guard is certifying falsehoods

The pin check *is* reachable — stripping one `@ dc739001` from
`.dreamwork/lane-641-report.md` line 136 in the scratch clone gives:

```
STALE .dreamwork/lane-641-report.md:136: watch.py:4068 is 25 lines behind its
byte-identical evidence at watch.py:4093
FAIL: 1 unqualified and 0 misclassified shifted citation(s)
```

So the guard's live assertion is: *these 19 historical citations keep their
`@ dc739001` pin.* Everything else — `DRIFT`, the byte-match, the class census
— is scaffolding for locating them.

**That assertion is false for the citations it protects.** Twelve of the 19
name a symbol in the prose beside them. Resolving each against
`git show dc739001:watch.py`:

- **0 of 12** have that symbol within ±5 lines of the coordinate they are pinned to.
- **5 of 12** name a symbol **absent from `dc739001:watch.py` entirely**.
  Three of those five (`BURN_LIMIT_CAP`, `chatList`, `setCardMode`) live in
  `client/` at that revision; the other two (`reviews5`,
  `test_chat_command_entry_is_far_left_default`) are not production symbols at
  all — a lane slug and a test name that the "nearest backticked identifier"
  rule picked up. That second case is itself evidence against §3's idea 3: the
  symbol *extractor* is as unreliable as the symbol *resolver*.
- The other 7 are 136–510 lines away.

The mechanism, traced end to end for one case:

```
$ git log --format='%h %ad' --date=short -1 e2acedf5   # brief 548 authored
e2acedf5 2026-07-30
$ git grep -n 'BURN_LIMIT_CAP = ' e2acedf5 -- watch.py
e2acedf5:watch.py:3712:const BURN_LIMIT_CAP = 256;      # TRUE when written
$ git grep -ln 'BURN_LIMIT_CAP' dc739001 -- '*.js' '*.py'
dc739001:client/router.js
dc739001:client/views.js                                # gone from watch.py
```

The citation was correct at `e2acedf5`; #397's client extraction moved the code
out; `check_watch_citations.fix()` then appended `@ dc739001` — a revision at
which the claim is false. **The mechanical repair manufactured false
provenance.** It did what it was designed to do; the design conflated *"this
coordinate participates in a global shift from dc739001"* with *"this
coordinate was correct at dc739001"*, and a reader cannot tell the difference
from the document.

This is #847's own warning realised — its record already says a byte-match
"certified a questions.md citation as a clean +10 shift while the content it
quoted lives in client/style.css and has never been in watch.py at all."

### 2.5 The proposed reuse, measured

`dev/reanchor_citations.py` prints **nothing** today — zero past-EOF citations
in living docs, matching lint's clean row. Its symbol rule has never run
against the certified set. Applying it there (`resolve()` over each of the 19,
scored against the byte-match ground truth):

- 10 of 19 resolve to **exactly one** definition — the rule's success condition.
- **10 of 10 resolve to the wrong place.** 5 land in `client/views.js`; 5 land
  136–510 lines off inside `watch.py`. Exact hits: **0**.

"Exactly one definition in the current production tree" is a *uniqueness* gate,
not a *correctness* gate. After #397 moved ~9,300 lines into `client/`, the
unique definition of a symbol named by a `watch.py` citation is frequently in a
different file — so the rule confidently rewrites `watch.py:3712` to
`client/views.js:476`, repairing the coordinate and destroying the record.

### 2.6 The same disease in a second instrument — and it is red on master now

`dev/check_watch_citations.py` is an example, not the inventory.
`dev/apply_reanchors_i3.py` carries a **74-member** `ANCHORS` table — the
`REVIEWED_DOCS` population that `check_watch_citations.py` deliberately excludes
— and `ReviewedAnchor.resolve()` is the *strongest* form of the anchoring idea
this repo has built: symbol **plus exact multi-line evidence text** plus an
optional Python scope, re-located by exact block search, refusing on missing or
ambiguous matches rather than guessing.

At the base sha, in a clean clone, with nothing of mine applied:

```
$ git -C $C rev-parse --short HEAD        # 55afc4f6, clean tree
$ python3 -m pytest -p no:randomly test_reanchor_citations.py -q
E ValueError: reviewed citation anchors did not resolve:
E   watch.py:5081 (_send) cannot be reanchored: reviewed evidence is missing; drift unknown
E   watch.py:5199 (parsed.path) cannot be reanchored: reviewed evidence is missing; drift unknown
E assert (345, 3) == (342, 0)              # a hardcoded literal in the test itself
2 failed, 13 passed
```

**2 of 74 anchors are dead and master is red.** Two different failure modes in
one file: evidence text that no longer exists (the anchor cannot resolve), and
a test literal — `(342, 0)` — derived from the tree on the day it was written.

Credit where it is due: this instrument fails *honestly*. It refuses rather
than guessing, which is the discipline the filing admires and which idea 3a
below does not have. But it demonstrates the cost that discipline carries, and
it separates two questions this repo has been answering as one: **a living-prose
citation should be re-reviewed when the code it names changes; a historical
record should never need touching again.** `ANCHORS` applies a living-prose
instrument to a corpus that is partly historical, so ordinary code edits
generate reds only a human can clear. That is #914's complaint in a second
incarnation.

*(Out of scope here and not fixed: master is red. Reported to the coordinator.)*

## 3. Candidates — IGC

**Context.** `watch.py` is 7100 lines and grows several times a night under
concurrent lanes. 395 `watch.py:N` citations across 84 docs. 19 are frozen into
a repo-wide guard as an exact multiset located by one global hand-measured
constant. The pins on those 19 are measurably false (§2.4).

**G1** the check survives an ordinary insertion above the cited region with no
human edit · **G2** a zero is loud — "examined nothing" cannot print like
"nothing failed" · **G3** never certifies a claim that is false · **G4** needs
no flag-day rewrite of the corpus while lanes are landing · **G5** retains a
reachable, discriminating red · **G6** an ordinary edit to the cited code does
not oblige a human to re-record the instrument's expectation.

G6 is the goal this corpus specifically needs, and it is why the answer differs
for living prose and historical records. The 19 are historical: they describe a
past tree, so no present-day code change can make them need editing. Any
instrument that says otherwise is asking humans to maintain a record of the
past against the present.

| Idea | All | G1 | G2 | G3 | G4 | G5 | G6 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| 1. Status quo — global `DRIFT`, re-measured by hand | ✘ | ✘ | ✔ | ✘ | ✔ | ✔ | ✘ |
| 2. Per-citation offset from the real diff (#845) | ✘ | ✔ | ✔ | ✘ | ✔ | ✔ | ✔ |
| 3a. Unique-symbol-definition rule (`reanchor_citations`) | ✘ | ✔ | ? | ✘ | ✘ | ✘ | ✔ |
| 3b. Symbol + exact evidence + scope (`apply_reanchors_i3`) | ✘ | ✔ | ✔ | ✔ | ✘ | ✔ | ✘ |
| 4. Content hash / context fingerprint | ✘ | ✔ | ✘ | ✘ | ✘ | ✔ | ✘ |
| 5. Tolerant fuzzy re-location (±N lines) | ✘ | ✔ | ✔ | ✘ | ✔ | ✘ | ✔ |
| 6. Accept drift; auto-re-certify | ✘ | ✔ | ✔ | ✘ | ✔ | ✘ | ✔ |
| 7. **Retire the oracle; assert the property directly** | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |

The decisive errors:

- **1 · G1** measured: 19 → 0 on one inserted line (§2.3). **G3** measured: 0/12
  prose symbols within ±5 of their pin (§2.4). **G6** the constant is
  hand-measured. This is the idea that already deformed a lane's code.
- **2 · G3** a per-citation offset certifies the *offset*, never the *claim*. It
  makes the false certification of §2.4 cheaper to produce, not rarer — and
  #847's record documents the exact live case.
- **3a · G3** measured: 10/10 unique resolutions are wrong (§2.5). **G4** it *is*
  the flag-day rewrite. **G5** 9 of 19 name no resolvable symbol at all, so the
  guard would carry a permanent 47% unadjudicated class over its whole subject.
- **3b — the strongest rival, and it is refuted by measurement, not argument.**
  It is already built, already applied to 74 anchors, and honest by design
  (hence its ✔ on G3, which 3a lacks). **G6** is decisive: §2.6 measures it red
  on clean master, with 2 of 74 anchors dead because the evidence text they
  quote no longer exists. Every ordinary edit to cited code obliges a human to
  re-review and re-record. **G4** applying it to the 19 is the flag-day rewrite
  again. Rejecting 3b is rejecting the best version of the brief's direction,
  on evidence from this repo's own running instrument.
- **4 · G3/G2** same class as 2, with a larger coincidence surface. This repo
  has already paid for it: `DISTINCTIVE_MIN_LEN` exists because 681 blank lines
  in the base revision are byte-identical to each other, and the lessons record
  `check_watch_citations` matching certified lines against a **blank** line.
- **5 · G3/G5** a tolerance window is a coincidence budget. The offsets
  `check_watch_citations.py`'s own comment records for this corpus are
  +0/+10/+22/+83/+227/+228/+262/+347/+348, so a window wide enough to absorb a
  night's movement is ~350 lines and matches nearly anything.
- **6 · G5** decisive and general: a check that rewrites its own expectation
  when it fails cannot fail. It is the degrade-to-zero family in its purest
  form — the expectation stops being a claim and becomes a transcript.

## 4. Recommendation

**Retire the oracle. Assert the property the guard actually holds, keyed to
nothing that a `watch.py` edit can move.**

Bind `Counter[(doc, citation_token)]` over the pinned historical citations —
e.g. `('.dreamwork/handoffs.md', 'watch.py:3654')`, which legitimately appears
twice — and require that each carries an `@ <rev>` whose revision resolves in
git. **No base-revision text, no `DRIFT`, no byte-match, no line arithmetic on
either side.** A `Counter` keeps the duplicate-preservation that #702/#841
bought; dropping `doc_line` from the identity is what makes it immune to a doc
being appended to, which `handoffs.md` is constantly.

**Under the exact event that caused this filing** — one line inserted into the
`COMMANDS` table — **nothing happens.** The check never opens `watch.py`.

**Under the event that would defeat the rejected direction** — a symbol renamed
or defined twice — **also nothing**, because the check never reads a symbol.
Its own defeating event is different and worth stating plainly: *a document
restructured so a citation's token changes or it moves between files.* That is
a human editing the prose, which is exactly the moment a human should be
re-reading the citation. It cannot be triggered by a lane touching production
code, which is the whole of #914.

**What this gives up, said out loud.** It stops asserting that the coordinate
is correct at the pinned revision. That is a gain, not a loss, because the
guard asserts that today and is wrong — but a narrowing that is not stated in
the PASS line and the docstring is itself a degrade-to-zero. The PASS line must
say `pinned, not verified`.

**The false pins are a separate, real defect.** Twelve of 19 pinned coordinates
do not hold at their pinned revision. Do not repair them in the same increment
— repairing them is judgement per citation, which is precisely #847's argument
for why its own paydown cannot be mechanical. File it; §5 does not touch it.

### The degrade-to-zero answer, concretely

Three counts, all derived from the tree at run time and none of them constants:
`docs_scanned`, `citations_seen`, `pinned`. All three print on PASS.

- `docs_scanned == 0` or `citations_seen == 0` → **exit 2**, naming which
  denominator was empty. Today the doc side has no such check: an empty
  `_scan_affected_citations` is caught only *incidentally*, by the multiset
  comparison — and `test_zero_resolved_citations_is_a_fault_not_a_vacuous_pass`
  asserts exactly that incidental path. Make it direct.
- The `(doc, token)` multiset is bound exactly, as today. It cannot silently
  shrink: a missing member prints as `-(doc, token)`.
- No count may be reported without its denominator. `19 pinned` alone is the
  shape that reads identical whether the scan worked; `19 of 19 pinned across
  8 documents, 216 citations seen` cannot. (216 is today's real figure — the
  guard's own class census sums to it: 19 + 5 + 33 + 55 + 104.)

### The migration risk, answered by not having one

The lane's warning — re-certifying 19 entries "would itself drift at the next
merge" — is correct, and it is an argument against ideas 3 and 4, not against
this one. **This recommendation edits zero documents.** The 19 already carry
their pins; the change is entirely inside `dev/check_watch_citations.py`, and
its new expectation is derived from data that no concurrent lane is touching.
There is no flag day to survive.

## 5. The first increment (~20 minutes)

Replace the certified identity and delete the oracle from the *assertion* path,
in `dev/check_watch_citations.py` alone:

1. Add `PINNED_CITATIONS: frozenset[tuple[str, str]]` — the 19 as
   `(doc, token)`, derivable today from the guard's own output.
2. `check()` scans `AFFECTED_DOCS` for `CITATION` tokens; requires every member
   present and followed by `@ <rev>`; requires `git cat-file -e <rev>^{commit}`.
3. Fault at exit 2 on `docs_scanned == 0` or `citations_seen == 0`, naming which.
4. PASS line: `N of N pinned across M document(s); K citation(s) seen — pinned,
   not verified against the pinned revision`.
5. Keep the `DRIFT` class census if it is wanted, but **only under a heading
   that says it is a report and not an assertion**, and remove it from the
   return value. Deleting it is also defensible.

Red-proof both directions, for the lane that ships it:

- **D1a** — strip `@ dc739001` from `.dreamwork/lane-641-report.md:136`;
  the discriminating message must name the document and the token, not a count.
  Reachable today: verified above.
- **D1b — the seam #914 is about.** Build a fixture tree with one line inserted
  into `watch.py` and assert the check **passes**. Assert it against a fixture,
  never by editing `watch.py`, or the proof cannot be re-run.
- **D2 — the open false-green, which must be reported and not closed.** This
  check cannot detect that a pinned coordinate is *false at its pinned
  revision*. Measured: 12 of 19 are. That is the data defect above, and it is
  #847/#880's corpus job, not this one's.

## 6. What this design does not do

It does not adopt symbol anchors for the existing corpus — measured wrong 10
times out of 10 (§2.5), and their strongest implementation is red on master
(§2.6). It leaves symbol naming to **new** prose, where it costs nothing at
write time and is #880's proper subject: *a new citation names a symbol and
does not name a line.* Converting 348 existing ones is #847's paydown, is
judgement per citation, and is not made easier by any anchor scheme in §3.

It does not repair the false pins (§2.4) or the two dead `ANCHORS` (§2.6).
Both are named here so the next lane starts from them rather than rediscovering
them; both need filing.
