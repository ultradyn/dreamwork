/* delegate — a React component whose render CALLS a builder.
 *
 * #630 P2. This is the one file in the native runtime that touches markup,
 * and the whole point of it is that it does NOT contain any: a delegating
 * wrapper holds a *call*, never a copy. There is exactly one statement of the
 * markup in the repo — the builder in `client/*.js` that `watch.py` already
 * serves — so at the markup level there is nothing to diverge FROM.
 *
 * The property is worth stating precisely, because "derived" is easy to claim
 * and easy to lose:
 *
 *   - Divergence is IMPOSSIBLE, not merely detected. Not because a check
 *     compares two renderings, but because the second rendering does not
 *     exist. `Delegate` has no markup of its own and no fallback markup. If
 *     the builder is missing it renders an ERROR naming the builder; it
 *     cannot render an out-of-date twin, because there is no twin to render.
 *   - STALENESS is the residual channel and it is only DETECTED — a bundle
 *     compiled from yesterday's builders is a real state, and `client_dist`'s
 *     sha256 manifest plus `lint.py`'s ERROR are what make it impossible to
 *     miss (#653). That distinction is the honest one and it is the plan's
 *     (`component-transition.md` §2b); do not collapse it into "cannot
 *     diverge" when reporting.
 *
 * Why no JSX, deliberately: `React.createElement('div', …)` states an element
 * NAME, never a tag literal, so the wrapper-purity check (`test_client_dist`)
 * can forbid `<div…` across this whole directory without also forbidding the
 * runtime from creating elements at all. A JSX build would put `<div>` back
 * into the source text and make that check pick between "markup" and
 * "markup-shaped syntax that compiles to a call" — a distinction a regex
 * cannot draw and a reviewer would have to draw by hand every time.
 */
import React from 'react';

/* The host element a delegated builder's string is committed into.
 *
 * `div` rather than the builder's own outermost tag, and that is not
 * cosmetic: choosing per-builder would mean this file knowing what each
 * builder emits — a second description of exactly the thing it exists not to
 * describe. The extra div is inert (the builders' CSS is class-driven,
 * `client/style.css`), and P3 mounts into `#view` where a wrapper div is what
 * `setContent` writes into anyway.
 *
 * IT CARRIES NO CLASS, AND THAT IS THE DELIBERATE PART. Max spiked a
 * component vocabulary himself on 2026-07-25 (`spike/components`, findings
 * `9b54b4f0`, `.dreamwork/docs/spikes/2026-07-25-component-unification.md`)
 * and the load-bearing finding was about class names, not about behaviour:
 *
 *     "a card's behavioural hooks (`.anshero`, `data-qkey`) are private
 *      addresses that must never be a shared vocabulary class — that rule is
 *      the durable lesson here regardless of what is adopted."
 *
 * The mechanism he measured: `sendAnswer` addresses its FLIP hero with
 * `card.querySelector('.anstext')`. That is an ADDRESS, not a style hook, and
 * it is correct only while the class is unique inside the card. A shared
 * class is by definition not unique, so the moment a vocabulary class lands
 * in a card the address becomes a first-match guess — and it breaks SILENTLY,
 * the first time a card happens to contain two of them.
 *
 * A delegating wrapper is immune to this where his markup vocabulary was not,
 * and the immunity is worth naming because it is an argument for this plan's
 * shape that the plan does not make: the wrapper does not rewrite the
 * builder's markup, it renders the builder's own string verbatim. No class is
 * added, renamed, or shared, so every existing behavioural address keeps
 * exactly the uniqueness it has today. The runtime's own identity therefore
 * lives in `data-*` attributes — never in `className` — so that this stays
 * true when a later phase is tempted to "just add a class for styling".
 * `dev/capture/coexist.mjs` asserts it against the live DOM. */
const HOST = 'div';

/* Build a component from a builder call.
 *
 * `name` is the builder's identifier, used in errors and carried on the
 * component as `dwBuilder` so the registry (and P5's `.d.ts` emitter) can ask
 * a component what it delegates to without a second table.
 *
 * `call` receives the component's props and must return the builder's string.
 * It is written as a thunk rather than taking the builder function directly
 * because the builders are top-level `const`/`function` in the PAGE's script
 * scope, not module exports: a later classic script resolves `qaCard` through
 * the global lexical environment, so the reference must be evaluated at
 * RENDER time in the page, not at bundle time here. (Measured, not assumed —
 * `dev/capture/coexist.mjs` asserts the builders are reachable by bare name
 * from an injected script before it grades anything else.)
 */
export function fromBuilder(name, call) {
  function Delegate(props) {
    let markup;
    try {
      markup = call(props);
    } catch (err) {
      /* The builder threw. Say which builder and say the original message:
         a wrapper that swallowed this would render blank and send whoever
         debugs it into React rather than into the builder. */
      throw new Error(
        'delegate ' + name + ': the builder threw — ' + (err && err.message));
    }
    if (typeof markup !== 'string') {
      /* The reachability failure, named. Most likely cause by far: this
         bundle was loaded on a page that does not carry client/*.js, so the
         bare identifier resolved to nothing. There is deliberately NO
         fallback markup here — a fallback is a second statement, which is
         the one thing this file may not contain. */
      throw new Error(
        'delegate ' + name + ': the builder returned ' + typeof markup +
        ', not markup. This wrapper has no markup of its own to render ' +
        'instead — it is a call into ' + name + ', and ' + name + ' is not ' +
        'reachable from this page.');
    }
    return React.createElement(HOST, {
      'data-dw-delegate': name,
      dangerouslySetInnerHTML: { __html: markup },
    });
  }
  Delegate.displayName = 'Delegate(' + name + ')';
  /* What this component delegates to, readable from the component itself.
     P5 hangs the per-component `.d.ts` and usage doc off the registry entry;
     this is the field that lets either be generated from the builder rather
     than written beside it. */
  Delegate.dwBuilder = name;
  return Delegate;
}
