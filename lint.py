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
import difflib
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

# #653: the same reading `watch.serving_report` carries. One implementation of
# "is client/dist built from this tree", two surfaces — a second copy of the
# comparison is a second answer, and the pair would disagree on the day one of
# them was edited.
import client_dist

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
# The origin rule reads WHOLE entries (ENTRY_HEAD/ENTRY_ID, from
# ledger_parse below), not head
# lines, so combined entries (`- **#250/#251**`) are governed on either id.
# LEDGER_ID is pinned identical to watch.py's LEDGER_ENTRY by a test and is
# combined-aware for the same reason (#315): its bold span is ids only
# (`#7` or `#7/#8`). Callers that counted a captured digit run must now
# extract every id in the span — see check_tasks and check_ledger_sections.
ORIGIN_CUTOFF = 216
ORIGIN_VALUES = ("human", "loop", "unknown")
# #352: the entry/origin grammar — ENTRY_HEAD, ENTRY_ID, ORIGIN_MARK,
# ledger_entries — is ledger_parse.py's, imported, never re-copied (the
# drift lesson of 3073055). The names stay importable from lint for the
# callers that already read them here. `open_section_text` is the Open
# slice two checks below once wrote out by hand.
from ledger_parse import (ENTRY_HEAD, ENTRY_ID, ORIGIN_MARK, ledger_entries,
                          open_section_text, origin_marks, source_of_truth,
                          store_entries, store_ids_by_state, store_path)
# #592: the #458 shim is a `dreamwork-migration-notice`, and recognising one is
# migration_notice.py's job — the worktree excuse below must not be spendable on
# a tasks.md that merely happens to lack a header.
from migration_notice import parse_notice

# #419: a blocked-on-human claim, same `key: **value**` idiom as origin/related.
# The marker names a KIND of blocker (a human decision), not a specific question
# — a task-blocker (`blocked on #352`) is a different relation and stays prose.
# Joined per-entry before matching, so it survives a hard wrap the way origin does.
BLOCKED_ON_HUMAN_MARK = re.compile(r"blocked-on:\s*\*\*\s*([^*]+?)\s*\*\*")
# A `gate:` companion naming where the ruling lives (the task whose question
# carries this decision), for the case the question does not carry the entry's
# own id — the #371 trap. Optional; absent defaults to the entry's own id.
GATE_MARK = re.compile(r"gate:\s*\*\*\s*([^*]+?)\s*\*\*")


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

    By path, not as a package. The old reason given here was "watch.py is a
    single file by design", which stopped being true at #397 — the client is
    eight files under `client/`, and #480 already ships a sibling closure
    beside the snapshot. What survives is the constraint that actually holds:
    the deploy snapshot is a FILE at a conventional path, resolved from
    `watch.py`'s own directory, so importing by path is what keeps this
    agreeing with the deployed layout rather than with the repo's.

    Returns None if it is unimportable — mid-edit by another agent, say — so
    the rest of the checks still run.
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
        # #611: names of ledger checks that were CALLED and examined nothing,
        # because the ledger text they were handed held no entries. Kept apart
        # from `rows` so `check_ledger_skips` can render them as ONE row at the
        # end of the run — six near-identical rows saying "the ledger did not
        # travel" is the volume failure #612 is about, and one row that names
        # all six carries the same information.
        self.ledger_skips: list[str] = []

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
    # #555 — conflict markers are silent to parse_questions (it keys on
    # `- **Title**` entry heads), so a marker line renders as nothing — the
    # same reader-cannot-see-what-is-there defect #554 closed for handoffs.md,
    # in the channel to the human. Scanned from the raw text BEFORE any early
    # return: the parse hazard is independent of the parser (proven by the
    # born-hollow demo, which passed all four forms with watch loaded). One
    # ERROR per marker line so each is named. Reuses the ONE #554 regex.
    for ln in text.splitlines():
        m = CONFLICT_MARKER_RE.match(ln)
        if m:
            rep.add(
                ERROR, "questions.md",
                f"conflict marker `{m.group(0)}` at line start ({ln!r}) — a "
                f"merge-conflict marker left in questions.md is silent to the "
                f"parser; resolve and remove it (#555)")
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


# A questions.md that is NET shorter than its last committed form by more than
# this many lines is a tail-truncation (#533), not any normal act. Every
# legitimate questions.md edit is line-neutral or net-positive: a fold cuts an
# entry from `## Open` and pastes it (with a ruling summary) into `## Answered`
# (+3 typical); an answer/note append adds lines; surfacing a question adds a
# whole entry. The loop never bulk-deletes — the 07:44 incident lost 122 lines
# in one silent write. Measured, not guessed: the incident is 122; the largest
# real fold on this repo (+103/-100) is net +3. 50 sits clear of every real
# change and well under the loss it exists to catch.
QUESTIONS_TRUNCATION_THRESHOLD = 50


def questions_truncation_guard(old_text, new_text, *, groom=False,
                               threshold=QUESTIONS_TRUNCATION_THRESHOLD):
    """Is `new_text` a tail-truncated form of `old_text`?

    Pure — testable without a filesystem. A net loss of more than `threshold`
    lines is a probable truncation: the coordinator wrote the file from a
    partial read and the tail fell off. `groom` is the escape hatch for the
    one legitimate net loss (a deliberate bulk-archive), signalled by a
    ``groom:`` marker in the commit message. Returns ``(level, detail)`` —
    ERROR when the loss is unexplained, OK otherwise (silent on the clean
    case; `check_questions` owns the file's OK row).
    """
    old_n = len((old_text or "").splitlines())
    new_n = len((new_text or "").splitlines())
    lost = old_n - new_n
    if lost > threshold and not groom:
        return (ERROR,
                f"lost {lost} lines vs HEAD (net; threshold {threshold}) — "
                f"probable tail-truncation (#533): a fold is line-neutral and "
                f"the loop never bulk-deletes. If this is a deliberate archive, "
                f"mark the commit `groom:`.")
    return (OK, "")


def _head_questions(dw: Path, ref: str = "HEAD") -> str | None:
    """HEAD's questions.md for the target's repo, or None when unreadable.

    `git show` is read-only plumbing and takes no index lock (the active
    mitigation on this host is about `git status`). None means "no baseline"
    so a questions.md not yet tracked does not read as "nothing lost".

    ``ref`` defaults to HEAD (the pre-commit comparison). The #585
    retroactive check passes ``HEAD~1`` to compare the just-committed
    version against its parent — catching a truncation that committed
    *without* lint running in the pre-commit window (#575).
    """
    try:
        show = subprocess.run(
            ["git", "-C", str(dw.parent), "show",
             f"{ref}:.dreamwork/questions.md"],
            capture_output=True, text=True, timeout=10)
        return show.stdout if show.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _last_questions_commit_has_groom(dw: Path) -> bool:
    """True if the most recent commit touching questions.md carries ``groom:``.

    lint runs on the working tree before a commit exists, so the in-progress
    change's message is not yet written; the last *committed* message is the
    available signal. A deliberate bulk-archive is committed with ``groom:``
    and lint honours it on the next pass.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(dw.parent), "log", "-1", "--format=%B",
             "--", ".dreamwork/questions.md"],
            capture_output=True, text=True, timeout=10)
        return out.returncode == 0 and "groom:" in (out.stdout or "")
    except (OSError, subprocess.SubprocessError):
        return False


def check_questions_truncation(dw: Path, rep: Report) -> None:
    """#533: catch a tail-truncation of questions.md before it is committed.

    At 07:44 on 2026-07-30 the coordinator wrote questions.md from a partial
    read and 122 lines of the #229 thread (the nested-table note and everything
    below it) silently fell off. The signature correctly fired; nothing
    compared the result to what was there before, so the loss was committed at
    ``0f97df03`` and only restored at ``fd53d82a``. This check is that
    comparison: the working tree against HEAD. A net loss over the threshold is
    not any normal act (a fold is line-neutral; appends add), so it is an ERROR
    until explained by a ``groom:`` marker. watch.py is innocent — ``collect()``
    only reads and every writer is an ``append_*`` that preserves every line —
    so the gate belongs here, at the file the coordinator rewrites.

    Silent when there is no git baseline (a fixture, a target outside a repo):
    'cannot check' must not be a fault.

    #585 — retroactive post-commit check. The HEAD-vs-working-tree
    comparison above is structurally blind *after* a truncation commits:
    HEAD == working tree, net loss reads 0. The retroactive arm compares
    HEAD vs HEAD~1, so a truncation that committed without lint running
    in the pre-commit window (#575) is caught on the next ``lint.py`` /
    ``just test`` run. ``groom:`` on the last commit clears it (a
    deliberate archive is the one legitimate net loss).
    """
    path = dw / "questions.md"
    if not path.exists():
        return  # check_questions owns the absent case
    if not (dw.parent / ".git").exists():
        return  # no git baseline to compare against
    head = _head_questions(dw)
    if head is None:
        return  # questions.md not yet tracked; nothing to compare
    level, detail = questions_truncation_guard(
        head, path.read_text(), groom=_last_questions_commit_has_groom(dw))
    if level == ERROR:
        rep.add(ERROR, "questions.md", detail)

    # #585: retroactive — did the last commit itself truncate?
    parent = _head_questions(dw, ref="HEAD~1")
    if parent is not None:
        level2, detail2 = questions_truncation_guard(
            parent, head, groom=_last_questions_commit_has_groom(dw))
        if level2 == ERROR:
            rep.add(ERROR, "questions.md",
                    f"#585 retroactive: {detail2}")


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


def check_resolution_marker_outside_title(dw: Path, watch, rep: Report) -> None:
    """A `→ … (date)` marker inside an entry's BOLD TITLE is invisible (#411).

    `parse_answered` takes an entry's title as the first line and everything
    after it as the body, and `answered_at` reads only the body. A bold title
    that WRAPS across lines is legal and ordinary — 30 of 65 entries wrap — so
    wrapping itself is not the defect and erroring on it would red the corpus.
    The defect is the marker landing inside that wrapped span, where the reader
    structurally cannot see it: the entry renders as never resolved, and the
    `#411` WARN that should have caught it names "dropped marker" for something
    that was written, just in the wrong place.

    Three of the five undated entries found on 2026-07-29 were this, not
    dropped markers — and the repair itself hit it twice, because the first
    attempt inserted the head INSIDE #264's wrapped title and the entry stayed
    undated. Hence a check rather than a habit: the position is invisible in the
    text and the only symptom is a missing date on a different check's row.

    ERROR, because unlike an undated withdrawn ask there is no legitimate
    reading of a marker in the title — it is always a misplacement, and the
    entry it describes always renders wrong.
    """
    path = dw / "questions.md"
    if not path.exists() or watch is None:
        return
    text = path.read_text()
    # The title span runs from the entry head to the line that closes its bold
    # run. Derived from the file, so a corpus that stops wrapping does not
    # quietly turn this check into a no-op -- the precondition below says so.
    entries = list(re.finditer(r"(?m)^- \*\*.*?(?=^- \*\*|\Z)", text, re.S))
    wrapped = 0
    offenders = []
    for m in entries:
        lines = m.group(0).split("\n")
        span = [lines[0]]
        if lines[0].count("**") < 2:                  # title continues
            wrapped += 1
            for ln in lines[1:]:
                span.append(ln)
                if "**" in ln:
                    break
        title_span = "\n".join(span)
        if watch.RESOLVED_AT.search(title_span):
            offenders.append(lines[0].strip()[:64])
    if not entries:
        return                          # check_questions owns unparseable
    # The precondition this check depends on: at least one entry's title
    # actually wraps. If none does, there is no multi-line span for a marker to
    # hide in and this check has no subject -- say so rather than passing.
    if offenders:
        rep.add(
            ERROR,
            "questions.md",
            f"{len(offenders)} entr(y/ies) carry a `→ … (date)` marker INSIDE "
            f"the wrapped bold title, where `answered_at` cannot see it — move "
            f"it to the head of the body: {'; '.join(offenders[:3])} (#411)")
        return
    # Silent on success, like `check_answered_resolution_dates` above:
    # `check_questions` owns this file's OK row and a second one fragments the
    # summary. Unlike a coverage check, this one needs no vacuity guard on the
    # live corpus — if no title wrapped, the defect would be *impossible*
    # rather than merely unobserved, so silence is the honest state. The
    # precondition that at least one title wraps is asserted where it can
    # actually expire: in the test, derived from its fixture.


# Same shape as watch.RESOLVED_AT but unanchored: the stranded marker this
# check hunts has already been absorbed INTO a sub-bullet's text, so it no
# longer sits at a line start and the anchored pattern cannot find it.
_RESOLVED_IN_TEXT = re.compile(r"→[^:\n]*?\(\d{4}-\d{2}-\d{2}")


def check_resolution_marker_after_subbullet(dw: Path, watch, rep: Report) -> None:
    """A `→ answered` marker AFTER a nested `- **` bullet never reaches the
    body (#467).

    `_parse_entries` invariant 3: a sub-bullet absorbs every following
    non-bullet line as its own wrapped continuation, and only a blank line
    (or a plain `- ` bullet) releases it. So a resolution marker written
    after an `Answer`/`Note` sub-bullet is swallowed into that sub-bullet's
    text — it never lands in `body`, `answered_at` returns None, the fold
    looks done, and the #411 WARN reports a *dropped* marker for one that
    was written, just in the wrong place. Measured 2026-07-29 folding his
    `#445` answer; moving the marker above the answer line fixed it
    instantly. Third instance of the #411 family: dropped (`#264`, `#263`),
    trapped inside a wrapped title, and now orphaned past a nested bullet.

    The unreachable test is the PARSER's, not a position heuristic: an entry
    offends when `answered_at` sees no marker AND the marker text is found
    inside a sub-bullet the parser did absorb. That keeps the check honest
    about the one wrinkle in invariant 3 — a blank line between the bullet
    and the marker releases the marker back into the body, and that marker
    is legal here no matter how odd it looks.

    ERROR, because unlike an undated withdrawn ask there is no legitimate
    reading of a marker the reader structurally cannot see — it is always a
    misplacement, and the entry it describes always renders wrong.
    """
    path = dw / "questions.md"
    if not path.exists() or watch is None:
        return
    try:
        items = watch.parse_answered(path.read_text())
    except Exception:
        return                          # check_questions owns unparseable
    offenders = []
    for it in items:
        if watch.answered_at(it["body"]) is not None:
            continue                    # the reader sees a marker; legal
        for f in it.get("follows", []):
            if _RESOLVED_IN_TEXT.search(f.get("text", "")):
                offenders.append(it["title"].strip()[:64])
                break
    if not offenders:
        # Silent on success, like its #411 siblings: `check_questions` owns
        # this file's OK row and a second one fragments the summary. The
        # precondition (the fixture's marker is genuinely unreachable) is
        # asserted where it can expire: in the test, derived from the real
        # parser rather than trusted from the fixture's layout.
        return
    sample = "; ".join(offenders[:3])
    more = "" if len(offenders) <= 3 else f"; +{len(offenders) - 3} more"
    rep.add(
        ERROR,
        "questions.md",
        f"{len(offenders)} answered entr(y/ies) carry a `→ answered` marker "
        f"AFTER a nested `- **` sub-bullet, where the parser absorbs it into "
        f"the sub-bullet and `answered_at` cannot see it — move the marker "
        f"above the first sub-bullet, to the head of the body: "
        f"{sample}{more} (#467)")


# ── a fold must not drop a sub-decision (#421 B) ─────────────────────
# The defect this exists for, stated in the ask that granted it: `#275`'s
# Q3/Q5/Q6 sat unanswered for days with nothing noticing, because a multi-
# part ask can be HALF answered, the entry folded on the strength of the
# parts that were, and the remainder becomes invisible — nothing ever
# re-reads a folded entry. His ruling (`#421`, 2026-07-29 01:17, `rec`:
# A+B+D) made "lint errors when a fold drops a sub-decision" the buildable
# half (B), and this is it.
#
# RECOGNISING A SUB-DECISION MUST NOT BE A GUESS FROM PROSE. The corpus
# labels decisions `Q1`/`Q2`, `M1`/`M2`/`M3`, `S1`–`S4`, `C1`–`C4`,
# `H1`/`H2`, `I1`, `R1`–`R3`, … — 49 distinct `**L<n>**` forms across 139
# lines, all declared in FREEFORM PROSE (`**Q1 — open the gate…**`,
# `**Ask: \`C1\`, \`C2\`…**`). Deriving "which tokens are decisions" from
# that is the half-working-regex failure this repo has paid for most, so
# the contract instead gives the ask ONE canonical declaration line and
# the check reads ONLY that line — stated in `file-formats.md` in the same
# commit as this code (the format never ships ahead of the parser).
SUBDEC_DECL = re.compile(r"\*\*\s*Sub-decisions:\s*\*\*\s*(.+)")
# A declared sub-decision is a backticked `<Letter><digits>` token, matching
# the `**Ask: \`C1\`, \`C2\`, \`C3\`, \`C4\`**` backtick-comma style already
# in the corpus. Letter-then-digits is narrow on purpose: it excludes
# `#264`, `P1` (a priority band, not a decision) and bare numbers.
SUBDEC_LABEL = re.compile(r"`([A-Z]\d+)`")



def _answered_split(raw: str) -> int:
    """Offset of the literal `## Answered` heading, or 0 if absent.

    Anchored (`^…$`, MULTILINE) rather than a substring search: the phrase
    appears inside entry prose in this corpus, and an unanchored split has
    corrupted this repo's sectioned files twice — once writing 130 lines into
    the wrong half of tasks.md. Returns 0 when absent so callers fall back to
    the whole file rather than silently seeing an empty open half.
    """
    m = re.search(r"^## Answered[ \t]*$", raw, re.M)
    return m.start() if m else 0

def check_subdecisions(dw: Path, watch, rep: Report) -> None:
    """#421 B: a folded entry that drops a declared sub-decision is an ERROR.

    A multi-part ask can be half-answered, and half is the dangerous state:
    the entry gets folded on the strength of the parts that WERE answered,
    and the unanswered remainder becomes invisible because nothing ever re-
    reads a folded entry. `#275`'s Q3/Q5/Q6 sat open for days exactly that
    way. This check makes a fold that drops a declared sub-decision loud.

    **Recognising a sub-decision is declared, not guessed.** The corpus
    labels decisions in freeform prose (`Q1`, `M1`, `S1`…), and inferring
    them is the half-working-regex failure mode this repo distrusts most.
    So the contract gives an ask ONE canonical declaration — a bold line
    opening `**Sub-decisions:**` then backticked `Q1`, `Q2`, `Q3` — and
    this reads ONLY that line, never prose. The form is documented in
    `file-formats.md` (the ask contract, clause B) in the same commit as
    this code.

    **History handling: the marker is its own content-resolved cutoff.**
    An entry that does NOT declare its sub-decisions is not examined — so
    the entire historical corpus (which predates the marker) is silent,
    and the live tree stays clean on day one. The marker's PRESENCE is the
    claim "these sub-decisions were declared under the rule and must be
    resolved at fold", which makes scope content-resolved without a sha
    pinned by hand (immune to rebase, cherry-pick and shallow clone — the
    objections that made `#405` refuse a hand-pinned cutoff).

    **A fold resolves a declared label** if the label appears as a token
    (word-bounded `<Letter><digits>`) anywhere in the folded entry OUTSIDE
    the declaration line — covering the `→ answered`/`→ resolved` head (which
    names labels in plain text as often as bold: `→ answered (…): D1` is a
    real shape), a `Rec **Q1**` decision, and an `Answer (…)` bullet in one
    rule. The precision concern that runs through this file — *recognising*
    a sub-decision — is held by the DECLARATION (only a declared label is
    checked, never prose), so a token match against the fold of a short
    decision record is honest. A declared label that appears in NONE of
    those zones was dropped, and that is the ERROR his ruling names.

    The recording half of B ("an unanswered sub-decision is recorded") is
    satisfied by the SAME rule: a fold that carries a sub-decision forward
    NAMES it in the head (`→ answered (…): rec on Q1; Q2/Q3 carried
    forward`), so naming-it is both the resolution and the record. There
    is no second store.
    """
    if watch is None:
        return                          # parse_answered belongs to watch.py
    path = dw / "questions.md"
    if not path.exists():
        return                          # check_questions owns the absent case
    try:
        raw = path.read_text()
        items = watch.parse_answered(raw)
    except Exception:
        return                          # check_questions owns unparseable
    # The dormancy discipline (#430): a check whose data has not been adopted
    # yet CANNOT go red, so it rots unnoticed. The count must be VISIBLE once
    # there is a subject, never an error on zero. The subject is "a
    # declaration marker exists anywhere in this file" — scanning the raw text
    # (open AND answered), because a marker on an OPEN entry (#275 today) is a
    # future subject for this check even though the check's ERROR domain is
    # the fold. Pre-adoption (no marker anywhere) the check is SILENT, the
    # same convention every other clean questions.md check follows
    # (check_answered_resolution_dates, check_author_tags): a clean file shows
    # exactly one OK row, from check_questions, and a second row here would
    # break that invariant on every target. The marker's presence is the
    # switch: silent until a declaration exists, visible the moment one lands.
    has_subject = SUBDEC_DECL.search(raw) is not None
    examined = 0
    declared_total = 0
    for it in items:
        body = it.get("body", "") or ""
        dm = SUBDEC_DECL.search(body)
        if not dm:
            continue                    # no declaration -> not under the rule
        declared = SUBDEC_LABEL.findall(dm.group(1))
        if not declared:
            continue                    # declaration present but label-free:
                                        # malformed, not a dropped decision;
                                        # check_questions' shape rules own it
        declared_total += len(dict.fromkeys(declared))
        examined += 1
        # The resolution evidence is the WHOLE folded entry — title, body
        # with the declaration line removed, and every retained follow-up
        # (Answer/Note/Follow-up bullets are lifted into `follows` for
        # Answered entries, not kept in `body`). The declaration line is
        # excluded so a label that appears ONLY in its own declaration is
        # not mistaken for resolved. `dm.start()`..`dm.end()` spans the
        # whole `**Sub-decisions:** …` match on line-joined body text.
        follows_text = " ".join(f.get("text", "") for f in it.get("follows", []))
        evidence = (it.get("title", "") + " "
                    + body[:dm.start()] + body[dm.end():] + " "
                    + follows_text)
        resolved = set()
        for lab in declared:
            # Word-bounded token match: accepts `rec on Q1` (plain) in the
            # head, `**Q1**` (bold), `` `Q1` `` (backtick) and `Q1 yes` in
            # a retained Answer follow-up. THE production line whose change
            # reds the check — make this unconditionally True and a dropped
            # label stops erroring (the dropped-subdecision red proves it).
            if re.search(rf"\b{re.escape(lab)}\b", evidence):
                resolved.add(lab)
        dropped = [lab for lab in dict.fromkeys(declared) if lab not in resolved]
        if dropped:
            title = (it.get("title") or "").strip()
            short = title[:56] + ("…" if len(title) > 56 else "")
            rep.add(
                ERROR, "questions.md",
                f"{short} was folded but drops declared sub-decision(s) "
                f"{', '.join(dropped)} — a multi-part ask can be half-"
                f"answered and the remainder becomes invisible once folded "
                f"(#421 B): name each carried-forward label in the "
                f"`→ answered` head, or leave it open",
            )
    # Coverage is emitted when a declaration marker exists anywhere in the
    # file (open or answered) — so the check is VISIBLE once it has a
    # subject (#430), but silent pre-adoption alongside every other clean
    # questions.md check. Never ERROR on zero: a check that fails because a
    # convention is unadopted blocks commits for an unrelated reason. The
    # counts are the folded-side examination, derived at runtime.
    if has_subject and not rep.failed:
        # The row also names the OPEN declarations, because `0 folded, 0
        # checked` reads as "nothing here" when it actually means "adopted,
        # waiting for a fold". Adoption progress and examination coverage are
        # different facts and a reader needs both: on the day the convention
        # landed this row is 0/0 with a pending count, and the pending count
        # is what says the check has a future subject rather than no subject.
        # Derived from the open half at runtime, never a literal.
        open_half = raw[:_answered_split(raw)] if _answered_split(raw) else raw
        pending = sum(1 for m in SUBDEC_DECL.finditer(open_half)
                      if SUBDEC_LABEL.findall(m.group(1)))
        rep.add(
            OK, "questions.md",
            f"{examined} folded entr{'y' if examined == 1 else 'ies'} "
            f"examined, {declared_total} declared sub-decision"
            f"{'s' if declared_total != 1 else ''} checked"
            + (f"; {pending} open ask{'s' if pending != 1 else ''} declare"
               f"{'' if pending != 1 else 's'} sub-decisions and will be "
               f"checked at fold" if pending else "")
            + " (#421 B)")


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


def _indent_body_continuations(entry_text: str) -> str:
    """Indent non-blank column-0 lines after the head so the entry reparses.

    `ledger_entries` ends an entry at the first column-0 line that is not a
    head, and that rule is load-bearing (the prose under `## Recently landed`
    is not entries and must never join one) — it is NOT widened here. But a
    store body holds multi-paragraph prose and pasted output at column 0, and
    fed to `ledger_entries` verbatim every such line ends the entry, so the
    text after it is invisible to every text-consuming check (#696). This
    projection step — applied only when `ledger_view` synthesises ledger text
    from store rows — indents each non-blank continuation line (every line
    after the head) with ONE leading space, so `ledger_entries` keeps it.

    ONE space: `ledger_entries` admits any line whose first char is space/tab,
    and one space cannot be read as a note (`  · `), a head (`ENTRY_HEAD` is
    `^-`, anchored at column 0, so ` - **#N**` does not match), or a marker.
    The stored body and its digest are untouched — this is a read-side act.
    """
    lines = entry_text.split("\n")
    for i in range(1, len(lines)):
        if lines[i] and lines[i][0] not in " \t":
            lines[i] = " " + lines[i]
    return "\n".join(lines)


def ledger_view(dw: Path):
    """``(text, source)`` for every ledger-content check — the #294 dispatch.

    ``text, source = ledger_view(dw)`` — ``dw`` is the ``.dreamwork/``
    directory, not ``tasks.md``; the return is a tuple, so a single-name
    assign fails late and confusingly (#697).

    ``source == 'markdown'`` (today, and every target that never cuts over):
    ``text`` is ``tasks.md`` verbatim and every check runs exactly as it
    always has. ``source == 'store'`` (the cutover watermark is present):
    ``text`` is SYNTHESIZED from the store — `store_entries` returns every
    row with a ``- **#N**`` head (verbatim for the import's headed bodies,
    synthesized from the store columns for the `file` verb's headless ones,
    #557), so the bodies reparse; they are placed under synthesized
    ``## Open`` / ``## Recently landed`` headings in id order. Every text-consuming check then runs over live store data
    with no change to its own code, and `watch.parse_ledger` over the
    synthesized text returns the store's id sets.

    The dispatch fails closed toward Markdown: `source_of_truth` itself
    answers ``'markdown'`` on a missing or unreadable store, and any error
    building the projection falls through to the Markdown path — lint must
    never go blind because the flip machinery had a bad day. In store mode
    ``tasks.md`` is a one-line #458 shim, so the Markdown path would see an
    empty ledger; that case means the store projection failed, which is a
    finding about the store, and the section check's history half (against
    ``tasks.md.deprecated``) still runs below.
    """
    if str(dw).endswith(".md"):  # #697 — dw is .dreamwork/, not tasks.md
        raise TypeError(
            "ledger_view(dw) takes the .dreamwork/ directory, not tasks.md — "
            "pass dw and unpack the tuple: text, source = ledger_view(dw)."
        )
    try:
        if source_of_truth(dw) == "store":
            entries = store_entries(dw)
            open_ids, landed_ids = store_ids_by_state(dw)
            oset, lset = set(open_ids), set(landed_ids)
            # #696: indent column-0 body continuation lines so ledger_entries
            # keeps multi-paragraph prose and pasted output instead of ending
            # the entry at the first column-0 line (silently losing the text).
            open_bodies = [_indent_body_continuations(b)
                           for ids, b in entries if str(ids[0]) in oset]
            landed_bodies = [_indent_body_continuations(b)
                             for ids, b in entries if str(ids[0]) in lset]
            text = ("## Open\n\n" + "\n\n".join(open_bodies)
                    + "\n\n## Recently landed\n\n"
                    + "\n\n".join(landed_bodies) + "\n")
            return text, "store"
    except Exception:
        pass  # fall through to Markdown — never let the dispatch blind lint
    path = dw / "tasks.md"
    if not path.exists():
        return None, "markdown"
    return path.read_text(), "markdown"


def shared_store_for_worktree(dw: Path) -> Path | None:
    """The MAIN checkout's ledger store when ``dw`` sits in a linked worktree,
    else ``None``. Existence is the caller's question; this only resolves it.

    #592, the defect this exists for. ``ledger.sqlite3`` is gitignored (#294 —
    it is machine-local), so it can never appear in a linked worktree. But
    `source_of_truth` reads the cutover watermark OUT OF that very file, so an
    absent store answers ``'markdown'`` — indistinguishable from a repo that
    never cut over — and `check_tasks` falls through to the #458 migration
    notice shim, which has no ``Next id`` header. Every lane worktree therefore
    ended its verification on a FALSE ERROR, and three consecutive hand-offs
    taught the next lane that a lint ERROR is background noise.

    Discriminating on "am I in a worktree?" ALONE would be a blanket silence,
    so this hands back the shared checkout's store PATH and the caller requires
    it to exist: a ledger that is genuinely gone stays a loud ERROR even when
    the complaint is raised from inside a worktree. Only the path's EXISTENCE
    is ever consulted — never its contents — so lint's findings still describe
    nothing but its own ``--target``.

    The link is read from git's own record: a linked worktree's ``.git`` is a
    FILE holding ``gitdir: <common>/worktrees/<name>``, where a main checkout's
    is a directory. That is a fact on disk rather than a subprocess, so the
    answer cannot depend on whether `git` is runnable, and every branch below
    fails toward ``None`` — toward the ERROR — on anything unexpected.
    """
    if store_path(dw).exists():
        return None  # the store is right here; nothing to excuse
    dot_git = dw.parent / ".git"
    if not dot_git.is_file():
        return None  # a main checkout (`.git/` dir) is never excused
    try:
        pointer = dot_git.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not pointer.startswith("gitdir:"):
        return None
    gitdir = Path(pointer[len("gitdir:"):].strip())
    if not gitdir.is_absolute():
        gitdir = (dw.parent / gitdir).resolve()
    # `<common>/worktrees/<name>` — anything else is not a linked worktree.
    if gitdir.parent.name != "worktrees":
        return None
    return store_path(gitdir.parent.parent.parent / ".dreamwork")


def note_ledger_skip(rep: Report, check: str) -> None:
    """Record that ``check`` was called and examined NO ledger entries.

    #611, and the same house rule #592's WARN was written to obey: *a check
    that did not run must say so, because silent absence reads as a pass.*
    After #592 the `tasks.md` row honestly WARNs in a lane worktree, but its
    neighbours went on printing nothing at all — measured on the live repo,
    `lint --target <worktree>` lost `origin recorded on all 390 entries`,
    `section split agrees with watch.py`, and all 7 of #323's stale-open WARNs
    without a word about any of them. A reader scanning that report sees no
    complaint from those checks and concludes they had none.

    The skip is RECORDED rather than reported here so `check_ledger_skips`
    can render one row naming every skipped check. Six rows each saying "the
    ledger did not travel" is the volume failure #612 closes, and it buys
    nothing: the cause is one cause. Each call site sits at the check's own
    existing silent-return, so the list is derived from the code that actually
    skipped and cannot drift from it the way a hand-written list of "checks
    that skip in a worktree" would (`lessons.md:405` in reverse — the fix is
    the row, not a second description of it).

    The predicate is uniform and deliberately narrow: **the ledger text held
    no entries at all.** A check that examined every entry and found none in
    scope (all ids predate #216 for `check_task_origins`; nothing landed yet
    for `check_landed_asks`) really did run, and must not be reported as
    skipped — otherwise a fresh project, whose ledger legitimately starts at
    #1, would carry this row forever and it would become the ignored row this
    exists to prevent.
    """
    if check not in rep.ledger_skips:
        rep.ledger_skips.append(check)


def check_ledger_skips(rep: Report) -> None:
    """#611: ONE row naming every ledger check that examined nothing.

    Runs last, because the skipping checks are spread across `run_checks` and
    each can only speak for itself. Silent when nothing skipped — a row that
    is always present is a row nobody reads, which is the failure this is
    supposed to prevent rather than cause. WARN, never ERROR: not having run
    is not a defect in the target, it is missing coverage in the report, and
    #592's precedent is that the honest answer to "did not run" is a warning
    that says so.
    """
    if not rep.ledger_skips:
        return
    names = ", ".join(rep.ledger_skips)
    rep.add(WARN, "ledger checks", (
        f"{len(rep.ledger_skips)} check(s) examined NOTHING and must not be "
        f"read as passing: {names} — the ledger text they were handed holds "
        f"no entries (in a lane worktree the gitignored store cannot travel; "
        f"see the `tasks.md` row). Lint the main checkout for their "
        f"findings (#611)"))


def check_tasks(dw: Path, rep: Report) -> None:
    """The ledger. Its ids are permanent, so a collision is unrecoverable."""
    text, source = ledger_view(dw)
    if text is None:
        rep.add(WARN, "tasks.md", "absent — required only when the backend is session-scoped")
        return

    if source == "store":
        # The store is the sequence authority (AUTOINCREMENT, seeded and
        # verified at import; an unseeded store refuses to open). The
        # duplicate-id and `Next id` header invariants below are Markdown
        # file invariants — the store enforces them by PRIMARY KEY and by
        # construction, so lint's job here is to prove the projection
        # parses, not to re-check what one source cannot violate.
        ids = [int(x) for m in LEDGER_ID.findall(text)
               for x in ENTRY_ID.findall(m)]
        if not ids:
            rep.add(ERROR, "ledger store",
                    "store mode but the projection parses to zero ids — "
                    "the flip machinery is suspect, not the ledger")
        else:
            rep.add(OK, "ledger store",
                    f"{len(ids)} ids projected from the store (sequence "
                    f"authority: AUTOINCREMENT in the store)")
        check_task_origins(text, rep)
        check_ledger_sections(dw, text, source, rep)
        check_landed_still_open(dw, text, rep)
        check_self_completed_open(dw, text, rep)
        return


    # LEDGER_ID captures an ids-only span (`#7` or `#7/#8`); a combined head
    # names every id in it, so extract each id with ENTRY_ID rather than
    # int() on the span itself, which would choke on the slash (#315).
    ids = [int(x) for m in LEDGER_ID.findall(text) for x in ENTRY_ID.findall(m)]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        rep.add(ERROR, "tasks.md", f"duplicate id(s) {dupes} — two entries claim one permanent id")

    m = NEXT_ID.search(text)
    if not m:
        # #592: in a linked worktree the gitignored store cannot have
        # travelled, so this text is the #458 migration shim and the missing
        # header is an artefact of WHERE lint is standing, not a defect. Only
        # excused when all three hold: the shared checkout really does carry
        # the store, this really is a linked worktree, and the text really is
        # the migration notice — a tasks.md that merely lacks a header still
        # ERRORs, here as anywhere.
        shared = shared_store_for_worktree(dw)
        if shared is not None and shared.exists() and parse_notice(text):
            rep.add(WARN, "tasks.md", (
                f"ledger absent (worktree) — `{store_path(dw).name}` is "
                f"gitignored and does not travel; the shared store is "
                f"{shared}. The ledger checks did not run here (this row is "
                f"the refusal to fake having run) — lint the main checkout "
                f"for them"))
        else:
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
    check_ledger_sections(dw, text, source, rep)
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
    # headings: it is a shared helper (ledger_parse.open_section_text, #352)
    # with its own pinned tests, and a second caller's need is a poor reason
    # to widen it.
    open_text = open_section_text(text)
    if open_text is None:
        # #611. git named close/merge commits (we got past `not closed`), so
        # there was real work to compare against and no ledger to compare it
        # to. On the live repo this is where all 7 stale-open WARNs vanish
        # inside a worktree.
        note_ledger_skip(rep, "check_landed_still_open")
        return

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
        note_ledger_skip(rep, "check_self_completed_open")  # #611
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
    qpath = dw / "questions.md"
    if watch is None or not qpath.exists():
        return
    text, _source = ledger_view(dw)
    if text is None:
        note_ledger_skip(rep, "check_landed_asks")  # #611
        return
    try:
        open_ids, landed = watch.parse_ledger(text)
        asks = watch.parse_open_questions(qpath.read_text())
    except Exception:
        return  # the shape checks above own reporting an unreadable file
    if not open_ids and not landed:
        # #611: no ids in EITHER section — the ledger held nothing, so no ask
        # was correlated against anything. Distinct from the `not landed`
        # return below, which is a real correlation over a ledger whose work
        # has simply not landed yet (every fresh project); reporting that as
        # a skip would make this row permanent and therefore ignored.
        note_ledger_skip(rep, "check_landed_asks")
        return
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


def check_ledger_sections(dw: Path, text: str, source: str, rep: Report) -> None:
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

    **Store mode (#294):** the cross-check is vacuous over the synthesized
    projection (one source cannot disagree with itself), so its subject
    becomes the FROZEN HISTORY — `tasks.md.deprecated`, which the design
    says is never deleted automatically. The two readers run over THAT
    file: it must exist, it must parse to a non-empty id set, and the two
    counts must agree. A hand-edit of the deprecated file desyncs it
    exactly the way #304's original bug did, and the check stays live.
    """
    # #555 — conflict markers in the ledger. parse_ledger keys on `## Open`
    # and entry heads, so a marker line is silent to BOTH readers this check
    # cross-checks — the same #548/#554 defect, in the most parse-sensitive
    # file in the repo. `text` is tasks.md verbatim in markdown mode and the
    # store projection in store mode (a marker in either is corruption).
    # Scanned from the raw text BEFORE the source branch: the hazard is
    # independent of which backend holds the ledger. One ERROR per line.
    # The deprecated file (store mode) has its OWN scan below — both files
    # route through this one check, but via different variables (`text` param
    # vs the `dtext` local in the store branch), so a single loop cannot
    # cover both. Reuses the ONE #554 regex.
    for ln in text.splitlines():
        m = CONFLICT_MARKER_RE.match(ln)
        if m:
            rep.add(
                ERROR, "tasks.md",
                f"conflict marker `{m.group(0)}` at line start ({ln!r}) — a "
                f"merge-conflict marker left in the ledger is silent to "
                f"parse_ledger; resolve and remove it (#555)")
    if source == "store":
        dep = dw / "tasks.md.deprecated"
        if not dep.exists():
            rep.add(ERROR, "tasks.md.deprecated",
                    "absent in store mode — the design's rule is NEVER "
                    "delete the deprecated ledger automatically; its loss "
                    "is the history's loss (#294 R4)")
            return
        try:
            import watch
            dtext = dep.read_text()
            dopen, dlanded = watch.parse_ledger(dtext)
        except Exception:
            rep.add(ERROR, "tasks.md.deprecated",
                    "unreadable or unparseable in store mode — the frozen "
                    "history must stay parseable (#294 R4)")
            return
        if not dopen and not dlanded:
            rep.add(ERROR, "tasks.md.deprecated",
                    "parses to zero ids in store mode — the history file "
                    "has rotted or been replaced (#294 R4)")
            return
        # #555 — the FROZEN history rots the same silent way: a marker line
        # is invisible to parse_ledger, so it must be LOUD here. This is the
        # second scan site for the ledger family: `tasks.md.deprecated` is
        # read only in this store branch (as `dtext`), so the `text` scan at
        # the top of the function cannot reach it.
        for ln in dtext.splitlines():
            m = CONFLICT_MARKER_RE.match(ln)
            if m:
                rep.add(
                    ERROR, "tasks.md.deprecated",
                    f"conflict marker `{m.group(0)}` at line start ({ln!r}) "
                    f"— a merge-conflict marker left in the frozen history "
                    f"is silent to parse_ledger; resolve and remove it (#555)")
        section, mine = None, 0
        for ln in dtext.splitlines():
            stripped = ln.strip()
            if stripped.startswith("## "):
                section = stripped
            elif section == "## " + "Open":
                m = LEDGER_ID.match(ln)
                if m:
                    mine += len(ENTRY_ID.findall(m.group(1)))
        if len(dopen) != mine:
            rep.add(ERROR, "tasks.md.deprecated",
                    f"open-id count disagrees on the FROZEN history: this "
                    f"linter counts {mine}, watch.parse_ledger sees "
                    f"{len(dopen)} — a hand-edit of the deprecated file "
                    f"moved a section boundary (#304, history half)")
        else:
            rep.add(OK, "tasks.md.deprecated",
                    f"frozen history intact ({len(dopen)} open / "
                    f"{len(dlanded)} landed, two readers agree)")
        return

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
        # A ledger with no headings at all is another check's problem — but
        # the CROSS-CHECK still did not happen, and #611 is that saying
        # nothing about that reads as the two readers having agreed.
        note_ledger_skip(rep, "check_ledger_sections")
        return

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
    checked = errors = seen = 0
    for ids, body in ledger_entries(text):
        seen += 1
        if not ids or max(ids) < ORIGIN_CUTOFF:
            continue
        checked += 1
        name = "/".join(f"#{i}" for i in ids)
        # Head-authoritative (#696): body prose that quotes `origin: **x**`
        # must not double the head's claim now that the projection makes
        # body continuation lines visible. ORIGIN_MARK is still imported for
        # the callers that read it from lint's namespace.
        marks = origin_marks(body)
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
    if not seen:
        # #611: no entries AT ALL — this check looked at nothing, which is
        # not the same as finding nothing wrong. `seen` rather than `checked`:
        # a ledger whose ids all predate the cutoff WAS examined in full.
        note_ledger_skip(rep, "check_task_origins")
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
    text, _source = ledger_view(dw)
    if text is None:
        note_ledger_skip(rep, "check_human_blocker")  # #611
        return
    # Slice the Open section once, the shared ledger_parse idiom (#352) that
    # check_landed_still_open also uses, so only OPEN entries are governed —
    # a landed entry is not "blocked on him".
    open_text = open_section_text(text)
    if open_text is None:
        note_ledger_skip(rep, "check_human_blocker")  # #611
        return

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
    # Store mode (#294 T2): `current_task_ids` and per-agent `task_ids` are
    # RETIRED fields — the store is the one source for what is in flight.
    # Their typing is moot; their ABSENCE is the invariant, owned by
    # check_retired_status_fields_absent below. Skip, or a target mid-cutover
    # lints red on a field that is about to be deleted.
    if source_of_truth(dw) == "store":
        return
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

    **Store mode (#294 T2) — this check INVERTS.** The cutover deletes
    `queue`, `current_task_ids` and per-agent `task_ids` from `status.json`
    (the store is the one source; the disagreement this WARN measured
    disappears by construction). A drift check whose compared fields no
    longer exist would pass vacuously — examining nothing is the hollow-
    check failure this repo keeps paying for. So in store mode the invariant
    is the inverse: the three retired fields must stay ABSENT. Same shape as
    #303's append-only `.status-keys` memo — a field that reappears is a
    REGRESSION (a second derived truth regrowing), not a drift, so it is an
    ERROR, never a WARN.
    """
    if source_of_truth(dw) == "store":
        path = dw / "status.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(data, dict):
            return
        regrown = [k for k in ("queue", "current_task_ids") if k in data]
        agents = data.get("agents")
        if isinstance(agents, list):
            for a in agents:
                if isinstance(a, dict) and "task_ids" in a:
                    regrown.append(f"agents[{a.get('name', '?')}].task_ids")
        if regrown:
            rep.add(
                ERROR,
                "status.json",
                f"retired field(s) reappeared post-cutover: "
                f"{', '.join(regrown)} — the store is the one source for "
                f"queue depth and in-flight tasks; a regrown field is a "
                f"second derived truth (#294 T2 / #362 inverse)",
            )
        else:
            rep.add(OK, "status.json",
                    "retired fields (queue, current_task_ids, agent task_ids) "
                    "stay absent — one source, nothing to drift")
        return
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
    # Shared argv[2] validator for the guards, not a guard: it asserts nothing
    # about the product — it refuses a missing or all-digits <outdir> (the
    # port-as-outdir mistake that mkdir'd `39898/` in the repo root) before any
    # guard makes its directory. One copy of the refusal; the guards that call
    # it are the checks. Its binding tests live in test_guard_argv.py. (#376)
    "outdir",
    # Shared server starter for the guards that run their OWN watch.py, not a
    # guard: it asserts nothing about the product. It exists because those
    # guards spawn with `stdio: 'ignore'` and then `sleep`, so a port already
    # held meant python exited invisibly and every later assertion graded a
    # stale server's target. One copy of "prove the responder is ours". (#461)
    "serve",
    # Shared DOM reader for the dock guards, not a guard: it asserts nothing and
    # gates nothing. It exists because docktarget and noteprop both had to ask
    # "is this still the question I docked?" of rendered text, and #385 put a live
    # age inside that headline -- one copy of the strip-the-age rule, so the next
    # thing added to a headline cannot red two guards again. (#413)
    "dom",
    "beautycap", "cmdcap", "menucap", "reviewcap",  # capture tools, for looking
    "optrace", "rm-check2", "worldspace",
    # A perf A/B capture, not a guard: it measures rAF throughput in the
    # question->review dissolve under several filter conditions and prints the
    # distribution. A perf threshold on this never-idle host is a load-meter,
    # not a check (#444 ground); the motion guard for this gesture is
    # dissolve.mjs (transitionstart-based). (#449)
    "dissolveperf",
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


# #693: the commit.cleanup values that PRESERVE '#' lines. This repo puts the
# task id at the START of every commit subject, so the subject IS a '#' line.
# On the editor path — which `git rebase --continue` uses — the default
# 'strip' cleanup deletes every line beginning with '#', silently losing the
# id and the landing-discovery route it carries (#404). 'default' behaves as
# 'strip' when a comment character is in use, and an UNSET value resolves to
# 'default', so unset / empty / strip / default all eat '#' lines. These three
# are the exhaustive set that do not (git's own closed set of cleanup modes);
# the check is an allowlist rather than "is it set" because 'strip' and
# 'default' are SET and non-empty and both eat the subject — the exact
# false-green a presence-only check would pass on.
COMMIT_CLEANUP_SAFE = frozenset({"whitespace", "verbatim", "scissors"})


def check_commit_cleanup(dw: Path, rep: Report) -> None:
    """commit.cleanup must preserve '#' lines — subjects start with #NNN (#693).

    `.git/config` is not tracked, so the mitigation does not survive a fresh
    clone, a new machine, or a re-init: a lesson that does not become a check
    is a lesson waiting to be re-learned, and the cost of re-learning it is
    silent data loss of the id that makes a landing discoverable. Takes the
    repo root (``dw.parent``), not a ``.dreamwork/`` file, because the value
    lives in git's config. Skips silently when not inside a git work tree:
    `git config --get` exits 1 both for unset-in-a-repo and for a plain
    directory (it reads global/system config without needing a repo), so the
    two are indistinguishable from its exit code — and a synthetic target
    that is not a git repo must not ERROR on a config it has no place to set.
    """
    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=dw.parent, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return
    if inside.returncode != 0:
        return  # not a git repo — nothing to check, nothing to report
    try:
        out = subprocess.run(
            ["git", "config", "--get", "commit.cleanup"],
            cwd=dw.parent, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return
    raw = out.stdout.strip()
    if raw in COMMIT_CLEANUP_SAFE:
        rep.add(OK, "commit.cleanup", f"'{raw}' preserves '#' lines")
    else:
        shown = raw if raw else "<unset> (defaults to strip on the editor path)"
        rep.add(
            ERROR, "commit.cleanup",
            f"{shown} — eats '#' lines on the editor path "
            f"(git rebase --continue), and commit subjects start with '#NNN'; "
            f"the id is silently deleted and the landing becomes "
            f"undiscoverable (#693, #404). Run: git config commit.cleanup scissors",
        )


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


# #471 — registration is not execution. A guard in DEFAULT_GUARDS gates
# nothing if it never reaches an assertion: the #471 guards threw in
# serveVerified (the shared port was held by a server for a different
# target) before any ok() call, so each got a recipe-level FAIL line,
# GATED NOTHING for 3.5 hours, and the suite reported "N registered" the
# whole time. The signal that a guard ACTUALLY ran and judged lives in its
# own output, not in the recipe's exit-branch: every guard — the
# report.mjs users AND the guards that inline the same idiom — emits
# genuine `PASS <name>` / `FAIL <name>` verdict lines via ok()/present(),
# and marks a pre-judgment death with the crash sentinel below. That
# sentinel is the marker for "did not judge", NOT a verdict, so "ran and
# judged" is defined as: at least one verdict line that is not the
# sentinel. A guard that asserts zero is indistinguishable from one that
# found nothing (CLAUDE.md: "a check that examines nothing looks identical
# to one that found nothing"), so zero-assertion == not-judged by
# construction — which is what makes the #471 shape (threw before any
# ok()) count as "did not execute" even though the recipe printed a line.
_CRASH_SENTINEL = "FAIL the guard threw before finishing its checks"
_GUARD_VERDICT = re.compile(r"^(PASS|FAIL) .*$", re.MULTILINE)


def ran_and_judged(log_text: str) -> bool:
    """True iff a guard's log shows it reached at least one real assertion.

    The complement of serveVerified-style death (#471): a guard that threw
    before its first ok() has no genuine verdict — only the crash sentinel,
    or an ``Error:`` stack and nothing. Genuine = a ``^(PASS|FAIL) `` line
    that is not exactly the sentinel. Tested on the real production line:
    this is the function ``guard-execution`` calls per guard log, not a
    fixture-built copy of the decision (the #469/#471 hollowness shape).
    """
    for m in _GUARD_VERDICT.finditer(log_text or ""):
        if m.group(0) != _CRASH_SENTINEL:
            return True
    return False


# The subcommand the `guards` recipe invokes after its per-guard loop. Named
# once so the recipe (justfile), the dispatcher (main), and the structural
# lint check all agree on the handle; a rename reddens check_guards_execution
# _accounting, which is the point.
GUARD_EXECUTION_HOOK = "guard-execution"


def check_client_dist(root: Path, rep: Report) -> None:
    """#653 — `client/dist/` must be built from the tree it is committed with.

    The #630 transition commits its build output, because `just deploy` ships
    committed state and the dashboard must come up from a plain checkout with
    no node. That trade buys a serve-time with no toolchain and costs exactly
    one failure mode: **staleness**. It cannot be made impossible without a
    serve-time build, which the no-node requirement refuses — so it is made
    impossible to MISS, and this is the commit-time half of that (the other is
    the same reading in `watch.serving_report`).

    ERROR, not WARN, and on purpose: a stale dist is a real divergence between
    what the repo says the design package is and what the builders say. WARN
    is for things worth knowing; this one has a one-command fix and naming it
    softly is how it would come to be ignored.

    `root` is the skill directory. A target that is not this repo has no
    `client_dist.py` beside a `watch.py`, and this says nothing there.
    """
    if not (root / "client_dist.py").exists() or not (root / "watch.py").exists():
        return
    reading = client_dist.check(str(root))
    state = reading.get("state")
    if state == client_dist.OK:
        rep.add(OK, "client/dist", reading.get("note") or "current")
        return
    detail = reading.get("note") or state
    fix = reading.get("fix")
    rep.add(ERROR, "client/dist",
            "%s%s" % (detail, (" — %s" % fix) if fix else ""))


def check_guards_execution_accounting(root: Path, rep: Report) -> None:
    """The guard runner must compare executed vs registered, not just run.

    `check_guards_registered` measures REGISTRATION (a file exists for each
    name) — that is the row that reported "N registered" while eight guards
    idled. The live measurement (which guards ran AND judged) can only be
    taken during a run, so it lives in the `guards` recipe, which calls
    ``lint.py guard-execution``. lint cannot watch a run; what it CAN do is
    refuse to let that measurement be silently deleted (the "became hollow"
    shape CLAUDE.md warns of): this reads the justfile and errors if the
    recipe no longer invokes the comparison.

    The can-it-be-skipped axis settles where the red lives and why both
    halves exist: the recipe comparison cannot be skipped inside a
    `just guards`/`just test` run — it feeds the exit code — and this check
    cannot be skipped inside a `just lint`/`just test` run, so deleting the
    measurement reddens one of the two gates a lane always runs.
    """
    justfile = root / "justfile"
    if not justfile.exists():
        return
    text = justfile.read_text(encoding="utf-8")
    if not GUARDS_LIST.search(text):
        return  # check_guards_registered already warned about the missing list
    # The recipe must INVOKE the comparison as a command (not merely name it
    # in a comment) AND wire it to the exit code. Either alone can pass over a
    # deletion: a commented-out hook with `fail=` elsewhere, or a hook that
    # prints but never fails.
    invoked = re.search(rf"\blint\.py\s+{GUARD_EXECUTION_HOOK}\b", text) is not None
    wired = re.search(
        rf"{GUARD_EXECUTION_HOOK}.*\bfail=", text, re.MULTILINE) is not None
    if not invoked or not wired:
        rep.add(ERROR, "justfile",
                "the `guards` recipe no longer compares executed vs registered "
                f"guards (missing `lint.py {GUARD_EXECUTION_HOOK}` wired to "
                "`fail`) — a registered guard that never judges gates nothing, "
                "which is exactly what #471 hid for 3.5h; registration is not "
                "execution")
        return
    rep.add(OK, "justfile",
            "guard runner compares executed vs registered and fails on a gap")


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


# #445 — the three-axis posture vocabulary (pace × asking × delegation),
# ratifying #443's finding that run-mode conflated three independent decisions.
# Pace and asking are closed sets of named stops; delegation carries a NUMBER
# (an average-concurrency TARGET, never a cap — his #445 Q3), whose posture
# label is derived for display. The closed sets live here as the single source
# today; increment 2's dashboard controls must import them rather than
# restating, the same way this file imports RUN_MODES from watch.py.
POSTURE_STOPS_PACE = ("idle", "steady", "hot")
# Asking keeps all FOUR of the levels he dictated at length (#445) — his
# words, in order. `near-auto` and `auto` differ observably: near-auto still
# evaluates each material choice and writes it to a journal (ADR-shaped),
# surfacing nothing; `auto` is "tasked with figure it out" and never blocks on
# a reply. Merging them would delete a behaviour he specified, so the asking
# axis has four stops where pace and delegation have three — and that is the
# honest shape (his "3 stops" was a maybe/IDK about the control, which is a
# later increment's problem to render, not a reason to drop a level).
POSTURE_STOPS_ASKING = ("ask", "inform", "near-auto", "auto")
# #342 — the delivery posture axis: when he is interrupted. instant (default)
# wakes the loop the moment he sends something; batched rides the durable
# receipt and drains on the next tick's cursor read. Absent = instant, so a
# pre-axis posture file behaves identically. Closed set, fail loud — the same
# outcome as pace/asking.
POSTURE_STOPS_DELIVERY = ("instant", "batched")
# #510 — the orchestration posture axis: does the coordinator implement
# increments itself, or only dispatch + review? hands-on (default) is today —
# the coordinator implements inline (it may ALSO delegate, per the delegation
# number); orchestrator is the coordinator-only mode — every increment is
# dispatched and the coordinator's role is adjudication/review/ledger only.
# Absent = hands-on, so a pre-axis posture file behaves identically — the
# same absent-derives-today property delivery holds. Binary because the
# differentiating decision is exactly "does the coordinator implement or not";
# "solo vs fleet" is already delegation's job. Closed set, fail loud — the
# same outcome as pace/asking/delivery.
POSTURE_STOPS_ORCHESTRATION = ("hands-on", "orchestrator")
# Delegation posture labels, shown beside the integer target. The integer is
# authoritative; the label is a derived display string.
DELEGATION_POSTURES = ("own", "assist", "delegate")
# delivery and orchestration are RECOGNISED axes (an unknown axis name warns),
# but they are OPTIONAL — absent is the default (instant / hands-on), so
# check_posture never warns on their absence the way it does for
# pace/asking/delegation. The clean-bill denominator accounts for that (see
# check_posture).
POSTURE_AXES = ("pace", "asking", "delegation", "delivery", "orchestration")

# #650 — the subagent policy: the first FREE-TEXT posture field, and the
# reason it is NOT an axis in `.dreamwork/posture`.
#
# Every axis above is a closed set or a number, and that is not incidental:
# `check_posture`'s whole shape is "a value outside the vocabulary fails
# loud", which is the property that stops a silent fallback from dropping his
# choice. Free text has no vocabulary, so it cannot be checked that way — and
# carrying it INSIDE the line-oriented posture file would cost the CLOSED
# axes their loudness, twice over:
#
#   * A multi-line value needs either an escaped one-liner (where a
#     hand-inserted real newline then silently truncates the policy) or a
#     block form whose unterminated case swallows every `axis: value` line
#     below it. Free text able to eat a closed axis is precisely the failure
#     this file's fail-loud discipline exists to prevent.
#   * `write_posture` (watch.py) is a whole-file atomic overwrite, fired by
#     every posture chip press. Any writer that did not know about the policy
#     would erase it without a word — and the erasing writer already exists.
#
# So the policy lives in its own machine-local sibling,
# `.dreamwork/subagent-policy`, whose ENTIRE CONTENT is the value: no
# grammar, nothing to escape, nothing to misparse, and the posture file's
# parser is untouched — so the closed-set loudness path is not merely
# preserved, it is unmodified code.
#
# This does NOT split one dial across two files. The posture DATATYPE has
# always spanned more than one file: `watch.resolve_posture` merges
# `.dreamwork/run-mode` with `.dreamwork/posture` into a single dict, and
# this is the third source it merges. Each file carries exactly the format it
# can carry. The #445/#342 widen-not-sibling ruling governs closed-set AXES,
# and its load-bearing premise — "widening lets the closed-set discipline
# already guarding pace/asking guard this for free" — is false by
# construction for free text, which gets nothing for free and endangers what
# it is stored beside. The ruling's other goal, ONE control surface, is
# untouched: there is still one `POST /posture`, one arm, one ceremony.
SUBAGENT_POLICY_FILE = "subagent-policy"
# Posture field names that are RECOGNISED but do not live in
# `.dreamwork/posture`. check_posture ERRORs (rather than warning "unknown
# axis") when one appears there: the posture parser drops the line, so his
# policy would be silently not in effect — a dropped choice, which is the
# run-mode/watch-tint hazard and fails loud for the same reason.
POSTURE_TEXT_FIELDS = {"subagent-policy": f".dreamwork/{SUBAGENT_POLICY_FILE}"}

# His standing subagent policy, verbatim (2026-07-31, folded by #650), and
# the value in effect whenever `.dreamwork/subagent-policy` is absent — the
# same absent-derives-a-default shape every other axis holds, except that the
# default is his prose rather than a stop name. It is COMMITTED here on
# purpose: the override file is machine-local and gitignored like `posture`
# itself, so a standing policy that lived only there would not survive a
# fresh checkout and could not be reviewed in a diff.
#
# Copied EXACTLY — wording, punctuation, and typos ("taks") included. This is
# his policy in his voice; normalising it would make the stored policy differ
# from the policy he wrote, and a reader could no longer tell which words
# were his. Long lines are deliberate for the same reason: re-wrapping is a
# change to the value.
SUBAGENT_POLICY_DEFAULT = """\
- easy/trivial/research/scanning tasks: Sonnet 5 low or medium
- common UI tasks, low stakes, cheap model: use `ccc -y @glm52` (see ccc --help). This won't show up as a claude subagent but is much cheaper for us. get them to use worktrees and you can dispatch an opus5 subagent to run review-and-fix loop (see skill) over glm52's work before merging. This should be preferred over using opus5 directly.
- when glm52 fails, or for high stakes components (eg with architectural consequences or when setting precedents); common implementation tasks, ui work, etc: opus 5 high or xhigh
- difficult or very complex taks or those requiring insight or judgement: fable high
"""

# The conversion of today's run-mode values into the three-axis vocabulary
# (#445 Q2: "convert the current modes into the new values"). Stated as a
# mapping, not a rewrite — each old value lands in the new space with NO
# silent change in behaviour for a loop that has not been restarted.
#
# ASKING is `ask` for all three, grounded in measured behaviour, not the
# middle stop: today's loop writes a questions.md entry AND a review artifact
# for ~every material decision (108 resolutions, 28 artifacts at the time of
# writing), and his own #445 words are "you do ask me a lot of stuff." That
# is level 1 (ask me everything), not level 2 (inform — ~10-20% escalate).
# Deriving `inform` would make the loop stop asking and start emitting
# documents instead — the one regression that would cost him immediately.
#
# PACE for assisted derives `hot` because watch.py describes BOTH hot and
# assisted as "continuous work" (vs lackadaisical's "idle-friendly") — the
# pace is genuinely continuous, so this is unpacking a bundle that was always
# there, not inventing a decision. It is the one derivation that carries
# forward a bundled assumption (the very thing #443 identified); the fix is
# that pace is now independently settable, not that the starting point moves.
RUN_MODE_TO_POSTURE: dict[str, dict[str, object]] = {
    "lackadaisical": {"pace": "idle", "asking": "ask", "delegation": 0},
    "hot": {"pace": "hot", "asking": "ask", "delegation": 0},
    "assisted": {"pace": "hot", "asking": "ask", "delegation": 1},
}


def derive_posture(mode: str) -> dict[str, object] | None:
    """Today's run-mode value -> its three-axis posture decomposition (#445).

    Returns None for an unrecognised mode (the derivation falls back to
    run-mode's own default-handling; `check_run_mode` is what says the file no
    longer matches). Single source — increment 2's runtime must import this
    rather than restating the mapping, the way this file imports RUN_MODES.
    """
    entry = RUN_MODE_TO_POSTURE.get(mode)
    if entry is None:
        return None
    return dict(entry)


def delegation_posture(target: int) -> str:
    """Avg-concurrency target integer -> its posture label (display only).

    0 is *occasional/own* (avg < 0.5), not forbidden; 1 is *assist* (0.5–1.5);
    2 and up is *delegate*. The number steers the average; it is never a cap.
    """
    if target <= 0:
        return "own"
    if target == 1:
        return "assist"
    return "delegate"


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


def check_posture(dw: Path, watch, rep: Report) -> None:
    """Three-axis posture: pace × asking × delegation (#445, ratifies #443).

    `.dreamwork/posture` is a sibling to run-mode — same physical contract
    (gitignored, machine-local, re-read every tick). ABSENT is the default:
    the loop derives posture from run-mode via the conversion mapping in
    `file-formats.md`, so a loop that has not been restarted behaves
    identically (the per-tick re-read is load-bearing — #426). PRESENT is an
    explicit three-axis override.

    Pace and asking are closed sets: an unknown value ERRORs, failing loud
    the same way run-mode and watch-tint do (a silent fallback that drops his
    choice is the hazard). Delegation carries a NUMBER — an average-
    concurrency target, NOT a cap — so a nonsense value (negative, non-
    integer) only WARNs, and nothing here ever reads the running fleet size:
    an average is an average, and a checker that flagged a session above or
    below its target would be wrong most of the time (#445 Q3).
    """
    path = dw / "posture"
    if not path.exists():
        return
    raw = path.read_text(encoding="utf-8", errors="replace")
    values: dict[str, str] = {}
    seen_any = False
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^([a-z][a-z-]*):\s*(.*?)\s*$", s)
        if not m:
            continue
        seen_any = True
        k, v = m.group(1), m.group(2)
        # A free-text field written into the axis file (#650). This is not an
        # "unknown axis" — the name is recognised, the FILE is wrong — and it
        # is an ERROR rather than a WARN because `parse_posture_text` drops
        # the line, so the policy he thought he set would not be in effect and
        # nothing else would say so. Same hazard as an unknown run-mode.
        if k in POSTURE_TEXT_FIELDS:
            rep.add(ERROR, "posture",
                    f"{k!r} is free text and does not live here — it belongs "
                    f"in {POSTURE_TEXT_FIELDS[k]}, whose whole content is the "
                    f"value. A line here is dropped by the parser, so the "
                    f"policy would silently not be in effect")
            continue
        if k not in POSTURE_AXES:
            rep.add(WARN, "posture",
                    f"unknown axis {k!r} — recognised: {', '.join(POSTURE_AXES)}")
            continue
        if k in values:
            rep.add(WARN, "posture",
                    f"axis {k!r} appears more than once — keeping the first")
            continue
        values[k] = v
    # A present file that parsed to nothing is inert: posture stays derived,
    # so it is not an error, but it is worth knowing the file does nothing.
    # (The "count on the OK row" rule — #380 — means a parser that matched
    # nothing must not look the same as one that found nothing wrong.)
    if not seen_any:
        rep.add(WARN, "posture",
                "present but no `axis: value` lines parsed — posture stays "
                "derived from run-mode; the file is inert")
        return

    valid = 0
    # PACE — closed set, fail loud.
    pace = values.get("pace")
    if pace is None:
        rep.add(WARN, "posture", "no `pace:` line — pace stays derived from run-mode")
    elif pace not in POSTURE_STOPS_PACE:
        rep.add(ERROR, "posture",
                f"pace {pace!r} is not one of {', '.join(POSTURE_STOPS_PACE)} "
                f"— a closed set fails loud, like run-mode")
    else:
        valid += 1
    # ASKING — closed set, fail loud.
    asking = values.get("asking")
    if asking is None:
        rep.add(WARN, "posture", "no `asking:` line — asking stays at the derived default")
    elif asking not in POSTURE_STOPS_ASKING:
        rep.add(ERROR, "posture",
                f"asking {asking!r} is not one of {', '.join(POSTURE_STOPS_ASKING)} "
                f"— a closed set fails loud, like run-mode")
    else:
        valid += 1
    # DELEGATION — a number (avg-concurrency target), not a gate. Warn on
    # nonsense only; never on the running fleet size.
    dlg = values.get("delegation")
    dlg_label = None
    if dlg is None:
        rep.add(WARN, "posture",
                "no `delegation:` line — delegation stays derived from run-mode")
    else:
        try:
            n = int(dlg)
        except ValueError:
            rep.add(WARN, "posture",
                    f"delegation {dlg!r} is not an integer — an average-"
                    "concurrency target is a number; warn, not error, because "
                    "it steers rather than gates")
        else:
            if n < 0:
                rep.add(WARN, "posture",
                        f"delegation {n} is negative — nonsense; 0 means "
                        "occasional (avg <0.5), not forbidden")
            else:
                valid += 1
                dlg_label = delegation_posture(n)
    # DELIVERY (#342) — an OPTIONAL axis: absent is the default (instant), so
    # it NEVER warns on absence the way pace/asking/delegation do (those fall
    # back to a run-mode derivation; delivery has no derivation — it is just
    # instant). A present invalid value ERRORs: a closed set fails loud, the
    # same outcome as pace/asking, never a silent fallback that drops his
    # choice.
    delivery = values.get("delivery")
    delivery_ok = delivery is None or delivery in POSTURE_STOPS_DELIVERY
    if delivery is not None and not delivery_ok:
        rep.add(ERROR, "posture",
                f"delivery {delivery!r} is not one of "
                f"{', '.join(POSTURE_STOPS_DELIVERY)} — a closed set fails "
                f"loud, like pace and asking")
    # ORCHESTRATION (#510) — an OPTIONAL axis, the same shape delivery takes:
    # absent is the default (hands-on), so it NEVER warns on absence the way
    # pace/asking/delegation do (those fall back to a run-mode derivation;
    # orchestration has no derivation — it is just hands-on). A present
    # invalid value ERRORs: a closed set fails loud, never a silent fallback
    # that drops his choice.
    orchestration = values.get("orchestration")
    orchestration_ok = (orchestration is None
                        or orchestration in POSTURE_STOPS_ORCHESTRATION)
    if orchestration is not None and not orchestration_ok:
        rep.add(ERROR, "posture",
                f"orchestration {orchestration!r} is not one of "
                f"{', '.join(POSTURE_STOPS_ORCHESTRATION)} — a closed set "
                f"fails loud, like pace and asking")
    # Clean bill only when the three required axes are valid AND delivery /
    # orchestration (if present) are valid, carrying the count so coverage
    # can never shrink to silence beside a finding. Both optional axes join
    # the "of N" denominator only when they are actually set — a pre-axis
    # three-line file still reads "3 of 3", not "3 of 5" (which would imply
    # the optional axes are missing rather than default).
    if valid == 3 and delivery_ok and orchestration_ok:
        denom = (3
                 + (1 if delivery is not None else 0)
                 + (1 if orchestration is not None else 0))
        row = (f"{denom} of {denom} axes valid · "
               f"pace={pace} asking={asking} "
               f"delegation={dlg} ({dlg_label})")
        if delivery is not None:
            row += f" delivery={delivery}"
        if orchestration is not None:
            row += f" orchestration={orchestration}"
        rep.add(OK, "posture", row)


def check_subagent_policy(dw: Path, rep: Report) -> None:
    """The free-text subagent policy sibling (#650).

    `.dreamwork/subagent-policy` has NO grammar: the whole file is the value.
    So there is nothing here to validate against a vocabulary — and that is
    the point, not a gap. This check reports WHICH policy is in effect (the
    override file, or the standing default) and says aloud when a present
    file is inert, which is all a free-text field can honestly be checked
    for.

    It deliberately never inspects the CONTENT. A policy that happens to
    contain a line reading `pace: warp` is prose about pace, not a posture
    axis; a checker that read it as one would have quietly turned free text
    back into a closed set, and would fail on his own wording. The closed
    axes keep their loudness because they are in a different file, parsed by
    code this check does not touch.

    ABSENT is normal and clean: the standing default (SUBAGENT_POLICY_DEFAULT)
    is in effect, so the loop is never without a policy. It still gets an OK
    row rather than silence — absence is a real state here (a value IS in
    effect), and coverage that vanishes when nothing is wrong is the #380
    hazard.
    """
    path = dw / SUBAGENT_POLICY_FILE
    if not path.exists():
        rep.add(OK, "subagent-policy",
                f"absent — the standing default is in effect "
                f"({len(SUBAGENT_POLICY_DEFAULT.splitlines())} lines)")
        return
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        rep.add(WARN, "subagent-policy",
                f"unreadable as UTF-8 ({exc.__class__.__name__}) — the "
                f"standing default is in effect and nothing else says so")
        return
    if not raw.strip():
        # The inert-file shape check_posture already uses for a file that
        # parsed to nothing: not an error (the default still applies), but a
        # file that looks set and is not must not pass in silence. Clearing
        # the override is `rm`, not an empty write.
        rep.add(WARN, "subagent-policy",
                "present but blank — the standing default is in effect; the "
                "file is inert (delete it, or write a policy)")
        return
    rep.add(OK, "subagent-policy",
            f"override in effect · {len(raw.splitlines())} lines, "
            f"{len(raw)} chars")


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
    # `m.group(1)` is everything after the path column — the description
    # (which holds the enumeration) AND the lifecycle note. A plan named only
    # in the lifecycle column is not something a reader can *find*, so the
    # match is scoped to the description column alone: the first pipe-delimited
    # field after the path. Unioning the whole row let a name in an unrelated
    # parenthetical pass for an enumeration entry (#699). Fail closed on a row
    # whose shape does not isolate a description column — a row this cannot
    # parse is exactly the case where it must not report a match.
    if "|" not in m.group(1):
        rep.add(WARN, "doc-map.md",
                "plans row is not the expected `path | description | lifecycle` "
                "shape — cannot identify the enumeration column")
        return
    desc_col = m.group(1).split("|", 1)[0]
    listed = set()
    for paren in re.findall(r"\(([^()]*)\)", desc_col):
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

    # #555 — a conflict marker in a brief is silent to every brief reader
    # (classify_brief_handoff_scope keys on structure the way the other
    # parsers do), the same reader-cannot-see-what-is-there defect #554
    # closed for handoffs.md. The scan lives in the CHECK, not the
    # classifier: classify_brief_handoff_scope only reads text for in-scope
    # briefs (grandfathered/skipped short-circuit BEFORE the read), so it
    # is structurally blind to markers in those — and it is a pure
    # dict-returning function (used by test precondition assertions) that
    # must not couple to `rep`. So this scans every brief the check already
    # enumerated, regardless of scope: a marker is corruption in any of
    # them. Runs before the cutoff-resolution early return so a marker is
    # caught even when resolution would fail. One ERROR per line, naming
    # the file. Reuses the ONE #554 regex.
    for path in briefs:
        try:
            btext = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for ln in btext.splitlines():
            m = CONFLICT_MARKER_RE.match(ln)
            if m:
                rep.add(
                    ERROR, "briefs",
                    f"{path.name}: conflict marker `{m.group(0)}` at line "
                    f"start ({ln!r}) — a merge-conflict marker left in a "
                    f"brief is silent to its readers; resolve and remove it "
                    f"(#555)")

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


# ── brief lane-private snapshot directory (#652) ──────────────────────
# Distinctive phrase from the SKILL.md paragraph that made the snapshot
# directory lane-private. Content-resolved via `git log -S`, same idiom as
# WORKTREE_ABS_INBOX_PHRASE (#405): a reword that removes this phrase must
# ERROR loudly rather than grandfather every brief in silence.
# Must sit on ONE line in SKILL.md: `git log -S` is a literal substring
# search, so a line break inside the phrase makes the cutoff unresolvable.
# That happened while writing this check; the loud-ERROR branch below is what
# caught it, which is the argument for keeping that branch loud.
LANE_SCRATCH_PHRASE = "names a lane-private snapshot directory"
# A brief teaches the #349 restore protocol when it carries the prohibition
# that protocol exists for. Measured across 218 briefs: 67 carry some form of
# "never `git checkout`", the wording varying only in trailing punctuation.
RESTORE_CLAUSE_RE = re.compile(r"never\s+`?git\s+checkout", re.I)
# The brief routed the lane to a derived private directory: it names the
# helper (`dev/lane_scratch.py`) or the root it lives under (`lane-scratch`).
LANE_SCRATCH_TOKEN_RE = re.compile(r"lane[_-]scratch", re.I)
# Lane name as it appears in a worktree path, e.g. `.worktrees/lane-652scratch`.
WORKTREE_LANE_RE = re.compile(r"\.worktrees/([A-Za-z0-9._-]+)")
# An unambiguous pointer at the SHARED harness scratchpad. Flagged even when the
# brief also names the helper, because the realistic failure is a brief that
# mentions the helper in prose and then pastes an older worked example — the
# lane copies the example. Measured over 218 briefs: `/tmp/claude-` appears in 1
# (pre-cutoff), `$SCRATCH` in 0, so this is near-zero noise. Deliberately does
# NOT match `$S/`, which is the correct idiom once S is bound by the helper.
SHARED_SCRATCHPAD_RE = re.compile(r"/tmp/claude-|\$SCRATCH\b")


def resolve_lane_scratch_cutoff(root: Path) -> str | None:
    """Commit that introduced the lane-private snapshot rule into SKILL.md.

    Content-resolved (`git log -S` on LANE_SCRATCH_PHRASE). Oldest hit wins.
    None is the hollow outcome the check refuses to treat as a pass.
    """
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "log", "-S", LANE_SCRATCH_PHRASE,
             "--format=%H", "--", "SKILL.md"],
            stderr=subprocess.DEVNULL, text=True, timeout=30,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    shas = out.split()
    if not shas:
        return None
    return shas[-1]


def brief_names_lane_private_snapshot(text: str) -> bool:
    """Does this brief route the lane to a snapshot path it cannot collide on?

    Two accepted shapes. The helper (or its root) named anywhere — the intended
    route. Or a hand-rolled path that carries the brief's own lane name outside
    the `.worktrees/` path it was read from, which is the property that actually
    matters: a path another concurrent lane cannot also derive.
    """
    if LANE_SCRATCH_TOKEN_RE.search(text):
        return True
    for lane in set(WORKTREE_LANE_RE.findall(text)):
        # Blank out the worktree paths themselves, so the lane name occurring
        # only in `.worktrees/<lane>` does not count as a snapshot path.
        stripped = text.replace(f".worktrees/{lane}", ".worktrees/_")
        if re.search(r"/[\w./-]*" + re.escape(lane), stripped):
            return True
    return False


def classify_brief_lane_scratch(root: Path) -> dict:
    """Split restore-teaching briefs by whether they post-date the private-dir rule.

    Returns ``{cutoff, teaching, in_scope, grandfathered, skipped, missing}``
    where ``teaching`` is every brief carrying the restore prohibition,
    ``in_scope`` / ``grandfathered`` / ``skipped`` are subsets of those, and
    ``missing`` is in-scope basenames that name no lane-private snapshot path.
    """
    empty: dict = {
        "cutoff": None, "teaching": [], "in_scope": [],
        "grandfathered": [], "skipped": [], "missing": [], "shared": [],
    }
    briefs_dir = root / ".dreamwork" / "docs" / "briefs"
    if not briefs_dir.is_dir():
        return empty
    cutoff = resolve_lane_scratch_cutoff(root)
    if not cutoff:
        return empty
    cutoff_t = commit_unix_time(root, cutoff)
    if cutoff_t is None:
        return empty
    out = {
        "cutoff": cutoff, "teaching": [], "in_scope": [],
        "grandfathered": [], "skipped": [], "missing": [], "shared": [],
    }
    for path in sorted(briefs_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not RESTORE_CLAUSE_RE.search(text):
            continue
        out["teaching"].append(path.name)
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
        if not brief_names_lane_private_snapshot(text):
            out["missing"].append(path.name)
        if SHARED_SCRATCHPAD_RE.search(text):
            out["shared"].append(path.name)
    return out


def check_brief_lane_scratch(dw: Path, rep: Report) -> None:
    """A brief teaching the `cp` restore protocol names a lane-private dir (#652).

    The scratchpad is shared by every concurrent lane (one CLI session, one
    ``CLAUDE_CODE_SESSION_ID``, one directory). Two lanes snapshotting to the
    same generic name means one restore writes the other's bytes while both
    ``cmp`` checks pass — the #349 protocol turned into silent corruption.

    Scope is the briefs that carry the restore prohibition (RESTORE_CLAUSE_RE),
    because those are the ones that put a lane in front of the hazard. Untracked
    briefs are skipped (mid-write). Cutoff is content-resolved from
    LANE_SCRATCH_PHRASE — a hollow no-cutoff is an ERROR, not a silent pass.

    What this check does NOT do, stated so it is not mistaken for the fix: it
    reads briefs, not lane behaviour. A brief can name the private directory and
    the lane still snapshot somewhere else. The directory being derived is the
    safety mechanism; this only keeps the routing from silently dropping out of
    the boilerplate, which is the failure #644 records.
    """
    root = dw.parent
    briefs_dir = dw / "docs" / "briefs"
    if not briefs_dir.is_dir():
        return
    if not (root / "SKILL.md").exists():
        return
    # Precondition for the check's meaning: if no brief teaches the restore
    # protocol there is nothing to examine. That is silence, not OK coverage —
    # a check that matches nothing passes forever.
    any_teaching = any(
        RESTORE_CLAUSE_RE.search(p.read_text(encoding="utf-8", errors="replace"))
        for p in briefs_dir.glob("*.md")
        if p.is_file()
    )
    if not any_teaching:
        return

    cutoff = resolve_lane_scratch_cutoff(root)
    if not cutoff:
        rep.add(
            ERROR, "briefs",
            "could not resolve the lane-private snapshot cutoff from SKILL.md "
            f"content (phrase {LANE_SCRATCH_PHRASE!r}) — every restore-teaching "
            "brief would have been left unchecked; a reworded phrase or missing "
            "history is a loud failure, never a silent pass (#652)",
        )
        return

    try:
        blob = subprocess.check_output(
            ["git", "-C", str(root), "show", f"{cutoff}:SKILL.md"],
            stderr=subprocess.DEVNULL, text=True, timeout=20,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        blob = ""
    if LANE_SCRATCH_PHRASE not in blob:
        rep.add(
            ERROR, "briefs",
            f"cutoff `{cutoff[:7]}` resolved from content but does not contain "
            "the lane-private snapshot phrase — content resolution picked the "
            "wrong commit, so every restore-teaching brief would be mis-scoped "
            "(#652)",
        )
        return

    scope = classify_brief_lane_scratch(root)
    for name in scope["missing"]:
        rep.add(
            ERROR, "briefs",
            f"{name} teaches the `cp` restore protocol but names no lane-private "
            "snapshot directory — concurrent lanes share one scratchpad, so two "
            "generic snapshot names silently restore each other's bytes with "
            "both `cmp` checks green; route it to `dev/lane_scratch.py` (#652)",
        )
    for name in scope["shared"]:
        rep.add(
            ERROR, "briefs",
            f"{name} teaches the `cp` restore protocol and points at the SHARED "
            "harness scratchpad — every concurrent lane resolves to that one "
            "directory, so naming the helper in prose does not help if the "
            "worked example still snapshots there; the lane copies the example "
            "(#652)",
        )
    n_t = len(scope["teaching"])
    n_in = len(scope["in_scope"])
    n_gf = len(scope["grandfathered"])
    if n_t and not scope["missing"] and not scope["shared"]:
        rep.add(
            OK, "briefs",
            f"{n_t} restore-teaching brief(s), {n_in} in scope after "
            f"lane-private snapshot rule, {n_gf} grandfathered (#652)",
        )


LANE_OWNS_MARKER = "lane-owns:"
WORKTREE_BRIEF_MARKER_KNOWN = WORKTREE_BRIEF_MARKER  # alias for clarity below


def _brief_names_worktree(text: str) -> bool:
    """A brief is a dispatched-lane brief when it names a worktree path."""
    return WORKTREE_BRIEF_MARKER_KNOWN in text


def _parse_lane_owns(text: str) -> list[str]:
    """The ``Lane-owns:`` paths declared in a brief, in declaration order.

    A line ``Lane-owns: watch.py, dev/capture/`` yields ``["watch.py",
    "dev/capture/"]``. Comma-separated, backtick-stripped, POSIX-normalised.
    Empty payload (``Lane-owns:`` alone) is treated as absent: a declared but
    empty ownership list protects nothing and reads as a forgotten fill-in.
    """
    owned: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.lower().startswith(LANE_OWNS_MARKER.lower()):
            continue
        payload = line.split(":", 1)[1].strip()
        for token in payload.split(","):
            token = token.strip().strip("`").strip()
            if token:
                norm = token.replace("\\", "/")
                if norm not in owned:
                    owned.append(norm)
    return owned



def _live_lane_worktrees(root: Path) -> list[tuple[str, str]]:
    """(worktree path, branch) for each dispatched lane, or [] if unknowable.

    Reads git's own worktree registry rather than ``status.json``, which #465
    measured as carrying no worktree path at all. Returns [] on any git failure
    so the caller degrades to silence, never to a false accusation.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    lanes, path, branch = [], None, None

    def flush():
        # A lane is a LINKED worktree on a `wt/*` branch. The main checkout and
        # any unrelated worktree are not lanes, and a detached-HEAD worktree has
        # no branch line at all — so `branch` may legitimately be None here.
        if path is None or not branch:
            return
        if not branch.startswith("wt/"):
            return
        if Path(path).resolve() == root.resolve():
            return
        lanes.append((path, branch))

    for line in out.stdout.splitlines() + [""]:
        if line.startswith("worktree "):
            flush()
            path, branch = line[len("worktree "):].strip(), None
        elif line.startswith("branch "):
            # `branch refs/heads/wt/deployact` → `wt/deployact`. Strip only the
            # ref prefix; the branch's own slash is part of its name.
            ref = line[len("branch "):].strip()
            branch = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
        elif not line.strip():
            flush()
            path, branch = None, None
    flush()
    return lanes


def _dirty_paths(root: Path) -> list[str] | None:
    """Repo-relative paths dirty in ``root`` (staged, unstaged or untracked).

    None when git cannot be asked — the caller must then stay silent rather
    than report a clean tree it never measured. ``--no-optional-locks`` because
    a background ``git status`` taking the real index.lock is a documented
    mitigation on this machine.
    """
    try:
        out = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), "status",
             "--porcelain", "--untracked-files=all"],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    paths = []
    for line in out.stdout.splitlines():
        if len(line) < 4:
            continue
        entry = line[3:]
        # A rename reads `old -> new`; the destination is the dirty path.
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        paths.append(entry.strip().strip('"'))
    return paths


def lane_owned_paths(dw: Path, branch: str) -> list[str]:
    """Union of ``Lane-owns:`` paths over every brief naming this lane.

    The single lane-ownership reader, shared by the backstop
    (``check_lane_containment_backstop``) and the pre-merge assertion
    (``dev/lane_guard.py pre-merge``). A lane is matched by its worktree-name
    suffix (the segment after ``wt/``), which appears in a brief as
    ``wt/<suffix>`` or ``.worktrees/<suffix>``.

    UNION over every brief naming the lane, not the first match. A worktree
    name gets reused across sessions, so one lane can have several briefs —
    `#402` had `402-dreamers-shape.md` and `402-dreamers.md` at once, and
    first-match-by-filename picked the OLDER one, which declared nothing: the
    lane silently went unprotected while the coverage row still counted it.
    Eight task ids in this repo have more than one brief. Union is the safe
    direction: over-protecting a path costs a dispatch, under-protecting
    corrupts the disjointness invariant the whole fan-out rests on.
    """
    suffix = branch.split("/", 1)[-1]
    briefs_dir = dw / "docs" / "briefs"
    if not briefs_dir.is_dir():
        return []
    owned: list[str] = []
    for brief in sorted(briefs_dir.glob("*.md")):
        text = brief.read_text(encoding="utf-8", errors="replace")
        if f"wt/{suffix}" in text or f".worktrees/{suffix}" in text:
            for o in _parse_lane_owns(text):
                if o not in owned:
                    owned.append(o)
    return owned


def check_lane_containment_backstop(dw: Path, rep: Report) -> None:
    """A path a dispatched lane owns must not be dirty in the main checkout (#468).

    `#465`'s pre-commit guard refuses the *commit*; this is the backstop it named
    as its successor, and it catches the state one step earlier — a lane's stray
    edit sitting in the main working tree, uncommitted. That is the state that
    actually did the damage: it aborted a verified `#263` merge that had been
    held for half an hour, before any commit was attempted.

    Silent unless something is wrong. Three ways to be unknowable, each of which
    degrades to silence rather than to a false accusation: git unavailable, no
    linked lane worktrees, no brief declaring ownership. A check that accused a
    clean tree would be disabled within the hour and then protect nothing.

    Precondition asserted at runtime: a lane is only examined when its brief
    yielded a NON-EMPTY owned set. Without that the intersection is empty by
    construction and the check would pass vacuously for every lane forever —
    which is precisely how `#465`'s own premise (`status.json` ownership) failed.
    """
    root = dw.parent
    lanes = _live_lane_worktrees(root)
    if not lanes:
        return
    if not (dw / "docs" / "briefs").is_dir():
        return
    dirty = _dirty_paths(root)
    if dirty is None:
        return
    examined = 0
    found = False
    for lane_path, branch in lanes:
        owned = lane_owned_paths(dw, branch)
        if not owned:
            # Unknowable for this lane, not clean. `check_brief_lane_owns`
            # is the check that makes the omission loud; this one stays quiet.
            continue
        examined += 1
        contested = sorted(
            d for d in dirty
            if any(d == o or d.startswith(o.rstrip("/") + "/") for o in owned)
        )
        if contested:
            found = True
            rep.add(
                ERROR, "lane-containment",
                f"{', '.join(contested)} dirty in the MAIN CHECKOUT but owned by "
                f"lane {branch} ({lane_path}) — a lane editing the main tree is "
                f"#465, and it aborts a merge before any commit is attempted; "
                f"move the edit into the worktree or revert it here (#468)")
    # The OK row is a CLEAN BILL, so it must not sit beside a finding saying the
    # opposite — a check that contradicts itself in one run gets read as noise
    # and then ignored. (Found by the red-proof: the first version printed both.)
    if examined and not found:
        rep.add(
            OK, "lane-containment",
            f"{examined} of {len(lanes)} live lane(s) declare ownership; "
            f"no owned path is dirty in the main checkout")

def check_brief_lane_owns(dw: Path, rep: Report) -> None:
    """A worktree-naming brief must declare its owned paths (#465).

    The lane-containment guard (``dev/lane_guard.py``) refuses a main-checkout
    commit touching a dispatched lane's owned paths — but it can only do that
    when the lane's brief declares them. A worktree brief with no ``Lane-owns:``
    line is a lane the guard cannot protect, so this check makes the omission
    loud at brief-write time rather than a silent no-op at commit time.

    Scope: briefs whose body names a worktree (``.worktrees/``) and were written
    after the rule landed in SKILL.md. History before the rule is grandfathered
    (the lane-containment guard did not exist, so neither did the obligation).
    The cutoff is content-resolved from ``LANE_OWNS_PHRASE`` — a hollow
    no-cutoff is an ERROR, never a silent pass (#405's shape).

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
    # rule has nothing to examine. Silence, not OK coverage.
    wt_briefs = [
        p for p in briefs_dir.glob("*.md")
        if p.is_file() and _brief_names_worktree(
            p.read_text(encoding="utf-8", errors="replace"))
    ]
    if not wt_briefs:
        return

    cutoff = _resolve_lane_owns_cutoff(root)
    if not cutoff:
        rep.add(
            ERROR, "briefs",
            "could not resolve the lane-owns cutoff from SKILL.md content "
            f"(phrase {LANE_OWNS_PHRASE!r}) — every worktree brief would have "
            "been left unchecked; a reworded phrase or missing history is a "
            "loud failure, never a silent pass (#465)",
        )
        return
    cutoff_t = _commit_unix_time(root, cutoff)
    if cutoff_t is None:
        rep.add(
            ERROR, "briefs",
            f"lane-owns cutoff `{cutoff[:7]}` resolved but has no commit time "
            f"— cannot classify briefs; refusing to pass over them (#465)",
        )
        return

    in_scope: list[str] = []
    grandfathered: list[str] = []
    missing: list[str] = []
    for path in sorted(wt_briefs):
        brief_t = _brief_commit_time(root, path)
        if brief_t is None or brief_t < cutoff_t:
            grandfathered.append(path.name)
            continue
        in_scope.append(path.name)
        owned = _parse_lane_owns(
            path.read_text(encoding="utf-8", errors="replace"))
        if not owned:
            missing.append(path.name)
    for name in missing:
        rep.add(
            ERROR, "briefs",
            f"{name} names a worktree (`.worktrees/`) but declares no "
            f"`Lane-owns:` paths — the lane-containment guard cannot protect a "
            f"lane whose brief does not say what it owns (#465)",
        )
    if wt_briefs and not missing:
        rep.add(
            OK, "briefs",
            f"{len(wt_briefs)} worktree-naming brief(s), {len(in_scope)} in "
            f"scope after lane-owns rule, {len(grandfathered)} grandfathered "
            f"(#465)",
        )


LANE_OWNS_PHRASE = "Lane-owns:"


def _resolve_lane_owns_cutoff(root: Path) -> str | None:
    """Commit that introduced the ``Lane-owns:`` obligation into SKILL.md."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "log", "-S", LANE_OWNS_PHRASE,
             "--format=%H", "--", "SKILL.md"],
            stderr=subprocess.DEVNULL, text=True, timeout=30,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    shas = out.split()
    if not shas:
        return None
    return shas[-1]


def _commit_unix_time(root: Path, sha: str) -> float | None:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "show", "-s", "--format=%ct", sha],
            stderr=subprocess.DEVNULL, text=True, timeout=20,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    out = out.strip()
    try:
        return float(out) if out else None
    except ValueError:
        return None


def _brief_commit_time(root: Path, path: Path) -> float | None:
    rel = path.relative_to(root) if path.is_absolute() else path
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "log", "-1", "--format=%ct", "--", str(rel)],
            stderr=subprocess.DEVNULL, text=True, timeout=20,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    out = out.strip()
    try:
        return float(out) if out else None
    except ValueError:
        return None


# #554 — git merge-conflict markers, EXACTLY seven of the char at line start
# (column 0, the only position git ever emits them at). Four diff3/merge forms:
# `<<<<<<<` (ours) and `>>>>>>>` (theirs) may carry a label after a space;
# `|||||||` is the diff3 base (the `||||||| e2acedf5` line that lived committed
# in handoffs.md through the #548 merge while 397/397 tests passed); `=======`
# is the separator (always a bare seven-`=` line). The negative lookahead
# makes each EXACTLY seven — eight-plus never comes from git, and pinning seven
# keeps a longer run (a markdown setext `=`-underline, a prose `=====` wall)
# out of the match. Matched line-by-line (re.match anchors at column 0), so a
# `=` run MID-prose (`foo ===== bar`) is silent because it is not at the start.
# ONE definition, module-level, so the other parse-sensitive ledger docs can
# reject the same forms through it rather than restating the pattern (the #137
# single-definition rule); see check_handoffs's wider-scope note below.
CONFLICT_MARKER_RE = re.compile(
    r'<{7}(?!<)'      # <<<<<<<  — ours, may carry a label
    r'|={7}(?!=)'     # =======  — the separator, exactly seven =
    r'|>{7}(?!>)'     # >>>>>>>  — theirs, may carry a label
    r'|\|{7}(?!\|)')  # |||||||  — diff3 base, may carry the base sha


HANDOFF_QUOTE_CAP = 200
# A sentence terminator only when what follows is whitespace or end-of-string.
# Measured against all 99 live pending claimers: `lint.py`, `tasks.md` and
# `#565/#569, #583` are never split, because the character after the dot is a
# letter or a digit in every one of them.
HANDOFF_SENTENCE_END = re.compile(r"^(.*?[.!?])(?=\s|$)", re.S)


def handoff_quote(field: str) -> str:
    """A hand-off's prose field, cut to its first sentence for a report row.

    #612. `handoffs.md` writes each hand-off as ONE physical line, and the
    `· by <claimer>` grammar's claimer group runs to end of line — so the
    field carries the entire hand-off body. Measured on the live file: 99
    pending rows, median claimer **1470** characters, longest **4568**. The
    #381 fold prompt reproduced that verbatim, and the #592 hand-off alone
    (3809 characters) dominated the main checkout's whole lint report.

    That is the same tune-out failure #592 existed to stop, arriving by
    volume instead of by false positives: a report nobody can skim is a
    report nobody reads. The prompt's job is to make the fold impossible to
    miss, not to reproduce the hand-off — the file is right there.

    **First sentence** is the shortest prefix ending in ``.``, ``!`` or ``?``
    that is FOLLOWED BY whitespace or end-of-string.

    **When there is no terminator at all** — 30 of the 99 live claimers, so
    not a hypothetical — the whole field is the candidate and the cap below
    is what bounds it. There is no guessing at an implied sentence.

    **The cap is a backstop, not the usual path.** Live first-sentence
    lengths run 71..759, median 160, so 200 leaves most whole (the #592
    one is 188) and bounds the outlier. The cut lands on the last space at
    or before the cap so a word is never split, and ``…`` says it was cut.

    **The sha is not in here.** Callers interpolate it as its own field, and
    the two fold prompts print it BEFORE this quote — so no input to this
    function can push the actionable part off the row or drop it. That is
    the property `test_the_sha_survives_every_truncation` pins.
    """
    flat = re.sub(r"\s+", " ", field or "").strip()
    m = HANDOFF_SENTENCE_END.match(flat)
    quote = m.group(1) if m else flat
    if len(quote) <= HANDOFF_QUOTE_CAP:
        return quote
    cut = quote[:HANDOFF_QUOTE_CAP]
    space = cut.rfind(" ")
    return (cut[:space] if space > 0 else cut).rstrip() + "…"


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
    # #554 — conflict markers are the ONE corruption this file's parser is
    # structurally blind to. parse_handoffs keys on `##` section heads and
    # `- **#id**` entry heads; a git merge-conflict marker line matches none of
    # those, so it falls straight through to `continue` and renders as nothing
    # — which is exactly what happened at the #548 merge: a `||||||| e2acedf5`
    # line sat committed in this file and the full suite passed. A marker is a
    # reader-cannot-see-what-is-there defect (data loss, silent by nature), so
    # this is ERROR, never WARN. Scanned from the raw text BEFORE the
    # `watch is None` early return: the parse hazard is independent of the
    # parser — proven by the born-hollow demo, which passed all four forms with
    # watch loaded. One ERROR per marker line so each is named.
    #
    # Wider scope (#554 decision): the same rejection SHOULD apply to every
    # tool-parsed ledger doc — `tasks.md`/`tasks.md.deprecated` (parse_ledger,
    # the most parse-sensitive file in the repo), `questions.md`
    # (parse_questions), and `briefs/*.md` (classify_brief_handoff_scope) —
    # because each parser keys on its own head grammar the way parse_handoffs
    # does, so a marker is the same silent corruption there. NOT done here: those
    # are separate check regions held by other lanes, and this lane owns the
    # handoffs check region only. Prose docs (watch-design.md, transitions.md)
    # are excluded by design — markers there are ugly, not parse hazards.
    # Landed as #555: the sweep now lives in check_questions,
    # check_ledger_sections (text + tasks.md.deprecated), and
    # check_brief_handoff_obligation, each reusing this one regex.
    for ln in text.splitlines():
        m = CONFLICT_MARKER_RE.match(ln)
        if m:
            rep.add(
                ERROR, "handoffs.md",
                f"conflict marker `{m.group(0)}` at line start ({ln!r}) — a "
                f"merge-conflict marker left in handoffs.md is silent to the "
                f"parser; resolve and remove it (#554)")
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
        # #612: `line` is the same single physical line the claimer comes
        # from, so it carries the whole hand-off body too — the identical
        # unbounded quote, one branch away from the fold prompt. It never
        # fires on the live file (0 malformed today), which is exactly why
        # fixing only the branch that is currently loud would leave the
        # defect to resurface the first time this one fires.
        rep.add(
            WARN, "handoffs.md",
            f"#{nid} has a hand-off entry the grammar does not recognise "
            f"(needs `· landed \\`<sha>\\` · … · by <claimer>` under "
            f"`## Pending`, or `→ folded (ts):` under `## Folded`; id may be "
            f"`#N`, `#Na`, or `#N/#M`): {handoff_quote(line)!r} "
            f"(#381/#401/#406)")

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

    ledger_text, _source = ledger_view(dw)
    if ledger_text is None:
        return
    try:
        open_ids, landed_ids = watch.parse_ledger(ledger_text)
    except Exception:
        return  # a mid-edit ledger is not a hand-off problem

    # THE delivery signal: pending (not folded) and still open. Correlation
    # normalises sub-ids/combined tokens to parent ledger ids via the named
    # helper — never ENTRY_ID's incidental letter-strip (#401).
    # `if nid in folded_ids: continue` is the consumed marker — the one line
    # that stops a complied hand-off being nagged forever. For combined ids
    # (#521/522), the literal string is not in folded_ids but its parents are,
    # so the consumed check must test parents too (same idiom as the delivery
    # signal below uses handoff_parent_ids for the same reason).
    for nid, sha, claimer in pending:
        if nid in folded_ids:
            continue
        parents = watch.handoff_parent_ids(nid)
        if any(p in folded_ids for p in parents):
            continue
        if any(p in open_ids for p in parents):
            # #612: sha FIRST, then the quote — the sha is the actionable
            # part, so it must never sit behind a field whose length the
            # writer of the hand-off controls.
            rep.add(
                WARN, "handoffs.md",
                f"#{nid} is named as landed in a hand-off (sha `{sha}`, by "
                f"{handoff_quote(claimer)}) but is still under `## Open` — "
                f"fold it into the ledger and append a `→ folded` line (#381)")
        elif any(p in landed_ids for p in parents):
            # #576: the task IS landed (the coordinator folded it into the
            # ledger) but the `→ folded` line was never appended to handoffs.md.
            # The #381 check above only catches tasks still under `## Open`;
            # landed-but-unfolded was invisible, which is how 24 entries
            # accumulated unnoticed (Max's backlog concern, 2026-07-31).
            # Same WARN, same grace: a freshly-landed hand-off sits pending
            # for the one tick before the coordinator folds, and the fold
            # writes the `→ folded` line in the same commit.
            rep.add(
                WARN, "handoffs.md",
                f"#{nid} is landed in the ledger but has no `→ folded` line "
                f"in handoffs.md (sha `{sha}`, by {handoff_quote(claimer)}) "
                f"— append one under `## Folded` (#576)")

    # #677 — the rebase-before-handoff rule as a check. At the moment a
    # hand-off is pending AND its task is still open (i.e. awaiting merge),
    # the branch it names should not be behind master: `git rev-list --count
    # <sha>..master` non-zero → WARN naming the sha and the count. A count is a
    # question, not a verdict (#590): behind-ness is expected for a lane still
    # working, which is why the pending-and-open anchor is the right scope and a
    # not-yet-merged row is the only one this fires on (hazard 1/4 — measured 0
    # such rows on today's file, so no wall).
    #
    # WARN not ERROR (hazard 2): a lane that deliberately did not rebase
    # because the rebase was genuinely hard, and handed back the analysis
    # instead, is behaving correctly per the rule — an ERROR would punish the
    # honest path.
    #
    # THE CASE THE RULE'S ORDERING CLAUSE EXISTS TO PREVENT (hazard 3, the
    # primary one): a lane that appended its hand-off and THEN rebased has a
    # sha that no longer exists on its branch at all, so `rev-list` fails. A
    # check that silently skips what it cannot resolve is #671 repeating — so
    # whatever this pass cannot evaluate it must SAY SO (#671): "examined N,
    # behind M, could not evaluate K" is the minimum honest shape, printed as a
    # row whenever the pass ran at all. #679 owns "names nothing" as an ERROR
    # for the whole file; this pass's could-not-evaluate is the per-row report
    # of the same fact at the moment it blocks the behind check, never a silent
    # skip.
    in_repo = (dw.parent / ".git").exists()
    examined = behind = could_not = 0
    for nid, sha, claimer in pending:
        if nid in folded_ids:
            continue
        parents = watch.handoff_parent_ids(nid)
        if any(p in folded_ids for p in parents):
            continue
        if not any(p in open_ids for p in parents):
            continue  # not awaiting merge — the delivery loop handles it
        row_sha = next((s for s in
                        [r for r in pending if r[0] == nid][0].shas
                        if re.fullmatch(r"[0-9a-f]{7,40}", s)
                        and re.search(r"[a-f]", s)), None)
        if row_sha is None:
            could_not += 1
            continue
        examined += 1
        try:
            rev = subprocess.run(
                ["git", "-C", str(dw.parent), "rev-list", "--count",
                 f"{row_sha}..master"],
                capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            could_not += 1
            examined -= 1
            continue
        if rev.returncode != 0 or not rev.stdout.strip().isdigit():
            # sha resolves to nothing (a rebased-away landing) — #679 ERRORs
            # it file-wide; here it is a could-not-evaluate for this pass.
            could_not += 1
            examined -= 1
            continue
        n = int(rev.stdout.strip())
        if n > 0:
            behind += 1
            rep.add(
                WARN, "handoffs.md",
                f"#{nid} (sha `{row_sha}`) is {n} commit(s) behind master — "
                f"rebase onto master before the merge lands a stale result "
                f"(a clean merge that leaves a build output stale is invisible "
                f"to git, #655/#677)")
    if examined or behind or could_not:
        rep.add(
            OK, "handoffs.md",
            f"behind-master: examined {examined} awaiting-merge hand-off(s), "
            f"{behind} behind, {could_not} could not be evaluated")

    # #679 — a sha cited as a landing/merge in handoffs.md must RESOLVE. A sha
    # that names nothing is indistinguishable from a real one to every reader
    # who does not resolve it, and the loop's own coordinator invented four in
    # ten minutes (three fold-line merge shas, then a ledger note sha). ERROR,
    # not WARN: a dead landing sha is the loop's false evidence — the
    # surrounding prose is true, the sha is not, and "names nothing" is an
    # ERROR (#679 hazard 2).
    #
    # SCOPE — the established citation contexts, not a bare scan (hazard 1).
    # `CITED_SHA` is the proven keyword-led discriminator from
    # `check_cited_shas` (the `fade326` alias analysis there settled "the
    # keyword immediately introduces the token"), reused here against the SAME
    # `text` this check already reads — extending the reader, not opening a
    # second one. Deliberately NOT scanned, each because CITED_SHA excludes it:
    #   - bare/prose backticked tokens with no landing keyword (a reference is
    #     not a claim about a landing; widening reintroduces the alias false
    #     positive `check_cited_shas` already paid to learn);
    #   - sha256 page digests and `client/dist/manifest.json` content hashes
    #     (the 40-char cap plus backtick delimitation rejects the 64-char form);
    #   - pure-digit PIDs/counts (`re.search(r"[a-f]")`, the same filter);
    #   - lane/session identifiers in `(lane \`019fb4e0\`, …)` fold notes
    #     ("lane" is not a landing keyword). Measured on today's file: 225
    #     candidates, 1 dead, 0 alias/digest false positives.
    # Each dead sha is attributed to its row's task id via the parser's own
    # `pending`/`folded_ids` structure — the binding that means a copy-pasted
    # parser giving a different id fails this check's tests (#655's guard).
    handoff_shas = []
    for _m in CITED_SHA.finditer(text):
        _token = _m.group(1)
        if re.search(r"[a-f]", _token) and _token not in handoff_shas:
            handoff_shas.append(_token)
    if handoff_shas:
        sha_to_ids = {}
        for _row in pending:
            for _s in _row.shas:
                if re.search(r"[a-f]", _s):
                    sha_to_ids.setdefault(_s, set()).add(_row.id)
        for _nid, _fshas in folded_ids.shas_by_id.items():
            for _s in _fshas:
                if re.search(r"[a-f]", _s):
                    sha_to_ids.setdefault(_s, set()).add(_nid)
        in_repo = (dw.parent / ".git").exists()
        _unchecked = "%d cited landing/merge sha(s) went unchecked" % len(handoff_shas)
        try:
            _proc = subprocess.run(
                ["git", "-C", str(dw.parent), "cat-file", "--batch-check"],
                input="".join("%s^{commit}\n" % s for s in handoff_shas),
                capture_output=True, text=True, timeout=20,
            )
        except (OSError, subprocess.SubprocessError) as _exc:
            rep.add(WARN if in_repo else OK, "handoffs.md",
                    f"could not ask git about the hand-off citations "
                    f"({type(_exc).__name__}), so {_unchecked}")
        else:
            if _proc.returncode != 0 and not _proc.stdout:
                rep.add(WARN if in_repo else OK, "handoffs.md",
                        f"git could not read this tree, so {_unchecked}"
                        + ("" if in_repo else " (no `.git` here, which is not a fault)"))
                return
            _out = _proc.stdout.splitlines()
            if len(_out) != len(handoff_shas):
                rep.add(WARN, "handoffs.md",
                        f"git answered for {len(_out)} of {len(handoff_shas)} "
                        f"cited sha(s) — one line per input is expected, so "
                        f"the rest were never examined")
                return
            dead = [s for s, line in zip(handoff_shas, _out)
                    if "missing" in line or "ambiguous" in line]
            if dead and len(dead) == len(handoff_shas):
                # Almost certainly the wrong tree (a fresh clone, a different
                # target), not a file full of lies. Suppressing the ERRORs is
                # right; suppressing the fact is not (#380).
                rep.add(OK, "handoffs.md",
                        f"all {len(handoff_shas)} cited sha(s) are missing "
                        f"here, read as the wrong tree rather than a wrong "
                        f"file — so nothing was checked")
                return
            for s in dead:
                ids = sorted(sha_to_ids.get(s, set()))
                whom = (" (#" + ", #".join(ids) + ")") if ids else ""
                rep.add(
                    ERROR, "handoffs.md",
                    f"`{s}` is cited as a landing or merge in handoffs.md"
                    f"{whom} but git has no such commit — a worktree sha is "
                    f"unreachable once the branch is merged or rebased, so "
                    f"cite the sha on the branch you merged INTO (#679)")
            if not dead:
                rep.add(OK, "handoffs.md",
                        f"{len(handoff_shas)} cited landing/merge sha(s) all "
                        f"resolve")


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

    Reads through `ledger_view` — the #294 dispatch — so a store-mode target
    is examined against its STORE projection, not the #458 shim that stands in
    for `tasks.md` after cutover (#685). The shim has no entries, so the
    pre-fix direct read examined nothing and said nothing — which read as a
    pass. That is exactly the silent-skip the next paragraph forbids, which is
    why this is the dispatch and not a `note_ledger_skip` row: in the main
    checkout the data is present and readable, so finding nothing to examine is
    a finding about the projection, not a skip.

    The OK summary reports how many entries it examined and against how many
    markers, as well as how many pairs checked and how many were unparseable:
    a check that counts what it examined cannot silently stop examining things
    (#671 is the worked example of this reporting shape). A run that examined
    zero entries says so and is WARN, not a clean pass — both halves of the
    correlation it performs (entries, markers) are on the report.

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
    text, source = ledger_view(dw)   # the #294 dispatch — #685
    if text is None:
        return
    entries = watch.ledger_entries(text)
    n_entries = len(entries)
    # The marker may hard-wrap: the loop writes at ~72 columns, so join each
    # entry's lines before reading it, the same allowance the origin rule makes.
    claims: dict[int, set[int]] = {}
    all_ids = {i for ids, _ in entries for i in ids}
    n_unparseable = 0
    n_markers = 0   # #685: entries that carried a `related:` field (examined)
    for ids, raw in entries:
        flat = re.sub(r"\s+", " ", raw)
        head = "/".join("#%d" % i for i in ids)
        fields = list(RELATED_FIELD.finditer(flat))
        found = RELATED_MARKER.findall(flat)
        if not fields:
            continue
        n_markers += 1   # this entry carried a `related:` field (#685)
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
    # #685: the examined count is on the report (#671's shape), so a run that
    # examined zero entries cannot read as a clean pass. The two halves of what
    # this check correlates — entries and markers — are both named, with the
    # source `ledger_view` actually read (it fails closed toward markdown on any
    # store error, so the word is what was read, not an assumption).
    has_marker_error = any(lvl == ERROR and w == "tasks.md" and "(#353)" in d
                           for lvl, w, d in rep.rows)
    if n_entries == 0:
        # Zero entries is a cannot-check, not a clean bill — the dispatch found
        # nothing to examine (broken projection, or a worktree whose store
        # cannot travel). WARN, never OK; and never a skip row, because in the
        # main checkout this condition should not exist (#685).
        rep.add(WARN, "tasks.md", (
            f"examined 0 entries against 0 markers ({source}) — the ledger "
            f"yielded no entries, so no related-marker could be checked; this "
            f"is not a clean result (#685)"))
        return
    pairs = {tuple(sorted((a, b))) for a, named in claims.items() for b in named}
    if has_marker_error:
        return      # ERRORs already speak; an OK summary would contradict them
    if n_markers == 0:
        rep.add(OK, "tasks.md",
                f"examined {n_entries} entries against 0 markers ({source})")
    else:
        rep.add(OK, "tasks.md", (
            f"examined {n_entries} entries against {n_markers} markers "
            f"({source}); {len(pairs)} related pair(s), all reciprocal; "
            f"{n_unparseable} entries unparseable"))


LESSON_DUP_RATIO = 0.78
LESSON_DUP_JACCARD = 0.50
_LESSON_STOP = frozenset(
    "a an the and or of to in on for with by is are was were be been it its "
    "this that not no never must can could should would from at as so if "
    "then than when what which who how why your you we our their they them "
    "he she his her do does did have has had will just only every each any "
    "all one two three".split())


def _load_lessons_index():
    """Import dev/lessons_index.py for its entry parser — one parser, not two.

    By path, same reasoning as `load_watch`: lint runs from the skill dir
    against any target, and a second copy of the entry grammar is how this
    repo's checks drift. Returns None if it is unimportable so the rest of
    the checks still run — and the caller reports that, because a comparison
    that could not run must never look like one that ran.
    """
    path = SKILL_DIR / "dev" / "lessons_index.py"
    if not path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("_lessons_index_for_lint", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def _norm_claim(claim: str) -> str:
    s = claim.lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _claim_tokens(claim: str) -> frozenset:
    return frozenset(t for t in _norm_claim(claim).split()
                     if t not in _LESSON_STOP and len(t) > 2)


def _head_lessons(dw: Path) -> str | None:
    """HEAD's lessons.md for the target's repo, or None when unreadable.

    `git show` is read-only plumbing and takes no index lock (the active
    mitigation on this host is about `git status`). None — not "" — means
    "no baseline", so a lessons.md that simply is not tracked yet does not
    read as "every lesson is new".
    """
    target = dw.parent
    try:
        top = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10)
        if top.returncode != 0:
            return None
        rel = (dw / "lessons.md").resolve().relative_to(
            Path(top.stdout.strip()).resolve())
        show = subprocess.run(
            ["git", "-C", str(target), "show", f"HEAD:{rel.as_posix()}"],
            capture_output=True, text=True, timeout=10)
        return show.stdout if show.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def check_lesson_near_duplicates(dw: Path, rep: Report) -> None:
    """A NEW lesson whose first sentence near-duplicates an existing one is
    the #349 repeat in its file-shaped form.

    The 2026-07-28 repeat was an ACTION, so the retrieval half of #349 is
    `dev/lessons_index.py`. This is the write-time backstop: had anything
    compared first sentences, the one true duplicate in the file's history
    (the "guard assertion whose subject may not exist must never throw"
    lesson, written twice in one batch — lessons.md:580 ≈ :622) would have
    been refused. Thresholds are measured, not guessed: over all 44.5k
    pairs in the current file, exactly that one pair reaches ratio >= 0.78
    AND token-jaccard >= 0.50; the next-highest pair sits at 0.645. The
    catch radius is honest — near-verbatim repeats fire, a genuinely
    re-worded repeat (ratio 0.37-0.63, measured) does not — which is why
    this check is the backstop and not the fix.

    "New" means the claim is absent from HEAD's lessons.md: the refusal
    bites at write time, when the loop is appending. A pair already in HEAD
    is WARN, not ERROR — merging it is his call (the #349 posture forbids
    pruning without him), and a WARN names it forever rather than going
    silent. No git baseline (a fixture, a target outside a repo) degrades
    to WARN-only and SAYS so.
    """
    path = dw / "lessons.md"
    if not path.exists():
        rep.add(WARN, "lessons.md", "absent — init seeds it; the loop appends it")
        return
    lix = _load_lessons_index()
    if lix is None:
        rep.add(WARN, "lessons.md",
                "dev/lessons_index.py unimportable — the near-duplicate check "
                "cannot run (this row is the refusal to fake having run)")
        return
    claims = [(ln, lix.claim_of(body))
              for ln, body in lix.parse_entries(path.read_text(encoding="utf-8"))]
    norms = [_norm_claim(c) for _, c in claims]
    toks = [_claim_tokens(c) for _, c in claims]
    pairs = []  # (line_a, line_b, ratio)
    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            if not norms[i] or not norms[j]:
                continue
            sm = difflib.SequenceMatcher(None, norms[i], norms[j])
            if sm.quick_ratio() < LESSON_DUP_RATIO:
                continue
            ratio = sm.ratio()
            if ratio < LESSON_DUP_RATIO:
                continue
            union = toks[i] | toks[j]
            if union and len(toks[i] & toks[j]) / len(union) >= LESSON_DUP_JACCARD:
                pairs.append((claims[i][0], claims[j][0], ratio))
    head = _head_lessons(dw)
    if head is None:
        new_lines: set[int] = set()
    else:
        head_claims = {_norm_claim(lix.claim_of(b))
                       for _, b in lix.parse_entries(head)}
        new_lines = {ln for (ln, _), n in zip(claims, norms)
                     if n not in head_claims}
    new_pairs = [p for p in pairs if p[0] in new_lines or p[1] in new_lines]
    old_pairs = [p for p in pairs if p not in new_pairs]
    for a, b, ratio in new_pairs[:5]:
        rep.add(ERROR, "lessons.md", (
            f"new first sentence near-duplicates an existing lesson "
            f"(lessons.md:{a} ≈ lessons.md:{b}, ratio {ratio:.2f}) — the "
            f"repeat #349 exists to refuse; fold the new evidence into the "
            f"existing entry instead of writing the lesson twice"))
    if old_pairs:
        listed = ", ".join(f"lessons.md:{a} ≈ lessons.md:{b}"
                           for a, b, _ in old_pairs[:5])
        if head is None:
            rep.add(WARN, "lessons.md", (
                f"{len(old_pairs)} near-duplicate first-sentence pair(s): "
                f"{listed} — no git baseline, so new vs pre-existing is "
                f"unknowable and the write-time refusal is OFF"))
        else:
            rep.add(WARN, "lessons.md", (
                f"{len(old_pairs)} near-duplicate first-sentence pair(s) "
                f"already in HEAD: {listed} — merging is his call (#349 "
                f"posture: no pruning without him)"))
    if not pairs:
        baseline = "" if head is not None else (
            "; no git baseline — write-time refusal OFF (this run could only "
            "have caught pre-existing pairs)")
        rep.add(OK, "lessons.md",
                f"{len(claims)} first sentences, none near-duplicate{baseline}")


# #289 — the ONLY prose decision-claim grammar this check recognises. It is
# the declared V1 shape (`Review (accepted): <artifact>`) from the pre-store
# design, and it is deliberately the whole vocabulary: free-prose verdict
# detection has been measured wrong in this repo too many times (the
# keyword-rule failures file-formats.md documents), so an entry merely
# saying "accepted" near an artifact name is NOT a claim here.
REVIEW_PROSE_CLAIM = re.compile(
    r"Review \((pending|accepted|rejected)[^)]*\)\s*:\s*([^\s`]+\.html)")


def check_review_decision_integrity(dw: Path, rep: Report) -> None:
    """#289 — the coordinator-owned WARN half of the `review_decision` store.

    The writer-level gate (`ledger_write.record_review_decision`'s
    DecisionConflict) stops a *second writer* contradicting a settled row.
    This check is the ambient half, and it WARNs — never ERRORs — on the two
    drifts the gate cannot see:

    1. **A dangling `question_title`.** A decision row names the question it
       belongs to by TITLE (the same identity `data-qid` carries). Titles
       can be edited after a decision is recorded, and the store does not
       follow — so a row can point at a question that no longer exists under
       that title. The known-title set comes from the REAL parsers
       (`watch.parse_open_questions` / `watch.parse_answered`), never a
       second copy.
    2. **A prose claim conflicting the store.** The pre-store V1 grammar
       (`Review (accepted): <artifact>`) is the only recognised prose
       decision-claim; where it and the store disagree, the store is the
       authority by contract and the prose is the drift.

    An artifact with NO row is 'unlinked' — a state, not a finding — and an
    unrecorded prose claim is deliberately NOT flagged (the grammar was
    never adopted; nobody was taught to write it, so flagging it would be
    noise against a vocabulary of one). Both exits REPORT what was examined:
    a check that examines nothing must not print nothing.
    """
    area = "review_decision"
    if source_of_truth(dw) != "store":
        rep.add(OK, area,
                "markdown-mode target — decisions live nowhere structured; "
                "the check is moot, not passed")
        return
    db = dw / "ledger.sqlite3"
    if not db.exists():
        rep.add(WARN, area,
                "store-mode watermark but no ledger.sqlite3 — cannot check "
                "(this row is the refusal to fake having run)")
        return
    rows = watch._review_decisions(dw)  # the ONE production reader
    qpath = dw / "questions.md"
    if qpath.exists():
        qtext = qpath.read_text(encoding="utf-8")
        titles = {q["title"] for q in watch.parse_open_questions(qtext)}
        titles |= {q["title"] for q in watch.parse_answered(qtext)}
    else:
        qtext, titles = "", None
    findings = 0
    for artifact in sorted(rows):
        decision, title = rows[artifact]
        if titles is not None and title not in titles:
            findings += 1
            rep.add(WARN, area, (
                f"{artifact}: decision '{decision}' names a question_title "
                f"no question carries — \"{title}\" is dangling (the title "
                f"was likely edited after the decision was recorded; the "
                f"store does not follow title edits)"))
    if qtext:
        for m in REVIEW_PROSE_CLAIM.finditer(qtext):
            claim, artifact = m.group(1), m.group(2)
            if artifact in rows and rows[artifact][0] != claim:
                findings += 1
                rep.add(WARN, area, (
                    f"{artifact}: prose claims '{claim}' but the store "
                    f"records '{rows[artifact][0]}' — the store is the "
                    f"authority (R5); the prose is the drift"))
    if findings == 0:
        suffix = "" if titles is not None else \
            "; questions.md absent — the dangling half could not run"
        rep.add(OK, area,
                f"{len(rows)} row(s) examined, none dangling or "
                f"conflicted{suffix}")


# Counts line-start ``dw-turn`` openers — the SAME column-0 anchor the parser
# (``watch._CHAT_TURN_RE``) requires, so the count and the parser cannot
# disagree about what an opener is. A marker NOT at column 0 is inline prose
# (the anti-forgery rule at 5cea6e0f), never an opener, so it is not counted.
_CHAT_OPENER = re.compile(r"^<!--\s*dw-turn\s+role=", re.MULTILINE)


def check_chats_v1(dw: Path, watch, rep: Report) -> None:
    """#504 — the chats-v1 transcript store: malformed transcripts and bad
    chat.json WARN (proportionate — never ERROR; the store degrades silently
    when a reader skips a chat, it does not lose other data).

    Two defects, both WARN:

    1. **A turn block that does not parse.** The transcript is append-only
       conversational truth; ``watch._parse_chat_turns`` is its ONE reader (the
       same one ``list_chats`` and the reply CLI use). A line-start ``dw-turn``
       opener the parser does NOT turn into a turn means a malformed block — a
       torn close marker, a structurally incomplete header — and the reader
       sees fewer turns than the transcript wrote. Counted by comparing
       line-start openers to parsed turns; a disagreement names the dir.

    2. **A bad chat.json.** ``chat.json`` carries IDENTITY only (never a second
       truth — title/turns/status are derived at read time). It must be valid
       JSON, and its ``id`` must agree with the dir name, because the dir IS
       the identity a reply targets (``apply_chat_turn`` keys on it, and the
       reply CLI's existence check follows it).

    Degrades to silence on an ABSENT store (a fresh target has no chats) and on
    a store with no chat dirs (reports nothing rather than a vacuous OK — a
    check that examined zero chats must not print "all well-formed"). Reports
    the count examined on the clean row so coverage cannot shrink to silence.
    Reuses the production reader ``watch._parse_chat_turns`` / ``watch._safe_json``
    rather than a second copy of either.
    """
    area = "chats-v1"
    if watch is None:
        return
    root = dw / watch.CHAT_DIR
    if not root.is_dir():
        return  # absent store → degrade silently (a fresh target has no chats)
    examined = 0
    findings = 0
    for cdir in sorted(p for p in root.iterdir() if p.is_dir()):
        transcript = cdir / "transcript.md"
        if not transcript.exists():
            continue
        examined += 1
        text = transcript.read_text(encoding="utf-8", errors="replace")
        # (1) a turn block that does not parse: an opener the production reader
        # does not turn into a turn (torn close, incomplete header). The opener
        # counter is anchored at line start, matching the parser's anchor.
        openers = len(_CHAT_OPENER.findall(text))
        turns = watch._parse_chat_turns(text)
        if openers != len(turns):
            findings += 1
            rep.add(WARN, area, (
                f"{cdir.name}: transcript has {openers} dw-turn opener(s) but "
                f"{len(turns)} parsed — a turn block is malformed (the reader "
                f"sees fewer turns than were written)"))
        # (2) chat.json must be valid JSON and its id must agree with the dir.
        meta = cdir / "chat.json"
        if meta.exists():
            data = watch._safe_json(
                meta.read_text(encoding="utf-8", errors="replace"))
            if data is None:
                findings += 1
                rep.add(WARN, area,
                        f"{cdir.name}: chat.json is not valid JSON")
            elif not isinstance(data, dict) or data.get("id") != cdir.name:
                findings += 1
                rep.add(WARN, area, (
                    f"{cdir.name}: chat.json id {data.get('id')!r} disagrees "
                    f"with the dir name (the dir is the identity a reply "
                    f"targets)"))
    if examined == 0:
        return  # a store with no chat dirs reports nothing (not a vacuous OK)
    if findings == 0:
        rep.add(OK, area,
                f"{examined} chat(s) examined, all transcripts and chat.json "
                f"well-formed")


def run_checks(dw: Path, watch, rep: Report) -> None:
    """Every check, in one place, because a SECOND copy of this list drifted.

    `test_lint.py`'s helper used to hand-maintain its own sequence, and it had
    fallen six checks behind — including the one being added when this was
    found. A check absent from the test harness is a check whose tests cannot
    fail, which is the failure mode this repo keeps rediscovering. One list,
    called by `main()` and by the tests, cannot drift from itself.
    """
    check_questions(dw, watch, rep)
    check_questions_truncation(dw, rep)
    check_answered_resolution_dates(dw, watch, rep)
    check_resolution_marker_outside_title(dw, watch, rep)
    check_resolution_marker_after_subbullet(dw, watch, rep)
    check_subdecisions(dw, watch, rep)
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
    check_posture(dw, watch, rep)
    check_subagent_policy(dw, rep)
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
    check_brief_lane_scratch(dw, rep)
    check_brief_lane_owns(dw, rep)
    check_lane_containment_backstop(dw, rep)
    check_related_markers(dw, watch, rep)
    check_lesson_near_duplicates(dw, rep)
    check_review_decision_integrity(dw, rep)
    check_chats_v1(dw, watch, rep)
    check_status_keys(dw, rep)
    # Takes the skill dir, not `.dreamwork/`: the justfile and the guards are
    # the tool's own, so this only says anything when linting this repo.
    check_commit_cleanup(dw.parent, rep)
    check_guards_registered(dw.parent, rep)
    check_guards_execution_accounting(dw.parent, rep)
    check_client_dist(dw.parent, rep)
    # LAST, and it must stay last: the ledger checks that can skip are spread
    # through the list above and each records its own skip as it returns, so
    # the single #611 row can only be rendered once they have all had their
    # turn.
    check_ledger_skips(rep)


def _guard_execution_main(argv: list[str]) -> int:
    """``lint.py guard-execution <OUT> <guard> [<guard> ...]``.

    Reads each guard's run log at ``<OUT>/<guard>.log`` and reports how many
    of the requested (registered) guards ran AND judged, failing when any did
    not. Invoked by the `guards` recipe after the per-guard loop, because a
    recipe-level FAIL line (the #471 shape: the guard threw in serveVerified
    before any ok()) GATES NOTHING unless the executed set is compared to the
    registered set.

    Preconditions are asserted at runtime, not assumed: a comparison of two
    sets is vacuous if either is empty, and a broken OUT (zero logs) must not
    read as "everything ran" — that is the #471 failure mode inverted.
    """
    ap = argparse.ArgumentParser(
        prog="lint guard-execution",
        description="Report which requested guards ran-and-judged; fail on a gap (#471).")
    ap.add_argument("out", help="the recipe's OUT tempdir holding <guard>.log files")
    ap.add_argument("guards", nargs="+", help="the requested (registered) guard names")
    a = ap.parse_args(argv)
    out = Path(a.out)
    # Plain identifiers only — the names come from the recipe's own list, but
    # a stray path segment must never reach `out / f"{g}.log"`.
    ident = re.compile(r"^[A-Za-z0-9_-]+$")
    requested = list(dict.fromkeys(g for g in a.guards if ident.match(g)))
    executed = []
    missing = []
    seen_log = 0
    for g in requested:
        log = out / f"{g}.log"
        text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
        if text:
            seen_log += 1
        (executed if ran_and_judged(text) else missing).append(g)
    if not requested:
        print("guard-execution: no guards requested — comparison is vacuous",
              file=sys.stderr)
        return 2
    if seen_log == 0:
        print(f"guard-execution: read 0 logs under {out} — expected <guard>.log "
              f"files for {len(requested)} guard(s); a broken OUT reads as "
              f"'everything ran', which is #471's failure mode inverted",
              file=sys.stderr)
        return 2
    n_reg = len(requested)
    n_exec = len(executed)
    if missing:
        print(f"  FAIL guards: {len(missing)} of {n_reg} registered guard(s) did "
              f"NOT run-and-judge: {', '.join(missing)}")
        print("        each printed no genuine PASS/FAIL verdict — died before "
              "judging (the #471 shape: registered, gated nothing)")
        return 1
    # Both counts on the OK row: a single number cannot show a gap, and the
    # row that hid this bug ("N registered") carried exactly one.
    print(f"  OK    guards: {n_exec} of {n_reg} registered guard(s) ran and judged")
    return 0


def main(argv: list[str] | None = None) -> int:
    raw = sys.argv[1:] if argv is None else list(argv)
    if raw and raw[0] == GUARD_EXECUTION_HOOK:
        return _guard_execution_main(raw[1:])
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
