
---

## #864 — EXPEDITED delivery class + stop hook — lane `opus-864expedite` (Opus 5)

**VERDICT: complete and verified.** Base `b91bb4a212e932c06d8106a2831920b0d6643df4`;
rebased onto local master **`e25bc236c6d5252ea6cf8603cfc1fde5ebdd2d68`** (clean, no
conflicts; master moved twice while I worked — `fa93d18e`, then `e25bc236`; `origin/master`
was `a7a88df9`, behind, so I used the local branch as the boilerplate requires). Worktree is *outside* the repo, as briefed.

### The deliverable: how the hook and the tick share ONE cursor

**The hook is not a consumer. It never touches the cursor.**

`dev/journal_consume.py expedite` reads the *same* `(cursor, head]` range `pending` reads,
through the *same* `events_since_cursor` projection, and then does two things it must not do:
neither of them.

- **It never calls `advance_cursor`.** Only one caller ever advances, so double-consume is
  structurally impossible and #531's `--through` bound is untouched. Everything the hook
  delivers is *still* in `(cursor, head]`, still listed by the next `pending`, still drained
  by the next `consume` — which is his "it can also be drained like normal from the event
  queue", and it is the property, not a nicety.
- **It never writes the #658 `.pending-read` marker** — deliberately, and this one is easy to
  get wrong. A hook firing between the coordinator's `pending` and its `consume --through N`
  would otherwise rewrite that marker and #712's `through == mark["through"]` guard would
  **refuse the drain**: a hook that silently jams your tick. `test_expedite_does_not_write_the
  _read_coverage_marker_so_the_tick_is_not_jammed` asserts the marker is byte-identical across
  a hook run *and* that the bounded consume still succeeds afterwards.

**Then what stops the double DELIVERY?** The exactly-once proof #527 already wired into the
drain — not the cursor. `expedite` routes each receipt it delivers through the same
`apply.reconcile` against the same applied-ledger, so the marker lands at the pause. When your
tick drains that receipt, `_prove_drained` proves `APPLIED`, writes nothing, and the receipt is
**absent from the `UNAPPLIED` list — the list you act on**. Delivered early, acted on once
(#519/#527). Receipt-id recognition is the mechanism and it was already there.

One hazard, named rather than hidden: if the hook's output never reached the agent, the marker
would still have landed and your tick would print only `applied N` — an instruction swallowed
in silence. So **`consume` now prints an explicit `EXPEDITED <id> <route> already delivered at
a pause — \`show <id>\` for its text` line** for each such receipt (#136). SKILL.md's tick
section says what that line means. Verified live end-to-end (below).

Two smaller rules fall out: a receipt whose proof is `UNKNOWN` (torn applied-ledger) is **not**
delivered by the hook — no marker landed, so delivering it would double up on the tick; it
degrades to BATCHED and the count is reported on stderr (#702). And `consume` has **no cap and
must not get one**: a cursor is a position, so a drain cannot skip a receipt.

### Where the flag lives, and why

**Derived from `(route, payload)`, stored nowhere.** `user_events/delivery.py` —
`EXPEDITE_KINDS = ("do-next",)` + `is_expedited(route, payload)`. The journal is
receipt-authority-only: `exact_payload_bytes` are the bytes he sent, hash-chained, and nothing
is written back. A mutable `expedited` column (or a sidecar keyed by receipt id) would be a
second durable truth about a receipt — the #263 anti-pattern this design already refused once
for the cursor. Three consequences: it is **retroactive** (a `do next` already in the journal
is expedited the moment the class exists — no migration, no backfill); it **cannot drift from
the payload** because it reads it; and it adds **no journal surface at all**, because the kind
is already in the payload — the same string `PREEMPT_KINDS` matches on.

One home, two importers (`watch.py` for the wake gate, `dev/journal_consume.py` for the drain).
A second copy of the tuple in either is the drift the module exists to prevent, so neither has one.

`do-next` moves from PRE-EMPT to EXPEDITED. `delivery-modes.md` had marked that row **PROPOSAL
— "He did not name it — open if he disagrees"**; he now has, and the extension records it.

### The cap, and what "prioritised" means concretely

`expedite --limit N` orders the WHOLE pending range by `(class, ordinal)` — expedited first —
takes the first N, and delivers the expedited members of that slice. Ordinary receipts are
**never** delivered by the hook (that is what keeps the flag meaningful); they are counted on
stderr and wait for your tick. So the claim is literal: **when ordinary receipts hold the lower
ordinals, they still do not take the cap's slots.**

### What enabling it requires of you

Nothing arrives by merging: **`.claude/` is gitignored**, so the hook cannot land by checkout,
and `.dreamwork/expedite` is absent (= off), so `emits_wake` behaves exactly as today. To enable:

    python3 dev/expedite_hook.py install --target /home/xertrov/.llm-general/skills/ud-dreamwork

That writes `.dreamwork/expedite` = `on` **and** merges one Stop entry into
`.claude/settings.json` (merging, never clobbering; a re-install replaces only its own entry).
`status` reports both, and warns if the gate is on with no hook registered. `uninstall` removes
both — they are written together so they cannot diverge. **The hook takes effect in sessions
started after the install**, so it cannot fire mid-tick in your current session.

Know the trade before you run it: **with the gate on, `do next` stops emitting a wake line in
any mode** (his words — "it doesn't interrupt the agent"). Until the hook is installed and a
session restarted, that means `do next` waits for the tick. That is why the gate and the hook
install together, and why the gate is **gitignored** — deliberately against SKILL.md's word
"tracked", because a travelling gate would strip `do next` of its wake on a machine where no
hook exists to deliver it. `file-formats.md` and `.gitignore` both state that reason.

### Red-proof, direction 1 — four injections, all via `dev/redproof.py`

**RED1 — prioritisation.** Seam: `dev/journal_consume.py`, `cmd_expedite`'s sort key. Dropped
the class term (`key=lambda ce: (0 if ce[0] else 1, ce[1].ordinal)` → `key=lambda ce:
(ce[1].ordinal,)`). Discriminating failure, naming which receipts in which order:

```
E  AssertionError: under a cap of 4 the expedited receipts take the slots even though the
   ordinary ones hold the lower ordinals: want ['0645cc6d-6c9e-5f62-a7af-117d9ae66c2e',
   '38387cf8-92be-5f0b-9b99-d5f3d18fc93a', '86dc8ea1-cab3-598d-8b5d-97b0ff15336d',
   '3c4f03e6-4a1d-51d8-9b29-1cf6fb41f725'] (ordinals [7, 8, 9, 10]), got []
```

**RED2 — the cursor, the one you asked me to prove.** Seam: `cmd_expedite`; added an
`advance_cursor` to the live head after delivery, i.e. made the hook a second consumer. **All
five expedite tests went red**, and the third names the exact live failure:

```
E  AssertionError: every seeded receipt must STILL be pending after the hook — the hook
   delivers, the tick drains. want [5 ids], got []; if the expedited ones are missing the
   cursor advanced past unread events (silent loss), and if the list is short the range moved
E  AssertionError: the tick's bounded consume must still succeed after a hook fired
   mid-sequence; got exit 64 (err='consume: --through 3 is at or below the cursor (3); a
   stale ordinal must not rewind or no-op silently — re-read pending and note its head')
```

Note what this shows: **the delivered-set assertion PASSED under that injection.** Only the
surviving-pending-set assertion caught it. That is direction-2 candidate (b), closed by
construction rather than by claim.

**RED3 — the flag.** Seam: `user_events/delivery.py`, `is_expedited` → `command_kind(...) is
not None` (every `/command` reads as expedited):

```
E  AssertionError: expedite must deliver exactly the expedited receipts, in ordinal order:
   want ['b6b9874b-…','4e9479f6-…'], got ['0f9ed4e0-…','b6b9874b-…','aded1ba0-…','4e9479f6-…',
   '4fde01cd-…'] (kinds in seed order: ['add-idea','do-next','maintenance','do-next','add-idea'])
```

**RED4 — the wake gate.** Seam: `watch.py`, `emits_wake`'s expedite branch `return False` →
`return True`: `E AssertionError: True is not false : do-next must not wake, gate on`.

`python3 dev/redproof.py check` (the #795 wording master landed today):

```
history: examined 8 commit(s) since fa93d18eb889 (master) against 3 injected path(s);
         read 23 blob(s), 0 holding a recorded injection.
check: restoration clean — 4 injection(s) registered (role: author); registered bytes are
       restored and absent from the working tree and from this branch's commits.
targets: 4 other target(s), 0 test-like target(s).
tool scope: red-proof semantics and production reach were NOT verified.
```

### Red-proof, direction 2 — all five candidates CONSTRUCTED, all five closed

**(a) Green while the cursor was never advanced (redelivers forever).** For this verb the
cursor is *supposed* never to advance, so the real hazard is the mirror: a delivered-set-only
test passes while the hook re-emits the same receipt at *every* pause. Closed by
`test_expedite_at_a_second_pause_delivers_nothing_again`, which asserts the second run delivers
nothing **and** that the receipts are still pending — so "nothing to say" is proven distinct
from "nothing is there". Under RED3 (flag broken) it fails on its own precondition.

**(b) Green while the cursor advanced PAST unread events.** Constructed as RED2 above.
**Confirmed real**: the delivered-set assertion passed while the events were gone. Closed by
the surviving-pending-set assertion, which is on every one of the five tests.

**(c) Zero-denominator green.** Constructed and **CONFIRMED as a real false green**: with the
flag broken (RED3's injection) and an all-expedited fixture (`["do-next"]*3`), the delivered set
still equals the expected set — the test passes on broken code. Verbatim from my probe:

```
D2-c all-expedited fixture: PASSES (false green) -- delivered 3/3; the precondition my test
asserts is 0 < 3 < 3, which is FALSE here, so the real test refuses this fixture
```

Closed by the runtime precondition `0 < len(expedited) < len(kinds)` in
`test_expedite_delivers_only_expedited_and_leaves_every_event_pending`.

**(d) The cap is never reached.** Constructed and **CONFIRMED as a real false green**: with
*only* the sort key broken and `--limit 100` over a population of 12, the delivered set is
identical and the test passes:

```
D2-d cap=100 over a population of 12: PASSES (false green) -- delivered 6; the precondition
my test asserts is limit < 12, FALSE here
```

Closed by two runtime preconditions, both derived from the fixture rather than written as
literals (the "literal tuned to today's fixture" rule): `limit < len(ids)`, and
`max(ordinary_ordinals) < min(expedited_ordinals)` — the second is what makes a pure-ordinal
implementation deliver **zero**.

**(e) The hook is registered but never fires.** Closed with a **live proof**, since you are
right that it is not observable from inside the turn. I built a throwaway target in `/tmp`
(its own fixture journal seeded with one `add-idea` and one `do-next`, gate on, hook installed
via `install --target`), then ran a **separate headless `claude -p` session** in it with the
prompt *"Reply with exactly the word: ok"*. That session did not reply "ok". It replied:

> *"Received an expedited item containing a test fixture (`THE-EXPEDITED-PROBE-STRING-9F8E`)
> that explicitly says not to act on it — so I've taken no action on it. Nothing else pending."*

The probe string appears nowhere in the prompt, so that answer is only reachable if Claude Code
fired the Stop hook and its `additionalContext` reached the model. The durable side effect
agrees: `.dreamwork/applied.md` was created holding **exactly one** marker —
`<!-- dreamwork:/command:b6b9874b-… -->`, the `do-next` receipt. The `add-idea` receipt has no
marker, so **the flag discriminated on the live path too**, not just in tests.

And the cursor argument held under the live hook. Immediately afterwards, in that target:

```
cursor = 0 / head = 2                      # the hook moved nothing
pending: listed 2 receipt(s) ordinals 1..2 head 2   # both still pending
consume --through 2  ->  consumed 2 event(s) / applied 1 / unapplied 1
UNAPPLIED   0f9ed4e0-…  receipt.created  /command                # the ordinary one: act on it
EXPEDITED   b6b9874b-…  /command  already delivered at a pause — `show b6b9874b-…` for its text
```

That is the whole design in six lines: delivered early, cursor untouched, drained normally,
acted on once, and named rather than swallowed. Temp targets deleted.

### Verification run (all after the rebase)

- `python3 -m pytest test_journal_consume.py` — **34 → 37 passed** (5 new; +2 from master's
  merges since dispatch). Full file.
- `python3 -m pytest test_watch.py -p no:randomly` — **518 passed, 65 subtests passed** in 77s.
  Full file, run twice: once before the rebase and once after, identical both times.
- `python3 -m pytest $(python3 dev/repo_wide_guards.py list)` — **3 passed**. The list printed:
  `test_no_raw_connect.py::test_no_raw_sqlite_connect_in_production_sources`,
  `test_ledger_cli.py::test_the_map_covers_every_verb`,
  `test_check_watch_citations.py::test_reviewed_watch_citation_population_is_still_resolved`.
  (`_VERB_ARGV` covers `dev/ledger.py`'s parser only; `expedite` is a `journal_consume` verb, and
  I checked there is no equivalent map for that tool.)
- `python3 lint.py` — **no ERRORs, `clean (5 warning(s))`**, the documented worktree baseline:
  `tasks.md` ledger-absent, `status.json` absent, `tasks.md` examined-0-entries, `lessons.md`
  580≈622 near-duplicate (pre-existing, in HEAD), `ledger checks` examined-nothing. Complete row
  set compared, not the trailer count.
- The new `check_expedite_gate` was exercised both ways: `'yes'` → `ERROR … is not 'on' … delete
  the file to mean off` with lint exit 1; `on` → `OK expedite on`; absent → no row at all.
- No mutating verb was ever run against `.dreamwork/user-events.sqlite3` or the ledger. Every
  test and probe used a fixture journal under `tmp_path` or `/tmp`. Nothing bound `:35110`/`:35113`.

### One thing I had to fix that was not mine, and it is a merge hazard for you

`test_check_watch_citations.py` went red the moment I added a **three-line import** at
`watch.py:53`. Its `DRIFT` is a global hand-measured constant against `dc739001`, and its own
docstring says why: *"Any net insertion above the cited region breaks this identically whether
it is +1 or +150 — it is exact-match, not a threshold."* That is **#845**, still open. I
re-measured 22 → 25 and the `EXPECTED_CERTIFIED_MULTISET` restores **byte-identically**, which
is what proves the re-measure correct rather than merely quiet.

**This is a live merge hazard tonight:** any other lane that inserts a line above `watch.py`
line ~3476 will collide with my `DRIFT = 25` — not as a textual conflict, but as a red on
master after the second merge. If a sibling lane touches `watch.py`'s top half, expect to
re-measure once more after both land.

### Out of scope, found, NOT fixed — for you to file

**`delivery-modes.md` contradicts `watch.py` on what instant mode means for batched kinds.**
The doc's §"Two rules run through the whole table" states: *"In instant mode, batched kinds are
**still batched** (an `add-idea` does not interrupt even in instant mode)."* The code says the
opposite — `emits_wake` returns `delivery_mode(target) == DELIVERY_DEFAULT` for every non-
pre-empt kind, so in instant mode an `add-idea` **does** wake, and `test_watch.py::
test_emits_wake_matrix_pure` asserts exactly that (`for kind in ("add-idea", "maintenance",
"some-plugin"): self.assertTrue(watch.emits_wake(kind, instant))`). The doc sentence is stale
prose from the pre-ruling draft; the code and its test agree with each other. I left both alone
— correcting the ruling's own text is your call, not a lane's.

---

## DOGFOOD REPORT (#864)

**1 — the brief's `_VERB_ARGV` warning is wrong for this task, and it is stated as a certainty.**
The head says *"`test_ledger_cli.py::test_the_map_covers_every_verb` is in that set and **a new
CLI verb must be added to `_VERB_ARGV`** or it fails; two merges were reverted in one hour for
exactly that class of omission."* `_VERB_ARGV` enumerates **`dev/ledger.py`'s** parser verbs
only. `expedite` is a `dev/journal_consume.py` verb, so the map does not cover it and the guard
passes untouched (verified: 3 passed). I also grepped for an equivalent map for
`journal_consume` — there is none. The warning is right in general and wrong here, and a lane
that obeyed it literally would have added a bogus `expedite` row to a `ledger.py` map and
broken that guard. Suggest the boilerplate say *"a new **`dev/ledger.py`** verb"*.

**2 — `dev/ledger.py get 531` returns a title that is not #531's subject.** It prints
`title: Burndown limit number input too narrow — '128' does not fit visibly` with a body about
the dashboard input, and then a fold note that is entirely about the cursor: *"consume
--through <ordinal> bounds the advance + #526 proof loop to the pending read's head (a89a0bcf,
merge e54d1142)"*. Every brief tonight cites #531 for the cursor contract, and the boilerplate
requires quoting the relied-on line — so the honest quote comes from a fold note attached to a
burndown-input entry. Two tasks look merged into one row. It cost me a double-take and it will
cost the next lane one; worth a ledger check.

**3 — `#845` (the `watch.py` citation `DRIFT` constant) is a live tax on every lane, and it is
larger than it looks.** A **three-line import** at `watch.py:53` reddened
`test_check_watch_citations.py`, a repo-wide guard, with a 19-line multiset diff that reads like
a documentation disaster. The tool's own docstring already knows: *"Any net insertion above the
cited region breaks this identically whether it is +1 or +150 — it is exact-match, not a
threshold."* In practice `watch.py` is now append-only-below-line-3476 for anyone who does not
want to re-measure a global constant, and nothing warns you before you edit. This is not a
complaint about the guard, which is doing its job; it is that **#845 is the highest-friction
open item I hit tonight** and it will keep firing on ordinary work.

**4 — `.claude/` is gitignored here, so "install the hook in `.claude/`" is not shippable as
written.** His ask's *"or similar"* turned out to be load-bearing: a tracked hook is impossible
in this repo, which is what forced the installer design (tracked script + `install` verb that
merges into the gitignored settings). That is arguably the better shape anyway — it is what
makes "ship it so I can enable it deliberately" true by construction rather than by discipline
— but it is worth knowing before the next hook task is scoped as a one-file drop-in.

**5 — SKILL.md's experiment-gate convention says "tracked" and its own example is gitignored.**
*"An experiment ships off by default behind its own **tracked** `.dreamwork/<name>` file — the
`watch-tint`/`run-mode` family"* — but `run-mode` is in `.gitignore` (line 32) and `watch-tint`
is not. The word "tracked" therefore cannot mean "in git", or the cited family contradicts it.
I read it as "a known, documented file with a `file-formats.md` row and a `lint.py` check",
gitignored my gate for a stated reason, and documented the deviation in three places. One word
would fix the convention: drop "tracked", or say "tracked or machine-local per the file's own
travel semantics".

**6 — `dev/redproof.py`'s new #795 wording is a genuine improvement, noted so it survives.**
`check` now says *"restoration clean … tool scope: red-proof semantics and production reach
were NOT verified"* instead of a flat "clean". I would have quoted the old wording as if it
certified my reds reached their seams. It does not, and now it says so. Good change.

**7 — no friction with `dev/redproof.py`'s snapshot protocol, `dev/lane_scratch.py`, or the
worktree-outside-the-repo arrangement.** Four injections across three files, all restored and
verified, snapshots landed lane-privately under `~/.cache/ud-dreamwork/lane-scratch/…/opus-864expedite/`.
Stated rather than omitted, per #136/#671.
