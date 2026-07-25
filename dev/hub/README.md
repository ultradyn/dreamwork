# dreamhub guard

The structural half of dreamhub's verification. `test_dreamhub.py` asserts on
generated source; this asserts on what a real browser rendered. Both are
needed and neither substitutes for the other — a component can be correct in
source and wrong on screen, which is #117 and its sharper repeat.

## The contract

`node dev/hub/hub.mjs <OUT> <PORT>` — the same `(OUT, PORT)` argv contract
`dev/capture/` uses. One contract; a second doubles the confusion.

One difference, stated rather than left to be discovered: **this guard starts
its own server.** The hub's input is N targets plus a registry, not one target
directory, so gluing it into a shared serve-then-run recipe would be the
second contract worth avoiding. The justfile line that wires it in (#134) is
therefore one line with no plumbing:

```
node dev/hub/hub.mjs "$OUT/hub" 39897 || fail=1
```

## The fixture

`dev/hub/fixture/` holds five target shapes; a sixth (`gone`) is in the
registry and deliberately absent from disk. `prep.py` copies it and applies
`ages.json`, because a state that means "how long since the last tick" cannot
be frozen to a wall-clock timestamp — it would be `dreaming` today and a
permanent red light by the weekend. The guard also points one target at a stub
watch on an ephemeral port, so the page has one row that is genuinely UP:
without it, "the down row does not link to a dead port" is satisfied by a page
that never renders a link at all.

Nothing here writes into the repo. `prep.py` copies out; the guard's server
runs with `DREAMHUB_HOME` pointed at `OUT`.

## `contract.mjs` — the cross-file dependency

`node dev/hub/contract.mjs <OUT> <PORT> [<watch.py>]`

Stage 1 has exactly one cross-file dependency and it is a protocol, not an
import: the hub polls `/mtime` and re-reads `/data.json` on change. That is
what keeps the open-question count to one implementation. The cost is that
`watch.py` belongs to another dreamer, and if `/mtime` stops being
`"<gen> <mtime>"`, or `open_questions` is renamed, or `/data.json` moves, the
hub does not crash — it reports stale or unknown counts and looks fine doing
it. Nothing else in stage 1 would notice.

So this starts a real `watch.py` over a copy of `dev/capture/fixture`, points
a hub at it, and asserts the two agree — then edits the copy's `questions.md`
and asserts the hub *follows*, because agreeing once is also what a hub with
a frozen cache does.

The optional third argument runs a different `watch.py`. `watch.py` is not
edited here, so that is how the guard is shown to discriminate: point it at a
deliberately drifted copy. All three of these were verified red —

| Drift | What the guard says |
|---|---|
| `/mtime` loses its generation half | `/mtime is "<generation> <mtime>"` fails |
| `open_questions` renamed | the count mismatches, and the page check fails with it |
| `/data.json` moves | names the moved endpoint, not a startup timeout |

## Two things this guard learned the hard way

- **A readiness probe must prove the server is yours.** The first version
  waited for anything that answered on `PORT`. Another dreamer was running
  watch instances a few ports away; dreamhub failed to bind, the probe found a
  stranger's page, and the guard asserted against it — reporting zero rows
  over a page that was never the hub. It now checks `/hub.json` for its own
  fixture and dies loudly otherwise.
- **A guard must not crash on the first symptom.** `rows.find(...)` returning
  undefined threw on the first property access, so one rendering bug produced
  a TypeError and zero named checks. `row()` now returns a blank and records
  the absence, so a single run reports every failure it can see.

## Running it

```
node dev/hub/hub.mjs /tmp/hubguard 39897
```

Exits 0 or 1, prints `PASS`/`FAIL` per check, and leaves `hub.png` and
`hub-narrow.png` in `OUT` for a human to look at. Look at them: both of the
render bugs fixed in increment 5 were found by looking at the screenshot
after every assertion had passed.
