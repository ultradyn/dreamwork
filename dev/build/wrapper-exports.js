// The ONE hand-written input to `just build-client`.
//
// Everything else in the generated entry is `client/*.js`, concatenated in
// watch.py's own `_CLIENT_ASSETS` order — read out of watch.py by AST at build
// time, so the bundle's load order has one truth and cannot quietly diverge
// from the page's. The builders are CONSUMED here, never copied: this file is
// appended into the same lexical scope, so it can name `qaCard`, `agePair`,
// `label` &c. directly.
//
// #653 (P1 of the #630 transition) exports NOTHING on purpose. The build step
// lands before anything it could export exists — the wrappers are P5's work
// (#630 plan §2a). When they arrive, each is a CALL into a builder above:
//
//     export const QaCard = ({ q, k, ctx }) =>
//       ambient(ctx, () => html(qaCard(q, k)));
//
// and never a second statement of the markup. That is enforced rather than
// remembered: `test_client_dist.py` refuses any HTML tag literal in this file,
// and proves its own detector by first finding tag literals in
// client/components.js — so it cannot pass by being broken.
export {};
