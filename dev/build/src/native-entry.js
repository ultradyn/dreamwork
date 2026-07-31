/* native-entry — what `client/dist/native.js` is, and what it deliberately
 * is not. #630 P2.
 *
 * IT MOUNTS NOTHING, and that is a property of this file rather than a
 * promise about it: the only top-level statements here construct and fill a
 * registry. There is no `document` access, no
 * listener, no timer, and nothing that runs against a page. Loading this
 * bundle on the dashboard would be inert.
 *
 * That is worth contrasting with the OTHER bundle the build emits. `ds/`
 * (P1, #653) is the design-tool package and it CONCATENATES `client/*.js`,
 * so it carries their 40 top-level side effects — `setInterval(ages, 1e3)`,
 * `document.addEventListener`, `window.dreambg = …` — which is inert in a
 * design tool and would be a disaster on the dashboard, where those effects
 * are already running from the page's own copy. So `native.js` does NOT
 * concatenate the builders. It REFERENCES them, by bare name, resolved at
 * render time from the page's script scope (`delegate.js` explains how, and
 * `test_client_dist` asserts the builders' source text is absent from this
 * bundle — "consumed, never copied" as a checked property of the artifact,
 * not a description of the intent).
 *
 * The two bundles therefore differ in kind and not only in contents:
 *   ds/index.js   builders INSIDE, for a tool that has no page.
 *   native.js     builders OUTSIDE, for the page that already has them.
 *
 * Exports land on `window.dwNative` (esbuild `--global-name`). The router
 * consults `dwNative.registry`; nothing else should reach for it.
 */
import React from 'react';
import * as ReactDOM from 'react-dom/client';
import { createRegistry } from './registry.js';
import { registerProbe, PROBE_ROUTE } from './probe.js';
import { registerResearch } from './research.js';
import { OWNED_ATTR } from './registry.js';

export const registry = createRegistry();
registerProbe(registry);
registerResearch(registry);

/* Re-exported so a guard (and P3) can assert WHICH React is running without
 * a second copy arriving from anywhere else. Two Reacts on one page is the
 * classic duplicate-runtime bug, and the check for it is "is there exactly
 * one, and is it this one". */
export { React, ReactDOM, PROBE_ROUTE, OWNED_ATTR };
export const version = React.version;
