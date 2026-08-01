#!/usr/bin/env python3
"""Run one browser guard at exact revisions without inventing a verdict.

This is deliberately a revision *judge*, not a wrapper around ``git bisect``.
It prints PASS, FAIL, or DID NOT JUDGE for every requested revision.  Only a
complete set of classified revisions can be fed to a search for a boundary.

The historical revision supplies watch.py, client assets, the guard, fixture,
and justfile.  This file supplies isolation and classification.  A fresh
detached worktree preserves repository metadata (some guards use ``git show
HEAD:...``) while excluding ignored files from the caller's present-day tree.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


CRASH_SENTINEL = "FAIL the guard threw before finishing its checks"
GUARD_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")
ASSERTION = re.compile(r"^\s*(PASS|FAIL) (.+)$", re.MULTILINE)
RECIPE_HEADER = re.compile(r"^guards(?:\s+[^:]*)?:\s*$")


class Verdict(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    DID_NOT_JUDGE = "DID NOT JUDGE"


@dataclass(frozen=True)
class Result:
    revision: str
    sha: str | None
    verdict: Verdict
    reason: str
    preflight: str
    output: str = ""


def _run(argv: list[str], *, cwd: Path, env: dict[str, str] | None = None,
         timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=timeout, check=False)


def resolve_commit(repo: Path, revision: str) -> str | None:
    cp = _run(["git", "rev-parse", "--verify", f"{revision}^{{commit}}"], cwd=repo)
    return cp.stdout.strip() if cp.returncode == 0 else None


def port_is_free(port: int) -> bool:
    with socket.socket() as sock:
        # Match Python's guard server.  Without SO_REUSEADDR a just-finished
        # revision's TIME_WAIT socket makes the next revision look like a live
        # contaminating server even though no process is listening.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _guards_recipe_body(justfile: str) -> list[str]:
    """Extract command-bearing lines from the top-level ``guards`` recipe."""
    lines = justfile.splitlines()
    for index, line in enumerate(lines):
        if not RECIPE_HEADER.fullmatch(line):
            continue
        body: list[str] = []
        for candidate in lines[index + 1:]:
            if candidate and not candidate[0].isspace():
                break
            stripped = candidate.lstrip()
            if stripped and not stripped.startswith("#"):
                body.append(stripped)
        return body
    return []


def inspect_revision_tree(tree: Path, sha: str, guard: str) -> str | None:
    """Return why this tree cannot be judged, or None when prerequisites hold."""
    if not (tree / ".git").exists():
        return "revision tree has no .git; source-pinning guards cannot run"

    head = _run(["git", "rev-parse", "HEAD"], cwd=tree)
    if head.returncode != 0 or head.stdout.strip() != sha:
        return "revision tree HEAD does not equal the requested commit"

    status = _run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all",
         "--ignored=matching"], cwd=tree)
    if status.returncode != 0:
        return "git status could not verify revision-tree cleanliness"
    if status.stdout.strip():
        return "revision tree is contaminated before the guard: " + status.stdout.splitlines()[0]

    required = (
        "watch.py", "justfile", "lint.py", "dev/capture/fixture",
        f"dev/capture/{guard}.mjs",
    )
    missing = [rel for rel in required if not (tree / rel).exists()]
    if missing:
        return "revision lacks required guard inputs: " + ", ".join(missing)

    # Inspect the recipe body, not arbitrary bytes in the file.  This proves
    # the historical recipe has the direct checks we know how to audit; it
    # deliberately makes no claim to interpret arbitrary shell semantics.
    just = (tree / "justfile").read_text(encoding="utf-8", errors="replace")
    body = _guards_recipe_body(just)
    if not any(re.match(r"python3\s+lint\.py\s+guard-execution\b", line) and
               re.search(r"\|\|\s*fail=1\s*$", line) for line in body):
        return "historical guards recipe has no direct judged-guard gate"
    if not any(re.match(r"node\s+[\"']?dev/capture/\$g\.mjs[\"']?(?:\s|$)", line)
               for line in body):
        return "historical guards recipe has no direct selected-guard invocation"
    port_check = any(line.startswith("_holder_line=$(ss ") for line in body)
    target_read = any(line.startswith("served=$(curl ") and "/data.json" in line
                      for line in body)
    target_check = any("$served" in line and "$OUT/target" in line and
                       line.startswith("if [ ") for line in body)
    if not (port_check and target_read and target_check):
        return "historical guards recipe has no direct server identity/ownership gate"

    pin = _run(["git", "show", "HEAD:watch.py"], cwd=tree)
    if pin.returncode != 0:
        return "git show HEAD:watch.py failed; source-pinning guards cannot judge"
    return None


def classify_output(output: str, returncode: int, guard: str) -> tuple[Verdict, str]:
    """Classify only evidence the historical recipe's judgement gate emitted."""
    suite_pass = re.search(rf"^\s*PASS {re.escape(guard)}\s*$", output, re.MULTILINE)
    suite_fail = re.search(rf"^\s*FAIL {re.escape(guard)}(?:\s|$)", output, re.MULTILINE)
    assertions = [(kind, body) for kind, body in ASSERTION.findall(output)
                  if not body.startswith(f"{guard} ")]
    real_fails = [body for kind, body in assertions
                  if kind == "FAIL" and not body.startswith(
                      "the guard threw before finishing its checks")]
    unmet_preconditions = [body for body in real_fails
                           if body.lower().startswith("precondition:") or
                           "exists (else every check below" in body]

    if returncode == 0 and suite_pass:
        # inspect_revision_tree requires the historical guard-execution gate;
        # rc=0 therefore means its private raw log contained a real assertion.
        return Verdict.PASS, "historical guard-execution gate confirmed a judged pass"
    if suite_fail and unmet_preconditions:
        return Verdict.DID_NOT_JUDGE, "guard precondition failed: " + unmet_preconditions[0]
    if suite_fail and real_fails:
        return Verdict.FAIL, real_fails[0]
    if CRASH_SENTINEL in output:
        return Verdict.DID_NOT_JUDGE, "guard crashed before a behavioural assertion"
    if returncode == 124:
        return Verdict.DID_NOT_JUDGE, "guard timed out without a classified assertion"
    return Verdict.DID_NOT_JUDGE, (
        f"historical recipe exited {returncode} without a complete judgement receipt")


def read_preflight(repo: Path) -> str:
    cp = _run([sys.executable, "dev/guard_preflight.py"], cwd=repo)
    lines = [line for line in cp.stdout.splitlines() if line.startswith("guard preflight:")]
    return lines[-1] if lines else "guard preflight: UNAVAILABLE — did not produce a verdict"


def judge_revision(repo: Path, revision: str, guard: str, port: int,
                   preflight: str, *, timeout: int = 180) -> Result:
    sha = resolve_commit(repo, revision)
    if sha is None:
        return Result(revision, None, Verdict.DID_NOT_JUDGE,
                      "revision does not resolve to a commit", preflight)
    if not port_is_free(port):
        return Result(revision, sha, Verdict.DID_NOT_JUDGE,
                      f"guard port {port} is already held", preflight)

    parent = Path(tempfile.mkdtemp(prefix="dreamwork-bisect-"))
    tree = parent / "tree"
    added = False
    try:
        add = _run(["git", "worktree", "add", "--detach", str(tree), sha], cwd=repo)
        if add.returncode != 0:
            return Result(revision, sha, Verdict.DID_NOT_JUDGE,
                          "git worktree add failed: " + add.stdout.strip(), preflight)
        added = True
        reason = inspect_revision_tree(tree, sha, guard)
        if reason:
            return Result(revision, sha, Verdict.DID_NOT_JUDGE, reason, preflight)

        env = os.environ.copy()
        env["DREAMWORK_GUARDS"] = guard
        env["DREAMWORK_HUB_GUARDS"] = ""
        env["DREAMWORK_GUARD_TIMEOUT"] = str(timeout)
        try:
            cp = _run(["just", "guards", str(port)], cwd=tree, env=env,
                      timeout=timeout + 30)
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            return Result(revision, sha, Verdict.DID_NOT_JUDGE,
                          "outer runner timed out before a judgement", preflight, output)
        verdict, why = classify_output(cp.stdout, cp.returncode, guard)
        return Result(revision, sha, verdict, why, preflight, cp.stdout)
    finally:
        if added:
            # The path is a private mkdtemp made above.  Inspect first; forced
            # removal is needed for ignored __pycache__ files a historical run
            # may create, and can touch no caller-owned worktree.
            _run(["git", "worktree", "remove", "--force", str(tree)], cwd=repo)
        shutil.rmtree(parent, ignore_errors=True)


def _exit_for(results: list[Result], preflight: str) -> int:
    if any(r.verdict is Verdict.DID_NOT_JUDGE for r in results):
        return 125
    if any(r.verdict is Verdict.FAIL for r in results):
        # A red under CAUTION-or-worse is evidence that needs a calmer rerun,
        # not a boundary.  Preserve the judged fact while refusing the claim.
        if "guard preflight: OK " not in preflight:
            return 125
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("revisions", nargs="+", help="commits to judge, in displayed order")
    ap.add_argument("--guard", required=True)
    ap.add_argument("--port", type=int, default=39890)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--force-risk", action="store_true",
                    help="run under WRONG-ANSWER-RISK; a red still exits 125")
    ns = ap.parse_args(argv)
    repo = ns.repo.resolve()
    if not GUARD_NAME.fullmatch(ns.guard):
        ap.error("--guard must be a simple guard name")
    if not 39890 <= ns.port <= 39899:
        ap.error("--port must be in this lane's authorised range 39890-39899")

    preflight = read_preflight(repo)
    print(preflight)
    if "WRONG-ANSWER-RISK" in preflight and not ns.force_risk:
        for rev in ns.revisions:
            print(f"{rev}: DID NOT JUDGE — preflight refused the wrong-answer regime")
        return 125

    results = [judge_revision(repo, rev, ns.guard, ns.port, preflight,
                              timeout=ns.timeout) for rev in ns.revisions]
    for result in results:
        short = result.sha[:12] if result.sha else "unresolved"
        print(f"{result.revision} ({short}): {result.verdict.value} — {result.reason}")
        print(f"  {result.preflight}")
        if result.verdict is not Verdict.PASS and result.output:
            for line in result.output.splitlines():
                if line.lstrip().startswith(("FAIL ", "Error", "guards:")):
                    print("  " + line.strip())
    rc = _exit_for(results, preflight)
    if rc == 125:
        print("boundary: REFUSED — at least one revision or red result is unclassifiable")
    elif rc == 1:
        print("boundary input: complete, with at least one judged failure")
    else:
        print("boundary input: complete; every requested revision passed")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
