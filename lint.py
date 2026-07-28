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
import subprocess
import sys
from pathlib import Path

# #331: the ids-only bold span has ONE definition, in watch.py. We import it
# here rather than restating it, so this reader cannot drift from the parser's.
# `check_ledger_sections` already did `import watch` at function scope; this
# makes the module-level `LEDGER_ID` consume the same single core.
import watch

SKILL_DIR = Path(__file__).resolve().parent

ERROR, WARN, OK = "ERROR", "WARN", "OK"

DREAM_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{4}-[a-z0-9-]+\.md$")
# Built from watch.IDS_ONLY_SPAN (#331): one definition of an ids-only bold
# span, shared with watch.LEDGER_ENTRY and status_sync.LEDGER_HEAD. The head
# form (`^- **(<span>)**`) is pinned identical across all three readers by
# `test_ledger_entry_rule_has_exactly_one_copy`. Combined-aware: the span is
# ids only, so a head like `- **#7/#8**` names BOTH ids — callers extract
# each with ENTRY_ID rather than int() on the span (#315).
LEDGER_ID = re.compile(rf"^- \*\*({watch.IDS_ONLY_SPAN})\*\*", re.M)
NEXT_ID = re.compile(r"^Next id: \*\*(\d+)\*\*", re.M)
# #323: the repo keeps `close(#N):` / `merge(#N):` rigorously, so a commit
# subject is a usable signal that a task shipped. The trailing character class
# matters: without it `close(#31)` would answer for #3.
CLOSE_SUBJECT = re.compile(r"^(?:close|merge)\(#(\d+)[)/,]")
# #335: a completion keyword near a date or sha. The vocabulary is what a
# naive grep would reach for — and it matches five of 108 open entries when
# run across the whole entry, only one of which is real. The check's value
# is POSITION (inside the metadata run, not the body), not the vocabulary:
# `_metadata_clause` is what holds the four false positives silent.
COMPLETION_MARK = re.compile(
    r"\b(?:completed|landed|merged)\b"
    r".{0,40}?"
    r"(?:\d{4}-\d{2}-\d{2}|[0-9a-f]{7,})",
    re.IGNORECASE,
)

# ── task provenance, forward-only from the cutoff (#213) ──────────────
# The origin rule reads WHOLE entries (ENTRY_HEAD/ENTRY_ID below), not head
# lines, so combined entries (`- **#250/#251**`) are governed on either id.
# LEDGER_ID is pinned identical to watch.py's LEDGER_ENTRY by a test and is
# combined-aware for the same reason (#315): its bold span is ids only
# (`#7` or `#7/#8`). Callers that counted a captured digit run must now
# extract every id in the span — see check_tasks and check_ledger_sections.
ORIGIN_CUTOFF = 216
ORIGIN_VALUES = ("human", "loop", "unknown")
ENTRY_HEAD = re.compile(r"^- \*\*([^*]+?)\*\*")
ENTRY_ID = re.compile(r"#(\d+)")
# An origin claim is `origin: **value**`; the entry's lines are joined
# before matching, so a hard-wrapped marker (`origin:` ending a line, the
# value opening the next — #288 and #252 both do this) still reads.
ORIGIN_MARK = re.compile(r"origin:\s*\*\*\s*([^*]+?)\s*\*\*")

# #419: a blocked-on-human claim, same `key: **value**` idiom as origin/related.
# The marker names a KIND of blocker (a human decision), not a specific question
# — a task-blocker (`blocked on #352`) is a different relation and stays prose.
# Joined per-entry before matching, so it survives a hard wrap the way origin does.
BLOCKED_ON_HUMAN_MARK = re.compile(r"blocked-on:\s*\*\*\s*([^*]+?)\s*\*\*")
# A `gate:` companion naming where the ruling lives (the task whose question
# carries this decision), for the case the question does not carry the entry's
# own id — the #371 trap. Optional; absent defaults to the entry's own id.
GATE_MARK = re.compile(r"gate:\s*\*\*\s*([^*]+?)\s*\*\*")


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


def _metadata_clause(entry_text: str) -> str:
    """The ` · `-delimited tag run between the title and the body prose (#335).

    An entry's metadata is the chain of short tags following the title:
    `P1`, `incident`, `origin: **human**`, `owner: dreamer-x`, and similar.
    The same words deeper in the prose body are NOT metadata — four real
    open entries carry `landed`/`completed`/`merged` in their body for
    legitimate reasons (#275, #283, #269, #281), and a vocabulary rule that
    ignored position has precision 1-in-5.

    The boundary is structural, not lexical: the chain is a sequence of
    ` · `-separated tokens, and the body begins at the first token that
    reads as prose — one carrying a `;` (the punctuation the metadata run
    never uses), or too long to be a tag (> 50 chars). Measured on the five
    real entries: #261's `completed **2026-07-26 16:21**` token is 31 chars
    with no `;`, so it stays inside the chain; each false positive's keyword
    sits in a body token past the boundary.
    """
    flat = " ".join(ln.strip() for ln in entry_text.split("\n"))
    m = ENTRY_HEAD.match(flat)
    if not m:
        return ""
    rest = flat[m.end():]
    sep = re.match(r"\s*[—-]\s+", rest)
    if not sep:
        return ""  # no title separator: cannot locate the metadata run
    rest = rest[sep.end():]
    parts = rest.split(" · ", 1)
    if len(parts) < 2:
        return ""  # no ` · ` at all: title + body, no metadata chain
    tokens = []
    for tok in parts[1].split(" · "):
        tok = tok.strip()
        if not tok:
            continue
        if ";" in tok or len(tok) > 50:
            break
        tokens.append(tok)
    return " · ".join(tokens)


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


def check_answered_resolution_dates(dw: Path, watch, rep: Report) -> None:
    """How many answered entries the page renders with NO resolved date (#411).

    `answered_at(body)` returns when a folded entry was resolved, for the
    collapsed-row view. It is deliberately never-guessing — a wrong date is
    worse than no date — so an answered entry that returns None is one of two
    honest things: it was withdrawn (no answer, so no timestamp), or it predates
    the resolution-marker convention. Both are legitimate *today*. What this
    check exists to catch is the regression: a future fold that drops or
    mis-places the `→ answered (…)` marker on an entry that should carry one
    makes the date silently disappear, and nothing today would notice.

    So the number is DERIVED — never a literal — and it names the entries so a
    reader can tell a withdrawn entry from a dropped marker. WARN, not ERROR:
    a None that names a withdrawn ask is correct, and crying ERROR on the
    legitimate state would teach the reader to mute it. The check is the
    coverage this task's ledger entry asks for: "a count cannot silently stop
    counting" (#411).
    """
    path = dw / "questions.md"
    if not path.exists():
        return                          # check_questions owns the absent case
    if watch is None:
        return                          # cannot run the reader; nothing to assert
    try:
        items = watch.parse_answered(path.read_text())
    except Exception:
        return                          # check_questions owns unparseable
    undated = [it["title"] for it in items if watch.answered_at(it["body"]) is None]
    if not undated:
        # Silent when every answered entry carries a date. `check_questions`
        # already owns the OK row for this file, and emitting a second one
        # fragments the summary; the coverage this check exists to provide is
        # the WARN that names the undated entries, not an OK that duplicates it.
        return
    # Name at most three so the line stays readable; the count is the signal.
    sample = "; ".join(t[:48] for t in undated[:3])
    more = "" if len(undated) <= 3 else f"; +{len(undated) - 3} more"
    rep.add(
        WARN,
        "questions.md",
        f"{len(undated)} of {len(items)} answered entries have no resolution "
        f"date — a withdrawn ask carries none by design, but a dropped "
        f"`→ answered (…)` marker is a regression that otherwise hides: "
        f"{sample}{more} (#411)")


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


# #343: the SHAPE of an author tag, which is what makes this check quiet
# enough to be believed. Three parts, and each one was earned:
#   - a single leading word (`Note`, `Answer`, `Follow-up`) — hyphens allowed,
#     spaces not. This is what excludes prose that happens to parenthesise a
#     date, e.g. the real `- **Four early asks, all applied (2026-07-25)** —`
#     in this repo's questions.md, which was the check's only false positive
#     when first run against live data.
#   - a timestamp inside the parenthesis, which excludes ordinary bolded
#     bullets like `- **Option A (cheapest):**`.
#   - a colon immediately after the parenthesis, as every real tag has.
# Narrower than it could be, deliberately: a WARN that fires once wrongly per
# run teaches the reader to skip the ones that are right. The known cost is
# that a tag mangled so badly it loses its colon is missed; the wrong-NAME
# case this exists for keeps the shape and only changes the word.
DATED_TAG = re.compile(r"^\s*- \*\*[A-Z][A-Za-z-]* \([^)]*\d{4}-\d{2}-\d{2}[^)]*\):")


def check_author_tags(dw: Path, watch, rep: Report) -> None:
    """#343: a tag the RENDERER does not know silently deletes his words.

    `watch.py` recognises a contribution by an exact prefix (`NOTE_TAGS`,
    `ANSWER_TAGS`). A bullet spelled any other way is not a contribution: it
    falls into the entry BODY and renders as a `·` item with its raw tag
    visible as text and no author label — the #340 defect, reachable by a
    one-word typo, on the channel the loop depends on.

    The typo is natural because the two channels are spelled ASYMMETRICALLY:
    his is `Note (human, …)`, the loop's is `Follow-up (loop, …)`. `Note
    (loop, …)` reads perfectly reasonable and matches nothing. It was written
    on the P0 question gating five lanes an hour after a merge message
    explaining that `Answer (loop, …)` was the #254 bug for this exact reason
    — so knowing the failure by name demonstrably does not prevent it, and
    `lint.py` reported `clean` over it.

    The prefixes are READ FROM `watch.py`, never restated here. A second copy
    of the tag list is a second thing able to disagree with the renderer, and
    renderer-disagreement is the whole defect class; if watch.py gains a tag,
    this check must accept it the same day without being edited.

    WARN, not ERROR — same reasoning as #323 and #335: it names the line so a
    false positive is obvious. A case could be made for ERROR, since there is
    no legitimate reason to write a tag the renderer cannot read; it stays a
    WARN because a human hand-editing these files mid-thought should not be
    stopped, only told.
    """
    if watch is None:
        # the tuples belong to watch.py; without them there is nothing to
        # compare against, and inventing a fallback list here would be the
        # second copy this check exists to avoid
        return
    prefixes = tuple(p for p, _ in list(watch.NOTE_TAGS) + list(watch.ANSWER_TAGS))
    if not prefixes:
        return
    for name in ("questions.md", "answers.md"):
        path = dw / name
        if not path.exists():
            continue
        try:
            lines = path.read_text().splitlines()
        except OSError:
            continue
        bad = []
        for ln in lines:
            if not DATED_TAG.match(ln):
                continue
            s = ln.strip()
            if any(s.startswith(p) for p in prefixes):
                continue
            bad.append(s[:46].rstrip())
        if bad:
            rep.add(
                WARN, name,
                f"{len(bad)} bullet(s) carry an author tag the renderer does not "
                f"know, so they fall into the entry body with the tag showing and "
                f"no author label (#343/#340): {'; '.join(bad[:3])}"
                f" — the loop writes `- **Follow-up (loop, …)`, not `Note (loop, …)`",
            )


ANSWER_BULLET_STAMP = re.compile(r"\((?:via watch, )?(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})")


def check_unfolded_answers(dw: Path, watch, rep: Report) -> None:
    """#366: he answered, and the page kept asking for an hour.

    His #346 ruling — the one that turned over three of four recommendations —
    arrived at 01:23 and was still under `## Open` when it was folded at 02:27: one
    hour and four minutes, measured, not the "two hours" a first draft of this
    docstring claimed. For all of it the dashboard went on presenting a settled
    question beside three genuinely open ones, which is worse than a missing check:
    it spends the scarcest thing in the loop, his attention, on work already done.

    **He named the real fix himself**, minutes after seeing the fold: *"this shows
    why we need tooling i think (like cli) so that there's always a little status
    msg tacked on about that. then you will be prompted to check and can always
    know what is not folded in etc."* That is #357, and this check is only its
    interim half — it fires when someone runs `lint.py`, whereas he wants the
    count tacked onto every invocation, which is ambient rather than opt-in.

    Nothing could have caught it. `check_questions` verifies the file PARSES,
    `check_author_tags` verifies a tag is READABLE, and both were clean. Neither
    asks the question this one asks: **is there an answer sitting in a section
    reserved for the unanswered?**

    TWO faults, both found in the same fold, and they need different levels:

    - **An answer-tagged bullet under `## Open`** is an unfolded answer. WARN, and
      the message carries the AGE rather than merely the fact — because there is a
      legitimate window (his answer lands, the loop folds it on the next tick), and
      an ERROR firing inside that window would cry wolf on correct behaviour. Age
      is what distinguishes the window from the failure, so age is what it prints.
      The age comes from the bullet's own timestamp against the clock, so a
      one-minute-old answer reads differently from a two-hour-old one without
      needing two rules.
    - **Two answer bullets sharing one timestamp** is a duplicate delivery
      (#274's third witness: his answer landed twice, byte-identical, and
      `watch-events.log` carried the same `01:23:21` line twice). WARN and named
      as #274, because the duplication happens upstream of the file write — the
      loop can only clean it up, so refusing to commit would punish the wrong
      party.

    **Why the second is the one that could not be seen by reading**, which is why
    a check is the only defence: `_parse_entries` lifts EVERY answer-tagged bullet
    in `## Answered`, so both copies leave the contribution list and the rendered
    page is correct while the file is wrong.

    The tag prefixes are read from `watch.py` — never restated — for
    `check_author_tags`'s reason: a second copy of that list is a second thing able
    to disagree with the renderer, and renderer-disagreement is the defect class.
    """
    from datetime import datetime

    if watch is None:
        return
    answer_prefixes = tuple(p for p, _ in list(watch.ANSWER_TAGS))
    if not answer_prefixes:
        return
    path = dw / "questions.md"
    if not path.exists():
        return
    try:
        text = path.read_text()
    except OSError:
        return
    # THE RAW SECTION, not the parsed entries — and this cost a green red-run.
    # The first version of this check read `_parse_entries(text, "Open", False)`
    # and looked for the tag in `body`. It reported nothing over the real
    # two-hour-old file, because #340's fix makes an answer bullet in `## Open`
    # a CONTRIBUTION: the raw tag is stripped, the author label carries it, and a
    # parsed contribution cannot say whether it was an answer or a note. The
    # reader deliberately hides the one fact this check needs. So the scan is raw
    # — but the VOCABULARY still comes from `watch.ANSWER_TAGS`, so there is no
    # second copy of the thing that can disagree with the renderer.
    lines = text.split("\n")
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == "## Open")
    except StopIteration:
        return                      # check_questions owns a file with no sections
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("## ")), len(lines))
    now = datetime.now()
    per_entry: dict[str, list[str]] = {}
    order: list[str] = []
    title = None
    for ln in lines[start + 1:end]:
        if ln.startswith("- **"):
            title = ln[4:].strip().rstrip("*").strip()
            continue
        if title is None:
            continue
        if any(ln.strip().startswith(p) for p in answer_prefixes):
            if title not in per_entry:
                per_entry[title] = []
                order.append(title)
            m = ANSWER_BULLET_STAMP.search(ln)
            per_entry[title].append(m.group(1) + " " + m.group(2) if m else "")
    for title in order:
        stamps = [s for s in per_entry[title] if s]
        short = title[:56] + ("…" if len(title) > 56 else "")
        age = ""
        if stamps:
            try:
                oldest = min(datetime.strptime(s, "%Y-%m-%d %H:%M") for s in stamps)
                hours = (now - oldest).total_seconds() / 3600.0
                age = (" — answered %.0f minutes ago" % (hours * 60) if hours < 1
                       else " — answered %.1f hours ago" % hours)
            except ValueError:
                pass
        rep.add(WARN, "questions.md", (
            f"{short} is under `## Open` and already carries his answer{age}; the "
            f"dashboard is still asking a settled question beside the open ones — "
            f"fold it (#366)"))
        dupes = {s for s in stamps if stamps.count(s) > 1}
        for s in sorted(dupes):
            rep.add(WARN, "questions.md", (
                f"{short} carries {stamps.count(s)} answer bullets stamped {s} — a "
                f"duplicate delivery, and invisible once folded because every "
                f"answer bullet is lifted out of the body (#274)"))


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
    # LEDGER_ID captures an ids-only span (`#7` or `#7/#8`); a combined head
    # names every id in it, so extract each id with ENTRY_ID rather than
    # int() on the span itself, which would choke on the slash (#315).
    ids = [int(x) for m in LEDGER_ID.findall(text) for x in ENTRY_ID.findall(m)]
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
            rep.add(OK, "tasks.md", f"{len(ids)} ids, next id {nxt}")

    check_task_origins(text, rep)
    check_ledger_sections(text, rep)
    check_landed_still_open(dw, text, rep)
    check_self_completed_open(dw, text, rep)


def check_landed_still_open(dw: Path, text: str, rep: Report) -> None:
    """#323: git says it landed; the ledger still lists it under Open.

    `check_ledger_sections` compares the open COUNT between two readers, so
    it catches a miscount and never a task sitting in the wrong section —
    nothing compared the ledger against git at all. Three stale-opens turned
    up in one evening (#314, #156, #315), and the third was found by this
    check's own measurement rather than by anyone noticing, which is the
    argument for automating it: the failure is silent and it makes the queue
    overstate what is left, while the entries that SUPERSEDED the landed one
    read as unrelated work.

    **It WARNs and must never ERROR.** A close commit is strong evidence, not
    proof: #275 carries both a `close` and a `merge` and is legitimately open
    because its ask awaits his ruling, which is part of its definition of
    done (#306). An error would make an honest state unrepresentable, so this
    is a prompt to look, like the styleguide audit.

    THE DISCRIMINATION, which is the whole design. A prose keyword search was
    tried first and is wrong: #315's body contains "landed" while describing
    the *problem* (`#301 fixed the LANDED half`), so a keyword rule flags the
    stale case for the wrong reason and cannot separate it from a deliberate
    partial. The rule is instead **git names a close/merge commit that the
    entry does not name**. That works because an entry which deliberately
    stays open after a landing already cites its commit — measured on the
    three real cases: #315 (commit `4b69196`, uncited → flagged, correctly),
    #269 (`e383492`, cited → silent, correctly), #275 (`4b49ecb`, cited →
    silent, correctly).

    A target that is not a git repository is skipped in silence. The loop runs
    on projects that may not be under git at all, and "cannot check" must not
    render as "nothing to fix".

    **#363 — the message carries WHEN, because the reader was the failure mode.**
    This check fired correctly three times in one night and a coordinator
    overrode it from memory each time — *"that is another session's live lane"* —
    and was right only the first. #334's work had merged at 01:39; the override
    continued for an hour past that, and its worktree surviving is what made the
    wrong answer feel true. Softening the wording was proposed and then withdrawn
    by trying to build it: a liveness signal would have printed "another lane is
    mid-flight" for that whole hour, which is worse than a blunt message, and a
    softened WARN is one nobody re-checks. What the entry asks for instead is
    that the reader "check git, which takes one command" — so the check runs the
    command and prints the answer. An override now has to be made against a
    timestamp and an age rather than against a bare sha.
    """
    # `\x1f` rather than a space, because `%cr` is itself spaced ("3 hours ago")
    # and a space-split would have to know how many fields to expect.
    try:
        out = subprocess.run(
            ["git", "-C", str(dw.parent), "log", "--format=%h\x1f%cI\x1f%cr\x1f%s"],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return
    if out.returncode != 0:
        return  # not a repo, or no commits yet: nothing to compare against

    # id -> [(sha, when, ago)] for its close/merge commits. The trailing class
    # stops `close(#31)` from answering for #3, which a bare prefix match would.
    closed: dict[int, list[tuple[str, str, str]]] = {}
    for line in out.stdout.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 4:
            continue
        sha, iso, ago, subject = parts
        m = CLOSE_SUBJECT.match(subject)
        if m:
            # `%cI` is `2026-07-28T01:39:02+10:00`; the minute is as precise as
            # this needs to be and the timezone is noise for a local reader.
            closed.setdefault(int(m.group(1)), []).append(
                (sha, iso[:16].replace("T", " "), ago))
    if not closed:
        return

    # Slice the Open section rather than teaching `ledger_entries` about
    # headings: it is a shared helper with its own pinned tests, and a second
    # caller's need is a poor reason to widen it.
    lines = text.splitlines()
    start = end = None
    for n, ln in enumerate(lines):
        if ln.strip().startswith("## "):
            if ln.strip() == "## Open":
                start = n + 1
            elif start is not None:
                end = n
                break
    if start is None:
        return
    open_text = "\n".join(lines[start:end])

    stale: list[str] = []
    acknowledged = 0
    for ids, body in ledger_entries(open_text):
        for tid in ids:
            landings = closed.get(tid)
            if not landings:
                continue
            if any(sha in body for sha, _, _ in landings):
                acknowledged += 1       # a deliberate partial: it cites its commit
            else:
                # #363: the AGE is the part that argues. The evidence goes in the
                # message so the reader does not have to run `git log` to weigh
                # it — see the docstring for why that is the whole fix.
                evidence = ", ".join(
                    f"`{sha}` {when}, {ago}" for sha, when, ago in landings)
                stale.append(f"#{tid} ({evidence})")
    for name in stale:
        rep.add(
            WARN,
            "tasks.md",
            f"{name} is under `## Open` but git already has a close/merge commit "
            f"for it that the entry does not name — either fold it into "
            f"`## Recently landed`, or, if it is deliberately still open, cite "
            f"that commit in the entry the way #269 and #275 do (#323)",
        )
    if acknowledged and not stale:
        rep.add(OK, "tasks.md",
                f"{acknowledged} open entr{'y' if acknowledged == 1 else 'ies'} "
                f"cite the landing that would otherwise look stale")


def check_self_completed_open(dw: Path, text: str, rep: Report) -> None:
    """#335: an entry under `## Open` that declares ITSELF completed in its
    metadata run.

    #261 sat open for a full day carrying `completed **2026-07-26 16:21**`
    in the ` · `-separated chain after its title — the same run that carries
    `P1`, `origin:` and `owner:`. `check_landed_still_open` (#323) cannot see
    this class: it compares the ledger against git and warns when a
    `close(#N)`/`merge(#N)` commit is uncited, but #261 was closed in PROSE,
    with no such commit to name, so it was structurally invisible.

    **The discrimination is POSITION, not vocabulary, and it was measured.**
    A keyword grep for `completed|landed|merged` near a date or sha across
    the 108 open entries returns five hits and only one is real — precision
    1-in-5. The four false positives (#275, #283, #269, #281) each carry the
    keyword deep in the prose body for a legitimate reason (a partial
    landing, a sub-stage, a sha cited for a sub-finding). So the rule is: a
    completion marker inside the entry's **metadata clause** is a self-
    declared close; the same words in the body are not. `_metadata_clause`
    above draws that boundary.

    **WARN, never ERROR** — same reasoning as #323: strong evidence worth a
    look, not a gate. The message names the id and the phrase it matched, so
    a false positive is obvious rather than a mystery. Degrades silently on a
    ledger with no `## Open`, an empty one, or a missing file, exactly as
    `check_landed_still_open` does.
    """
    lines = text.splitlines()
    start = end = None
    for n, ln in enumerate(lines):
        if ln.strip().startswith("## "):
            if ln.strip() == "## Open":
                start = n + 1
            elif start is not None:
                end = n
                break
    if start is None:
        return
    open_text = "\n".join(lines[start:end])

    for ids, body in ledger_entries(open_text):
        clause = _metadata_clause(body)
        if not clause:
            continue
        m = COMPLETION_MARK.search(clause)
        if not m:
            continue
        # Extract the full ` · `-delimited token containing the match, so the
        # message reads as a complete phrase (e.g. `completed **2026-07-26
        # 16:21**`) rather than a regex substring cut mid-token.
        s = clause.rfind(" · ", 0, m.start())
        s = s + 3 if s != -1 else 0
        e = clause.find(" · ", m.end())
        e = e if e != -1 else len(clause)
        phrase = clause[s:e]
        name = "/".join(f"#{i}" for i in ids)
        rep.add(
            WARN,
            "tasks.md",
            f"{name} is under `## Open` but its metadata run carries "
            f"`{phrase}` — a completion marker in the ` · ` chain after "
            f"the title is a self-declared close; either fold it into "
            f"`## Recently landed`, or, if it is deliberately still open, "
            f"strike that marker from the metadata run (#335)",
        )


def check_landed_asks(dw: Path, watch, rep: Report) -> None:
    """#306: an ask whose subject has already shipped is not a gate.

    #290 was authorized by the human in `answers.md` and its implementation
    landed and deployed, while the P1 question sat in `questions.md` Open for
    ~15 hours — because the answering commit wrote the answer channel and the
    ledger and never touched the ask channel. The two do not cross-reference,
    and an ask whose subject has landed looks exactly like one still waiting,
    so a coordinator handoff had to carry a hand-written "this question is
    stale" caveat. That is a human remembering in place of a tool checking.

    **All** named ids must be landed, not any. The naive any-landed rule was
    measured against this repo first and fired on the real `#229/#270 topic
    chats v2` question, where #270 had landed but #229 was still open and the
    ask was genuinely live. A check that cries wolf on a live question teaches
    the reader to ignore it, which is worse than no check.

    WARN, not ERROR: an amendment thread on a landed task is legitimate, and
    this cannot tell one from a forgotten fold. It names the id and asks for a
    fold or a reopen — and says so precisely, because those are the only two
    that clear it. It reads titles, so a prose "still open because…" note in the
    body cannot silence it; the message used to suggest exactly that, which
    would leave the entry warning forever and teach the reader to ignore the
    check, the failure this docstring opens by naming. Caught the first time it
    fired on real work: the coordinator closed #275 in the ledger while its
    six-question ask was live, and the honest remedy was the reopen — that
    task's own terms make approval part of done.

    The actual cure — one write path that folds the ask when the answer is
    recorded — belongs to #263's event journal; this is only the detector.
    """
    qpath, tpath = dw / "questions.md", dw / "tasks.md"
    if watch is None or not qpath.exists() or not tpath.exists():
        return
    try:
        _open_ids, landed = watch.parse_ledger(tpath.read_text())
        asks = watch.parse_open_questions(qpath.read_text())
    except Exception:
        return  # the shape checks above own reporting an unreadable file
    if not landed:
        return

    for entry in asks:
        ids = re.findall(r"#(\d+)", entry.get("title", ""))
        if ids and all(i in landed for i in ids):
            rep.add(
                WARN,
                "questions.md",
                f"open ask names only landed task(s) {', '.join('#' + i for i in ids)}"
                f" — fold the ask, or reopen the task; a note in the body cannot"
                f" clear this, only the title is read (#306)",
            )


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
    Two readers of one file must not diverge; the repo pins LEDGER_ID to
    watch's LEDGER_ENTRY for the same reason, and both are combined-aware
    so a head like `- **#7/#8**` counts BOTH ids in BOTH readers (#315).
    """
    # Count open IDS, not open LINES: parse_ledger returns an id SET, and a
    # combined head (`- **#7/#8**`) names two ids on one line. Counting lines
    # would make this reader see 1 where parse_ledger sees 2 — the exact
    # disagreement widening one reader alone produces (#315). LEDGER_ID
    # captures the ids-only span; ENTRY_ID reads each id in it.
    section, mine = None, 0
    for ln in text.splitlines():
        stripped = ln.strip()
        if stripped.startswith("## "):
            section = stripped
        elif section == "## " + "Open":
            m = LEDGER_ID.match(ln)
            if m:
                mine += len(ENTRY_ID.findall(m.group(1)))
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
            f"open-id count disagrees: this linter counts {mine}, "
            f"watch.parse_ledger sees {len(theirs)} — a section heading is "
            f"probably quoted inside an entry, which moves where the open "
            f"section is thought to end (#304)",
        )
    else:
        rep.add(OK, "tasks.md", f"section split agrees with watch.py at {mine} open ids")


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


def _question_id_sets(watch, qpath: Path):
    """The ids a questions.md file names in each section, via the real parser.

    Returns ``(open_ids, answered_ids)`` as sets of ints, or ``(None, None)``
    when the file or parser is unavailable — callers treat None as "cannot
    correlate" and stay silent, the idiom every cross-file check here follows
    for an absent reader.
    """
    if watch is None or not qpath.exists():
        return None, None
    try:
        text = qpath.read_text()
        open_ids = set()
        for it in watch.parse_open_questions(text):
            open_ids |= {int(x) for x in re.findall(r"#(\d+)", it.get("title", ""))}
        answered_ids = set()
        for it in watch.parse_answered(text):
            answered_ids |= {int(x) for x in re.findall(r"#(\d+)", it.get("title", ""))}
    except Exception:
        return None, None
    return open_ids, answered_ids


def check_human_blocker(dw: Path, watch, rep: Report) -> None:
    """#419 — no human blocker without a question, made checkable.

    He tried to rule on `#264` and found no question to act on: the loop had
    reported itself blocked on him while no `questions.md` entry existed. His
    words: *"there always has to be an answer in our data."* The invariant is
    that every open task whose blocker is a human decision has a question that
    is **open** or **answered-but-unfolded**. Both are legitimate; **absent is
    not.**

    A task cannot currently SAY it is blocked on a human — entries express it in
    prose — and prose is not checkable, so this reads a `blocked-on: **human**`
    marker in the metadata chain (same idiom as `origin:` / `related:`). The
    marker is forward-only, not a retrofit, so **absence means "no claim", never
    "unblocked"**: an entry without one is simply not making a machine-readable
    claim, and the check says nothing about it. That is the brief's explicit
    requirement, and the alternative — a check over prose keyword matching — is
    the hollow-check failure this repo has spent a day learning to distrust.

    ONE direction is enforced:

    - **Direction 1 (ERROR): "there always has to be an answer in our data."** An
      open entry carries `blocked-on: **human**`, and NO question (open or
      answered) names the gate id — the `gate:` value if present, else the
      entry's own id. **Transitive coverage does NOT count.** A neighbouring
      task's question covering the same decision does not satisfy an entry whose
      own id has none, because a reader landing on the entry alone cannot find
      it — the #371 trap. Name the neighbour with `gate:` and the check follows
      it there.

    **Direction 2 ("he ruled and nobody processed it") is deliberately NOT
    implemented.** The brief's amendment (16:23) retracted the #371 specimen: a
    ruling that *answers* a decision does not *authorise* the work — "answered ≠
    authorised." His Q2 amended a design whose implementation was a
    separately-gated increment, so reading the landed answer as a green light was
    the exact error `7c5fc82` made and `6ea8f6b` retracted. The other three
    specimens are non-defects too (#254 deliberate partial, #367 in progress, #50
    authorised-but-not-started). A Direction-2 rule built on "the gate's question
    is answered" rests on a false equivalence, and the live repo measures the
    cost: the prose form `blocked on #N` where N is answered fires on 11 open
    entries, all 11 legitimate task dependencies on N's *work* landing. #371
    itself is among the eleven. A WARN that fires 11 wrong and 0 right is the
    hollow-check this repo refuses, so Direction 2 is refused. Catching "ruled
    but unprocessed" needs a mechanism that records *authorisation*, not one that
    infers it from a question's section heading.

    The correlation set comes from the REAL parser — `parse_open_questions` /
    `parse_answered` for the titles — never a second copy. Every count printed is
    derived at runtime. Silent on a missing ledger, a missing questions.md, or an
    unimportable watch (cannot correlate ⇒ say nothing), exactly as
    `check_landed_asks` degrades.
    """
    tpath = dw / "tasks.md"
    if not tpath.exists():
        return
    # Slice the Open section once, the idiom check_landed_still_open uses, so
    # only OPEN entries are governed — a landed entry is not "blocked on him".
    lines = tpath.read_text().splitlines()
    start = end = None
    for n, ln in enumerate(lines):
        if ln.strip().startswith("## "):
            if ln.strip() == "## Open":
                start = n + 1
            elif start is not None:
                end = n
                break
    if start is None:
        return
    open_text = "\n".join(lines[start:end])

    open_ids, answered_ids = _question_id_sets(watch, dw / "questions.md")
    if open_ids is None:
        # Cannot correlate without the question reader — say nothing rather
        # than claim every marked entry is fine (the hollow-pass this repo
        # keeps refusing).
        return

    marked = 0
    d1_errors = 0
    for ids, body in ledger_entries(open_text):
        # The marker is anchored the way `related:` is — `blocked-on:` at a `·`
        # boundary or line start — so quoting the vocabulary in prose (which the
        # #419 entry itself does) does NOT manufacture a phantom marker. We read
        # only the metadata clause, never the whole entry, for the same reason
        # `check_self_completed_open` reads position and not vocabulary.
        clause = _metadata_clause(body)
        clause_flat = re.sub(r"\s+", " ", clause)
        marks = [v.strip() for v in BLOCKED_ON_HUMAN_MARK.findall(clause_flat)]
        if not marks:
            continue  # no machine-readable claim; absence is "no claim", not "unblocked"
        marked += 1
        name = "/".join(f"#{i}" for i in ids)
        # Vocabulary: one value, human. Wrong case / extra values are a claim a
        # reader would have to interpret, same reasoning as the origin marker.
        vals = [v for v in marks if v != "human"]
        if vals:
            d1_errors += 1
            rep.add(
                ERROR, "tasks.md",
                f"{name} is blocked-on: **{vals[0]}** — the vocabulary is exactly "
                f"`human`; a task-blocker stays in prose (`blocked on #N`), this "
                f"marker names a human decision (#419)")
            continue
        # Resolve the gate: the `gate:` value if present, else the entry's own
        # ids. An entry may legitimately carry several own ids; any of them
        # having a question satisfies Direction 1.
        gate_match = GATE_MARK.search(clause_flat)
        if gate_match:
            gates = [int(x) for x in ENTRY_ID.findall(gate_match.group(1))]
        else:
            gates = []
        if not gates:
            gates = list(ids)
        # Direction 1: no question (open or answered) names any gate id. This is
        # the load-bearing half — "there always has to be an answer in our data".
        if not any(g in open_ids or g in answered_ids for g in gates):
            d1_errors += 1
            gate_desc = ", ".join(f"#{g}" for g in gates)
            rep.add(
                ERROR, "tasks.md",
                f"{name} is marked blocked-on: **human** but no questions.md "
                f"entry names {gate_desc} — blocked on him with nothing on the "
                f"channel to him; file the question, or name the ruling's "
                f"neighbour with `gate:`. \"there always has to be an answer in "
                f"our data\" (#419)")
            continue
        # NOTE: Direction 2 (gate answered ⇒ stall) is deliberately absent. See
        # the docstring: "answered ≠ authorised", and the prose form fires 11/11
        # false positives on the live repo. Do not re-add it without a mechanism
        # that records AUTHORISATION rather than inferring it from a section.
    # Coverage, derived not pinned, so a check that stops examining entries
    # cannot look the same as one that examined them all (#395 idiom).
    if marked and not d1_errors:
        rep.add(
            OK, "tasks.md",
            f"{marked} of {len(open_ids)} open entries marked blocked-on-human "
            f"all have a question (#419)")


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
    # `push` is the loop's report on its own channel to the human (#190). It is
    # a nested object whose shape check_status_push validates below; the
    # top-level type guard here catches a writer that put a string or list
    # where the object belongs, which would make every reader of it throw or
    # render nonsense — the same failure shape every other row here guards.
    "push": dict,
    # Which tasks the loop claims, as ids rather than prose (#332). The list
    # type is guarded here; that its ELEMENTS are integers is guarded by
    # check_status_task_ids, because that is the mistake a writer actually
    # makes and this table cannot see inside a list.
    "current_task_ids": list,
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


# #402b — the id vocabulary. A plain id is an integer (`263`); a sub-id is a
# string of digits then one letter (`"392a"`); a quoted plain id (`"263"`) is
# always wrong. This mirrors the hand-off id grammar (`watch.HANDOFF_ID_TOKEN`,
# `#401`) — `\d+[a-z]?` — so there is ONE sub-id shape across the two surfaces
# rather than a second definition a future writer must keep aligned. A live
# set legitimately holds int and str at once (status_sync._normalise_live keeps
# the string form by design, #402a), so this accepts the sub-id and rejects
# only the quoted-plain shape that matches no task row.
SUB_ID = re.compile(r"^\d+[a-z]$")


def _is_sub_id(v: object) -> bool:
    """True for a legitimate sub-id string (``"392a"``), False otherwise."""
    return isinstance(v, str) and SUB_ID.match(v) is not None


def _bad_ids(value: object) -> list[str]:
    """The ill-typed members of a task-id list, rendered for a human.

    A member is BAD when it is neither a plain int nor a sub-id string: a
    quoted plain id (``"263"``), a bool, a float, or a malformed string.
    `type(v) is not int` rather than `isinstance` on purpose: `isinstance(True,
    int)` is True in Python, so the natural spelling waves a bool through. That
    is not a hypothetical here — the sibling field `in_flight` was written as a
    bool by this very loop, and the dashboard rendered `doing: true` for forty
    minutes before #327 caught it. A bool arriving in this list is the same
    writer making the same slip one key over.

    A sub-id string (``"392a"``) is NOT bad: `current_task_ids` can
    legitimately carry one (#402b), because a lane may be `#392a` and
    `status_sync` derives the field from that `task` value. Only a quoted PLAIN
    id (``"263"``) is bad — it looks right, reads right to a human, and matches
    no task row, silently.
    """
    if not isinstance(value, list):
        return []          # the list-ness of the field is STATUS_TYPES' job
    return [repr(v) for v in value
            if type(v) is not int and not _is_sub_id(v)]


def check_status_task_ids(dw: Path, rep: Report) -> None:
    """#332 — the loop's claim about WHICH tasks it is on, machine-readably.

    `/tasks` (#281) puts an "in progress" badge on the rows the loop claims,
    and it has to decide per row whether this is one of them. The prose in
    `task` cannot answer that: one sentence routinely names several ids in
    different states ("folding #281's answer, #326 next"), so a reader
    scraping ids out of it would badge the wrong rows. Hence
    `current_task_ids` at the top level and `task_ids` per agent, both arrays
    of ints.

    Both are OPTIONAL, like every other field here — a loop that has not
    adopted them yet is not broken, and the badge simply does not render. What
    is not tolerable is a field that is PRESENT and stringly typed: `"#281"`
    or `"281"` where `281` belongs looks right in the file, reads right to a
    human, survives JSON validation and the type table above, and then matches
    no row at all. Every `in` test against a list of ints quietly returns
    False, so the badge never appears and nothing anywhere says why. That is
    the silent-data-loss shape this file calls an ERROR, so it is one.
    """
    path = dw / "status.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return             # check_status already reported it
    if not isinstance(data, dict):
        return

    problems = []
    bad = _bad_ids(data.get("current_task_ids"))
    if bad:
        problems.append(f"current_task_ids has non-integer member(s) {', '.join(bad)}")

    agents = data.get("agents")
    if isinstance(agents, list):
        for a in agents:
            if not isinstance(a, dict):
                continue
            bad = _bad_ids(a.get("task_ids"))
            if bad:
                name = a.get("name") or "<nameless>"
                problems.append(
                    f"agent {name}: task_ids has non-integer member(s) {', '.join(bad)}")

    if problems:
        rep.add(ERROR, "status.json", "; ".join(problems) +
                " — a plain id is an integer (263) and a sub-id is a string "
                "(\"392a\"); a quoted plain id (\"263\") matches no task row, "
                "silently")


def check_status_agrees_with_ledger(dw: Path, watch, rep: Report) -> None:
    """#362 — the two halves of one fact, and they had already drifted.

    `status.json` states queue depth and which tasks are in flight; `tasks.md`
    IS queue depth and what is in flight. Two files holding two halves of one
    fact, which `lessons.md` (#306) says to assume have already drifted — and
    they had, in both fields, at the moment this was written:

    - `queue` summed to **115** while `parse_ledger` read **123** open. Nothing
      compared them, so eight tasks of drift accumulated silently across a night
      of hand-maintained edits.
    - `current_task_ids` was `[]` while `agents[].task_ids` named three tasks in
      flight. `check_status_task_ids` above validates member TYPES and passes an
      empty list, so `[]` lints clean — and `file-formats.md` says `/tasks`
      badges rows from that field, so #281 would have shipped badging nothing.

    Both are WARNs, not ERRORs, and the distinction is the whole design:
    `status.json` is a projection of a live process, written best-effort on a
    tick, and the loop is explicitly told that failing to write it must never
    block. A momentary lag while an increment is mid-flight is normal and
    truthful; crying red on it would punish the loop for the honesty this file
    exists to provide. What is not truthful is drift nobody ever measures, and a
    WARN measures it.

    The `current_task_ids` case is a CONTRADICTION rather than a lag, so it is
    reported whatever the numbers say: a loop that knows three agents' task ids
    cannot simultaneously not know which tasks are current. It is silent when
    the field is absent, because absent means "not adopted" by this file's
    contract, and silent when `agents` is absent for the same reason.
    """
    path = dw / "status.json"
    tasks = dw / "tasks.md"
    if not path.exists() or not tasks.exists():
        return
    try:
        data = json.loads(path.read_text())
        text = tasks.read_text()
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(data, dict):
        return
    open_ids, _ = watch.parse_ledger(text)

    queue = data.get("queue")
    if isinstance(queue, dict):
        counts = [v for v in queue.values() if isinstance(v, int)]
        if len(counts) == len(queue) and counts:
            total = sum(counts)
            if total != len(open_ids):
                rep.add(WARN, "status.json", (
                    f"queue sums to {total} but the ledger has {len(open_ids)} open "
                    f"entries ({total - len(open_ids):+d}) — two files holding two "
                    f"halves of one fact drift, and nothing measured this one "
                    f"until #362"))

    current = data.get("current_task_ids")
    agents = data.get("agents")
    if isinstance(current, list) and not current and isinstance(agents, list):
        owned = sorted({i for a in agents if isinstance(a, dict)
                        for i in (a.get("task_ids") or []) if isinstance(i, int)})
        if owned:
            rep.add(WARN, "status.json", (
                f"current_task_ids is empty while agents claim {owned} — a loop that "
                f"knows its agents' task ids cannot not know which tasks are current, "
                f"and `/tasks` badges rows from this field, so it would badge nothing "
                f"(#362)"))


def check_status_push(dw: Path, rep: Report) -> None:
    """#190 — the loop's push-channel health, as written into status.json.

    `attn` died with a 403 for an entire afternoon and nothing made the loop
    notice: it reported progress into a transcript the human was not reading
    while the channel it believed had escalated sat refused. The dashboard is
    the only surface left that can say so, and `status.json`'s `push` object
    is how it learns. So a `push` the dashboard cannot read is exactly the
    silent class this file exists for — the loop thinks it reported a fault
    and the page renders nothing.

    Three states are distinguishable from the DATA, and lint must accept all
    three: no `push` key (never tried), `ok:true` (last landed), `ok:false`
    (last failed). A failed push is a TRUTHFUL runtime claim, not a broken
    file, so it lints clean — crying red on it would punish the loop for
    reporting the very fault this field exists to surface. Only a wrong TYPE
    is a writer bug worth catching.

    The `at` stamp follows the same clock rule as `last_tick`: a dashboard
    whose thesis is liveness must not render an invented time, and two agents
    have already written future timestamps by estimating elapsed time. A
    future `at` makes "failed 4m ago" a lie.

    Unknown subfields are tolerated — `status.json`'s key list is a MENU not a
    whitelist (#310), and that rule descends into `push`: the loop may grow
    the object (a fallback channel, a retry count), and a check that rejected
    the first addition would red the day it shipped.
    """
    path = dw / "status.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return  # check_status already reported it
    if not isinstance(data, dict):
        return
    p = data.get("push")
    if p is None or not isinstance(p, dict):
        return  # absent is one of the three states; a non-dict is caught by STATUS_TYPES

    want = {"at": str, "channel": str, "ok": bool, "detail": str}
    wrong = [
        f"push.{k} is {type(p[k]).__name__}, want {t.__name__}"
        for k, t in want.items()
        if k in p and not isinstance(p[k], t)
    ]
    if wrong:
        rep.add(ERROR, "status.json", "; ".join(wrong) +
                " — the dashboard cannot read the push-channel state")
        return

    at = p.get("at")
    if isinstance(at, str):
        skew = _future_skew(at)
        if skew is not None and skew > 60:
            rep.add(
                ERROR,
                "status.json",
                f"push.at is {int(skew // 60)}min in the FUTURE — read the clock, "
                f"do not estimate; a wrong `at` makes 'failed Nm ago' a lie",
            )
            return


STATUS_KEYS_HEADER = (
    "# Top-level `status.json` keys this target has been seen to carry (#303).\n"
    "# APPEND-ONLY, and deliberately so: see lint.py's check_status_keys.\n"
    "# A key you meant to retire is removed by editing THIS file, by hand.\n"
)


def check_status_keys(dw: Path, rep: Report) -> None:
    """Notice a `status.json` that lost keys it used to carry.

    A coordinator's wholesale rewrite dropped `retired_today` — fifteen prior
    lanes' retirements — and lint called the result clean, because a projection
    missing a key is indistinguishable from one that never had it. So the
    "used to carry" half has to live somewhere, and #303 refuted the
    git-tracked route: the only tracked description of this file is
    `file-formats.md`'s field table, which does not name `retired_today` (it
    would have missed the very incident that filed this) and which, treated as
    required, would red-flag every fresh target whose status.json is nearly
    empty by design.

    So the memo is a gitignored sidecar beside the gitignored file it
    describes, and it costs `lint.py` its read-only character — the one real
    price, paid deliberately.

    **It is append-only, and that is the load-bearing part.** The obvious
    implementation records the current key set each run, which means the first
    run after a bad rewrite adopts the REDUCED set as the new baseline and the
    loss is invisible from the second run on. That yields exactly one warning,
    in the same run as the mistake, and then silence — worse than no check,
    because it looks like a check. Union-only means a lost key keeps warning
    until a human edits the memo, which is the only act that should be able to
    say "yes, that key is gone on purpose".
    """
    path, memo_path = dw / "status.json", dw / ".status-keys"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return  # check_status already reported it; do not learn from a broken file
    if not isinstance(data, dict):
        return
    current = set(data)

    remembered: set[str] = set()
    if memo_path.exists():
        try:
            remembered = {
                ln.strip()
                for ln in memo_path.read_text().splitlines()
                if ln.strip() and not ln.lstrip().startswith("#")
            }
        except OSError as exc:
            rep.add(WARN, ".status-keys", f"unreadable ({exc.strerror}) — cannot tell if a key was lost")
            return

    lost = sorted(remembered - current)

    union = remembered | current
    if union != remembered:
        try:
            memo_path.write_text(STATUS_KEYS_HEADER + "".join(f"{k}\n" for k in sorted(union)))
        except OSError as exc:
            # Never fail the loop over a memo, but never claim to be watching
            # something we could not record either.
            rep.add(WARN, ".status-keys", f"could not record {len(union - remembered)} new key(s): {exc.strerror}")
            return

    if lost:
        rep.add(
            WARN,
            "status.json",
            f"lost {len(lost)} key(s) it used to carry: {', '.join(lost)} — a wholesale "
            f"rewrite drops what it does not restate; if deliberate, delete them from "
            f"`.dreamwork/.status-keys`",
        )
    else:
        rep.add(OK, ".status-keys", f"{len(union)} known key(s), none lost")


GUARDS_LIST = re.compile(r'DEFAULT_GUARDS="([^"]*)"')

# `.mjs` files in dev/capture/ that are deliberately not guards. Each is either
# a capture tool the human runs to LOOK at something, a one-off trace kept for
# its technique, or the shared helper. Named explicitly rather than pattern-
# matched, because a heuristic that guessed would have to guess wrong in one of
# the two possible directions: declare a real guard non-load-bearing, or nag
# about a helper on every run until nobody reads the warning.
NOT_GUARDS = frozenset({
    "report",                                    # shared exit-handler helper
    # Shared DOM reader for the dock guards, not a guard: it asserts nothing and
    # gates nothing. It exists because docktarget and noteprop both had to ask
    # "is this still the question I docked?" of rendered text, and #385 put a live
    # age inside that headline -- one copy of the strip-the-age rule, so the next
    # thing added to a headline cannot red two guards again. (#413)
    "dom",
    "beautycap", "cmdcap", "menucap", "reviewcap",  # capture tools, for looking
    "indtrace", "optrace", "rm-check2", "note82", "pip83", "worldspace",
    # A measurement, not a guard: it renders prototype geometry against a COPY of a
    # built artifact and prints numbers. It gates nothing because there is nothing
    # yet to gate — #367 increment 2 has no shipped CSS. When that lands, its real
    # guard is a separate file and this stays a measurement. (#367)
    "marktab-geometry",
    # A tool, not a guard: it takes a path and measures whichever artifact you
    # hand it, so it has no fixed subject to gate and binds no port. It is the one
    # shared above-the-fold check that review briefs cite, replacing the inline
    # copy each lane used to write.
    #
    # The `#ask` contract now exists (#436): `review_artifact.py` refuses a
    # source that is neither a meaningful `#ask` nor a `no_ask:` exemption, and
    # every current artifact carries the choice as a `<meta>` in its head. All
    # 11 src/-having artifacts were retrofitted and now carry a real `#ask`.
    # The 12 untemplated artifacts predate the contract, have no `src/` to
    # rebuild from, and cannot be hand-edited (generated output); they are the
    # declared-migration class. A walking guard would red on those 12 unless it
    # skipped them by `classify` first, so the guard stays unregistered until
    # the untemplated migrate or a skip-by-class guard is written. This file
    # stays the tool that guard calls. (#429, #430, #436)
    "above_fold",
})


def check_guards_registered(root: Path, rep: Report) -> None:
    """A guard file that is not in `DEFAULT_GUARDS` gates nothing (#377).

    #117 named this once and it has happened four times since. `filehead` and
    `fileview` arrived with seven named red proofs each and were deliberately
    left unregistered — "one line, still not mine" — and `fileimg` (#336) and
    `qfade` (#326) had been outside the list since they were written. All four
    PASS when invoked by hand, which is precisely why nobody noticed: in a
    report, a guard that works and a guard that runs look the same.

    Two directions, and both are real. A file with no entry is a check nothing
    invokes. An entry with no file is a runner line that either errors or is
    skipped depending on the recipe, and it survives a rename of the guard it
    named.

    This does not classify. `NOT_GUARDS` is a hand-maintained list, so adding a
    `.mjs` to that directory forces exactly one cheap decision: register it, or
    say here why it is not a guard. That decision is the whole value — the four
    misses above were all made by someone who never had to make it.

    `root` is the skill directory (where the justfile lives), not `.dreamwork/`.
    """
    justfile = root / "justfile"
    if not justfile.exists():
        return
    found = GUARDS_LIST.search(justfile.read_text(encoding="utf-8"))
    if not found:
        rep.add(WARN, "justfile",
                "no DEFAULT_GUARDS assignment found — the guard runner's list is "
                "the only thing that decides which guards actually run")
        return
    registered = set(found.group(1).split())
    capture = root / "dev" / "capture"
    files = {p.stem for p in capture.glob("*.mjs")} if capture.is_dir() else set()

    orphans = sorted(files - registered - NOT_GUARDS)
    if orphans:
        rep.add(WARN, "justfile",
                f"{len(orphans)} guard(s) in dev/capture/ are not in DEFAULT_GUARDS "
                f"and so gate nothing: {', '.join(orphans)} — register them, or add "
                f"them to lint.NOT_GUARDS with the reason they are not guards")
    missing = sorted(registered - files)
    if missing:
        rep.add(WARN, "justfile",
                f"DEFAULT_GUARDS names {len(missing)} guard(s) with no file in "
                f"dev/capture/: {', '.join(missing)} — a renamed guard leaves its "
                f"old name here and the runner cannot tell you")
    if not orphans and not missing:
        rep.add(OK, "justfile",
                f"{len(registered)} guard(s) registered, each with a file")


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
        # #371's pair. `short` is the opposite condition to `truncated` and the
        # two say different things to someone recovering his words, so the flag
        # is worthless without the count beside it.
        if "short" in rec and rec["short"] is not True:
            bad.append(f"line {i}: short must be true when present")
        if ("short" in rec) != ("got" in rec):
            bad.append(f"line {i}: got must be present iff short is")
        if "got" in rec and not isinstance(rec["got"], int):
            bad.append(f"line {i}: got is not an int")

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


DOC_MAP_PLANS_ROW = re.compile(r"^\|\s*`\.dreamwork/docs/plans/`\s*\|(.*)$", re.M)


def check_doc_map_plans(dw: Path, rep: Report) -> None:
    """The doc map's plans row enumerates the plans, so it goes stale on its own.

    Every other row in `doc-map.md` describes a file whose name is in the row,
    so the row cannot drift from the thing it names. This one describes a
    DIRECTORY and then lists its contents in prose — a shape that is wrong the
    next time anyone adds a plan, and wrong silently, because nothing reads it
    but a human who has no way to know the list is short. It listed 8 of 14 on
    2026-07-27; six plans existed that a reader of the map could not learn
    existed.

    Keeping the enumeration is deliberate rather than deleting it — "detail is
    ranked, never withheld" (DREAMWORK.md), and a map whose answer is `ls` has
    stopped being a map. So the list stays and this makes it checkable, which
    is the trade the repo makes everywhere else: a fact worth stating is a fact
    worth a reader.

    WARN both ways. A plan on disk but not in the row is undiscoverable; a name
    in the row with no file is either a typo or a plan that landed and was
    pruned from the directory but not the prose — the row's own rule says to
    prune, and this is what noticing looks like.
    """
    path, plans = dw / "docs" / "doc-map.md", dw / "docs" / "plans"
    if not path.exists() or not plans.is_dir():
        return
    m = DOC_MAP_PLANS_ROW.search(path.read_text())
    if not m:
        rep.add(WARN, "doc-map.md", "no `.dreamwork/docs/plans/` row — the plans are unmapped")
        return
    listed = set()
    for paren in re.findall(r"\(([^()]*)\)", m.group(1)):
        listed |= {n.strip() for n in paren.split(",") if n.strip()}
    if not listed:
        rep.add(WARN, "doc-map.md", "plans row names no plans — it used to enumerate them")
        return

    on_disk = {p.stem for p in plans.glob("*.md")}
    missing, phantom = sorted(on_disk - listed), sorted(listed - on_disk)
    if missing:
        rep.add(
            WARN,
            "doc-map.md",
            f"plans row omits {len(missing)} plan(s) that exist: {', '.join(missing)}"
            " — a reader of the map cannot learn they are there",
        )
    if phantom:
        rep.add(
            WARN,
            "doc-map.md",
            f"plans row names {len(phantom)} plan(s) with no file: {', '.join(phantom)}"
            " — landed and pruned, or a typo",
        )
    if not missing and not phantom:
        rep.add(OK, "doc-map.md", f"plans row matches {len(on_disk)} on disk")


def check_review_artifacts(dw: Path, rep: Report) -> None:
    """#329 — review artifacts whose frame has drifted behind the template.

    `review_artifact.py check` already answers current / stale / untemplated
    per artifact and exits 1 on any stale, but nothing ran it — so an artifact
    silently kept an old frame after the template improved, which is exactly
    the drift #325 exists to end, returning by a different door. This wires
    that answer into the per-target lint pass.

    **WARN on stale, never ERROR.** A stale frame is legible and recoverable:
    the words are still there, the page still renders, and the fix is one
    rebuild. ERROR is reserved here for what a reader cannot see at all, and a
    stale frame is not that. Same call `check_landed_still_open` makes for a
    task git says landed: strong evidence worth a prompt to look, not a gate.

    **Silent on `untemplated`.** The artifacts that predate the template are
    deliberately not migrated (#325), and a check that WARNs on each of them
    every run is noise everyone learns to ignore — which is the failure that
    hides the one that matters. `untemplated` is a third answer on purpose, and
    lint honours that by saying nothing about it.

    **Degrades silently** when the pieces are absent, following the idiom
    `check_landed_still_open` set for a non-repo target: no `.dreamwork/review/`
    directory, no `.html` in it, `review_artifact.py` missing or unrunnable, or
    a non-zero exit with no stale verdict parsed all return without a row.
    "Cannot check" must not read as "nothing to fix".

    Shells out to the real CLI rather than importing, the same move
    `check_landed_still_open` makes for git — and two traps come with that
    interface, both learned the hard way: `check` takes FILES, not a directory
    (it exits 1 on a directory, correctly), and it exits 1 on ANY stale, which
    is the signal this reads rather than treats as a crash. The non-recursive
    glob matches `watch.py`'s `list_reviews`, so a source in `src/` is
    invisible to this check (and to the dashboard) while a built artifact is not.
    """
    review_dir = dw / "review"
    if not review_dir.is_dir():
        return
    files = sorted(review_dir.glob("*.html"))
    if not files:
        return
    try:
        out = subprocess.run(
            [sys.executable, str(SKILL_DIR / "review_artifact.py"),
             "check", *[str(f) for f in files]],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return  # script/python missing, or it hung: cannot check, say nothing

    # `check` prints one line per file: `  <verdict> <path>`, with a
    # `  (built from <stamp>)` suffix on stale ones. Only stale is a finding.
    stale: list[tuple[str, str]] = []
    for line in out.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) < 2 or parts[0] != "stale":
            continue
        m = re.match(r"(.+?)\s+\(built from\s+(.+?)\)\s*$", parts[1])
        stale.append((m.group(1), m.group(2)) if m else (parts[1], "?"))

    if stale:
        for path, stamp in stale:
            rep.add(
                WARN,
                "review/",
                f"{Path(path).name} is stale (built from {stamp}) — rebuild it "
                f"from its source under `.dreamwork/review/src/` so the frame "
                f"tracks the current template (`review_artifact.py build`) (#329)",
            )
    elif out.returncode == 0:
        rep.add(OK, "review/", f"{len(files)} artifact(s), none stale")
    # else: non-zero exit with no stale verdict (a read error, or check itself
    # unhappy) — degrade silently rather than claim all is well.


CITED_SHA = re.compile(
    r"(?:landed|merged?|closed?|commit|fixed|reverted|sha)\**\s*(?:at|in|as)?\s*\**\s*"
    r"`([0-9a-f]{7,40})`", re.I)

# The same lead-in, capturing ANY backticked token, so a citation that is not hex
# is visible at all. `CITED_SHA` cannot see one — which is how #362 hid.
CITED_ANY = re.compile(
    r"(?:landed|merged?|closed?|commit|fixed|reverted|sha)\**\s*(?:at|in|as)?\s*\**\s*"
    r"`([^`\n]{1,40})`", re.I)
# A CLOSED vocabulary of slot shapes, and the closure is the discrimination. The
# obvious rule — a landing keyword introducing a token that is not a sha — was
# measured on the live ledger first and flags four things, none of them a
# placeholder: `questions.md`, `dev/capture/report.mjs`, `dither: "lsb-ign-v1"`,
# and a run of prose. Precision 0-in-4. This vocabulary flags all nine shapes an
# unfilled slot actually takes and none of those four.
PLACEHOLDER_CITATION = re.compile(
    r"^(?:<[^>]*>|pending|tbd|todo|x{3,}|sha|hash|\?+|-+)$", re.I)


def check_placeholder_citations(dw: Path, rep: Report) -> None:
    """A landing citation that is an unfilled slot rather than a commit (#381).

    #362's entry read ``**LANDED `<pending>`**`` and sat under `## Open` for
    hours before being found BY ACCIDENT while selecting an unrelated task.
    Nothing saw it: `check_cited_shas` reads hex, and a placeholder is not hex,
    so the one check whose whole subject is "does this citation point at a
    commit" was structurally blind to a citation that pointed at nothing.

    **WARN, never ERROR, and the reason is a real constraint rather than
    caution.** A commit cannot cite its own sha, so ``landed `PENDING``` is what
    the ledger honestly says for exactly one commit — the one that does the work.
    Erroring would block it. What is missing is not a prohibition but a nudge for
    the FOLLOW-UP, which until now was carried entirely by the writer
    remembering, and twice tonight was not.
    """
    path = dw / "tasks.md"
    if not path.exists():
        return
    try:
        text = path.read_text()
    except OSError:
        return
    seen = []
    for match in CITED_ANY.finditer(text):
        token = match.group(1)
        if not PLACEHOLDER_CITATION.match(token):
            continue
        # The nearest preceding entry id, so the row names something findable.
        before = text[:match.start()]
        ids = re.findall(r"- \*\*#(\d+)", before)
        where = "#%s" % ids[-1] if ids else "an entry"
        if (where, token) not in seen:
            seen.append((where, token))
    for where, token in seen:
        rep.add(
            WARN, "tasks.md",
            f"{where} cites `{token}` as a landing, which is a placeholder and "
            f"not a commit — expected for the one commit that cannot name its "
            f"own sha, so this is the reminder to fill it in with a follow-up "
            f"(#381)",
        )


# ── brief hand-off obligation (#398) ──────────────────────────────────
# Distinctive phrase from the SKILL.md paragraph that introduced the
# dispatch-time hand-off obligation (#394). Resolved via `git log -S`, never a
# pinned sha — same content-resolution idiom as
# test_review_artifact._prechange_review_artifact. **Pick is load-bearing:** a
# reword that removes this phrase makes `git log -S` return nothing; the check
# must then ERROR loudly rather than grandfather every brief in silence.
# Chosen because it opens the obligation paragraph, appears once in history,
# and is unlikely to be restated elsewhere by accident.
HANDOFF_OBLIGATION_PHRASE = (
    "A subagent that LANDS a commit writes two things, not one"
)


def resolve_handoff_obligation_cutoff(root: Path) -> str | None:
    """The commit that introduced the hand-off dispatch obligation into SKILL.md.

    Content-resolved (`git log -S` on HANDOFF_OBLIGATION_PHRASE), never a
    pinned sha. Returns a full 40-char sha, or None when history has no hit —
    and None is the hollow outcome the third test refuses to treat as a pass.
    When multiple commits touch the count, the oldest (introduction) wins.
    """
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "log", "-S", HANDOFF_OBLIGATION_PHRASE,
             "--format=%H", "--", "SKILL.md"],
            stderr=subprocess.DEVNULL, text=True, timeout=30,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    shas = out.split()
    if not shas:
        return None
    return shas[-1]  # git log is newest-first; last is the introduction


def brief_add_commit(root: Path, rel_path: str) -> str | None:
    """The commit that first added `rel_path`, or None if untracked / never committed."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "log", "--diff-filter=A", "-1",
             "--format=%H", "--", rel_path],
            stderr=subprocess.DEVNULL, text=True, timeout=20,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    sha = out.strip()
    return sha or None


def commit_unix_time(root: Path, sha: str) -> int | None:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "log", "-1", "--format=%ct", sha],
            stderr=subprocess.DEVNULL, text=True, timeout=10,
        )
        return int(out.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, OSError, ValueError):
        return None


def classify_brief_handoff_scope(root: Path) -> dict:
    """Split committed briefs by whether their add-commit is after the obligation.

    Returns ``{cutoff, in_scope, grandfathered, skipped, missing}`` where
    ``in_scope`` / ``grandfathered`` / ``skipped`` are lists of brief basenames
    and ``missing`` is the in-scope basenames that lack `.dreamwork/handoffs.md`.
    Used by the check and by the precondition assertions in its tests so a
    vacuous split (everything on one side) fails loudly.
    """
    empty: dict = {
        "cutoff": None, "in_scope": [], "grandfathered": [],
        "skipped": [], "missing": [],
    }
    briefs_dir = root / ".dreamwork" / "docs" / "briefs"
    if not briefs_dir.is_dir():
        return empty
    cutoff = resolve_handoff_obligation_cutoff(root)
    if not cutoff:
        return empty
    cutoff_t = commit_unix_time(root, cutoff)
    if cutoff_t is None:
        return empty
    out = {
        "cutoff": cutoff, "in_scope": [], "grandfathered": [],
        "skipped": [], "missing": [],
    }
    for path in sorted(briefs_dir.glob("*.md")):
        rel = str(path.relative_to(root))
        add = brief_add_commit(root, rel)
        if not add:
            # Untracked / never committed: the state a brief is in WHILE it is
            # being written. lint runs mid-increment constantly; flagging a
            # half-written file is how a check gets muted. Skip, do not scope.
            out["skipped"].append(path.name)
            continue
        add_t = commit_unix_time(root, add)
        if add_t is None:
            out["skipped"].append(path.name)
            continue
        # "Newer than" is strict: same commit as the cutoff is grandfathered
        # (the brief was not written *after* the obligation landed).
        if add_t <= cutoff_t:
            out["grandfathered"].append(path.name)
            continue
        out["in_scope"].append(path.name)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            out["missing"].append(path.name)
            continue
        # Substring match on the full path form the obligation uses. Crude:
        # a brief that says "do not touch `.dreamwork/handoffs.md`" still
        # passes. Intent parsing would false-positive on correct briefs, and a
        # false positive mutes the check — the failure that matters. Err loose.
        if ".dreamwork/handoffs.md" not in text:
            out["missing"].append(path.name)
    return out


def check_brief_handoff_obligation(dw: Path, rep: Report) -> None:
    """A brief written after the hand-off obligation must carry it (#398).

    `#381` built the channel; `#394` put the producer obligation into SKILL.md
    and the dispatch prompt. Neither was checkable until the *brief* became
    the thing: a committed file whose add-commit is resolvable. A brief that
    dispatches a lane without mentioning `.dreamwork/handoffs.md` is the
    defect, and a coordinator habit with no check decays silently.

    Cutoff is content-resolved from SKILL.md (HANDOFF_OBLIGATION_PHRASE), never
    a pinned sha. The hollow outcome this refuses: cutoff resolves to nothing
    and every brief is skipped, looking identical to a clean pass. That is an
    ERROR naming the phrase, not silence.

    Decisions baked in (both have a defensible wrong answer — see the brief):

    1. **Untracked briefs are skipped**, not in scope. lint runs mid-write;
       nagging an unfinished brief mutes the check.
    2. **Mention = substring `.dreamwork/handoffs.md`.** Loose on purpose:
       parsing "do not touch" is over-engineering that false-positives.

    Coverage number on the OK line (idiom #395): how many briefs were in scope
    and how many grandfathered, so a check that stops examining things cannot
    look the same as one that examined them all.
    """
    root = dw.parent
    briefs_dir = dw / "docs" / "briefs"
    if not briefs_dir.is_dir():
        return
    briefs = list(briefs_dir.glob("*.md"))
    if not briefs:
        return
    # Only govern a tree that has the skill text this obligation lives in.
    # A foreign dreamwork target with a briefs/ dir but no SKILL.md is not
    # this contract's subject.
    if not (root / "SKILL.md").exists():
        return

    cutoff = resolve_handoff_obligation_cutoff(root)
    if not cutoff:
        # THE hollow outcome, made loud: without a cutoff every brief would be
        # skipped and the check would print nothing. ERROR, not silent OK.
        rep.add(
            ERROR, "briefs",
            "could not resolve the hand-off obligation cutoff from SKILL.md "
            f"content (phrase {HANDOFF_OBLIGATION_PHRASE!r}) — every brief "
            "would have been left unchecked; a reworded phrase or missing "
            "history is a loud failure, never a silent pass (#398)",
        )
        return

    # The resolved commit must actually carry the obligation. A -S hit on a
    # removal or a wrong path would otherwise grandfather everything.
    try:
        blob = subprocess.check_output(
            ["git", "-C", str(root), "show", f"{cutoff}:SKILL.md"],
            stderr=subprocess.DEVNULL, text=True, timeout=20,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        blob = ""
    if HANDOFF_OBLIGATION_PHRASE not in blob:
        rep.add(
            ERROR, "briefs",
            f"cutoff `{cutoff[:7]}` resolved from content but does not contain "
            f"the obligation phrase — content resolution picked the wrong "
            f"commit, so every brief would be mis-scoped (#398)",
        )
        return

    scope = classify_brief_handoff_scope(root)
    for name in scope["missing"]:
        rep.add(
            ERROR, "briefs",
            f"{name} was added after the hand-off obligation landed and does "
            f"not mention `.dreamwork/handoffs.md` — a brief that dispatches "
            f"a lane without the obligation is the defect (#398)",
        )
    # Coverage always, when anything was examined. OK only when clean: an OK
    # next to ERRORs would tell a reader scanning for the OK line the opposite
    # of the truth (the #353 related-pair trap).
    n_in = len(scope["in_scope"])
    n_gf = len(scope["grandfathered"])
    if (n_in or n_gf) and not scope["missing"]:
        rep.add(
            OK, "briefs",
            f"{n_in} brief(s) in scope after hand-off obligation, "
            f"{n_gf} grandfathered (#398)",
        )


# ── brief worktree absolute-inbox path (#405) ─────────────────────────
# Distinctive phrase from the SKILL.md paragraph that made worktree the
# dispatch default and required absolute report paths. Content-resolved
# via `git log -S`, same idiom as HANDOFF_OBLIGATION_PHRASE (#398). A
# reword that removes this phrase must ERROR loudly, not grandfather
# every worktree brief in silence.
WORKTREE_ABS_INBOX_PHRASE = (
    "Inbox and hand-off paths given to a worktree lane are absolute"
)
# An absolute path to inbox.md: leading `/` then path segments, ending in
# `/inbox.md`. Repo-relative `.dreamwork/inbox.md` deliberately fails this.
ABS_INBOX_PATH_RE = re.compile(r"/[\w./-]+/inbox\.md")
# A brief that *names* a worktree dispatch target (not merely the word
# "worktree"). The defect is a worktree lane handed a relative inbox path.
WORKTREE_BRIEF_MARKER = ".worktrees/"


def resolve_worktree_abs_inbox_cutoff(root: Path) -> str | None:
    """Commit that introduced the absolute-inbox worktree rule into SKILL.md.

    Content-resolved (`git log -S` on WORKTREE_ABS_INBOX_PHRASE). Oldest hit
    wins. None is the hollow outcome the check refuses to treat as a pass.
    """
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "log", "-S", WORKTREE_ABS_INBOX_PHRASE,
             "--format=%H", "--", "SKILL.md"],
            stderr=subprocess.DEVNULL, text=True, timeout=30,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    shas = out.split()
    if not shas:
        return None
    return shas[-1]


def classify_worktree_brief_abs_inbox(root: Path) -> dict:
    """Split worktree-naming briefs by whether they post-date the absolute-path rule.

    Returns ``{cutoff, worktree, in_scope, grandfathered, skipped, missing}``
    where ``worktree`` is every brief whose body contains ``.worktrees/``,
    ``in_scope`` / ``grandfathered`` / ``skipped`` are subsets of those, and
    ``missing`` is in-scope basenames that lack an absolute ``…/inbox.md`` path.
    """
    empty: dict = {
        "cutoff": None, "worktree": [], "in_scope": [],
        "grandfathered": [], "skipped": [], "missing": [],
    }
    briefs_dir = root / ".dreamwork" / "docs" / "briefs"
    if not briefs_dir.is_dir():
        return empty
    cutoff = resolve_worktree_abs_inbox_cutoff(root)
    if not cutoff:
        return empty
    cutoff_t = commit_unix_time(root, cutoff)
    if cutoff_t is None:
        return empty
    out = {
        "cutoff": cutoff, "worktree": [], "in_scope": [],
        "grandfathered": [], "skipped": [], "missing": [],
    }
    for path in sorted(briefs_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if WORKTREE_BRIEF_MARKER not in text:
            continue
        out["worktree"].append(path.name)
        rel = str(path.relative_to(root))
        add = brief_add_commit(root, rel)
        if not add:
            out["skipped"].append(path.name)
            continue
        add_t = commit_unix_time(root, add)
        if add_t is None:
            out["skipped"].append(path.name)
            continue
        if add_t <= cutoff_t:
            out["grandfathered"].append(path.name)
            continue
        out["in_scope"].append(path.name)
        if not ABS_INBOX_PATH_RE.search(text):
            out["missing"].append(path.name)
    return out


def check_brief_worktree_abs_inbox(dw: Path, rep: Report) -> None:
    """A brief that names a worktree must give an absolute inbox path (#405).

    A lane in ``.worktrees/x`` told to append to ``.dreamwork/inbox.md`` writes
    its own copy; the coordinator never reads it. The obligation lives in
    SKILL.md; this check makes the brief carry it once the rule has landed.

    Only briefs whose body contains ``.worktrees/`` are examined. Untracked
    briefs are skipped (mid-write). Cutoff is content-resolved from
    WORKTREE_ABS_INBOX_PHRASE — a hollow no-cutoff is an ERROR, not a silent
    pass. Absolute = matches ABS_INBOX_PATH_RE (leading ``/…/inbox.md``).

    Coverage on the OK line: worktree-naming count, in-scope, grandfathered —
    so a check that stops matching cannot look the same as one that examined
    them all. Precondition the live tests assert: at least one worktree-naming
    brief exists (a check that silently matches nothing passes forever).
    """
    root = dw.parent
    briefs_dir = dw / "docs" / "briefs"
    if not briefs_dir.is_dir():
        return
    if not (root / "SKILL.md").exists():
        return
    # Precondition for the check's meaning: if no brief names a worktree, the
    # rule has nothing to examine. That is silence (not OK coverage), and the
    # live tests refuse a vacuous match-set — do not invent a clean pass here.
    any_wt = any(
        WORKTREE_BRIEF_MARKER in p.read_text(encoding="utf-8", errors="replace")
        for p in briefs_dir.glob("*.md")
        if p.is_file()
    )
    if not any_wt:
        return

    cutoff = resolve_worktree_abs_inbox_cutoff(root)
    if not cutoff:
        rep.add(
            ERROR, "briefs",
            "could not resolve the worktree absolute-inbox cutoff from "
            f"SKILL.md content (phrase {WORKTREE_ABS_INBOX_PHRASE!r}) — every "
            "worktree brief would have been left unchecked; a reworded phrase "
            "or missing history is a loud failure, never a silent pass (#405)",
        )
        return

    try:
        blob = subprocess.check_output(
            ["git", "-C", str(root), "show", f"{cutoff}:SKILL.md"],
            stderr=subprocess.DEVNULL, text=True, timeout=20,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        blob = ""
    if WORKTREE_ABS_INBOX_PHRASE not in blob:
        rep.add(
            ERROR, "briefs",
            f"cutoff `{cutoff[:7]}` resolved from content but does not contain "
            f"the worktree absolute-inbox phrase — content resolution picked "
            f"the wrong commit, so every worktree brief would be mis-scoped "
            f"(#405)",
        )
        return

    scope = classify_worktree_brief_abs_inbox(root)
    for name in scope["missing"]:
        rep.add(
            ERROR, "briefs",
            f"{name} names a worktree (`.worktrees/`) but has no absolute "
            f"`…/inbox.md` path — a worktree lane given a relative inbox path "
            f"reports into its own copy and the coordinator never sees it "
            f"(#405)",
        )
    n_wt = len(scope["worktree"])
    n_in = len(scope["in_scope"])
    n_gf = len(scope["grandfathered"])
    if n_wt and not scope["missing"]:
        rep.add(
            OK, "briefs",
            f"{n_wt} worktree-naming brief(s), {n_in} in scope after "
            f"absolute-inbox rule, {n_gf} grandfathered (#405)",
        )


def check_handoffs(dw: Path, watch, rep: Report) -> None:
    """The delivery half of the single-writer rule (#381).

    A foreign session that lands work it does not own the ledger for appends a
    line to `.dreamwork/handoffs.md` under `## Pending`; the coordinator folds
    it and appends a `→ folded` line under `## Folded`. The file is the
    channel, and THIS check is what makes an unfolded one visible to whoever
    runs lint — without it, the entry sits done-but-open until someone happens
    to look, which is the hour #334 and #362 cost.

    One WARN, and the consumed marker is the sole thing that silences it:

    - **a hand-off names `#N` as landed but `#N` is still under `## Open`.**
      The delivery signal; the whole point. WARN, never ERROR: a freshly-landed
      hand-off is *supposed* to sit pending for the one tick before the
      coordinator folds it, so erroring would cry wolf on correct behaviour.

    A consumed hand-off (Folded names its id) is **silent, always** — even if
    the task is still under `## Open`. That is the load-bearing choice and the
    reason the fold record exists: a check that nags after you have complied
    gets muted, and a muted check is worse than none. The fold record is the
    coordinator's "I have seen this", and once it lands the hand-off stops
    counting, by design. So the consumed marker is the one line whose removal
    redds `test_a_consumed_handoff_is_not_flagged_again`.

    The id sets come from `watch.parse_ledger` — the real parser, never a
    second copy, for `check_author_tags`'s reason. Missing file or empty
    sections: silent, the way a fresh target is.
    """
    path = dw / "handoffs.md"
    if not path.exists():
        return
    try:
        text = path.read_text()
    except OSError:
        return
    if watch is None:
        return  # the parser lives in watch; without it this check cannot run
    pending, folded_ids, malformed = watch.parse_handoffs(text)

    # #415 — a task landing in two commits is the ordinary case. The parser's
    # Pending grammar (`watch.HANDOFF_PENDING_RE`) matches a SINGLE backticked
    # sha, so an honest `· landed \`54c68e8\` \`25a3fe4\` ·` lands in `malformed`
    # even though every required field is present. Recognise that shape here
    # and reclassify it: it is a valid multi-sha hand-off, not a garbled line.
    # The grammar lives in watch.py (held by another lane); this is a lint-local
    # widening on top of `malformed`, the same bucket, so it does not touch the
    # parser's return shape. A line with ONE sha parses cleanly and never reaches
    # malformed, so this only ever admits the two-or-more case.
    #
    # The pattern mirrors the single-sha grammar's shape: the id bold head, then
    # `landed`, then one-or-more backticked shas, then `· <ts> · by <claimer>`.
    # It is anchored on the `by <claimer>` tail so a line missing that field (the
    # zero-sha case, `· landed ·`) does NOT match — that stays malformed.
    multi_sha_handoff = re.compile(
        r"^-\s+\*\*#" +                       # the bold id head (bare, any id)
        r"[\w/]+\*\*\s*·\s*landed\s+" +       # `· landed `
        r"(?:`[^`\n]+`\s*){2,}" +             # two-or-more backticked shas
        r"·\s*.+?\s*·\s*by\s+.+?\s*$")        # `· <ts> · by <claimer> — what`
    truly_malformed = [(nid, line) for nid, line in malformed
                       if not multi_sha_handoff.match(line.strip())]
    multi_sha_count = len(malformed) - len(truly_malformed)

    # Format: an entry head the grammar does not recognise, or one in the wrong
    # section (#401/#406). Always named — never silenced by a same-id fold
    # record. A Pending-shaped line under `## Folded` is the #406 defect; a
    # fold for the same id must not hide it (that was the silent path).
    for nid, line in truly_malformed:
        rep.add(
            WARN, "handoffs.md",
            f"#{nid} has a hand-off entry the grammar does not recognise "
            f"(needs `· landed \\`<sha>\\` · … · by <claimer>` under "
            f"`## Pending`, or `→ folded (ts):` under `## Folded`; id may be "
            f"`#N`, `#Na`, or `#N/#M`): {line!r} (#381/#401/#406)")

    # Coverage (#395 idiom / #401): how many of each bucket the parser saw.
    # A check that counts what it examined cannot silently stop examining.
    # The multi-sha count is derived at runtime from `malformed`, never a
    # literal — and it is named separately so a recognised two-sha hand-off
    # cannot hide inside `malformed` counting as a defect (#415).
    coverage = (f"{len(pending)} pending, {len(folded_ids)} folded, "
                f"{len(truly_malformed)} malformed")
    if multi_sha_count:
        coverage += f", {multi_sha_count} multi-sha hand-off(s) recognised"
    rep.add(OK, "handoffs.md", coverage)

    ledger_path = dw / "tasks.md"
    if not ledger_path.exists():
        return
    try:
        open_ids, _landed_ids = watch.parse_ledger(ledger_path.read_text())
    except Exception:
        return  # a mid-edit ledger is not a hand-off problem

    # THE delivery signal: pending (not folded) and still open. Correlation
    # normalises sub-ids/combined tokens to parent ledger ids via the named
    # helper — never ENTRY_ID's incidental letter-strip (#401).
    # `if nid in folded_ids: continue` is the consumed marker — the one line
    # that stops a complied hand-off being nagged forever.
    for nid, sha, claimer in pending:
        if nid in folded_ids:
            continue
        parents = watch.handoff_parent_ids(nid)
        if any(p in open_ids for p in parents):
            rep.add(
                WARN, "handoffs.md",
                f"#{nid} is named as landed in a hand-off (by {claimer}, sha "
                f"`{sha}`) but is still under `## Open` — fold it into the "
                f"ledger and append a `→ folded` line (#381)")


def check_cited_shas(dw: Path, rep: Report) -> None:
    """A ledger entry that cites a commit which does not exist (#350).

    `check_landed_still_open` treats a cited commit as the entry's evidence that
    it is deliberately still open, and every fold writes one. Nothing checked
    that the sha RESOLVES — and a dead citation is silent in both directions: the
    reader following it finds nothing, and the check that reads citations cannot
    tell a wrong sha from an honest one.

    Found by self-review, not by anyone noticing: #302's entry cited
    `f0f4e2a`-merge while the work is actually at `08cd931`. Almost certainly the
    worktree branch's sha, unreachable after the merge — which is the general
    hazard, because the sha an agent reports is from the tree it worked in.

    THE DISCRIMINATION, measured on the live ledger rather than assumed, because
    two looser rules were tried first and both were wrong:

    - *every backticked 7-40 hex token* flags 94, of which 6 are pure-digit PIDs
      (`1246815`, `251691418`) that are valid hex. Requiring at least one `a-f`
      removes all six.
    - *a landing keyword within 40 characters* still flags `fade326` — a c2c peer
      alias that happens to be seven hex digits — because the keyword 40 chars
      back belongs to a NEIGHBOURING sha (``merged `7cdfc61`** (agent `fade326``).
      Proximity cannot tell which token a keyword introduces.
    - *the keyword immediately introduces the token* flags 37 citations, of which
      exactly 1 is dead: the real one. `fade326` is excluded in both its contexts.

    So precision is 1-in-1 and it catches the only instance in 237 entries. It
    deliberately does not read a bare `· `abc1234` ·` with no keyword: those are
    references, not claims about a landing, and widening to them reintroduces the
    alias false positive.

    **WARNs, never ERRORs**, following `check_landed_still_open`: a wrong sha is
    recoverable and the entry's words are still true.

    **And a skip is always a row (#380).** The sentence above used to end "skipped
    in silence when the target is not a git repository — 'cannot check' must not
    read as 'nothing to fix'", which contradicted itself: silence is exactly what
    makes the one read as the other. Four exits said nothing, and one of them
    fired — the full suite failed once on `test_a_dead_cited_sha_warns` and then
    passed twenty-five runs in isolation, so the check had declined to run and
    left no trace anywhere to say which exit it took. Whichever it was, it is
    now named in the report.
    """
    path = dw / "tasks.md"
    if not path.exists():
        return
    try:
        text = path.read_text()
    except OSError:
        return
    shas = []
    for match in CITED_SHA.finditer(text):
        token = match.group(1)
        # Pure-digit tokens are PIDs and counts that happen to be valid hex.
        if re.search(r"[a-f]", token) and token not in shas:
            shas.append(token)
    if not shas:
        return
    # #380: every exit below used to be a bare `return`, which is the one thing
    # the docstring says must not happen. A skip is now always a row. The LEVEL
    # discriminates whose fault it is: `.git` present and git still unusable is
    # an anomaly worth a WARN, while a target that is not a repository has done
    # nothing wrong and gets an OK that merely says so.
    in_repo = (dw.parent / ".git").exists()
    unchecked = "%d cited commit(s) went unchecked" % len(shas)
    try:
        proc = subprocess.run(
            ["git", "-C", str(dw.parent), "cat-file", "--batch-check"],
            input="".join("%s^{commit}\n" % s for s in shas),
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        rep.add(WARN if in_repo else OK, "tasks.md",
                f"could not ask git about the ledger's citations "
                f"({type(exc).__name__}), so {unchecked}")
        return
    if proc.returncode != 0 and not proc.stdout:
        rep.add(WARN if in_repo else OK, "tasks.md",
                f"git could not read this tree, so {unchecked}"
                + ("" if in_repo else " (no `.git` here, which is not a fault)"))
        return
    lines = proc.stdout.splitlines()
    if len(lines) != len(shas):
        # `--batch-check` writes exactly one line per input, so a short answer
        # means something went wrong mid-stream. `zip()` used to absorb this and
        # report "all resolve" over a tail it had never looked at — including a
        # dead sha sitting in that tail.
        rep.add(WARN, "tasks.md",
                f"git answered for {len(lines)} of {len(shas)} cited commit(s) "
                f"— one line per input is expected, so the rest were never "
                f"examined and this says nothing about them")
        return
    dead = []
    for sha, line in zip(shas, lines):
        if "missing" in line or "ambiguous" in line:
            dead.append(sha)
    if dead and len(dead) == len(shas):
        # Every single one missing means we are almost certainly not looking at
        # the repository these shas came from (a fresh clone, a different
        # target), not that the ledger is entirely wrong. Suppressing the WARNs
        # is right; suppressing the fact that it happened is what #380 fixed.
        rep.add(OK, "tasks.md",
                f"all {len(shas)} cited commit(s) are missing here, read as the "
                f"wrong tree rather than a wrong ledger — so nothing was checked")
        return
    for sha in dead:
        rep.add(
            WARN,
            "tasks.md",
            f"cites commit `{sha}` as a landing, but git has no such commit — a "
            f"worktree sha is unreachable once the branch is merged or rebased, "
            f"so cite the sha on the branch you merged INTO (#350)",
        )
    if not dead:
        rep.add(OK, "tasks.md", f"{len(shas)} cited commit(s) all resolve")


# Case-insensitive on purpose, so a wrong case is FOUND and then errored rather
# than silently reading as prose. Same reasoning as the origin marker's
# vocabulary check: an unreadable claim must not look like an absent one.
#
# Field-anchored (#395): the marker must sit on a `·`-delimited field boundary
# (or at the start of the flattened entry). Matching mid-sentence lets the
# non-greedy `[^*]*?` run forward to the next `**` anywhere in the entry and
# manufactures a phantom marker — #395's own ledger entry produced five before
# it was reworded. Anchoring does not create a new phantom class: a real claim
# is already a `· related: **…**` field, so matching only there is the same
# surface the writer uses. Prose that happens to write that full field form is
# a real claim, not a phantom; mid-sentence vocabulary without the field
# boundary is ignored.
RELATED_MARKER = re.compile(r"(?:^|[·])\s*related:\s*\*\*([^*]*?)\*\*", re.I)
# A field-anchored `related:` whether or not the value is bolded — the seam
# #395 closes. Without this, an unbolded marker falls through `if not found:
# continue` and is skipped in silence, which hid four broken relations.
RELATED_FIELD = re.compile(r"(?:^|[·])\s*related:\s*", re.I)
# Two adjacent bold spans after the field prefix: only the first id is captured
# and the rest surface as a misleading reciprocity complaint (#395 trap 2).
RELATED_ADJACENT_SPANS = re.compile(
    r"(?:^|[·])\s*related:\s*\*\*[^*]*\*\*\s*,\s*\*\*", re.I)
RELATED_ID = re.compile(r"#(\d+)")


def check_related_markers(dw: Path, watch, rep: Report) -> None:
    """A `related:` marker names tasks that are one piece of work (#353).

    The ledger has expressed this relation for a year by writing two ids in one
    title — `- **#250/#251**` — which is an IMPLICIT relation, readable only by a
    human who notices the slash. #346's store cannot represent it at all, because
    `task(id PRIMARY KEY)` is one row per id, and his 01:23 ruling asked for the
    relation to become explicit: a symmetric n:n `related` table, distinct from
    one-way `depends`.

    So splitting those entries has to put the relation somewhere the migration can
    read, or the split DESTROYS the only record of which two tasks were one piece
    of work. This is that somewhere, and it follows the origin marker's idiom
    because a second idiom for `key: **value**` would be a second thing to learn:

        · related: **#251**
        · related: **#251, #292**

    THE RECIPROCITY RULE IS THE POINT, and it is where the SQL and the Markdown
    differ for a reason. `related` in SQLite carries `CHECK (a < b)` so the pair is
    stored ONCE and cannot disagree with itself. Prose has no such luxury: an
    entry is read alone, so a reader who lands on #250 must learn about #251
    without going looking. Both entries therefore carry the marker — and the
    disagreement that duplication invites is exactly what this check removes.
    Reciprocity is cheap to enforce and impossible to remember.

    A present-but-unparseable marker is an ERROR, not a silent skip (#395). The
    hole was specifically missing bold: `· related: #383` matched no
    RELATED_MARKER, hit `if not found: continue`, and four broken relations hid
    behind that. Wrong-case markers still match and still fire the case branch —
    that branch is not dead. Two adjacent bold spans
    (`**#393**, **#394**`) are a shape error of their own rather than a truncated
    reciprocity complaint. Field anchoring keeps mid-sentence vocabulary from
    manufacturing phantom markers.

    The OK summary reports how many entries were unparseable as well as how many
    pairs checked: a check that counts what it examined cannot silently stop
    examining things.

    ERRORs rather than WARNs, unlike `check_cited_shas`, because there is no
    legacy to grandfather: at the time of writing the live ledger has **zero**
    `related:` markers (measured, not assumed — `RELATED_MARKER` finds none in 180
    entries), so nothing existing can be broken by strictness, and the first
    marker written is checked on the day it is written.

    Deliberately NOT here: `depends`. Its Markdown form would have to reconcile
    with the 29 entries that say `blocked on #N` in prose today, which is its own
    task and its own decision about whether that prose becomes a marker or stays
    prose. Naming a `depends:` shape now, with nothing using it and 29 entries
    contradicting it, would be a contract written ahead of its evidence.
    """
    path = dw / "tasks.md"
    if not path.exists():
        return
    try:
        text = path.read_text()
    except OSError:
        return
    entries = watch.ledger_entries(text)
    # The marker may hard-wrap: the loop writes at ~72 columns, so join each
    # entry's lines before reading it, the same allowance the origin rule makes.
    claims: dict[int, set[int]] = {}
    all_ids = {i for ids, _ in entries for i in ids}
    n_unparseable = 0
    for ids, raw in entries:
        flat = re.sub(r"\s+", " ", raw)
        head = "/".join("#%d" % i for i in ids)
        fields = list(RELATED_FIELD.finditer(flat))
        found = RELATED_MARKER.findall(flat)
        if not fields:
            continue
        if not found:
            # Field present, bold form absent — the #395 hole. Name the shape,
            # not a downstream reciprocity symptom about claims we never saw.
            n_unparseable += 1
            rep.add(ERROR, "tasks.md", (
                f"{head} has a `related:` marker that is unparseable — the form "
                f"is `· related: **#N** ·` or `· related: **#N, #M** ·` with the "
                f"bold span; without it the marker is read as absent and the "
                f"reciprocity check skips the entry in silence (#353)"))
            continue
        if len(fields) > 1 or len(found) > 1:
            rep.add(ERROR, "tasks.md", (
                f"{head} has {max(len(fields), len(found))} `related:` "
                f"markers — two claims about the same relation is none; list every "
                f"id in one marker (#353)"))
            continue
        if RELATED_ADJACENT_SPANS.search(flat):
            # One span must hold the whole list. Feeding only the first id into
            # reciprocity makes the message point at the silent drop, not the shape.
            n_unparseable += 1
            rep.add(ERROR, "tasks.md", (
                f"{head} has a `related:` marker with two adjacent bold spans — "
                f"only the first id is read and the rest are dropped; put every "
                f"id in one span: `· related: **#N, #M** ·` (#353)"))
            continue
        if "related: **" not in flat:
            # Reachable, not dead (#395 trap 1): Related: **#7** and related:**#7**
            # both match RELATED_MARKER while failing this literal-prefix test.
            rep.add(ERROR, "tasks.md", (
                f"{head} writes its related marker in "
                f"the wrong case — the vocabulary is exactly `related:` so a reader "
                f"never has to interpret it (#353)"))
            continue
        named = {int(n) for n in RELATED_ID.findall(found[0])}
        if not named:
            rep.add(ERROR, "tasks.md", (
                f"{head} has a `related:` marker naming "
                f"no id — the value is one or more `#N`, comma separated (#353)"))
            continue
        for own in ids:
            claims[own] = named
        for target in sorted(named):
            if target in ids:
                rep.add(ERROR, "tasks.md", (
                    f"{head} names ITSELF as related — "
                    f"the relation is between two tasks (#353)"))
            elif target not in all_ids:
                rep.add(ERROR, "tasks.md", (
                    f"{head} is related to #{target}, "
                    f"which is not an id in the ledger — a relation pointing at "
                    f"nothing is worse than none (#353)"))
    for own, named in sorted(claims.items()):
        for target in sorted(named):
            if target == own or target not in all_ids:
                continue        # already reported above
            back = claims.get(target)
            if back is None or own not in back:
                rep.add(ERROR, "tasks.md", (
                    f"#{own} is related to #{target} but #{target} does not say so "
                    f"back — an entry is read alone, so both carry the marker and "
                    f"this check is what keeps them agreeing (#353)"))
    # Only claim reciprocity when nothing above contradicted it. The first live
    # red-proof of this check printed `3 related pair(s), all reciprocal` in the
    # same run as `#250 is related to #251 but #251 does not say so back`, because
    # the summary was unconditional — a reader scanning for the OK line would have
    # been told the opposite of the truth by the check that found it.
    #
    # The unparseable count is coverage (#395): had the pre-fix check printed
    # "N pairs, K entries unparseable" the silent-skip hole would have been on
    # screen for days. A check that counts what it examined cannot silently
    # stop examining things.
    if claims and not any(lvl == ERROR and w == "tasks.md" and "(#353)" in d
                          for lvl, w, d in rep.rows):
        pairs = {tuple(sorted((a, b))) for a, named in claims.items() for b in named}
        rep.add(OK, "tasks.md", (
            f"{len(pairs)} related pair(s), all reciprocal; "
            f"{n_unparseable} entries unparseable"))


def run_checks(dw: Path, watch, rep: Report) -> None:
    """Every check, in one place, because a SECOND copy of this list drifted.

    `test_lint.py`'s helper used to hand-maintain its own sequence, and it had
    fallen six checks behind — including the one being added when this was
    found. A check absent from the test harness is a check whose tests cannot
    fail, which is the failure mode this repo keeps rediscovering. One list,
    called by `main()` and by the tests, cannot drift from itself.
    """
    check_questions(dw, watch, rep)
    check_answered_resolution_dates(dw, watch, rep)
    check_answers(dw, watch, rep)
    check_author_tags(dw, watch, rep)
    check_unfolded_answers(dw, watch, rep)
    check_tasks(dw, rep)
    check_human_blocker(dw, watch, rep)
    check_landed_asks(dw, watch, rep)
    check_status(dw, rep)
    check_status_task_ids(dw, rep)
    check_status_agrees_with_ledger(dw, watch, rep)
    check_status_push(dw, rep)
    check_watch_port(dw, rep)
    check_watch_tint(dw, watch, rep)
    check_run_mode(dw, watch, rep)
    check_plugin_commands(dw, watch, rep)
    check_submissions(dw, rep)
    check_skill_version(dw, rep)
    check_dreamwork_frontmatter(dw, rep)
    check_dreams(dw, rep)
    check_doc_map_plans(dw, rep)
    check_review_artifacts(dw, rep)
    check_cited_shas(dw, rep)
    check_placeholder_citations(dw, rep)
    check_handoffs(dw, watch, rep)
    check_brief_handoff_obligation(dw, rep)
    check_brief_worktree_abs_inbox(dw, rep)
    check_related_markers(dw, watch, rep)
    check_status_keys(dw, rep)
    # Takes the skill dir, not `.dreamwork/`: the justfile and the guards are
    # the tool's own, so this only says anything when linting this repo.
    check_guards_registered(dw.parent, rep)


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
    run_checks(dw, watch, rep)

    print(f"lint {dw}")
    print(rep.render())
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
