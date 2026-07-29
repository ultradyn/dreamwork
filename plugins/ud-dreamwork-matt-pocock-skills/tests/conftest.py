"""Fixtures shared by the ud-dreamwork-matt-pocock-skills adapter seam tests.

T1–T5 (design §12) prove the bridge's three invariants hold at the seams. The
fixtures here build REAL scratch targets (a valid markdown ledger, a seeded
questions.md, and a REAL post-cutover store via the same `perform_cutover`
idiom `test_lint.TestStoreModeLint._cut_over` uses) so the checks run against
the cutover path, never the main checkout's live `.dreamwork/`.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import subprocess
import sys
from pathlib import Path

# plugin/ lives at parents[1], plugins/ at parents[2], the core root at
# parents[3] (this file is .../tests/conftest.py).
PLUGIN = Path(__file__).resolve().parents[1]
CORE = Path(__file__).resolve().parents[3]
ADAPTER = PLUGIN / "tracker_adapter.py"
SKILL = PLUGIN / "SKILL.md"

for _p in (str(CORE), str(PLUGIN)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ledger_parse  # noqa: E402
import watch  # noqa: E402
import tracker_adapter  # noqa: E402


# A valid markdown ledger: both anchored headings in order + a `Next id` header
# (what `dev/ledger.py file` asserts and `perform_cutover` imports).
TASKS_MD = (
    "# Task ledger\n\n"
    "Next id: **12**\n\n"
    "## Open\n\n"
    "- **#10** — a clean open entry · P1 · task · origin: **human**\n\n"
    "## Recently landed\n\n"
    "- **#11** — a clean landed entry · P0 · implementation · "
    "origin: **human** (abc1234)\n"
)

# A questions.md seeded with ONE existing entry, so a posed grill question is a
# DISTINCT new entry (the T3 precondition derives its existence at runtime
# rather than assuming an empty file).
QUESTIONS_MD = (
    "# Questions for the human\n\n"
    "## Open\n\n"
    "- **existing seed question.** some context.\n\n"
    "## Answered\n"
)


def make_target(base: Path, *, questions: str = QUESTIONS_MD,
                tasks: str = TASKS_MD) -> Path:
    """A scratch dreamwork target under `base` with core ledger + questions."""
    target = base / "target"
    dw = target / ".dreamwork"
    dw.mkdir(parents=True)
    (dw / "tasks.md").write_text(tasks, encoding="utf-8")
    (dw / "questions.md").write_text(questions, encoding="utf-8")
    return target


def cut_over(dw_dir: Path) -> None:
    """Flip a markdown `.dreamwork/` to store mode via the REAL cutover path.

    Mirrors `test_lint.TestStoreModeLint._cut_over`: runs
    `ud-dw-tasks-migrate perform_cutover`, which writes the watermark + store +
    deprecated shim. The caller asserts `source_of_truth` flipped, because a
    cutover that silently did nothing would make a T2 'identical' pass vacuous."""
    loader = importlib.machinery.SourceFileLoader(
        "_ud_dw_tasks_migrate_t5xx", str(CORE / "ud-dw-tasks-migrate"))
    spec = importlib.util.spec_from_loader("_ud_dw_tasks_migrate_t5xx", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    mod.perform_cutover(str(dw_dir), out=io.StringIO())


def fake_runner():
    """A subprocess stand-in that captures argv and returns a clean result.

    Used where a seam check asserts on the verb argv without actually running
    the verb (T1/T2/T4). Returns (runner, argvs)."""
    argvs: list[list[str]] = []

    def _run(argv, **kwargs):
        argvs.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="ok\n", stderr="")

    return _run, argvs
