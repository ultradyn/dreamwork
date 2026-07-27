# The hollow-check pattern recurs in the diagnosis, not just the check

## The direct finding (one line)

`dev/capture/plugcmd.mjs` §4 read `document.querySelector('.cmdmsg')`, which
resolves to `#fmsg` (the file-message node, `watch.py:1562` — it shares the
`cmdmsg` class and sits first in the DOM) rather than `#cmdmsg` (the command-
confirmation node, `watch.py:1587`, that `confirmationFor` writes). `#fmsg` is
always empty after a command submit, so the check returned `""` over a working
product and stayed deterministically red. Fixed; red-proved; commit `a6d66b0`.

## The thing I want to remember

The brief that asked for this fix is a carefully-written diagnosis document.
It lays out four "measured facts, by the coordinator, on a hand-built fixture
server," builds a hypothesis ("the guard samples at a fixed 900ms, and on the
plugin path the round-trip has not completed by then. It is a race, not a
400"), and a chain of reasoning that follows from fact #1: `said` comes back
empty; the confirmation holds for ~5s once set; therefore the empty string
means `show()` had not been called yet; therefore the response had not been
handled. Each step is correct **conditional on the empty string being the
value of the element the product writes to**.

It wasn't. The empty string was the value of a *different element* that
happens to share a class with the right one. The product was never slow. The
POST was never in flight at 900ms. `show()` had been called and had finished
long before the guard looked. The entire race narrative — the timing
measurements the brief asked me to take first, the plugin-resolution suspect,
the "either way the instrument is wrong" framing — was built on a symptom
whose instrument was reading the wrong node.

What interested me is that this is **the same pattern** the repo's own
verification rules are there to catch in checks:

> a green red-run is a finding, never a relief... when a test patches, fakes
> or hand-builds anything, name the production line that would have to change
> for it to fail, then change that line and watch. If you cannot name one,
> there isn't one.

The check-level rule is: don't trust a pass until you've shown the check can
see a failure. The diagnosis-level analogue — which I think this brief
demonstrates without naming it — is: **don't trust a symptom until you've
shown the instrument that produced it is looking at the thing you think it's
looking at.** The coordinator measured `""` carefully, three times, on a
hand-built fixture. The measurement was real and reproducible. The
interpretation was built on the assumption that `.cmdmsg` and "the element
the composer writes its confirmation to" were the same node. They weren't,
and no amount of repeated measurement would have surfaced that — only
reading the DOM and asking *which* node the selector resolves to.

The clue that was available all along was in the brief's own fact #1:

> `said` comes back as `""` — empty. **Not** `rejected (400)`. So the guard's
> own headline ("a menu entry that 400s") is describing something that is not
> happening.

That's a sharp observation. It says: the failure mode the check was *named
for* isn't the failure mode it's seeing. The brief took that as evidence for
the race hypothesis (the third state: not-accepted, not-rejected, but
not-yet-arrived). It is equally, and as it turns out actually, evidence that
the check is reading the wrong place — a check reading the wrong element also
returns a value that matches neither the accepted nor the rejected branch,
because it is observing neither. "Not the named failure mode" should
fan out to both "a different product failure mode" *and* "the instrument is
looking at the wrong thing", and the second branch is the one this repo's own
history should bias toward, because it is the one that has bitten repeatedly.

## The practical takeaway, for me

When a guard fails with a value that matches none of the named outcomes of
the check — not the accepted text, not the rejected text, but empty or
unexpected — the first question is not "what is the product doing slowly or
wrongly", it is "which node does my selector resolve to, and is it the node
the product actually writes". `querySelector('.foo')` and `getElementById
('foo')` differ exactly when more than one element carries the class, and
the composer's chrome reuses `cmdmsg` as a class across two role-distinct
nodes (`#fmsg` the file message, `#cmdmsg` the command message). A class that
names a *role* and a class that names a *component* will collide like this
whenever a page has two instances of the component. Reach for `#id` (or the
page's autoglobal) when the check is about one specific instance; reach for
the class only when the check is deliberately about the set.

## What I am not claiming

The brief's diagnosis framework was good — it named its facts, separated
measurement from inference, and told me to measure first because "this is the
question that decides everything below". That discipline is exactly why the
real cause took one probe to find rather than an hour: I went to measure the
core-vs-plugin timing, read the right element to do it, and the message was
already there. The framework worked. The one thing it didn't have a guard
for was the instrument behind its own fact #1.
