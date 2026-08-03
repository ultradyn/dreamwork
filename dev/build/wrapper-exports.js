// The ONE hand-written input to `just build-client`.
//
// Everything else in the generated entry is `client/*.js`, concatenated in
// watch.py's own `_CLIENT_ASSETS` order — read out of watch.py by AST at build
// time, so the bundle's load order has one truth and cannot quietly diverge
// from the page's. The builders are CONSUMED here, never copied: this file is
// appended into the same lexical scope, so it can name `qaCard`, `agePair`,
// `label` &c. directly.
//
// Each export is a CALL into the builder above, never a second statement of
// the markup. That is enforced rather than
// remembered: `test_client_dist.py` refuses any HTML tag literal in this file,
// and proves its own detector by first finding tag literals in
// client/components.js — so it cannot pass by being broken.
import React from 'react';

const HOST = 'div';

/* QaCard's builder reads the page's mutable `data` and `view` bindings while
 * formatting links. Give a design-tool preview a bounded temporary context,
 * then restore the surrounding bundle even when the builder throws. `rmr`
 * and `submitCard` exist in the concatenated client sources too, but qaCard
 * does not read either while rendering; its onclick string merely names the
 * latter for a real dashboard to resolve after mount. */
const ambient = (ctx, render) => {
  const previousData = data;
  const previousView = view;
  try {
    data = (ctx && ctx.data) || {};
    view = (ctx && ctx.view) || { name: null, param: null, q: null };
    return render();
  } finally {
    data = previousData;
    view = previousView;
  }
};

export const QaCard = ({ q, k, ctx = {} }) => React.createElement(HOST, {
  'data-dw-delegate': 'qaCard',
  dangerouslySetInnerHTML: { __html: ambient(ctx, () => qaCard(q, k)) },
});

QaCard.displayName = 'QaCard';
QaCard.dwBuilder = 'qaCard';

export const Label = ({ text }) => React.createElement(HOST, {
  'data-dw-delegate': 'label',
  dangerouslySetInnerHTML: { __html: label(text) },
});

Label.displayName = 'Label';
Label.dwBuilder = 'label';

export const PipBtn = ({ url, label }) => React.createElement(HOST, {
  'data-dw-delegate': 'pipBtn',
  dangerouslySetInnerHTML: { __html: pipBtn(url, label) },
});

PipBtn.displayName = 'PipBtn';
PipBtn.dwBuilder = 'pipBtn';

export const Expand = ({ s, inner, cls = '', keep = '' }) =>
  React.createElement(HOST, {
    'data-dw-delegate': 'expand',
    dangerouslySetInnerHTML: { __html: expand(s, inner, cls, keep) },
  });

Expand.displayName = 'Expand';
Expand.dwBuilder = 'expand';

export const FollowThread = ({ follows, fold, ctx = {} }) =>
  React.createElement(HOST, {
    'data-dw-delegate': 'followThread',
    dangerouslySetInnerHTML: { __html: ambient(ctx, () => followThread(follows, fold)) },
  });

FollowThread.displayName = 'FollowThread';
FollowThread.dwBuilder = 'followThread';

export const QaCompose = ({ key, st, title }) => React.createElement(HOST, {
  'data-dw-delegate': 'qaCompose',
  dangerouslySetInnerHTML: { __html: qaCompose(key, st, title) },
});

QaCompose.displayName = 'QaCompose';
QaCompose.dwBuilder = 'qaCompose';

export const ArtifactRow = ({ r, kind }) => React.createElement(HOST, {
  'data-dw-delegate': 'artifactRow',
  dangerouslySetInnerHTML: { __html: artifactRow(r, kind) },
});

ArtifactRow.displayName = 'ArtifactRow';
ArtifactRow.dwBuilder = 'artifactRow';
