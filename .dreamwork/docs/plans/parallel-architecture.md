# Break up watch.py, and the norms that make parallel work cheap (#124)

Human-proposed 2026-07-25 (~10:45), after I measured the bottleneck:
"break up watch.py and adopt norms that help work in parallel for faster
dreaming (note: we don't want to overuse subagents by default, might get
expensive, but if the user asks for parallelization, then we have the
option provided we first have the right architecture)".

The framing matters: **parallelism stays opt-in, the architecture stops
making it impossible.** Today a `parallelize` request against the webui
can only be honoured by one agent, because one file is the whole surface.

## The measurement

`watch.py` is 4008 lines and has taken 58 commits on 2026-07-25
alone.

**Updated 2026-07-25 ~14:53, and the second measurement is the stronger
one.** The queue reached 43 open tasks and sorted naturally into EIGHT
coherent batches — composer geometry, composer behaviour, motion polish,
panels, repo identity, structural, ambient, hooks. **Seven of the eight
need `watch.py`.** So the coordinator can dispatch exactly one dreamer
at a time, not because there is one dreamer's worth of work, but because
there is one file. In thirty minutes the human filed nineteen items; all
nineteen queued behind the same holder.

The disjointness invariant permits exactly one holder, so every UI steer
serialises through one dreamer however many are free. That is no longer
an argument that the file is a bottleneck: it IS the bottleneck,
measured, with the work sitting in the queue unable to start.

## What must not break

- **Stdlib only, no build step.** A package of plain modules keeps this;
  a bundler does not.
- **`python3 watch.py --target . --dev` still works** from a checkout.
- **Deployment.** `just deploy` snapshots `git show HEAD:watch.py` to a
  single file outside the repo, so the running server cannot be changed
  by an agent editing the tree. A multi-file layout breaks that in a way
  worth noticing *before* the split, not after: the snapshot becomes
  `git archive HEAD <dir> | tar -x` into a versioned directory, and the
  server runs from there. Same property, one more line.
- **The generation reload.** Open tabs reload when the server restarts;
  whatever the layout, `/mtime` must still bump.

## Candidate seams, in the order they pay

1. **Components** (`#112`) — the artifact vocabulary in its own module.
   Already planned, already measured as cheap, and it is the seam that
   gives a second dreamer somewhere to stand.
2. **The shader** — `SHADER_JS`, `mountDreambg`, the world-space
   anchoring. Self-contained, rarely co-edited with anything else, and
   the single largest block.
3. **Question surface** — `qaCard`, the parsers, the three write
   endpoints. Cohesive, heavily edited, and the spike showed its
   coupling to the rest is one CSS address.
4. **Server core** — routing, `resolve_confined`, `/data.json`, the
   status reader. The part nobody wants to touch by accident.
5. **Chrome/router/motion** — the shell, `renderChrome`, the dissolve.

Each slice is only worth taking when a real batch would have used it;
splitting ahead of demand is the same mistake as building the wrong
abstraction.

## Norms that make it work (the actual deliverable)

The split alone buys little. What buys parallelism is a set of rules
that make "who may touch this" answerable without asking:

- **Ownership is per module, declared at dispatch**, and recorded in
  `status.json`'s `agents` block as it already is. Finer modules mean
  finer ownership, which is the whole point.
- **Claims and holdings move through files; messages only wake readers.**
  The coordinator is the sole writer of the shared ledger. A landed report
  names what it did *and did not* do from its brief, so a crossed correction
  exposes the gap rather than implying it was applied. An instruction that
  must precede a commit names the commit boundary it must precede.
- **Absence is not established inside the report window.** If a report may
  still be arriving, wait a beat and read the inbox again before declaring it
  missing. The reader can be stale just as easily as the writer.
- **Explicit staging protects ownership only when the staged change is
  yours.** A held path carrying edits you did not make is a question, not a
  commit; `git add <path>` is not permission to sweep another agent's
  mid-proof work into your increment.
- **Shared vocabularies get one owner.** `COMMANDS`, the token block,
  the motion constants: one module, one holder, everyone else reads.
  Today's failures were all shared mutable state without a named owner —
  an id counter, a working tree, a port, a fixture.
- **A CSS class is a style hook or an element address, never both**
  (spike #115). Cross-module addressing is how a split file silently
  re-couples.
- **Guards are per module too.** `dev/capture/` scripts already take
  `(OUT, PORT)` and run against a frozen fixture; a module's guard is
  what lets its owner verify without the whole page.
- **The styleguide stays single-source.** `watch-design.md` documents
  the system, not each file, or the split multiplies the doc burden.
- **Ports have owners, and a test proves the server is its own.** This
  section was written predicting that shared mutable state without a
  named owner would bite — "an id counter, a working tree, a port, a
  fixture" — and on 2026-07-25 the port did, in the worst available
  way: dreamhub's guard failed to bind 39897/39895/39894, its readiness
  probe found a *watch* instance answering nearby, and it asserted 23
  checks against a stranger's server. Green, and measuring somebody
  else's process.

  | Range | Owner | Use |
  |---|---|---|
  | `35110` | coordinator (`just deploy`) | the deployed dashboard the human reads; persisted in `.dreamwork/watch-port` |
  | `39890-39899` | whoever holds `watch.py` | `just watch` dev server, `just guards` fixture server |
  | `39880-39889` | whoever holds `dreamhub.py` | hub server and `dev/hub/` guards |
  | `39870-39879` | unallocated | claim it here before using it |

  Ranges are necessary and **not sufficient** — a stale process from a
  previous batch can still hold a port you own. So every guard
  **verifies the server is its own before asserting**: fetch something
  only that server serves and check it, rather than treating any 200 as
  readiness. A readiness probe that accepts any answer is how a test
  ends up grading a stranger.

## Cost discipline (his constraint, not an afterthought)

Parallelism is a capability, not a default. The loop already says the
coordinator works one inline increment at a time and `parallelize` is an
explicit fan-out; nothing here changes that. Two dreamers on disjoint
modules cost roughly two dreamers — worth it when the human is streaming
steers faster than one can absorb, wasteful when he is away and the
queue is deep but quiet.

## Open question for the human

Sequencing. Rec: do NOT do this as one big split. Take seam 1 with #112
because it is already justified, seam 2 (shader) next only if a batch
actually wants it, and let the rest wait for demand. A 3000-line file
rewritten in one increment is exactly the kind of change this loop's
philosophy exists to prevent — and the day's evidence is that the
expensive bugs came from structure nobody had exercised, not from
structure nobody had tidied.
