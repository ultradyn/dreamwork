#!/usr/bin/env python3
"""watch.py — read-only localhost dashboard for a running dreamloop.

Plan: .dreamwork/docs/plans/watch-py.md (human-authorized 2026-07-25).
Stdlib only. Binds 127.0.0.1 exclusively; no write endpoints exist.
Stage 1: server core (/ , /data.json , /mtime), port persistence, --open.
"""

import argparse
import http.server
import json
import os
import random
import subprocess
import time
import webbrowser

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>dreamwork watch</title>
<style>
  body { background:#0b0f19; color:#f3f4f6; margin:0; padding:2rem;
         font-family:'JetBrains Mono',ui-monospace,monospace; }
  .wrap { max-width:900px; margin:0 auto; }
  h1 { font-size:1.3rem; background:linear-gradient(135deg,#6366f1,#a855f7);
       -webkit-background-clip:text; background-clip:text; color:transparent; }
  .meta { color:#9ca3af; font-size:.8rem; margin-bottom:1.5rem; }
  .badge { display:inline-block; padding:.1rem .55rem; border-radius:999px;
           font-size:.75rem; background:#1e293b; color:#a5b4fc;
           border:1px solid #334155; margin-left:.4rem; }
  .badge.warn { background:#3b1e1e; color:#fca5a5; border-color:#7f1d1d; }
  section { background:#111827; border:1px solid #1f2937; border-radius:16px;
            padding:1rem 1.25rem; margin-bottom:1.25rem; }
  h2 { font-size:.95rem; color:#c7d2fe; margin:.2rem 0 .8rem; }
  details { margin:.35rem 0; border-left:3px solid #312e81; padding-left:.7rem; }
  summary { cursor:pointer; color:#e0e7ff; }
  summary .age { color:#9ca3af; font-size:.75rem; margin-left:.5rem; }
  pre { white-space:pre-wrap; color:#cbd5e1; font-size:.8rem;
        background:#0b0f19; border-radius:8px; padding:.75rem; }
  .git div { font-size:.8rem; color:#9ca3af; padding:.08rem 0; }
  .git .maint { color:#a855f7; }
  .dim { color:#6b7280; font-size:.8rem; }
</style></head><body><div class="wrap">
<h1>dreamwork watch</h1>
<div class="meta" id="meta">loading…</div>
<div id="sections"></div>
<script>
const esc = t => { const d = document.createElement('div');
                   d.textContent = t ?? ''; return d.innerHTML; };
function dreamBlock(d) {
  return `<details><summary>${esc(d.name)}<span class="age">${esc(d.age)} old</span></summary><pre>${esc(d.content)}</pre></details>`;
}
function render(d) {
  const qb = d.open_questions > 0
    ? `<span class="badge warn">${d.open_questions} open question${d.open_questions>1?'s':''}</span>`
    : `<span class="badge">questions clear</span>`;
  document.getElementById('meta').innerHTML =
    `${esc(d.target)} · ${esc(d.files['skill-version'])} · ${esc(d.generated)} ${qb}`;
  let h = '';
  h += `<section><h2>Dreams (${d.dreams.length})</h2>` +
       (d.dreams.map(dreamBlock).join('') || '<div class="dim">none active</div>') +
       (d.dreams_archive.length
         ? `<details><summary class="dim">archive (${d.dreams_archive.length})</summary>` +
           d.dreams_archive.map(dreamBlock).join('') + `</details>` : '') +
       `</section>`;
  h += `<section><h2>Files</h2>` +
       ['DREAMWORK.md','questions.md','lessons.md'].map(n =>
         `<details><summary>${n}</summary><pre>${esc(d.files[n])}</pre></details>`
       ).join('') + `</section>`;
  h += `<section><h2>Status</h2>` + (d.status
        ? `<pre>${esc(JSON.stringify(d.status, null, 2))}</pre>`
        : `<div class="dim">no status.json yet (loop writes it each tick once stage 3 lands)</div>`) +
       `</section>`;
  h += `<section class="git"><h2>Recent commits</h2>` +
       d.git.map(l => `<div class="${l.includes('dreamwork(maintain:') ? 'maint' : ''}">${esc(l)}</div>`).join('') +
       `</section>`;
  document.getElementById('sections').innerHTML = h;
}
let last = null;
async function tick() {
  try {
    const m = await (await fetch('/mtime')).text();
    if (m !== last) { last = m;
      render(await (await fetch('/data.json')).json()); }
  } catch (e) { /* server restarting; retry */ }
  setTimeout(tick, 2000);
}
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
