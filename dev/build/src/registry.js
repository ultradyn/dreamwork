/* registry — route → component, and the mount/unmount/update seam a router
 * will call. #630 P2.
 *
 * This is the SECOND registry the plan names (`component-transition.md` §2b,
 * §4-P2). The first is the string-builder dispatch in `buildCurrent`.
 * #751 P3 partitions them: `/research` resolves here, every other route still
 * resolves through its builder, and the router unmounts before crossing the
 * boundary.
 *
 * THE OWNERSHIP RULE, which is the whole coexistence story and the reason
 * this file has a `verify()`:
 *
 *   `#view` has exactly ONE owner at a time. Either the builders own it —
 *   `setContent` reconciles it through morphdom (`client/router.js:1656`) —
 *   or a component owns it, mounted here. Never both, and that is what
 *   "each route resolves in exactly one of the two registries" means once it
 *   is a running property rather than a table.
 *
 * The rule is not enforceable from inside this module: morphdom is driven by
 * the router, and a router that renders a builder string over a live root
 * will simply delete that root's DOM out from under React. Measured, not
 * assumed — `dev/capture/coexist.mjs` drives exactly that collision and
 * records what happens. So what this module supplies instead is DETECTION:
 * `verify()` answers whether every root it believes is mounted is still in
 * the document. A P3 router asserts that before it renders a builder string,
 * and a torn root becomes a named red instead of a blank region nobody can
 * explain.
 *
 * Stated in the brief's terms: for the WRAPPERS, divergence is impossible
 * (`delegate.js` — the markup has one statement). For the OWNERSHIP rule,
 * violation is detected, not impossible. Two different guarantees; conflating
 * them is how the weaker one gets reported as the stronger.
 */
import React from 'react';
import { createRoot } from 'react-dom/client';
import { flushSync } from 'react-dom';

/* The attribute that marks a component-owned container in the DOM. One
 * spelling, exported, because the guard and any future morphdom skip-hook
 * both need to recognise these nodes and a second spelling is a second
 * truth about what "component-owned" looks like.
 *
 * An ATTRIBUTE and not a class, on Max's own measured rule (`spike/components`
 * `9b54b4f0`, 2026-07-25): shared class names destroy the uniqueness that the
 * page's existing gesture code relies on when it addresses an element inside
 * a card by class. `delegate.js` carries the full finding. A morphdom
 * skip-hook in a later phase should match on this attribute for the same
 * reason — `[data-dw-mount]` cannot collide with anything the builders emit,
 * where a `.component` class could. */
export const OWNED_ATTR = 'data-dw-mount';

export function createRegistry() {
  /* route name → entry. An entry is `{ component, doc }`; `doc` is free-form
     and unused in P2, and it is here rather than added later because a
     registry whose entries can carry a per-component `.d.ts` and usage doc is
     the one P5 can build on without a second table beside it. */
  const entries = new Map();
  /* route name → { host, container, root, data } for the roots that are
     mounted RIGHT NOW. Separate from `entries` because registration is a
     build-time fact and mounting is a runtime one. */
  const live = new Map();

  function register(route, entry) {
    if (typeof route !== 'string' || !route) {
      throw new TypeError('registry.register needs a route name');
    }
    if (!entry || typeof entry.component !== 'function') {
      throw new TypeError(
        'registry.register(' + route + ') needs {component}: a component');
    }
    if (entries.has(route)) {
      /* Two components claiming one route is the authority-map failure in
         miniature, and it must be loud at registration rather than silently
         last-wins at mount. */
      throw new Error(
        'registry: ' + route + ' is already registered — a route has one ' +
        'authority, and two claims on it is the thing the authority map ' +
        'exists to refuse');
    }
    entries.set(route, entry);
    return entry;
  }

  function has(route) { return entries.has(route); }
  function get(route) { return entries.get(route) || null; }
  function routes() { return Array.from(entries.keys()).sort(); }
  function mounted() { return Array.from(live.keys()).sort(); }

  /* Mount `route`'s component into `host`, in a container this registry owns.
   *
   * A container of our own rather than rendering directly into `host`: React
   * takes over everything inside its root, and `#view` is not ours to take
   * over — `unmount` must be able to hand `host` back exactly as it was.
   * `dev/capture/coexist.mjs` asserts that round-trip byte-for-byte. */
  function mount(route, host, data, param) {
    const entry = entries.get(route);
    if (!entry) {
      throw new Error(
        'registry: nothing registered for ' + route + ' (registered: ' +
        routes().join(', ') + ')');
    }
    if (!host || typeof host.appendChild !== 'function') {
      throw new TypeError('registry.mount(' + route + ') needs a host element');
    }
    if (live.has(route)) {
      throw new Error(
        'registry: ' + route + ' is already mounted — mounting twice leaks ' +
        'the first root, and a leaked root keeps rendering into a detached ' +
        'tree where nothing can see it be wrong');
    }
    const container = host.ownerDocument.createElement('div');
    container.setAttribute(OWNED_ATTR, route);
    host.appendChild(container);
    const root = createRoot(container);
    const rec = {
      host: host, container: container, root: root, data: data, param: param,
    };
    live.set(route, rec);
    render(rec, entry, data);
    return rec;
  }

  /* Commit SYNCHRONOUSLY. Measured, and it is the finding that changed this
     module's shape: React 18's `root.render` schedules concurrently, so
     immediately after `mount()` the container is still EMPTY. The first run
     of `dev/capture/coexist.mjs` failed on exactly that.
   *
   * It matters because of what the router does next. `setContent`
   * (`client/router.js:1656`) commits and then MEASURES on the following
   * lines — `fitReview()` reads the review pane's height,
   * `positionQuestionColumn()` places by the question's midpoint,
   * `paintIndicators(true)` lands a zero-width indicator. A component mount
   * that had not committed yet would put every one of those measurements
   * against an empty box, and the symptom would be a layout that is subtly
   * wrong on the first frame and correct forever after — the hardest class
   * of bug to attribute.
   *
   * So the seam's contract is the same as the builders': when it returns,
   * the DOM is committed. `flushSync` is what makes a concurrent renderer
   * keep that promise. The cost is giving up batching on this path, which is
   * the right trade: the page renders on a ~2s tick, not on a keystroke. */
  function render(rec, entry, data) {
    flushSync(function () {
      rec.root.render(React.createElement(entry.component, {
        data: data,
        param: rec.param,
      }));
    });
  }

  /* Push new data into every mounted root.
   *
   * This is the TICK seam. `root.render` with new props re-renders in place
   * and PRESERVES component state — that is React's contract and it is what
   * makes "the data lands, the component's own state survives" true rather
   * than hoped. A P3 router calls this from `setData` (`router.js:1044`),
   * which is the one place `data` is replaced, so components and builders
   * read one data authority and there is no second fetch. */
  function update(data) {
    const touched = [];
    live.forEach(function (rec, route) {
      const entry = entries.get(route);
      rec.data = data;
      /* Synchronous for the same reason as the mount: the tick's painters
         (`ages()`, `paintIndicators`, `restoreCardState`…) run on the lines
         after the render and must not measure a box that has not updated. */
      render(rec, entry, data);
      touched.push(route);
    });
    return touched.sort();
  }

  /* Unmount `route` and put `host` back the way it was found.
   *
   * `root.unmount()` first, then remove the container: unmounting runs
   * cleanup effects while the DOM is still attached, which is what lets a
   * component release listeners it added outside its own subtree. Removing
   * first would run them against a detached tree. */
  function unmount(route) {
    const rec = live.get(route);
    if (!rec) return false;
    live.delete(route);
    rec.root.unmount();
    if (rec.container.parentNode) {
      rec.container.parentNode.removeChild(rec.container);
    }
    return true;
  }

  function unmountAll() { return mounted().map(unmount).length; }

  /* Is every root this registry believes is mounted still in its document?
   *
   * Returns `{ mounted: [...], detached: [...] }`. `detached` is the
   * ownership rule being violated: something removed a component-owned
   * container without telling the registry, and the overwhelmingly likely
   * something is a builder render reconciling `#view` (morphdom's
   * `childrenOnly` pass replaces the children it does not recognise).
   *
   * A reading, never a throw, for `client_dist.py`'s reason: the state this
   * exists to describe is the broken one, and a raise there reads like the
   * detector being broken and starts the diagnosis in the wrong subsystem. */
  function verify() {
    const out = { mounted: [], detached: [] };
    live.forEach(function (rec, route) {
      const doc = rec.container.ownerDocument;
      const attached = !!(doc && doc.contains(rec.container));
      (attached ? out.mounted : out.detached).push(route);
    });
    out.mounted.sort();
    out.detached.sort();
    return out;
  }

  return {
    register: register, has: has, get: get, routes: routes,
    mount: mount, update: update, unmount: unmount, unmountAll: unmountAll,
    mounted: mounted, verify: verify,
  };
}
