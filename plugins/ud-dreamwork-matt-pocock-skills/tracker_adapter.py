#!/usr/bin/env python3
"""tracker_adapter.py — the matt-pocock bridge's one real spec (design §8).

Maps the mattpocock/skills issue-tracker operations onto the Dreamwork ledger
verb seam and the questions.md channel. Three binding invariants, each a
design constraint the seam checks (T1–T5) pin:

  C1 — tasks only through `dev/ledger.py` verbs. This module NEVER opens
       `.dreamwork/tasks.md` or `.dreamwork/ledger.sqlite3`, and NEVER branches
       on source-of-truth. create / close / list_open shell out to the verb;
       the verb dispatches on `source_of_truth` internally, so the #294
       markdown→store cutover is invisible here by construction. (T1, T2.)
  C2 — grill questions land through the production `watch.human_block` (the
       only writer that cannot forge an entry), never hand-formatted. No
       invented author tag: only the closed set `watch.NOTE_TAGS` /
       `watch.ANSWER_TAGS` already hold is used — `Follow-up (loop, …)`.
       (T3, T5.)
  C3 — no per-target state is written under `.dreamwork/` beyond the core
       files the loop already owns (tasks.md, questions.md). (T4.)

The adapter is the suite's issue-tracker adapter; the suite's
`docs/agents/issue-tracker.md` (written at activation, NOT here) points at this
contract. This file is the contract itself: code + tests. It shells out to the
verb; it does not link the ledger module into the suite's process.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# The dreamwork core lives at <core>/ and this module at
# <core>/plugins/ud-dreamwork-matt-pocock-skills/tracker_adapter.py, so the
# core root is two parents up from this file's directory. `watch` (the
# production question writer / parser) is imported from there for `needs_info`
# — the only operation that does NOT shell out, per design §8 (the question
# channel uses `human_block`, an in-process production function).
_THIS_DIR = Path(__file__).resolve().parent
_CORE_DIR = _THIS_DIR.parent.parent
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))
import watch  # noqa: E402  — the production writer/reader, reused not copied

LEDGER_SCRIPT = _CORE_DIR / "dev" / "ledger.py"
SEED_QUESTIONS = "# Questions for the human\n\n## Open\n\n## Answered\n"


# ---------------------------------------------------------------------------
# paths — constructed, never opened here (C1)
# ---------------------------------------------------------------------------

def ledger_script(core_dir=None) -> Path:
    """Path to `dev/ledger.py` under the dreamwork core (overridable for tests)."""
    return Path(core_dir) / "dev" / "ledger.py" if core_dir else LEDGER_SCRIPT


def _dw(target_dir) -> Path:
    return Path(target_dir) / ".dreamwork"


def ledger_path(target_dir) -> Path:
    """The target's ledger path, as a STRING passed to the verb's `--ledger`.

    Constructed only — never opened by this module (C1). The verb opens it."""
    return _dw(target_dir) / "tasks.md"


def questions_path(target_dir) -> Path:
    """The target's questions.md (the grill channel — not the ledger)."""
    return _dw(target_dir) / "questions.md"


# ---------------------------------------------------------------------------
# task verbs — shell out to dev/ledger.py (C1: never open the ledger here)
# ---------------------------------------------------------------------------
#
# `runner` defaults to subprocess.run and is injectable so the seam checks can
# mock the subprocess without patching the global — the verb's argv is the
# thing T1/T2 assert on. Every verb takes `--ledger <path>` and lets the verb
# dispatch on source_of_truth internally; this module passes no
# source-of-truth flag and reads no watermark.

def create(core_dir, target_dir, title, *, note=None, priority=None, type=None,
           origin="loop", runner=subprocess.run):
    """create issue / publish ticket  →  `dev/ledger.py file`.

    The suite's "publish to tracker" call. Files a task in the shared ledger
    through the verb; the bridge mints no id and holds no queue."""
    argv = [sys.executable, str(ledger_script(core_dir)), "file", title,
            "--ledger", str(ledger_path(target_dir)), "--origin", origin]
    if note is not None:
        argv += ["--note", note]
    if priority is not None:
        argv += ["--priority", priority]
    if type is not None:
        argv += ["--type", type]
    return runner(argv, capture_output=True, text=True)


def close(core_dir, target_dir, task_id, *, note, runner=subprocess.run):
    """close / wontfix  →  `dev/ledger.py fold --note`.

    Lands the entry with a note through the verb; the bridge moves no text."""
    argv = [sys.executable, str(ledger_script(core_dir)), "fold", str(task_id),
            "--note", note, "--ledger", str(ledger_path(target_dir))]
    return runner(argv, capture_output=True, text=True)


def list_open(core_dir, target_dir, *, runner=subprocess.run):
    """list open issues  →  `dev/ledger.py counts`.

    Returns the verb's open/landed id counts. A read consumer; it shells out
    exactly like the write verbs so the #294 cutover is invisible (T2)."""
    argv = [sys.executable, str(ledger_script(core_dir)), "counts",
            "--ledger", str(ledger_path(target_dir))]
    return runner(argv, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# grill seam — questions.md via watch.human_block (C2: never hand-format)
# ---------------------------------------------------------------------------

def grill_note(body, when):
    """The loop's follow-up note carrying a grill question's recommended answer.

    Routed through the PRODUCTION `watch.human_block` so the body — which may
    contain pasted bullets or `- **` text — can never forge a top-level entry
    or a section heading (C2). The author tag is `Follow-up (loop, …)`, a
    member of the closed `watch.NOTE_TAGS` set; none is invented (T5)."""
    return watch.human_block(f"- **Follow-up (loop, {when}):**", body)


def pose_question(questions_text, question, body, when):
    """Insert a new grill question as the FIRST entry under `## Open`.

    One grill question → one questions.md entry (design OQ2). The entry head
    is structural; the loop's note (the load-bearing human/loop text) is built
    by `grill_note` → `human_block`. Pure — testable without a filesystem, and
    what T3 parses back through the REAL `watch.parse_open_questions`."""
    entry = f"- **{question}**\n{grill_note(body, when)}"
    return _insert_first_open_entry(questions_text, entry)


def _insert_first_open_entry(text, entry_block):
    """Place `entry_block` as the first entry under an exact `## Open` heading.

    Anchors on the literal `## Open` heading line (the reader's own match), not
    on a substring scan. A missing heading is an error, not a silent no-op — a
    questions.md the bridge cannot write into is a fault to surface."""
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        if ln.strip() == "## Open":
            # skip the conventional blank line that follows the heading, then
            # insert the entry with blank separators either side
            j = i + 1
            if j < len(lines) and lines[j].strip() == "":
                j += 1
            new = lines[:i + 1] + ["", entry_block, ""] + lines[j:]
            return "\n".join(new)
    raise ValueError("no `## Open` heading in questions.md — cannot pose a grill question")


def needs_info(target_dir, question, body, when):
    """set state needs-info  →  ask the human via `questions.md` (C2).

    Poses one grill question (no resolution — grilling is HITL; the bridge
    never answers its own questions). Writes to questions.md, a CORE file the
    loop already owns, so the bridge introduces no new file under .dreamwork/
    (C3/T4)."""
    path = questions_path(target_dir)
    text = path.read_text(encoding="utf-8") if path.is_file() else SEED_QUESTIONS
    path.write_text(pose_question(text, question, body, when), encoding="utf-8")
