/* #890 — the sole full-page renderer for the /goals read surface. */
import React from 'react';
import { fromBuilder } from './delegate.js';

const Details = fromBuilder('mdB', function (props) {
  return mdB(props.text || '');
});

const stateChip = node => React.createElement(
  'span', { className: 'goalstate ' + node.state }, node.state);

function GoalPage(props) {
  const payload = props.data && props.data.goals;
  if (!payload || payload.health === 'missing') {
    return React.createElement('div', { className: 'goalpage-fault' },
      'goal tree unavailable: examined 0 nodes; no canonical goal store');
  }
  const examined = Number(payload.examined_count) || 0;
  const expected = Number(payload.expected_count) || 0;
  if (payload.health !== 'ok') {
    return React.createElement('div', null,
      React.createElement('div', { className: 'goalpage-count' },
        'examined ' + examined + ' of ' + expected + ' goal nodes'),
      React.createElement('div', { className: 'goalpage-fault' },
        payload.error || 'goal tree unavailable'));
  }
  if (expected === 0) {
    return React.createElement('div', null,
      React.createElement('div', { className: 'goalpage-count' },
        'examined 0 of 0 goal nodes'),
      React.createElement('div', { className: 'dim' },
        'no goals yet — the examined tree is genuinely empty'));
  }
  const nodes = payload.nodes || [];
  const byId = new Map(nodes.map(node => [node.id, node]));
  const current = byId.get(payload.current_goal_id) || null;
  const depthOf = node => {
    let depth = 0, parent = byId.get(node.parent_id), seen = new Set();
    while (parent && !seen.has(parent.id)) {
      seen.add(parent.id); depth += 1; parent = byId.get(parent.parent_id);
    }
    return depth;
  };
  const tree = React.createElement('div', { className: 'goaltree' },
    nodes.map(node => React.createElement('div', {
      className: 'goaltree-row', key: node.id,
      style: { paddingLeft: (depthOf(node) * 18) + 'px' },
    }, stateChip(node),
    React.createElement('span', { className: 'goaltree-title' }, node.title),
    React.createElement('span', { className: 'goalmeta' },
      node.total_count == null ? 'progress unavailable'
        : node.completed_count + '/' + node.total_count,
      node.blockers.length ? ' · ' + node.blockers.length + ' blocked' : ''))));
  const currentPanel = current ? React.createElement('section', {
    className: 'goalcurrent', 'data-goal-id': String(current.id),
  }, React.createElement('div', { className: 'goalcurrent-head' },
    stateChip(current), React.createElement('h2', null, current.title),
    React.createElement('span', { className: 'goalmeta' },
      current.total_count == null ? 'progress unavailable'
        : current.completed_count + '/' + current.total_count)),
  React.createElement(Details, { text: current.details }),
  React.createElement('h3', null, 'criteria'),
  current.criteria.length
    ? React.createElement('ul', { className: 'goalcriteria' },
        current.criteria.map((criterion, index) =>
          React.createElement('li', { key: index }, criterion)))
    : React.createElement('div', { className: 'dim' },
        'no criteria found under ## Done when'),
  React.createElement('h3', null, 'member tasks'),
  current.member_tasks.length
    ? current.member_tasks.map(task => React.createElement('div', {
        className: 'goaltask', key: task.id,
      }, React.createElement('span', { className: task.state },
        '#' + task.id + ' · ' + task.state), ' · ' + task.title))
    : React.createElement('div', { className: 'dim' },
        current.progress_error || 'no member tasks'),
  React.createElement('h3', null, 'blockers'),
  current.blockers.length
    ? current.blockers.map(blocker => React.createElement('div', {
        className: 'goalblocker', key: blocker.kind + ':' + blocker.id,
      }, blocker.kind + ' #' + blocker.id + ' · ' + blocker.title +
         ' — ' + blocker.reason))
    : React.createElement('div', { className: 'dim' }, 'none'),
  React.createElement('h3', null, 'last panel verdict'),
  current.verdicts.length
    ? current.verdicts.map(verdict => React.createElement('div', {
        className: 'goalverdict' + (verdict.refuted ? ' refuted' : ''),
        key: verdict.lens,
      }, React.createElement('div', null,
        verdict.lens + ' · ' + (verdict.refuted ? 'refuted' : 'passed')),
      (verdict.refuted ? verdict.findings : verdict.corroborated).map(
        (finding, index) => React.createElement('div', {
          className: 'goalmeta', key: index,
        }, finding))))
    : React.createElement('div', { className: 'dim' }, 'no panel verdict yet'))
    : React.createElement('div', { className: 'goalpage-fault' },
        'no current goal selected — the tree below remains readable');
  return React.createElement('div', null,
    React.createElement('div', { className: 'goalpage-count' },
      'examined ' + examined + ' of ' + expected + ' goal nodes'),
    currentPanel, React.createElement('h2', null, 'goal tree'), tree);
}

export function registerGoals(registry) {
  return registry.register('goals', {
    component: GoalPage,
    doc: 'Native /goals read surface; sole full-page renderer.',
  });
}
