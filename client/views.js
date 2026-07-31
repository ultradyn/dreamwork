
/* view builders: each returns the inner HTML of #view for one route.
   The dashboard/questions views are data-driven (re-rendered live on
   mtime change); the file view is a static read. */
function dreamBlock(d) {
  return expand(
    `${esc(d.name)}<span class="age" data-mt="${d.mtime}"></span>`,
    mdB(d.content), '', `dream:${d.name}`);
}
/* ── the questions channel's health (#136) ────────────────────────────────
   "Nothing needs you" and "the loop's channel to you is broken" produce the
   same number, and for one morning they produced the same page: a dashboard
   reading zero open questions over a file holding six. So the count is not
   allowed to be the only thing that speaks — `questions_health` says WHICH
   zero this is, and only the broken one is loud.

   The calm states render nothing at all. That is deliberate and it is the
   half that keeps this check alive: a fresh target seeds an empty
   questions.md by design, and a page that greeted every new target with a
   warning would train him to ignore the one that matters. Absence of a
   message IS the all-clear, exactly as it was before. */
/* what the empty list SAYS is a claim about the file, so it is keyed on
   whether the file could be read at all. "none — all answered" was made
   unconditionally, which is the sentence that lied for a whole morning. */
const QNONE = { ok: 'none — all answered', empty: 'none — all answered',
                missing: 'none yet',
                unreadable: 'none that this page can read' };
const QHEALTH = {
  // the path is NOT backticked here: linkify would turn it into a /file link
  // to a file that does not exist, and an affordance that leads nowhere is a
  // small lie of its own on the one panel about lying.
  missing: { label: '',
    body: 'no .dreamwork/questions.md yet — the loop writes one the first ' +
          'time it needs you.' },
  unreadable: { label: 'questions unreadable',
    body: '.dreamwork/questions.md has content and this page can see no ' +
          'entries in it. anything the loop has asked you is sitting in that ' +
          'file, invisible here, while this page says none. an entry is a ' +
          'top-level bullet with a bold title, under a literal ## Open.' },
};
function qHealth(d) {
  const c = QHEALTH[d && d.questions_health];
  if (!c) return '';
  const src = (d.files || {})['questions.md'];
  const n = src ? src.split('\n').length : 0;
  return `<div class="qhealth ${d.questions_health}">` +
    (c.label ? `<div class="qhlabel">${esc(c.label)}` +
       (n ? ` · ${n} lines, 0 entries` : '') + `</div>` : '') +
    `<div class="qhbody">${mdInline(c.body)}</div></div>`;
}
/* ── the status section (#130) ────────────────────────────────────────────
   His words: "on main dashboard page for a dreamworker, the status section
   shows json. It should render that json nicely, using colors effectively,
   and making good use of space, and cutting out or hiding bulk or boring
   stuff."

   This panel is how he checks the loop at a glance, and a glance is three
   questions: what is happening, who is doing it, and does anything need him.
   Everything else in status.json is there so an AGENT can resume — which
   makes it load-bearing rather than junk, so it is folded and never dropped.

   **Nothing is dropped, only demoted.** status.json is a schema rather than a
   fixed shape and the loop keeps adding keys to it (it grew by half at 10:44
   the day this was written, which is what made the dump unreadable). A
   renderer that showed a known list would silently hide the next thing the
   loop learned to say, so the fold takes whatever is LEFT rather than a
   second list — a new key costs a click, not a disappearance.

   **Colour by significance, never by JSON type.** Tinting strings, numbers
   and booleans is the obvious move and the wrong one: it makes the panel
   louder without making any of it easier to read, and it spends the page's
   one accent on `true`. The accent goes to `awaiting_human` and nowhere else
   here, because it is the only thing on this panel waiting on HIM — the same
   axis the question card's three states run on. Everything else is the text
   ramp: what is happening is brightest, what it is for sits under it, the
   liveness facts are dim, the fold is dimmer. */
function stLines(v) {
  if (v == null) return [];
  if (Array.isArray(v)) return v.flatMap(stLines);
  if (typeof v === 'object')
    return Object.entries(v).map(([k, x]) =>
      `${k.replace(/_/g, ' ')}: ${stLines(x).join(', ')}`);
  return [String(v)];
}
const stField = (k, v) =>
  `<div class="stfield"><span class="stk">${esc(k.replace(/_/g, ' '))}</span>` +
  `<span class="stvals">` +
  stLines(v).map(l => `<div class="stval">${mdInline(l)}</div>`).join('') +
  `</span></div>`;
const ST_GLANCE = ['awaiting_human', 'push', 'task', 'goal', 'agents', 'queue',
                   'pending_events', 'last_tick', 'last_commit'];
const ST_AGENT_GLANCE = ['name', 'in_flight'];
function statusBlock(s, handoffs) {
  if (!s || typeof s !== 'object') return '';
  const hands = Array.isArray(handoffs) ? handoffs : [];
  const arr = v => Array.isArray(v) ? v : (v == null ? [] : [v]);
  const agents = arr(s.agents).filter(a => a && typeof a === 'object');
  let h = `<div id="status">` + label('status');
  // 0. can the loop reach him at all. A push that failed is the master fault
  //    here — it contextualises everything under it: an `awaiting_human` list
  //    the loop cannot deliver, a task he will never be pinged about. It goes
  //    first, in the page's one BROKEN colour, naming the channel and the
  //    reason because the remedy is his and "push down" alone sends him
  //    hunting (the 403 and the credit message are the actionable part).
  //
  //    QUIET BY CONSTRUCTION for the two non-fault states, and that is the
  //    half that keeps this credible: no `push` key means the loop has not
  //    tried (a fresh target), and ok:true means the last one landed. Only
  //    ok:false earns pixels. The branch is strict (`=== false`) so a missing
  //    or malformed ok — which lint catches at the writer — never reads as a
  //    fault, and a channel that is fine deserves no pixels. The three states
  //    are distinguishable from the DATA (absent / true / false), not from
  //    the render: a loop that never tried must NOT look identical to one
  //    whose pushes all land, and the browser guard asserts all three.
  const p = s.push;
  if (p && typeof p === 'object' && p.ok === false) {
    const ch = p.channel ? esc(String(p.channel)) : 'the channel';
    const why = p.detail ? esc(String(p.detail)) : 'no reason given';
    const at = p.at ? Date.parse(p.at) : NaN;
    // `data-at` (not data-mt/data-ct): a thing that HAPPENED renders "Xm ago",
    //    grammar rather than format (see ages()) — the sweep fills the span
    //    with "Xm ago" itself, so no appended "ago" here and a space before
    //    it so "failed" and the age do not run together. NaN falls back to
    //    verbatim, the same rule as last_tick.
    const when = isNaN(at)
      ? (p.at ? esc(String(p.at)) : '')
      : `failed <span class="age" data-at="${at / 1000}"></span>`;
    h += `<div class="stpush">` +
      `<div class="stpushhead">push channel down` +
      (when ? ` · ${when}` : '') + `</div>` +
      `<div class="stpushbody">the loop cannot reach you — its last push (` +
      ch + `) came back: ` + why + `. pushes land nowhere until this clears; ` +
      `the remedy is likely yours (billing or re-auth), not the loop's. ` +
      `this dashboard keeps working either way.</div></div>`;
  }
  // 1. does anyone need HIM. First, and the one accented thing here.
  const need = arr(s.awaiting_human);
  if (need.length)
    h += `<div class="stneed">` +
      `<div class="stneedhead">${need.length} awaiting you</div>` +
      need.map(x => `<div class="stneedrow">${mdInline(String(x))}</div>`)
          .join('') + `</div>`;
  // 2. what is happening, and what it is for
  if (s.task) h += `<div class="sttask">${mdInline(String(s.task))}</div>`;
  if (s.goal) h += `<div class="stgoal">${mdInline(String(s.goal))}</div>`;
  // 3. who is doing it — a name and the one line that says what they are on
  if (agents.length)
    h += agents.map(a =>
      `<div class="stagent"><span class="stname">${esc(String(a.name || '?'))}` +
      `</span><span class="stdoing">${mdInline(String(a.in_flight || '—'))}` +
      `</span></div>`).join('');
  // 4. liveness: the small facts that say the loop is still running. The tick
  //    is rendered through the page's live-age idiom rather than as a
  //    timestamp — a dashboard whose thesis is liveness should say "2m old",
  //    and it should keep counting while he watches it.
  const facts = [];
  if (s.queue) facts.push(esc(`${s.queue.in_progress || 0} in flight · ` +
                              `${s.queue.pending || 0} pending`));
  // #655 — batched events waiting for the coordinator to drain (receipts after
  // the journal cursor; the same set `journal_consume.py pending` lists). The
  // coordinator drains them itself each tick, so this is a liveness signal
  // rather than something waiting on HIM — it rides the dim facts ramp, never
  // the accent. Quiet at zero like the hand-offs fact one line down: an empty
  // drain is the steady state, and a "0" sat beside the task counts would read
  // as a scary zero rather than as all-clear (the brief names that exactly).
  // It appears only when events are backing up, which is the one time it
  // matters. Derived server-side from the SAME cursor read as the drain, so it
  // cannot disagree with the tool that actually processes them.
  //
  // THREE STATES FROM THE DATA, the `push` fact's rule twenty lines up: a
  // number is a measurement, and `null` means the journal is THERE and could
  // not be read. That third state must not borrow zero's pixels. The drain
  // fails closed and shouts over an unreadable journal (a schema drift or a
  // torn file raises `VersionMismatchError` and refuses to open); a count that
  // answered `0` there would paint the dashboard's most reassuring state for
  // its least reassuring reason, and permanently — that fault does not clear
  // on the next tick. `== null` catches null and undefined, and `typeof` keeps
  // a `0` off this branch; still the dim ramp, because an unreadable journal
  // is the loop's errand, not his.
  if (typeof s.pending_events === 'number' && s.pending_events)
    facts.push(esc(`${s.pending_events} to drain`));
  else if ('pending_events' in s && s.pending_events == null)
    facts.push('drain depth unreadable');
  // hand-offs awaiting a fold (#381): a count + the ids, inside the facts row
  // rather than a second appearing block, so it reuses the status panel's one
  // tick-driven treatment and authors no second motion idiom. A coordinator
  // looking at this page constantly notices it even if a tick was skipped.
  if (hands.length)
    facts.push(esc(`${hands.length} hand-off${hands.length > 1 ? 's' : ''} to fold: ` +
                   hands.map(h => '#' + h.id).join(', ')));
  const t = s.last_tick ? Date.parse(s.last_tick) : NaN;
  // no space before the span: `.age` carries its own left margin, and a
  // literal one on top of it reads as a typo.
  // The gate is on the FIELD, not on the parse: `if (t)` is falsy for NaN, so
  // the verbatim fallback this line documents had never once run and an
  // unparseable last_tick rendered nothing at all — #154's shape exactly (a
  // documented behaviour nobody measured). Guarded now in identity.mjs.
  if (s.last_tick)
    facts.push(isNaN(t) ? esc(String(s.last_tick))
                        : `tick<span class="age" data-mt="${t / 1000}"></span>`);
  if (s.last_commit) facts.push(esc(String(s.last_commit)));
  if (facts.length)
    h += `<div class="stfacts">` +
         facts.map(f => `<span>${f}</span>`).join('') + `</div>`;
  // 5. the rest — folded, because an agent resumes from it and he does not
  //    read it. Whatever is LEFT, not a second known list.
  const rest = Object.keys(s).filter(k => !ST_GLANCE.includes(k));
  const deep = agents.filter(a =>
    Object.keys(a).some(k => !ST_AGENT_GLANCE.includes(k)));
  if (rest.length || deep.length)
    h += expand(`the rest (${rest.length + deep.length})`,
      deep.map(a => `<div class="stagentmore">` +
        `<div class="stk">${esc(String(a.name || '?'))}</div>` +
        Object.keys(a).filter(k => !ST_AGENT_GLANCE.includes(k))
          .map(k => stField(k, a[k])).join('') + `</div>`).join('') +
      rest.map(k => stField(k, s[k])).join(''), 'dim', 'status-rest');
  return h + `</div>`;
}
/* ── the dashboard's questions section folds (#141) ───────────────────────
   His words: "on the dashboard, the questions section should be collapsed by
   default and show how many questions there are left to answer. it should be
   grayed out and disabeld when that number is zero."

   THE COUNT IS `open_questions`, the server's, and there is deliberately no
   second way to arrive at it — the crumb badge he glances at from every route
   reads that same field, and two counts that can disagree is how a page
   starts lying about the one number he checks.

   DISABLED MEANS "NOTHING HERE NEEDS YOU", NOT "YOU MAY NOT LOOK". At zero
   the summary drops to the dim end of the ramp and loses the accent — and the
   disclosure still opens. Refusing to open would be a claim about permission,
   where zero is a claim about need.

   AND IT IS KEYED ON HEALTH, NOT ON THE COUNT (#136). An unreadable
   questions.md produces a zero too, and a calm grey "nothing to answer" two
   lines under that file's amber warning would be the page contradicting
   itself. The grey is for a genuine zero; every other zero keeps the live
   treatment and lets the warning above it speak.

   THE WHOLE SECTION FOLDS, awaiting-fold cards included. The summary names
   what is inside, so a collapsed panel never hides the fact that something is
   in flight.

   AND IT TRAVELS (#196). This comment used to argue the opposite — that the
   fold was a standalone `expand`, instant like the `.md` peeks, because
   "nothing that MOVES sits below the toggle". That was simply false about
   this page: reviews, files, status and the tint picker all sit below it, and
   the section swings by ~1250px, so the one gesture licensed to snap was the
   largest displacement on the dashboard. His report, verbatim: the questions
   "just appear and disappear". The fold now goes through `travelCard` and the
   page's departure/arrival idioms like every other disclosure — see the
   `.qsec > summary` handler. */
const qSummary = d => {
  const n = d.open_questions || 0;
  const fold = d.questions_open.filter(q => q.answer).length;
  const calm = !n && (d.questions_health === 'empty' ||
                      d.questions_health === 'ok');
  return `<summary class="qseclabel${calm ? ' none' : ''}">questions` +
    (n ? ` · <span class="qsecn">${n} to answer</span>`
       : ` · nothing to answer`) +
    (fold ? ` · ${fold} awaiting fold` : '') + `</summary>`;
};
function qSection(d) {
  const qo = d.questions_open.map((q, i) => [q, i]);
  const openQ = qo.filter(([q]) => !q.answer);
  const foldQ = qo.filter(([q]) => q.answer);
  let inner = '';
  if (openQ.length)
    inner += label('answer questions') +
             openQ.map(([q, i]) => qaCard(q, 'o' + i)).join('');
  if (foldQ.length)
    inner += label('answered · awaiting fold') +
             foldQ.map(([q, i]) => qaCard(q, 'o' + i)).join('');
  if (!inner)
    inner = `<div class="dim">${QNONE[d.questions_health] || QNONE.ok}</div>`;
  return `<details class="qsec" data-keep="qsec">` + qSummary(d) + inner +
         `</details>`;
}
/* what "a commit happened" means, as one comparable value (#151). The whole
   sequence, not just the head: a rebase or an amend can change the panel
   without changing its top row. */
const gitKey = d => ((d && d.git) || []).map(c => c.sha).join(' ');
/* one commit row (#132). Two things about it are load-bearing rather than
   presentational:
     · `data-sha` is the row's IDENTITY, so a re-render can tell which rows
       survived it — the same job `data-qid` does for a question card.
     · the age is an EMPTY node carrying `data-ct`. Nothing server-rendered
       ever states the age, because it is stale the second after it is
       written; `ages()` fills it and keeps filling it (see below). */
/* what this page is RUNNING, said out loud (#140). One line, directly under
   the `commits` label, because the answer is only meaningful beside the list
   of commits it is behind.

   IT IS NEVER SILENT, and that is the one place this deliberately differs
   from the hub's version of the same line. dreamhub says nothing on a healthy
   row because it has N rows and a line on every healthy one hides the
   unhealthy one; here there is one page, and a silent healthy state is
   indistinguishable from no check at all — which is the failure this whole
   page is organised against. So the quiet states are quiet (dim, one short
   line) and only a genuinely wrong state is loud.

   The states, the vocabulary and the missing-commit list are `deployed.py`'s,
   value for value (#147), so hovering this line and reading the hub row give
   the same answer in the same words. Detail is ranked, never withheld: the
   summary is the line and the individual missing commits are its title. */
const SERVE_TEXT = {
  current: s => `serving ${esc(s.rev || '?')}`,
  // "dashboard commits", not "commits", and the extra word is load-bearing
  // HERE in a way it is not on the hub: this line sits directly above a list
  // of ALL of the project's commits, where "3 commits behind" would read as a
  // claim about those rows. HEAD can move thirty times without the dashboard
  // moving once.
  //
  // It said "watch.py commits" until #397, which was exact while watch.py WAS
  // the dashboard — every css and js byte lived in its string literals. Once
  // the client moved to client/, `missing` counts commits to watch.py AND the
  // assets, so the old word named a file that most of those commits do not
  // touch. "dashboard" is also the hub's noun for the same count, which the
  // value-for-value rule (#147) wants anyway.
  behind: s => `this page is ${s.missing.length} dashboard commit` +
    `${s.missing.length === 1 ? '' : 's'} behind · serving ${esc(s.rev || '?')}`,
  untracked: () => 'this page is serving code that is in no commit — ' +
    'started from an uncommitted tree',
};
function servingLine(d) {
  const s = (d && d.deployed) || null;
  if (!s || !s.state) return '';
  const missing = s.missing || [];
  const say = SERVE_TEXT[s.state];
  // a state this page has never heard of is still a reading: say the state
  // rather than rendering nothing, which is what "no match" looked like
  if (!say)
    return `<div class="gserve unknown" title="${esc(s.note || '')}">` +
           `serving — unknown · ${esc(s.note || s.state)}</div>`;
  const loud = s.state !== 'current';
  const title = missing.length
    ? ` title="${esc(missing.map(([h, sub]) => `${h}  ${sub}`).join('\n'))}"`
    : '';
  // #462 — the remedy appears ONLY when the row is genuinely behind. The
  // action runs `just deploy` (re-snapshot from HEAD + restart; the generation
  // bump reloads this tab), behind the #290 arm and the page's one confirmation
  // lifecycle. Never baked with .dreamin — revealStaleAction() applies that
  // start pose once, on the current→behind transition only (see setContent).
  const remedy = s.state === 'behind'
    ? ` — <button class="gservact" type="button" ` +
      `aria-label="update this page via just deploy">just deploy</button>` +
      ` to update`
    : '';
  return `<div class="gserve${loud ? ' stale' : ''}"${title}>` +
         `${say({ ...s, missing })}${remedy}</div>`;
}
/* what a row holds when he opens it (#166). The subject is a LABEL for the
   reasoning; the body is the reasoning, and in this repo it is the most
   useful text in the log — the row shows sixty ellipsised characters of it.

   Through `mdB`, which reflows (#102): a commit body is hard-wrapped at ~72
   columns by every tool that writes one, and rendered verbatim in a wider
   column it reads as a poem. It is prose the loop wrote, so it takes the
   prose renderer, exactly as `.md` files do.

   THE FILES ARE PLAIN TEXT, NOT LINKS, and that is a decision rather than an
   omission: a path from an old commit may not exist now, and #157 is open
   precisely because a link that 404s promises something. When #157 lands
   these become links by resolving first, not by being linkified now.

   Both empty cases say so. "(no message body)" and "(no files)" are one line
   each and they are the difference between "this commit had nothing more to
   tell you" and "this page could not read it" — which is #136's rule, one
   panel over. A no-body commit first shows its FULL subject (#486): the
   header's .gsub may ellipsise it, and "the subject is all of it" is a lie
   the page cannot afford when the subject is a long fold line. */
const gitDetail = c => `<div class="gdetail">` +
  `<div class="gmeta">${esc(c.full || c.sha)} · ${esc(c.who || 'unknown')}` +
  `</div>` +
  ((c.body || '').trim() ? mdB(c.body)
    : `<div class="gfullsub">${esc(c.subject)}</div>` +
      `<div class="gnone">(no message body — the subject is all of it)</div>`) +
  ((c.files || []).length
    ? `<div class="gfiles">` +
      c.files.map(f => `<span class="gfile">${esc(f)}</span>`).join('') +
      (c.more ? `<span class="gfile gmore">+${c.more} more</span>` : '') +
      `</div>`
    : `<div class="gnone">(no files — an empty or merge commit)</div>`) +
  `</div>`;
/* ...and the row IS the disclosure (#166). `<details>` rather than a div
   with a class, so it inherits the page's whole disclosure vocabulary at
   once: `summary::before`'s +/- affordance, #169's air and luminance step,
   `data-keep`'s survival across the tick, and the shared expand handler's
   motion. `data-sha` stays the row's identity for `GIT_LIST`; `data-keep`
   is a SECOND key because they answer different questions — one addresses
   the row inside its list, the other addresses what he opened across a
   re-render, and a commit row is the first element on this page to need
   both at once. */
const gitRow = c => `<details class="commit${
    c.subject.includes('dreamwork(maintain:') ? ' maint' : ''}"` +
  ` data-sha="${esc(c.sha)}" data-keep="commit:${esc(c.sha)}">` +
  `<summary class="grow"><span class="gsha">${esc(c.sha)}</span>` +
  `<span class="gsub">${esc(c.subject)}</span>` +
  `<span class="age cage" data-ct="${c.t}"></span></summary>` +
  gitDetail(c) + `</details>`;
/* ── the burndown (#142) ──────────────────────────────────────────────────
   Two tracks over one set of columns, because the open count alone cannot
   tell "he steers fast" from "the work is slow" — those are the same curve.

     the LEVEL   how many tasks were open in that bucket. This is the
                 burndown, and on this project it has gone up all day.
     the FLOW    arrivals above a hairline, completions below it. Direction
                 is the primary distinction and it needs no colour; the two
                 sit one step apart on the text ramp only so the eye can
                 tell them apart when a column is one pixel tall.

   NO VELOCITY SCORE, deliberately. A rate computed over a day of a loop
   that has been alive for a day is a claim about the future dressed as a
   measurement, and the page would then be believed about it.

   THE ACCENT IS NOT SPENT HERE. Nothing in this panel is waiting on him —
   it is context, not an errand — and the accent's one job on this page is
   marking what needs him. Same rule the status panel follows (#130). */
const BURN_SERIES = [['open', 'bdlevel'], ['arrived', 'bdup'],
                     ['landed', 'bddown']];
/* #417: commits rides the gate too — a weight-only change is still a
   series change, even when open/arrived/landed are flat. */
const burnKey = d => ((d && d.burndown && d.burndown.buckets) || [])
  .map(b => `${b.t0}:${b.arrived}:${b.landed}:${b.open}:${b.commits || 0}`)
  .join(' ');
const BURN_STEP_NAME = { 3600: 'hourly', 14400: 'every four hours',
                         86400: 'daily', 604800: 'weekly',
                         2419200: 'every four weeks' };
/* #487: the ladder the head cycles through — same seconds as BURN_STEPS,
   fine → coarse, wrapping. One list, never a second vocabulary. */
const BURN_STEP_ORDER = [3600, 14400, 86400, 604800, 2419200];
let burnStepPref = null;   // null = server auto; else a BURN_STEP_ORDER entry
/* #499: client-side column-count limit. Default 28; <=0 means all/max;
   hard cap 256 (#546: raised from 168 — measured free: columns flex-shrink
   with min-width:0 so no track/page overflow at any limit or viewport; the
   only effect is thinner columns, already sub-pixel at 168 on mobile).
   Preference is per-target in localStorage (same family as
   burn_step — URL params would fight the posture picker's shared-arm
   idiom less, but the page already keeps small UI state for this panel in
   localStorage, and that is the tie-breaker). Cross-tab: each tab reads
   on load; no storage-event fanout (burn_step does not either) so it
   never races the posture pending key. */
const BURN_LIMIT_DEFAULT = 28;
const BURN_LIMIT_CAP = 256;
// null = use default; number is the stored preference (0 = all).
let burnLimitPref = null;
let _burnLimitDidLoad = false;
/* a bucket's label. Hourly buckets want a clock; daily and wider want a
   date, because "00:00" five times in a row is not a time axis. */
const bstamp = (t, step) => {
  const d = new Date(t * 1000);
  return step >= 86400
    ? d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    : d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
};
/* #417 c3: map ledger commits → level-line cap weight.
   0 commits → 1px (below the floor, so quiet ≠ one).
   1..peak  → 2..6px linear. Peak is always 6px; a lone commit is 2px. */
const CAP_ZERO = 1, CAP_MIN = 2, CAP_MAX = 6;
const commitCap = (n, peak) => {
  const c = Math.max(0, n | 0), p = Math.max(0, peak | 0);
  if (c <= 0) return CAP_ZERO;
  if (p <= 1) return CAP_MIN;
  return Math.round(CAP_MIN + (CAP_MAX - CAP_MIN) * (c - 1) / (p - 1));
};
const bdbar = (b, k, cls, max, peakCommits) => {
  const h = max ? Math.round((b[k] / max) * 100) : 0;
  let style = `height:${h}%`;
  // level line only: open-count height + commits weight
  if (k === 'open')
    style += `;border-top-width:${commitCap(b.commits || 0, peakCommits)}px`;
  return `<div class="bdbar ${cls}" data-bk="${b.t0}" data-series="${k}"` +
    ` data-commits="${b.commits || 0}"` +
    ` style="${style}"></div>`;
};
/* the provenance coverage (#217). THREE COUNTS AND A DENOMINATOR, read
   from the ledger's first sightings (#216): who filed each task at its
   ARRIVAL, which no later edit can reclassify. The historical unknown is
   drawn as itself — the absence of a claim — and is never added to loop
   or implied to be the loop's. The copy names what the denominator IS
   (committed first sightings in recorded git history), which is also the
   scope: an entry still uncommitted in the working tree is not a
   historical arrival and appears nowhere here. */
function provBlock(p) {
  if (!p) return '';
  const total = p.total || 0;
  if (!total)
    return `<div class="bdnote">no first sightings in recorded git history ` +
           `yet</div>`;
  /* order is user · historical unknown · loop: the unknown sits as the
     honest gap BETWEEN the two knowns, not after them (#544). The bar,
     legend, aria-label and hover titles all derive from this one list, so
     they agree by construction. */
  const rows = [['human', p.human, 'phuman'],
                ['historical unknown', p.unknown, 'punknown'],
                ['loop', p.loop, 'ploop']];
  const incomplete = p.history_complete === false;
  /* the aria-label is the WHOLE datum in words: the bar is a picture of
     this sentence, and the sentence is what a screen reader gets. */
  const aria = `task provenance: ${rows.map(([n, c]) => `${n} ${c}`).join(', ')}` +
    ` — ${total} first sightings in recorded git history` +
    (incomplete ? ', coverage is incomplete (shallow clone)' : '');
  return `<div class="bdprov">` +
    `<div class="provbar" role="img" aria-label="${esc(aria)}">` +
    rows.map(([n, c, cls]) =>
      /* Flex distributes the exact remaining track after the two gaps, so
         independently rounded percentages cannot leave a false empty sliver.
         A real but tiny cohort stays visible; zero remains truly absent. */
      `<div class="provseg ${cls}" style="--share:${c};min-width:${c ? 2 : 0}px" ` +
      `title="${esc(n)} ${c}" aria-hidden="true"></div>`).join('') +
    `</div>` +
    `<div class="provline" title="${esc(rows.map(([n, c]) => `${n} ${c}`).join(' · '))}">` +
    rows.map(([n, c, cls]) =>
      `<span class="${cls}">${esc(n)} ${c}</span>`).join(' · ') +
    `</div>` +
    `<div class="provsrc">${total} first sightings in recorded git ` +
    `history</div>` +
    (incomplete
      ? `<div class="provsrc">shallow clone — first sightings before its ` +
        `boundary are invisible, so coverage is incomplete</div>` : '') +
    `</div>`;
}
/* the median filed-to-landed duration (#218). One honest number — the
   median of every filed-to-landed pair the walk already holds — and the
   population it was computed over. NOT a velocity score, a rate, or an
   index: a single duration that says how long finished work took. The
   population is the INTERSECTION of arrived and landed (the work that
   finished), so the copy says "finished" plainly: a reader otherwise
   assumes "how long work takes" and the still-open long tail is excluded,
   which is the optimistic bias the brief named. It rides the SAME age
   ladder as the commits (`ageParts`), one figure at its dominant unit —
   `1h`, `2d` — rather than a second humanizer, and the count beside it is
   the size of the population, because a median over 4 pairs and one over
   200 are different kinds of claim. NO MOTION: this panel re-renders
   through innerHTML on every tick and nothing about it is a layout change
   the page initiates (transitions.md), so this declares no transition —
   the same contract provenance holds one block up, and reduced-motion
   parity is the identical settled visual. */
function medDur(m) {
  if (!m && m !== 0) return '';
  const p = ageParts(Math.floor(Date.now()/1000) - Math.round(m));
  return p.big + p.bu;
}
function medianBlock(s) {
  const n = (s && typeof s.median_n === 'number') ? s.median_n : 0;
  /* THE NO-DATA CASE follows the panel's "which kind of nothing" idiom
     (`test_ledger_series_says_which_kind_of_nothing`): a bare `0` or a
     dash is the wrong thing under any count, because it reads as "work
     takes no time" rather than as "nothing has finished". Nothing has
     landed yet is its own sentence. (n===0 here means work has arrived
     but none of it has the pair a duration needs.) */
  if (!n)
    return `<div class="bdmed">nothing landed yet — no filed-to-landed ` +
           `duration to take the median of</div>`;
  const dur = medDur(s.median);
  /* The aria-label is the whole datum in words: the bar-less line states
     its own population and question, the way the provenance bar's label
     does. "finished" is the load-bearing word — it is what separates this
     median from the one a reader assumes. */
  const aria = `median time finished work took to land: ${dur} ` +
    `(over ${n} filed-to-landed ${n === 1 ? 'pair' : 'pairs'}; ` +
    `still-open work is not in this median)`;
  return `<div class="bdmed" role="img" aria-label="${esc(aria)}">` +
    `<span class="bdnum">${esc(dur)}</span> median time finished work ` +
    `took to land · over ${n} ${n === 1 ? 'pair' : 'pairs'}</div>`;
}
/* #417 c4: ledger-commits-per-period as one figure line. SHORTENED so it
   does not ellipsise at either viewport (his condition): the long form
   ("16 median ledger commits per period · 59 peak · 3 periods with none")
   clipped at mobile. The short form keeps the three facts — median, peak,
   empty periods — and names "commits/period" once so the unit is not
   lost. NO MOTION: settled text, reduced-motion parity free. */
function commitFigBlock(s) {
  if (!s || s.state !== 'ok') return '';
  const med = (typeof s.commit_median === 'number') ? s.commit_median : 0;
  const peak = (typeof s.commit_max === 'number') ? s.commit_max : 0;
  const quiet = (typeof s.commit_quiet === 'number') ? s.commit_quiet : 0;
  const total = (typeof s.commit_total === 'number') ? s.commit_total : 0;
  if (!total && !peak)
    return `<div class="bdcommit-copy">no ledger commits in these periods</div>`;
  const aria = `ledger commits per period: median ${med}, peak ${peak}` +
    (quiet ? `, ${quiet} period${quiet === 1 ? '' : 's'} with none` : '') +
    ` (${total} total)`;
  return `<div class="bdcommit-copy" role="img" aria-label="${esc(aria)}">` +
    `<span class="bdnum">${med}</span> median commits/period · peak ${peak}` +
    (quiet ? ` · ${quiet} empty` : '') + `</div>`;
}
function burnPanel(d) {
  const s = (d && d.burndown) || null;
  if (!s || !s.state) return '';
  // the "cannot chart it" states live INSIDE `.bd` too, so the panel has one
  // address in every state. A reader that has to ask "is it missing or is it
  // empty" is the failure this whole page is organised against, and it
  // applies to the page's own checks as much as to him.
  if (s.state !== 'ok')
    return label('burndown') + `<div class="bd">` +
      `<div class="bdnone">${esc(s.note || s.state)}</div></div>`;
  ensureBurnLimit();
  const all = s.buckets || [];
  const totalN = all.length;
  /* #499: slice to the most recent `lim` columns when the series exceeds
     the active limit. lim=0 means all/max (no slice). Presence of the
     control is totalN > BURN_LIMIT_DEFAULT (28) — his rule: "when we have
     more than 28 elements" — NOT vs the active limit. That way limit=0
     (all) still shows the control so he can dial back; a rule that hid it
     against the active limit left no in-UI recovery. */
  const lim = activeBurnLimit();          // 0 = all
  const showLim = totalN > BURN_LIMIT_DEFAULT;
  const bs = (lim > 0 && totalN > lim) ? all.slice(-lim) : all;
  const flowMax = Math.max(1, ...bs.map(b => Math.max(b.arrived, b.landed)));
  const levelMax = Math.max(1, ...bs.map(b => b.open));
  const peakCommits = (typeof s.commit_max === 'number') ? s.commit_max
    : Math.max(0, ...bs.map(b => b.commits || 0));
  /* #417: columns carry the exact numbers the hover/focus readout names
     (open + flow + commits). Level-track columns are keyboard-focusable so
     the mapping is learnable without a pointer. #487: no native title= —
     .bdtip/.bdinsp are the one hover surface; a browser tooltip stacked
     on them is the second surface the brief forbade. */
  const col = (b, focusable) => {
    const stamp = bstamp(b.t0, s.step);
    const c = b.commits || 0;
    const title = `${stamp} · ${b.open} open · ${b.arrived} arrived · ` +
      `${b.landed} landed · ${c} commit${c === 1 ? '' : 's'}`;
    /* #298: the inspector needs what the glance tip does not — the exact
       interval (t0→t1) and the coverage state. A period with no ledger
       commit CARRIES the previous level rather than measuring it (the
       chart's own rule), so the inspector must be able to say so. */
    const focus = focusable
      ? ` tabindex="0" role="listitem"` +
        ` data-open="${b.open}" data-arrived="${b.arrived}"` +
        ` data-landed="${b.landed}" data-commits="${c}"` +
        ` data-stamp="${esc(stamp)}"` +
        ` data-t0="${b.t0}" data-t1="${b.t0 + s.step}"` +
        ` data-covered="${c > 0 ? 1 : 0}"`
      : '';
    return `<div class="bdcol"${focus}` +
      ` aria-label="${esc(title)}">`;
  };
  // The head states the three totals it is a picture of, so a chart too
  // small to read is still a fact. `open` is the CURRENT count and it comes
  // from the same walk the columns do, not from a second reading.
  // #487: the step name is a cycle control (click / Enter / Space), not
  // bare prose — next ladder step, wrapping, announced via aria-live.
  // #499: when totalN exceeds the DEFAULT (28), the same line carries
  // `limit [ N] [⟳]` — no second row (#417). Presence is vs 28, not the
  // active limit, so all-mode (0) still shows the control.
  const stepName = BURN_STEP_NAME[s.step] || 'bucketed';
  const stepAria = `granularity ${stepName} — activate to cycle`;
  const limVal = displayBurnLimitValue();
  /* #524: [-] input [+] ⟳ — steppers flank the field; id is the #523
     restore key (any focused input inside #view needs a stable id). */
  const limCtl = showLim
    ? `<span class="bdlimit" data-total="${totalN}" data-limit="${limVal}">` +
      `limit ` +
      `<button type="button" class="bdlimit-step" data-dir="-1" ` +
      `aria-label="decrease column limit">−</button>` +
      /* type=text not number: Chromium refuses selectionStart/Range on
         number inputs, so #523 cannot restore caret/selection otherwise.
         inputmode=numeric keeps the mobile keypad; clamp stays in
         applyBurnLimit (min/max attrs are advisory for AT). */
      `<input type="text" id="bdlimit-in" class="bdlimit-in" ` +
      `inputmode="numeric" pattern="[0-9]*" autocomplete="off" ` +
      `min="0" max="${BURN_LIMIT_CAP}" ` +
      `value="${limVal}" ` +
      `aria-label="column limit, 0 for all, max ${BURN_LIMIT_CAP}">` +
      `<button type="button" class="bdlimit-step" data-dir="1" ` +
      `aria-label="increase column limit">+</button>` +
      `<button type="button" class="bdlimit-reset" ` +
      `aria-label="reset column limit to ${BURN_LIMIT_DEFAULT}">⟳</button>` +
      `</span>`
    : '';
  let h = label('burndown') + `<div class="bd">` +
    `<div class="bdtip" hidden role="status" aria-live="polite"></div>` +
    /* #298/#487: the inspector is the richer reading; pin is RHS-or-above
       (bdinspLay), not column-centred. role=status like the tip. */
    `<div class="bdinsp" hidden role="status"></div>` +
    `<div class="bdhead"><span class="bdhead-nums">` +
    `<span class="bdnum">${s.open}</span> open · ` +
    `${s.arrived} arrived · ${s.landed} landed · ` +
    `<button type="button" class="bdstep" role="button"` +
    ` data-step="${s.step}"` +
    ` aria-label="${esc(stepAria)}">${esc(stepName)}</button>` +
    `</span>${limCtl}</div>` +
    `<div class="bdtrack bdnet" role="list" ` +
      `aria-label="open count per period; line weight is ledger commits">` +
      bs.map(b => col(b, true) +
        bdbar(b, 'open', 'bdlevel', levelMax, peakCommits) + `</div>`)
        .join('') + `</div>` +
    `<div class="bdtrack bdflow">` +
      bs.map(b => col(b, false) +
        `<div class="bdhalf bdtop">${bdbar(b, 'arrived', 'bdup', flowMax)}</div>` +
        `<div class="bdrule"></div>` +
        `<div class="bdhalf bdbot">${bdbar(b, 'landed', 'bddown', flowMax)}</div>` +
        `</div>`).join('') + `</div>` +
    `<div class="bdaxis"><span>${esc(bstamp(bs.length ? bs[0].t0 : s.from, s.step))}</span>` +
      `<span>arrivals above · landed below · weight is commits</span>` +
      `<span>${esc(bstamp(s.to, s.step))}</span></div>`;
  /* WHO FILED EACH TASK, said honestly (#217). The old panel reported its
     own coverage (`sourced N/M`) because the ledger could not answer the
     question; #216 made the answer readable from first sightings, so the
     panel now draws the split WITH its unknown remainder visible. The
     block is constant-height for the same reason the head is one
     ellipsised line: numbers that change must never move the panels below
     while the bars are travelling. */
  h += provBlock(s.provenance);
  /* HOW LONG FINISHED WORK TOOK, said honestly (#218). One duration —
     the median of filed-to-landed — and the population it was computed
     over, never a velocity score or a rate. It is COPY in the panel's
     surrounding text, not a mark on the chart: #417's caution is that the
     burndown's quality is not to be traded for an extra series, and a
     median belongs in the chart's honest voice (denominators named,
     unknowns drawn) rather than competing with it. The population is the
     INTERSECTION of arrived and landed — the work that finished — so the
     label says so plainly, because a reader otherwise assumes "how long
     work takes" and the still-open long tail is excluded. NO MOTION: this
     panel re-renders through innerHTML on every tick and nothing about it
     is a gesture the page initiates (transitions.md), so this line declares
     no transition and reduced-motion parity is the identical settled
     visual — the same contract provenance holds one block up. */
  h += medianBlock(s);
  /* #417 c4 — commits-per-period figure. After the median, same voice:
     one fixed line in the panel's surrounding copy. The +19px is a
     deliberate one-time allowance baked into the panel's constant
     height, not a growth that moves the page on a data change. */
  h += commitFigBlock(s);
  return h + `</div>`;
}
/* #504 — the minimal topic-chat list (Q4). His messages to the agent and
   their replies, surfaced from the chats-v1 transcripts the /command `chat`
   application step writes. UI word is "topic chat" (Q2); implementation vocab
   is chat/turn/reply, never `thread` (#229). Reuses the dashboard's dim-row +
   .age annotation idiom — no new token, no new motion (the panel re-renders
   through innerHTML each tick; an arriving chat is the same settled re-render
   the commits list makes). Quiet when empty, like reviews. A pending chat
   (no agent turn yet — awaiting the dreamer's reply) is the in-flight state. */
function chatRow(c) {
  const pend = c.status === 'pending';
  const turn = c.turns === 1 ? '1 turn' : `${c.turns} turns`;
  // #562 — the row is a link to its /chat/<id> page (the defect was "I can't
  // open the chat"). It keeps the dim-row + .age idiom the list already used:
  // status first (the actionable bit), then the last turn's preview, then a
  // dim count. `dim` overrides the anchor's accent so the row still reads as a
  // quiet row, not a lit link — the same dim-row voice the dashboard's other
  // annotation lines keep. encodeURIComponent is the URL-segment escape (esc
  // does not escape "); a chat id is a safe path component regardless.
  return `<a class="dim chatrow" href="/chat/${encodeURIComponent(c.id)}"` +
    ` data-chat="${esc(c.id)}" data-status="${esc(c.status)}">` +
    `${pend ? 'pending' : 'replied'} · ${esc(c.preview)}` +
    ` <span class="age">${turn}</span></a>`;
}
function chatList(d) {
  // #563 — the section is ALWAYS visible, even when there are no chats (he
  // asked for it: the topic-chats section should always show). The label
  // renders whether or not chats exist, the count line tells the truth at 0
  // (`0 total`, the unread clause absent — the same #562 rule), and an empty
  // state takes the dashboard's existing dim-line idiom (the same `none yet`
  // reviews and answers use — no new token). This REMOVES the appear/vanish
  // the old `return ''` guard produced: a section that is always present has
  // no arrival/departure to animate, the smallest possible motion story
  // (transitions.md — the panel still re-renders through innerHTML each tick,
  // the same settled re-render the commits list makes, so no new gesture).
  const chats = (d && d.chats) || [];
  const total = chats.length;
  const unread = total ? chats.filter(c => c.unread).length : 0;
  const cnt = unread > 0 ? `${unread} unread · ${total} total`
                         : `${total} total`;
  return label(`topic chats · ${cnt}`) +
    (total ? chats.map(chatRow).join('') : '<div class="dim">none yet</div>');
}
/* #562 — /chat/<id>: the conversation itself. A chat is its own subject, so
   it earns a URL (watch-design.md's navigate principle — the same warrant
   /reviews earned), and each row in the list links here. The dw-turn frames
   of transcript.md read as turns (his / the dreamer's), newest last; the
   chat's derived title is the page heading (TITLES.chat reads d.chats). No
   new motion: arriving is the route dissolve every destination shares, and
   reduced-motion parity is that dissolve's own instant swap. */
function chatTurn(t) {
  const you = t.role === 'human';
  // his / the dreamer's: a dim who-label + age above the body, the same
  // dim-row + .age annotation voice the list already uses.
  return `<div class="chaturn" data-role="${esc(t.role)}">` +
    `<div class="chatmeta"><span class="chatwho">${you ? 'you' : 'dreamer'}</span>` +
    ` <span class="age">${esc(t.at)}</span></div>` +
    `<div class="chatbody">${esc(t.body)}</div></div>`;
}
function buildChat(fetched) {
  // Unknown id degrades quietly, in the page's own voice — never a traceback,
  // never a thrown exception (the same .qmissing shape buildQuestion uses).
  // No composer on this path: you cannot reply to a chat that does not exist.
  if (!fetched)
    return `<div class="qmissing"><div class="qmisshead">not found</div>` +
      `<div class="qmissbody">this link names a chat the list no longer ` +
      `has — it was most likely removed while you watched. No other chat ` +
      `has been substituted for it.</div>` +
      `<div class="qmissback"><a href="/">&larr; back to dashboard</a></div>` +
      `</div>`;
  return label('topic chat') +
    (fetched.entries || []).map(chatTurn).join('') +
    chatReplyComposer(fetched);
}
/* #577 — the reply composer on /chat/<id>. It reuses the EXISTING composer
   components rather than a second surface: postJSON for the POST, DraftStore
   for a chat-specific draft key (chat:<id>, never the main composer's), the
   #255 confirmation lifecycle (confirmationFor) for success, and the .askform
   idiom the /answers ask box already keeps. It arrives with the route (the
   page surfaces on the dissolve every destination shares — no second motion
   idiom; transitions.md) and the confirmation IS the #255 motion.

   The textarea carries a STABLE id so #523 keyed reconciliation keeps it
   across the tick (value/caret/focus ride the kept node); bindChatReplyDraft
   (router.js) is the reload backstop. data-chat is the chat id, read at send
   so a kept box on a stale tick still replies to the right conversation. */
function chatReplyComposer(fetched) {
  return `<form id="chatreply" class="askform" data-chat="${esc(fetched.id)}">` +
    `<label class="label" for="chatreplybox">reply</label>` +
    `<textarea id="chatreplybox" placeholder="A reply to the dreamer"></textarea>` +
    `<div><button type="submit">Reply</button> ` +
    `<span id="chatreplymsg" class="cmdmsg" aria-live="polite"></span></div></form>`;
}
/* one in-flight reply at a time, the #292 discipline one surface over. While
   a POST is pending, a second submit/Ctrl+Enter is a no-op; the generation
   counter lets only the latest reply touch the surface. Leaving /chat is
   surface destruction (invalidateChatReplyFlight, router.js's navigate) so a
   late response cannot clear/tick a form that no longer exists. */
let chatReplyFlightGen = 0, chatReplyInFlight = false;
let _chatReplyConfirm = null;
/* lazily built: confirmationFor lives in command.js (loaded after views.js),
   so the instance is made on first use, not at module top-level. baseClass is
   'cmdmsg' so the surface reuses the page's ONE confirmation component — its
   .ok accent, .depart atmospheric exit and :empty hide — rather than a second
   idiom (transitions.md: never author a second gesture). */
function chatReplyConfirm() {
  if (!_chatReplyConfirm)
    _chatReplyConfirm = confirmationFor(document, 'chatreplymsg', 'cmdmsg', rmr);
  return _chatReplyConfirm;
}
function invalidateChatReplyFlight() {
  chatReplyFlightGen++;
  chatReplyInFlight = false;
  if (_chatReplyConfirm) _chatReplyConfirm.clear();
}
async function sendChatReply(form) {
  if (chatReplyInFlight) return;
  const box = form.querySelector('#chatreplybox');
  if (!box) return;
  const words = box.value.trim();
  if (!words) return;
  const chatId = form.getAttribute('data-chat') || (view && view.param) || '';
  if (!chatId) return;
  chatReplyInFlight = true;
  const mine = ++chatReplyFlightGen;
  const lid = DraftStore.id('chat', chatId);
  // the #255 lifecycle: success arrives through .dreamin, holds ~5s readable,
  // then departs on the atmospheric exit. Rejection/connection claims replace
  // it immediately — a falsehood must not linger through a gentle exit.
  const attempt = chatReplyConfirm().begin();
  // THROUGH postJSON — the one seam every submission passes, so the reply is
  // witnessed by the client log (#175) and deduped by the journal (#274, via
  // the per-attempt X-Client-Action-Id minted from the chat draft's store).
  const res = await postJSON('/chat-reply', { id: chatId, text: words },
      DraftStore.attemptId(lid));
  // superseded (a newer reply) or surface destroyed (navigated off /chat) —
  // do not touch a newer flight's flag or a surface that no longer exists.
  if (mine !== chatReplyFlightGen) return;
  chatReplyInFlight = false;
  if (view.name !== 'chat') return;
  const liveBox = document.getElementById('chatreplybox');
  if (!liveBox) return;
  const v = res && res._dwv;
  if (res && DraftStore.isDurable(res)) {
    if (!attempt.success()) return;       // superseded between POST and here
    liveBox.value = '';
    DraftStore.clear(lid);                // only on durable landed
    // the next /mtime tick re-fetches /chatdata and the new human turn
    // appears in the transcript; tick() commits that re-render immediately.
    await tick();
  } else {
    const why = (v && v.rejected && v.reason && REJECT_WHY[v.reason])
              || (v && QSEND_WHY[v.status]);
    attempt.claim(!res ? 'no connection'
      : (why ? `not written — ${why}. your words are kept`
             : 'reply was refused — your words are kept'));
  }
}
/* the chat page needs the full transcript, which is not in /data.json (only
   the derived summaries ride it). /chatdata?id= serves the parsed turns for
   one chat — the /filedata idiom one surface over. Fetched fresh each build
   so a reply landing on a live tick appears with no reload (the tick is gated
   on an mtime change, so this is one small fetch per re-render, like
   /data.json itself). null on any failure → buildChat degrades in-voice. */
async function fetchChat(id) {
  try {
    const res = await fetch('/chatdata?id=' + encodeURIComponent(id || ''));
    if (res.ok) return await res.json();
  } catch (e) {}
  return null;
}
/* #545 — the dashboard reviews panel caps at the most recent few rows and
   links to the full /reviews listing. The full list is its own subject and
   earns a URL (watch-design.md's navigate principle), so the panel is a
   window onto it rather than the whole thing. */
const REVIEWS_DASH_CAP = 5;
function buildDashboard(d) {
  let h = `<div id="sections">`;
  // a fault first (it is one line, and usually absent), then what the loop has
  // just DONE — "near the top of dreamworker dashboard should be the most
  // recent 5 commits" (human, 2026-07-25, #151). Nothing else changed order.
  h += qHealth(d);
  h += label('commits') + servingLine(d) + `<div class="git">` +
       d.git.map(gitRow).join('') + `</div>`;
  h += label(`dreams (${d.dreams.length})`) +
       (d.dreams.map(dreamBlock).join('') || '<div class="dim">none active</div>') +
       (d.dreams_archive.length
         ? expand(`archive (${d.dreams_archive.length})`,
                  d.dreams_archive.map(dreamBlock).join(''), 'dim',
                  'dreams-archive') : '');
  // #504 — the topic-chat list (Q4): his messages to the agent and their
  // replies, the main-dreamer first slice of #229/#270. #563 made the section
  // ALWAYS visible (was quiet-when-empty like reviews): the label + `0 total`
  // + a dim `none yet` line render even with no chats, so a chatless target
  // still sees the section. A pending chat (awaiting the dreamer's reply) is
  // the actionable state. Reuses the dashboard's dim-row + .age annotation
  // idiom — no new token, no motion (this panel re-renders through innerHTML
  // on every tick; a new chat arriving is the same settled re-render the
  // commits list does). NOTE the deliberate contrast: the reviews panel stays
  // quiet-when-empty (he has not asked to change it).
  h += chatList(d);
  // #564 — the two questions parts grouped under one visible "Q & A"
  // section. `label()` is the dashboard's section idiom, and its margin-top
  // (var(--space), the section-rhythm token) IS the real visual gap above
  // the group: previously qSection sat directly under the chats list with
  // only the `.25rem` a bare <details> carries. The gap is achieved entirely
  // on the questions side — chatList above is another lane's region and is
  // not touched. Static structure, so the panel's settled tick re-render
  // (#504) carries it with no new motion; the group's internal rhythm is
  // unchanged (grouping + separation, not a redesign of the cards).
  h += label('Q & A');
  h += qSection(d);
  h += `<div class="dim"><a href="/answers">questions for the dreamer · ${d.answers_open.length} open</a></div>`;
  if (d.reviews.length) {
    /* #463 — primary age is *created* (birth), not mtime. When birth is
       unavailable the row says so by name rather than lying with mtime.
       Secondary "modified X ago" only when created is known and differs;
       the chrome's ` · ` is the same separator #456 used for date/age. */
    /* #545 — cap the panel at the most recent REVIEWS_DASH_CAP rows: take
       the first of what the section already renders (#463 birth-newest-
       first, ascending filename tie-break) — no second ordering. Render
       exactly as before when the total is within the cap (no link, no
       "5 of 5" noise); only when there are more does the link line name
       the total honestly and point at the full /reviews listing. The rows
       are the same artifactRow the /reviews page renders — a row here and
       a row there are the same row. */
    const shown = d.reviews.slice(0, REVIEWS_DASH_CAP);
    h += label('reviews') + shown.map(r => artifactRow(r, 'review'))
        .join('');
    if (d.reviews.length > shown.length)
      h += `<div class="dim"><a href="/reviews">all ${d.reviews.length} reviews →</a></div>`;
  }
  h += label('files') +
       ['DREAMWORK.md','questions.md','lessons.md'].map(n =>
         expand(n, mdB(d.files[n], n), '', `file:${n}`)).join('');
  // ...then how the work itself is going (#142). Below the questions and the
  // reviews on purpose: the top of this page is what NEEDS him — a fault,
  // what just happened, what he must answer — and the burndown is context
  // rather than an errand. Above `status` because both are about the loop
  // and this one is the longer view of it.
  h += burnPanel(d);
  h += statusBlock(d.status, d.pending_handoffs);
  // #547: the run-mode picker was removed (superseded by posture below);
  // the /run-mode route and .dreamwork/run-mode file stay — other readers.
  h += posturePicker(d);   // #445 three-axis override of run-mode's posture
  h += tintPicker(d);      // last, and dim: a preference, not status
  return h + `</div>`;
}
function buildQuestions(d) {
  // three explicit states: open (needs the human), answered-awaiting-fold
  // (the loop's to fold), and the folded Answered section — all three the
  // same qaCard, grouped by the state it derives from the key + entry.
  const qo = d.questions_open.map((q, i) => [q, i]);
  const openQ = qo.filter(([q]) => !q.answer);
  const foldQ = qo.filter(([q]) => q.answer);
  let h = `<div id="qsections">` + qHealth(d);
  h += label(`open (${openQ.length})`) +
       (openQ.map(([q, i]) => qaCard(q, 'o' + i)).join('') ||
        `<div class="dim">${QNONE[d.questions_health] || QNONE.ok}</div>`);
  if (foldQ.length)
    h += label(`answered · awaiting fold (${foldQ.length})`) +
         foldQ.map(([q, i]) => qaCard(q, 'o' + i)).join('');
  h += label('answered') + (d.answered_entries.length
    ? d.answered_entries.map((e, j) => qaCard(e, 'a' + j)).join('')
    : '<div class="dim">(none yet)</div>');
  return h + `</div>`;
}
function answerRecord(e, answered=false) {
  const body = `<div class="aqbody">${mdB(e.body)}</div>`;
  // #238/#247: content-stable aid from the server backs both list identity and
  // data-keep so open rides snapshotFolds (re-open only). Missing aid must
  // fail CLOSED: omit both data-aid and data-keep so empty keys cannot collide
  // folds or FLIP, and never emit a shared sentinel like ans:missing.
  if (answered) {
    if (!e.aid) {
      return `<details class="aq answered"><summary>${esc(e.title)}</summary>` +
        `${body}</details>`;
    }
    const id = esc(e.aid);
    return `<details class="aq answered" data-aid="${id}" data-keep="${id}">` +
      `<summary>${esc(e.title)}</summary>${body}</details>`;
  }
  // Open records must NOT bake a permanent `.dreamin` into the HTML (#293):
  // that class is only the enter-snap start pose. New open rows receive a
  // one-shot arrival in revealNewOpenAsks() after setContent (start pose +
  // rAF remove). Hard refresh / first paint of existing rows stays fully
  // visible — no stuck pose. Identity is server `aid` (title+body+ordinal),
  // never title alone — exact-title distinct-body twins must both arrive.
  if (!e.aid) {
    return `<article class="aq open"><div class="qt">${esc(e.title)}</div>` +
      `<div class="label">you asked · awaiting dreamer</div>${body}</article>`;
  }
  return `<article class="aq open" data-aqid="${esc(e.aid)}">` +
    `<div class="qt">${esc(e.title)}</div>` +
    `<div class="label">you asked · awaiting dreamer</div>${body}</article>`;
}
function buildAnswers(d) {
  let h = d.answers_health === 'unreadable'
    ? `<div class="qhealth"><span>answers channel unreadable</span> · <a href="/file?p=.dreamwork%2Fanswers.md">.dreamwork/answers.md</a></div>` : '';
  h += `<form id="askform" class="askform"><label class="label" for="askbox">ask the dreamer</label>` +
    `<textarea id="askbox" placeholder="A question for the dreamer"></textarea>` +
    `<div><button type="submit">Ask</button> <span id="askmsg" class="dim" aria-live="polite"></span></div></form>`;
  h += label(`open (${d.answers_open.length})`) +
    (d.answers_open.map(e => answerRecord(e)).join('') || `<div class="dim">none awaiting the dreamer</div>`);
  h += label(`answered (${d.answers_answered.length})`) +
    (d.answers_answered.map(e => answerRecord(e, true)).join('') || `<div class="dim">none yet</div>`);
  return `<div id="answersections">${h}</div>`;
}
/* /answers ask: one in-flight attempt at a time (#292).
   · While a POST is pending, further submit/Ctrl+Enter is a no-op (does not
     queue a second request with the same bytes).
   · askFlightGen: a response applies only if it still owns the generation.
   · Failure keeps his words; only a matching successful generation clears.
   · Leaving /answers (navigate away) is surface destruction: invalidateAskFlight
     bumps generation and clears the in-flight flag so a rebuilt form is not
     blocked, and a late old response cannot clear/status/tick the new surface.
   · Tick re-renders while still on /answers do NOT invalidate — same surface. */
let askFlightGen = 0, askInFlight = false;
function invalidateAskFlight() {
  askFlightGen++;
  askInFlight = false;
}
async function sendAsk(form) {
  if (askInFlight) return;
  const box = form.querySelector('#askbox'), msg = form.querySelector('#askmsg');
  if (!box) return;
  const words = box.value.trim(); if (!words) return;
  askInFlight = true;
  const mine = ++askFlightGen;
  let res = null;
  if (msg) msg.textContent = 'asking…';
  try { res = await postAsk(words,
      DraftStore.attemptId(DraftStore.id('ask', 'main'))); } catch (e) {}
  // Superseded or surface destroyed — do not touch a newer flight's flag.
  if (mine !== askFlightGen) return;
  askInFlight = false;
  // Re-query: navigate may have replaced the form; never mutate a new surface
  // with an old attempt's outcome, and never tick unless still on /answers.
  if (view.name !== 'answers') return;
  const liveBox = document.getElementById('askbox');
  const liveMsg = document.getElementById('askmsg');
  if (!liveBox) return;
  const v = res && res._dwv;
  if (res && DraftStore.isDurable(res)) {
    liveBox.value = '';
    // durable success only — the #459 ask draft must not reappear as sent
    DraftStore.clear(DraftStore.id('ask', 'main'));
    if (liveMsg) liveMsg.textContent = 'asked';
    await tick();
  } else if (liveMsg) {
    // a rejected 202 (res.ok true, body rejected — E5) used to take this branch
    // as a success and clear the box; the verdict `landed` routes it here, and
    // the reason is named in his voice where the surface already has a message.
    const why = (v && v.rejected && v.reason && REJECT_WHY[v.reason])
              || (v && QSEND_WHY[v.status]);
    liveMsg.textContent = !res
      ? 'dreamwork is unreachable — your words are kept'
      : (v && v.rejected)
        ? (why ? `not written — ${why}. your words are kept`
               : 'question was refused — your words are kept')
        : 'question was refused — your words are kept';
  }
}
/* #158: reflow by file kind, never by content sniff. A .py with a `#`
   comment must stay pre; a research .md must reflow. Path from the query
   is the only signal — same extensions a human means by ".md or similar". */
function isMarkdownFile(p) {
  const s = String(p || '').toLowerCase();
  return s.endsWith('.md') || s.endsWith('.markdown') || s.endsWith('.mdx');
}
/* #284 — the split the heading lockup rests on. Both halves come out of the
   route's own `p` VERBATIM: nothing is normalised, no separator is inserted
   and no segment is collapsed, because the copy button promises the exact
   path back and the metadata line must agree with it character for character.
   `fileDir` keeps its trailing slash for the same reason — that slash is a
   segment boundary the path really has.

   A root-level file has NO parent, and gets no metadata line rather than an
   invented `./`. A heading that claims a directory it does not have is the
   same lie as an ellipsis, one segment smaller. */
const fileBase = p => {
  const s = String(p || ''), i = s.lastIndexOf('/');
  return i < 0 ? s : (s.slice(i + 1) || s);
};
const fileDir = p => {
  const s = String(p || ''), i = s.lastIndexOf('/');
  return i < 0 || !s.slice(i + 1) ? '' : s.slice(0, i + 1);
};
/* #336: human-readable byte count for the binary-file panel. Two units, two
   digits each — same shape as the commit age, so a 153065-byte PNG reads as
   `149.5 KB` rather than a long unbroken number. */
function humanSize(n) {
  const units = [['B', 1], ['KB', 1024], ['MB', 1024 * 1024],
                 ['GB', 1024 * 1024 * 1024]];
  for (let i = units.length - 1; i >= 0; i--) {
    if (n >= units[i][1]) {
      const v = n / units[i][1];
      const digits = i === 0 ? 0 : (v >= 100 ? 0 : 1);
      return v.toFixed(digits) + ' ' + units[i][0];
    }
  }
  return '0 B';
}
/* buildFile renders the body of /file for three kinds of file (#336), and a
   markdown file in one of two MODES (#252 — `mode` comes from the route, so
   Rendered vs Source is deep-linkable):
   - text: <pre> (or reflowed .md, per #158) — with the server's #351
     highlighted markup when the extension names a supported language.
   - image: an <img> served from /filebytes, framed like everything else
     in the column.
   - binary (non-image): a panel that SAYS what the file is — type, size
     — with a download affordance, instead of dumping its bytes into a
     <pre> as plausible-looking mojibake. The bytes are reachable (the
     download link) but never by accident, on the page's "detail is
     ranked, never withheld" rule. */
function buildFile(param, fetched, mode) {
  if (!fetched)
    return '<div id="filebody"><div class="dim">not found</div></div>';
    if (fetched.binary) {
      const dl = '/filebytes?p=' + encodeURIComponent(param || '');
      const mime = fetched.mime || 'application/octet-stream';
      const size = fetched.size || 0;
      if (fetched.kind === 'image') {
        /* MOTION: the image rides the route dissolve like every other part
           of #view (it is inside #view). Its bytes arrive asynchronously,
           though, so the <img> also carries its own arrival — a self-
           contained opacity fade on load, applied as a start pose that
           imgArrived() removes. Reduced motion suppresses the pose in CSS,
           so the image is fully visible from the first frame and the load
           handler is a no-op: same information and timing with the movement
           removed, never a feature that silently degrades. The mime and
           size travel as data-* so imgFailed can fall back to the binary
           panel without refetching. */
        return '<div id="filebody" class="fileimg-wrap">' +
               `<img class="fileimg pose" alt="" src="${dl}" ` +
               `data-mime="${esc(mime)}" data-size="${size}" ` +
               `onload="imgArrived(this)" onerror="imgFailed(this)"></div>`;
      }
      /* NON-IMAGE BINARY. The copy is read by a person who expected to see
         something — write it as information, not as an error. The file IS
         here, it is named, and its bytes are one click away; what it is not
         is text the page can show, so the page says that plainly. */
      return '<div id="filebody"><div class="filebin">' +
             label('binary file') +
             '<div class="filebin-row"><span class="filebin-k">type</span>' +
             `<span class="filebin-v">${esc(mime)}</span></div>` +
             '<div class="filebin-row"><span class="filebin-k">size</span>' +
             `<span class="filebin-v">${humanSize(size)}</span></div>` +
             `<a class="filebin-dl" href="${dl}" download>download the bytes</a>` +
             '</div></div>';
    }
  const text = fetched.text;
  /* #252 — SOURCE IS THE VERBATIM PATH THAT ALREADY EXISTED. It is the same
     `<pre>${esc(text)}</pre>` every non-markdown file at /file has always
     rendered, reached by a second route rather than by a second renderer, and
     that is precisely what makes the bytes trustworthy: there is nothing
     between the server's string and one escaped text node — no transform to
     audit, no tokeniser to drift out of step with the file.

     DO NOT HIGHLIGHT THIS PANE. #351 asks for syntax highlighting on /file,
     and a markdown file's Source mode is the one pane it must not touch: he
     asked for this mode so that what he copies out of it is the file. His
     words: that is the whole point of the mode and not a detail to optimise
     away. The condition is EXPLICIT (never "no hl happened to arrive") so
     the guarantee does not depend on what the server chose to send. */
  const renderPlain = isMarkdownFile(param) && mode === 'source';
  /* #351 — every OTHER text file takes the server's highlighted markup when
     it arrived (a known source extension; see file_highlight_html). The
     markup is review_artifact's #339 output — tok- spans, escaped, its
     round-trip proved byte-exact — so textContent is still the file. When
     no `hl` arrived (an extension the map does not name) the render is the
     same verbatim <pre> it always was: plain, never guessed. */
  const src = (!renderPlain && fetched.hl) ? fetched.hl
                                         : `<pre>${esc(text)}</pre>`;
  /* filePath threads into mdB so relative [text](../x) targets resolve
     against this file's directory into the closed linkable set (#522). */
  const body = (isMarkdownFile(param) && mode !== 'source')
    ? mdB(text, param) : src;
  return `<div id="filebody">${body}</div>`;
}
/* the image's own arrival (#336): if its bytes land after the view settled,
   it is still in its .pose start state — remove it once, on the load event,
   to ease in on .fileimg's standing opacity transition. If the bytes
   arrived during the route dissolve, the dissolve already carried the image
   and the load event finds no .pose to remove. Idempotent. */
function imgArrived(img) {
  if (!img || img.dataset.arrived) return;
  img.dataset.arrived = '1';
  if (img.classList.contains('pose')) {
    void img.offsetWidth;
    img.classList.remove('pose');
  }
}
/* a load failure (truncated upload, exotic codec the browser cannot decode)
   is the wrong state to leave as a broken-image icon. Replace the dead <img>
   with the same binary-info panel a non-image binary gets — the bytes stay
   reachable via the download link. The mime/size come from the data-*
   attributes captured at build time, so the failure path need not refetch. */
function imgFailed(img) {
  if (!img || img.dataset.failed) return;
  img.dataset.failed = '1';
  const body = img.closest('#filebody');
  if (!body) return;
  const mime = img.dataset.mime || 'application/octet-stream';
  const size = parseInt(img.dataset.size || '0', 10) || 0;
  const dl = img.getAttribute('src') || '';
  body.className = '';
  body.innerHTML = '<div class="filebin">' +
    '<div class="label">image would not render</div>' +
    '<div class="filebin-row"><span class="filebin-k">type</span>' +
    `<span class="filebin-v">${esc(mime)}</span></div>` +
    '<div class="filebin-row"><span class="filebin-k">size</span>' +
    `<span class="filebin-v">${humanSize(size)}</span></div>` +
    `<a class="filebin-dl" href="${esc(dl)}" download>download the bytes</a>` +
    '</div>';
}
/* review view: the raw artifact in an iframe (style-isolated) with the
   originating question docked beside it (answer box included), so it can
   be answered with the review in front of you. Deep-loads without a
   question just show the artifact. */
function buildReview(name, q, d) {
  const src = '/reviewraw?p=' + encodeURIComponent(name || '');
  let dock = '';
  if (q && d) {
    const i = d.questions_open.findIndex(x => x.title === q);
    if (i >= 0)
      dock = `<aside class="qdock" id="qdock">` +
        label('answering') + qaCard(d.questions_open[i], 'o' + i) + `</aside>`;
  }
  // The width he dragged is emitted INTO the markup rather than applied after
  // paint: a route change already animates this column's outer width, and a
  // second correction one frame later would be a visible re-lay-out of every
  // paragraph in both columns.
  const pct = readSplit();
  return `<div id="reviewwrap"${dock ? '' : ' class="nodock"'}` +
      (dock ? ` style="--rsplit:${pct.toFixed(1)}%"` : '') + `>` +
      `<div id="reviewdoc"><iframe id="reviewframe" src="${src}" ` +
      `title="review artifact" loading="lazy"></iframe></div>` +
      (dock ? reviewSplitBar(pct) : '') +
      dock +
    `</div>`;
}
/* ONE artifact row shape for both listing surfaces (#484): the dashboard's
   reviews panel and the /research route. kind is 'review' | 'research';
   the view is /<kind>?p=<name> and the raw endpoint /<kind>raw?p=<name> by
   the one convention, so a second surface is a parameter, not a second
   idiom. The #463 age pair (created primary, modified secondary only when
   the rendered figures differ) comes with the row. */
function artifactRow(r, kind) {
  let age = '';
  if (r.created_known && r.created != null) {
    age = `<span class="age" data-mt="${r.created}"></span>`;
    if (r.show_modified)
      age += `<span class="rsep"> · </span>` +
             `<span class="age rmod" data-mt="${r.mtime}" data-cr="${r.created}"` +
             ` data-review-mod="${esc(r.name)}"></span>`;
  } else {
    age = `<span class="age ageunk">created unknown</span>` +
          `<span class="rsep"> · </span>` +
          `<span class="age rmod" data-mt="${r.mtime}" data-review-mod="${esc(r.name)}"></span>`;
  }
  /* #289 — review decision from the ledger store (store-mode only). A row
     WITH a decision carries question_title (NOT NULL by contract), so the
     marker links to /question?qid=<title> — opening the question that the
     artifact was raised against. accepted (✔) and rejected (✘) are DONE:
     the marker dims like a folded entry. pending is in flight, so its
     marker stays lit. 'unlinked' (no record) renders NO marker — absence of
     a record is its own state, distinct from 'pending' by contract. */
  const dec = r.decision;
  const hasDec = dec === 'accepted' || dec === 'rejected' || dec === 'pending';
  let status = '';
  if (hasDec) {
    const glyph = dec === 'accepted' ? '✔'
                : dec === 'rejected' ? '✘' : 'pending';
    const inner = `<span class="rdecision r${dec}">${glyph}</span>`;
    status = r.question_title
      ? `<a class="rqlink" href="/question?qid=${encodeURIComponent(r.question_title)}">${inner}</a>`
      : inner;
  }
  return `<div data-${kind}="${esc(r.name)}" data-decision="${dec || 'unlinked'}">` +
    `<a href="/${kind}?p=${encodeURIComponent(r.name)}">${esc(r.name)}</a>` +
    pipBtn('/' + kind + 'raw?p=' + encodeURIComponent(r.name), r.name) +
    age + status + `</div>`;
}
/* #484 — research artifacts: the review VIEW idiom (the raw self-contained
   artifact in an iframe for style isolation; the same #reviewwrap/#reviewframe
   nodes, which is what lets the tick's snapshotReviewFrame/restoreReviewFrame
   preservation reach it unchanged) over a listing with NO questions.md
   pairing and NO archive-on-answered lifecycle — research outlives the
   decisions it informed (.dreamwork/docs/research/README.md). No dock, no
   split: there is no question to sit beside. */
function buildResearch(name, d) {
  if (name)
    return `<div id="reviewwrap" class="nodock">` +
      `<div id="reviewdoc"><iframe id="reviewframe" src="` +
      '/researchraw?p=' + encodeURIComponent(name) +
      `" title="research artifact" loading="lazy"></iframe></div></div>`;
  if (!d) return '<div class="dim">loading…</div>';
  if (!d.research.length)
    return label('research') +
      `<div class="dim">no built research artifacts yet — sources live in ` +
      `<code>.dreamwork/docs/research/src/</code> and build through ` +
      `<code>review_artifact.py</code>, the one template pipeline.</div>`;
  return label('research') +
    d.research.map(r => artifactRow(r, 'research')).join('');
}
/* #545 — every review artifact on one page, the listing shape the review
   and research surfaces already share: one artifactRow factory, the same
   dock-link behaviour and created/modified age pair. The dashboard's cap
   points here; this is the full list that earned a URL (watch-design.md's
   navigate principle: the full list is its own subject). A row on the
   dashboard and a row here are the same row — kind is still 'review', so
   the dock-link and decision marker are unchanged. */
function buildReviews(d) {
  if (!d) return '<div class="dim">loading…</div>';
  if (!d.reviews.length)
    return label('reviews') + '<div class="dim">none yet</div>';
  return label('reviews') +
    d.reviews.map(r => artifactRow(r, 'review')).join('');
}
/* #452 — ONE question on its own page: a surface the loop's churn cannot
   shift under him mid-answer. The key (`qid` in the URL) is the question's
   TITLE identity — the same string `data-qid` already carries to survive
   regrouping — chosen for what survives it: body rewrites, priority
   re-sorts and the open→answered fold all keep the title, and those three
   ARE the churn this page exists for (the loop rewrote #449's entry three
   times in fifteen minutes while he was reading it). A RETITLE breaks the
   key, and that case fails LOUD, in the .qmissing notice below — never a
   blank page and never a different question ("I could not tell" and
   "nothing" must not render the same). #294's planned question_id can
   later be accepted beside the title without invalidating a single link. */
/* #583 — the dual-column marker. `#qfocus` already scopes the focus view
   uniquely (it exists on no other route), and `.qdual` is the layout-split
   branch the CSS keys the two-column grid off: the question body (`.qbody`)
   becomes the left reading column and the answer/note compose (`.qcompose`)
   the right, taller-than-normal response column. The split is CSS-driven and
   focus-scoped on purpose — `qaCard` is the shared component the dashboard,
   /questions and the dock all render through, and changing its structure is
   out of scope; only the focus container opts the same card into two columns.
   The missing-key branch does NOT carry it (no card → nothing to split). */
function buildQuestion(title, d) {
  if (!d) return '<div class="dim">loading…</div>';
  if (title) {
    const oi = (d.questions_open || []).findIndex(x => x.title === title);
    if (oi >= 0)
      return `<div id="qfocus" class="qdual">` +
        qaCard(d.questions_open[oi], 'o' + oi) + `</div>`;
    /* the fold, followed: answering re-indexes the entry into
       answered_entries while he watches, and the page moves WITH it — a
       live question reported as gone is the failure this route exists to
       prevent. Same title, same card, new 'a<n>' address. */
    const ai = d.answered_entries.findIndex(x => x.title === title);
    if (ai >= 0)
      return `<div id="qfocus" class="qdual">` +
        qaCard(d.answered_entries[ai], 'a' + ai) + `</div>`;
  }
  /* Unresolved. The notice says WHAT (the key names nothing live), WHY
     (most likely a retitle), and the way back — and it guesses at nothing:
     a near title is a different question. Not --warn: the channel is fine,
     the question is simply gone, and a fault colour would cry broken over
     an edit. */
  return `<div id="qfocus"><div class="qmissing">` +
    `<div class="qmisshead">not found</div>` +
    `<div class="qmissbody">this link names a question the list no longer ` +
    `has — it was most likely re-titled or removed while you watched. ` +
    `No other question has been substituted for it.</div>` +
    `<div class="qmissback"><a href="/questions">&larr; back to questions</a></div>` +
    `</div></div>`;
}
/* ── the review split (#305) ──────────────────────────────────────────────
   An INVISIBLE affordance still has to be operable by everything that
   operates a control, so the bar is a real `separator` with a value: a
   pointer drags it, arrow keys step it, Home/End reach the floors, and
   Enter or a double-click puts it back. A drag-only splitter is a splitter
   the keyboard cannot see.

   Where the width lives: `localStorage`, read by `buildReview` at build
   time so a fresh /review PAINTS at his width instead of sliding to it.
   It is a preference rather than shared state, and nothing else has to
   carry it across a re-render — the tick replaces only `#qdock`
   (`setLiveContent`), never `#reviewwrap`. */
const RSPLIT_KEY = 'dw.review.split';
/* 70/30 by default because that is where BOTH columns read: the artifacts
   are authored around a ~1000px document and 30% of the widened column is
   ~46ch of question, against the 34ch dock that made this task. The floors
   are the range in which that stays true — at 82% the question is a margin
   note for someone who is only reading, at 30% the artifact is a thumbnail. */
const RSPLIT_MIN = 30, RSPLIT_MAX = 82, RSPLIT_DEF = 70;
const clampSplit = v => Math.min(RSPLIT_MAX,
  Math.max(RSPLIT_MIN, Number.isFinite(v) ? v : RSPLIT_DEF));
function readSplit() {
  let v = NaN;
  try { v = parseFloat(localStorage.getItem(RSPLIT_KEY)); } catch (e) {}
  return clampSplit(v);
}
const reviewSplitBar = pct =>
  `<div id="rsplit" class="rsplit" role="separator" tabindex="0"` +
  ` aria-orientation="vertical" aria-label="review and question widths"` +
  ` aria-valuemin="${RSPLIT_MIN}" aria-valuemax="${RSPLIT_MAX}"` +
  ` aria-valuenow="${Math.round(pct)}"` +
  ` aria-valuetext="${Math.round(pct)}% review, ${100 - Math.round(pct)}% question"` +
  ` title="drag to set the widths · arrow keys step, enter resets"` +
  ` onpointerdown="beginSplit(event)" onkeydown="splitKey(event)"` +
  ` ondblclick="applySplit(${RSPLIT_DEF}, true)"></div>`;
/* the live value is the one in the DOM, not the one on disk: a drag writes
   both, and reading back the element cannot disagree with what is rendered. */
function curSplit() {
  const wrap = document.getElementById('reviewwrap');
  const v = wrap ? parseFloat(wrap.style.getPropertyValue('--rsplit')) : NaN;
  return Number.isFinite(v) ? v : readSplit();
}
function applySplit(pct, keyed) {
  const wrap = document.getElementById('reviewwrap');
  if (!wrap) return;
  const v = clampSplit(pct);
  wrap.classList.toggle('rkeyed', !!keyed);
  wrap.style.setProperty('--rsplit', v.toFixed(1) + '%');
  const bar = document.getElementById('rsplit');
  if (bar) {
    bar.setAttribute('aria-valuenow', String(Math.round(v)));
    bar.setAttribute('aria-valuetext',
      `${Math.round(v)}% review, ${100 - Math.round(v)}% question`);
  }
  try { localStorage.setItem(RSPLIT_KEY, v.toFixed(1)); } catch (e) {}
}
function beginSplit(e) {
  const wrap = document.getElementById('reviewwrap');
  const bar = document.getElementById('rsplit');
  if (!wrap || !bar || e.button !== 0) return;
  e.preventDefault();                     // no text selection while dragging
  /* The mapping is a RATIO measured entirely in painted space — the pointer's
     travel over the pane's painted width — so it needs no correction for the
     enter transform that may still be playing above it (transitions.md's
     mid-transform rule bites when the two spaces are MIXED). The rect is
     re-read per move because that width is itself animating while the column
     glides. */
  const x0 = e.clientX, pct0 = curSplit();
  wrap.classList.remove('rkeyed');
  bar.classList.add('rdrag');
  try { bar.setPointerCapture(e.pointerId); } catch (err) {}
  const move = ev => {
    const r = wrap.getBoundingClientRect();
    applySplit(pct0 + (ev.clientX - x0) / (r.width || 1) * 100, false);
  };
  const end = () => {
    bar.classList.remove('rdrag');
    bar.removeEventListener('pointermove', move);
    bar.removeEventListener('pointerup', end);
    bar.removeEventListener('pointercancel', end);
  };
  bar.addEventListener('pointermove', move);
  bar.addEventListener('pointerup', end);
  bar.addEventListener('pointercancel', end);
}
function splitKey(e) {
  const step = e.shiftKey ? 8 : 2;
  let next = null;
  if (e.key === 'ArrowLeft') next = curSplit() - step;
  else if (e.key === 'ArrowRight') next = curSplit() + step;
  else if (e.key === 'Home') next = RSPLIT_MIN;
  else if (e.key === 'End') next = RSPLIT_MAX;
  else if (e.key === 'Enter' || e.key === ' ') next = RSPLIT_DEF;
  else return;
  e.preventDefault();
  applySplit(next, true);
}
/* THE PANE IS AS TALL AS THE WINDOW ALLOWS (#305, his last sentence).
   Its top is wherever the chrome ended, which depends on how the heading and
   crumbs wrapped, so it is measured rather than assumed — and measured with
   `offsetTop`, which is LAYOUT. `getBoundingClientRect` would be read through
   whatever transform the dissolve is part-way through (transitions.md), and
   this runs inside `setContent`, i.e. one frame before `.enter` is committed.
   Nothing here animates: a window resize is not a gesture. */
function fitReview() {
  const wrap = document.getElementById('reviewwrap');
  if (!wrap) return;
  let top = 0;
  for (let n = wrap; n; n = n.offsetParent) top += n.offsetTop;
  // the body's own bottom padding, so the pane ends where the page ends
  const pad = parseFloat(getComputedStyle(document.body).paddingBottom) || 0;
  const h = Math.round(window.innerHeight - top - pad);
  wrap.style.setProperty('--rvh', Math.max(0, h) + 'px');
  syncDockFade();                    // a resize changes what is still below
}
addEventListener('resize', fitReview);
/* WHICH BOX SCROLLS, asked once (#326). The docked question's scrollport is
   the body wrapper, not the card — the card holds the answer box too, and a
   scrollport that holds the box cannot fade its text at the box. Off /review
   the wrapper generates no box, so this returns an element whose scrollTop is
   always 0, which is what those callers already assumed of the card. Declared
   as a function so the three callers spread across three script blocks do not
   depend on which block loads first. */
function qaScroller(card) {
  return card ? card.querySelector('.qbody') : null;
}
/* IS ANYTHING STILL PASSING UNDER THE ANSWER BOX? That is the only question
   the fade band asks, and the answer is a scroll distance, so it is read
   rather than remembered. A card that does not overflow at all answers "no"
   by the same arithmetic — there is nothing below, so there is nothing to
   fade — which is the zero case his exception describes.

   Called from the three places the answer can change and nowhere else: the
   scroll itself, a resize, and a re-render — the last of those from the tick
   AFTER the scroll it reads has been put back, not from inside the swap. The
   listener is delegated on the CAPTURE phase because `scroll` does not
   bubble and the card it is watching is replaced every two seconds. */
function syncDockFade() {
  const dock = document.getElementById('qdock');
  if (!dock) return;
  const card = dock.querySelector(':scope > .qa');
  const body = card && qaScroller(card);
  if (!body) return;
  const below = body.scrollHeight - body.clientHeight - body.scrollTop;
  dock.classList.toggle('atend', below <= 2);
  /* and the mirror of it at the head: nothing is above at the top, so the
     title is crisp there and the edge only softens once he has scrolled */
  dock.classList.toggle('attop', body.scrollTop <= 2);
}
addEventListener('scroll', e => {
  const t = e.target;
  if (t && t.nodeType === 1 && t.classList.contains('qbody')) syncDockFade();
}, true);
/* #583 — the dual-column response follows him through a long question. His
   geometry: the response column's vertical centre is the midpoint of the
   question's VISIBLE portion — what is actually on screen — so it pairs with
   whatever part he is reading rather than sitting at a fixed screen midpoint
   while the question scrolls past it. Read as a single midpoint of
   [max(top,0), min(bottom,vh)]: continuous (no jump as an edge crosses the
   viewport), always inside the viewport, and equal to the screen centre
   exactly when the question fills it. "Always present regardless of scroll"
   is `position: sticky` (CSS) — the column rides the viewport while the
   question scrolls beside it; this function only sets WHERE inside it, so the
   column tracks the question instead of the screen.

   The value lives on `document.body` as `--qcol-top`, never on the compose:
   morphdom reconciles #view's children every tick, and an inline `top` on the
   compose would be the one attribute the fresh markup does not carry, so it
   would reset to the CSS floor every two seconds and the column would jump.
   `body` is outside #view entirely, so the property is never reconciled away,
   and it inherits down to the compose the CSS rule reads it on. The rule only
   applies under `#qfocus.qdual`, so a stale value left on body after leaving
   the route has no consumer — cleared anyway for tidiness. */
function positionQuestionColumn() {
  const focus = document.getElementById('qfocus');
  const dual = focus && focus.classList.contains('qdual');
  const body = document.body;
  if (!dual) {
    body.style.removeProperty('--qcol-top');
    return;
  }
  const card = focus.querySelector('.qa');
  const q = card && card.querySelector('.qbody');
  const comp = card && card.querySelector('.qcompose');
  if (!q || !comp) { body.style.removeProperty('--qcol-top'); return; }
  const vh = window.innerHeight;
  const r = q.getBoundingClientRect();
  // the question's VISIBLE portion, clamped to the viewport
  const top = Math.max(r.top, 0);
  const bottom = Math.min(r.bottom, vh);
  let centre = (top + bottom) / 2;
  const hc = comp.offsetHeight;
  // keep the response column fully in view; if it is taller than the viewport
  // (it never is — it is the compose box — but the clamp must not invert)
  // just centre on the screen
  if (hc > 0 && hc < vh)
    centre = Math.max(hc / 2, Math.min(centre, vh - hc / 2));
  else
    centre = vh / 2;
  body.style.setProperty('--qcol-top', Math.round(centre - hc / 2) + 'px');
}
let qcolRaf = 0;
const scheduleQCol = () => {
  if (qcolRaf) return;
  qcolRaf = requestAnimationFrame(() => { qcolRaf = 0; positionQuestionColumn(); });
};
addEventListener('scroll', scheduleQCol, true);
addEventListener('resize', scheduleQCol);

/* every number on this page that can drift without a disk change is written
   HERE, once a second, as TEXT into nodes that already exist — never through
   a re-render. That was already the shape; #132 is what makes it load-bearing
   rather than convenient. A commit age at seconds resolution has to change
   every second, and routing that through the tick's `innerHTML` swap would
   re-run the regroup (#113) and re-carry his half-typed text (#118) sixty
   times a minute, forever, to move one digit. `setContent` re-runs this after
   every swap, so a fresh render is filled in before it paints. */
function ages() {
  /* data-mt: a FILE (or review *created*) is `5m old`. #463 adds `.rmod` for
     the secondary "modified X ago" on a review whose created ≠ mtime — same
     attribute, different grammar, so a single forEach branches on class. */
  document.querySelectorAll('.age[data-mt]').forEach(el => {
    const s = ageStr(parseFloat(el.dataset.mt));
    if (!el.classList.contains('rmod')) { el.textContent = s + ' old'; return; }
    /* #463 — the secondary earns its place only if it SAYS something the
       primary does not. `data-cr` is the created figure the row already shows;
       when both render to the same string the modification is invisible at
       this resolution, so the pair is dropped rather than printing
       `3d old · modified 3d ago`. Server-side exact inequality flagged 24 of
       28 real artifacts (create, then write content — sub-millisecond), which
       is why the verdict is here, beside the formatter, and not a threshold
       someone has to tune. Runs inside ages(), which setContent calls BEFORE
       paint, so the pair is absent from the first frame rather than vanishing
       out of a painted one (transitions.md — nothing disappears). */
    const cr = el.dataset.cr;
    if (cr !== undefined && ageStr(parseFloat(cr)) === s) {
      const sep = el.previousElementSibling;
      if (sep && sep.classList.contains('rsep')) sep.hidden = true;
      el.hidden = true;
      el.textContent = '';
      return;
    }
    el.hidden = false;
    el.textContent = 'modified ' + s + ' ago';
  });
  /* #392a: a `.age[data-ct]` node is TWO figures (timed — a commit's real
     timestamp) UNLESS it carries `data-day="1"`, which marks it DAY-precision
     (a question title's date-only midnight). One figure when we know only the
     day; two when we know the time. The number of figures IS the precision. */
  document.querySelectorAll('.age[data-ct]').forEach(el => {
    if (el.dataset.day === '1') {
      paintDayAge(el, parseFloat(el.dataset.ct));
    } else {
      paintAgePair(el, parseFloat(el.dataset.ct), ' ago');
    }
  });
  /* a third flavour, and the difference is grammar rather than format (#165):
     a FILE is `5m old`, a thing he DID is `5m ago`. Commit resolution
     (`data-ct`) is two padded units and far too wide for a 38ch panel, so the
     history takes the short one. */
  document.querySelectorAll('.age[data-at]').forEach(el =>
    el.textContent = ageStr(parseFloat(el.dataset.at)) + ' ago');
  /* #473 — "updated X ago" on a question whose content changed after first
     sight. Same honesty rule as #463's review secondary: only show when the
     rendered figure says something the created age does not. Pure text —
     ages() never transitions digit flips. */
  document.querySelectorAll('.age.qup[data-ut]').forEach(el => {
    const u = parseFloat(el.dataset.ut);
    if (!(u > 0)) { el.hidden = true; el.textContent = ''; return; }
    const s = ageStr(u);
    // pair with the created age on the same .qt, if present
    const qt = el.closest('.qt');
    const crEl = qt && qt.querySelector('.age.qage[data-ct]');
    if (crEl) {
      const cr = parseFloat(crEl.dataset.ct);
      if (cr > 0 && ageStr(cr) === s) {
        const sep = el.previousElementSibling;
        if (sep && sep.classList.contains('rsep')) sep.hidden = true;
        el.hidden = true;
        el.textContent = '';
        return;
      }
    }
    el.hidden = false;
    el.textContent = 'updated ' + s + ' ago';
  });
  const upd = document.getElementById('upd');
  if (upd && fetchedAt) upd.textContent =
    `updated ${ageStr(fetchedAt/1000)} ago`;
  applyTitle();     // the liveness word drifts with the clock, not with disk
  applyFavicon();   // ...and the orbit advances one frame per second on it
  applyTint();      // ...and his colour arrives from whichever window set it
}
/* #473 — an "updated X ago" that first appears is an ARRIVAL (transitions.md:
   no size floor). Mirror revealReviewMods: track known keys, one-shot
   .dreamin, first paint + reduced motion settle fully lit. Digit flips stay
   pure text via ages(). */
let knownQuestionUps = null;
function revealQuestionUpdates() {
  const nodes = [...document.querySelectorAll(
    '.age.qup[data-ut]:not([hidden])')];
  const now = new Set(nodes.map(el => el.dataset.qUpd || el.dataset.ut));
  if (knownQuestionUps === null || window.__dwSkipQuestionUpArrival) {
    nodes.forEach(el => el.classList.remove('dreamin'));
    knownQuestionUps = now;
    return;
  }
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  for (const el of nodes) {
    const k = el.dataset.qUpd || el.dataset.ut;
    if (knownQuestionUps.has(k)) continue;
    if (reduce) continue;
    el.classList.add('dreamin');
    void el.offsetWidth;
    requestAnimationFrame(() => {
      if (el.isConnected) el.classList.remove('dreamin');
    });
  }
  knownQuestionUps = now;
}
/* #463 — a "modified X ago" that appears when a review's mtime pulls away
   from its birth is an ARRIVAL (transitions.md: no size floor). Track which
   review-mod keys we have already settled; a newly-present `.rmod` gets the
   one-shot `.dreamin` enter-snap, then eases in. First paint and reduced
   motion settle fully lit (function, no pose) — the same contract as
   revealNewOpenAsks / revealStaleAction. Pure ages() digit flips stay
   exempt; this only fires when the secondary *node* appears. */
let knownReviewMods = null;
function revealReviewMods() {
  // Only the dashboard reviews list carries these; leave any other route
  // with a clean slate so the next dashboard paint settles, not re-arrives.
  if (view.name !== 'dashboard') { knownReviewMods = null; return; }
  /* `:not([hidden])` because ages() drops a secondary whose figure reads the
     same as the primary (#463). A hidden node is not on the page, so treating
     it as an arrival would animate nothing and, worse, would record it as
     known — so the row's REAL first modification would then be a no-op. */
  const nodes = [...document.querySelectorAll(
    '.age.rmod[data-review-mod]:not([hidden])')];
  const now = new Set(nodes.map(el => el.dataset.reviewMod));
  if (knownReviewMods === null || window.__dwSkipReviewModArrival) {
    nodes.forEach(el => el.classList.remove('dreamin'));
    knownReviewMods = now;
    return;
  }
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  for (const el of nodes) {
    if (knownReviewMods.has(el.dataset.reviewMod)) continue;
    if (reduce) continue;
    el.classList.add('dreamin');
    void el.offsetWidth;
    requestAnimationFrame(() => {
      if (el.isConnected) el.classList.remove('dreamin');
    });
  }
  knownReviewMods = now;
}
/* #289 — a review's DECISION token appearing/changing on its row is a state
   change (transitions.md: no size floor), and it reuses the SAME one-shot
   `.dreamin` arrival idiom as revealReviewMods (#463) / revealQuestionUpdates
   (#473): the row survives the tick (keyed by filename, travels via the list
   FLIP only when it MOVES), but the decision marker inside it is new
   innerHTML. Track each row's `data-decision`; on a genuine change the marker
   gets the enter-snap start pose, then eases in on the standing transition.
   First paint settles visible (no pose), reduced motion skips the pose
   (function only), and a decision going TO 'unlinked' is a departure of inner
   content (no survivor to animate) so it gets no arrival — the marker simply
   is absent from the new innerHTML, the same as the status panel's
   data-driven facts. */
let knownReviewDecisions = null;
function revealReviewDecisions() {
  // Only the dashboard reviews list carries decisions; reset on any other
  // route so the next dashboard paint settles rather than re-arriving.
  if (view.name !== 'dashboard') { knownReviewDecisions = null; return; }
  const rows = [...document.querySelectorAll('[data-review]')];
  const now = {};
  for (const r of rows) now[r.dataset.review] = r.dataset.decision || 'unlinked';
  if (knownReviewDecisions === null) {
    knownReviewDecisions = now;   // first paint: settle visible
    return;
  }
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  for (const r of rows) {
    const name = r.dataset.review, dec = now[name];
    if (knownReviewDecisions[name] === dec) continue;   // unchanged
    if (dec === 'unlinked') continue;   // marker left, not arrived
    const marker = r.querySelector('.rdecision');
    if (!marker || reduce) continue;
    marker.classList.add('dreamin');
    void marker.offsetWidth;
    requestAnimationFrame(() => {
      if (marker.isConnected) marker.classList.remove('dreamin');
    });
  }
  knownReviewDecisions = now;
}
/* one field, two destinations: the mode group under the box picks which
   (#103). Everything downstream — the morph, the ripple, the re-render hold
   — is unchanged; only the routing is new. */
const cardMode = key => {
  const el = document.getElementById('qi' + key);
  const c = el && el.closest('.qcompose');
  return (c && c.dataset.mode) || 'note';
};
/* ONE implementation of "this card's text is destined for X" — used by the
   mode buttons and by the tick's restore (#118), so the two cannot drift.
   The mode is honoured only if this card actually offers it: a folded entry
   is note-only, so a carried-over 'answer' falls back to what the card
   rendered rather than arming a send that would fail. */
function setCardMode(comp, mode, snap) {
  if (!comp || !mode) return;
  const group = comp.querySelector('.sgroup.qmodes');
  const btn = group && group.querySelector('.qmode[data-mode="' + mode + '"]');
  if (!btn && comp.dataset.mode !== mode) return;   // not on offer here
  comp.dataset.mode = mode;
  if (group) group.querySelectorAll('.sgbtn').forEach(b => {
    const on = b === btn;
    b.classList.toggle('on', on);
    b.setAttribute('aria-checked', on ? 'true' : 'false');
  });
  const ta = comp.querySelector('textarea');
  if (ta) {
    ta.placeholder = QPLACE[mode] || '';
    // #273: keep the accessible name in lockstep with the mode control.
    const card = comp.closest('.qa');
    const titleEl = card && (card.querySelector(':scope > .qbody > .qt')
      || card.querySelector(':scope > .qfold > .qt')
      || card.querySelector('.qt'));
    const title = titleEl ? titleEl.textContent.replace(/\s+/g, ' ').trim() : '';
    ta.setAttribute('aria-label', qaFieldLabel(mode, title));
    const send = comp.querySelector('.qsend');
    if (send) send.setAttribute('aria-label', qaSendLabel(mode));
  }
  if (group) slideIndicator(group, !!snap);
}
function submitCard(key) {
  return cardMode(key) === 'answer' ? sendAnswer(key) : sendComment(key);
}
async function sendAnswer(key) {
  const el = document.getElementById('qi' + key);
  const card = el && el.closest('.qa');
  const q = qaEntry(key, card);
  if (!el || !el.value.trim() || !q) return;
  const val = el.value.trim();
  const fromRect = el.getBoundingClientRect();   // the box the text lived in
  const res = await postAnswer(q.title, val,
      DraftStore.attemptId(DraftStore.id('card', q.title)));
  // a failed write must NOT run the morph: the morph IS the confirmation, and
  // confirming a write that did not happen is the one thing worse than the
  // 409 itself (#136). A rejected 202 (res.ok true, body rejected:true — E5)
  // is that same failure, so the verdict `landed` decides, never res.ok.
  const v = res && res._dwv;
  if (!res || !v || !v.landed) { qaFail(card, v); return; }
  // the one moment it is safe to forget (#163's rule, one surface over): the
  // answer landed, so its draft must not survive to reappear as a thought he
  // already sent. A failed send returns above and keeps it. isDurable is the
  // module's receipt seam (writeVerdict.landed today; #263 later).
  if (DraftStore.isDurable(res)) dwDraft.clear(q.title);
  if (!card) return;
  holdRerenderUntil = Date.now() + MORPH_HOLD_MS;   // see ROUTER_JS
  // the morph IS the confirmation: the box reshapes into the answered state,
  // the typed text lifting from the box into the rendered answer (the
  // lifted-hero rule — the answer text is the tracked element). A soft
  // ripple accents it. reduced-motion just swaps to the answered state.
  // Restated through the SAME component, so it cannot drift from a fresh
  // render of the same entry.
  //
  // ...and the card is not alone on the page (#191). Restating it changes its
  // HEIGHT, so every card below it moves — and this path went through neither
  // snapshot nor regroup, so they moved in one frame, in the one gesture this
  // page has most carefully taught to travel. Same seam as the disclosure
  // handler below: snapshot, mutate, regroup.
  const before = snapshotCards();
  const next = Object.assign({}, q, { answer: val });
  card.className = 'qa ' + qaState(next, key);
  card.innerHTML = qaInner(next, key);
  const anstext = card.querySelector('.anstext');
  // the settled destination, measured before the regroup clamps the card's
  // height for its travel — the flip's `to` is where the answer ENDS UP
  const toRect = anstext && anstext.getBoundingClientRect();
  regroupCards(before, null, null, card);
  if (typeof ripple === 'function')
    ripple(fromRect.left + fromRect.width / 2, fromRect.top + 22);
  if (!rmr && anstext && typeof flipDock === 'function')
    flipDock(anstext, fromRect, toRect);
}
/* thread a follow-up note onto any entry — same lifted-hero morph as an
   answer: the note lifts from the box into the thread, ripple accenting. */
async function sendComment(key) {
  const el = document.getElementById('qi' + key);
  const card = el && el.closest('.qa');
  const entry = qaEntry(key, card);
  if (!el || !el.value.trim() || !entry) return;
  const val = el.value.trim();
  const fromRect = el.getBoundingClientRect();
  const res = await postComment(entry.title, val,
                                key[0] === 'o' ? 'Open' : 'Answered',
      DraftStore.attemptId(DraftStore.id('card', entry.title)));
  const v = res && res._dwv;
  // a rejected 202 (res.ok true, body rejected — E5) clears the draft below,
  // which was the only copy of the note, so the verdict `landed` decides —
  // the same rule as sendAnswer one function up.
  if (!res || !v || !v.landed) { qaFail(card, v); return; }
  // a note is a successful send too, and the box clears for the next one — so
  // its draft clears with it, or the next re-render would restore the just-sent
  // note into the empty box he meant to clear (#269, #163's rule).
  if (DraftStore.isDurable(res)) dwDraft.clear(entry.title);
  holdRerenderUntil = Date.now() + MORPH_HOLD_MS;
  if (!card) { el.value = ''; return; }
  // #191, the same as an answer: the note lands INSIDE the card, so the card
  // grows and every card below it moves. Snapshot before the first thing that
  // changes a height — the box being cleared is one of those the moment a box
  // grows with what he types (#177), so it is inside the window rather than
  // trusted to stay inert.
  const before = snapshotCards();
  el.value = '';
  clearBox(el);                               // #177: snap to the floor; the regroup owns the travel
  // the LAST segment, because what he just wrote is the newest thing in the
  // thread — appending to the first would drop it above an answer written
  // hours earlier, which is the bug this whole split exists to prevent (#128).
  // That segment is also never the collapsed one, so it cannot land hidden.
  let host = [...card.querySelectorAll('.threadin')].pop();
  if (!host) {
    const thread = document.createElement('div'); thread.className = 'thread';
    host = document.createElement('div'); host.className = 'threadin';
    thread.appendChild(host);
    /* into the BODY, at its end (#326). `insertBefore(…, '.qcompose')` put it
       in the same visual place while the box was the card's last child, and
       would now land it OUTSIDE the review dock's scroller — a note he cannot
       scroll, wedged between the question and the box. The end of `.qbody` is
       the end of the thread on every route, which is what the segment rule
       below is about. */
    (qaScroller(card) || card).appendChild(thread);
  }
  const f = document.createElement('div');
  f.className = 'follow human';        // it is his; say so, same as a reload
  f.innerHTML = `<span class="who">${WHO.human}</span>` + mdInline(val);
  host.appendChild(f);
  const toRect = f.getBoundingClientRect();
  regroupCards(before, null, null, card);
  if (typeof ripple === 'function') ripple(fromRect.left + 24, fromRect.top + 14);
  if (!rmr && typeof flipDock === 'function') flipDock(f, fromRect, toRect);
}
