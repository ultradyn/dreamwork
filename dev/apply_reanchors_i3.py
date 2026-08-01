#!/usr/bin/env python3
"""Resolve the reviewed citation anchors created by #777 increment 3.

The historical filename is retained because this is the one supported route
for those anchors.  An anchor's reviewed source text and named symbol are
authoritative; ``reviewed_line`` is only a baseline for reporting drift.  The
current line is derived by finding the evidence, so inserting lines cannot rot
the guard.  Missing or ambiguous evidence is a refusal, never a guessed line.
Despite its historical name, this is a read-only standing resolver: it never
writes source or documentation, and ``test_reanchor_citations.py`` exercises
its 74-anchor population.

IGC (#789), in the context of frequently edited ``watch.py``:

=======================  ===  ==  ==  ==  ==
Idea                     All  G1  G2  G3  G4
=======================  ===  ==  ==  ==  ==
symbol only               no  yes  no  no  yes
line plus repair          no  no   no  yes yes
symbol + reviewed text   yes  yes yes yes yes
=======================  ===  ==  ==  ==  ==

G1 survives arbitrary line insertion; G2 refuses ambiguity or missing
evidence; G3 preserves the human-reviewed referent; G4 keeps one supported
route.  Symbol-only is refuted by common tokens and call/definition ambiguity.
Line-plus-repair still makes healthy movement require a mutating pre-test step
and can guess among matches.  Reviewed text is stable under movement, while an
edit to the evidence correctly requires review.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ResolvedAnchor:
    path: str
    reviewed_line: int
    current_line: int
    symbol: str

    @property
    def drift(self) -> int:
        return self.current_line - self.reviewed_line


@dataclass(frozen=True)
class ReviewedAnchor:
    path: str
    reviewed_line: int
    symbol: str
    evidence: str
    scope: str | None = None

    def resolve(self, root: Path) -> ResolvedAnchor:
        path = root / self.path
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        evidence_lines = self.evidence.splitlines()
        leaf = self.symbol.rsplit(".", 1)[-1].removesuffix("()")
        symbol_pattern = re.compile(rf"(?<![\w$]){re.escape(leaf)}(?![\w$])")
        offsets = [
            offset for offset, line in enumerate(evidence_lines)
            if symbol_pattern.search(line)
        ]
        if len(offsets) != 1:
            raise ValueError(
                f"{self.path}:{self.reviewed_line} ({self.symbol}) has invalid reviewed "
                f"evidence: expected the named symbol exactly once, got {len(offsets)}"
            )
        offset = offsets[0]
        candidates = [
            start + offset + 1
            for start in range(len(lines) - len(evidence_lines) + 1)
            if lines[start:start + len(evidence_lines)] == evidence_lines
        ]
        if self.scope is not None:
            candidates = _within_python_scope(path, self.scope, candidates)
        deltas = [line - self.reviewed_line for line in candidates]
        label = f"{self.path}:{self.reviewed_line} ({self.symbol})"
        if not candidates:
            raise ValueError(
                f"{label} cannot be reanchored: reviewed evidence is missing; "
                "drift unknown"
            )
        if len(candidates) != 1:
            detail = ", ".join(
                f"line {line} (drift {delta:+d})"
                for line, delta in zip(candidates, deltas)
            )
            raise ValueError(f"{label} is ambiguous: {detail}")
        current = candidates[0]
        if symbol_pattern.search(lines[current - 1]) is None:
            raise ValueError(
                f"{label} reanchored to line {current} "
                f"(drift {current - self.reviewed_line:+d}) but lacks the named symbol"
            )
        return ResolvedAnchor(self.path, self.reviewed_line, current, self.symbol)


def _within_python_scope(path: Path, scope: str, candidates: list[int]) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    ranges = [
        (node.lineno, node.end_lineno)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == scope
        and node.end_lineno is not None
    ]
    if len(ranges) != 1:
        return []
    start, end = ranges[0]
    return [line for line in candidates if start <= line <= end]


ANCHORS = [
    ReviewedAnchor('watch.py', 342, 'COMMANDS', 'COMMANDS = ('),
    ReviewedAnchor('watch.py', 3683, 'track_question_updates', 'def track_question_updates(target, entries):'),
    ReviewedAnchor('watch.py', 3717, '_store_algo', '    if _store_algo(store) != SIG_ALGO:'),
    ReviewedAnchor('watch.py', 3726, 'seen_at', '            seen_at = reseeded_at if isinstance(prev, dict) else None'),
    ReviewedAnchor('watch.py', 3728, 'digest', '                "digest": _entry_content_digest(e),'),
    ReviewedAnchor('watch.py', 3735, 'return', '        _write_question_sigs(path, store)\n        return entries', scope='track_question_updates'),
    ReviewedAnchor('watch.py', 3737, 'dirty', '    dirty = False'),
    ReviewedAnchor('watch.py', 3752, 'digest', '        elif prev.get("digest") != dig:'),
    ReviewedAnchor('watch.py', 3765, 'emits_wake', '            if emits_wake("question-updated", target):'),
    ReviewedAnchor('watch.py', 3792, 'os.replace', '        os.replace(tmp, path)', scope='_write_question_sigs'),
    ReviewedAnchor('watch.py', 3797, 'collect', 'def collect(target, burn_step=None):'),
    ReviewedAnchor('watch.py', 3812, 'track_question_updates', '    track_question_updates(target, q_open + q_answered)'),
    ReviewedAnchor('watch.py', 4538, 'DELIVERY_DEFAULT', 'DELIVERY_DEFAULT = "instant"'),
    ReviewedAnchor('watch.py', 4615, 'PREEMPT_KINDS', 'PREEMPT_KINDS = ("chat", "do-now", "do-next")'),
    ReviewedAnchor('watch.py', 4566, 'delivery_mode', 'def delivery_mode(target):'),
    ReviewedAnchor('watch.py', 4575, 'emits_wake', 'def emits_wake(kind, target):'),
    ReviewedAnchor('watch.py', 4585, 'DELIVERY_DEFAULT', '    return delivery_mode(target) == DELIVERY_DEFAULT'),
    ReviewedAnchor('watch.py', 4621, 'log_event', 'def log_event(target, line):'),
    ReviewedAnchor('watch.py', 4632, 'OSError', '    except OSError:', scope='log_event'),
    ReviewedAnchor('watch.py', 4668, '_journal_receive', 'def _journal_receive(target, envelope):'),
    ReviewedAnchor('watch.py', 4685, '_journal_record_health', 'def _journal_record_health(target, receipt_id, health, detail=""):'),
    ReviewedAnchor('watch.py', 4847, 'command_line', 'def command_line(kind, text, source="", receipt_id=None):'),
    ReviewedAnchor('watch.py', 4963, '_journal_receive', '        def _journal_receive(self, target):'),
    ReviewedAnchor('watch.py', 5457, '_journal_receive', '                self._journal_receive(target)'),
    ReviewedAnchor('watch.py', 5672, '_handle_command', '        def _handle_command(self):'),
    ReviewedAnchor('watch.py', 5834, '_handle_run_mode', '        def _handle_run_mode(self):'),
    ReviewedAnchor('watch.py', 5863, '_handle_posture', '        def _handle_posture(self):'),
    ReviewedAnchor('watch.py', 6077, 'WRITE_ROUTE_HANDLERS', '        WRITE_ROUTE_HANDLERS = {'),
    ReviewedAnchor('watch.py', 2667, 'append_human_question', 'def append_human_question(text, question, stamp):'),
    ReviewedAnchor('watch.py', 909, 'read_bytes', 'def read_bytes(path):'),
    ReviewedAnchor('watch.py', 5139, '_send_bytes', '        def _send_bytes(self, full, rel, *, inline):'),
    ReviewedAnchor('watch.py', 804, 'read_text', 'def read_text(path, limit=None):'),
    ReviewedAnchor('watch.py', 974, 'detect_file_kind', 'def detect_file_kind(full):'),
    ReviewedAnchor('watch.py', 4606, 'resolve_confined', 'def resolve_confined(target, rel):'),
    ReviewedAnchor('watch.py', 947, 'INLINE_IMAGE_EXTS', 'INLINE_IMAGE_EXTS = ("png", "jpg", "jpeg", "gif", "webp", "avif")'),
    ReviewedAnchor('watch.py', 4860, '_expected_disconnect', 'def _expected_disconnect(exc):'),
    ReviewedAnchor('watch.py', 5190, 'do_GET', '        def do_GET(self):'),
    ReviewedAnchor('watch.py', 5081, '_send', '        def _send(self, body, ctype):'),
    ReviewedAnchor('watch.py', 4313, 'parse_posture_text', 'def parse_posture_text(raw):'),
    ReviewedAnchor('watch.py', 4394, 'resolve_posture', 'def resolve_posture(target):'),
    ReviewedAnchor('watch.py', 4437, 'write_posture', 'def write_posture(target, pace, asking, delegation, delivery=None,'),
    ReviewedAnchor('watch.py', 4505, 'posture_line', 'def posture_line(pace, asking, delegation, orchestration, source=""):'),
    ReviewedAnchor('watch.py', 5533, '_handle_answer', '        def _handle_answer(self):'),
    ReviewedAnchor('ledger_parse.py', 66, 'ledger_entries', 'def ledger_entries(text: str) -> list[tuple[list[int], str]]:'),
    ReviewedAnchor('ledger_parse.py', 37, 'ENTRY_HEAD', 'ENTRY_HEAD = re.compile(r"^- \\*\\*([^*]+?)\\*\\*")'),
    ReviewedAnchor('watch.py', 2042, 'ledger_series', 'def ledger_series(target, path=LEDGER_PATH, now=None, step=None):'),
    ReviewedAnchor('watch.py', 1619, '_LEDGER_SNAPS', '_LEDGER_SNAPS = {}         # (rev, tree-relative path) -> parsed snapshot'),
    ReviewedAnchor('watch.py', 1540, 'LEDGER_ENTRY', 'LEDGER_ENTRY = re.compile(rf"^- \\*\\*({IDS_ONLY_SPAN})\\*\\*", re.M)'),
    ReviewedAnchor('watch.py', 1570, 'LEDGER_COMBINED_MENTION', 'LEDGER_COMBINED_MENTION = re.compile(rf"\\*\\*({IDS_ONLY_SPAN})\\*\\*")'),
    ReviewedAnchor('watch.py', 1623, 'parse_ledger', 'def parse_ledger(text):'),
    ReviewedAnchor('watch.py', 1648, '_open_ids', 'def _open_ids(text):'),
    ReviewedAnchor('watch.py', 4721, 'log_submission', 'def log_submission(target, path, body, nbytes, truncated=False, short=False):'),
    ReviewedAnchor('watch.py', 5380, 'do_POST', '        def do_POST(self):'),
    ReviewedAnchor('watch.py', 4639, 'MAX_BODY', 'MAX_BODY = 20_000'),
    ReviewedAnchor('watch.py', 2561, 'atomic_write_text', 'def atomic_write_text(path, text):'),
    ReviewedAnchor('watch.py', 4603, 'ANSWER_LOCK', 'ANSWER_LOCK = threading.Lock()'),
    ReviewedAnchor('watch.py', 5366, '_read_json', '        def _read_json(self):'),
    ReviewedAnchor('watch.py', 4164, 'WATCHED_MTIME_IGNORED', 'WATCHED_MTIME_IGNORED = frozenset((QUESTION_SIGS, QUESTION_SIGS + ".tmp"))'),
    ReviewedAnchor('watch.py', 4264, 'write_tint', 'def write_tint(target, name):'),
    ReviewedAnchor('watch.py', 4207, 'watched_mtime', 'def watched_mtime(target):'),
    ReviewedAnchor('watch.py', 4280, 'read_run_mode', 'def read_run_mode(target):'),
    ReviewedAnchor('watch.py', 1360, 'serving_cached', 'def serving_cached(target):'),
    ReviewedAnchor('watch.py', 3553, 'skill_identity', 'def skill_identity(target=None):'),
    ReviewedAnchor('watch.py', 6087, '_handle_posture', '            "/posture": _handle_posture,'),
    ReviewedAnchor('watch.py', 5205, 'data.json', '            elif parsed.path == "/data.json":'),
    ReviewedAnchor('watch.py', 5235, 'mtime', '            elif parsed.path == "/mtime":'),
    ReviewedAnchor('ledger_write.py', 38, 'note_task', 'def note_task(store, task_id, note, *, actor="loop") -> None:'),
    ReviewedAnchor('watch.py', 2485, 'parse_open_answers', 'def parse_open_answers(text):'),
    ReviewedAnchor('watch.py', 5312, 'reviewraw', '            elif parsed.path == "/reviewraw":'),
    ReviewedAnchor('watch.py', 5199, 'parsed.path', '            if (parsed.path in ("/", "/questions", "/answers", "/file",'),
    ReviewedAnchor('watch.py', 5574, '_handle_comment', '        def _handle_comment(self):'),
    ReviewedAnchor('client/router.js', 1638, 'reconciliation', '/* #505 — keyed reconciliation of #view (I5: morphdom + content-hash skip).'),
    ReviewedAnchor('client/router.js', 1750, 'morphdom', '  morphdom(viewEl, \'<div id="view">\' + html + \'</div>\', {'),
    ReviewedAnchor('dreamwork_db/migrate.py', 28, 'MIGRATIONS', 'MIGRATIONS = ('),
]


def resolve_all(root: Path, anchors: list[ReviewedAnchor] = ANCHORS) -> list[ResolvedAnchor]:
    resolved: list[ResolvedAnchor] = []
    errors: list[str] = []
    for anchor in anchors:
        try:
            resolved.append(anchor.resolve(root))
        except (OSError, SyntaxError, ValueError) as exc:
            errors.append(str(exc))
    if errors:
        raise ValueError("reviewed citation anchors did not resolve:\n" + "\n".join(errors))
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        resolved = resolve_all(args.root.resolve())
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    for anchor in resolved:
        print(
            f"{anchor.path}:{anchor.reviewed_line} -> {anchor.path}:{anchor.current_line} "
            f"({anchor.symbol}, drift {anchor.drift:+d})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
