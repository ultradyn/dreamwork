# Lessons

Newest last, each pointing at its source dream. Not a log — only things
that should change future behavior.

**Shape: a bolded claim you could read on its own, then the concrete case
that earned it.** The claim keeps the file skimmable; the evidence stops
it reading as platitudes. Prune a lesson once it has graduated into a
guardrail or a check — if `lint.py` or a guard now enforces it, it does
not need to persuade anyone. (Entries above the 2026-07-25 batch predate
this shape and convert opportunistically.)

- Verify before dismissing a subagent's contradiction — its fresh look may
  beat your cached fact. (2026-07-25-0210-dogfood-reflection)
- Facts that gate behavior (git-ness, backends, authorization) go stale —
  recheck them from the world at reconcile, not from memory.
  (2026-07-25-0210-dogfood-reflection)
- Watch for over-investing in one finished sub-feature (polish, extra
  mechanisms) while primary paths and principles stay unexercised — it's the
  make-work gradient in miniature. (2026-07-25-0244-alignment-roll-py-hotspot)
- In an alignment review, "ungated polish" may be human-authorized surface
  whose trail lived only in chat — check before recommending a trim; the
  durable fix for chat-authorized work is a verifiable in-band provenance
  note, not a revert. (2026-07-25-0310-alignment-pass2-clean)
- For a visual/WebGL task judged by headless screenshots, expect flaky
  headless-GL (SwiftShader) context loss — a blank render is likely the
  driver, not your shader. Add a webglcontextlost/restored rebuild handler
  and reload-on-loss capture; measure pixels rather than trusting the eye.
  (2026-07-25-0445-dreambg-shader-tilt-shift)
- For morph/dissolve transitions: put ALL softening (blur + displacement)
  inside ONE SVG filter and drive its attrs per-frame from rAF; keep only
  opacity/transform on CSS transitions — you can't CSS-tween a `filter`
  containing a non-interpolable `url(#…)`. Clear the inline filter at rest
  for a crisp, zero-cost settled state. Cost scales with filtered-layer
  area, not turbulence octaves. (2026-07-25-0623-dream-dissolve-transition)
- For a shared-element FLIP that crosses a full view-swap, lift the hero
  above the swap's dissolve (z-index, higher opacity floor, less own-blur)
  and make its glide OUTLAST the dissolve — else it inherits the page mist
  and reads as "page changed + thing appeared", not "thing travelled".
  (2026-07-25-0646-review-morph-and-frametime)
- Dev-overlay frametime that's inter-frame delta sits at vsync regardless
  of cost; wrap draw() in performance.now() for the real signal. Measured:
  the ambient shader is ~0.1-0.3ms/frame — transition dips are SVG-filter
  compositing, not the shader. (2026-07-25-0646-review-morph-and-frametime)
- Global single-key hotkeys must ignore keystrokes when a text field is
  focused — add the guard WITH the first text input, not after the bug
  report; the conflict is invisible until an input exists.
  (2026-07-25-0713-palette-worldspace-batch)
- A detached/floating control window (Document-PiP, window.open) must carry
  its own identity (what it steers), because the context that spawned it is
  gone and several may be open. (2026-07-25-0713-palette-worldspace-batch)
- Wall-clock shader phase must be range-reduced (e.g. %86400) or highp float
  precision dies at epoch magnitudes; world-space window anchoring needs
  BOTH a screen-position domain offset and shared phase, or seams break.
  (2026-07-25-0713-palette-worldspace-batch)
- For an enter animation, the start state must SNAP not transition — set
  `transition:none` on the start-state class, reflow, then remove it next
  frame; with an always-on transition, adding the class animates *toward*
  the start value and it never gets there (looks like a pop-in).
  (2026-07-25-0806-question-flow-and-reload-batch)
- A server generation on /mtime (client reloads when it changes) fixes stale
  tabs on any restart for free; `--autoreload` = os.execv on source-mtime,
  socket is close-on-exec so the port frees. Land dev-loop speedups early.
  (2026-07-25-0806-question-flow-and-reload-batch)
- Prefer impossible-by-construction over validation: parse so a sub-bullet
  can never be mistaken for an entry; key list rows by index not a
  DOM-round-tripped title. (2026-07-25-0806-question-flow-and-reload-batch)
- Busy-dreamer mailboxes deliver between turns, so coordinator orders
  routinely cross dreamer reports — write orders idempotently, expect
  "DONE" lines that predate them, and re-state once on the next idle
  rather than assuming receipt. (coordinator, 2026-07-25 wrap)
- Session-scoped task backends lose the queue *and* its ids on restart —
  the ledger (`.dreamwork/tasks.md`) is what makes task numbers safe to
  cite from docs, plans, and commit messages. (coordinator, 2026-07-25 restart)
- `git add -A` while a dreamer holds the same tree silently commits its
  in-flight edits — stage by explicit path whenever work is parallel.
  (coordinator, 2026-07-25 restart)
- Durable shared state wants a single writer: naming an owner is cheap and
  invisible to omit, and the race only appears under fan-out — when nobody
  is watching. (2026-07-25-0832-ledger-coherence)
- Write a migration's "How to apply" against the broken target that
  motivated it, not the healthy one you are sitting in.
  (2026-07-25-0832-ledger-coherence)
- Never let selection depend on a channel you have not read back: Claude
  Code's TaskGet returns subject/status/description only, so task
  `metadata` is write-only there. (2026-07-25-0832-ledger-coherence)
- An id that is already durable upstream beats minting a new one: the
  ledger holds only work the loop originated, or a busy forge floods it.
  (2026-07-25-0832-ledger-coherence)
- A fix stated in terms of its own implementation breaks the other
  implementation: "the ledger" had to become a concept (durable record)
  before backend-neutral lines could safely use the word.
  (2026-07-25-0832-ledger-coherence, verify pass)
- Re-deriving an item from upstream never re-derives the loop's progress
  on it — external identity is enough until work starts, not after.
  (2026-07-25-0832-ledger-coherence, verify pass)
- Redefining a term silently rewrites every rule that uses it: after
  turning "the ledger" into a concept, the rules resting on it had to be
  re-read — one had quietly started saying forge issues could never be
  selected. (2026-07-25-0832-ledger-coherence, final pass)
- Mounting a SECOND instance of a surface (second window, second render) is
  the cheapest audit of the first: it falsifies coordinate, normalisation and
  sign assumptions that are unfalsifiable while N=1. Budget a duplication
  feature for finding bugs in the original. (2026-07-25-0846-composer-batch)
- A passing pixel/visual comparison proves nothing until you show it FAILS on
  the old code — temporarily restore the bug and re-run. Also assert the plate
  has detail, or "identical" is satisfied by "identically blank".
  (2026-07-25-0846-composer-batch)
- To compare a time-varying visual across captures that can never be
  simultaneous (two frames, two documents), freeze the clock via
  `addInitScript` overriding `Date.now` rather than trying to synchronise
  them. (2026-07-25-0846-composer-batch)
- `position:fixed` is NOT viewport-relative when an ancestor has
  `transform`/`perspective`/`filter` — that ancestor becomes the containing
  block, so rect-derived coordinates need its origin subtracted.
  (2026-07-25-0846-composer-batch)
- A judgement call raised only in chat is not recorded: the ask-discipline
  covers questions the loop *asks*, and a "here is a change you did not
  request, tell me if you hate it" is one of those. Caught in my own work
  hours later. (coordinator, 2026-07-25)
- A rule that asks an agent to *state* something binds only where that
  something is durably carried to it — check the carriers before trusting
  the rule. "Name the chain" shipped with its middle link living nowhere
  readable. (2026-07-25-0926-goals-coherence)
- Editing a file whose structure is data (questions.md entries, ledger
  lines) needs a structural check, not a glance: count the entries before
  and after. An Edit whose old_string spans an entry boundary can drop the
  next entry's title and silently merge two records. (coordinator,
  2026-07-25 — I did this to a live human-facing question.)
- A CSS class is either a style hook or an element address, never both:
  sharing an addressing class turns a guaranteed lookup into a
  first-match guess that stays correct until the container holds two of
  them, then fails silently. (spike #115, docs/spikes/)
- A UI symptom carries no information about which LAYER produced it:
  reproduce the input before believing the diagnosis in the report. Three
  reports today named the wrong layer, each confidently and reasonably; all
  three were falsified in under five minutes.
  (2026-07-25-1010-question-surface)
- When the READER learns a new way to name something, go check the WRITER
  still finds it by that name — `append_subbullet` matched titles by first
  source line, so a wrapped-title entry silently dropped every /answer and
  /comment with no error anywhere. Nothing surfaces a silent write failure
  on the human's own input channel. (2026-07-25-1010-question-surface)
- A measure-then-write in rAF always paints one frame behind a CSS
  transition; if a constraint must hold every frame, express it in CSS.
  `(100vw - 100%)/2` is the gutter, because `100%` is the containing block.
  (2026-07-25-1010-question-surface)
- Instrument bugs outnumber feature bugs: Range rects are per inline BOX not
  per line, getBoundingClientRect includes transforms (use offsetWidth for
  "did it re-lay-out"), and a page-wide selector measures the page rather
  than the component. Budget for debugging the instrument.
  (2026-07-25-1010-question-surface)
- Prefer an A/B over an absolute threshold for a layout metric, and sweep the
  parameter: the reflow win peaks in the MIDDLE of a width sweep, so any
  single width would have made the fix look trivial or heroic.
  (2026-07-25-1010-question-surface)
- A guard that reads mutable content is testing the content; its false reds
  train you to ignore it. Freeze a fixture, and reset it between guards that
  write, or the first writer eats what the next one needs.
  (2026-07-25-1010-question-surface)
- A test count that changes for no reason you authored is a state signal, not
  a curiosity — 63 vs 55 was how a wrong-branch checkout got noticed.
  (2026-07-25-1010-question-surface)
- Give a list row two identities when writes and animation need different
  ones: a positional key addresses the entry, a stable id IS the entry and
  survives it moving between sections. (2026-07-25-1010-question-surface)
- Distance from the artifact converts into confidence rather than doubt,
  which is backwards: the coordinator misdiagnosed three reports today
  and the dreamer holding the file was right every time. Dispatch the
  hypothesis, never the conclusion. (coordinator, 2026-07-25 reflection)
- Ask of every durable thing the loop invents: who owns it? Shared
  mutable state without a named owner failed three times in six hours —
  an id counter, a working tree, a port — each invisible until a second
  actor existed. (coordinator, 2026-07-25 reflection)
- Delegation parallelism is bounded by the largest single file: watch.py
  is 3055 lines and took 39 commits today, so every UI steer serialises
  through one dreamer no matter how many are free. The disjointness
  invariant is correct and the file is the constraint. (coordinator,
  2026-07-25)
- **A coordinator's diagnosis is a hypothesis and should be labelled one
  in the dispatch.** Five times on 2026-07-25 the coordinator named a
  plausible layer and the dreamer measured a different one — #106, #107,
  #121, #123 — and each time the cost of being wrong was zero *because
  the dispatch said measure it first*. The practice, not the accuracy, is
  what protects the work. (coordinator, 2026-07-25)
- A wrapper (proxy, shim, adapter) can patch what a page *calls* — fetch,
  pushState — but never what it *reads*: `location.pathname` compared to
  string literals is unreachable from outside. Split the surface into
  calls and reads before promising adaptation; the reads are the part
  that fails silently. (2026-07-25-1104-dreamhub-stage1)
- A component can be CORRECT IN SOURCE and wrong on screen: `.sgbtn` asked
  for `background:none` from #103 and never once rendered that way, because a
  leftover `.qa button` element rule outspecified it (0,1,1 over 0,1,0). A
  pytest asserting on generated source passes on this for as many commits as
  you like — the sharper version of #117's lesson. A catch-all element rule
  inside a component's scope is a latent override of every component that
  ever renders inside it. (2026-07-25-1111-question-states)
- Anything a re-render destroys that exists NOWHERE ELSE must be carried
  across it, not protected by suppressing the render: typed text, the caret,
  focus, the destination mode, what he expanded. Liveness and his input are
  not in tension — one seam (`snapshotCardState`) serves both.
  (2026-07-25-1111-question-states)
- A clone used as a departure ghost must have its IDENTITY stripped, not just
  its position set: it keeps `data-qid`, so every keyed lookup on the page can
  find a corpse — including the one that restores his typing.
  (2026-07-25-1111-question-states)
- Counting direction reversals does NOT tell a breath from a sawtooth: the
  snap-back is itself a reversal, so a one-way sweep passes. Measure how LONG
  the fall takes (the fraction of moving samples that are falling).
  (2026-07-25-1111-question-states)
- FLIP a list by POSITION and HEIGHT, never by scale: once a state collapses
  its card, the height ratio can be 15x and a scale morph squashes the text.
  And a resizing card's height animation already carries everything below it,
  so the FLIP must only handle the RESIDUAL or neighbours move twice.
  (2026-07-25-1111-question-states)
- Assert the OUTCOME, not the mechanism: "every card that moved carried an
  inline transform" forbade the better motion (a neighbour riding an animated
  height needs no transform of its own). "Got there continuously" is the
  property that survives a change of implementation.
  (2026-07-25-1111-question-states)
- A timed courtesy (auto-dismiss, auto-close, auto-advance) must be cancelled
  by any sign the human is still using the thing — and the cancel needs to
  cover the in-flight window before the timer exists.
  (2026-07-25-1111-question-states)
- **A fix that is committed but not deployed is indistinguishable from a
  bug, and the human is looking at the deployed page.** #129 was reported
  24 seconds after the commit that fixed it and ~4 minutes before the
  deploy; the report was accurate, the code was correct, and a tracing
  cycle was spent on the gap between them. Deployment latency
  manufactures phantom bugs. (coordinator, 2026-07-25, #140)
- **Prose about a tool drifts from the tool faster than anyone expects.**
  file-formats.md said tasks.md and status.json had no stated contract;
  within the hour lint.py was checking both. Same author, same day, and
  the doc was explicitly about the dangers of drift. Which is the
  argument for executable contracts stated in the doc itself — not
  because people are careless, but because the gap opens even when they
  are not. (coordinator, 2026-07-25, #137)
- **Writing a check and running it green is half the work; making it red
  on purpose is the half that finds out whether you tested the thing or
  its neighbour.** Three checks were caught proving nothing on 2026-07-25,
  by three different agents, none visible by reading it: the wisp guard
  passed on a one-way sweep because it counted direction reversals; the
  oneinput guard passed on the textarea leak because it asserted the
  BUTTON spans the field; a dreamhub test passed on a serial probe
  because it built its own thread pool. Each was found only by
  reintroducing the bug. (coordinator, 2026-07-25)
- **A closed `<details>` does NOT display:none its children in current
  Chromium.** — content-visibility keeps their rects from the last layout,
  so a height-or-rect test for "is it hidden" passes on collapsed
  content. Use `checkVisibility()`. Found writing #128's thread guard;
  it is the fourth check today that would have proved nothing, and the
  only one whose cause was the browser rather than the author.
  (dreamer-thread, 2026-07-25)
- **Never let the page fold away what the human just wrote.** #128's first
  version collapsed the note segment at the END of the list when a
  question had no answer yet — which swept every live steer on every
  open question into the folding half. Only the SETTLED segment, above
  the resolution, may collapse; a note added now lands below the answer
  and stays visible. The guard caught it, not the author.
  (dreamer-thread, 2026-07-25, #128)
- **A flaky test is a hypothesis, not a nuisance.** A 1-in-8 failure in the
  hub's server tests was `port or hub_port()` treating port 0 as ABSENT,
  so `serve(0)` — bind-any-free-port — silently bound a persisted port
  instead and sometimes collided. Dismissing it as flake would have
  shipped it, and the intermittency WAS the symptom: falsy-zero bugs
  only surface when the collision happens to land. Reach for "what is
  actually different between the runs" before "rerun it".
  (dreamer-hubbuild, 2026-07-25, #96)
- **A readiness probe that accepts any answer will eventually grade a
  stranger's server.** dreamhub's guard failed to bind its port, its
  probe found a watch.py instance answering nearby, and it asserted 23
  checks against it — green, and measuring somebody else's process.
  Ports now have named owners (parallel-architecture.md), but ranges are
  not sufficient because a stale process can hold a port you own: fetch
  something only YOUR server serves and check it, rather than treating
  any 200 as ready. (dreamer-hubbuild, 2026-07-25, #96)
- **Assertions passing is not the same as the page being right.** The
  hub's 23 checks were green when a screenshot showed two real bugs: a
  row for a missing directory offering a command to start it, and an
  `elif` that dropped the note explaining why a mid-write row had no
  task. Look at the render after the assertions pass — they only cover
  the questions someone thought to ask. (dreamer-hubbuild, 2026-07-25)
- **A line-oriented log that an agent acts on is an injection surface, and
  the human's own input box is the vector.** `watch-events.log` is one
  event per line and the coordinator's monitor wakes on a line and reads
  it as an instruction — so a newline typed into the composer could forge
  a second event, and the loop would act on a command the human never
  sent. No malice required: a pasted multi-line note would have done it,
  and the result would have looked like him asking for something he did
  not. Collapse newlines where human text enters any record an agent
  reads. (dreamer-thread, 2026-07-25, #126)
- **The loop applied its own no-unread-channel rule to targets and not to
  itself.** Dreamers append reports to a file the coordinator tails and
  have lost nothing in a day of heavy use; utility subagents report by
  final message, and that channel silently swallowed two of three
  deliverables — the coordinator only noticed because it was tracking
  what it had dispatched. A guardrail written for one direction is not
  automatically applied in the other, and the machinery you built is
  exactly where you will forget to look. (coordinator, 2026-07-25, #144)
- **Fold by complement, never by allowlist: demote what you do not name,
  never drop it.** The status panel shows four named things and folds
  "whatever is left", not "these other known keys" — because status.json
  is a schema that keeps growing, and an allowlist would silently hide
  the next field the loop learns to write, in exactly the way that looks
  fine. Same shape as the morning's parser bug: a reader that cannot see
  something renders identically to there being nothing to see. The
  fixture now carries a key the renderer has never heard of, and a guard
  asserts it stays findable. (dreamer-thread, 2026-07-25, #130)
- **Before asking whether a layer handles X correctly, ask whether X
  survives to that layer at all** — feed it two inputs differing only in X
  and compare the outputs. #128's hypothesis was "the render leaves notes
  in source order", which assumes the order reaches the render. Parsing
  the same entry with its sub-bullets in either order gave BYTE-IDENTICAL
  structures, so the chronology was never there and every hypothesis about
  the renderer died at once — without reading it. This is the step after
  "reproduce the input": a differential on the property in question, and
  it is how you find out the property was never there.
  (2026-07-25-1201-thread-and-status, #128)
- **When a fix is stated as a class, spend four minutes finding the second
  instance immediately.** The events-log newline fix was generalised to
  "human text must not be able to forge a record"; looking for another
  instance took four minutes and found a worse one — /comment writes into
  questions.md, so a typed newline forges a whole ENTRY on the loop's
  primary human channel (#146, filed not fixed). The second instance is
  usually on the more important channel, because the more important
  channel is the one with more writers.
  (2026-07-25-1201-thread-and-status, #126)
- **Write the timestamp from the clock in the same command that writes
  the file.** SKILL.md already says timestamps come from the system clock
  and never from memory; the coordinator broke its own rule anyway,
  recording `last_tick: 12:14` at 12:04 by copying the heartbeat
  message's text and estimating. It was invisible until the status panel
  rendered it where a human would read it — a wrong timestamp is a claim
  about freshness, and a stale-looking loop and a lying one are
  indistinguishable from outside. (coordinator, 2026-07-25)
- **A check is only as good as the distance between what it asserts and
  what it exercises.** Three of dreamhub's passed on their own bug, each
  for a different reason: one asserted an end state that the WRONG
  implementation also reaches (slug recomputed on read renames the
  survivor, not the incumbent); one exercised a different code path than
  the one shipped (it built its own thread pool instead of calling
  `probe_all`, so a fully serial `probe_all` passed); one asserted an
  outcome with TWO sufficient causes (the per-second age tick was
  invisible because the 2s poll re-renders ages anyway). Injection found
  all three; reading found none — and the third was fixed by finding the
  case where only one cause operates, which turned a redundant-looking
  mechanism into a stated behaviour.
  (2026-07-25-1205-dreamhub-build, #96)
- **To guard a wire contract with a component you do not own: run the
  REAL one over a COPY of its fixture, assert agreement, then mutate the
  input and assert the reader FOLLOWS — and show it red against DRIFTED
  COPIES so the owned file is never touched.** Agreeing once is also what
  a permanently frozen cache does. dreamhub caught `/mtime` losing its
  generation half, `open_questions` renamed, and `/data.json` moved; none
  of the three crashes anything, which is exactly why a guard is needed —
  the reader goes on serving stale or unknown values and looks fine.
  (2026-07-25-1205-dreamhub-build, #96)
- **Where you can remove shared mutable state instead of naming an owner,
  remove it.** Naming an owner is the fallback. A fixed guard port made
  dreamhub's guard attach to a neighbouring dreamer's watch instance and
  assert against a stranger's page; the readiness check that catches that
  is worth keeping, but defaulting to an ephemeral port makes the
  collision impossible rather than loud. Fourth unowned-state incident in
  a day (id counter, working tree, port, port).
  (2026-07-25-1205-dreamhub-build, #96)
- **`or` as a default is wrong for every value whose zero is meaningful,
  and it fails intermittently rather than loudly.** `port or hub_port()`
  read `serve(0)` — "any free port" — as "no port given" and bound a
  random persisted one instead, succeeding almost every time and
  colliding about one run in eight. The intermittency was the symptom;
  the falsy zero was the bug. (2026-07-25-1205-dreamhub-build, #96)
- **A dependency you cannot import is one you are forced to describe, and
  the description is worth more than the coupling you avoided.** Being
  locked out of `watch.py` produced protocol-level reuse; enumerating
  what the hub depends on is what made the drift guard writable at all —
  you cannot guard a contract you have not written down.
  (2026-07-25-1205-dreamhub-build, #96)
- **Needing one variable interpolated opts the whole document into shell
  expansion.** The coordinator wrote a dreamer relay through an unquoted
  heredoc to get a timestamp in, and every backticked term in it —
  `_parse_entries`, `- **`, `## ` — was executed as a command
  substitution and replaced with nothing. The message stayed plausible
  and lost its nouns. Same class as #146, aimed inward: text written into
  a record without escaping, where the record's reader treats part of
  that text as syntax. Use a quoted heredoc and add the timestamp on its
  own line. (coordinator, 2026-07-25)
- **Indenting human text is not enough to make a record safe; the reader
  has two tests and they read different things.** #146's brief said to
  indent continuation lines, which defeats the reader's `- **` and `## `
  tests — both of which it applies to the RAW line. But it applies "does
  this start a bullet" to the STRIPPED line, and a bullet ENDS a
  sub-bullet's capture, so an indented `- foo` still dropped the rest of
  his words into the entry's body, where they render as prose the loop is
  assumed to have written. That is #109 failing through a different door,
  and an entry-count assertion passes on it. Before sanitising for a
  parser, enumerate every test it makes and what each one is applied to.
  (2026-07-25, #146)
- **A file inbox is durable but it is not a wake signal.** Coordinator
  relays land in a file the dreamer reads "between increments", so an
  agent that has gone idle never sees them — a batch written two minutes
  after a dreamer went quiet sat unread until it was pinged. Durability
  and delivery are different problems and the loop solved only the first.
  Write the instruction to the file AND send a message; the file is what
  survives, the message is what arrives. (coordinator, 2026-07-25, #144)
- **When a format fails silently, the fix is a WRITER, not a second
  description of it.** ud-dreamtask's opening had agents hand-writing
  `questions.md` and `status.json` — the two files here that fail by
  being invisible. `newerrand.py` emits them and states no format of its
  own; its test shells out to `lint.py`, so the linter stays the single
  interpreter and the creator is merely something it checks. The
  injection that proves the arrangement works is the one where
  `awaiting_human: "nobody"` reds ONLY the lint check.
  (2026-07-25-1221-ud-dreamtask-build, #50)
- **Inheriting by reference puts the obligation on the file being
  pointed AT.** ud-dreamtask names SKILL.md's Guardrails, Subagents and
  Durable-state sections instead of copying them, which is right — but a
  rename now orphans a live pointer in another repo, and nothing in this
  repo would notice. That obligation belongs in the doc-map, where a
  docs-freshness pass reads it, not in a comment in the skill that
  depends on it. (2026-07-25-1221-ud-dreamtask-build, #50)
- **A subagent is the party least able to judge its own context cost, so
  the retire decision is the coordinator's.** dreamer-thread offered a
  context call after its first batch; the coordinator gave it a second
  and a third because it said it had room, and it reached ~600k tokens.
  "Dreamers are batches, not careers" was already written down — what was
  missing was that the incumbent's own assessment is evidence, not a
  decision. Default fresh; reuse only inside ~4 minutes of its last stop,
  where the cache is still warm and a respawn would throw it away.
  (coordinator, human-corrected, 2026-07-25)
- **An exemption is where a check quietly dies, so define it as narrowly as
  the failure allows and prove it did not swallow the real one.** #136's
  calm state could have been "no prose in the file", which blesses the exact
  morning failure — a questions.md whose only lines were `##` headings the
  loop had written AS its questions. Calm therefore requires no prose AND the
  literal `## Open` the reader matches, and the guard's last read-side
  assertion takes the file the exemption blesses, adds one line of prose, and
  requires the fault to surface anyway. The linter made the looser version of
  this mistake an hour earlier and red-lit every freshly seeded target.
  (2026-07-25, #136)
- **A confirmation shown for a write that did not happen is worse than the
  failure it hides.** `/answer`'s response was discarded, so a refused write
  still ran the submit morph: the card restated itself as answered, his text
  was cleared, and the live tick put the question back two seconds later with
  no explanation anywhere. Check what came back before showing the thing that
  means "it landed", and keep his text — at that moment it is the only copy.
  (2026-07-25, #136)
- **The instrument is wrong more often than the feature.** Five times on
  2026-07-25 a check disagreed with the code and the CHECK was at fault,
  each initially looking like a code bug: a closed `<details>` keeps its
  rects in current Chromium (use `checkVisibility()`); a CSS token read
  off `:root` never equals a computed colour (resolve it through a
  throwaway element); `node guard.mjs | tail` reports TAIL's exit code,
  so a failing guard reads green; a selector naming the state under test
  passes vacuously the moment that state changes; freezing a
  module-scope `let` from outside does nothing. When a check and the
  code disagree, suspect the check first — it is younger, less exercised,
  and nobody has been using it all day. (dreamer-thread, 2026-07-25)
- **Guard runs take 15-25 minutes under this repo's current load** (several
  dreamers, ~40 chromium processes, load average 14). Start the run
  BEFORE writing the commit message, not after. `just guards <port>`
  buffers all output to the end, so poll the per-guard logs in the run's
  temp dir if you want progress. (dreamer-thread, 2026-07-25)
- **Verify the transport, not the sender: a silent agent and a silent
  channel look identical.** A review subagent answered three times into
  plain text output, which is not a channel at all — only files and
  harness messages reach the coordinator — so each "idle, no findings"
  was a full report with nowhere to go. It recovered only when told to
  write to a file. That is the third instance in one day of a write
  nobody could read: dashboard commands landing in a log the tick flow
  never checked, and a project's questions.md rendering as "nothing to
  answer". In every case the writer believed it had communicated. Ask
  what READS this, not whether it was written. (reviewer-skillmd,
  2026-07-25, #144)
- **A documented behaviour that never happened is worse than an
  undocumented one, because the document stops anyone checking.** #113's
  motion matrix carried a row saying an arriving card snaps then eases
  in. It never did: `.dreamin` set `transition:none`, `.qa` declared the
  same three transitions at the same specificity and later in the sheet,
  and the cascade gave it to `.qa` — so every arrival since #104 was a
  pop-in, under a matrix that said otherwise. Found only because reusing
  the mechanism somewhere new made it measurable. When you write a state
  down, measure that state once. (dreamer-rows, 2026-07-25, #154)
- **A synthetic `element.click()` sails straight through
  `pointer-events:none`.** So a guard asserting "the collapsed section
  still opens" passes on a summary the human physically cannot click.
  Drive the check with a real pointer when the thing being tested is
  whether HE can operate it — a synthetic event tests the handler, not
  the affordance. (dreamer-rows, 2026-07-25, #141)
- **A guard that prints its checks at the TAIL misleads whoever DIAGNOSES
  it, even when the runner catches it.** A crashed guard prints nothing,
  which reads identically to printing no failures — three injections
  looked like "this check proves nothing" when the check had never been
  reached. Narrowed after its finder surveyed the actual exposure:
  `just guards` branches on each guard's EXIT CODE, so a crash does read
  as FAIL and the gate holds. What breaks is the human-facing half — the
  log says nothing was wrong while the run says it failed, and you debug
  the wrong thing. Print as you go. (dreamer-rows, 2026-07-25, corrected
  by its own survey)
- **A shared fixture that cannot express a feature makes its guard vacuous,
  and vacuous reads exactly like green.** `dev/capture/fixture` is not a git
  repository, so `git_tail` returns `[]` and the commits panel is EMPTY on
  the server every guard shares — every check about a commit row would have
  passed against nothing at all. The guard builds its own git target
  instead, which is also the only way to reach the 100-day boundary. Before
  writing a check against a shared fixture, ask whether that fixture can
  hold the state under test; an empty section satisfies every assertion
  about its contents. (dreamer-rows, 2026-07-25, #132/#151)
- **A guard clause that is an optimisation in the common case has no check
  until you construct the uncommon one.** #151's "animate on a new sha, not
  on a tick" gate looks unfalsifiable: delete it and a quiet tick still
  moves nothing, because the regroup early-returns for a row that did not
  move. The gate is only observable when the rows move for some OTHER
  reason — which is precisely the case it exists for. So the guard makes
  them move (an unreadable questions.md puts #136's warning above the
  panel) and requires them to arrive with the layout rather than travel to
  it. If deleting the thing changes no outcome you can name, you are not
  testing it. (dreamer-rows, 2026-07-25, #151)
- **A rule the loop already wrote down and already broke wants a WRITER, not
  a re-reading.** "Write the timestamp from the clock in the same command
  that writes the file" is in this file, and a dreamer estimated three
  report timestamps anyway — 13:12/14:05/14:47/15:40 for events that
  happened between 13:04 and 13:50, on a channel the coordinator uses to
  order work. Five different agents drifted the same way that day, always
  mid-batch: elapsed time feels longer from inside the work, so the warning
  was evidence about the warning. `relay.py coord --as <name>` now takes the
  dreamer→coordinator direction too. (dreamer-rows, 2026-07-25)
- **A report can be right about the gap and stale about the fix, and the
  reason will be the gap itself.** The dreamer above reported that no writer
  existed for its direction — twenty minutes after the coordinator had built
  one and written it to the dreamer's inbox. It never read it: the inbox is
  durable but not delivered, and the dreamer was mid-guard-run, which is
  exactly the failure it was reporting. The general form: **a finding about
  a broken channel cannot be trusted to have arrived through that channel.**
  Before reporting that something is missing, re-read the inbox — a batch
  written while you were busy is indistinguishable from no batch at all.
  (dreamer-rows, coordinator-corrected, 2026-07-25)
- **A proxy check eventually gets believed as the thing it proxies.**
  `audit-styleguide` asks "did this commit touch both files?" as a stand-in
  for "is the page's behaviour written down?", and after 29 green commits
  the loop — including the coordinator, in a task description — was
  calling its misses real gaps without looking. Both were false
  positives, one because the doc landed two minutes BEFORE the code,
  which is the better practice. And the failure nobody would ever
  notice runs the other way: touching both files passes whether or not
  the doc says anything at all. State in the check itself what it does
  not prove. (coordinator, 2026-07-25, #155)
- **An answer that does not engage with its question is a signal, not a
  decision.** On 2026-07-25 four submissions arrived through the
  dashboard reading "traced answer for the regroup" and "a note routed
  by the mode group" — he was exercising the regroup and the mode group,
  not answering. Folding them would have closed the dreamhub URL-space
  question and ud-dreamtask's stage-6 gate on test content, and both
  would have looked decided. The loop has no way to tell a test
  submission from a real one and should not try to build one: the
  guardrail already covers it — mismatched signals mean something is
  wrong, so do not guess, ask. Read the answer against the question
  before acting on it. (coordinator, 2026-07-25)
- **At 16px a change of POSITION is legible where a change of LUMINANCE
  is not.** The favicon orbits rather than breathes, and that was decided
  by rendering both at 16px on real tab-strip greys instead of reasoning
  about them — a breathing dot at favicon size reads as a static dot.
  Same conclusion #113's wisp reached from the opposite direction, where
  a breath had room to be seen. The general form: an idiom that works at
  one scale is not a design at another, and the cheap way to know is to
  render it at the size it will actually be. The same look also killed an
  opaque near-black tile that was correct on his dark browser theme and a
  black block on a light one. (dreamer-identity, 2026-07-25, #153)
- **A syntax error is invisible to every test that asserts on source
  text.** A pair of backticks inside a GLSL COMMENT closed the JS
  template literal the shader lives in, so the rest of the shader parsed
  as JavaScript and the page rendered blank. Every pytest substring
  assertion still passed — the source genuinely CONTAINS those strings;
  it simply will not parse. Only the browser guards caught it, twenty
  minutes later, as thirty unrelated red lines pointing nowhere near the
  cause. `just test` now runs `node --check` over the assembled script,
  which is a two-second check that turns a twenty-minute mystery into a
  line number. Any language embedded in a template literal has this
  hazard, and comments are where it hides, because nobody proofreads a
  comment for delimiters. (dreamer-identity, 2026-07-25, #143)
- **A guard assertion whose subject may not exist must RETURN a value,
  never throw.** Three times in one file a check written for the
  "the write silently did nothing" case died on `readFileSync` instead
  of reporting it — so the injection the check existed for produced a
  stack trace rather than a red line, and read as the check being
  broken. The failure it was built to catch is precisely the state where
  its subject is absent. (dreamer-identity, 2026-07-25)
- **Measure where the thing actually is, after waiting for the state it
  is in.** A hue measurement was wrong three times while the feature was
  right the whole time: it sampled a region overlapping the text column,
  then slept less than the 2s poll it was waiting on, then sampled while
  the page was still on another route with an iframe over the spot. Wait
  for the state, sample where the field is, and know which route you are
  on. (dreamer-identity, 2026-07-25)
- **An idiom that works at one scale is not a design at another, and
  rendering it at its real size is the cheap way to find out.** #153's
  favicon began as a breathing bloom — lovely at ×7, an indistinguishable
  smudge at the 16px a tab strip actually draws, ten frames apart. At that
  size a change of POSITION reads where a change of LUMINANCE does not, so it
  orbits instead. The same look killed an opaque near-black tile that was
  right on his dark browser theme and a black block on a light one. Both were
  found by putting the real pixels on real tab-strip greys, not by reasoning
  about them; #113's wisp reached the opposite conclusion because a card has
  room for a breath. (dreamer-identity, 2026-07-25, #153)
- **Design for the frame rate the environment will actually give you — and
  then check the case you optimised away.** A hidden document gets no
  rendering opportunities, so rAF does not run in a background tab, which is
  where a favicon lives; quantising the orbit to one frame per second is
  right there and under the background timer clamp both. He then watched it
  in the FOREGROUND and called it too slow (#182). Both halves are true at
  once, and the answer is two regimes rather than a speed-up. The reasoning
  was not wrong; it was complete for one case and silent about the other.
  (dreamer-identity, 2026-07-25, #153/#182)
- **The fast half of a test suite asserts on a string, and a string is not a
  program.** A pair of backticks inside a GLSL *comment* ended the JS
  template literal the shader lives in; the rest parsed as JavaScript and the
  page went blank. Every pytest substring assertion still matched perfectly,
  because the source contains the strings — it just will not parse. Only the
  browser guards caught it, twenty minutes later, as thirty unrelated red
  lines. `node --check` over the assembled script closes that class in 0.2s.
  Ask whether your cheap checks can distinguish a broken artefact from a
  working one, not whether they pass. (dreamer-identity, 2026-07-25, #143)
- **A guard assertion whose subject may not exist has to degrade to a
  reading, never throw.** Twice in one file the injection a check existed for
  destroyed the check: the favicon reader rejected on an icon that never
  loads, and the tint reader threw on a file the write had silently skipped.
  Both times the run said "the guard threw" and named nothing, so the
  diagnosis started in the wrong place. A crash reads like silence — return a
  zero and let the assertion do the talking. (dreamer-identity, 2026-07-25,
  #153/#143)
- **Fixing the instance is what leaves the class alive.** `just guards`
  accepted any answer on its port, so a stray `just watch` left on 39890 made
  ten guards assert fixture facts against the live repo — twenty minutes, and
  red lines about a fixture that was never being read. This exact class had
  been diagnosed that morning from dreamhub and fixed *where it was
  reported*; the runner kept the mechanism. When a lesson names a class, ask
  what else is in it before writing it down. (dreamer-identity, 2026-07-25)
- **Re-reading the inbox is not the same as re-verifying the claim.** A
  dreamer closed its batch reporting a handover as outstanding; it had
  landed fifty minutes earlier. It HAD followed its own rule — a finding
  about a channel cannot be trusted to have arrived through that channel,
  so re-read the inbox first — but the answer was in the WORKING TREE,
  not the inbox, and it asserted a present-tense fact about a file it had
  not re-read. The general form: a close is written over minutes, and
  anything it claims about current state was read at the start of
  writing. Re-check the claim itself, in the place the claim lives.
  (dreamer-identity, 2026-07-25, corrected by its own check)
- **`focus()` into a closed `<details>` does nothing and reports nothing.**
  The dashboard restored his caret into a box inside a folded section, so
  the field came back filled, caret placed, and dead — no error, no
  return value, no way to tell from the calling code. Two consequences
  beyond the fix: seams must be ordered by what NESTS, not only by what
  measures (restore folds before restoring state); and a refocus should
  check the focus actually landed rather than assume the call worked.
  (dreamer-motion, #179, 2026-07-25)
- **The visible thing gets blamed for the invisible thing's bug.** #179
  was reported as the commit panel stealing focus; the panel was innocent
  and the steal happened on EVERY re-render. It was simply the one element
  on that page whose re-render he could see. A guard had been green over it
  for hours because it only ever visited the page where the boxes are
  top-level. When a report names a trigger, reproduce it on a DIFFERENT
  trigger before believing the name. (dreamer-motion, #179, 2026-07-25)
- **Prose full of backticks must never reach a shell through double
  quotes.** `git commit -m "... the `common` field ..."` executed the
  backticks and silently deleted the word from its own sentence — the same
  class as the heredoc that ate `_parse_entries` and produced `relay.py`.
  This repo's writing names files and identifiers constantly, so the
  exposure is permanent: use `-F -` with a QUOTED heredoc, or stdin.
  (coordinator, 2026-07-25, twice in one day)
- **When direction is the report, the check must assert the SIGN.** #174
  was a departing commit row travelling *up* into a gesture pushing four
  other rows *down* — a gesture fighting itself — and every existing check
  passed on it: `dashboard.mjs` counted that a ghost existed and that the
  survivors moved, and both are true of the version he complained about.
  "It moved" and "there was a ghost" are satisfied by exactly backwards.
  Same trap as counting that the wisp changed rather than how. The general
  form: when the human's words are about a DIRECTION, a magnitude check is
  not a weak version of the right check, it is a check that cannot fail.
  (dreamer-motion, 2026-07-25, #174 / 2026-07-25-1620-motion-batch)
- **A report that will not reproduce is usually pointing at its neighbour,
  not at nothing.** Neither half of #184 reproduced: the card above an
  answered one shows zero travel and zero transform across 354 frames, and a
  whole commit cycle moves no question card at all with the panel height
  constant. But #174 — a departing row running backwards against everything
  around it, in the panel directly above that list — was confirmed red in the
  same batch, and a gesture that fights itself is exactly what "things that
  did not move are animating" describes from across the room. So measure the
  claim, write the non-reproduction down, and then look for a CONFIRMED bug
  in the same square inch of screen before doubting him. A quiet drop loses
  both halves of that. (dreamer-motion, 2026-07-25, #184 /
  2026-07-25-1620-motion-batch)
- **A comparison that could not run must never look like one that ran and
  found nothing.** Four instances in one day, three of them in a single
  half-hour: a guard whose readiness probe accepted any answer and graded
  a stranger's server; a dream-filename slice off by one so every parse
  failed and the check reported "6 named correctly"; a shell loop where
  `$r:watch.py` was mangled and `2>/dev/null` hid the fatal, so it
  compared nothing and reported "no match" three times with total
  confidence; and a lock-assertion spy that caught its own fixture's git
  calls. The general form: **absence of a positive result is not evidence
  of a negative one**, and error suppression is what erases the
  difference. Give every "could not compare" its own named state, and
  assert the comparison actually happened. (coordinator, #147, 2026-07-25)
- **A guard reaches only the routes and gestures someone found easy to
  drive.** #179's typing guard was green for hours because it only ever
  visited `/questions`, where the cards are top-level — the dashboard,
  where they nest inside a fold, was the harder page to automate and the
  one he actually uses. The counter is one question per new guard: which
  of his routes and which of his gestures does this NOT reach?
  (dreamer-motion, #179, 2026-07-25)
- **When a path holds the tick, the guard's WINDOW is the measurement.**
  The sharpest of the three, and it corrects the other two. `regroup.mjs`
  HAS submitted through the real UI since #104 and was still green over
  #191 for a day: it traces 5.2s, past the 1.6s `holdRerenderUntil`, so
  the tick's own regroup travelled the neighbour and every "it slid"
  assertion passed over a teleport that had happened a second and a half
  earlier. Nothing was wrong with its route or its driver — only with how
  long it looked. **A guard that watches long enough will see some later
  mechanism produce the result it wants.** `morph.mjs` traces 1400ms and
  additionally asserts the card node was never replaced, so whatever
  moved, the morph moved. (dreamer-gesture, #191, 2026-07-25)
- **And the coordinator wrote that lesson twice before reading the file.**
  Worth keeping attached to it. dreamer-motion said `regroup.mjs` "answers
  by POST and lets the tick do the whole move"; I recorded that. Its
  successor found the trace-window cause; I recorded that as a
  *correction*, saying the first account was wrong. Then it told me the
  first account had been accurate, and I finally opened the file: it
  **clicks** `.qmode` and `.qsend`, and its own header says it traces "a
  real POST /answer and the live tick" over 5200ms. Both dreamers were
  right; the second was more complete. Three versions of one lesson from
  two reports and zero readings, when the file was three commands away —
  and the lesson being revised was *measure, do not inherit*.
- **An assertion is only a guard if failing it stops the next step.** A
  script asserted its edit anchor existed, refused to write when it did
  not — and the `git commit` on the following line ran anyway, publishing
  a message claiming an edit that never happened. The assertion worked
  perfectly and guarded nothing, because it was a separate command rather
  than a chained one. Same family as the tail-printing guards (#192),
  where the check is fine and the thing downstream of it is not: **ask of
  every check not only "is it right?" but "what does it stop?"**
  (coordinator, 2026-07-25)
- **If a report is about how something MOVES, an end-state check cannot
  fail on it — and neither can "did it move".** Three bugs in one batch
  (#191 a two-position teleport, #159 a confirmation lit on frame 0, #169
  a 20px snap at the end of a travel) all ended in exactly the right
  place; the frames between were the defect. All three guards assert the
  same quantity, **the number of distinct intermediate values**, and none
  assert a mechanism. Write the check against the middle or do not write
  it. (dreamer-gesture, #191/#159/#169, 2026-07-25)
- **Inside a FLIP's measurement, layout must land INSTANTLY; only the FLIP
  animates.** `regroupCards` measures the new rect in the same tick as the
  mutation, so a CSS transition on `padding` (or height, or a child's box)
  hands it a start-of-transition rect: it then plays perfectly to a height
  the element never reaches and snaps the difference when the inline height
  clears. Injected, that tripped one check out of sixteen — "it travelled
  continuously over 45 positions" passed on it.
  (dreamer-gesture, #169, 2026-07-25)
- **Revert a deliberate RED injection with the inverse of the injection,
  never with `git checkout <file>`.** The whole-file revert also destroyed
  51 lines of uncommitted work that shared the file. If a script made the
  injection, a script unmakes it. (dreamer-gesture, 2026-07-25)
- **A dreamer retiring in prose is not a dreamer retired.** Twice on
  2026-07-25 an agent replied "shutdown acknowledged, retiring" and then
  stayed alive and idle, because the handshake needs a structured
  `shutdown_response` and a sentence is not one (reviewer-skillmd, then
  dreamer-gesture). From the coordinator's side a completed retirement and
  a prose one look identical until availability notifications start
  arriving — so **the retirement is not done when the agent says so, it is
  done when the harness says the agent terminated.** Same class as the
  batch that produced it: the thing that reports success and the thing
  that succeeded are different events. (coordinator, 2026-07-25)
- **A shared helper's invariants may hold only because of the shape of its
  callers, and its comment cannot tell you which.** #196 sent the first
  `<details>` through `travelCard` and the first multi-node clone through
  `dreamAway`, and both broke: `travelCard` interpolated a border-box
  measurement into a content-box `height` (harmless while every caller had no
  vertical padding), and `dreamAway` stripped the ghost's identity from the
  node but not its subtree (complete while every ghost WAS one node). Neither
  was wrong when written. **When a helper acquires its first caller of a new
  shape, re-derive its invariants rather than reading its comment.**
  (dreamer-qsec, 2026-07-25)
- **A reasoned exemption gets believed; a bare TODO gets checked.** The
  dashboard's questions fold snapped for the whole life of #141 behind a
  justification written down twice and confidently — "nothing that MOVES sits
  below the toggle" — which four panels falsify in one glance. #169's guard
  then visited that exact element, asserted its padding and colour, and never
  noticed it was not animating. **When a rule exempts something, check the
  exemption's premise, not just its conclusion** — and when it turns out
  false, leave the correction visible, because the false-and-checkable shape
  is the reusable part. (dreamer-qsec, 2026-07-25)
- **A rendering is not a record.** #199 was filed as "his answers live in
  exactly one place, questions.md". They lived in NO place verbatim: the guard
  submitted an answer, searched that file for it, and correctly reported it
  missing — `append_answer` hard-wraps, so his string was on disk as
  `an answer that lands\n    3160481`. Nobody had noticed because nobody had
  ever searched a file they only ever read rendered. **Before trusting "it is
  saved in X", check that X holds the bytes and not a presentation of them** —
  a file written *for* a reader has almost always transformed what it stored.
  (dreamer-qsec, 2026-07-25)
- A pipeline's exit status is its LAST command's: `python lint.py | tail` inside
  a `&&` chain let a commit land while the linter was red. **A pipe eats the
  failure before `&&` can see it** — the same lesson as "an assertion is only a
  guard if failing it stops the next step", in a form that passed a morning of
  vigilance. Run the gate bare; filter its output only after it has gated.
  (coordinator, 2026-07-25)
- A check that cannot fail for its own stated reason is worse than no check:
  its message names the wrong thing and sends the next person to the wrong
  file. #163's mode-switch assertion ran after a reload, so it was really
  re-testing the restore; it types fresh now. Run the check against a build
  missing ONLY the thing it names. (dreamer-qsec, 2026-07-25)
- **A check earns its message only if you have seen it fail for THAT message's
  reason.** "It went red when I broke the feature" is not enough when one break
  reddens twelve checks. Three guards in the #198/#163/#175/#165 batch held a
  check that could not fail for its stated cause: a phase that inherited a
  post-reload box and so re-tested the restore while claiming to test the mode
  switch; a partition check that rebuilt the expected name inside the GUARD and
  passed against a build with no store; and an `every` over an empty array. All
  three were invisible while green AND while counted — they showed up only
  reading the red output line by line. Corollary, learned the same hour: **a
  count is not evidence.** A `grep -c` said 6 FAILs where the truth was 14,
  because the server had been swapped under the compound command.
  (dreamer-qsec, 2026-07-25)
- **Absence should cost one line, not thirty seconds.** A guard driven at a
  page that lacks its subject waits out the full Playwright timeout and reports
  "the guard threw" — which says nothing about the page and points the reader
  at the guard. Assert the subject EXISTS before driving it: the red run then
  costs 3.4s and names the missing thing. (dreamer-qsec, 2026-07-25)
- **Deletion is invisible to a max-mtime poll.** `watched_mtime` statted only
  files, and removing one cannot raise the maximum mtime of the files that
  remain — so an open page went on showing an unloaded plugin's commands until
  something unrelated was written. Every "unloading is the absence of a write"
  contract (and there are several here — fold-by-complement, `human_block`,
  plugin-commands.json itself) depends on absence being OBSERVABLE, which is a
  separate property nobody had checked. Walk the directories: a directory's
  mtime moves when an entry is added or removed, and it adds no re-renders,
  because a created file already carries a fresh mtime. (dreamer-plugcmd,
  2026-07-25, #86)
- **Hang a reactive hook off where the value is ASSIGNED, never off one of its
  fetchers.** `data` had two: `ensureData` for the first paint and `tick` for
  the live one. Hooking the tick looks like hooking the live path and is not —
  `ensureData` sets `lastMtime` as it fetches, so the first tick finds nothing
  changed, and the feature never worked on a freshly opened page while working
  perfectly on every later change. The fix is one `setData` seam, not a second
  call site; a second call site fixes the symptom and re-arms the trap.
  (dreamer-plugcmd, 2026-07-25, #86)
- **Seeding a fixture can make a NEIGHBOURING guard vacuous without making it
  red**, and that is the worse of the two failures. #197 added a third open
  question so the sort had something to sort; `identity.mjs` had a literal 3
  awaiting-human items beside a fixture holding 2, and that GAP was its whole
  check — "the title uses awaiting_human, not the open-question count" is
  byte-identical to a wrong title once the two numbers match. It went on
  passing. When a guard's assertion depends on two fixture numbers DIFFERING,
  derive both at runtime and assert the gap; a literal tuned to today's
  fixture is a check with an expiry date nobody can see. (dreamer-plugcmd,
  2026-07-25, #197)
- A ledger line is a snapshot, not the tree: the coordinator demanded a
  same-commit contract that had already landed three hours earlier, because
  it enforced what the entry SAID was missing instead of checking whether it
  still was. Before enforcing "X is absent", look for X. (coordinator,
  2026-07-25, #197 / 6284402)
- A check and the thing it checks cannot hold separate copies of one rule:
  the priority linter shipped with a WIDER copy of the marker regex than the
  parser, so the three most plausible human typos were blessed by the check
  and ignored by the page. Ask the subject, never re-derive. (dreamer-
  plugcmd, 2026-07-25, #197 / 3073055)
- A backup that failed to write is not a backup: the coordinator ran the
  destructive step (git checkout --) in the same breath as saving the patch,
  and the save had silently failed — shell locals do not survive across
  lines here. Verify the copy EXISTS before destroying the original; the
  work was recovered only because agent transcripts record every edit.
  (coordinator, 2026-07-25)
- Changes you did not make, in a path you hold, are a question and not a
  commit: the coordinator landed a live agent's working tree mid-red-proof
  and it happened to be complete. The tree is shared; only your own edits
  are yours to stage. (dreamer-plugcmd, 2026-07-25, #206 sixth crossing)
- **Copying a mechanism copies its code, not its status.** #151's
  animate-on-new-data gate is a BEHAVIOUR on the commits panel (a row can
  move for some other reason, and its guard constructs that case) and an
  OPTIMISATION on the burndown, where a bar's height is a pure function of
  the series — delete it and nothing changes, because `regroupBars`
  early-returns on an equal height. The check written to guard it would not
  go red. Kept for the forced layouts it saves, and written down as
  unguarded on purpose, because a check that cannot fail sends the next
  person to the wrong file. Ask of every inherited guard clause whether it
  is still load-bearing where you put it. (dreamer-panels, 2026-07-25, #142)
- **When you reuse a travel idiom, re-derive where the property it RESTORES
  comes from — not what the code does.** `travelCard` clears its inline
  height at the end because its elements get their size from layout; a
  burndown bar gets its size from an inline `height:N%` the renderer wrote,
  so the identical line collapsed every bar to its 2px rule after every
  animation and left it there until an unrelated re-render replaced the
  nodes. #198's shape — a permanent bug with a short unreliable lifetime —
  and nothing in reading the code says it, because `travelCard`'s invariant
  was true of every caller it had. A check aimed elsewhere found it.
  (dreamer-panels, 2026-07-25, #142)
- **A panel whose height "is fixed" is a premise, and the prose under the
  chart is where it stops being true.** The burndown's note carried the
  counts; `0 of 4` becoming `0 of 14` rewrapped it onto a fourth line and
  grew the panel 14px, so bars eased over 850ms above four panels that had
  already jumped. The varying numbers moved into a one-line ellipsised head
  (#151's mechanism for #151's reason) and the note became constant. Measure
  the premise; #204 is what it costs not to.
  (dreamer-panels, 2026-07-25, #142)
- **Cross-tab countdowns are distributed systems; "the tab that armed it"
  is not an ownership protocol.** #290's first cross-tab version let every
  tab arm a timer for the same shared deadline — both owner and follower
  POSTed at `until` (found by a reviewer, then reproduced ~1/3 of runs).
  Then the ownership fix made the initiator's *leaving the dashboard* drop
  the commit (re-arm gated on picker DOM), and the orphan-reclaim for
  tab-close was dead code because `readRunPending` purged expired pendings
  before the deferred reclaim could read them. Three real production bugs,
  each invisible to the previous guard. What held: ownership is
  timer+flag+sessionStorage-id state (never DOM), exactly one tab claims via
  a synchronous read→remove CAS, and every lifecycle transition (navigate,
  reload, close, cancel) needs its own RED scenario — not a variant of the
  happy path. (watch, 2026-07-27, #290)
- **A guard that arms the already-committed state is testing a cancel by
  definition.** #290's flaky "cross-tab adopt" check called `pickRunMode`
  with the committed mode — which the UI treats as cancel — so there was no
  arm to adopt, and the failure rate depended on timing making that obvious.
  Flake hunts should first ask "is the premise the state I think it is";
  predicate waits (`waitPage`) then replace fixed sleeps, because
  storage-event latency varies under load. A guard that flakes 2/3 is a
  defect even when the code is right. (watch, 2026-07-27, #290)
- **The watcher you already run beats the tracer you were about to
  authorise.** #283 was one dashboard answer away from a privileged audit
  rule when the existing git-lock-watch journal simply recorded the creator:
  `pi-powerline-footer`'s `git status --porcelain` with a 500ms `proc.kill`
  and no `--no-optional-locks`, orphaned under load. Before escalating
  observability (sudo, auditd, new packages), re-read the evidence the
  current instruments already captured — the argv+parent line was there the
  whole time. (systems, 2026-07-27, #283)
