/* chatsurface — #562: the topic-chat list carries an unread/total count and
   each row links to a /chat/<id> page that renders the conversation. #563: the
   section is ALWAYS visible — a chatless target still renders the label,
   `0 total`, and a dim `none yet` empty-state line.

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
import { mkdirSync, rmSync, cpSync, readFileSync } from 'node:fs';
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
  drives: 'dashboard chat list (count line + row links), the always-visible ' +
          'empty state on a chatless target (#563), and /chat/<id> ' +
          '(transcript render + not-found degrade) in normal AND reduced motion',
  traceWindow: 'static reads after settle; no motion trace — the route ' +
               'dissolve is dissolve.mjs\'s gesture and the count line is a ' +
               'settled re-render. Reduced motion is asserted as parity of ' +
               'content (function), not of timing.',
});

// ── a target with REAL transcripts, through the production writer ──────────
// apply_chat_turn is the one writer (#504/#827): it preserves body structure,
// reversibly escapes structural-looking marker lines, and its parser anchors
// both dw-turn markers at line start. Planting through it proves the page reads
// what the loop writes. Never hand-build transcript text.
const DIR = join(OUT, 'target');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });
const QUESTION_SOURCE = readFileSync(
  join(DIR, '.dreamwork/questions.md'), 'utf8');
ok('#857 precondition: the document fixture has hard-wrapped source prose',
   /hard-wrapped across two\n\s+source lines/.test(QUESTION_SOURCE));
const addTurn = (id, role, text, at = null) => execFileSync('python3', ['-c',
  `import watch; watch.apply_chat_turn(${JSON.stringify(DIR)}, ` +
  `${JSON.stringify(id)}, ${JSON.stringify(role)}, ${JSON.stringify(text)}, ` +
  `${JSON.stringify(at)})`],
  { stdio: 'ignore' });
// pending + unread (one human turn — last turn is his)
addTurn('chat-unread', 'human', 'a question that needs a reply',
        '2026-01-01T00:00:00');
// replied + READ (human then agent — last turn is the dreamer's)
addTurn('chat-read', 'human', 'an answered question',
        '2026-01-03T00:00:00');
const MARKDOWN_REPLY = 'First line.\nSecond line.\n\nSecond paragraph.\n\n' +
  '> Quoted first line.\n> Quoted second line.\n\n' +
  '## Rendered reply\n\n- first item\n- second item\n\n' +
  '```python\nprint("<unsafe>")\n```\n\n' +
  '<script id="chat-inject">window.chatInjected=1</script>';
addTurn('chat-read', 'agent', MARKDOWN_REPLY,
        '2026-01-03T00:01:00');
ok('#857 precondition: the production-writer fixture contains a single newline',
   /[^\n]\n[^\n]/.test(MARKDOWN_REPLY));
// replied + UNREAD (he followed up AFTER the reply — last turn is his again)
addTurn('chat-followup', 'human', 'first message',
        '2026-01-02T00:00:00');
addTurn('chat-followup', 'agent', 'a reply landed',
        '2026-01-02T00:01:00');
addTurn('chat-followup', 'human', 'a follow-up after the reply',
        '2026-01-02T00:02:00');

// own port — the shared fixture is chatless and this guard owns its target
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const PORT = await freePort();
const child = await serveVerified(DIR, PORT, { expect: DIR });
const BASE = `http://127.0.0.1:${PORT}`;

// ── a CHATLESS target for the always-visible empty state (#563) ──────────
// The shared fixture is chatless by default (no .dreamwork/chats-v1/), so a
// fresh copy with NO apply_chat_turn is the empty case — the production
// writer is deliberately NOT called, proving the page reads absence the same
// way collect surfaces it (collect → []). chatList must still render the
// label + `0 total` + a dim `none yet` line on this target (#563 made the
// section always visible; was `return ''` under #504).
const EDIR = join(OUT, 'target-empty');
rmSync(EDIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', EDIR, { recursive: true });
const EPORT = await freePort();
const echild = await serveVerified(EDIR, EPORT, { expect: EDIR });
const EBASE = `http://127.0.0.1:${EPORT}`;

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

  // ── Act 0: the empty state — the section is always visible (#563) ───────
  // A chatless target still renders the section. Production line: chatList's
  // empty branch (the absence of the old `return ''` guard + the else-arm
  // `none yet` copy). The empty-state dim line is bound to the chat section
  // SPECIFICALLY — it is the topic-chats label's immediate next sibling — so
  // the answers panel's own `none yet` (watch.py) cannot satisfy this check
  // (the hollow-trap: a bare `.dim` text match would pass over a chat
  // regression). No motion is traced: the empty state is static DOM, so
  // reduced-motion parity is the identical render (transitions.md).
  await p.goto(`${EBASE}/`, { waitUntil: 'networkidle' });
  await waitFor(p, '.label');
  const edash = await p.evaluate(() => {
    const labels = [...document.querySelectorAll('.label')];
    const lab = labels.find(x => (x.textContent || '').startsWith('topic chats'));
    // chatList emits label(...) + '<div class="dim">none yet</div>' with
    // nothing between, so the empty-state line is the label's next element.
    const next = lab ? lab.nextElementSibling : null;
    return {
      label: lab ? lab.textContent : null,
      nextIsDim: !!(next && next.classList.contains('dim')),
      nextText: next ? (next.textContent || '').trim() : '',
      rowCount: document.querySelectorAll('[data-chat]').length,
    };
  });
  notes.push('empty dashboard: ' + JSON.stringify(edash));
  ok('#563 empty: the topic-chats label renders on a chatless target',
     !!edash.label);
  ok('#563 empty: the count line is exactly "topic chats · 0 total"',
     edash.label === 'topic chats · 0 total');
  ok('#563 empty: no unread clause at 0 chats',
     edash.label && !edash.label.includes('unread'));
  ok('#563 empty: no chat rows on a chatless target',
     edash.rowCount === 0);
  ok('#563 empty: the dim "none yet" line is the section body ' +
     '(the label\'s next sibling, not the answers panel\'s own "none yet")',
     edash.nextIsDim && edash.nextText === 'none yet');

  // ── Act 1: the count line tells the truth + rows are links ──────────────
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await waitFor(p, '[data-chat]');
  const dash = await p.evaluate(() => {
    const labels = [...document.querySelectorAll('.label')];
    const lab = labels.find(x => (x.textContent || '').startsWith('topic chats'));
    const rows = [...document.querySelectorAll('[data-chat]')].map(a => ({
      tag: a.tagName, href: a.getAttribute('href') || '',
      id: a.getAttribute('data-chat') || '',
      top: Math.round(a.getBoundingClientRect().top),
      turnText: ((a.querySelector('.age') || {}).textContent || '').trim(),
      text: (a.textContent || '').trim(),
      breaks: a.querySelectorAll('br').length,
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
  ok('adjacent chat rows occupy distinct lines (never "2 turnsreplied")',
     new Set(dash.rows.map(r => r.top)).size === dash.rows.length);
  ok('every settled row count matches its authoritative transcript count',
     dash.rows.length > 0 && dash.rows.every(r => {
       const rec = byId.get(r.id);
       const want = rec && (rec.turns === 1 ? '1 turn' : `${rec.turns} turns`);
       return r.turnText === want;
     }));
  const followupRow = dash.rows.find(r => r.id === 'chat-followup');
  ok('the followup chat has a row linking to its page',
     !!followupRow && followupRow.href === '/chat/chat-followup');
  const readRow = dash.rows.find(r => r.id === 'chat-read');
  ok('#857 dashboard preview remains the escaped one-line preview (0 <br>)',
     !!readRow && readRow.breaks === 0 &&
     readRow.text.includes('First line. Second line.'));

  // #657: drive the transient state he reported, not the settled reload.
  // chat-read is deliberately newest before this submission and carries
  // "2 turns". A fresh pending row is inserted above it. Without a stable
  // row key morphdom reuses chat-read's positional `.age` node, whose
  // reconcileGuard-owned text stays "2 turns" even though /data.json already
  // says the new chat has exactly one complete human turn. A later reload
  // rebuilds the DOM and appears to "settle" it to 1 — the observed shape.
  const submitted = await p.evaluate(async () => {
    const action = crypto.randomUUID();
    const r = await fetch('/command', {
      method: 'POST',
      headers: {'Content-Type':'application/json',
                'X-Client-Action-Id': action},
      body: JSON.stringify({kind:'chat', text:'fresh count probe', from:'/'}),
    });
    const body = await r.json();
    await tick();                 // immediate live reconcile; no reload/settle
    const id = body.receipt && body.receipt.receipt_id;
    const row = id && document.querySelector(`[data-chat="${id}"]`);
    const server = await (await fetch('/data.json')).json();
    const rec = (server.chats || []).find(c => c.id === id);
    return {
      status: r.status, id,
      serverTurns: rec && rec.turns,
      serverStatus: rec && rec.status,
      domTurns: row && row.querySelector('.age') &&
                row.querySelector('.age').textContent.trim(),
    };
  });
  notes.push('fresh chat immediately after submit: ' + JSON.stringify(submitted));
  ok('fresh chat submission committed a pending one-turn transcript',
     submitted.status === 202 && submitted.serverStatus === 'pending' &&
     submitted.serverTurns === 1);
  ok('fresh chat immediately renders "1 turn"; an unkeyed row must not reuse ' +
     'the previous chat\'s reconcileGuard-owned "2 turns" age text',
     submitted.domTurns === '1 turn');

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

  // #827: assert the RENDERED DOM, never the input string. The fixture was
  // planted through apply_chat_turn, so these nodes jointly prove transcript
  // newlines survived and chatTurn passed the parsed body through the shared
  // markdown renderer. Raw HTML remains inert visible text: mdInline escapes
  // before mdSpans adds its own trusted markup.
  await p.goto(`${BASE}/chat/chat-read`, { waitUntil: 'networkidle' });
  await waitFor(p, '.chaturn[data-role="agent"] .chatbody');
  const markdown = await p.evaluate(() => {
    const body = document.querySelector('.chaturn[data-role="agent"] .chatbody');
    const first = body && body.querySelector(':scope > p');
    const quote = body && body.querySelector('blockquote.mdquote');
    const lineHeight = first ? parseFloat(getComputedStyle(first).lineHeight) : 0;
    const range = document.createRange();
    if (first) range.selectNodeContents(first);
    const renderedLines = first
      ? new Set([...range.getClientRects()].filter(r => r.width > 1)
        .map(r => Math.round(r.top))).size : 0;
    const defaultProbe = document.createElement('div');
    defaultProbe.innerHTML = mdRender('control first\ncontrol second', mdInline);
    const chatProbe = document.createElement('div');
    chatProbe.innerHTML = mdRender('control first\ncontrol second', mdInline,
                                   { preserveSoftBreaks: true });
    return {
      paragraphs: body ? [...body.querySelectorAll(':scope > p')]
        .map(n => (n.textContent || '').trim()) : [],
      heading: body && body.querySelector('.mdh')
        ? body.querySelector('.mdh').textContent.trim() : '',
      bullets: body ? [...body.querySelectorAll('.mdli')]
        .map(n => (n.textContent || '').trim()) : [],
      code: body && body.querySelector('pre.mdcode')
        ? body.querySelector('pre.mdcode').textContent : '',
      paragraphBreaks: first ? first.querySelectorAll(':scope > br').length : 0,
      paragraphLines: first ? first.innerText.split('\n').length : 0,
      renderedLines,
      paragraphHeight: first ? first.getBoundingClientRect().height : 0,
      lineHeight,
      quoteBreaks: quote ? quote.querySelectorAll(':scope > br').length : 0,
      quoteLines: quote ? quote.innerText.split('\n').length : 0,
      fenceBreaks: body ? body.querySelectorAll('pre.mdcode br').length : 0,
      defaultControlBreaks: defaultProbe.querySelectorAll('br').length,
      chatControlBreaks: chatProbe.querySelectorAll('br').length,
      injectedNode: !!document.querySelector('#chat-inject'),
      injectedEffect: window.chatInjected === 1,
      literalScript: body ? body.textContent.includes('<script id="chat-inject">') : false,
    };
  });
  notes.push('markdown chat DOM: ' + JSON.stringify(markdown));
  ok('#857 rendered first paragraph has 2 lines / 1 <br> and measured height ' +
     `(${markdown.renderedLines} painted lines, ${markdown.paragraphBreaks} br, ` +
     `${markdown.paragraphHeight.toFixed(1)}px / ${markdown.lineHeight.toFixed(1)}px line)`,
     markdown.paragraphLines === 2 && markdown.renderedLines === 2 &&
     markdown.paragraphBreaks === 1 &&
     markdown.paragraphHeight >= markdown.lineHeight * 1.8);
  ok('#857 consecutive quote source lines render as 2 lines / 1 <br>',
     markdown.quoteLines === 2 && markdown.quoteBreaks === 1);
  ok('#857 the opt-in chat rendering differs from the flowed document control',
     markdown.defaultControlBreaks === 0 && markdown.chatControlBreaks === 1);
  ok('#857 <br> is not emitted inside fenced code', markdown.fenceBreaks === 0);
  ok('#827 markdown DOM preserves the blank-line paragraph boundary',
     markdown.paragraphs[1] === 'Second paragraph.');
  ok('#827 markdown DOM renders the heading node',
     markdown.heading === 'Rendered reply');
  ok('#827 markdown DOM renders both bullet nodes',
     JSON.stringify(markdown.bullets) ===
       JSON.stringify(['first item', 'second item']));
  ok('#827 markdown DOM renders the fenced code node',
     markdown.code === 'print("<unsafe>")');
  ok('#827 raw HTML is escaped before markdown markup is introduced',
     !markdown.injectedNode && !markdown.injectedEffect && markdown.literalScript);

  await sleep(2200); // pass through the normal 2s innerHTML/morph refresh
  const afterMorph = await p.evaluate(() => {
    const first = document.querySelector(
      '.chaturn[data-role="agent"] .chatbody > p');
    return {
      breaks: first ? first.querySelectorAll(':scope > br').length : 0,
      lines: first ? first.innerText.split('\n').length : 0,
    };
  });
  notes.push('chat soft break after 2s morph: ' + JSON.stringify(afterMorph));
  ok('#857 the settled 2s morph preserves 2 rendered lines / 1 <br>',
     afterMorph.lines === 2 && afterMorph.breaks === 1);

  // The same renderer is shared with document surfaces. Questions must keep
  // their normal Markdown soft-break rule: hard-wrapped source prose flows.
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
  await waitFor(p, '.qbody .md');
  const questionFlow = await p.evaluate(() => {
    const md = document.querySelector('.qbody .md');
    return {
      paragraphs: md ? md.querySelectorAll('p').length : 0,
      breaks: md ? md.querySelectorAll('p > br').length : -1,
    };
  });
  notes.push('question document flow: ' + JSON.stringify(questionFlow));
  ok('#857 question body wrapped prose still flows (paragraphs present, 0 <br>)',
     questionFlow.paragraphs > 0 && questionFlow.breaks === 0);

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
try { echild.kill(); } catch (_) {}
finish();
