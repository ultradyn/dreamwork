# Questions for the human

## Open

- **2026-07-25 — a question whose bold title is hard-wrapped across two
  source lines, which is normal input.** The loop writes this file at about
  seventy-two columns, so a title that runs long simply continues onto the
  next line and closes its `**` wherever that falls. This body is long
  enough to wrap several times inside a question card, which is what the
  reflow guard measures. Artifact: `.dreamwork/review/fixture-review.html`
  — a backticked review path becomes a link that docks this question beside
  the artifact, which is what the review dock and the route-change guards
  travel to.
  - **Note (human, via watch, 2026-07-25 09:00):** a note from him that is
    itself hard-wrapped over more than one line, so the parser has to keep
    the continuation with its own bullet instead of spilling the tail into
    the body.
  - **Follow-up (loop, 2026-07-25 09:01):** and one from the loop, so the
    page has both authors side by side to distinguish.
- **2026-07-25 — a second open question, so answering the first leaves a
  neighbour to close the gap.** The regroup guard needs at least one card
  below the one it answers, or there is nothing to watch slide up. Some
  more prose so this body also wraps: **bold**, *emphasis* and a
  `backticked/path.md` all appear here so the inline renderer has one of
  each to render.

- **2026-07-25 — a third question, already answered from the page and
  awaiting the loop's fold.** This is the state that vanishes from live
  content the moment the loop does its job, which is exactly why the guard
  cannot depend on live content. A guard whose red light tracks whether
  someone happened to fold a question overnight is not measuring the code,
  and after the second false alarm nobody reads it any more.

  The reflow guard measures line boxes and compares them against the fewest
  a block could use, so every body here is written long enough to wrap
  several times inside a question card. That is not padding: a measurement
  taken over two short paragraphs would be dominated by their ragged last
  lines, and would report a difference between the two renderers that had
  nothing to do with either of them.

  It also compares the same text rendered both ways across a sweep of
  column widths, because the damage a literal line break does depends on
  how much narrower the card is than the seventy-two columns the source was
  wrapped at. At a very narrow column both renderers wrap constantly; at a
  wide one the source almost fits. The interesting widths are in between,
  and they are the widths a real card gets.
  - **Note (human, via watch, 2026-07-25 08:44):** a note written BEFORE
    the answer that sits below it. This is the shape that read as him
    replying to himself (#128): the parse discarded the timestamps and the
    answer's position among the notes, so the render hoisted the answer
    above every note no matter when it was written.
  - **Follow-up (loop, 2026-07-25 08:59):** and the loop's reply to that
    note, still before the answer — so the segment that precedes the
    resolution holds two notes and two authors, and is long enough to be a
    thread that collapses.
  - **Answer (via watch, 2026-07-25 09:02):** an answer that was typed on
    the dashboard and runs onto a second source line.
  - **Follow-up (in-session, 2026-07-25 09:03):** a legacy loop tag, kept
    so the four-form author mapping stays exercised — and, being the only
    note written AFTER the answer, the one segment that stays inline.

## Answered

- **A folded question, filed by the loop.** → resolved (2026-07-25): this
  entry lives under `## Answered`, so it is the third card state and it can
  take notes but not an answer — /answer appends into Open, so the mode
  group is not offered a choice that would fail.
  - **Follow-up (via watch, 2026-07-25 09:04):** a legacy human tag, kept
    for the same reason as the legacy loop one above.
- **A second folded question.** → resolved (2026-07-25): two of these, so
  the Answered section is a list rather than a single row.
