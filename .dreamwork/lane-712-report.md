# lane-712 — "the marker proves a line was PRINTED, not SEEN"

## Verdict, up front

**"Seen" cannot be established from inside a process that only controls
"printed", and this lane does not claim to have established it.** What it lands
is two things that are achievable, and it says which is which:

1. **A refusal that closes the traced loss.** `consume --through N` now refuses
   when `N` is *below* the head of the read on record, not only above it. The
   traced command — `pending` prints 96..99, operator holds 97..99, `consume
   --through 96` — is refused, and the message names ordinal 96. This proves
   *the bound came from the read on record*. It does not prove anyone read it.
2. **A coverage statement on a channel the truncation does not touch.**
   `pending` writes `listed 4 receipt(s), ordinals 96..99` to **stderr**, so
   `pending | tail -3` truncates the listing and still prints the count and the
   full range. This makes a truncated view *visibly* inconsistent. It is a
   **visibility** property, not a binding one — see the open case below, which
   is honest about the fact that a printed inconsistency has already been
   ignored once in this loop's history.

Neither establishes that a reader SAW anything. The property remains
**printed**, plus **the bound agrees with the most recent listing**.

---

## The IGC

### Context

`dev/journal_consume.py` is the loop's per-tick drain. `pending` lists
`(cursor, head]` one line per receipt and records the head ordinal it printed
into a `.pending-read` sidecar; `consume --through N` drains `(cursor, N]` and
refuses if `N` outruns that marker (#658).

The loss: the operator's *view* of `pending`'s stdout is truncated by a shell
pipe. `tail` removes the **oldest** lines — which are exactly the ordinals at
the **bottom** of the range a subsequent consume advances over. The marker
records only the **head** — exactly the part `tail` preserves. So the marker is
aligned with the surviving half of the output and blind to the removed half.

Note the asymmetry, because it narrows the problem usefully: **`head`-style
truncation cannot lose anything.** If the operator sees 96,97,98 and consumes
`--through 98`, ordinal 99 stays pending and is re-listed next tick. Only
truncation-from-the-top loses data, because only it hides ordinals *below* the
bound.

This is the loop's hottest path — every tick, forever (#612). Bare `consume`
must remain a non-wedging escape (#658's deliberate design).

### Goals (binary)

- **G1** — closes the traced loss: `pending` lists 96..99, operator holds
  97..99, `consume --through 96` does not silently advance. Pass = a refusal
  that names ordinal 96.
- **G2** — cannot wedge the tick: an escape a coordinator can reach at 3am
  without reading the source, and it is not "delete the marker file".
- **G3** — no added ceremony on the normal path: the tick case is no longer to
  type than `consume --through <head>` (#612).
- **G4** — not dischargeable by reflex: the mechanism cannot be satisfied by a
  one-line shell habit that reintroduces the loss (#644 — discipline fixes are
  the ones that fail).
- **G5** — honest: "printed" must not render identically to "seen" (#136).
- **G6** — does not weaken #531: an event landing between the read and the
  consume still stays pending.
- **G7** — closes the *class*, not just the instance: also catches the natural
  variant, where the operator holds 97..99 and consumes `--through 99` (the
  head, which `tail` preserved), advancing over 96 unseen.

### The matrix

| Idea | All | G1 | G2 | G3 | G4 | G5 | G6 | G7 |
|------|:---:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| I1 do nothing (refuse the premise) | ✘ | ✘ | ✔ | ✔ | ✘ | ✔ | ✔ | ✘ |
| I2 `--through` must EQUAL the read head | ✘ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✘ |
| I3 in-band trailer on stdout | ✘ | ✘ | ✔ | ✔ | ✘ | ✔ | ✔ | ✘ |
| I4 coverage line on **stderr** | ✘ | ✘ | ✔ | ✔ | ✘ | ✔ | ✔ | ✘ |
| I5 cite the first listed receipt id | ✘ | ✔ | ✔ | ✘ | ✘ | ✔ | ✔ | ✔ |
| I6 `pending` writes the listing to a file | ✘ | ✘ | ✔ | ✘ | ✘ | ✔ | ✔ | ✘ |
| I7 list newest-first so `tail` keeps the safe end | ✘ | ✘ | ✔ | ✔ | ✘ | ✔ | ✔ | ✘ |
| I8 accept and detect afterwards | ✘ | ✘ | ✔ | ✔ | ✘ | ✔ | ✔ | ✘ |

**Zero survivors.** Per the method that is not a failure of the ideas — it is a
finding about the goals. The binding goal is G7, and G7 is where the argument
actually lives.

### Why G7 is not achievable in-process, and the proof of it

Any value `pending` prints falls into exactly one of two cases under a
truncation:

- **It survives the truncation.** Then a truncated reader can relay it, so
  requiring it proves nothing about coverage. (`tail` preserves the end, which
  is why every trailer — I3, and the coordinator's own candidate — fails as a
  *proof*, however well it works as a *signal*.)
- **It does not survive.** Then an honest reader who used that truncation
  cannot produce it either — which is the point: requiring it *binds*. But the
  only region guaranteed removed by `tail` is the **top** of the output, so the
  required value must be the identity of the **first listed line** — a receipt
  id, since the first *ordinal* is mechanically `cursor + 1` and derivable
  without reading anything.

That is I5, and it is the only idea in the field that passes G7. So G7 is
achievable — at I5's price. The rest of this argument is about that price.

### The one I reject most reluctantly: I5

I5 (`consume --through 99 --saw <receipt-id-of-the-first-listed-line>`) is the
only mechanism that actually binds the class. I reject it on **G3 and G4 in
combination**, which is one decisive error and not two survivable ones:

- Alone, G3 (ceremony) would be survivable — one extra token per tick is not
  much, and correctness is worth some ceremony.
- Alone, G4 would be survivable — a bypass that requires deliberate effort
  still catches the accident, and the accident is the whole threat model here
  (#658 is titled from "I did this to myself and caught it only by luck").
- Together they are decisive: the bypass is *`--saw $(… pending | head -1 | cut
  -f1)`*, a one-liner that any agent — including this loop's own coordinator —
  will write the first time the flag is inconvenient, at 3am, on the path that
  runs every tick. At that point the loop is paying the ceremony forever and
  buying nothing, and worse, the green exit now *looks* like proof of coverage.
  A mechanism whose most likely steady state is "satisfied mechanically while
  proving nothing" is worse than no mechanism, because #136's rule cuts against
  it: "you read everything" and "I cannot tell what you read" would render
  identically, and the identical rendering would be the reassuring one.

The reluctance is real: I5 is the only correct answer to the question as asked,
and I am rejecting it for a reason about people rather than a reason about
mechanism. I record it so it can be reopened if the ceremony ever becomes free
— e.g. if the drain is ever driven by a wrapper that does the read and the
consume in one process, at which point the citation costs nothing because no
human transcribes it. **That is the shape that actually closes #712, and it is
out of this lane's volume.**

### Why the others are refuted

- **I1 (refuse the premise — discipline plus #658's existing refusals).** ✘ G1:
  the traced command still succeeds today. ✘ G4: it *is* the discipline fix, and
  the loop's own history is the evidence against it — the coordinator consumed
  blind once and lost a human instruction, recovered only by hand-written SQL
  (#658). This is the legitimate answer the brief offers, and it is refuted by
  one line of code being cheaper than the rule it replaces.
- **I3 (stdout trailer).** ✘ G7 as above, and dominated by I4 at the same price:
  it rides the very channel being truncated, so whether it survives depends on
  *which* truncation was used (`tail` keeps it, `head` and `grep` remove it),
  and it puts a non-event line into a record documented as "one line per event,
  receipt id first" that `_pending_ids`-style parsers split on tabs.
- **I4 (stderr coverage line).** ✘ G7 — it states the inconsistency, it does not
  prevent acting on one. Kept anyway; see below.
- **I6 (listing to a file).** ✘ G3 (an extra read step every tick), ✘ G7 — it
  moves the truncation rather than removing it: the operator can `tail` the file
  exactly as they tailed the pipe. The brief already flagged this distinction
  and it holds.
- **I7 (newest-first).** ✘ G7 — it does not make anything visible, it swaps
  which pipe is dangerous: `tail` becomes safe (the operator holds the oldest
  ordinals and consuming through the max they saw is lossless) and `head`
  becomes the loss. It also inverts the chronological order of human
  instructions in the one output where reading order is meaning.
- **I8 (detect afterwards).** ✘ G1/G7 — there is no later step that would
  notice; the cursor is a scalar and consumption leaves no per-ordinal record of
  what was claimed to have been read.

### The decision

**I2 and I4 are not rivals — they close different holes and compose**, which
the method explicitly allows. I2 is a refusal (it binds the traced instance);
I4 is a signal (it makes the class visible on an unpipeable channel). Together
they hold {G1, G2, G3, G5, G6} and state honestly that G7 is open.

**Why strict equality costs nothing real.** I2 removes the ability to consume
*part* of what a read listed. That capability has no genuine use here, and this
is the argument that made the decision cheap: **the alternative to a partial
consume is no consume, and no consume loses nothing** — an unadvanced range is
re-listed in full on the next tick. So there is nothing a partial drain buys
that skipping the drain does not buy more safely, and no `--partial` escape
hatch is needed (one was considered and dropped: it would be the flag an
annoyed agent adds by reflex, which is G4 again).

---

## What changed

- `dev/journal_consume.py`
  - `consume --through N` gains a fourth named refusal (#136's rule: each zero
    state names itself): `N` **below** the head of the read on record. The
    message names the ordinals the consume would advance the cursor over,
    names the head the read actually printed, and names both escapes.
  - `pending` writes a coverage line to **stderr**: `pending: listed N
    receipt(s), ordinals L..H (consume --through H)`. Quiet on empty, as the
    verb's contract requires. stdout is byte-for-byte unchanged, so the
    machine-parse contract ("one line per event, receipt id first") holds.
  - `_load_pending_read` now validates the marker's *shape*, not just that it
    is JSON. Its docstring already claimed a corrupt marker degrades to the
    named absent refusal; a parseable-but-malformed marker (`{}`) raised
    `KeyError` instead. Same guard, same commit — a guard whose subject may not
    exist must degrade to a reading, never throw.
- `SKILL.md` — the tick habit: `--through` must be *the* head of the read on
  record, four refusals not three, and the stderr coverage line.

## Red-proof

### Direction 1 — three injections, each red on its discriminating message

All via `dev/redproof.py begin/restore`; never `git checkout` (#349). No commit
was made while a file was sabotaged.

**RED 1 — the traced loss itself.** Injected: `if through < mark["through"]:` →
`if False:  # INJECTED` (the pre-#712 shape, which bounded `--through` from
above only). `test_consume_through_below_read_head_refuses_naming_the_lost_ordinal`
went red **on the loss, not on a count**:

```
AssertionError: consume --through 1 must REFUSE: the read on record printed
through 4, so a bound of 1 came from an older or truncated view and would
advance past an unseen ordinal; got exit 0
(out='consumed 1 event(s)\napplied 0\nunapplied 1\nUNAPPLIED\t0f9ed4e0-…')
assert 0 == 64
```

`consumed 1 event(s)` with exit 0 **is** the traced loss reproduced — the
ordinal the operator's `tail` removed was drained and the cursor advanced.
Whole file: **1 failed, 26 passed** — nothing else binds it.

Restored, the refusal reads (real output, from the test's own run):

```
consume: --through 2 is BELOW the head of the read on record (3) — a bound
that did not come from that read came from an older or truncated view of it,
and ordinals [1, 2] would be advanced past on that basis. Re-run `pending` (do
not pipe it through `head`/`tail`) and consume --through 3; or consume nothing
this tick — an unadvanced range is re-listed in full, so skipping loses
nothing. Bare `consume` (no --through) is never gated by the marker.
```

It names the ordinals at stake, the head of the read on record, and two
escapes — neither of which is "delete the marker file".

**RED 2 — the channel.** Injected: the coverage statement's `err.write(` →
`out.write(`, i.e. **exactly idea I3**, the in-band trailer this design was
chosen over. `test_pending_coverage_line_reaches_stderr_when_stdout_is_truncated`:

```
AssertionError: stderr must state the count the operator can compare against
the 2 lines they hold; got ''
assert 'listed 4 receipt(s)' in ''
```

Note **"2 lines they hold"** — the same `tail -3` that gave the operator three
event lines now gives them two plus the trailer. The in-band form both rides
the truncated channel and eats one of the operator's remaining lines. The
assertion order was changed *before* this run (commit `a5c2822c`) precisely so
the red lands on that property rather than on the parser contract; run first,
the injection also reds **three pre-existing tests the lane did not write**
(`test_pending_lists_events_since_cursor`, `test_pending_does_not_advance`,
`test_consume_refuses_on_corruption_cursor_unmoved`), which independently bind
"stdout is exactly the event record".

**RED 3 — the marker shape guard.** Injected: the `isinstance` checks in
`_load_pending_read` → `return mark`.
`test_malformed_marker_degrades_to_the_named_absent_refusal` reds on the
**production crash**, not on a reading of the helper:

```
>               if mark["journal_id"] != journal_id:
E               KeyError: 'journal_id'
dev/journal_consume.py:557: KeyError
```

The assertion order was changed first (commit `fa8ace4d`) so the black-box
consequence is what fails; the white-box `_load_pending_read(...) is None`
assertion now runs *after* it, so the test's scaffolding is not standing in
front of the defect. Independently confirmed outside pytest under the same
injection: `RAISED KeyError: 'journal_id'` from `cli.main(["consume", …])`.

**Gate**, run before reporting and after the rebase:

```
history: examined 5 commit(s) since 255d6427e564 (master) against 1 injected
path(s); read 5 blob(s), 0 holding a recorded injection.
check: clean — 1 injection(s) registered, all restored and absent from the
working tree and from this branch's commits:
  dev/journal_consume.py (sha 90a3bfcec2b2, hint: 'return mark  # INJECTED: …')
EXIT=0
```

(It registers one *path*, not one injection — three injections were made into
that path in sequence, each `begin`/`restore`d, and it records the latest.)

### Direction 2 — the cases this fix still gets wrong, constructed and RUN

Both on the **fixed** code, on a throwaway fixture journal in `/tmp`. The live
`.dreamwork/user-events.sqlite3` was never opened by anything in this lane.

**(a) The natural `tail` variant — OPEN, and it is the more likely form.**
The traced command took `--through` from an *earlier* read; the obvious thing to
do with `tail -3` is take the head off the last line you can still see — and
`tail` preserves the end, so that head is the *real* head:

```
pending printed 4 lines; the operator holds 3
stderr (survives the pipe): pending: listed 4 receipt(s), ordinals 1..4 (consume --through 4)
the head they CAN still see (tail keeps the end): ord=4

consume --through 4  ->  exit 0
stdout: consumed 4 event(s)
cursor now: 4
CONSUMED UNREAD: ord=1 — printed, never in the operator's hands, and NOTHING refused.
```

Every check passes: the bound equals the head of the read on record, the marker
matches, #531's bound holds. **Ordinal 1 is consumed unread.** The only signal
is the stderr line saying `listed 4` against the 3 lines in hand — a thing to
*notice*, not a thing that binds. And this loop has already demonstrated that
noticing does not happen: in the original incident `consume --through 96`
printed `consumed 1 event(s)` immediately after a `pending` whose output filled
three lines, and that discrepancy was not caught either. **I am claiming
visibility, and visibility has failed here before.** Only I5 closes this, at the
price argued above.

**(b) "Read the bytes" is not what `pending` delivers at all — OPEN.**
The brief asks whether reading the bytes is the same as seeing. On this path the
weaker question bites first: `pending` never shows the bytes. Measured on a
189-byte payload carrying two separate requests:

```
--- preview case: payload is 189 bytes ---
f993874d-…  receipt.created  /command  ord=1  189B  {"kind": "add-idea", "text": "implement via subagent; we should be able to archi…

second request visible in the pending line? False
```

So the honest statement of what this lane's answer proves is weaker than
"printed" even: **the ordinal was printed, and an 80-char rendering of its
payload was printed.** Nothing here proves a reader saw the line, and nothing
here proves the content crossed the boundary at all — `show <id>` is the verb
that delivers the content and nothing requires it.

One thing measured that is *better* than the ledger's note on #712 assumed: the
"there is more here than you can see" mitigation it proposes (mark lines whose
payload exceeds the preview) **already exists in-band** — the line carries
`189B` and the preview ends in `…`. Both present in the output above. That
mitigation does not need building; what it does not do is make anyone follow it.

## Cited issues, with the relied-on line

- **#658** (landed) — the relied-on line, from the SKILL.md clause it landed and
  which #712 quotes: *"the marker proves every line was **printed**, not that
  every line was **seen**, so `pending | tail` still defeats it — the discipline
  and the refusal are both needed."* And from the ledger entry: *"Marker LANDED
  at eb012756 (lane-658drain) … THE ORIGINAL FAILURE IS NOT CLOSED — traced at
  the gate: pending prints 96..99, marker through=99, consume --through 96 is
  inside the range, no refusal, receipt consumed unread."* Both of its closed
  cases are preserved: consuming with no prior read
  (`test_consume_through_absent_marker_refuses_named_bootstrap`) and consuming
  *past* what a read listed (`test_consume_through_refuses_when_read_was_truncated`)
  are untouched and green.
- **#531** — the `--through` bound. Relied-on line (its ledger fold note):
  *"consume --through <ordinal> bounds the advance + #526 proof loop to the
  pending read's head (a89a0bcf, merge e54d1142); both edge refusals EX_USAGE 64
  pre-read."* Not weakened: `test_consume_through_bounds_advance_leaves_late_event_pending`
  passes unchanged — it consumes `--through H` where H is the head its own
  `pending` read reported, which is exactly what #712 now *requires*, and the
  late event still stays pending. #712 tightens the same bound in the other
  direction and touches neither edge refusal.
- **#136** — the rule stated as the defect. Relied-on line: *"THREE zero-states,
  not one: missing is a quiet warning …; present-but-unparseable is a fault and
  must look like one; genuinely empty is #141's calm grey."* Applied twice here:
  the fourth refusal names its own case (`BELOW the head of the read on record`)
  rather than sharing #658's "never listed" wording, and the malformed-marker
  fix is that rule exactly — a marker that is present but shapeless was
  rendering as an exception, not as a named state.
- **#671** — a check that examined nothing must not read as passing. Relied-on
  line: *"the count is real (420 commits WERE examined), the 'nothing to review'
  is false, and the two together read as a positive all-clear."* Applied: every
  new assertion is preceded by a derived precondition, and the load-bearing one
  is `assert lost <= mark["through"]` — without it the direction-1 test would be
  re-proving #658's already-closed case and would pass on unfixed code. The
  channel test derives `held` from the real output and asserts `len(held) < n`
  before asserting anything about stderr.
- **#612** — volume, and the cost of ceremony on a per-tick path. Relied-on
  line: *"A report nobody can skim is a report nobody reads."* Applied: the
  normal tick did **not** get longer to type. `--through <head>` is what SKILL.md
  already prescribed; the only change is that the value must be *the* head, and
  `pending` now prints the exact command, so the step went from transcription to
  copy-paste. Cost on the hot path: **one line of stderr per non-empty read**,
  and zero on an empty one. The rejected I5 would have added a token per tick
  forever, which is the #612 argument doing real work rather than decorating the
  report.

## Rebase

Rebased onto local `master` at `255d6427` (`docs(#720): a green reading is
evidence only if you know what produced it`) — read with `git rev-parse master`,
not from the brief. Five commits replayed cleanly, **no conflicts**; the
line-anchored `grep -nE '^(<{7}|>{7}|\|{7}|={7}$)'` over the tree returns
nothing. `redproof.py check` re-run after the rebase (output above) because the
rebase rewrote every sha it scans.

## Verification

- `python3 -m pytest -q test_journal_consume.py test_watch.py` (the two files
  this change touches) → **502 passed, 1 deselected, 57 subtests passed** in 68s,
  post-rebase. `test_journal_consume.py` alone: **27 passed** (24 pre-existing,
  unchanged, + 3 new).
- `python3 lint.py` → `clean (6 warning(s))` — the six are the known lane-worktree
  warning that the gitignored ledger store cannot travel (#611), not findings.
- No browser guards: non-UI lane (#666). No ports bound. Load at the time of the
  suite run: 23-27.
- **The live journal was never touched.** Every run used a `tmp_path` or
  `tempfile.mkdtemp()` fixture with an explicit `--journal`.

## Out of scope — found, not fixed

1. **The `.pending-read` sidecar has no `file-formats.md` row.** It is a file the
   loop writes and a tool parses, which this repo's conventions say must have its
   shape stated there and checked by `lint.py` in the same commit. #658 landed it
   without one, and #712 deepens the reliance on it (the marker is now compared
   for equality, not just as an upper bound) without changing its shape. Worth a
   row; not this lane's change to make silently.
2. **Ledger entry #531's title is about something else.** `dev/ledger.py get 531`
   returns *"Burndown limit number input too narrow — '128' does not fit
   visibly"* with a fold note that correctly describes the `consume --through`
   bound. The brief cites #531 as "the `--through` bound itself" and the note
   agrees; the title does not. One of them is attached to the wrong id.
3. **The real close for #712 is a wrapper, not a flag.** Stated in the IGC: if
   the read and the consume ever run in one process, the coverage citation costs
   nothing because no human transcribes it, and I5's decisive error evaporates.
   That is a different shape of change from anything in this lane's volume.
