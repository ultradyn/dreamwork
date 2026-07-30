/* chatsurface — #562: the topic-chat list carries an unread/total count and
   each row links to a /chat/<id> page that renders the conversation.

   The defect (his words): "is that unread or total?" (the count was total-only
   and didn't say so) and "the actual issue is that I can't open the chat!" (the
   row was an inert <div>; no handler read data-chat and no /chat route existed).

   Production lines the red-proof names (watch.py):
     - chatList's unread/total count-line branch (the `unread > 0` clause)
     - chatRow's `<a href="/chat/<id>">` (was an inert <div>)
     - routeOf's /chat/<id> branch + buildChat's turn rendering + the
       /chatdata endpoint (the page that did not exist)
     - _chat_record_and_turns's `unread` derivation (last turn is his)

   This guard builds its OWN target — the shared fixture is chatless, so every
   check below would pass vacuously on it — and plants REAL transcripts through
   watch.apply_chat_turn (the production writer), never hand-built fixture text
   the parser never saw. It picks its own port for the same reason dashboard.mjs
   does: the datum is a property of a target this guard owns.

   No motion is traced here: the chat page arrives on the route dissolve every
   destination shares (guarded by dissolve.mjs), and the count line's text
   change on a tick is the documented settled re-render. This guard asserts
   STRUCTURE + reduced-motion parity (function survives reduced motion), which
   is the half of transitions.md's contract a structural guard can hold.

   usage: node chatsurface.mjs <outdir> [port]   (port ignored — own server) */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { execFileSync } from 'node:child_process';
import { mkdirSync, rmSync, cpSync } from 'node:fs';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { serveVerified } from './serve.mjs';
import { waitFor } from './dom.mjs';
import { makeReporter } from './report.mjs';
import { outdir } from './outdir.mjs';

const OUT = outdir(process.argv);
mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));

const { ok, present, declare, finish, notes, errs } = makeReporter();
declare({
  drives: 'dashboard chat list (count line + row links) and /chat/<id> ' +
          '(transcript render + not-found degrade) in normal AND reduced motion',
  traceWindow: 'static reads after settle; no motion trace — the route ' +
               'dissolve is dissolve.mjs\'s gesture and the count line is a ' +
               'settled re-render. Reduced motion is asserted as parity of ' +
               'content (function), not of timing.',
});

// ── a target with REAL transcripts, through the production writer ──────────
// apply_chat_turn is the one writer (#504): it one-lines the body and its
// parser anchors both dw-turn markers at line start, so planting through it
// proves the page reads what the loop writes. Never hand-build transcript text.
const DIR = join(OUT, 'target');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });
const addTurn = (id, role, text) => execFileSync('python3', ['-c',
  `import watch; watch.apply_chat_turn(${JSON.stringify(DIR)}, ` +
  `${JSON.stringify(id)}, ${JSON.stringify(role)}, ${JSON.stringify(text)})`],
  { stdio: 'ignore' });
// pending + unread (one human turn — last turn is his)
addTurn('chat-unread', 'human', 'a question that needs a reply');
// replied + READ (human then agent — last turn is the dreamer's)
addTurn('chat-read', 'human', 'an answered question');
addTurn('chat-read', 'agent', 'the dreamer replied');
// replied + UNREAD (he followed up AFTER the reply — last turn is his again)
addTurn('chat-followup', 'human', 'first message');
addTurn('chat-followup', 'agent', 'a reply landed');
addTurn('chat-followup', 'human', 'a follow-up after the reply');

// own port — the shared fixture is chatless and this guard owns its target
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const PORT = await freePort();
const child = await serveVerified(DIR, PORT, { expect: DIR });
const BASE = `http://127.0.0.1:${PORT}`;

try {
  // ── preconditions: derive the unread/total split from live data ─────────
  const d = await (await fetch(`${BASE}/data.json`)).json();
  const chats = Array.isArray(d.chats) ? d.chats : [];
  const byId = new Map(chats.map(c => [c.id, c]));
  const total = chats.length;
  const unreadN = chats.filter(c => c.unread).length;
  notes.push('chats: ' + JSON.stringify(chats.map(c => ({
    id: c.id, status: c.status, unread: c.unread, turns: c.turns }))));
  ok('precondition: server shipped chats (the shared fixture has none)',
     total >= 2);
  ok('precondition: at least one unread chat (else the unread clause is untested)',
     unreadN >= 1);
  ok('precondition: at least one read chat (else the no-unread arm is untested)',
     chats.some(c => !c.unread));
  // the unread derivation itself, read through the production reader
  ok('unread is derived (chat-read last turn is agent -> not unread)',
     byId.get('chat-read') && byId.get('chat-read').unread === false);
  ok('unread is derived (chat-followup last turn is human -> unread; ' +
     'replied AND unread, the subset relationship)',
     byId.get('chat-followup') && byId.get('chat-followup').unread === true &&
     byId.get('chat-followup').status === 'replied');
  if (total < 2 || !byId.has('chat-followup') || !byId.has('chat-read')) {
    child.kill(); finish(); process.exit(1);
  }

  const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
  const p = await br.newPage({ viewport: { width: 1280, height: 900 } });
  p.on('pageerror', e => errs.push(String(e)));

  // ── Act 1: the count line tells the truth + rows are links ──────────────
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await waitFor(p, '[data-chat]');
  const dash = await p.evaluate(() => {
    const labels = [...document.querySelectorAll('.label')];
    const lab = labels.find(x => (x.textContent || '').startsWith('topic chats'));
    const rows = [...document.querySelectorAll('[data-chat]')].map(a => ({
      tag: a.tagName, href: a.getAttribute('href') || '',
      id: a.getAttribute('data-chat') || '',
    }));
    return { label: lab ? lab.textContent : null, rows };
  });
  notes.push('dashboard label: ' + JSON.stringify(dash.label));
  ok('the topic-chats count line renders', !!dash.label);
  // unread clause present iff unread > 0; total always labelled "N total"
  if (dash.label) {
    const wantUnread = unreadN > 0
      ? `${unreadN} unread · ${total} total` : `${total} total`;
    ok(`count line is honest (unread clause only when > 0): expect ` +
       `"${wantUnread}"`, dash.label.endsWith(wantUnread) &&
       dash.label.startsWith('topic chats · '));
    ok('the unread clause appears when there are unread chats',
       unreadN > 0 ? dash.label.includes('unread') : !dash.label.includes('unread'));
  }
  // each row is a link to /chat/<id> (was an inert <div>)
  ok('there is a row per chat', dash.rows.length === total);
  ok('every row is an anchor (not the old inert <div>)',
     dash.rows.length > 0 && dash.rows.every(r => r.tag === 'A'));
  ok('every row links to its /chat/<id> page',
     dash.rows.length > 0 && dash.rows.every(r => r.href === '/chat/' + r.id));
  const followupRow = dash.rows.find(r => r.id === 'chat-followup');
  ok('the followup chat has a row linking to its page',
     !!followupRow && followupRow.href === '/chat/chat-followup');

  // ── Act 2: the page renders the conversation (drive the real gesture) ───
  // Click the row — the real gesture for arriving at a chat — rather than
  // goto'ing the URL, so the in-app route + /chatdata fetch are exercised.
  const clicked = await p.evaluate(() => {
    const a = document.querySelector('[data-chat="chat-followup"]');
    if (!a) return false;
    a.scrollIntoView({ block: 'center' });
    return true;
  });
  ok('the followup row is reachable to click', clicked);
  if (clicked) {
    await p.click('[data-chat="chat-followup"]');
    await waitFor(p, '.chaturn');
    await sleep(300);     // let the dissolve settle + turns paint
    ok('clicking a row navigated to /chat/<id>',
       p.url().endsWith('/chat/chat-followup'));
    const chat = await p.evaluate(() => {
      const turns = [...document.querySelectorAll('.chaturn')].map(t => ({
        role: t.getAttribute('data-role'),
        who: (t.querySelector('.chatwho') || {}).textContent || '',
        body: ((t.querySelector('.chatbody') || {}).textContent || '').trim(),
      }));
      const head = (document.querySelector('#chrome .htitle') || {}).textContent || '';
      // the way back is the dashboard crumb (the not-found notice carries its
      // own .qmissback link; a real chat page does not, so look for the crumb)
      const back = !!document.querySelector('#meta a[href="/"]');
      return { turns, head, back };
    });
    notes.push('chat page: ' + JSON.stringify(chat));
    ok('the chat page renders a turn per transcript turn',
       chat.turns.length === 3);
    ok('turns render newest-last in transcript order',
       chat.turns.length === 3 &&
       chat.turns[0].body === 'first message' &&
       chat.turns[1].body === 'a reply landed' &&
       chat.turns[2].body === 'a follow-up after the reply');
    ok('roles are labelled his / the dreamer\'s (you / dreamer)',
       chat.turns.map(t => t.who).join(',') === 'you,dreamer,you');
    ok('the heading is the chat\'s derived title (its first human turn)',
       chat.head === 'first message');
    ok('the page carries a way back to the dashboard', chat.back);
  }

  // ── Act 2: unknown id degrades in the page's own voice ──────────────────
  // A deep link to an id that is not a chat must render the not-found notice,
  // never a traceback. errs collects pageerror events — a thrown exception
  // would land there and red the "no console error" check.
  await p.goto(`${BASE}/chat/no-such-chat`, { waitUntil: 'networkidle' });
  await sleep(300);
  const nf = await p.evaluate(() => {
    const m = document.querySelector('.qmissing');
    return { found: !!m, text: m ? (m.textContent || '') : '' };
  });
  notes.push('not-found: ' + JSON.stringify(nf));
  ok('an unknown chat id degrades to the not-found notice (never a traceback)',
     nf.found && /not found/i.test(nf.text));
  ok('no pageerror fired on the chat surface (no thrown exception)',
     !errs.some(e => /chat/i.test(e)));

  // ── reduced-motion parity: function survives, only timing changes ───────
  // transitions.md's hard contract: reduced motion changes timing, never
  // function or legibility. The chat page arrives on the route dissolve (made
  // instant under reduced motion); the conversation must still render in full.
  const ctx = await br.newContext({ reducedMotion: 'reduce' });
  const rp = await ctx.newPage();
  await rp.goto(`${BASE}/chat/chat-followup`, { waitUntil: 'networkidle' });
  await waitFor(rp, '.chaturn');
  await sleep(200);
  const rmTurns = await rp.evaluate(() =>
    document.querySelectorAll('.chaturn').length);
  ok('reduced motion: the chat page still renders every turn (parity)',
     rmTurns === 3);
  await br.close();
} catch (e) {
  errs.push('guard threw: ' + (e && e.stack ? e.stack : String(e)));
}

try { child.kill(); } catch (_) {}
finish();
