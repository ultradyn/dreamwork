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
