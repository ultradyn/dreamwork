# Building dreamhub stage 1 — what the plan could not have known

Task #96, build. Nine increments plus two the plan did not have, eleven
commits, `ab32541..51a62bc`. 102 pytest, 32 structural checks, 8 contract
checks. The plan (`dreamhub-stage1.md`) was good enough to build from
directly and I diverged from it in exactly two places, both noted below.

## Three checks passed on their own bug

The instruction to show every guard failing before trusting it earned its
keep three times, and none of the three was visible by reading.

1. **`test_slug_is_stored_not_recomputed`** asserted that after adding a
   colliding project, the incumbent still had its slug. Recomputing on read
   *also* yields that, because the incumbent is recomputed first and wins.
   The failure that actually bites is the other direction: remove the
   incumbent, and the survivor is silently renamed.
2. **`test_one_slow_project_does_not_delay_the_others`** built its own
   `ThreadPoolExecutor` and mapped `_probe_live_safe` over rows. It passed
   with `probe_all` fully serial, because it never called `probe_all`. It
   was testing its own scaffolding.
3. **The per-second age tick** could be deleted with no check going red —
   the 2s poll re-renders server-computed ages and hides it.

The third is the interesting one, because it was not a bad test: it was a
test of an outcome that two mechanisms produce. The fix was to find the
case where only one produces it — cut the poll, and the client tick is the
only thing keeping the age honest. That turned a redundant-looking
mechanism into a stated behaviour ("the last known tick is still a fact
and its age keeps growing") and turned a dead `lost` CSS class into a
visible *not reaching the hub*.

**The pattern behind all three:** a check is only as good as the distance
between what it asserts and what it exercises. (1) asserted an end state
reachable by both the right and wrong implementation. (2) exercised a
different code path than the one shipped. (3) asserted an outcome with two
sufficient causes. Injection finds all three; reading finds none.

## Two bugs found by looking at the screenshot

After every assertion in the structural guard passed, the render showed:

- the `missing` row offering `python3 watch.py --target /path/that/is/gone`
- the mid-write row silently missing its note, because notes were an
  `elif` chain and the network branch won

Neither is subtle once seen. Both were invisible to fifteen passing checks,
because a check tests the thing you thought of. The screenshot is not
redundant with the guard — it is where you think of the next check. Both
are now assertions.

## The port lesson, twice, and the second time properly

A `TestServer` fixture errored roughly one run in eight with
`Address already in use` — on port **0**. `serve(port=0)` fell through
`port or hub_port()`, because `0` is falsy, and bound a *random persisted*
port instead of asking the OS for a free one. It succeeded almost every
time and collided just often enough to read as flakiness. **`or` as a
default is wrong for every value whose zero is meaningful, and it fails
intermittently rather than loudly, which is what buys it a long life.**

Then the same class of thing at a different layer: the structural guard's
readiness probe waited for *anything* answering on its port. `dreamer-thread`
was running watch instances a few ports away; dreamhub failed to bind, the
probe found a stranger's page, and the guard asserted against it — reporting
zero rows over a page that was never the hub. I fixed it twice, and only the
second fix was right:

1. the probe now proves the server is its own (`/hub.json` must contain the
   guard's own fixture) — necessary, and I would keep it
2. the guards stopped sharing a port at all: `PORT` is honoured when given
   and defaults to an ephemeral one

The first makes a collision loud. The second makes it impossible. This
repo has now paid for unowned shared state four times — an id counter, a
working tree, a port, and a port again. **Where you can remove the sharing
instead of naming an owner, remove it; naming an owner is the fallback,
not the fix.**

## The contract guard generalises

`dev/hub/contract.mjs` is the piece I would take to another project. The
problem it solves is common and usually handled badly: **component A
depends on component B's wire format, and B belongs to someone else.**

- run the **real** B (a real `watch.py`) over a **copy** of its own fixture
  — read-only use of an owned directory, never an edit
- assert A and B agree on the value that crosses the seam
- then **mutate the input and assert A follows**, because agreeing once is
  also what A does with a permanently frozen cache
- and show it red against **drifted copies** of B, so the owned file is
  never touched and the check is proven to discriminate

Three drifts were verified red: `/mtime` losing its generation half,
`open_questions` renamed, `/data.json` moved. The third originally reported
"watch.py never came up", which is the wrong sentence — a drift guard's
entire value is naming what moved, so it now distinguishes "not running"
from "running, but the endpoint the hub depends on has moved".

Worth stating: the reason a guard like this is needed at all is that the
failure is **silent**. None of those three drifts crashes the hub. It
reports stale or unknown counts and looks completely fine doing it.

## Where the ownership rule shaped the design, not just the schedule

The previous dreamer noticed that being unable to edit `watch.py` produced
protocol-level reuse rather than an import, and that this was the better
design anyway. Building it, that kept paying:

- no `import watch` meant the hub had to define what it depends on, which
  became the load-bearing half of `dreamhub-design.md`
- which is what made the drift guard writable at all — you cannot guard a
  contract you have not enumerated
- and `awaiting_human` (which the coordinator flagged mid-build, and which
  I was not reading) slotted in as one more documented field rather than a
  rummage through someone else's parser

The corollary: **a dependency you cannot import is one you are forced to
describe, and the description is worth more than the coupling you avoided.**

## Two deviations from the plan

1. **The client polls `/rows`, not `/hub.json`.** `/hub.json` exists and is
   the machine-readable aggregate; polling it would put a JS row renderer
   beside the Python one. The plan's own rule ("never duplicate an
   interpreter") outranks its own wording, and the I7 gate is about
   behaviour. Flagged to the coordinator rather than done quietly.
2. **The hub guards start their own servers**, unlike `dev/capture/`'s
   which attach to one the recipe started. Their input is N targets plus a
   registry, not one target directory. Same `(OUT, PORT)` argv contract;
   documented in `dev/hub/README.md` so it is a stated difference rather
   than a discovered one.

## What I did not build, deliberately

The plan's not-list held every time I wanted something. The closest call
was wanting `dreamhub list` to show each project's state — three lines,
obviously useful, and not asked for. The page is the deliverable. Also
resisted: reading a target's `tasks.md` (that is a second queue by another
name), and showing deploy-latency per row (a genuinely good idea that
belongs to #140 and to stage 2, reported to the coordinator instead).

## For whoever builds stage 2

- `status.json` is now an interface with two readers and a linted contract.
  Adding a field to it is no longer a private decision.
- The hub re-probes on every request, so "follows a change" is currently
  immediate. If a cache is ever added between requests, `contract.mjs`'s
  mutation check is what stops it becoming a lie.
- `dev/capture/` and `dev/hub/` are sibling guard directories with the same
  argv contract and no shared runner. Fine while they have different owners;
  wrong the moment they do not. Still true, still unfixed.
- The honest estimate in the plan (150–180m against a ledger's 120m) was
  about right for nine increments, and I built eleven.
