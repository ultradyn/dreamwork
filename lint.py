#!/usr/bin/env python3
"""lint — check a target's `.dreamwork/` files against the shapes their readers require.

    python3 lint.py [--target DIR]

Some files the loop writes are parsed by a tool, and a file in the wrong
shape fails SILENTLY: zero parsed entries renders identically to nothing to
report. On 2026-07-25 a dreamwork instance opened its dashboard to zero
questions over a file holding six, four of them genuinely open. Nothing
errored. Nothing was logged. The loop believed it had escalated.

`file-formats.md` states the shapes in prose. This checks them, and the
difference matters: prose is a second description that can drift from the
parser, which is the bug one layer up. **So this calls the real readers
rather than reimplementing them** — `watch.py`'s parsers are imported and
run, so a lint pass means the dashboard can genuinely see the file. If the
parser changes, this changes with it for free.

Exit codes: 0 clean or warnings only, 1 if any ERROR, 2 if the target is
not a dreamwork target at all.

Levels:
  ERROR  a reader cannot see what is there. Data loss, silent by nature.
  WARN   worth knowing, not broken. A missing questions.md is the common
         case — the loop writes it almost immediately, and init seeds it.
  OK     parsed, with the counts it parsed.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent

ERROR, WARN, OK = "ERROR", "WARN", "OK"

DREAM_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{4}-[a-z0-9-]+\.md$")
LEDGER_ID = re.compile(r"^- \*\*#(\d+)\*\*", re.M)
NEXT_ID = re.compile(r"^Next id: \*\*(\d+)\*\*", re.M)


def load_watch():
    """Import watch.py for its parsers.

    By path, not as a package: watch.py is a single file by design (the
    deploy snapshot depends on it) and this must not become a second reason
    it cannot move. Returns None if it is unimportable — mid-edit by another
    agent, say — so the rest of the checks still run.
    """
    path = SKILL_DIR / "watch.py"
    if not path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("_watch_for_lint", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, level: str, what: str, detail: str) -> None:
        self.rows.append((level, what, detail))

    @property
    def failed(self) -> bool:
        return any(level == ERROR for level, _, _ in self.rows)

    def render(self) -> str:
        width = max((len(w) for _, w, _ in self.rows), default=0)
        lines = [f"  {lvl:<5} {what:<{width}}  {detail}" for lvl, what, detail in self.rows]
        errors = sum(1 for lvl, _, _ in self.rows if lvl == ERROR)
        warns = sum(1 for lvl, _, _ in self.rows if lvl == WARN)
        if errors:
            lines.append(f"\n{errors} error(s), {warns} warning(s) — see file-formats.md")
        else:
            lines.append(f"\nclean ({warns} warning(s))")
        return "\n".join(lines)


def check_questions(dw: Path, watch, rep: Report) -> None:
    """The channel to the human. The one that failed."""
    path = dw / "questions.md"
    if not path.exists():
        rep.add(WARN, "questions.md", "absent — init seeds it; the loop writes it early")
        return

    text = path.read_text()
    if not text.strip():
        rep.add(OK, "questions.md", "empty")
        return

    # Check the section headings first, because their absence is both the
    # actual failure that happened and the one with a nameable cause. A
    # generic "parsed nothing" would be true but far less useful.
    heads = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("## ")]
    if "## Open" not in heads:
        rep.add(
            ERROR,
            "questions.md",
            f"no literal `## Open` heading — every entry is invisible to the "
            f"dashboard AND unwritable by /answer. Found: {heads[:4] or 'none'}",
        )
        return

    if watch is None:
        rep.add(WARN, "questions.md", "`## Open` present; watch.py unimportable, so entries unverified")
        return

    o = len(watch.parse_open_questions(text))
    a = len(watch.parse_answered(text))
    if o or a:
        rep.add(OK, "questions.md", f"{o} open, {a} answered")
        return

    # Zero entries has two causes that must not be confused, and getting this
    # wrong once already made the linter cry wolf on the skeleton that
    # initialization.md step 7 MANDATES — a checker that fails the correct
    # initial state is a checker nobody reads by week two.
    #
    # A SEEDED SKELETON is headings and nothing else: legitimately empty, and
    # the ordinary state of a fresh target between init and the first ask.
    # CONTENT THAT PARSES TO NOTHING is the real failure — a file with prose
    # in it that the reader cannot see, which renders as "nothing to answer"
    # while real questions sit in it.
    body = [
        ln for ln in text.splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    if not body:
        rep.add(OK, "questions.md", "seeded, no entries yet")
    else:
        rep.add(
            ERROR,
            "questions.md",
            f"{len(body)} lines of content and the reader sees NO entries — "
            f"renders as 'nothing to answer'. Entries need `- **Title**` at top level",
        )


def check_tasks(dw: Path, rep: Report) -> None:
    """The ledger. Its ids are permanent, so a collision is unrecoverable."""
    path = dw / "tasks.md"
    if not path.exists():
        rep.add(WARN, "tasks.md", "absent — required only when the backend is session-scoped")
        return

    text = path.read_text()
    ids = [int(m) for m in LEDGER_ID.findall(text)]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        rep.add(ERROR, "tasks.md", f"duplicate id(s) {dupes} — two entries claim one permanent id")

    m = NEXT_ID.search(text)
    if not m:
        rep.add(ERROR, "tasks.md", "no `Next id: **N**` header — the next task cannot be numbered safely")
    else:
        nxt = int(m.group(1))
        if ids and nxt <= max(ids):
            rep.add(
                ERROR,
                "tasks.md",
                f"Next id is {nxt} but #{max(ids)} exists — the next task would collide",
            )
        elif not dupes:
            rep.add(OK, "tasks.md", f"{len(ids)} entries, next id {nxt}")


# status.json has two readers now (watch.py and dreamhub.py), which makes it
# an interface. Every field is optional — readers degrade, a fresh loop writes
# almost nothing — so a wrong TYPE is the failure worth catching: an absent
# field reads as "unknown", while a string where a list belongs makes a reader
# render nonsense or throw.
STATUS_TYPES = {
    "task": str,
    "goal": str,
    "agents": list,
    "queue": dict,
    "awaiting_human": list,
    "last_tick": str,
    "last_commit": str,
}


def check_status(dw: Path, rep: Report) -> None:
    path = dw / "status.json"
    if not path.exists():
        rep.add(WARN, "status.json", "absent — written on the first tick; gitignored ephemera")
        return
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        rep.add(ERROR, "status.json", f"invalid JSON at line {exc.lineno} — every reader sees nothing")
        return
    if not isinstance(data, dict):
        rep.add(ERROR, "status.json", f"top level is {type(data).__name__}, not an object")
        return

    wrong = [
        f"{k} is {type(data[k]).__name__}, want {t.__name__}"
        for k, t in STATUS_TYPES.items()
        if k in data and not isinstance(data[k], t)
    ]
    if wrong:
        rep.add(ERROR, "status.json", "; ".join(wrong))
        return

    # An agent without a name cannot be reported on by any reader.
    nameless = sum(1 for a in data.get("agents", []) if not (isinstance(a, dict) and a.get("name")))
    if nameless:
        rep.add(ERROR, "status.json", f"{nameless} agent(s) with no `name` — unreportable by any reader")
        return

    # A timestamp in the FUTURE is always wrong and always detectable, and
    # two different agents produced one on 2026-07-25 by estimating elapsed
    # time instead of reading the clock — both felt that far more time had
    # passed than had. `last_tick` is a claim about freshness, so a wrong one
    # makes a stalled loop and a lying one indistinguishable from outside.
    tick = data.get("last_tick")
    if isinstance(tick, str):
        skew = _future_skew(tick)
        if skew is not None and skew > 60:
            rep.add(
                ERROR,
                "status.json",
                f"last_tick is {int(skew // 60)}min in the FUTURE — read the clock, "
                f"do not estimate elapsed time",
            )
            return

    agents = data.get("agents") or []
    waiting = data.get("awaiting_human") or []
    detail = f"valid; {len(agents)} agent(s)"
    if waiting:
        detail += f", {len(waiting)} awaiting the human"
    rep.add(OK, "status.json", detail)


def _future_skew(stamp: str):
    """Seconds by which `stamp` is ahead of now, or None if unparseable.

    Unparseable is not an error: the field is optional and a target may write
    a shape this does not know. Only a confidently-future time is reported.
    """
    from datetime import datetime

    try:
        when = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    now = datetime.now(tz=when.tzinfo) if when.tzinfo else datetime.now()
    return (when - now).total_seconds()


def check_watch_port(dw: Path, rep: Report) -> None:
    """The address the human's bookmark points at. Two readers as of #96."""
    path = dw / "watch-port"
    if not path.exists():
        rep.add(WARN, "watch-port", "absent — written when the dashboard is first deployed")
        return
    raw = path.read_text().strip()
    if not raw.isdigit() or not (1024 <= int(raw) <= 65535):
        rep.add(ERROR, "watch-port", f"{raw!r} is not a usable port — deploy and the hub both read this")
    else:
        rep.add(OK, "watch-port", raw)


def check_watch_tint(dw: Path, watch, rep: Report) -> None:
    """His colour for this project.

    Worth a check for one reason: an unknown name does not break the page, it
    silently ignores what he chose. The file is only ever written through a
    validated POST, so a bad value means a hand-edit or a rename in watch.py —
    and in both cases the page falls back to the default with nothing on
    screen to say so.

    Reads the closed set from watch.py rather than restating it, so the check
    cannot drift from what the page accepts. Absent returns SILENTLY, unlike
    watch-port's WARN: most targets will never set a colour, and a warning on
    every one of them is the noise that hides the real one.
    """
    path = dw / "watch-tint"
    if not path.exists():
        return
    raw = path.read_text().strip()
    names = sorted(getattr(watch, "TINTS", {})) if watch else []
    if not names:
        rep.add(WARN, "watch-tint", f"{raw!r} — unverified (watch.py unreadable)")
    elif raw not in names:
        rep.add(
            ERROR,
            "watch-tint",
            f"{raw!r} is not one of {', '.join(names)} — the page falls back to "
            f"the default and nothing says his choice was dropped",
        )
    else:
        rep.add(OK, "watch-tint", raw)


PLUGIN_KIND = re.compile(r"^[a-z0-9]+-[a-z0-9-]*[a-z0-9]$")


def loaded_plugins(root: Path):
    """Plugin names under DREAMWORK.md's Plugins/Load bullets.

    Returns None for "cannot tell", which is deliberately not the same value
    as the empty set. A target with no Plugins section has not declared that
    nothing is loaded — it has said nothing — and treating silence as "none
    loaded" would mark every declared command stale on a target that simply
    never wrote the section.
    """
    path = root / "DREAMWORK.md"
    if not path.exists():
        return None
    section = re.search(r"^## Plugins\s*$(.*?)(?=^## |\Z)", path.read_text(), re.M | re.S)
    if not section:
        return None
    body = section.group(1)
    stop = re.search(r"^- \*{0,2}Don't load", body, re.M)
    if stop:
        body = body[: stop.start()]
    return set(re.findall(r"`(ud-dreamwork-[a-z0-9-]+)`", body))


def check_plugin_commands(dw: Path, watch, rep: Report) -> None:
    """Commands a plugin declares, written into the target so watch.py can see them (#86).

    Two failure modes, and neither announces itself.

    STALE: a plugin is unloaded and its commands stay in the menu, so the
    human sends something nothing answers. The file is rewritten WHOLE at
    load, which makes unloading the absence of a write rather than a
    remembered deletion — but only while something notices a file that
    outlived its plugin. That is this check, cross-read against DREAMWORK.md.

    SHADOWED: `writing-plugins.md` forbids repurposing a core command in
    prose. Prose cannot refuse. Core kinds come from watch.py's COMMANDS, so
    the ban tracks the real table instead of a copy of it.

    Absent returns silently: most targets load no plugin that declares
    anything, and a note on each of them is the noise that hides the one
    that matters.
    """
    path = dw / "plugin-commands.json"
    if not path.exists():
        return
    try:
        doc = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        rep.add(ERROR, "plugin-commands", f"unparseable JSON ({exc}) — the composer shows no plugin commands at all")
        return
    if not isinstance(doc, dict) or not isinstance(doc.get("commands"), list):
        rep.add(ERROR, "plugin-commands", "expected an object with a `commands` array")
        return

    cmds = doc["commands"]
    core = {c["kind"] for c in getattr(watch, "COMMANDS", ())} if watch else set()
    core_prefixes = {k.split("-")[0] for k in core}
    declared = loaded_plugins(dw.parent)
    seen: dict[str, str] = {}

    for i, c in enumerate(cmds):
        where = f"commands[{i}]"
        if not isinstance(c, dict):
            rep.add(ERROR, "plugin-commands", f"{where} is not an object")
            continue
        missing = [f for f in ("kind", "label", "desc", "plugin") if not isinstance(c.get(f), str) or not c[f]]
        if missing:
            rep.add(ERROR, "plugin-commands", f"{where} missing {', '.join(missing)}")
            continue
        kind, plugin = c["kind"], c["plugin"]
        if kind in core:
            rep.add(ERROR, "plugin-commands", f"{kind!r} shadows a core command — {plugin} would silently take it over")
        elif not PLUGIN_KIND.match(kind):
            rep.add(ERROR, "plugin-commands", f"{kind!r} is not `namespace-name` in lowercase — the composer sends it on the wire")
        elif kind.split("-")[0] in core_prefixes:
            rep.add(ERROR, "plugin-commands", f"{kind!r} uses the core namespace {kind.split('-')[0]!r} — pick the plugin's own")
        if kind in seen:
            rep.add(ERROR, "plugin-commands", f"{kind!r} declared by both {seen[kind]} and {plugin} — one of them never runs")
        seen[kind] = plugin
        if declared is None:
            rep.add(WARN, "plugin-commands", f"{kind!r} — unverified (no Plugins section in DREAMWORK.md)")
        elif plugin not in declared:
            rep.add(ERROR, "plugin-commands", f"{kind!r} is declared by {plugin}, which is not loaded — a stale menu entry nothing answers")

    if all(w != "plugin-commands" for _, w, _ in rep.rows):
        rep.add(OK, "plugin-commands", f"{len(cmds)} declared" if cmds else "none declared")


def check_skill_version(dw: Path, rep: Report) -> None:
    path = dw / "skill-version"
    if not path.exists():
        rep.add(WARN, "skill-version", "absent — init's update check cannot tell which migrations ran")
        return
    name = path.read_text().strip()
    if not (SKILL_DIR / "migrations" / name).exists():
        rep.add(
            ERROR,
            "skill-version",
            f"names `{name}`, which is not a file in migrations/ — every migration reads as pending",
        )
    else:
        rep.add(OK, "skill-version", name)


def check_dreams(dw: Path, rep: Report) -> None:
    """Filenames only. The contract here IS the filename — it carries the
    date and time that ordering depends on."""
    d = dw / "dreams"
    if not d.is_dir():
        return
    names = sorted(d.glob("*.md"))
    bad = [p.name for p in names if not DREAM_NAME.match(p.name)]
    if bad:
        rep.add(WARN, "dreams/", f"{len(bad)} misnamed (want YYYY-MM-DD-HHMM-slug.md): {bad[:3]}")
        return

    # A dream stamped in the FUTURE sorts wrong forever, and the filename IS
    # the ordering. Three different dreamers did this on 2026-07-25 — one by
    # 65 minutes — each estimating elapsed time instead of running `date`.
    # Same bias as the status.json check above, in the one place where the
    # damage is permanent rather than momentary.
    from datetime import datetime

    now = datetime.now()
    ahead = []
    for p in names:
        stamp = p.name[:15]  # YYYY-MM-DD-HHMM — 15 chars, not 16
        try:
            when = datetime.strptime(stamp, "%Y-%m-%d-%H%M")
        except ValueError:
            continue
        if (when - now).total_seconds() > 300:
            ahead.append(p.name)
    if ahead:
        rep.add(
            ERROR,
            "dreams/",
            f"{len(ahead)} stamped in the FUTURE, so they sort wrong forever: "
            f"{ahead[:3]} — get <hhmm> from `date`, never from memory",
        )
    else:
        rep.add(OK, "dreams/", f"{len(names)} named correctly")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="lint",
        description="Check a dreamwork target's .dreamwork/ files against the shapes their readers require.",
    )
    ap.add_argument("--target", default=".", help="target project directory (default: cwd)")
    args = ap.parse_args(argv)

    target = Path(args.target).resolve()
    dw = target / ".dreamwork"
    if not dw.is_dir():
        print(f"lint: {target} has no .dreamwork/ — not a dreamwork target", file=sys.stderr)
        return 2

    watch = load_watch()
    rep = Report()
    check_questions(dw, watch, rep)
    check_tasks(dw, rep)
    check_status(dw, rep)
    check_watch_port(dw, rep)
    check_watch_tint(dw, watch, rep)
    check_plugin_commands(dw, watch, rep)
    check_skill_version(dw, rep)
    check_dreams(dw, rep)

    print(f"lint {dw}")
    print(rep.render())
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
