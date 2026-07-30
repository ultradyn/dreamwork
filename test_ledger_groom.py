"""#558 — the groom verb (red-first).

The ``groom`` verb in ``dev/ledger.py`` backfills the store's NULL origins
to ``'unknown'`` — the value ``lint.check_task_origins`` names as the
truthful origin of a task filed before the #213 origin contract. The store
CHECK constraint admits it::

    origin TEXT CHECK (origin IS NULL OR origin IN ('human','loop','unknown'))
                                                  (ledger_store.py:262)

It reports the count, is idempotent, refuses markdown-mode with a named
reason (the origin lives in entry TEXT there — a text rewrite is a
different act), and reuses ``emit_warnings`` like every other verb.

EXPECTATIONS ARE DERIVED AT RUNTIME: the NULL-origin count and the
set-origin count both come from a direct read of the scratch store (the
source the verb reads), never a literal tuned to today's fixture — the
companion rule. Each test names the PRODUCTION LINE its red-proof targets;
the red-proof was run: the line was sabotaged (``cp`` backup, never
``git checkout``), the named test went red, the source was restored
byte-identical (``cmp``). A green red-run would be a finding reported,
never a relief.
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import re
import sqlite3
from pathlib import Path

import pytest

import ledger_parse
import ledger_store

REPO = Path(__file__).resolve().parent
MIGRATE_CLI = REPO / "ud-dw-tasks-migrate"


def _load_migrate():
    """Load the extensionless migrate CLI via SourceFileLoader."""
    loader = importlib.machinery.SourceFileLoader(
        "ud_dw_tasks_migrate_558", str(MIGRATE_CLI))
    spec = importlib.util.spec_from_loader("ud_dw_tasks_migrate_558", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _load_dev_ledger():
    """Load dev/ledger.py as a module (it lives in dev/, not the root)."""
    loader = importlib.machinery.SourceFileLoader(
        "dev_ledger_groom_558", str(REPO / "dev" / "ledger.py"))
    spec = importlib.util.spec_from_loader("dev_ledger_groom_558", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture
def migrate():
    return _load_migrate()


@pytest.fixture
def dev_ledger():
    return _load_dev_ledger()


# Fixture ledger — 3 open / 2 landed, mixed type so the untyped count is
# non-zero (the footer test depends on it). All ids < 216, so the migrate
# import gives every row a NULL origin (pre-cutoff, never recorded). The
# tests then SET a known subset non-NULL so the backfill has a real MIX to
# act on, with both counts derived from the store at runtime.
LEDGER = """# Task ledger

Next id: **16**

## Open

- **#10** — first open task · P1 · task · origin: **human**

- **#12** — second open task · P2 · bug · origin: **loop**

- **#15** — third open no-type · P3 · origin: **human**

## Recently landed

- **#11** — a landed task · P0 · task · origin: **human** (abc1234)

- **#13** — another landed · P2 · idea · origin: **loop**
"""


def _write_watermark(db_path, ts="2026-07-29T00:00:00Z"):
    """Write the one-way cutover watermark into a scratch store's meta table."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO meta (key, value) VALUES ('ledger_cut_over', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (ts,))
    conn.commit()
    conn.close()


def _setup_store(migrate, dw_dir):
    """Import LEDGER into a watermarked scratch store.

    Mirrors ``test_ledger_cli._setup_store``: open_store + the migrate
    module's ``_populate_store``. The import rule gives every row a NULL
    origin (all ids < 216), so the store starts all-NULL and the tests SET
    a known subset to build the mix.
    """
    db_path = dw_dir / ledger_parse.STORE_FILENAME
    analysis = migrate.build_analysis(
        LEDGER, ledger_path=str(dw_dir / "tasks.md"))
    store = ledger_store.open_store(str(db_path), ledger_text=LEDGER)
    try:
        migrate._populate_store(store.conn, LEDGER, analysis)
    finally:
        store.close()
    _write_watermark(db_path)
    return db_path


def _store_dw(migrate, tmp, name="dw"):
    """A scratch .dreamwork/ dir with the store imported from LEDGER."""
    dw = tmp / name
    dw.mkdir()
    (dw / "tasks.md").write_text(LEDGER)
    _setup_store(migrate, dw)
    return dw


def _set_origins(db_path, values):
    """Set origin for the given {id: value} pairs; pass None to NULL it.

    The migrate import populates origins from the markers (human/loop), so a
    fresh store starts all-SET. The tests NULL a known subset to build the
    MIX groom backfills — the column state the #357 footer counts as
    ``missing origin``.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        for tid, val in values.items():
            conn.execute("UPDATE task SET origin=? WHERE id=?", (val, tid))
        conn.commit()
    finally:
        conn.close()


def _null_origin_ids(db_path):
    """The ids whose origin is NULL — the rows groom must flip to 'unknown'."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return [r[0] for r in conn.execute(
            "SELECT id FROM task WHERE origin IS NULL ORDER BY id")]
    finally:
        conn.close()


def _all_ids(db_path):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return [r[0] for r in conn.execute("SELECT id FROM task ORDER BY id")]
    finally:
        conn.close()


def _origin_of(db_path, tid):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return conn.execute(
            "SELECT origin FROM task WHERE id=?", (tid,)).fetchone()[0]
    finally:
        conn.close()


def _untyped_count(db_path):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM task WHERE type IS NULL").fetchone()[0]
    finally:
        conn.close()


def _run(dev_ledger, argv):
    """Run the CLI in-process; return (rc, stdout, stderr) as strings.

    Catches SystemExit (argparse's invalid-command exit) so a red run is a
    clean assertion failure, not a crash — the born-red state before the
    verb exists reads as rc=2, not a stack trace.
    """
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = dev_ledger.main(argv)
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


# ===========================================================================
# backfill count — groom reports the NULL-origin count and flips them all
# ===========================================================================

def test_groom_backfills_null_origins_and_reports_count(migrate, dev_ledger, tmp_path):
    """groom reports how many NULL origins it backfilled to ``'unknown'``.

    PRODUCTION LINE (red-proof target): the ``WHERE origin IS NULL`` clause
    in the verb's UPDATE. RED: make it a no-op (``WHERE 0``) and groom
    reports 0 while the store still holds NULL origins.
    """
    dw = _store_dw(migrate, tmp_path)
    db = dw / ledger_parse.STORE_FILENAME

    # NULL a known subset so the backfill has a MIX. The migrate import
    # populates every origin from its marker, so a fresh store is all-SET;
    # NULLing a subset builds the column state groom backfills while the
    # rest stay as their truthful claims (human/loop).
    ids = _all_ids(db)
    _set_origins(db, {tid: None for tid in ids[2:]})  # NULL all but first two

    # Derived precondition (the companion rule): a genuine MIX — both NULL
    # and set origins exist, and the NULL count is non-trivial.
    null_ids = _null_origin_ids(db)
    assert null_ids, "precondition: fixture must have NULL origins to backfill"
    assert len(null_ids) < len(ids), (
        "precondition: fixture must have a MIX so the backfill is selective")

    rc, out, _ = _run(dev_ledger, ["groom", "--ledger", str(dw / "tasks.md")])
    assert rc == 0, f"groom must exit 0, got {rc}"

    # The reported count equals the NULL count derived from the store
    # (the rows the UPDATE's WHERE matched).
    m = re.search(r"backfilled (\d+)", out)
    assert m is not None, f"groom must report the backfill count: {out!r}"
    assert int(m.group(1)) == len(null_ids), (
        f"groom reported {m.group(1)} backfills, expected {len(null_ids)} "
        f"(the NULL-origin count derived from the store)")

    # After: zero NULL origins remain — every one was flipped to 'unknown'.
    assert not _null_origin_ids(db), (
        "groom must leave no NULL origin behind")

    # And every previously-NULL origin is now exactly 'unknown' (the truthful
    # value lint.check_task_origins names), not some other guess.
    for tid in null_ids:
        assert _origin_of(db, tid) == "unknown", (
            f"#{tid} must be 'unknown' after groom, got {_origin_of(db, tid)!r}")

    # The SET origins were NOT touched (still their imported claim — a
    # backfill of the NULL-only set leaves existing claims alone). The kept
    # set is derived from the store (the complement of the NULL ids).
    kept = [i for i in ids if i not in null_ids]
    assert kept, "precondition: some origins were set before groom (the mix)"
    for tid in kept:
        assert _origin_of(db, tid) != "unknown", (
            f"#{tid} was set before groom and must NOT be overwritten to "
            f"'unknown'; got {_origin_of(db, tid)!r}")
        assert _origin_of(db, tid) is not None, (
            f"#{tid} set origin must stay set, got NULL")


# ===========================================================================
# idempotency — a second run changes 0 rows
# ===========================================================================

def test_groom_is_idempotent_second_run_changes_zero(migrate, dev_ledger, tmp_path):
    """A second groom run reports 0 — no NULL origin remains to backfill.

    PRODUCTION LINE (red-proof target): the ``WHERE origin IS NULL`` clause.
    After the first run flips every NULL to ``'unknown'``, the clause
    matches nothing, so ``rowcount`` is 0. RED: a verb that backfilled
    unconditionally (dropping the WHERE) would report the same count twice.
    """
    dw = _store_dw(migrate, tmp_path)
    db = dw / ledger_parse.STORE_FILENAME

    # NULL a subset so the first run has real work (the import leaves every
    # origin set; NULLing builds the backfillable column state).
    _set_origins(db, {tid: None for tid in _all_ids(db)[2:]})

    null_before = _null_origin_ids(db)
    assert null_before, "precondition: NULL origins exist before groom"

    # First run: backfills every NULL origin (len(null_before) rows).
    rc1, out1, _ = _run(dev_ledger, ["groom", "--ledger", str(dw / "tasks.md")])
    assert rc1 == 0
    m1 = re.search(r"backfilled (\d+)", out1)
    assert m1 is not None and int(m1.group(1)) == len(null_before), (
        f"first groom: {out1!r}")

    # Precondition (derived): no NULL origin remains — the first run worked.
    assert not _null_origin_ids(db), (
        "precondition: first groom must clear all NULL origins")

    # Second run: reports 0 — the WHERE matches nothing now.
    rc2, out2, _ = _run(dev_ledger, ["groom", "--ledger", str(dw / "tasks.md")])
    assert rc2 == 0, f"second groom must exit 0, got {rc2}"
    m2 = re.search(r"backfilled (\d+)", out2)
    assert m2 is not None and int(m2.group(1)) == 0, (
        f"second groom must report 0 backfills (idempotent): {out2!r}")
    assert not _null_origin_ids(db), "second groom must change nothing"


# ===========================================================================
# markdown-mode refusal — origin is a store column, not markdown text
# ===========================================================================

def test_groom_refuses_markdown_mode_with_named_reason(migrate, dev_ledger, tmp_path):
    """groom refuses in markdown mode — origin is a store concept, not text.

    PRODUCTION LINE (red-proof target): the ``if source_of_truth(dw_dir) !=
    'store'`` gate in ``_verb_groom``. RED: delete the gate and a
    markdown-mode groom reaches a store open that has no store to open.

    The decision (recorded in the verb docstring): markdown's origin is a
    TEXT claim an entry makes (``origin: **human**``), classified by
    ``classify_origin`` — there is no ``origin`` COLUMN to backfill, and a
    markdown groom would be a text rewrite (inserting ``origin: **unknown**``
    into entry bodies), a fundamentally different act. ``check_task_origins``
    already enforces governed entries carry exactly one marker.
    """
    dw = tmp_path / "md"
    dw.mkdir()
    (dw / "tasks.md").write_text(LEDGER)
    # No watermark → markdown mode (and no store file at all).
    assert ledger_parse.source_of_truth(str(dw)) == "markdown", (
        "precondition: this scratch dir is markdown mode")

    rc, out, err = _run(dev_ledger, ["groom", "--ledger", str(dw / "tasks.md")])
    assert rc != 0, f"markdown-mode groom must exit non-zero, got {rc}"
    assert "origin" in err.lower(), (
        f"refusal must name the reason (origin is not a markdown concept): "
        f"{err!r}")
    assert out == "", f"markdown-mode groom must write no stdout: {out!r}"
    # Nothing was created (markdown mode has no store to mutate).
    assert not (dw / ledger_parse.STORE_FILENAME).exists(), (
        "markdown-mode groom must not create a store")


# ===========================================================================
# the footer still prints — groom reuses emit_warnings like every verb
# ===========================================================================

def test_groom_emits_the_warning_footer(migrate, dev_ledger, tmp_path):
    """groom tacks the warning footer onto stderr like every other verb.

    PRODUCTION LINE (red-proof target): the ``emit_warnings`` call in
    ``main()``'s tail (the one every verb rides). After groom clears the
    missing-origin count to 0, the footer still emits if another count is
    non-zero — here the untyped count (NULL ``type`` rows), which groom
    does NOT touch (#558 is origin-only; types are per-task judgment).

    Precondition (derived): the fixture has untyped rows so the footer
    genuinely emits after groom (missing-origin -> 0, untyped > 0). Without
    it the footer is silent and the assertion vacuous.
    """
    dw = _store_dw(migrate, tmp_path)
    db = dw / ledger_parse.STORE_FILENAME

    # NULL a subset so groom does REAL work before the footer reads the
    # post-groom state — without this, missing-origin is already 0 at import
    # and the "missing origin absent" assertion is vacuous.
    _set_origins(db, {tid: None for tid in _all_ids(db)[2:]})
    assert _null_origin_ids(db), (
        "precondition: NULL origins exist so groom genuinely backfills")

    # Derived precondition: untyped rows exist so the footer emits AFTER
    # groom clears the missing-origin count. #15 is "no-type" in the fixture.
    assert _untyped_count(db) > 0, (
        "precondition: fixture must have untyped rows so the footer emits")

    rc, out, err = _run(dev_ledger, ["groom", "--ledger", str(dw / "tasks.md")])
    assert rc == 0

    assert "warnings:" in err, (
        f"groom must carry the footer on stderr like every verb: {err!r}")
    # missing origin is now absent (0) — the very count groom cleared.
    assert "missing origin" not in err, (
        "groom cleared the missing-origin count, so it must be absent "
        f"from the footer: {err!r}")
    # The untyped count rides the footer (groom does not touch types).
    assert "untyped" in err, (
        f"the untyped count must ride the footer (groom is origin-only): "
        f"{err!r}")
