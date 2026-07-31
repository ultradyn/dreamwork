/* probe — the only registry entry #630 P2 ships, and it mounts nothing.
 *
 * P2's job is to retire the transition's top-ranked risk: "React and morphdom
 * fight over DOM" (`component-transition.md` §6-R1, which names the cheapest
 * signal as "a scratch page with one component root inside `#view` under
 * forced ticks"). This is that component. It is not a surface, it converts
 * nothing, and no route reaches it — `client/dist/native.js` is not in PAGE.
 *
 * It delegates to `buildResearch` on purpose rather than to something
 * invented: `/research` is the surface P3 converts (`views.js:1318`), so the
 * delegation path P3 needs is the delegation path this proves. A probe that
 * exercised a made-up builder would prove the machinery and not the case.
 *
 * WHAT IT MAKES OBSERVABLE, and why each attribute is on the DOM rather than
 * inferred by the guard: a Playwright guard can only read what is rendered,
 * and "the component instance survived a tick" is otherwise indistinguishable
 * from "it was destroyed and an identical one was built". So:
 *
 *   data-dw-probe-instance  a value minted ONCE per component instance. Same
 *                           value before and after ⇒ React kept the instance
 *                           and its state. A remount mints a new one.
 *   data-dw-probe-seen      how many distinct `data` objects this instance
 *                           has been rendered with. Increments ⇒ the update
 *                           actually ARRIVED. A static value means the tick
 *                           reached the registry and stopped there.
 *
 * Both are needed and neither is sufficient: the instance alone passes on a
 * component that survives but never updates; the counter alone passes on a
 * component that is destroyed and rebuilt at every tick (its fresh instance
 * would show 1 forever, which reads as "not incrementing" only if you know
 * what to compare it to). Together they discriminate, which is the property
 * a red has to have to mean anything.
 */
import React from 'react';
import { fromBuilder } from './delegate.js';

/* `/research`'s listing, rendered by CALLING the builder the page serves.
 *
 * `buildResearch` is resolved at render time from the page's script scope —
 * it is a top-level `function` in `client/views.js`, which the page
 * concatenates into PAGE (`watch.py:691`). This bundle does not contain it
 * and must not: containing it would be the copy that `delegate.js` exists to
 * avoid, and `test_client_dist` asserts the builders' source is ABSENT from
 * native.js for exactly that reason. */
export const ResearchListing = fromBuilder('buildResearch', function (props) {
  return buildResearch(null, props.data || null);
});

export function Probe(props) {
  /* Minted once per instance, by a lazy initialiser React runs only on the
     first render of THIS instance. A plain module-level counter would be
     minted once per BUNDLE and would survive a remount — passing exactly
     where the check needs to fail. */
  const [instance] = React.useState(function () {
    return 'p' + Math.random().toString(36).slice(2, 10);
  });
  const [seen, setSeen] = React.useState(0);

  /* Keyed on `data` IDENTITY, which is the tick's own semantics: `setData`
     (`client/router.js:1044`) assigns a freshly parsed `/data.json` object
     every time, so identity moves on exactly the ticks that carried data. */
  React.useEffect(function () {
    setSeen(function (n) { return n + 1; });
  }, [props.data]);

  return React.createElement(
    'div',
    { 'data-dw-probe': 'research' },
    React.createElement('span', {
      'data-dw-probe-instance': instance,
      'data-dw-probe-seen': String(seen),
    }),
    React.createElement(ResearchListing, { data: props.data }));
}

/* The route name. Two underscores and a word that is not a path: `routeOf`
 * (`client/router.js:990`) can never produce it, so the probe cannot be
 * reached by navigation even once P3 wires the registry into the router. */
export const PROBE_ROUTE = '__probe';

export function registerProbe(registry) {
  return registry.register(PROBE_ROUTE, {
    component: Probe,
    doc: 'P2 coexistence probe — delegates to buildResearch. Not a surface.',
  });
}
