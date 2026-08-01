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

## Storage

This tool writes no files and opens no store for writing; it emits text on
stdout.  Persisting a brief is `dispatch_lane.persist_prompt`'s job and it
already owns the corpus path, the create-once semantics, and the hash receipt.
That keeps the tracked/untracked question (`#867`) a parameter of a component
this tool does not touch.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FRAME_PATH = ROOT / "briefs" / "frame.md"
BOILERPLATE_PATH = ROOT / "briefs" / "boilerplate.md"

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
_DIRECTION_2 = re.compile(r"direction[ ‑-]?2", re.IGNORECASE)
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
    if not stripped or stripped.startswith("#"):
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


def validate_core(core: str) -> None:
    """Refuse an authored core that is absent, placeholder, or has no direction 2.

    Each refusal names a mode this function can actually detect.  It cannot
    detect a direction-2 list that is present, substantive and wrong.
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
    for line in [*lines, "# end"]:
        if line.lstrip().startswith("#"):
            if heading is not None and not body_seen:
                raise BriefFault(
                    f"the authored core section {heading.strip()!r} has no body — a "
                    "copied heading with nothing under it reads as a written section "
                    "and is not one"
                )
            heading, body_seen = line, False
        elif _substantive(line):
            body_seen = True

    for index, line in enumerate(lines):
        if _DIRECTION_2.search(line) and any(_substantive(rest) for rest in lines[index + 1:]):
            return
    raise BriefFault(
        "the authored core names no direction-2 construction with a body — "
        "\"here is how a test of this could pass while the thing is broken\" is "
        "task-specific and carries this loop's quality; 40 of the 40 most recent "
        "briefs carry one (dev/brief_corpus_stats.py)"
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
          prepared_checkout: Path | None = None) -> str:
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

    validate_core(core)

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
    parser.add_argument("--task", type=int, required=True, help="the task id")
    parser.add_argument("--lane", help="branch name (default: cx-<task>)")
    parser.add_argument(
        "--owns", required=True,
        help="comma-separated repo paths the lane owns (`Lane-owns:`, #465)")
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


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.core_from_task:
            if args.core is not None:
                raise BriefFault("--core and --core-from-task name two different cores")
            core = core_from_task(args.task, args.ledger)
        elif args.core is None or str(args.core) == "-":
            if sys.stdin.isatty():
                raise BriefFault(
                    "no authored core: --core was not given and stdin is a terminal"
                )
            core = sys.stdin.read()
        else:
            core = _read(args.core, "authored core")
        owns = [token.strip().strip("`") for token in args.owns.split(",") if token.strip().strip("`")]
        brief = build(args.task, args.lane or f"cx-{args.task}", owns, core,
                      ledger=args.ledger, frame_path=args.frame)
    except BriefFault as exc:
        print(f"brief refused: {exc}", file=sys.stderr)
        return 2

    if args.out:
        try:
            args.out.write_text(brief, encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(f"brief refused: could not write {args.out}: {exc}", file=sys.stderr)
            return 2
        print(f"brief written: {args.out} ({len(brief)} bytes)", file=sys.stderr)
    else:
        sys.stdout.write(brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
