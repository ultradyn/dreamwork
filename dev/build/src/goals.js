/* #890 — the sole full-page renderer for the /goals read surface. */
import React from 'react';
import { fromBuilder } from './delegate.js';

const Details = fromBuilder('mdB', function (props) {
  return mdB(props.text || '');
});

const stateChip = node => React.createElement(
  'span', { className: 'goalstate ' + (node.state_error ? 'unreadable' : node.state) },
  node.state_error ? 'unreadable' : node.state);

const goalDepth = (node, byId) => {
  let depth = 0, parent = byId.get(node.parent_id), seen = new Set();
  while (parent && !seen.has(parent.id)) {
    seen.add(parent.id); depth += 1; parent = byId.get(parent.parent_id);
  }
  return depth;
};

const goalOptions = (nodes, includeRoot) => {
  const byId = new Map(nodes.map(node => [node.id, node]));
  return [
    ...(includeRoot ? [React.createElement('option', { value: '', key: 'root' },
      'Tree root')] : []),
    ...nodes.map(node => React.createElement('option', {
      value: String(node.id), key: node.id,
    }, '↳ '.repeat(goalDepth(node, byId)) + node.title)),
  ];
};

const fieldError = (id, text) => text ? React.createElement('div', {
  className: 'goalfield-error', id: id, role: 'alert',
}, text) : null;

const goalField = (label, id, control, error, hint) => React.createElement(
  'div', { className: 'goalfield' },
  React.createElement('label', { htmlFor: id }, label),
  control,
  hint ? React.createElement('div', {
    className: 'goalfield-hint', id: id + '-hint',
  }, hint) : null,
  fieldError(id + '-error', error));

function GoalWrites(props) {
  const nodes = props.nodes;
  const first = String(props.currentId || (nodes[0] && nodes[0].id) || '');
  const [mode, setMode] = React.useState(nodes.length ? 'details' : 'add');
  const [detailsGoal, setDetailsGoal] = React.useState(first);
  const [details, setDetails] = React.useState(function () {
    const node = nodes.find(item => String(item.id) === first);
    return node ? node.details : '';
  });
  const [detailsBaseline, setDetailsBaseline] = React.useState(function () {
    const node = nodes.find(item => String(item.id) === first);
    return { goal: first, details: node ? node.details : '' };
  });
  const [conditionGoal, setConditionGoal] = React.useState(first);
  const [currentGoal, setCurrentGoal] = React.useState(first);
  const [condition, setCondition] = React.useState('');
  const [title, setTitle] = React.useState('');
  const [newDetails, setNewDetails] = React.useState('');
  const [parent, setParent] = React.useState(first);
  const [rank, setRank] = React.useState('');
  const [errors, setErrors] = React.useState({});
  const [message, setMessage] = React.useState({ kind: '', text: '' });
  const [busy, setBusy] = React.useState(false);
  const titleRef = React.useRef(null);
  const detailsRef = React.useRef(null);
  const conditionRef = React.useRef(null);

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

  React.useEffect(function () {
    if (!props.createRequest) return;
    setMode('add');
    setParent(String(props.createRequest.parentId));
    setErrors({});
    const node = nodes.find(item => item.id === props.createRequest.parentId);
    setMessage({ kind: 'quiet', text: node
      ? 'Adding a child under “' + node.title + '”.'
      : 'Adding a goal at the tree root.' });
  }, [props.createRequest]);

  React.useEffect(function () {
    if (props.createRequest && mode === 'add' && titleRef.current) {
      titleRef.current.focus();
    }
  }, [props.createRequest, mode]);

  React.useEffect(function () {
    if (!props.editRequest) return;
    const id = String(props.editRequest.goalId);
    const node = nodes.find(item => String(item.id) === id);
    if (!node) return;
    setMode('details'); setDetailsGoal(id); setDetails(node.details || '');
    setDetailsBaseline({ goal: id, details: node.details || '' });
    setErrors({}); setMessage({ kind: 'quiet', text:
      'Editing “' + node.title + '”.' });
  }, [props.editRequest]);

  React.useEffect(function () {
    if (props.editRequest && mode === 'details' && detailsRef.current) {
      detailsRef.current.focus();
    }
  }, [props.editRequest, mode]);

  async function write(payload, clear) {
    setBusy(true); setMessage({ kind: 'quiet', text: 'Saving…' });
    try {
      const response = await fetch('/goals', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const verdict = await writeVerdict(response);
      if (!verdict.landed) {
        setMessage({ kind: 'error', text: 'Could not save this form — ' +
          (verdict.detail || verdict.reason || 'the store did not accept it') });
      } else {
        clear();
        setMessage({ kind: 'ok', text: 'Saved quietly · appears on the next tick' });
      }
    } catch (error) {
      setMessage({ kind: 'error', text:
        'Could not save this form — the page could not reach the store' });
    }
    setBusy(false);
  }

  const selectDetailsGoal = event => {
    const id = event.target.value;
    const node = nodes.find(item => String(item.id) === id);
    setDetailsGoal(id); setDetails(node ? node.details : '');
    setErrors({});
  };
  const selector = (id, value, change, includeRoot, describedBy) =>
    React.createElement('select', { id: id, value: value, onChange: change,
      disabled: busy, 'aria-describedby': describedBy },
    goalOptions(nodes, includeRoot));
  const changeMode = next => {
    setMode(next); setErrors({}); setMessage({ kind: '', text: '' });
  };
  const modeButton = (value, text) => React.createElement('button', {
    type: 'button', className: 'goalwrite-mode', disabled: busy,
    'aria-pressed': mode === value, onClick: () => changeMode(value),
  }, text);
  const actions = (...children) => React.createElement(
    'div', { className: 'goalwrite-actions' }, ...children);

  let form;
  if (mode === 'details' && nodes.length) {
    const unchanged = detailsGoal === detailsBaseline.goal &&
      details === detailsBaseline.details;
    form = React.createElement('form', { className: 'goalwrite', noValidate: true,
      onSubmit: event => {
        event.preventDefault();
        write({ action: 'edit-details', goal_id: Number(detailsGoal), details },
          () => setDetailsBaseline({ goal: detailsGoal, details }));
      } }, React.createElement('h3', null, 'Edit goal details'),
    React.createElement('p', { className: 'goalwrite-intro' },
      'Choose a goal, revise its Markdown, then save or abandon the edit.'),
    goalField('Goal', 'goal-details-goal',
      selector('goal-details-goal', detailsGoal, selectDetailsGoal, false),
      null, 'Indented titles show where each goal sits in the tree.'),
    goalField('Details', 'goal-details-text', React.createElement('textarea', {
      id: 'goal-details-text', ref: detailsRef, value: details, disabled: busy,
      onChange: event => setDetails(event.target.value),
    }), null, 'Markdown is supported.'),
    actions(React.createElement('button', { type: 'submit', disabled: busy ||
      unchanged }, 'Save changes'),
    React.createElement('button', { type: 'button', className: 'quiet',
      disabled: busy || unchanged, onClick: () => {
        setDetailsGoal(detailsBaseline.goal); setDetails(detailsBaseline.details);
        setErrors({});
        setMessage({ kind: 'quiet', text: 'Edit abandoned; the tree was unchanged.' });
      } }, 'Cancel edit')));
  } else if (mode === 'condition' && nodes.length) {
    form = React.createElement('form', { className: 'goalwrite', noValidate: true,
      onSubmit: event => {
        event.preventDefault();
        if (!condition.trim()) {
          setErrors({ condition: 'Done when is required' });
          if (conditionRef.current) conditionRef.current.focus();
          return;
        }
        setErrors({});
        write({ action: 'add-condition', goal_id: Number(conditionGoal),
          condition: condition.trim() }, () => setCondition(''));
      } }, React.createElement('h3', null, 'Add a completion condition'),
    React.createElement('p', { className: 'goalwrite-intro' },
      'State one observable condition that marks this goal done.'),
    goalField('Goal', 'goal-condition-goal', selector('goal-condition-goal',
      conditionGoal, event => setConditionGoal(event.target.value), false),
      null, 'Indented titles show where each goal sits in the tree.'),
    goalField('Done when', 'goal-condition-text', React.createElement('input', {
      id: 'goal-condition-text', ref: conditionRef, value: condition, disabled: busy,
      onChange: event => {
        setCondition(event.target.value);
        if (errors.condition) setErrors({ ...errors, condition: '' });
      }, 'aria-invalid': !!errors.condition,
      'aria-describedby': errors.condition ? 'goal-condition-text-error' : undefined,
      placeholder: 'The outcome can be checked…',
    }), errors.condition),
    actions(React.createElement('button', { type: 'submit', disabled: busy },
      'Add condition'), React.createElement('button', { type: 'button',
      className: 'quiet', disabled: busy || !condition, onClick: () => {
        setCondition(''); setErrors({});
      } }, 'Clear condition')));
  } else if (mode === 'current' && nodes.length) {
    form = React.createElement('form', { className: 'goalwrite', noValidate: true,
      onSubmit: event => {
        event.preventDefault();
        write({ action: 'set-current', goal_id: Number(currentGoal) }, function () {});
      } }, React.createElement('h3', null, 'Set the current goal'),
    React.createElement('p', { className: 'goalwrite-intro' },
      'Choose the goal the loop should treat as current.'),
    goalField('Goal', 'goal-current-goal', selector('goal-current-goal',
      currentGoal, event => setCurrentGoal(event.target.value), false),
      null, 'Indented titles show where each goal sits in the tree.'),
    actions(React.createElement('button', { type: 'submit', disabled: busy },
      'Make current')));
  } else {
    form = React.createElement('form', { className: 'goalwrite', noValidate: true,
      onSubmit: event => {
        event.preventDefault();
        if (!title.trim()) {
          setErrors({ title: 'Goal title is required' });
          if (titleRef.current) titleRef.current.focus();
          return;
        }
        setErrors({});
        write({ action: 'add-goal', title: title.trim(), details: newDetails,
          parent_id: parent === '' ? null : Number(parent),
          rank: rank === '' ? null : Number(rank) }, function () {
          setTitle(''); setNewDetails(''); setRank('');
        });
      } }, React.createElement('h3', null,
      nodes.length ? 'Add a goal' : 'Add the first goal'),
    React.createElement('p', { className: 'goalwrite-intro' }, nodes.length
      ? 'Place the goal in the tree now; details and ordering can stay optional.'
      : 'Start with the outcome this tree exists to achieve.'),
    goalField('Goal title', 'goal-new-title', React.createElement('input', {
      id: 'goal-new-title', ref: titleRef, value: title, disabled: busy,
      onChange: event => {
        setTitle(event.target.value);
        if (errors.title) setErrors({ ...errors, title: '' });
      }, 'aria-invalid': !!errors.title,
      'aria-describedby': errors.title ? 'goal-new-title-error' : undefined,
      placeholder: 'A clear outcome',
    }), errors.title),
    goalField('Parent', 'goal-new-parent', selector('goal-new-parent', parent,
      event => setParent(event.target.value), true, 'goal-new-parent-hint'),
      null, 'Choose Tree root for a top-level goal; indented titles preserve context.'),
    goalField('Details', 'goal-new-details', React.createElement('textarea', {
      id: 'goal-new-details', value: newDetails, disabled: busy,
      onChange: event => setNewDetails(event.target.value),
      placeholder: 'Context, constraints, or useful links (Markdown)',
    }), null, 'Optional · Markdown is supported.'),
    React.createElement('details', { className: 'goalwrite-advanced' },
      React.createElement('summary', null, 'Ordering (optional)'),
      goalField('Sibling rank', 'goal-new-rank', React.createElement('input', {
        id: 'goal-new-rank', value: rank, disabled: busy, type: 'number',
        onChange: event => setRank(event.target.value), placeholder: 'Automatic',
      }), null, 'Leave blank to use the default order.')),
    actions(React.createElement('button', { type: 'submit', disabled: busy },
      nodes.length ? 'Add goal' : 'Create first goal'),
    React.createElement('button', { type: 'button', className: 'quiet',
      disabled: busy || !(title || newDetails || rank || parent), onClick: () => {
        setTitle(''); setNewDetails(''); setRank(''); setParent(''); setErrors({});
        setMessage({ kind: 'quiet', text: 'Draft cleared; the tree was unchanged.' });
      } }, 'Clear draft')));
  }

  return React.createElement('section', { className: 'goalwrites', id: 'goal-editor' },
    React.createElement('div', { className: 'goalsection-head' },
      React.createElement('div', null, React.createElement('div', {
        className: 'goalsection-kicker' }, 'Edit the structure'),
      React.createElement('h2', null, 'Change the tree')),
      React.createElement('p', { className: 'goalmeta' },
        'Writes appear after the loop reads the receipt on its next tick.')),
    nodes.length ? React.createElement('div', {
      className: 'goalwrite-modes', 'aria-label': 'Choose an editing action',
    }, modeButton('add', 'Add goal'), modeButton('details', 'Edit details'),
    modeButton('condition', 'Add condition'), modeButton('current', 'Set current')) : null,
    React.createElement('div', { className: 'goalwrite-card' }, form),
    React.createElement('div', { className: 'goalwrite-status ' + message.kind,
      role: message.kind === 'error' ? 'alert' : 'status',
      'aria-live': message.kind === 'error' ? 'assertive' : 'polite' }, message.text));
}

function GoalPage(props) {
  const [createRequest, setCreateRequest] = React.useState(null);
  const [editRequest, setEditRequest] = React.useState(null);
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
  const nodes = payload.nodes || [];
  const byId = new Map(nodes.map(node => [node.id, node]));
  const current = byId.get(payload.current_goal_id);
  const tree = expected === 0
    ? React.createElement('div', { className: 'goaltree-empty' },
        React.createElement('strong', null, 'No goals yet'),
        React.createElement('p', null,
          'The examined tree is genuinely empty. Create the first goal below.'))
    : nodes.length ? React.createElement('ul', { className: 'goaltree' },
      nodes.map(node => React.createElement('li', {
        className: 'goaltree-row', id: 'goal-' + node.id, key: node.id,
        style: { '--goal-depth': Math.min(goalDepth(node, byId), 8) },
      }, React.createElement('div', { className: 'goaltree-node' }, stateChip(node),
      React.createElement('span', { className: 'goaltree-title' }, node.title),
      React.createElement('span', { className: 'goalmeta' },
        node.state_error ? 'unreadable — ' + node.state_error
        : node.total_count == null ? 'progress unavailable'
        : node.completed_count + '/' + node.total_count,
        node.state_error ? ''
        : node.blockers.length ? ' · ' + node.blockers.length + ' blocked' : '')),
      React.createElement('div', { className: 'goaltree-actions' },
        React.createElement('a', { className: 'goaltree-action', href: '#goal-editor',
          onClick: event => {
            event.preventDefault();
            setEditRequest({ goalId: node.id, nonce: Date.now() });
          },
          'aria-label': 'Edit details for ' + node.title }, 'Edit'),
        React.createElement('a', { className: 'goaltree-action', href: '#goal-editor',
          onClick: event => {
            event.preventDefault();
            setCreateRequest({ parentId: node.id, nonce: Date.now() });
          },
          'aria-label': 'Add child under ' + node.title }, 'Add child')))))
    : React.createElement('div', { className: 'goalpage-fault' },
        'examined ' + examined + ' of ' + expected +
        ' goal nodes, but no readable rows were returned');
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
        '. The tree above remains readable.')
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
    : expected === 0 ? null : React.createElement('div', {
        className: 'goalpage-fault' },
        'no current goal selected — the tree above remains readable');
  return React.createElement('div', { className: 'goalpage' },
    React.createElement('section', { className: 'goaltree-section',
      'aria-labelledby': 'goal-tree-heading' },
      React.createElement('div', { className: 'goalsection-head' },
        React.createElement('div', null, React.createElement('div', {
          className: 'goalsection-kicker' }, 'The working hierarchy'),
        React.createElement('h2', { id: 'goal-tree-heading' }, 'goal tree')),
        React.createElement('div', { className: 'goalpage-count' },
          'examined ' + examined + ' of ' + expected + ' goal nodes')),
      tree),
    currentPanel,
    React.createElement(GoalWrites, { nodes: nodes,
      currentId: payload.current_goal_id, createRequest: createRequest,
      editRequest: editRequest }));
}

export function registerGoals(registry) {
  return registry.register('goals', {
    component: GoalPage,
    doc: 'Native /goals read surface; sole full-page renderer.',
  });
}
