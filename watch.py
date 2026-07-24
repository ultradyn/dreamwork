#!/usr/bin/env python3
"""watch.py — read-only localhost dashboard for a running dreamloop.

Plan: .dreamwork/docs/plans/watch-py.md (human-authorized 2026-07-25).
Stdlib only. Binds 127.0.0.1 exclusively. Read-only with ONE deliberate
exception (human-authorized 2026-07-25): POST /answer appends a marked
answer block under an open question in questions.md — the loop folds it
on its next tick. No other write paths exist.
"""

import argparse
import http.server
import json
import os
import random
import subprocess
import threading
import time
import webbrowser

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>dreamwork watch</title>
<style>
  body { background:#0b0f19; color:#d1d5db; margin:0; padding:2.5rem 1rem;
         font-family:ui-monospace,'JetBrains Mono',monospace; font-size:.8rem; }
  .wrap { max-width:72ch; margin:0 auto; }
  header { color:#f3f4f6; font-size:1rem; margin-bottom:.25rem; }
  #meta { color:#6b7280; margin-bottom:2rem; }
  #meta .q { color:#a5b4fc; }
  .label { color:#6b7280; text-transform:uppercase; letter-spacing:.08em;
           font-size:.7rem; margin:1.6rem 0 .5rem; }
  details { margin:.25rem 0; }
  summary { cursor:pointer; color:#e5e7eb; list-style:none; }
  summary::before { content:"+ "; color:#6b7280; }
  details[open] > summary::before { content:"- "; }
  .age { color:#6b7280; margin-left:.5rem; }
  pre { white-space:pre-wrap; color:#9ca3af; margin:.4rem 0 .8rem 1ch;
        border-left:1px solid #1f2937; padding-left:1ch; }
  .git div { color:#6b7280; }
  .git .maint { color:#a5b4fc; }
  .dim { color:#4b5563; }
  .qa { margin:.6rem 0 1rem; }
  .qa .qt { color:#e5e7eb; }
  .qa textarea { width:100%; background:#111827; color:#d1d5db;
    border:1px solid #1f2937; border-radius:4px; font:inherit;
    padding:.4rem; margin:.3rem 0; min-height:3rem; box-sizing:border-box; }
  .qa button { background:#1e293b; color:#a5b4fc; border:1px solid #334155;
    border-radius:4px; font:inherit; padding:.25rem .8rem; cursor:pointer; }
</style></head><body><div class="wrap">
<header>dreamwork watch</header>
<div id="meta">loading…</div>
<div id="sections"></div>
<script>
const esc = t => { const d = document.createElement('div');
                   d.textContent = t ?? ''; return d.innerHTML; };
const ageStr = mt => {
  let s = Math.max(0, Date.now()/1000 - mt);
  for (const [u, div] of [["d",86400],["h",3600],["m",60]])
    if (s >= div) return `${Math.floor(s/div)}${u}`;
  return `${Math.floor(s)}s`;
};
function dreamBlock(d) {
  return `<details><summary>${esc(d.name)}<span class="age" data-mt="${d.mtime}"></span></summary><pre>${esc(d.content)}</pre></details>`;
}
let data = null, fetchedAt = 0;
function render(d) {
  const q = d.open_questions > 0
    ? ` · <span class="q">${d.open_questions} open question${d.open_questions>1?'s':''}</span>`
    : '';
  document.getElementById('meta').innerHTML =
    `${esc(d.target)} · ${esc(d.files['skill-version'])} · <span id="upd"></span>${q}`;
  let h = '';
  h += `<div class="label">dreams (${d.dreams.length})</div>` +
       (d.dreams.map(dreamBlock).join('') || '<div class="dim">none active</div>') +
       (d.dreams_archive.length
         ? `<details><summary class="dim">archive (${d.dreams_archive.length})</summary>` +
           d.dreams_archive.map(dreamBlock).join('') + `</details>` : '');
  if (d.questions_open.length) {
    h += `<div class="label">answer questions</div>` +
      d.questions_open.map((q, i) =>
        `<div class="qa"><div class="qt">${esc(q.title)}</div>` +
        `<pre>${esc(q.body.trim())}</pre>` +
        `<textarea id="qa${i}" placeholder="answer…"></textarea>` +
        `<button onclick="sendAnswer(${i})">answer</button></div>`
      ).join('');
  }
  h += `<div class="label">files</div>` +
       ['DREAMWORK.md','questions.md','lessons.md'].map(n =>
         `<details><summary>${n}</summary><pre>${esc(d.files[n])}</pre></details>`
       ).join('');
  if (d.status)
    h += `<div class="label">status</div><pre>${esc(JSON.stringify(d.status, null, 2))}</pre>`;
  h += `<div class="label">commits</div><div class="git">` +
       d.git.map(l => `<div class="${l.includes('dreamwork(maintain:') ? 'maint' : ''}">${esc(l)}</div>`).join('') +
       `</div>`;
  document.getElementById('sections').innerHTML = h;
  ages();
}
function ages() {
  document.querySelectorAll('.age[data-mt]').forEach(el =>
    el.textContent = ageStr(parseFloat(el.dataset.mt)) + ' old');
  const upd = document.getElementById('upd');
  if (upd) upd.textContent =
    `updated ${ageStr(fetchedAt/1000)} ago`;
}
async function sendAnswer(i) {
  const el = document.getElementById('qa' + i);
  if (!el || !el.value.trim()) return;
  await fetch('/answer', { method:'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ question: data.questions_open[i].title,
                           answer: el.value.trim() }) });
}
let last = null;
async function tick() {
  try {
    const m = await (await fetch('/mtime')).text();
    if (m !== last) { last = m; fetchedAt = Date.now();
      data = await (await fetch('/data.json')).json(); render(data); }
  } catch (e) { /* server restarting; retry */ }
  setTimeout(tick, 2000);
}
setInterval(ages, 1000);
tick();
</script></div></body></html>
"""


def age_str(seconds):
    for unit, div in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= div:
            return f"{int(seconds // div)}{unit}"
    return f"{int(seconds)}s"


def read_text(path, limit=200_000):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except OSError:
        return None


def list_dreams(dirpath, now):
    out = []
    if not os.path.isdir(dirpath):
        return out
    for name in sorted(os.listdir(dirpath), reverse=True):
        p = os.path.join(dirpath, name)
        if name.endswith(".md") and os.path.isfile(p):
            out.append({"name": name,
                        "mtime": os.path.getmtime(p),
                        "age": age_str(now - os.path.getmtime(p)),
                        "content": read_text(p)})
    return out


def git_tail(target, n=15):
    try:
        res = subprocess.run(
            ["git", "-C", target, "log", "-n", str(n), "--pretty=%h %s"],
            capture_output=True, text=True, timeout=5)
        return res.stdout.splitlines() if res.returncode == 0 else []
    except (OSError, subprocess.TimeoutExpired):
        return []


def parse_open_questions(text):
    """[{title, body}] for each '- **Title**' entry in the Open section."""
    items = []
    if not text:
        return items
    in_open = False
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            in_open = line.strip() == "## Open"
            current = None
        elif in_open and line.startswith("- **"):
            title, _, rest = line[4:].partition("**")
            current = {"title": title,
                       "body": rest.strip() + "\n" if rest.strip() else ""}
            items.append(current)
        elif in_open and current is not None:
            current["body"] += line + "\n"
    return items


def append_answer(text, title, answer, stamp):
    """Insert an answer bullet at the end of the titled Open entry.

    Returns (new_text, matched). Pure — testable without a filesystem.
    """
    block = f"  - **Answer (via watch, {stamp}):** {answer}"
    lines = text.splitlines()
    out = []
    in_open = False
    in_target = False
    matched = False

    def close_target():
        nonlocal in_target
        if in_target:
            out.append(block)
            in_target = False

    for line in lines:
        if line.startswith("## "):
            close_target()
            in_open = line.strip() == "## Open"
        elif in_open and line.startswith("- **"):
            close_target()
            if line[4:].split("**", 1)[0] == title:
                in_target = True
                matched = True
        out.append(line)
    close_target()
    return "\n".join(out) + "\n", matched


def open_question_count(questions_text):
    if not questions_text:
        return 0
    in_open = False
    count = 0
    for line in questions_text.splitlines():
        if line.startswith("## "):
            in_open = line.strip() == "## Open"
        elif in_open and line.startswith("- **"):
            count += 1
    return count


def collect(target):
    now = time.time()
    dw = os.path.join(target, ".dreamwork")
    questions = read_text(os.path.join(dw, "questions.md"))
    return {
        "target": os.path.abspath(target),
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dreams": list_dreams(os.path.join(dw, "dreams"), now),
        "dreams_archive": list_dreams(
            os.path.join(dw, "dreams", "archive"), now),
        "files": {
            "DREAMWORK.md": read_text(os.path.join(target, "DREAMWORK.md")),
            "questions.md": questions,
            "lessons.md": read_text(os.path.join(dw, "lessons.md")),
            "skill-version": (read_text(
                os.path.join(dw, "skill-version")) or "").strip(),
        },
        "open_questions": open_question_count(questions),
        "questions_open": parse_open_questions(questions),
        "status": json.loads(read_text(os.path.join(dw, "status.json"))
                             or "null"),
        "git": git_tail(target),
    }


def watched_mtime(target):
    latest = 0.0
    paths = [os.path.join(target, "DREAMWORK.md"),
             os.path.join(target, ".git", "logs", "HEAD")]
    dw = os.path.join(target, ".dreamwork")
    for root, _dirs, files in os.walk(dw):
        paths.extend(os.path.join(root, f) for f in files)
    for p in paths:
        try:
            latest = max(latest, os.path.getmtime(p))
        except OSError:
            pass
    return latest


def persistent_port(target):
    marker = os.path.join(target, ".dreamwork", "watch-port")
    saved = read_text(marker)
    if saved and saved.strip().isdigit():
        return int(saved.strip())
    port = random.randrange(3000, 63000)
    try:
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w") as f:
            f.write(f"{port}\n")
    except OSError:
        pass
    return port


ANSWER_LOCK = threading.Lock()


def make_handler(target):
    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, body, ctype):
            data = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/":
                self._send(PAGE, "text/html")
            elif self.path == "/data.json":
                self._send(json.dumps(collect(target)), "application/json")
            elif self.path == "/mtime":
                self._send(str(watched_mtime(target)), "text/plain")
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path != "/answer":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 20_000:
                self.send_error(413)
                return
            try:
                req = json.loads(self.rfile.read(length))
                title = str(req["question"]).strip()
                answer = str(req["answer"]).strip()
            except (ValueError, KeyError):
                self.send_error(400)
                return
            if not title or not answer:
                self.send_error(400)
                return
            qpath = os.path.join(target, ".dreamwork", "questions.md")
            stamp = time.strftime("%Y-%m-%d %H:%M")
            with ANSWER_LOCK:
                text = read_text(qpath)
                if text is None:
                    self.send_error(404)
                    return
                new_text, matched = append_answer(text, title, answer, stamp)
                if not matched:
                    self.send_error(409)
                    return
                with open(qpath, "w", encoding="utf-8") as f:
                    f.write(new_text)
            self._send(json.dumps({"ok": True}), "application/json")

        def log_message(self, *_args):
            pass

    return Handler


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--target", default=".", metavar="DIR")
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--open", action="store_true",
                   help="open the dashboard in a browser")
    args = p.parse_args(argv)
    port = args.port or persistent_port(args.target)
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", port), make_handler(args.target))
    url = f"http://127.0.0.1:{port}/"
    print(f"dreamwork watch: {url} (target {os.path.abspath(args.target)})")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
