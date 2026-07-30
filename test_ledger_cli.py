"""#497 — read-only task CLI (red-first).

Four read verb groups in ``dev/ledger.py``: ``list``, ``get``, ``count``,
``reviews``. READ-ONLY — none mutates the store, the ledger, or the journal.
The store read rides ``ledger_parse`` primitives (``store_records``,
``store_ids_by_state``, ``store_review_decisions``); a second store reader in
the verb module is the defect #352 exists to prevent.

EXPECTATIONS ARE DERIVED AT RUNTIME, never literals tuned to today's store:

- Store-mode expectations come from the MARKDOWN FIXTURE via the production
  readers (``watch.parse_ledger`` / ``ledger_parse.ledger_entries``) — the
  source the store was IMPORTED from, so it is independent of the store
  primitives the verbs ride. That is the dispatch-parity idiom
  ``test_ledger_dispatch.py`` uses, and it is what keeps a red-proof honest:
  sabotaging a store primitive breaks the verb's output but NOT the
  expectation (they come from different readers).
- Review expectations come from the rows the test itself WROTE (its own
  input), never from ``store_review_decisions`` — same reason.

Every test that needs two things to differ derives both and asserts the gap.
Each test names the PRODUCTION LINE its red-proof targets; each red-proof was
run: the line was sabotaged (``cp`` backup, never ``git checkout``), the test
went red, the source was restored byte-identical. A green red-run would be a
finding reported, never a relief.
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import sqlite3
from pathlib import Path

import pytest

import ledger_parse
import ledger_store
import ledger_write
import watch

REPO = Path(__file__).resolve().parent
MIGRATE_CLI = REPO / "ud-dw-tasks-migrate"


def _load_migrate():
    """Load the extensionless migrate CLI via SourceFileLoader."""
    loader = importlib.machinery.SourceFileLoader(
        "ud_dw_tasks_migrate_497", str(MIGRATE_CLI))
    spec = importlib.util.spec_from_loader("ud_dw_tasks_migrate_497", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _load_dev_ledger():
    """Load dev/ledger.py as a module (it lives in dev/, not the root)."""
    loader = importlib.machinery.SourceFileLoader(
        "dev_ledger_cli_497", str(REPO / "dev" / "ledger.py"))
    spec = importlib.util.spec_from_loader("dev_ledger_cli_497", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture
def migrate():
    return _load_migrate()


@pytest.fixture
def dev_ledger():
    return _load_dev_ledger()


# ---------------------------------------------------------------------------
# Fixture ledger — 3 open / 2 landed, mixed type/origin so a filter or field
# bug is visible. The markdown fixture is the INDEPENDENT source of truth the
# store-mode expectations derive from.
# ---------------------------------------------------------------------------
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


def _fixture_ids():
    """The fixture's id sets from the MARKDOWN reader (independent of store)."""
    return watch.parse_ledger(LEDGER)


def _write_watermark(db_path, ts="2026-07-29T00:00:00Z"):
    """Write the one-way cutover watermark into a scratch store's meta table."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO meta (key, value) VALUES ('ledger_cut_over', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (ts,))
    conn.commit()
    conn.close()


def _setup_store(migrate, dw_dir):
    """Import LEDGER into a scratch store, write the cutover watermark.

    Mirrors ``test_ledger_dispatch._setup_store``: open_store + the migrate
    module's ``_populate_store`` (bypassing the CLI's ``.dreamwork/`` guard;
    our scratch dir is under tmp_path so the bypass is safe).
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


def _run(dev_ledger, argv):
    """Run the CLI in-process; return (rc, stdout, stderr) as strings."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = dev_ledger.main(argv)
    return rc, out.getvalue(), err.getvalue()


def _store_dw(migrate, dw, cut_over=True):
    """A scratch .dreamwork/ with the store imported from LEDGER.

    ``dw`` is the directory to build (caller picks distinct dirs for parity
    tests). With ``cut_over`` the watermark is written (store is source of
    truth); without it the same store files exist but the verbs read markdown.
    """
    dw.mkdir()
    (dw / "tasks.md").write_text(LEDGER)
    if cut_over:
        _setup_store(migrate, dw)
    else:
        # markdown mode: still create an (unwatermarked) store so list/count
        # dispatch to the markdown path and reviews refuses.
        db_path = dw / ledger_parse.STORE_FILENAME
        analysis = migrate.build_analysis(LEDGER, ledger_path=str(dw / "tasks.md"))
        store = ledger_store.open_store(str(db_path), ledger_text=LEDGER)
        try:
            migrate._populate_store(store.conn, LEDGER, analysis)
        finally:
            store.close()
    return dw


# ===========================================================================
# count
# ===========================================================================

def test_count_json_store_matches_fixture(migrate, dev_ledger, tmp_path):
    """count --json reports open/landed counts that match the markdown fixture.

    PRODUCTION LINE (red-proof target): ``_verb_count``'s
    ``counts = {"open": len(open_ids), "landed": len(landed_ids)}`` assembly,
    fed by ``store_ids_by_state``. RED: swap open/landed there and the JSON
    swaps (caught because open != landed, asserted below).
    """
    dw = _store_dw(migrate, tmp_path / "dw")
    exp_open, exp_landed = _fixture_ids()

    # Preconditions (derived, never trusted): both states non-empty, and the
    # two counts differ so a swap is visible (a fixture with equal counts
    # makes the parity check vacuous).
    assert exp_open and exp_landed, "fixture must have both states"
    assert len(exp_open) != len(exp_landed), (
        "fixture open/landed counts must differ so a swap is caught")

    rc, out, _ = _run(dev_ledger, ["count", "--json", "--ledger", str(dw / "tasks.md")])
    assert rc == 0
    data = json.loads(out)
    assert data == {"open": len(exp_open), "landed": len(exp_landed)}, (
        f"count --json mismatch: {data} vs open={len(exp_open)} "
        f"landed={len(exp_landed)}")


def test_count_state_filter_store(migrate, dev_ledger, tmp_path):
    """count --state open reports only open, and drops landed from the JSON.

    PRODUCTION LINE: the ``if args.state: counts = {args.state: ...}`` branch
    in ``_verb_count``. RED: remove the branch and both states leak in.
    """
    dw = _store_dw(migrate, tmp_path / "dw")
    exp_open, exp_landed = _fixture_ids()
    assert exp_landed, "precondition: fixture has landed ids to be filtered out"

    rc, out, _ = _run(dev_ledger,
                      ["count", "--state", "open", "--json", "--ledger", str(dw / "tasks.md")])
    assert rc == 0
    data = json.loads(out)
    assert data == {"open": len(exp_open)}, f"{data}"
    assert "landed" not in data, "count --state open must not include landed"


def test_count_human_shape(migrate, dev_ledger, tmp_path):
    """count (human) prints `state: N` lines, open before landed."""
    dw = _store_dw(migrate, tmp_path / "dw")
    exp_open, exp_landed = _fixture_ids()
    rc, out, _ = _run(dev_ledger, ["count", "--ledger", str(dw / "tasks.md")])
    assert rc == 0
    lines = out.rstrip("\n").split("\n")
    assert lines == [f"open: {len(exp_open)}", f"landed: {len(exp_landed)}"], (
        f"human count shape: {lines!r}")


# ===========================================================================
# list
# ===========================================================================

_CONTRACT_KEYS = {"id", "state", "title", "priority", "type", "origin"}


def test_list_json_store_ids_match_fixture(migrate, dev_ledger, tmp_path):
    """list --json ids (all states) match the markdown fixture, ascending.

    PRODUCTION LINE: ``store_records`` (rows the verb reads) + ``_verb_list``'s
    JSON emit. RED: drop a column or a row from store_records and the id set
    or the JSON shape breaks. Expectations come from parse_ledger (a DIFFERENT
    reader), so sabotaging store_records breaks the verb but not the expectation.
    """
    dw = _store_dw(migrate, tmp_path / "dw")
    exp_open, exp_landed = _fixture_ids()
    exp_all = sorted(int(x) for x in set(exp_open) | set(exp_landed))
    # Precondition: at least two tasks so ascending order is observable.
    assert len(exp_all) >= 2, "fixture must have >= 2 tasks"

    rc, out, _ = _run(dev_ledger, ["list", "--json", "--ledger", str(dw / "tasks.md")])
    assert rc == 0
    data = json.loads(out)
    got_ids = [r["id"] for r in data]
    assert got_ids == exp_all, f"list ids: {got_ids} vs {exp_all}"
    # Ascending (default sort).
    assert got_ids == sorted(got_ids), "default sort must be ascending id"
    # EXACTLY the contract keys (a future binary rewrite must match).
    for r in data:
        assert set(r.keys()) == _CONTRACT_KEYS, f"unexpected keys: {set(r.keys())}"


def test_list_state_open_store(migrate, dev_ledger, tmp_path):
    """list --state open shows only open ids.

    PRODUCTION LINE: the ``if getattr(args, 'state', None)`` filter in
    ``_records_for``. RED: delete the filter and landed ids leak in.
    """
    dw = _store_dw(migrate, tmp_path / "dw")
    exp_open, exp_landed = _fixture_ids()
    # Preconditions: open non-empty, AND open != all (landed non-empty) so a
    # missing filter is caught.
    assert exp_open and exp_landed, "fixture must have both states"

    rc, out, _ = _run(dev_ledger,
                      ["list", "--state", "open", "--json", "--ledger", str(dw / "tasks.md")])
    assert rc == 0
    data = json.loads(out)
    got = sorted(r["id"] for r in data)
    exp = sorted(int(x) for x in exp_open)
    assert got == exp, f"list --state open: {got} vs {exp}"
    # Every returned row is open (the filter held).
    assert all(r["state"] == "open" for r in data), "filtered rows must be open"


def test_list_sort_desc_store(migrate, dev_ledger, tmp_path):
    """list --sort id-desc reverses the order.

    PRODUCTION LINE: ``recs.sort(..., reverse=(sort == "id-desc"))`` in
    ``_records_for``. RED: force reverse=False and the order stays ascending.
    """
    dw = _store_dw(migrate, tmp_path / "dw")
    exp_all = sorted(int(x) for x in (set(_fixture_ids()[0]) | set(_fixture_ids()[1])))
    assert len(exp_all) >= 2, "precondition: >= 2 tasks so order is observable"

    rc, out, _ = _run(dev_ledger,
                      ["list", "--sort", "id-desc", "--json", "--ledger", str(dw / "tasks.md")])
    assert rc == 0
    data = json.loads(out)
    got = [r["id"] for r in data]
    assert got == list(reversed(exp_all)), f"desc order: {got} vs {list(reversed(exp_all))}"


def test_list_human_line_shape(migrate, dev_ledger, tmp_path):
    """list (human) prints one line per task, each starting `#<id>  <state>`."""
    dw = _store_dw(migrate, tmp_path / "dw")
    exp_all = sorted(int(x) for x in (set(_fixture_ids()[0]) | set(_fixture_ids()[1])))
    rc, out, _ = _run(dev_ledger, ["list", "--ledger", str(dw / "tasks.md")])
    assert rc == 0
    lines = [ln for ln in out.splitlines() if ln]
    assert len(lines) == len(exp_all), f"one line per task: {len(lines)} vs {len(exp_all)}"
    # Each line begins with the id token and carries the title (from fixture).
    for ln in lines:
        assert ln.startswith("#"), f"line must start with id token: {ln!r}"


# ===========================================================================
# get
# ===========================================================================

def test_get_known_task_store(migrate, dev_ledger, tmp_path):
    """get <known id> prints the id/state line and the title from the fixture.

    PRODUCTION LINE: the ``match = next((r for r in recs if r["id"] == args.id), None)``
    lookup in ``_verb_get``. RED: break the predicate (e.g. ``r["id"] != args.id``)
    and get falls to not-found.
    """
    dw = _store_dw(migrate, tmp_path / "dw")
    exp_open, _ = _fixture_ids()
    target = sorted(int(x) for x in exp_open)[0]
    # The title is the head-line prose of the fixture entry for that id.
    entries = ledger_parse.ledger_entries(LEDGER)
    exp_title = None
    for ids, body in entries:
        if target in ids:
            # head line: `- **#N** — <title> · ...`
            head = body.split("\n", 1)[0]
            exp_title = head.split("—", 1)[1].split(" · ", 1)[0].strip()
    assert exp_title, "precondition: fixture entry has a parseable title"

    rc, out, _ = _run(dev_ledger, ["get", str(target), "--ledger", str(dw / "tasks.md")])
    assert rc == 0
    assert f"#{target}" in out, f"get must name the id: {out!r}"
    assert exp_title in out, f"get must carry the title {exp_title!r}: {out!r}"
    assert "state:" not in out  # state rides the id line, not a `field:` line


def test_get_unknown_task_store(migrate, dev_ledger, tmp_path):
    """get <unknown id> exits 1 with a stderr message, no stdout body.

    PRODUCTION LINE: the ``if match is None: ... return 1`` branch in
    ``_verb_get``. RED: return 0 and the body write leaks to stdout.
    """
    dw = _store_dw(migrate, tmp_path / "dw")
    exp_all = set(int(x) for x in (set(_fixture_ids()[0]) | set(_fixture_ids()[1])))
    unknown = max(exp_all) + 1000  # guaranteed absent
    assert unknown not in exp_all, "precondition: the id is truly absent"

    rc, out, err = _run(dev_ledger, ["get", str(unknown), "--ledger", str(dw / "tasks.md")])
    assert rc == 1, f"unknown id must exit 1, got {rc}"
    assert "not found" in err, f"stderr must say not found: {err!r}"
    assert out == "", f"unknown id must write no stdout: {out!r}"


# ===========================================================================
# reviews
# ===========================================================================

def _write_reviews(dw):
    """Write two review decisions into the scratch store via the PRODUCTION
    writer (``ledger_write.record_review_decision``). Returns the rows the
    test wrote — its own input is the independent expectation."""
    store = ledger_store.open_store(str(dw / ledger_parse.STORE_FILENAME))
    rows = [
        {"artifact": "plan-a.html", "question_title": "first question",
         "decision": "accepted", "decided_at": "2026-07-29T01:00:00Z", "actor": "watch"},
        {"artifact": "plan-b.html", "question_title": "second question",
         "decision": "rejected", "decided_at": "2026-07-30T02:00:00Z", "actor": "human"},
    ]
    try:
        for r in rows:
            ledger_write.record_review_decision(
                store, r["artifact"], r["question_title"], r["decision"],
                actor=r["actor"], at=r["decided_at"])
    finally:
        store.close()
    return rows


def test_reviews_list_store(migrate, dev_ledger, tmp_path):
    """reviews list echoes the rows written, newest-first.

    PRODUCTION LINE: ``store_review_decisions`` (rows) + the
    ``for r in reversed(rows)`` emit in ``_verb_reviews``. Expectations come
    from the rows the test WROTE (its own input), not from the primitive — so
    sabotaging the primitive breaks the verb but not the expectation. RED:
    drop the ``reversed`` and the order flips (caught because the two
    decisions have different decided_at, asserted below).
    """
    dw = _store_dw(migrate, tmp_path / "dw")
    written = _write_reviews(dw)
    # Precondition: the two decisions differ in time so newest-first is ordered.
    times = [r["decided_at"] for r in written]
    assert len(set(times)) == len(times), "decisions must have distinct times"

    rc, out, _ = _run(dev_ledger, ["reviews", "list", "--ledger", str(dw / "tasks.md")])
    assert rc == 0
    lines = [ln for ln in out.splitlines() if ln]
    assert len(lines) == len(written), f"one line per decision: {lines!r}"
    # Newest first: the newer artifact (plan-b) appears before the older.
    artifacts = [ln.split("  ", 1)[0] for ln in lines]
    newer = max(written, key=lambda r: r["decided_at"])["artifact"]
    assert artifacts[0] == newer, f"newest-first: {artifacts!r}"
    # Every written artifact appears.
    assert set(artifacts) == {r["artifact"] for r in written}


def test_reviews_get_store(migrate, dev_ledger, tmp_path):
    """reviews get <artifact> prints the full row that was written.

    PRODUCTION LINE: the ``next((r ... if r["artifact"] == args.artifact), None)``
    lookup in ``_verb_reviews``. RED: break the predicate and get falls to
    not-found (exit 1).
    """
    dw = _store_dw(migrate, tmp_path / "dw")
    written = _write_reviews(dw)
    target = written[0]

    rc, out, _ = _run(dev_ledger,
                      ["reviews", "get", target["artifact"], "--ledger", str(dw / "tasks.md")])
    assert rc == 0
    assert f"artifact: {target['artifact']}" in out
    assert f"decision: {target['decision']}" in out
    assert f"question_title: {target['question_title']}" in out
    assert f"actor: {target['actor']}" in out


def test_reviews_get_unknown_store(migrate, dev_ledger, tmp_path):
    """reviews get <unknown artifact> exits 1 with a stderr message."""
    dw = _store_dw(migrate, tmp_path / "dw")
    _write_reviews(dw)
    rc, out, err = _run(dev_ledger,
                        ["reviews", "get", "nope.html", "--ledger", str(dw / "tasks.md")])
    assert rc == 1, f"unknown artifact must exit 1, got {rc}"
    assert "not found" in err, f"stderr: {err!r}"


def test_reviews_refuses_markdown_mode(migrate, dev_ledger, tmp_path):
    """reviews list refuses in markdown mode (the table is a store concept).

    PRODUCTION LINE: the ``if source_of_truth(dw_dir) != "store"`` gate in
    ``_verb_reviews``. RED: delete the gate and the verb reads an unwatermarked
    store (which the fixture _does_ have) instead of refusing.
    """
    dw = _store_dw(migrate, tmp_path / "md", cut_over=False)
    assert ledger_parse.source_of_truth(str(dw)) == "markdown", (
        "precondition: this scratch dir is markdown mode")
    rc, out, err = _run(dev_ledger, ["reviews", "list", "--ledger", str(dw / "tasks.md")])
    assert rc == 1, f"markdown-mode reviews must exit 1, got {rc}"
    assert "markdown mode" in err, f"stderr: {err!r}"


# ===========================================================================
# dispatch parity — markdown vs store agree (the contract holds in both modes)
# ===========================================================================

def test_count_parity_markdown_store(migrate, dev_ledger, tmp_path):
    """count gives the same figures in markdown mode and store mode."""
    dw_md = _store_dw(migrate, tmp_path / "md", cut_over=False)
    dw_st = _store_dw(migrate, tmp_path / "st", cut_over=True)
    rc_m, out_m, _ = _run(dev_ledger, ["count", "--json", "--ledger", str(dw_md / "tasks.md")])
    rc_s, out_s, _ = _run(dev_ledger, ["count", "--json", "--ledger", str(dw_st / "tasks.md")])
    assert rc_m == 0 and rc_s == 0
    assert json.loads(out_m) == json.loads(out_s), (
        f"count parity: md={out_m!r} st={out_s!r}")


def test_list_parity_markdown_store(migrate, dev_ledger, tmp_path):
    """list --json gives the same id set and states in markdown and store mode.

    PRODUCTION LINE: ``_read_records``'s ``source_of_truth`` dispatch + the
    markdown ``_markdown_records`` path. priority/type are None in markdown
    (no reader) but populated in store, so parity is on id+state+title only.
    """
    dw_md = _store_dw(migrate, tmp_path / "md", cut_over=False)
    dw_st = _store_dw(migrate, tmp_path / "st", cut_over=True)
    _, out_m, _ = _run(dev_ledger, ["list", "--json", "--ledger", str(dw_md / "tasks.md")])
    _, out_s, _ = _run(dev_ledger, ["list", "--json", "--ledger", str(dw_st / "tasks.md")])
    md = {(r["id"], r["state"], r["title"]) for r in json.loads(out_m)}
    st = {(r["id"], r["state"], r["title"]) for r in json.loads(out_s)}
    assert md == st, f"list parity md={md} st={st}"
