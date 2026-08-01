
/* Command palette (#71): the heading's + opener reveals a small form to
   steer the dreaming loop without a chat turn. Submitting POSTs /command,
   which drops a source-tagged line into watch-events.log — the loop's tail
   monitor wakes on it (same transport as answers). A pop-out (Document
   Picture-in-Picture, window.open fallback) keeps the form handy while the
   main tab navigates; it identifies its project so multi-target popouts
   don't blur together. reduced-motion skips the drift, never the function. */
function ripple(x, y) {                     // soft expanding ring, dream feel
  if (rmr) return;
  const r = document.createElement('div');
  r.className = 'ripple';
  const s = 14;
  r.style.left = (x - s / 2) + 'px'; r.style.top = (y - s / 2) + 'px';
  r.style.width = r.style.height = s + 'px';
  r.style.transition = 'transform 1.1s cubic-bezier(.22,.61,.36,1), ' +
    'opacity 1.1s ease';
  r.style.opacity = '0.5';
  document.body.appendChild(r);
  requestAnimationFrame(() => {
    r.style.transform = 'scale(18)'; r.style.opacity = '0';
  });
  setTimeout(() => r.remove(), 1200);
}
/* the popped-out window is a bare document — give it its own dark theme and
   an identity band tinted like the page it came from. */
const POPOUT_CSS = `
  :root { color-scheme:dark; }
  * { scrollbar-width:thin; scrollbar-color:#4b5563 transparent; }
  ::-webkit-scrollbar { width:7px; height:7px; }
  ::-webkit-scrollbar-track { background:transparent; }
  ::-webkit-scrollbar-thumb { background:#4b5563; border-radius:4px; }
  ::-webkit-scrollbar-thumb:hover { background:#6b7280; }
  body { margin:0; background:#0b0f19; color:#d1d5db;
    font-family:ui-monospace,'JetBrains Mono',monospace; font-size:13px; }
  #dreambg { position:fixed; inset:0; z-index:-1; width:100vw;
             height:100vh; }
  .strip { height:4px; background:__STRIP__; }
  .phead { padding:.7rem .9rem .1rem; }
  .ptitle { color:#f3f4f6; }
  .ppath { color:#6b7280; font-size:.72rem; word-break:break-all;
    margin-top:.15rem; }
  form { padding:.3rem .9rem .9rem; }
  .plabel { color:#6b7280; text-transform:uppercase; letter-spacing:.08em;
    font-size:.66rem; margin:.6rem 0 .3rem; }
  select, textarea { width:100%; box-sizing:border-box; background:#111827;
    color:#d1d5db; border:1px solid #1f2937; border-radius:4px; font:inherit;
    padding:.4rem; margin:.2rem 0; }
  textarea { min-height:3.2rem; resize:vertical; }
  button { background:#1e293b; color:__ACCENT__; border:1px solid #334155;
    border-radius:4px; font:inherit; padding:.3rem .9rem; cursor:pointer;
    margin-top:.4rem; }
  .pmsg { color:#6b7280; font-size:.7rem; min-height:1em; margin-top:.4rem;
    transition:opacity .35s ease,filter .35s ease,transform .35s cubic-bezier(.32,.1,.2,1); }
  .pmsg.ok { color:__ACCENT__; }
  .pmsg.dreamin { transition:none;opacity:0;filter:blur(7px);transform:translateY(5px); }
  .pmsg.depart { opacity:0;filter:blur(7px);transform:translateY(-5px); }
  @media (prefers-reduced-motion:reduce){.pmsg{transition:none!important}}
  iframe { border:0; width:100%; height:calc(100vh - 54px); display:block;
    background:#0b0f19; }`;
const POPOUT_BODY = (base, path) => `
  <div class="strip"></div>
  <div class="phead"><div class="ptitle">+ command &middot; ${esc(base)}</div>
    <div class="ppath">${esc(path)}</div></div>
  <form id="pform" autocomplete="off">
    <div class="plabel">command the dream</div>
    <select id="pkind">${COMMANDS.map(c =>
      `<option value="${c.kind}">${esc(c.label)}</option>`).join('')}</select>
    <textarea id="ptext" placeholder="a thought for the dream…"></textarea>
    <div><button type="submit">send</button></div>
    <div class="pmsg" id="pmsg" aria-live="polite"></div>
  </form>`;
/* Every popped-out window (command form OR a doc/review iframe) wears the
   same identity: a hue-tinted band, the project basename + full path, and a
   matching title — so multiple target popouts never blur together. */
function popoutShell(w, base, path, tint, titleWord) {
  const doc = w.document;
  doc.title = titleWord + ' · ' + base + ' · dreamwork';
  const warm = tint >= 0;
  const accent = warm ? '#c4b5fd' : '#a5b4fc';
  const strip = warm ? 'linear-gradient(90deg,#6d5bd0,#a855f7)'
                     : 'linear-gradient(90deg,#4f5bd5,#5b8def)';
  doc.head.innerHTML = '<meta charset="utf-8">';
  const st = doc.createElement('style');
  st.textContent = POPOUT_CSS.replace(/__ACCENT__/g, accent)
                             .replace('__STRIP__', strip);
  doc.head.appendChild(st);
  return doc;
}
const popHead = (label, base, path) =>
  `<div class="strip"></div><div class="phead">` +
  `<div class="ptitle">${esc(label)} &middot; ${esc(base)}</div>` +
  `<div class="ppath">${esc(path)}</div></div>`;
/* Every floated window dreams the same dream. The shader is world-space
   anchored (#74): it reads ITS OWN window's screenX/screenY, so a popout
   parked anywhere over the page samples the identical deterministic field
   and the pattern stays continuous across the seam. Mounted after `fill`,
   because the fills assign body.innerHTML and would wipe the canvas. */
function mountPopoutBg(w, tint) {
  try {
    const cv = w.document.createElement('canvas');
    cv.id = 'dreambg';
    w.document.body.appendChild(cv);
    const bg = mountDreambg(w, cv, {});     // no dev overlay, no layer switcher
    if (!bg) return;
    bg.setTint(tint);                       // wear the spawning view's hue
    w.addEventListener('pagehide', () => bg.stop());
  } catch (e) { /* no WebGL here: the flat #0b0f19 still reads fine */ }
}
/* open a floating window — Document Picture-in-Picture where available (stays
   put while the main tab navigates), else a positioned window.open — and let
   `fill` render into it with the shared identity. */
async function openPopout(name, size, fill) {
  const d = await ensureData();
  const path = (d && d.target) || '';
  const base = path.split('/').filter(Boolean).pop() || 'dreamwork';
  const tint = TINT[view.name] || 0;
  let w = null;
  if (window.documentPictureInPicture &&
      documentPictureInPicture.requestWindow) {
    try { w = await documentPictureInPicture.requestWindow(size); }
    catch (e) { /* fall through */ }
  }
  if (!w) w = window.open('', name + '_' + base,
    'width=' + (size.width + 20) + ',height=' + (size.height + 20) +
    ',left=80,top=80');
  if (w) { fill(w, base, path, tint); mountPopoutBg(w, tint); }
  return w;
}
/* #255 — one confirmation lifecycle for every composer surface. Success is
   valid even when another draft begins, so it owns its ~5s readable hold and
   atmospheric departure. False/error claims withdraw it immediately. Closing
   a surface is destruction: clear synchronously and cancel old callbacks. */
const CMD_CONFIRM_HOLD_MS = 5000;
function confirmationFor(doc,id,baseClass,reduced) {
  const view=doc.defaultView||window,node=()=>doc.getElementById(id);
  let holdT=0,clearT=0,generation=0,departEnd=null;
  const cancel=()=>{
    view.clearTimeout(holdT);view.clearTimeout(clearT);holdT=clearT=0;
    const m=node();if(m&&departEnd)m.removeEventListener('transitionend',departEnd);
    departEnd=null;
  };
  const clear=()=>{generation++;cancel();const m=node();if(m){m.textContent='';m.className=baseClass;}};
  const show=(text,ok,lifecycle,expectedGeneration)=>{
    if(expectedGeneration!==undefined&&expectedGeneration!==generation)return false;
    generation++;const mine=generation;cancel();const m=node();if(!m)return false;
    m.className=baseClass+(ok?' ok':'');m.textContent=text;
    if(!reduced&&text){m.classList.add('dreamin');void m.offsetWidth;
      view.requestAnimationFrame(()=>{if(mine===generation)m.classList.remove('dreamin')});}
    if(lifecycle)holdT=view.setTimeout(()=>{if(mine!==generation)return;
      if(reduced){clear();return;}
      m.classList.add('depart');
      departEnd=()=>{if(mine===generation)clear();};
      m.addEventListener('transitionend',departEnd,{once:true});
      clearT=view.setTimeout(departEnd,650);
    },CMD_CONFIRM_HOLD_MS);
    return true;
  };
  const begin=()=>{
    clear();const mine=generation;
    return {success:()=>show('sent to the dream',true,true,mine),
      claim:(text,ok=false)=>show(text,ok,false,mine)};
  };
  /* `note` is `claim` with the LIFECYCLE — a report of something that already
     happened, so it holds for ~5s and then departs on the atmospheric exit
     rather than sitting in the chrome until something else replaces it. The
     composer has no use for it (its success text is fixed, and its failures
     are claims that must not depart gently while still false); #284's copy
     confirmation does, for both outcomes, because a copy that failed a second
     ago is history and not a standing claim about the world. */
  return {begin,claim:(text,ok=false)=>show(text,ok,false),
          note:(text,ok=true)=>show(text,ok,true),clear};
}
async function requestPopout() {
  const w = await openPopout('dreamcmd', { width: 340, height: 320 },
    (w, base, path, tint) => {
      const doc = popoutShell(w, base, path, tint, '+ command');
      doc.body.innerHTML = POPOUT_BODY(base, path);
      // #860 — the textarea FILLS the popout exactly: no scrollbar, but one
      // pixel taller and there would be. CSS flex left slack (flex-basis auto
      // absorbs growth), so the fill is JS-computed and self-correcting: set
      // the textarea tall, read how far the document overflowed, and subtract
      // that excess from the height. The result makes documentElement scroll
      // height == client height, and +1px tips it over. Re-run on every resize
      // so the fill survives the window being dragged. resize:none because the
      // window itself is the resize unit now, not the textarea handle.
      const fitPopout = () => {
        const ta = doc.getElementById('ptext');
        if (!ta) return;
        const de = doc.documentElement;
        ta.style.resize = 'none';
        const prevH = ta.style.height, prevMH = ta.style.minHeight;
        ta.style.minHeight = '0'; ta.style.height = '9999px';
        void ta.offsetWidth;
        const fillH = 9999 - (de.scrollHeight - de.clientHeight);
        ta.style.height = fillH + 'px'; ta.style.minHeight = '0';
        void ta.offsetWidth;
      };
      w.addEventListener('resize', fitPopout);
      const endpoint = location.origin + '/command';
      // captured at SPAWN, not read at submit: this window floats free while
      // the main tab navigates on, and its own location is about:blank. Where
      // it was popped out FROM is the honest hint, and it is also the thing he
      // popped it out to keep beside him.
      const from = fromPath();
      const confirmation=confirmationFor(doc,'pmsg','pmsg',w.matchMedia('(prefers-reduced-motion: reduce)').matches);
      w.addEventListener('pagehide',confirmation.clear,{once:true});
      doc.addEventListener('keydown', ev => {        // Ctrl/Cmd+Enter submits
        if ((ev.ctrlKey || ev.metaKey) && ev.key === 'Enter') {
          ev.preventDefault(); doc.getElementById('pform').requestSubmit();
        }
      });
      // #459: popout #ptext binds to DraftStore as popout:main — same rules
      // as the main composer (save every input, restore into empty, clear
      // only on durable success). The popout document is a separate window
      // but shares the same origin localStorage partition.
      const pta = doc.getElementById('ptext');
      const popLid = DraftStore.id('popout', 'main');
      if (pta) {
        DraftStore.bind(pta, popLid);
        DraftStore.restore(popLid, pta);
      }
      fitPopout();   // #860: size to fill after the draft is restored into the box
      doc.getElementById('pform').addEventListener('submit', async ev => {
        ev.preventDefault();
        const kind = doc.getElementById('pkind').value;
        const text = doc.getElementById('ptext').value.trim();
        if (kind !== 'do-next' && !text) {
          confirmation.claim('a thought is needed'); return;
        }
        const attempt=confirmation.begin();
        try {
          // #274: raw-fetch site owns its headers — send the per-attempt id
          // from the popout draft's store so a double-click dedupes, same as
          // the postJSON paths.
          const popHeaders = { 'Content-Type': 'application/json' };
          const popAid = DraftStore.attemptId(popLid);
          if (popAid) popHeaders['X-Client-Action-Id'] = popAid;
          const r = await fetch(endpoint, { method: 'POST',
            headers: popHeaders,
            body: JSON.stringify({ kind, text, from }) });
          // raw-fetch site: owns its Response, so reads the verdict here. A
          // rejected 202 (r.ok true) would otherwise clear his thought (#136).
          const pv = await writeVerdict(r);
          // attach for isDurable (same shape postJSON sets)
          r._dwv = pv;
          if (DraftStore.isDurable(r)) {
            if(!attempt.success())return;
            doc.getElementById('ptext').value = '';
            DraftStore.clear(popLid);
          } else {
            const why = (pv.rejected && pv.reason && REJECT_WHY[pv.reason])
                     || QSEND_WHY[pv.status];
            attempt.claim(why ? `not written — ${why}. your words are kept`
                              : 'rejected (' + r.status + ')');
          }
        } catch (e) { attempt.claim('no connection'); }
      });
    });
  if (w && window.__closeCmd) window.__closeCmd();
}
/* pop a doc/review into a floating iframe window (kept identity header) so it
   stays handy while the main tab navigates. #556: src/title are
   attribute-position, fed by `pip.dataset.pip*` — which parse escA's
   `&quot;` BACK to a raw `"` on read, so the whole payload re-enters as one
   value one hop past #374's pipBtn fix. escA (not esc) keeps the quote
   inside the attribute; `label` is the live vector (the raw decoded label),
   `src` carries `/file?p=<encodeURIComponent payload>` so its `"` arrives as
   %22 — nearly safe already, but escA is correct-by-position there too. */
function popoutDoc(url, label) {
  openPopout('dreamdoc', { width: 620, height: 560 },
    (w, base, path, tint) => {
      const doc = popoutShell(w, base, path, tint, label);
      doc.body.innerHTML = popHead(label, base, path) +
        `<iframe src="${escA(url)}" title="${escA(label)}"></iframe>`;
    });
}
/* The rich composer has one mount route. A target supplies the document and
   window that own its DOM; the implementation stays inside this function, so
   a surface that bypasses the contract gets neither bindings nor a mounted
   marker — there is no fallback renderer to drift into a stale twin. */
function mountComposer(target) {
  if (!target || !target.document || !target.window || !target.surface)
    throw new Error('composer mount requires document, window and surface');
  const document = target.document;
  const window = target.window;
  const pal = document.getElementById('cmdpalette');
  if (!pal)
    throw new Error('composer mount ' + target.surface + ' missing #cmdpalette');
  if (pal.dataset.composerMount)
    throw new Error('composer already mounted by ' + pal.dataset.composerMount);
  pal.dataset.composerMount = target.surface;
  const confirmation=confirmationFor(document,'cmdmsg','cmdmsg',rmr);
  /* ── the status line ARRIVES, it does not appear (#159) ──────────────────
     It used to be four bare `textContent` assignments: the text landed,
     `:empty` stopped applying, and the line was simply THERE on the next
     paint. Everything else on this page that turns up eases in, and this is
     the composer's only feedback that a steer reached the loop at all.

     ONE implementation, for the usual reason: there were four assignment
     sites and a fifth message would otherwise have arrived differently from
     the other four.

     The enter is the page's standing `.dreamin` snap — which only started
     working at all today (#154), so this is its first new user. The forced
     reflow is not decoration: without a style recalc between adding the class
     and removing it, the element never commits opacity 0 and the transition
     has nothing to run from. That IS #154, and it is cheaper to be correct by
     construction here than to rely on some other read forcing the layout. */
  const setCmdMsg=(text,ok)=>confirmation.claim(text,ok);
  /* A successful claim departs through confirmationFor. Clearing here means
     destruction (manual close/route change), so it is intentionally instant:
     keeping a dead surface's timer alive can erase a later message after the
     composer reopens. False/error claims replace success immediately for the
     same reason — a false statement must not linger through a departure. */
  const clearCmdMsg=confirmation.clear;
  let open = false;
  const CMD_GAP = 18;            // breathing room under the +/× opener
  /* ── the panel does not close under him (#131 / #291) ────────────────────
     His words: "if on the composer, someone enters something, ctrl+enter
     submits, then starts typing again, the composer should not fade away.
     also the timeout before fading away should be increased by 1.5x."
     And later (#291): it should auto-disappear ~1.5s after a successful
     command, not after the confirmation's ~5s hold (#255 accidentally
     tied the two together).

     The auto-dismiss is a courtesy — it gets the panel out of the way once
     the thought has landed — and a courtesy must never take a channel away
     from someone who is still using it. That is the same rule as #118: what
     the human is in the middle of doing outranks anything the page decided
     on a timer. Any sign of him still being in here cancels the dismiss, and
     `composing` covers the race where he resumes DURING the POST, before
     there is a timer to cancel. The confirmation lifecycle is independent:
     typing cancels only this timer; left alone, panel close is destruction
     and hard-clears the line with the panel. */
  const CMD_DISMISS_MS = 1425;               // was 950; his 1.5x (#131/#291)
  let dismissT = 0, composing = false;
  const cancelDismiss = () => { clearTimeout(dismissT); dismissT = 0; };
  /* ── the half-typed thought survives a reload (#163) ─────────────────────
     The panel already keeps its text across a close and across a route
     change — it lives outside `#view`, so nothing rebuilds it. What loses his
     words is a RELOAD: the tab crashing, him refreshing, the server restarting
     and `tick` calling `location.reload()` on a new generation. That last one
     is the page doing it TO him.

     BROWSER STORAGE IS RIGHT HERE AND WAS WRONG FOR #143, and the difference
     is worth stating because the two look identical from a distance. A tint is
     a setting ABOUT the project: it should follow the project to another
     machine, so it lives in `.dreamwork/watch-tint` and is committable. An
     unsent draft is a thought in progress that he has not chosen to send to
     anyone — writing it to the repo would publish it, and #199 already gives
     the server a verbatim record of everything he DID send. So this one stays
     in the browser, on this machine, and never travels.

     PARTITIONED BY `data.target`, the absolute project path — not by the
     project NAME, because two checkouts can share a basename and a draft
     surfacing under the wrong loop is worse than a lost one. With no target
     yet (the first fetch has not landed) nothing is read or written at all,
     rather than everything sharing an empty key.

     THE TWO-WINDOW SEMANTIC, stated rather than discovered: he runs several
     windows per project — that is what #143 syncs a tint for — and they share
     one key, so the store holds THE MOST RECENT unsent thought on this
     project. A restore never overwrites a box that already has text in it
     (#118's rule: what he is in the middle of outranks anything stored), so
     two live composers never fight; only the stored copy is last-write-wins.

     IT RESTORES SILENTLY, and that is a decision about a different channel.
     `setCmdMsg` is the composer's one line for whether his command LANDED
     (#159), and putting "draft restored" on it would spend the one place he
     looks for a send confirmation on something that is not one. The text
     being in the box is the statement. */
  /* Composer drafts ride DraftStore as composer:main. draftKey keeps the
     pre-module key shape string (`'dw:draft:' + tgt`) so dual-read and the
     partition unit test still name the same contract; the module owns the
     actual write. */
  const draftKey = () => {
    const tgt = (typeof data !== 'undefined' && data && data.target) || '';
    return tgt ? 'dw:draft:' + tgt : '';
  };
  const composerLid = () => DraftStore.id('composer', 'main');
  function saveDraft() {
    // touch draftKey so the partition string stays live in PAGE for tests
    if (!draftKey()) return;
    const t = document.getElementById('cmdtext');
    if (!t) return;
    DraftStore.save(composerLid(), t.value,
      t.value ? { kindHint: activeKind } : undefined);
  }
  /* ONLY on a successful send, which is the whole contract. A draft that is
     cleared on close, on blur, or on a rejected POST is a draft that
     disappears at exactly the moments he most needs it back. */
  function clearDraft() {
    if (!draftKey()) return;
    DraftStore.clear(composerLid());
  }
  function restoreDraft() {
    const t = document.getElementById('cmdtext');
    if (!draftKey() || !t || t.value) return;   // a live box outranks storage (#118)
    const rec = DraftStore.get(composerLid());
    if (!rec || !rec.text) return;
    t.value = rec.text;
    fitText(t, false);                        // #177: size the box to the restored draft, snapped
    // the kind travels with the text, because the kind is WHERE THE TEXT GOES
    // (#103's rule for a card's mode, one surface over). Validated against the
    // live vocabulary: a plugin's command can disappear between sessions, and
    // silently sending his words as the wrong kind is worse than defaulting.
    const k = rec.meta && rec.meta.kindHint;
    if (k && COMMANDS.some(c => c.kind === k)) setKind(k);
  }
  // The composer is position:fixed, but `.wrap` carries `perspective`, which
  // makes IT the containing block — so `top`/`left` are measured from .wrap,
  // not the viewport. Rects are viewport coords, so subtract that origin or
  // the panel drifts right of the + and hangs a body-padding too low.
  function fixedOrigin() {
    const cb = document.querySelector('.wrap');
    if (!cb) return { x: 0, y: 0 };
    const b = cb.getBoundingClientRect();
    return { x: b.left, y: b.top };
  }
  function place() {
    const plus = document.getElementById('cmdplus');
    if (!plus) return;
    const r = plus.getBoundingClientRect();
    const w = pal.offsetWidth || Math.min(window.innerWidth * 0.92, 340);
    const o = fixedOrigin();
    // The opener rotates 45deg into an × when open, which swells its painted
    // box by its half-diagonal. Anchor off the centre (invariant under that
    // rotation) and the painted extent, so the breathing room is what the eye
    // sees and is the same whether we place while closed or while open.
    const bw = plus.offsetWidth || r.width;          // layout box, transform-free
    const bh = plus.offsetHeight || r.height;
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const left = cx - bw / 2;
    const bottom = cy + (bw + bh) * Math.SQRT2 / 4;   // rotated half-height
    pal.style.left =
      (Math.max(8, Math.min(left, window.innerWidth - w - 8)) - o.x) + 'px';
    pal.style.top = (bottom + CMD_GAP - o.y) + 'px';
  }
  // Command selection: a radiogroup of buttons with one background indicator
  // that slides between them. `snap` lands it without a slide — used for the
  // first placement and for reflows, because an indicator that animates from
  // its 0-width start reads as a glitch, not a choice (the enter-snap rule).
  const kindsEl = document.getElementById('cmdkinds');
  const menuEl = document.getElementById('cmdmenu');
  // #547 — the default kind is DECLARED, never positional: the entry marked
  // `default`, else the far-left kind as a last resort. A future reorder of
  // the row must not change the default; a future change of default must not
  // reorder the row. The marker rides COMMANDS (the `let` the plugin half
  // appends to, #86), so the fallback [0] is always a core kind when nothing
  // is marked. ONE resolver idiom, used at every read site (initial
  // selection, plugin-unload fallback, post-submit decay) so the three
  // cannot drift.
  const defaultKind = (from) => {
    const list = from || COMMANDS;
    const marked = list.find(c => c.default);
    return ((marked || list[0]) || {}).kind;
  };
  let activeKind = defaultKind();
  // The row carries the common kinds PLUS the active one when it is uncommon,
  // so whatever is selected always has a button for the indicator to sit on.
  // Rebuilding is membership-only: a common->common switch leaves the row
  // (and so the indicator) alone, which is what lets it slide.
  let rowKinds = [];
  const rowWant = () => COMMANDS
    .filter(c => c.common || c.kind === activeKind).map(c => c.kind);
  function renderKinds() {
    if (!kindsEl) return false;
    const want = rowWant();
    if (want.join('\u0000') === rowKinds.join('\u0000')) return false;
    rowKinds = want;
    kindsEl.innerHTML =
      '<span class="sgind cmdind" id="cmdind" aria-hidden="true"></span>' +
      COMMANDS.filter(c => want.indexOf(c.kind) >= 0).map(c =>
        '<button type="button" class="sgbtn cmdkind" data-kind="' + esc(c.kind) +
        // the row carries no visible plugin mark, on purpose: it is a MODE
        // switch whose one job is saying where the text goes, its width is
        // load-bearing (#162 is the row wrapping and taking the panel with
        // it), and by the time a kind is in the row he has already read the
        // attribution in the menu, which is the only place one is offered.
        // The title still names it, because the row is also where he comes
        // back to a choice he made an hour ago.
        '" role="radio" aria-checked="false" title="' + esc(c.desc) +
        (c.plugin ? esc(' · from ' + c.plugin) : '') + '">' +
        esc(c.label) + '</button>').join('');
    return true;
  }
  // The menu lists EVERY kind with its description — the discoverability
  // surface, and the only place a plugin's command is ever offered (#86).
  function menuItem(c) {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'cmdmenuitem';
    b.setAttribute('role', 'menuitem');
    b.dataset.kind = c.kind;
    // WHO ANSWERS THIS, named on the item itself, at the quietest step of the
    // ramp. A plugin command can vanish between sessions and a core one
    // cannot, so the two are not interchangeable and the menu says which is
    // which — quietly, because on the overwhelmingly common day no plugin
    // declares anything and this is one more word in a small menu.
    b.innerHTML = '<span class="cmk">' + esc(c.label) + '</span>' +
      (c.plugin ? '<span class="cmpl">' + esc(c.plugin) + '</span>' : '') +
      '<span class="cmd">' + esc(c.desc) + '</span>';
    return b;
  }
  /* Reconciled by KIND, not rebuilt, and that is what makes the arrival
     legible: the nodes it returns are exactly the ones that were not here
     before, so only they carry the enter idiom. An innerHTML rebuild would
     re-create the core items too — identical pixels, but any hover or focus
     he was holding would be dropped, and there would be no way to tell an
     arriving item from a surviving one. */
  function renderMenu() {
    if (!menuEl) return [];
    const have = new Map(
      [...menuEl.children].map(n => [n.dataset.kind, n]));
    const arrived = [], frag = document.createDocumentFragment();
    for (const c of COMMANDS) {
      let n = have.get(c.kind);
      if (n) have.delete(c.kind);
      else { n = menuItem(c); arrived.push(n); }
      frag.appendChild(n);              // appending a live node MOVES it
    }
    // written whole, so a plugin unloading is the ABSENCE of an entry rather
    // than a remembered deletion — the same move the file itself makes
    have.forEach(n => n.remove());
    menuEl.appendChild(frag);
    return arrived;
  }
  /* ── the plugin half of the vocabulary (#86) ─────────────────────────────
     `writing-plugins.md` has granted plugins their own command namespace in
     prose for as long as there have been plugins, and the composer could not
     render one: the contract promised what the UI could not show. It rides
     /data.json, so this runs on every tick and must be cheap and idempotent.

     COMPARED WHOLE, because the file is WRITTEN whole. Anything finer would
     be a second model of a file whose entire shape is "this is the current
     set", and the two could disagree. */
  let pluginKey = '[]';
  function syncPluginCommands(list) {
    const next = Array.isArray(list) ? list : [];
    const key = JSON.stringify(next);
    if (key === pluginKey) return [];      // every tick but the ones that matter
    pluginKey = key;
    COMMANDS = CORE_COMMANDS.concat(next);
    const arrived = renderMenu();
    /* His selection can be a command that no longer exists — he chose it, the
       plugin unloaded, and the row would still offer a kind the server now
       refuses with a bare 400. Fall back to the declared default, which
       cannot go away (the marker is on a core kind). */
    if (!COMMANDS.some(c => c.kind === activeKind))
      setKind(defaultKind(CORE_COMMANDS));
    else
      setKind(activeKind);                 // re-mark `.on` on the new nodes
    /* THE ARRIVAL, and the condition on it is not an exemption.
       A menu that is shut is not showing him anything, so nothing has
       appeared: when he next hovers it open, the menu's own reveal is what
       brings these in, and that gesture already obeys the page. What needs a
       gesture of its own is the case where the set changes UNDER HIS EYE —
       the menu open in front of him — and that is the one animated here. */
    if (!rmr && menuEl && window.getComputedStyle(menuEl).visibility === 'visible')
      arrived.forEach(n => {
        n.classList.add('qreveal', 'dreamin');
        requestAnimationFrame(() => n.classList.remove('dreamin'));
        setTimeout(() => n.classList.remove('qreveal'), CARD_MS + 150);
      });
    return arrived;
  }
  // the tick is the only caller; exposed because the composer is its own IIFE
  window.dwPluginCommands = syncPluginCommands;
  // the same slideIndicator every question card uses (#103) — one
  // implementation, so the composer and the cards can never drift apart
  const moveIndicator = snap => slideIndicator(kindsEl, snap);
  function setKind(kind) {
    activeKind = kind;
    // a rebuilt row has a brand-new 0-width indicator, so land it rather than
    // slide it up from nothing (the enter-snap rule)
    const rebuilt = renderKinds();
    kindsEl.querySelectorAll('.cmdkind').forEach(b => {
      const on = b.dataset.kind === kind;
      b.classList.toggle('on', on);
      b.setAttribute('aria-checked', on ? 'true' : 'false');
    });
    if (menuEl) menuEl.querySelectorAll('.cmdmenuitem').forEach(b =>
      b.classList.toggle('on', b.dataset.kind === kind));
    moveIndicator(rebuilt);
  }
  /* The saves hang off HIS choice, never off `setKind` itself. `setKind` also
     runs at init and from `restoreDraft`, and saving there would write the
     empty box over a stored draft before it was ever read — deleting the
     feature at the moment it was supposed to work. */
  if (kindsEl) kindsEl.addEventListener('click', e => {
    const b = e.target.closest('.cmdkind');
    if (b) { e.preventDefault(); setKind(b.dataset.kind); saveDraft(); }
  });
  if (menuEl) menuEl.addEventListener('click', e => {
    const b = e.target.closest('.cmdmenuitem');
    if (b) { e.preventDefault(); setKind(b.dataset.kind); saveDraft(); }
  });
  // the menu opens on hover/focus in CSS; mirror that into aria-expanded,
  // which CSS cannot set.
  /* ── the history (#165) ──────────────────────────────────────────────────
     THE SOURCE IS #175's CLIENT LOG, and that is a decision the task's own
     ledger line did not make — it said `watch-events.log`, written before #199
     and #175 existed. Three sources exist now and they are not
     interchangeable:

       · `watch-events.log` — has the route (#126), covers every window and
         every machine that reached this server, but it is a RENDERING: one
         line per act, summarised for an agent to read. It cannot say whether
         a submission landed, because a line is only written once one did.
       · `.dreamwork/submissions.log` (#199) — verbatim and complete, but
         written BEFORE the work, so it is pre-outcome by construction.
       · #175's client log — has the OUTCOME, which is the field he cannot
         recover any other way, and is the only witness to a submission the
         server refused or never heard.

     A history is for recall and recovery, so the outcome decides it. Mixing
     the three would mean explaining, on every row, which of them that row
     came from and what it therefore cannot tell him — a panel that has to
     apologise per row is worse than a narrow one that says its limit once.

     SO IT SAYS ITS LIMIT ONCE, at the foot: this browser only. The ledger
     asked for exactly that honesty about `watch-events.log` being machine-
     local, and it applies more sharply here, not less.

     ONE LIST WITH THE KIND MARKED, per the ledger — he does not think of an
     answer as a different act from a command, and two lists would ask him to
     remember which one he used. */
  const HIST_MAX = 40;
  const histRow = r => {
    const bad = r.outcome === 'rejected' || r.outcome === 'unreachable';
    const why = r.outcome === 'rejected' ? '(' + r.status + ')'
              : r.outcome === 'unreachable' ? '(never sent)' : '';
    return '<div class="cmdhrow' + (bad ? ' bad' : '') +
      (r.outcome === 'pending' ? ' pending' : '') + '">' +
      '<span class="cmdhkind">' + esc(r.kind || r.path || '?') + '</span>' +
      '<span class="cmdhtext" title="' + esc(r.text || '') + '">' +
      esc(r.text || '') + '</span>' +
      (why ? '<span class="cmdhwhy">' + esc(why) + '</span>' : '') +
      '<span class="cmdhage age" data-at="' + (r.at / 1000) + '"></span></div>';
  };
  async function renderHist() {
    const body = document.getElementById('cmdhistbody');
    const sum = document.getElementById('cmdhistsum');
    if (!body) return;
    const recs = (await subsAll()) || [];
    // newest first: the thing he is looking for is nearly always the last
    // thing he did, and `id` is the store's own order (#175)
    const rows = recs.slice().sort((a, b) => b.id - a.id).slice(0, HIST_MAX);
    if (sum) sum.textContent = rows.length ? 'history · ' + recs.length
                                           : 'history';
    body.innerHTML = rows.length
      ? rows.map(histRow).join('') +
        '<div class="cmdhnote">what this browser has sent, on this project. ' +
        'other windows and other machines keep their own.</div>'
      // THE EMPTY STATE SAYS "NOT HERE", NEVER "NOT AT ALL". This browser is
      // one witness of several: a fresh profile, a second machine, or a
      // cleared store all land here, and "you have sent nothing" would be a
      // confident false statement about his own history. Same sentence shape
      // as the populated footer, so the scope reads identically either way.
      : '<div class="cmdhnote">nothing sent from this browser yet. other ' +
        'windows and other machines keep their own.</div>';
    ages();                       // the ages tick with everything else (#132)
    // it ARRIVES, on the page's one enter idiom — the rows are fetched async,
    // so without this they appear a frame after the panel finished opening,
    // which is the snap #196 was about at a smaller size
    if (!rmr) {
      body.classList.add('qreveal', 'dreamin');
      requestAnimationFrame(() => body.classList.remove('dreamin'));
      setTimeout(() => body.classList.remove('qreveal'), CARD_MS + 150);
    }
  }
  const histEl = document.getElementById('cmdhist');
  if (histEl) histEl.addEventListener('toggle', () => {
    if (histEl.open) renderHist();
  });
  const moreEl = document.getElementById('cmdmore');
  if (moreEl) {
    const btn = moreEl.querySelector('.cmdmorebtn');
    const expose = v => btn && btn.setAttribute('aria-expanded', v);
    moreEl.addEventListener('pointerenter', () => expose('true'));
    moreEl.addEventListener('pointerleave', () => expose('false'));
    moreEl.addEventListener('focusin', () => expose('true'));
    moreEl.addEventListener('focusout', () => expose('false'));
  }
  renderMenu();
  setKind(activeKind);              // paint the initial row + selection
  // #570 — the composer box is manually resizable (CSS `resize:vertical`). A
  // drag of the native handle is continuous input, and the box's height
  // transition (.85s, #177) would put it behind his hand (transitions.md #305:
  // his pointer already supplies every intermediate position), so the press
  // PAUSES the transition for its whole duration: the box follows the pointer
  // rather than trailing it. A height change on release means he dragged it,
  // and that marks the composition manual — autosize yields to his size until
  // the next submit (the `_manual` gate in fitText), which re-enables growth.
  // `#cmdtext` is a static node (outside #view), so these listeners live once.
  (function () {
    const ta = document.getElementById('cmdtext');
    if (!ta) return;
    let pressH = null;
    ta.addEventListener('pointerdown', () => {
      pressH = ta.getBoundingClientRect().height;
      ta.style.transition = 'none';      // a drag is continuous: no transition
    });
    const release = () => {
      if (pressH == null) return;
      const endH = ta.getBoundingClientRect().height;
      if (Math.abs(endH - pressH) > 1) ta._manual = true;   // he dragged it
      pressH = null;
      void ta.offsetWidth;
      ta.style.transition = '';           // restore for autosize's growth (#177)
    };
    ta.addEventListener('pointerup', release);
    ta.addEventListener('pointercancel', release);
  })();
  // the shell is served before /data.json returns, so the plugin half is
  // normally still in flight here and arrives via the tick below; this covers
  // the case where it landed first and nothing would otherwise ask for it
  if (data) syncPluginCommands(data.plugin_commands);
  /* he is composing again, so the panel is not finished with */
  for (const ev of ['input', 'keydown', 'pointerdown'])
    pal.addEventListener(ev, () => {
      composing = true;
      // NO DEBOUNCE, deliberately: a debounce is a window in which his words
      // are lost, which is the one thing this exists to prevent. The value is
      // a single command, so the write is far too small to be worth batching.
      if (ev === 'input') {
        saveDraft();
        fitText(document.getElementById('cmdtext'), true);  // #177: grow with the thought
      }
      if (dismissT) cancelDismiss();
    });
  function openCmd() {
    cancelDismiss(); composing = false;
    place(); pal.classList.add('open'); open = true;
    // before the indicator moves: a restored draft may carry a KIND, and
    // `setKind` is what the indicator is being landed under (#163)
    restoreDraft();
    moveIndicator(true);          // land under the active kind, never slide in
    const plus = document.getElementById('cmdplus');
    if (plus) plus.classList.add('on');
    const t = document.getElementById('cmdtext');
    if (t) setTimeout(() => t.focus(), rmr ? 0 : 140);
  }
  function closeCmd() {
    cancelDismiss();
    pal.classList.remove('open'); open = false;
    document.querySelectorAll('#cmdplus.on').forEach(p =>
      p.classList.remove('on'));
    clearCmdMsg();
  }
  window.__closeCmd = closeCmd;
  document.addEventListener('submit', e => {
    if (e.target && e.target.id === 'askform') {
      e.preventDefault(); sendAsk(e.target);
    }
    // #577 — the /chat/<id> reply composer (sendChatReply lives in views.js;
    // one script scope, so it is reachable here at event time).
    if (e.target && e.target.id === 'chatreply') {
      e.preventDefault(); sendChatReply(e.target);
    }
  });
  document.addEventListener('click', e => {
    const pip = e.target.closest && e.target.closest('.pipbtn');
    if (pip) { e.preventDefault();
      popoutDoc(pip.dataset.pipurl, pip.dataset.piplabel || 'doc'); return; }
    const plus = e.target.closest && e.target.closest('#cmdplus');
    if (plus) { e.preventDefault(); open ? closeCmd() : openCmd(); return; }
    // #709 — the /chat/<id> archive toggle (sendChatArchive lives in
    // views.js; one script scope, reachable at event time).
    const arch = e.target.closest && e.target.closest('.chatarchbtn');
    if (arch) { e.preventDefault(); sendChatArchive(arch); return; }
    if (open && e.target.closest && !e.target.closest('#cmdpalette')) closeCmd();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && open) closeCmd();
  });
  // Ctrl/Cmd+Enter submits from a text field: an answer box (anywhere —
  // questions view, review dock), the command palette, or the /answers
  // ask box (#292 — same shortcut, same one-submit rule).
  document.addEventListener('keydown', e => {
    if (!((e.ctrlKey || e.metaKey) && e.key === 'Enter')) return;
    const t = e.target;
    if (t && t.tagName === 'TEXTAREA' && /^qi[oa]\d+$/.test(t.id)) {
      e.preventDefault(); submitCard(t.id.slice(2));
    } else if (t && t.id === 'cmdtext') {
      e.preventDefault();
      document.getElementById('cmdform').requestSubmit();
    } else if (t && t.id === 'askbox') {
      e.preventDefault();
      const form = document.getElementById('askform');
      if (form) form.requestSubmit();
    } else if (t && t.id === 'chatreplybox') {
      // #577 — the same shortcut, the same one-submit rule, one surface over.
      e.preventDefault();
      const form = document.getElementById('chatreply');
      if (form) form.requestSubmit();
    }
  });
  window.addEventListener('resize', () => {
    if (!open) return;
    place(); moveIndicator(true);         // the group may have re-wrapped
  });
  document.getElementById('cmdform').addEventListener('submit', async e => {
    e.preventDefault();
    const kind = activeKind;
    const text = document.getElementById('cmdtext').value.trim();
    if (kind !== 'do-next' && !text) {
      setCmdMsg('a thought is needed', false);
      return;
    }
    composing = false;          // from here, anything he does means "still here"
    {
      // THROUGH `postJSON`, not a fetch of its own (#175). It is the one seam
      // every submission passes, so routing the composer through it is what
      // makes the client-side record complete rather than well-intentioned —
      // a second fetch here would be a third of his submissions unwitnessed,
      // which is #191's lesson about one gesture spelled two ways, aimed at
      // data instead of at motion.
      const attempt=confirmation.begin();
      const r = await postJSON('/command', { kind, text, from: fromPath() },
          DraftStore.attemptId(composerLid()));
      const cv = r && r._dwv;
      if (r && cv && cv.landed) {
        if(!attempt.success())return;
        const plus = document.getElementById('cmdplus');
        if (plus) { const b = plus.getBoundingClientRect();
          ripple(b.left + b.width / 2, b.top + b.height / 2); }
        document.getElementById('cmdtext').value = '';
        clearDraft();  // unguarded ON PURPOSE: already inside cv.landed, and
        // an isDurable() here would read as a gate while gating nothing (#163)
        // #570 — a manual resize disabled autosize for that composition; a
        // submit re-enables it (the box resets to its floor in the fitText
        // call below), so the next thought grows again. The manual size is
        // not persisted (his words: "then it returns to normal behavior");
        // #571 may add a setting for that, out of scope here.
        const cmdTa = document.getElementById('cmdtext');
        cmdTa._manual = false;
        cmdTa._fitH = null;
        // #337: a landed STEERING command does not keep its kind — the
        // composer decays back to the default (the entry marked `default`,
        // else the far-left kind), so his NEXT message is never silently
        // promoted to the authority of the one he just sent. Read the
        // property off the LIVE table (COMMANDS is a `let`; plugin kinds
        // APPEND, #86), and absent means NOT sticky, so no kind is named
        // here and a new one is not a third place to remember. The default
        // is resolved by the one idiom (defaultKind), never positional, so a
        // row reorder cannot change what his next message lands as (#547).
        // The decay rides setKind — the indicator's existing slide, not a
        // second gesture (transitions.md). chat and add-idea are sticky
        // (#504) and skip this, so a conversation or a run of parked
        // thoughts is not interrupted by re-selection.
        const sent = COMMANDS.find(c => c.kind === kind);
        if (sent && !sent.sticky) setKind(defaultKind());
        fitText(document.getElementById('cmdtext'), true);  // #177: shrink back, the same gesture reversed
        // he may already have started typing again while the POST was in
        // flight, before there was any timer to cancel. Courtesy is NOT
        // the confirmation hold (#291): that is CMD_CONFIRM_HOLD_MS on the
        // controller, independent of whether the panel stays open.
        cancelDismiss();
        if (!composing) dismissT = setTimeout(closeCmd, CMD_DISMISS_MS);
      } else if (r) {
        // a rejected 202 (r.ok true, body rejected — E5) used to fall into the
        // success branch and clear his thought; the verdict routes it here and
        // names the reason in his voice. transitions.md: a falsehood replaces
        // success immediately and does not depart slowly.
        const why = (cv && cv.rejected && cv.reason && REJECT_WHY[cv.reason])
                 || (cv && QSEND_WHY[cv.status]);
        attempt.claim(why ? `not written — ${why}. your words are kept`
                          : 'rejected (' + r.status + ')');
      } else attempt.claim('no connection');   // postJSON returns null on throw
      // if he is watching the history, it must include what he just did —
      // including, and especially, when it failed
      if (histEl && histEl.open) renderHist();
    }
  });
  document.getElementById('cmdpop').addEventListener('click', requestPopout);
  return Object.freeze({ close: closeCmd, open: openCmd, surface: target.surface });
}
window.mountComposer = mountComposer;
mountComposer({ document, window, surface: 'main' });
