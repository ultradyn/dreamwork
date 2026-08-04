#!/usr/bin/env python3
"""Generate the mechanical frame of a lane brief; refuse an empty authored core.

    python3 dev/brief.py --task 881 --owns dev/brief.py,test_brief.py \
        --core /path/to/core.md > /tmp/brief.md
    python3 dev/dispatch_lane.py --prompt /tmp/brief.md --prepare

Measured before it was written (`.dreamwork/docs/measurements/881-brief-frame.md`,
reproduce with `dev/brief_corpus_stats.py`): across the 40 most recent briefs the
appended boilerplate is 73.7% of the bytes and is already one file
concatenation, while the hand-retyped frame is only 7.3%.  So this tool is not
mainly a typing saver.  What it fixes is that `## Standing rules` was retyped 33
times and produced **32 distinct bodies** — a lane's rule set depended on what
the coordinator remembered.  `- REBASE onto master before you report` reached
9 of 33.  `Lane-owns:`, which SKILL.md makes mandatory and `lint.py` makes an
ERROR, reached 2 of 40.

## The boundary, and why it is enforced rather than documented

MECHANICAL, generated here: the identity header and its derived values, the
repo-root and absolute-inbox lines, the `--ledger` read form, the standing
rules, the live-state prohibitions, the report skeleton, the boilerplate append.

AUTHORED, supplied by `--core` and never templated: the defect with its
measurements, the fix-shape reasoning, and the direction-2 candidate list —
*"here is how a test of this could pass while the thing is broken"*.  That last
one is where this loop's quality comes from and a generator that templated it
would emit briefs that look complete and teach nothing, which is worse than
slow.  `validate_core` therefore REFUSES a core that is empty, placeholder, or
carries no direction-2 section with a body.  Refusing rather than warning is
the point: a generator that emits a frame with a `TODO` core is a generator
that will be used that way at 3am.

**What that refusal can and cannot detect.**  It binds *presence with a
non-placeholder body*.  It cannot judge whether the direction-2 list is any
good — no check can — and it must not be reported as if it did.

Tool-verb validation is narrower still: it checks only that a named verb exists
on master's copy of a tool.  It does not re-derive numbers, environments, tool
arguments, or which interpreter a lane will actually run.  A brief can pass
this check and remain wrong in any of those ways, so every result names both
the checked and NOT-CHECKED populations.

Placeholder detection is LINE-shaped, not token-shaped, and that came from the
measurement: the only two placeholder tokens in 40 brief heads are both in
#881's own brief, which discusses placeholders in prose.  A token-level
`contains("TODO")` would have refused the brief that commissioned this tool.

## On sharing a notion of validity with the validator

`dev/dispatch_lane.py` refuses a brief that fails any of: the exact coordinator
inbox line, a bare unique `Branch:` line, a `Base sha:` equal to the branch
point off master, the boilerplate appended verbatim and last.  The strongest
version of this tool is one whose output cannot fail that validation — but if
the two shared their notion of a valid brief, the validator could no longer
witness a generator bug, and "checker and checked share a source of truth" is
this repo's recurring root cause.

So they are independent in production and bound by a test.  This module imports
nothing from `dispatch_lane` and re-derives every constrained value from the
same primary source the validator consults (`git merge-base`, `git worktree
list`, the repo layout) rather than from the validator's parse of it.  The
literal inbox sentence is retyped here on purpose.  `test_brief.py` asserts it
equals `dispatch_lane.COORDINATOR_INBOX_PREFIX` and runs real generated output
through `dispatch_lane.validate_prompt`.  Drift is then a loud test failure
before it costs a dispatch, and a runtime typo here is still refused by an
instrument that did not help write it.

The one exception is `--review` (#1115).  A review prompt had no generator at
all — the coordinator concatenated `briefs/review-frame.md` by hand, and
`#1109` measured that the frame was a convention, not a construction.  The fix
is to make the generator and the receipt the *same path*: `review_prompt`
appends the frame by construction and `main` persists through
`dispatch_lane.persist_review_prompt` (#1112) rather than re-deriving the
receipt.  So the lane path (`build`) stays independent of `dispatch_lane`, and
the review path deliberately is not — collapsing generator and validator for
review is the point, because a hand-assembled review prompt is exactly what
there is no second instrument to witness.

## #644 IGC: one mechanical mitigation, not a bundle

Context: a precise authored core can carry (F1) a remembered/inferred specific,
(F2) mutable ledger state, (F3) a relaxed rule remembered as live, or (F4) a
derived count that rotted. G1 is independent of author confidence; G2 keeps a
correct, precise brief generatable; G3 closes a live defect without another
author convention. “partial” catches only a subset of a family.

| Rival | All | F1 | F2 | F3 | F4 | Refuses correct? | G1 | G2 | G3 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| inline confidence labels | ✘ | ✔ | — | — | — | no | ✘ | ✔ | ✘ |
| derive boilerplate constants | ✘ | — | — | — | ✔ | no | ✔ | ✔ | ✘ |
| resolve repo `file:line` at base SHA | ✔ | partial | — | — | — | no | ✔ | ✔ | ✔ |
| date/SHA on rule citations | ✘ | — | — | partial | — | yes | ✘ | ✘ | ✘ |
| omit mutable ledger fields | ✘ | — | ✔ | — | — | yes | ✔ | ✘ | ✘ |

Decisive errors: confidence labels still trust the confidently-wrong author;
the stale count named by this task has already been removed, so a new derived
token would not close typed counts; a ruling date exposes age but cannot prove
the ruling remains live and rejects a correct undated citation; forbidding a
currently-correct ledger field rejects a correct brief. Base-SHA resolution is
the sole survivor: it closes the observed wrong-path coordinate mechanically,
while stating plainly that a resolving line can still support a false claim.

## #1209 IGC: close one remaining family without refusing correct briefs

Context: #644 left (F3) relaxed rules quoted as live, (F4) rotted generated
counts, and (F5) stale mutable fields. G1 closes an observed family
mechanically; G2 never refuses a correct precise brief; G3 is independent of a
confident author's judgement. “partial” means the rival catches only its
explicitly detectable subset.

| Rival | All | F3 | F4 | F5 | Refuses correct? | G1 | G2 | G3 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| date/SHA on rule citations | ✘ | partial | — | — | yes | ✘ | ✘ | ✘ |
| derive and compare `lesson citations` rows | ✔ | — | partial | — | no | ✔ | ✔ | ✔ |
| forbid mutable ledger fields in heads | ✘ | — | — | ✔ | yes | ✔ | ✘ | ✔ |

Decisive errors: a ruling date exposes age but neither proves the ruling is
still live nor accepts a correct undated citation; forbidding a current ledger
field rejects a correct brief. The surviving asymmetric check derives the
named lint population at the generation SHA and refuses only a mismatch. It
closes the observed F4 instance without claiming to catch arbitrary counts;
F3 and F5 remain open.

## Storage

This tool writes no files and opens no store for writing; it emits text on
stdout.  Persisting a brief is `dispatch_lane.persist_prompt`'s job and it
already owns the corpus path, the create-once semantics, and the hash receipt.
That keeps the tracked/untracked question (`#867`) a parameter of a component
this tool does not touch.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import land_lane


ROOT = Path(__file__).resolve().parent.parent
FRAME_PATH = ROOT / "briefs" / "frame.md"
BOILERPLATE_PATH = ROOT / "briefs" / "boilerplate.md"

# The **#NNN** glossed-citation token is defined ONCE, shared with
# dev/citation_audit.py, so the two extractors cannot drift apart again (#1156).
# This is a shared DEFINITION, not a shared validity judgment — the
# dispatch_lane independence documented below is untouched, because the token
# shape is not a constrained value either tool re-derives from the corpus.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from dev.citation_token import GLOSSED_CITATION_TOKEN  # noqa: E402

# Retyped rather than imported from dispatch_lane, on purpose — see the module
# docstring.  test_brief.py binds the two literals.
COORDINATOR_INBOX_PREFIX = (
    "Coordinator inbox — ABSOLUTE path, append your completion summary here "
    "when you finish: "
)

# A line is a placeholder only when its ENTIRE content, after bullets and
# markdown decoration are stripped, is fill-in material.  A sentence that
# mentions TODO is a sentence.
_DECORATION = re.compile(r"^(?:[-*+]\s+|\d+[.)]\s+)?[`*_~\s]*(.*?)[`*_~\s:.,;-]*$")
_PLACEHOLDER_BODY = re.compile(
    r"^(?:TODO|TBD|FIXME|XXX|WIP|PLACEHOLDER|N/?A|\.{2,}|…"
    r"|<[^<>]*>|\[[^\[\]]*\]"
    r"|(?:TODO|TBD|FIXME|XXX)\s*[:-].*)$",
    re.IGNORECASE,
)
CANONICAL_TRAPS_HEADING = (
    "## Traps this fix must survive — EVERY BULLET BELOW IS A THING NOT TO DO"
)
_TRAPS_SECTION_HEADING = re.compile(
    r"^ {0,3}#{1,6}[ \t]+(?:"
    r"direction[ ‑-]?2\b|"
    r"traps[ \t]+this[ \t]+(?:fix|round)[ \t]+must[ \t]+survive\b"
    r")",
    re.IGNORECASE,
)
_MARKDOWN_CLASS = re.compile(
    r"(?:\.md\s+(?:file|document)s?\b|markdown\s+(?:file|document)s?\b)",
    re.IGNORECASE,
)
_BLANKET = re.compile(r"\b(?:any|all|every)\b", re.IGNORECASE)
_PROHIBITION = re.compile(
    r"\b(?:do\s+not|don't|must\s+not|never|no)\b.*"
    r"\b(?:edit|write|create|modify|touch|change)(?:ed|ing|s)?\b|"
    r"\b(?:edit|write|create|modify|touch|change)(?:ed|ing|s)?\b.*"
    r"\b(?:forbidden|prohibited|not\s+allowed)\b",
    re.IGNORECASE,
)
# Header fields the generator owns.  A core that also carries one would give
# dispatch_lane two `Branch:` lines and no way to tell which is the instruction.
_RESERVED_FIELD = re.compile(
    r"^(Worktree|Branch|Base sha|Repo root|Lane-owns|Coordinator inbox)\b", re.MULTILINE
)

# A Markdown ATX heading, per CommonMark §4.2: 0–3 leading spaces, 1–6 `#`, then
# a space (or tab) or end-of-line.  A bare leading `#` with no following space —
# `#847 is the campaign` — is NOT a heading, which is the distinction #947 turns
# on: opening a sentence with a task id is the house style and must not read as
# a section opener.  The previous code used `startswith("#")` and treated every
# such line as a heading, so the section it belonged to was left apparently
# empty.  ONE definition is shared by `_substantive` and `validate_core`'s
# section walk (#852/#905: the checker and the checked must not disagree about
# their subject).
_ATX_HEADING = re.compile(r"^ {0,3}#{1,6}(?:[ \t]|$)")


def _is_atx_heading(line: str) -> bool:
    """Whether ``line`` opens a Markdown ATX heading (CommonMark §4.2)."""
    return _ATX_HEADING.match(line) is not None


# A fenced code-block opener (CommonMark §4.5): up to 3 leading spaces, then 3+
# backticks or tildes.  Lines inside a fence are never headings and never
# structure — a brief whose job is to describe document structure must be able
# to quote Markdown, and a fenced ``## Read ...`` is a quotation, not a section
# of the brief (#947 third instance).
_FENCE_OPEN = re.compile(r"^( {0,3})(`{3,}|~{3,})")


def _is_traps_section_heading(line: str) -> bool:
    """Recognise the trap-list section by its heading, never by body prose."""
    return _TRAPS_SECTION_HEADING.search(line) is not None


def _canonicalize_traps_heading(core: str) -> str:
    """Give legacy authored cores an unambiguous trap heading on emission."""
    lines = core.splitlines()
    in_fence = False
    fence_char = ""
    fence_len = 0

    for index, line in enumerate(lines):
        if in_fence:
            if re.match(
                rf"^ {{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*$", line
            ):
                in_fence = False
            continue
        opened = _FENCE_OPEN.match(line)
        if opened:
            in_fence = True
            fence_char = opened.group(2)[0]
            fence_len = len(opened.group(2))
            continue
        if _is_traps_section_heading(line):
            lines[index] = CANONICAL_TRAPS_HEADING

    return "\n".join(lines)

_TOOL_INVOCATION = re.compile(
    r"(?<![\w./-])(?P<path>"
    r"/[^\s`\"'<>]*/ud-dreamwork/(?:dev/)?[A-Za-z_][\w-]*\.py"
    r"|dev/[A-Za-z_][\w-]*\.py"
    r"|[A-Za-z_][\w-]*\.py)"
    r"[ \t]+(?P<verb>[A-Za-z][\w-]*)"
)
_QUOTED_PROSE = re.compile(r'"[^"\n]*"|“[^”\n]*”|\'[^\'\n]*\'|‘[^’\n]*’')
_ARGPARSE_CHOICES = re.compile(r"choose from (?P<choices>[^)]+)\)")
_DOCUMENTED_SUBCOMMANDS = re.compile(r"`(?P<verb>[a-z][a-z0-9-]*)(?:\s|`)")

# Deliberately narrow: this reports decimal integers asserted in prose, not
# every digit-shaped token in Markdown.  The exclusions keep task ids, source
# coordinates, versions, dates, percentages, approximations, digit-grouped
# values, inline code, quotations, and code blocks out of the population.  A
# report with known blind spots is usable; a noisy "all numbers" scan is not.
_ASSERTED_QUANTITY = re.compile(
    r"(?<![#\w.,:/~-])(?P<number>\d+)(?![\w.,/%~-])"
    r"(?:[ \t]+(?P<unit>[A-Za-z][A-Za-z-]*))?"
)
_INLINE_CODE = re.compile(
    r"(?<!`)(?P<fence>`+)(?P<body>.*?)(?P=fence)(?!`)", re.DOTALL
)
# Repo-relative source coordinates are mechanically decidable at the brief's
# generation SHA.  Keep the suffix list source-shaped so prose such as
# ``version 3.11:2`` is not promoted into a citation, and require a full path
# token so the tail of a URL cannot match on its own (#644).
_FILE_LINE_CITATION = re.compile(
    r"(?<![\w./-])(?P<path>"
    r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*"
    r"\.(?:css|html|js|json|md|mjs|py|sh|toml|txt|ya?ml)"
    r"):(?P<first>[1-9]\d*)(?:-(?P<last>[1-9]\d*))?"
    r"(?![\w.-])",
    re.IGNORECASE,
)
_LESSON_CITATION = re.compile(r"lessons\.md:(\d+)")
_COUNT_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_LESSON_CITATION_COUNT_CLAIM = re.compile(
    r"\b(?P<count>\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(?:known\s+)?`?lesson[ -]citations?`?\s+"
    r"(?:false[ -]positive\s+)?rows?\b",
    re.IGNORECASE,
)
_GLOSSED_TASK_CITATION = re.compile(
    rf"(?<![\w/]){GLOSSED_CITATION_TOKEN}\s*(?:—|:)\s*"
    rf"(?P<gloss>\S.*?)(?=\s+(?:\*\*)?#\d+(?:\*\*)?\s*(?:—|:)|$)"
)
_DIRECTION_NUMBER = re.compile(r"\bdirection\s+\d+\b", re.IGNORECASE)
_VERIFICATION_CUE = re.compile(
    r"\b(?:verif(?:y|ied|ication)|re[ -]?deriv(?:e|ation)|reproduc(?:e|tion))\b",
    re.IGNORECASE,
)
_COMMANDISH = re.compile(
    r"(?:^|[;&|]\s*|\b)(?:awk|find|git|grep|just|python\d*|rg|sed|wc)\b|"
    r"(?:^|\s)(?:\./|dev/)[\w./-]+",
    re.IGNORECASE,
)
_BLOCKING_STOP_CUE = re.compile(
    r"(?:\b(?:stop|refuse|do\s+not\s+proceed)\b.*"
    r"\b(?:if|unless|when|otherwise)\b|"
    r"\b(?:if|unless|when|otherwise)\b.*"
    r"\b(?:stop|refuse|do\s+not\s+proceed)\b)",
    re.IGNORECASE,
)
_BLOCKING_SECTION_CUE = re.compile(
    r"\bblocking\b.*\b(?:numbers?|invariants?|stop[ -]?conditions?)\b",
    re.IGNORECASE,
)
_NONBLOCKING_CUE = re.compile(
    r"\b(?:not\s+blocking|non[ -]blocking|context\s+only|do\s+not\s+stop)\b",
    re.IGNORECASE,
)
_INVARIANCE_JUSTIFICATION_CUE = re.compile(
    r"\binvariants?\b|"
    r"\b(?:cannot|can't|does\s+not|won't|will\s+not|do\s+not)\s+"
    r"(?:change|perish)\b|"
    r"\bstable\b|\bunchanging\b|"
    r"\bdispatch(?:ing)?\b[^.\n]*\b(?:cannot|does\s+not|will\s+not)\s+change\b",
    re.IGNORECASE,
)
_UNIT_STOPWORDS = {
    "after", "and", "as", "at", "before", "by", "for", "from", "in",
    "is", "of", "on", "or", "than", "that", "the", "to", "was", "were",
    "with",
}

# --- #1028: command-existence and task-state claim reports -----------------
#
# Two mechanically checkable premise classes that burned six dispatches in one
# evening (#1028).  Both follow the #994 precedent: REPORT, do not certify.
# A ``just <recipe>`` inside inline code or a fenced block is a claim the recipe
# exists; a ``#NNN`` inside a state-predicate or expected-output context is a
# claim about that task's state.  Both are resolvable at generation by a command
# the lane would otherwise run itself.
#
# ``just`` is an English word, so the recipe matcher is restricted to CODE
# CONTEXT (inline code and fenced blocks).  Measured across the corpus: 10 false
# positives in 152 prose matches ("just the", "just as"), zero in 199
# code-context matches.
_JUST_RECIPE = re.compile(
    r"(?<![\w./-])just\s+(?P<recipe>[a-z][a-z0-9_-]*)\b", re.IGNORECASE
)
# A #NNN directly asserted to be in a state: "#641 is live", "#630 is open".
# "live"/"stale" map to formal state "open"; "done"/"closed" to "landed".
_OPEN_IMPLYING = r"open|live|stale"
_LANDED_IMPLYING = r"landed|done|closed"
# A #NNN directly asserted to be in a state: "#641 is live", "#630 is open".
# "live"/"stale" map to formal state "open"; "done"/"closed" to "landed".
# The gap between the subject #NNN and the state verb carries a negative
# lookahead on ``#\d+`` so the predicate binds to THAT id, not a later one:
# in "#671 exactly, and #816 is a live task" the gap after #671 hits #816 and
# fails, so #671 is NOT claimed and #816 IS — fixing the prior lane's false
# positive for #671 and the simultaneous miss of #816 (#1028).
_TASK_STATE_PREDICATE = re.compile(
    r"#(?P<task>\d+)(?:(?!#\d+)[^.\n;]){0,25}?\b(?:is|are|was|were|remain|stands)\b"
    r"(?:(?!#\d+)[^.\n;]){0,15}?\b(?P<state>"
    + _OPEN_IMPLYING + r"|" + _LANDED_IMPLYING + r")\b",
    re.IGNORECASE,
)
# A WARN-row expected-output claim: "WARN rows (#630, #641)".  This predicts
# every id in the clause will appear in lint output, i.e. claims each is
# active.  The prior regex captured a SINGLE ``#NNN`` and ``finditer`` resumed
# AFTER it — so "WARN rows (#630, #700)" reported #630 and dropped #700 as an
# "other citation", missing exactly the landed-id mismatch this checker exists
# to find (#1028 P1).  The clause is bounded by a sentence terminator (``.``,
# newline, ``;``) or 30 chars — the SAME boundary the prior lane measured as
# false-positive-free across 77 cores (a wider window reaches ``#794`` in
# quoted standing-rules prose, "WARN ROW SET … (`#794`)", and creates ~20
# false positives).  Every ``#NNN`` inside the clause is then a claim.
_TASK_WARN_OUTPUT = re.compile(
    r"\bWARN\s+rows?\b(?P<clause>[^.\n;]{0,30})",
    re.IGNORECASE,
)


class BriefFault(Exception):
    """A brief could not be generated from the inputs given."""


def blanket_markdown_prohibition(text: str) -> bool:
    """Whether one prose block forbids the whole Markdown-file class.

    This is intentionally semantic rather than pinned to the measured
    ``.md document`` spelling: ``any Markdown file`` is the same defect.
    Paragraphs are normalized so ordinary Markdown wrapping cannot hide it.
    """
    blocks: list[str] = []
    current: list[str] = []
    for line in [*text.splitlines(), ""]:
        if not line.strip() or re.match(r"^\s*(?:[-*+] |\d+[.)] )", line):
            if current:
                blocks.append(" ".join(current))
            current = [line] if line.strip() else []
        else:
            current.append(line)
    for block in blocks:
        prose = re.sub(r"[`*_]", "", " ".join(block.split()))
        prose = re.sub(r'["“][^"”]*["”]', "", prose)
        if (_MARKDOWN_CLASS.search(prose) and _BLANKET.search(prose)
                and _PROHIBITION.search(prose)):
            return True
    return False


def _git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            capture_output=True, text=True, check=False,
        )
    except OSError as exc:
        raise BriefFault(f"could not run git: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or f"git exited {result.returncode}"
        raise BriefFault(f"git {' '.join(args)}: {detail}")
    return result.stdout


def main_checkout() -> Path:
    """The main checkout, resolved from git rather than from this file's path."""
    common = _git("rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    if not common or "\n" in common:
        raise BriefFault("git returned no unique common directory")
    path = Path(common)
    if not path.is_absolute() or path.name != ".git" or not path.is_dir():
        raise BriefFault(f"git common directory is not a checkout .git dir: {path}")
    return path.parent


def worktree_for(branch: str) -> Path:
    """The worktree checked out on ``branch``, asked of git, never guessed.

    Deriving it means a brief cannot name a worktree that does not exist, and
    proves the branch exists in the same reading.  The corpus shows why the
    convention is not a safe default: `Worktree:` moved from
    `ud-dreamwork/.worktrees/` to `skills/.worktrees/` mid-corpus when #846
    landed, and 14 of 40 briefs still name the old shape.
    """
    current: Path | None = None
    for line in _git("worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            current = Path(line[len("worktree "):])
        elif line == f"branch refs/heads/{branch}" and current is not None:
            if not current.is_dir():
                raise BriefFault(
                    f"git lists a worktree for branch {branch!r} at {current}, "
                    "but that is not an existing directory"
                )
            return current.resolve()
    raise BriefFault(
        f"no worktree is checked out on branch {branch!r}; create it before "
        "generating its brief, so the brief cannot name a worktree that does not exist"
    )


def base_sha(branch: str) -> str:
    """The branch point off master — the value dispatch_lane will recompute."""
    sha = _git("merge-base", "master", branch).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise BriefFault(
            f"branch point of master and {branch!r} did not resolve to a commit: {sha!r}"
        )
    return sha


def task_record(task: int, ledger: Path) -> dict:
    """One task record, read-only, through ledger.py's own reader."""
    sys.path.insert(0, str(ROOT / "dev"))
    try:
        import ledger as ledger_module  # noqa: PLC0415
    except ImportError as exc:
        raise BriefFault(f"could not load the ledger reader: {exc}") from exc
    try:
        records = ledger_module._read_records(str(ledger.parent))
    except Exception as exc:
        raise BriefFault(f"could not read ledger {ledger}: {exc}") from exc
    if not records:
        raise BriefFault(
            f"ledger {ledger} holds NO entries at all, so a not-found for #{task} "
            "would be a fact about the ledger and not about the task"
        )
    match = next((r for r in records if r["id"] == task), None)
    if match is None:
        raise BriefFault(f"#{task} not found in {ledger} ({len(records)} entries read)")
    return match


def _substantive(line: str) -> bool:
    """True if the line carries authored content rather than fill-in or structure."""
    stripped = line.strip()
    if not stripped or _is_atx_heading(line):
        return False
    body = _DECORATION.match(stripped)
    inner = body.group(1).strip() if body else stripped
    if not inner:
        return False
    return not _PLACEHOLDER_BODY.fullmatch(inner)


def substantive_lines(text: str) -> list[str]:
    """The lines carrying authored content — not blank, not a heading, not fill-in.

    Public because `dev/launch_lane.py` shares it.  Both are brief EMITTERS, so
    a shared notion of "the author wrote something" is correct there; the
    independent witness is `dev/dispatch_lane.py`, which neither imports.
    """
    return [line for line in text.splitlines() if _substantive(line)]


def _scope_derivation_report(checkout: Path, owns: list[str]) -> str:
    """Report tests the gate derives from existing, non-inert owned files."""
    resolved = tuple(path for path in owns if (checkout / path).is_file())
    if not resolved:
        raise BriefFault(
            f"scope derivation FAULT: resolved 0 existing files from "
            f"{len(owns)} Lane-owns entrie(s); check comma separation and path "
            "spelling. Lanes creating only new files must also name an existing "
            "owned file."
        )
    changed = tuple(
        path for path in resolved if not land_lane._is_inert_doc(path)
    )
    if not changed:
        return (
            f"scope derivation NOT CHECKED: resolved {len(resolved)} existing "
            "Lane-owns file(s), all inert documentation; doc-only lane declared "
            "explicitly by naming its documentation, so there is no gate diff"
        )

    named = tuple(
        sorted(set(filter(None, (land_lane._derived_test(path) for path in changed))))
    )
    modules = tuple(
        filter(None, (land_lane._dotted_module(path) for path in changed))
    )
    imported = land_lane._import_derived(checkout, modules)
    mapped, mapped_dirs = land_lane._map_derived(changed)
    derived = tuple(sorted(set(named) | set(imported) | set(mapped)))
    existing = tuple(path for path in derived if (checkout / path).is_file())
    authored = land_lane._named_files(owns)
    covered = tuple(path for path in existing if path in authored)
    omitted = tuple(path for path in existing if path not in authored)
    by_rule = f"name={len(named)} import={len(imported)} map={len(mapped)}"
    if not existing:
        raise BriefFault(
            f"scope derivation FAULT: selected 0 existing test(s) from "
            f"{len(changed)} existing non-inert Lane-owns file(s) by "
            f"{len(land_lane.DERIVATION_RULES)} rules [{by_rule}] — an empty "
            "selection is indistinguishable from broken derivation"
        )
    omission = (
        f"{len(omitted)} omitted: {' '.join(omitted)}"
        if omitted else "0 omitted"
    )
    dirs = f"; matched dirs: {' '.join(mapped_dirs)}" if mapped_dirs else ""
    return (
        f"scope derivation REPORT: selected {len(existing)} existing test(s) "
        f"from {len(changed)} existing non-inert Lane-owns file(s) by "
        f"{len(land_lane.DERIVATION_RULES)} rules [{by_rule}]; authored "
        f"Lane-owns covered {len(covered)} of {len(existing)}; {omission}{dirs}. "
        "This is a report, not an edit grant: the coordinator decides whether "
        "an imported test is genuinely in the change's blast radius."
    )


def _base_scope_derivation_report(
    checkout: Path, base_sha: str, owns: list[str]
) -> str:
    """Run the gate's derivation over materialized bytes from the lane base."""
    try:
        listing = subprocess.run(
            ["git", "-C", str(checkout), "ls-tree", "-r", "--name-only", "-z", base_sha],
            capture_output=True, check=False,
        )
    except OSError as exc:
        raise BriefFault(f"scope derivation FAULT: could not run git: {exc}") from exc
    if listing.returncode:
        detail = listing.stderr.decode(errors="replace").strip()
        raise BriefFault(
            f"scope derivation FAULT: could not read base tree {base_sha}: "
            f"{detail or f'git exited {listing.returncode}'}"
        )
    tracked = {
        path.decode(errors="surrogateescape")
        for path in listing.stdout.split(b"\0") if path
    }
    materialize = {
        path for path in tracked
        if (path.startswith("test_") and "/" not in path and path.endswith(".py"))
        or path in owns
    }
    with tempfile.TemporaryDirectory(prefix="brief-base-scope-") as temp_dir:
        base = Path(temp_dir)
        for path in materialize:
            target = Path(path)
            if target.is_absolute() or ".." in target.parts:
                raise BriefFault(f"scope derivation FAULT: unsafe base-tree path {path!r}")
            content = subprocess.run(
                ["git", "-C", str(checkout), "show", f"{base_sha}:{path}"],
                capture_output=True, check=False,
            )
            if content.returncode:
                detail = content.stderr.decode(errors="replace").strip()
                raise BriefFault(
                    f"scope derivation FAULT: could not materialize {path} from "
                    f"base {base_sha}: {detail or f'git exited {content.returncode}'}"
                )
            destination = base / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content.stdout)
        return _scope_derivation_report(base, owns)


def _tool_invocations(core: str) -> list[tuple[str, str]]:
    """Find command-shaped tool invocations, not quoted or fenced examples."""
    found: list[tuple[str, str]] = []
    in_fence = False
    fence_char = ""
    fence_len = 0
    for line in core.splitlines():
        if in_fence:
            if re.match(
                rf"^ {{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*$", line
            ):
                in_fence = False
            continue
        opened = _FENCE_OPEN.match(line)
        if opened:
            in_fence = True
            fence_char = opened.group(2)[0]
            fence_len = len(opened.group(2))
            continue
        searchable = _QUOTED_PROSE.sub("", line)
        found.extend(
            (match.group("path"), match.group("verb"))
            for match in _TOOL_INVOCATION.finditer(searchable)
        )
    return found


def _master_tool_path(named_path: str) -> str:
    """Map a brief spelling to the repository path whose master bytes matter."""
    marker = "/ud-dreamwork/"
    if marker in named_path:
        return named_path.split(marker, 1)[1]
    if named_path.startswith("dev/"):
        return named_path
    return f"dev/{named_path}"


def _derive_master_verbs(named_path: str) -> tuple[set[str] | None, str | None]:
    """Derive verbs by executing master's real bytes from a real sibling file."""
    repo_path = _master_tool_path(named_path)
    try:
        source = _git("show", f"master:{repo_path}")
    except BriefFault:
        return None, None

    target_dir = ROOT / Path(repo_path).parent
    temp_path: Path | None = None
    try:
        # Master is deliberate: the coordinator's working tree is exactly where
        # an unlanded verb can exist and mislead an authored lane brief.  A real
        # sibling file preserves __file__ and imports; /dev/fd process
        # substitution detaches both from their repository anchor.
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target_dir,
            prefix=".brief-master-", suffix=".py", delete=False,
        ) as materialized:
            materialized.write(source)
            temp_path = Path(materialized.name)

        try:
            unknown = subprocess.run(
                [sys.executable, str(temp_path), "brief-validator-unknown-verb", "--no-create"],
                cwd=ROOT, capture_output=True, text=True, check=False, timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None, None
        choice_match = _ARGPARSE_CHOICES.search(unknown.stderr)
        if choice_match:
            verbs = {
                token.strip().strip("'\"")
                for token in choice_match.group("choices").split(",")
            }
            return verbs, "argparse choices"

        try:
            help_run = subprocess.run(
                [sys.executable, str(temp_path), "--help"], cwd=ROOT,
                capture_output=True, text=True, check=False, timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None, None
        help_text = help_run.stdout + help_run.stderr
        marker = help_text.find("Subcommands:")
        if help_run.returncode == 0 and marker >= 0:
            verbs = {
                match.group("verb")
                for match in _DOCUMENTED_SUBCOMMANDS.finditer(help_text[marker:])
            }
            if verbs:
                return verbs, "documented subcommands"
        return None, None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _validate_tool_invocations(core: str) -> str:
    """Validate what is derivable and name what was not checked."""
    invocations = _tool_invocations(core)
    cache: dict[str, tuple[set[str] | None, str | None]] = {}
    checked = 0
    unresolved: list[str] = []
    techniques: dict[str, list[str]] = {}
    invalid: list[tuple[str, str]] = []
    for named_path, verb in invocations:
        repo_path = _master_tool_path(named_path)
        if repo_path not in cache:
            cache[repo_path] = _derive_master_verbs(named_path)
        verbs, technique = cache[repo_path]
        if verbs is None:
            unresolved.append(named_path)
            continue
        checked += 1
        techniques.setdefault(technique or "unknown", []).append(named_path)
        if verb not in verbs:
            invalid.append((named_path, verb))

    summary = (
        f"examined {len(invocations)} invocation(s), {checked} derivable, "
        f"{len(unresolved)} not derivable; the {len(unresolved)} were NOT CHECKED"
    )
    if invalid:
        named_path, verb = invalid[0]
        raise BriefFault(
            f"tool verb check ERROR: {named_path} has no verb {verb!r} on master — {summary}"
        )
    if unresolved:
        detail = ", ".join(dict.fromkeys(unresolved))
        return f"tool verb check NOT CHECKED: {summary}; not derivable: {detail}"
    resolved = "; ".join(
        f"{technique}: {', '.join(dict.fromkeys(paths))}"
        for technique, paths in techniques.items()
    )
    suffix = f"; {resolved}" if resolved else ""
    return f"tool verb check OK: {summary}{suffix}"


def _quantity_verification_report(core: str) -> str:
    """Report prose integers lacking adjacent commands in verification blocks.

    This is intentionally a syntactic completeness report, not a truth check.
    A command is adjacent when it shares the quantity's line or is the previous
    or next non-blank line. Requiring that local relationship prevents one
    unrelated command elsewhere in a long verification section from lending
    borrowed coverage to every quantity in the core. Whether the command can
    actually produce the number is not statically knowable and is stated in
    every non-empty report.
    """
    lines = core.splitlines()
    verification_lines: set[int] = set()
    command_lines: set[int] = set()
    prose: list[tuple[int, str]] = []
    verification_section = False
    in_fence = False
    fence_char = ""
    fence_len = 0

    def mask_code(match: re.Match[str]) -> str:
        return "".join("\n" if char == "\n" else " " for char in match.group())

    prose_lines = _INLINE_CODE.sub(mask_code, core).splitlines()
    inline_command_lines = {
        core.count("\n", 0, match.start())
        for match in _INLINE_CODE.finditer(core)
        if _COMMANDISH.search(match.group("body"))
    }

    for index, line in enumerate(lines):
        if in_fence:
            if re.match(
                rf"^ {{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*$", line
            ):
                in_fence = False
            elif verification_section and line.strip():
                command_lines.add(index)
                verification_lines.add(index)
            continue

        opened = _FENCE_OPEN.match(line)
        if opened:
            in_fence = True
            fence_char = opened.group(2)[0]
            fence_len = len(opened.group(2))
            if verification_section:
                verification_lines.add(index)
            continue

        if _is_atx_heading(line):
            verification_section = _VERIFICATION_CUE.search(line) is not None
        elif _VERIFICATION_CUE.search(prose_lines[index]):
            # A bold or ordinary imperative such as "Re-derive these counts"
            # is also a verification-block opener; the next heading closes it.
            verification_section = True

        if verification_section:
            verification_lines.add(index)
            if line.startswith(("    ", "\t")) or index in inline_command_lines:
                command_lines.add(index)

        if line.startswith(("    ", "\t")) or re.match(r"^\s*>", line):
            continue
        prose.append((
            index,
            _DIRECTION_NUMBER.sub("", _QUOTED_PROSE.sub("", prose_lines[index])),
        ))

    substantive = [index for index, line in enumerate(lines) if line.strip()]
    ordinal = {line_no: position for position, line_no in enumerate(substantive)}
    quantities: list[tuple[int, str, bool]] = []
    for line_no, line in prose:
        for match in _ASSERTED_QUANTITY.finditer(line):
            unit = match.group("unit")
            label = match.group("number")
            if unit and unit.lower() not in _UNIT_STOPWORDS:
                label += f" {unit}"
            covered = line_no in verification_lines and any(
                abs(ordinal[line_no] - ordinal[command]) <= 1
                for command in command_lines
            )
            quantities.append((line_no + 1, label, covered))

    covered = sum(is_covered for _, _, is_covered in quantities)
    if not quantities:
        return (
            "quantity verification NOT CHECKED: found 0 asserted quantities in "
            "prose; adjacent re-derivation commands covered 0 of 0. There is no "
            "quantity population, so this is not an all-verified result."
        )
    uncovered = [
        f"line {line_no} {label!r}"
        for line_no, label, is_covered in quantities if not is_covered
    ]
    gap = (
        f"{len(uncovered)} uncovered: {', '.join(uncovered)}"
        if uncovered else "0 uncovered"
    )
    return (
        f"quantity verification REPORT: found {len(quantities)} asserted "
        f"quantities in prose; adjacent re-derivation commands in verification "
        f"blocks covered {covered} of {len(quantities)}; {gap}. This is a "
        "syntactic completeness report, not proof: it does not verify that a "
        "command can produce the claimed quantity."
    )


def _blocking_number_report(core: str) -> str:
    """Report blocking-number claims without judging whether they are invariant."""
    lines = core.splitlines()
    prose_lines = _INLINE_CODE.sub(
        lambda match: "".join("\n" if char == "\n" else " " for char in match.group()),
        core,
    ).splitlines()
    eligible: set[int] = set()
    justification_lines: set[int] = set()
    blocking_section = False
    section_justified = False
    in_fence = False
    fence_char = ""
    fence_len = 0

    for index, line in enumerate(prose_lines):
        if in_fence:
            if re.match(
                rf"^ {{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*$", line
            ):
                in_fence = False
            continue
        opened = _FENCE_OPEN.match(line)
        if opened:
            in_fence = True
            fence_char = opened.group(2)[0]
            fence_len = len(opened.group(2))
            continue

        prose = _DIRECTION_NUMBER.sub("", line)
        if _is_atx_heading(prose):
            blocking_section = (
                _BLOCKING_SECTION_CUE.search(prose) is not None
                and _NONBLOCKING_CUE.search(prose) is None
            )
            section_justified = (
                blocking_section
                and _INVARIANCE_JUSTIFICATION_CUE.search(prose) is not None
            )
        elif _BLOCKING_SECTION_CUE.search(prose) and re.match(
            r"^\s*(?:[-*+]\s+)?\*\*", prose
        ):
            # House briefs also use a bold prose label rather than an ATX head:
            # ``**BLOCKING — these three are invariant:**``.
            blocking_section = True
            section_justified = (
                _INVARIANCE_JUSTIFICATION_CUE.search(prose) is not None
            )
        if _NONBLOCKING_CUE.search(prose):
            blocking_section = False
            section_justified = False
        elif prose.strip() and (blocking_section or _BLOCKING_STOP_CUE.search(prose)):
            eligible.add(index)
            if section_justified:
                justification_lines.add(index)
        if _INVARIANCE_JUSTIFICATION_CUE.search(prose):
            justification_lines.add(index)

    substantive = [index for index, line in enumerate(lines) if line.strip()]
    ordinal = {line_no: position for position, line_no in enumerate(substantive)}
    blocking: list[tuple[int, str, bool]] = []
    for line_no in sorted(eligible):
        prose = _DIRECTION_NUMBER.sub("", prose_lines[line_no])
        for match in _ASSERTED_QUANTITY.finditer(prose):
            unit = match.group("unit")
            label = match.group("number")
            if unit and unit.lower() not in _UNIT_STOPWORDS:
                label += f" {unit}"
            justified = any(
                abs(ordinal[line_no] - ordinal[claim]) <= 1
                for claim in justification_lines
            )
            blocking.append((line_no + 1, label, justified))

    justified_count = sum(justified for _, _, justified in blocking)
    if not blocking:
        return (
            "blocking-number invariance NOT CHECKED: found 0 blocking numbers "
            "presented in prose; invariance justification claims covered 0 of 0. "
            "State: no blocking numbers presented, so this is not an "
            "all-justified result."
        )
    details = "; ".join(
        f"line {line_no} {label!r} justification claim "
        f"{'PRESENT' if justified else 'MISSING'}"
        for line_no, label, justified in blocking
    )
    state = (
        "presented and all carry justification claims"
        if justified_count == len(blocking)
        else "presented with unjustified blocking numbers"
    )
    return (
        f"blocking-number invariance REPORT: found {len(blocking)} blocking "
        f"number(s) presented in prose; invariance justification claims covered "
        f"{justified_count} of {len(blocking)}. State: {state}. {details}. "
        "Justification correctness is NOT CHECKED and requires human judgment: "
        "which of these can the act of dispatching change?"
    )


def _citation_title(task: int, ledger: Path) -> str | None:
    """Resolve one cited task id to its ledger title; ``None`` means absent."""
    try:
        return str(task_record(task, ledger)["title"]).strip()
    except BriefFault as exc:
        if str(exc).startswith(f"#{task} not found in "):
            return None
        raise


# A Markdown list marker (CommonMark §5.1/§5.2): bullet or ordered, with the
# whitespace that separates it from its content.  The content column of the
# item is where its text begins (lead + marker + gap), and that — not column
# zero — is the baseline an indented code block is measured from (#1213 r2).
_LIST_MARKER = re.compile(r"^(?P<lead> *)(?P<mark>[-*+]|[0-9]+[.)])(?P<gap>[ \t]+)")


def _expand_tabs(text: str, start: int = 0) -> int:
    """CommonMark column advance over ``text`` from column ``start``.

    A space (or any non-TAB glyph) adds one; a TAB jumps to the next multiple
    of 4 measured from the CURRENT column — not four flat spaces.  This is the
    single tab rule shared by the list-marker measurement and the code-block
    test (``_expanded_indent``), so a TAB in the marker gap and a TAB in a
    code block's indent are scored by one yardstick and can never disagree
    (#1213 r3: round 2 scored the gap in byte lengths while the indent test
    expanded tabs, and the gap won — silently exempting list prose).
    """
    col = start
    for char in text:
        if char == "\t":
            col = 4 * (col // 4 + 1)
        else:
            col += 1
    return col


def _expanded_indent(line: str) -> int:
    """Leading indent in CommonMark columns — a TAB advances to a multiple of 4.

    A naive ``len(line) - len(line.lstrip(" "))`` counts only spaces, so a
    tab-indented code block reads as indent 0 and the citation check skips
    nothing CommonMark would (#1213 r2: tabs).  The rule itself lives in
    ``_expand_tabs`` and is shared with the marker measurement (#1213 r3).
    """
    lead = ""
    for char in line:
        if char == " " or char == "\t":
            lead += char
        else:
            break
    return _expand_tabs(lead)


# A fence opener with no cap on leading spaces: whether a leading fence is a
# REAL fence is decided against the enclosing list context (up to three spaces
# past the item's content column), so a block nested inside a list item still
# opens and closes (#1213 r2: list-fence gap).  ``_FENCE_OPEN`` (capped at three
# absolute spaces) stays the rule for the top-level-only walkers that share it.
_FENCE_OPEN_ANY = re.compile(r"^(?P<lead> *)(?P<fence>`{3,}|~{3,})")


def _citation_prose_lines(core: str):
    """Yield ``(line_no, line)`` for authored prose; skip genuine code blocks.

    Code blocks are quoted material — a pasted refusal, captured output — not
    live citations, so a brief about citation defects can show one (#1213).
    Two things make the skip correct rather than blanket:

    * it is RELATIVE to the enclosing list item.  CommonMark measures an
      indented code block from the item's CONTENT column, not from column zero,
      so four-space-indented text inside a list item whose text begins at
      column 2 or 3 is list content (checked), and only content-column + 4 is a
      code block.  Round 1 used an absolute four-column rule, which exempted
      most of a typical brief — briefs are almost entirely nested bullets — and
      turned a check that exists to refuse bad citations into one that passes
      them quietly (#1213 r2).
    * the blank-line precondition is kept: an indented code block cannot
      interrupt a paragraph, so a four-space continuation with no preceding
      blank line stays prose and stays checked.

    Inline code is NOT exempt here; only fenced and indented blocks are skipped.
    """
    list_stack: list[int] = []          # content columns of open list items
    in_indented = False
    code_indent = 4                      # meaningful only while in_indented
    in_fence = False
    fence_char = ""
    fence_len = 0
    fence_col = 0                        # content column the fence opened at
    blank_before = True

    for line_no, line in enumerate(core.splitlines(), 1):
        if in_fence:
            # The closing fence may sit at the same content column, up to three
            # past it (CommonMark §4.5); the block lives inside the list item,
            # so the close is measured from ``fence_col`` too.
            lead = _expanded_indent(line)
            close = _FENCE_OPEN_ANY.match(line)
            if (close is not None
                    and close.group("fence")[0] == fence_char
                    and len(close.group("fence")) >= fence_len
                    and fence_col <= lead <= fence_col + 3
                    and not line[lead + len(close.group("fence")):].strip()):
                in_fence = False
            continue

        leading = _expanded_indent(line)

        if in_indented:
            if not line.strip():
                blank_before = True
                continue
            if leading >= code_indent:
                continue
            in_indented = False            # block closed — re-classify the line

        ci = list_stack[-1] if list_stack else 0
        marker = _LIST_MARKER.match(line)
        if marker is not None:
            lead = marker.group("lead")
            mark_lead = _expand_tabs(lead)
            while list_stack and list_stack[-1] > mark_lead:
                list_stack.pop()
            # The content column is where the item's text begins — lead, marker
            # and gap scored in CommonMark columns, so a TAB in the gap (a
            # natural way to indent list prose) lands at the same column the
            # code-block test measures from.  Byte-length ``len()`` here would
            # disagree with ``_expanded_indent`` and silently exempt the very
            # list prose this check exists to protect (#1213 r3).
            content_col = _expand_tabs(
                lead + marker.group("mark") + marker.group("gap"))
            if not list_stack or content_col > list_stack[-1]:
                list_stack.append(content_col)
            blank_before = False
            yield line_no, line
            continue

        if not line.strip():
            blank_before = True
            continue

        # A non-marker line after a blank that dedents below the open item
        # closes that item (and anything deeper); a lazy continuation, with no
        # blank before it, does not, and leaves the content column untouched.
        if blank_before and leading < ci:
            while list_stack and list_stack[-1] > leading:
                list_stack.pop()
            ci = list_stack[-1] if list_stack else 0

        rel = leading - ci
        opened = _FENCE_OPEN_ANY.match(line)
        if opened is not None and 0 <= rel <= 3:
            in_fence = True
            fence_char = opened.group("fence")[0]
            fence_len = len(opened.group("fence"))
            fence_col = ci
            blank_before = False
            continue

        if blank_before and leading >= ci + 4:
            in_indented = True
            code_indent = ci + 4
            blank_before = False
            continue

        blank_before = False
        yield line_no, line


def _validate_file_line_citations(core: str, checkout: Path, sha: str) -> None:
    """Refuse repo ``file:line`` citations absent at the generation SHA.

    This checks only authored prose.  Fenced and indented code blocks are
    specimens or captured output, not active citations; treating their
    historical coordinates as current claims would refuse correct briefs — a
    brief that quotes a refusal message cannot show the coordinate it warns
    about (#1213).  Inline code is NOT exempt: a live citation is normally
    written in backticks, so exempting it would disable the check outright.
    Semantic accuracy is outside this check: a line can resolve and still
    support the wrong conclusion.

    The block classification is delegated to ``_citation_prose_lines``: it
    measures an indented code block from the enclosing list item's content
    column, not from column zero, so nested bullets and continuation paragraphs
    stay checked while only genuine code blocks are skipped (#1213 r2).
    """
    citations: list[tuple[int, str, int, int]] = []
    for line_no, line in _citation_prose_lines(core):
        prose = re.sub(r"https?://\S+", " ", line)
        for match in _FILE_LINE_CITATION.finditer(prose):
            first = int(match.group("first"))
            last = int(match.group("last") or first)
            citations.append((line_no, match.group("path"), first, last))

    faults: list[str] = []
    blobs: dict[str, list[str] | None] = {}
    for line_no, path, first, last in citations:
        if path not in blobs:
            result = subprocess.run(
                ["git", "-C", str(checkout), "show", f"{sha}:{path}"],
                capture_output=True,
                text=True,
                check=False,
            )
            blobs[path] = result.stdout.splitlines() if result.returncode == 0 else None
        source = blobs[path]
        if source is None:
            faults.append(f"core line {line_no} `{path}:{first}` (path absent)")
        elif last < first:
            faults.append(
                f"core line {line_no} `{path}:{first}-{last}` "
                "(range ends before it starts)"
            )
        elif last > len(source):
            rendered = f"{path}:{first}" if first == last else f"{path}:{first}-{last}"
            faults.append(
                f"core line {line_no} `{rendered}` "
                f"(line exceeds file's {len(source)} lines)"
            )

    if faults:
        raise BriefFault(
            f"file:line citation does not resolve at generation sha {sha}: "
            + "; ".join(faults)
            + ". Cite the repo-relative path and a line present in that exact tree; "
            "this proves resolution only, not that the line supports the claim."
        )


def _validate_lesson_citation_count(core: str, checkout: Path, sha: str) -> None:
    """Refuse a stale claim about lint's numeric lesson-citation WARN rows.

    The check deliberately recognises only the observed, mechanically
    derivable population. Fenced and quoted text is historical evidence, not a
    live claim. A correct count passes; unrelated quantities are untouched.
    """
    claims: list[tuple[int, int]] = []
    in_fence = False
    fence_char = ""
    fence_len = 0
    for line_no, line in enumerate(core.splitlines(), 1):
        if in_fence:
            if re.match(
                rf"^ {{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*$", line
            ):
                in_fence = False
            continue
        opened = _FENCE_OPEN.match(line)
        if opened:
            in_fence = True
            fence_char = opened.group(2)[0]
            fence_len = len(opened.group(2))
            continue
        prose = _QUOTED_PROSE.sub(" ", line)
        for match in _LESSON_CITATION_COUNT_CLAIM.finditer(prose):
            token = match.group("count").lower()
            claims.append((line_no, int(token) if token.isdigit() else _COUNT_WORDS[token]))

    if not claims:
        return

    def git_read(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(checkout), *args],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or f"git exited {result.returncode}"
            raise BriefFault(
                "could not derive `lesson citations` rows at generation sha "
                f"{sha}: {detail}"
            )
        return result.stdout

    lesson_lines = git_read("show", f"{sha}:.dreamwork/lessons.md").splitlines()
    paths = git_read(
        "ls-tree", "-r", "--name-only", sha, "--",
        ".dreamwork/lessons.md", "briefs",
    ).splitlines()
    findings = 0
    for path in paths:
        if path != ".dreamwork/lessons.md" and not (
            path.startswith("briefs/") and path.endswith(".md")
        ):
            continue
        for match in _LESSON_CITATION.finditer(git_read("show", f"{sha}:{path}")):
            target = int(match.group(1))
            actual = (
                lesson_lines[target - 1]
                if 1 <= target <= len(lesson_lines)
                else None
            )
            if actual is None or not actual.startswith("- **"):
                findings += 1

    mismatches = [
        f"core line {line_no} claims {claimed} known `lesson citations` row(s)"
        for line_no, claimed in claims
        if claimed != findings
    ]
    if mismatches:
        raise BriefFault(
            "; ".join(mismatches)
            + f", but generation sha {sha} has {findings}. Re-derive the row set "
            "at the brief base; do not replace this with a fresher constant."
        )


def _citation_authority_report(core: str, ledger: Path) -> str:
    """Put each explicit citation gloss beside its ledger title for human review."""
    prose_lines = _INLINE_CODE.sub(
        lambda match: "".join("\n" if char == "\n" else " " for char in match.group()),
        core,
    ).splitlines()
    citations: list[tuple[int, int, str]] = []
    in_fence = False
    fence_char = ""
    fence_len = 0
    for line_no, line in enumerate(prose_lines, 1):
        if in_fence:
            if re.match(
                rf"^ {{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*$", line
            ):
                in_fence = False
            continue
        opened = _FENCE_OPEN.match(line)
        if opened:
            in_fence = True
            fence_char = opened.group(2)[0]
            fence_len = len(opened.group(2))
            continue
        prose = re.sub(r"https?://\S+", " ", line)
        for match in _GLOSSED_TASK_CITATION.finditer(prose):
            citations.append((
                line_no,
                int(match.group("task")),
                match.group("gloss").strip().strip("*_ "),
            ))

    if not citations:
        return (
            "citation authority NOT CHECKED: found 0 task citations carrying an "
            "author gloss; resolved 0 and found 0 unresolvable. There is no "
            "citation population, so this is not an all-verified result."
        )

    # P1 (#1028, citation-path sibling): an unreadable/empty ledger must NOT
    # refuse the dispatch.  This report runs FIRST in validate_core, before the
    # task-state report, so an unfixed unreadable-ledger path here refuses the
    # dispatch even though the state-path P1 is fixed — a fix at the named site
    # only, while the sibling re-raised, made the refusal survive unchanged.  A
    # per-task "not found" returns None inside _citation_title and is fine; a
    # ledger-level failure (could not read / holds no entries) re-raises and is
    # caught here as NOT CHECKED — report-only, exactly when the tool knows
    # least (#136).
    try:
        _citation_title(citations[0][1], ledger)
    except BriefFault as exc:
        return (
            f"citation authority NOT CHECKED: found {len(citations)} task "
            f"citation(s) carrying an author gloss but the ledger could not "
            f"be read ({exc}); 0 resolved; 0 unresolvable. There IS a "
            "citation population, so this is not an all-verified result; the "
            "citations were not checked."
        )

    details: list[str] = []
    resolved = 0
    for line_no, task, gloss in citations:
        title = _citation_title(task, ledger)
        if title is None:
            details.append(
                f"line {line_no} #{task} UNRESOLVABLE: author gloss {gloss!r}; "
                "no ledger title"
            )
        else:
            resolved += 1
            details.append(
                f"line {line_no} #{task} RESOLVED: author gloss {gloss!r}; "
                f"ledger title {title!r}"
            )
    return (
        f"citation authority REPORT: found {len(citations)} task citation(s) "
        f"carrying an author gloss; resolved {resolved}; unresolvable "
        f"{len(citations) - resolved}. Semantic agreement is NOT CHECKED and "
        f"requires human judgment. " + "; ".join(details)
    )


def _command_existence_report(core: str) -> str:
    """Report ``just <recipe>`` claims confirmed against ``just --dry-run``.

    A brief that names ``just build`` when the recipe is ``just build-client``
    is a false premise that looks verified because ``build-client`` exists
    nearby and lends it credibility (#630/#1028).  This binds to the SPECIFIC
    recipe named in code context — inline code or fenced blocks — and probes
    each with ``just --dry-run``, which resolves the recipe rather than
    grepping a word in ``just --list`` (the direction-2 trap: a commented-out
    recipe or a variable assignment matches a list grep but not a dry-run).

    REPORT, not REFUSE (#994): a recipe that exists but requires positional
    arguments passes ``just --dry-run`` with a usage error rather than a
    "does not contain recipe" error — that is an existence confirmation, not
    a finding.  Only the "does not contain recipe" message is a finding.
    """
    claims: list[tuple[int, str]] = []  # (line_no, recipe)
    lines = core.splitlines()
    in_fence = False
    fence_char = ""
    fence_len = 0
    for index, line in enumerate(lines):
        if in_fence:
            if re.match(
                rf"^ {{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*$", line
            ):
                in_fence = False
            else:
                for match in _JUST_RECIPE.finditer(line):
                    claims.append((index + 1, match.group("recipe")))
            continue
        opened = _FENCE_OPEN.match(line)
        if opened:
            in_fence = True
            fence_char = opened.group(2)[0]
            fence_len = len(opened.group(2))
            continue
        # Inline code: `` `just build` `` is a claim, not a discussion.
        for match in _INLINE_CODE.finditer(line):
            for recipe_match in _JUST_RECIPE.finditer(match.group("body")):
                claims.append((index + 1, recipe_match.group("recipe")))

    if not claims:
        return (
            "command existence NOT CHECKED: found 0 `just <recipe>` claim(s) "
            "in code context; resolved 0; 0 MISSING. There is no "
            "command-claim population, so this is not an all-verified result."
        )

    recipes = sorted({recipe for _, recipe in claims})
    missing: list[str] = []
    checked = 0
    not_checked: list[str] = []  # recipes we could not classify
    try:
        for recipe in recipes:
            result = subprocess.run(
                ["just", "--dry-run", recipe],
                cwd=ROOT, capture_output=True, text=True, check=False, timeout=10,
            )
            if result.returncode == 0:
                checked += 1
            elif "does not contain recipe" in result.stderr:
                missing.append(recipe)
            elif "positional argument" in result.stderr:
                # A usage error naming positional arguments is an existence
                # confirmation: the recipe resolved, it just needs args.
                # ONLY this error implies existence — a malformed or unreadable
                # Justfile, or any other parser error, does NOT, and blessing
                # it would silently certify every command claim in the brief
                # (#1028). Everything else is NOT CHECKED.
                checked += 1
            else:
                not_checked.append(recipe)
    except (OSError, subprocess.TimeoutExpired):
        return (
            f"command existence NOT CHECKED: found {len(claims)} "
            f"`just <recipe>` claim(s) ({len(recipes)} distinct) but "
            "`just --dry-run` could not run. There IS a command-claim "
            "population, so this is not an all-verified result; the claims "
            "were not checked."
        )

    details = [
        f"`just {recipe}` (line(s) "
        f"{', '.join(str(ln) for ln in sorted({l for l, r in claims if r == recipe}))}) "
        f"MISSING: recipe does not exist"
        for recipe in missing
    ]
    findings = (
        f"{len(missing)} MISSING: {'; '.join(details)}"
        if missing else "0 MISSING"
    )
    if not_checked:
        findings += (
            f"; {len(not_checked)} NOT CHECKED: "
            f"{', '.join(not_checked)} (just --dry-run returned an error that "
            "neither confirms nor denies the recipe — e.g. a malformed Justfile)"
        )
    return (
        f"command existence REPORT: found {len(claims)} `just <recipe>` "
        f"claim(s) in code context ({len(recipes)} distinct recipe(s)); "
        f"resolved {checked} of {len(recipes)}; {findings}. Probed with "
        "`just --dry-run`, which resolves the recipe rather than grepping a "
        "word in `just --list`. This is a syntactic existence report, not "
        "proof: it does not verify that a recipe produces the claimed result."
    )


def _task_state(task: int, ledger: Path) -> str | None:
    """Resolve one task's state; ``None`` means the id is absent from the ledger."""
    try:
        return str(task_record(task, ledger)["state"]).strip()
    except BriefFault as exc:
        if str(exc).startswith(f"#{task} not found in "):
            return None
        raise


def _collect_state_claims(
    lines: list[str],
) -> tuple[dict[tuple[int, int], tuple[int, int, str, str | None]], int]:
    """Collect state-claim candidates and count ``#NNN`` citations, fence-aware.

    Single source of truth for the fence tracking and ``(line, task)`` keying
    the state-claim report and the corpus measurement scanner both depend on.
    The scanner imports this so the population it measures is the one
    production sees, instead of re-implementing the fence logic and drifting —
    the measurement copy once opened ``~~~`` fences but only closed backtick
    ones, so a claim after a closed ``~~~`` fence was hidden from the scanner
    but seen by production (#1028 Finding 3).
    """
    claims: dict[tuple[int, int], tuple[int, int, str, str | None]] = {}
    total_citations = 0
    in_fence = False
    fence_char = ""
    fence_len = 0
    for index, line in enumerate(lines):
        if in_fence:
            if re.match(
                rf"^ {{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*$", line
            ):
                in_fence = False
            continue
        opened = _FENCE_OPEN.match(line)
        if opened:
            in_fence = True
            fence_char = opened.group(2)[0]
            fence_len = len(opened.group(2))
            continue
        for match in _TASK_STATE_PREDICATE.finditer(line):
            key = (index + 1, int(match.group("task")))
            claims[key] = (index + 1, int(match.group("task")),
                           "state predicate", match.group("state"))
        for match in _TASK_WARN_OUTPUT.finditer(line):
            # Capture EVERY #NNN in the bounded WARN-row clause, not just the
            # first — "WARN rows (#630, #700)" claims both ids (#1028 P1).
            for cite in re.finditer(r"#(\d+)", match.group("clause")):
                task = int(cite.group(1))
                key = (index + 1, task)
                claims.setdefault(key, (index + 1, task, "WARN output", None))
        total_citations += len(re.findall(r"#\d+", line))
    return claims, total_citations


def _task_state_claim_report(core: str, ledger: Path) -> str:
    """Report task ids in state-claim contexts against their actual ledger state.

    A brief that says "expect a live WARN for #641" while #641 is ``landed``
    sends a lane to verify an expectation that can never hold (#1024/#1028).
    This binds to the SPECIFIC claim — a #NNN that is the grammatical subject
    of a state predicate ("#641 is live") or inside a WARN-row expected-output
    claim ("WARN rows (#641)") — not to every citation (the direction-2 trap:
    flagging every #NNN drowns the real finding).  The prior lane also matched
    a generic ``expect|fixture ... #NNN`` regex; measured at 66.7% false
    positives across 77 cores it was DROPPED (#1028).

    REPORT, not REFUSE (#994/#136): an unreadable or empty ledger is reported
    as NOT CHECKED, never allowed to escape and refuse the dispatch — the tool
    knows least exactly then.  Claims are keyed by (line, task) so a #NNN on
    one line matched by more than one regex counts once: deriving "other
    citations" as ``total - len(claims)`` went negative when one line matched
    twice (#1028 P2), and a count that can go below zero is a count derived
    twice.
    """
    lines = core.splitlines()
    claims, total_citations = _collect_state_claims(lines)

    claim_list = list(claims.values())

    if not claim_list:
        return (
            f"task-state claim NOT CHECKED: found 0 task-state claim(s); "
            f"resolved 0; 0 mismatched. {total_citations} other #NNN "
            "citation(s) without state-claim language were NOT CHECKED. "
            "There is no state-claim population, so this is not an "
            "all-verified result."
        )

    # P1 (#1028): an unreadable/empty ledger must NOT refuse the dispatch.  A
    # per-task "not found" returns None inside _task_state and is fine; a
    # ledger-level failure (could not read / holds no entries) re-raises and is
    # caught here as NOT CHECKED — report-only, exactly when the tool knows
    # least (#136).
    try:
        _task_state(claim_list[0][1], ledger)
    except BriefFault as exc:
        return (
            f"task-state claim NOT CHECKED: found {len(claim_list)} "
            f"task-state claim(s) but the ledger could not be read ({exc}); "
            "0 resolved; 0 mismatched. There IS a state-claim population, so "
            "this is not an all-verified result; the claims were not checked."
        )

    state_cache: dict[int, str | None] = {}
    details: list[str] = []
    resolved = 0
    mismatched = 0
    unresolvable = 0
    for line_no, task, context, claimed_word in claim_list:
        if task not in state_cache:
            state_cache[task] = _task_state(task, ledger)
        actual = state_cache[task]
        if actual is None:
            unresolvable += 1
            details.append(
                f"line {line_no} #{task} UNRESOLVABLE in {context!r}: "
                "no ledger entry"
            )
            continue
        resolved += 1
        if claimed_word is not None:
            implied = (
                "open" if re.fullmatch(_OPEN_IMPLYING, claimed_word, re.I)
                else "landed"
            )
        else:
            implied = "open"  # WARN-output claims imply an active task
        if actual != implied:
            mismatched += 1
            details.append(
                f"line {line_no} #{task} MISMATCH in {context!r}: "
                f"claim implies {implied!r} ({claimed_word or context}); "
                f"actual state {actual!r}"
            )
        else:
            details.append(
                f"line {line_no} #{task} MATCH in {context!r}: "
                f"actual state {actual!r}"
            )

    # P2 (#1028): derive "other citations" once, from distinct (line, task)
    # claims, so it can never go negative.  Each claim key implies at least one
    # #NNN occurrence on its line, so len(claims) <= total_citations always.
    unclassified = total_citations - len(claims)
    return (
        f"task-state claim REPORT: found {len(claim_list)} task-state claim(s); "
        f"resolved {resolved}; mismatched {mismatched}; unresolvable "
        f"{unresolvable}. {unclassified} other #NNN citation(s) without "
        "state-claim language were NOT CHECKED (direction-2: flagging every "
        "citation drowns the finding). " + "; ".join(details) + " State "
        "consistency is REPORTED, not certified: a claim's implied state is "
        "a heuristic and requires human judgment."
    )


def validate_core(core: str, ledger: Path | None = None) -> int:
    """Refuse an authored core that is absent, placeholder, or has no traps section.

    Each refusal names a mode this function can actually detect.  Tool verbs
    are checked against master when their runtime surface is derivable; an
    underivable surface is reported as NOT CHECKED, never collapsed into pass
    or fail.  This catches only a wrong tool version, not wrong numbers,
    environments, argument shapes, or interpreter paths.  On the happy path it
    returns how many ATX sections the walk examined, so a caller can print the
    denominator on every path (#868: a run that examined zero sections must not
    read the same as one that examined forty and found them all written).
    """
    if not core.strip():
        raise BriefFault(
            "the authored core is empty — the frame is generated but the defect, "
            "its measurements, the fix shape and the direction-2 candidates are "
            "the brief; supply them with --core"
        )

    reserved = _RESERVED_FIELD.search(core)
    if reserved is not None:
        field = reserved.group(1)
        raise BriefFault(
            f"the authored core declares {field}:, which this tool generates — "
            f"two {field}: lines leave dispatch_lane unable to tell the instruction "
            "from the quotation; remove it from the core"
        )

    if blanket_markdown_prohibition(core):
        raise BriefFault(
            "the authored core prohibits the whole Markdown-file class while the "
            "standing contract requires .dreamwork/inbox.md and may require a "
            ".dreamwork/dreams/<date>-<time>-<slug>.md file; protect the campaign "
            "by identity instead: `Documents you must NOT edit — "
            ".dreamwork/docs/**.md, .dreamwork/lessons.md, .dreamwork/handoffs.md, "
            ".dreamwork/tasks.md, .dreamwork/questions.md, doc-map.md, DREAMWORK.md, "
            "README.md`, with .dreamwork/inbox.md and .dreamwork/dreams/ explicitly "
            "outside that prohibition"
        )

    lines = core.splitlines()
    if not any(_substantive(line) for line in lines):
        raise BriefFault(
            "the authored core has no substantive line — every line is blank, a "
            "heading, or a placeholder (TODO, <describe …>, [fill in]); a frame "
            "with a placeholder core is worse than no generated brief"
        )

    heading: str | None = None
    body_seen = False
    in_fence = False
    fence_char = ""
    fence_len = 0
    fence_opened_at = 0
    sections_seen = 0
    traps_heading_seen = False
    empties: list[tuple[str, str]] = []  # (heading line, the line that closed it)

    def closes_fence(line: str) -> bool:
        return re.match(
            rf"^ {{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*$", line
        ) is not None

    for line_no, line in enumerate(lines, 1):
        if in_fence:
            if closes_fence(line):
                in_fence = False
            # Inside a fence a line is never a heading and never structure.
            continue
        opened = _FENCE_OPEN.match(line)
        if opened:
            # A code block IS authored content under the current section.
            in_fence = True
            fence_char = opened.group(2)[0]
            fence_len = len(opened.group(2))
            fence_opened_at = line_no
            body_seen = True
            continue
        if _is_atx_heading(line):
            sections_seen += 1
            if heading is not None and not body_seen:
                empties.append((heading, line))
            heading, body_seen = line, False
            traps_heading_seen = traps_heading_seen or _is_traps_section_heading(line)
        elif _substantive(line):
            body_seen = True
    # An unterminated fence leaves the rest of the core unchecked: every line
    # after the opener was skipped, so `empties` and `sections_seen` describe
    # only the part walked before it.  Master before #947 had no fence tracking
    # and LOUDLY false-positived on quoted headings; #947 made that quiet by
    # swallowing the rest of the core, turning loud-and-wrong into quiet-and-
    # wrong (#952).  Refusing here restores the loud direction without the
    # false positive — the author closes the fence and re-runs — and names the
    # remedy (#940): the line that opened it and the closing delimiter.
    if in_fence:
        kind = "backtick" if fence_char == "`" else "tilde"
        raise BriefFault(
            f"the authored core opens a fenced code block on line "
            f"{fence_opened_at} ({fence_char * fence_len!r}) and never closes "
            f"it — every line after that was skipped, so the section walk "
            f"examined only {sections_seen} section(s) and the rest of the "
            f"core is unchecked. Close it with a line of at least "
            f"{fence_len} {kind}(s) and nothing else."
        )
    # Flush the final section: a heading left open at end-of-core.
    if heading is not None and not body_seen:
        empties.append((heading, "end of the core"))
    if empties:
        raise BriefFault(_no_body_message(empties, sections_seen))

    ledger = ledger or (main_checkout() / ".dreamwork" / "tasks.md")
    tool_report = _validate_tool_invocations(core)
    quantity_report = _quantity_verification_report(core)
    citation_report = _citation_authority_report(core, ledger)
    blocking_report = _blocking_number_report(core)
    command_report = _command_existence_report(core)
    state_report = _task_state_claim_report(core, ledger)
    if traps_heading_seen:
        print(tool_report, file=sys.stderr)
        print(quantity_report, file=sys.stderr)
        print(citation_report, file=sys.stderr)
        print(blocking_report, file=sys.stderr)
        print(command_report, file=sys.stderr)
        print(state_report, file=sys.stderr)
        return sections_seen
    # Reaching here proves `empties` came back empty (it raises above), so the
    # denominator is the one signal left that the walk ran on thin data: a core
    # that examined zero sections reads like a core that examined twelve.
    raise BriefFault(
        f"the authored core names no direction-2 construction with a body — "
        f"the section walk examined {sections_seen} section(s) before this "
        f"refusal. \"here is how a test of this could pass while the thing is "
        f"broken\" is task-specific and carries this loop's quality; 40 of the "
        f"40 most recent briefs carry one (dev/brief_corpus_stats.py)"
    )


def _no_body_message(empties: list[tuple[str, str]], sections_seen: int) -> str:
    """The 'section has no body' refusal, naming every offender and what it saw.

    #940: a refusal names what it OBSERVED, not only the condition — so each
    empty heading is paired with the line that closed it with no prose between
    (another heading, or end-of-core).  core-847b cost two launch cycles because
    the refusal stopped at the first offender, so EVERY empty section is named.
    The denominator is printed (#868): a run that examined zero sections must
    not read the same as one that examined forty and found them all written.
    """
    def closer_phrase(closer: str) -> str:
        if closer == "end of the core":
            return "end of the core"
        return f"the next heading {closer.strip()!r}"

    single = "a copied heading with nothing under it reads as a written section and is not one"
    if len(empties) == 1:
        head, closer = empties[0]
        return (
            f"the authored core section {head.strip()!r} has no body — {single}; "
            f"the line that ended it with no prose between was {closer_phrase(closer)} "
            f"(1 of {sections_seen} sections examined)"
        )
    parts = [
        f"{head.strip()!r} (closed by {closer_phrase(closer)})"
        for head, closer in empties
    ]
    return (
        f"the authored core has {len(empties)} of {sections_seen} sections with no "
        f"body — {single}. Each heading below was followed by another heading "
        f"(or end of core) with no prose between:\n  " + ";\n  ".join(parts)
    )


def frame_sections(text: str) -> list[str]:
    """The `## ` sections of the frame file, in order, as whole blocks."""
    sections: list[str] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections.append("\n".join(current).strip())
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        sections.append("\n".join(current).strip())
    return [section for section in sections if section]


def review_prompt(core: str, frame: str) -> str:
    """Concatenate authored review text with ``briefs/review-frame.md`` (#1115).

    The frame is appended verbatim as the final section, by construction — the
    receipt half (#1112, ``dispatch_lane.persist_review_prompt``) can then
    verify it landed, because the very thing that validates the frame is the
    thing that persists it.  This is the construction `#1109` named as missing:
    before it, the frame was a coordinator convention hand-concatenated per
    dispatch, and no instrument could prove it reached a reviewer.

    ``frame`` is the RAW file text (the bytes
    ``dispatch_lane.validate_review_prompt`` searches for verbatim), so it is
    appended without stripping.  Returned text is exactly what
    ``persist_review_prompt`` validates and receipts; a caller that alters it
    will be refused at persist time, not silently accepted.
    """
    core = core.strip()
    if not core:
        raise BriefFault(
            "review core is empty; no task-specific review text was supplied"
        )
    if not frame.strip():
        raise BriefFault(
            "review frame briefs/review-frame.md is empty; the assertion "
            "examined no rules"
        )
    return core + "\n\n" + frame


def _read(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise BriefFault(f"could not read {label} {path}: {exc}") from exc


def build(task: int, branch: str, owns: list[str], core: str, *,
          ledger: Path | None = None, frame_path: Path = FRAME_PATH,
          boilerplate_path: Path = BOILERPLATE_PATH,
          prepared_worktree: Path | None = None,
          prepared_base_sha: str | None = None,
          prepared_checkout: Path | None = None,
          _core_already_validated: bool = False) -> str:
    checkout = prepared_checkout.resolve() if prepared_checkout else main_checkout()
    if prepared_checkout is not None and not prepared_checkout.is_absolute():
        raise BriefFault(f"prepared checkout must be absolute: {prepared_checkout}")
    ledger = ledger or (checkout / ".dreamwork" / "tasks.md")
    if not owns:
        raise BriefFault(
            "no --owns paths — SKILL.md (#465) makes `Lane-owns:` mandatory on a "
            "worktree brief and lint.check_brief_lane_owns ERRORs without it; the "
            "lane-containment guard has nothing to protect from an empty set"
        )

    if not _core_already_validated:
        validate_core(core, ledger)
    core = _canonicalize_traps_heading(core)

    frame = frame_sections(_read(frame_path, "frame"))
    if not frame:
        raise BriefFault(
            f"frame file {frame_path} yielded ZERO sections — a generated brief "
            "carrying no standing rules looks exactly like a healthy one, so this "
            "refuses rather than emitting a frame that templated nothing"
        )
    boilerplate = _read(boilerplate_path, "standing contract")
    if not boilerplate.strip():
        raise BriefFault(
            f"standing contract {boilerplate_path} is empty; the appended half "
            "would carry no rules"
        )

    record = task_record(task, ledger)
    if (prepared_worktree is None) != (prepared_base_sha is None):
        raise BriefFault(
            "prepared_worktree and prepared_base_sha must be supplied together"
        )
    if prepared_worktree is None:
        worktree = worktree_for(branch)
        resolved_base = base_sha(branch)
    else:
        worktree = prepared_worktree.resolve()
        if not prepared_worktree.is_absolute():
            raise BriefFault(f"prepared worktree must be absolute: {prepared_worktree}")
        if not re.fullmatch(r"[0-9a-f]{40}", prepared_base_sha or ""):
            raise BriefFault(f"prepared base sha is not a commit id: {prepared_base_sha!r}")
        resolved_base = prepared_base_sha
    _validate_file_line_citations(core, checkout, resolved_base)
    _validate_lesson_citation_count(core, checkout, resolved_base)
    print(
        _base_scope_derivation_report(checkout, resolved_base, owns),
        file=sys.stderr,
    )
    head = "\n".join([
        f"# Task #{task} — {record['title'].strip()}",
        "",
        f"Worktree: {worktree}",
        f"Branch: {branch}",
        f"Base sha: {resolved_base}",
        f"Lane-owns: {', '.join(owns)}",
        "",
        f"Repo root: {checkout}",
        f"{COORDINATOR_INBOX_PREFIX}{checkout / '.dreamwork' / 'inbox.md'}",
        "  (`inbox.md`, NOT `.dreamwork/handoffs.md`.)",
        "",
        "**Read the task record first**, using the form the standing contract "
        "gives for a worktree:",
        "",
        f"    python3 dev/ledger.py get {task} --ledger {ledger}",
        "",
    ])
    return "\n\n".join([head.rstrip("\n"), core.strip(), *frame, boilerplate.rstrip("\n")]) + "\n"


def core_from_task(task: int, ledger: Path | None = None) -> str:
    """The task record's own body, as the authored core — the "alongside tasks" half.

    Max's ask was for prompts "pre-written alongside tasks".  Measured on this
    task's own record: the body already carried the defect, its measurements,
    the fix-shape fork, and the direction-2 hazards.  So the durable home for an
    authored core ALREADY EXISTS and it is the task body — no draft-prompt
    column, no second store, no writer added beside the coordinator's.

    The body is lifted, never templated, and `validate_core` still runs on it.
    A record with no direction-2 reasoning is refused exactly as a hand-written
    core would be, which reports a thin task record rather than papering over it.
    """
    ledger = ledger or (main_checkout() / ".dreamwork" / "tasks.md")
    body = _core_of(task_record(task, ledger).get("body") or "", task)
    if not body:
        raise BriefFault(
            f"#{task}'s record carries no body beyond its title, so there is no "
            "authored core to lift; write the core and pass --core"
        )
    return body


def _core_of(body: str, task: int) -> str:
    """The authored prose of a record body, in either ledger mode.

    Store mode returns the body alone; MARKDOWN mode returns the
    ``- **#<id>** <title>`` head line followed by the body indented under it
    (measured, not assumed).  Emitting that verbatim would open the brief with
    a stray bullet, and would make a title-only record look like a core.  So
    drop the head line and dedent by the common leading whitespace.
    """
    lines = body.splitlines()
    if lines and re.match(rf"^- \*\*#{task}\*\*", lines[0]):
        lines = lines[1:]
    indents = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
    dedent = min(indents) if indents else 0
    return "\n".join(line[dedent:] if line.strip() else "" for line in lines).strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # --task (lane brief) and --review (review dispatch) are the two modes; a
    # review is of a branch, not a task, so neither flag is required alone but
    # exactly one must be given (#1115).
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--task", type=int, help="the task id (lane brief mode)")
    mode.add_argument(
        "--review", metavar="BRANCH",
        help="emit a review dispatch prompt for BRANCH with briefs/review-frame.md "
             "appended by construction, and persist its receipt (#1115)")
    parser.add_argument("--lane", help="branch name (default: cx-<task>)")
    parser.add_argument(
        "--round", type=int, default=1,
        help="review round number (review mode only, default 1) — reaches the "
             "receipt (#1115)")
    parser.add_argument(
        "--owns",
        help="comma-separated repo paths the lane owns (`Lane-owns:`, #465); "
             "lane-brief mode only — build() refuses an empty set")
    parser.add_argument(
        "--core", type=Path,
        help="file holding the authored core; `-` or omitted reads stdin")
    parser.add_argument(
        "--core-from-task", action="store_true",
        help="use the task record's own body as the authored core (#881 storage call)")
    parser.add_argument("--ledger", type=Path, help="ledger path (default: the main checkout's)")
    parser.add_argument("--frame", type=Path, default=FRAME_PATH)
    parser.add_argument("--out", type=Path, help="write here instead of stdout")
    return parser


def _read_core(args) -> str:
    """The authored core/review text from --core, stdin, or --core-from-task."""
    if args.core_from_task:
        if args.core is not None:
            raise BriefFault("--core and --core-from-task name two different cores")
        if args.task is None:
            raise BriefFault("--core-from-task needs --task (lane-brief mode)")
        return core_from_task(args.task, args.ledger)
    if args.core is None or str(args.core) == "-":
        if sys.stdin.isatty():
            raise BriefFault(
                "no authored core: --core was not given and stdin is a terminal"
            )
        return sys.stdin.read()
    return _read(args.core, "authored core")


def _main_review(args) -> int:
    """Emit a review dispatch prompt and persist its receipt (#1115).

    The generator and the receipt are the same path: ``review_prompt`` appends
    the frame by construction and ``dispatch_lane.persist_review_prompt``
    (#1112) validates and writes it.  There is no second persist call and no
    hand-concatenation to get wrong.
    """
    branch = args.review
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", branch or ""):
        print(
            "review refused: --review <branch> is required and must be one safe "
            "path component (letters, digits, . _ -)",
            file=sys.stderr,
        )
        return 2
    # Imported at function scope, not module scope, so the lane-brief path
    # (`build`) never depends on `dispatch_lane` — that independence is the
    # invariant this module's docstring states and the lane path's tests
    # (test_launch_lane.py, test_dispatch_lane.py) depend on (#1115).  A
    # module-level import made `brief` unimportable in every fixture repo
    # whose `dispatch_lane` stub cannot be imported, breaking 21 tests.
    import dispatch_lane  # noqa: PLC0415
    try:
        core = _read_core(args)
        frame = _read(dispatch_lane.REVIEW_FRAME_PATH, "review frame")
        prompt = review_prompt(core, frame)
        receipt = dispatch_lane.persist_review_prompt(prompt, branch, args.round)
    except (BriefFault, dispatch_lane.DispatchFault) as exc:
        print(f"review refused: {exc}", file=sys.stderr)
        return 2
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    payload = prompt
    if args.out:
        try:
            args.out.write_text(payload, encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(f"review refused: could not write {args.out}: {exc}", file=sys.stderr)
            return 2
    else:
        sys.stdout.write(payload)
    print(
        f"review prompt persisted: branch={branch}; round={args.round}; "
        f"receipt={receipt}; digest={digest}",
        file=sys.stderr,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.review:
        return _main_review(args)
    try:
        core = _read_core(args)
        if not args.owns:
            raise BriefFault(
                "no --owns paths — SKILL.md (#465) makes `Lane-owns:` mandatory "
                "on a worktree brief and lint.check_brief_lane_owns ERRORs without "
                "it; the lane-containment guard has nothing to protect from an "
                "empty set"
            )
        owns = [token.strip().strip("`") for token in args.owns.split(",") if token.strip().strip("`")]
        # main reads the section count and prints the tool-verbs denominator in
        # one validation; direct build callers still self-validate by default.
        sections = validate_core(core, args.ledger)
        brief = build(args.task, args.lane or f"cx-{args.task}", owns, core,
                      ledger=args.ledger, frame_path=args.frame,
                      _core_already_validated=True)
    except BriefFault as exc:
        print(f"brief refused: {exc}", file=sys.stderr)
        return 2

    if args.out:
        try:
            args.out.write_text(brief, encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(f"brief refused: could not write {args.out}: {exc}", file=sys.stderr)
            return 2
        print(f"brief written: {args.out} ({len(brief)} bytes; "
              f"core sections examined={sections})", file=sys.stderr)
    else:
        sys.stdout.write(brief)
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
