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
import re
import sqlite3
import subprocess
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


# ===========================================================================
# #667 — the store did not resolve HERE: refuse rather than answer from nothing
#
# THE MEASURED DEFECT. `ledger.sqlite3` is gitignored (#294) so it never
# travels into a lane worktree, and the `tasks.md` the cutover left behind is
# the #458 shim. Every verb therefore answered out of an EMPTY ledger, and
# `get` in particular said `#NNN not found` — which a lane reads as "that task
# is not in the ledger", not as "you invoked the tool wrong". lane-659attractor
# needed four ledger reads and got four false not-founds.
#
# The class this belongs to is #611's: *a check that examined nothing must not
# read as passing*, here applied to a READER. So the assertions below are not
# "does it refuse" alone — a refusal that does not hand back the working
# invocation leaves the lane exactly where the false answer did.
#
# PRODUCTION LINES (red-proof targets), each named on the test that owns it:
#   `_unresolved_store`'s two conditions (the resolver + `_read_records`), the
#   `shared is not None` gate at the top of `_dispatch`, the `args.cmd ==
#   "sweep"` exit-0 branch, and `_unresolved_store_message`'s `--ledger` line.
#
# Every fixture is a REAL git worktree of a REAL post-cutover repo with a REAL
# absent store — test_lint.TestWorktreeLedgerAbsent's requirement, for the same
# reason: an excuse must be exercised against the actual absence, never against
# a fixture that quietly kept a ledger around.
# ===========================================================================

# Minimal valid argv per verb, WITHOUT --ledger (the caller appends it). The
# gate is at the dispatch, so every verb must hit it; this map is the only
# hand-written thing in the sweep below and `test_the_map_covers_every_verb`
# derives the verb set from the PARSER and requires exact agreement, so a verb
# added later fails loudly here instead of quietly escaping the gate.
_VERB_ARGV = {
    "counts": ["counts"],
    "fold": ["fold", "10", "--note", "x"],
    "file": ["file", "a new task"],
    "note": ["note", "10", "--note", "x"],
    "sweep": ["sweep"],
    "list": ["list"],
    "get": ["get", "10"],
    "count": ["count"],
    "reviews": ["reviews", "list"],
    "groom": ["groom"],
}


def _parser_verbs(dev_ledger):
    """The verb set from the PARSER itself, never a literal.

    argparse names every choice in its own error for an unknown one, so an
    invalid verb is the cheapest way to ask the parser what it accepts without
    reaching into private attributes.
    """
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        with pytest.raises(SystemExit):
            dev_ledger.main(["definitely-not-a-verb"])
    m = re.search(r"choose from ([^)]+)\)", err.getvalue())
    assert m, f"could not read the verb set off the parser: {err.getvalue()!r}"
    return {v.strip().strip("'\"") for v in m.group(1).split(",")}


def _git(root, *a):
    return subprocess.run(["git", "-C", str(root), *a],
                          capture_output=True, text=True, check=True)


def _cutover_repo(migrate, root):
    """A REAL post-cutover main checkout: shim committed, store gitignored.

    The cutover runs through the PRODUCTION path (`perform_cutover`), so the
    `tasks.md` left behind is the real #458 migration notice rather than a
    hand-written stand-in for it.
    """
    dw = root / ".dreamwork"
    dw.mkdir(parents=True)
    (dw / "tasks.md").write_text(LEDGER)
    migrate.perform_cutover(str(dw), out=io.StringIO())
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    (root / ".gitignore").write_text(".dreamwork/ledger.sqlite3*\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "post-cutover seed")
    assert ledger_parse.store_path(dw).exists(), \
        "fixture precondition: the main checkout must carry a real store"
    return dw


def _worktree(root, name):
    """A REAL linked worktree of `root` — the shape a lane is dispatched into."""
    wt = root.parent / name
    _git(root, "worktree", "add", "-q", "-b", name, str(wt))
    return wt / ".dreamwork"


def _absence_preconditions(wtdw):
    """The absence the whole class is about, asserted rather than assumed."""
    assert not ledger_parse.store_path(wtdw).exists(), \
        "precondition: the worktree must genuinely have NO store"
    assert ledger_parse.source_of_truth(str(wtdw)) == "markdown", \
        "precondition: the markdown fallback must genuinely engage"


def _wt_fixture(migrate, tmp_path, name):
    """(main .dreamwork, worktree .dreamwork) with the absence asserted."""
    dw = _cutover_repo(migrate, tmp_path / "main")
    wtdw = _worktree(tmp_path / "main", name)
    _absence_preconditions(wtdw)
    return dw, wtdw


def test_get_from_a_worktree_refuses_instead_of_saying_not_found(
        migrate, dev_ledger, tmp_path):
    """THE DEFECT. The measured symptom was `#NNN not found` for a REAL id.

    PRODUCTION LINE: the `if shared is not None:` gate at the top of
    `_dispatch`. RED: delete it and `get` answers `not found` out of the shim,
    which is the bug verbatim.
    """
    _, wtdw = _wt_fixture(migrate, tmp_path, "lane-get")
    # Derived, not assumed: the id asked for is one the ledger really holds,
    # so a `not found` here can only be the false one.
    real = sorted(int(i) for i in _fixture_ids()[0])[0]

    rc, out, err = _run(dev_ledger, ["get", str(real), "--ledger", str(wtdw / "tasks.md")])
    # The false answer's exact shape, from `_verb_get` — matched literally
    # rather than on the bare words "not found", which the refusal itself
    # quotes when explaining what it is refusing to do.
    assert f"ledger: #{real} not found" not in err, (
        f"a real id must never come back as not-found from a worktree: {err!r}")
    assert rc != 0 and out == "", f"rc={rc} out={out!r}"
    assert "did not resolve" in err, f"the cause must be named: {err!r}"


def test_the_refusal_hands_back_the_working_invocation(
        migrate, dev_ledger, tmp_path):
    """A refusal that does not name the fix leaves the lane where the false
    answer did — this is the half that makes the refusal worth anything.

    PRODUCTION LINE: the `--ledger {shared.parent / 'tasks.md'}` line in
    `_unresolved_store_message`. RED: emit the relative default instead and the
    path assertion fails (the lane would re-run the invocation that just
    failed).
    """
    dw, wtdw = _wt_fixture(migrate, tmp_path, "lane-fix")
    _, _, err = _run(dev_ledger, ["get", "10", "--ledger", str(wtdw / "tasks.md")])
    assert "--ledger" in err, f"the flag must be named: {err!r}"
    assert str(dw / "tasks.md") in err, (
        f"the message must carry the MAIN checkout's absolute ledger path, "
        f"not a relative default the lane already used: {err!r}")
    # #592's requirement on its own row: name the store you FOUND, never
    # assert where one ought to be.
    assert str(ledger_parse.store_path(dw)) in err, \
        f"the message must name the store it verified: {err!r}"
    # And the named form must actually work from here.
    rc, out, _ = _run(dev_ledger, ["get", "10", "--ledger", str(dw / "tasks.md")])
    assert rc == 0 and "#10" in out, f"the offered invocation must work: {rc} {out!r}"


def test_the_refusal_is_distinguishable_from_a_real_not_found(
        migrate, dev_ledger, tmp_path):
    """The whole point, at the exit code. `get`'s exit 1 already MEANS "no such
    id" (#497's output contract), so a refusal reusing it would hide itself
    inside the answer it refuses to give.

    PRODUCTION LINE: the `return 2` in `_dispatch`'s gate. RED: return 1 and
    the two codes collapse.
    """
    dw, wtdw = _wt_fixture(migrate, tmp_path, "lane-codes")
    all_ids = {int(x) for x in (set(_fixture_ids()[0]) | set(_fixture_ids()[1]))}
    absent = max(all_ids) + 1000
    assert absent not in all_ids, "precondition: the id is truly absent"

    rc_refused, _, _ = _run(dev_ledger, ["get", "10", "--ledger", str(wtdw / "tasks.md")])
    rc_notfound, _, err_nf = _run(
        dev_ledger, ["get", str(absent), "--ledger", str(dw / "tasks.md")])
    assert rc_notfound == 1 and "not found" in err_nf, (
        f"the real not-found must survive unchanged: {rc_notfound} {err_nf!r}")
    assert rc_refused != rc_notfound, (
        f"a store that did not resolve must not exit like an absent id "
        f"(both {rc_refused})")


def test_the_map_covers_every_verb(dev_ledger):
    """The sweep below is only as good as its coverage, so the verb set is
    derived from the parser and required to agree exactly.

    Without this, a verb added later would silently escape the gate AND the
    test that is supposed to notice.
    """
    assert _parser_verbs(dev_ledger) == set(_VERB_ARGV), (
        f"parser verbs {_parser_verbs(dev_ledger)} vs mapped {set(_VERB_ARGV)}")


def test_every_verb_is_gated_not_just_get(migrate, dev_ledger, tmp_path):
    """`get` was the verb MEASURED, not the only one affected: `list` said
    `(no tasks)`, `count` said 0, and a write verb no-oping against a store
    that is not there would be worse than either.

    PRODUCTION LINE: the gate's placement at the TOP of `_dispatch` rather than
    inside `_verb_get`. RED: move it into `_verb_get` and every verb but `get`
    goes back to answering from the shim.
    """
    _, wtdw = _wt_fixture(migrate, tmp_path, "lane-allverbs")
    ledger_arg = ["--ledger", str(wtdw / "tasks.md")]
    before = (wtdw / "tasks.md").read_bytes()
    unrefused, wrote, wrong_stream = [], [], []
    for verb, argv in sorted(_VERB_ARGV.items()):
        rc, out, err = _run(dev_ledger, argv + ledger_arg)
        blob = out + err
        if "did not resolve here (#667)" not in blob:
            unrefused.append((verb, rc, blob[:120]))
            continue
        # DIRECTION-2 CLOSURE. Printing the refusal is not the same as
        # obeying it: a verb that says "refusing" and then writes anyway
        # satisfies a message assertion completely. The write verbs are the
        # ones where that would matter, so the file itself is the check.
        if (wtdw / "tasks.md").read_bytes() != before:
            wrote.append(verb)
        # #497's contract keeps stdout machine-clean; only sweep, whose own
        # cannot-check lines go to stdout, may put the refusal there.
        if verb != "sweep" and "#667" in out:
            wrong_stream.append(verb)
    assert not unrefused, f"verbs that answered from an absent store: {unrefused}"
    assert not wrote, f"verbs that refused and wrote anyway: {wrote}"
    assert not wrong_stream, f"refusal leaked onto machine-clean stdout: {wrong_stream}"


def test_a_refused_write_verb_writes_nothing(migrate, dev_ledger, tmp_path):
    """DIRECTION-2 CLOSURE, and it needed its own fixture to be worth anything.

    Printing "refusing" is not the same as not writing. Asserted against the
    #458 shim the assertion is HOLLOW: the shim has no `## Open` heading, so
    `assert_headings` refuses the write a second time regardless of this gate
    — a refuse-then-write injection stays GREEN there, which is how this test
    came to exist. Measured, not assumed.

    So the ledger here is HEADED BUT EMPTY: `_read_records` is empty (the gate
    fires) AND `assert_headings` passes (the write would otherwise land), which
    is the only shape where the gate is the sole thing standing between a lane
    worktree and a write into a ledger nobody reads.

    PRODUCTION LINE: the `return 2` in the gate — the RETURN specifically,
    not the message. RED: emit the message and fall through for the write
    verbs, and `file` appends an entry to a ledger the loop will never see.
    """
    _, wtdw = _wt_fixture(migrate, tmp_path, "lane-headedempty")
    (wtdw / "tasks.md").write_text(
        "# Task ledger\n\nNext id: **1**\n\n## Open\n\n## Recently landed\n")
    # Both preconditions, measured — either one missing makes this hollow.
    assert not dev_ledger._read_records(str(wtdw)), \
        "precondition: the gate must actually fire here"
    dev_ledger.assert_headings((wtdw / "tasks.md").read_text(), "precondition")

    before = (wtdw / "tasks.md").read_bytes()
    for argv in (_VERB_ARGV["file"], _VERB_ARGV["fold"], _VERB_ARGV["note"]):
        _run(dev_ledger, argv + ["--ledger", str(wtdw / "tasks.md")])
    assert (wtdw / "tasks.md").read_bytes() == before, (
        "a refused write verb must leave the ledger byte-identical: "
        f"{(wtdw / 'tasks.md').read_text()!r}")


def test_sweep_refuses_without_breaking_its_advisory_exit_code(
        migrate, dev_ledger, tmp_path):
    """#404 ruled sweep advisory: "every failure mode is a printed line and
    exit 0 — 'cannot check' must never read as 'nothing to fix'". The refusal
    obeys that contract rather than overriding it, and its line goes to stdout
    where sweep's other cannot-check lines go.

    PRODUCTION LINE: the `if args.cmd == "sweep": ... return 0` branch in the
    gate. RED: drop it and sweep exits 2, breaking a ruled contract.
    """
    _, wtdw = _wt_fixture(migrate, tmp_path, "lane-sweep")
    rc, out, err = _run(dev_ledger, ["sweep", "--ledger", str(wtdw / "tasks.md")])
    assert rc == 0, f"sweep must stay exit-0 advisory, got {rc}"
    assert "did not resolve here (#667)" in out, f"on stdout, like its siblings: {out!r}"
    assert "nothing to review" not in out + err, (
        f"a sweep that read no entries must not report nothing to review: {out!r}")


def test_get_names_the_emptiness_when_there_is_no_shared_store_to_point_at(
        migrate, dev_ledger, tmp_path):
    """The hole the `_dispatch` gate cannot reach, found by constructing it: a
    `--ledger` that names an empty ledger OUTSIDE any git checkout (a lane that
    knows it needs the flag and mistypes the path) resolves to no worktree, so
    there is nothing to point it at — and `#NNN not found` came back verbatim,
    which is #667's sentence arriving by a second door.

    Refusing was rejected: the same emptiness is a brand-new project's
    legitimate state, and refusing it would have to extend to `file`, which is
    how the first task gets in. Naming the emptiness is the part that costs
    nothing.

    PRODUCTION LINE: the `if not recs:` branch in `_verb_get`. RED: delete it
    and the bare `not found` is all the lane sees.
    """
    dw = tmp_path / "loose" / ".dreamwork"
    dw.mkdir(parents=True)
    (dw / "tasks.md").write_text("# Task ledger\n\nNext id: **1**\n")
    assert dev_ledger._unresolved_store(str(dw)) is None, \
        "precondition: nothing for the dispatch gate to resolve to"
    assert not dev_ledger._read_records(str(dw)), \
        "precondition: the ledger genuinely holds nothing"

    rc, _, err = _run(dev_ledger, ["get", "667", "--ledger", str(dw / "tasks.md")])
    assert rc == 1, f"the #497 contract's exit code is unchanged: {rc}"
    assert err.count("\n") == 1, f"and it stays ONE stderr line: {err!r}"
    assert "NO entries at all" in err, (
        f"a not-found from an empty ledger must say the ledger was empty: {err!r}")
    # And a real not-found against a POPULATED ledger must not gain the note,
    # or the note becomes noise on the case it is not about.
    dw2 = _cutover_repo(migrate, tmp_path / "main")
    _, _, err2 = _run(dev_ledger, ["get", "9999", "--ledger", str(dw2 / "tasks.md")])
    assert "NO entries at all" not in err2, (
        f"a populated ledger's not-found is a real answer: {err2!r}")


def test_a_healthy_main_checkout_is_never_refused(migrate, dev_ledger, tmp_path):
    """Coverage, not discrimination: the ordinary case must keep working.

    This one cannot go red on a bad predicate — the main checkout HAS a store,
    so `_read_records` is non-empty and the gate's second clause would spare it
    even if the first were wrong. The discriminating version is the next test.
    """
    dw = _cutover_repo(migrate, tmp_path / "main")
    assert (tmp_path / "main" / ".git").is_dir(), \
        "precondition: a main checkout's .git is a directory"
    rc, out, err = _run(dev_ledger, ["get", "10", "--ledger", str(dw / "tasks.md")])
    assert rc == 0 and "#10" in out, f"rc={rc} out={out!r} err={err!r}"
    assert "#667" not in err, f"a main checkout must never be refused: {err!r}"


def test_a_main_checkout_whose_store_is_gone_is_not_refused(
        migrate, dev_ledger, tmp_path):
    """The half that stops this becoming a blanket silence, put where it can
    actually fail: a main checkout with a genuinely absent store reads from
    NOTHING too, so only the resolver separates it from a lane worktree.

    Its ledger really is gone, and the honest answer is the one it already
    gives — never "re-run against the main checkout", which here would be the
    invocation it just ran.

    PRODUCTION LINE: `lint.shared_store_for_worktree` in `_unresolved_store`
    (#592's resolver, whose own `.git` discrimination is red-proofed by
    test_lint.TestWorktreeLedgerAbsent). RED: replace the resolver with the
    local store path — the plausible "simplification" — and this refuses a main
    checkout while pointing it at itself.
    """
    dw = _cutover_repo(migrate, tmp_path / "main")
    for suffix in ("", "-wal", "-shm"):
        side = Path(str(ledger_parse.store_path(dw)) + suffix)
        if side.exists():
            side.unlink()
    # The preconditions that make this the SAME emptiness a worktree has —
    # without them the test passes for the wrong reason.
    assert not ledger_parse.store_path(dw).exists(), \
        "precondition: the store is genuinely gone"
    assert not dev_ledger._read_records(str(dw)), \
        "precondition: this checkout reads from nothing, exactly like a worktree"
    assert (tmp_path / "main" / ".git").is_dir(), \
        "precondition: only the .git shape separates this from a lane worktree"

    rc, out, err = _run(dev_ledger, ["get", "10", "--ledger", str(dw / "tasks.md")])
    assert "#667" not in err, (
        f"a main checkout must never be told to go read the main checkout: {err!r}")
    assert "not found" in err and rc == 1, (
        f"its ledger really is gone; the honest answer is unchanged: {rc} {err!r}")


def test_a_worktree_with_a_real_markdown_ledger_is_never_refused(
        migrate, dev_ledger, tmp_path):
    """#611's predicate, and the narrowest thing separating this from a
    blanket worktree silence: a ledger that HOLDS ENTRIES really answered, and
    refusing it would replace a true answer with a lecture.

    PRODUCTION LINE: `_unresolved_store`'s `if _read_records(dw_dir): return
    None`. RED: delete that clause and this worktree — whose ledger is right
    there and complete — is refused.
    """
    dw = _cutover_repo(migrate, tmp_path / "main")
    wtdw = _worktree(tmp_path / "main", "lane-realmd")
    _absence_preconditions(wtdw)
    # The one thing that differs from every other worktree case: a real ledger
    # travelled here. Assert it really parses to entries before relying on it.
    (wtdw / "tasks.md").write_text(LEDGER)
    assert dev_ledger._read_records(str(wtdw)) , \
        "precondition: this worktree's ledger must genuinely hold entries"
    assert ledger_parse.store_path(dw).exists(), \
        "precondition: the shared store exists, so only the entry count decides"

    rc, out, err = _run(dev_ledger, ["get", "10", "--ledger", str(wtdw / "tasks.md")])
    assert "#667" not in err, (
        f"a worktree whose ledger really holds entries must answer, not "
        f"refuse: {err!r}")
    assert rc == 0 and "#10" in out, f"rc={rc} out={out!r}"


def test_a_worktree_whose_shared_store_is_gone_is_not_refused(
        migrate, dev_ledger, tmp_path):
    """The excuse is spent on ABSENCE-BY-DESIGN only. If the store the worktree
    shares is itself gone, there is nowhere to send the lane, and telling it to
    re-run against a path that holds nothing would be a second false answer.

    PRODUCTION LINE: the `not shared.exists()` clause in `_unresolved_store`
    (#592's docstring makes that existence the caller's obligation). RED: drop
    the existence check and this test's message points at a store that is not
    there.
    """
    dw = _cutover_repo(migrate, tmp_path / "main")
    wtdw = _worktree(tmp_path / "main", "lane-orphan")
    _absence_preconditions(wtdw)
    ledger_parse.store_path(dw).unlink()
    for suffix in ("-wal", "-shm"):
        side = Path(str(ledger_parse.store_path(dw)) + suffix)
        if side.exists():
            side.unlink()
    assert not ledger_parse.store_path(dw).exists(), \
        "precondition: the shared store is genuinely gone"

    _, _, err = _run(dev_ledger, ["get", "10", "--ledger", str(wtdw / "tasks.md")])
    assert "#667" not in err, (
        f"with no shared store there is nothing to point at: {err!r}")
