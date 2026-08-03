/* #751 — the first native surface.
 *
 * The shell is React-owned. Artifact rows are not: /reviews and the dashboard
 * still consume artifactRow, so the component delegates each row through the
 * P2 wrapper. There is one row implementation and no fallback copy here.
 *
 * #1066 — Label is the shared native component defined in
 * wrapper-exports.js (the design-package authority, landed #1060). It calls
 * label() at render time — one markup statement, one React component,
 * consumed by both the runtime (here, via import) and the design package
 * (in-scope by construction). The fromBuilder('label') delegate that used to
 * live here is gone: authority moved, it was not copied.
 */
import React from 'react';
import { fromBuilder } from './delegate.js';
import { Label } from '../wrapper-exports.js';

const ArtifactRow = fromBuilder('artifactRow', function (props) {
  return artifactRow(props.row, 'research');
});

export function Research(props) {
  const [instance] = React.useState(function () {
    return 'r' + Math.random().toString(36).slice(2, 10);
  });
  const [seen, setSeen] = React.useState(0);
  React.useEffect(function () {
    setSeen(function (n) { return n + 1; });
  }, [props.data]);
  const name = props.param;
  const data = props.data;
  let content;
  if (name) {
    content = React.createElement(
      'div', { id: 'reviewwrap', className: 'nodock' },
      React.createElement(
        'div', { id: 'reviewdoc' },
        React.createElement('iframe', {
          id: 'reviewframe',
          src: '/researchraw?p=' + encodeURIComponent(name),
          title: 'research artifact',
          loading: 'lazy',
        })));
  } else if (!data) {
    content = React.createElement('div', { className: 'dim' }, 'loading…');
  } else {
    const children = [
      React.createElement(Label, { key: 'label', text: 'research' }),
    ];
    if (!data.research.length) {
      children.push(React.createElement(
        'div', { className: 'dim', key: 'empty' },
        'no built research artifacts yet — sources live in ',
        React.createElement('code', null, '.dreamwork/docs/research/src/'),
        ' and build through ',
        React.createElement('code', null, 'review_artifact.py'),
        ', the one template pipeline.'));
    } else {
      data.research.forEach(function (row) {
        children.push(React.createElement(ArtifactRow, {
          key: row.name,
          row: row,
        }));
      });
    }
    content = children;
  }
  return React.createElement('div', {
    'data-dw-research-instance': instance,
    'data-dw-research-seen': String(seen),
  }, content);
}

export function registerResearch(registry) {
  return registry.register('research', {
    component: Research,
    doc: 'Native /research shell; rows delegate to artifactRow.',
  });
}
