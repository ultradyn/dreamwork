"""ud-dw-tasks-migrate --import/--verify — #294 increment 4, exercised.

Imports the parsed ledger into the flat schema at a SCRATCH path (never
.dreamwork/) and re-verifies the scratch DB row-for-row against the parse.

Every expectation is DERIVED from the production parsers at runtime (the
same discipline as test_tasks_migrate.py): where no production reader
exists for a field (bands, types are prose `·`-fields — #346), the
test-side scan is bound to the production branch by red-proof, recorded in
the final report. A fixture that lost its injected shape would let a check
pass over nothing, so each derivation is asserted non-empty first.

The tampered-DB tests are the ones that prove verification can FAIL: they
assert the failure NAMES the row, so a verify that prints a bare "mismatch"
cannot pass.
"""

import hashlib
import importlib.machinery
import importlib.util
import io
import re
import sqlite3
from collections import Counter
from pathlib import Path

import pytest

import ledger_parse
import lint

REPO = Path(__file__).resolve().parent
CLI = REPO / "ud-dw-tasks-migrate"
LIVE_LEDGER = REPO / ".dreamwork" / "tasks.md"


def _load_cli():
    loader = importlib.machinery.SourceFileLoader("ud_dw_tasks_migrate", str(CLI))
    spec = importlib.util.spec_from_loader("ud_dw_tasks_migrate", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture
def module():
    return _load_cli()


# ---------------------------------------------------------------------------
# Importable fixture — every LEGAL shape (compound/bolded/missing/out-of-set
# band, pre-216 unmarked origin, out-of-vocabulary origin, dangling related,
# combined entry, human blocked-on field) and NONE of the fatal ones (no
# duplicate ids, no strays, no id-less heads). Next id == MAX(id)+1.
# ---------------------------------------------------------------------------
FIXTURE = """# Task ledger

Next id: **112**

## Open

- **#100** — a pre-216 entry with no origin and no band at all

- **#101** — a clean open entry · P1 · idea · origin: **human**
  with a cross-ref to #102 that is only a reference.

- **#102** — a compound-band entry · P0/P1 · bug · origin: **loop**

- **#103** — a bandless entry · task · origin: **human**

- **#104** — a wholly-bolded band field · **P3** · feature · origin: **loop**

- **#105** — an out-of-band entry · P4 · chore · origin: **human**

- **#106** — relates and blocks · P2 · design · origin: **human**
  · related: **#101, #999** · blocked on #102 until it lands

- **#107/#108** — a combined entry · P2 · reliability · origin: **loop**

- **#109** — an out-of-vocabulary origin · P2 · task · origin: **robot**

## Recently landed

- **#110** — a clean landed entry · P0 · implementation · origin: **human** (abc1234)
  · blocked-on: **human** while he ruled

- **#111** — a landed entry relating back · P1 · idea · origin: **loop** (def5678)
  · related: **#101**
"""

KNOWN_TYPES = {"idea", "task", "bug", "chore", "feature", "design",
               "implementation", "reliability"}
BAND_FIELD = re.compile(r"^P\d+(/P\d+)*$")
CLOSED_BANDS = {"P0", "P1", "P2", "P3"}


def _band_fields(body: str) -> list[str]:
    out = []
    for frag in body.split("·"):
        f = frag.strip()
        m = re.match(r"^\*\*(.+?)\*\*$", f)
        if m:
            f = m.group(1).strip()
        if BAND_FIELD.match(f):
            out.append(f)
    return out


def _derived(text: str) -> dict:
    """Every expectation, derived from the production parsers at runtime."""
    watch = lint.load_watch()
    assert watch is not None, "watch.py unimportable — the parsers are the fixture"
    open_raw, landed_raw = watch.parse_ledger(text)
    entries = ledger_parse.ledger_entries(text)
    open_ids = {int(x) for x in open_raw}
    landed_ids = {int(x) for x in landed_raw}
    per_id = {}
    for ids, body in entries:
        for i in ids:
            assert i not in per_id, "fixture gained a duplicate id — not importable"
            per_id[i] = body
    return {
        "open": open_ids,
        "landed": landed_ids,
        "entries": entries,
        "per_id": per_id,
        "all_ids": open_ids | landed_ids,
        "digests": {i: hashlib.sha256(b.encode()).hexdigest()
                    for i, b in per_id.items()},
    }


def _scratch(tmp_path, name="scratch.sqlite3") -> str:
    return str(tmp_path / name)


def _db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _import(module, text: str, db: str, out=None) -> int:
    import tempfile
    p = Path(tempfile.mkdtemp()) / "tasks.md"
    p.write_text(text)
    return module.main(["--import", "--ledger", str(p), "--to", db],
                       out=out or io.StringIO())


# ---------------------------------------------------------------------------
# Population — one task row per id, every column from the parse.
# ---------------------------------------------------------------------------
def test_import_populates_one_row_per_id(module, tmp_path):
    d = _derived(FIXTURE)
    assert d["open"] and d["landed"], "fixture lost its two sections"
    db = _scratch(tmp_path)
    assert _import(module, FIXTURE, db) == 0
    rows = _db(db).execute("SELECT id, state FROM task").fetchall()
    assert Counter(r["state"] for r in rows) == Counter(
        {"open": len(d["open"]), "landed": len(d["landed"])})
    assert {r["id"] for r in rows} == d["all_ids"]
    assert len(rows) == len(d["all_ids"]), "an id was lost or duplicated"


def test_import_stores_verbatim_body_and_digest(module, tmp_path):
    d = _derived(FIXTURE)
    db = _scratch(tmp_path)
    assert _import(module, FIXTURE, db) == 0
    conn = _db(db)
    for i, body in d["per_id"].items():
        row = conn.execute("SELECT body, body_digest FROM task WHERE id=?",
                           (i,)).fetchone()
        assert row is not None, f"#{i} missing"
        assert row["body"] == body, f"#{i} body not verbatim"
        assert row["body_digest"] == d["digests"][i], f"#{i} digest mismatch"


def test_import_band_resolutions(module, tmp_path):
    d = _derived(FIXTURE)
    compound = {ids[0] for ids, body in d["entries"]
                if len(ids) == 1 and any("/" in b for b in _band_fields(body))}
    out_of_band = {ids[0] for ids, body in d["entries"]
                   if any(b not in CLOSED_BANDS and "/" not in b
                          for b in _band_fields(body))}
    bandless = {ids[0] for ids, body in d["entries"]
                if len(ids) == 1 and not _band_fields(body)}
    assert compound and out_of_band and bandless, (
        "fixture lost a band shape — the resolution check would pass over nothing")
    db = _scratch(tmp_path)
    assert _import(module, FIXTURE, db) == 0
    conn = _db(db)
    for i in compound:
        r = conn.execute("SELECT priority, priority_uncertain FROM task "
                         "WHERE id=?", (i,)).fetchone()
        assert (r["priority"], r["priority_uncertain"]) == ("P1", 1), (
            f"#{i} compound must import as the LOWER band + uncertain (S2)")
    for i in bandless:
        r = conn.execute("SELECT priority, priority_uncertain FROM task "
                         "WHERE id=?", (i,)).fetchone()
        assert (r["priority"], r["priority_uncertain"]) == ("P2", 0), (
            f"#{i} missing band imports as P2 by contract")
    for i in out_of_band:
        r = conn.execute("SELECT priority FROM task WHERE id=?", (i,)).fetchone()
        assert r["priority"] is None, (
            f"#{i} out-of-set band must import NULL, never a guessed band")
