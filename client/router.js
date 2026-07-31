
/* Single-document router. Views swap inside #view; the shader canvas is
   its sibling and is never touched, so the background is unbroken across
   navigations. Deep links still work: the server hands back this same
   shell for /, /questions, /file and /review, and we render the matching
   view on load. /review embeds the raw artifact (served at /reviewraw) in
   an iframe; a question that links to it travels along, docked. */
const rmr = matchMedia('(prefers-reduced-motion: reduce)').matches;
let data = null, fetchedAt = 0, lastMtime = null, serverGen = null;
/* after a local answer morph, hold the live re-render briefly so the card
   settles in place before the loop's fresh data regroups it (#79/#81).
   #234 derived the hold from the critical path instead of padding it:
   - `flipDock`'s transform leg is 1.15s — the longest VISIBLE gesture of
     the submit morph (its filter/opacity legs are shorter, and its 1500ms
     safety-net `clear` only strips inline styles `transitionend` already
     stripped at ~1150ms, so nothing is on screen past the transform).
   - the regroup's `CARD_TRAVEL` is 850ms of visible travel; its inline
     cleanup at `CARD_MS + 150` is, again, invisible.
   - the ripple lives on `document.body`, outside the re-rendered view, so
     a tick cannot interrupt it at all.
   So 1150ms plus one beat of slack for the rAF that starts the transition
   and for frame jitter: 1250ms. 850ms was considered and rejected — it
   would release mid-glide. Under reduced motion NONE of the three runs
   (`flipDock`/`ripple` skip on `rmr`, `regroupCards` returns early), so
   the same number is pure margin there, and the shared constant keeps the
   two paths from drifting. Measured by dev/capture/morphhold.mjs. */
const MORPH_HOLD_MS = 1250;
let holdRerenderUntil = 0;
/* /mtime is "<generation> <mtime>": a changed generation means the server
   was rebuilt (--autoreload) or restarted (redeploy) — reload to pick up the
   new shell; a changed mtime just re-renders the live data. */
const parseMtime = raw => {
  raw = (raw || '').trim();
  const sp = raw.indexOf(' ');
  return sp >= 0 ? { gen: raw.slice(0, sp), mtime: raw.slice(sp + 1) }
                 : { gen: '', mtime: raw };
};
let view = { name: null, param: null, q: null };
/* /file view fetch (#336). `fetched` is one of:
   - null: the file is missing or the request failed → 'not found'
   - {text}: the file is text → render as today (md or <pre>)
   - {binary, kind, mime, size}: a binary file → render an <img> (kind ===
     'image') or a binary-info panel with a download affordance (else).
   The /filedata response carries one of those shapes; never the bytes. */
let fileCache = { param: null, fetched: undefined };
/* per-page atmosphere: a tiny tint bias the shader lerps toward (~1.5s) */
const TINT = { dashboard: 0.0, questions: 0.14, answers: 0.08, file: -0.14, review: 0.22, question: 0.18, research: -0.08, reviews: 0.19, chat: 0.05 };
/* per-route dissolve signature: each destination swirls from its own
   turbulence seed, so arriving somewhere has a consistent feel (pairs with
   the per-route tint). Distinct small integers give distinct fields. */
const SEED = { dashboard: 7, questions: 23, answers: 29, file: 41, review: 61, question: 67, research: 71, reviews: 73, chat: 89 };
/* ── the tab title (#153) ─────────────────────────────────────────────────
   The title is the ONLY part of this dashboard that exists while the tab is
   backgrounded, which is most of its life — so it answers the page's whole
   question rather than naming the app: DOES IT NEED ME, and WHICH loop is
   this. Both, because the workflow is now several dreaming agents at once.

       (2) dreamwork/ud-dreamwork · dreaming · questions
        ^   ^                        ^          ^
        |   |                        |          where you are (dropped first)
        |   |                        is the loop still ticking
        |   which app, and which loop of it
        how many things are waiting on YOU

   THE COUNT IS FRONT-LOADED because tabs truncate from the RIGHT, so
   everything past the first field is a bonus. Zero renders as `(0)`, not as
   an empty bracket: a title that says nothing about the count is
   indistinguishable from a page that has not loaded.

   THE TWO LOUD FIELDS ARE ORTHOGONAL, which is what keeps them worth
   reading. The count says whether HE is the bottleneck; the word says
   whether the LOOP is alive. `(2) x · stalled` — he is blocked and it is not
   moving — is a state neither field could report alone, and it is exactly
   the quiet failure this project exists to make loud.

   `!` REPLACES THE COUNT when the reader cannot see questions.md (#136),
   because in that state the count is the thing that lies. It does not say
   what broke — a tab title cannot — it says look, which is all a tab title
   is for. The dashboard's amber line says the rest.

   NOTHING IS CLAIMED THAT IS NOT KNOWN. Before data arrives the shell's own
   `<title>` stands; a target with no status.json gets no liveness word; an
   unparseable `last_tick` gets none either, on `note_author`'s rule. */
const TITLE_ROUTE = { dashboard: () => '', questions: () => 'questions',
                      answers: () => 'answers',
                      file: p => p || 'file',
                      review: p => 'review ' + (p || ''),
                      question: () => 'question',
                      research: p => 'research' + (p ? ' ' + p : ''),
                      reviews: () => 'reviews',
                      chat: () => 'chat' };
/* two missed heartbeats (4.75m each) — one late beat is a busy machine, two
   is a loop that stopped. */
const STALE_TICK_MS = 10 * 60 * 1000;
const statusOf = d => (d && d.status && typeof d.status === 'object')
  ? d.status : null;
/* The honest count of what is visibly waiting on HIM. It derives from the
   open questions he can inspect, never from hand-maintained status prose;
   `awaiting_human` still names WHAT waits in the status panel (#181). */
function titleNeed(d) {
  if (!d) return null;
  if (d.questions_health === 'unreadable') return '!';
  return String(d.open_questions || 0);
}
function titleLive(d) {
  const s = statusOf(d);
  const t = s && s.last_tick ? Date.parse(s.last_tick) : NaN;
  if (isNaN(t)) return '';
  return Date.now() - t > STALE_TICK_MS ? 'stalled' : 'dreaming';
}
const projectName = d => ((d && d.target) || '').replace(/[\/]+$/, '')
                          .split(/[\/]/).pop();
/* WHICH loop, in one field. It was the project alone until he ruled at 15:30
   on 2026-07-25 (`(4) dreamwork · <status> · <extra>`) that the app's name
   comes back — the argument for dropping it was that a tab strip never has
   room, and his answer is that he wants to know what he is looking at.

   His example put `dreamwork` in the slot the PROJECT name occupied, and he
   was reading the ud-dreamwork dashboard when he wrote it, so it reads
   equally as "the app name returns" and as "this is what my tab already
   says". This is the one shape that is right under both: one compound field
   where he put one field, and for another target it reads `dreamwork/hark`,
   which is what it is. The state stays third, so truncation still takes the
   route first. */
const titleWho = d => {
  const proj = projectName(d);
  return proj ? 'dreamwork/' + proj : 'dreamwork';
};
function pageTitle(v, d) {
  const need = titleNeed(d);
  if (need === null) return null;             // no data: claim nothing
  const route = (TITLE_ROUTE[v.name] || TITLE_ROUTE.dashboard)(v.param);
  return `(${need}) ` +
    [titleWho(d), titleLive(d), route].filter(Boolean).join(' · ');
}
/* ── his colour for this project (#143) ───────────────────────────────────
   His words: "user can customize color tint for watch on dashboard for
   dreamworker. shoudl persist for that project and update any other windows
   for that project too."

   PERSIST *AND* SHARE IS WHAT RULES OUT localStorage: it syncs the tabs on
   one machine and loses the setting on the next, and the setting is meant to
   be how he tells this project apart from the others. It lives in
   `.dreamwork/watch-tint`, committable beside everything else the loop keeps
   about a project — so a checkout of the repo arrives already wearing it.

   AND SHARING NEEDS NO NEW MECHANISM. The write lands under `.dreamwork/`,
   which `watched_mtime` already walks, so the existing 2s `/mtime` poll
   carries it: he picks a colour in one window and every other window on this
   project follows within a tick, with nothing added and no reload.

   A HUE, NEVER A COLOUR — see `TINTS`. It rotates the ambient field about
   the grey axis and moves the FAVICON with it. It does not touch the text
   ramp and it deliberately does not touch `--accent`: the accent has one
   job, marking the live and actionable thing, and an indigo accent over a
   green field is more legible than one that moved with it, not less. So the
   thing the tint identifies is the project, and the thing the accent marks
   is still the only thing that needs him. */
let projTint = null;
const tintHue = name => TINTS[name] != null ? TINTS[name] : TINTS[TINT_DEFAULT];
const favHue = () => tintHue(projTint || TINT_DEFAULT);
function applyTint() {
  if (!data) return;
  const name = TINTS[data.tint] != null ? data.tint : TINT_DEFAULT;
  if (name === projTint) return;              // idempotent: the 1s sweep runs it
  projTint = name;
  if (window.dreambg)
    window.dreambg.setProjHue(
      (tintHue(name) - TINTS[TINT_DEFAULT]) * Math.PI / 180);
  // every cached frame was drawn in the old hue, and the icon is the one
  // place the tint has to be right immediately — it is what he is looking at
  // in the OTHER windows when this arrives.
  favCache.clear();
  applyFavicon();
}
/* The picker is the page's standing sliding group (#103/#121), not new
   chrome: an outline that travels, no fill anywhere, so the dreaming field
   stays the background of every button. Each label wears its own hue, which
   is the only way a name like `teal` means anything before you click it. */
function tintPicker(d) {
  const cur = TINTS[d.tint] != null ? d.tint : TINT_DEFAULT;
  return label('tint') +
    `<div class="sgroup tintpick" role="radiogroup" aria-label="project tint">` +
    `<div class="sgind"></div>` +
    Object.keys(TINTS).map(n =>
      `<button type="button" role="radio" class="sgbtn tintbtn` +
      `${n === cur ? ' on' : ''}" data-tint="${esc(n)}"` +
      ` style="--tintswatch:hsl(${TINTS[n]}, 62%, 66%)"` +
      ` aria-checked="${n === cur ? 'true' : 'false'}"` +
      ` onclick="pickTint('${esc(n)}')">${esc(n)}</button>`).join('') +
    `</div><div class="tintmsg" id="tintmsg" aria-live="polite"></div>`;
}
/* A refused write must not leave a swatch selected that will not survive the
   next tick — the same rule as /answer (#136): check what came back before
   showing the thing that means "it landed". */
async function pickTint(name) {
  const msg = document.getElementById('tintmsg');
  let ok = false;
  try {
    const res = await fetch('/tint', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tint: name }),
    });
    // raw-fetch site: owns its Response, so reads the verdict here. A rejected
    // 202 (res.ok true) would otherwise apply a tint that did not land (#136).
    ok = (await writeVerdict(res)).landed;
  } catch (e) { ok = false; }
  if (ok) {
    if (msg) msg.textContent = '';
    // do not wait for the poll in the window he is actually looking at
    if (data) { data.tint = name; applyTint(); }
    document.querySelectorAll('.sgroup.tintpick').forEach(g => {
      g.querySelectorAll('.sgbtn').forEach(b => {
        const on = b.dataset.tint === name;
        b.classList.toggle('on', on);
        b.setAttribute('aria-checked', on ? 'true' : 'false');
      });
      slideIndicator(g, false);
    });
  } else if (msg) {
    msg.textContent = 'could not save the tint — the file was refused';
  }
}
/* ── #445 three-axis posture controls ───────────────────────────────────
   Sibling of run-mode. Authority is `.dreamwork/posture` when present;
   otherwise the UI paints the derivation from run-mode (lint.derive_posture
   via collect()). ONE shared 10s arm covers a whole posture edit — three
   independent arms would be three ceremonies for one file. Reuses RUN_ARM_MS
   rather than a second cooldown. Asymmetry is honest: pace three chips,
   asking four (his dictation — never compress), delegation an integer
   target with a derived label (own/assist/delegate) — a TARGET, never a cap.
   One POST /posture; one events line only on a real change. */
let postArmGen = 0;
let postArmTimer = null;
let postArmTick = null;
let postArmShouldCommit = false;
let postArmUntil = 0;
// Draft of the whole triple while arming (any axis change resets the arm).
let postDraft = null;
// #551: the posture slot's 'remind' button. The ambient #posture-src slot
// (both file and derived sources) carries a link-styled 'remind' button that
// POSTs /remind; on a 202 the slot confirms and the control cannot retrigger
// for REMIND_COOLDOWN_MS. The cooldown state is MODULE-SCOPE — exactly like
// postArmUntil — so a live re-render (the 2s tick rebuilds posturePicker)
// mid-cooldown repaints the confirming state, never a clickable button. It is
// never read back from the DOM: posturePicker reads remindCooldownUntil when
// it builds the slot HTML, so morphdom sees the confirming state in both the
// live DOM and the new HTML and does not revert it.
let remindCooldownUntil = 0;
let remindInFlight = false;
const REMIND_COOLDOWN_MS = 10000;
function remindSlotInner() {
  // The #posture-src inner HTML for the AMBIENT (non-armed) state. The armed
  // 'arming override…' state is handled by its callers and stays unchanged.
  if (remindCooldownUntil && Date.now() < remindCooldownUntil)
    return '<span class="remind-sent">sent · the loop has been reminded</span>';
  return '<button type="button" class="remind-btn" id="remind-btn"' +
    ' onclick="sendRemind()">remind</button>';
}
function paintRemindSlot() {
  // #553: a live posture arm wins the slot. sendRemind's cooldown-end
  // setTimeout calls this to repaint the button back, but if the human
  // armed an override during the cooldown the 'arming override…' copy is
  // live — repainting here would resurrect the button for ≤2s until the
  // next data tick re-renders (morphdom self-heals). pendingPostIsLive is
  // the same predicate the armed state itself uses (paintSlot), so there is
  // no second test of arm-ness to drift. The next tick's posturePicker
  // rebuilds the slot from the same predicate, so the arm is restored if
  // it is still live then.
  if (pendingPostIsLive(readPostPending())) return;
  const src = document.getElementById('posture-src');
  if (src) src.innerHTML = remindSlotInner();
}
async function sendRemind() {
  // One press composes the reminder SERVER-side (target id + resolved posture
  // + SKILL.md pointer); the client sends nothing but the press. On a 202 the
  // slot confirms and locks for REMIND_COOLDOWN_MS; an in-flight guard also
  // prevents a double-POST before the first resolves.
  if (remindInFlight) return;
  if (remindCooldownUntil && Date.now() < remindCooldownUntil) return;
  remindInFlight = true;
  try {
    const res = await fetch('/remind', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    const rv = await writeVerdict(res);
    if (rv.landed) {
      remindCooldownUntil = Date.now() + REMIND_COOLDOWN_MS;
      paintRemindSlot();
      setTimeout(() => { paintRemindSlot(); }, REMIND_COOLDOWN_MS);
    }
  } catch (e) { /* transient: the slot stays armed for another press */ }
  remindInFlight = false;
}
function postPendingKey() {
  return (data && data.target) ? ('dw:posture-pending:' + data.target) : null;
}
function postTabId() {
  try {
    let id = sessionStorage.getItem('dw:posture-tab');
    if (!id) {
      id = 't' + Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem('dw:posture-tab', id);
    }
    return id;
  } catch (e) { return 'anon'; }
}
const POST_ORPHAN_GRACE_MS = 3000;
function readPostPending() {
  try {
    const k = postPendingKey();
    if (!k) return null;
    const p = JSON.parse(localStorage.getItem(k) || 'null');
    if (!p || typeof p.pace !== 'string' || typeof p.asking !== 'string')
      return null;
    if (POSTURE_STOPS_PACE.indexOf(p.pace) < 0) return null;
    if (POSTURE_STOPS_ASKING.indexOf(p.asking) < 0) return null;
    if (typeof p.delegation !== 'number' || p.delegation < 0) return null;
    // delivery is optional in a stale pending cache — default it to instant
    // rather than rejecting, so a pre-#342 pending entry still resumes.
    if (p.delivery != null && POSTURE_STOPS_DELIVERY.indexOf(p.delivery) < 0)
      return null;
    // orchestration is optional in a stale pending cache — default it to
    // hands-on, so a pre-#510 pending entry still resumes.
    if (p.orchestration != null
        && POSTURE_STOPS_ORCHESTRATION.indexOf(p.orchestration) < 0)
      return null;
    if (typeof p.until !== 'number') return null;
    if (p.phase === 'cancel') {
      if (Date.now() >= p.until) { localStorage.removeItem(k); return null; }
      return p;
    }
    if (Date.now() >= p.until + POST_ORPHAN_GRACE_MS) {
      localStorage.removeItem(k);
      return null;
    }
    return p;
  } catch (e) { return null; }
}
function pendingPostIsLive(p) {
  return !!(p && !p.phase && typeof p.until === 'number' && Date.now() < p.until);
}
function writePostPending(draft, until, owner) {
  try {
    const k = postPendingKey();
    if (!k) return;
    localStorage.setItem(k, JSON.stringify({
      pace: draft.pace, asking: draft.asking, delegation: draft.delegation,
      delivery: draft.delivery, orchestration: draft.orchestration,
      until, owner: owner || postTabId(),
    }));
  } catch (e) {}
}
function writePostCancel(draft) {
  try {
    const k = postPendingKey();
    if (!k) return;
    localStorage.setItem(k, JSON.stringify({
      pace: draft.pace, asking: draft.asking, delegation: draft.delegation,
      delivery: draft.delivery, orchestration: draft.orchestration,
      phase: 'cancel', until: Date.now() + 800, owner: postTabId(),
    }));
  } catch (e) {}
}
function clearPostPending() {
  try {
    const k = postPendingKey();
    if (k) localStorage.removeItem(k);
  } catch (e) {}
}
function committedPosture(d) {
  const p = (d && d.posture) || {};
  const pace = POSTURE_STOPS_PACE.indexOf(p.pace) >= 0 ? p.pace : POSTURE_STOPS_PACE[0];
  const asking = POSTURE_STOPS_ASKING.indexOf(p.asking) >= 0
    ? p.asking : POSTURE_STOPS_ASKING[0];
  const delivery = POSTURE_STOPS_DELIVERY.indexOf(p.delivery) >= 0
    ? p.delivery : 'instant';
  const orchestration = POSTURE_STOPS_ORCHESTRATION.indexOf(p.orchestration) >= 0
    ? p.orchestration : 'hands-on';
  let dlg = 0;
  try { dlg = Math.max(0, parseInt(p.delegation, 10) || 0); } catch (e) { dlg = 0; }
  return {
    pace, asking, delegation: dlg, delivery, orchestration,
    source: p.source === 'file' ? 'file' : 'derived',
    delegation_label: p.delegation_label || delegationLabel(dlg),
  };
}
function delegationLabel(n) {
  if (n <= 0) return 'own';
  if (n === 1) return 'assist';
  return 'delegate';
}
function paintPostureSelection(draft, snap) {
  document.querySelectorAll('.sgroup.paxis-chips').forEach(g => {
    const axis = g.dataset.axis;
    g.querySelectorAll('.sgbtn').forEach(b => {
      const on = b.dataset.stop === draft[axis];
      b.classList.toggle('on', on);
      b.setAttribute('aria-checked', on ? 'true' : 'false');
    });
    slideIndicator(g, !!snap);
  });
  const val = document.getElementById('pstepval');
  const lab = document.getElementById('psteplabel');
  if (val) val.textContent = String(draft.delegation);
  if (lab) {
    const name = delegationLabel(draft.delegation);
    lab.textContent = name;
    lab.dataset.label = name;
  }
  const dec = document.getElementById('pstepdec');
  const inc = document.getElementById('pstepinc');
  if (dec) dec.disabled = draft.delegation <= 0;
  if (inc) inc.disabled = draft.delegation >= POSTURE_DELEGATION_UI_MAX;
  const src = document.getElementById('posture-src');
  if (src) {
    const live = pendingPostIsLive(readPostPending());
    if (live) {
      // Armed: a posture change is pending. UNCHANGED from #445 — only this
      // state earns words in the slot.
      src.textContent = 'arming override…';
      src.className = 'posture-src file';
    } else {
      // Ambient (#551): both file and derived sources carry the 'remind'
      // link-btn. The old 'override · .dreamwork/posture' / 'derived from run
      // mode' text was ruled useless unless a change is pending.
      src.className = 'posture-src' + (draft.source === 'file' ? ' file' : '');
      src.innerHTML = remindSlotInner();
    }
  }
}
function clearPostArmUI() {
  if (postArmTimer) { clearTimeout(postArmTimer); postArmTimer = null; }
  if (postArmTick) { clearInterval(postArmTick); postArmTick = null; }
  postArmUntil = 0;
  const bar = document.getElementById('pbar');
  const fill = document.getElementById('pbarfill');
  const count = document.getElementById('pcount');
  if (bar) bar.hidden = true;
  if (fill) {
    fill.classList.add('snap');
    fill.style.width = '100%';
  }
  if (count) count.textContent = '';
  paintPosturePin();   // #565: posture arm cleared → re-evaluate the dock
}
function armPostureUI(draft, until, gen) {
  if (postArmTimer) { clearTimeout(postArmTimer); postArmTimer = null; }
  if (postArmTick) { clearInterval(postArmTick); postArmTick = null; }
  const bar = document.getElementById('pbar');
  const fill = document.getElementById('pbarfill');
  const count = document.getElementById('pcount');
  const rm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const remainingMs = () => Math.max(0, until - Date.now());
  const setCount = () => {
    if (gen !== postArmGen) return;
    if (!count) return;
    const s = Math.ceil(remainingMs() / 1000);
    // #674: the params line lists the WHOLE pending point, all five axes —
    // pace · asking · delegation · delivery · orchestration. It had only the
    // first three; he noticed orchestration missing (orchestrator/hands-on,
    // #510). delivery (#342) was absent too, contrary to the brief that
    // described it as present — measured on the pre-#674 build, the line read
    // `arms in 10s · steady · ask · 0`, three values, not four.
    //
    // The `||` defaults mirror committedPosture's absent fallbacks so the line
    // never reads "undefined". They are a floor, NOT the source: every draft
    // that reaches here is built from committedPosture (armPostureDraft,
    // pickPostureAxis, stepPostureDelegation, syncPostureFromData) and so
    // always carries all five. If a draft ever stops carrying one, the
    // fallback prints a value the user never chose and the pytest gate — which
    // evals this expression against its own draft — cannot see it. That is why
    // posturerecuse.mjs clicks the real chips and reads #pcount back.
    const label = draft.pace + ' · ' + draft.asking + ' · ' + draft.delegation
      + ' · ' + (draft.delivery || 'instant')
      + ' · ' + (draft.orchestration || 'hands-on');
    count.textContent = s > 0
      ? `arms in ${s}s · ${label}`
      : `applying ${label}…`;
  };
  setCount();
  if (!rm && bar && fill) {
    bar.hidden = false;
    const left = remainingMs();
    const frac = Math.max(0, Math.min(1, left / RUN_ARM_MS));
    fill.classList.add('snap');
    fill.style.transitionDuration = '0ms';
    fill.style.width = (frac * 100) + '%';
    void fill.offsetWidth;
    fill.style.transitionDuration = Math.max(0, left) + 'ms';
    fill.classList.remove('snap');
    fill.style.width = '0%';
  } else if (bar) {
    bar.hidden = true;
  }
  postArmUntil = until;
  paintPosturePin();   // #565: posture arm live → dock immediately
  postArmTick = setInterval(() => {
    if (gen !== postArmGen) return;
    setCount();
    if (remainingMs() <= 0 && postArmTick) {
      clearInterval(postArmTick); postArmTick = null;
    }
  }, 250);
  postArmTimer = setTimeout(() => {
    if (gen !== postArmGen) return;
    if (postArmShouldCommit) commitPosture(draft, gen);
    else {
      clearPostArmUI();
      setTimeout(() => {
        if (gen !== postArmGen) return;
        const p = readPostPending();
        const cur = committedPosture(data);
        if (p && !p.phase && p.pace === draft.pace
            && p.asking === draft.asking
            && p.delegation === draft.delegation
            && (cur.pace !== draft.pace || cur.asking !== draft.asking
                || cur.delegation !== draft.delegation
                || cur.source !== 'file'))
          commitPosture(draft, gen, { orphan: true });
        else
          paintPostureSelection(committedPosture(data), true);
      }, 1500);
    }
  }, remainingMs());
}
function claimPostPending(draft, { orphan = false } = {}) {
  try {
    const k = postPendingKey();
    if (!k) return false;
    const raw = localStorage.getItem(k);
    if (!raw) return false;
    const p = JSON.parse(raw);
    if (!p || p.phase === 'cancel') return false;
    if (p.pace !== draft.pace || p.asking !== draft.asking
        || p.delegation !== draft.delegation) return false;
    if (p.owner && p.owner !== postTabId()) {
      if (!orphan) return false;
      if (typeof p.until === 'number' && Date.now() < p.until + 1000)
        return false;
    }
    localStorage.removeItem(k);
    return true;
  } catch (e) { return false; }
}
async function commitPosture(draft, gen, opts) {
  if (gen !== postArmGen) return;
  const msg = document.getElementById('pmsg');
  const orphan = !!(opts && opts.orphan);
  if (!claimPostPending(draft, { orphan })) {
    postArmShouldCommit = false;
    clearPostArmUI();
    paintPostureSelection(committedPosture(data), true);
    return;
  }
  let ok = false;
  let body = null;
  try {
    const res = await fetch('/posture', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pace: draft.pace,
        asking: draft.asking,
        delegation: draft.delegation,
        delivery: draft.delivery,
        orchestration: draft.orchestration,
        from: location.pathname + location.search,
        tab: postTabId(),
        orphan: orphan || false,
      }),
    });
    const rv = await writeVerdict(res);
    ok = rv.landed;
    body = rv;
  } catch (e) { ok = false; }
  if (gen !== postArmGen) return;
  if (ok) {
    postArmShouldCommit = false;
    clearPostArmUI();
    if (msg) msg.textContent = '';
    if (data) {
      data.posture = {
        pace: draft.pace,
        asking: draft.asking,
        delegation: draft.delegation,
        delivery: draft.delivery,
        orchestration: draft.orchestration,
        source: 'file',
        delegation_label: delegationLabel(draft.delegation),
      };
    }
    postDraft = null;
    paintPostureSelection(committedPosture(data), true);
  } else if (msg) {
    msg.textContent = 'could not save the posture — the write was refused';
    clearPostPending();
    postArmShouldCommit = false;
    clearPostArmUI();
    postDraft = null;
    paintPostureSelection(committedPosture(data), true);
  }
}
function armPostureDraft(next) {
  const msg = document.getElementById('pmsg');
  if (msg) msg.textContent = '';
  const cur = committedPosture(data);
  // Re-selecting the fully committed point cancels any pending arm.
  if (next.pace === cur.pace && next.asking === cur.asking
      && next.delegation === cur.delegation
      && next.delivery === cur.delivery
      && next.orchestration === cur.orchestration && cur.source === 'file') {
    postArmGen++;
    postArmShouldCommit = false;
    writePostCancel(cur);
    clearPostArmUI();
    postDraft = null;
    paintPostureSelection(cur, false);
    setTimeout(() => {
      const p = readPostPending();
      if (p && p.phase === 'cancel') clearPostPending();
    }, 100);
    return;
  }
  const until = Date.now() + RUN_ARM_MS;
  postArmGen++;
  const gen = postArmGen;
  postArmShouldCommit = true;
  postDraft = {
    pace: next.pace, asking: next.asking, delegation: next.delegation,
    delivery: next.delivery, orchestration: next.orchestration,
    source: 'file',
  };
  writePostPending(postDraft, until, postTabId());
  paintPostureSelection(postDraft, false);
  armPostureUI(postDraft, until, gen);
}
function pickPostureAxis(axis, stop) {
  if (axis === 'pace' && POSTURE_STOPS_PACE.indexOf(stop) < 0) return;
  if (axis === 'asking' && POSTURE_STOPS_ASKING.indexOf(stop) < 0) return;
  if (axis === 'delivery' && POSTURE_STOPS_DELIVERY.indexOf(stop) < 0) return;
  if (axis === 'orchestration'
      && POSTURE_STOPS_ORCHESTRATION.indexOf(stop) < 0) return;
  const base = postDraft || committedPosture(data);
  const next = {
    pace: base.pace, asking: base.asking, delegation: base.delegation,
    delivery: base.delivery, orchestration: base.orchestration,
  };
  next[axis] = stop;
  armPostureDraft(next);
}
function stepPostureDelegation(delta) {
  const base = postDraft || committedPosture(data);
  let n = base.delegation + delta;
  if (n < 0) n = 0;
  if (n > POSTURE_DELEGATION_UI_MAX) n = POSTURE_DELEGATION_UI_MAX;
  armPostureDraft({
    pace: base.pace, asking: base.asking, delegation: n,
    delivery: base.delivery, orchestration: base.orchestration,
  });
}
function posturePicker(d) {
  const pending = readPostPending();
  const arm = pendingPostIsLive(pending) ? pending : null;
  const cur = arm
    ? { pace: arm.pace, asking: arm.asking, delegation: arm.delegation,
        delivery: arm.delivery || 'instant',
        orchestration: arm.orchestration || 'hands-on', source: 'file' }
    : committedPosture(d);
  if (arm) postDraft = cur;
  const paceChips = POSTURE_STOPS_PACE.map(n =>
    `<button type="button" role="radio" class="sgbtn pchip` +
    `${n === cur.pace ? ' on' : ''}" data-stop="${esc(n)}"` +
    ` aria-checked="${n === cur.pace ? 'true' : 'false'}"` +
    ` aria-describedby="pdesc-text"` +
    ` onclick="pickPostureAxis('pace','${esc(n)}')">${esc(n)}</button>`
  ).join('');
  // Asking keeps all FOUR stops — his dictation. The control is asymmetric
  // on purpose; do not compress to three for tidy geometry.
  const askChips = POSTURE_STOPS_ASKING.map(n =>
    `<button type="button" role="radio" class="sgbtn pchip` +
    `${n === cur.asking ? ' on' : ''}" data-stop="${esc(n)}"` +
    ` aria-checked="${n === cur.asking ? 'true' : 'false'}"` +
    ` aria-describedby="pdesc-text"` +
    ` onclick="pickPostureAxis('asking','${esc(n)}')">${esc(n)}</button>`
  ).join('');
  // #342: delivery — a fourth axis row reusing the pace/asking chip idiom
  // verbatim (same .sgbtn.pchip class, same pickPostureAxis, the shared arm).
  // No second gesture; the chip arrives and changes state the same way.
  const deliveryChips = POSTURE_STOPS_DELIVERY.map(n =>
    `<button type="button" role="radio" class="sgbtn pchip` +
    `${n === cur.delivery ? ' on' : ''}" data-stop="${esc(n)}"` +
    ` aria-checked="${n === cur.delivery ? 'true' : 'false'}"` +
    ` aria-describedby="pdesc-text"` +
    ` onclick="pickPostureAxis('delivery','${esc(n)}')">${esc(n)}</button>`
  ).join('');
  // #510: orchestration — a fifth axis row, the same chip idiom again. The
  // axis is inert until a consumer reads it; the control lands now so the
  // dial is settable the same way every other axis is.
  const orchChips = POSTURE_STOPS_ORCHESTRATION.map(n =>
    `<button type="button" role="radio" class="sgbtn pchip` +
    `${n === cur.orchestration ? ' on' : ''}" data-stop="${esc(n)}"` +
    ` aria-checked="${n === cur.orchestration ? 'true' : 'false'}"` +
    ` aria-describedby="pdesc-text"` +
    ` onclick="pickPostureAxis('orchestration','${esc(n)}')">${esc(n)}</button>`
  ).join('');
  const dlgLab = delegationLabel(cur.delegation);
  // #551: the slot is 'arming override…' while a change is pending (arm),
  // else the 'remind' link-btn (remindSlotInner reads the module-scope
  // cooldown so a live re-render mid-cooldown repaints the confirming state).
  const srcInner = arm ? esc('arming override…') : remindSlotInner();
  // #488: source chip beside the heading; pdesc always in flow (no hidden).
  return `<section class="posture" id="posture" aria-label="posture">` +
    `<div class="posture-head">` +
    `<div class="label">posture</div>` +
    `<div class="posture-src${cur.source === 'file' ? ' file' : ''}"` +
    ` id="posture-src">${srcInner}</div></div>` +
    `<div class="posture-axes">` +
    `<div class="paxis" data-axis="pace">` +
    `<div class="paxis-lab" id="pace-lab">pace</div>` +
    `<div class="sgroup paxis-chips" role="radiogroup" data-axis="pace"` +
    ` aria-labelledby="pace-lab">` +
    `<div class="sgind"></div>${paceChips}</div></div>` +
    `<div class="paxis" data-axis="asking">` +
    `<div class="paxis-lab" id="asking-lab">asking</div>` +
    `<div class="sgroup paxis-chips" role="radiogroup" data-axis="asking"` +
    ` aria-labelledby="asking-lab">` +
    `<div class="sgind"></div>${askChips}</div></div>` +
    `<div class="paxis" data-axis="delegation">` +
    `<div class="paxis-lab" id="dlg-lab">delegation · avg concurrency target</div>` +
    `<div class="pstep" role="group" aria-labelledby="dlg-lab">` +
    `<button type="button" class="pstepbtn" id="pstepdec"` +
    ` aria-label="decrease delegation target"` +
    ` onclick="stepPostureDelegation(-1)"` +
    `${cur.delegation <= 0 ? ' disabled' : ''}>−</button>` +
    `<span class="pstepval" id="pstepval" aria-live="polite">` +
    `${esc(String(cur.delegation))}</span>` +
    `<button type="button" class="pstepbtn" id="pstepinc"` +
    ` aria-label="increase delegation target"` +
    ` onclick="stepPostureDelegation(1)"` +
    `${cur.delegation >= POSTURE_DELEGATION_UI_MAX ? ' disabled' : ''}>+</button>` +
    `<span class="psteplabel" id="psteplabel" data-label="${esc(dlgLab)}">` +
    `${esc(dlgLab)}</span></div>` +
    `<div class="pstephint">target, not a cap · 0 is occasional, not forbidden</div>` +
    `</div></div>` +
    // #342 delivery axis — same .paxis/.paxis-chips shape as pace/asking.
    `<div class="paxis" data-axis="delivery">` +
    `<div class="paxis-lab" id="delivery-lab">delivery · when interrupted</div>` +
    `<div class="sgroup paxis-chips" role="radiogroup" data-axis="delivery"` +
    ` aria-labelledby="delivery-lab">` +
    `<div class="sgind"></div>${deliveryChips}</div></div>` +
    // #510 orchestration axis — same .paxis/.paxis-chips shape as pace/asking.
    `<div class="paxis" data-axis="orchestration">` +
    `<div class="paxis-lab" id="orchestration-lab">orchestration · coordinator role</div>` +
    `<div class="sgroup paxis-chips" role="radiogroup" data-axis="orchestration"` +
    ` aria-labelledby="orchestration-lab">` +
    `<div class="sgind"></div>${orchChips}</div></div>` +
    `<div class="pdesc" id="pdesc" role="tooltip" aria-hidden="true">` +
    `<span class="pdesc-text" id="pdesc-text"></span></div>` +
    // #674: .parm (the bar + "arms in …" line) is emitted OUTSIDE the
    // .posture <section> so its position:sticky bounds to the tall dashboard
    // container, not the short section. Sticky is bounded by the parent's box,
    // so a sticky child of .posture clamps to .posture's top edge and never
    // reaches the viewport bottom — measured: armed #parm stuck at top=958
    // (≈ .posture's top) vs viewport bottom 700. As a sibling of the section,
    // .parm pins to viewport bottom correctly. The axes chips (which he said
    // should NOT dock) stay inside .posture and scroll away.
    `</section>` +
    `<div class="parm" id="parm">` +
    `<div class="pbar" id="pbar" hidden aria-hidden="true">` +
    `<div class="pbarfill" id="pbarfill"></div></div>` +
    `<span class="pcount" id="pcount" aria-live="polite"></span>` +
    // #569: the deploy update countdown is recused here from #fmsg — the
    // posture row's remaining horizontal space, after the posture countdown.
    `<span class="pdep" id="pdep" aria-live="polite"></span></div>` +
    `<div class="pmsg" id="pmsg" aria-live="polite"></div>`;
}
/* Shared description for posture stops — presentation only; never arms. */
let pdescKey = null;
let pdescPendingKey = null;
let pdescMorphGen = 0;
let pdescHideTimer = null;
let pdescMorphTimer = null;
function pdescReduced() {
  return matchMedia('(prefers-reduced-motion: reduce)').matches;
}
function postDescFor(axis, stop) {
  if (axis === 'pace' && POSTURE_PACE_DESC[stop]) return POSTURE_PACE_DESC[stop];
  if (axis === 'asking' && POSTURE_ASKING_DESC[stop]) return POSTURE_ASKING_DESC[stop];
  if (axis === 'delegation' && POSTURE_DELEGATION_DESC[stop])
    return POSTURE_DELEGATION_DESC[stop];
  if (axis === 'delivery' && POSTURE_DELIVERY_DESC[stop])
    return POSTURE_DELIVERY_DESC[stop];
  if (axis === 'orchestration' && POSTURE_ORCHESTRATION_DESC[stop])
    return POSTURE_ORCHESTRATION_DESC[stop];
  return '';
}
function hidePostDesc(immediate) {
  const shell = document.getElementById('pdesc');
  const text = document.getElementById('pdesc-text');
  if (!shell) return;
  if (pdescHideTimer) { clearTimeout(pdescHideTimer); pdescHideTimer = null; }
  if (pdescMorphTimer) { clearTimeout(pdescMorphTimer); pdescMorphTimer = null; }
  // #488: shell stays in flow; idle is opacity:0, never hidden/display:none.
  if (!shell.classList.contains('open')) {
    pdescKey = null; pdescPendingKey = null; return;
  }
  pdescMorphGen++;
  pdescPendingKey = null;
  const rm = !!immediate || pdescReduced();
  const finish = () => {
    shell.classList.remove('open', 'pose', 'depart');
    shell.setAttribute('aria-hidden', 'true');
    if (text) { text.textContent = ''; text.classList.remove('out', 'in'); }
    pdescKey = null; pdescPendingKey = null;
  };
  if (rm) { finish(); return; }
  shell.classList.add('depart');
  const onEnd = e => {
    if (e.target !== shell || e.propertyName !== 'opacity') return;
    shell.removeEventListener('transitionend', onEnd);
    finish();
  };
  shell.addEventListener('transitionend', onEnd);
  pdescHideTimer = setTimeout(finish, 550);
}
function showPostDesc(axis, stop) {
  const body = postDescFor(axis, stop);
  if (!body) return;
  const shell = document.getElementById('pdesc');
  const text = document.getElementById('pdesc-text');
  if (!shell || !text) return;
  if (pdescHideTimer) { clearTimeout(pdescHideTimer); pdescHideTimer = null; }
  shell.classList.remove('depart');
  const key = axis + ':' + stop;
  const rm = pdescReduced();
  const first = !shell.classList.contains('open');
  if (first) {
    pdescMorphGen++;
    if (pdescMorphTimer) { clearTimeout(pdescMorphTimer); pdescMorphTimer = null; }
    text.classList.remove('out', 'in');
    text.textContent = body;
    shell.dataset.key = key;
    shell.setAttribute('aria-hidden', 'false');
    shell.classList.add('open');
    if (rm) shell.classList.remove('pose');
    else {
      shell.classList.add('pose');
      void shell.offsetWidth;
      shell.classList.remove('pose');
    }
    pdescKey = key;
    pdescPendingKey = null;
    return;
  }
  if (key === pdescKey && !pdescPendingKey) return;
  pdescPendingKey = key;
  if (rm) {
    text.textContent = body;
    shell.dataset.key = key;
    pdescKey = key;
    pdescPendingKey = null;
    return;
  }
  // dissolve then resolve — shell geometry fixed
  text.classList.add('out');
  const gen = ++pdescMorphGen;
  if (pdescMorphTimer) clearTimeout(pdescMorphTimer);
  pdescMorphTimer = setTimeout(() => {
    if (gen !== pdescMorphGen) return;
    const k = pdescPendingKey || pdescKey;
    const [ax, st] = (k || '').split(':');
    const b = postDescFor(ax, st);
    if (!b) return;
    text.textContent = b;
    shell.dataset.key = k;
    pdescKey = k;
    pdescPendingKey = null;
    text.classList.remove('out');
    text.classList.add('in');
    void text.offsetWidth;
    text.classList.remove('in');
  }, 340);
}
document.addEventListener('pointerover', e => {
  const b = e.target && e.target.closest && e.target.closest('#posture .pchip');
  if (!b) return;
  const g = b.closest('.paxis-chips');
  if (!g) return;
  showPostDesc(g.dataset.axis, b.dataset.stop);
});
document.addEventListener('focusin', e => {
  const b = e.target && e.target.closest && e.target.closest('#posture .pchip');
  if (!b) return;
  const g = b.closest('.paxis-chips');
  if (!g) return;
  showPostDesc(g.dataset.axis, b.dataset.stop);
});
document.addEventListener('pointerout', e => {
  const sec = document.getElementById('posture');
  if (!sec) return;
  setTimeout(() => {
    if (sec.matches(':hover')) return;
    hidePostDesc();
  }, 0);
});
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  const shell = document.getElementById('pdesc');
  if (!shell || !shell.classList.contains('open')) return;
  hidePostDesc();
});
// Stepper hover: show the label's description (own/assist/delegate)
document.addEventListener('pointerover', e => {
  const lab = e.target && e.target.closest && e.target.closest('#psteplabel');
  if (!lab) return;
  showPostDesc('delegation', lab.dataset.label || lab.textContent);
});
function syncPostureFromData() {
  const pending = readPostPending();
  if (pending && pending.phase === 'cancel') {
    if (document.getElementById('posture'))
      paintPostureSelection({
        pace: pending.pace, asking: pending.asking,
        delegation: pending.delegation, delivery: pending.delivery || 'instant',
        orchestration: pending.orchestration || 'hands-on',
        source: 'file',
      }, true);
    postArmShouldCommit = false;
    clearPostArmUI();
    return;
  }
  if (pending && !pending.phase) {
    if (pending.owner && pending.owner === postTabId())
      postArmShouldCommit = true;
    const draft = {
      pace: pending.pace, asking: pending.asking,
      delegation: pending.delegation, delivery: pending.delivery || 'instant',
      orchestration: pending.orchestration || 'hands-on',
      source: 'file',
    };
    postDraft = draft;
    if (document.getElementById('posture'))
      paintPostureSelection(draft, true);
    if (pendingPostIsLive(pending)) {
      postArmGen++;
      armPostureUI(draft, pending.until, postArmGen);
    } else if (postArmShouldCommit || !pending.owner
               || pending.owner === postTabId()) {
      postArmGen++;
      commitPosture(draft, postArmGen, { orphan: !postArmShouldCommit });
    } else {
      postArmGen++;
      const gen = postArmGen;
      setTimeout(() => {
        if (gen !== postArmGen) return;
        const p = readPostPending();
        const cur = committedPosture(data);
        if (p && !p.phase
            && (cur.pace !== p.pace || cur.asking !== p.asking
                || cur.delegation !== p.delegation
                || cur.delivery !== (p.delivery || 'instant')
                || cur.orchestration !== (p.orchestration || 'hands-on')
                || cur.source !== 'file'))
          commitPosture({
            pace: p.pace, asking: p.asking, delegation: p.delegation,
            delivery: p.delivery || 'instant',
            orchestration: p.orchestration || 'hands-on',
          }, gen, { orphan: true });
      }, 200);
    }
    return;
  }
  postDraft = null;
  if (document.getElementById('posture'))
    paintPostureSelection(committedPosture(data), true);
  postArmShouldCommit = false;
  clearPostArmUI();
}
window.addEventListener('storage', e => {
  if (!e.key || e.key.indexOf('dw:posture-pending:') !== 0) return;
  if (!data || e.key !== postPendingKey()) return;
  const pending = readPostPending();
  postArmGen++;
  if (!pending) {
    postArmShouldCommit = false;
    clearPostArmUI();
    return;
  }
  if (pending.phase === 'cancel') {
    postArmShouldCommit = false;
    clearPostArmUI();
    paintPostureSelection(committedPosture(data), true);
    return;
  }
  postArmShouldCommit = false;
  const draft = {
    pace: pending.pace, asking: pending.asking,
    delegation: pending.delegation, delivery: pending.delivery || 'instant',
    orchestration: pending.orchestration || 'hands-on',
    source: 'file',
  };
  postDraft = draft;
  paintPostureSelection(draft, true);
  armPostureUI(draft, pending.until, postArmGen);
});
/* Set from the route change, from the tick, AND from the 1s age sweep — the
   liveness word drifts with the wall clock and nothing on disk changes when
   a loop stops, so it needs the same seam the commit ages use (#132).
   Assigning only on a real change keeps that free. */
function applyTitle() {
  const t = pageTitle(view, data);
  if (t && document.title !== t) document.title = t;
}

function routeOf(loc) {
  if (loc.pathname === '/questions') return { name: 'questions', param: null };
  if (loc.pathname === '/answers') return { name: 'answers', param: null };
  if (loc.pathname === '/file') {
    const sp = new URLSearchParams(loc.search);
    /* #252 — the view mode is part of the ROUTE, not a toggle the page
       remembers, so a copied or shared link preserves the intent it was
       copied with. Anything that is not `source` is rendered: an unknown
       value must not mint a third state, and `?view=` on a non-markdown path
       is simply inert (the switch is markdown-only and its body is verbatim
       either way). */
    return { name: 'file', param: sp.get('p'),
             mode: sp.get('view') === 'source' ? 'source' : 'rendered' };
  }
  if (loc.pathname === '/review') {
    const sp = new URLSearchParams(loc.search);
    return { name: 'review', param: sp.get('p'), q: sp.get('q') };
  }
  if (loc.pathname === '/question') {
    const sp = new URLSearchParams(loc.search);
    // the key is the question's TITLE identity — the same string data-qid
    // carries — so it survives everything the loop's churn does short of a
    // retitle (#452)
    return { name: 'question', param: sp.get('qid') };
  }
  // #484 — no param: the listing of built research artifacts; ?p=<name>:
  // one artifact in the review view's iframe idiom.
  if (loc.pathname === '/research') {
    const sp = new URLSearchParams(loc.search);
    return { name: 'research', param: sp.get('p') };
  }
  // #545 — the full reviews listing the dashboard's cap points at.
  if (loc.pathname === '/reviews') return { name: 'reviews', param: null };
  // #562 — /chat/<id>: one topic chat's conversation. The id is the path
  // segment after /chat/; /chat with no id degrades to the page's not-found
  // voice (a chat is its own subject — the navigate principle).
  if (loc.pathname === '/chat' || loc.pathname.startsWith('/chat/')) {
    const seg = loc.pathname.slice(6);  // after '/chat/'
    return { name: 'chat', param: seg ? decodeURIComponent(seg) : null };
  }
  return { name: 'dashboard', param: null };
}
/* THE ONE PLACE `data` IS REPLACED, and it is a function rather than an
   assignment because there are TWO fetchers — the first paint (`ensureData`)
   and the live tick — so anything that must react to new data has to be hung
   off both or it silently works on one path only.

   #86 is how that was found. The composer's plugin vocabulary was notified
   from the tick alone, which looks like the live path and is not the first
   one: `ensureData` sets `lastMtime` as it fetches, so the first tick sees
   nothing changed and does nothing, and the commands never arrived at all on
   a freshly opened page. Adding a second call site would have fixed the
   symptom and left the next reader the same trap, which is #191's lesson
   about one gesture spelled two ways, aimed at data instead of at motion. */
function setData(next) {
  data = next;
  // WHICH PLUGINS RESOLVED IS A PROPERTY OF THE MACHINE, not of watch.py, so
  // the composer's vocabulary can change under a page that is already open
  // (#86). It compares whole and returns immediately on the ticks — nearly
  // all of them — where the declared set has not moved.
  if (window.dwPluginCommands) window.dwPluginCommands(data.plugin_commands);
  return data;
}
async function ensureData() {
  if (data) return data;
  try {
    const { gen, mtime } = parseMtime(await (await fetch('/mtime')).text());
    if (serverGen === null) serverGen = gen;
    lastMtime = mtime;
    fetchedAt = Date.now();
    if (burnStepPref === null) burnStepPref = loadBurnStepPref();
    setData(await (await fetch(dataJsonUrl())).json());
  } catch (e) {}
  return data;
}
async function fetchFile(param) {
  if (fileCache.param === param) return fileCache.fetched;
  let fetched = null;
  try {
    const res = await fetch('/filedata?p=' + encodeURIComponent(param || ''));
    if (res.ok) {
      const j = await res.json();
      if (j && j.binary) {
        fetched = { binary: true, kind: j.kind, mime: j.mime, size: j.size };
      } else if (j && typeof j.content === 'string') {
        /* #351: `hl` is the server's highlighted markup for a known source
           extension (review_artifact's #339 scanner, cached per file
           version). Absent for everything else; the client never tokenises
           and never invents markup — it only chooses between the server's
           two renderings. */
        fetched = { text: j.content,
                    hl: typeof j.hl === 'string' ? j.hl : null };
      }
    }
  } catch (e) {}
  fileCache = { param, fetched };
  return fetched;
}
async function buildCurrent() {
  /* #522: the file view also needs `data` — linkify / linkifyMd consult
     `data.linkable_paths` to decide which targets to promote. Skipping
     ensureData here left a cold /file load with data===null, so every
     known path stayed literal (and any later tick only re-rendered on an
     mtime change). Same closed set as every other prose surface. */
  if (view.name === 'file') {
    await ensureData();
    return buildFile(view.param, await fetchFile(view.param), view.mode);
  }
  // #562 — /chat/<id> needs ensureData (the chrome heading reads d.chats for
  // the derived title) AND the fetched transcript (not in /data.json).
  if (view.name === 'chat') {
    await ensureData();
    return buildChat(await fetchChat(view.param));
  }
  const d = await ensureData();
  if (view.name === 'review') return buildReview(view.param, view.q, d);
  if (view.name === 'question') return buildQuestion(view.param, d);
  if (view.name === 'research') return buildResearch(view.param, d);
  if (view.name === 'reviews') return buildReviews(d);
  if (!d) return '<div class="dim">loading…</div>';
  if (view.name === 'questions') return buildQuestions(d);
  if (view.name === 'answers') return buildAnswers(d);
  return buildDashboard(d);
}
/* #505 p2 — KEPT (not absorbed): #askbox is a single node kept by id under
   reconciliation, so its value/caret/scroll/focus would mostly ride the kept
   node — but the box AUTOGROWS (fitText on input), setting an inline
   style.height that morphAttrs clobbers to the server floor each tick, and no
   post-morph path re-fits it (bindAskDraft restores value only). This pair
   re-applies that height (and the silent scroll clamp) for a focused AND an
   unfocused box. The belt stays until the height is re-fit another way. */
function snapshotAskState() {
  const box = document.getElementById('askbox');
  if (!box || (!box.value && box !== document.activeElement)) return null;
  return {value:box.value, focus:box === document.activeElement,
          start:box.selectionStart, end:box.selectionEnd, scroll:box.scrollTop,
          height:box.style.height};
}
function restoreAskState(saved) {
  if (!saved) return;
  const box = document.getElementById('askbox'); if (!box) return;
  box.value = saved.value;
  putScroll(box, saved.scroll);          // same silent clamp as the card's
  if (saved.height) box.style.height = saved.height;
  try { box.setSelectionRange(saved.start, saved.end); } catch (e) {}
  if (saved.focus) refocus(box);
}
/* #505 p2: #523 (a focused input/textarea inside #view surviving a tick) is
   now carried by keyed reconciliation, not a hand snapshot/restore pair. The
   node is KEPT by its id, so focus, caret and selection ride the node, and
   reconcileGuard's focus-gated value-stamp keeps mid-edit text from being
   clobbered to the server/default. The old snapshotViewInputs/restoreViewInputs
   pair is deleted. Give any new field a stable id and it inherits this. */
/* #459: bind #askbox to DraftStore (ask:main). Snapshot (#118) carries a
   tick; storage carries a reload. bind is re-entrant-safe: unbind first so a
   tick re-render does not stack input listeners. Restores only into an empty
   box (live outranks). Silent — the text in the box is the statement. */
function bindAskDraft() {
  const box = document.getElementById('askbox');
  if (!box) return;
  const lid = DraftStore.id('ask', 'main');
  if (box.__dwDraftBound) DraftStore.unbind(box);
  DraftStore.bind(box, lid);
  DraftStore.restore(lid, box);
}
/* #577 — bind the /chat/<id> reply box to a CHAT-SPECIFIC draft key
   (chat:<id>, never the main composer's or the ask box's), so a half-typed
   reply survives a reload of the page alone and never collides with a
   steering thought or a question. The same discipline as bindAskDraft:
   unbind first so a kept #chatreplybox (held by id under #523 reconciliation)
   is not double-bound across a tick; restore only into an empty box (live
   outranks storage, #118). view.param is the route's chat id. */
function bindChatReplyDraft() {
  const box = document.getElementById('chatreplybox');
  if (!box) return;
  const chatId = (view && view.param) || box.form && box.form.getAttribute('data-chat') || '';
  if (!chatId) return;
  const lid = DraftStore.id('chat', chatId);
  if (box.__dwDraftBound) DraftStore.unbind(box);
  DraftStore.bind(box, lid);
  DraftStore.restore(lid, box);
  fitText(box, false);   // #708: size to the restored value, and re-fit a kept
                         // box whose inline height a /mtime tick clobbered
}
/* ── DraftStore (#269 module + #459 consumers) ───────────────────────────
   One deep module every text surface consumes. localStorage-backed (IDB is
   deferred: sync write on input cannot fail mid-keystroke; an async store
   would make the acute path worse than today). Rules, measured not assumed
   (draft-durability-status.md / 6a6ddff):

     - save on every `input`, no debounce;
     - restore only into a mounted element that declares its logical id —
       never fuzzy-match (wrong-box restore is worse than loss);
     - clear only on durable success via isDurable (close/blur/reject keep it);
     - a live box outranks storage (#118);
     - every storage call is try/catch — degrade to no-persistence, never a
       broken box;
     - cards key on the question TITLE (data-qid), not a positional index.

   logicalId = kind + ":" + scopeKey inside data.target. New key shape:
     dw:draft:v1:<target>:<logicalId>
   Dual-read of the pre-module keys so an existing browser draft is never
   orphaned by the extraction:
     card:<title>     ← dw:adraft:<target>:<title>
     composer:main    ← dw:draft:<target>
   On save through the new API the old key is removed after the new one is
   written (dual-read, not dual-write forever). Cross-tab (C1) and 30-day GC
   leave seams only — not built here. #263 receipt is isDurable's future
   body; today it prefers writeVerdict.landed when attached, else res.ok. */
const DraftStore = (() => {
  const tgt = () => (typeof data !== 'undefined' && data && data.target) || '';
  const id = (kind, scopeKey) => {
    if (!kind) return '';
    return kind + ':' + (scopeKey == null ? '' : String(scopeKey));
  };
  // primary key — design §1 storageKey; t first so legacy payload checks hold
  const v1Key = logicalId => {
    const t = tgt();
    return t && logicalId ? 'dw:draft:v1:' + t + ':' + logicalId : '';
  };
  // pre-module keys (still dual-read; string shapes kept for tests + migration)
  const legacyKey = logicalId => {
    const t = tgt();
    if (!t || !logicalId) return '';
    if (logicalId.indexOf('card:') === 0)
      return 'dw:adraft:' + t + ':' + logicalId.slice(5);
    if (logicalId === 'composer:main')
      return 'dw:draft:' + t;
    return '';
  };
  const parseRec = raw => {
    if (!raw) return null;
    let d = null;
    try { d = JSON.parse(raw); } catch (e) { return null; }
    if (!d || typeof d.t !== 'string' || !d.t) return null;
    return d;
  };
  const readRaw = logicalId => {
    const k1 = v1Key(logicalId);
    if (!k1) return null;
    try {
      const n = localStorage.getItem(k1);
      if (n) return { raw: n, from: 'v1', key: k1 };
      const lo = legacyKey(logicalId);
      if (lo) {
        const o = localStorage.getItem(lo);
        if (o) return { raw: o, from: 'legacy', key: lo };
      }
    } catch (e) { /* storage unavailable */ }
    return null;
  };
  function get(logicalId) {
    const hit = readRaw(logicalId);
    if (!hit) return null;
    const d = parseRec(hit.raw);
    if (!d) return null;
    return {
      v: d.v || 1, logicalId, project: tgt(), text: d.t,
      updatedAt: d.at || 0, meta: d.k ? { kindHint: d.k } : {},
      attemptId: d.aid || null,
      _from: hit.from, _key: hit.key
    };
  }
  function save(logicalId, text, meta) {
    const k1 = v1Key(logicalId); if (!k1) return;
    try {
      if (text) {
        const rec = { t: text };
        if (meta && meta.kindHint) rec.k = meta.kindHint;
        rec.v = 1;
        rec.at = Date.now();
        // #274: keep the per-attempt id only while the text it was minted for
        // is unchanged. An edit after a failure is a NEW composition, so the
        // next submit mints fresh and dedupes against nothing; an in-flight
        // double-click sends the same id twice and the journal dedupes the
        // second. Reading the CURRENT record (not the one being built) is what
        // decides — a re-save of identical text keeps the id alive.
        const prev = get(logicalId);
        if (prev && prev.attemptId && prev.text === text) rec.aid = prev.attemptId;
        localStorage.setItem(k1, JSON.stringify(rec));
        // migrate: once the new key holds the truth, drop the old shape so a
        // second tab does not re-promote a cleared draft from legacy alone
        const lo = legacyKey(logicalId);
        if (lo) try { localStorage.removeItem(lo); } catch (e2) {}
      } else {
        localStorage.removeItem(k1);
        const lo = legacyKey(logicalId);
        if (lo) localStorage.removeItem(lo);
      }
    } catch (e) { /* storage unavailable; the live box is unaffected */ }
  }
  function restore(logicalId, el) {
    if (!logicalId || !el || el.value) return;  // live outranks (#118)
    const rec = get(logicalId);
    if (!rec || !rec.text) return;
    el.value = rec.text;
    if (el.dataset) el.dataset.draftId = logicalId;
  }
  function clear(logicalId) {
    const k1 = v1Key(logicalId); if (!k1) return;
    try {
      localStorage.removeItem(k1);
      const lo = legacyKey(logicalId);
      if (lo) localStorage.removeItem(lo);
    } catch (e) {}
  }
  /* receipt seam: prefer writeVerdict.landed (rejected 202 is res.ok true but
     not durable — E5b). Fall back to res.ok for call sites without _dwv.
     #263 second gate may replace this body later; consumers only call clear
     after isDurable says yes. */
  function isDurable(res) {
    if (!res) return false;
    if (res._dwv) return !!res._dwv.landed;
    return !!res.ok;
  }
  /* #274: mint a v4 UUID. crypto.randomUUID is the clean path but is gated to
     secure contexts (https / loopback); the dashboard is reached over LAN http
     too, so getRandomValues — available in every context — is the real engine
     and Math.random the last resort. Never empty: an empty id means the server
     mints a fresh per-request UUID and a retry is a distinct action (the bug). */
  function _mintId() {
    try { if (crypto.randomUUID) return crypto.randomUUID(); } catch (e) {}
    try {
      if (crypto.getRandomValues) {
        const b = crypto.getRandomValues(new Uint8Array(16));
        b[6] = (b[6] & 0x0f) | 0x40; b[8] = (b[8] & 0x3f) | 0x80;
        const h = x => ('0' + x.toString(16)).slice(-2);
        return h(b[0]) + h(b[1]) + h(b[2]) + h(b[3]) + '-' +
               h(b[4]) + h(b[5]) + '-' + h(b[6]) + h(b[7]) + '-' +
               h(b[8]) + h(b[9]) + '-' +
               h(b[10]) + h(b[11]) + h(b[12]) + h(b[13]) + h(b[14]) + h(b[15]);
      }
    } catch (e) {}
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
      const r = Math.random() * 16 | 0;
      return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
  }
  /* #274: the per-attempt idempotency key, one per composition. Sent as
     X-Client-Action-Id so the journal dedupes a retry or double-click of the
     SAME attempt; cleared with the draft on durable landed (a failed send
     keeps both, so his retry dedupes against the first). Dropped by save()
     when the text changes, so an edit after a failure mints fresh and never
     collides with the abandoned attempt. Lives IN the draft record, so it
     survives a restart beside the words it was minted for. */
  function attemptId(logicalId) {
    const k1 = v1Key(logicalId);
    if (!k1) return _mintId();          // no target partition: unsynced, still unique
    try {
      const prev = get(logicalId);
      if (prev && prev.attemptId) return prev.attemptId;
      const aid = _mintId();
      if (prev) {
        // stamp the id onto the existing draft without disturbing its text
        const hit = readRaw(logicalId);
        if (hit) {
          const d = parseRec(hit.raw);
          if (d) { d.aid = aid; localStorage.setItem(k1, JSON.stringify(d)); }
        }
      }
      // no draft record: nothing to persist beside (no text to retry), so the
      // id is unsynced — still correct for the in-flight double-click in hand.
      return aid;
    } catch (e) { return _mintId(); }
  }
  // bind: input→save, declare data-draft-id. No debounce. opts.meta() optional.
  function bind(el, logicalId, opts) {
    if (!el || !logicalId) return;
    el.dataset.draftId = logicalId;
    const onInput = () => {
      const meta = opts && typeof opts.meta === 'function' ? opts.meta() : null;
      save(logicalId, el.value, meta || undefined);
    };
    el.addEventListener('input', onInput);
    el.__dwDraftBound = { logicalId, onInput };
  }
  function unbind(el) {
    if (!el || !el.__dwDraftBound) return;
    el.removeEventListener('input', el.__dwDraftBound.onInput);
    delete el.__dwDraftBound;
  }
  // seams for later increments — no-op / stubs, not built here
  function forget(logicalId) { clear(logicalId); }
  function forgetProject() { /* retention increment */ }
  function gc() { /* 30-day idle GC — deferred with the store backend */ }
  function onRemote() { /* C1 offer-to-load — needs the store; seam only */ }
  return {
    id, bind, unbind, save, restore, clear, get, isDurable, attemptId,
    forget, forgetProject, gc, onRemote,
    // test/guard seams: expose key builders without re-deciding shapes
    _v1Key: v1Key, _legacyKey: legacyKey
  };
})();
/* thin façade: existing answer-box call sites keep dwDraft.save(title, …).
   Routes through DraftStore so card and composer share one policy. */
const dwDraft = {
  save(title, value) {
    if (!title) return;
    DraftStore.save(DraftStore.id('card', title), value);
  },
  restore(title, el) {
    if (!title) return;
    DraftStore.restore(DraftStore.id('card', title), el);
  },
  clear(title) {
    if (!title) return;
    DraftStore.clear(DraftStore.id('card', title));
  }
};
/* Put a drafted answer back into every box a render just created. Runs AFTER
   the in-memory snapshot (`restoreCardState`) has had its say, so the more
   recent live state wins and storage is the backstop — which is the whole
   point: #118 carries text across a tick, this carries it across the reload
   #118 cannot. A box the snapshot already filled is a live box, and storage
   does not overwrite it (dwDraft.restore's `el.value` guard). Called from
   every DOM commit that recreates cards — `setContent` and the review-dock
   `replaceWith` — not only at load, because a box that reappears on a tick
   needs its draft back just as much as one that reappears on a reload. */
function restoreAnswerDrafts() {
  document.querySelectorAll('.qa[data-qid]').forEach(card => {
    let title = null;
    try { title = decodeURIComponent(card.dataset.qid); } catch (e) { return; }
    if (!title) return;
    const ta = card.querySelector('textarea[id^="qi"]');
    if (!ta) return;
    const before = ta.value;
    dwDraft.restore(title, ta);
    // #177: a draft restored into a fresh box must size that box, snapped —
    // the reload path `restoreCardState` does not reach (no in-memory snapshot
    // survived it), so without this a restored multi-line draft sits in a
    // 2-row box until the first keystroke.
    if (ta.value && ta.value !== before) fitText(ta, false);
  });
}
/* #505 p2 — KEPT (not absorbed): the dock's review <iframe> holds a
   cross-origin browsing context (scroll/state) that is precious and
   irrecoverable. The pair is a NO-OP when the reconciler keeps #reviewframe
   by id (same node → fresh === saved → the replaceWith is skipped), and a
   safety net that swaps the live frame back if the reconciler ever rebuilds
   it. Deleting it would trade a harmless no-op for a one-way loss. */
function snapshotReviewFrame() {
  const frame = document.getElementById('reviewframe');
  if (!frame) return null;
  const saved = { frame, src: frame.src, x: 0, y: 0, readable: false };
  try {
    saved.x = frame.contentWindow.scrollX;
    saved.y = frame.contentWindow.scrollY;
    saved.readable = true;
  } catch (e) { /* cross-origin artifacts keep their URL; scroll is opaque */ }
  return saved;
}
function restoreReviewFrame(saved) {
  if (!saved) return;
  const fresh = document.getElementById('reviewframe');
  if (!fresh) return;
  // Preserve the live browsing context itself. Recreating an iframe starts a
  // navigation which necessarily resets its scroll and may also discard state
  // inside cross-origin artifacts that the parent is forbidden to inspect.
  if (fresh !== saved.frame) fresh.replaceWith(saved.frame);
  if (saved.frame.src !== saved.src) saved.frame.src = saved.src;
  if (saved.readable) {
    try { saved.frame.contentWindow.scrollTo(saved.x, saved.y); } catch (e) {}
  }
}
function setLiveContent(html) {
  if (view.name === 'review') {
    const parsed = document.createElement('template');
    parsed.innerHTML = html;
    const currentDock = document.getElementById('qdock');
    const nextDock = parsed.content.querySelector('#qdock');
    if (currentDock && nextDock) {
      // #505 phase 2 (Q3): reconcile the dock through the SAME keyed
      // reconciler #view uses, not a wholesale replaceWith. Only the swap
      // MECHANISM changes — same content, same lifecycle. childrenOnly keeps
      // #qdock's OWN attrs, so the .attop/.atend fade depths (#326) ride the
      // root and survive without the old hand-copy (the server carries
      // neither, so a fresh dock used to resolve the full 24px first and
      // land a style pass late, dimming both edges for half a second). The
      // .qa[data-qid] card + its textarea are matched by key and KEPT, so a
      // draft, caret and prose selection inside the dock survive a tick (the
      // Q3 goal). Dock key = the question title (data-qid), stable across
      // ticks (the dock answers ONE question, view.q); the dock root is
      // positional. #reviewframe is a sibling outside #qdock, untouched here
      // as it was under replaceWith.
      window.__dwViewRenderGen = (window.__dwViewRenderGen || 0) + 1;
      morphdom(currentDock, nextDock, {
        childrenOnly: true,
        getNodeKey: viewNodeKey,
        onBeforeElUpdated: reconcileGuard,
      });
    } else setContent(html);
    paintIndicators(true); ages();
    // a kept dock textarea already holds its draft; restoreAnswerDrafts is
    // the storage backstop for a reload and declines a non-empty box.
    restoreAnswerDrafts();
    return;
  }
  setContent(html);
}
/* One-shot atmospheric arrival for NEW /answers open rows (#293 amend).
   Keys by data-aqid (server `open:` aid over title+body+ordinal — never
   title alone). First paint of the answers view, and hard refresh,
   settle fully visible without replaying .dreamin. Live-added
   rows (after a successful /ask) snap to the enter pose then ease in;
   reduced motion leaves them fully visible (function, no start pose).
   window.__dwSkipOpenAskArrival is a deliberate inject point for the
   browser guard's RED of the arrival mechanism. */
let knownOpenAskKeys = null;
function revealNewOpenAsks() {
  if (view.name !== 'answers') { knownOpenAskKeys = null; return; }
  const nodes = [...document.querySelectorAll('.aq.open[data-aqid]')];
  const now = new Set(nodes.map(el => el.dataset.aqid));
  if (knownOpenAskKeys === null || window.__dwSkipOpenAskArrival) {
    // first answers paint, or inject: settle without stuck dreamin
    nodes.forEach(el => el.classList.remove('dreamin'));
    knownOpenAskKeys = now;
    return;
  }
  const rmr = matchMedia('(prefers-reduced-motion: reduce)').matches;
  for (const el of nodes) {
    if (knownOpenAskKeys.has(el.dataset.aqid)) continue;
    if (rmr) continue;                          // already fully lit
    el.classList.add('dreamin');
    void el.offsetWidth;                        // commit opacity 0
    requestAnimationFrame(() => {
      if (el.isConnected) el.classList.remove('dreamin');
    });
  }
  knownOpenAskKeys = now;
}
/* #462 — one-shot atmospheric arrival for the staleness row's remedy, present
   only when the page is behind. The row is re-rendered through innerHTML
   every tick, so like revealNewOpenAsks the .dreamin start pose is applied
   ONLY on the genuine current→behind transition (the moment the page just
   fell behind), never on first paint (which settles visible), never replayed
   on a tick where the affordance was already present, and never under
   reduced motion (function, no pose). Behind→current is a redeploy = a
   generation change = a full reload, so there is no departure to animate: the
   affordance leaves with the page that held it. window.__dwSkipStaleArrival
   is the guard's RED inject point, mirroring __dwSkipOpenAskArrival. */
let knownStaleAction = null;
function revealStaleAction() {
  if (view.name !== 'dashboard') { knownStaleAction = null; return; }
  const node = document.querySelector('.gservact');
  const now = !!node;
  if (knownStaleAction === null || window.__dwSkipStaleArrival) {
    if (node) node.classList.remove('dreamin');
    knownStaleAction = now;
    return;
  }
  if (now && !knownStaleAction) {
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!reduce && node) {
      node.classList.add('dreamin');
      void node.offsetWidth;                    // commit the start pose
      requestAnimationFrame(() => {
        if (node.isConnected) node.classList.remove('dreamin');
      });
    }
  }
  knownStaleAction = now;
}
/* #505 — keyed reconciliation of #view (I5: morphdom + content-hash skip).
   The chrome already survived ticks because renderChrome reuses crumbs by
   key; #view used to wholesale-replace via innerHTML, which is why a prose
   Range inside a question card died on every poll (R1). Survivor nodes
   matched by the page's existing identity attrs are KEPT — selection,
   caret, listeners, open disclosures ride the node rather than a 12th
   snapshot. Views stay pure HTML-string builders (G2); this is the one
   seam that commits them.

   Keys (one canonical attr per element class, same as *_LIST):
     data-qid, data-aid, data-sha, data-review, data-keep, then id.
   Corpse rule: .qaghost / .ghost never receive a key (dreamAway strips
   identity; the reconciler refuses them as a second belt).

   window.__dwViewRenderGen advances on every non-skipped mutation so
   guards can prove a tick did work without requiring node replacement
   (under reconciliation survivors are the same objects). */
let lastViewHtml = null;
window.__dwViewRenderGen = 0;
function viewNodeKey(node) {
  if (!node || node.nodeType !== 1) return undefined;
  // corpse rule — a ghost holds no address (watch.py dreamAway + Q4)
  if (node.classList &&
      (node.classList.contains('qaghost') || node.classList.contains('ghost')))
    return undefined;
  const d = node.dataset;
  if (d) {
    if (d.qid) return 'qid:' + d.qid;
    if (d.aid) return 'aid:' + d.aid;
    if (d.sha) return 'sha:' + d.sha;
    if (d.review) return 'review:' + d.review;
    if (d.keep) return 'keep:' + d.keep;
    // burndown columns (#494): data-t0 is the bucket identity
    if (d.t0 && node.classList && node.classList.contains('bdcol'))
      return 't0:' + d.t0;
  }
  if (node.id) return 'id:' + node.id;
  return undefined;
}
/* #505 — the reconciliation rules shared by every morphdom seam (the #view
   reconcile in setContent AND the review-dock reconcile in setLiveContent).
   One source, so the dock and the view can never drift on what survives a
   tick. Each rule names the human-owned state it defends from morphAttrs. */
function reconcileGuard(fromEl, toEl) {
  if (fromEl.classList &&
      (fromEl.classList.contains('qaghost') ||
       fromEl.classList.contains('ghost')))
    return false;
  // ages() owns .age textContent between ticks — builder markup leaves
  // the spans empty. Skipping identical-identity age nodes preserves
  // the filled figure and avoids a one-frame blank (dashboard #132).
  if (fromEl.classList && fromEl.classList.contains('age') &&
      toEl.classList && toEl.classList.contains('age')) {
    const attrs = ['data-mt', 'data-ct', 'data-at', 'data-ut',
                   'data-cr', 'data-day'];
    let same = fromEl.className === toEl.className;
    for (let i = 0; i < attrs.length; i++) {
      if (fromEl.getAttribute(attrs[i]) !== toEl.getAttribute(attrs[i]))
        same = false;
    }
    if (same) return false;
  }
  // #577 — the /chat reply confirmation (#chatreplymsg) is the one #255
  // surface that lives INSIDE #view, so a tick re-render would wipe its
  // client-set text the instant it brings the new turn — cutting a 5s hold
  // to under one tick. The other #255 surfaces (#cmdmsg, #fmsg) sit in the
  // chrome outside #view and never re-render; this span does. Preserve the
  // live node while a confirmation is showing (non-empty), the same keep
  // rule .age spans use for client-filled figures; once confirmationFor
  // clears it (empty) it reconciles normally again. (confirmationFor owns
  // the .dreamin/.depart classes and the ~5s timer; this only stops a tick
  // from clobbering the node it paints on.)
  if (fromEl.id === 'chatreplymsg' && fromEl.textContent.trim())
    return false;
  // Human-owned open on data-keep disclosures: builders always emit
  // closed; open is his. Stamp onto toEl so morphAttrs does not clear
  // it (absorbs snapshotFolds re-open). Mid-gesture height travels the
  // same way — a kept node mid-fold must not lose its inline height.
  if (fromEl.tagName === 'DETAILS' && fromEl.dataset && fromEl.dataset.keep) {
    if (fromEl.open) toEl.open = true;
    if (fromEl.style && fromEl.style.height)
      toEl.style.height = fromEl.style.height;
  }
  // #505 p2: a FOCUSED input/textarea's typed value is his — the fresh
  // markup carries the server/default, and morphdom's INPUT/TEXTAREA
  // handler would otherwise clobber mid-edit text back to it. Stamping the
  // live value onto toEl makes that handler see them equal and skip
  // (absorbs snapshotViewInputs' value restore; caret, scroll and focus
  // are not attributes and survive on the kept node without a stamp).
  // Focus-gated on purpose: the burndown limit input's "re-render restores
  // the previous value" contract (#499) fires on blur — when the field is
  // NOT focused — so an unfocused input still takes the server value and
  // an invalid/unapplied entry still resets.
  if ((fromEl.tagName === 'INPUT' || fromEl.tagName === 'TEXTAREA') &&
      document.activeElement === fromEl &&
      fromEl.value !== toEl.value)
    toEl.value = fromEl.value;
  // Card-internal disclosures (no data-keep) and the compose dest-mode are
  // still re-driven by snapshotCardState (kept): the mode is a multi-element
  // UI (setCardMode toggles .qmode buttons, placeholder, aria-labels and the
  // indicator) an attribute stamp cannot cover, so the belt stays coherent
  // rather than half-absorbed. Box heights (autogrow) and read-scroll ride
  // the same belts (askState / cardState).
  if (fromEl.isEqualNode(toEl)) return false;
  return true;
}
function setContent(html) {
  // I5 hash-skip: identical build → nothing to reconcile (and no gen bump).
  if (html === lastViewHtml) return;
  lastViewHtml = html;
  window.__dwViewRenderGen = (window.__dwViewRenderGen || 0) + 1;
  const viewEl = document.getElementById('view');
  morphdom(viewEl, '<div id="view">' + html + '</div>', {
    childrenOnly: true,
    getNodeKey: viewNodeKey,
    onBeforeElUpdated: reconcileGuard,
  });
  // before anything measures: the review pane's height is a measurement, and
  // crossfade reads the dock's rect on the very next line after setContent.
  fitReview();
  // #583: place the dual-column response at the question's visible midpoint
  // before first paint, so it lands centred rather than flashing at the floor
  // and snapping on the first scroll frame.
  positionQuestionColumn();
  // fresh groups carry a 0-width indicator, so land it rather than let it
  // slide up out of nothing (the enter-snap rule)
  paintIndicators(true);
  ages();
  revealNewOpenAsks();
  revealStaleAction();
  // #462: the remedy may be re-created when the row is new; re-apply
  // arm/running classes and label so a mid-arm tick does not reset idle copy.
  paintStaleDeployUI();
  // #565: re-apply the posture dock — morphdom rebuilt #posture, so the
  // .psticky class (conditional on a live countdown) must be re-set every
  // render or a tick while armed loses the dock.
  paintPosturePin();
  // #569: re-apply the recused deploy countdown (#pdep) — morphdom rebuilt
  // the slot empty, so a tick while deploying must repopulate it (and a tick
  // after clear must collapse it), like paintStaleDeployUI re-applies the
  // button. deployStatusText() is '' when no deploy is live.
  paintDeployStatus(deployStatusText());
  revealReviewMods();
  revealReviewDecisions();  // #289: decision-token arrival, same idiom
  revealQuestionUpdates();  // #473: updated-ago arrival, after ages() hides dishonest ones
  // #445: arm-resume idiom for the three-axis posture control (the run-mode
  // picker it used to sit beside was removed in #547; posture derives from
  // .dreamwork/run-mode via collect(), independent of any picker surface).
  syncPostureFromData();
  // #454: rolled questions re-roll here, on the same argument as the
  // drafts below — every render commits through this seam, and the tick's
  // regroups measure AFTER it, so a kept roll invents no travel.
  restoreRolls();
  // every navigate and every non-review tick commits through here, so this is
  // the one place that puts a drafted answer back after the box is recreated —
  // the in-memory snapshot does the same for a tick, but only storage survives
  // the reload he reported (#269). Runs before paint, so the text is part of
  // the first frame rather than arriving into an empty box. Idempotent on
  // kept nodes (dwDraft.restore declines a non-empty box).
  restoreAnswerDrafts();
  // #459: re-bind + restore from storage. bindAskDraft unbinds first so a
  // kept #askbox is not double-bound (the binding discipline under #505).
  bindAskDraft();
  // #577: same discipline for the /chat/<id> reply box (chat:<id> key).
  bindChatReplyDraft();
}
/* ── what the human did to a card survives a tick (#118, #111) ────────────
   The tick re-renders the question list through `innerHTML`, so every card
   node is genuinely replaced — and with it whatever the human was part-way
   through typing, and whichever folded entry he had just opened up to read.
   Liveness is not negotiable (the tick has always committed its new DOM
   immediately), so the fix is not to suppress the render; it is to carry
   across the render the state that exists NOWHERE ELSE. What he typed, where
   his caret is, which endpoint it is destined for, and what he has expanded
   are not on disk, so nothing downstream can reconstruct them.

   Keyed by `data-qid` — the question itself — for exactly the reason the
   regroup is: answering re-indexes an entry out of `questions_open`, so a
   positional key would drop the text at the very moment the card moves. */
/* #505 p2 — KEPT (not absorbed): the compose dest-mode is a DERIVED
   multi-element UI, not a single attribute — setCardMode toggles the .qmode
   button .on/aria-checked, the textarea placeholder/aria-label, the send
   aria-label and slides the indicator — so an attribute stamp in
   reconcileGuard cannot cover it. The belt also re-fits box height (fitText)
   and force-layout scroll (putScroll). value/caret now also survive on the
   kept card node, but mode/height/disclosures stay this belt's coherent job. */
function snapshotCardState() {
  const act = document.activeElement;
  const m = new Map();
  document.querySelectorAll('.qa[data-qid]').forEach(card => {
    const comp = card.querySelector('.qcompose');
    const ta = comp && comp.querySelector('textarea');
    // EVERY disclosure in the card, in document order: the folded entry itself
    // (#111) and its settled thread (#128) both render closed, so either being
    // open is something he did and nothing on disk records.
    const dets = [...card.querySelectorAll('details')].map(d => d.open);
    const typed = ta && (ta.value || ta === act);
    const opened = dets.some(Boolean);
    // HOW FAR HE HAS READ is his too (#305). On /review the question's body is
    // the scroller (#326 — the card holds the answer box, which must not fade
    // with the text), and the tick replaces the whole dock — so a question he
    // had scrolled halfway through would snap back to its first line every two
    // seconds, which is #118 with reading in place of typing.
    const sc = qaScroller(card);
    const read = sc ? sc.scrollTop : 0;
    // #479: a destination-MODE switch is something he did too, and it lives
    // only in this node — the group renders at the card's default, so any
    // other mode is his click. A tick that lands between the click and the
    // first keystroke otherwise re-renders the DEFAULT destination and
    // silently re-aims words he has not typed yet.
    const modeHis = comp && comp.dataset.mode !==
      qaDefaultMode(card.classList.contains('open') ? 'open' : 'awaiting');
    if (!typed && !opened && !read && !modeHis) return; // he has done nothing
    m.set(card.dataset.qid, {
      open: dets, read,
      value: typed ? ta.value : null, mode: comp && comp.dataset.mode,
      focus: ta === act,
      start: typed ? ta.selectionStart : 0, end: typed ? ta.selectionEnd : 0,
      dir: typed ? ta.selectionDirection : 'none',
      scroll: typed ? ta.scrollTop : 0,
      // #177's box height is re-fit from the restored content (`fitText` in
      // restoreCardState), so it is not carried here — recomputing is the same
      // value and cannot drift from the content the snapshot also restored.
    });
  });
  return m;
}
/* PUT A SCROLL OFFSET BACK, AND CHECK THAT IT LANDED — `refocus`'s rule
   (#179) applied to the other thing a restore hands back silently.

   A `scrollTop` assigned to a node the swap is one statement old is clamped
   to zero: as far as the assignment can see the fresh box has no overflow
   yet. It reports nothing in either direction, and whether it happens at all
   depends on whether something between the swap and here already forced a
   layout — so it is a bug with an unreliable lifetime (#198's shape), which
   is exactly the kind a guard passes over. Reading the value back both
   detects it and forces the layout that fixes it.

   Deliberately unguarded, and said out loud rather than left implied: the
   browser guard's tick check covers the FEATURE (his place in the question
   survives), and it stays green with the retry removed, because on that run
   something else had already forced the layout. A check that cannot fail for
   its stated cause sends the next reader to the wrong file. The mechanism was
   measured directly instead — assigning 209 to a just-swapped card reads back
   0, and reads back 209 with the layout forced first. */
function putScroll(el, top) {
  if (!el || !top) return;               // re-fill only, never clear
  el.scrollTop = top;
  if (el.scrollTop !== top) el.scrollTop = top;   // the read above laid it out
}
function restoreCardState(saved) {
  if (!saved || !saved.size) return;
  document.querySelectorAll('.qa[data-qid]').forEach(card => {
    const s = saved.get(card.dataset.qid);
    if (!s) return;
    // only ever re-opened, never closed: the fresh render is the default and
    // what he did to it is the addition
    const dets = [...card.querySelectorAll('details')];
    (s.open || []).forEach((o, i) => { if (o && dets[i]) dets[i].open = true; });
    // how far he had READ into the question (#305) — see putScroll
    putScroll(qaScroller(card), s.read);
    const comp = card.querySelector('.qcompose');
    // the mode is WHERE THE TEXT GOES: a re-render must never silently
    // redirect it — and it rides even with no text yet, because the click
    // that set it is his whether or not a keystroke has followed (#479), so
    // it is restored BEFORE the no-text early return below. setCardMode
    // declines a mode the new state cannot accept.
    setCardMode(comp, s.mode, true);
    if (s.value === null) return;
    const ta = comp && comp.querySelector('textarea');
    if (!ta) return;                       // the state stopped offering a box
    ta.value = s.value;
    // #177: re-fit the box to its restored content, SNAPPED — the tick
    // re-creates the box at its floor every ~2s, so an animated fit here would
    // re-grow it under him on every tick while he is mid-thought. The height
    // the snapshot carried is now derived from the content rather than trusted,
    // which is the same preference as letting `fitText` recompute on input.
    fitText(ta, false);
    putScroll(ta, s.scroll);
    try { ta.setSelectionRange(s.start, s.end, s.dir || 'none'); } catch (e) {}
    if (s.focus) refocus(ta);
  });
}
/* Put the caret back in the box he was typing in — and CHECK that it landed,
   because the way this fails is silence (#179).
   `focus()` on an element inside a CLOSED <details> does nothing at all and
   throws nothing, so a card restored while its section was still shut came
   back filled but dead, and only on the dashboard, where cards live inside
   `.qsec`. Ordering the two restores fixes that instance; this kills the
   class, which is what "his state survives ANY re-render" needs — the next
   container someone wraps the list in has no snapshot of its own and would
   silently eat the focus again.
   Re-opening is always safe here BY CONSTRUCTION: he could only have been
   typing in a box whose ancestors were open, so every one of them re-opening
   is restoring what he had. It obeys the standing rule that a restore only
   ever RE-OPENS or RE-FILLS — the worst it can do is give something back. */
function refocus(ta) {
  ta.focus({ preventScroll: true });
  if (document.activeElement === ta) return;
  for (let n = ta.parentElement; n; n = n.parentElement)
    if (n.tagName === 'DETAILS') n.open = true;
  ta.focus({ preventScroll: true });
}
/* ── the regroup (#104, #77) ──────────────────────────────────────────────
   Answering a question moves it out of the open list and under a different
   heading. That is one moment seen two ways: the questions below close the
   gap it left (#104), and the question itself travels to its new section
   rather than being re-set there (#77). So it is one mechanism — a FLIP over
   the list, keyed by `data-qid`, which is the question and survives the move
   its positional key cannot.

   Liveness is not delayed by this. The new DOM is committed IMMEDIATELY, as
   the tick always has; only the visual transform is animated, so what is on
   screen is always the current data drawn from where it used to be. */
/* which heading a card currently sits under — the thing #77 is actually
   about. Not the card's own state class: the submit morph already changed
   that locally when the answer was sent, so by regroup time it would report
   no change even though the card is about to cross the page. */
/* #118's rule one level up (#141). A SECTION he has opened is his, it exists
   nowhere on disk, and the tick rebuilds the dashboard through `innerHTML` —
   so without this the questions fold would snap shut under him every two
   seconds, which is the bug #118 fixed for a card's own disclosure. Keyed by
   `data-keep` rather than by position, and only ever RE-OPENED: the fresh
   render is the default and what he did to it is the addition. Any future
   section that wants the same gets it by carrying the attribute. */
/* #477: re-opening is not enough when the tick catches the gesture ITSELF.
   `el.open = true` on the fresh node arrives at full height in ONE frame, and
   if the section was part-way through its 850ms open when the tick fired, that
   frame replaces the travel with a teleport — #196's snap re-entering at the
   surface #196 fixed, every time a tick happens to land inside the gesture.

   What it was mid-gesture is already legible on the page and needs no separate
   bookkeeping: `travelCard` owns `height` while it runs, so a non-empty inline
   `height` IS the tell, and it cannot go stale because `travelCard` clears it
   itself at CARD_MS + 150. The interrupted height is just the old node's rect
   at snapshot time. */
function cardGroup(el) {
  for (let n = el.previousElementSibling; n; n = n.previousElementSibling)
    if (n.classList.contains('label')) return n.textContent;
  return '';
}
/* the keyed lists that move. A "list" is a selector plus the attribute that
   IS a row's identity — never its position, because the whole job here is
   telling a row that MOVED from a row that LEFT, and a positional key cannot.
   Both lists go through the same snapshot and the same regroup: #151 is
   #104's motion over a different set of rows, and a second implementation of
   "one leaves, its neighbours travel" would be two things to keep true. */
const QA_LIST = { sel: '.qa[data-qid]', key: 'qid' };
const ANSWER_LIST = { sel: '.aq.answered[data-aid]', key: 'aid' };
const GIT_LIST = { sel: '.git .commit[data-sha]', key: 'sha' };
const REVIEW_LIST = { sel: '[data-review]', key: 'review' };
function snapshotCards(list) {
  list = list || QA_LIST;
  const m = new Map();
  document.querySelectorAll(list.sel).forEach(el =>
    m.set(el.dataset[list.key], {
      rect: el.getBoundingClientRect(),
      group: cardGroup(el),
      // cloned up front because a departure has no node left to animate once
      // the re-render has happened, and we cannot know which will depart
      node: el.cloneNode(true),
    }));
  return m;
}
/* ONE way a card moves inside the list (#104, #77, #113). It travels from the
   rect it had to the rect it has — in position AND in height — and when it
   crossed to a different HEADING it is lifted while it goes, so the eye
   follows that one card across the page instead of reading the whole list as
   re-laid-out.

   Height, not scale, and that distinction is load-bearing. `flipDock` morphs
   by `scale()`, which is right for the review dock, where the card genuinely
   changes column. Inside the list the column never changes — but the HEIGHT
   now can, by a factor of fifteen, because folding collapses the card (#111).
   A scale morph would stretch the text by that ratio at frame 0 and read as a
   squash, not a fold. So the size travels as height, with the box clipped
   while it does.

   Every state change on this list also changes the heading the card sits
   under, so `lifted` is the same signal as "the state changed" — read from
   the heading rather than the class, because the submit morph has already
   changed the class locally by the time we get here. */
const CARD_MS = 850;
const CARD_TRAVEL =
  'transform .85s cubic-bezier(.32,.1,.2,1),' +
  ' height .85s cubic-bezier(.32,.1,.2,1), filter .7s ease, opacity .7s ease';
function travelCard(el, was, now, lifted) {
  const resized = Math.abs(was.height - now.height) >= 1;
  el.style.transition = 'none';            // the enter-snap rule, again
  el.style.transform = `translate(${was.left - now.left}px,` +
                       `${was.top - now.top}px)`;
  if (resized) {
    // border-box, because the two numbers being interpolated came from
    // getBoundingClientRect and that is a BORDER box, while `height` is a
    // content box by default. It was a distinction without a difference while
    // the only travellers were `.qa` and `.git .commit`, neither of which has
    // vertical padding — and then #196 sent a <details> through here, which
    // gains #169's `.5rem` of air on the frame it opens. Left as content-box
    // the travel aims 16px past its real height and SNAPS back the moment the
    // inline height is cleared: invisible to an end-state check, and to "did
    // it move", which is the shape of every motion bug this page has had.
    el.style.boxSizing = 'border-box';
    el.style.height = was.height + 'px';
    el.style.overflow = 'hidden';          // content must not spill as it folds
  }
  if (lifted) {
    el.style.zIndex = '4'; el.style.filter = 'blur(5px)'; el.style.opacity = '.4';
  }
  void el.offsetWidth;                     // commit the inverted start
  el.style.transition = CARD_TRAVEL;
  // an explicit identity, not a removal: the inline transform IS the signal
  // that a card travelled rather than being re-laid-out, and removing it
  // synchronously leaves nothing for a per-frame trace to see. Cleared below.
  el.style.transform = 'translate(0px, 0px)';
  if (resized) el.style.height = now.height + 'px';
  if (lifted) { el.style.filter = ''; el.style.opacity = ''; }
  setTimeout(() => {
    for (const p of ['transition', 'transform', 'height', 'overflow',
                     'boxSizing', 'zIndex', 'filter', 'opacity']) el.style[p] = '';
  }, CARD_MS + 150);
}
/* an element leaving fades rather than vanishing — the page's one departure
   idiom, lifted out of flow at the rect it occupied so survivors can close
   the gap underneath it, then dissolved on the mist. `clipTop` hides the part
   of the ghost the survivor still occupies, which is what makes it usable for
   a BODY leaving as well as for a whole card leaving. */
function dreamAway(wrap, node, rect, clipTop) {
  if (!wrap) return;
  const org = wrap.getBoundingClientRect();
  // A ghost is a CORPSE, not the card, so it must not keep the card's
  // address. It is a clone, so it arrives carrying data-qid and data-qkey —
  // and it is appended to .wrap, which means every `.qa[data-qid]` walk on
  // the page would find it: snapshotCards would capture its absolute rect as
  // the question's, restoreCardState would type into it, and a per-frame
  // trace would measure it instead of the card animating underneath. That
  // last one is how this was found. Strip the identity at the door rather
  // than teaching six lookups to skip it.
  // Every identity attribute on the page, not just this list's: a corpse
  // holds no address at all, and enumerating them here is one line where
  // teaching each lookup to skip a ghost would be six.
  //
  // AND THROUGHOUT THE SUBTREE, not only on the node itself (#196). While the
  // only things that dreamed away were one card and one commit row, the node
  // WAS the whole identity; the questions fold ghosts a clone of the entire
  // open section, which carries `data-keep="qsec"` and every card inside it.
  // `snapshotFolds` walks `details[data-keep]` and the last match wins — and a
  // ghost is appended to `.wrap`, i.e. last — so that one attribute surviving
  // means the next tick reads the section as still open and re-opens it under
  // him, a second after he shut it.
  const IDS = ['data-qid', 'data-qkey', 'data-sha', 'data-keep', 'data-aid'];
  for (const n of [node, ...node.querySelectorAll(IDS.map(a => `[${a}]`).join(','))])
    for (const a of IDS) n.removeAttribute(a);
  node.classList.add('qaghost');
  node.style.left = (rect.left - org.left) + 'px';
  node.style.top = (rect.top - org.top) + 'px';
  node.style.width = rect.width + 'px';
  if (clipTop > 0) node.style.clipPath = `inset(${Math.round(clipTop)}px 0 0 0)`;
  wrap.appendChild(node);
  void node.offsetWidth;
  // Two beats (#277): dissolve in place first (.pregone, 180ms), then leave
  // (.gone, 700ms). The liquify/blur lives in an SVG mist filter (#departMist)
  // driven per-frame from rAF — the same idiom as the route dissolve's
  // #dissolveOut — so the ghost hazes and liquifies rather than just CSS-blurring.
  // #453: the field is the same cached feImage texture as the route dissolve,
  // drifted by feOffset instead of a baseFrequency ramp — a departure ghost is
  // small, but feTurbulence re-rasterizes per frame whatever the area (#449).
  // Removing .pregone restores .qaghost's .7s transition for the departure leg.
  // Commits are excluded: their gesture is the grow-and-fall (line 677), and
  // they keep CSS blur(6px) instead of the SVG filter.
  if (node.classList.contains('commit')) {
    node.classList.add('gone');
  } else if (!mistTexture()) {
    node.classList.add('pregone');     // no canvas: CSS-blur departure only
    setTimeout(() => { node.classList.remove('pregone'); node.classList.add('gone'); }, 180);
  } else {
    const dm = document.querySelector('#departMist feDisplacementMap');
    const bl = document.querySelector('#departMist feGaussianBlur');
    const of = document.querySelector('#departMist feOffset');
    const smooth = x => x * x * (3 - 2 * x);
    const t0m = performance.now();
    const MIST_MS = 880;               // 180ms pregone + 700ms gone
    // drift bounded by the ghost's own size: the offset must never push the
    // tiled field's edge into sampling reach (region margin − scale/2).
    const drift = Math.max(0, Math.min(8, rect.width * 0.25 - 8, rect.height * 0.25 - 8));
    node.style.filter = 'url(#departMist)';
    node.classList.add('pregone');
    (function mistStep(now) {
      const u = Math.min(1, (now - t0m) / MIST_MS);
      const e = smooth(u);
      if (dm) dm.setAttribute('scale', (e * 14).toFixed(2));
      if (bl) bl.setAttribute('stdDeviation', (e * 4.5).toFixed(2));
      if (of) {                        // the field flows up as it liquifies,
        of.setAttribute('dx', (e * drift * 0.6).toFixed(1));  // rising with
        of.setAttribute('dy', (-e * drift).toFixed(1));       // the ghost
      }
      if (u < 1 && node.isConnected) requestAnimationFrame(mistStep);
    })(performance.now());
    setTimeout(() => {
      node.classList.remove('pregone');
      node.classList.add('gone');
    }, 180);
  }
  setTimeout(() => node.remove(), 1050);
}
/* the same departure idiom for a subtree that has just left the layout but is
   still in the DOM — a `<details>` that closed. It has no box any more, so the
   rect is the one measured while it did. */
function ghostNode(el, rect) {
  if (rmr || !rect || !rect.height) return;
  dreamAway(document.querySelector('.wrap'), el.cloneNode(true), rect, 0);
}
/* what is really arriving or leaving when a card changes height. Normally that
   is everything under its title line — the card folded or unfolded — and the
   title itself survives as the summary, so it is not part of the move.

   A disclosure INSIDE the card resizes the card too (its settled follow-up
   thread, #128), and there only that disclosure's own contents move: the body,
   the answer and the compose box were on screen before and after and must not
   be re-faded. So the toggle that caused the change is passed in when it is
   known, and when it is the card's own `.qfold` this is exactly what it always
   was. */
/* `.qbody` is looked THROUGH, never at (#326). It is the review dock's
   scrollport and nothing anywhere else — `display:contents`, no box — so a
   ghost cloned from it has no rect and a `.qreveal` transition on it has
   nothing to animate. The pieces that arrive and depart are its children, and
   they are the same list this returned before the wrapper existed. */
function cardBody(el, toggled) {
  const root = (toggled && el.contains(toggled)) ? toggled
             : (el.querySelector(':scope > .qfold') || el);
  return [...root.children]
    .flatMap(c => c.classList.contains('qbody') ? [...c.children] : [c])
    .filter(c => c.tagName !== 'SUMMARY' && !c.classList.contains('qt'));
}
/* was the height change caused by a disclosure NESTED inside the card, rather
   than by the card's own fold? The two need different departure ghosts, so
   they are told apart once, here. */
const nestedToggle = (el, toggled) =>
  !!toggled && el.contains(toggled) &&
  toggled !== el.querySelector(':scope > .qfold');
/* the arriving half of a fold, and the page has exactly one of them (#196).
   A body that arrives EASES IN rather than being wiped up by the growing box —
   the same moment `dreamAway` runs backwards. Shared by the card fold and the
   dashboard's questions section, because two spellings of one gesture is how
   a reader concludes the softer one was optional. */
function revealBody(el, toggled) {
  cardBody(el, toggled).forEach(c => {
    c.classList.add('qreveal', 'dreamin');
    requestAnimationFrame(() => c.classList.remove('dreamin'));
    setTimeout(() => c.classList.remove('qreveal'), CARD_MS + 150);
  });
}
const BODY_STEP = 24;             // about a line: below this nothing "left"
/* Cards are processed in DOM order, and that is load-bearing rather than
   incidental.

   A resizing card's own height animation carries everything below it — the
   layout does that continuously, for free, and it is the better motion
   because the neighbours stay welded to the card they are following. So the
   FLIP only has to handle the RESIDUAL: whatever moved for some other reason.
   Restoring a card's old height before the next card is measured is exactly
   what makes the next card's `now` mean "where it would be if only that
   resize had happened", so the residual it FLIPs is the right one. FLIPping
   the full difference instead would move a neighbour twice — once by
   transform and once by layout — and it would snap back at the end.

   The commits panel (#151) runs through this unchanged, and the two branches
   that are about a CARD are inert there BY CONSTRUCTION rather than by a
   guard clause: a commit row is fixed-height, so `dh` is always 0 and neither
   body branch is reachable, and no `.label` precedes a row inside `.git`, so
   `cardGroup` returns '' on both sides and nothing is ever lifted. Both of
   those are properties of the markup, which is why they are stated in the CSS
   and in gitRow rather than tested for here. */
function regroupCards(before, toggled, list, restated) {
  if (rmr || !before || !before.size) return;
  list = list || QA_LIST;
  const wrap = document.querySelector('.wrap');
  const seen = new Set();
  document.querySelectorAll(list.sel).forEach(el => {
    const id = el.dataset[list.key], was = before.get(id);
    seen.add(id);
    if (!was) {                       // newly arrived: snap, then ease in
      el.classList.add('dreamin');
      requestAnimationFrame(() => el.classList.remove('dreamin'));
      return;
    }
    const now = el.getBoundingClientRect();
    const moved = Math.abs(was.rect.left - now.left) >= 1 ||
                  Math.abs(was.rect.top - now.top) >= 1;
    // a card can change SIZE without moving — it is the first in its list and
    // it just folded — and that is as much a travel as a move
    const dh = now.height - was.rect.height;
    if (!moved && Math.abs(dh) < 1) return;
    travelCard(el, was.rect, now, was.group !== cardGroup(el));
    // A card the CALLER restated is not one whose body arrived or left (#191).
    // The submit morph replaces the card's contents itself and gives the one
    // thing that is genuinely new — the answer, the note — its own lifted-hero
    // arrival; the body, the thread and the compose box were on screen before
    // and after. Re-fading them would say a change happened where none did,
    // which is #128's rule one surface over. Its HEIGHT still travels, and
    // that is the thing carrying every card below it.
    if (el === restated) return;
    // The box travelling is only half of a fold. The BODY is leaving, and an
    // element leaving fades rather than vanishing (human, 2026-07-25:
    // "when it folds in, the body shouldn't disappear all at once"). The new
    // card is already the folded one, so there is no live body left to
    // animate — which is exactly what the up-front clone is for. Ghost it at
    // the rect it occupied, clipped to below the line the survivor still
    // fills, and let it dream away on the departure idiom.
    //
    // A NESTED disclosure closing is ghosted by its own handler instead: the
    // settled thread sits above the compose box, so what disappears is a
    // MIDDLE band, and clipping the card-level clone to below the new height
    // would ghost the bottom slice — the compose box, which never left.
    if (dh <= -BODY_STEP) {
      if (!nestedToggle(el, toggled))
        dreamAway(wrap, was.node, was.rect, now.height);
    }
    // ...and unfolding is the same moment run backwards: the body ARRIVES,
    // so it eases in rather than being wiped up by the growing box.
    else if (dh >= BODY_STEP) revealBody(el, toggled);
  });
  // gone entirely: dream away where it stood, so it fades rather than blinks
  before.forEach((was, id) => {
    if (!seen.has(id)) dreamAway(wrap, was.node, was.rect, 0);
  });
}
/* ── #454: rolling an open question up to the top of its scroll ─────────
   His words: "the size of each collapsed question should be at least like
   5-6 lines ... more like a card or the top of a rolled up scroll." The
   floor is the whole design — a one-line collapse is a title list, and a
   title alone does not say whether an entry still needs him — so it is a
   line COUNT times the RENDERED line height (lineHeightOf's measured
   probe), never a pinned pixel constant (#441's split-literal lesson).

   The gesture is the card fold's own (#111/#169): snapshot, toggle,
   regroup — the height travels, the departing slice ghosts below the new
   edge, the arriving body eases in. No second way to move a card.
   `toggled` stays null so nestedToggle reads false and the card-level
   clone is what ghosts: what leaves IS this card's bottom slice, which is
   exactly what that clone clipped below the new height says.

   State is the question's title identity (data-qid), persisted to the
   dw-ui IndexedDB store and pinged across tabs through the standing
   'storage'-event idiom — "persisted to IndexedDB and kept in sync like
   other ui state". rolledQids is this page's truth between the two: the
   click writes all three, the storage event and the boot read keep the
   set current, and restoreRolls re-applies it inside setContent — the one
   seam navigate and tick both commit through — so neither a tick nor a
   route swap can unroll what he rolled, nor hold rolled what another tab
   unrolled. */
const ROLL_LINES = 5.5;          // the 5-6 line floor, in RENDERED lines
const rolledQids = new Set();    // decoded title identities
function rollHeight(card) {
  const probe = card.querySelector('.qbody .md p') ||
                card.querySelector('.qbody .qt') || card;
  return Math.ceil(lineHeightOf(probe) * ROLL_LINES);
}
function setRolled(card, rolling) {
  card.classList.toggle('rolled', rolling);
  const btn = card.querySelector('button.qroll');
  if (btn) {
    btn.setAttribute('aria-expanded', String(!rolling));
    btn.textContent = rolling ? 'unroll' : 'roll up';
  }
  if (rolling) card.style.setProperty('--rollh', rollHeight(card) + 'px');
  else card.style.removeProperty('--rollh');
}
/* re-apply the truth after ANY render. Landing inside setContent means
   landing before the tick's regroups MEASURE: a card re-rendered unrolled
   and re-rolled here has the small rect it had at snapshot, so no travel
   is invented for a state nothing changed. The dock's card is the reading
   surface — it is never rolled, and its button is not offered. */
function restoreRolls() {
  if (!rolledQids.size && !document.querySelector('.qa.rolled')) return;
  document.querySelectorAll('.qa[data-qid]').forEach(card => {
    if (card.closest('.qdock')) return;
    let title = null;
    try { title = decodeURIComponent(card.dataset.qid); } catch (e) { return; }
    const want = rolledQids.has(title);
    if (want !== card.classList.contains('rolled')) setRolled(card, want);
  });
}
function rollPingKey() {
  return (data && data.target) ? ('dw:qroll:' + data.target) : null;
}
/* the gesture never waits on storage: the click writes this page's set
   first, then the IndexedDB record a reload reads back (raced, uiPut),
   then the ping other tabs follow (best-effort). */
function persistRoll(title, rolling) {
  uiPut('qroll:' + title, rolling);
  const k = rollPingKey();
  if (k) try {
    localStorage.setItem(k,
      JSON.stringify({ qid: title, rolled: rolling, at: Date.now() }));
  } catch (e) {}
}
function applyRoll(card, rolling) {
  if (rmr) { setRolled(card, rolling); return; }
  const before = snapshotCards(QA_LIST);
  setRolled(card, rolling);
  regroupCards(before, null, QA_LIST);
}
function toggleRoll(card) {
  let title = null;
  try { title = decodeURIComponent(card.dataset.qid); } catch (e) { return; }
  if (!title) return;
  const rolling = !card.classList.contains('rolled');
  if (rolling) rolledQids.add(title); else rolledQids.delete(title);
  persistRoll(title, rolling);
  applyRoll(card, rolling);
}
addEventListener('click', e => {
  if (!e.target.closest) return;
  const btn = e.target.closest('button.qroll');
  if (!btn) return;
  const card = btn.closest('.qa[data-qid]');
  if (!card || card.closest('.qdock')) return;
  e.preventDefault();
  toggleRoll(card);
});
/* another tab rolled or unrolled: adopt into the set and re-apply through
   the SAME gesture — a card rolling in the corner of his eye still
   arrives and departs rather than appearing, because the ping is a state
   change he can see. */
window.addEventListener('storage', e => {
  if (!e.key || e.key !== rollPingKey() || !e.newValue) return;
  let m = null;
  try { m = JSON.parse(e.newValue); } catch (er) { return; }
  if (!m || typeof m.qid !== 'string') return;
  if (m.rolled) rolledQids.add(m.qid); else rolledQids.delete(m.qid);
  const card = document.querySelector(
    '.qa[data-qid="' + encodeURIComponent(m.qid) + '"]');
  if (card && !card.closest('.qdock') &&
      !!m.rolled !== card.classList.contains('rolled'))
    applyRoll(card, !!m.rolled);
});
/* boot: the store is the truth a reload reads back. Async on purpose —
   first paint never waits on IndexedDB (a roll restored a beat late is a
   restore; a page that waited on storage is the failure the raced write
   already refuses to risk). ensureData first: the database's name is the
   project's. */
async function loadRolls() {
  await ensureData();
  const recs = await uiAll();
  if (!recs) return;
  recs.forEach(r => {
    if (r && typeof r.k === 'string' && r.k.indexOf('qroll:') === 0) {
      const t = r.k.slice(6);
      if (r.v) rolledQids.add(t); else rolledQids.delete(t);
    }
  });
  restoreRolls();
}
loadRolls();
/* the burndown's bars (#142), on #151's gate and for #151's reason.

   A bar is a VALUE re-rendered, not an element that moved, so the opt-in
   rule's default is that it does not animate — and if the panel re-rendered
   its bars on every tick, a bar creeping by one pixel every two seconds
   would be motion with nothing behind it, which is exactly what #151's gate
   exists to prevent. But when the numbers really change, a bar jumping to a
   new height is the same snap the section fold was, one panel down.

   So: gated on the SERIES, never on the tick, and animated by height alone,
   because the panel's own height is fixed and nothing below it can move.

   AND THE GATE HERE IS AN OPTIMISATION, NOT A BEHAVIOUR — which #151's is
   not, and the difference is worth stating rather than leaving for someone
   to assume. A commit row can move because something ELSE re-laid the page
   out, so #151's gate has an observable effect and a guard that constructs
   it. A bar's height is a pure function of the series, so "the data changed"
   and "a bar moved" are the same event: delete this gate and `regroupBars`
   early-returns on every equal height, and no outcome changes. It is kept
   for the forced layouts it saves twice a second, forever. It is NOT
   guarded, and that is deliberate — a check that cannot fail is worse than
   no check, because its message sends the next person to the wrong file.
   That last part is why this needs no FLIP over neighbours — and it is a
   PREMISE, not an aside, so `burndown.mjs` asserts the panel height is
   invariant across a data change rather than taking my word for it. #204 is
   what a reasoned exemption costs when nobody checks its premise.

   Keyed by bucket AND series: two bars share a column and three share a
   bucket, so the bucket alone is not an identity — the shortening that
   merged three cards into one series in a trace was this same mistake. */
function snapshotBars() {
  const m = new Map();
  document.querySelectorAll('.bd .bdbar[data-bk]').forEach(el =>
    m.set(el.dataset.bk + '/' + el.dataset.series, {
      h: el.getBoundingClientRect().height,
      // #417 c3: weight travels with height so a commits-only change does
      // not snap. parseFloat of computed border-top-width is the px value.
      cap: parseFloat(getComputedStyle(el).borderTopWidth) || 0,
    }));
  return m;
}
function regroupBars(before) {
  if (rmr || !before || !before.size) return;
  document.querySelectorAll('.bd .bdbar[data-bk]').forEach(el => {
    const was = before.get(el.dataset.bk + '/' + el.dataset.series);
    const nowH = el.getBoundingClientRect().height;
    const nowCap = parseFloat(getComputedStyle(el).borderTopWidth) || 0;
    if (was === undefined) {          // a new bucket: snap, then ease in
      el.classList.add('dreamin');
      requestAnimationFrame(() => el.classList.remove('dreamin'));
      return;
    }
    const hMoved = Math.abs(was.h - nowH) >= 1;
    const capMoved = el.classList.contains('bdlevel') &&
                     Math.abs(was.cap - nowCap) >= 0.5;
    if (!hMoved && !capMoved) return;
    /* RESTORE THE PERCENTAGE, NEVER CLEAR THE HEIGHT. Every other travel on
       this page clears its inline height at the end because those elements
       get their size from layout — a bar gets its size from an inline
       `height:N%` written by the renderer, so clearing it leaves the bar at
       ZERO. The whole chart collapsed to its 2px rules after every animation
       and stayed there until the next re-render put fresh nodes in: #198's
       shape exactly, a permanent bug with a short, unreliable lifetime,
       laundered by something unrelated. Found by the guard's quiet-tick
       check, which measured the bars at 2px before the tick it was about. */
    const pct = el.style.height;
    const capEnd = el.style.borderTopWidth;
    el.style.transition = 'none';     // the enter-snap rule, again
    // border-box for `travelCard`'s reason: `now` came from
    // getBoundingClientRect, which is a BORDER box, and `.bdlevel` is a 2px
    // rule with no fill — left content-box the travel aims 2px past where it
    // ends and snaps when the percentage comes back.
    el.style.boxSizing = 'border-box';
    if (hMoved) el.style.height = was.h + 'px';
    if (capMoved) el.style.borderTopWidth = was.cap + 'px';
    void el.offsetWidth;
    el.style.transition = 'height .85s cubic-bezier(.32,.1,.2,1),' +
      'border-top-width .85s cubic-bezier(.32,.1,.2,1)';
    if (hMoved) el.style.height = nowH + 'px';
    if (capMoved) el.style.borderTopWidth = nowCap + 'px';
    setTimeout(() => {
      el.style.transition = ''; el.style.boxSizing = '';
      el.style.height = pct;
      // restore the rendered width (inline style from bdbar) rather than
      // clearing it — clearing would snap back to the CSS default 2px.
      if (capEnd) el.style.borderTopWidth = capEnd;
      else if (capMoved) el.style.borderTopWidth = nowCap + 'px';
    }, CARD_MS + 150);
  });
}
/* #487 — cycle the burndown's bucket width. The ladder is BURN_STEP_ORDER
   (same seconds as the server's BURN_STEPS). Preference rides localStorage
   keyed by target so a reload keeps the reading he picked; null means the
   server auto-picks. Fetching /data.json?burn_step=N is the only write
   surface — collect re-buckets, nothing else changes. */
function burnStepStorageKey() {
  try {
    return 'dw:burn-step:' + ((data && data.target) || '');
  } catch (e) { return 'dw:burn-step'; }
}
function loadBurnStepPref() {
  try {
    const v = parseInt(localStorage.getItem(burnStepStorageKey()), 10);
    if (BURN_STEP_ORDER.indexOf(v) >= 0) return v;
  } catch (e) {}
  return null;
}
function dataJsonUrl() {
  const s = burnStepPref;
  return (s && BURN_STEP_ORDER.indexOf(s) >= 0)
    ? '/data.json?burn_step=' + s : '/data.json';
}
async function cycleBurnStep(back) {
  const cur = (data && data.burndown && data.burndown.step)
    || BURN_STEP_ORDER[0];
  let i = BURN_STEP_ORDER.indexOf(cur);
  if (i < 0) i = 0;
  /* #489: plain click walks coarse→fine (his order: daily → 4-hourly →
     hourly → wrap to every-four-weeks); shift-click reverses. The
     ladder itself stays fine→coarse — click decrements, shift
     increments. */
  const L = BURN_STEP_ORDER.length;
  const next = BURN_STEP_ORDER[(i + (back ? 1 : L - 1)) % L];
  burnStepPref = next;
  try { localStorage.setItem(burnStepStorageKey(), String(next)); }
  catch (e) {}
  try {
    const wasBurn = burnKey(data);
    const bdHover = snapshotBdHover();   // #494: step cycle is also a swap
    // #523 rides reconciliation now (snapshotViewInputs retired in #505 p2):
    // a focused limit input is kept by id and value-stamped in the morph.
    setData(await (await fetch(dataJsonUrl())).json());
    const burnBefore = (burnKey(data) !== wasBurn) ? snapshotBars() : null;
    if (view && view.name === 'dashboard') {
      const html = await buildCurrent();
      setLiveContent(html);
      if (burnBefore) regroupBars(burnBefore);
      restoreBdHover(bdHover);
    }
  } catch (e) {}
}
addEventListener('click', e => {
  const btn = e.target.closest && e.target.closest('.bdstep');
  if (!btn) return;
  e.preventDefault();
  cycleBurnStep(e.shiftKey);
});

/* #499 — column-count limit. Client-only: no server state, no endpoint.
   localStorage per target (see burnLimitPref note above). Invalid input
   is refused quietly — re-render restores the previous value; no toast
   idiom exists on this panel. */
function burnLimitStorageKey() {
  try {
    return 'dw:burn-limit:' + ((data && data.target) || '');
  } catch (e) { return 'dw:burn-limit'; }
}
function loadBurnLimitPref() {
  try {
    const raw = localStorage.getItem(burnLimitStorageKey());
    if (raw == null || raw === '') return null;
    const v = parseInt(raw, 10);
    if (!Number.isFinite(v)) return null;
    return v;
  } catch (e) { return null; }
}
function ensureBurnLimit() {
  if (_burnLimitDidLoad) return;
  _burnLimitDidLoad = true;
  const v = loadBurnLimitPref();
  if (v !== null) burnLimitPref = v;
}
/* Active slice size: 0 = all (no slice); else 1..BURN_LIMIT_CAP. */
function activeBurnLimit() {
  ensureBurnLimit();
  if (burnLimitPref === null) return BURN_LIMIT_DEFAULT;
  if (!Number.isFinite(burnLimitPref) || burnLimitPref <= 0) return 0;
  return Math.min(BURN_LIMIT_CAP, Math.max(1, Math.floor(burnLimitPref)));
}
function displayBurnLimitValue() {
  ensureBurnLimit();
  if (burnLimitPref === null) return BURN_LIMIT_DEFAULT;
  if (!Number.isFinite(burnLimitPref)) return BURN_LIMIT_DEFAULT;
  if (burnLimitPref <= 0) return 0;
  return Math.min(BURN_LIMIT_CAP, Math.floor(burnLimitPref));
}
/* Generation so a hold-to-repeat burst cannot paint an older build over a
   newer pref: each applyBurnLimit bumps the gen; a superseded await drops. */
let _burnLimitRenderGen = 0;
async function rerenderBurnLimit() {
  if (!view || view.name !== 'dashboard' || !data) return;
  const gen = ++_burnLimitRenderGen;
  try {
    const bdHover = snapshotBdHover();
    // #523 rides reconciliation now (snapshotViewInputs retired in #505 p2).
    const html = await buildCurrent();
    if (gen !== _burnLimitRenderGen) return;   // a newer apply won
    setLiveContent(html);
    restoreBdHover(bdHover);
  } catch (e) {}
}
function applyBurnLimit(raw) {
  /* Refuse invalid quietly: non-numeric / empty leaves the prior pref
     and restores the input's displayed value (no toast idiom).
     <=0 → all/max (stored as 0). >cap → clamp to cap. */
  if (raw === '' || raw == null) {
    const inp = document.getElementById('bdlimit-in')
      || document.querySelector('.bdlimit-in');
    if (inp) inp.value = String(displayBurnLimitValue());
    return;
  }
  const n = parseInt(String(raw).trim(), 10);
  if (!Number.isFinite(n)) {
    const inp = document.getElementById('bdlimit-in')
      || document.querySelector('.bdlimit-in');
    if (inp) inp.value = String(displayBurnLimitValue());
    return;
  }
  const store = n <= 0 ? 0 : Math.min(BURN_LIMIT_CAP, n);
  burnLimitPref = store;
  _burnLimitDidLoad = true;
  try { localStorage.setItem(burnLimitStorageKey(), String(store)); }
  catch (e) {}
  rerenderBurnLimit();
}
function resetBurnLimit() {
  burnLimitPref = null;               // back to default 28
  _burnLimitDidLoad = true;
  try { localStorage.removeItem(burnLimitStorageKey()); }
  catch (e) {}
  rerenderBurnLimit();
}
/* #524 — one step of the limit, same clamp as applyBurnLimit / the input
   min/max. Returns whether the value moved (hold-at-bound is a quiet
   no-op, not an error). */
function bdStepNudge(dir) {
  const step = dir < 0 ? -1 : 1;
  const cur = displayBurnLimitValue();
  let next = cur + step;
  if (next < 0) next = 0;
  if (next > BURN_LIMIT_CAP) next = BURN_LIMIT_CAP;
  if (next === cur) return false;
  applyBurnLimit(String(next));
  return true;
}
/* Hold-to-repeat: state is MODULE-LEVEL, not on the button node. Each
   nudge re-renders the panel (applyBurnLimit → setLiveContent), so a
   timer bound to the button dies on the first step; the interval must
   outlive the nodes. First delay ~400ms, then ~80ms — conventional
   feel, no motion to reduce. A data tick mid-hold must not stop the
   repeat (#523/#524 composition): pointercancel from a destroyed node
   is ignored; only a real pointerup ends it. */
let _bdStepHold = null;   // {dir, delayTimer, repTimer} | null
let _bdStepSuppressClick = false;
function bdStepHoldStop() {
  if (!_bdStepHold) return;
  if (_bdStepHold.delayTimer) clearTimeout(_bdStepHold.delayTimer);
  if (_bdStepHold.repTimer) clearInterval(_bdStepHold.repTimer);
  _bdStepHold = null;
}
function bdStepHoldStart(dir) {
  bdStepHoldStop();
  _bdStepHold = { dir, delayTimer: null, repTimer: null };
  bdStepNudge(dir);
  _bdStepHold.delayTimer = setTimeout(() => {
    if (!_bdStepHold || _bdStepHold.dir !== dir) return;
    _bdStepHold.repTimer = setInterval(() => {
      if (!_bdStepHold) return;
      bdStepNudge(_bdStepHold.dir);
    }, 80);
  }, 400);
}
addEventListener('change', e => {
  const inp = e.target && e.target.closest && e.target.closest('.bdlimit-in');
  if (!inp) return;
  applyBurnLimit(inp.value);
});
addEventListener('keydown', e => {
  const inp = e.target && e.target.closest && e.target.closest('.bdlimit-in');
  if (!inp) return;
  if (e.key === 'Enter') { e.preventDefault(); inp.blur(); }
});
addEventListener('pointerdown', e => {
  const btn = e.target && e.target.closest && e.target.closest('.bdlimit-step');
  if (!btn || e.button !== 0) return;
  const dir = parseInt(btn.getAttribute('data-dir'), 10);
  if (dir !== 1 && dir !== -1) return;
  _bdStepSuppressClick = true;   // pointer path owns the first step
  bdStepHoldStart(dir);
});
addEventListener('pointerup', e => {
  if (!_bdStepHold) return;
  if (e.button === 0) bdStepHoldStop();
});
addEventListener('pointercancel', e => {
  if (!_bdStepHold) return;
  // Destroyed-by-swap cancel: the old button is already disconnected.
  // Keep the hold so a mid-hold data tick / re-render does not stop it.
  const t = e.target;
  if (t && t.isConnected === false) return;
  bdStepHoldStop();
});
addEventListener('click', e => {
  const step = e.target && e.target.closest && e.target.closest('.bdlimit-step');
  if (step) {
    e.preventDefault();
    if (_bdStepSuppressClick) { _bdStepSuppressClick = false; return; }
    // Keyboard activation (Enter/Space on a focused stepper).
    const dir = parseInt(step.getAttribute('data-dir'), 10);
    if (dir === 1 || dir === -1) bdStepNudge(dir);
    return;
  }
  const btn = e.target && e.target.closest && e.target.closest('.bdlimit-reset');
  if (!btn) return;
  e.preventDefault();
  resetBurnLimit();
});

/* #417 per-column hover/focus readout. Shows open + arrived + landed +
   commits so the level line's two meanings (height = open, weight =
   commits) are never left implied. The tip is an arrival: rundesc's
   atmospheric pose → ease-in / depart, never a native title blink.
   Height of .bd is unchanged — the tip floats. Accent is not spent. */
let bdtipCol = null;
let bdtipHideTimer = null;
function bdtipReduced() {
  try { return matchMedia('(prefers-reduced-motion: reduce)').matches; }
  catch (e) { return false; }
}
function bdtipText(col) {
  const stamp = col.dataset.stamp || '';
  const open = col.dataset.open;
  const arrived = col.dataset.arrived;
  const landed = col.dataset.landed;
  const commits = col.dataset.commits;
  // open named first: he asked "which I think is what the line is, right?"
  // — answer it before naming the weight's meaning.
  return `<span class="bdnum">${esc(open)}</span> open · ` +
    `${esc(arrived)}↑ ${esc(landed)}↓ · ` +
    `<span class="bdnum">${esc(commits)}</span> commit` +
    `${commits === '1' ? '' : 's'}` +
    (stamp ? ` · ${esc(stamp)}` : '');
}
function hideBdTip(immediate) {
  const tip = document.querySelector('.bd .bdtip');
  if (!tip || tip.hidden) { bdtipCol = null; return; }
  if (bdtipHideTimer) { clearTimeout(bdtipHideTimer); bdtipHideTimer = null; }
  const rm = !!immediate || bdtipReduced();
  const finish = () => {
    tip.hidden = true; tip.classList.remove('depart', 'pose');
    tip.innerHTML = ''; bdtipCol = null;
  };
  if (rm) { finish(); return; }
  tip.classList.remove('pose');
  tip.classList.add('depart');
  bdtipHideTimer = setTimeout(finish, 450);
}
/* settle=true: land fully visible with no pose replay. Used by #494's
   rearm across the tick re-render — from his POV the tip never left, so
   re-posing every two seconds would be motion with nothing behind it. */
/* #559 — cross-dissolve a live tip/inspector's CONTENT when its column
   changes. The container persists (no .depart, no pose, no opacity dip);
   old content becomes an outgoing .bdx ghost (the .depart envelope) and
   new content rides .bdi (the arrival envelope), both on the same .42s the
   surface's own arrival/departure use. Reduced motion snaps (content set
   directly, no layers). A no-op when the values are unchanged. */
function bdContentSwap(el, freshHTML) {
  if (bdtipReduced()) { el.innerHTML = freshHTML; return; }
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const tmp = document.createElement('div'); tmp.innerHTML = freshHTML;
  // current content: a prior swap leaves it in a .bdi layer; read that, not
  // the layered innerHTML (else the ghost would wrap a nested .bdi).
  const cur = el.querySelector('.bdi');
  const curHTML = cur ? cur.innerHTML : el.innerHTML;
  if (norm((cur || el).textContent) === norm(tmp.textContent)) {
    el.innerHTML = freshHTML; return;     // same values — no dissolve
  }
  const out = document.createElement('div');
  out.className = 'bdx';                   // outgoing ghost, old content
  out.innerHTML = curHTML;
  const ind = document.createElement('div');
  ind.className = 'bdi';                   // incoming, new content
  ind.innerHTML = freshHTML;
  el.innerHTML = '';
  el.append(out, ind);                     // ind in-flow sizes the box
  void el.offsetWidth;                     // start pose, then play both
  requestAnimationFrame(() => {
    out.classList.add('out');              // old departs (.depart shape)
    ind.classList.add('in');               // new arrives (.pose→rest)
  });
  const clear = () => { if (out.parentNode) out.remove(); };
  out.addEventListener('transitionend', clear, { once: true });
  setTimeout(clear, 540);                  // safety past the .42s envelope
}
function showBdTip(col, settle) {
  const bd = col && col.closest && col.closest('.bd');
  const tip = bd && bd.querySelector('.bdtip');
  if (!tip || !col || !col.dataset || col.dataset.open === undefined) return;
  if (bdtipHideTimer) { clearTimeout(bdtipHideTimer); bdtipHideTimer = null; }
  const same = bdtipCol === col && !tip.hidden;
  const live = !tip.hidden && !tip.classList.contains('depart');
  const fresh = bdtipText(col);
  bdtipCol = col;
  // #559: a LIVE tip switching columns persists and cross-dissolves its
  // content — no depart, no arrival pose, no opacity dip on the container.
  if (live && !same && !settle && !bdtipReduced()) { bdContentSwap(tip, fresh); return; }
  tip.innerHTML = fresh;
  if (same || settle) {
    tip.hidden = false;
    tip.classList.remove('depart', 'pose');
    return;
  }
  const rm = bdtipReduced();
  tip.hidden = false;
  tip.classList.remove('depart');
  if (rm) { tip.classList.remove('pose'); return; }
  // enter-snap: pose at opacity 0, reflow, then ease in
  tip.classList.add('pose');
  void tip.offsetWidth;
  requestAnimationFrame(() => tip.classList.remove('pose'));
}
// pointer + focus, delegated — columns are rebuilt every tick
/* #559 — the hit zone is the WHOLE column: the top open-tasks section
   (.bdnet), the bottom landed/arrivals section (.bdflow), and the gap
   between them. The two sections are separate flex tracks whose columns
   are pixel-aligned by index, so a point over ANY of them resolves to the
   net column at that index (the source of truth — it carries data-open,
   is keyboard-focusable, and feeds every reader). Geometry, not a DOM
   walk: the flow columns carry no data and are not inside .bdnet, so the
   old `.closest('.bdnet .bdcol[data-open]')` hit-test missed the entire
   bottom half. Returns null off the chart (above/below/beside). */
function bdColAtPoint(x, y) {
  const bd = document.querySelector('.bd');
  if (!bd) return null;
  const net = bd.querySelector('.bdnet');
  if (!net) return null;
  const flow = bd.querySelector('.bdflow');
  const top = net.getBoundingClientRect().top;
  const bot = flow ? flow.getBoundingClientRect().bottom
                   : net.getBoundingClientRect().bottom;
  if (y < top - 1 || y > bot + 1) return null;   // off the column strip
  for (const c of net.children) {
    if (!c.dataset || c.dataset.open === undefined) continue;
    const r = c.getBoundingClientRect();
    if (x >= r.left && x <= r.right) return c;
  }
  return null;
}
addEventListener('pointerover', e => {
  let col = e.target.closest && e.target.closest('.bdnet .bdcol[data-open]');
  if (!col) col = bdColAtPoint(e.clientX, e.clientY);   // #559 bottom section
  if (!col) return;
  lastBdPtr = { x: e.clientX, y: e.clientY };
  showBdTip(col);
  bdinspSchedule(col);             // #298: a hover that dwells inspects
});
/* keep the last pointer position while a hover/pin is live so a tick can
   rearm against the column still under the hand (#494), not a stale t0
   that a step-cycle may have retired. */
addEventListener('pointermove', e => {
  if (bdtipCol || bdinspCol || bdinspPin)
    lastBdPtr = { x: e.clientX, y: e.clientY };
}, { passive: true });
addEventListener('pointerout', e => {
  // #559: a column's full height is ONE hit zone, and moving between
  // columns PERSISTS the tip (showBdTip cross-dissolves, never hide-and-
  // show). Only a genuine leave — the pointer over NO column — departs.
  if (bdColAtPoint(e.clientX, e.clientY)) return;
  // leave the tip up while focus stays on a column (keyboard parity)
  const ae = document.activeElement;
  if (ae && ae.matches && ae.matches('.bdnet .bdcol[data-open]')) return;
  hideBdTip(false);
  bdinspCancel();
  if (!bdinspPin) hideBdInsp(false);   // a pinned (tapped) reading stays
});
addEventListener('focusin', e => {
  const col = e.target.closest && e.target.closest('.bdnet .bdcol[data-open]');
  if (!col) return;
  showBdTip(col);
  showBdInsp(col);   // #298: focus is already deliberate — no dwell
});
addEventListener('focusout', e => {
  const col = e.target.closest && e.target.closest('.bdnet .bdcol[data-open]');
  if (!col) return;
  const to = e.relatedTarget;
  if (to && to.closest && to.closest('.bdnet .bdcol[data-open]')) return;
  hideBdTip(false);
  bdinspCancel();
  if (!bdinspPin) hideBdInsp(false);
});
/* #298 — the column inspector: the richer reading a DELIBERATE look gets.
   The #417 glance tip answers a passing hover; the inspector answers a
   hover that DWELLS (700ms), a keyboard focus (immediate — focus is
   already deliberate), or a tap (pinned until dismissed). Same seam, same
   arrival idiom, same data attributes — never a second hover. */
let bdinspCol = null, bdinspPin = false, bdinspDwell = null;
let bdinspHideTimer = null;
const BD_DWELL = 700;
function bdstampFull(t) {
  const d = new Date(t * 1000);
  return d.toLocaleDateString(undefined,
    { weekday: 'short', day: 'numeric', month: 'short' }) + ' ' +
    d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}
function bdinspHTML(col) {
  const d = col.dataset;
  const t0 = +d.t0, t1 = +d.t1, now = Date.now() / 1000;
  const iv = bdstampFull(t0) + ' – ' + (t1 > now ? 'now' : bdstampFull(t1));
  // coverage the geometry cannot say: a period with no ledger commit
  // CARRIES the previous level; the current period is still arriving.
  const cov = [d.covered === '1' ? 'measured'
                                : 'level carried — no ledger commits'];
  if (t1 > now) {
    cov.push('period in progress');
    /* #498: % of this open period elapsed, from the column's real t0/t1
       (not from column index). Clamped to 0..100 so a clock skew past the
       bounds cannot invent a figure the interval itself forbids. */
    const span = t1 - t0;
    if (span > 0) {
      const pct = Math.max(0, Math.min(100,
        Math.round(100 * (now - t0) / span)));
      cov.push(pct + '% elapsed');
    }
  }
  return `<div class="bdin-iv">${esc(iv)}</div>` +
    `<div><span class="bdnum">${esc(d.open)}</span> open · ` +
    `${esc(d.arrived)} arrived · ${esc(d.landed)} landed · ` +
    `<span class="bdnum">${esc(d.commits)}</span> commit` +
    `${d.commits === '1' ? '' : 's'}</div>` +
    `<div class="bdin-cov">${esc(cov.join(' · '))}</div>`;
}
function bdinspLay(bd, col, el) {
  /* #487: consistent pin, not column-centred. RHS of the panel when the
     inspector's measured width fits in the right half (room derived from
     rendered layout — no guessed px breakpoint); otherwise above the
     chart. When above, also above .bdtip so the glance stats line and the
     details never overlap. Same pose/depart arrival; only the resting
     slot changes.
     #498 geometry: pin max-width to the panel in px before measuring so
     a long coverage line (…period in progress · N% elapsed) cannot make
     offsetWidth exceed the panel, and clamp left so left+width stays
     inside — the border-box CSS is the real fix; this is the placement
     half of the same guarantee. */
  const bdr = bd.getBoundingClientRect();
  const track = bd.querySelector('.bdnet');
  const tr = track ? track.getBoundingClientRect() : bdr;
  const tip = bd.querySelector('.bdtip');
  const tipOn = tip && !tip.hidden;
  const tipR = tipOn ? tip.getBoundingClientRect() : null;
  el.style.maxWidth = bdr.width + 'px';
  const w = el.offsetWidth, h = el.offsetHeight;
  const pad = 4;
  // room = inspector fits entirely in the right half of the panel
  const hasRoom = (w + pad * 2) <= (bdr.width / 2);
  el.dataset.bdslot = hasRoom ? 'rhs' : 'above';
  // horizontal clamp: never past the panel edges
  const clampL = left => Math.max(0, Math.min(left, Math.max(0, bdr.width - w)));
  if (hasRoom) {
    el.style.left = clampL(bdr.width - w) + 'px';
    el.style.right = 'auto';
    // below the tip when it is up (no overlap); otherwise above the track
    let top = tr.top - bdr.top - h - pad;
    if (tipR) {
      const tipBot = tipR.bottom - bdr.top;
      top = Math.max(top, tipBot + pad);
    }
    el.style.top = top + 'px';
  } else {
    // centred horizontally, fully above chart AND above the tip line
    el.style.left = clampL((bdr.width - w) / 2) + 'px';
    el.style.right = 'auto';
    let top = tr.top - bdr.top - h - pad;
    if (tipR) {
      const tipTop = tipR.top - bdr.top;
      top = Math.min(top, tipTop - h - pad);
    }
    el.style.top = top + 'px';
  }
}
function bdinspCancel() {
  if (bdinspDwell) { clearTimeout(bdinspDwell); bdinspDwell = null; }
}
function hideBdInsp(immediate) {
  const el = document.querySelector('.bd .bdinsp');
  bdinspCancel();
  if (!el || el.hidden) { bdinspCol = null; bdinspPin = false; return; }
  if (bdinspHideTimer) { clearTimeout(bdinspHideTimer); bdinspHideTimer = null; }
  const finish = () => {
    el.hidden = true; el.classList.remove('depart', 'pose');
    el.innerHTML = ''; bdinspCol = null; bdinspPin = false;
  };
  if (!!immediate || bdtipReduced()) { finish(); return; }
  el.classList.remove('pose');
  el.classList.add('depart');
  bdinspHideTimer = setTimeout(finish, 450);
}
/* settle=true: same contract as showBdTip's settle — rearm across a tick
   without replaying the arrival pose (#494). */
function showBdInsp(col, settle) {
  const bd = col && col.closest && col.closest('.bd');
  const el = bd && bd.querySelector('.bdinsp');
  if (!el || !col.dataset || col.dataset.t0 === undefined) return;
  bdinspCancel();
  if (bdinspHideTimer) { clearTimeout(bdinspHideTimer); bdinspHideTimer = null; }
  const same = bdinspCol === col && !el.hidden;
  const live = !el.hidden && !el.classList.contains('depart');
  const fresh = bdinspHTML(col);
  bdinspCol = col;
  // #559: a LIVE inspector switching columns persists and cross-dissolves
  // its content — no depart, no arrival pose, no opacity dip on the box.
  // .bdi (new content) is in-flow, so it sizes the box before bdinspLay.
  if (live && !same && !settle && !bdtipReduced()) {
    el.hidden = false;
    bdContentSwap(el, fresh);
    bdinspLay(bd, col, el);
    return;
  }
  el.innerHTML = fresh;
  el.hidden = false;               // visible before measuring
  bdinspLay(bd, col, el);
  if (same || settle) { el.classList.remove('depart', 'pose'); return; }
  el.classList.remove('depart');
  if (bdtipReduced()) { el.classList.remove('pose'); return; }
  el.classList.add('pose');        // enter-snap, then ease in (#417 idiom)
  void el.offsetWidth;
  requestAnimationFrame(() => el.classList.remove('pose'));
}
/* #494 — carry hover/pin across the live tick's innerHTML swap.

   The dashboard re-renders whenever ANY watched file changes (status.json
   every few seconds on the 2s /mtime poll). Without a carry, burnPanel
   recreates .bdtip/.bdinsp as hidden empty nodes and bdtipCol/bdinspCol
   still reference the detached columns — the tip fades in, then 1–2s later
   "it all resets" with the mouse unmoved. Detach also fires pointerout,
   which arms hide timers against the FRESH nodes; restore cancels those
   and rearms for the column still under the pointer (or the pinned t0).

   Identity is data-t0 (the bucket), never the node. settle=true so a
   rearm is not a second arrival every two seconds. Departing surfaces are
   not snapshotted — a leave already under way stays a leave. */
let lastBdPtr = null;
function bdColByT0(t0) {
  if (t0 == null || t0 === '') return null;
  const want = String(t0);
  let found = null;
  document.querySelectorAll('.bdnet .bdcol[data-open]').forEach(c => {
    if (c.dataset.t0 === want) found = c;
  });
  return found;
}
/* #505 p2 — KEPT (not absorbed): the .bdtip/.bdinsp hover overlay is a
   DERIVED UI surface the diff is structurally blind to. The server emits
   both hidden/empty, so the reconciler would stamp `hidden`, strip the
   .depart/.pose classes and clear their content every tick; their
   visibility and content are recomputed by showBdTip/showBdInsp from
   module-level state (bdinspPin, bdtipCol/bdinspCol, hide timers, lastBdPtr)
   — and stamping stale content would show a wrong number after data changes.
   Kept .bdcol[data-t0] nodes mean no detach/pointerout fires under
   reconciliation, but the overlay still has to be re-driven. */
function snapshotBdHover() {
  const tip = document.querySelector('.bd .bdtip');
  const insp = document.querySelector('.bd .bdinsp');
  const tipLive = !!(tip && !tip.hidden && !tip.classList.contains('depart')
                     && bdtipCol);
  const inspLive = !!(insp && !insp.hidden && !insp.classList.contains('depart')
                      && bdinspCol);
  const act = document.activeElement;
  const focusCol = act && act.matches &&
    act.matches('.bdnet .bdcol[data-open]') ? act : null;
  return {
    tipT0: tipLive ? bdtipCol.dataset.t0 : null,
    inspT0: (inspLive || bdinspPin) && bdinspCol ? bdinspCol.dataset.t0 : null,
    pin: !!bdinspPin,
    focusT0: focusCol ? focusCol.dataset.t0 : null,
    hadTip: tipLive,
    hadInsp: inspLive,
  };
}
function restoreBdHover(s) {
  if (!s || (!s.tipT0 && !s.inspT0 && !s.pin && !s.focusT0)) return;
  // detach pointerout may have armed hide timers on the new nodes
  if (bdtipHideTimer) { clearTimeout(bdtipHideTimer); bdtipHideTimer = null; }
  if (bdinspHideTimer) { clearTimeout(bdinspHideTimer); bdinspHideTimer = null; }
  bdinspCancel();
  let under = null;
  if (lastBdPtr) {
    try { under = bdColAtPoint(lastBdPtr.x, lastBdPtr.y); }   // #559 full-height
    catch (e) {}
  }
  if (s.focusT0) {
    const fc = bdColByT0(s.focusT0);
    if (fc) {
      const keepPin = s.pin;
      fc.focus();   // focusin shows tip + insp; settle not needed
      if (keepPin && s.inspT0) {
        const pc = bdColByT0(s.inspT0);
        if (pc) { bdinspPin = true; showBdInsp(pc, true); }
      }
      return;
    }
  }
  if (s.pin && s.inspT0) {
    const pc = bdColByT0(s.inspT0);
    if (pc) { bdinspPin = true; showBdInsp(pc, true); }
    if (under) showBdTip(under, true);
    else if (s.hadTip && s.tipT0) {
      const tc = bdColByT0(s.tipT0);
      if (tc) showBdTip(tc, true);
    }
    return;
  }
  // Unpinned hover: prefer the column under the pointer (real mouse);
  // fall back to snapshotted t0 (synthetic pointerover has no coords).
  const col = under || (s.tipT0 && bdColByT0(s.tipT0));
  if (!col) return;
  if (s.hadTip || under) showBdTip(col, true);
  if (s.hadInsp) {
    const ic = under || (s.inspT0 && bdColByT0(s.inspT0)) || col;
    if (ic) showBdInsp(ic, true);
  } else if (s.hadTip || under) {
    bdinspSchedule(col);           // dwell was mid-flight — restart
  }
}
function bdinspSchedule(col) {
  if (bdinspPin) return;           // a pinned reading is not hover's to move
  bdinspCancel();
  bdinspDwell = setTimeout(() => showBdInsp(col), BD_DWELL);
}
/* tap selects / dismisses — no preventDefault, so chart scroll is never
   the inspector's to break. A tap on another column moves the pin; a tap
   outside the chart lets it go. */
addEventListener('click', e => {
  const col = e.target.closest && e.target.closest('.bdnet .bdcol[data-open]');
  if (col) {
    if (bdinspPin && bdinspCol === col) hideBdInsp(false);
    else { bdinspPin = true; showBdInsp(col); }
    return;
  }
  if (bdinspPin) hideBdInsp(false);
});
addEventListener('keydown', e => {
  if (e.key === 'Escape' && bdinspCol) { hideBdTip(true); hideBdInsp(false); }
});
/* a scrolled page moves the column out from under the reading — depart,
   never drift along stale coordinates. */
addEventListener('scroll', () => { if (bdinspCol) hideBdInsp(false); },
  { passive: true, capture: true });
/* switching a card's mode: the indicator slides, the placeholder follows,
   and the field keeps whatever is typed in it — the text is the point, the
   mode is only where it goes. */
addEventListener('click', e => {
  const btn = e.target.closest && e.target.closest('.qmode');
  if (!btn) return;
  e.preventDefault();
  // membership is fixed here, so the indicator slides rather than lands
  setCardMode(btn.closest('.qcompose'), btn.dataset.mode, false);
});
/* #177 — a text box grows with what he types, to its own ceiling, then
   scrolls. The ceiling is a per-surface contract carried as `data-max-rows`
   (the composer 15, an answer/note box 6); the asymmetry is deliberate, so a
   long thought in the floating composer never shoves the question list for a
   ten-second sentence in a card.

   ONE gesture, not a second one. The box's HEIGHT travels on the page's
   atmospheric height-travel curve (.85s, the same `cubic-bezier(.32,.1,.2,1)`
   the card fold and #104's regroup use), and what sits below it is CARRIED
   by that travel rather than teleported: a height transition re-flows the
   box's containing block every frame, so the cards (or the composer's send
   row) ride the growth continuously, welded to it — the same outcome #104's
   FLIP produces for a discrete regroup, reached the way a small, frequent,
   one-line change reaches it. The plan's literal seam (snapshot → resize →
   `regroupCards(…, card)`) was the first instinct and is the right gesture,
   but `travelCard` clamps the host card to its old height with
   `overflow:hidden` for the travel, which HIDES the line he just typed (and
   its caret) for the whole .85s on every newline — unacceptable for the most
   frequent animation on the page. Letting the box itself own the travel keeps
   the caret in view and carries everything below on the same curve; the
   gesture is the page's, only the carrier differs.

   `animate=false` is the enter-snap rule again: a restore (the tick putting
   his text back, a draft surfaced on open) must not re-grow the box every two
   seconds, so it sets the height with the transition paused. A SEND clears the
   box through `clearBox` for the same reason — the card's own regroup already
   owns that height travel, and a second one on the textarea would fight it. */
function lineHeightOf(ta, cs) {
  cs = cs || getComputedStyle(ta);
  const lh = parseFloat(cs.lineHeight);
  if (isFinite(lh) && lh > 0) return lh;     // a resolved pixel line-height
  // 'normal' is font-metric-dependent and not a number: measure it with a
  // probe that inherits the box's own font, so the ceiling tracks the font
  // rather than a guessed ratio tuned to today's.
  const p = document.createElement('div');
  p.style.cssText = 'position:absolute;visibility:hidden;white-space:pre;' +
    'border:0;padding:0;margin:0;width:0;font:' + cs.font +
    ';line-height:' + cs.lineHeight;
  p.textContent = 'M\nM';
  document.body.appendChild(p);
  const h = p.getBoundingClientRect().height / 2;
  p.remove();
  return h || (parseFloat(cs.fontSize) * 1.2);
}
function fitText(ta, animate) {
  if (!ta) return;
  // #570 — once the user has dragged the composer's resize handle, autosize
  // yields to his height for the rest of this composition: a content fit would
  // otherwise overwrite his resize on the next keystroke (the box #177 noted
  // `resize:none` to prevent). A submit (or a close that re-renders the box)
  // clears `_manual` and re-enables growth.
  if (ta._manual) return;
  const rows = parseInt(ta.dataset.maxRows, 10);
  if (!rows) return;                          // no ceiling: leave the box alone
  const cs = getComputedStyle(ta);
  if (!ta._lh) ta._lh = lineHeightOf(ta, cs); // constant for the font; cache it
  // border belongs to the border-box `height` but not to `scrollHeight`, so it
  // is added back so a 1px-bordered composer box never reads 2px short and
  // starts scrolling a line early.
  const bord = parseFloat(cs.borderTopWidth) + parseFloat(cs.borderBottomWidth);
  const ceil = Math.round(rows * ta._lh + bord);
  const oldH = ta.getBoundingClientRect().height;
  // measure the content's TRUE height: shrink first (transition paused) so a
  // deletion reads back smaller rather than as the box it currently fills —
  // scrollHeight otherwise returns max(content, client) and never shrinks.
  ta.style.transition = 'none';
  ta.style.height = 'auto';
  const want = ta.scrollHeight + bord;
  const target = Math.max(ta._lh + bord, Math.min(want, ceil));
  if (animate) {
    // the enter-snap rule, inverted: commit the OLD height with no transition,
    // then set the target with the standing transition restored, so the box
    // travels from where it was to where its content now needs.
    ta.style.height = oldH + 'px';
    void ta.offsetWidth;
    ta.style.transition = '';                 // the CSS height transition reapplies
    ta.style.height = target + 'px';
  } else {
    // a restore (tick, draft): snap to the target and THEN restore the
    // standing transition, so the box does not re-grow under him on every
    // tick yet the next input he types still travels.
    ta.style.height = target + 'px';
    void ta.offsetWidth;
    ta.style.transition = '';
  }
  ta._fitH = target;                          // #570: the height autosize owns
}
/* snap a box to its floor — used after a send clears it, where the CARD's own
   regroup already owns the height travel and a second transition on the
   textarea would animate against it. Sets no height, so the CSS `min-height`
   is the floor. */
function clearBox(ta) {
  if (!ta) return;
  ta.style.transition = 'none';
  ta.style.height = '';
  ta._manual = false;            // #570: a send re-enables autosize for the next box
  ta._fitH = null;               //   (no inline height to diverge from)
  void ta.offsetWidth;
  ta.style.transition = '';
}
/* save a drafted answer as he types (#269 acute). Delegated on `document`
   because the box is recreated by every re-render — a listener bound to the
   node would die with it. Keyed by `data-qid` (the question's title identity),
   resolved against the live card so the draft never lands under the wrong
   question, and written through `dwDraft` so the composer's rules apply
   verbatim: no debounce, wrapped storage, and a value of '' removes the key
   (deleting his words is his act, unlike a close or a failed send). */
addEventListener('input', e => {
  const t = e.target;
  if (!t || t.tagName !== 'TEXTAREA' || !/^qi[oa]\d+$/.test(t.id)) return;
  const card = t.closest('.qa[data-qid]');
  if (!card || !card.dataset.qid) return;
  let title = null;
  try { title = decodeURIComponent(card.dataset.qid); } catch (er) { return; }
  if (title) dwDraft.save(title, t.value);
  fitText(t, true);                           // #177: the box grows with what he typed
});
/* #708 — the /chat reply box grows with the same gesture as the answer box.
   Its draft persists through DraftStore under key chat:<id> (bound in
   bindChatReplyDraft); this listener owns only the height. The id guard makes
   it a no-op on the answer/note boxes the listener above already owns. */
addEventListener('input', e => {
  const t = e.target;
  if (!t || t.id !== 'chatreplybox') return;
  fitText(t, true);
});
/* opening or closing a disclosure INSIDE a card HIMSELF — the folded entry
   (#111) or its settled follow-up thread (#128) — is the same moment as the
   loop folding one: a card changes height and its neighbours close or open the
   gap underneath it. So both go through the same snapshot and the same
   regroup, rather than growing a second way to move a card. That is the
   styleguide's line: an expand inside a list whose OTHER members move is the
   one that animates; a standalone `<details>` still toggles instantly. The
   native toggle is prevented because <details> flips before any event we could
   measure from, and a FLIP with nothing to measure is a jump. */
/* ...AND A COMMIT ROW IS THE SAME MOMENT (#166), which is why this handler
   takes a list of surfaces rather than gaining a sibling. A commit row IS
   its own `<details>` where a card CONTAINS one, so the element that resizes
   differs — and that is the only thing that differs. Everything else (the
   snapshot, the regroup, the body ghost, the reveal, reduced motion) is
   shared, and a second handler is how one gesture becomes two that drift.

   The `host` is the member of the keyed list whose box changes: for a card
   that is the `.qa` around the toggle, for a commit row it is the toggle
   itself. `nestedToggle` reads true in both cases (neither `det` is the
   card's own `.qfold`), so the departing body is ghosted by this handler at
   the rect it had rather than clipped from the card-level clone. */
const EXPAND_SURFACES = [
  { sum: '.qa details > summary', host: '.qa[data-qid]', list: QA_LIST },
  // #250: keyed host requires data-aid. Missing-aid answered details still
  // match the summary selector, so preventDefault would leave them dead
  // without a listless fallback (no invented sentinel, no data-keep).
  { sum: '.aq.answered > summary', host: '.aq.answered[data-aid]',
    list: ANSWER_LIST, listlessFallback: true },
  { sum: '.git .commit > summary', host: '.git .commit[data-sha]',
    list: GIT_LIST },
];
/* Human-click fold for a <details> that is not a member of a keyed list
   (#250). Reuses travelCard / revealBody / dreamAway — the qsec shape.
   Open-state survival across ticks is not this function's job: expand()
   peeks and .qsec carry data-keep so snapshotFolds restores them; listless
   missing-aid answered details deliberately omit it and re-close on tick.
   reduced-motion still toggles; only timing drops. */
function foldDetailsLocal(det) {
  if (!det) return;
  if (rmr) { det.open = !det.open; return; }
  const was = det.getBoundingClientRect();
  const corpse = det.open ? det.cloneNode(true) : null;
  det.open = !det.open;
  const now = det.getBoundingClientRect();
  travelCard(det, was, now, false);
  if (det.open) revealBody(det);
  else dreamAway(document.querySelector('.wrap'), corpse, was, now.height);
}
addEventListener('click', e => {
  if (!e.target.closest) return;
  const m = EXPAND_SURFACES.find(s => e.target.closest(s.sum));
  if (!m) return;
  /* #452: a REAL LINK inside the summary (the folded card's focus
     affordance) is navigation, not a fold — decline it so the router's
     handler takes it. This handler is registered FIRST, so its
     preventDefault would otherwise mark the click handled and the
     router's `e.defaultPrevented` check would skip the navigation: the
     link read as present but only ever toggled the fold. */
  if (e.target.closest('a')) return;
  e.preventDefault();
  const det = e.target.closest(m.sum).parentElement;
  const host = det.closest(m.host);
  if (!host) {
    // #250: answered summary matched, but no data-aid host — listless fold
    if (m.listlessFallback) foldDetailsLocal(det);
    return;
  }
  // measured while it still HAS a box: a closed <details> keeps its children
  // in the DOM and gives them no geometry, so the rect has to be taken first
  const leaving = (det.open && nestedToggle(host, det)) ? cardBody(host, det) : [];
  const rects = leaving.map(c => c.getBoundingClientRect());
  const before = snapshotCards(m.list);
  det.open = !det.open;
  regroupCards(before, det, m.list);
  leaving.forEach((c, i) => ghostNode(c, rects[i]));
});
/* the dashboard's questions section (#141) opening and closing — the SAME
   moment one level up (#196), and his report of it was that the questions
   "just appear and disappear".

   It is not a card, so it does not go through `regroupCards`: the cards inside
   it have no geometry at all while the section is shut, and a FLIP from a zero
   rect is a slide in from the page's top-left corner. It is instead the card
   fold with the roles enlarged — a summary that survives, a body that arrives
   or departs, and a HEIGHT that carries everything below it. So it reuses the
   three pieces that already say that: `travelCard` for the height (which is
   what moves reviews, files, status and the tint picker, continuously and for
   free, welded to the section they are following), `revealBody` for the
   arrival, `dreamAway` for the departure.

   THE DEPARTURE'S DIRECTION IS ALREADY RIGHT and that is worth saying out loud
   (#174): the panels below travel UP to close the gap, and the standing ghost
   rises, so this needed no sign of its own. The commits panel is the exception
   here, not the rule.

   The corpse is cloned BEFORE the toggle: a closed <details> keeps its
   children in the DOM and gives them no geometry, so a clone taken afterwards
   is a picture of nothing. Same reason the native toggle is prevented — it
   flips before any event we could measure from.

   Under reduced motion this handler declines the click entirely and the native
   toggle does the work at once, which is the hard contract: timing changes,
   function does not. */
addEventListener('click', e => {
  const sum = e.target.closest && e.target.closest('.qsec > summary');
  if (!sum || rmr) return;
  e.preventDefault();
  const det = sum.parentElement;
  const was = det.getBoundingClientRect();
  const corpse = det.open ? det.cloneNode(true) : null;
  det.open = !det.open;
  const now = det.getBoundingClientRect();
  travelCard(det, was, now, false);
  if (det.open) revealBody(det);
  // clipped to the line the summary still fills, exactly as a folding card
  // clips to the title it keeps
  else dreamAway(document.querySelector('.wrap'), corpse, was, now.height);
});
/* Plain read peeks — dreams, .md files, status overflow (#277 reusable).
   These were native <details> toggles with no animation: closing one snapped
   the body away. They now go through the same foldDetailsLocal path as the
   keyed-list fallback (#250), so the body departs on the mist idiom and
   everything below travels rather than jumping. reduced-motion: native toggle.
   Open state rides data-keep via expand()'s keep arg + snapshotFolds
   (status-rest, file:*, dream:*, dreams-archive) — same #141 rule the
   questions section already had; without it the tick re-closes under him. */
addEventListener('click', e => {
  const sum = e.target.closest && e.target.closest('.peek > summary');
  if (!sum || rmr) return;
  e.preventDefault();
  foldDetailsLocal(sum.parentElement);
});
addEventListener('resize', () => paintIndicators(true));
/* ── the persistent chrome (#110) ─────────────────────────────────────────
   The heading is not content, it is the page's frame: the same + opener, a
   title, and a crumb row, on every route. While it lived inside #view it
   dissolved and was rebuilt on every navigation, which is why a route change
   read as "the elements jump around" rather than as the page opening up. So
   it is a SIBLING of #view — the standing #dreambg already has — it survives
   the route change, and it travels to its new position.

   Crumbs are KEYED, and that is the whole trick: a survivor has to be
   literally the same element before and after, or a FLIP has nothing to
   measure and you get a fade where a glide was asked for. `home` is one
   crumb across three routes even though its text gains and loses an arrow. */
const TITLES = {
  dashboard: () => 'dreamwork watch',
  questions: () => 'questions',
  answers: () => 'answers',
  /* #284: the BASENAME is the heading. The parent path is metadata and lives
     one line down, in the crumb row (`crumbsFor`). */
  file: v => esc(fileBase(v.param || '')),
  review: v => `review<span class="revname">${esc(v.param || '')}</span>`,
  /* #452: the heading names the SURFACE, not the question — a title can run
     to a line and a half, and it is rendered in full by the card directly
     below. When the key resolves nowhere the missing notice says so. */
  question: () => 'question',
  /* #596 — the bare surface word, like the questions/answers/reviews
     listings and the word TITLE_ROUTE builds the tab from. #452's rule: the
     heading names the SURFACE. An open artifact (`?p=`) is named by the tab
     (TITLE_ROUTE appends it) and reachable from the crumb row's pip — the
     heading stays the surface either way. */
  research: () => 'research',
  /* #545 — the listing surface; the heading names it like the research
     listing does. */
  reviews: () => 'reviews',
  /* #562 — the chat page's heading is the chat's DERIVED title (from d.chats,
     the same derivation the list shows), not the bare word "chat": a chat is
     its own subject, so its name heads the page. Falls back to 'chat' while
     data loads or for an unknown id (the body degrades in-voice either way). */
  chat: (v, d) => {
    const c = ((d && d.chats) || []).find(x => x.id === v.param);
    return c ? esc(c.title) : 'chat';
  },
};
/* The copy button carries no path of its own, on purpose: it reads
   `view.param`, which is what the router parsed out of the URL and therefore
   the same string the heading and the metadata line were built from. A
   `data-path` attribute would be a second copy of the truth AND a new
   attribute-injection site — `esc()` escapes `<`/`>`/`&` but not `"`, so a
   query string can already break out of an attribute here (see the note in
   watch-design.md). Reading the route needs no escaping at all.

   `aria-describedby` names the metadata line and then the heading, in that
   order, so a screen reader announces the button as the full path in reading
   order: "copy path, button, .dreamwork/docs/research/, notes.md". When there
   is no parent it describes itself by the heading alone. */
const copyPathBtn = hasDir =>
  `<button type="button" class="fcopy"` +
  ` aria-describedby="${hasDir ? 'fdir htitle' : 'htitle'}">copy path</button>`;
/* #252 — Rendered / Source, beside the path, for markdown only.
   TWO ORDINARY INTERNAL LINKS, not buttons, and that is three things at once:
   the mode is deep-linkable because it is in the href, it is keyboard- and
   middle-click-operable because it is a link, and the swap rides the router's
   existing dissolve because `isInternal` already claims `/file`. A pair of
   buttons would have needed a handler, a history push and a transition of its
   own — three re-implementations of what the route already does.

   THE `.on` STATE IS DELIBERATELY NOT IN THIS HTML. `renderChrome` rewrites a
   crumb whose html changed, and a rewritten `.sgroup` is fresh nodes with a
   0-width indicator — the outline would grow out of the row's left edge
   instead of sliding to the other label. Held out, the switch is a SURVIVOR
   across a mode change and `paintFileMode` slides it: the sliding selection
   group's own documented gesture (#121). That is also why the crumb is
   declared `stable`. */
const fileModeSwitch = p => {
  const base = '/file?p=' + encodeURIComponent(p);
  return '<span class="sgroup fmodes" role="group" aria-label="markdown view">' +
    '<span class="sgind" aria-hidden="true"></span>' +
    `<a class="sgbtn fmode" data-mode="rendered" href="${base}">rendered</a>` +
    `<a class="sgbtn fmode" data-mode="source" href="${base}&amp;view=source">source</a>` +
    '</span>';
};
/* The switch's state, painted AFTER the crumb row is assembled, because the
   indicator needs the row's final geometry. `slide` is true only when the
   group SURVIVED the render — a group that just arrived lands instead, on the
   enter-snap rule, and reduced motion always lands (`slideIndicator`). */
function paintFileMode(v, slide) {
  const g = document.querySelector('#meta .fmodes');
  if (!g) return;
  const want = (v && v.mode === 'source') ? 'source' : 'rendered';
  for (const a of g.querySelectorAll('.fmode')) {
    const on = a.dataset.mode === want;
    a.classList.toggle('on', on);
    // `aria-current="page"` rather than a radio's checked state: these ARE
    // pages, and saying so is what makes the switch honest to a screen reader
    // about being navigation.
    if (on) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  }
  slideIndicator(g, !slide);
}
function crumbsFor(v, d) {
  const home = { k:'home', html:'<a href="/">&larr; dashboard</a>' };
  if (v.name === 'questions' || v.name === 'answers') return [home];
  if (v.name === 'file') {
    const p = v.param || '', dir = fileDir(p);
    const row = [home];
    // `.wrapany` is the crumb row's wrap exception, named once in style.css;
    // `.fdir` is now only this path's colour and selectability (#595).
    if (dir) row.push({ k:'fdir', html:`<span class="fdir wrapany" id="fdir">${esc(dir)}</span>` });
    row.push({ k:'fcopy', html: copyPathBtn(!!dir) });
    // Markdown only (#252). The key carries the PATH, so switching files
    // departs one switch and arrives another (a different file's control),
    // while switching MODE on one file keeps the same element and lets the
    // indicator slide.
    if (isMarkdownFile(p))
      row.push({ k:'fview:' + p, html: fileModeSwitch(p), stable: true });
    row.push({ k:'pip', html: pipBtn('/file?p=' + encodeURIComponent(p),
                                     p || 'file') });
    return row;
  }
  if (v.name === 'review') return [
    { k:'qs', html:'<a href="/questions">&larr; questions</a>' },
    { k:'home', html:'<a href="/">dashboard</a>' },
    { k:'pip', html: pipBtn('/reviewraw?p=' + encodeURIComponent(v.param || ''),
                            'review: ' + (v.param || '')) }];
  // #452: the focused page belongs to the questions list — the way back is
  // the same pair the review dock carries (no artifact to pop out here).
  if (v.name === 'question') return [
    { k:'qs', html:'<a href="/questions">&larr; questions</a>' },
    { k:'home', html:'<a href="/">dashboard</a>' }];
  // #484: the listing's way back is the dashboard; an artifact adds the
  // listing as its middle crumb and the raw pop-out, the review pair's
  // shape with no questions half (there is no pairing to return to).
  if (v.name === 'research') {
    const row = [{ k:'home', html:'<a href="/">&larr; dashboard</a>' }];
    if (v.param) row.push(
      { k:'list', html:'<a href="/research">research</a>' },
      { k:'pip', html: pipBtn('/researchraw?p=' + encodeURIComponent(v.param),
                              'research: ' + v.param) });
    return row;
  }
  // #545: the reviews listing's way back is the dashboard, the same single
  // home crumb the research listing carries (no artifact here, just the list).
  if (v.name === 'reviews')
    return [{ k:'home', html:'<a href="/">&larr; dashboard</a>' }];
  // #562: the chat page's way back is the dashboard — the chat list lives
  // there. Same single home crumb the listings carry.
  if (v.name === 'chat')
    return [{ k:'home', html:'<a href="/">&larr; dashboard</a>' }];
  if (!d) return [];
  // #491 — the version crumb sits BESIDE the freshness age ("updated Ns ago"),
  // and a bare migration filename in that slot read as "this file changed Ns
  // ago". It is not: the value is the target's RECORDED skill version
  // (.dreamwork/skill-version, written by orient), a different source from the
  // skill tree's latest migration (skill_identity). The value is honest; the
  // defect was the adjacency implying an age, because the crumb named nothing
  // about what it IS. So it says so — a dim "skill" label before the name —
  // and the neighbour no longer supplies the meaning. Built only when there is
  // a name to show (an empty version file renders no crumb, not a bare dot).
  // #595 — BOTH of these crumbs carry a value whose length is set by data, not
  // by design: `target` is whatever absolute path this checkout lives at, and
  // `version` is an arbitrary-length migration FILENAME. A `.crumb` is
  // `white-space:nowrap` (#284), so neither could break and the dashboard
  // scrolled sideways by 28px at 390px — against the styleguide's promise that
  // it never does. They take `.wrapany` on an INNER span, the same shape `.fdir`
  // uses, so the crumb keeps the nowrap that holds its own separator. Nothing
  // here is tuned to today's string: any length wraps.
  const sv = d.files['skill-version'];
  const row = [
    { k:'target', html:'<span class="wrapany">' + esc(d.target) + '</span>' },
  ];
  if (sv) row.push({ k:'version',
    html:'<span style="color:var(--dim)">skill</span> ' +
         '<span class="wrapany">' + esc(sv) + '</span>' });
  row.push(
    { k:'updated', html:'<span id="upd"></span>' },
    // the count is zero whether everything is answered or the file cannot be
    // read, so the crumb must not quietly render the broken case as the calm
    // one (#136) — it is the badge he glances at from every route.
    { k:'openq', html: d.questions_health === 'unreadable'
        ? `<a class="q qh" href="/questions">questions unreadable</a>`
        : d.open_questions > 0
        ? `<a class="q" href="/questions">${d.open_questions} open ` +
          `question${d.open_questions > 1 ? 's' : ''}</a>`
        : `<a class="q" href="/questions" style="color:var(--dimmer)">` +
          `questions</a>` });
  return row;
}
/* where the heading sits RIGHT NOW — taken before the column class flips,
   because that flip is what moves everything. */
function chromeSnapshot() {
  const meta = document.getElementById('meta');
  const titleEl = document.querySelector('#chrome .htitle');
  if (!meta || !titleEl) return null;
  const at = new Map();
  for (const el of meta.children) at.set(el.dataset.k, el.getBoundingClientRect());
  return { at, title: titleEl.getBoundingClientRect() };
}
/* a departing crumb dreams away where it stood: lifted out of flow at its own
   rect so the survivors can close the gap underneath it, then dissolved on
   the page's mist idiom rather than simply vanishing. */
function departCrumbs(gone) {
  const ch = document.getElementById('chrome');
  if (!ch) return;
  const org = ch.getBoundingClientRect();
  for (const [el, r] of gone) {
    if (!r) { el.remove(); continue; }
    el.classList.add('crumbout');
    el.style.left = (r.left - org.left) + 'px';
    el.style.top = (r.top - org.top) + 'px';
    el.style.width = r.width + 'px';
    ch.appendChild(el);
    void el.offsetWidth;
    el.classList.add('crumbgone');
    setTimeout(() => el.remove(), 900);
  }
}
function renderChrome(v, d, snap) {
  const meta = document.getElementById('meta');
  const titleEl = document.querySelector('#chrome .htitle');
  if (!meta || !titleEl) return;
  const nextTitle = (TITLES[v.name] || TITLES.dashboard)(v, d);
  const next = crumbsFor(v, d);
  const prev = new Map([...meta.children].map(el => [el.dataset.k, el]));
  const row = [], arrived = [];
  let keptModes = false;
  for (const c of next) {
    let el = prev.get(c.k);
    if (el) {
      prev.delete(c.k);
      /* A `stable` crumb owns its own state and is never rewritten while it
         survives (#252). The mode switch is the one: its `.on` class is
         painted by `paintFileMode`, so an html comparison would see the live
         class, disagree, and replace the nodes the FLIP and the sliding
         indicator both need to be the SAME elements. Its key carries the
         path, so nothing stale can survive a change of file. */
      if (c.stable) keptModes = keptModes || /^fview:/.test(c.k);
      else if (el.innerHTML !== c.html) el.innerHTML = c.html;
    }
    else {
      el = document.createElement('span');
      el.className = 'crumb'; el.dataset.k = c.k; el.innerHTML = c.html;
      if (snap && !rmr) { el.classList.add('dreamin'); arrived.push(el); }
    }
    row.push(el);
  }
  const gone = [...prev].map(([k, el]) => [el, snap ? snap.at.get(k) : null]);
  meta.replaceChildren(...row);
  if (snap && !rmr) departCrumbs(gone); else gone.forEach(([el]) => el.remove());
  if (titleEl.innerHTML !== nextTitle) {
    titleEl.innerHTML = nextTitle;
    if (snap && !rmr) { titleEl.classList.add('dreamin'); arrived.push(titleEl); }
  }
  /* #172 — project identity, edge-pinned. The basename is invariant across
     routes, so it is a SURVIVOR: rewrite only when the name itself changes
     (a different target would be a full reload anyway). First appearance
     rides the same enter-snap as the route word; a route change that leaves
     the name alone does not re-dream it. Full path is the title= tooltip —
     not in the bar — for popoutShell's reason (two checkouts, one basename). */
  const projEl = document.getElementById('hproj');
  if (projEl) {
    const name = projectName(d);
    const path = (d && d.target) || '';
    if (name) {
      if (projEl.textContent !== name) {
        projEl.textContent = name;
        if (snap && !rmr) {
          projEl.classList.add('dreamin');
          arrived.push(projEl);
        }
      }
      if (projEl.getAttribute('title') !== path) projEl.setAttribute('title', path);
      projEl.hidden = false;
    } else {
      projEl.textContent = '';
      projEl.removeAttribute('title');
      projEl.hidden = true;
    }
  }
  // #252: the switch's state and whether it slides. Before `ages()` only
  // because both are "finish the row"; it needs the row's final geometry,
  // which `replaceChildren` above has already committed.
  paintFileMode(v, !!snap && keptModes);
  ages();
  /* The review pane's top IS the bottom of this chrome, so it is refitted
     wherever the chrome is (re)laid out — `setContent` runs BEFORE this on
     every route change, and a crumb row that has not been written yet
     measures ~21px short. Here rather than after the FLIP below because a
     transform does not move `offsetTop`, and the early return above is on
     the animation, not on the layout. */
  fitReview();
  if (!snap || rmr) return;
  // FLIP the survivors from where they stood to where the new row puts them,
  // then release the arrivals from their snapped start state (the enter-snap
  // rule: with an always-on transition, adding the start class animates
  // TOWARD the start value instead of beginning there).
  for (const el of row) {
    const b = snap.at.get(el.dataset.k);
    if (!b) continue;
    const a = el.getBoundingClientRect();
    const dx = b.left - a.left, dy = b.top - a.top;
    if (!dx && !dy) continue;
    el.style.transition = 'none';
    el.style.transform = `translate(${dx}px, ${dy}px)`;
    void el.offsetWidth;
    el.style.transition = '';
    el.style.transform = '';
  }
  requestAnimationFrame(() => arrived.forEach(el => el.classList.remove('dreamin')));
}
/* ── copying the exact path (#284) ────────────────────────────────────────
   The heading shows the basename and the metadata line shows the parent, so
   the ONE place the whole path still exists in full is the route — and that
   is what this copies, character for character, with no separator inserted
   and nothing normalised. Reading `view.param` rather than an attribute is
   also what keeps a second copy of the truth off the page.

   Built lazily because `confirmationFor` is declared in COMMAND_JS, which is
   concatenated after this block; a top-level call here would depend on where
   the script boundaries happen to fall.

   BOTH OUTCOMES SPEAK, on the page's one confirmation lifecycle. The failure
   is not an apology — it names the fallback, and the fallback is real: the
   metadata line is selectable text precisely so a refused clipboard leaves
   him something to do. Under reduced motion `confirmationFor` keeps the hold
   and the clear and drops only the fade, which is the hard contract: same
   information, same timing, no movement. */
let fileMsg = null;
const fileConfirmation = () =>
  (fileMsg || (fileMsg = confirmationFor(document, 'fmsg', 'cmdmsg fmsg', rmr)));
async function copyFilePath() {
  const path = (view && view.name === 'file' && view.param) || '';
  const c = fileConfirmation();
  if (!path) { c.note('there is no path to copy', false); return; }
  try {
    if (!navigator.clipboard || !navigator.clipboard.writeText)
      throw new Error('no clipboard');
    await navigator.clipboard.writeText(path);
    c.note('path copied', true);
  } catch (e) {
    c.note('copy was blocked — the path beside it is selectable', false);
  }
}
/* #462 — the staleness row's remedy RUNS `just deploy` (authorised 03:46).
   Confirmation and failure speak on the page's ONE lifecycle (#fmsg), the
   same confirmationFor the file-path copy uses. The arm is #290's RUN_ARM_MS
   idiom reused: first click arms, re-click cancels, only the deadline POSTs,
   so two clicks do not start two deploys. Concurrent with an in-flight deploy
   is refused client-side and single-flight server-side.

   After a landed POST the server may die (that is the point of redeploy). The
   loaded document keeps polling /mtime; a new GENERATION is success (tick
   reloads). DEPLOY_WAIT_MS with no generation change is the named failure —
   never a spinner forever. Drafts ride #269's localStorage and survive the
   reload by construction (the restart destroys the server, not the document's
   storage). */
let staleDeployGen = 0;
let staleDeployPhase = null;   // null | 'arming' | 'running'
let staleDeployUntil = 0;
let staleDeployTimer = null;
let staleDeployTick = null;
let staleDeployWait = null;

function paintStaleDeployUI() {
  const btn = document.querySelector('.gservact');
  if (!btn) return;
  const arming = staleDeployPhase === 'arming';
  const running = staleDeployPhase === 'running';
  btn.classList.toggle('arming', arming);
  btn.classList.toggle('running', running);
  btn.setAttribute('aria-busy', running ? 'true' : 'false');
  if (arming) {
    const s = Math.max(0, Math.ceil((staleDeployUntil - Date.now()) / 1000));
    btn.textContent = s > 0 ? `arms in ${s}s` : 'updating…';
  } else if (running) {
    btn.textContent = 'updating…';
  } else {
    btn.textContent = 'just deploy';
  }
}

/* #565 — does EITHER countdown that lives in the posture widget have a live
   deadline right now? The widget docks (paintPosturePin) only while one is
   live, so it is not permanently covering ~35% of the viewport. Reads the
   posture-arm deadline + cross-tab pending, and the deploy-arm phase — the
   two hosts that share the widget's countdown bar. */
function posturePinnedLive() {
  if (staleDeployPhase === 'arming' || staleDeployPhase === 'running')
    return true;
  if (postArmUntil && Date.now() < postArmUntil) return true;
  return pendingPostIsLive(readPostPending());
}
function paintPosturePin() {
  // #674: the dock is the progress bar + "arms in …" line (#parm), not the
  // whole posture component. The class is the lever #565 established; only
  // its host changed.
  const el = document.getElementById('parm');
  if (el) el.classList.toggle('psticky', posturePinnedLive());
}

/* #569 — the deploy update message recused into the posture widget's #pdep
   slot. Width rides the explicit-width idiom #pbarfill uses: width cannot
   transition from auto, so we measure the text's natural width, snap to the
   previous explicit width (transition off), then travel to the new one
   (transition on). That eases the reflow as the label changes — 'arms in
   3s' -> 'updating — waiting for the new page' — instead of snapping. Clear
   travels the width back to 0 (overflow:hidden makes 0 invisible, so there
   is no opacity to flash on the morphdom rebuild). pdepW tracks the previous
   width across calls (module-scope, like postArmUntil). */
let pdepW = 0;
function paintDeployStatus(text) {
  const el = document.getElementById('pdep');
  if (!el) return;
  if (text) {
    el.textContent = text;
    el.classList.add('snap');            // transition:none while measuring
    el.style.width = 'auto';
    void el.offsetWidth;                 // reflow at natural width
    const w = el.scrollWidth;            // natural content width
    el.style.width = pdepW + 'px';       // snap back to previous explicit
    void el.offsetWidth;
    el.classList.remove('snap');         // transition restored
    el.style.width = w + 'px';           // travel previous -> new
    pdepW = w;
  } else {
    el.classList.remove('snap');
    el.style.width = '0px';              // travel natural -> 0
    pdepW = 0;
    // clear the text once the collapse has played so an empty slot measures
    // 0 (and is genuinely empty) on the next show.
    const node = el;
    setTimeout(() => { if (node.style.width === '0px') node.textContent = ''; }, 320);
  }
}
/* The deploy status text for the current phase (mirrors paintStaleDeployUI's
   button label) — used to re-apply #pdep after a tick rebuild (setContent),
   the same way paintStaleDeployUI re-applies the button. */
function deployStatusText() {
  if (staleDeployPhase === 'arming') {
    const s = Math.max(0, Math.ceil((staleDeployUntil - Date.now()) / 1000));
    return s > 0 ? `arms in ${s}s — then this page updates` : '';
  }
  if (staleDeployPhase === 'running') return 'updating — waiting for the new page';
  return '';
}

function clearStaleDeployArm() {
  if (staleDeployTimer) { clearTimeout(staleDeployTimer); staleDeployTimer = null; }
  if (staleDeployTick) { clearInterval(staleDeployTick); staleDeployTick = null; }
  staleDeployUntil = 0;
  if (staleDeployPhase === 'arming') staleDeployPhase = null;
  paintStaleDeployUI();
  paintDeployStatus(deployStatusText());  // #569: re-apply/clear #pdep with the phase
  paintPosturePin();   // #565: deploy arm cleared → re-evaluate the dock
}

function cancelStaleDeployArm() {
  staleDeployGen++;
  clearStaleDeployArm();
}

/* #636 — the deploy is over and it did NOT land. ONE teardown, deliberately,
   because three hand-kept copies is exactly how this broke: #565 gated the
   posture dock on posturePinnedLive() (which reads staleDeployPhase) and
   taught every path that RAISES the pin to call paintPosturePin() —
   armStaleDeploy, fireStaleDeploy's entry, clearStaleDeployArm — but the
   three paths that LOWER it lived inline inside fireStaleDeploy and were
   each missed. Measured on all three (refused / unreachable /
   never-finished): the phase went back to null and the failure was named in
   #fmsg, while #posture stayed position:sticky with .psticky 17s later.
   setContent is the only other caller of paintPosturePin and it runs solely
   when /mtime's mtime token moves, so on a quiet target the widget stayed
   welded to the viewport bottom indefinitely.

   This does NOT deepen #569's coupling: the deploy still owns its own
   teardown and simply re-evaluates the shared pin predicate, the same way
   arming does. When the countdown becomes its own component the seam to lift
   is this function, not three scattered copies. */
function endStaleDeploy() {
  staleDeployPhase = null;
  paintStaleDeployUI();
  paintDeployStatus('');   // #569: clear the slot; the failure is a notice
  paintPosturePin();       // #565/#636: countdown over — release the dock
}

function armStaleDeploy() {
  const until = Date.now() + RUN_ARM_MS;
  staleDeployGen++;
  const gen = staleDeployGen;
  staleDeployPhase = 'arming';
  staleDeployUntil = until;
  paintStaleDeployUI();
  paintPosturePin();   // #565: deploy countdown live → dock the posture widget
  const remainingMs = () => Math.max(0, staleDeployUntil - Date.now());
  // #490: countdown is steady text that ticks once per second. #569 recused
  // it into the posture widget's #pdep slot — paintDeployStatus eases the
  // width as the number ticks and never adds .dreamin (the posture arm's
  // #pcount is plain text too; one countdown idiom, so the ~4 Hz flash the
  // old #fmsg claim/re-note caused is structurally impossible here).
  let lastLeft = -1;
  const setCount = () => {
    if (gen !== staleDeployGen) return;
    const left = Math.ceil(remainingMs() / 1000);
    if (left <= 0) return;
    if (left === lastLeft) return;  // same second — do nothing
    lastLeft = left;
    paintStaleDeployUI();
    paintDeployStatus(`arms in ${left}s — then this page updates`);
  };
  setCount();
  if (staleDeployTick) clearInterval(staleDeployTick);
  staleDeployTick = setInterval(setCount, 250);
  if (staleDeployTimer) clearTimeout(staleDeployTimer);
  // Remaining, not a fixed RUN_ARM_MS — same shape the posture arm uses, so a
  // mid-arm rebuild and the guard's compressed clock both land correctly.
  staleDeployTimer = setTimeout(() => {
    if (gen !== staleDeployGen) return;
    if (staleDeployTick) { clearInterval(staleDeployTick); staleDeployTick = null; }
    staleDeployTimer = null;
    fireStaleDeploy(gen);
  }, remainingMs());
}

async function fireStaleDeploy(gen) {
  if (gen !== staleDeployGen) return;
  staleDeployPhase = 'running';
  paintStaleDeployUI();
  paintPosturePin();   // #565: deploy running → keep the widget docked
  const c = fileConfirmation();
  // #569: the running message is recused into the posture widget (#pdep).
  // Errors (refused / network / timeout) stay in #fmsg — they are notices,
  // not the live countdown — and clear the slot.
  paintDeployStatus('updating — waiting for the new page');
  let landed = false;
  try {
    const res = await fetch('/deploy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from: location.pathname + location.search }),
    });
    // raw-fetch site: owns its Response, gates on writeVerdict — never res.ok
    // alone (#263 E5b). A rejected 202 would otherwise look like success.
    const rv = await writeVerdict(res);
    landed = rv.landed;
    if (!landed) {
      endStaleDeploy();   // #636: phase + button + slot + dock, one seam
      /* The two ways this route refuses are both `domain_invalid`, so the
         generic copy ("the value was not one the server accepts") is wrong for
         both — and these are the ONLY two refusals he can provoke. `detail`
         names which. The old `res.status === 403` branch was dead: since the
         202 cutover (#263 E5) a refusal is 202 + rejected, never 403, so the
         "only runs from this machine" line could never have printed. */
      const why = DEPLOY_WHY[rv.detail]
        || (rv.rejected && rv.reason && REJECT_WHY[rv.reason])
        || null;
      c.note(
        rv.detail === 'in_flight'
          ? `already updating — ${why}`
          : `update was refused — ${why || 'try again in a moment'}`,
        false);
      return;
    }
  } catch (e) {
    endStaleDeploy();   // #636: phase + button + slot + dock, one seam
    c.note('update was refused — the page could not reach the server', false);
    return;
  }
  if (gen !== staleDeployGen) return;
  // Landed: the server may already be dying. Watch for a new generation;
  // if none arrives by DEPLOY_WAIT_MS, name the failure.
  // window.__dwDeployWaitMs is the guard's short-deadline inject (mirrors
  // __dwSkipStaleArrival): production never sets it; the default is the
  // styleguide constant.
  const waitMs = (typeof window.__dwDeployWaitMs === 'number')
    ? window.__dwDeployWaitMs : DEPLOY_WAIT_MS;
  const startedAt = Date.now();
  const baseline = serverGen;
  if (staleDeployWait) clearInterval(staleDeployWait);
  staleDeployWait = setInterval(() => {
    if (gen !== staleDeployGen) {
      clearInterval(staleDeployWait); staleDeployWait = null; return;
    }
    // tick() reloads on generation change; if we are still here past the
    // deadline, the new generation never came.
    if (serverGen && baseline && serverGen !== baseline) {
      clearInterval(staleDeployWait); staleDeployWait = null;
      return; // reload is in flight or done
    }
    if (Date.now() - startedAt >= waitMs) {
      clearInterval(staleDeployWait); staleDeployWait = null;
      endStaleDeploy();   // #636: phase + button + slot + dock, one seam
      c.note(
        'update never finished — this page is still the old one',
        false);
    }
  }, 400);
}

function onStaleActionClick() {
  const c = fileConfirmation();
  if (staleDeployPhase === 'running') {
    c.note('update already in flight — waiting for the new page', false);
    return;
  }
  if (staleDeployPhase === 'arming') {
    cancelStaleDeployArm();
    c.note('update cancelled', true);
    return;
  }
  armStaleDeploy();
}
addEventListener('click', e => {
  const stale = e.target.closest && e.target.closest('.gservact');
  if (stale) { onStaleActionClick(); return; }
  const btn = e.target.closest && e.target.closest('.fcopy');
  if (btn) copyFilePath();
});
/* Dream dissolve: the outgoing view becomes a ghost that liquifies into a
   swirling mist (turbulence displacement + blur grow) and drifts upward as
   it fades; the incoming view coalesces from the same mist and settles
   perfectly crisp. Opacity + transform ride CSS; the mist is an SVG filter
   whose displacement + blur we envelope per-frame here, so the middle of
   the dissolve lingers hazy. The shader stirs in sympathy (pulseWarp).
   reduced-motion swaps instantly — no ghost, no mist. */
const DREAM_MS = 1150;                     // dwell of the whole dissolve
// #449: the SVG liquify mist (feTurbulence→displacement→blur, driven per-frame
// from stepFx) was shelved behind this switch. Measured 2026-07-29 on the route
// he named (question→review): Chrome rasterizes feTurbulence afresh every frame
// and does not cache it across frames, so freezing baseFrequency, freezing ALL
// six stepFx attribute writes, and even clamping the ghost's filtered area 42%
// (553×1557→553×900, geometry confirmed) all bought nothing — the cost was the
// turbulence primitive regenerating, not the displacement math, the attribute
// writes, or the area. Removing both dissolve filters recovered +100–128% of
// rAF frames (capture: dev/capture/dissolveperf.mjs).
// #453: the mist is RESTORED as the human's texture idea — one cached noise
// field pre-rendered once (mistTexture below), consumed via feImage and MOVED
// per frame by feOffset ("just having a single texture ... and then just like
// moving it"). Nothing regenerates per frame; feOffset/feTile shift a cached
// bitmap, and #449 measured the displacement+blur math itself as free (I3).
// Measured in the same harness against #449's bar — see transitions.md (*The
// mist filter*) for the numbers. The shelved feTurbulence filters stay defined
// (#dissolveOutT/#dissolveInT) and MIST_IMPL 'turbulence' selects them for
// comparison. MIST_ON false = CSS blur carries the dissolve (#449's fallback;
// body.mistoff rules), whatever MIST_IMPL says.
const MIST_ON = true;
const MIST_IMPL = 'feimage';   // 'feimage' (#453) | 'turbulence' (#449, shelved)
// The cached mist field: a TILEABLE fractal value-noise texture, generated
// once, deterministic (fixed PRNG state so captures are reproducible), with
// independent R and G fields for the two displacement axes. Tileable by
// construction — each octave's lattice wraps at its period — so feTile repeats
// it seamlessly and feOffset can drift it without a seam ever crossing.
let MIST_TEX = null;
function mistTexture() {
  if (MIST_TEX !== null) return MIST_TEX;
  try {
    const T = 256;
    const cv = document.createElement('canvas'); cv.width = cv.height = T;
    const cx2 = cv.getContext('2d');
    if (!cx2) throw new Error('no 2d context');
    const im = cx2.createImageData(T, T);
    const fade = t => t * t * (3 - 2 * t);
    const hash = (x, y, p, sd) => {
      x = ((x % p) + p) % p; y = ((y % p) + p) % p;      // wrap → tileable
      let h = (x * 374761393 + y * 668265263 + sd * 2246822519) >>> 0;
      h = (h ^ (h >>> 13)) >>> 0; h = (h * 1274126177) >>> 0;
      return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
    };
    const oct = (px, py, p, sd) => {
      const gx = px / T * p, gy = py / T * p;
      const x0 = Math.floor(gx), y0 = Math.floor(gy);
      const fx = fade(gx - x0), fy = fade(gy - y0);
      const v00 = hash(x0, y0, p, sd), v10 = hash(x0 + 1, y0, p, sd);
      const v01 = hash(x0, y0 + 1, p, sd), v11 = hash(x0 + 1, y0 + 1, p, sd);
      return (v00 * (1 - fx) + v10 * fx) * (1 - fy) +
             (v01 * (1 - fx) + v11 * fx) * fy;
    };
    // periods/weights chosen to read like the old baseFrequency≈0.009 field
    // (~110px blobs) at a 256px tile: 2–3 large forms per tile, finer octaves
    // for the swirl. R and G are independent fields (sd 11 vs 47).
    const OS = [[2, .42], [4, .27], [8, .18], [16, .13]];
    let mn = 1, mx = 0;
    const R = new Float32Array(T * T), G = new Float32Array(T * T);
    for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
      let r = 0, g = 0;
      for (const [p, w] of OS) { r += oct(x, y, p, 11) * w; g += oct(x, y, p, 47) * w; }
      R[y * T + x] = r; G[y * T + x] = g;
      if (r < mn) mn = r; if (r > mx) mx = r;
    }
    for (let i = 0; i < T * T; i++) {   // stretch R to the full range (same
      const r = (R[i] - mn) / (mx - mn); // band G occupies, ±2%)
      im.data[i * 4] = r * 255;
      im.data[i * 4 + 1] = Math.max(0, Math.min(255, (G[i] - mn) / (mx - mn) * 255));
      im.data[i * 4 + 2] = 128; im.data[i * 4 + 3] = 255;
    }
    cx2.putImageData(im, 0, 0);
    MIST_TEX = cv.toDataURL('image/png');
    document.querySelectorAll('#dreamfx feImage.texsrc').forEach(fi => {
      fi.setAttribute('href', MIST_TEX);
      fi.setAttributeNS('http://www.w3.org/1999/xlink', 'xlink:href', MIST_TEX);
    });
  } catch (e) {
    MIST_TEX = '';                        // no canvas: degrade to CSS blur
    document.body.classList.add('mistoff');
  }
  return MIST_TEX;
}
const fxNode = (id, tag) => document.querySelector('#' + id + ' ' + tag);
function crossfade(html, xopts) {
  xopts = xopts || {};
  const viewEl = document.getElementById('view');
  if (rmr) {
    document.body.classList.toggle('review', !!xopts.review);
    document.body.classList.toggle('file', !!xopts.file);
    document.body.classList.toggle('question', !!xopts.question);
    setContent(html);
    renderChrome(view, data, null);
    return;
  }
  // The review view is a wider column, so a route change onto or off it
  // RESIZES the page. Measure everything that is about to move BEFORE the
  // class flip that moves it.
  const outRect = viewEl.getBoundingClientRect();
  const outW = outRect.width, outH = outRect.height;
  const outTop = viewEl.offsetTop;
  const snap = chromeSnapshot();
  const ghost = viewEl.cloneNode(true);
  ghost.removeAttribute('id'); ghost.className = 'ghost';
  // a cloned iframe would re-fetch and flash while dissolving — drop it;
  // the ghost only needs the chrome/text to blur away.
  ghost.querySelectorAll('iframe').forEach(f => f.remove());
  viewEl.parentNode.appendChild(ghost);
  // Pin the ghost to the box it was rendered in. It is LEAVING: it should
  // dissolve as it was, not re-wrap every paragraph into a new column while
  // still fully opaque — that reflow, at frame 0 and at full opacity, was
  // the "elements jump around" (#107). The chrome now sits above #view, so
  // the ghost is placed at #view's own offset rather than stretched to the
  // wrapper with `inset:0`.
  ghost.style.top = outTop + 'px';
  ghost.style.width = outW + 'px';
  ghost.style.height = outH + 'px';
  // ...and the column itself glides to its new width rather than snapping
  // (see body.wsliding). The incoming view reflows as it widens, behind the
  // mist and up from opacity 0, so the resize reads as the page opening.
  document.body.classList.add('wsliding');
  document.body.classList.toggle('review', !!xopts.review);
  document.body.classList.toggle('file', !!xopts.file);
  document.body.classList.toggle('question', !!xopts.question);
  setContent(html);
  renderChrome(view, data, snap);   // the heading travels; it does not reload
  // measure the docked question's resting rect BEFORE the enter transform,
  // so a shared-element FLIP from the clicked question lands true.
  const dock = document.getElementById('qdock');
  const dockRect = dock ? dock.getBoundingClientRect() : null;
  // #449/#453: the liquify mist is behind MIST_ON, and applied to the GHOST
  // ONLY. #453 measured the cost model end to end in #449's own harness on
  // this host: the per-frame price is the COUNT of full-page SVG filter
  // rasterisations, nothing else — feImage≈feTurbulence, static≈animated,
  // two filters ≈ 24 frames, one ≈ 34, none ≈ 47-50. So the departing view
  // keeps the whole gesture (liquify + flow + haze, one rasterisation) and
  // the arriving view's haze is the compositor CSS blur (measured free).
  // MIST_IMPL picks the field: 'feimage' is the cached moved texture (#453),
  // 'turbulence' the shelved per-frame feTurbulence (#449).
  const mistOk = MIST_ON && (MIST_IMPL === 'turbulence' || mistTexture());
  if (mistOk) {
    const sfx = MIST_IMPL === 'turbulence' ? 'T' : '';
    ghost.style.filter = 'url(#dissolveOut' + sfx + ')';
  }
  viewEl.classList.add('enter');
  void viewEl.offsetWidth;                 // commit the hidden start state
  if (xopts.fromRect && dock && dockRect) flipDock(dock, xopts.fromRect, dockRect);
  if (window.dreambg) window.dreambg.pulseWarp();
  requestAnimationFrame(() => {
    viewEl.classList.remove('enter');      // CSS eases opacity + drift in
    ghost.classList.add('out');            // CSS eases opacity + drift out
  });
  const t0 = performance.now();
  let raf = 0;
  const finish = () => {
    if (raf) cancelAnimationFrame(raf), raf = 0;
    if (ghost.isConnected) ghost.remove();
    viewEl.style.filter = '';              // crisp at rest, zero filter cost
    document.body.classList.remove('wsliding');
  };
  // The per-frame mist envelope, on the ghost's one rasterisation. feimage:
  // the displacement/blur envelopes plus feOffset DRIFTS that move the cached
  // field's two interfering layers on different bearings — the flow the
  // baseFrequency ramp used to fake, now from a field nothing regenerates.
  // turbulence (shelved): the original writes. The envelope endpoints are
  // identical either way, so the gesture's shape does not depend on the
  // mechanism.
  if (mistOk) {
    const sfx = MIST_IMPL === 'turbulence' ? 'T' : '';
    const dOut = fxNode('dissolveOut' + sfx, 'feDisplacementMap');
    const bOut = fxNode('dissolveOut' + sfx, 'feGaussianBlur');
    const tOut = fxNode('dissolveOut' + sfx, 'feTurbulence');
    const o1 = fxNode('dissolveOut' + sfx, 'feOffset');
    // per-destination swirl signature: this arrival's field. feimage moves a
    // STATIC field, so the seed selects where in the tile the field starts
    // and on what bearing it drifts; turbulence seeds the noise itself.
    const seed = SEED[view.name] != null ? SEED[view.name] : 7;
    if (tOut) tOut.setAttribute('seed', seed);
    // drift: bounded so the offset never pushes the tiled field's edge into
    // the region displacement can sample (region margin − scale/2; the
    // narrowest filtered element on any route is the 553px questions column).
    const ang = (seed % 12) / 12 * 2 * Math.PI;
    const ox0 = (seed * 37) % 96 - 48, oy0 = (seed * 91) % 96 - 48;
    const DX = Math.cos(ang) * 40, DY = Math.sin(ang) * 40;
    const smooth = x => x * x * (3 - 2 * x);
    function stepFx(now) {
      const u = Math.min(1, (now - t0) / DREAM_MS);
      const eo = smooth(u);                          // ghost: mist grows in
      if (dOut) dOut.setAttribute('scale', (eo * 25).toFixed(2));
      if (bOut) bOut.setAttribute('stdDeviation', (eo * 3.8).toFixed(2));
      if (o1) {
        o1.setAttribute('dx', (ox0 + eo * DX).toFixed(1));
        o1.setAttribute('dy', (oy0 + eo * DY).toFixed(1));
      }
      const bf = (0.009 + eo * 0.009).toFixed(4);    // shelved: field tightens
      if (tOut) tOut.setAttribute('baseFrequency', bf);
      if (u < 1) raf = requestAnimationFrame(stepFx);
      else finish();
    }
    raf = requestAnimationFrame(stepFx);
  }
  setTimeout(finish, DREAM_MS + 400);      // safety net
}
/* shared-element morph: the docked question travels from where it was
   clicked (its list rect) to its docked rect — auto-animate style, but the
   dream twist is a blurred, low-opacity drift rather than a crisp slide. */
function flipDock(dock, fromRect, toRect) {
  const dx = fromRect.left - toRect.left;
  const dy = fromRect.top - toRect.top;
  const sx = Math.max(0.15, fromRect.width / (toRect.width || 1));
  const sy = Math.max(0.15, fromRect.height / (toRect.height || 1));
  // Lift the travelling question above the page mist (z-index) and keep it
  // luminous, so the eye tracks THIS element gliding to its dock while the
  // rest of the page dissolves behind it — a shared-element morph, but
  // dream-blurred not crisp. Its glide outlasts the mist so the travel reads.
  dock.style.zIndex = '4';
  dock.style.transformOrigin = 'top left';
  dock.style.transform = `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`;
  dock.style.filter = 'blur(5px)';
  dock.style.opacity = '0.4';
  dock.style.transition = 'none';
  void dock.offsetWidth;                    // commit the inverted start
  requestAnimationFrame(() => {
    dock.style.transition =
      'transform 1.15s cubic-bezier(.22,.61,.36,1), filter .95s ease, ' +
      'opacity .85s ease';
    dock.style.transform = 'none';
    dock.style.filter = '';
    dock.style.opacity = '1';
  });
  const clear = () => {
    for (const p of ['transition', 'transform', 'transformOrigin', 'filter',
                     'opacity', 'zIndex']) dock.style[p] = '';
  };
  dock.addEventListener('transitionend', clear, { once: true });
  setTimeout(clear, 1500);                  // safety net
}
/* ── the reading position across a mode swap (#252) ───────────────────────
   The document's scrollable range as the CONTENT implies it, in LAYOUT space.
   Two traps, both documented in transitions.md and both live here:

   - `documentElement.scrollHeight` answers for the outgoing GHOST too. The
     ghost is an absolutely positioned clone inside `.wrap`, so while it lives
     (~1.15s) it extends the document's scrollable area — and going
     source -> rendered it is the taller of the two. The restore would land
     low and then be clamped when the corpse is removed.
   - `getBoundingClientRect` answers in VISUAL space, and on the frame this
     runs `#view` is mid-`enter`: pushed back in Z and scaled down. Every rect
     beneath it reads small. `offsetTop`/`offsetHeight` are layout values and
     are immune to both, which is why the chain is walked by hand. */
function contentBottom() {
  const v = document.getElementById('view');
  if (!v) return 0;
  let y = 0;
  for (let n = v; n; n = n.offsetParent) y += n.offsetTop;
  return y + v.offsetHeight +
    (parseFloat(getComputedStyle(document.body).paddingBottom) || 0);
}
const scrollRange = () => Math.max(0, contentBottom() - window.innerHeight);
/* A RATIO, not a pixel offset: the two panes are different heights (a rendered
   document is shorter than the source it came from, by roughly its own markup)
   so the same pixel offset is a different place in the text. Null when there
   is nothing to scroll, so a short file restores nothing rather than 0/0. */
const scrollRatio = () => {
  const range = scrollRange();
  return range > 0 ? Math.min(1, window.scrollY / range) : null;
};
function restoreScrollRatio(r) {
  if (r === null || r === undefined) return;
  const range = scrollRange();
  if (range > 0) window.scrollTo(0, Math.round(r * range));
}
async function navigate(name, param, opts) {
  opts = opts || {};
  const mode = opts.mode === 'source' ? 'source' : 'rendered';
  /* A mode swap is a change of REPRESENTATION, not of place: same file, same
     point in it. Every other navigation is a new document and has no position
     to keep, which is why this is not a general scroll-restore. */
  const modeSwap = !!view && view.name === 'file' && name === 'file' &&
                   view.param === param && (view.mode || 'rendered') !== mode;
  const keepRatio = modeSwap ? scrollRatio() : null;
  if (window.__closeCmd) window.__closeCmd();   // context is changing
  // Leaving /answers destroys the ask surface — drop in-flight ownership so a
  // late /ask cannot clear or tick a form that no longer exists, and so a
  // return visit is not blocked by a stuck askInFlight flag (#292 lifecycle).
  if (view && view.name === 'answers' && name !== 'answers')
    invalidateAskFlight();
  // #577 — leaving /chat destroys the reply surface for the same reason: a
  // late /chat-reply must not clear/tick a box that no longer exists, and a
  // return visit must not be blocked by a stuck chatReplyInFlight flag.
  if (view && view.name === 'chat' && name !== 'chat')
    invalidateChatReplyFlight();
  // #284: a copy confirmation belongs to the file it was made on, and the
  // chrome SURVIVES a route change — so without this the message would follow
  // him onto another page and describe a path no longer on screen. Route
  // change is destruction here, exactly as it is for the composer.
  if (fileMsg && !(view && view.name === name && view.param === param))
    fileMsg.clear();
  view = { name, param, q: opts.q || null, mode };
  applyTitle();
  if (window.dreambg) window.dreambg.setTint(TINT[name] || 0);
  const url = name === 'questions' ? '/questions'
    : name === 'answers' ? '/answers'
    : name === 'file' ? '/file?p=' + encodeURIComponent(param || '') +
        (mode === 'source' ? '&view=source' : '')
    : name === 'review' ? '/review?p=' + encodeURIComponent(param || '') +
        (opts.q ? '&q=' + encodeURIComponent(opts.q) : '')
    : name === 'question' ? '/question?qid=' + encodeURIComponent(param || '')
    : name === 'research' ? '/research' +
        (param ? '?p=' + encodeURIComponent(param) : '')
    : name === 'reviews' ? '/reviews'
    : name === 'chat' ? '/chat/' + encodeURIComponent(param || '')
    : '/';
  /* The wide artifact column is the review idiom's, and a research DOC
     (#484, /research?p=…) is the same reading gesture over the same
     #reviewwrap nodes — so it borrows body.review rather than growing a
     second wide-column rule. The research LISTING stays the normal column. */
  const artifactDoc = name === 'review' || (name === 'research' && !!param);
  if (opts.push) history.pushState({ name, param, q: opts.q || null }, '', url);
  const html = await buildCurrent();
  if (opts.transition === false) {
    document.body.classList.toggle('review', artifactDoc);
    document.body.classList.toggle('file', name === 'file');
    document.body.classList.toggle('question', name === 'question');
    setContent(html);
    renderChrome(view, data, null);   // first paint: arrive, don't animate
  } else {
    crossfade(html, { fromRect: opts.fromRect, review: artifactDoc,
                      file: name === 'file', question: name === 'question' });
  }
  // after the new content is in layout, and only for the swap that has a
  // position worth keeping
  if (modeSwap) restoreScrollRatio(keepRatio);
}
/* only same-document routes are intercepted; external links, new-tab and
   modified clicks fall through to the browser. */
function isInternal(a) {
  if (!a || a.target === '_blank' || a.hasAttribute('download')) return false;
  if (a.origin !== location.origin) return false;
  return a.pathname === '/' || a.pathname === '/questions'
      || a.pathname === '/answers'
      || a.pathname === '/file' || a.pathname === '/review'
      || a.pathname === '/question' || a.pathname === '/research'
      || a.pathname === '/reviews'
      || a.pathname.startsWith('/chat/');
}
addEventListener('click', e => {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey ||
      e.shiftKey || e.altKey) return;
  const a = e.target.closest('a');
  if (!isInternal(a)) return;
  e.preventDefault();
  const r = routeOf(a);
  // `routeOf` reads `search` off the <a> as readily as off `location`, so the
  // mode switch needs no handler of its own: it is two ordinary internal links
  // (#252), which is also what makes it keyboard-operable and deep-linkable.
  const opts = { push: true, q: r.q, mode: r.mode };
  // a review link fired from inside a question card seeds the shared-element
  // morph: remember where the question sat so it can travel to its dock.
  if (r.name === 'review' && r.q) {
    const card = a.closest('.qa');
    if (card) opts.fromRect = card.getBoundingClientRect();
  }
  navigate(r.name, r.param, opts);
});
addEventListener('popstate', () => {
  const r = routeOf(location);
  navigate(r.name, r.param, { push: false, q: r.q, mode: r.mode });
});
/* live tick: re-render the active data-driven view in place, no fade.
   Tolerates the brief unreachable window while the server restarts. */
async function tick() {
  try {
    const { gen, mtime } = parseMtime(await (await fetch('/mtime')).text());
    if (serverGen === null) serverGen = gen;
    else if (gen && gen !== serverGen) { location.reload(); return; }
    if (mtime !== lastMtime && Date.now() >= holdRerenderUntil) {
      lastMtime = mtime; fetchedAt = Date.now();
      const wasGit = gitKey(data), wasBurn = burnKey(data);
      if (burnStepPref === null) burnStepPref = loadBurnStepPref();
      setData(await (await fetch(dataJsonUrl())).json());
      // the data lands instantly; surviving cards then travel from where
      // they were to where the new grouping put them (#104/#77). What the
      // human is mid-way through typing rides across the swap (#118).
      const tickView = view;
      const kept = snapshotCardState();
      const askKept = snapshotAskState();
      const reviewFrame = snapshotReviewFrame();
      const before = snapshotCards();
      // #523 is now carried by keyed reconciliation: a focused input inside
      // #view is KEPT by id, and reconcileGuard's value-stamp keeps mid-edit
      // text. No snapshot/restore pair (snapshotViewInputs retired in #505 p2).
      // #494: burndown hover/pin — same carry as card state, keyed by
      // bucket t0. Snapshot BEFORE the swap; the detach fires pointerout
      // which would otherwise clear the fresh (hidden) tip/inspector.
      const bdHover = snapshotBdHover();
      // Exact artifact *created* times can reorder these rows on any data
      // tick (#463). Keep their filename identity and reuse the list FLIP
      // rather than snapping.
      const reviewBefore = view.name === 'dashboard'
        ? snapshotCards(REVIEW_LIST) : null;
      // #151: the commits panel animates on a NEW COMMIT, never on a tick.
      // The dashboard re-renders whenever ANY watched file changes — the loop
      // rewrites status.json every few seconds — so rows travelling on a tick
      // would be motion with nothing behind it, which is the opt-in rule. The
      // sha sequence is the thing that means "a commit happened", and it is
      // compared before the swap because after it there is nothing to compare.
      const gitBefore = (view.name === 'dashboard' && gitKey(data) !== wasGit)
        ? snapshotCards(GIT_LIST) : null;
      // the same gate for the same reason, one panel down (#142)
      const burnBefore = (view.name === 'dashboard' && burnKey(data) !== wasBurn)
        ? snapshotBars() : null;
      // Reuse the router's current-view seam so every data-backed route,
      // including the review dock, receives the same live snapshot (#271).
      // Card-owned state rides the existing #118/#269 discipline below.
      const html = await buildCurrent();
      // buildCurrent may await /filedata. A user navigation made during that
      // wait owns the screen; stale tick work must never overwrite it.
      if (view !== tickView) return setTimeout(tick, 2000);
      setLiveContent(html);
      restoreBdHover(bdHover);       // #494 before anything that measures
      restoreReviewFrame(reviewFrame);
      // FOLDS FIRST, then the cards inside them (#179). Both must land before
      // the regroups, which MEASURE — a section restored afterwards would be
      // measured shut and then opened underneath the animation — but the
      // order BETWEEN them is not free: a card's box is restored by putting
      // his text back and putting the CARET back in it, and focus() inside a
      // closed <details> does nothing and reports nothing. On the dashboard
      // every card lives inside `.qsec`, which renders closed, so restoring
      // the card first re-filled the box and silently dropped the focus.
      restoreCardState(kept);
      // #523 no longer has a restore here: a focused input inside #view is
      // KEPT by id under reconciliation, and reconcileGuard's value-stamp
      // preserved its mid-edit value during the morph (caret/focus/scroll
      // ride the kept node). syncDockFade still runs before paint (#326).
      syncDockFade();
      restoreAskState(askKept);
      // storage is the backstop when the snapshot was empty (reload, or he
      // navigated away and back). Live text from the snapshot already wins.
      bindAskDraft();
      bindChatReplyDraft();   // #577: chat:<id> draft backstop
      regroupCards(before);
      regroupCards(reviewBefore, null, REVIEW_LIST);
      regroupCards(gitBefore, null, GIT_LIST);
      regroupBars(burnBefore);
      // the crumbs carry live numbers too (open count, version) — and the
      // tick re-renders in place, instantly, so they never animate
      renderChrome(view, data, null);
    }
  } catch (e) { /* server restarting; retry next tick */ }
  setTimeout(tick, 2000);
}
setInterval(ages, 1000);
if (!MIST_ON) document.body.classList.add('mistoff');   // #449: see crossfade
(function () {                              // initial view from the URL
  const r = routeOf(location);
  navigate(r.name, r.param,
           { push: false, transition: false, q: r.q, mode: r.mode });
  tick();
})();
