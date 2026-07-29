"""ud-dw-tasks-migrate --verify — the tamper suite for #294 increment 4.

These are the tests that prove verification can FAIL: each tampers the
scratch DB after a clean import, then asserts --verify exits nonzero AND
names the row. A verify that prints a bare "mismatch" — or that reads the
import's intentions instead of the DB's contents — cannot pass these.

The idempotency and refusal tests live here too: a second --import is a
no-op with identical verification; a divergent DB is a loud refusal, never
a silent repair.
"""

import io
import sqlite3
from pathlib import Path

import pytest

from test_tasks_migrate_import import (
    FIXTURE, _derived, _import, _load_cli, _scratch,
)

REPO = Path(__file__).resolve().parent
# Post-cutover (#294) the live Markdown ledger is the FROZEN deprecated file —
# tasks.md itself is a one-line migration-notice shim that build_analysis
# refuses (_Unparseable: no `## Open`). The import/verify acceptance checks
# describe the frozen document, so that is the file they must read.
LIVE_LEDGER = REPO / ".dreamwork" / "tasks.md.deprecated"


@pytest.fixture
def module():
    return _load_cli()


def _tamper(db: str, sql: str, params=()):
    conn = sqlite3.connect(db)
    conn.execute(sql, params)
    conn.commit()
    conn.close()


def _verify(module, text: str, db: str) -> tuple[int, str]:
    import tempfile
    p = Path(tempfile.mkdtemp()) / "tasks.md"
    p.write_text(text)
    out = io.StringIO()
    rc = module.main(["--verify", "--ledger", str(p), "--to", db], out=out)
    return rc, out.getvalue()


@pytest.fixture
def imported(module, tmp_path):
    db = _scratch(tmp_path)
    assert _import(module, FIXTURE, db) == 0
    return db


# ---------------------------------------------------------------------------
# Tamper — every one of these MUST fail verification, naming the row.
# ---------------------------------------------------------------------------
def test_verify_clean_db_passes(module, imported):
    rc, out = _verify(module, FIXTURE, imported)
    assert rc == 0, out
    assert "verification OK" in out


def test_tampered_body_fails_naming_the_row(module, imported):
    d = _derived(FIXTURE)
    victim = min(d["open"])
    _tamper(imported, "UPDATE task SET body = body || 'x' WHERE id = ?",
            (victim,))
    rc, out = _verify(module, FIXTURE, imported)
    assert rc == 65
    assert f"task #{victim}:" in out and "body" in out


def test_tampered_digest_fails_naming_the_row(module, imported):
    d = _derived(FIXTURE)
    victim = max(d["landed"])
    _tamper(imported, "UPDATE task SET body_digest = 'faked' WHERE id = ?",
            (victim,))
    rc, out = _verify(module, FIXTURE, imported)
    assert rc == 65
    assert f"task #{victim}:" in out and "body_digest" in out


def test_tampered_band_fails_naming_the_row(module, imported):
    d = _derived(FIXTURE)
    compound = {ids[0] for ids, body in d["entries"]
                if any("/" in b for b in
                       __import__("test_tasks_migrate_import")
                       ._band_fields(body))}
    assert compound, "fixture lost its compound band — tamper has no anchor"
    victim = min(compound)
    # P3 is a valid FK target: detection must come from the VALUE check.
    _tamper(imported, "UPDATE task SET priority = 'P3' WHERE id = ?", (victim,))
    rc, out = _verify(module, FIXTURE, imported)
    assert rc == 65
    assert f"task #{victim}:" in out and "priority" in out


def test_tampered_uncertain_bit_fails(module, imported):
    _tamper(imported,
            "UPDATE task SET priority_uncertain = 0 "
            "WHERE priority_uncertain = 1")
    rc, out = _verify(module, FIXTURE, imported)
    assert rc == 65
    assert "priority_uncertain" in out


def test_missing_row_fails_naming_the_id(module, imported):
    d = _derived(FIXTURE)
    victim = max(d["all_ids"])
    _tamper(imported, "DELETE FROM task WHERE id = ?", (victim,))
    rc, out = _verify(module, FIXTURE, imported)
    assert rc == 65
    assert f"task #{victim}: missing" in out


def test_extra_row_fails_naming_the_id(module, imported):
    d = _derived(FIXTURE)
    extra = max(d["all_ids"]) + 500
    conn = sqlite3.connect(imported)
    peak = conn.execute("SELECT MAX(id) FROM task").fetchone()[0]
    conn.close()
    assert extra > peak, "extra id must not collide with an imported one"
    # Insert then fix the sequence back down is impossible (seed refuses to
    # lower on next open_store), so tamper seq too, mimicking a bad writer.
    _tamper(imported,
            "INSERT INTO task(id, state, title, body) VALUES (?, 'open', 't', 'b')",
            (extra,))
    _tamper(imported, "UPDATE sqlite_sequence SET seq = ?", (peak,))
    rc, out = _verify(module, FIXTURE, imported)
    assert rc == 65
    assert f"task #{extra}:" in out


def test_dropped_related_edge_fails(module, imported):
    d = _derived(FIXTURE)
    related = set()
    import lint, ledger_parse
    for ids, body in d["entries"]:
        for m in lint.RELATED_MARKER.finditer(body):
            for x in ledger_parse.ENTRY_ID.findall(m.group(1)):
                for own in ids:
                    pair = (min(own, int(x)), max(own, int(x)))
                    if int(x) in d["all_ids"] and pair[0] != pair[1]:
                        related.add(pair)
    assert related, "fixture lost its related pair — tamper has no anchor"
    a, b = sorted(related)[0]
    _tamper(imported, "DELETE FROM related WHERE a = ? AND b = ?", (a, b))
    rc, out = _verify(module, FIXTURE, imported)
    assert rc == 65
    assert "related" in out


def test_dropped_depends_edge_fails(module, imported):
    d = _derived(FIXTURE)
    edges = set()
    for ids, body in d["entries"]:
        for m in __import__("re").finditer(r"blocked on (#\d+)", body,
                                           __import__("re").I):
            n = int(m.group(1)[1:])
            for own in ids:
                if n in d["all_ids"] and n != own:
                    edges.add((own, n))
    assert edges, "fixture lost its depends edge — tamper has no anchor"
    t, n = sorted(edges)[0]
    _tamper(imported, "DELETE FROM depends WHERE task = ? AND needs = ?",
            (t, n))
    rc, out = _verify(module, FIXTURE, imported)
    assert rc == 65
    assert "depends" in out


def test_tampered_sequence_fails(module, imported):
    _tamper(imported, "UPDATE sqlite_sequence SET seq = seq + 7 "
                      "WHERE name = 'task'")
    rc, out = _verify(module, FIXTURE, imported)
    assert rc == 65
    assert "sequence" in out


def test_tampered_origin_fails_naming_the_row(module, imported):
    d = _derived(FIXTURE)
    marked = {i for i, b in d["per_id"].items()
              if "origin: **human**" in b}
    assert marked, "fixture lost its human-origin entries"
    victim = min(marked)
    _tamper(imported, "UPDATE task SET origin = 'loop' WHERE id = ?", (victim,))
    rc, out = _verify(module, FIXTURE, imported)
    assert rc == 65
    assert f"task #{victim}:" in out and "origin" in out


# ---------------------------------------------------------------------------
# Idempotency — the chosen rule: second --import is a no-op with identical
# verification; a DIVERGENT DB is a loud refusal, never a silent repair.
# ---------------------------------------------------------------------------
def test_second_import_is_a_noop_with_identical_verification(module, imported):
    out = io.StringIO()
    rc = _import(module, FIXTURE, imported, out=out)
    assert rc == 0, out.getvalue()
    assert "no-op" in out.getvalue()
    assert "verification OK" in out.getvalue()
    rc2, out2 = _verify(module, FIXTURE, imported)
    assert rc2 == 0, out2


def test_second_import_over_divergent_db_refuses_loudly(module, imported):
    d = _derived(FIXTURE)
    victim = min(d["open"])
    _tamper(imported, "UPDATE task SET body = body || 'x' WHERE id = ?",
            (victim,))
    out = io.StringIO()
    rc = _import(module, FIXTURE, imported, out=out)
    assert rc == 65, "a divergent DB must refuse, not silently repair"
    assert f"task #{victim}:" in out.getvalue()
    # …and the tamper must still be there afterwards: no repair happened.
    body = sqlite3.connect(imported).execute(
        "SELECT body FROM task WHERE id = ?", (victim,)).fetchone()[0]
    assert body.endswith("x"), "the refusal repaired the row it refused over"


# ---------------------------------------------------------------------------
# Refusals — ledgers with no ruled import resolution never reach the schema.
# ---------------------------------------------------------------------------
def _ledger(entries: str, next_id: int) -> str:
    return (f"# Task ledger\n\nNext id: **{next_id}**\n\n"
            f"## Open\n\n{entries}\n## Recently landed\n")


def test_duplicate_ids_refuse_import(module, tmp_path):
    text = _ledger(
        "- **#5** — twin one · P1 · task · origin: **human**\n\n"
        "- **#5** — twin two · P1 · task · origin: **loop**\n", 6)
    out = io.StringIO()
    rc = _import(module, text, _scratch(tmp_path), out=out)
    assert rc == 65
    assert "refused" in out.getvalue() and "duplicate ids" in out.getvalue()


def test_stray_entry_refuses_import(module, tmp_path):
    text = ("# Task ledger\n\n- **#7** — a stray preamble entry · P2 · task\n\n"
            "Next id: **7**\n\n## Open\n\n"
            "- **#6** — a clean open entry · P1 · task · origin: **human**\n\n"
            "## Recently landed\n")
    out = io.StringIO()
    rc = _import(module, text, _scratch(tmp_path), out=out)
    assert rc == 65
    assert "refused" in out.getvalue()
    assert "entry outside both sections" in out.getvalue()


def test_seed_drift_refuses_import(module, tmp_path):
    text = _ledger(
        "- **#9** — a clean open entry · P1 · task · origin: **human**\n", 5)
    out = io.StringIO()
    rc = _import(module, text, _scratch(tmp_path), out=out)
    assert rc == 65
    assert "refused" in out.getvalue() and "seed" in out.getvalue()


def test_import_leaves_no_db_on_refusal(module, tmp_path):
    text = _ledger(
        "- **#5** — twin one · P1 · task · origin: **human**\n\n"
        "- **#5** — twin two · P1 · task · origin: **loop**\n", 6)
    db = _scratch(tmp_path)
    assert _import(module, text, db) == 65
    assert not Path(db).exists(), "a refused import must not create the DB"


def test_dreamwork_target_refused(module, tmp_path):
    db = str(tmp_path / ".dreamwork" / "ledger.sqlite3")
    out = io.StringIO()
    rc = _import(module, FIXTURE, db, out=out)
    assert rc == 77
    assert ".dreamwork" in out.getvalue()
    assert not Path(db).exists()


def test_import_without_to_is_usage_error(module):
    out = io.StringIO()
    with pytest.raises(SystemExit):
        module.main(["--import", "--ledger", "x.md"], out=out)


def test_import_report_prints_counts_and_seed(module, tmp_path):
    d = _derived(FIXTURE)
    derived_next = max(d["all_ids"]) + 1
    header = int(__import__("lint").NEXT_ID.search(FIXTURE).group(1))
    assert header == derived_next, "fixture's header drifted from its parser"
    out = io.StringIO()
    assert _import(module, FIXTURE, _scratch(tmp_path), out=out) == 0
    assert f"{len(d['all_ids'])} task rows" in out.getvalue()
    assert f"next id: {derived_next}" in out.getvalue()


# ---------------------------------------------------------------------------
# Live-repo acceptance — this repo's real tasks.md into a scratch DB.
# ---------------------------------------------------------------------------
def test_live_ledger_import_acceptance(module, tmp_path):
    import sqlite3 as sq
    text = LIVE_LEDGER.read_text()
    # Precondition: the frozen ledger genuinely has its groomed-id shape —
    # the headless rule is what this acceptance exercises, so assert it has
    # the two sections and at least one section id with no entry head.
    assert "## Open" in text, (
        "LIVE_LEDGER must be the frozen ledger, not the shim")
    d = _derived(text)
    a = module.build_analysis(text, ledger_path=str(LIVE_LEDGER))
    headless = {c["id"] for c in
                a["conflicts"].get("section id without an entry", [])}
    entries_ids = {i for ids, _ in d["entries"] for i in ids}
    assert headless and headless.isdisjoint(entries_ids), (
        "live ledger lost its groomed-id shape — revisit the headless rule")
    db = _scratch(tmp_path)
    out = io.StringIO()
    rc = module.main(["--import", "--ledger", str(LIVE_LEDGER),
                      "--to", db], out=out)
    assert rc == 0, out.getvalue()
    conn = sq.connect(f"file:{db}?mode=ro", uri=True)
    rows = conn.execute("SELECT id, state FROM task").fetchall()
    assert len(rows) == len(entries_ids)
    assert {r[0] for r in rows} == entries_ids
    # The band resolutions, derived from the dry-run's own conflict list.
    compounds = {c["id"] for c in
                 a["conflicts"].get("band outside closed set", [])}
    bandless = {c["id"] for c in
                a["conflicts"].get("missing band (P2 by contract)", [])}
    assert len(compounds) >= 3 and len(bandless) >= 18, (
        "live ledger's known conflict floors moved — re-derive expectations")
    for (i,) in conn.execute("SELECT id FROM task WHERE priority_uncertain=1"):
        assert i in compounds, f"#{i} uncertain without a compound report"
    for i in compounds:
        assert conn.execute("SELECT priority FROM task WHERE id=?",
                            (i,)).fetchone()[0] == "P1"
    for i in bandless:
        assert conn.execute("SELECT priority FROM task WHERE id=?",
                            (i,)).fetchone()[0] == "P2"
    # Groomed ids: no rows; the sequence still seeds at the ledger's next id.
    assert not conn.execute(
        f"SELECT 1 FROM task WHERE id IN ({','.join(map(str, headless))})"
    ).fetchone()
    seq = conn.execute("SELECT seq FROM sqlite_sequence WHERE name='task'"
                       ).fetchone()[0]
    assert seq + 1 == a["seed"]["seed"]


def test_live_groomed_stub_row_fails_verify(module, tmp_path):
    """A fabricated stub for a groomed id is the exact bug the headless rule
    exists to catch — inject one, verify must refuse it by name."""
    text = LIVE_LEDGER.read_text()
    assert "## Open" in text, (
        "LIVE_LEDGER must be the frozen ledger, not the shim")
    a = module.build_analysis(text, ledger_path=str(LIVE_LEDGER))
    headless = sorted(c["id"] for c in
                      a["conflicts"].get("section id without an entry", []))
    assert headless, "live ledger lost its groomed ids — test has no anchor"
    db = _scratch(tmp_path)
    assert module.main(["--import", "--ledger", str(LIVE_LEDGER),
                        "--to", db], out=io.StringIO()) == 0
    _tamper(db, "INSERT INTO task(id, state, title, body) "
                "VALUES (?, 'landed', 'stub', 'stub')", (headless[0],))
    rc, out = _verify(module, text, db)
    assert rc == 65
    assert f"task #{headless[0]}: groomed id has a row" in out
