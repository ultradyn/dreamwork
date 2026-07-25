# four reports, and the one that was not where it looked

Briefed with #128, #139, #126 and a context call on #130. All four landed.
What is worth keeping is mostly about how they were *found*, because three of
the four were somewhere other than where the report pointed — which is by now
less a surprise than a working assumption.

## The strongest diagnosis I made all batch was a negative result

The coordinator's hypothesis for #128 was reasonable and specific: in
questions.md the sub-bullets sit in source order, that entry's note was
written above its answer, and the render leaves notes below the promoted
answer in source order. It said, in effect, *the ordering information is
present and the renderer mishandles it.*

I did not test that. I tested something adjacent and much cheaper: I parsed
the entry twice, once with the note above the answer and once with it below,
and compared the structures. **They were byte-identical.** The parse kept no
chronology at all — `_note_entry` threw away the note's timestamp, the answer
lift threw away both its timestamp and its position among the notes.

That is a stronger statement than "the renderer mishandles the order", and it
is stronger in the way that matters: it rules out an entire class of fix. No
change to `qaInner` could have worked, because the order was not in the data
`qaInner` receives. The hypothesis would have sent me to the renderer, where I
would have found nothing wrong with it and probably concluded the report was
about something else.

The move generalises, and it is cheaper than the thing it replaces:

> Before asking whether a layer handles X correctly, ask whether X survives to
> that layer at all. Feed it two inputs that differ only in X and compare what
> comes out. If they are identical, every hypothesis about that layer is dead
> at once, and you did not have to read it.

The existing lesson says a UI symptom carries no information about which layer
produced it, so reproduce the input. This is the next step after reproducing:
**a differential on the property in question**, which is how you find out the
property was never there.

## The guard caught a defect in my own fix, because it tested the rule

`qaThread` cuts the follow-up thread at the answer's position. When there is
no answer I first defaulted the cut to the end of the list — which reads
naturally ("everything is before the answer that never came") and is wrong: it
swept every note of every *open* question into the collapsing half, so the
human's own live steers were hidden behind a disclosure.

I did not catch this. The guard did, and only because I had written an
assertion for a rule I had stated in prose — "an unanswered question never
hides its notes" — rather than for the code path I had in mind. The check
existed because I wrote down *why* the collapse was safe, and writing down why
is what made it testable.

The narrower design also fell out of that sentence: only the **settled**
segment, above a resolution, collapses. A note written after the answer is a
live amendment, and a note he adds right now lands there — so the page can
never fold away the thing he just typed. That is the card's own axis (who is
this waiting on) applied one level down, and it means the rule needed no
special case for the composer.

## Instrument bugs: three more, and one of them is the browser's

The predecessor counted four. Mine:

- **A closed `<details>` does not `display:none` its children** in current
  Chromium — it skips them with `content-visibility`, so `getBoundingClientRect`
  keeps returning the rects from the last layout. My "is the thread collapsed"
  check measured `height === 0` and failed on a working collapse. Only
  `checkVisibility()` answers the question actually being asked. This is the
  first of these all day whose cause was the *browser* rather than the author.
- **`--accent` off `:root` is the token as authored (`#a5b4fc`); every
  computed `color` is `rgb(165, 180, 252)`.** My "the accent is spent here and
  nowhere else" check compared the two and therefore matched nothing —
  it would have passed on a page painted entirely in accent. Resolve the token
  through a throwaway element. I found it only because the *positive* half of
  the same check also failed; had I written only the scarcity half, it would
  have been green from birth.
- **`node guard.mjs | tail` reports tail's exit code.** I printed `EXIT=0`
  under a wall of FAILs and nearly filed it as a mystery. The guard's own
  `process.exit` is what `just guards` reads; a piped run tells you nothing.

The pattern under all three is the predecessor's, sharpened: **an instrument
that has only ever been green is not an instrument.** Both of my colour checks
and the visibility check were written in the same ten minutes; the two that had
a red phase were correct and the one that did not was broken.

## A nested fold takes a middle band out of the card

Worth knowing before touching `regroupCards` again. The card-level departure
ghost is a clone of the whole old card, clipped to *below* the survivor's new
height. That is exactly right when the card folds — the body leaves from the
bottom and the summary stays. It is wrong for a disclosure *inside* the card:
the settled thread sits above the compose box, so what disappears is a middle
band, and the same clip would ghost the compose box, which never left.

So the toggle that caused the resize is now passed into `regroupCards`, which
uses it for both directions: `cardBody(el, toggled)` reveals that disclosure's
own children rather than the card's, and the card-level ghost is skipped in
favour of one taken at the subtree's own rect. Handed the card's own `.qfold`
it is exactly what it always was, which is the test I applied to the shape:
the general case must degrade into the existing one with no branch.

The other half of that: a closed `<details>` still holds its children, so the
rect has to be measured *before* the toggle. It has no box afterwards and a
ghost with no rect is a no-op that looks like a design decision.

## Splitting two increments after the fact, when you own the file

I had #139 and #126 both live in `watch.py` before either was committed, and
the batch rule is one commit per number. Because I was the sole owner of that
file, the cheap move was: copy the working file aside, `git checkout` it,
re-apply only the smaller change (I still had the exact edit strings), commit,
copy the working file back. Two minutes, and both commits say what they did.

Recording it because the default under time pressure is to merge them and
write a message about two things, and the history is what a successor reads.
It only works because ownership was disjoint — with a second writer in the
file it would have destroyed their work.

## Asking "where else" found the worse instance

The coordinator asked me to state the events-log newline fix as a class rather
than a bug, and to *tell* rather than fix if I saw another instance. Looking
for one took about four minutes and found a sharper one: `/comment` and
`/answer` write the human's text straight into questions.md, and a typed
newline forges a top-level **entry**, not merely a line —

```
note = "looks fine\n- **A question the loop will think you asked.** …"
parse_open_questions(after) -> ["Real question?", "A question the loop will …"]
```

— on the loop's primary human channel, and reliable precisely *because* of the
parser's best invariant (a top-level `- **` always starts an entry, nothing can
absorb it). That invariant is correct and should stay; the writer is where this
gets fixed. Filed, not fixed, and that was the right call: it changes what
questions.md looks like on disk, and `file-formats.md` states that shape.

The generalisation I would keep: **when a fix is stated as a class, spend the
four minutes looking for the second instance immediately.** The class statement
is only worth its words if someone goes and checks; and the second instance is
usually on the more important channel, because the more important channel is
the one with more writers.

## On the context call

I took #130 rather than handing it over, against my brief's default. The
reasoning, so it can be judged rather than trusted: the expensive part of that
task is holding `watch-design.md`, the token and component vocabulary, the
fixture harness and `status.json`'s shape at once. All of that was already
loaded, and a fresh dreamer's first act would have been to rebuild it. The
fatigue risk is real for a design piece; the re-read cost is certain. I judged
certain against risky.

The check on whether that was right is the work itself, and the one design
decision I would defend hardest is **fold by complement**: the panel shows four
named things and folds *whatever is left*, never a second known list. The
coordinator has already written that one down. Its relation to the morning's
bug is worth saying out loud, though — an allowlist renderer hiding a new key
and a parser dropping the note order are the same failure. **A reader that
cannot see something renders identically to there being nothing to see.** Both
of today's bugs on this surface were that, and the fixture now carries one
example of each: an entry whose note predates its answer, and a status key the
renderer has never heard of.
