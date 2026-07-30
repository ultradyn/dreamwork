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
  **It happened again on 2026-07-28 (#348), and worse.** `git checkout --
  review_artifact.py` reverted the uncommitted feature *under test*, so the two
  injections that followed ran against a tree with no sql support: they failed
  because the feature was ABSENT, printed one tidy `FAILED` line each, and read
  exactly like discriminating reds. Two of three proofs were worthless and
  nothing announced it — the tell was `git status` showing only the test file
  modified. So the rule gains a mechanism and a check. Mechanism: **snapshot to
  scratch and restore from the snapshot** (`cp f $S/bak` / `cp $S/bak f`), which
  cannot reach anything but the file injected into; `git checkout` is correct only
  once the work under test is committed. Check: **after every undo, confirm the
  tree still contains what you meant to keep**, because a red from the harness,
  the scaffolding or the undo is indistinguishable in the output from a real one.
  That this lesson existed for three days and did not prevent the repeat is
  itself the finding — see #349.
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
- **Describe the incompleteness you can detect, not every incompleteness that
  exists.** #216 initially documented `history_complete:false` for shallow
  *or partial* clones, but the implementation can detect Git's shallow
  boundary only; partial clones may lazy-fetch the required blobs and report
  complete. The conservative runtime behaviour was right and the broader
  prose was not — narrow the claim to the observable contract rather than
  implying a detector that does not exist. (dreamer, 2026-07-27, #216)
- **Rewriting a projection file wholesale silently drops the fields you did
  not know were load-bearing.** Taking over a target, this coordinator
  authored a fresh `status.json` from scratch rather than merging into the
  parsed dict, and `retired_today` — fifteen prior lanes' retirements, the
  only record of who did what before the handoff — vanished with no error
  anywhere. `lint.py` validated the result as clean, because a projection
  with a missing key is indistinguishable from one that never had it. It was
  recoverable only because the old contents happened to still be in the
  session's context. Merge into what you read; never re-author a file whose
  full key set you have not enumerated. (Same tick, `lint.py` DID catch an
  estimated `last_tick` four minutes in the future — the difference is that
  someone had written a check for that one.)
  (coordinator, 2026-07-27, #281 handover)
- **A file whose sections are found by `split()` on a raw string can be
  re-sectioned by its own prose.** Writing #301 — an entry *about* a ledger
  parser bug — quoted the literal `##`-marker in its body, and
  `parse_ledger`'s unanchored `split("## Open",1)[1].split("## Recently
  landed",1)` split there instead of at the heading: the ledger read as 2 open
  / 187 landed rather than 105 / 84, so every derived number on the dashboard
  was wrong while that text sat on disk. `lint.py` called the file clean the
  whole time, because it counts entries with `ledger_entries`, which never
  splits on sections — the check nearest the damage was structurally unable to
  see it. Caught only by re-reading the file back through the REAL parser
  after the write, which is the habit the repo already has a rule for and the
  reason it has one. Anchor structural markers to line starts, and be
  suspicious of any format where documenting the format can break it.
  (coordinator, 2026-07-27, #304)
- **An answer that arrives on a different channel leaves the original ask
  open, and nothing notices.** #290 was authorized by the human in
  `answers.md` and shipped and deployed, while its P1 entry in `questions.md`
  sat Open for ~15 hours — because the answering commit wrote the answer
  channel and the ledger and never touched the ask channel. The two do not
  cross-reference, and an ask whose subject has landed looks exactly like one
  still waiting; the previous coordinator's handoff carried a hand-written
  "this question is stale" caveat, which is a human remembering in place of a
  tool checking. When you record a decision, close the thing that asked for
  it in the same commit — and where two files hold two halves of one fact,
  assume they have already drifted. (coordinator, 2026-07-27, #306)
- **A test harness that hand-copies the production list of checks will drift,
  and the checks missing from it have tests that cannot fail.**
  `test_lint.py`'s `run()` maintained its own sequence of lint checks and had
  fallen six behind `main()` — including the check being added when this was
  noticed, so its new tests passed while exercising nothing. The tell was a
  test that failed for no visible reason: the fixture parsed, both parsers
  worked in isolation, and the check simply was not being called. Any place
  where the tests enumerate what production enumerates is this bug waiting;
  make production export the list and have the tests call it.
  (coordinator, 2026-07-27, #306)
- **Do not brief a dreamer in N increments before you know the feature has
  N-1 working intermediates.** `#305` was dispatched as "three increments,
  commit each"; the feature turned out to be one atomic change — a split pane
  is not usable without the drag, and the persistence hunks are a handful of
  lines inside the same functions. At ~38 minutes the dreamer had 335
  uncommitted insertions and my checkpoint told it to split, which would have
  manufactured two broken commits to satisfy a cap whose purpose is bounding
  risk. The cap is real, but the risk it bounds is *uncommitted work*, not
  *large diffs*: a coherent 335-line feature that is committed and reviewable
  is safer than three commits that do not run. Brief the cap as "commit at
  every point where the tree works", and where you genuinely want a seam, name
  it at dispatch from the code rather than from the number three — a seam
  invented afterwards is churn, and the coordinator who invented it should say
  so plainly rather than let the dreamer absorb the contradiction.
  (coordinator, 2026-07-27, #305)
- **Grepping a dream for its own phrasing does not tell you whether its lesson
  was captured.** Dream grooming asks "are the lessons in `lessons.md`?", and
  the fast way to answer looks like grepping the dream's distinctive lines. It
  is wrong in the direction that loses work: distillation REWORDS, so a lesson
  that landed as "the visible thing gets blamed for the invisible thing's bug"
  answers zero to a grep for "the trigger he names is evidence, not a cause",
  and the dream reads as undistilled when it is done. On 2026-07-27 that test
  said four of six active dreams still held uncaptured lessons; reading the
  first one showed both of its were already there, worded differently. A
  same-phrase grep is a test for COPYING, and copying is the one thing
  distillation is not. Read the destination. (coordinator, 2026-07-27)
- **A wrong value that something else routinely overwrites is not a transient —
  it is a permanent bug with a short, unreliable lifetime.** #198 was briefed
  as "the end state is correct, so just bound the window", and the end state is
  not correct: nothing autocorrects. What healed it was `setContent` repainting
  every group on the next view re-render, which his live dashboard happens to
  do every couple of seconds. So the bug was permanent and the laundering was
  incidental — and on the FIXTURE, which cannot re-render on its own, a guard
  written to the "transient" story would have passed by luck. Two consequences:
  when something looks self-correcting, find the thing that corrects it and ask
  whether it always runs; and never let "it fixes itself" downgrade a bug's
  severity, because the repair is somebody else's side effect and it will be
  refactored by someone who does not know it is load-bearing.
  (dreamer-qsec via #198, distilled by the coordinator 2026-07-27)
- **A red proof can be defamed by its own injection.** Among four instrument
  bugs in one batch, the nastiest was an injection written as `'' || x`, which
  returns `x` — so the deliberate break never applied, the guard stayed green,
  and the honest reading of that is "this check cannot fail". The danger is the
  direction of the mistake: every other instrument bug makes a good check look
  broken and you go looking, while this one makes a *correct* check look hollow,
  and the next move after "it would not go red" is to rewrite or delete the
  check that was right all along. So a red proof has two halves, and the second
  is usually skipped: confirm the check went red, AND confirm the injection
  actually changed the behaviour — read the injected source back, or assert the
  broken build fails some *other* check that the break necessarily also breaks.
  A green run after an injection is two indistinguishable states until you look:
  a check that cannot fail, and a break that never happened.
  (dreamer-panels via #142, distilled by the coordinator 2026-07-27)
- **A claim that X is being *held* somewhere cannot be checked by reading X.**
  `position:sticky` shifts a box in LAYOUT, so `offsetTop` and
  `getBoundingClientRect()` on a glued box already contain the offset and
  report the same numbers as a box that merely happens to be last — the first
  "the answer box is glued" check compared the box with itself and passed a
  page where nothing was glued. The same day, in the same guard, a fade band
  deleted outright (`content:none`) reported `opacity: 1` and a real `top` from
  `getComputedStyle(el, '::before')`, because a pseudo-element that is never
  generated still has a computed style: existence is a question for `content`,
  drawn-ness one for `display`. Both claims were about a RELATIONSHIP — held
  relative to where the content ends, hiding relative to a band that exists —
  and reading one side of a relationship always returns something true.
  (dreamer-reviewsplit, 2026-07-27, #305)
- **A hard-coded scroll position in a guard has a shelf life.** `scrollTop =
  220` was mid-range when it was written and became "scrolled to the very end"
  when a 16px margin came off and the scrollport grew — after which three fade
  checks passed for the wrong reason and two failed for the wrong one. Measure
  `scrollHeight - clientHeight` and compute the position from it, and assert
  the range is big enough for the middle to be a middle.
  (dreamer-reviewsplit, 2026-07-27, #305)
- **A hand-rolled conflict-marker sweep is an enumeration, and a missing member
  of the set reports clean.** Resolving #305's `lessons.md` conflict, the
  coordinator grepped `^(<<<<<<<|=======|>>>>>>>)`, got "none", and committed a
  file still carrying `||||||| f72f730` on line 1040 — the diff3 base marker,
  the one form the pattern did not name. It survived precisely because
  `merge.conflictStyle` was diff3 and the base region was EMPTY (both sides
  were pure appends), so deleting `=======` left the base marker adjacent to
  real content and it read as prose. Use `git diff --cached --check`, which
  knows all four forms and exits 2; and for a merge, the check that actually
  matters is not "no markers" but "both parents' content survived" — set
  containment of each parent's lines against the merged file, which takes four
  lines of Python and cannot be fooled by a form you forgot.
  (coordinator, 2026-07-27, #305)
- **A quiet dreamer with a clean tree can be mid-run.** At 18:25 this
  coordinator concluded dreamer-reviewsplit's batch was over from four signals,
  every one of them real: 21 minutes without a commit, a clean worktree, a dream
  file written (which dreamers write when finishing), and three unanswered
  inbox messages. On that conclusion it killed the dreamer's `--autoreload` dev
  server and a second server it read as a guard orphan — and the dreamer had a
  LIVE `just guards` run, discoverable in one command: its server's parent was
  `bash /run/user/1000/just/just-*/guards` with cwd in its worktree. All four
  signals are ALSO what a dreamer looks like while a guard suite runs: guards
  commit nothing, touch nothing tracked, and occupy it for minutes at a time
  during which it reads no inbox. Silence and a clean tree describe the work
  not landing; they say nothing about whether it stopped. Before acting on
  "it is done", walk the process tree — `ps -o ppid= -p <pid>` up to init on
  anything holding a guard port. Same shape as #203's orphan rule: age and
  idleness prove nothing, provenance proves it.
  (coordinator, 2026-07-27, #305)
- **A precondition assertion is decorative if the shell chains past it.** The
  #308 close ran a `python3` edit that opened with `assert m, "#308 block not
  found"`, and the regex was stale (it expected `#311` to follow #308; filing
  #311-#313 at the top of Open had put `#303` there). The assertion fired
  exactly as designed — and the commit landed anyway, because the two commands
  were joined with `;` instead of `&&`. The result is the worst of both: a
  correct `transitions.md`, a commit message announcing the close, and a ledger
  still listing the task Open. Guarded edits and the commit that records them
  are ONE operation; join them with `&&`, or put the commit in a separate call
  after reading the guard's output. This is the same family as "assert in the
  check the precondition the check depends on" (CLAUDE.md) with the failure one
  level out: the precondition was asserted, and nothing was listening.
  (coordinator, 2026-07-27, #308)
- **Piping a dispatched agent's stdout through `tail` destroys the whole log if
  it dies.** #312's ccc subagent was launched with `... | tail -40` so the
  coordinator would get a tidy summary. `tail` buffers until its input closes,
  so the task output file sat at 0 bytes for twelve minutes, and when the agent
  was killed the entire transcript went with it — no report, no error, no clue
  why it died, and four modified files sitting uncommitted in the worktree. The
  work was recoverable only because a worktree is a directory on disk. This is
  the existing rule (*every subagent reports through a FILE, because a final
  message is a channel nobody reads back*) applied one level lower: the
  TRANSPORT needs a file too. Redirect to a log with `> log 2>&1` and `tail` the
  file when you want to look; never make the pipe the only copy. Corollary for
  diagnosis: while an agent is alive, the state of its worktree is a better
  liveness signal than its stdout, and `git status --porcelain` there costs
  nothing.
  (coordinator, 2026-07-27, #312)

- **"No process matches the tool's name" is not a liveness test, and the
  destructive step must not be the one that asks.** At 19:53 the coordinator
  ran `ps | grep -E "opencode"`, saw one match, and concluded a second ccc
  agent had exited. At 19:58 that agent committed. At 20:00 the coordinator
  removed its worktree with `--force`. **The grep could not have found it**: a
  `ccc` agent's visible process is a `zsh -c` wrapper, so its command line
  never contains the tool's name — the check had no chance of being right and
  looked authoritative anyway. Four other signals agreed with the wrong answer
  (quiet log, three merged commits, a clean tree, a finished-looking final
  entry) because every one of them also describes an agent mid-increment; this
  is the second time in one session that agreement among weak signals stood in
  for one strong one. **The mechanical test needs no judgement: does any live
  process have that directory as its `cwd`** (`readlink /proc/<pid>/cwd`) —
  the same discriminator #203 uses in the opposite direction to find a server
  whose lane is *gone*. The stranded agent's own cwd read
  `…/311-guards (deleted)`, which is how the mistake was finally noticed. Cost
  here was small only by luck: the dismiss work survived **because it was a
  commit**, and `--force` is precisely the flag that declines to ask. Filed as
  #316 so removal refuses instead of the operator remembering.
  (coordinator, 2026-07-27, #311/#316)

- **A pid that is "report only" when you brief an agent can be "kill me" by the
  time the agent runs.** #203's reaper was briefed with two live pids named as
  report-not-kill test cases, and it reaped both. Its account held on
  inspection: between dispatch and its run, both lanes had been cleaned up, so
  their cwds went `(deleted)` and they stopped being the judgement calls the
  brief described — they became mechanically dead-lane, which is the one class
  the tool may kill. **The brief encoded a classification with a shelf life and
  called it an instruction.** Two rules follow. For the briefer: name the
  PROPERTY you mean ("anything whose cwd is a live worktree"), never a pid list,
  because a pid is a snapshot of a classification. For the tool: a machine-wide
  sweep must default to naming what it would do and require a second
  confirmation — which is what the agent then built, unprompted, as its own
  response. And note the shape of the near-miss: its dry-run PRINTED
  `DREAMWORK_REAP_NEVER_KILL=897036,3408270` as the way to spare them, and it
  ran the sweep without exporting it. **A safety mechanism you were told about
  and did not use is not a safety mechanism**, which is the argument for the
  refusal gate over the advisory hint.
  (ccc-glm52-203 + coordinator, 2026-07-27, #203)

- **A field computed for a display note is not a guard, and it reads like one.**
  The same reaper computed `is_deployed` and printed `note=deployed-dashboard`
  beside the record — so the deployed instance looked accounted for. The kill
  path never consulted it, and a deployed dashboard with a `(deleted)` cwd
  classified as dead-lane like any orphan; `--all-dead --yes` SIGTERMed the one
  server the human actually reads. Reachable by routine means: `just deploy`
  starts the snapshot from the current directory, so deploy from a worktree,
  remove the worktree later, and the record builds itself. When reviewing a tool
  that acts destructively, **grep every protective-sounding field for a SECOND
  use** — the one where a decision is made. One use means it is a label.
  (coordinator, 2026-07-27, #203)

- **The push channel to him is dead, and the loop found out by trying to use
  it.** `attn` exited 403 at 20:17: *"You have run out of credits or need a Grok
  subscription."* This is #190 verbatim — the loop cannot reach him and only the
  dashboard can say so — now with a concrete cause rather than a suspicion, and
  it is a QUOTA failure, so it will recur on its own schedule and no code change
  here prevents it. The operational consequence while it lasts: anything the
  loop needs him for is only discoverable by him opening the dashboard, so
  questions.md and the dashboard's own surfaces are the whole channel. Do not
  read a silent human as an absent one.
  (coordinator, 2026-07-27, #190)

- **A test that fakes the code's dependency can end up asserting a property of
  the fake.** Twice in two hours, both times on a red proof that came back
  GREEN. (a) #320's fixture built the relevant-commit list itself instead of
  calling `window_positions`, so reverting the window's UNIT — the single
  decision the test was named for — changed nothing it could see. (b) #321's
  fake `styleguide_added_text` returned `""` for non-styleguide commits, so
  deleting the styleguide-file filter changed nothing either; the input could
  not reach the branch under test. Both read as thorough unit tests and both
  were structurally incapable of failing. **The tell is cheap: after writing a
  test that patches anything, ask which line of production code would have to
  change for this to fail — then change it and watch.** Red-first catches this
  and nothing else does; it is why the rule is a rule and not a preference.

- **An agent can finish the work and die before committing it, and that looks
  identical to an agent that produced nothing.** ccc-glm52-192 built
  `report.mjs`, converted three guards, ran its crash proofs — and exited in the
  breath before `git commit`. `occupied.py` correctly reported the worktree
  CLEAR and `git log master..HEAD` was empty, so both liveness and commit
  history said "nothing here". The work was sitting in the working tree.
  **So the two checks before writing an agent off are not one check:** ask
  whether anyone is still in there (`occupied.py`), and ask whether anything is
  in there (`git status --porcelain`, including `??`). The first protects a live
  agent (#316, learned by destroying one); the second protects a dead one's
  output. A worktree that is clear AND dirty is the case both were written for
  and neither names.

- **A background task reported "completed" is not a command that finished.** The
  harness announced `bpn1w66nw completed (exit code 0)` while `just guards` was
  still running — the same task id then announced completion a SECOND time when
  it genuinely ended. In between, its log held 38 PASS of 42 and its
  `echo exit=$?` line had never run, so the log looked like a suite that died
  partway. Acting on that reading, the next `just guards` collided with the
  still-live server and #203's pre-flight refused it, which then read as a
  stale-server orphan; the reaper (correctly) declined to kill it, and the
  actual parent turned out to be the live recipe `bash /run/user/1000/just/*/guards`.
  **Two cheap discriminators, before concluding anything about a background
  command: `kill -0 <recipe pid>` and whether the log's last line is a verdict
  or just the last thing printed so far.** An empty `exit=` capture means the
  command has not reached it, never that it exited 0. Chaining
  `cmd > log; echo exit=$?; grep …` also hands the TASK's exit status to the
  grep, so the summary's exit code describes the grep and not the command.

- **Match the liveness instrument to the agent KIND.** `occupied.py` reads
  `/proc/<pid>/cwd`, so it answers for process-backed agents (`ccc`, shells,
  servers) and reports **`clear` for a native subagent working at full tilt** —
  a native agent owns no process with a cwd in the tree, so there is nothing to
  read. The trap is that `clear` plus a dirty tree is *also* the exact signature
  of the died-before-committing case recorded a lesson above, and that case's
  remedy is **commit the tree** — which, applied to a live native agent, buries
  the increment it is still writing. That sequence was started here on
  2026-07-27 against `tmpl325` and stopped one step short by `stat`: three files
  written in the previous 70 seconds. **For a native agent the instruments are
  file mtimes and whether its completion notification actually arrived.** The
  caveat now prints in `occupied.py`'s own `clear` output, is asserted by
  `test_clear_names_the_kind_of_agent_it_cannot_see`, and is in `lifecycle.md`
  step 1 and the checklist — because a warning that lives only here is read by
  nobody standing at the decision.

- **A coordinator's confident diagnosis, handed to an agent as "the likely one",
  is a steer toward the wrong fix.** For #269 I read his word *"autoreload"*, found
  the live tick re-render, and wrote into both the brief and the ledger that this
  was probably the biting mode — with the plausible mechanism spelled out (the
  textarea is a new node after a re-render, so the typed text goes with the old
  one). It was wrong: #118's in-memory snapshot already covered that path, and the
  real loss was the plain full reload, which is what he actually said. What saved
  it was one line in the brief — *reproduce both modes first and say which you
  reproduced* — so the agent measured before building and reported the correction.
  **Write the hypothesis down, but always require reproduction to rank the modes,
  and never let the ledger keep the guess without the measurement beside it.** A
  diagnosis in a task entry reads as established fact to whoever picks it up next.
  The corrected entry keeps both, deliberately.

- **The strongest guard evidence is a DISCRIMINATING red, not a red.** #269's guard
  drives two loss modes; run against pre-fix code it returned mode 2 PASS and mode
  1 FAIL. That single asymmetry proves far more than an all-red run would: it shows
  the guard distinguishes the path that was already covered from the path that was
  broken, so it cannot be passing for an unrelated reason. When a check covers
  several mechanisms, **look at the SHAPE of the red, not just its exit code** — a
  hollow check tends to move all its assertions together. (Same run, honestly: one
  assertion — "a successful answer clears the draft" — passed pre-fix vacuously,
  nothing having been stored to clear. Count such an assertion out of the proof.)

- **Four traps in checks, all found by `tmpl325` inside one task (#325), each a
  check that passed with the code it named deleted.** Worth keeping together
  because they are one species: an assertion whose subject is not what its name
  claims. (1) **A self-documenting HTML template cannot contain its own
  markers** — documenting a `<!--…-->` syntax inside an HTML comment terminates
  that comment at the first close sequence and spills the rest into the page;
  guard it in code, since a note is read after the damage. (2) **"the selector
  occurs somewhere in the stylesheet" is not "the component is styled"** —
  `@media print`'s `break-inside` lists mention many components, so a presence
  check over all contexts passes with the component's real rule deleted; require
  the unconditional context AND a non-empty declaration set. (3) **An
  indentation check must assert on a continuation line** — the first line
  inherits the template's literal whitespace and passes with the formatting code
  removed. (4) **A test named for a property it cannot fail on is worse than no
  test**: `stamp_is_derived_from_bytes` passed against a hardcoded digest. When a
  name claims derivation, the assertion must **vary the input** and watch the
  output move.

- **Long commit messages go through `git commit -F <file>`, not `-m "…"`.** Three
  shell-quoting incidents in one evening, all in the same family: `?` characters
  in a message glob-expanded and killed the commit (`no matches found: ??`);
  `echo "exit=$?"` after a pipe reported the exit status of `tail` rather than the
  command being verified, twice, once concluding a real failure was a success; and
  `just guards port=39895` passed the literal string `port=39895` as the
  positional argument. The messages here are long by design — they carry the
  reasoning — which makes `-m` the wrong tool for them, and a scratch file is one
  extra call. For exit status: never read `$?` through a pipe; redirect to a file
  and check the status directly.

- **Pin the EXPLICIT ccc alias (`@oc-glm52`), never the generic one (`@glm52`).**
  Tonight `@glm52` resolved to `runner=opencode provider=zai-coding-plan` for five
  successful agents and then, an hour later, to `runner=grok provider=llmp` for the
  sixth — the alias config changed under the loop. The grok-runner agent produced
  **127 bytes of log and zero file writes in twelve minutes** while sitting in
  state `S`, i.e. live and silent, which is the failure mode hardest to tell from
  slow. `ccc --help` prints the resolved alias table; `@oc-glm52` and `@gk-glm52`
  name the runner explicitly and cannot drift. **Symptom to watch for:** a log that
  is only a warning line after several minutes, when the working runner streams
  hundreds of KB. Check `wc -c` on the log and `find -newermt` in the worktree
  before assuming an agent is merely thinking.

- **Killing a `ccc` wrapper does NOT kill the runner it spawned.** `kill <ccc pid>`
  returned success and `occupied.py` then showed the child — `grok --model glm-5.2
  --always-approve -p …` — still live with its cwd in the same worktree. Twenty
  seconds later a replacement agent was launched there, so for a moment **two
  agents shared one worktree**, which is precisely the split brain the disjointness
  invariant exists to prevent. **After killing any dispatched agent, re-run
  `occupied.py` on its worktree and kill what remains before launching a
  replacement** — the wrapper is not the process doing the work, and the same fact
  is already recorded in the other direction (a ccc agent's visible process is a
  shell wrapper, so `ps | grep opencode` can never find it).

- **A stand-down MESSAGE is not a retirement mechanism; `TaskStop` is.** `tmpl325`
  was sent an explicit "stand down, your batch is complete, nothing further
  needed" after its work merged and its worktree was removed — and then reported
  itself idle-and-available **twice**, sixteen minutes apart. It had nowhere to
  work and nothing to do, and it was still alive. SKILL.md already says retiring
  is done when the harness says it terminated, not when the agent says so, and
  notes it happened twice in one day; this is the third, and the first where a
  courteous stand-down message was mistaken for the act. **The symptom is
  repeated idle notifications from an agent whose work has landed** — and that is
  a reliable signal, because an agent that has actually exited cannot send one.
  `TaskStop({task_id: "<name>"})` is the act; send the message for the agent's
  benefit if you like, then stop it.

- **Write the DOCUMENTED status key, not a private one beside it.** This session
  wrote its runtime state into an ad-hoc `dreamers` key while `agents` — the key
  with two readers (`watch.py`'s glance and `dreamhub`'s `/hub.json`) — sat
  untouched for ~40 minutes still listing two retired agents as `in_flight: true`.
  The deployed dashboard therefore named departed agents as working, which is the
  one thing a liveness surface must never do, and nothing complained: a stale
  value and a fresh one are the same shape. `file-formats.md` says `in_flight` is
  **one line of prose**; a bool there renders literally as `doing: true`, because
  `watch.py` `String()`s it. **Before inventing a status field, grep
  `file-formats.md` for the one that already exists** — and if a wholesale rewrite
  drops a key, `#303`'s `.status-keys` memo will make you say the removal was
  deliberate, which is the guardrail working.

- **A measurement can be correct and answer the wrong question.** `#327` reported
  that the landed reader misses space-joined bold id spans. I challenged it: I
  measured `LEDGER_ENTRY` over entry heads with every separator and got **0
  missed**, and the spans it named turned out to sit mid-sentence in prose. My
  measurement was right and irrelevant — the defect is in
  `LEDGER_COMBINED_MENTION`, a *different* reader whose whole job is harvesting ids
  from roll-up prose. The finding was real and my refutation was not. **When
  refuting a claim about "the reader", make the claimant name the reader and the
  line before concluding anything** — asking for that is what resolved it, and it
  cost one message instead of a wrongly-dropped P2. Asking a subagent to
  substantiate is cheap; deciding it is wrong from your own adjacent measurement is
  not.

- **Assign guard ownership by NAME, never by directory glob — a UI change drags
  its guard along with it.** I dispatched `#324` owning `dev/capture/*.mjs`
  (a mechanical sweep converting 15 hand-rolled reporters) while `fade326` was
  already out owning `watch.py` plus, as I wrote it, `dev/capture/qfade.mjs`. Both
  then edited `dev/capture/reviewsplit.mjs`, for entirely orthogonal reasons:
  `#326` moved the scroller from `.qa` to `.qa > .qbody`, so its guard had to
  re-point or it would assert on the wrong element; `#324` rewrites the same
  file's `checks[]`/`process.exitCode` tail. Neither agent did anything wrong —
  **the ownership assignment was wrong**, because a change to a surface almost
  always forces a change to the guard that watches it, and a directory glob
  silently claims that guard for someone else. The tell is that the collision was
  invisible from both sides: each agent saw a file inside the scope it was given.
  **So: when a dreamer owns a UI surface, it owns that surface's guards too, and
  a sweep over a guard directory is scoped by explicit filename list minus
  whatever is currently held.** And when the collision already exists and one of
  the two is a `ccc` agent — non-interactive, single prompt, no inbox — it cannot
  be steered mid-run, so the only lever left is **merge order**: land the semantic
  change first and rebase the mechanical sweep onto it, never the reverse, because
  a conversion merged first turns the semantic diff into a conflict against code
  that no longer exists.

- **`git commit -m` silently eats `**bold**` in this shell — so in this repo, always
  `-F <file>`.** The shell is zsh, where `**` is a recursive glob; a message quoting
  a ledger entry's `**#96 stage 1**` came out as "whose only span is  — prose", with
  the token simply gone and no error, because the pattern matched nothing and zsh
  dropped it. Nothing failed: the commit succeeded and read almost sensibly, which is
  why it survives review. This is not an edge case here — every ledger entry, every
  question title and every author tag in this project is written in `**bold**`, so a
  commit message that quotes durable state is the NORMAL case and `-m` corrupts it.
  Two other members of the same family had already been paid for tonight (`??` and
  `?` in a message about a git status output, which at least errored loudly with
  `no matches found`), and the fix is the same one every time: write the message to a
  file and pass `-F`. The general rule, which is cheaper than remembering the
  metacharacter list: **if a message quotes the contents of a file, it goes through a
  file.**

- **When writing a file a tool parses, run the tool's parser on it before committing —
  and change one character to confirm the check discriminates.** The format doc tells you
  what the shape is; only the parser tells you whether what you wrote IS that shape.
  Learned on the author tags, whose two channels are spelled asymmetrically
  (`- **Note (human, via watch, …)` vs `- **Follow-up (loop, …)`), so `Note (loop, …)`
  matches neither `NOTE_TAGS` nor `ANSWER_TAGS` and silently deletes the words from the
  page. The incident narrative is pruned: that specific failure now has a check,
  `lint.check_author_tags` (#343), and a check no longer has to persuade anyone. What
  survives here is the general habit, which has no check and cannot have one.
- **A hand-rolled scan over `tasks.md` has now lost twice to per-id set membership — stop
  writing them.** Validating #335's new check, the coordinator measured twice that #247 was
  not under `## Open` and was wrong both times: once a regex requiring `- **#247** — ` that
  the real entry did not match, once a section comparison that reported the wrong side of a
  heading. On the strength of those two readings the check looked like it had a false
  positive, and a correct check nearly got sent back. `watch.py`'s own `parse_ledger` settled
  it in one line by returning 247 in the open-id set — and #247 had indeed been sitting open
  while declaring `completed at ba03c1f`, the #261 bug class, invisible to every other check
  because there is no `close(#247)` commit for `check_landed_still_open` to cite. The same
  failure had already happened hours earlier on #331, where an ad-hoc `\*\*([^*]+)\*\*` scan
  claimed 9 missing ids and per-id membership showed all 19 missing. The lesson written then
  said to test ids directly; it was not followed, which is the actual finding here. So,
  operationally: **when the question is "is this id in this section", import the reader the
  rest of the system uses and ask it.** A second regex over the same file is not a second
  opinion — it is one more thing that can be wrong in the same way, and it carries the
  authority of a measurement while having none of the standing. And the reader answers in
  its own units: **`parse_ledger` returns sets of STRING ids**, so `346 in open_ids` is
  silently `False` for an int, with no error and no hint. That happened on #346/#347/#348 —
  the count had risen 111 to 113, the membership test said `{False}`, and the claim was
  written down anyway on the strength of the count. Importing the right reader is half the
  discipline; **checking the type it hands back is the other half**, because a wrong-units
  membership test fails exactly the way a genuinely absent id does.

- **`cd` persists between tool calls, so a worktree dispatch silently redirects every later
  write into that agent's tree.** Right after `cd .worktrees/339-highlight && ccc …`, an
  append meant for the main checkout's `.dreamwork/lessons.md` landed in the RUNNING agent's
  copy — a file it did not own and had no reason to see modified. The tell was `lint.py`
  reporting `status.json absent`, which is impossible in the main checkout and normal in a
  worktree; without that row the edit would have been invisible until the agent's diff looked
  strange. Reverted with `git -C <worktree> checkout --` before it could reach a commit. The
  rule: **after any `cd`, write with absolute paths, or `cd` back in the same command.** The
  repo already insists on staging by explicit path because several agents share the tree;
  this is the same hazard one level up — the path you did not state is chosen for you.

- **A check with a deliberately silent third verdict cannot be read as reassurance about the
  change that produced it.** #339 edited `review-artifact.template.html`, and `template_stamp()`
  digests the frame's bytes precisely so that every templated artifact goes stale. The agent
  rebuilt exactly one of thirteen. `lint.py` said `review/ 13 artifact(s), none stale` — and
  that row is *true* and *useless* here, because `check_review_artifacts` is silent on
  `untemplated` by design (#325 never migrated the old artifacts, and a WARN per run on each
  would be the noise that hides the row that matters). Twelve untemplated + one rebuilt and
  twelve un-rebuilt + one untouched produce the same sentence. The per-file
  `review_artifact.py check` distinguishes them in one command, and it did: 12 `untemplated`,
  1 `current`, so the single rebuild was provably the complete set. The rule: **when a check
  reports a count and suppresses a state, a change that moves things INTO the suppressed
  state makes its summary row unreadable — ask the underlying tool per item instead.** The
  generalisation is worse than it looks, because the row reads as coverage: `13 artifact(s)`
  invites the reader to believe thirteen things were checked.

- **A test can carry the right assertion over a fixture that cannot trigger it, and that reads
  as coverage.** Validating #339, replacing the single line `escaped = html.escape(text,
  quote=False)` with `escaped = text` — raw markup emitted straight into a built artifact —
  left all 758 tests green. `test_highlighting_introduces_no_network_dependency` asserts
  `"<script" not in out`, which is exactly the assertion that should have caught it, over five
  samples containing no `<script`. Its neighbour round-trip test calls `html.unescape` on the
  output before comparing, so a raw `<` and an escaped `&lt;` are the same string by the time
  it asserts. Both are careful, well-documented tests about the right property. This is the
  sibling of the known "the fake returned `''` for exactly the input that would reach the
  branch": there the scaffolding blocked the injection, here the *sample* did. So when
  red-proving, do not only ask "did a test fail" — ask **which** test, and if the one you
  expected stayed green, its fixture is the bug. Three injections were run here to establish
  the suite discriminates at all; two failed small distinct subsets, and the third failing
  nothing is what found this.

- **A check that emits both a verdict and findings must gate the verdict on the
  findings, and no fixture that tests one outcome at a time can catch it when it
  does not.** `check_related_markers` was red-proved with ten injections, eight of
  them discriminating to a single test, and then its FIRST use on the live ledger
  printed `3 related pair(s), all reciprocal` in the same run as `#250 is related
  to #251 but #251 does not say so back`. The summary was unconditional. Every one
  of the eleven fixtures asserted errors **or** the OK line, never both in one run,
  so all eleven were structurally blind to the contradiction — and a reader
  scanning output for the reassuring line would have been told the opposite of the
  truth by the check that had just found it. Red-proving establishes that each
  branch can fail; it says nothing about what the check *says* when two branches
  fire together. So when a check has a summary row, write one test that makes a
  finding fire and asserts the summary is ABSENT. (coordinator, #353, 2026-07-28)
- **A shell's working directory persists across calls, so one `cd` into a worktree
  silently redirects every later verification into the wrong checkout — and it
  fails as a missing file, not as a wrong answer.** A coordinator `cd`'d into
  `.worktrees/264-transition-boundary` to inspect a dreamer's tree, never came
  back, and forty minutes later ran a red-proof there: the snapshot `cp` failed
  because that checkout has no `status.json` (it is gitignored), the injection
  never landed, and the "restore" `cp` failed too. Both errors were one line each
  above a lint run that then reported `absent — written on the first tick`, which
  reads exactly like a clean result if you are looking for the WARN you expected.
  It was luck that the failure mode was a stale `cp` rather than an edit applied
  to the wrong copy of the file. Two habits, both cheap: a coordinator inspecting
  another checkout uses `git -C <path>` and absolute paths, never `cd`; and any
  proof whose setup can fail asserts its setup succeeded before believing its
  result. (coordinator, #362, 2026-07-28)
- **An offset into a file you are also editing goes stale the moment you edit
  earlier in it, and the resulting splice lands in the middle of a neighbour's
  body where nothing reads it as damage.** Folding #229 meant one scripted pass
  over `tasks.md`: bump the next id, cut #229, repoint three dependents, insert
  #373 where #229 had been. The insertion index was found before the three
  repoints, each of which added a line above it, so #373's head was welded into
  `#230`'s body — `settings, ex- **#373** — Build topic chats…` — and because an
  entry head must be line-anchored, #373 was not an entry at all. What caught it
  was not lint but the increment's own before/after `parse_ledger` diff printing
  `new: []` when it had just filed a task. Two habits: recompute every anchor
  **after** the edits that precede it (find the landmark again, do not carry the
  number), and make a rewrite of a structured file assert what it changed — an id
  set before and after costs one line and fails loudly on a corrupt splice that
  reads fine in a diff. The same pass had already welded two `questions.md`
  entries via an `Edit` whose `old_string` spanned an entry boundary; both are the
  one mistake, which is assuming a boundary instead of asserting it. Both were
  free to undo only because a `cp` snapshot was taken first — that habit was
  written down for injections, and it turns out to cover botched edits too.
  (coordinator, #229/#373, 2026-07-28)
- **The same `st_ino` does not mean hardlinked, and the difference decides whether
  an atomic rename strands anything.** #369 was filed, diagnosed, fixed and
  committed on the claim that `~/.claude/settings.json` and
  `~/.claude-w/settings.json` are two hardlinks to one inode, because both stat as
  `256518042`. They are not: `st_nlink` is **1** and `~/.claude` is a *symlink to*
  `~/.claude-w` — one file reached by two paths. Under a directory symlink
  `os.replace` strands nothing, so the silent failure the task was written about
  could not have happened on this machine, and `--apply` was safe against the
  default path all along. The inode was measured; the relationship was inferred
  from it, and inferred wrongly, in a ledger entry that then read as measured for
  four hours. Two habits: when two paths share an inode, print `st_nlink` and
  `os.path.islink` on **every component** before naming the relationship — one
  command, and it is the command that distinguishes the two mechanisms; and when a
  premise is a filesystem fact, re-measure it at fix time rather than trusting the
  entry, because the entry recorded your inference, not your observation. The fix
  itself survives on its own merits (a hardlinked config is a real hazard, and the
  readback plus post-write link check turns a silent class into exit 2), which is
  exactly why the wrong premise could have gone unnoticed: the code was right for
  a reason that was not the stated one. (coordinator, #369, 2026-07-28)
- **A CSS edit to a shared selector in `review-artifact.template.html` must be
  mirrored byte-for-byte in `.dreamwork/review/tasks-page.html`.**
  `test_template_rules_match_the_reference_rule_for_rule` pins every selector the
  two share to identical declarations, and the only documented door for a
  difference (`DECLARATION_DIVERGENCES`) is empty — so a one-line fix like
  `white-space:nowrap` on `.topactions a` reddens the fidelity test unless the
  reference carries it too. tasks-page.html is the hand-rolled artifact the
  template was cut from: untemplated, never rebuilt, and the coupling is manual
  and invisible until `just test` runs. The reference deserves the fix anyway —
  but the next person editing a shared template selector should not have to
  discover the second file by a red test. (dreamer, #347/#372, 2026-07-28-0337-two-seams-in-the-review-frame)
- **`getClientRects().length === 1` on an `inline-flex` element is hollow: the
  box stays one rect while the text wraps inside it.** The natural "did the box
  split?" check reported `1` for four nav labels that were visibly broken
  ("measur/ed"). The instrument that discriminates is a `Range` over each WORD —
  a word split mid-character spans two lines and yields two rects while its box
  stays one — skipping words with `-` or `/`, where a break is correct
  typography. The inverse of the earlier Range lesson (rects are per inline box):
  there the *contents* were stable and the *container* misbehaved; here the
  container reports stable geometry while its contents break. A box-level or
  end-state check passes over exactly this case. (dreamer, #347, 2026-07-28-0337-two-seams-in-the-review-frame)
- **A check that declines to run must say so; a bare `return` turns "cannot
  check" into "nothing to fix".** `check_cited_shas` had four silent exits, and
  its own docstring stated the very principle they broke. The evidence arrived as
  a flake: one full-suite run failed on `test_a_dead_cited_sha_warns`, then
  twenty-five isolated runs and a full re-run passed and no single other test file
  reproduced it — so the check had skipped, and there was no row anywhere naming
  which exit it took. A silent skip is undiagnosable by construction. Fixing it
  also exposed a defect nothing had noticed: `zip(shas, stdout.splitlines())`
  absorbed a short answer from `git cat-file --batch-check`, and the red proof
  showed the check reporting *"2 cited commit(s) all resolve"* having looked at
  one — the dead sha was in the truncated tail. The level is the discrimination,
  not the silence: WARN when `.git` is present and git still failed, OK when the
  target simply is not a repository. (coordinator, #380)
- **A validator whose pattern only matches WELL-FORMED values is blind to a
  malformed one — the absence looks identical to "nothing to check".**
  `check_cited_shas` exists to answer "does this citation point at a commit", and
  it could not see `` landed `<pending>` `` at all, because its regex requires
  7-40 hex characters. So the one entry in the ledger whose citation pointed at
  nothing was invisible to precisely the check named after that question, and
  #362 sat done-but-open for hours until someone found it by accident. Ask of any
  validator: what does a value have to look like to escape the pattern entirely?
  That class needs its own row, not a wider pattern — the wider rule was tried and
  flags four filenames and a run of prose on the live ledger, precision 0-in-4,
  while a closed vocabulary of slot shapes flags all nine real ones and none of
  the four. (coordinator, #381)
- **The claim most likely to be wrong is the one you did the most work on — and
  writing it up carefully is what makes it survive.** Three dispatched lanes in one
  batch each refuted something their brief listed under *"what is established — do
  not re-derive it"*: a fixed-`setTimeout` race that was a wrong CSS selector
  (#382), a wall-clock sampling window that was a `distinct >= 8` frame count on a
  genuinely smooth travel (#383), and an explicit "checked rather than assumed"
  that no guard asserted on the misread node, when one did (#384). Three for three
  against the coordinator, and every error sat inside the most-measured part of the
  brief. The measurements were right every time; the **explanation attached to
  them** was wrong every time. So: mark the join between measured and inferred in
  the brief's own prose — presenting both in one voice under one confident heading
  is what turns a guess into an inherited fact — and attach "refute this if it is
  wrong" to the **named hypothesis** rather than leaving it as general permission
  at the bottom. All three agents used that permission; it is the highest-yield
  line in the template. (coordinator, #382/#383/#384)
- **A well-verified small change costs the same as a well-verified large one, and
  the floor is the verification.** A two-line selector fix (#384) cost 18 minutes;
  rebuilding the sampling instrument in three guards with a load matrix and three
  separate sabotage red-runs (#383) cost 38. Ten times the work for twice the
  clock, because #384's time went almost entirely on proving a neighbouring flake
  was pre-existing — which is exactly what should have happened. Consequence for
  dispatch: a two-line fix does not earn a lane of its own. Batch small mechanical
  fixes into one brief, or do them inline. (coordinator, #384)
- **`git commit` commits the index, not the paths you added — so "stage by
  explicit path" does not stop you burying a concurrent agent's work.** This repo's
  convention existed precisely to prevent that, named `git add -A` as the hazard,
  and was **wrong about the mechanism**: with a lane's test file already staged,
  `git add .dreamwork/tasks.md && git commit -m "file(#387): …"` produced a
  two-file commit carrying `test_user_events_digest.py` inside a ledger commit
  (`12f47e3`). Nothing in my own command hinted at it, and I only found out because
  the lane reported the loss honestly instead of inventing a commit of its own.
  Measured both ways in a scratch repo: with a peer's file staged, `git add mine &&
  git commit` gives a two-file commit; **`git commit --only mine`** gives a
  one-file commit and leaves the peer's file still staged. The general shape:
  **a safeguard can name the right danger and the wrong mechanism, and it then reads
  as protection while providing none** — the way to tell is to reproduce the failure
  it claims to prevent, not to re-read the rule. **And the fix has its own quiet
  edge, found within the hour: `git commit --only <directory>` does not pick up
  untracked files inside it and does not say it skipped them**, so a commit landed
  claiming to add three briefs and carried none. For a new file the sequence is
  `git add <file>` then `git commit --only <file>` — verified to still leave a
  concurrent lane's staged work alone. Both halves of this share one shape: **a git
  command that reads as though it did the thing.** (coordinator, #263 lane A)
- **Before holding a verification for a quiet machine, ask which direction the
  noise pushes the verdict.** I deferred #277's `dreamfade` guard twice waiting for
  an idle box, on the reasonable-sounding grounds that load had already made motion
  guards fail deterministically (125/16, byte-identical failure sets). But the
  failure mode is a *dropped intermediate frame*, so load manufactures false
  **reds** and cannot manufacture a false green. It passed at load 37, and that
  green is *stronger* evidence than one from an idle machine would have been. The
  wait bought nothing and delayed a merge's verification by an hour. The general
  form: **noise that is asymmetric turns one of the two verdicts into proof** — a
  green under conditions that only cause failure is conclusive, so identify the
  asymmetry before deciding a measurement needs better conditions.
  (coordinator, #277)
- **A red-run that depends on a value differing from the platform default is only
  as discriminating as that default — and the plan cannot see the default.** The
  #263 plan prescribed, for `B1`, "delete the `PRAGMA synchronous=FULL` execute and
  the assertion fails". On SQLite 3.53 the compile-time default **is already FULL**,
  so the deletion changed nothing and the prescribed red came back **green**. The
  lane obeyed the rule that a green red-run is a finding rather than a relief: it
  did not conclude the code was fine, it made the pragma load-bearing (pin `NORMAL`,
  then `FULL`) so the deletion genuinely leaves `1`. Verified twice — by the lane and
  independently by the coordinator, `got 1` with seven neighbours green. Two things
  generalise: **a durability setting that happens to match the platform default is
  untested by construction**, and a written red line is a hypothesis about the
  platform, so it earns the same scepticism as the code. (coordinator + lane B, #263)
- **Disjoint files are not disjoint environments, and the loop's invariant only
  covers files.** Five lanes were dispatched with provably disjoint file ownership,
  which is the invariant this skill states. Load then hit **139 on 16 cores**, and
  the cause was not contention — it was **#386's brief, which told it to
  characterise a flake "under moderate load (3 busyloops)"**. It was doing exactly
  what I asked. But #300 was concurrently measuring per-frame motion timing in the
  same tree, and load is the one thing that makes those measurements lie. So two
  lanes that could not possibly touch the same byte were still interfering, through
  the machine. **A lane that deliberately consumes a shared resource — CPU, a port,
  the wall clock — must be scheduled against the lanes that measure it, not merely
  against the lanes that edit the same files.** The scheduling resource is whatever
  is scarce, and CPU is scarce whenever anything timing-sensitive is being verified.
  (coordinator, #300/#386)
- **A one-shot dispatch has no steering channel, and that is a design gap in the
  brief, not a property of the runner.** When I found the load conflict above, there
  was nothing I could do about it: `ccc` lanes report to `.dreamwork/inbox.md` on
  exit and read nothing while running, so a coordinator who spots a problem
  mid-flight can only watch. The skill already knows the fix for dreamers —
  `relay.py` writes to a subagent inbox, and "steering an agent takes two acts:
  write, then wake" — but a brief that never names an inbox to read leaves the
  coordinator mute for the lane's whole life. **Every brief for a lane longer than a
  few minutes should name a file the lane checks between increments**, precisely
  because the thing worth saying mid-flight is usually something neither party could
  have known at dispatch. (coordinator, #300/#386)
- **A load generator that orphans its workers turns a bounded measurement into an
  unbounded CPU leak, and it compounds silently across rounds.** #386's brief asked
  it to characterise a flake "under moderate load (3 busyloops)". Correct ask. But
  each round's `/tmp/busyloop.py` workers were **reparented to `systemd --user`
  (ppid 1092) when their shell exited** and kept spinning: two dead cohorts, six
  processes, up to 18 minutes each, ~5 cores burned for no measurement at all. Load
  read **161 on 16 cores**, of which only four processes belonged to anything live.
  Diagnosing it needs ppid, not `pcpu` — the orphans are indistinguishable from the
  real ones by CPU alone, and identical in `ps` output except for their parent.
  **So: a brief that asks for generated load must also require the generator be
  reaped** (a `try/finally`, a process group killed on exit, or a self-terminating
  worker with a deadline), and a coordinator seeing implausible load should check
  parentage before concluding contention. Killing only the reparented cohort
  restored the machine without corrupting the live measurement. (coordinator, #386)
- **A deferred-commit control makes the durable write a LATE signal, so a
  side-effect check that samples only durable state cannot see the damage it was
  written to catch.** My #300 acceptance criterion said: count `/run-mode` POSTs,
  `watch-events.log` lines and the run-mode file's bytes across a hover sweep, and
  assert them unchanged. Sound-looking, and **unsound**: #290's arm deliberately
  does not POST for **ten seconds**, so a hover that calls `pickRunMode` lights the
  arm UI, writes pending `localStorage` and starts the countdown while every signal
  I named stays silent. The lane's first red-run of that check came back **green
  with the bug in place**, and it applied the rule instead of the instruction. The
  fix is to assert the signals that flip at **selection** rather than at commit —
  `#runcount` must not read `arms in`, and `dw:run-mode-pending:` keys must be
  unchanged — with the durable signals kept as necessary-but-not-sufficient.
  Generalises to every arm, confirm, and debounce-to-write control: **sample the
  pending surface, or you only observe the world ten seconds later, which is also
  after the damage is done.** (coordinator + #300 lane, #300/#290)
- **The strongest red is one whose failure names the real-world consequence.**
  Lane C's `C3` red — replacing temp-then-`os.replace` with the direct
  `open(path, "w")` that `watch.py:8462` does today — did not merely fail an
  assertion: it printed `b'' != b'the quick brown fox…'`. The file was **emptied**.
  That is exactly what a crash mid-write does to `questions.md` or `answers.md`
  right now, and reading the diff of that failure tells you why the increment
  matters in a way "assertion failed" never would. Worth choosing injections for
  this property: the one that produces a legible catastrophe teaches more than the
  one that produces a boolean. (coordinator, #263 lane C)
- **Defence-in-depth and a discriminating red are in direct tension: where two
  mechanisms each prevent the bug, deleting one proves nothing.** The #263 plan named
  `UNIQUE(client_action_id)` as the red line for "two processes, one UUID, one
  receipt". Removing it leaves the suite **green** — verified by the lane and again
  independently — because `BEGIN IMMEDIATE` plus the SELECT-before-insert already
  serialise the writers, so the second process replays and never reaches the
  constraint. The lane did not stop at the finding: it probed the mechanism, and
  `DEFERRED` + no `UNIQUE` does give `database is locked`, so the concurrency is real
  and `UNIQUE` merely is not the line carrying it. **This was the second wrong red
  line in one plan** — `B1`'s assumed a pragma differing from the platform default —
  and both share a shape: **a plan written before the code names the mechanism the
  author imagines will carry the property, not the one that ends up carrying it.**
  Two consequences. Keep the redundant layer (it is not wasted) but stop claiming it
  is tested; and when a red comes back green, the question is not "is the code fine"
  but **"which layer is actually holding this up?"** — answering that is what turns a
  hollow check into a correct one. (coordinator + lane B2, #263)
- **A guard that decouples its action from its trace has a race by construction, and
  this repo has now paid for it twice.** `#386`'s `gitrow` did
  `p.evaluate(TRACE(ms))` — starting a bounded trace window — then dispatched the
  click as a *separate* Playwright roundtrip. Under load the roundtrip's latency put
  the click outside the window, so the trace honestly recorded 0px and the guard read
  as "nothing moved". The fix, and the idiom to reuse, is `dreamfade.mjs`'s: **dispatch
  the action INSIDE the trace evaluate**, so action and observation share one browser
  roundtrip and no amount of transport latency can separate them. The tell that
  distinguishes this from a real motion bug: the *settled* case fails identically —
  `#386`'s CLOSE gesture, on a row open through several roundtrips, failed the same
  0px way, and a settled row cannot be mid-arrival. **When both a transitional and a
  settled case fail the same way, suspect the instrument's timing, not the page.**
  (#386 lane, recorded by coordinator)
- **Where a check compares against a captured value, make the capture's honesty
  MACHINE-CHECKED rather than documented — and resolve it by content, not by a pinned
  sha.** My #367 criterion asked the lane to *state in its report* how it obtained the
  pre-change render, because the trap is recomputing both sides with the new code so
  they move together (the shape behind two false greens here). The lane did better
  than the criterion: `test_a_source_with_no_marks_renders_byte_identically_apart_from_the_stamp`
  compares against a frozen digest **and then proves that digest honest** by checking
  the pre-change builder out of git, re-running it, and asserting agreement — with a
  guard that the resolved ref does **not** already contain the new constant, since
  otherwise the comparison would be new-vs-new and prove nothing. It resolves that ref
  by **content** (newest commit whose `review_artifact.py` lacks `MARKS_WARN_AT`), so a
  rebase that rewrites shas cannot quietly turn the proof into a no-op. Verified
  independently: it lands on `12d17ad`, which carries neither `MARKS_WARN_AT` nor
  `essential_marks`. **The general upgrade: a prose claim in a report protects the
  first reader; an assertion protects every future one.** Prefer having the test
  re-derive its own baseline over asking an author to promise they captured it right.
  (#367 lane, recorded by coordinator)
- **A property that is a PERMISSION rather than a behaviour has no behavioural red,
  so assert it structurally and keep the behavioural check as the regression net.**
  Lane F's `F3` had to prove "only `replay` may cause a domain effect". The natural
  test snapshots the managed files, runs `list`/`show`/`health`, and asserts
  byte-identical — and it **cannot be red**, because read commands do not write
  anyway: *"doesn't write"* and *"is forbidden to write"* produce identical file
  bytes. The lane's first attempt at a red (route every command through the write
  path) broke `F1`'s list test too, because list's success **is** the thing the guard
  classifies, so it was not discriminating either. What made it discriminate: dispatch
  the permitted commands by membership in `READ_COMMANDS` **upstream** of the guard, so
  widening the guard to `return True` cannot reach them — and then assert the
  classification itself, `{c for c in COMMANDS if _write_authorized(c)} == {"replay",
  "purge"}`. **The two checks earn different places: the structural assertion is the
  discriminating red, the behavioural snapshot is the net that catches the next person
  who accidentally makes a read command write** (a cache, a log, an mtime touch).
  Distinct from "assert the outcome, not the mechanism" — this is about properties that
  are facts of the dispatch table rather than of any run. (#263 lane F)
- **`grep -c` exits 1 when the count is zero, so the success case breaks an `&&`
  chain.** The #367 lane lost the tail of a verification sequence to this: it was
  counting occurrences it *wanted* to be zero, got zero, and every check after the
  `&&` silently did not run. The shell cannot tell "no matches" from "failed", and
  neither could the transcript. Append `|| true` whenever the **count itself** is the
  result rather than the match — and more generally, a verification chain joined by
  `&&` reports a skipped tail as a pass, so prefer `;` with per-step echoes for
  anything whose zero is a legitimate answer. (#367 lane)
- **Dispatching a lane is `ccc … &` in a FOREGROUND harness call — never `&` inside a
  harness-backgrounded one.** I have now made this mistake twice, so the fix is a
  recipe rather than a caution. `ccc` blocks for the lane's whole life, so it needs a
  `&`; but if the harness call is *also* backgrounded, the harness watches the wrapper
  shell, which exits in milliseconds. It then reports the dispatch "completed (exit
  code 0)" while the lane is thirty seconds old, and **no completion notification ever
  arrives** — so a coordinator waiting to be told a lane finished waits forever, and
  the failure looks exactly like a lane that is still working. Correct form: one
  ordinary (non-backgrounded) Bash call containing `ccc @runner "…" > /dev/null 2>&1 &`
  per lane, then `sleep 3` and `pgrep -af "^ccc @"` **in the same call** to prove they
  came up. `pgrep -c "^ccc @"` returns 0 without `-f`, because the pattern matches the
  command *name* and not its arguments — so verify with `-f` or the proof lies too.
  Consequence when it happens: the lanes are fine, only the notification is lost, so
  fall back to polling `pgrep` and `.dreamwork/inbox.md`.
  **CORRECTED 2026-07-28 11:31, and the correction cost two lanes: `> /dev/null 2>&1` in
  the recipe above is WRONG. Use `> "$LOG" 2>&1`.** `ccc @grok` began returning
  `Unauthorized (401) … Invalid or expired credentials` mid-day; two lanes died at three
  seconds and the only artifact naming the cause went to `/dev/null`. **A lane that dies
  before its first token is indistinguishable from one that ran and reported nothing** —
  same clean worktree, same empty inbox, same absent process — and the two have opposite
  fixes. `ccc`'s own run log does not cover for it: `~/.local/state/cc-w/ccc/runs/<run>/`
  holds `output.txt` and `transcript.txt`, and for a 401 death **both are zero bytes**,
  because the error is on stderr only.
  **And the `-f` half of this entry did not save me either, which is the part worth
  keeping.** It was written here, correctly, before today. I still ran `pgrep -c "ccc @"`,
  read `0` for a live lane, declared it dead, and started a second lane **in the same
  worktree** — two agents on one file set, the split-brain the disjointness invariant
  exists to prevent. So: **a lesson only prevents the mistake if it is read at the moment
  of the mistake**, and a file this long is not read at that moment. The durable fix is
  not a better entry here; it is putting the flag in the recipe you copy — which is why
  the corrected form appears above rather than as a caution below it. Liveness is
  `pgrep -af`; before declaring a lane dead require **two** agreeing signals: no process
  *by command line*, and either an error in `$LOG` or an exit trailer. A quiet transcript
  is not one of them — grok and pi runners write **zero bytes until exit**.
- **A lane's stated uncertainty is a map to the defect, not a question to answer.**
  #367 increment 1 ended its report with an honest flag: a valueless `data-mark` is
  ignored rather than refused, the contract is silent, *tell me if you'd rather it
  refuse*. The tempting move is to rule on it. I probed the area around it instead —
  four inputs through the real parser — and **the case it asked about was correct
  while the case one step over was the bug**: `data-mark=""` and `data-mark="   "`
  were collected as marks with unreadable labels, untested (#389). This is not
  carelessness in the lane; it is the shape of attention. A builder audits the case it
  *noticed*. Enumerating that case's neighbours is cheap for whoever arrives with no
  investment in the design, and structurally hard for whoever wrote it. Two
  consequences: brief lanes to **enumerate the neighbours of any edge case they flag**
  before reporting; and as a reviewer, spend attention on the boundary of a report's
  stated uncertainty rather than on re-running its reds — across ten lanes here,
  re-running a lane's reds almost always confirms it, and probing what it said it was
  unsure about almost always finds something. (Sample the re-runs rather than dropping
  them: they are cheap *because* they confirm, and their value is keeping reports
  honest, not their finding rate.)
- **Quote the human's ruling verbatim and show the derived boundary as derived —
  a paraphrase inherits his authority while no longer being his words.** He ruled
  *"soft 7, hard 15"* on #367's cap. Two of my documents recorded that as "a warning at
  7", which reads as faithful and is off by one: a cap of 7 that warns *at* 7 is a cap
  of 6, and the code correctly has `MARKS_WARN_AT = 8`. The #367 builder caught the
  disagreement because `file-formats.md` and its brief agreed with each other against
  the plan. The damage was never the typo — it is that a builder could have
  implemented a cap he never set **and cited my plan for it**. So: keep his words in
  quotes, and put the derived constant beside them visibly derived (`soft 7 →
  MARKS_WARN_AT = 8`) so a reader checks arithmetic instead of trusting prose. Two
  documents restating one ruling in their own words is the same single-source failure
  `lint.py` enforces against for file formats; his rulings deserve that discipline
  more, not less. (#367)
- **A new file in a registry-checked directory reddens every OTHER lane's baseline until
  it is registered — so a lane can be handed a red `just test` it did not cause and
  cannot fix.** #367's measurement lane added `dev/capture/marktab-geometry.mjs`, which
  `lint.py`'s `check_guards_registered` correctly flags as a guard that gates nothing.
  That flag is a `test_lint.py` failure, so **lane D's `just test` went red on a file in
  a directory lane D was forbidden to touch.** Lane D handled it right — named it
  pre-existing, attributed it, did not chase it — but it burned attention and it could
  as easily have been read as its own breakage. Two consequences: when dispatching a
  lane that will create a file in a directory something enumerates (guards, plugins,
  fixtures, migrations), **either register it in the same commit or tell the lane to**,
  and put the registration in its acceptance criteria; and when two lanes run
  concurrently, a brief's stated baseline test count is a **fact with a short shelf
  life** — say "take the count from the tree, not from this brief". Disjoint file
  ownership does not give disjoint test suites, which is the same lesson as disjoint
  files not giving disjoint environments, arriving through a different door.
- **"Probably load flakes" is a hypothesis, and the quiet re-run is how you learn which
  one was real — mine hid a P1 behind ten correct guesses.** #385 finished with a full
  `just test` showing eleven failing guards at load 121, attributed them to
  multi-lane contention, and said honestly that it had not re-run quietly. It was right
  about **ten of the eleven** — they all pass at load 37–48. The eleventh, `prominence`,
  fails **every time, in isolation, on all four of its surfaces** (#391): a real
  regression that predates today's lanes and had been sitting behind a load-flake
  reading. The asymmetry already recorded here — *these guards fail by dropping frames,
  so load manufactures false reds only; a green under load is conclusive and a red needs
  a re-run* — is what makes the re-run cheap and mandatory, and this is the first time it
  paid a P1. **A high hit rate on "that's just noise" is exactly what makes the exception
  invisible:** ten correct dismissals train you to accept the eleventh. So the rule is
  not "distrust the lane" — the lane reasoned well and disclosed the gap — it is
  **never let a load-attributed red be closed by attribution; close it with a quiet
  run, and if the fleet is busy, leave it open and named.**
- **A readiness probe that falls through on failure turns a config error into a mystery,
  and I did it to myself while investigating #388.** I spawned `watch.py` with a flag it
  does not have (`--no-open`), so argparse killed it instantly; my `for i in $(seq 1 40)`
  curl loop then failed forty times, **fell through without checking**, and the guard
  reported `ERR_CONNECTION_REFUSED`. I briefly read that as a guard bug. That is exactly
  #388's thesis reproduced first-hand: **`ECONNREFUSED` cannot distinguish "the server was
  starved" from "the server never started"**, and the fix is not a longer timeout but a
  probe whose failure is **fatal and named** — `if [ "$up" != yes ]; then echo "server
  never came up in Ns"; cat the log; exit 1; fi`. Print the server's own stderr on that
  path; mine said `unrecognized arguments` the whole time and nobody was looking.
- **When a fix changes two things to cure one symptom, find out which one carried it —
  the other may be silently breaking something else.** #277 (`22f9884`) was quieting an
  8px summary shift under the pointer during a fold. It made two changes: it rewrote the
  shared rule `details[open] { padding:.5rem 0 }` to `padding:0 0 .5rem`, and it added
  `.qa.folded .qfold { margin:0 }`. The padding rewrite **silently broke #169** — "an
  expanded element becomes prominent, not just taller" — on all four surfaces, for three
  hours, behind a load-flake reading (#391). Restoring the padding and re-running #277's
  **own** guard plus eight neighbours: **all nine pass.** So the margin fix was the
  load-bearing half and the padding rewrite was never needed for #277's purpose at all.
  Two habits fall out. **A deliberate change to a SHARED rule is the one to isolate:**
  `details[open]` styles four surfaces, so a one-sided rewrite trades a contract nobody
  in that commit was thinking about. And **when you fix a regression whose cause was
  itself an intentional fix, re-run the guard of the task that made it** — otherwise you
  have only moved the breakage back where it came from, and neither commit's author will
  see it. That check was outside the fixing lane's remit (it was forbidden the full
  sweep), so it is the coordinator's, and it is the whole difference between "restored
  #169" and "restored #169 and confirmed #277 never needed the trade".
- **When two lanes need the same file, the answer is sequencing or a worktree — never "check
  `git diff` before you commit". That is a mitigation dressed as an invariant, and I nearly
  shipped one.** Writing #354 increment 1's brief I found it needed `watch.py`, which #381's
  lane also needs for a small dashboard line. Rather than sequence them I wrote a note
  calling the overlap *"deliberate"*, split the file by region (the request path versus the
  page), and told the lane to stop if it saw changes that were not its own. Every part of
  that is wrong in the same way: **`git commit --only watch.py` still sweeps in a concurrent
  lane's uncommitted work in that file** — `--only` isolates *paths*, not *hunks*, which is
  precisely the gap it does not close (**deduced, not observed**: the #264 evidence lane went
  looking and found **no instance** of a same-file hunk sweep in the whole session — the one
  index sweep, `12f47e3`, was a plain `git commit`, which is `--only`'s *absence*. The two
  failures that did happen are a bare `git commit` burying a staged file, and `--only
  <directory>` silently skipping untracked ones. Keep the mechanism, drop the pretence that it
  bit) — and the party asked to notice is the one least able
  to, because unfamiliar diff in a file it is actively editing reads as its own work. The
  disjointness invariant exists because **a check that depends on a lane's vigilance is not
  an invariant**; the two mechanisms that hold by construction are running the lanes in
  sequence and giving one a worktree. Region-splitting a file is the seductive version
  because it *sounds* like disjointness and produces the same sentence in a brief. **Test for
  it: if the guarantee has the word "should notice" or "check before" in it, it is a
  mitigation.** Sequencing cost me nothing here — #381's brief already orders the dashboard
  piece last, so the file may never be contended at all.

- **"Assert the two values differ" guards against a vacuous check, not a wrong one — and I have
  been writing it into briefs all session as though it did both.** The instruction is real and it
  has earned its place: a fixture whose two ages are equal cannot tell a working age display from
  one that prints a constant, and this repo has paid for exactly that. But it proves the output
  *varies with the input*, which is strictly weaker than the output being *right*. **Two values
  can differ and both be wrong by the same offset**, and a differ-check is blind to every error of
  that shape — every fixed offset, every unit error, every wrong epoch.
  · **Measured, not reasoned:** #385's criterion 4 asked that the questions headline show an age
  and that a fixture's two ages differ. Both held; the guard was green; I re-ran its discriminating
  red myself and it was a good one. Fifteen minutes later the deployed page showed my
  ~24-minute-old question as **`08h 17m ago`**, because `data-ct` resolves to **midnight** of
  the entry's date. The two fixture ages differed by two days and were both wrong by eight hours,
  and nothing in the check could see it (#392).
  · **The tell is that the criterion never names a number the code does not already produce.**
  "These two differ" is computed from the output; "an entry written at 07:54 renders 24m, not 8h"
  is computed from the *input* and compared against the output. Only the second can catch an
  offset. **A check that only compares outputs to each other cannot find a systematic error — one
  value must come from outside the system.**
  · **And it is the coordinator's failure, not the lane's.** The brief asked the right question —
  *"check whether a parseable timestamp reaches the client, or whether one has to be added"* — and
  then wrote acceptance criteria satisfiable without answering it. A question in the prose and a
  criterion in the list are not the same instrument: **the lane optimises against the criteria, so
  anything I actually need must be a criterion.** Prose is where I explain; the numbered list is
  where I bind.
  · **Found by looking at the deployed page, which no check does.** Ten guards, a lint pass and a
  re-run red all agreed. The eight-hour error was visible in one screenshot.

- **Derive a lane's ownership list from its deliverables, not from the files that obviously
  contain the work — a brief that requires a new artifact must also grant whatever *registers*
  that artifact.** Otherwise the lane gets two options and both are bad: leave a check warning and
  look incomplete, or edit a file the brief did not grant and break the disjointness invariant.
  · **Measured:** #367 increment 2a's brief required "one new `dev/capture/*.mjs`" and granted the
  seven files the visible change lives in. It did not grant the `justfile`. But a new guard only
  counts as a guard once it is in `DEFAULT_GUARDS` (`justfile`) or explicitly excused in
  `lint.NOT_GUARDS` (`lint.py`) — and `lint.py` was held by another lane. The lane appended
  `markrail` to `DEFAULT_GUARDS`, which was correct, unavoidable, and outside its list. I ratified
  it by relay. **Nothing collided only because no other lane needed the `justfile` — that was luck,
  not design.**
  · **The generative question, which takes one pass over the criteria:** for each deliverable, what
  else must change for it to *count*? A new guard needs registering. A new file in a
  registry-checked directory needs a registry row. A new format needs its `file-formats.md` entry.
  A visible change needs `watch-design.md`. Every one of those is a second file, and every one of
  them is a file some other lane may hold — which is when the sequencing decision has to be made,
  at dispatch, not discovered by the lane at minute thirty.
  · This is the same failure as [[the numbered list is where I bind]] seen from the other side:
  there I put a requirement in prose and no criterion; here I put a requirement in the criteria
  and withheld the means. **A brief has to be checked against itself — deliverables against
  criteria against ownership — and the coordinator is the only party who can do it, because it is
  the only party that sees all the lanes.**

- **Independent routes that share an assumption are one route — and the shared assumption is
  invisible precisely because they agree.** Three derivations of the same number agreed and all
  three were wrong; the production code was right and was the outlier.
  · **Measured:** an audit lane reported the dashboard's burndown as +1 too high for four
  consecutive buckets, with "two independent routes" (awk over `git show`, and a Python regex).
  I re-derived it a third way and got the lane's number. The payload said 110, we all said 109.
  **The code was right.** All three routes matched `^- \*\*#(\d+)\*\*` and the ledger had one
  **combined head** — `- **#138/#156**` — which that pattern cannot match. Three tools, one
  assumption: *one id per bullet*. `file-formats.md:244` documents combined heads explicitly and
  says both ledger readers count every id in them; none of the three routes had read it.
  · **The lane named the defect in its own uncertainty note** — *"whether both counters miss the
  same way (they agree with each other)"* — and I spent twenty minutes confirming its finding
  before taking that sentence seriously. [[a lane's stated uncertainty is a map to the defect]]
  fired for the third time today. **Read the uncertainty section first, not last.**
  · **The refinement this forces on [[one value must come from outside the system]]:** outside-ness
  is required of an *expected value*, because the code cannot be the judge of its own correctness.
  But when routes **disagree**, the production code is legitimate *evidence about which side is
  wrong* — asking the deployed `parse_ledger` what it counted settled in one call what three
  independent derivations could not. Those are different uses and I had collapsed them: I avoided
  the code for twenty minutes on a principle that did not apply.
  · **Cheap tell, and it was on screen the whole time:** my count was 109 strict matches out of
  **110 top-level bullets**. A count that does not equal the number of things it is counting is
  the whole finding. **When two counts of one collection differ, count the collection.**
  · **The unrelated real defect found beside it, which is why the neighbours rule keeps earning
  its place:** `#156` genuinely appeared under `## Open` twice at once — in the combined head and
  as its own entry — giving 111 ids where 110 were unique. `lint.check_tasks` has reported exactly
  this as an ERROR since `b7151ec` (2026-07-25), and it splits combined heads correctly. **It sat
  there for about sixteen hours anyway** (07-26 20:23 → 07-27 12:23), which means during that
  window `lint.py` was either not run or not read. The check was never the problem.

- **A check that skips an unrecognised shape is indistinguishable, in its output, from a check that
  passed.** `continue` and "fine" print the same thing: nothing. So every parser-based check has a
  silent third outcome besides pass and fail — *did not apply* — and that outcome is invisible at
  exactly the moments it matters.
  · **Measured, and it had been true for days:** `lint.check_related` enforces that a relation
  between two ledger entries is named by both, because *"an entry is read alone"*. Its marker regex
  requires a **bold** span and the function does `if not found: continue`. Three entries had written
  the marker without asterisks. Those three were skipped in silence — and behind them sat **four
  broken relations** (`#388→#383`, `#388→#386`, `#387→#361`, `#386→#383`), none of which any run had
  ever reported. The check was working perfectly on the entries it could see (#395).
  · **I found it only because lint rejected an edit of my own.** Nothing about the ledger looked
  wrong; the six-warning baseline looked healthy. A check with a silent skip does not decay
  loudly — it reports `clean` while its coverage shrinks, so the number of entries it *actually*
  examined is the fact nobody has.
  · **So the cheap general guard is a coverage number, not a verdict.** `check_related` already
  prints `3 related pair(s), all reciprocal`; had it printed *"3 pairs checked, 3 entries skipped as
  unparseable"* the hole would have been on screen for days. **A check that counts what it examined
  cannot silently stop examining things.**
  · **Two smaller traps found by walking into both**, and both share the shape: the failure is
  reported somewhere other than its cause. Adjacent bold spans yield only the **first** id, so a
  three-id relation silently becomes a one-id relation — and the error surfaces as a *reciprocity*
  complaint about the ids it dropped, pointing away from the shape that dropped them. And the marker
  vocabulary **cannot be quoted in prose**: naming it in an entry body lets the non-greedy `[^*]*?`
  run to the next `**` anywhere in the entry, manufacturing phantom markers — my entry *about* this
  bug produced five of them.

- **A caveat varies one axis and silently holds the others fixed. The defect is usually in one of
  the fixed ones.** So when a lane names an uncertainty, test the axis it names *and* the axis it
  assumed constant — the second is where it was not looking, which is exactly why it did not name it.
  · **Measured:** #367 increment 2a's report ended with a precise, honest caveat — *"two non-nested
  adjacent marked siblings closer than a tab height would not be staggered"*. It varies **distance**
  between two marks. I built probe artifacts at three densities: adjacent paragraphs (13.1px apart),
  consecutive list items (8.6px), flags 19.1px tall. **No overlap at any of them** — the caveat's own
  axis was clean.
  · **The axis it held constant was the marked element's *type*.** It assumed a block. An **inline**
  `data-mark` — which `file-formats.md` documents as legal, *"on any element inside `body`"* — puts
  the flag outside the reading column entirely, because `left` then resolves from the inline box's
  offset. Measured: clipped past the page edge by **12px at 1000, 112px at 900, 151px at 861**, and
  861 is one pixel above the cliff chosen to guarantee the worst case fits (#396). P1, on the
  feature that had just shipped.
  · **This is the fourth time today** that a lane flagged one case honestly, the flagged case was
  fine, and the case beside it was a real defect. The pattern is now specific enough to act on
  rather than to admire: **read the caveat as a sentence with variables, name every variable it
  holds still, and vary one.**
  · **And the guard was green throughout, correctly.** `markrail` asserts the flag anchors within 2px
  of the reading column's right edge, and that is *true* for the block marks its fixture contains.
  The hole is coverage, not logic — the same shape as [[a check that skips an unrecognised shape]],
  reached from the other direction: there the check could not parse the input, here the input was
  never in the fixture. **Both look like a passing check and neither is a check of the thing.**

- **The way to get the coordinator's own account reviewed is to commission it — and it works the
  first time you try it.** An hour after noting *"I verify every lane; nobody verifies me"* as a
  structural gap, I dispatched a lane whose brief said, in effect: *this document is my account,
  written from inside the session by the party most invested in believing the fan-out went well.
  Read it, cite it, and **check** it. Where `git log` disagrees, `git log` wins and you say so.
  Finding it wrong is one of the more valuable things you could do here.* It found two errors in
  one pass.
  · **What it found, and both were load-bearing.** (1) *"Thirteen lanes"* conflated cumulative
  dispatches with concurrency: the real figures are ~17 dispatched and **peak concurrency 5**. So
  every claim of the form *"thirteen lanes and no check caught X"* was really *"five concurrent at
  most, seventeen over four hours"* — a materially weaker version of the experiment than the one I
  was describing. (2) The `git commit --only` **same-file hunk sweep I had written into six briefs
  as an observed incident has no instance**; the one index sweep was a plain `git commit`, which is
  `--only`'s *absence*. True as mechanism, presented as observation.
  · **The mechanism of error 1 is the transferable half: a number updated from memory across
  sections is not a measurement.** My tally drifted *nine* (06:56) → *ten* (07:15) → *thirteen*, and
  it drifted because it lived **only in prose** — three appearances in a document, zero in any
  record. So: **any figure that recurs gets exactly one place that holds it, and prose cites that
  place.** `status.json` is that place here and I was not using it for this.
  · **Why commissioning beats resolving to be careful**, which is what I would otherwise have
  written down: the errors were invisible *from inside*. I had re-read that document while adding to
  it and the drift never registered, because each increment was locally consistent with the one
  before. The reviewer needs a different vantage, not more diligence — and the cheapest different
  vantage is `git log` in someone else's hands.
  · **Make it a criterion, not an invitation.** The brief did not merely permit disagreement; it
  made *"if your counts disagree with that document, the disagreement is a finding and you must
  report it"* a numbered acceptance criterion, and named the two hollow outcomes (a concurrency
  survey; restating the document). Compare the general permission at the bottom of every brief,
  which produces refutations only when a lane trips over one. [[the numbered list is where I bind]].

- **The relay reaches a lane that has increments left and misses one that runs straight through —
  and the coordinator cannot tell which it dispatched. So anything mandatory belongs in the dispatch
  prompt; the relay is only for refinements it is safe to miss.**
  · **Measured, both directions.** `#389`'s lane read its relay and said so — its report carries
  *"Bonus red (relay's second direction)"* and a section *"Relay (#389) neighbours — measured and
  decided"*. `#395`'s lane did not: its relay was written at 08:59, four minutes into a ~15-minute
  run, and its report mentions the relay **zero** times and did the thing the relay asked for **not
  at all**. Same mechanism, same instruction in every brief to *"re-read it between increments"*,
  opposite outcomes.
  · **The discriminator is the lane's own shape, not the timing.** A lane that treats its task as
  one increment never reaches a boundary and so never re-reads — and whether a task decomposes into
  increments is decided *by the lane*, after dispatch, invisibly. So relay delivery is not
  unreliable in a way a coordinator can plan around; it is unreliable in a way a coordinator cannot
  even observe without checking each report for evidence of receipt.
  · **What I got wrong, concretely:** I put a *ratification* in `#367`'s relay (fine — it confirmed
  something the lane had already done, so missing it was harmless) and then put a *new obligation*
  in `#395`'s (write a hand-off line). The second is the wrong channel for a mandatory thing, and it
  simply did not happen. **Sort by "what if this is never read": if the answer is "the deliverable is
  incomplete", it is not relay material.**
  · **This is `#381`'s bug one layer up, exactly as its lane said** while being told not to act on it:
  *"the coordinator writes a steer, a lane that has gone idle never reads it, and nothing wakes
  it."* The difference is that the ledger's hand-off channel now has a **check** that notices an
  unconsumed line, and the relay has nothing — so a missed steer is silent at both ends. **Verify
  what READS a thing, and note that "it was written" and "a report shows evidence of receipt" are
  different observations.**

- **Extend "a lane's stated uncertainty is a map to the defect" to what a lane says about the
  LOOP, not just about its own work. I had a rule for the second and none for the first, and it
  cost two hours.**
  · **Measured:** `#381`'s lane, asked whether its design would also fix coordinator→lane steering,
  answered: *"the relay is itself a write-then-hope channel: the coordinator writes a steer, a lane
  that has gone idle never reads it, and nothing wakes it — the same class of problem one layer
  up."* It named the mechanism, named the fix, and I had explicitly told it to enjoy the irony and
  not act on it. I read it, recorded it as an observation, **and then wrote four more relays over
  the next two hours**, including one carrying a mandatory obligation that was never performed.
  · **The asymmetry is the finding.** When a lane says *"I am not confident about X in my own
  work"* this repo now treats that as a lead and probes it — three real defects came from exactly
  that today (#389, #390, #396). When a lane says *"the machinery you are steering me with has this
  flaw"*, there was no habit at all, and the claim is **cheaper to test** than most: `#395`'s
  report needed one `grep` to show the relay was never read.
  · **Why it is easy to miss and it is not about attention.** A claim about a lane's own work
  arrives as a caveat under a heading I read looking for problems. A claim about the loop arrives
  as *commentary* — often as a pleasantry, in a section I invited — and it reads as insight rather
  than as a bug report. **The framing that makes it land: if a lane's sentence would be a P2 had I
  written it in the ledger, treat it as one.** *"The relay is a write-then-hope channel with no
  wake"* is a P2 in my own voice.
  · So the operational addition is one line at report-reading time: **after folding a lane's
  findings about the task, re-read whatever it said about the loop and ask what would falsify it.**

- **A red-proof injection is a write, and it needs the same ownership analysis as any other
  write. I applied that rule to my own injections all session and never once to a lane's.**
  · **Measured, as a near-miss:** `#398`'s brief told its lane to prove the red by *"removing the
  `handoffs.md` mention from a brief added after the cutoff"*. There were exactly **two** briefs on
  the new side of that cutoff, and **both belonged to lanes running at that moment** (`#397`,
  `#392a`). So the instruction was not merely risky — it was **guaranteed** to write into a live
  lane's brief. I watched `397-client-extraction-design.md` change to
  `.dreamwork/NOT_THE_HANDOFF` and back. The lane restored it correctly; had `#397` re-read its
  brief in that window it would have been told to append to a file that does not exist.
  · **Why I missed it, and it is structural rather than careless:** I treat an injection as
  *ephemeral* — snapshot, injure, restore — so it never entered the ownership column of the brief.
  Every injection **I** performed today went into a file I had first checked was unheld
  (`watch.py`, `lint.py`, `review_artifact.py`, the template). The reasoning was there; it simply
  never crossed from my own actions into the instructions I write for others.
  · **So the ownership list must cover what a red TOUCHES, not only what the deliverable
  changes** — the same shape as [[an ownership list comes from the deliverables]], one step further
  out: there the brief withheld a file the deliverable needed; here it silently required a file the
  *verification* needed. **Both are answered by one pass: for each criterion, what does satisfying
  it write to?**
  · **And the better instruction is cheap and strictly stronger:** point the check at a **temp
  root** and injure a copy. If a check cannot be pointed at a different root, that is itself a
  finding — a check untestable without mutating live state has a design problem, which is more
  interesting than the red it was blocking.

- **Grep proves the injection's text landed; it does not prove the file still loads. A broken
  injection and a discriminating red look alike in a tail of output and mean opposite things.**
  · **Measured, and I nearly believed it:** injecting a dead cutoff phrase into `lint.py` for
  `#398`'s red, I replaced the regex's group 1 — which for a parenthesised multi-line constant is
  just `(` — leaving a file that would not parse. `pytest` reported `IndentationError` during
  **collection**. Two lines of red output, the test I was targeting named nowhere, and it would have
  read as "something failed, good". A collection error is not a test failure: **zero tests ran**, so
  the run says nothing about the code at all.
  · The existing rule *"grep for your injection to confirm it reached the code"* is necessary and
  insufficient — the text was there. The one extra check costs nothing: **`python3 -c "import ast;
  ast.parse(open(f).read())"` before believing any result**, or for a non-Python target, whatever
  loads it.
  · The general shape, which is the reason to keep this: **verify the run exercised the code, not
  merely that it was unhappy.** A red whose message does not name the test you were targeting is
  not yet evidence.

- **The fallback that exists to catch an unrecognised shape usually shares the pattern that makes
  the shape unrecognised — so the one class it was built for is the one class it cannot report.**
  · **Measured in production code, not in a check (`#401`).** `watch.parse_handoffs` has two
  patterns: `HANDOFF_PENDING_RE` for a well-formed hand-off, and `HANDOFF_BARE_RE` whose stated job
  is *"a Pending entry head the grammar does not recognise"* — a real, deliberate, well-documented
  validator. Both are `#(\d+)`. So `- **#392a** · landed …` matches neither, falls through both
  branches, and yields `pending=[]`, `malformed=[]`. **The file reads exactly like an empty one**,
  and `#381`'s entire premise is that a landing here cannot be lost.
  · The generalisation, which is the reason to keep this: **a validator written as "anything the
  parser did not accept" is only as wide as the vocabulary its author had in mind.** Ours recognised
  numeric ids, so it could see a garbled *sha* or a missing *claimer* — every axis except the one it
  shared with the parser. **Vary the axis the fallback and the parser have in common**, and check
  that the fallback still fires. If it does not, the shape is invisible rather than reported.
  · Sibling to *independent-routes-share-an-assumption*, and worse in one way: two disagreeing
  routes at least produce a discrepancy. A parser and its own fallback produce **silence**, which
  is the output of a healthy file.

- **`sha256sum <missing> <present> 2>/dev/null` prints one line and I read the one line as a
  match.** · Comparing the deployed dashboard against the tree this tick, I ran
  `sha256sum ~/.cache/dreamwork/deployed/watch.py watch.py 2>/dev/null`, got a single hash back
  under a heading I had written as *"deployed sha vs tree"*, and moved on. The deployed file is
  named **`ud-dreamwork-watch.py`** — `<project>-watch.py`, not `watch.py` — so the first argument
  did not exist and my own `2>/dev/null` deleted the only evidence of that.
  · **The output of "compared, identical" and "compared nothing" is one line either way.** The
  same shape as the two above and the third instance today: absence rendering as success.
  · Cheap fix, and it is the same fix every time: **make the comparison state its own arity** —
  `sha256sum a b | wc -l` must be 2, or `test -f` each side first. Never suppress stderr on a
  command whose failure mode is a missing operand.

- **"Inherit these numbers, do not re-derive them" is how the coordinator's arithmetic error
  becomes three lanes' premise.** · I wrote, in `#397`'s brief *and* its dispatch prompt, that
  `server_class` (`watch.py:262`) is **6,798 lines, 72% of the file** — presented as measured, with
  an explicit instruction not to re-derive it because the measurement was *done*. It is **10
  lines**. The lane checked anyway, said so, and `ast` confirms it: largest top-level def is
  `make_handler` at **434**, and the 6,756 lines I had attributed to `server_class` are **8
  module-level string constants** sitting between it and the next `def`.
  · **The mechanism, which is the reusable part:** I had measured function size as the span from one
  `^def ` to the next, so every module-level statement in between was billed to the preceding
  function. **For anything structural, use `ast`, not a line-oriented regex** — `ast` cannot
  mis-attribute a span because it parses the nesting the regex is guessing at.
  · The instruction was well-motivated: re-deriving costs a lane real minutes, and this repo's
  briefs are better for carrying measurements. But **"do not re-derive" removes the only check on
  the number**, so it must be spent deliberately: say which figures are load-bearing and MUST be
  re-derived, and let the cheap ones be inherited. Here the load-bearing figure was the one I got
  wrong, and the only thing that saved the plan was a *separate* instruction to ground every claim
  in line numbers.
  · **Corollary worth its own line: a lane that contradicts the brief's own premise is doing the
  job.** Read the contradiction before the conclusion.

- **When three of four agents deviate from an instruction and the three that deviated are the ones
  that got it right, the instruction is wrong.** · Every brief here says of `handoffs.md`: *append
  only with `cat >>`, never rewrite.* `## Pending` is **not the last section**, so an EOF append
  lands inside `## Folded`. The one lane that obeyed literally produced the defect; the three that
  inserted before `## Folded` — a rewrite, which the instruction forbids — produced the correct
  result. **Compliance selects against the outcome the obligation exists to secure** (`#406`).
  · The diagnostic is cheap and I did not run it for months: **before blaming the agents, execute
  your own instruction literally and see where it lands.** A shell one-liner would have shown this
  the first day.
  · And the sections turned out to be **redundant** — the two line shapes are self-distinguishing
  and correlation is by id — so the constraint that broke the append was buying nothing. **When an
  instruction and a format fight, check whether the format's structure is load-bearing at all**
  before rewording the instruction.

- **A conflict resolved by declining never reaches the branch that would have resolved it
  differently.** · The whole session's binding constraint was file contention on `watch.py`:
  a shelved increment, three serialised dispatches, two tasks blocked right now, a hand-maintained
  ownership list, and a **459-line design document** commissioned to relieve it. `CLAUDE.md` states
  worktrees as the standing preference and `SKILL.md` says explicitly that when disjointness cannot
  be arranged, the dreamer goes in a worktree *and the invariant then holds by construction*.
  **Every lane ran in the shared tree, and nothing consulted either rule** (`#405`).
  · Not a knowledge failure — both documents were read at init. A **control-flow** failure: the
  coordinator checks ownership, finds a conflict, and treats it as *do not dispatch*. The queue
  branch resolves the conflict, so the worktree branch is never evaluated. **A rule that only
  applies after a decision the code makes earlier is unreachable, however well documented.**
  · The general check: for each documented fallback, ask **what has to fail for this branch to be
  taken** — and then whether anything upstream quietly succeeds instead. A fallback nobody reaches
  looks identical to one nobody needs.

- **The coordinator inbox HAS now lost a report, so the sentence that says it never has is wrong —
  and it is the sentence used to justify routing everything through it.** · `SKILL.md` states that
  dreamers *"append to the coordinator inbox and have never lost one"*, and offers that as the reason
  to dispatch utilities the same way. `#392a` landed real work (`159917b`), wrote a hand-off line,
  and **never appended to the inbox**. Its reasoning, its rejected alternatives (it chose the word
  `today` over `0d`) and its stated uncertainties are gone. I have its diff and its commit messages,
  and I reconstructed the rest by reading the code — which worked, and only because the change was
  small.
  · **Measured across four lanes in one batch, three channels:** git **4/4**; the hand-off line
  **4/4 written** but **3/4 in the right section**; the inbox **3/4**. Exactly one channel cannot be
  skipped, and it is the one nobody designed as a channel: **a lane cannot land work without
  committing**, so the commit is structurally reliable in a way an append never is.
  · The lesson is not "watch the inbox harder" — that is what the sentence already assumed. It is
  that **"has never failed" is an absence of observation, not a property**, and it decays silently:
  nobody re-checks a claim like that, and its counterexample looks exactly like a quiet lane.
  · Practical form: **put what must survive in the commit** — message, and any document the work
  produced. Treat the inbox as the place richer context *usually* arrives, never as the place a
  deliverable lives.

- **A compliance measurement taken at commit time measures the wrong moment: landing and reporting
  are not one act.** · At 09:46 I observed that two lanes had landed commits and neither had written
  its hand-off line, and I nearly filed "prompt placement is insufficient" as a finding. I withheld
  the count on the grounds that both lanes were **still alive**. Both wrote their lines within the
  next fifteen minutes; the final count was **4 of 4**. The fix was working and the measurement was
  early.
  · **The general rule: before recording a compliance failure, establish that the agent has
  FINISHED.** A live process and a non-compliant one are indistinguishable from the artefact, and
  the honest instrument is `pgrep`, not the file. Cheap, and it would have inverted this conclusion.
  · Worth pairing with the opposite error, which this repo has also paid for: an agent that says it
  is done and is not. **Neither the artefact nor the agent's own word settles it — the harness
  does.**

- **A parser that detects a shape it knows is broken should treat it as naming NOTHING, not as
  naming what it managed to read. Partial trust is the mechanism that makes a drop silent.**
  · **The constructive counterpart to a day of silent-drop findings, and the only check measured
  today that fails CLOSED.** `lint.check_related_markers` meets `related: **#501**, **#502**` — two
  adjacent bold spans, of which the regex captures only the first. It does not proceed with `{501}`.
  It reports the malformed marker **and** treats the entry as naming nothing, so **every** id that
  should have been named — including `#501`, which it *did* capture — raises a reciprocity ERROR.
  Measured against a control: the broken form gives **3 ERRORs** (the first naming the true cause),
  the correct one-span form gives **0** and a coverage line.
  · Three messages for one defect looks like noise and is not: the first names the cause, and the
  other two are the blast radius stated explicitly. Compare the alternative — proceed with `{501}`
  and `#502`'s relation vanishes with **no** message anywhere. That is `#401`, `#399` and `#406` in
  one line, and it is what partial trust buys.
  · The rule generalises past parsers: **when validation and extraction disagree, extraction must
  yield nothing.** A reader that returns its best effort alongside a warning invites every caller to
  use the effort and ignore the warning — and one of them will be a check.
  · Worth noting *why* this one is right: `#395`'s author had just been bitten by exactly this class,
  and built the fail-closed behaviour deliberately. **The design is not an accident, and neither is
  the fact that it is the only one of its kind here.**

- **`lint.py` exiting 0 is not a green baseline, and a `-k` selection that excludes the failing test
  is indistinguishable from a passing suite. `just test` exists for exactly this and I did not run
  it.** · For hours today `test_lint.py::TestLandedAsks::test_this_repo_has_no_forgotten_folds` was
  **failing on master** — 496 passed, 1 failed — and I did not know. Two independent reasons, and
  each alone was sufficient: `python3 lint.py` **exits 0** because the underlying finding is a
  **WARN**, not an ERROR; and every pytest run I made was a selection
  (`-k "cutoff or grandfather or handoff"`, `-k "date_only or timed_timestamp"`) that never included
  it. A **lane** found it in one line by running the whole file.
  · The shape is the day's recurring one arriving in my own habits: **the output of "nothing is
  wrong" and "I did not look there" is identical.** A selection is a coverage decision, and a
  coverage decision with no coverage number is a guess.
  · Rules, both cheap: **run the project's own full verification before believing a baseline** — here
  that is `just test`, and it is the repo's only CI. And **when a check has severities, know which
  ones the exit code reflects**; a WARN that no exit code carries is a finding that only a reader
  sees, and nobody reads.

- **Moving a ledger entry must not rewrite its `related:` list — and I compounded four edits without
  running the check between them, turning 4 errors into 14.** · Closing `#401` and `#406` meant
  moving them from `## Open` to `## Recently landed`. I combined them under one head `#401/#406`,
  which made every entry relating to either id owe a back-reference to **both**, and then tried to
  repair the cascade by patching one marker at a time, then by computing a closure whose own id
  regex (`#[\w/]+`) split `#401/#406` into `#401/` and `#406`. **That is the same
  narrow-id-vocabulary defect I spent the day filing, committed by me while filing it.**
  · What worked, after restoring the last clean copy: **move the entry verbatim and leave the marker
  untouched, positioned last.** The relation graph was already consistent; the move never needed to
  touch it. Then one edit, one `lint` run, repeat — and the pair count moved by exactly the expected
  amount each time (42 → 44 for one new two-relation entry), which is the arithmetic that proves the
  edit did what it claimed.
  · The generalisable half: **when a repair makes a check worse, stop and restore rather than
  continue.** Four errors was a diagnosable state; fourteen was a state I had authored. And
  **restoring is only cheap if the last good version is committed** — the reason to commit small.

- **A partial syncer manufactures the illusion of a synced file, and its success message is the
  trap.** · `just status-sync` prints *"already in sync (136 open, 1 live)"*. It recomputes exactly
  two fields — `queue` and `current_task_ids` — from ground truth. Measured today, while it said
  that: `last_tick` was **133 minutes** stale, `last_commit` was **30+ commits** behind, and
  `deployed.pid` named a **dead process**. The message is true and scoped to a subset the reader
  cannot see, which is worse than no message, because a reader who runs a sync tool and is told
  "in sync" stops looking.
  · **The consequence reached the human.** His browser tab read `· stalled` for over two hours while
  the loop was working — and `watch.py` was *correct*: `Date.now() - t > STALE_TICK_MS`, with a
  comment saying that word is how he tells whether the loop is alive. **The renderer did its job and
  the data lied to it.** When a display is wrong, check whether it is faithfully displaying something
  wrong before you go looking in the renderer; I nearly opened `watch.py`.
  · Same shape as the coverage-number rule, moved from checkers to writers: **a tool that maintains
  part of a record must either own all of it or name the parts it does not touch.** Silence about
  scope reads as completeness.
  · The generalisable diagnostic, and it costs one pass: **for each field in a record, name what
  writes it and when.** Anything with no writer is decoration that will eventually be believed.

- **Verifying my own brief's citations before dispatch found that the P1 it described was already
  fixed. The check cost two minutes and saved a lane.** · Writing `#340`'s brief I cited
  `watch.py:8282` and `:8407`. The `#399` merge had shifted the file, so I re-checked — and the
  re-check did not just correct two numbers. It found **two** `lift_answer=False` call sites where
  the entry described one, on **two different channels** whose fix is **asymmetric**; and then that
  the defect itself was gone, fixed at `8009c90`, with the entry still under `## Open` because it
  never cited the sha.
  · **A lane obeying that brief would have done real harm.** The entry called it a one-argument fix;
  applied symmetrically it would have attributed **loop prose to the human** — the inverse of the
  bug, and a correctness fault by this repo's own `#109`. The brief was confident, specific, and
  wrong in three ways.
  · The habit that caught it is small: **re-derive every line number and every count in a brief
  against the tree you are dispatching against, not the tree the entry was written against.** A
  ledger entry is a claim from the day it was written; the file moves under it. This is the third
  time in one day the inherited-measurement trap has come round, and the first time checking it was
  free.
  · Corollary, cheap and general: **when a ledger entry describes a defect, reproduce the defect
  before commissioning the fix.** Not the diagnosis — the symptom. If it will not reproduce, the
  task has changed shape and the brief you were about to write is for a different repo.

- **`cmd | tail` reports `tail`'s exit code, so a failing suite announced itself as exit 0 — and I
  had already started saying it was green.** · I ran `timeout 1200 just test 2>&1 | tail -25` in the
  background. The harness reported **exit code 0**. The captured output ended
  `error: Recipe 'guards' failed with exit code 1`. **The pipeline's status is the last command's**,
  and `tail` always succeeds.
  · This is the day's recurring shape wearing its plainest disguise: **a success signal that reports
  on something other than the thing you care about.** It sits alongside `lint.py` exiting 0 on a
  WARN, `sha256sum` printing one line for a missing operand, and `grep -c` exiting 1 on zero — four
  instances, one family.
  · Fix, and it is one token: **`set -o pipefail`**, or read `${PIPESTATUS[0]}`, on any pipeline
  whose left side is the thing being judged. Better for long runs: **do not pipe at all** — write to
  a file and read the file, so the exit code belongs to the command.

- **I merged on a partial verification forty minutes after recording the lesson that a partial
  verification is not a verification.** · `#399`'s own brief made **`just test` green** the
  acceptance criterion, in those words, because the suite was red and a `-k` selection had hidden it
  from me for hours. I then verified the lane's work with `pytest test_watch.py test_lint.py`
  (502 passed), an independent red, and four lint checks — **and merged while `just test` was still
  running**. It failed. Bisect: the burndown guard **passes at the merge's first parent and fails at
  HEAD**, so the merge traded `forgotten_folds` red for burndown red and the suite was never green.
  · **Knowing the rule and having just written it down did not make me apply it.** The gap was that
  the guards live *outside* the tool I habitually reach for, so "I ran the tests" felt complete while
  being, precisely, the selection the lesson was about.
  · The operational form, which is what I actually needed: **the acceptance criterion is a gate, not
  a report.** If a brief says the criterion is `just test` green, nothing merges until that command
  has exited and been read. Waiting cost nothing; merging early cost a regression on `master` and a
  bisect to find it.


- **I discarded the one artifact that explained two lane deaths, then diagnosed the first death as a
  mystery and re-dispatched into the same wall.** · The dispatch recipe I had been using ends
  `> /dev/null 2>&1 &`. Two `ccc @grok` lanes on `#399b` died at ~3 seconds with no commits, no
  report, and a clean worktree. The third dispatch differed in one respect — `> "$LOG" 2>&1` — and
  the cause was the first line of the file: `Unauthorized (401) … Invalid or expired credentials`,
  `Model: grok-4.5`. The runner's credential had expired; every lane sent to it would die the same
  way.
  · **A lane that dies before its first token is indistinguishable from one that ran and reported
  nothing** — same empty inbox, same clean tree, same absent process. The two have opposite fixes
  (refresh the credential vs. rewrite the brief), so guessing between them is how forty minutes go.
  · **The runner's own log does not cover for you, and looks like it should.**
  `~/.local/state/cc-w/ccc/runs/<run>/` holds `output.txt` and `transcript.txt` — for a 401 death
  **both are zero bytes**, because the error is on stderr only. Finding that directory felt like
  finding the answer and it was empty.
  · Fix: **never `/dev/null` a dispatch.** `> "$LOG" 2>&1`, and read `$LOG` the moment a lane looks
  quiet. It costs one variable. This is the same family as the pipefail lesson above — a channel
  that reports on something other than the thing you care about — except here the channel was
  deliberately destroyed by me.

- **`cd` persists between Bash calls, and I spent ten minutes editing the ledger in a worktree while
  believing I was in the main checkout.** · One earlier call began `cd .worktrees/399b && git log …`
  to check on a lane. Every subsequent call inherited that directory. I then filed `#410` into the
  worktree's `tasks.md`, ran `lint.py` against the worktree's `.dreamwork/`, and — because a
  worktree has no untracked files — concluded from a directory listing that `status.json`,
  `inbox.md`, `run-mode`, `watch-events.log`, `submissions.log` and `.status-keys` had all been
  **deleted**. They had not. Nothing was lost, and the tree was fine.
  · **The tool had been telling me on every single run and I read past it.** `lint.py`'s first line
  of output is the absolute path it is linting; it had read `…/.worktrees/399b/.dreamwork` for four
  consecutive invocations. I was grepping that output for `WARN|ERROR` and the header fell outside
  my filter — **a filter narrow enough to be useful is narrow enough to hide the thing that says
  which file you are looking at.**
  · The tell that finally worked was an *inconsistency between two readings*, not the readings
  themselves: `ls` said six files were missing while `lint` reported `handoffs.md`, `questions.md`
  and `watch-port` all fine. A directory cannot be half-deleted, so the target had to be wrong.
  · Fix: **`cd <abs> && …` at the head of any call that touches repo state**, rather than trusting
  inherited cwd — and when a measurement says something catastrophic happened, check the instrument
  is pointed at the right thing before believing it. Panic is a reason to re-read the header.

- **A check with two WARNs that are "the condition and its inverse" is a smell, and the
  inverse one is the one that gets the whole check muted.** `check_handoffs` was first
  written with a delivery WARN (a hand-off names `#N` landed but `#N` is still open) and
  its mirror, a "stale fold record" WARN (marked folded but still open). They read as a
  tidy pair. But the second fires on a **transient** — the fold record lands a tick before
  the ledger move — and a transient that the check assumes will self-correct does not, so
  it **nags every run after you have complied**. A check that nags after compliance gets
  muted, and a muted check is worse than none. The honest pair is **one WARN for the
  unacted state and silence-by-construction for the acted state**, where "acted" is marked
  by a record the actor writes and the check treats that record as authoritative instead
  of re-deriving whether the act really happened. (#381 lane, dream 0838)
- **A consumed-marker test must exercise the path where the marker is load-bearing, and
  that is the OPEN path.** The same lane's test would have passed with the marker ignored
  entirely, had it used a landed task: the delivery signal requires the task to be open,
  so a landed-and-folded hand-off is silent whether or not the marker is respected.
  **A test on the masking case is structurally incapable of detecting the bug it is named
  for** — the "test scaffolding stood in front of the code" trap, in its quietest form.
  Ask which input makes the mechanism necessary, and test that one. (#381 lane, dream 0838)
- **"Did my change leave X byte-identical?" must resolve its baseline by CONTENT, never by
  a moving ref.** `git show HEAD:file` is the obvious implementation and it is wrong in
  this tree: HEAD moved twice within an hour under concurrent lanes (e84ca0c → 5e908ff,
  then 8d5ad92 after the lane's own commit), and once the feature is committed HEAD
  *carries* it, so the check compares new against new and passes forever. A pinned SHA
  breaks on the next rebase; recomputing the expected side with the new code is the hollow
  version. What survived both a peer's commit and its own: **walk `git log -- <file>` for
  the newest commit whose copy lacks the feature's marker constant**, freeze a digest
  captured before editing as the fallback, **re-run the pre-change builder from the
  resolved ref and assert it reproduces the frozen digest** (so the constant is verified
  rather than fabricated), and guard with `assert not hasattr(old, "<feature>")` so the
  resolver can never silently pick a post-change commit. (#367 inc1, dream 0658)

- **Never judge a running lane's work from its worktree — read its branch tip.** I built a
  merge gate for `#399b`, red-proved it in both directions, ran it against
  `.worktrees/399b/watch.py`, and it scored the lane's fix at **176 landed** — which is
  exactly the pre-fix number. The lane was mid red-proof: it had deliberately injected the
  old behaviour to prove a test fails, so the file on disk was the bug, not the fix. Had I
  not recognised the number I would have reported a good fix as a total regression.
  **A running lane's worktree is mutable by definition — the injection *is* the method we
  ask for.** Its commits are the artifact. Default any review instrument to
  `git show <branch>:<file>`, and assert the source is non-empty so a bad ref fails loudly
  rather than scoring an empty module.
- **A check appended after `sys.exit()` reports success by not existing.** Same session,
  same gate: I added an eighth check to the end of the file, below the exit line, and the
  gate printed **GATE PASSED** while the eighth check had never run — and it was the one
  that would have failed. This is the day's dominant family — a signal reporting on
  something other than the thing you care about — but with a twist worth naming: the other
  members (`cmd | tail`, `lint` exiting 0 on a WARN, `grep -c`) report the *wrong* status,
  whereas this one reports the status of a *smaller program than you think you wrote*.
  **After adding a check, confirm the count of checks that ran went up**, not merely that
  the output still looks right.
- **A residual found mid-task is filed at the moment the ledger is least likely to be
  read — and it was already in it.** Closing `#399b` I ran my merge gate, found the
  landed reader still drops space-joined multi-id spans, measured 16 ids, and filed it as
  new work (`#412`). `#331` had carried that exact gap for days: same defect, a better
  count (**19** — I missed the `+`-joined `**#157 + #222 + #223**` span entirely), an
  independent verification at `04b9e00`, and a fix that mine directly contradicts. I wrote
  *"the fix looks like `(?:[ /]#\d+)*`"*; `#331` says *"the point of this task is NOT to
  add `[ /+]` to a third regex"*, because two prior widenings each moved the defect one
  door along. **Recognition does not scale — 135 open entries is far past the size where
  "I'd remember if we had this" is true**, and the mid-task moment is exactly when nobody
  looks. The check costs one command and it is not a title search: **grep the ledger for
  the SYMBOL** (`LEDGER_COMBINED_MENTION`) before filing anything about code. It finds the
  entry no title match would, because the duplicate describes the same line of code in
  entirely different words.
- **Writing the entry is where the ledger's own rules bite hardest.** Withdrawing `#412`
  I put `**#331**` in the head line at column 0 — which made `#331` read as *landed*,
  reintroducing in one prose sentence the precise leak `#399` had just fixed — and I wrote
  the reciprocal as two adjacent bold spans when the form is one span with a comma. Both
  in a commit whose subject was tidying the ledger. **Re-run `parse_ledger` and assert
  `open ∩ landed == ∅` after every ledger edit, not only after parser changes.** Prose
  about ids is ledger data; the reader cannot tell your commentary from a landing.
- **Make every check print its own verdict, because the exit code is what a pipeline silently
  replaces.** Seventh instance of the day's dominant family, one hour after writing it up for
  the sixth: I ran the `#331` gate as `python3 gate331.py master | tail -35`, read `EXIT=0`,
  and the gate had in fact failed. The lesson did not stop me — I had written it twice. What
  stopped me was that the gate ends with a literal `GATE PASSED` / `GATE FAILED` line, so the
  output contradicted the status and the output was the true one. **The habit is not
  "don't pipe"** — that one has now failed seven times and will fail again. It is: **every
  check emits a verdict token, and you read the token, never `$?`.** A guardrail that survives
  your own forgetting beats a lesson that depends on remembering.
- **A criterion that cannot fail is not a criterion, and briefs are where they hide.** My
  `#331` brief required the lane to prove `#501`/`#502` do not land. Red-proving the gate
  showed that check passes even against a deliberately over-wide pattern that IS landing both
  ids — because in the live ledger they sit on an *indented* line, so the column-0 rule holds
  them inert no matter what the pattern does. The check tests a different guard than the one it
  names. 26 of 27 prose spans in the landed section are protected this way; only
  `**#96 stage 1**` sits at column 0 where the pattern is the sole guard, which is exactly why
  `#331` named that fixture and no other. **When a check has two independent guards in front of
  it, disable the one you are not testing** — here, put the fixture span at column 0 — or you
  are measuring the wrong one and cannot tell.
- **Read the clock; do not estimate elapsed time from how long the work felt.** I stamped a
  brief addendum `12:47` and a questions follow-up `12:58` while the system clock read `12:43` —
  both in the future, one of them in an entry he reads. The work between them was dense
  (a gate, two red-proofs, three commits) and dense work feels long. The rule is already
  written for `status.json`; it applies to **anything a reader will date**, and the cost of
  obeying it is `date '+%H:%M'`.
- **"Pre-existing" is a claim about time that gets read as a claim about severity — and it is how
  a real signal becomes paperwork.** Three guards had been failing since morning. I wrote them
  into three consecutive lane briefs as *"known pre-existing on master, you are not required to
  fix them"*, with a load-flake hypothesis I had never tested — it came from seeing them fail
  once at load 29. All three were real: `qacard` was **inverted** (green with the bug present),
  and `docktarget`/`noteprop` were bisected to `#385` putting a live age inside the question
  headline, which broke every check that identified a question by its rendered text. Six hours,
  three lanes, and each lane dutifully re-confirmed the failures and moved on — because that is
  what I told them the failures meant. **A failure excused in a brief must carry a cause and an
  owner, or the excuse is doing the work the investigation should have done.** The tell was
  available from the first run and I did not read it: four failures across two guards were all
  **one invariant**, and the *reduced-motion* arm failed beside the animated one, which no
  timing flake explains.
- **Fixing `master` under a running lane silently invalidates the acceptance criteria you gave
  it.** I briefed the `#331` lane with *"three failures are known pre-existing on master —
  verify they fail on master too"*, then spent that lane's runtime fixing all three on `master`.
  Its branch predates the fixes, so its own run shows 3 failures against `master`'s 0 — a
  difference that reads exactly like *"my change broke three guards"*. The work was good and the
  timing made it a trap. **A brief's criteria are a contract against a named baseline; if you
  move the baseline, you have edited the contract of an agent that cannot hear you.** Either
  hold shared-baseline fixes until the lane lands, or post the correction the moment you commit
  — and expect it to be unread, so also plan to explain the discrepancy at review rather than
  treating the lane's confusion as a defect in the lane.
- **A review gate whose baseline is a moving ref expires at exactly the merge it was built for.**
  `gate331.py` compared the candidate against `master`. That was right for four runs and wrong on
  the fifth: once `wt/331` merged, candidate *was* baseline, so "the 19 are lost at baseline"
  failed and the arithmetic compared 171 against 171+19. It printed **GATE FAILED** while every
  substantive check beside it passed — a true statement pointing the wrong way, which is worse
  than a plain error because the instinct is to distrust the merge. **Name the baseline as an
  explicit argument and pass the pre-merge sha**; a gate is a two-ended measurement and only one
  end may float.
- **The line that captures an exit code can be the line that discards it.** I ran
  `just test > "$LOG" 2>&1; echo "EXIT=$?" >> "$LOG"` in the background. The harness reported the
  job as *"exit code 0"* and it was not wrong — the compound command's status is `echo`'s, and
  `echo` succeeded. The real code was **1**, preserved only inside the log by the marker. My first
  reading blamed the harness; the truth is that appending the marker makes the marker the last
  command. It is the `| tee` failure wearing the clothes of the fix. **Read the marker, never the
  job's status** — and note that the run had stopped at pytest, so the browser guards never ran
  and "the suite is green" was a claim nothing in that run supported.
- **A harness-backgrounded dispatch can be stopped without the lane having failed, and the two
  look identical if you only check whether the process is gone.** The `#411` lane was reported
  `killed` about a minute in. Every failure signal I have learned to check said *nothing was
  wrong*: the log held its 127 bytes of ordinary runner warning, no 401, no traceback, and the
  worktree was untouched — which is precisely what a lane that never got started looks like, and
  also what one that died looks like. **The discriminator is the log's CONTENT, not the process's
  absence**, and it only exists because dispatches now write to a file instead of `/dev/null`.
  Re-dispatched with `setsid … & disown` so the lane's lifetime is not the background task's;
  `ps -o ppid=` confirms it reparented away from the harness. Check the parent, not just the pid.
- **The "must NOT happen" half of a gate is the half that is born hollow, and only an injection
  finds it.** My `#411` gate asserted that two *withdrawn* asks keep returning `None`, because
  `answered_at` must never fabricate a date. Against a deliberately over-greedy reader — any
  parenthesised date, no `→` required — **both of those checks still passed**, and the gate
  printed GATE PASSED. The reason was not subtle once looked at: **neither withdrawn body
  contains a parenthesised date at all**, so there was no bait for a greedy reader to take. The
  checks were structurally incapable of failing on the exact thing they were named for, while
  reading as the careful part of the gate.
  The positive checks were fine — they name a value that must appear, so a broken reader misses
  it. **A negative check names a value that must NOT appear, and the live fixture usually does
  not contain it for unrelated reasons.** So: **feed the bait yourself.** Call the function
  directly with input that would tempt the failure, *and* pair it with a positive control — a
  reader that returns `None` for everything sails through a bait check alone. Both directions now
  discriminate: narrow fails the recoveries, greedy fails the bait, correct passes both.
- **Three times in one day a careful lane was marked wrong by a checker that was itself too
  narrow.** `qacard` demanded a two-figure age after `#392a` had deliberately made date-only
  entries show one; the dock guards compared a raw title against a headline `#385` had put a live
  age inside; the hand-off grammar allowed one sha while `#411` honestly landed in two. In every
  case the failing signal was read as *"the work is wrong"* — twice by me, in briefs, for six
  hours — when it meant *"the contract moved and the check did not."*
  The shape is specific enough to act on: **a check encodes a contract at the moment it was
  written, and the thing it checks keeps evolving.** `just audit-styleguide` measures
  code-against-doc; nothing measures check-against-doc, and all three of these had a *correct*
  doc sitting beside a *stale* check. So when a lane and a check disagree here, **the prior should
  be that the check is stale**, not that the lane erred — that is now 3-for-3 — and the first
  question is "what changed since this check was written?", not "what did the lane break?"

- **A worst-case extrapolation, restated once, becomes a measurement — and I handed one to the
  human inside a question he was ruling on.** `#367`'s entry told him option A costs *"~214px"*
  of chrome at seven marks. Built and measured, it is **167.9px**. The 214 was arithmetic —
  a 180px worst-case tab, times three rows, plus gaps — and every step of it was defensible; it
  was simply never observed, and realistic mixed labels pack tighter than seven copies of the
  worst case. By the time it reached him it carried no trace of being derived.
  **The number was also the entire decision**: A versus C is 214-vs-32 in prose and 168-vs-32 in
  fact, and the second framing is materially kinder to the option I was arguing against. He
  asked to see the previews *before* ruling, which is the only reason it was caught.
  So: **in anything a human decides on, a figure that was computed rather than observed says so
  in the same sentence.** "~214px (extrapolated from the 180px worst-case tab, not measured)"
  costs nine words and cannot mislead. And when the decision turns on the number, build the
  thing and measure it before asking — the artifact took a lane thirteen minutes.

- **Two edits in one hour damaged sectioned Markdown by searching the whole file for a boundary
  the sections define.** `s.index("## Recently landed")` matched a **prose mention** two thousand
  lines above the real heading, and filed two closed tasks into the middle of `## Open`. Then
  cutting an entry from `## Open` to *"the next `- **` anywhere in the file"* ran past the end of
  the section and **swallowed the `## Answered` heading itself**.
  Both are the day's dominant class one more time — a lookup that reports on something other than
  the thing you cared about — and neither raised an error: the first was caught because
  `parse_ledger` said open went 136→137 when it should have gone to 135, the second because a
  count of open entries came back 6 when it should have been 0. **The file looked fine both times.**
  Two rules, and they cost one line each: **anchor the heading match** (`^## X$` with `re.M`) and
  **assert it matches exactly once** — `tasks.md` has seven unanchored matches and one real
  heading; and **scope the entry search to the section you already sliced**, never to the whole
  file. Then cross-check with the production parser before committing, because that is what
  caught both.

- **The dispatch recipe makes lanes write the hand-off line twice, and the second copy blocks the
  merge.** Briefs give the **absolute** path `/…/ud-dreamwork/.dreamwork/handoffs.md` — the main
  checkout — so a report survives whatever happens to the worktree. But the same brief tells the
  lane to *commit* that line. In a worktree those are two different files, so the line lands
  uncommitted in main **and** committed on the branch, and `git merge` refuses with *"local
  changes would be overwritten"* on a file whose two versions are byte-identical.
  Harmless once understood and confusing at exactly the wrong moment — it arrives after the work
  is done, looking like a conflict. The fix is to say which copy is authoritative: **write the
  report to the absolute inbox path (main checkout, uncommitted, always readable) and commit the
  hand-off line inside the worktree only.** Until the template says so, the coordinator's merge
  step is `git checkout -- .dreamwork/handoffs.md` first, after checking the two are identical.

- **I wrote the lesson for a bug and then committed the bug, twenty minutes later, in a brief.**
  The entry above says to anchor a section-heading match and *"cross-check with the production
  parser before committing, because that is what caught both."* I then answered the question *"is
  `#172` open or landed?"* with an **unanchored** split, concluded a P1 had been falsely marked done,
  and put that in a brief to a running lane **and** in a commit message. `watch.parse_ledger` said
  `open? True` the moment I finally asked it.
  **Writing a lesson down does not install it.** What would have caught this is not more resolve —
  it is that the check was one line and I skipped it because the question felt small ("which section
  is this entry in?"). The small questions are exactly where a hand-rolled reader gets used, because
  reaching for the production parser feels like overkill for one boolean.
  So the operational form, narrower than the lesson it follows: **any claim about which section a
  ledger or questions entry is in comes from `watch.parse_ledger` / `watch.parse_open_questions`,
  never from `str.split` or a regex.** Four hand-rolled parsers have been wrong here in one day —
  `awaiting_human`'s count (4 vs 5, a wrapped title), two section splits, and one more this hour
  that silently skipped a two-line entry head — against a file whose production parser was
  importable every time. **The habit worth having is not "be careful with regexes", it is "the
  parser is one import away".**
  The damage was contained by luck rather than design: the false claim sat in a brief's *motivation*
  section, so none of the eight criteria depended on it. Had it sat in a criterion, a lane would have
  built to it.

- **Three times today a shell line reported success for a command that had not run, because I put
  the check and the action next to each other instead of joining them.** `python3 lint.py` then
  `git commit` on the following line — committed with two lint errors. `cmd > log` then
  `echo EXIT=$? >> log` — the harness reported *echo's* status, so a failing run showed "exit code
  0". And `if lint; then git commit …; echo "COMMITTED"; fi` — the commit failed on a gitignored
  pathspec and **`COMMITTED` printed anyway**, because `;` does not care.
  Every one of these is the day's dominant class in its smallest form: **a success signal reporting
  on something other than the thing you care about**. And they are all the same one-character fix —
  `&&`, not a newline and not `;` — plus the habit of ending a gated sequence with the thing whose
  status you actually want: `lint && commit && echo OK || echo FAILED`.
  The reason it recurs is worth naming: a two-line shell block *looks* sequential-therefore-
  conditional, because that is how the prose in your head reads. It is not. **If the second command
  must not run when the first fails, the shell has to be told, every time.**

- **Both wordings of the hand-off instruction are wrong, and I found the second by hitting it twice.**
  The original told lanes to append to the **absolute** main-checkout path *and* commit it — so the
  line landed uncommitted in main and committed on the branch, and `git merge` refused on a file whose
  two versions were byte-identical. I "fixed" it by telling lanes to commit the hand-off **inside the
  worktree** instead. That produced a **content conflict on every merge**, twice in twenty minutes,
  because the coordinator is editing the same file's `## Folded` section while the lane appends to
  `## Pending`.
  The mistake was treating this as a path question when it is an **ownership** question, and the
  skill already answers it: *durable shared state wants a single writer*. `handoffs.md` is durable
  shared state; `inbox.md` is append-only and per-lane, which is why the inbox has never conflicted.
  **So: lanes write the report to the absolute `inbox.md` and nothing else. The coordinator writes
  the hand-off line, from the report, when it merges.** That also removes the one duty lanes most
  often got wrong (one lane wrote both, one wrote the wrong section, one used a two-sha form the
  grammar rejected) and it means the hand-off says what the *merge* concluded, not what the lane
  predicted.
  Worth noticing about the shape of the error: I diagnosed it correctly the first time, wrote the
  lesson, and then chose a fix that moved the collision instead of removing it. **A fix that relocates
  a conflict looks like a fix exactly once.**

- **"He answered it" and "we may build it" are different facts, and an affirmative answer is
  the most convincing way to confuse them.** 2026-07-28: his *"Q2 yes"* amended `#263`'s design
  law; the implementation of that amendment is increment 20, which is lane **E**, which his same
  answer withheld behind a second gate. I read the "yes", cleared `#371`'s blocker, and dispatched
  a lane into work he had explicitly withheld — caught only while writing that lane's merge gate.
  **Evidence it was avoidable:** the plan states both facts in one table row (*"landed in the
  design … Increment 20 implements it — behind the second gate"*), and the ledger entry I was
  editing already carried the same distinction about the previous approval (*"the approval covers
  the CONTRACT, not #263's implementation"*). So the trap is not missing information; it is that
  an answer's **tone** reads as permission while its **scope** is a separate question nobody
  prompts you to ask. **Before acting on an answer: name what it authorises, and find the sentence
  that says so.** If the only sentence you can point at is the answer itself, you have its scope
  from its mood.
- **A finished prerequisite does not open a gate, and nobody is watching the gap.** The same
  incident, second half: lanes A–D landed at 07:25 and the gate's condition (*"until A–D are
  proved"*) was met for nine hours with **no question asking him to open it** — and lane D was
  never recorded in the ledger entry the gate reads from, so the entry could not show its own
  condition was met. **Evidence:** I discovered the gate was openable by walking into it, not by
  checking. A gate whose condition is satisfiable by our own work needs the ask filed **when the
  condition is met**, which means recording the thing that met it. This is `#419`'s invariant
  arriving from the direction nobody wrote it for.

- **A lane's self-reported `n/n` is a claim about its own brief, never about the plan's lane.**
  2026-07-28: lane C reported *"DONE, 3/3 green"* and it was true — it built three increments and
  all three passed. Lane C in the plan is increments **11–15**. So `3/3` was silent about `C4` and
  `C5`, the ledger recorded *DONE*, and nine hours later I quoted it to the human as *"A–D are all
  landed, the second gate's condition is met"* — inviting him to open a gate over unproved
  prerequisites. **Evidence:** `user_events/domain_files.py` has no marker search and no
  `rebaseline`; `test_user_events_domain_files.py` holds three tests; the plan's lane table was one
  file away and I did not open it. Caught by a subagent reading the tree, the **fifth** lane that day
  to refute a figure I derived rather than observed — and every one of the five was a figure I had
  reasoned to from a document, not measured. **So: reconcile a lane's count against the plan's lane
  definition before either number is quoted, and treat "DONE" in our own ledger as a lane's word for
  itself.** A denominator that comes from the same source as the numerator measures nothing.
- **Read the clock before writing a timestamp, every time, including in prose.** Same day, twice
  inside twenty minutes and the second time was ten minutes after committing the fix for the first:
  five timestamps written by counting forward from the heartbeat interval, all in the future by three
  to twelve minutes. `relay.py` stamps from the clock precisely because this happened four times in
  one day in July — but it only protects relays, and these were sentences in `questions.md`, a plan
  and three briefs, where nothing stamps for me. **Evidence it is not cosmetic:** a lane has to decide
  whether a mid-flight brief amendment predates its own commits, which is exactly the question the
  `#419` lane was handed. `date '+%H:%M'` costs one line and the habit is the only available fix.

- **Write the number from the command's output in the same act, or do not write it.** 2026-07-28, in
  the space of ten minutes and three commits, all inside the one task about how the loop writes to
  him: I published a question entry claiming *"249 words"* (it was 342), redrafted claiming *"232"*
  (it was 256), and only the third draft carried a figure a script had computed and asserted against
  the parser. Every one of those was typable because the number sat in prose next to a measurement
  nobody had run. **Evidence this is the day's dominant defect and not a slip:** six lane refutations
  the same day, and every single one was a figure derived by reasoning from a document rather than
  observed — `214px` for a measured `167.9`, `8,647` lines for `9,688`, lane C `3/3` for `3 of 5`,
  `open=138` for `139`, a sub-question alphabet of five letters for one of ten, *"34 entries don't ask
  anything"* for 34 single-decision asks. **The fix is mechanical, not attentional:** have the script
  write the figure into the text and then assert the text equals the measurement, so the two cannot
  drift. Where prose must carry a number by hand, run the command in the same shell command as the
  edit.
- **A substring cannot tell an assertion from its retraction.** Same day: I gave a lane the criterion
  *"grep your built output for `met`, `proved`, `all landed` and say what you found"* to catch a wrong
  claim surviving an edit. Five hits came back — and all five were inside corrections, the headline
  being literally *"I told you the condition was met. It is not"*. **Evidence:** resolving it needed
  reading 160 characters of context around each hit, which is the work the grep was supposed to
  replace. The criterion produced the right outcome only because the lane also reported honestly.
  **A negative check over natural language needs the polarity in the pattern or a human in the loop —
  say which you are relying on.**

- **The corpus we measure is the corpus we write into.** 2026-07-28: a plan's headline figure —
  *"the two entries promising a one-word answer are 300 and 448 words, both above the corpus median of
  302"* — was true when written and **false twenty minutes later**, because between the measurement
  and the artifact I filed **two more questions into the corpus being measured**, one of them the
  question presenting the finding. The lane re-derived at n=58 and got 307/455 against 308, so one
  entry now sits one word *under*. **Evidence the fix is phrasing, not care:** *"both above the
  median"* is a hostage to the next thing we file; *"one at the median, one half again as long"*
  survives it, and both sentences describe the same data. So when a figure measures **our own
  output**, state the claim in a form the next act cannot falsify, and say what n it was taken at.
  Corollary discovered the same hour: **stop quoting a document's own length inside it.** That count
  was 342, then 256, then 247, then 191 across four drafts, and I published a wrong figure for the
  first two.
- **When two derivations disagree, the useful state is "they disagree and agree on the conclusion."**
  Same finding: the lane's word counts and mine differ (307/455 vs 300/448, medians 308 vs 300) and
  **neither of us resolved why**. But both refute the literal claim and both support the
  weak-coupling conclusion. **Evidence for recording rather than reconciling:** picking one silently
  would have hidden a real methodological gap, and reconciling it would have cost more than the
  conclusion is worth. Record the disagreement, act on what survives both, and say the gap is open —
  a figure with two independent derivations bracketing it is stronger than one with a single
  authoritative-looking value.
- **A hollow check has a third cause nobody was watching for: the assertion is right and it is
  applied to the wrong page.** Measuring the `#263` artifact I called
  `newPage({viewportSize: {...}})`. Playwright's option is **`viewport`**; the wrong key is accepted
  in silence, so the "desktop 1280×900" run and the "mobile 390×844" run were **both the default
  1280×720** — one page measured twice under two labels, reported as two viewports verified.
  **Evidence it was luck that caught it, not rigour:** the tell was that the two runs agreed *to the
  byte* — identical `scrollHeight` for a 1280px and a 390px render, which is impossible for a
  responsive page. Had the artifact happened to pass at 720 I would have shipped "verified at both
  viewports" having checked one. The existing rules do not catch this: the assertion was correct, so
  reviewing the assertion finds nothing, and a red-proof would have gone red for the right reason on
  the wrong page. **So: every measurement that configures its subject must assert the configuration
  took effect, before it measures anything.** For a viewport that is `innerWidth === requested`
  *and* `innerHeight === requested`, and the second is not redundant — proved, not reasoned: the
  default width is 1280 and desktop asks for 1280, so on the wrong key **the width matches anyway**
  and only the height reveals it. A width-only precondition passes the exact bug. Fixed once, in
  `dev/capture/above_fold.mjs` (`1dd973f`), so no lane writes its own again.
- **A criterion that names an element nobody agreed to is unenforced, not enforced.** Every review
  brief for weeks demanded the ask sit above the fold, measured on `#ask`. **`#ask` existed on 2 of 22
  built artifacts.** On the other 20 the criterion could not be evaluated at all, so it read as a
  standard while functioning as a wish, and no lane was ever wrong for ignoring it. **Evidence the
  gap was invisible from either side:** the two artifacts that *do* have the id disagree about the
  answer — one puts the ask inside the hero and passes at 218/266, one puts it after and fails at
  594/1006 — so even the compliant cases had no shared meaning. **Before writing a criterion that
  names a selector, a file, or a marker, measure how much of the corpus has one.** If the answer is
  "two", the deliverable is the convention, not the criterion.
- **`bottom < innerHeight` was the wrong shape for the thing it was protecting.** The above-fold rule
  as written demands the ask's *box end* within the first screen. `#263`'s ask is 870px tall because
  it carries three decisions — the literal is unsatisfiable at any viewport, and obeying it would mean
  splitting one coherent decision across pages to please a measurement. **Evidence the intent was
  recoverable:** the reason the rule exists is "he can see what he is being asked", which measures as
  *the block starts above the fold* **and** *its first decision does too* — and the second half is
  load-bearing, because `top < innerHeight` alone passes a block that begins one pixel up with every
  word below. When a mechanical criterion becomes unsatisfiable, the usual cause is that it encoded a
  proxy; recover the intent and re-encode it, rather than dropping the check or exempting the page.
- **A claim about a running process, stored as prose, is false the moment the process changes and
  nothing can contradict it.** `status.json` said *"deploy = current — … Independently verified by this
  coordinator at 16:05, not taken on report."* Every clause was true at 16:05. `#218` landed at 16:44,
  and from then until 18:05 he was served a snapshot from **15:49** — so the median line the loop had
  recorded as *delivered* was not on the page he was looking at, **while he used that page to decide the
  `#263` gate.** **Evidence the phrasing made it worse:** *"independently verified, not taken on report"*
  is exactly the wording that earns trust, and it is what stopped anyone re-checking. A timestamped
  verification does not cover any later moment, and prose has no mechanism to notice. **The fix is that
  a claim about live state must be computed when it is read, not written down** — `dev/deploy_state.py`
  (`e135335`) replaces the sentence, and its output carries the clock it was taken at.
- **"The file is right" and "he is seeing the file" are two questions, and answering the first reads as
  answering both.** The first version of `deploy_state.py` compared the snapshot's bytes to
  `HEAD:watch.py` and stopped. **Its own docstring named the gap it was leaving** — *"a running process
  could still be serving from memory after its file changed underneath it"* — and I shipped it anyway.
  **Evidence, from two minutes later, inside its own red-proof:** overwriting the snapshot made
  `--autoreload` re-exec the server into old code; after I restored the file the script reported
  **current** while the served page was provably pre-`#218` (no `bdmed`, panel back to 158px). So the
  discriminating signal is not the file, the pid, or the process start time — a re-exec keeps its pid
  *and* its start time. It is `GENERATION`, set at module import and re-set on every import. **When you
  write down a limitation, that is not a disclosure, it is a bug you have chosen not to fix yet.**
- **The stale thing may be your reference, not the thing you are checking.** The `#417` lane's artifact
  said the burndown panel is **177px**; I measured **158px** live and was one sentence from reporting
  the lane wrong. 177 − 158 = **19px** = exactly the line `#218` adds, and the lane was right: my
  reference was a server running two-hour-old code. **Evidence it was nearly a wrong accusation:** the
  lane could not have defended itself — it had reverted its uncommitted `watch.py` as its brief
  required, so its renders were unreproducible from the tree by design. **Before disbelieving a lane's
  measurement, establish that your own instrument is current** — especially when it is a long-running
  process, which is the one kind of instrument that goes stale silently.
- **`pkill -f <name>` matches every process whose command line mentions the name, including yours.**
  `just deploy` does `pkill -f ud-dreamwork-watch.py` and killed the shell running the deploy — exit
  **144** (128+16, SIGTERM), the recipe cut off partway, on the one recipe whose half-completion leaves
  his dashboard down. **Evidence it is unreportable from the inside:** `pkill` has already killed the
  process that would have logged it, so it fails silently by construction. It had never bitten because
  it only fires when the *caller's* command line contains the basename, which a bare `just deploy` does
  not — mine did, because I had assigned the path to a variable. **Kill by pid; a pattern that must not
  match the caller will one day match the caller.** (`#431`)
- **Three times in one day the assertion was right and the surface was wrong, so state it as a rule:
  measure the product, not the file.** (1) The viewport option key was wrong, so two labelled viewports
  were one default page. (2) The panel height I used to judge a lane came from a server running
  two-hour-old code, and I nearly reported the lane wrong. (3) The above-fold check I had just written
  compared against `innerHeight` — **844 on mobile — while he reads artifacts inside an iframe whose
  visible height is 504**, a 40% overstatement, so an ask at 600px would have passed while being
  invisible. **Evidence the three are one failure and not three:** in every case the code under test was
  correct, the assertion was correct, and reviewing either would have found nothing — what was wrong was
  the *thing the assertion was pointed at*. **Evidence it is cheap to avoid:** each was caught by one
  question — *is this the surface he actually has?* — and answering it took a single measurement of the
  real route. Ask it of every check that renders, fetches, or reads a snapshot.
- **"No lane of mine is running" is not "the machine is idle", and mistaking one for the other wasted
  four experiments.** `#428`'s frame-sampling guards fail intermittently; four separate runs tried to
  catch the cause by running the full suite on an idle machine, and each time I recorded the run as
  confounded because I had dispatched a lane through it. The fourth time I checked the actual number:
  **load 29.9 on 16 cores with zero lanes of mine running** — `ccm`, `herdr`, `codex`, `pi` and four
  other `claude` processes, none of them mine. **Evidence the self-blame was wrong:** my two lanes are a
  rounding error against a baseline near 30, so serialising them could not have produced the idle arm the
  experiment needed, and no amount of discipline would have delivered it. **Evidence the fix is to stop
  isolating:** the variable is unavailable on this host, so the suite now records load per verdict and the
  correlation accumulates over ordinary use with no reserved window at all. When an experiment keeps
  coming back confounded, measure the thing you are assuming is constant before designing a fifth run.
- **A constant derived from a range must take the FLOOR, and three successive attempts at one number were
  all optimistic in the same direction.** The mobile fold went 706 (the top of the measured range) → 691
  (the floor, measured in a worktree) → **670** (the floor on his real target). Each wrong value called
  clipped content visible, which is the one direction that matters for a check whose job is refusing asks
  he cannot see. **Evidence it is a class and not a slip:** the frame's bottom is pinned but its top is
  not, and three separate inputs move it — the artifact's name length, the *target directory's* basename
  (it is the project name, and it shares the title bar), and how the name breaks. A value verified in
  `.worktrees/frame` is not verified for a dashboard whose target is `ud-dreamwork`, because the longer
  project name wraps the title one line further. **Prefer deriving it at runtime; if you must hard-code,
  bind the number to a check that re-measures the real surface** — that check is what caught 691.
- **A derived length is not a derived layout, and a fixture is not the surface.** Building the worst-case
  input by padding a stem to the right character count produced `xxxx…`, one unbreakable run with no
  hyphen to break on where real names have several — so it wrapped to three lines where the real name
  wraps to two, and demanded a fold no artifact needs. Then the same check, given the *real* longest name,
  was still wrong: the guard's own target directory is `devoverlay-target`, longer than the real project
  name and sharing the title bar. **Evidence:** three fixture-based versions gave 651, 672 and 672 against
  a real 693. **When the property under test is a property of the real corpus in the real chrome, serve
  the real thing read-only** — hermeticity that measures the wrong layout buys nothing.
- **The self-matching process check bit a third time, and the match came from the comment explaining the
  self-match.** After `#431`'s `pkill -f` killed the shell running `just deploy`, and after my
  `pgrep -af 'ccc --yolo'` idle check matched its own shell, I reached for the `[c]cc` bracket trick — and
  it still matched, because the literal string `ccc --yolo` appeared in the comment I had written *about*
  the problem, inside the same command line. **Evidence the trick is not the fix:** the bracket only stops
  the pattern from matching itself; it cannot stop the rest of the command line from containing the
  string. Build the pattern from parts at runtime, or match on the executable name without `-f`.
- **A brief can specify a measurement that is blind to the bug it targets.** I asked the `#433` lane to
  prove the rail fixed by comparing the rail's `scrollWidth` against its client width. **Evidence it was
  useless:** `railOverflow` was false in every one of 13 artifacts, before and after the fix, because the
  collision is *intra*-rail — two children overlapping inside a rail that never overflows. The lane said
  so, and my own probe confirmed it. **When writing an acceptance criterion, check it goes red on the
  current bug before shipping it to someone as the standard** — otherwise it is a wish, and the lane has
  to notice on your behalf.

- **An unanchored split on `## Recently landed` hit a PROSE mention of the heading, not the heading.** Folding four landed entries, `t.split('## Recently landed', 1)` matched an open entry that *quoted* the heading, truncating the open section and writing a file with **two** landed headers — 130 lines moved into the wrong half. lint caught it, but only indirectly: it reported a *reciprocity* error about an unrelated pair (`#395`/`#353`), which cost four probe commands to trace back to the structure. The ledger already records this defect twice about itself and a brief written an hour earlier told a lane to guard against exactly it. Fix: `re.search(r'^## Recently landed$', t, re.M)` plus `assert` that both headings match exactly once — and assert the post-write invariant too, since the symptom appears far from the cause.

- **Unescaped backticks in a double-quoted zsh argument execute, and the ledger silently loses shas.** A `dev/ledger.py fold --note "… `159917b` … lane `wt/qage` …"` call had its backticked spans run as commands (`zsh: command not found: 159917b`), so the note landed missing **two shas and the lane name** — and the opening `**B` of `**BOTH` was consumed too. **`lint.py` cannot catch this**: a note with no sha is legal prose, and its cited-sha check only validates shas that are *present*. The earlier folds that night were undamaged only because they happened to use `\``. Fixes, in order of reliability: pass the note via a **heredoc or a file** rather than an argument, or escape every backtick. And when a shell prints `command not found` for something that was meant to be data, treat the write that followed as suspect and re-read it — the failure is upstream of any check.

- **A perf hypothesis that names the animated attribute is usually wrong; measure
  what happens when you remove the whole thing.** `#449`'s dissolve was framey and
  two plausible causes were proposed and both refuted by measurement: the
  coordinator's (animating `feTurbulence@baseFrequency` invalidates the noise field
  each frame — freezing it measured ≈ baseline, as did freezing *all six* per-frame
  attribute writes) and the human's (too much filtered area — a 42% clamp of the
  ghost box, 553×1557 → 553×900, gave 13.7 → 13.7 frames and worst frame 184.9 →
  187.4ms). The real shape was a **threshold, not a gradient**: removing *either*
  of the two SVG filters alone ≈ baseline, removing **both** → frames 12 → 28
  (+128%), worst frame 262 → 129ms. Two filter rasterisations per frame contending
  with a main-thread shader cascade into long tasks; one is as bad as two.
  **Evidence it matters:** the authorised fix (viewport-clamp the mist) was measured
  to ship no win *before* it was built, because the lane measured the clamp instead
  of assuming the area story. Had it shipped on the reasoning, the gesture would
  have been degraded for nothing. Corollary for this repo: bisect by *presence*
  first (all off, one off, both off), and only then by parameter.

- **A test that selects a fixture loosely and then asserts the fixture's shape
  fails on new legitimate data, not on the bug it guards.** `#392b`'s check took
  *any* dated open question from the live `questions.md` and then asserted the title
  carried no time — correct as an assertion, wrong as a selection, because since
  `#392b` a title may legally carry ` HH:MM`. The first timed ask filed afterwards
  (a `#449` entry, minutes later) turned it red on master. Fix: **select on the
  property you need** (date-only entries), then assert the precondition that *at
  least one exists* — which is the thing that can actually expire. **Evidence:**
  the first red-proof of the fix came back green because the injection rewrote only
  `— YYYY-MM-DD` and the live titles carry the date *before* the em dash, so it
  reached nothing; a green red-run is a finding, and re-running it against the real
  title shape fired the precondition as designed.

- **A probe that does not verify *whose* process answered can report any result at
  all.** Verifying `#263`'s `E3` cutover, two consecutive probes returned `200
  {"ok": true}` — the exact legacy `journal_shadow=False` fallback — which read as a
  failed cutover for a change that had in fact landed correctly. The cause was in the
  probe: `watch.py` has no `--no-open` flag, so the server I launched died on an
  argparse error and `urllib` silently reached a **stale lane server already
  listening on that port**, running pre-merge code. This is the fixture-in-front-of-
  the-code failure moved to the network: nothing was mocked, and the answer still
  came from somewhere other than the code under test. **Evidence:** with the listener
  resolved from `ss -ltnp` and asserted to be my own pid, the same request returned
  `202` + `Location` + a receipt id present in all three journal tables. Rule:
  **assert the responder's identity, not just that something responded** — and treat
  a subprocess you never confirmed came up as a subprocess that did not.

- **A fault-injection fake pins the failure it was written for, and goes blind to
  every other one.** `health.mjs` carries exactly the checks this repo would want
  for `#263`'s `E5` defect — *"never shows the answered state for a write that did
  not land"* and *"keeps his text, which is now the only copy of it"* — and both
  were **green with the defect fully present**. Its `route.fulfill` hardcodes
  `status: 409`, so it only ever drives a refusal where `res.ok` is **false**. `E5`
  made a refusal arrive as `202`, where `res.ok` is **true**, and the checks were
  structurally incapable of seeing it. **Evidence:** the lane ran all 16 checks
  before touching anything and reported GREEN, and the coordinator had separately
  measured the real behaviour over HTTP — `POST /ask {"nope": …}` → `202 {"ok":
  false, "rejected": true}` — with `watch.py:3109` clearing the box on `res.ok`
  alone. Two checks named for the exact invariant, both passing over its violation.
  The rule that follows is not "write more checks": it is that a fake's **fixed
  parameter is part of the check's scope**, so a check driven by one hardcoded
  status asserts something narrower than its name claims. When a contract changes
  which status carries a failure, every fake pinned to the old one silently stops
  covering it — and nothing in the guard output says so.

- **Proving the fix works is not evidence the defect existed.** `#461` began from a
  real vulnerability in `health.mjs` — fixed port from `argv`, no check on the
  responder, `sleep(2500)` — and the brief generalised it to "the own-server
  guards". A rollout converted sixteen; measuring them afterwards showed **three**
  were ever vulnerable. The property needs two halves that had not been counted
  together: a **fixed** port, so a squatter can pre-hold it, **and** no check on
  which server answered. Eight of them ignore the port argument entirely and pick
  an ephemeral one, so the failure cannot occur; all eight also verified their
  responder inline already. **Evidence:** the coordinator's own squatter proof on
  `gitrow` exited 1 and looked like a confirmation — but it exercised the *new*
  code, and `gitrow` had an inline target check all along, so the old code would
  have failed too. Only reading the pre-merge blob settled it. So a red-proof
  against the *fix* answers "does the check work"; it never answers "was anything
  broken", and those get conflated exactly when a plausible story is already in
  hand. Measure the pre-state from history, per subject, before generalising one
  finding into a sweep.

- **A red-proof that needs the diff's own new code to be reachable proves nothing
  about the defect.** `#461`'s batch 2 converted eight guards that were already
  immune (ephemeral ports, inline responder checks) and reported red-proving each
  one *"with a squatter on the pin each guard takes from `argv[3]`"*. They took no
  such pin: **the conversion added it**, with a comment saying it existed so a
  squatter proof could aim. The proof was real, the failure was real, and both were
  properties of the new code. **Evidence, and it is why this mattered more than
  churn:** the `guards` recipe hands every guard `{{port}}` while the shared server
  already holds it, so the added pin aims eight self-porting guards at a socket
  that is guaranteed occupied — under that exact condition the converted guard
  exits 1 and master's exits 0. The rollout would have reddened eight guards in
  `just test` to fix a defect none of them had. Test: **could this red have been
  produced against the code as it stood before the diff?** If reaching the failure
  required a parameter, flag or seam the same change introduced, the proof is
  circular — and it will look most convincing exactly when the change is largest.

- **An exactness the reader cannot see is not a difference.** `#463` asked for a
  secondary *"modified X ago"* on a review artifact *"when ctime != mtime"*, and the
  literal implementation of *differs* — `created_ns != mtime_ns` — is true for **24
  of this repo's 28 artifacts**, because writing a file sets birth and the content
  write then moves mtime a few hundred microseconds later. Nothing was edited; the
  page would simply have printed `3d old · modified 3d ago` on nearly every row,
  which is the exact inverse of the rule. **Evidence it was not a fixture artifact:**
  the lane's own test asserted equality on an unedited file and failed, and the same
  measurement on the real corpus gives 24/28 at nanosecond exactness and 0/28 at
  display resolution. The fix is where the *rule* lives, not where the data does: a
  "when they differ" condition compares **the figures a reader sees** — so the
  server marks a candidate and the client decides beside its own formatter. Two
  corollaries earned the same hour: mirroring the formatter on the other side to
  decide there would be a second copy of the thing whose output *is* the criterion;
  and a fixture that demonstrates *"modified long after created"* by pushing mtime
  hours past birth pushes it into the **future**, where the age reads `0s` and the
  row proves nothing — birth is always now, so age the created side instead.

- **When an external sweep kills a lane, its report is gone but its work is not —
  commit the worktree before anything else.** Both lanes were killed mid-task at
  03:42; the harness output files were **0 bytes**, so every claim they would have
  made about verification died with them, while 407 and 373 lines of real work sat
  uncommitted in their worktrees, one `git checkout` away from nothing. **Evidence
  the reports were the only loss that mattered:** the surviving record was the
  coordinator inbox's per-milestone lines — which is exactly why the handshake
  protocol writes progress to a file as it goes rather than reporting once at the
  end. Order of operations: commit each worktree as an explicit `wip(#N)` on its own
  branch **saying it is unverified**, then verify from the diff rather than from a
  report that no longer exists. A lane's death is not evidence its work is bad; it
  is evidence nobody has checked it.

- **Two agreeing signals are not corroboration when both come from the same misreading.**
  Filed at 04:24 as a routing bug — *"`ccc @glm52` runs grok"* — on two pieces of
  evidence: `ccc` printing `warning: runner "grok"`, and a direct probe answering
  *"Grok (xAI)"* when asked its own identity. The human corrected it 23 minutes later:
  **`@glm52` uses the grok CLI harness with the glm-5.2 model.** So the runner label
  names the *harness* and never claimed anything about the model, and the self-report was
  a model's account of itself under a harness that supplies an identity. Each signal was
  wrong on its own, and they were believed because they matched. The confidence came
  entirely from the agreement, and the agreement came from measuring one wrong thing
  twice. **What would have caught it costs nothing: ask the human, or read the config
  that did the dispatching, before writing a P1 that says his instruction is not being
  honoured.** Corollary for provenance: record a lane's model from **what dispatched
  it**, never from the process's own account — and treat *"state which model you are"* in
  a brief as a courtesy field, not evidence.

- **A dispatch alias is a claim about which model you got; the lane's handshake is NOT the
  measurement either** (superseding the first version of this entry, which said it was).** His orchestrator framing names two runners for different strengths —
  `ccc @grok` (fast) and `ccc @glm52` (slower, often more capable) — and the whole
  point of the pair is that a second lane is a *different* judgement. **Evidence it
  was not:** `ccc --yolo @glm52 "reply with the model name and provider you are"`
  answers **`Grok (xAI)`**; `ccc` prints `warning: runner "grok"` on the way in; and
  every lane log in one long session shows `runner "grok"`, including one file named
  `421a-glm.log` for a dispatch addressed to glm deliberately. So several ledger
  entries and `status.json` rows recorded `glm-4.6 via ccc @glm52` — taken from the
  alias typed, never from what answered. The failure is silent by construction: the
  alias is accepted, the work gets done, the output is good, and nothing anywhere
  contradicts the attribution. It surfaced only because a lane obeyed the brief's
  *"state which model you are"* and its answer disagreed with the command I ran.
  Two consequences worth keeping: **a review lane that is secretly the same model as
  the lane it reviews is one model agreeing with itself**, which is the specific value
  the split exists to buy; and **a model attribution is history, so it is never
  guessed** — where the log is gone, the honest record is *unknown*.

- **In fish, one non-matching glob aborts the whole command — so a multi-path search
  can never run, and the empty output reads exactly like "it is not there."** Looking for
  ccc's alias→model config I ran `grep -rn glm52 ~/.config/ccc* ~/.ccc*`. Fish answered
  `no matches found: /home/xertrov/.ccc*` and ran **nothing** — the `~/.config/ccc*` half
  was never evaluated. I read that as evidence the config did not exist, said so in a P1,
  and wrote a brief telling a lane the registry *"is not in an obvious ~/.config/ccc"*.
  The lane found it immediately at **`~/.config/ccc/config.toml`**, with
  `[aliases.glm52] runner="grok" provider="llmp" model="glm-5.2"` — the exact answer, in
  the first place I claimed to have looked. **Evidence of the mechanism, not just the
  miss:** the error names only the failing pattern, so the output looks like a completed
  search with no hits; a `grep` that ran and found nothing and a `grep` that never ran
  are indistinguishable at a glance. Two habits: **one path per search when any path
  might not exist**, and treat "no output" from a compound command as *unknown* until the
  command's exit is checked. This is the same shape as a check that examines nothing —
  absence of a finding is not a finding, and here it manufactured a false one.

- **Writing a marker's literal form inside an entry body makes the parser count it as a marker.** Prose in
  `#469` mentioned `origin: **unknown**` to explain why an attribution stays unknown, and `lint` correctly
  errored: *"2 origin markers (loop, unknown) — exactly one is the claim; two is none"*. The checker was
  right and the writing was wrong. Evidence: `efa3f3a` fixes it by naming the value in words instead.
  The general shape is that **these files are parsed, so quoting their grammar inside them is writing in
  it** — the same reason a bolded `Lane-owns:` was invisible to `dev/lane_guard.py` (`#468`) and a nested
  `- **Answer (via watch…)**` bullet terminated a parsed entry (`#467`). Discuss a marker by describing it,
  never by spelling it.

- **Commit the brief BEFORE creating the lane's worktree, or the lane's branch does not contain its own
  brief.** Done in the wrong order twice tonight (`draftstore`, `premerge`): the worktree was branched from
  `master` and the brief committed a moment later, so the file exists in the main checkout and is absent
  from the lane's tree. The lane still reads it by absolute path and `dev/lane_guard.py` still enforces
  ownership — the guard runs in the main checkout, which has the brief — so nothing breaks. What it costs is
  a lane spending its first minutes reporting a phantom problem, and one did exactly that. The cost is real
  because the alternative it might reach for is worse: merging `master` mid-increment to "fix" it moves a
  working tree for no reason. Evidence: `94e0582` committed after the worktree at `wt/premerge` was created.

- **Two briefs must never grant the same LINE, not just the same file — and `DEFAULT_GUARDS` is one line every
  guard-adding lane wants.** I granted the `justfile` `DEFAULT_GUARDS` line to `mockups` (#417) and
  `summaryjson` (#275) at once. `mockups` registered first, taking it to 58; had the second lane also edited
  it, the merge would have conflicted on a single line two agents were each told they owned. The disjointness
  invariant is about the text, not the path, and a one-line grant reads as harmless precisely because it is
  small. Fix applied: guard registration is now **centralised at merge** — a lane builds and red-proofs its
  guard, runs it directly (`node dev/capture/<g>.mjs <outdir> <port>`), and REPORTS the name; the coordinator
  registers it. Say in the ledger that the guard was unregistered at the lane's commit, or its branch reads as
  gating when it does not. Evidence: the correction relayed to `summaryjson` at 06:00, before it wrote.

- **When a red-run comes back green, suspect the INJECTION before the test.** Verifying `#294`'s
  `test_autoincrement_does_not_reuse_a_deleted_high_water_id`, I dropped `AUTOINCREMENT` and all 14 tests
  stayed green. By this repo's own rule that is a finding, and I was one step from reporting the lane's test as
  hollow — but the test's docstring names `task.id` and I had edited `entry.entry_id`. Injecting into the right
  line reds exactly that one test. So the rule *"a green red-run is a finding, never a relief"* needs its
  companion: **confirm the injection reached the line the check names.** Both failure modes look identical from
  the outside — a check that cannot fail, and a probe that never arrived — and this repo has now been bitten by
  each. Read the docstring's named production line and edit *that*. Evidence: `46c3f4c`; the same session
  earlier produced an inconclusive lint probe that also proved nothing and was reported as inconclusive.

- **A log still being appended to is not a result, and reading one as complete is the same error as reading an
  empty output as proof.** Mid-run I grepped a live `just test` log for failures, saw `identity`/`gitrow`/
  `serving` absent from the FAIL list, and reported that they PASSED. The run had not reached them. When it
  did, all three failed — with the identical port error I had just spent two turns calling unexplained — and a
  lane refuted my claim by reading the very file I had pointed it at. Absence of evidence in a partial file is
  not evidence of absence, which is precisely the `#469` empty-glob mistake wearing different clothes. Before
  concluding anything from a log, establish that the producer EXITED; a tail is a snapshot of progress, and
  `grep -c FAIL` on it measures how far it got. Evidence: `#471`'s correction, four `is serving` messages in
  one run against my claim of three passes.

- **A malformed bisect range is worth two checks, and "that culprit is absurd" is not one of them.** Hunting
  the `#474` dock regression I ran `git bisect start <bad> <good>` with a "good" that was **not an ancestor** of
  the "bad". Bisect accepted it and reported *"445 revisions left"* where a well-formed range had 55, so:
  confirm ancestry with `git merge-base --is-ancestor good bad` before starting, restrict to the paths that
  could possibly matter (`-- watch.py dev/capture/<guard>.mjs` cut 841 first-parent commits to 55, six steps at
  25s), and know that `git bisect reset` must actually take — a stale `bisect log` served the previous run's
  verdict and I nearly read it as the new one.
  **The part I got wrong is the more useful half.** I dismissed the first verdict as *"a dream-file commit that
  cannot break a browser guard"* — because I read the commit **subject** (`dream(#385): …`) instead of its
  diffstat. `dream(` is this repo's message prefix for dream-journal *work*, not a marker that a commit only
  touches dream files: `0dd136e` changes `watch.py`, `test_watch.py`, `watch-design.md` and a guard. The
  well-formed bisect returned **the same commit**, and it was right the first time. So: an absurd-looking
  culprit indicts your reading of the commit before it indicts the method — run `git show --stat` on it, which
  costs one command, before concluding the range is broken. Evidence: `#474`, where that misreading cost two
  extra bisects and a lesson that had to be rewritten.

- **A subagent's own claim that it reversed a containment breach is the one thing you must verify yourself, and
  it takes two commands.** The `quiesce` lane wrote its plan amendment to the **main checkout** by resolving a
  path against the wrong root, self-caught it, reversed it with a content-anchored edit rather than `git
  checkout` (correct — a checkout would have discarded whatever else was there), and disclosed it unprompted.
  All good behaviour, and none of it is evidence: the reversal is a claim about bytes I can read. Verified with
  `git diff -- <path>` (empty) and `git show --stat HEAD | grep <path>` (absent), the second because the breach
  window **overlapped a merge of mine** and a dirty file caught in a commit is how `12f47e3` happened. Also
  worth keeping: `lint`'s lane-containment backstop reported the file dirty while it was, which is the first
  time that check has fired on a real breach rather than a rehearsal. Evidence: `#263` H2's merge, where the
  lane reported the breach and the two commands took under a minute.


- **Never cache a DOM reference across the live tick — it does not mutate the node, it REPLACES it.** The
  dashboard re-renders on a 2s phase that is independent of load, through `innerHTML`, so a reference taken at
  the start of a 6-second sample points at a **detached** node by the middle of it. That is not a stale value:
  a detached element's `getBoundingClientRect()` is all-zeros and its `getComputedStyle` reads a one-directional
  transient, so a trace does not go quiet — it **invents a defect**. Three guards read a snap, a sweep and a
  collapse-instead-of-grow off perfectly correct pages this way, and each was one line: re-acquire the reference
  every frame. What makes it expensive is that it looks like the page misbehaving and reproduces only where the
  tick phase collides, so it passes solo and fails in the suite — the shape everyone here reaches for "load" to
  explain. Evidence: `#475`'s `oneinput`/`wisp`/`qsec`, diagnosed by the `motion` lane with a probe that sampled
  the cached and a per-frame reference side by side (cached `drift down=1.00` FAIL vs fresh `0.57` PASS, 4/4).
- **And the mirror of it, which is a real page bug: the tick can replace the node CARRYING a transition.**
  Keeping the open state across the re-render is only half the contract; the fresh node also has to inherit the
  *gesture*, or a native `el.open = true` lands it at full height in one frame. Read the two together — the same
  re-render that invalidates a guard's reference invalidates the page's own in-flight animation, and only one of
  those two was ever fixed. Evidence: `#477`.
- **A "next increment is X" entry that was never folded reads as NOT-done when X landed hours ago — verify
  the landing in git before dispatching, not just the entry's prose.** I dispatched a lane to build `#294`'s
  schema + seeded sequence because the `#294` entry said "the next increment is the schema"; it had already
  landed at `50f4933` (06:07, before my session) and was never folded (0 citations). The lane found it and
  pivoted to a delta instead of duplicating — the good outcome — but the dispatch was wasted and the delta is
  now a design fork for the human. This is `#363`/`#404`'s family (a landing nobody folded), biting from the
  *task* side rather than the hand-off side. The check is one command: `git log --oneline --grep='#294'` and
  look for the landing commit before believing "next is X". Evidence: the `50f4933` entry/task split vs my
  lane's flat "1b" (`wt/294`), 2026-07-29. **Addendum (2026-07-30):** the dispatch-shortlist is the same trap
  with a reassuring face — I briefed #431 off its "ranked #1 startable, verified" row and caught it only at
  commit time: landed `522d30d`, folded `9a117c71`, and FOUR more of its rows checked out landed too (5/5
  stale). A shortlist's "verified" column expires with the next fold. The store query (`state='open'`) is the
  only trustworthy startable list; run it before every brief, not after the overwrite.
- **A lane that reads whole large files (`watch.py` ~8900 lines, `tasks.md` ~8000) can blow its context and die
  on `max_tokens_truncation` before writing anything.** The `#298` lane read 1.08M input tokens over 16 model
  calls and was truncated mid-work — zero commits, nothing to salvage. The brief's file list (`watch.py`,
  `tasks.md`, the design docs) is an invitation to read them wholesale, so the constraint has to be stated:
  grep for the symbol and read only that window, each file once. Put it in the dispatch prompt for any lane
  pointed at the big files. Evidence: `019fabf4` failed 931s / 30 tool calls / exit 1, 2026-07-29.
- **`dev/ledger.py fold` MOVES the entry — it is not an annotate-in-place tool, and calling it on an
  in-progress task closes that task.** I used `fold 294 --note …` to record increment 4 of a five-
  increment migration, and the entry went to `## Recently landed` with the cutover still open; the
  premature-landed window lasted four commits before the inc5 fold-call reported "nothing to fold" and
  exposed it. The note-appending was right, the tool was wrong: for a mid-task increment note, edit the
  entry by hand under `## Open`. `fold` is for done. Evidence: `ud-dw-tasks-migrate`'s census counts
  dropped #294 from open at 18:12; corrected 19:04.
- **Compaction loses the subagent HANDLES, not necessarily the subagents — poll "not_found" is not proof
  of death.** A compaction event made three running lanes' task ids unqueryable (`not_found` on poll), and
  I re-dispatched two of them as losses. Wrong in at least one case: the "dead" visual-review lane was
  still running and reported a full PASS forty minutes later, while its redundant re-dispatch had to be
  killed. The durable truths that DID hold: the lane that had written its deliverable to the repo
  (`cli-warning-layer.md`) was collectible without its transcript, and committed briefs under
  `.dreamwork/docs/briefs/` made re-dispatch a five-minute job. Corollaries: (1) after compaction,
  reconcile `status.json`'s agent list against reality but treat a lost handle as UNKNOWN, not dead —
  wait a tick or check for the lane's on-disk artifacts before re-dispatching, or you pay double for the
  same work; (2) a lane whose deliverable is a verdict (not a file) should write its report to disk as it
  goes, so a lost handle never means a lost report. Evidence: 2026-07-30 01:10 tick, lane 289viz
  (`019fae61`) reported after being declared dead; its re-dispatch (`019fae7e-9a5a`) killed as redundant.

- **The retired-field check caught the coordinator re-growing `task_ids` from memory of the old shape
  (2026-07-30).** Writing `status.json` agent entries by hand, I reached for the shape I remembered —
  with per-agent `task_ids` — and `#294` T2 had retired exactly that field as a second derived truth.
  `lint.py`'s retired-field check ERRORed on the same tick. Lesson: when hand-writing a machine-parsed
  file, copy the CURRENT shape from the file itself (or the check's message), never the remembered one —
  memory of a format predates its rulings. The check doing its job here is the standing proof that
  retired-field lint is not hollow.

- **2026-07-30 05:55 — the coordinator dropped `isolation="worktree"` on two dispatches and both lanes ran in the MAIN CHECKOUT.** The 510orc and 511live spawns went out with default isolation (shared workspace); both agents ran git in the main checkout, producing a topology mess (master reset a commit, one lane's commit on the other lane's branch, a coordinator commit landing on a lane branch mid-gate) plus a guard run racing branch switches. Recovery: preserve the lane's commit on its own branch, rebase the coordinator commit back onto master, delete the stray branch. The rule had been "worktree-isolated lanes" by posture, but nothing enforces it at the spawn site — the parameter is per-call and the default is shared. **Every spawn_subagent for a lane carries `isolation="worktree"` explicitly; a dispatch checklist item, not a remembered default.** This is the #465 class (lane in the main checkout) caused by the COORDINATOR this time, not the lane.
- **A sabotage written as `False and X or Y` is no sabotage** (2026-07-30, #511 gate). The coordinator's injection meant to disable a flag but `or Y` kept it live for exactly the ids under test — the red-run came back green while the "bug" was in place. The corrected injection disables the whole statement (`if False:`), and the green first run was treated as what it was: proof the injection never reached the branch, never as relief. Same class as the fixture-that-builds-the-list-itself, one gate later.

- **A `<<<<<<< … ======= … >>>>>>>` resolver is not a diff3 resolver** (2026-07-30, #508/#514 merge gates). The handoffs.md keep-both-sides resolver matched only the three-marker form; git's default conflict style is diff3, which adds a `||||||| base` section. The regex's first group swallowed the base marker and the base content, leaving stray `|||||||` lines and stale duplicated lines IN the resolved file — which then passed `git add` and only failed at lint's live-silence test. Two companions, same incident: `str.replace("## Folded", …)` matched the BACKTICKED prose mention before the section heading (first occurrence is not the target occurrence — anchor on a line-anchored pattern), and a fold-line updater that doesn't re-run the silence test before committing hands the red to the suite. The check that caught all three is the one the CLAUDE.md rule predicts: assert the precondition (here: no conflict markers of ANY of the four forms remain) rather than assuming the tool's output shape.

- **With defense-in-depth, a single-line sabotage going green is not automatically a hollow check — trace the second line before concluding either way** (2026-07-30, #523/#524 gate). The typed-clamp guard section (bdinput c2) went green when the WRITE clamp in `applyBurnLimit` was sabotaged — because a pre-existing, independently-written READ clamp in `displayBurnLimitValue` also caps the value on the way out. Sabotaging the read clamp alone went green the same way (the write clamp masks it). Neither run meant the check was hollow: the user-visible contract "a typed over-cap value never displays above the cap" is protected by two production lines, and the guard binds the contract, not either line. The honest red is the DISJUNCTION — sabotage both lines at once and the check failed exactly where predicted. So the triage rule sharpens: a green red-run is a finding, and the finding can be any of three shapes — (a) hollow check, (b) bad injection, (c) defense-in-depth — and only (c) resolves without touching the check. Name the candidate second line before declaring (a) or (b).

- **Capture paired visual evidence in ONE session against the FINAL fixture** (2026-07-30, #525 gate). The lane's desktop and mobile screenshots showed the same "ragged table" example rendering two different ways — prose on desktop, a table on mobile — because the fixture was edited between captures (the mobile shot shows the by-design body-pad case, desktop the header/delim degrade). Parsing is viewport-independent, so the pair reads as a contradiction and the reviewer has to re-derive which is true from the guard. The guard was load-bearing and held (independent red on the degrade hinge), so this was a finding about evidence, not correctness — but a contradictory evidence pair costs the reviewer exactly the trust the screenshots were meant to cheapen.

- **A `-k` filter that names the wrong test is scaffolding in front of the injection** (2026-07-30, #520 gate). The coordinator's independent red (mv injected between stop and wait-port-free) came back green TWICE, and both times the reason was the same and it was mine: `-k "order or ORDER"` selected `test_deploy_new_ordering_completes_against_autoreload_standin` (an end-to-end fixture that never reads the recipe text) and DESELECTED `test_justfile_deploy_stops_before_ship_before_start_before_verify` (the text-anchor test the injection was aimed at — its name holds no "order" substring). One real finding hid inside the mistake: the recipe-order test pinned only `stop < ship`, not `wait < ship`, so the intermediate order was genuinely unbound — worth strengthening, and strengthened (`i_stop < i_wait < i_ship`, red-proved against the same injection, `assert 1113 < 1062`). But the scaffold failure came first and would have masqueraded as that finding's proof had the first run been taken at face value. The discipline, sharper: **when a red-run is green, verify the selected test is the one the injection binds before concluding anything about the check** — run the named test by full name, and treat a green from a filtered run as unproven until the selection is audited.

- **A piped `git diff | head -N` review can hide the deletion the commit exists to make** (2026-07-30, #533 forensics). The questions.md truncation reached commit `0f97df03` (+8/−130) because the pre-commit review was `git diff .dreamwork/questions.md | head -30`: the +8 answer insertions sat at the top of the diff, the −130 tail deletion at line 2925 never entered the pipe, and the commit went in believing it was the answers alone. The cheap fix is not "read more lines" but **review the STAT, not the head**: `git diff --stat` shows the +8/−130 shape in one line and a −130 on a file you meant to append to is a siren at any scrollback. A diff review whose window is smaller than the diff is not a review of the commit — it is a review of the commit's first screen.

- **Red-proving the path you were told to fix leaves the seam's sibling arm unbound** (2026-07-30, #274 gate). The lane's five replay/attempt tests bound the ok-path replay end to end (one receipt, one application, real server, real journal) and every one was discriminating — but the verdict mapper the lane added (`_replay_verdict`) has TWO arms, and nothing bound the rejected arm: sabotaging `if result.state == "rejected":` to always-ok passed all five while a retried REFUSAL told the client `ok: true` — clearing a draft nothing durable holds, the #136 lie one seam over. The lane had even written the rejected contract into its own docstring; the red set just never visited it. The shape to check for at gates: **when the fix adds a branch that maps N cases, the red set must name an injection per arm, not per path** — "the dedup seam" is one path, "accepted replay" and "refused replay" are two arms, and the one nobody typed in the bug report is the one the tests forget. Closed gate-side with a born-red binding test (`test_replayed_rejection_returns_the_rejection_verdict`, AssertionError at the verdict assertion with every precondition green).

- **A lane worktree can be dirty at CREATION with the main checkout's uncommitted state** (2026-07-30, found gating the late 520deploy notice; hypothesis, evidence-consistent). A stale harness clone (527recon's tree, `.grok-1/.../subagent-019fafe8-…12a806c01584`) held a dirty questions.md (+8/−130) whose content was the main checkout's *post-truncation* file: HEAD (branched pre-truncation, tail present) → working tree (truncated + the 07:44-07:48 answers) — the diff is exactly the #533 incident's shape, and the file mtime (08:11:56) is the tree's creation time. The parsimonious read: harness worktree setup copied the main checkout's *dirty* file over the clean checkout at creation. Consequence for the #535 exit-dirtiness check: **`git status --porcelain` at lane completion must be read against dirtiness at CREATION, not assumed clean-by-construction** — a lane can inherit a dirty tree and the completion probe would misattribute the coordinator's uncommitted state to the lane. (Nothing was salvageable: the fossil's unique content was precisely what master deliberately restored away at `fd53d82a`.) **Corroborated same-day**: lane-526proof's tree holds the identical fossil (+8/−130, mtime 08:06:49 — six minutes before the 527 tree's), two independent lane trees created in the same window both carrying the main checkout's dirty file at creation; and the four harness instance dirs (`.grok`, `.grok-1`, `.grok-2`, `.grok-shared`) are views of ONE physical tree (same device:inode), so a "leftover worktrees" census sees 4 entries for 1 tree.

- **A glm-5.2 lane cannot read an image — a UI brief that says "look at your
  screenshot" is a crash instruction, not a step.** lane-504chat (glm-5.2)
  died mid-verification on `API 400: messages.content.type is invalid,
  allowed values: ['text']` — 102 model calls in, after committing, while
  doing exactly what its brief asked (visual check of its own PNG). The
  harness rejected the image content block; the lane had no recovery. For UI
  lanes: grok-4.5 can see (when its credentials work); a glm lane's brief
  must say text-only verification and leave the visual verdict to the
  coordinator, who reviews the lane's screenshots. (2026-07-30, #504 salvage
  gate.)
- **A #535 porcelain check keyed on MASTER's head sha is hollow against a
  harness clone — the object does not exist there, and `2>/dev/null` turns
  the failure into "no commits".** The salvage check ran
  `git log <master-sha>..HEAD` in the lane's independent clone; the sha was
  committed after the clone was cut, so git exited nonzero, the redirect hid
  it, and an empty result read as "crashed before working" — wrong: the lane
  had committed and the screenshots were the only thing that contradicted
  the verdict. Compare against the LANE's own base (`git log --oneline -5`,
  or the dispatch-time sha recorded at spawn), never master's. Assert the
  precondition the check depends on — the range's start point must resolve.
  (2026-07-30, same gate.)

- **A trace field that is collected but never asserted is a hollow check wearing a thorough header** (2026-07-30, #505 phase-2 gate). The independent red for the keyed reconciler deleted the qid-key branch from `viewNodeKey` — and passed BOTH guards aimed at keyed identity, selectkeep and regroup. selectkeep's green was defense-in-depth (`isEqualNode` short-circuits morphdom updates for unchanged cards, so positional fallback is invisible while nothing moves). regroup's green was worse: its header claims it asserts "the card is the SAME element before and after (keyed by data-qid, not by its positional key)" and the trace really does collect `sameNode` per frame — but no `ok()` ever reads that field; the assertion that runs is `n.frames.every(x => x.target)`, an existence-by-qid check that positional element-reuse satisfies while destroying node identity. The guard predates the reconciler: its own comment says node preservation "would need a keyed reconciler for the list — see the dream". The dream landed and the guard was never upgraded to assert what the architecture now provides. Two sharpened rules: **when a feature lands that makes a previously-impossible assertion possible, grep the guards for the deferral comments ("would need", "see the dream") and upgrade them in the same gate — a deferral comment is coverage debt whose due date is the merge.** And **the header's claim-list is not the assertion-list: read the `ok()` calls, never the comment.** (Filed #540; the binding check is a typed draft in a non-answered card surviving an answer-regroup with ITS question — the failure mode keys alone prevent, since the focus-gated value-stamp would pair a moved card's fromEl with the wrong toEl.)

- **Two guard-repair shapes from the d56a3c2a fallout** (2026-07-30, draft/indicator gate-repair). The #504 chat kind broke two guards at 12:14 and the redness went unseen for hours because the 13:33 suite was recorded from memory as "1 FAIL" — **write the suite verdict down from the log, not from the impression of it**. (a) *A guard whose sets are derived live cannot see a flag being dropped*: with `sticky` derived from the live COMMANDS, unsticking add-idea silently reclassified it as decaying — and it decayed CORRECTLY, so every derived arm stayed green. The binding form for a deliberate product contract is a **named membership floor** (`['chat','add-idea'].every(k => sticky.includes(k))`): growth joins freely, leaving is the loud event. (b) *Damage you assign is damage you measure wrong*: indicator's laundering break assigned `style.transform = 'translate(0px, 40px)'`, but the element RESTS at a non-zero transform (layout + transform positioning; the row wrap made the rest ~29.5px), so the break's net damage was 40−29.5 = 10.47px — under the check's own >20px precondition, which then "failed" while the heal worked. **Compose damage onto the rest (`el.style.transform += ' translate(...)'`), never replace it, unless you have first asserted the rest is zero.** Companion: the first heal-sabotage (watch.py:7090) came back green — the guard rides the setContent-internal paintIndicators(true) at :7271; a call-site count is not a call-path proof.
