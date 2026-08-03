/* Native /question: one stationary title follows a question across the fold.
 *
 * Deliberately do not use wrapper-exports.js's QaCard here. Its `ambient`
 * helper is a bounded design-tool context; on the dashboard it would shadow
 * the live `data` and `view` bindings while qaCard formats the card. This
 * render-time delegate calls the one qaCard markup authority directly, in
 * the page's live lexical environment, and adds no fallback copy.
 */
import React from 'react';
import { fromBuilder } from './delegate.js';

const FocusQaCard = fromBuilder('qaCard', function (props) {
  return qaCard(props.q, props.k, 'focus');
});

export function Question(props) {
  const data = props.data;
  const title = props.param;
  if (!data) {
    return React.createElement('div', { className: 'dim' }, 'loading…');
  }

  if (title) {
    const oi = (data.questions_open || []).findIndex(function (item) {
      return item.title === title;
    });
    if (oi >= 0) {
      return React.createElement('div', { id: 'qfocus', className: 'qdual' },
        React.createElement(FocusQaCard, {
          q: data.questions_open[oi], k: 'o' + oi,
        }));
    }

    /* Follow the fold under a stationary URL: answering moves the entry into
     * answered_entries and changes its address from o<n> to a<n>; it does not
     * make the live question disappear. */
    const ai = (data.answered_entries || []).findIndex(function (item) {
      return item.title === title;
    });
    if (ai >= 0) {
      return React.createElement('div', { id: 'qfocus', className: 'qdual' },
        React.createElement(FocusQaCard, {
          q: data.answered_entries[ai], k: 'a' + ai,
        }));
    }
  }

  /* A missing title is neither a transport fault nor permission to guess at
   * a nearby question. Keep the established neutral notice and way back. */
  return React.createElement('div', { id: 'qfocus' },
    React.createElement('div', { className: 'qmissing' },
      React.createElement('div', { className: 'qmisshead' }, 'not found'),
      React.createElement('div', { className: 'qmissbody' },
        'this link names a question the list no longer has — it was most ',
        'likely re-titled or removed while you watched. No other question ',
        'has been substituted for it.'),
      React.createElement('div', { className: 'qmissback' },
        React.createElement('a', { href: '/questions' },
          '← back to questions'))));
}

export function registerQuestion(registry) {
  return registry.register('question', {
    component: Question,
    doc: 'Native /question; follows one title from open to answered.',
  });
}
