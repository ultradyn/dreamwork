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

# ── task provenance, forward-only from the cutoff (#213) ──────────────
# The origin rule needs a WIDER entry grammar than LEDGER_ID: combined
# entries (`- **#250/#251**`) are entries too, and the check reads whole
# entries, not head lines. LEDGER_ID itself is pinned identical to
# watch.py's LEDGER_ENTRY by a test and is NOT widened — the id-collision
# and next-id rules keep their existing grammar, this rule gets its own.
ORIGIN_CUTOFF = 216
ORIGIN_VALUES = ("human", "loop", "unknown")
ENTRY_HEAD = re.compile(r"^- \*\*([^*]+?)\*\*")
ENTRY_ID = re.compile(r"#(\d+)")
# An origin claim is `origin: **value**`; the entry's lines are joined
# before matching, so a hard-wrapped marker (`origin:` ending a line, the
# value opening the next — #288 and #252 both do this) still reads.
ORIGIN_MARK = re.compile(r"origin:\s*\*\*\s*([^*]+?)\s*\*\*")


def ledger_entries(text: str) -> list[tuple[list[int], str]]:
    """Each ledger entry as (its ids, its full text).

    An entry is a list item opening `- **#…**`; its text is that line plus
    the following blank or indented lines. A line at column 0 that does not
    open an entry ENDS it — the prose summaries under Recently landed are
    not entries and never join one. Only the leading bold token numbers the
    entry: combined entries list every id (`- **#138/#156**`), while a
    `#264` in the body is a cross-reference, not the entry's number.
    """
    entries: list[tuple[list[int], list[str]]] = []
    cur: tuple[list[int], list[str]] | None = None
    for ln in text.split("\n"):
        m = ENTRY_HEAD.match(ln)
        if m:
            ids = [int(x) for x in ENTRY_ID.findall(m.group(1))]
            cur = (ids, [ln])
            entries.append(cur)
        elif cur is not None and (not ln.strip() or ln[0] in " \t"):
            cur[1].append(ln)
        else:
            cur = None
    return [(ids, "\n".join(lines)) for ids, lines in entries]


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
        bad = check_priorities(watch, text)
        if bad:
            rep.add(
                ERROR,
                "questions.md",
                f"{len(bad)} entry title(s) start with something that looks like a "
                f"priority but is not one of P1/P2/P3 — it will sort as unmarked "
                f"and read as marked: {', '.join(bad[:3])}",
            )
        else:
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


def check_answers(dw: Path, watch, rep: Report) -> None:
    """Optional channel from the human to the dreamer."""
    path = dw / "answers.md"
    if not path.exists():
        rep.add(OK, "answers.md", "absent — /ask creates it on first use")
        return
    text = path.read_text()
    heads = [ln.strip() for ln in text.splitlines()
             if ln.strip().startswith("## ")]
    if "## Open" not in heads or "## Answered" not in heads:
        rep.add(ERROR, "answers.md", "requires literal `## Open` and `## Answered` headings")
        return
    if watch is None:
        rep.add(WARN, "answers.md", "headings present; watch.py unimportable")
        return
    o = len(watch.parse_open_answers(text))
    a = len(watch.parse_answered_answers(text))
    health = watch.answers_health(text, o + a)
    if health == "unreadable":
        rep.add(ERROR, "answers.md", "content exists but no entries parse")
    else:
        rep.add(OK, "answers.md", f"{o} open, {a} answered")


# DELIBERATELY WIDER THAN THE PARSER’S, and that is the whole design. This
# regex asks "does this READ to a human as prioritised", so it accepts
# separators `watch.py` does not; whether the parser HONOURED it is asked of
# the parser itself, below. Making these two the same rule is precisely the
# bug this check exists to find, one file over.
PRIORITY = re.compile(r"^(P\d+)\s*[\u00b7:\-]\s*")


def check_priorities(watch, text: str) -> list[str]:
    """Titles that LOOK prioritised and do not SORT that way (#197).

    The marker is an optional `P1 · ` / `P2 · ` / `P3 · ` prefix, and absent
    means P2 — the middle band, so an explicit low genuinely sorts below an
    unmarked one. One failure is worth an error and it is the quiet one: a
    title that reads to a human as prioritised and sorts as unmarked, so the
    entry he most wants seen sits mid-list looking urgent. A title with no
    marker at all is normal and says nothing.

    THE BAND IS ASKED OF `watch.title_priority` AND NEVER RE-DERIVED HERE —
    the same move as `check_plugin_commands` reading core kinds from
    `COMMANDS` rather than a copy. It is not tidiness: this check shipped
    holding its own copy of the marker rule, and the copy was the more
    permissive of the two, so `P1: blocks work`, `P1·blocks work` and
    `P1 - blocks work` were each blessed by the linter and read as UNMARKED
    by the page. The checker was blind to its own stated failure in three of
    the four ways a human would most plausibly write it — because a check and
    the thing it checks cannot hold separate copies of one rule and stay
    honest.

    Two shapes, reported as one error, because to whoever wrote the title
    they are one mistake: the marker did not take.
    """
    bad = []
    for q in list(watch.parse_open_questions(text)) + list(watch.parse_answered(text)):
        title = " ".join(str(q.get("title", "")).split())
        m = PRIORITY.match(title)
        if not m:
            continue
        apparent = m.group(1)
        if apparent not in ("P1", "P2", "P3"):
            bad.append(f"{apparent} (outside the band)")
        elif f"P{watch.title_priority(title)}" != apparent:
            # A legal band with an illegal SEPARATOR: the parser saw no marker
            # at all. Name the fix, because "P1 is wrong" reads as nonsense to
            # someone who just typed a perfectly good P1.
            bad.append(f"{apparent} (wants `{apparent} · `)")
    return bad


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

    check_task_origins(text, rep)
    check_ledger_sections(text, rep)


def check_ledger_sections(text: str, rep: Report) -> None:
    """#304: a SECOND, independent reader of where the open section is.

    `watch.parse_ledger` finds the sections to tell the dashboard how many
    tasks are open and which have landed. It used to locate them with an
    unanchored `str.split` on the heading text, so an entry whose PROSE
    quoted a heading silently became the split point — the ledger read
    2 open / 187 landed against a true 105 / 84, and every number derived
    from it was wrong. Nothing noticed, including this linter, which counts
    entries without splitting sections at all.

    So this walks the lines itself — a genuinely separate implementation,
    not a call into the thing under test — and disagreement is the error.
    Two readers of one file must not diverge; the repo already pins
    LEDGER_ID to watch's LEDGER_ENTRY for the same reason.
    """
    section, mine = None, 0
    for ln in text.splitlines():
        stripped = ln.strip()
        if stripped.startswith("## "):
            section = stripped
        elif section == "## " + "Open" and LEDGER_ID.match(ln):
            mine += 1
    if section is None:
        return  # a ledger with no headings at all is another check's problem

    try:
        import watch
    except Exception:
        rep.add(WARN, "tasks.md", "watch.py unimportable — section split unverified")
        return

    theirs, _landed = watch.parse_ledger(text)
    if len(theirs) != mine:
        rep.add(
            ERROR,
            "tasks.md",
            f"open-entry count disagrees: this linter walks {mine}, "
            f"watch.parse_ledger sees {len(theirs)} — a section heading is "
            f"probably quoted inside an entry, which moves where the open "
            f"section is thought to end (#304)",
        )
    else:
        rep.add(OK, "tasks.md", f"section split agrees with watch.py at {mine} open")


def check_task_origins(text: str, rep: Report) -> None:
    """Forward-only provenance (#213), enforced from the #216 cutoff.

    From the cutoff onward, who filed a task is a fact the ledger records
    at filing time; before it, that fact was never written down and MUST
    NOT be reconstructed by guessing. So the rule looks only forward: an
    entry naming any id >= 216 in its leading token carries exactly one
    `origin: **human**` / `**loop**` / `**unknown**`. Entries whose ids
    all predate the cutoff are not checked at all — an old entry quoting
    the convention in its prose (#213's own entry does) is prose, not a
    marker.

    `unknown` is a first-class value, not a failure: it is the truthful
    origin of every post-cutoff task filed before this contract existed.
    """
    vocab = "origin: **human**, origin: **loop** or origin: **unknown**"
    checked = errors = 0
    for ids, body in ledger_entries(text):
        if not ids or max(ids) < ORIGIN_CUTOFF:
            continue
        checked += 1
        name = "/".join(f"#{i}" for i in ids)
        marks = [v.strip() for v in ORIGIN_MARK.findall(body)]
        if not marks:
            errors += 1
            rep.add(
                ERROR,
                "tasks.md",
                f"{name} has no origin — tasks from #{ORIGIN_CUTOFF} onward "
                f"record exactly one of {vocab} (`unknown` when it was never recorded)",
            )
        elif len(marks) > 1:
            errors += 1
            rep.add(
                ERROR,
                "tasks.md",
                f"{name} has {len(marks)} origin markers ({', '.join(marks)}) — "
                f"exactly one is the claim; two is none",
            )
        elif marks[0] not in ORIGIN_VALUES:
            errors += 1
            rep.add(
                ERROR,
                "tasks.md",
                f"{name} origin is **{marks[0]}** — the vocabulary is "
                f"human/loop/unknown, lowercase: exactly one of {vocab}",
            )
    if checked and not errors:
        rep.add(OK, "tasks.md", f"origin recorded on all {checked} entries from #{ORIGIN_CUTOFF} onward")


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


def check_run_mode(dw: Path, watch, rep: Report) -> None:
    """Main-dreamer run mode (#290).

    Same silent-fallback hazard as watch-tint: an unknown name is not a hard
    page failure, so lint is what says the file no longer matches what the
    server will accept. Reads RUN_MODES from watch.py — never restated.
    Absent is normal (default lackadaisical) and silent.
    """
    path = dw / "run-mode"
    if not path.exists():
        return
    raw = path.read_text().strip()
    names = list(getattr(watch, "RUN_MODES", ()) or ()) if watch else []
    if not names:
        rep.add(WARN, "run-mode", f"{raw!r} — unverified (watch.py unreadable)")
    elif raw not in names:
        rep.add(
            ERROR,
            "run-mode",
            f"{raw!r} is not one of {', '.join(names)} — the page falls back to "
            f"the default and nothing says his choice was dropped",
        )
    else:
        rep.add(OK, "run-mode", raw)


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


def check_submissions(dw: Path, rep: Report) -> None:
    """Everything he submitted, written before the loop could lose it (#199).

    The file exists because an answer that failed to match its entry was
    discarded with a 409 and recorded nowhere — his words, gone, on a path
    #116 proves is reachable. So this is the backup, and the check has to be
    careful not to punish it for doing its job.

    **A torn LAST line is a WARN, not an error.** A crash mid-append is
    precisely the situation the file is for; going red on it would mean the
    linter shouts loudest at the moment the log worked. A malformed line
    anywhere ELSE is a real error — it means a writer is emitting bad JSON
    rather than that a process died.

    Absent returns silently: a target where he has submitted nothing has no
    file, and that is the ordinary early state rather than a fault.
    """
    path = dw / "submissions.log"
    if not path.exists():
        return
    raw = path.read_text(encoding="utf-8", errors="replace")
    if not raw.strip():
        rep.add(OK, "submissions.log", "no submissions yet")
        return

    lines = raw.split("\n")
    torn = bool(lines[-1].strip())          # no trailing newline => partial
    if torn:
        rep.add(WARN, "submissions.log",
                "last line is incomplete — a crash mid-append, which is the case "
                "this file exists for; the lines before it are intact")
    body = lines[:-1] if torn else lines

    bad, n = [], 0
    for i, ln in enumerate(body, 1):
        if not ln.strip():
            continue
        try:
            rec = json.loads(ln)
        except ValueError:
            bad.append(f"line {i}: not JSON")
            continue
        if not isinstance(rec, dict):
            bad.append(f"line {i}: not an object")
            continue
        n += 1
        missing = [k for k in ("t", "path", "bytes") if k not in rec]
        if missing:
            bad.append(f"line {i}: missing {'/'.join(missing)}")
        if "bytes" in rec and not isinstance(rec["bytes"], int):
            bad.append(f"line {i}: bytes is not an int")
        has_req, has_raw = "req" in rec, "raw" in rec
        if has_req == has_raw:
            bad.append(f"line {i}: needs exactly one of req/raw")
        if has_raw != ("why" in rec):
            bad.append(f"line {i}: why must be present iff raw is")
        if rec.get("why") not in (None, "json", "decode"):
            bad.append(f"line {i}: why={rec['why']!r} not json/decode")
        if "truncated" in rec and rec["truncated"] is not True:
            bad.append(f"line {i}: truncated must be true when present")

    if bad:
        rep.add(ERROR, "submissions.log",
                f"{len(bad)} malformed record(s) — a reader recovering his words "
                f"cannot trust the file: {'; '.join(bad[:3])}")
    else:
        rep.add(OK, "submissions.log", f"{n} submission(s) recorded")


VERSION_TOKEN = re.compile(r"^(?:[0-9a-f]{12}|unknown)$")
FRONTMATTER_LINE = re.compile(r"^([a-z][a-z0-9-]*):\s*(.*)$")


def check_dreamwork_frontmatter(dw: Path, rep: Report) -> None:
    """#194 — DREAMWORK.md's version stamp, the thing the upgrade check
    compares `bin/ud-dw-githash` against.

    The file is the human's, so the survivable states stay WARN: no file,
    no frontmatter (a pre-#194 target), keys this check doesn't know. What
    goes red is a stamp that would lie to the comparison — identity must be
    exactly twelve hex or the word `unknown`, never the live dirty
    annotation, and a block that opens must close. A typoed key is caught
    by the required-key ERROR, not demoted to the absent-frontmatter WARN.
    """
    path = dw.parent / "DREAMWORK.md"
    if not path.exists():
        rep.add(WARN, "DREAMWORK.md", "absent — the loop has no recorded goals here")
        return
    lines = path.read_text().splitlines()
    if not lines or lines[0].strip() != "---":
        rep.add(
            WARN,
            "DREAMWORK.md",
            "no version frontmatter — the upgrade check reads blind until this target is stamped "
            "(migrations/2026-07-25-14-version-frontmatter.md)",
        )
        return
    try:
        close = next(i for i, ln in enumerate(lines[1:], start=1) if ln.strip() == "---")
    except StopIteration:
        rep.add(ERROR, "DREAMWORK.md", "frontmatter opens with --- and never closes — the whole file reads as metadata")
        return
    keys: dict[str, str] = {}
    for ln in lines[1:close]:
        m = FRONTMATTER_LINE.match(ln)
        if not m:
            rep.add(ERROR, "DREAMWORK.md", f"frontmatter line is not `key: value`: {ln!r}")
            return
        keys[m.group(1)] = m.group(2).strip()
    version = keys.pop("dreamwork-version", None)
    if version is None:
        rep.add(ERROR, "DREAMWORK.md", "frontmatter carries no dreamwork-version — it reads as stamped and says nothing")
        return
    if not VERSION_TOKEN.match(version):
        rep.add(
            ERROR,
            "DREAMWORK.md",
            f"dreamwork-version is {version!r} — must be exactly 12 hex chars or `unknown` "
            "(the FIRST TOKEN of ud-dw-githash output; a dirty `+N` is live state, not identity)",
        )
        return
    if keys:
        rep.add(WARN, "DREAMWORK.md", f"frontmatter keys this check does not know: {sorted(keys)} — fine, but grow the contract deliberately")
    rep.add(OK, "DREAMWORK.md", f"stamped {version}")


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
    check_answers(dw, watch, rep)
    check_tasks(dw, rep)
    check_status(dw, rep)
    check_watch_port(dw, rep)
    check_watch_tint(dw, watch, rep)
    check_run_mode(dw, watch, rep)
    check_plugin_commands(dw, watch, rep)
    check_submissions(dw, rep)
    check_skill_version(dw, rep)
    check_dreamwork_frontmatter(dw, rep)
    check_dreams(dw, rep)

    print(f"lint {dw}")
    print(rep.render())
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
