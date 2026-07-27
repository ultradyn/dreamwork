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
