/* #890 — the sole full-page renderer for the /goals read surface. */
import React from 'react';
import { fromBuilder } from './delegate.js';

const Details = fromBuilder('mdB', function (props) {
  return mdB(props.text || '');
});

const stateChip = node => React.createElement(
  'span', { className: 'goalstate ' + (node.state_error ? 'unreadable' : node.state) },
  node.state_error ? 'unreadable' : node.state);

const goalOptions = (nodes, includeRoot) => [
  ...(includeRoot ? [React.createElement('option', { value: '', key: 'root' },
    'tree root')] : []),
  ...nodes.map(node => React.createElement('option', {
    value: String(node.id), key: node.id,
  }, node.title)),
];

function GoalWrites(props) {
  const nodes = props.nodes;
  const first = String(props.currentId || (nodes[0] && nodes[0].id) || '');
  const [detailsGoal, setDetailsGoal] = React.useState(first);
  const [details, setDetails] = React.useState(function () {
    const node = nodes.find(item => String(item.id) === first);
    return node ? node.details : '';
  });
  const [conditionGoal, setConditionGoal] = React.useState(first);
  const [currentGoal, setCurrentGoal] = React.useState(first);
  const [condition, setCondition] = React.useState('');
  const [title, setTitle] = React.useState('');
  const [newDetails, setNewDetails] = React.useState('');
  const [parent, setParent] = React.useState(first);
  const [rank, setRank] = React.useState('');
  const [message, setMessage] = React.useState('');
  const [busy, setBusy] = React.useState(false);

  React.useEffect(function () {
    const valid = id => nodes.some(node => String(node.id) === id);
    const next = String(props.currentId || (nodes[0] && nodes[0].id) || '');
    if (!valid(detailsGoal) && next) {
      const node = nodes.find(item => String(item.id) === next);
      setDetailsGoal(next); setDetails(node ? node.details : '');
    }
    if (!valid(conditionGoal) && next) setConditionGoal(next);
    if (!valid(currentGoal) && next) setCurrentGoal(next);
    if (parent !== '' && !valid(parent)) setParent(next);
  }, [nodes, props.currentId]);

  async function write(payload, clear) {
    setBusy(true); setMessage('saving…');
    try {
      const response = await fetch('/goals', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const verdict = await writeVerdict(response);
      if (!verdict.landed) {
        setMessage('write refused — ' + (verdict.detail || verdict.reason ||
          'the store did not accept it'));
      } else {
        clear();
        setMessage('saved quietly · appears on the next tick');
      }
    } catch (error) {
      setMessage('write failed — the page could not reach the store');
    }
    setBusy(false);
  }

  const selectDetailsGoal = event => {
    const id = event.target.value;
    const node = nodes.find(item => String(item.id) === id);
    setDetailsGoal(id); setDetails(node ? node.details : '');
  };
  const selector = (value, change, includeRoot) => React.createElement(
    'select', { value: value, onChange: change, disabled: busy },
    goalOptions(nodes, includeRoot));
  return React.createElement('section', { className: 'goalwrites' },
    React.createElement('h2', null, 'write the tree'),
    React.createElement('p', { className: 'goalmeta' },
      'These writes are quiet: the loop reads their receipts on its next tick.'),
    nodes.length ? React.createElement('form', { className: 'goalwrite', onSubmit: event => {
      event.preventDefault();
      write({ action: 'set-current', goal_id: Number(currentGoal) }, function () {});
    } }, React.createElement('h3', null, 'current goal'),
    selector(currentGoal, event => setCurrentGoal(event.target.value), false),
    React.createElement('button', { type: 'submit', disabled: busy },
      'make current')) : null,
    nodes.length ? React.createElement('form', { className: 'goalwrite', onSubmit: event => {
      event.preventDefault();
      write({ action: 'edit-details', goal_id: Number(detailsGoal), details },
        function () {});
    } }, React.createElement('h3', null, 'edit details'),
    selector(detailsGoal, selectDetailsGoal, false),
    React.createElement('textarea', { value: details, disabled: busy,
      onChange: event => setDetails(event.target.value),
      'aria-label': 'goal details' }),
    React.createElement('button', { type: 'submit', disabled: busy },
      'save details')) : null,
    nodes.length ? React.createElement('form', { className: 'goalwrite', onSubmit: event => {
      event.preventDefault();
      write({ action: 'add-condition', goal_id: Number(conditionGoal),
        condition }, () => setCondition(''));
    } }, React.createElement('h3', null, 'add a condition'),
    selector(conditionGoal, event => setConditionGoal(event.target.value), false),
    React.createElement('input', { value: condition, disabled: busy,
      onChange: event => setCondition(event.target.value), required: true,
      placeholder: 'Done when…', 'aria-label': 'new goal condition' }),
    React.createElement('button', { type: 'submit', disabled: busy },
      'add condition')) : null,
    React.createElement('form', { className: 'goalwrite', onSubmit: event => {
      event.preventDefault();
      write({ action: 'add-goal', title, details: newDetails,
        parent_id: parent === '' ? null : Number(parent),
        rank: rank === '' ? null : Number(rank) }, function () {
          setTitle(''); setNewDetails(''); setRank('');
        });
    } }, React.createElement('h3', null, 'add a goal'),
    React.createElement('input', { value: title, disabled: busy, required: true,
      onChange: event => setTitle(event.target.value), placeholder: 'Goal title',
      'aria-label': 'new goal title' }),
    selector(parent, event => setParent(event.target.value), true),
    React.createElement('input', { value: rank, disabled: busy, type: 'number',
      onChange: event => setRank(event.target.value), placeholder: 'Sibling rank',
      'aria-label': 'sibling rank' }),
    React.createElement('textarea', { value: newDetails, disabled: busy,
      onChange: event => setNewDetails(event.target.value),
      placeholder: 'Details (Markdown)', 'aria-label': 'new goal details' }),
    React.createElement('button', { type: 'submit', disabled: busy },
      'add goal')),
    React.createElement('div', { className: 'goalwrite-status',
      'aria-live': 'polite' }, message));
}

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
        'no goals yet — the examined tree is genuinely empty'),
      React.createElement(GoalWrites, { nodes: [], currentId: null }));
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
      node.state_error ? 'unreadable — ' + node.state_error
      : node.total_count == null ? 'progress unavailable'
      : node.completed_count + '/' + node.total_count,
      node.state_error ? ''
      : node.blockers.length ? ' · ' + node.blockers.length + ' blocked' : ''))));
  const currentPanel = current ? React.createElement('section', {
    className: 'goalcurrent', 'data-goal-id': String(current.id),
  }, React.createElement('div', { className: 'goalmeta' }, 'current goal'),
  React.createElement('div', { className: 'goalcurrent-head' },
    stateChip(current), React.createElement('h2', null, current.title),
    React.createElement('span', { className: 'goalmeta' },
      current.state_error ? 'unreadable'
      : (current.total_count == null ? 'progress unavailable'
        : current.completed_count + '/' + current.total_count))),
  current.state_error
    ? React.createElement('div', { className: 'goalpage-fault' },
        'this goal could not be read — ' + current.state_error +
        '. The tree below remains readable.')
    : null,
  current.state_error ? null : React.createElement(Details, { text: current.details }),
  current.state_error ? null : React.createElement('h3', null, 'criteria'),
  current.state_error ? null : (current.criteria.length
    ? React.createElement('ul', { className: 'goalcriteria' },
        current.criteria.map((criterion, index) =>
          React.createElement('li', { key: index }, criterion)))
    : React.createElement('div', { className: 'dim' },
        'no criteria found under ## Done when')),
  current.state_error ? null : React.createElement('h3', null, 'member tasks'),
  current.state_error ? null : (current.member_tasks.length
    ? current.member_tasks.map(task => React.createElement('div', {
        className: 'goaltask', key: task.id,
      }, React.createElement('span', { className: task.state },
        '#' + task.id + ' · ' + task.state), ' · ' + task.title))
    : React.createElement('div', { className: 'dim' },
        current.progress_error || 'no member tasks')),
  current.state_error ? null : React.createElement('h3', null, 'blockers'),
  current.state_error ? null : (current.blockers.length
    ? current.blockers.map(blocker => React.createElement('div', {
        className: 'goalblocker', key: blocker.kind + ':' + blocker.id,
      }, blocker.kind + ' #' + blocker.id + ' · ' + blocker.title +
         ' — ' + blocker.reason))
    : React.createElement('div', { className: 'dim' }, 'none')),
  current.state_error ? null : React.createElement('h3', null, 'last panel verdict'),
  current.state_error ? null : (current.verdicts.length
    ? current.verdicts.map(verdict => React.createElement('div', {
        className: 'goalverdict' + (verdict.refuted ? ' refuted' : ''),
        key: verdict.lens,
      }, React.createElement('div', null,
        verdict.lens + ' · ' + (verdict.refuted ? 'refuted' : 'passed')),
      (verdict.refuted ? verdict.findings : verdict.corroborated).map(
        (finding, index) => React.createElement('div', {
          className: 'goalmeta', key: index,
        }, finding))))
    : React.createElement('div', { className: 'dim' }, 'no panel verdict yet')))
    : React.createElement('div', { className: 'goalpage-fault' },
        'no current goal selected — the tree below remains readable');
  return React.createElement('div', null,
    React.createElement('div', { className: 'goalpage-count' },
      'examined ' + examined + ' of ' + expected + ' goal nodes'),
    currentPanel, React.createElement(GoalWrites, {
      nodes: nodes, currentId: payload.current_goal_id,
    }), React.createElement('h2', null, 'goal tree'), tree);
}

export function registerGoals(registry) {
  return registry.register('goals', {
    component: GoalPage,
    doc: 'Native /goals read surface; sole full-page renderer.',
  });
}
