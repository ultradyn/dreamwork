"""ud-dw-user-events — the bounded CLI over the user-event journal, exercised.

The CLI is loaded by path (no .py extension, like bin/ud-dw-githash) and driven
through ``main([...], out=...)`` so exit codes are the real integers the script
returns, not a subprocess's. One subprocess test pins the shebang + ``--help``
contract, matching the repo's pattern for extensionless scripts (test_githash).

Fixtures populate the journal through the PRODUCTION path (open_journal +
receive), never a hand-built INSERT — building the state whose construction is
under test is the #320 trap. The CLI reads that journal read-only.
"""

import importlib.util
import io
import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from user_events.sqlite import Envelope, open_journal

REPO = Path(__file__).resolve().parent
CLI = REPO / "ud-dw-user-events"


def _load_cli():
    """Load the extensionless CLI via an explicit SourceFileLoader.

    spec_from_file_location returns None for a file with no .py suffix, so the
    loader must be named; an extensionless script is the repo's bin/ convention.
    """
    import importlib.machinery

    loader = importlib.machinery.SourceFileLoader("ud_dw_user_events", str(CLI))
    spec = importlib.util.spec_from_loader("ud_dw_user_events", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


# Distinct, well-formed UUIDv4s for deterministic fixtures.
def _uuid(i: int) -> str:
    return f"00000000-0000-4000-8000-{i:012d}"


@pytest.fixture
def module():
    """The CLI, loaded fresh per test (no cached module state)."""
    return _load_cli()


def seed_journal(path: Path, n: int, *, body: bytes | None = None) -> list:
    """Insert n receipts via the production receive() path; return their results."""
    results = []
    with open_journal(path) as j:
        for i in range(n):
            b = body if body is not None else f'{{"text":"answer-{i}"}}'.encode()
            res = j.receive(
                Envelope(
                    client_action_id=_uuid(i),
                    protocol_version="HTTP/1.1",
                    method="POST",
                    route="/answer",
                    content_type="application/json",
                    body=b,
                )
            )
            assert res.kind == "inserted", f"row {i} did not insert: {res.kind}"
            results.append(res)
    return results


# ---------------------------------------------------------------------------
# F4 — health names a recovery path for every failure semantic
# ---------------------------------------------------------------------------

DESIGN_DOC = REPO / ".dreamwork" / "docs" / "plans" / "user-event-journal.md"


def _parse_failure_semantics(path: Path) -> list:
    """The pre-colon phrase of each bullet in the design's §Failure semantics.

    The design doc is the source of truth; HEALTH_ROWS is the thing checked
    against it (no second copy of the rule is held here). The caller must assert
    the result is plausible — a parser that silently finds nothing makes the
    coverage check vacuous.
    """
    lines = path.read_text().splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == "## Failure semantics":
            start = i
            break
    assert start is not None, "## Failure semantics section not found in design doc"
    keys = []
    for ln in lines[start + 1:]:
        s = ln.strip()
        if s.startswith("## "):
            break  # next section ends the list
        if s.startswith("- "):
            key = s[2:].split(":", 1)[0].strip()
            if key:
                keys.append(key)
    return keys


def test_every_failure_semantic_has_a_health_row(module):
    semantics = _parse_failure_semantics(DESIGN_DOC)
    # CRITICAL (criterion 6, lessons.md:1447): a parse that silently finds
    # nothing must FAIL LOUDLY. Without this guard the coverage loop below
    # iterates over zero items and passes having checked nothing — a silent
    # third verdict that reads as reassurance. The count is derived from the
    # document; 5 is a sanity floor the current document (8) comfortably clears.
    assert len(semantics) >= 5, (
        f"parse found only {len(semantics)} failure semantics — the coverage "
        "check would be vacuous; the parser is broken or the section moved")
    assert len(semantics) == len(set(semantics)), (
        f"duplicate semantic keys parsed: {semantics}")

    rows = module.HEALTH_ROWS
    missing = [s for s in semantics if s not in rows]
    assert not missing, f"health has no recovery row for: {missing}"
    # No orphan rows either: every health row corresponds to a real semantic,
    # so the table cannot silently drift from the design.
    orphan = [k for k in rows if k not in set(semantics)]
    assert not orphan, f"health has rows for semantics not in the design: {orphan}"


def test_health_command_emits_one_row_per_semantic(module, tmp_path):
    db = tmp_path / "journal.sqlite3"
    seed_journal(db, 1)
    buf = io.StringIO()
    code = module.main(
        ["health", "--journal", str(db), "--target", str(tmp_path)], out=buf)
    assert code == module.EX_OK
    rows = [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]
    assert len(rows) == len(module.HEALTH_ROWS)
    assert {r["semantic"] for r in rows} == set(module.HEALTH_ROWS)
    for r in rows:
        assert r["recovery"]


# ---------------------------------------------------------------------------
# F3 — replay is the only command that may cause a domain effect
# ---------------------------------------------------------------------------


def test_no_command_but_replay_touches_a_domain_file(module, tmp_path):
    from user_events.domain_files import build_managed_text

    target = tmp_path / "target"
    target.mkdir()
    # Managed files built by the production writer helper (imported, never
    # edited — lane C owns domain_files.py).
    (target / "questions.md").write_text(
        build_managed_text("- **Q1** — an open question\n", 1, "test"))
    (target / "tasks.md").write_text(build_managed_text("tasks body\n", 1, "test"))
    db = tmp_path / "journal.sqlite3"  # journal OUTSIDE the target
    (res,) = seed_journal(db, 1)

    # Derive the protected set by WALKING the directory, never a hardcoded list
    # — a directory that grows is how a check goes hollow after its red run.
    managed = sorted(p for p in target.rglob("*") if p.is_file())
    assert managed, "fixture has no files to protect — the check would be vacuous"
    before = {p: p.read_bytes() for p in managed}

    # Every READ command leaves every managed file byte-identical. health is
    # added in F4; deriving from READ_COMMANDS means this covers it then too.
    read_cmds = [
        ["list", "--format", "jsonl"],
        ["show", str(res.sequence)],
    ]
    # (health joins read_cmds once F4 registers it in READ_COMMANDS)
    read_cmds += [["health"]] if "health" in module.READ_COMMANDS else []
    for cmd in read_cmds:
        buf = io.StringIO()
        code = module.main(
            cmd + ["--journal", str(db), "--target", str(target)], out=buf)
        assert code == module.EX_OK, f"{cmd[0]} failed: {buf.getvalue()!r}"
        after = {p: p.read_bytes() for p in managed}
        assert after == before, f"{cmd[0]} touched a managed domain file"

    # Discriminating half — the read-only guard (F3 red line). replay/purge are
    # the ONLY write-authorized commands; no read command is write-authorized.
    write_auth = {c for c in module.COMMANDS if module._write_authorized(c)}
    assert write_auth == {"replay", "purge"}, f"read-only guard widened: {write_auth}"
    for c in module.READ_COMMANDS:
        assert not module._write_authorized(c), f"{c!r} is write-authorized"

    # replay is permitted (the only write-authorized, implemented command); its
    # domain effects are not built, so it reports not_implemented and applies
    # nothing — and still touches no managed file.
    rbuf = io.StringIO()
    rcode = module.main(
        ["replay", "--journal", str(db), "--target", str(target)], out=rbuf)
    assert rcode == module.EX_OK
    assert json.loads(rbuf.getvalue())["replay"] == "not_implemented"
    assert {p: p.read_bytes() for p in managed} == before, "replay mutated a file"


# ---------------------------------------------------------------------------
# F2 — show is the only exact-bytes path; truncation reports what it dropped
# ---------------------------------------------------------------------------


def test_truncation_reports_the_original_length_and_digest(module, tmp_path):
    db = tmp_path / "journal.sqlite3"
    body = b"x" * 200
    max_bytes = 50
    # Precondition, derived at runtime: the payload must exceed --max-bytes,
    # else "truncation reports original length" is never exercised.
    assert len(body) > max_bytes
    (res,) = seed_journal(db, 1, body=body)
    expected_digest = res.request_digest

    buf = io.StringIO()
    code = module.main(
        ["show", res.receipt_id, "--journal", str(db), "--target", str(tmp_path),
         "--max-bytes", str(max_bytes)],
        out=buf,
    )
    assert code == module.EX_OK
    rec = json.loads(buf.getvalue())

    assert rec["truncated"] is True
    # The two named metadata fields (F2 red line: the truncation-metadata emit).
    assert "original_length" in rec, "truncation omitted original_length"
    assert rec["original_length"] == len(body), "original_length must be the full payload"
    assert rec["digest"] == expected_digest, "truncation must report the request digest"
    # The shown payload is bounded.
    assert len(rec["payload"].encode("utf-8", "replace")) <= max_bytes


def test_show_untruncated_carries_the_payload_and_stable_id(module, tmp_path):
    db = tmp_path / "journal.sqlite3"
    body = b'{"text":"a short answer"}'
    (res,) = seed_journal(db, 1, body=body)
    buf = io.StringIO()
    code = module.main(
        ["show", res.receipt_id, "--journal", str(db), "--target", str(tmp_path),
         "--max-bytes", "4096"],
        out=buf,
    )
    assert code == module.EX_OK
    rec = json.loads(buf.getvalue())
    assert rec["truncated"] is False
    assert rec["payload"].encode("utf-8") == body
    assert rec["id"] == res.receipt_id


def test_show_unknown_receipt_is_noinput(module, tmp_path):
    db = tmp_path / "journal.sqlite3"
    seed_journal(db, 1)
    assert module.main(
        ["show", "never-existed", "--journal", str(db), "--target", str(tmp_path)],
        out=io.StringIO(),
    ) == 66  # EX_NOINPUT


# ---------------------------------------------------------------------------
# F1 — list is a bounded projection with stable exit codes
# ---------------------------------------------------------------------------


def test_list_is_bounded_and_never_exceeds_limit(module, tmp_path):
    db = tmp_path / "journal.sqlite3"
    limit = 5
    n = limit + 4  # derived at runtime from the limit …
    assert n > limit  # … and asserted to EXCEED it (else the check is vacuous)
    seed_journal(db, n)

    buf = io.StringIO()
    code = module.main(
        ["list", "--journal", str(db), "--target", str(tmp_path),
         "--limit", str(limit), "--format", "jsonl"],
        out=buf,
    )
    assert code == module.EX_OK

    rows = [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]
    # The discriminating assertion: the row count IS the limit, not n. A test
    # that only checks field presence passes with LIMIT ? deleted; this one
    # cannot. (F1 red line: the LIMIT ? bind.)
    assert len(rows) == limit, (
        f"LIMIT ? not honoured: got {len(rows)} rows for limit {limit} "
        f"(fixture inserted {n})"
    )
    # The design's field set is present (secondary — presence alone is hollow).
    expected_fields = {"id", "sequence", "endpoint", "time", "digest",
                       "state", "payload_size"}
    for r in rows:
        assert expected_fields <= set(r), f"missing fields in row: {r}"


def test_exit_codes_are_stable(module, tmp_path):
    db = tmp_path / "journal.sqlite3"
    seed_journal(db, 2)

    # success -> 0 (EX_OK)
    assert module.main(
        ["list", "--journal", str(db), "--target", str(tmp_path)], out=io.StringIO()
    ) == 0

    # unknown command -> 64 (EX_USAGE); specific integer, not "non-zero"
    assert module.main(
        ["bogus", "--journal", str(db), "--target", str(tmp_path)], out=io.StringIO()
    ) == 64

    # journal absent -> 66 (EX_NOINPUT): the read path must not CREATE a journal
    assert module.main(
        ["list", "--journal", str(tmp_path / "absent.sqlite3"),
         "--target", str(tmp_path)], out=io.StringIO()
    ) == 66

    # bad argument -> 64 (EX_USAGE)
    assert module.main(
        ["list", "--journal", str(db), "--limit", "not-an-int"], out=io.StringIO()
    ) == 64


def test_the_cli_is_executable_and_help_documents_exit_codes():
    assert CLI.exists(), "ud-dw-user-events is missing"
    assert CLI.stat().st_mode & 0o111, "ud-dw-user-events is not executable"
    r = subprocess.run(
        [sys.executable, str(CLI), "--help"],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, f"--help exited {r.returncode}: {r.stderr}"
    # The stable exit codes are documented in the script's own --help.
    for token in ("EX_OK", "EX_USAGE", "EX_NOINPUT", "EX_SOFTWARE"):
        assert token in r.stdout, f"--help does not document {token}"


def test_submissions_is_never_load_bearing_in_the_journal_or_cli():
    """submissions.log is best-effort by design; if the journal or CLI ever
    needs it to answer a question, the journal is incomplete. Cheap grep guard
    against a whole class of drift (plan §"3 · submissions.log must not become
    load-bearing"). Read from file contents so it holds before the file is
    tracked, not only after."""
    targets = [CLI, *sorted((REPO / "user_events").glob("*.py"))]
    assert targets, "no files to scan — the precondition guard is vacuous"
    offenders = [str(p) for p in targets if b"submissions" in p.read_bytes()]
    assert not offenders, f"'submissions' is load-bearing in: {offenders}"
