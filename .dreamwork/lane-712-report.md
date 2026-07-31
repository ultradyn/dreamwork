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

(filled in below by the lane as each direction is run)

## Cited issues, with the relied-on line

(filled in below)
