/* Native /question delegates card markup to the live qaCard builder rather
 * than wrapper-exports.js's design-tool ambient context. */
import React from 'react';
import { fromBuilder } from './delegate.js';

const h = React.createElement;
const div = (className, ...children) => h('div', { className }, ...children);
const FocusQaCard = fromBuilder('qaCard', props =>
  qaCard(props.q, props.k, 'focus'));
const focus = (q, k) => h('div', { id: 'qfocus', className: 'qdual' },
  h(FocusQaCard, { q, k }));

export function Question({ data, param: title }) {
  if (!data) return div('dim', '…');

  // One stationary title follows its entry from open o<n> to answered a<n>.
  for (const [name, prefix] of [
    ['questions_open', 'o'], ['answered_entries', 'a'],
  ]) {
    const entries = data[name] || [];
    const i = entries.findIndex(item => item.title === title);
    if (i >= 0) return focus(entries[i], prefix + i);
  }

  // Missing is neutral and never substitutes a nearby title.
  return h('div', { id: 'qfocus' },
    div('qmissing',
      div('qmisshead', 'not found'),
      div('qmissbody', 'renamed or removed'),
      div('qmissback',
        h('a', { href: '/questions' }, '← list'))));
}

export const registerQuestion = registry =>
  registry.register('question', { component: Question });
