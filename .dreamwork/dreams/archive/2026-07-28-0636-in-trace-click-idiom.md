# In-trace click, and elementFromPoint as the pointer-events proxy

**dreamer-gesture, #386 (gitrow 0px-open). 2026-07-28 06:36.**

#386 was filed as "the click does not land under load," with the hypothesis that
the row's arrival transition was still in flight. It was not. The close gesture —
on a row fully settled through several roundtrips — failed the same 0px way, which
a settling row cannot. The cause was a test-harness timing race, and the shape of
it is worth keeping because it is the second time this repo has paid for a guard
that decouples its click from its trace.

## the race, stated once

`gesture()` did:

```
const t = p.evaluate(TRACE(ms));   // trace window starts here, runs `ms`
await sleep(60);
await p.click(selector);            // a SEPARATE Playwright roundtrip
return await t;
```

The trace window is bounded to **its own start**. The click is a separate
roundtrip whose latency (transport + Playwright's actionability checks) is
load-dependent and unbounded. Under load the click lands at t=1300ms or
t=1600ms, and the trace — which closes at its own t=1500ms — captures a partial
animation (height 22→64, 0 part-way) or nothing at all (0px, the row shut
*after* the window). Same cause, two faces, depending on how late the click was.

`dreamfade.mjs` already has the idiom that fixes this: the action runs **inside**
the trace evaluate, at t≈0, so there is no second roundtrip whose latency can
move. The reason gitrow didn't use it is that gitrow's click carries the #141
pointer-events contract — a synthetic `element.click()` sails through
`pointer-events:none` — and you cannot do a real Playwright pointer click from
inside a `page.evaluate`.

## elementFromPoint is the proxy that closes that gap

`document.elementFromPoint(cx, cy)` is the browser's own hit-test: it skips
`pointer-events:none` elements and returns whatever overlay sits on top. So
inside the trace, you hit-test the summary's centre, and only if the hit IS the
summary (or inside it) do you dispatch the synthetic click. A summary he cannot
press returns its interceptor; you record `landed: false` and the open reads 0px
**by name** ("the click reached the summary") rather than by luck.

This is the transferable piece: **any guard that needs a real-pointer property
(hit-testing, pointer-events) but wants the in-trace-click idiom can use
elementFromPoint as the proxy.** The contract is preserved because elementFromPoint
IS the hit-test a real pointer would do; the synthetic click is justified by the
hit-test having already proved the target is pressable.

## what this does NOT generalise to

elementFromPoint models **hit-testing**, not the full actionability Playwright
does (visibility, stability, enabled). For a gesture on a settled element that is
fine. For a gesture on something that might be transiently unstable, the
synthetic click fires where a real pointer would have waited — so the guard would
need its own stability gate if that matters. gitrow's row is always settled when
the gesture runs, so it does not.

## the load asymmetry, restated for this guard

The brief's load-asymmetry rule held exactly: a dropped intermediate frame makes
false **reds**, never false greens. After the fix, every run — even the failures —
showed `click {"landed":true}`. At load 100+ the residual reds were frame
starvation (the box drew 2 frames of a real 176px travel; `between()` correctly
read 0 part-way) and server starvation (`ECONNREFUSED` — the guard's own watch.py
dying). Both are re-run reds, neither is #386. A green under that load was
conclusive; the reds were not the gesture.

## the brief was wrong about the cause, and that is the finding

The brief's candidate — arrival transition in flight — was the natural guess and
it was refuted by one fact (the close gesture failed too, on a settled row). The
brief invited that refutation explicitly ("if it turns out the travel is real and
the sampling is still wrong, say so loudly"). The louder version: **the click and
the trace were decoupled, and under load the decoupling ate the window.** Same
family as #191 ("a guard's window can be the bug") and prominence's
armed-on-the-click measuring its own input latency — the instrument's timing
relative to the gesture, not the gesture itself.
