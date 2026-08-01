
window.DEV=/*DEV*/false;
const esc = t => { const d = document.createElement('div');
                   d.textContent = t ?? ''; return d.innerHTML; };
/* escA — attribute-position escape (#374). esc serialises TEXT (textContent →
   innerHTML), which escapes `&`, `<`, `>` but NOT `"` — the HTML serialiser
   only quotes inside attribute values. So esc's output is safe in element
   bodies but NOT between `="`…`"`: a `"` in the value closes the attribute
   early. The file route passes the raw `/file?p=` query param as a pip-button
   label, so a `"` in the query string let `onfocus=` ride in on the same
   focusable button. escA = esc plus `"` → `&quot;`, so the quote stays inside
   the attribute and the text-position esc keeps producing readable `"`. The
   pip-button builder's three `"`-delimited attributes use this; single-quote
   delimited attributes would need `&#39;` too, but the builder emits none. */
const escA = t => { const d = document.createElement('div');
                    d.textContent = t ?? '';
                    return d.innerHTML.replace(/"/g, '&quot;'); };
/* #836 — one split-bar component. The provenance breakdown and task-group
   progress both pass their named segments through this markup; callers own
   the words and the data, while this owns the geometry and stable segment
   identities. A zero total is not renderable: it has no denominator. */
function splitBar(rows, aria, key, animated) {
  const total = Array.isArray(rows)
    ? rows.reduce((n, row) => n + Number(row[1] || 0), 0) : 0;
  if (!(total > 0)) return '';
  return `<div class="provbar${animated ? ' panimate' : ''}" role="img" ` +
    `aria-label="${escA(aria)}">` +
    rows.map(([name, count, cls]) => {
      const value = Number(count || 0);
      return `<div id="${escA(`split-${key}-${cls}`)}" ` +
        `class="provseg ${escA(cls)}" ` +
        `style="flex-grow:${value};min-width:${value ? 2 : 0}px" ` +
        `title="${escA(`${name} ${value}`)}" aria-hidden="true"></div>`;
    }).join('') + `</div>`;
}
const ageStr = mt => {
  let s = Math.max(0, Date.now()/1000 - mt);
  for (const [u, div] of [["d",86400],["h",3600],["m",60]])
    if (s >= div) return `${Math.floor(s/div)}${u}`;
  return `${Math.floor(s)}s`;
};
/* the same age at commit resolution (#132 / #385): TWO units, each zero-
   padded to two digits — `05m 23s`, `02h 14m`, `03d 07h`, `02w 03d`,
   `01y 14w`.

   Two edges, both decided rather than fallen into:
     · under a minute it still reads as two units (`00m 12s`), so the column
       never changes width — and seconds-old is exactly when he is watching.
     · the ladder runs seconds → minutes → hours → days → weeks → years, so
       neither field reaches 100 for ~100 years (his invariant). Without the
       year and week rungs the day count alone passed 99 at 100 days.

   Year length is 365 days, not 52 weeks (= 364). A human reading `01y …`
   expects a calendar-ish year; 52 weeks of remainder inside that year is
   still ≤ 99, so the XX≤99 invariant holds either choice — but 365 matches
   the word "year" and the remainder is derived, not assumed. Weeks are
   always 7 days. */
const p2 = n => String(n).padStart(2, '0');
const AGE_Y = 365 * 86400, AGE_W = 7 * 86400;
const AGE_PAIRS = [
  ["y", AGE_Y, "w", AGE_W],
  ["w", AGE_W, "d", 86400],
  ["d", 86400, "h", 3600],
  ["h", 3600, "m", 60],
  ["m", 60, "s", 1],
];
/* {big, bu, small, su} — shared by the plain string form and the painted
   form so there is still one pair-selection path (#385). */
const ageParts = ct => {
  const s = Math.max(0, Math.floor(Date.now()/1000 - ct));
  for (const [bu, bd, su, sd] of AGE_PAIRS)
    if (s >= bd)
      return {big: Math.floor(s/bd), bu, small: Math.floor((s % bd)/sd), su};
  return {big: 0, bu: 'm', small: s, su: 's'};
};
const agePair = ct => {
  const p = ageParts(ct);
  return `${p2(p.big)}${p.bu} ${p2(p.small)}${p.su}`;
};
/* The pad digit of a single-figure unit is quieter than the value (#385):
   only the leading 0 of `05` / `09` wears `.agepad` — never a genuine tens
   digit. Shared by the two-figure and one-figure painters so the grey rule
   stays one path, not two that can drift apart. */
const pushFig = (frag, n) => {
  if (n < 10) {
    const pad = document.createElement('span');
    pad.className = 'agepad';
    pad.textContent = '0';
    frag.append(pad, String(n));
  } else {
    frag.append(p2(n));
  }
};
/* Write the pair into a live `.age` node — `05m 23s`, `02h 14m`. Built with
   DOM nodes rather than innerHTML — every character is a digit or unit
   letter we produced, but textContent cannot carry the pad span, and
   inventing a second parser for a four-token string would be a second
   formatter. No transition: ages() rewrites once a second as pure text
   update (transitions.md — the live mtime tick / ages sweep commits
   immediately; a digit flip is not a layout change). */
const paintAgePair = (el, ct, suffix) => {
  const p = ageParts(ct);
  const frag = document.createDocumentFragment();
  pushFig(frag, p.big);
  frag.append(p.bu, ' ');
  pushFig(frag, p.small);
  frag.append(p.su, suffix || '');
  el.replaceChildren(frag);
};
/* #392a: a date-only entry shows ONE figure, because the number of figures
   is the precision. A question title carries a day and no time, so the `ct`
   `qtHtml` builds is local midnight of that day — two figures would claim a
   sub-day time the file does not hold (a 24-minute-old entry reading
   `08h 17m ago`, every multi-day age ending in the same hour figure). So
   three days reads `03d ago` beside a timed commit's `03d 07h ago`: the
   MISSING second figure is the signal, read against the timed entries
   beside it. Reuses ageParts + the same greyed pad digit, so it is #385's
   idiom with the second figure removed rather than a second humanizer.
   An entry dated TODAY (under a day old) reads as the word `today` — `0d`
   is honest but reads as a broken zero for something filed this morning,
   and the word is the one honest thing day-only data supports. See
   watch-design.md (#392a). */
const paintDayAge = (el, ct) => {
  const s = Math.max(0, Math.floor(Date.now()/1000 - ct));
  if (s < 86400) { el.replaceChildren('today'); return; }   // same calendar day
  const p = ageParts(ct);
  const frag = document.createDocumentFragment();
  pushFig(frag, p.big);
  frag.append(p.bu, ' ago');
  el.replaceChildren(frag);
};
/* components: every section on every watch page renders through these */
const label = t => `<div class="label">${t}</div>`;
/* #819 — ONE button vocabulary. An action is outlined; specialist action
   types add behaviour without restating the button. Attribute names and
   classes are internal component inputs; every value that reaches markup is
   escaped here, at the one emit site. */
const buttonAttrs = attrs => Object.entries(attrs || {}).map(([name, value]) =>
  ` ${name}="${escA(value)}"`).join('');
const actionButton = ({ label, icon = '', className = '', title = '',
                        attrs = {}, iconOnly = false, armedLabel = '' }) => {
  const labels = armedLabel
    ? `<span class="uibtnlabels"><span>${escA(label)}</span>` +
      `<span class="uibtnarmed">${escA(armedLabel)}</span></span>`
    : (iconOnly ? '' : `<span class="uibtnlabel">${escA(label)}</span>`);
  return `<button class="uibtn uibtn-action${armedLabel ? ' uibtn-double' : ''}` +
    `${className ? ` ${className}` : ''}" type="button"` +
    `${title ? ` title="${escA(title)}"` : ''} aria-label="${escA(label)}"` +
    `${armedLabel ? ' aria-pressed="false"' : ''}${buttonAttrs(attrs)}>` +
    `${icon}${labels}</button>`;
};

const DOUBLE_CLICK_WINDOW_MS = 4000;
const doubleClickButton = ({ label, icon, className = '', attrs = {},
                             armedLabel = 'Action', windowMs = DOUBLE_CLICK_WINDOW_MS }) =>
  actionButton({ label, icon, className, armedLabel, attrs: {
    ...attrs, 'data-double-window': windowMs,
    style: `--double-click-window:${windowMs}ms`,
    'data-rest-label': label, 'data-armed-label': armedLabel,
  }});

const ARCHIVE_SVG = '<svg viewBox="0 0 20 18" width="14" height="13"' +
  ' aria-hidden="true"><path d="M2.5 5.5h15v10.5h-15zM1.5 2h17v3.5h-17z"' +
  ' fill="none" stroke="currentColor" stroke-width="1.4"' +
  ' stroke-linejoin="round"/><path d="M7 9h6" fill="none"' +
  ' stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>';

const doubleClickButtonState = new WeakMap();
function disarmDoubleClickButton(btn) {
  const state = doubleClickButtonState.get(btn);
  if (state && state.timer) clearTimeout(state.timer);
  doubleClickButtonState.delete(btn);
  btn.classList.remove('armed');
  btn.setAttribute('aria-pressed', 'false');
  btn.setAttribute('aria-label', btn.getAttribute('data-rest-label') || 'action');
}
/* First activation arms; only a second activation inside the component's
   window acts. `now` is injectable so a timing check can drive both sides of
   the boundary rather than waiting and accidentally testing only the happy
   path. Returns true only when `act` was admitted. */
function activateDoubleClickButton(btn, act, now = Date.now()) {
  const windowMs = Number(btn.getAttribute('data-double-window')) ||
    DOUBLE_CLICK_WINDOW_MS;
  const state = doubleClickButtonState.get(btn);
  if (state) {
    disarmDoubleClickButton(btn);
    if (now - state.armedAt < windowMs) { act(); return true; }
    return false;
  }
  const armedLabel = btn.getAttribute('data-armed-label') || 'Action';
  btn.classList.remove('armed');
  void btn.offsetWidth; // a fresh radial countdown after a prior expiry
  btn.classList.add('armed');
  btn.setAttribute('aria-pressed', 'true');
  btn.setAttribute('aria-label', `${armedLabel}: activate again within ${windowMs / 1000} seconds`);
  const armed = { armedAt: now, timer: null };
  armed.timer = setTimeout(() => {
    if (doubleClickButtonState.get(btn) === armed) disarmDoubleClickButton(btn);
  }, windowMs);
  doubleClickButtonState.set(btn, armed);
  return false;
}

/* a small standard picture-in-picture glyph — a low-emphasis action placed
   after doc/review affordances so pop-out is discoverable, never surprising.
   Clicking it floats the target (data-pipurl) in an identity-headed window. */
const PIP_SVG = '<svg viewBox="0 0 22 18" aria-hidden="true"' +
  '><rect x="1" y="1" width="20" height="16" rx="2.5"' +
  ' fill="none" stroke="currentColor" stroke-width="1.6"/>' +
  '<rect x="10.5" y="8.5" width="9" height="7" rx="1.2"' +
  ' fill="currentColor"/></svg>';
const pipBtn = (url, label) => actionButton({
  label: `pop out ${label}`, icon: PIP_SVG, iconOnly: true,
  className: 'pipbtn', title: 'pop out — floats while you navigate',
  attrs: { 'data-pipurl': url, 'data-piplabel': label },
});
/* #506 + #595 — the ONE emit for a known-internal path and its pip.
   Two guarantees at once, and until #595 the codebase could only hold one:

     #506  the pip never orphans onto a line of its own (it is chrome that
           must travel with the path it belongs to).
     #595  an arbitrarily long path never makes the PAGE scroll sideways.

   `.mdfile { white-space:nowrap }` bought the first by giving up the second —
   a 41-character path in `/file?p=DREAMWORK.md` scrolled the whole document
   32px sideways at 390px. Re-enabling wrapping on the `<code>` instead loses
   the first, and MEASURABLY so: swept over path lengths 30..120 at 390px, the
   pip orphaned at six of them. Chromium allows the line break wherever the
   INNERMOST inline box ending at that position permits one, so as long as the
   last thing before the button is wrappable text, `nowrap` on the enclosing
   `.mdfile` does not save it. (Verified against four other shapes — a word
   joiner, a nowrap `::after`, an inline pip, an inline-block unit — all six
   orphans, all of them.)

   So the path is emitted in two pieces. Everything but the last few characters
   rides `.wrapany` and breaks anywhere; the TAIL stays bare text in the unit's
   inherited `nowrap`, which makes the boundary before the button unbreakable
   BY CONSTRUCTION rather than by a rule about ancestors. The tail is a handful
   of characters plus a 14px glyph, so it fits on any line this page can
   produce — that is what makes the guarantee hold at ANY length rather than at
   the lengths someone tried. Swept 30..160: no orphan, no page overflow.

   TAIL_CH is small on purpose: it is dead weight in the wrap budget, and its
   only job is to be shorter than a line. The cut never lands inside an HTML
   entity — `lab` may carry `&amp;` from esc() — so a straddling entity moves
   the cut left to its `&`. */
const TAIL_CH = 6;
const tailCut = (s) => {
  let cut = Math.max(0, s.length - TAIL_CH);
  const amp = s.lastIndexOf('&', cut);
  if (amp >= 0 && s.indexOf(';', amp) >= cut) cut = amp;
  return cut;
};
const mdFileUnit = (url, label, pipLabel) => {
  const cut = tailCut(label);
  const head = label.slice(0, cut), tail = label.slice(cut);
  return '<span class="mdfile">`<a href="' + url + '">' +
         (head ? '<span class="wrapany">' + head + '</span>' : '') + tail +
         '</a>`' + pipBtn(url, pipLabel) + '</span>';
};
/* expand(): plain read peeks — dreams, .md files, status overflow.

   `keep` is a content-stable id for snapshotFolds / restoreFolds. It is NOT
   the summary text: summaries carry live counts (`the rest (6)`,
   `archive (3)`) that shift while the disclosure's identity does not. Without
   data-keep the live tick rebuilds the dashboard through innerHTML and the
   disclosure reappears closed under him (~2s /mtime poll; status.json
   rewrites force a re-render). Same class as #141 qsec / #494 tip: open state
   is his, nowhere on disk; restore is silent (`el.open = true`, no re-pose).
   Counted summaries MUST pass keep explicitly. */
const expand = (s, inner, cls='', keep='') => {
  const attr = keep ? ` data-keep="${esc(keep)}"` : '';
  return `<details class="peek"${attr}><summary class="${cls}">${s}</summary>` +
         `${inner}</details>`;
};
/* Backticked references become links only when the destination is known.
   `github.com/…` is an external URL; target files come from the collector's
   closed set. Everything else stays code — a broken link is a false promise.
   #506: a known-internal file link also carries the page's ONE pop-out
   affordance (`pipBtn`) immediately after the backticked span — same closed
   set as the link itself, never a second list. External and unknown get
   none: a pip floats a local view, and a pip on a 404 is a false promise.
   The pip sits OUTSIDE the backticks so mdSpans wraps only the path in
   <code> and the button stays chrome (not copy, not code); both ride a
   `.mdfile` nowrap unit so the glyph never orphans onto the next line. */
const linkify = h => h.replace(
  /`([\w.-]+(?:\/[\w.-]+)+\/?|[\w-]+\.[\w]{1,8})`/g,
  (m, p) => {
    if (p.startsWith('github.com/'))
      return '`<a href="https://' + p + '">' + p + '</a>`';
    if (data && Array.isArray(data.linkable_paths) &&
        data.linkable_paths.includes(p)) {
      const url = '/file?p=' + encodeURIComponent(p);
      return mdFileUnit(url, p, p);
    }
    return m;
  });
/* #522 — general markdown links `[text](target)`. Order is load-bearing:
   linkifyReview (more specific, review docks) runs first; this pass then
   consumes a known-internal or http(s) target whole so the `](…)` tail
   never bleeds; linkify's backticked-path pass runs last. Unknown targets
   stay fully literal (never half-rendered): the brackets remain visible
   and interior backticks become code without being promoted to links.
   Relative targets resolve against the viewed file's directory only when
   that resolution lands in `data.linkable_paths` — a broken link is a
   false promise, so anything else stays text. */
const mdNormJoin = (baseDir, rel) => {
  if (rel.startsWith('/')) return null;
  const parts = [...String(baseDir).split('/'), ...String(rel).split('/')];
  const stack = [];
  for (const p of parts) {
    if (p === '' || p === '.') continue;
    if (p === '..') { if (!stack.length) return null; stack.pop(); continue; }
    stack.push(p);
  }
  return stack.join('/');
};
const resolveMdTarget = (target, baseDir) => {
  // esc() may have turned & into &amp; inside a query string
  const t = String(target)
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>').replace(/&quot;/g, '"');
  if (/^https?:\/\//i.test(t)) return { kind: 'external', href: t };
  const paths = (data && Array.isArray(data.linkable_paths))
    ? data.linkable_paths : [];
  if (paths.includes(t)) return { kind: 'internal', path: t };
  if (baseDir != null) {
    const resolved = mdNormJoin(baseDir, t);
    if (resolved != null && paths.includes(resolved))
      return { kind: 'internal', path: resolved };
  }
  return { kind: 'literal' };
};
const linkifyMd = (h, baseDir) => h.replace(
  /\[([^\]]*)\]\(([^)\s]+)\)/g,
  (m, label, target) => {
    const r = resolveMdTarget(target, baseDir);
    // corpus often writes [`path`](…); strip surrounding backticks for display
    const lab = label.replace(/^`|`$/g, '');
    if (r.kind === 'internal') {
      const url = '/file?p=' + encodeURIComponent(r.path);
      // same .mdfile idiom as a backticked known path (#506, #595)
      return mdFileUnit(url, lab, r.path);
    }
    if (r.kind === 'external')
      // no pip — a pip floats a local view (#506)
      return '<a href="' + r.href + '" rel="noopener noreferrer">' + lab + '</a>';
    // fully literal: keep brackets, code-style interior backticks, but do
    // NOT leave raw `path` for linkify to half-promote (the bleed bug)
    return '[' + label.replace(/`([^`]+)`/g, '<code>$1</code>') +
           '](' + target + ')';
  });
const preB = t => `<pre>${linkify(esc(t))}</pre>`;
/* a backticked path to a review artifact docks THIS question onto the
   review page (carries its title); every other path stays a /file link.
   #472: the corpus mostly writes `.dreamwork/review/name.html` in backticks,
   which this always handled. One outlier wrote a markdown link
   [`name`](../review/name.html) — mdSpans has no [text](url) pass, and the
   relative `../review/` path is wrong for /questions — so the artifact was
   unreachable from the ask. Prefer the backticked shape; ALSO recognise
   markdown links whose target is a review artifact (basename after
   `../review/` or `.dreamwork/review/`) so a live entry that used the
   outlier shape still docks. A bare relative href is never left as-is.
   This pass stays MORE SPECIFIC than linkifyMd and must run first. */
const revDock = (name, title, label) =>
  '<a class="rev" href="/review?p=' + encodeURIComponent(name) +
  '&q=' + encodeURIComponent(title) + '">' + label + '</a>';
const linkifyReview = (escaped, title) => {
  // 1. markdown links to a review artifact — the #417 defect shape.
  //    Label may itself be backticked (`name`); strip those so the dock
  //    link is the affordance, not nested code around raw brackets.
  let h = escaped.replace(
    /\[(?:`)?([^\]`\n]+?)(?:`)?\]\((?:\.\.\/review\/|\.dreamwork\/review\/)([\w.-]+\.html?)\)/g,
    (m, text, name) => revDock(name, title, text));
  // 2. preferred corpus shape: backticked `.dreamwork/review/name.html`
  //    (link stays inside backticks so mdSpans wraps it in <code>, same as
  //    every other path linkifier on this page).
  h = h.replace(
    /`\.dreamwork\/review\/([\w.-]+\.html?)`/g,
    (m, name) => '`' + revDock(name, title, '.dreamwork/review/' + name) + '`');
  return h;
};
/* ── rendered prose (#102, #158) ──────────────────────────────────────────
   The loop writes its files hard-wrapped at ~72 columns. A <pre> renders
   those breaks literally and the browser re-wraps them again at a narrower
   reading column, so every paragraph breaks twice into a ragged mess. So we
   join the wraps back into paragraphs and let the column do the wrapping.

   The line this draws: MARKDOWN PROSE REFLOWS, RAW TEXT DOES NOT — by WHAT
   the text is, not who composed it (#158). Question bodies, answers,
   follow-ups, dreams, dashboard .md peeks, and `/file` for .md-like paths
   reflow through mdB. Source code and other files at `/file` stay verbatim
   in a <pre>. JSON is neither (#178). Status and git have their own components.

   Six things must survive the join, because each one carries meaning a
   joined line would destroy:
     · a blank line is a paragraph break
     · a leading `- ` is a real list item and its INDENT is its nesting —
       questions.md's whole parser rests on a sub-bullet never looking like
       an entry, and flattening the marker would render the two identically
     · a ``` fence is code, and code is not prose
     · a `#` heading stands alone
     · a leading `>` is a blockquote (#521) — consecutive quote lines form
       ONE block; a `>` inside a fence stays code (fences win)
     · a GFM pipe table (#525) — header row + `|---|` delimiter + body rows;
       cells keep their pipes as structure, not prose; a fence still wins
       over pipes; a malformed pair (no delimiter, ragged column count)
       degrades to prose rather than half-rendering
   Every other line break is a wrap, and gets joined with a space. */
const MD_BULLET = /^(\s*)[-*]\s+(.*)$/;
const MD_QUOTE = /^>\s?(.*)$/;
/* GFM pipe-table helpers (#525). Edge pipes are optional; cells trim.
   A delimiter cell is dashes with optional alignment colons — colons are
   IGNORED gracefully (no alignment rendering), not a second feature. */
const mdSplitRow = line => {
  let s = String(line).trim();
  if (s.startsWith('|')) s = s.slice(1);
  if (s.endsWith('|')) s = s.slice(0, -1);
  return s.split('|').map(c => c.trim());
};
const mdIsDelimRow = line => {
  const cells = mdSplitRow(line);
  // at least one cell, every cell is :?---+?: (one or more hyphens)
  return cells.length >= 1 &&
    cells.every(c => /^:?-{1,}:?$/.test(c) && /-+/.test(c));
};
const mdLooksLikeRow = line => {
  if (!String(line).includes('|')) return false;
  return mdSplitRow(line).length >= 2;
};
function mdBlocks(text, { preserveSoftBreaks = false } = {}) {
  const out = [];
  let cur = null, fence = null;
  const flush = () => { if (cur) { out.push(cur); cur = null; } };
  const lines = String(text == null ? '' : text).split('\n');
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/^\s*```/.test(line)) {                 // fence open or close
      if (fence) { out.push({ kind:'fence', text: fence.join('\n') }); fence = null; }
      else { flush(); fence = []; }
      continue;
    }
    if (fence) { fence.push(line); continue; }   // fences win over `>` and pipes (#521/#525)
    if (!line.trim()) { flush(); continue; }      // blank line ends a block
    if (/^\s*#{1,6}\s/.test(line)) {
      flush(); out.push({ kind:'h', text: line.replace(/^\s*#+\s*/, '') }); continue;
    }
    const m = line.match(MD_BULLET);
    if (m) { flush(); cur = { kind:'li', indent:m[1].length, text:m[2] }; continue; }
    const qm = line.match(MD_QUOTE);
    if (qm) {
      const piece = qm[1].trim();
      if (cur && cur.kind === 'quote') {
        if (piece) cur.text = cur.text
          ? (cur.text + (preserveSoftBreaks ? '\n' : ' ') + piece) : piece;
      } else {
        flush();
        cur = { kind: 'quote', text: piece };
      }
      continue;
    }
    // a non-quote line ends a quote block (do not glue prose onto it)
    if (cur && cur.kind === 'quote') flush();
    // #525 pipe table: header + delimiter of matching column count, then
    // consecutive pipe-looking body rows. Look-ahead is load-bearing —
    // without a well-formed delimiter the pipes stay prose (no half-render).
    if (mdLooksLikeRow(line) && i + 1 < lines.length && mdIsDelimRow(lines[i + 1])) {
      const header = mdSplitRow(line);
      const delim = mdSplitRow(lines[i + 1]);
      if (header.length === delim.length && header.length >= 2) {
        flush();
        const rows = [];
        i += 2; // consume header + delimiter
        while (i < lines.length && lines[i].trim() && mdLooksLikeRow(lines[i])) {
          rows.push(mdSplitRow(lines[i]));
          i++;
        }
        i--; // outer for-loop will advance
        out.push({ kind: 'table', header, rows });
        continue;
      }
      // ragged header/delimiter column counts → fall through to prose
    }
    if (cur) {
      cur.text += (preserveSoftBreaks ? '\n' : ' ') + line.trim();
      continue;
    }                                                      // a wrap: join it
    cur = { kind:'p', indent:0, text: line.trim() };
  }
  flush();
  if (fence) out.push({ kind:'fence', text: fence.join('\n') });
  return out;
}
/* Nesting is the RANK of a bullet's indent among the indents actually used,
   not the raw column count: a question body carries the source file's own
   2-space indent, so absolute columns would push every sub-bullet one level
   too deep. Rank is invariant to whatever base indent the text arrived with. */
function mdRender(text, inline, options = {}) {
  const blocks = mdBlocks(text, options);
  const renderInline = options.preserveSoftBreaks
    ? t => inline(t).replace(/\n/g, '<br>')
    : inline;
  const levels = [...new Set(blocks.filter(b => b.kind === 'li')
    .map(b => b.indent))].sort((a, b) => a - b);
  const mdTable = b => {
    // cells run the SAME inline pipeline as paragraphs/quotes (linkifyMd etc.)
    const th = b.header.map(c => `<th>${inline(c)}</th>`).join('');
    const body = b.rows.map(r => {
      // pad/truncate to header width so a ragged body row cannot add columns
      const cells = b.header.map((_, j) => (r[j] != null ? r[j] : ''));
      return '<tr>' + cells.map(c => `<td>${inline(c)}</td>`).join('') + '</tr>';
    }).join('');
    return `<table class="mdtable"><thead><tr>${th}</tr></thead>` +
           `<tbody>${body}</tbody></table>`;
  };
  return blocks.map(b =>
    b.kind === 'fence' ? `<pre class="mdcode">${esc(b.text)}</pre>` :
    b.kind === 'h' ? `<div class="mdh">${renderInline(b.text)}</div>` :
    b.kind === 'li' ? `<div class="mdli" style="--lvl:${levels.indexOf(b.indent)}">` +
                      `${renderInline(b.text)}</div>` :
    b.kind === 'quote' ? `<blockquote class="mdquote">${renderInline(b.text)}</blockquote>` :
    b.kind === 'table' ? mdTable(b)
                    : `<p>${renderInline(b.text)}</p>`).join('');
}

/* #282 — task references are resolved from DOM context, never by rewriting
   rendered HTML.  A TreeWalker can see the ancestry a regex sweep cannot:
   code, pre, existing links, scripts and the preview UI are rejected before
   a text node is parsed.  The same resolver is installed in the app document
   and same-origin review iframes, so Markdown and review HTML cannot drift. */
const TASK_REF_SKIP = 'a,button,code,pre,script,select,style,textarea,[data-task-ref-ui]';
const TASK_REF_RE = /(^|[^\w])#(\d+)\b/g;
const TASK_REF_CACHE_MS = 60 * 1000;
const taskRefCache = new Map();

function taskRefParts(text) {
  const out = [];
  let last = 0, match;
  TASK_REF_RE.lastIndex = 0;
  while ((match = TASK_REF_RE.exec(text)) !== null) {
    const hashAt = match.index + match[1].length;
    if (hashAt > last) out.push({ text: text.slice(last, hashAt) });
    out.push({ id: Number(match[2]), text: '#' + match[2] });
    last = hashAt + match[2].length + 1;
  }
  if (last < text.length) out.push({ text: text.slice(last) });
  return out;
}

function taskRefModel(task, stale) {
  if (!task) return { kind: 'missing', title: 'No such task', stale: false };
  const origin = ['human', 'loop', 'unknown'].includes(task.origin)
    ? task.origin : 'unknown';
  const body = String(task.body || '').replace(/\s+/g, ' ').trim();
  return {
    kind: 'task', stale: !!stale, id: task.id,
    title: task.title || 'Untitled task', date: task.date || 'date unknown',
    origin, state: task.state || 'unknown', priority: task.priority || null,
    type: task.type || null, owner: task.owner || null,
    dependencies: Array.isArray(task.dependencies) ? task.dependencies : [],
    description: body.length > 240 ? body.slice(0, 237).trimEnd() + '…' : body,
  };
}

function taskRefPanel(doc) {
  let panel = doc.getElementById('task-ref-preview');
  if (panel) return panel;
  const style = doc.createElement('style');
  style.dataset.taskRefUi = 'style';
  style.textContent = `
    .taskref{color:var(--accent,#7c8cff);text-decoration:underline;
      text-decoration-style:dotted;text-underline-offset:.18em}
    .taskref:focus-visible{outline:2px solid var(--accent,#7c8cff);outline-offset:3px}
    .taskpreview{position:fixed;z-index:2147483647;width:min(360px,calc(100vw - 24px));
      box-sizing:border-box;padding:14px 15px;border:1px solid rgba(140,150,190,.45);
      border-radius:12px;background:#171923;color:#f4f5fa;box-shadow:0 16px 50px #0008;
      font:13px/1.45 system-ui,sans-serif;opacity:0;transform:translateY(4px);
      pointer-events:none;transition:opacity 140ms ease,transform 140ms ease}
    .taskpreview.open{opacity:1;transform:none}.taskpreview .tp-title{font-weight:700;font-size:14px}
    .taskpreview .tp-meta{color:#b8bece;margin-top:4px}.taskpreview .tp-body{margin-top:8px}
    .taskpreview .tp-state{color:#ffd27a;margin-bottom:5px}
    @media(prefers-reduced-motion:reduce){.taskpreview{transition:none;transform:none}}
  `;
  (doc.head || doc.documentElement).appendChild(style);
  panel = doc.createElement('div');
  panel.id = 'task-ref-preview';
  panel.className = 'taskpreview';
  panel.dataset.taskRefUi = 'panel';
  panel.setAttribute('role', 'tooltip');
  panel.setAttribute('aria-live', 'polite');
  panel.hidden = true;
  doc.body.appendChild(panel);
  return panel;
}

function paintTaskRef(panel, model) {
  panel.replaceChildren();
  const add = (cls, text) => {
    if (!text) return;
    const node = panel.ownerDocument.createElement('div');
    node.className = cls; node.textContent = text; panel.appendChild(node);
  };
  if (model.kind === 'loading') return add('tp-state', 'Loading task…');
  if (model.kind === 'missing') return add('tp-state', 'No such task — this reference has no task data.');
  if (model.kind === 'unavailable') return add('tp-state', 'Task data unavailable — try again.');
  if (model.stale) add('tp-state', 'Stale task data — refresh failed.');
  add('tp-title', `#${model.id} — ${model.title}`);
  add('tp-meta', `${model.date} · origin ${model.origin} · ${model.state}`);
  const useful = [model.priority, model.type, model.owner && `owner ${model.owner}`,
    model.dependencies.length && `blocked on ${model.dependencies.map(n => '#' + n).join(', ')}`]
    .filter(Boolean).join(' · ');
  add('tp-meta', useful);
  add('tp-body', model.description || 'No description recorded.');
}

function positionTaskRef(panel, anchor) {
  panel.style.left = '0px'; panel.style.top = '0px'; panel.hidden = false;
  const r = anchor.getBoundingClientRect(), p = panel.getBoundingClientRect();
  const vw = panel.ownerDocument.documentElement.clientWidth;
  const vh = panel.ownerDocument.documentElement.clientHeight;
  const left = Math.max(8, Math.min(r.left, vw - p.width - 8));
  let top = r.bottom + 8;
  if (top + p.height > vh - 8) top = Math.max(8, r.top - p.height - 8);
  panel.style.left = left + 'px'; panel.style.top = top + 'px';
}

async function showTaskRef(anchor) {
  const doc = anchor.ownerDocument, panel = taskRefPanel(doc);
  const id = Number(anchor.dataset.taskId), cached = taskRefCache.get(id);
  const fresh = cached && Date.now() - cached.at < TASK_REF_CACHE_MS;
  paintTaskRef(panel, fresh ? taskRefModel(cached.task, false) : {kind:'loading'});
  panel.hidden = false; panel.classList.add('open');
  positionTaskRef(panel, anchor);
  if (fresh) return;
  try {
    const win = doc.defaultView && doc.defaultView.top || window;
    const res = await win.fetch('/tasksdata?t=' + encodeURIComponent(id));
    const payload = res.ok ? await res.json() : null;
    if (!payload || payload.health !== 'ok') throw new Error('task data unhealthy');
    taskRefCache.set(id, { task: payload.task || null, at: Date.now() });
    paintTaskRef(panel, taskRefModel(payload.task || null, false));
  } catch (e) {
    paintTaskRef(panel, cached
      ? taskRefModel(cached.task, true) : {kind:'unavailable'});
  }
  if (!panel.hidden) positionTaskRef(panel, anchor);
}

function hideTaskRef(doc) {
  const panel = doc.getElementById('task-ref-preview');
  if (!panel) return;
  panel.classList.remove('open');
  panel.hidden = true;
  doc.querySelectorAll('a.taskref[data-touch-ready]').forEach(a =>
    delete a.dataset.touchReady);
}

function linkTaskRefText(node) {
  const parent = node.parentElement;
  if (!parent || parent.closest(TASK_REF_SKIP)) return;
  if (!node.ownerDocument.__dwTaskRefReview && !parent.closest('.md')) return;
  const parts = taskRefParts(node.nodeValue || '');
  if (!parts.some(part => part.id != null)) return;
  const frag = node.ownerDocument.createDocumentFragment();
  for (const part of parts) {
    if (part.id == null) { frag.appendChild(node.ownerDocument.createTextNode(part.text)); continue; }
    const a = node.ownerDocument.createElement('a');
    a.className = 'taskref'; a.href = '/tasks?t=' + part.id;
    a.dataset.taskId = String(part.id); a.textContent = part.text;
    a.setAttribute('aria-describedby', 'task-ref-preview');
    frag.appendChild(a);
  }
  node.replaceWith(frag);
}

function resolveTaskRefs(root) {
  const doc = root.ownerDocument || root;
  if (!doc.createTreeWalker) return;
  const walker = doc.createTreeWalker(root, 4 /* SHOW_TEXT */);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach(linkTaskRefText);
}

function observeTaskRefs(doc, reviewHtml = false) {
  if (!doc || !doc.body || doc.__dwTaskRefs) return;
  doc.__dwTaskRefs = true;
  doc.__dwTaskRefReview = !!reviewHtml;
  taskRefPanel(doc);
  resolveTaskRefs(doc.body);
  const bindFrame = frame => {
    const load = () => { try { observeTaskRefs(frame.contentDocument, true); } catch (e) {} };
    frame.addEventListener('load', load); load();
  };
  doc.querySelectorAll('iframe').forEach(bindFrame);
  const observer = new doc.defaultView.MutationObserver(records => records.forEach(rec =>
    rec.addedNodes.forEach(node => {
      if (node.nodeType === 3) linkTaskRefText(node);
      else if (node.nodeType === 1) {
        if (node.tagName === 'IFRAME') bindFrame(node);
        resolveTaskRefs(node);
      }
    })));
  observer.observe(doc.body, {childList:true, subtree:true});
  doc.addEventListener('mouseover', e => { const a = e.target.closest && e.target.closest('a.taskref'); if (a) showTaskRef(a); });
  doc.addEventListener('mouseout', e => { const a = e.target.closest && e.target.closest('a.taskref'); if (a && !a.contains(e.relatedTarget)) hideTaskRef(doc); });
  doc.addEventListener('focusin', e => { const a = e.target.closest && e.target.closest('a.taskref'); if (a) showTaskRef(a); });
  doc.addEventListener('focusout', e => { const a = e.target.closest && e.target.closest('a.taskref'); if (a) hideTaskRef(doc); });
  doc.addEventListener('keydown', e => { if (e.key === 'Escape') hideTaskRef(doc); });
  doc.addEventListener('click', e => {
    const a = e.target.closest && e.target.closest('a.taskref');
    if (!a || !(doc.defaultView.matchMedia && doc.defaultView.matchMedia('(pointer:coarse)').matches)) return;
    if (a.dataset.touchReady === '1') return;
    e.preventDefault(); a.dataset.touchReady = '1'; showTaskRef(a);
  });
}

if (document.readyState === 'loading')
  document.addEventListener('DOMContentLoaded', () => observeTaskRefs(document), {once:true});
else
  observeTaskRefs(document);
/* Inline markdown the loop actually writes: **bold**, *em*, `code`. Bold is
   rendered as LUMINANCE — the page already says "more important" with its
   text ramp, and a mono bold would change metrics to say no more. Order is
   load-bearing: the linkifiers inject <a> INSIDE the backticks, so code
   spans convert after them and swallow the link; ** before * so a bold pair
   is never read as two emphases. Link pass order: linkifyReview (review
   docks) → linkifyMd (general [text](target), #522) → linkify (backticks). */
const mdSpans = h => h
  .replace(/`([^`]+)`/g, '<code>$1</code>')
  .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  .replace(/(^|[\s(\[])\*([^*\s][^*]*?)\*(?=$|[\s.,;:)\]])/g, '$1<em>$2</em>');
/* baseDir is the viewed file's directory (or null): relative markdown-link
   targets resolve only against it, and only when the result is linkable. */
const mdInlineAt = baseDir => t =>
  mdSpans(linkify(linkifyMd(esc(t), baseDir)));
const mdInline = t => mdInlineAt(null)(t);
const mdInlineReview = title => t =>
  mdSpans(linkify(linkifyMd(linkifyReview(esc(t), title), null)));
/* filePath (optional): the path being rendered, so relative [text](../x)
   targets can resolve against its directory into the closed linkable set. */
const mdB = (t, filePath) => {
  let base = null;
  if (filePath != null && filePath !== '') {
    const i = String(filePath).lastIndexOf('/');
    base = i >= 0 ? String(filePath).slice(0, i) : '';
  }
  return `<div class="md">${mdRender(t, mdInlineAt(base))}</div>`;
};
const mdBReview = (t, title) =>
  `<div class="md">${mdRender(t, mdInlineReview(title))}</div>`;
/* a follow-up thread and a quiet add-a-note box, carried by every question
   entry in every state. */
/* Authorship is visible wherever the human's words sit beside the loop's
   (#109). A note carries who wrote it, and the page says so QUIETLY: a dim
   uppercase label — the same idiom as every other label here — and the
   human's words a step brighter on the text ramp, because emphasis on this
   page is luminance. No accent: the accent is for live and actionable
   things, and a note is neither. An unattributed note (an unknown tag) gets
   no label at all — a wrong attribution is worse than an absent one. */
const WHO = { human: 'you', loop: 'loop' };
/* WHEN a contribution was written. On a thread that is not decoration: a note
   written before an answer must not read as a reply to it (#128), and position
   says which came first only to a reader who already trusts the order. Absent
   when the tag carried no stamp — never invented, the same rule as the author
   label above. */
const stamp = w => w ? `<span class="qts">${esc(w)}</span>` : '';
const followRow = f => {
  const a = f && f.author, txt = f && f.text != null ? f.text : f;
  return `<div class="follow${a ? ' ' + a : ''}">` +
    (WHO[a] ? `<span class="who">${WHO[a]}</span>` : '') +
    stamp(f && f.when) + `${mdInline(txt)}</div>`;
};
/* A settled thread COLLAPSES (#128; his words: "if we have a thread of notes
   like that, they should be collapsed but also expandable"). `fold` is passed
   only for the segment that precedes a resolution — see `qaThread` — and the
   threshold is two because one note is not a thread: hiding a single line
   behind a click costs more than it saves, and his own reported entry had
   exactly one.

   The notes live in a `.threadin` wrapper rather than directly in the
   disclosure, so the thing that arrives or leaves when it toggles is ONE node
   with its own rect — which is what `cardBody` reveals and what the collapse
   ghosts. */
const QTHREAD_FOLD_AT = 2;
const followThread = (follows, fold) => {
  if (!follows || !follows.length) return '';
  const inner = `<div class="threadin">` + follows.map(followRow).join('') +
                `</div>`;
  if (!fold || follows.length < QTHREAD_FOLD_AT)
    return `<div class="thread">${inner}</div>`;
  const last = follows[follows.length - 1];
  return `<div class="thread"><details class="qthread">` +
    `<summary>${follows.length} earlier notes` +
    (last && last.when
      ? `<span class="qwhen">up to ${esc(last.when)}</span>` : '') +
    `</summary>${inner}</details></div>`;
};
/* ── the sliding selection group ──────────────────────────────────────────
   One indicator that slides to the active option, shared by the composer's
   command kinds and by every question card's answer/note switch (#103).
   Three rules, learned in the composer and true for any user of it:

   - **Land, don't slide, on first paint and on reflow** (`snap`). The
     indicator starts 0-wide at the group's origin, so animating from there
     reads as a glitch rather than a choice — the enter-snap rule. Add
     `.snap` (transition:none), set the geometry, force a reflow, remove it.
   - **Size to the active BUTTON, never to the group.** The row wraps once a
     vocabulary outgrows one line, and a height:100% indicator would span
     every line at once.
   - **The selected label glows, it does not re-metric** (CSS): a text effect
     that changed layout would resize the very target being chased.
   - **Measure in LAYOUT space, never in visual space** (#198). The indicator
     is a sibling of the buttons, so what it needs is where they sit in the
     group — and `getBoundingClientRect` answers a different question: where
     they appear on screen, ancestor transforms included. `openCmd` paints the
     indicator on the same frame it reveals the panel, and the panel reveals
     THROUGH a transform (`translateY(-8px) scale(.97)` -> none over .5s), so
     every rect read there came back 3% small. Measured: the indicator landed
     4.5px left of the button it marks and 1.9px narrow, and stayed there —
     it looked self-correcting only because the next live tick re-renders the
     view, and `setContent` re-paints every group at rest.

     Same family as #170 and #160: a transformed ancestor silently redefines
     what a "position" means for everything measured beneath it. */
function slideIndicator(group, snap) {
  if (!group) return;
  const ind = group.querySelector(':scope > .sgind');
  const btn = group.querySelector(':scope > .sgbtn.on');
  if (!ind || !btn) return;
  const g = group.getBoundingClientRect(), b = btn.getBoundingClientRect();
  if (!b.width) return;                  // not laid out yet; nothing to chase
  // The scale the group is being drawn at RIGHT NOW, read from the one
  // element whose layout width we can also ask for directly. Dividing it out
  // turns the rects back into layout values, and it is exactly 1 — a no-op
  // to the sub-pixel — everywhere no ancestor is mid-transform, which is
  // every question card and the composer once it has settled.
  const s = group.offsetWidth ? g.width / group.offsetWidth : 1;
  if (!s) return;
  if (snap || rmr) ind.classList.add('snap');
  ind.style.width = (b.width / s) + 'px';
  ind.style.height = (b.height / s) + 'px';
  ind.style.transform = 'translate(' + ((b.left - g.left) / s) + 'px,' +
                        ((b.top - g.top) / s) + 'px)';
  if (snap && !rmr) {
    void ind.offsetWidth;                // reflow so the landing is not a slide
    ind.classList.remove('snap');
  }
}
/* every group that exists right now lands its indicator — called after any
   render, and on resize, since a wrapped row moves its buttons */
const paintIndicators = snap =>
  document.querySelectorAll('.sgroup').forEach(g => slideIndicator(g, snap));
/* ── the card's one input (#103) ──────────────────────────────────────────
   The human's words: "use same text input for answer and note. below text
   input, have a button group choose between [ Answer | Add Note ]. on the
   RHS of the text field, integrate a 'send' button that sits flush with the
   text field so they appear to be one thing."

   The mode picks the endpoint. Only modes the entry's state can actually
   accept are offered — /answer appends into the Open section, so a folded
   entry is note-only and the group does not render at all rather than
   offering a choice that would fail. A card that already has an answer
   defaults to note: answering again is an amendment, not the obvious act. */
const QMODES = { answer: 'answer', note: 'add note' };
const qaModesFor = st => st === 'folded' ? ['note'] : ['answer', 'note'];
const qaDefaultMode = st => st === 'open' ? 'answer' : 'note';
const QPLACE = { answer: 'answer…', note: 'add a note…' };
/* #273: accessible name tracks mode + target. Placeholder alone is not a
   name; the dock especially needs which question is being answered. */
const qaFieldLabel = (mode, title) => {
  const act = mode === 'note' ? 'add a note on' : 'answer';
  const t = String(title || '').replace(/\s+/g, ' ').trim();
  const short = t.length > 90 ? t.slice(0, 87) + '…' : t;
  return short ? `${act} ${short}` : (mode === 'note' ? 'add a note' : 'answer');
};
const qaSendLabel = mode => mode === 'note' ? 'send note' : 'send answer';
const qaCompose = (key, st, title) => {
  const modes = qaModesFor(st), mode = qaDefaultMode(st);
  const group = modes.length < 2 ? '' :
    `<div class="sgroup qmodes" role="radiogroup"` +
    ` aria-label="answer or add a note" data-modes="${key}">` +
    `<div class="sgind"></div>` +
    modes.map(m => `<button type="button" role="radio" data-mode="${m}"` +
      ` class="sgbtn qmode${m === mode ? ' on' : ''}"` +
      ` aria-checked="${m === mode ? 'true' : 'false'}">${QMODES[m]}</button>`
    ).join('') + `</div>`;
  return `<div class="qcompose" data-mode="${mode}">` +
    `<div class="qfield">` +
    `<textarea id="qi${key}" placeholder="${QPLACE[mode]}"` +
    ` data-max-rows="6"` +
    ` aria-label="${esc(qaFieldLabel(mode, title))}"></textarea>` +
    `<button type="button" class="qsend"` +
    ` aria-label="${esc(qaSendLabel(mode))}"` +
    ` onclick="submitCard('${key}')">send</button></div>` +
    group + `</div>`;
};
/* THE THREAD, SPLIT AROUND ITS RESOLUTION (#128).
   The answer is lifted out of the sub-bullets so the card can show it as the
   resolution — and the lift used to discard where it sat among the notes, so a
   note written two hours EARLIER rendered underneath it and read as a reply to
   it ("the first thing that showed up was like me replying to me?"). The
   parser now records `answer_at`, and the thread is cut there: the discussion
   that led to the resolution sits above it, an amendment sits below.

   Only the part above collapses. That is the card's own axis — who is the
   entry waiting on — applied one level down: discussion that a resolution has
   already answered is settled, and everything else on a question card is
   still live. So an unanswered question never hides its notes (they are the
   human's own steers), and a note he adds now lands in the segment below the
   answer, which is never folded away under him. */
const qaThread = q => {
  const f = (q && q.follows) || [];
  // No resolution ⇒ NOTHING is settled. Defaulting the cut to the end of the
  // list instead was the obvious-looking arithmetic and it swept every note of
  // every open question into the folding half — the guard caught it, which is
  // what a rule written as a rule is for.
  const at = (q && q.answer && q.answer_at != null) ? q.answer_at : 0;
  return [f.slice(0, at), f.slice(at)];
};
/* THE question component (#105). Every question on every surface —
   dashboard, /questions, the review dock, and the answer-submit morph —
   renders through this one card, so a change to how a question looks is one
   edit rather than a hunt.

   Contract: `qaCard(q, key, surface='list')`. The key ADDRESSES the entry in live `data`:
   'o'+index into `questions_open`, 'a'+index into `answered_entries`. It is
   never a title round-tripped through the DOM, so a stale render cannot
   write to the wrong entry. The state is DERIVED from the key and the entry,
   never passed in, so no caller can render an entry in a state its own data
   contradicts:
     open     — needs the human; shows an answer box
     awaiting — answered from the page, the loop hasn't folded it yet; the
                answer on a quiet accent rail with a ✓, no box, so it never
                reads as still-open
     folded   — key is 'a…'; the loop has folded it into `## Answered`
   `surface` says where the card is being read. It is explicit rather than a
   read of the router's global `view`, so the card, its controls and the roll
   restorer cannot disagree about the surface the user can actually see.
   `qaInner` is split out so the submit morph can restate a live card in its
   new state in place instead of assembling look-alike markup. */
const qaState = (q, key) =>
  key[0] === 'a' ? 'folded' : (q.answer ? 'awaiting' : 'open');
/* A reading surface shows the whole question and therefore has no meaningful
   rolled state. Focus and the review dock are callers of this ONE predicate;
   list/dashboard cards are not. Persisted roll truth stays separate — the
   router suppresses its rendering here without rewriting that truth. */
const isQuestionReadingSurface = surface =>
  surface === 'focus' || surface === 'dock';
/* The one structural difference between the states (#111). A folded entry is
   waiting on NOBODY, so it collapses — through the page's existing `expand`
   idiom, `<details>`/`<summary>`, marker and all. Its title line BECOMES the
   summary rather than sitting beside one, so `.qt` still names the question
   line in every state and every rule written against it keeps applying.
   Collapsed it still says which question and when it was answered, because a
   settled entry that cannot be found again has simply been hidden. */
/* #385: the date already lives in the title (`YYYY-MM-DD — …`, optional
   `P1 · ` prefix). Humanized age sits next to that date via the same
   `data-ct` + `paintAgePair` path commits use — one formatter, not a second.
   No date in the title → plain escape, same as before.
   #392a: a DATE-ONLY title is day-precision, so the span carries
   `data-day="1"` and ages() routes it to `paintDayAge` — one figure, not
   two. The flag is the precision of the input, read by the dispatch.
   #392b: an optional local ` HH:MM` after the date is a TIMED title. Its
   `ct` is that clock time (not midnight), and there is no `data-day`, so
   ages() uses paintAgePair — two figures, exact to the minute. Unknown
   time stays honestly imprecise (#392a); a known time must not fabricate
   from midnight. Same ` HH:MM` shape note tags already carry. */
const qtHtml = title => {
  // doubled backslashes: this lives in a Python string; the emitted JS
  // still sees a single backslash before each digit class.
  const m = /^(P[123] · )?(\d{4}-\d{2}-\d{2})(?: (\d{2}:\d{2}))?( — )([\s\S]*)$/.exec(title || '');
  if (!m) return esc(title);
  const [, prio, date, time, sep, rest] = m;
  const [Y, Mo, D] = date.split('-').map(Number);
  let ct, dayAttr = '';
  if (time) {
    const [h, mi] = time.split(':').map(Number);
    ct = Math.floor(new Date(Y, Mo - 1, D, h, mi).getTime() / 1000);
  } else {
    ct = Math.floor(new Date(Y, Mo - 1, D).getTime() / 1000);
    dayAttr = ' data-day="1"';
  }
  const when = esc(date) + (time ? esc(' ' + time) : '');
  /* #456: chrome's ` · ` between date and age so the eye finds where the
     date ends — bare adjacency made `2026-07-28 01d ago` one continuous
     digit run. Same glyph/spacing as every other chrome separator.
     #473: an optional "updated X ago" rides the same separator + ages()
     sweep (data-ut). ages() writes pure text — no transition on the
     second-by-second digit flip (the ages() contract). The NODE's first
     appearance is an arrival (revealQuestionUpdates → .dreamin). */
  /* #474: the separator is a NODE, not bare text, and that is load-bearing
     rather than tidy. Everything in this headline that is not the question's
     title has to be removable as a node, because two guards ask "is this
     still the question I docked?" of the headline minus its chrome — see
     dockHeadline in dev/capture/dom.mjs. #456 added this ` · ` as bare text
     between the date and the age span, so stripping the age node left the
     middot behind and the raw title stopped being a substring of the result.
     Both dock guards went red on a page that was behaving correctly, which
     is exactly the failure dom.mjs's own comment predicted. It is `.rsep`
     because #473's separator two functions down already is — one idiom, and
     the two middots in one headline now match instead of one being dimmer
     than the other. */
  return `${esc(prio || '')}${when}<span class="rsep"> · </span>` +
    `<span class="age qage" data-ct="${ct}"${dayAttr}></span>` +
    `${esc(sep)}${esc(rest)}`;
};
/* #473 — optional secondary after the created age. Emitted only when the
   server stamped updated_at (a real content change after first sight).
   ages() decides whether the figure is honest enough to show (#463 lesson:
   suppress when ageStr(updated) === ageStr(created)). */
const qUpdatedHtml = q => {
  const u = q && q.updated_at;
  if (u == null || !(u > 0)) return '';
  return `<span class="rsep"> · </span>` +
    `<span class="age qup" data-ut="${u}" data-q-upd="${esc(q.title || '')}"></span>`;
};
/* #452 — the way IN to the focused page, on every card in every state (a
   folded entry can be focused too: a settled question stays findable). A
   REAL LINK, the #252 argument three ways: the href makes it deep-linkable
   and copyable, keyboard operation is native, and the click rides the
   router's existing dissolve because isInternal already claims /question —
   a button would re-implement all three. The key is the title identity the
   card itself carries as data-qid, so the link and the card cannot
   disagree about which question they name. It is headline CHROME, so it is
   a node with a class, and that class is listed in dockHeadline (#474's
   rule). Suppressed when the card's explicit surface is focus — the page IS
   the focus — so markup never guesses its surface from router-global state. */
const qfocusLink = (title, surface) =>
  surface === 'focus' ? '' :
  ` <a class="qfocus" href="/question?qid=${encodeURIComponent(title)}"` +
  ` title="focus this question — open it on its own page"` +
  ` aria-label="focus this question on its own page">focus</a>`;
/* #454 — the way to roll an OPEN question up to the top of its scroll:
   the card clamps to a 5-6 line card rather than vanishing behind a
   title, because a title alone does not say whether an entry still needs
   him and the rolled top of the body does. A REAL BUTTON, the same
   argument the focus link makes three ways: keyboard operation is native,
   aria-expanded says the disclosure state to AT, and it rides the card's
   own arrival rather than appearing. Open state ONLY — the styleguide's
   axis already answers for the other two: awaiting still needs the loop
   (it does not collapse), and folded IS the collapse (#111). Emitted
   offered only when the card's explicit surface says roll has meaning. The
   same predicate also suppresses persisted roll rendering after a route or
   tick, so a hidden control and a rolled card cannot diverge again. */
const qrollBtn = surface =>
  isQuestionReadingSurface(surface) ? '' :
  ` <button type="button" class="qroll" aria-expanded="true"` +
  ` title="roll this question up to its first lines"` +
  ` aria-label="roll this question up to its first lines">roll up</button>`;
const qaInner = (q, key, surface='list') => {
  const st = qaState(q, key);
  const body = q.body && q.body.trim() ? mdBReview(q.body.trim(), q.title) : '';
  const [settled, since] = qaThread(q);
  /* An answer is his words as much as a note is, so it says so in the same
     vocabulary (#109, #128 part b): of two things he wrote, it must not be
     that only one is attributed. The author comes from the tag, so an answer
     tag nobody recognises gets no label rather than a guessed one.
     #446: a second answer used to overwrite the first at parse time; the
     parser now retains every one in `answers` (file order). Each gets its own
     attributed `.anstext` block here, so none of his words vanish on the
     rail either. With one answer the DOM is byte-identical to before, so the
     submit-morph's `flipDock` on the first `.anstext` and the wisp guard are
     unchanged; the first answer stays the resolution anchor the thread is
     cut around. */
  const ansBlocks = (st === 'awaiting')
    ? (q.answers && q.answers.length
        ? q.answers
        : (q.answer != null
            ? [{text: q.answer, when: q.answer_when, by: q.answer_by}]
            : []))
    : [];
  const answer = ansBlocks.length
    ? `<div class="anstag">answered · awaiting fold</div>` +
      ansBlocks.map(a => `<div class="anstext">` +
        (WHO[a.by] ? `<span class="who">${WHO[a.by]}</span>` : '') +
        stamp(a.when) + `${mdInline(a.text)}</div>`).join('')
    : '';
  /* WHAT THE QUESTION SAYS IS WRAPPED; THE BOX HE ANSWERS IT WITH IS NOT
     (#326). `.qbody` is the review dock's scrollport, so it holds everything
     that should scroll — the title included, which is what #305 designed and
     why its head fade is described as landing under `answering` rather than
     under the title. A pinned title would also cost reading height without a
     bound: at the 32ch floor a long one can run six lines and never scroll
     away. On every route but the dock the wrapper generates no box at all
     (`display:contents`), so this is one structure rather than two — which is
     what lets `qacard.mjs` keep comparing the dock's card with /questions'
     card shape for shape, and what lets the submit morph restate a dock card
     through this same function without rebuilding the dock's layout.

     A FOLDED entry keeps its title OUT of the wrapper, and has no choice: the
     title IS the `<summary>`, which must be the disclosure's first child. The
     wrapper's membership therefore differs by state — which nothing downstream
     can see, because everything that reads the card's own children looks
     through the wrapper (`cardBody`) and no dock card is ever folded. */
  const foot = followThread(settled, true) + answer + followThread(since, false);
  const compose = qaCompose(key, st, q.title);
  /* #473: updated-ago sits on the title line beside the created age, so it
     is part of the headline chrome rather than a second fact buried in the
     body. Folded entries carry it in the summary for the same reason the
     created age is there — a settled entry that cannot be found again has
     simply been hidden. */
  const up = qUpdatedHtml(q);
  const focus = qfocusLink(q.title, surface);
  const roll = st === 'open' ? qrollBtn(surface) : '';
  if (st === 'folded')
    return `<details class="qfold"><summary class="qt">${qtHtml(q.title)}${up}` +
      (q.when ? `<span class="qwhen">answered ${esc(q.when)}</span>` : '') +
      `${focus}</summary><div class="qbody">${body}${foot}</div>${compose}</details>`;
  return `<div class="qbody"><div class="qt">${qtHtml(q.title)}${up}${roll}${focus}</div>` +
         `${body}${foot}</div>${compose}`;
};
/* Two identities, deliberately. `data-qkey` ADDRESSES the entry in live data
   and is positional, so it is what writes use. `data-qid` is the question
   ITSELF, and it survives the entry moving between sections — which its key
   cannot, since answering re-indexes it from questions_open into
   answered_entries. The regroup animation keys off qid: it is the same
   question, so it travels rather than being re-set (#77). URI-encoded
   because a title may contain quotes and this is an attribute. */
const qaCard = (q, key, surface='list') =>
  `<div class="qa ${qaState(q, key)}" data-qkey="${key}"` +
  ` data-qid="${encodeURIComponent(q.title)}" data-qsurface="${surface}">` +
  `${qaInner(q, key, surface)}</div>`;
/* Resolve the logical question a LIVE CARD names, never merely the position it
   occupied when rendered (#266). A review route does not rebuild its dock on
   the data tick, so its `o<n>` can become stale while questions_open re-sorts.
   `data-qid` is the title identity the card already uses to survive regrouping;
   writes resolve that identity against fresh data. The positional fallback is
   only for callers with no live card, and fails closed when neither matches. */
const qaEntry = (key, card) => {
  if (!data || !key) return null;
  const list = key[0] === 'a' ? data.answered_entries : data.questions_open;
  const qid = card && card.dataset.qid;
  if (qid) {
    let title = null;
    try { title = decodeURIComponent(qid); } catch (e) { return null; }
    return (list || []).find(entry => entry.title === title) || null;
  }
  return (list || [])[+key.slice(1)] || null;
};
/* the page he was on when he sent it (#126). The query string is kept because
   WHICH artifact he was reading is usually the point. Every write path sends
   it; the server puts it in brackets in the events log, where it reads as a
   hint and not as an instruction. */
const fromPath = () => location.pathname + location.search;
/* Both POSTs RETURN their response, and both callers check it (#136). They
   did not, and the consequence was the worst shape available: a write that
   failed still ran the submit morph, so the card restated itself as answered,
   his text was cleared, and two seconds later the live tick quietly put the
   question back with no explanation anywhere. A file the reader cannot see is
   a file `/answer` cannot write to, so the read-side fault and the write-side
   "no match" are the same failure and want the same surfacing. */
/* ── every submission, as the CLIENT saw it (#175) ────────────────────────
   #199 gave the SERVER a verbatim record of everything it received. This is
   the other witness, and it exists for the case that one cannot cover: a
   submission the server never accepted, or never even heard. A 409 from
   `append_answer` (#136), a rejection he clicked past (#162), a POST that
   never left because the server was restarting — in every one of those, the
   client is the only party that knows what he tried to do.

   SO THE RECOVERY-CRITICAL FIELD IS THE OUTCOME, NOT THE TEXT. The text he
   can usually still see; what is unrecoverable an hour later is whether the
   thing he typed actually landed. A record is written BEFORE the request, as
   `pending`, and the outcome is attached when the response comes back — so a
   tab that dies mid-POST leaves a record saying exactly that, which is the
   true state and not a guess.

   PARTITIONED BY A DATABASE PER PROJECT, not by a field inside one database.
   A `project` column needs every reader to remember to filter by it, and a
   reader that forgets returns another loop's submissions while looking
   perfectly correct — the silent shape this page keeps closing. A separate
   database cannot leak by omission.

   NOTHING HERE MAY DELAY OR BREAK A SEND. Every failure resolves to null, and
   the write is raced against a short timeout: a wedged IndexedDB (a blocked
   upgrade, a storage-disabled origin) must cost him a few milliseconds, never
   a command. A missing record is a bad outcome; a command he could not send
   because of the logger is a worse one.

   IT MUST BE READABLE OR IT IS THEATRE. `#165` is the surface; until then, and
   for anyone debugging afterwards, `window.__dwSubmissions()` resolves to
   every record for the current project. */
const SUBS_STORE = 'subs';
const subsDbName = () => {
  const t = (typeof data !== 'undefined' && data && data.target) || '';
  return t ? 'dw-submissions:' + t : '';
};
/* the ONE IndexedDB helper, generalized rather than duplicated (#454):
   the open and the transaction are the wedged-store discipline — every
   failure resolves null, nothing throws at a caller — and each database
   says only what its upgrade creates. A second copy of this for a second
   store is how one of them loses the raced-timeout handling. */
function idbOpen(name, upgrade) {
  return new Promise(res => {
    if (!name || typeof indexedDB === 'undefined' || !indexedDB) return res(null);
    let rq;
    try { rq = indexedDB.open(name, 1); } catch (e) { return res(null); }
    rq.onupgradeneeded = () => upgrade(rq.result);
    rq.onsuccess = () => res(rq.result);
    rq.onerror = rq.onblocked = () => res(null);
  });
}
/* one transaction, always closed, never throwing at the caller */
function idbTx(openFn, store, mode, fn) {
  return openFn().then(db => new Promise(res => {
    if (!db) return res(null);
    let out = null;
    const done = v => { try { db.close(); } catch (e) {} res(v); };
    try {
      const tx = db.transaction(store, mode);
      const rq = fn(tx.objectStore(store));
      if (rq) rq.onsuccess = () => { out = rq.result; };
      tx.oncomplete = () => done(out);
      tx.onerror = tx.onabort = () => done(null);
    } catch (e) { done(null); }
  })).catch(() => null);
}
function subsOpen() {
  return idbOpen(subsDbName(), db => {
    if (!db.objectStoreNames.contains(SUBS_STORE))
      db.createObjectStore(SUBS_STORE, { keyPath:'id', autoIncrement:true });
  });
}
function subsTx(mode, fn) { return idbTx(subsOpen, SUBS_STORE, mode, fn); }
/* ── persisted UI state (#454) ──────────────────────────────────────────
   "Persisted to IndexedDB and kept in sync like other ui state." A SEPARATE
   database from the submissions log, for that log's own reason (a separate
   database cannot leak by omission): the subs store is an append-only
   record of what he SENT; this one is keyed state about how the page
   LOOKS — today the rolled questions. Same wedged-store discipline through
   the shared helper, and the write is raced the same way: a roll is a
   gesture, and a gesture never waits on storage.
   Cross-tab sync is no new mechanism either: the standing 'storage'-event
   idiom (#290's pending mode) carries the ping; IndexedDB carries the
   truth a reload reads back. */
const UI_STORE = 'ui';
const uiDbName = () => {
  const t = (typeof data !== 'undefined' && data && data.target) || '';
  return t ? 'dw-ui:' + t : '';
};
function uiOpen() {
  return idbOpen(uiDbName(), db => {
    if (!db.objectStoreNames.contains(UI_STORE))
      db.createObjectStore(UI_STORE, { keyPath:'k' });
  });
}
const uiTx = (mode, fn) => idbTx(uiOpen, UI_STORE, mode, fn);
const UI_WAIT_MS = 250;
const uiPut = (k, v) => Promise.race([
  uiTx('readwrite', st => st.put({ k, v, at: Date.now() })),
  new Promise(r => setTimeout(() => r(null), UI_WAIT_MS)),
]);
const uiAll = () => uiTx('readonly', st => st.getAll());
/* what KIND of act each endpoint is, in his terms rather than the protocol's.
   An unknown path still records, with the body kept whole — a new POST route
   is logged the day it is added, without anyone remembering this table. */
const SUB_ACT = {
  '/ask':     b => ({ kind:'ask',    title:b.question, text:b.question }),
  '/answer':  b => ({ kind:'answer', title:b.question, text:b.answer }),
  '/comment': b => ({ kind:'note',   title:b.question, text:b.comment }),
  '/command': b => ({ kind:b.kind,   title:null,       text:b.text }),
};
const subFields = (url, b) => (SUB_ACT[url] ||
  (x => ({ kind:url, title:null, text:JSON.stringify(x) })))(b || {});
const SUBS_WAIT_MS = 250;
const subsRecord = (url, body) => Promise.race([
  subsTx('readwrite', st => st.add(Object.assign(
    { at: Date.now(), path: url, from: (body || {}).from || null,
      outcome: 'pending', status: 0 }, subFields(url, body)))),
  new Promise(r => setTimeout(() => r(null), SUBS_WAIT_MS)),
]);
function subsOutcome(id, outcome, status) {
  if (id == null) return;
  subsTx('readwrite', st => {
    const g = st.get(id);
    g.onsuccess = () => {
      const r = g.result;
      // never rewritten except to attach the outcome it was waiting for, and
      // never deleted: an entry that stays `pending` is a true statement about
      // a tab that died mid-send, not a gap to be tidied away
      if (r) { r.outcome = outcome; r.status = status; st.put(r); }
    };
    return null;
  });
}
const subsAll = () => subsTx('readonly', st => st.getAll());
window.__dwSubmissions = subsAll;
/* THE ONE SEAM every submission goes through, which is what makes the record
   complete rather than well-intentioned — the same reason #199 persists from
   `do_POST` rather than from four handlers. */
/* The one verdict on a write's response, in one place (#263 E5b). Every POST
   path whose response decides whether to clear a box, clear a draft, or show a
   confirmation asks this — never `res.ok` alone. E5 made body-validation
   failures a 202 with a durable `rejected` transition and a bounded reason,
   and 202 makes `res.ok` true, so `res.ok` confirms a write that did not
   happen — and on /answer and /comment that confirmation clears the draft,
   which was the only remaining copy of what he typed. A Response body can be
   read ONCE, so this is the single reader: `postJSON` calls it and stashes the
   verdict on the Response it returns; the three raw-fetch sites (/tint,
   /run-mode, the popped-out command) each own their own Response and call it
   directly. `landed` is the whole rule — ok AND not rejected — and it is the
   one thing every write surface checks. */
async function writeVerdict(res) {
  if (!res) return { landed: false, rejected: false, reason: null, status: 0 };
  let j = null;
  try { j = await res.json(); } catch (e) { j = null; }
  const rejected = !!(j && j.rejected === true);
  return { landed: res.ok && !rejected, rejected,
           reason: (j && j.reason) || null,
           // `detail` narrows a closed-set reason for copy only (#462): several
           // distinct refusals share one contract reason, and a route that can
           // say which one must be able to. Never gated on — `landed` is.
           detail: (j && j.detail) || null, status: res.status };
}
/* #274: attemptId is the per-attempt idempotency key (X-Client-Action-Id).
   The caller mints it from its draft's attempt store so a retry or
   double-click of one attempt sends the SAME key and the journal dedupes the
   second; absent (CLI/curl, or a path not yet covered), the server mints a
   per-request UUID and the request is a distinct action. */
const postJSON = async (url, body, attemptId) => {
  const id = await subsRecord(url, body);
  let res = null;
  const headers = {'Content-Type':'application/json'};
  if (attemptId) headers['X-Client-Action-Id'] = attemptId;
  try { res = await fetch(url, { method:'POST',
    headers,
    body: JSON.stringify(body) }); } catch (e) { res = null; }
  const v = await writeVerdict(res);
  if (res) res._dwv = v;   // single body read; callers ask the verdict, not res.ok
  // the outcome #175's ledger records is the VERDICT's, not res.ok's: a
  // rejected 202 used to record 'ok' — the exact lie this fixes — so a tab
  // that dies mid-send no longer lies that a rejected body landed.
  subsOutcome(id, !res ? 'unreachable' : (v.landed ? 'ok' : 'rejected'),
              v.status);
  return res;
};
const postAnswer = (title, text, attemptId) =>
  postJSON('/answer', { question: title, answer: text, from: fromPath() },
           attemptId);
const postAsk = (text, attemptId) =>
  postJSON('/ask', { question: text, from: fromPath() }, attemptId);
const postComment = (title, note, section, attemptId) =>
  postJSON('/comment',
           { question: title, comment: note, section, from: fromPath() },
           attemptId);
/* Why a send did not land, in his terms. The status alone ("rejected (409)")
   names the protocol and not the problem. */
const QSEND_WHY = {
  404: 'there is no .dreamwork/questions.md to write to',
  409: 'this entry is not in .dreamwork/questions.md any more — it may have ' +
       'been folded, renamed, or the file may have stopped being readable',
  0:   'the page could not reach the server',
};
/* Why a body was REJECTED (E5: 202 + a durable `rejected` transition), in his
   terms. The server's reason code names the protocol; this names the problem.
   Closed set, paired with REJECTION_REASONS in user_events/sqlite.py — a code
   outside the set falls through to the status line, never an unrecognised
   string. Voice is watch-design.md's: a state, an em dash, what he can do. */
/* #462 — per-route narrowing of a closed-set reason, for copy only. In his
   voice: what happened and what it means for him, never a code. */
const DEPLOY_WHY = {
  in_flight: 'this page will pick up the new one when it lands',
  not_local: 'the update only runs from the machine serving the page',
};
const REJECT_WHY = {
  malformed_json: 'the request body could not be read',
  schema_invalid: 'a required field was missing or the wrong shape',
  domain_invalid: 'the value was not one the server accepts',
};
function qaFail(card, v) {
  const comp = card && card.querySelector('.qcompose');
  if (!comp) return;
  let m = comp.querySelector('.qerr');
  if (!m) { m = document.createElement('div'); m.className = 'qerr';
            comp.appendChild(m); }
  // his words stay in the box: the send failed, so the text is the only copy.
  // a rejected body (202 + rejected:true) is the same failure as a refused one
  // — the box does not clear and the morph does not run — so it says so in the
  // same idiom: a reason in his terms, then the consequence.
  const why = (v && v.rejected && v.reason && REJECT_WHY[v.reason]) ||
              (v && QSEND_WHY[v && v.status]);
  const head = (v && v.rejected) ? 'not written (rejected)'
                                 : `not written (${(v && v.status) || 0})`;
  m.textContent = `${head} — ${why || 'the server refused it'}` +
    '. what you typed is still here.';
}
