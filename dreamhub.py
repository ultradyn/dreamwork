#!/usr/bin/env python3
"""dreamhub.py — read-only aggregate overview of several dreamwork targets.

Plan: .dreamwork/docs/plans/dreamhub-stage1.md (human go 2026-07-25 10:48).
Design record: dreamhub-design.md (skill root).

Stdlib only, one file — so `just deploy`'s snapshot pattern applies to it
unchanged. Binds 127.0.0.1 exclusively. Writes NOTHING outside
`~/.config/dreamwork/hub/`: every per-project fact is read live from that
project's own `.dreamwork/` (and from its running watch instance) and is
never cached to disk, because a cached copy is a second source of truth
that goes stale exactly when it matters.

Reuse with watch.py is at the PROTOCOL layer, never the code layer: the hub
polls each target's `GET /mtime` and re-reads `GET /data.json` only when it
changes — the same contract watch's own client uses. So the hub never parses
`questions.md`, the open-question count keeps exactly one implementation,
and a target whose watch is down reports "unknown" rather than a second,
subtly different answer. No `import watch`.
"""

import argparse
import hashlib
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from concurrent import futures
from datetime import datetime

# Where the machine-local state lives. Which projects exist is a fact about
# THIS MACHINE, not about any repo — committing it would be wrong on the next
# machine and would leak local paths. `DREAMHUB_HOME` overrides it, which is
# what the tests and the guards point at their own fixtures with.
DEFAULT_HOME = os.path.join("~", ".config", "dreamwork", "hub")

# Registry schema version. Bump only for a shape change that an older
# dreamhub could misread; readers refuse anything they do not know.
REGISTRY_VERSION = 1

SLUG_OK = re.compile(r"[^a-z0-9._-]+")


def hub_home():
    return os.path.abspath(os.path.expanduser(
        os.environ.get("DREAMHUB_HOME") or DEFAULT_HOME))


def registry_path():
    return os.path.join(hub_home(), "projects.json")


def normalise(path):
    """User input → the one canonical form we store and compare.

    `~`, relative paths and trailing slashes all collapse here, so `add .`
    twice from two different directories cannot produce two entries for one
    project.
    """
    return os.path.abspath(os.path.expanduser(path))


def is_target(path):
    """Does this directory look like a dreamwork target?

    A target has a `.dreamwork/` or a `DREAMWORK.md`. The check exists so a
    typo'd path is rejected at `add` time rather than sitting in the list
    looking healthy — a registry entry that never resolves is indistinguish-
    able from a project whose loop is merely quiet.
    """
    return (os.path.isdir(os.path.join(path, ".dreamwork"))
            or os.path.isfile(os.path.join(path, "DREAMWORK.md")))


def slug_for(path, taken):
    """Stable, human-typeable name for a project — assigned ONCE, at add time.

    Recomputing a slug on read would mean that adding a colliding project
    silently renames an existing one, and every link, bookmark and log line
    that named the old slug would quietly point somewhere else. So the slug
    is stored, and this function is called exactly once per project.
    """
    base = SLUG_OK.sub("-", os.path.basename(path.rstrip(os.sep)).lower())
    base = base.strip("-") or "target"
    if base not in taken:
        return base
    return f"{base}-{hashlib.sha1(path.encode()).hexdigest()[:6]}"


class RegistryError(Exception):
    """The registry exists but cannot be understood."""


def _blank():
    return {"version": REGISTRY_VERSION, "projects": []}


def load_registry(strict=False):
    """Read the registry. Missing file = empty registry, which is normal.

    An UNREADABLE file is not normal, and `strict` is the difference that
    matters: a writer that treated corruption as "empty" would rewrite the
    file and destroy whatever was in it. Readers degrade; writers refuse.
    """
    path = registry_path()
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except FileNotFoundError:
        return _blank()
    except OSError as e:
        if strict:
            raise RegistryError(f"cannot read {path}: {e.strerror}")
        return _blank()
    try:
        data = json.loads(raw)
    except ValueError as e:
        if strict:
            raise RegistryError(f"{path} is not valid JSON ({e}); fix or "
                                f"move it aside — refusing to overwrite it")
        return _blank()
    if not isinstance(data, dict) or not isinstance(
            data.get("projects"), list):
        if strict:
            raise RegistryError(f"{path} is not a dreamhub registry — "
                                f"refusing to overwrite it")
        return _blank()
    if data.get("version") != REGISTRY_VERSION:
        if strict:
            raise RegistryError(
                f"{path} is registry version {data.get('version')!r}, this "
                f"dreamhub speaks {REGISTRY_VERSION}")
        return _blank()
    return data


def save_registry(reg):
    """Atomic replace: a torn write here loses the human's whole project list.

    Same reasoning as status.json being read defensively — except the hub is
    the writer, so it can simply make the torn state impossible.
    """
    path = registry_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def find(reg, slug_or_path):
    """Look a project up by slug first, then by path — `remove` takes either,
    because the human knows where a project IS more reliably than what the
    hub decided to call it."""
    for p in reg["projects"]:
        if p["slug"] == slug_or_path:
            return p
    target = normalise(slug_or_path)
    for p in reg["projects"]:
        if p["path"] == target:
            return p
    return None


def add_project(reg, path, force=False):
    """Register `path`. Returns (entry, created:bool).

    Adding an already-registered path is idempotent and silent — the human
    re-running `add` after a shell restart should not get an error, and must
    never get a second entry for one directory.
    """
    path = normalise(path)
    existing = next((p for p in reg["projects"] if p["path"] == path), None)
    if existing:
        return existing, False
    if not os.path.isdir(path):
        raise RegistryError(f"{path} is not a directory")
    if not force and not is_target(path):
        raise RegistryError(
            f"{path} has no .dreamwork/ and no DREAMWORK.md — not a dreamwork "
            f"target. Pass --force if you meant it.")
    entry = {
        "slug": slug_for(path, {p["slug"] for p in reg["projects"]}),
        "path": path,
        "added": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    reg["projects"].append(entry)
    return entry, True


# ------------------------------------------------------- the disk probe

# How long since the last tick before a loop stops counting as dreaming.
# Generous on purpose: the heartbeat is 4.75m, so a target that has missed
# one tick is not yet news, and a hub that cries stalled is a hub nobody
# looks at.
DREAMING_S = 10 * 60
QUIET_S = 60 * 60

DREAMING = "dreaming"
QUIET = "quiet"
STALLED = "stalled"
NO_STATUS = "no status"
MISSING = "missing"


def age_str(seconds):
    """Compact age, watch.py's vocabulary — the human reads both pages."""
    if seconds is None:
        return ""
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h"
    return f"{s // 86400}d"


def state_for(age):
    if age is None:
        return NO_STATUS
    if age < DREAMING_S:
        return DREAMING
    if age < QUIET_S:
        return QUIET
    return STALLED


def _parse_tick(value):
    """`last_tick` → epoch seconds, or None if it is not a timestamp.

    Returning None rather than guessing is the whole point: an unparseable
    tick must fall through to the file mtime, not become a fabricated age.
    """
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.strip()).timestamp()
    except ValueError:
        return None


def _as_list(value):
    return value if isinstance(value, list) else []


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def read_port(path):
    """The target's persisted watch port, or None if it was never watched."""
    try:
        with open(os.path.join(path, ".dreamwork", "watch-port"),
                  encoding="utf-8") as f:
            raw = f.read().strip()
    except OSError:
        return None
    return int(raw) if raw.isdigit() else None


def probe_disk(entry, now=None):
    """One registry entry → one row, from disk alone. Pure, no network.

    Never raises: every target is isolated, because a hub that 500s on one
    broken project has failed at the one job it has.
    """
    now = time.time() if now is None else now
    path = entry["path"]
    row = {
        "slug": entry["slug"], "path": path,
        "state": MISSING, "note": None, "port": None,
        "age": None, "age_str": "", "age_from": None,
        "task": None, "goal": None, "agents": [], "queue": None,
        "last_commit": None,
    }
    if not os.path.isdir(path):
        row["note"] = "directory is gone — remove it or fix the path"
        return row
    row["port"] = read_port(path)
    sfile = os.path.join(path, ".dreamwork", "status.json")
    mtime = _mtime(sfile)
    if mtime is None:
        row["state"] = NO_STATUS
        row["note"] = ("no .dreamwork/status.json — the loop has not ticked "
                       "here")
        return row

    status, torn = None, False
    try:
        with open(sfile, encoding="utf-8") as f:
            status = json.loads(f.read())
    except (OSError, ValueError):
        torn = True             # rewritten every tick; we WILL catch one
    if not isinstance(status, dict):
        status, torn = None, True

    tick = _parse_tick((status or {}).get("last_tick"))
    row["age_from"] = "last_tick" if tick is not None else "file"
    stamp = tick if tick is not None else mtime
    row["age"] = max(0.0, now - stamp)
    row["age_str"] = age_str(row["age"])
    row["state"] = state_for(row["age"])

    if torn:
        # A target caught mid-write is dreaming HARDER than the others, so
        # the age still stands (from the mtime) — only the contents are lost.
        row["note"] = "status.json unreadable — caught mid-write, or corrupt"
        return row
    if tick is None:
        row["note"] = "status.json has no readable last_tick; age is its mtime"

    row["task"] = status.get("task")
    row["goal"] = status.get("goal")
    row["queue"] = status.get("queue") if isinstance(
        status.get("queue"), dict) else None
    row["last_commit"] = status.get("last_commit")
    # Every shape below is checked rather than trusted. status.json is
    # hand-written prose-ish JSON that a dozen loops on a dozen versions of
    # the skill will produce, and one of them WILL put a number where this
    # expects a list. The hub's job is to keep showing the other rows.
    row["agents"] = [
        {"name": str(a.get("name") or "?"),
         "owns": [str(o) for o in _as_list(a.get("owns"))],
         "in_flight": a.get("in_flight")}
        for a in _as_list(status.get("agents")) if isinstance(a, dict)
    ]
    return row


# ------------------------------------------------------- the live probe

# One dead port must not hang the page — the classic aggregator failure and
# the single most likely stage-1 bug. Two mechanisms, and BOTH are needed:
# a hard per-request timeout (so one project cannot hang forever) and a
# thread per project (so a slow one does not add its timeout to everyone
# else's wait). A serial poll with timeouts is still N x timeout.
PROBE_TIMEOUT_S = 1.5

NEVER_WATCHED = "never watched"
UP = "up"
DOWN = "down"
TIMEOUT = "timeout"
UNREADABLE = "unreadable"


def _get(port, path, timeout):
    """GET http://127.0.0.1:<port><path> → body text. Raises on anything."""
    url = f"http://127.0.0.1:{port}{path}"
    with urllib.request.urlopen(url, timeout=timeout) as r:
        if r.status != 200:
            raise urllib.error.HTTPError(url, r.status, "not 200", r.headers,
                                         None)
        return r.read(1 << 20).decode("utf-8", "replace")


def probe_live(row, cache, timeout=PROBE_TIMEOUT_S):
    """Fill a row's live half from that project's own watch instance.

    THE reuse seam. The hub polls `/mtime` (tiny) and re-reads `/data.json`
    only when it changes — the same protocol watch's own client uses, so the
    hub costs a running watch almost nothing and `/mtime` doubles as the
    liveness check.

    It follows that the hub never parses `questions.md`. The open-question
    count keeps exactly one implementation, and when that implementation is
    not running the answer is None — *unknown* — never a second, subtly
    different count computed here. `None` renders as "?" and that is the
    honest thing for it to say.

    `cache` is `{slug: {"key": "<gen> <mtime>", "data": {...}}}`, in memory
    and per-process: a persisted aggregate would be a second source of truth
    with a longer life.
    """
    row.setdefault("watch", NEVER_WATCHED)
    row.setdefault("open_questions", None)
    row.setdefault("watch_url", None)
    row.setdefault("live_note", None)
    port = row.get("port")
    if not port:
        row["live_note"] = "no .dreamwork/watch-port — never watched"
        return row
    row["watch_url"] = f"http://127.0.0.1:{port}/"
    try:
        key = _get(port, "/mtime", timeout).strip()
    except socket.timeout:
        row["watch"], row["live_note"] = TIMEOUT, f":{port} did not answer"
        return row
    except urllib.error.HTTPError as e:
        row["watch"] = UNREADABLE
        row["live_note"] = f":{port} answered /mtime with {e.code}"
        return row
    except (urllib.error.URLError, OSError) as e:
        # Connection refused is the common, boring case: watch is not
        # running. It is not an error, it is a missing dashboard.
        reason = getattr(e, "reason", e)
        row["watch"] = TIMEOUT if isinstance(reason, socket.timeout) else DOWN
        row["live_note"] = (f":{port} did not answer" if row["watch"] == TIMEOUT
                            else f"no watch on :{port} — `just watch`")
        return row

    row["watch"] = UP
    slot = cache.get(row["slug"])
    if slot and slot.get("key") == key:
        row["open_questions"] = slot["data"].get("open_questions")
        return row
    try:
        data = json.loads(_get(port, "/data.json", timeout))
        if not isinstance(data, dict):
            raise ValueError("not an object")
    except socket.timeout:
        row["watch"], row["live_note"] = TIMEOUT, f":{port} did not answer"
        return row
    except (urllib.error.URLError, OSError, ValueError) as e:
        row["watch"] = UNREADABLE
        row["live_note"] = f":{port} served an unreadable /data.json ({e})"
        return row
    cache[row["slug"]] = {"key": key, "data": data}
    got = data.get("open_questions")
    row["open_questions"] = got if isinstance(got, int) else None
    return row


def probe_all(reg, cache, now=None, timeout=PROBE_TIMEOUT_S):
    """Every registry entry → a row. One thread per project.

    Isolation is the requirement: a hub that 500s, or stalls, because one
    project is broken has failed at the one job it has. Every failure mode
    lands in that project's own row and nowhere else.
    """
    rows = [probe_disk(e, now=now) for e in reg["projects"]]
    if not rows:
        return rows
    with futures.ThreadPoolExecutor(max_workers=min(16, len(rows))) as pool:
        list(pool.map(lambda r: _probe_live_safe(r, cache, timeout), rows))
    return rows


def _probe_live_safe(row, cache, timeout):
    try:
        return probe_live(row, cache, timeout)
    except Exception as e:                                  # noqa: BLE001
        # Last resort. An unforeseen exception in one worker must not take
        # the page down with it; it takes its own row down and says so.
        row["watch"] = UNREADABLE
        row["live_note"] = f"probe failed: {e.__class__.__name__}: {e}"
        return row


# ------------------------------------------------------------ the page

# Tokens are watch-design.md's, value for value, because this is the same
# surface seen from one level up: the human moves between the hub and a
# project's dashboard constantly and a second palette would read as a second
# product. Mono stack, two sizes, dim uppercase labels, hairlines not boxes,
# and ONE accent spent only on live or actionable things.
STYLE = """<style>
  :root { --bg:#0b0f19; --panel:#111827; --panel2:#1e293b;
    --line:#1f2937; --border:#334155; --text:#d1d5db; --bright:#f3f4f6;
    --lit:#e5e7eb; --muted:#9ca3af; --dim:#6b7280; --dimmer:#4b5563;
    --accent:#a5b4fc; --space:1.6rem; --radius:4px; }
  * { scrollbar-width:thin; scrollbar-color:var(--dimmer) transparent;
      box-sizing:border-box; }
  ::-webkit-scrollbar { width:7px; height:7px; }
  ::-webkit-scrollbar-track { background:transparent; }
  ::-webkit-scrollbar-thumb { background:var(--dimmer);
                              border-radius:var(--radius); }
  body { background:var(--bg); color:var(--text); margin:0;
         padding:2.5rem 1rem;
         font-family:ui-monospace,'JetBrains Mono',monospace; font-size:.8rem; }
  .wrap { max-width:72ch; margin:0 auto; }
  header { color:var(--bright); font-size:1rem; margin-bottom:.25rem; }
  #meta { color:var(--dim); margin-bottom:2rem; }
  .label { color:var(--dim); text-transform:uppercase; letter-spacing:.08em;
           font-size:.7rem; }
  a { color:var(--accent); text-decoration:none; }
  a:hover { text-decoration:underline; }
  /* Label the columns, not the gaps: every row states its two facts side by
     side under a header pair, because a label floating between two rows
     attaches itself to the wrong one and the reader never notices they have
     learned it backwards. */
  .cols { display:flex; justify-content:space-between; gap:1ch;
          padding-bottom:.4rem; border-bottom:1px solid var(--line); }
  .row { display:flex; justify-content:space-between; gap:2ch;
         padding:.9rem 0; border-bottom:1px solid var(--line); }
  .l { min-width:0; }
  .r { text-align:right; white-space:nowrap; flex:none; }
  .slug { color:var(--lit); }
  a.slug { color:var(--accent); }
  .task { color:var(--muted); margin-top:.3rem;
          overflow-wrap:anywhere; }
  .facts { color:var(--dim); margin-top:.3rem; overflow-wrap:anywhere; }
  .facts .q { color:var(--accent); }
  .owns { color:var(--dimmer); }
  .state { color:var(--muted); }
  /* The accent is scarce on purpose. A dreaming loop is the live thing on
     this page, so it gets it; quiet is neutral; stalled and broken are
     stated plainly rather than alarmed about, because the page is read at a
     glance and a wall of red says nothing. */
  .state.dreaming { color:var(--accent); }
  .state.stalled, .state.missing { color:var(--muted); }
  .age { color:var(--dim); margin-left:1ch; }
  .note { color:var(--dim); margin-top:.3rem; overflow-wrap:anywhere; }
  code { color:var(--muted); background:var(--panel); padding:0 .4ch;
         border-radius:var(--radius); overflow-wrap:anywhere; }
  .empty { color:var(--dim); margin-top:2rem; }
</style>"""

SCRIPT = """<script>
/* One renderer, and it is the Python one. The client swaps in a freshly
   rendered fragment rather than building rows of its own — a second
   renderer is a second set of rules about what a stalled project looks
   like, and the two only ever agree on the day they are written.
   Between polls the ages tick locally off data-since, which is trivia
   (a formatter), not an interpreter. */
const AGE = s => s < 60 ? Math.floor(s) + 's'
  : s < 3600 ? Math.floor(s / 60) + 'm'
  : s < 86400 ? Math.floor(s / 3600) + 'h' : Math.floor(s / 86400) + 'd';
function tickAges() {
  const now = Date.now() / 1000;
  document.querySelectorAll('.age[data-since]').forEach(el => {
    const t = parseFloat(el.dataset.since);
    if (!isNaN(t)) el.textContent = AGE(Math.max(0, now - t));
  });
}
async function poll() {
  try {
    const html = await (await fetch('/rows')).text();
    const rows = document.getElementById('rows');
    if (rows && html) { rows.innerHTML = html; tickAges(); }
    document.getElementById('meta').classList.remove('lost');
  } catch (e) { document.getElementById('meta').classList.add('lost'); }
}
setInterval(tickAges, 1000);
setInterval(poll, 2000);
tickAges();
</script>"""


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def watch_command(path):
    """The command that starts this project's dashboard.

    Stage 1 has no lifecycle: the hub SHOWS the command and the human runs
    it. Naming the real command is the whole value — the alternative is a
    row that says 'down' and leaves him to remember which tool it was.
    """
    sibling = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "watch.py")
    tool = sibling if os.path.isfile(sibling) else "watch.py"
    return f"python3 {tool} --target {path}"


def _facts(row):
    """The third line of a row: what is waiting on him, and who is out."""
    bits = []
    q = row.get("open_questions")
    if q:
        bits.append(f'<span class="q">{q} open question'
                    f'{"s" if q > 1 else ""}</span>')
    elif q == 0:
        bits.append("no open questions")
    else:
        bits.append("questions unknown")
    agents = row.get("agents") or []
    if agents:
        names = ", ".join(
            f'{esc(a["name"])}<span class="owns"> ({esc(", ".join(a["owns"]))})'
            f'</span>' if a["owns"] else esc(a["name"]) for a in agents)
        bits.append(f'{len(agents)} out: {names}')
    queue = row.get("queue") or {}
    if isinstance(queue.get("pending"), int):
        bits.append(f'{queue["pending"]} pending')
    return " · ".join(bits)


def render_row(row, now=None):
    now = time.time() if now is None else now
    since = (now - row["age"]) if row.get("age") is not None else None
    label = esc(row["slug"])
    left = (f'<a class="slug" href="{esc(row["watch_url"])}">{label}</a>'
            if row.get("watch") == UP and row.get("watch_url")
            else f'<span class="slug">{label}</span>')
    parts = [f'<div class="l">{left}']
    if row.get("task"):
        parts.append(f'<div class="task">{esc(row["task"])}</div>')
    parts.append(f'<div class="facts">{_facts(row)}</div>')
    # A down row must not link to a dead port. It shows what to run instead —
    # the one thing the human actually needs from a row in this state.
    if row.get("watch") in (DOWN, TIMEOUT, UNREADABLE, NEVER_WATCHED):
        parts.append(f'<div class="note">no dashboard · '
                     f'<code>{esc(watch_command(row["path"]))}</code></div>')
    elif row.get("note"):
        parts.append(f'<div class="note">{esc(row["note"])}</div>')
    parts.append("</div>")
    state = esc(row["state"])
    cls = state.replace(" ", "")
    age = (f'<span class="age" data-since="{since:.1f}">'
           f'{esc(row["age_str"])}</span>' if since is not None else "")
    parts.append(f'<div class="r"><span class="state {cls}">{state}</span>'
                 f'{age}</div>')
    return f'<div class="row" data-slug="{label}">{"".join(parts)}</div>'


def render_rows(rows, now=None):
    if not rows:
        return ('<div class="empty">No projects registered yet — '
                '<code>dreamhub add &lt;path&gt;</code></div>')
    head = ('<div class="cols"><span class="label">project</span>'
            '<span class="label">last tick</span></div>')
    return head + "".join(render_row(r, now) for r in rows)


def render_page(rows, now=None):
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>dreamhub</title>" + STYLE + "</head><body><div class='wrap'>"
        "<header>dreamhub</header>"
        f"<div id='meta'>{len(rows)} project{'' if len(rows) == 1 else 's'} "
        "on this machine</div>"
        f"<div id='rows'>{render_rows(rows, now)}</div>"
        + SCRIPT + "</div></body></html>")


# ---------------------------------------------------------- the server

def hub_port():
    """This hub's port, persisted — the same idiom as a target's
    `.dreamwork/watch-port`, one level up, so a bookmark keeps working."""
    marker = os.path.join(hub_home(), "port")
    try:
        with open(marker, encoding="utf-8") as f:
            saved = f.read().strip()
        if saved.isdigit():
            return int(saved)
    except OSError:
        pass
    import random
    port = random.randrange(3000, 63000)
    try:
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w", encoding="utf-8") as f:
            f.write(f"{port}\n")
    except OSError:
        pass
    return port


def make_handler(cache, timeout=PROBE_TIMEOUT_S):
    import http.server

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _send(self, body, ctype="text/html; charset=utf-8", code=200):
            raw = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            rows = probe_all(load_registry(), cache, timeout=timeout)
            if self.path == "/hub.json":
                self._send(json.dumps({
                    "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "projects": rows}, indent=2),
                    "application/json; charset=utf-8")
            elif self.path == "/rows":
                self._send(render_rows(rows))
            elif self.path == "/":
                self._send(render_page(rows))
            else:
                self._send("not found", "text/plain; charset=utf-8", 404)

    return Handler


def serve(port=None):
    import http.server
    # `is None`, not `or`: port 0 means "any free port" to the OS and is
    # exactly what a test or a guard asks for. `port or hub_port()` reads
    # 0 as absent and quietly binds a random persisted port instead —
    # which succeeds almost every time and collides just often enough to
    # look like flakiness.
    port = hub_port() if port is None else port
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port),
                                            make_handler({}))
    return httpd


# ---------------------------------------------------------------- CLI

def cmd_add(args):
    reg = load_registry(strict=True)
    entry, created = add_project(reg, args.path, force=args.force)
    if created:
        save_registry(reg)
        print(f"added {entry['slug']}  {entry['path']}")
    else:
        print(f"already registered as {entry['slug']}  {entry['path']}")
    return 0


def cmd_remove(args):
    reg = load_registry(strict=True)
    entry = find(reg, args.slug)
    if not entry:
        print(f"dreamhub: no project '{args.slug}' — try `dreamhub list`",
              file=sys.stderr)
        return 1
    reg["projects"].remove(entry)
    save_registry(reg)
    print(f"removed {entry['slug']}  {entry['path']}")
    return 0


def cmd_list(args):
    reg = load_registry()
    if not reg["projects"]:
        print("no projects registered — `dreamhub add <path>`")
        return 0
    width = max(len(p["slug"]) for p in reg["projects"])
    for p in reg["projects"]:
        print(f"{p['slug']:<{width}}  {p['path']}")
    return 0


def cmd_serve(args):
    port = hub_port() if args.port is None else args.port
    try:
        httpd = serve(port)
    except OSError as e:
        print(f"dreamhub: cannot bind 127.0.0.1:{port} ({e.strerror}). "
              f"Another dreamhub is probably already serving it "
              f"(the port persists in {os.path.join(hub_home(), 'port')}); "
              f"stop it or pass --port.", file=sys.stderr)
        return 1
    url = f"http://127.0.0.1:{port}/"
    print(f"dreamhub on {url}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="dreamhub",
        description="one page over several dreaming projects on this machine")
    sub = p.add_subparsers(dest="cmd")

    a = sub.add_parser("add", help="register a dreamwork target")
    a.add_argument("path")
    a.add_argument("--force", action="store_true",
                   help="register even if it does not look like a target")
    a.set_defaults(fn=cmd_add)

    r = sub.add_parser("remove", help="unregister a project (slug or path)")
    r.add_argument("slug")
    r.set_defaults(fn=cmd_remove)

    ls = sub.add_parser("list", help="show the registry")
    ls.set_defaults(fn=cmd_list)

    sv = sub.add_parser("serve", help="serve the hub page on 127.0.0.1")
    sv.add_argument("--port", type=int, default=None)
    sv.set_defaults(fn=cmd_serve)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "fn", None):
        parser.print_help()
        return 0
    try:
        return args.fn(args)
    except RegistryError as e:
        print(f"dreamhub: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
