"""Lossless ``questions.md`` parser — manifest with source spans (dry-run only).

Increment 7 of #645. Builds a length-framed manifest over
``.dreamwork/questions.md`` with byte-accurate source spans, then prints the
live denominators. It WRITES NOTHING, and that property is STRUCTURAL rather
than remembered: :func:`dry_run` opens the file with a kernel-enforced
read-only descriptor (``os.open(path, os.O_RDONLY)``), and this module
contains no write path, no ``sqlite3`` connection and no mutable store. A bug
cannot write through a descriptor the kernel opened read-only — that is the
property, and the ``test_dry_run_descriptor_is_kernel_read_only`` test proves
the descriptor rejects ``os.write`` with ``OSError / EBADF``.

This is DARK code: nothing imports it yet (increment 8 is the import/verify
unit). It is the first increment in this family to read production data, and
its containment rule is "cannot write", satisfied by construction.

The five fixtures (heading, wrapped-title, multi-answer, missing-date,
unclassifiable) encode the shapes that have bitten this repo — ``#753`` (a
heading inside a body truncating a section), ``#702`` (drop nothing you
cannot classify), ``#446`` (a second answer overwriting the first), and the
parser's own wrapped-title / missing-date shape assumptions. They are the
specification.

Losslessness is established by an INDEPENDENT route, not by the parser
agreeing with itself (``#759``): a minimal line scanner counts structural
heads using only ``## `` boundaries, with no knowledge of the entry grammar,
the title-wrapping rules or the contribution tags. The parser's manifest must
agree with that independent count; a span that is one byte short still fails
the round-trip because the check re-derives the expected length from a fresh
source split, not from the parser's own offset arithmetic.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Union

PathLike = Union[str, os.PathLike[str]]

# --- grammar tags (mirrored from watch.py, kept inline so this is a leaf) ---
#
# watch.py's ``_parse_entries`` is the production reader whose losslessness
# this unit certifies — so this module does NOT import it. The tags are
# reproduced verbatim so the two cannot silently disagree about what a
# contribution is, while the span tracking, the unclassified reporting and
# the coverage check are new and lossless.

_ENTRY_MARK = "- **"
_ANSWER_PREFIX = "- **Answer (via watch"
_NOTE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("- **Note (human,", "human"),
    ("- **Follow-up (via watch,", "human"),
    ("- **Follow-up (loop,", "loop"),
    ("- **Follow-up (in-session,", "loop"),
)
_SUB_STAMP = re.compile(r"(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?\s*\)")
# A folded entry's body opens with the resolution the loop wrote:
# ``→ <verdict> (<date>[ <time>]): …``. Anchored to a line start (re.M) so a
# date deeper in the body is never read; the leading ``→`` is the
# never-guess rule (a date with no resolution head is prose).
_RESOLVED_AT = re.compile(
    r"^\s*→[^:]*?\((\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?\s*\)", re.M
)
# ``asked_at`` lives in the title prefix: ``P1 · 2026-08-01 21:45 — title``.
_ASKED_AT = re.compile(
    r"\A(?:P[123]\s+·\s+)?(\d{4}-\d{2}-\d{2})"
    r"(?:\s+(\d{2}:\d{2})(?::(\d{2}))?)?\s+—\s"
)
_RECOGNIZED_SECTIONS = ("Open", "Answered")


# --- manifest types --------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Span:
    """A half-open ``[start, end)`` byte range into the source."""

    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass(frozen=True, slots=True)
class Contribution:
    """One timestamped answer or note sub-bullet, in source order."""

    kind: str            # 'answer' | 'note'
    author: str          # 'human' | 'loop'
    text: str            # bullet text (first line + wrapped continuation)
    when: str | None     # parsed timestamp, or None when unstamped
    span: Span


@dataclass(frozen=True, slots=True)
class QuestionEntry:
    """One classified question head with its body and contributions."""

    ordinal: int                       # 1-based, file order within recognized sections
    section: str                       # 'Open' | 'Answered'
    state: str                         # 'unanswered' | 'answered_pending_fold' | 'answered'
    title: str                         # wrapped title joined on whitespace
    body_markdown: str                 # prose body lines (excluding contribution bullets)
    asked_at: str | None
    asked_precision: str               # 'unknown' | 'day' | 'minute' | 'second'
    resolution_date: str | None        # parsed from the → head, or None
    contributions: tuple[Contribution, ...]
    raw_text: str                      # exact source bytes of the whole entry
    span: Span
    first_line: int                    # 0-based source line index
    last_line: int                     # 0-based, inclusive


@dataclass(frozen=True, slots=True)
class UnclassifiedRegion:
    """Bytes inside a recognized section the entry grammar could not attribute
    to any question. Reported (``#702``), never dropped."""

    raw_text: str
    span: Span
    first_line: int
    last_line: int


@dataclass(frozen=True, slots=True)
class QuestionManifest:
    """The lossless manifest over one ``questions.md`` source."""

    source_bytes: int
    source_chars: int
    source_lines: int
    sha256: str
    sections: tuple[str, ...]                 # recognized section names found, in order
    entries: tuple[QuestionEntry, ...]
    unclassified: tuple[UnclassifiedRegion, ...]
    heads_outside_sections: int               # column-0 ``- **`` heads not in a recognized section
    section_bytes: int                        # bytes inside recognized sections (informational)


# --- line table ------------------------------------------------------------

def _line_table(data: bytes) -> list[tuple[int, int]]:
    """``[(start, end_excl_newline_plus_1)]`` per line.

    ``end`` is the byte offset just past the line's trailing ``\\n`` — equal
    to the next line's start, or ``len(data)`` at EOF. Consecutive lines are
    contiguous and the whole file is covered by ``[table[0][0], table[-1][1])``.
    """
    table: list[tuple[int, int]] = []
    start = 0
    for i, b in enumerate(data):
        if b == 0x0A:
            table.append((start, i + 1))
            start = i + 1
    if start < len(data):
        table.append((start, len(data)))
    return table


def _line_text(data: bytes, start: int, end: int) -> str:
    """The decoded line text without its trailing newline."""
    seg = data[start:end]
    if seg.endswith(b"\r\n"):
        seg = seg[:-2]
    elif seg.endswith(b"\n"):
        seg = seg[:-1]
    return seg.decode("utf-8")


# --- grammar predicates ----------------------------------------------------

def _contribution_kind(stripped: str) -> tuple[str, str] | None:
    """``(kind, author)`` if the stripped line opens a contribution bullet."""
    if stripped.startswith(_ANSWER_PREFIX):
        return ("answer", "human")
    for prefix, author in _NOTE_PREFIXES:
        if stripped.startswith(prefix):
            return ("note", author)
    return None


def _is_entry_head(line: str) -> bool:
    """True for a column-0 ``- **`` line that is NOT a contribution bullet."""
    if not line.startswith(_ENTRY_MARK):
        return False
    return _contribution_kind(line.strip()) is None


def _asked_from_title(title: str) -> tuple[str | None, str]:
    """``(asked_at, precision)`` read off the title prefix, fail-closed."""
    m = _ASKED_AT.match(title)
    if not m:
        return (None, "unknown")
    date = m.group(1)
    if m.group(3):       # HH:MM:SS
        return (f"{date} {m.group(2)}:{m.group(3)}", "second")
    if m.group(2):       # HH:MM
        return (f"{date} {m.group(2)}", "minute")
    return (date, "day")


def _partition_title(segment: str) -> tuple[str, bool, str]:
    """Split an entry line's text at the title's closing ``**``.

    Returns ``(title_segment, closed, rest)``. ``closed`` is False when the
    title is hard-wrapped and continues on the next line.
    """
    seg, sep, rest = segment.partition("**")
    return seg, bool(sep), rest


def _sub_when(stripped: str) -> str | None:
    m = _SUB_STAMP.search(stripped.split(":**", 1)[0])
    if not m:
        return None
    return m.group(1) + (" " + m.group(2) if m.group(2) else "")


def _join_title(parts: list[str]) -> str:
    return " ".join(p.strip() for p in parts if p.strip())


# --- the parser ------------------------------------------------------------

def question_manifest(data: bytes) -> QuestionManifest:
    """Parse ``questions.md`` source bytes into a lossless manifest.

    Pure: takes bytes, returns a manifest, touches no filesystem. Byte spans
    are half-open ``[start, end)`` into ``data`` and are derived from a line
    table built once over the raw bytes, so multibyte UTF-8 never shifts an
    offset.

    Entry spans are contiguous within an entry: each owns its head line, all
    body/contribution lines, and trailing blank separators up to the next
    column-0 line. A column-0 line that is neither an entry head nor blank
    nor indented terminates the entry and opens an *unclassified* region
    (``#702`` — report, never drop). A ``## `` heading exits the section;
    entry heads that follow outside a recognized section are counted as
    ``heads_outside_sections`` (the ``#753`` shape).
    """
    text = data.decode("utf-8")
    table = _line_table(data)
    n_lines = len(table)
    sha = hashlib.sha256(data).hexdigest()

    sections_found: list[str] = []
    raw_entries: list[dict[str, Any]] = []
    unclassified: list[UnclassifiedRegion] = []
    heads_outside = 0

    in_recognized = False
    cur: dict[str, Any] | None = None
    title_open = False
    sub: str | None = None           # 'answer' | 'note' while absorbing continuation
    uncls: dict[str, Any] | None = None
    section_bytes = 0
    sec_content_start: int | None = None   # first byte after a recognized heading

    def flush_section(heading_start: int) -> None:
        """Accumulate section bytes up to the next heading."""
        nonlocal section_bytes, sec_content_start
        if sec_content_start is not None:
            section_bytes += heading_start - sec_content_start
            sec_content_start = None

    def close_entry() -> None:
        nonlocal cur, title_open, sub
        if cur is not None:
            raw_entries.append(cur)
        cur = None
        title_open = False
        sub = None

    def close_unclassified(table_end: int) -> None:
        nonlocal uncls
        if uncls is None:
            return
        fl, ll = uncls["first_line"], uncls["last_line"]
        span = Span(table[fl][0], table[ll][1])
        unclassified.append(UnclassifiedRegion(
            raw_text=data[span.start:span.end].decode("utf-8"),
            span=span, first_line=fl, last_line=ll,
        ))
        uncls = None

    for idx in range(n_lines):
        start, end = table[idx]
        line = _line_text(data, start, end)
        stripped = line.strip()

        # --- section heading: checked FIRST, exits any open entry/section ---
        if line.startswith("## "):
            close_entry()
            close_unclassified(end)
            flush_section(start)
            name = line[3:].strip()
            if name in _RECOGNIZED_SECTIONS:
                in_recognized = True
                sec_content_start = end     # budget starts AFTER the heading line
                if name not in sections_found:
                    sections_found.append(name)
            else:
                in_recognized = False
            continue

        if not in_recognized:
            if _is_entry_head(line):
                heads_outside += 1
            continue

        # --- inside a recognized section ---
        is_head = _is_entry_head(line)
        contrib = _contribution_kind(stripped)

        # invariant 1 (watch.py): a column-0 entry head ALWAYS starts a new
        # entry, unconditionally — even while a title is open.
        if is_head:
            close_unclassified(end)
            close_entry()
            seg, closed, rest = _partition_title(line[len(_ENTRY_MARK):])
            cur = {
                "section": sections_found[-1] if sections_found else "Open",
                "first_line": idx, "last_line": idx,
                "title_parts": [seg], "body_lines": [],
                "contributions": [], "contrib_first_line": None,
                "contrib_last_line": None,
            }
            title_open = not closed
            if closed and rest:
                cur["body_lines"].append(rest)
            continue

        # while a wrapped title is unclosed, every line is title continuation
        if cur is not None and title_open:
            seg, closed, rest = _partition_title(stripped)
            cur["title_parts"].append(seg)
            cur["last_line"] = idx
            if closed:
                title_open = False
                if rest:
                    cur["body_lines"].append(rest)
            continue

        # a contribution bullet belongs to the current entry
        if contrib is not None and cur is not None:
            close_unclassified(end)
            kind, author = contrib
            when = _sub_when(stripped)
            ctext = stripped.split(":**", 1)[-1].strip()
            cur["contributions"].append({
                "kind": kind, "author": author, "text": ctext, "when": when,
                "first_line": idx, "last_line": idx,
            })
            cur["last_line"] = idx
            sub = kind                     # absorb wrapped continuation
            continue

        # blank or indented line: body continuation, contribution wrap, or
        # unclassified orphan
        if line == "" or line[0].isspace():
            if cur is not None:
                close_unclassified(end)
                if sub is not None and stripped:
                    # wrapped continuation of the last contribution
                    cur["contributions"][-1]["text"] += " " + stripped
                    cur["contributions"][-1]["last_line"] = idx
                elif not stripped:
                    sub = None             # blank line ends contribution wrap
                else:
                    cur["body_lines"].append(line)
                cur["last_line"] = idx
            elif uncls is not None:
                uncls["last_line"] = idx
            elif stripped:
                # indented prose with no owning entry -> unclassified orphan
                uncls = {"first_line": idx, "last_line": idx}
            continue

        # column-0 non-entry, non-blank, non-indented line inside a recognized
        # section: the parser cannot attribute it (#702). It terminates the
        # current entry and feeds an unclassified region rather than being
        # silently absorbed into body.
        close_entry()
        if uncls is None:
            uncls = {"first_line": idx, "last_line": idx}
        else:
            uncls["last_line"] = idx

    close_entry()
    close_unclassified(len(data))
    flush_section(len(data))

    entries = tuple(_build_entry(e, idx + 1, data, table)
                    for idx, e in enumerate(raw_entries))
    return QuestionManifest(
        source_bytes=len(data),
        source_chars=len(text),
        source_lines=n_lines,
        sha256=sha,
        sections=tuple(sections_found),
        entries=entries,
        unclassified=tuple(unclassified),
        heads_outside_sections=heads_outside,
        section_bytes=section_bytes,
    )


def _build_entry(
    cur: dict[str, Any], ordinal: int, data: bytes, table: list[tuple[int, int]]
) -> QuestionEntry:
    first, last = cur["first_line"], cur["last_line"]
    span = Span(table[first][0], table[last][1])
    title = _join_title(cur["title_parts"])
    body = "\n".join(cur["body_lines"]).strip("\n")
    asked_at, asked_prec = _asked_from_title(title)
    resolution = None
    if cur["section"] == "Answered":
        m = _RESOLVED_AT.search(body)
        if m:
            resolution = m.group(1) + (" " + m.group(2) if m.group(2) else "")
    contribs = tuple(_build_contribution(c, data, table) for c in cur["contributions"])
    n_answers = sum(1 for c in contribs if c.kind == "answer")
    if cur["section"] == "Answered":
        state = "answered"
    elif n_answers > 0:
        state = "answered_pending_fold"
    else:
        state = "unanswered"
    return QuestionEntry(
        ordinal=ordinal, section=cur["section"], state=state, title=title,
        body_markdown=body, asked_at=asked_at, asked_precision=asked_prec,
        resolution_date=resolution, contributions=contribs,
        raw_text=data[span.start:span.end].decode("utf-8"), span=span,
        first_line=first, last_line=last,
    )


def _build_contribution(c: dict[str, Any], data: bytes, table: list[tuple[int, int]]) -> Contribution:
    fl, ll = c["first_line"], c["last_line"]
    span = Span(table[fl][0], table[ll][1])
    return Contribution(
        kind=c["kind"], author=c["author"], text=c["text"],
        when=c["when"], span=span,
    )


# --- independent coverage route (#759: hold the subject, vary interpreter) --

def independent_head_count(data: bytes) -> tuple[int, int]:
    """Count structural heads using ONLY ``## `` section detection.

    Returns ``(inside_recognized, outside_recognized)``. This scan has no
    knowledge of title-wrapping, contributions or the entry state machine —
    it is the independent interpreter the manifest must agree with. A parser
    that silently merged or dropped an entry disagrees here.

    It reproduces the parser's section-exit rule (a ``## `` heading of any
    name exits the current section) so both interpreters agree on which heads
    are "inside" — but it counts heads by a raw ``startswith('- **')`` test
    with no contribution exclusion, no title-wrapping logic, and no body
    attribution. That is the independence: the SAME section boundaries, a
    DIFFERENT head detector.
    """
    in_recognized = False
    inside = 0
    outside = 0
    for raw in data.split(b"\n"):
        line = raw.decode("utf-8", "replace").rstrip("\r")
        if line.startswith("## "):
            name = line[3:].strip()
            in_recognized = name in _RECOGNIZED_SECTIONS
            continue
        if line.startswith("- **") and not line.startswith("  "):
            if in_recognized:
                inside += 1
            else:
                outside += 1
    return inside, outside


def coverage_report(manifest: QuestionManifest, data: bytes) -> dict[str, Any]:
    """Verify losslessness against the independent route.

    Three independent computations must agree:

    1. *Head count* — the manifest's entry count must equal the independent
       line-scan's head count inside recognized sections.
    2. *Round-trip spans* — each entry's reported span, re-sliced from the
       raw source, must equal bytes whose length an independent fresh split
       re-derives. A span one byte short still fails because the expected
       length comes from re-splitting the source, not from the parser's own
       offset arithmetic.
    3. *Heads-outside parity* — the manifest's ``heads_outside_sections``
       must equal the independent scan's outside count.

    ``ok`` is False if any check disagrees or if the source is non-empty but
    no entry was examined (``#671``: a check that examined nothing must not
    read as passing).
    """
    indep_inside, indep_outside = independent_head_count(data)

    examined = len(manifest.entries)

    # round-trip: re-derive each entry's expected byte length from a FRESH
    # line split of the source, independent of the parser's line table.
    fresh_lengths = _byte_line_lengths(data)
    roundtrip_bad: list[str] = []
    for e in manifest.entries:
        expected = sum(fresh_lengths[i] for i in range(e.first_line, e.last_line + 1))
        if e.span.length != expected:
            roundtrip_bad.append(
                f"ordinal {e.ordinal}: span {e.span.length}B != "
                f"re-derived {expected}B (lines {e.first_line}..{e.last_line})"
            )
        elif data[e.span.start:e.span.end].decode("utf-8", "replace") != e.raw_text:
            roundtrip_bad.append(
                f"ordinal {e.ordinal}: span slice != stored raw_text"
            )

    empty_corpus = manifest.source_bytes > 0 and examined == 0

    checks = {
        "head_count": {
            "manifest": examined,
            "independent": indep_inside,
            "ok": examined == indep_inside,
        },
        "roundtrip_spans": {
            "verified": examined - len(roundtrip_bad),
            "examined": examined,
            "bad": roundtrip_bad,
            "ok": not roundtrip_bad,
        },
        "heads_outside": {
            "manifest": manifest.heads_outside_sections,
            "independent": indep_outside,
            "ok": manifest.heads_outside_sections == indep_outside,
        },
        "examined_corpus": {
            "source_bytes": manifest.source_bytes,
            "entries": examined,
            "ok": not empty_corpus,
            "refusal": empty_corpus,
        },
    }
    return {"ok": all(c["ok"] for c in checks.values()), "checks": checks}


def _byte_line_lengths(data: bytes) -> list[int]:
    """Length (including trailing newline) of each line, via a fresh split."""
    lengths: list[int] = []
    start = 0
    for i, b in enumerate(data):
        if b == 0x0A:
            lengths.append(i + 1 - start)
            start = i + 1
    if start < len(data):
        lengths.append(len(data) - start)
    return lengths


# --- dry run (reads the live file, writes nothing) -------------------------

def dry_run(path: PathLike) -> str:
    """Read ``questions.md`` read-only, parse it, return the denominator report.

    WRITES NOTHING, structurally: the file is opened with ``os.O_RDONLY``, a
    kernel-enforced read-only descriptor. There is no write path in this
    module, no ``sqlite3`` connection and no mutable store. A bug cannot
    write through a descriptor the kernel refuses to write — the
    ``test_dry_run_descriptor_is_kernel_read_only`` test proves the
    descriptor rejects ``os.write`` with ``OSError / EBADF``.
    """
    p = Path(path)
    fd = os.open(str(p), os.O_RDONLY)
    try:
        chunks: list[bytes] = []
        while True:
            block = os.read(fd, 1 << 20)
            if not block:
                break
            chunks.append(block)
        data = b"".join(chunks)
    finally:
        os.close(fd)

    manifest = question_manifest(data)
    cov = coverage_report(manifest, data)
    return _format_report(manifest, cov)


def _format_report(manifest: QuestionManifest, cov: dict[str, Any]) -> str:
    e = manifest.entries
    n = len(e)
    by_section = {s: sum(1 for x in e if x.section == s) for s in _RECOGNIZED_SECTIONS}
    by_state = {
        "unanswered": sum(1 for x in e if x.state == "unanswered"),
        "answered_pending_fold": sum(1 for x in e if x.state == "answered_pending_fold"),
        "answered": sum(1 for x in e if x.state == "answered"),
    }
    answered = [x for x in e if x.section == "Answered"]
    with_res = sum(1 for x in answered if x.resolution_date is not None)
    missing_res = len(answered) - with_res
    missing_ids = _missing_resolution_labels(answered)
    wrapped = sum(1 for x in e if _title_wrapped(x))
    asked_present = sum(1 for x in e if x.asked_at is not None)
    contribs = [c for x in e for c in x.contributions]
    n_answer = sum(1 for c in contribs if c.kind == "answer")
    n_note = sum(1 for c in contribs if c.kind == "note")
    multi_answer = sum(1 for x in e
                       if sum(1 for c in x.contributions if c.kind == "answer") > 1)
    cls_bytes = sum(x.span.length for x in e)
    uncls_bytes = sum(u.span.length for u in manifest.unclassified)

    lines = [
        "questions.md dry-run — lossless manifest (writes nothing)",
        f"source: {manifest.source_bytes} bytes / {manifest.source_chars} chars / "
        f"{manifest.source_lines} lines / sha256 {manifest.sha256[:16]}…",
        f"sections recognized: {', '.join('## ' + s for s in manifest.sections) or '(none)'}",
        f"entries classified: {n}  "
        f"(independent head count inside sections: {cov['checks']['head_count']['independent']})",
        f"  by section: " + ", ".join(f"{s} {by_section[s]}" for s in _RECOGNIZED_SECTIONS),
        f"  by state: unanswered {by_state['unanswered']}, "
        f"answered_pending_fold {by_state['answered_pending_fold']}, "
        f"answered {by_state['answered']}",
        f"answered with resolution date: {with_res} / {len(answered)}",
        f"answered missing resolution date: {missing_res} / {len(answered)}"
        + (f"  ({missing_ids})" if missing_ids else ""),
        f"hard-wrapped titles: {wrapped} / {n}",
        f"asked_at present: {asked_present} / {n}",
        f"contributions: {len(contribs)}  (answer {n_answer}, note {n_note})",
        f"entries with multiple answers: {multi_answer} / {n}",
        f"unclassified regions: {len(manifest.unclassified)}  "
        f"({uncls_bytes} bytes / {manifest.section_bytes} section bytes)",
        f"heads outside recognized sections: {manifest.heads_outside_sections}  "
        f"(independent: {cov['checks']['heads_outside']['independent']})",
        f"byte coverage: {cls_bytes} classified + {uncls_bytes} unclassified "
        f"= {cls_bytes + uncls_bytes} of {manifest.section_bytes} section bytes",
        f"round-trip spans: {cov['checks']['roundtrip_spans']['verified']} / {n} verified",
    ]
    refusal = cov["checks"]["examined_corpus"]["refusal"]
    if refusal:
        lines.append(
            f"REFUSAL: source_bytes={manifest.source_bytes} > 0 but entries=0 — "
            f"examined nothing (#671); 100% over 0 entries is not a pass"
        )
    else:
        lines.append(
            f"examined check: source_bytes={manifest.source_bytes}, entries={n} — "
            f"{'examined (ok)' if n > 0 else 'empty file (ok)'}"
        )
    status = "PASS" if cov["ok"] else "FAIL"
    lines.append(f"coverage verdict: {status}")
    return "\n".join(lines)


def _missing_resolution_labels(answered: list[QuestionEntry]) -> str:
    out = []
    for x in answered:
        if x.resolution_date is None:
            m = re.search(r"#(\d+)", x.title)
            out.append("#" + m.group(1) if m else x.title[:24])
    return ", ".join(out)


def _title_wrapped(entry: QuestionEntry) -> bool:
    """True when the title's closing ``**`` is not on the head line."""
    head_line = entry.raw_text.split("\n", 1)[0]
    return head_line.count("**") < 2


def main(argv: list[str] | None = None) -> int:
    """``python3 -m dreamwork_db.question_parse [path]`` — print the dry run."""
    import sys
    args = sys.argv[1:] if argv is None else argv
    path = args[0] if args else ".dreamwork/questions.md"
    sys.stdout.write(dry_run(path) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
