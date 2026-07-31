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
import lint  # #671 — `ledger_view`, the #294 dispatch the sweep tests derive from
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
    "reach": ["reach"],
    "list": ["list"],
    "get": ["get", "10"],
    "count": ["count"],
    "reviews": ["reviews", "list"],
    "groom": ["groom"],
    # #627 — store-mode-only write verbs. They ride the #667 gate like every
    # other verb, so their argv needs a valid --why (argparse-enforced) and an
    # id the fixture holds (#10), matching fold/note's shorthand.
    "reprioritise": ["reprioritise", "10", "P3", "--why", "x"],
    "unblock": ["unblock", "10", "--why", "x"],
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
    parser_verbs = _parser_verbs(dev_ledger)
    mapped = set(_VERB_ARGV)
    assert parser_verbs == mapped, (
        f"every parser verb must have a row in _VERB_ARGV (the gate sweep's "
        f"coverage map) and vice versa.\n"
        f"  add to _VERB_ARGV with a minimal valid argv: "
        f"{sorted(parser_verbs - mapped)}\n"
        f"  remove from _VERB_ARGV (no parser entry): "
        f"{sorted(mapped - parser_verbs)}")


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
    unrefused, wrote, wrong_stream, wrong_rc = [], [], [], []
    for verb, argv in sorted(_VERB_ARGV.items()):
        # #688 — reach needs NO ledger and dispatches BEFORE the gate, so it
        # neither takes --ledger nor can be gated by it. Excluding it here is
        # correct, not a gap: the gate protects ledger-reading verbs from
        # answering from an empty ledger, and reach never reads one.
        if verb == "reach":
            continue
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
        # The DISCRIMINATING assertion (#734). A refusal that exits 0 reads
        # as success (#671); one that exits 1 hides inside the "no such id"
        # answer it is refusing to give (#667, #497). The gate returns 2 —
        # non-zero, and not 1. Sweep keeps #404's advisory exit 0 (pinned by
        # test_sweep_refuses_without_breaking_its_advisory_exit_code).
        if verb != "sweep" and rc != 2:
            wrong_rc.append((verb, rc))
    assert not unrefused, f"verbs that answered from an absent store: {unrefused}"
    assert not wrote, f"verbs that refused and wrote anyway: {wrote}"
    assert not wrong_stream, f"refusal leaked onto machine-clean stdout: {wrong_stream}"
    assert not wrong_rc, (
        f"a store that did not resolve must exit 2, not 0 (reads as success, "
        f"#671) or 1 (collides with 'no such id', #667): {wrong_rc}")


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


# ===========================================================================
# #671 — `sweep` never got the #294 store dispatch, so after the cutover it
# correlated git against ZERO ledger entries and called that "nothing to
# review". MEASURED on the live repo before the fix: 442 commits examined,
# 177 open ids never seen, and the printed verdict was
# `sweep: nothing to review (this ran — see the examined count above)`.
#
# WHY THESE TESTS ARE SHAPED THE WAY THEY ARE, and it is the whole task in
# miniature: the defect is a CONFIDENT-LOOKING OUTPUT. `sweep` exits 0 on
# every failure mode by #404's ruling, so the check cannot be an exit code;
# and "sweep printed something" PASSES on the broken version, because the
# broken version prints confidently and at length. The assertion therefore has
# to be that a PLANTED LANDING IS NAMED — a claim only a sweep that actually
# read the store can satisfy.
#
# The findings are read back through the report's own printed format rather
# than by substring, so `#12` cannot be satisfied by `#124` and the header's
# own counts cannot be mistaken for a finding.
# ===========================================================================

SWEEP_FINDING = re.compile(r"^  #(\d+) — ", re.M)


def _named_ids(out):
    """The ids `sweep` actually FLAGGED, parsed from its own report format."""
    return {int(x) for x in SWEEP_FINDING.findall(out)}


def _plant(root, subject):
    """An id-bearing commit with no content — returns the short sha `sweep`
    will print (`%h`, the same format `_git_subjects` reads)."""
    _git(root, "commit", "-q", "--allow-empty", "-m", subject)
    return _git(root, "rev-parse", "--short", "HEAD").stdout.strip()


def _sweep_fixture(migrate, tmp_path, name="main"):
    """A REAL post-cutover checkout — store present, `tasks.md` the #458 shim.

    The precondition that makes every test below non-vacuous is asserted here,
    derived rather than assumed: the MARKDOWN the broken sweep read yields ZERO
    open ids, so anything these tests observe can only have come from the
    store. Without this the fixture could quietly keep a real `tasks.md` around
    and the whole file would pass against the defect.
    """
    root = tmp_path / name
    dw = _cutover_repo(migrate, root)
    md_open, md_landed = watch.parse_ledger((dw / "tasks.md").read_text())
    assert not md_open and not md_landed, (
        f"precondition: the markdown left by the cutover must yield NO entries, "
        f"else a markdown-reading sweep could pass; got {md_open}/{md_landed}")
    assert ledger_parse.source_of_truth(str(dw)) == "store", \
        "precondition: the fixture must genuinely be in store mode"
    return root, dw


def _sweep(dev_ledger, root, dw, since=None):
    args = ["sweep", "--ledger", str(dw / "tasks.md"), "--repo", str(root)]
    if since is not None:
        args += ["--since", since]
    rc, out, err = _run(dev_ledger, args)
    assert rc == 0, f"#404 ruled sweep exit-0 advisory, got {rc}: {err!r}"
    return out


def test_sweep_names_a_landing_for_an_open_id_held_only_by_the_store(
        migrate, dev_ledger, tmp_path):
    """THE DEFECT, and the assertion is the planted landing being NAMED.

    A green sweep on a repo with known-open ids and a known id-bearing commit
    must go RED if the open-id source returns empty — which is what #294's
    cutover did to it. The id here is OPEN IN THE STORE ONLY; the markdown the
    old code read is the #458 shim (asserted in `_sweep_fixture`), so naming it
    is a claim no markdown-reading sweep can make.

    PRODUCTION LINE: `text, source = lint.ledger_view(ledger_path.parent)` in
    `_dispatch`'s sweep branch. RED: restore `ledger_path.read_text()` — the
    defect verbatim — and this fails with "the planted landing was not named",
    while the report still prints its confident examined-count line.
    """
    root, dw = _sweep_fixture(migrate, tmp_path)
    # Derived from the fixture through the markdown reader the store was
    # imported from, never a literal tuned to today's store.
    open_ids, _ = _fixture_ids()
    tid = sorted(int(i) for i in open_ids)[0]
    sha = _plant(root, f"fix(#{tid}): a landing the entry does not cite")

    out = _sweep(dev_ledger, root, dw)

    assert tid in _named_ids(out), (
        f"the planted landing for open id #{tid} ({sha}) was NOT named — "
        f"sweep correlated against nothing and said so confidently: {out!r}")
    assert sha in out, f"the evidence sha must be printed: {out!r}"


def test_sweep_says_how_many_open_ids_it_correlated_against(
        migrate, dev_ledger, tmp_path):
    """#404 printed the examined COMMIT count so that "found nothing" differs
    from "did not run". #671 is that rule applied to only one half: the commit
    count stayed real while the ledger half silently went to zero. So the
    ledger half is accounted for on the same line, with the source it came
    from.

    PRODUCTION LINE: the `against {len(open_ids)} open ids ({source})` clause
    in `sweep_text`'s header. RED: drop it and the count assertion fails — the
    report goes back to being confident about a number it never states.
    """
    root, dw = _sweep_fixture(migrate, tmp_path)
    open_ids, _ = _fixture_ids()
    _plant(root, "docs(#999): an id the ledger does not hold")

    out = _sweep(dev_ledger, root, dw)

    assert f"against {len(open_ids)} open ids" in out, (
        f"the ledger half of the correlation must be counted on the report's "
        f"own header, like the commit half: {out!r}")
    assert "(store)" in out, (
        f"the source actually read must be named — `ledger_view` fails closed "
        f"toward markdown, so the word has to be its answer: {out!r}")


def test_sweep_reports_how_many_subjects_it_understood_not_just_examined(
        migrate, dev_ledger, tmp_path):
    """#682: examined≠understood — #671 one layer deeper. "examined N" cannot
    tell a sweep that matched M of N from one that matched 0 of N; both print
    the same count. The header now carries the id-bearing count (what
    SWEEP_SUBJECT matched) and names the dominant skip shape, so a 1-of-7
    sweep reads differently from a 7-of-7 all-clear.

    PRODUCTION LINE: `_skip_shape` + the `({idbearing} id-bearing, {skipped}
    skipped, mostly {dom})` clause in `sweep_text`'s header. RED: drop the
    clause and the count vanishes — the report goes back to "examined N" over a
    corpus it matched almost none of (#671's silent all-clear, one layer in).
    """
    root, dw = _sweep_fixture(migrate, tmp_path)
    # The four shapes #682 measured on the real corpus, in miniature: one
    # verb(#N): landing (high confidence), three Merge/Fold post-landing
    # markers (#707 widened these to lower-confidence findings — they now
    # MATCH rather than being skipped), one bare-#N lane commit (#707
    # widened this too), and a no-id doc commit (the only genuine skip).
    _plant(root, "fix(#10): a real landing")
    _plant(root, "Merge #11: a coordinator landing")
    _plant(root, "Fold #11 (merged abc1234)")
    _plant(root, "Merge #12: another sibling")
    _plant(root, "#10 — a bare lane commit")
    _plant(root, "docs: a commit with no id")

    # Pin the window open so the report is judged on its OWN contract (#682:
    # id-bearing vs skipped), not on `_default_since` — a `Fold #N` commit
    # planted as a subject-to-classify is also a window boundary (#714), and
    # letting it bound the window here would hide three of the six subjects
    # for a reason unrelated to what this test asserts.
    since = _git(root, "rev-list", "--max-parents=0", "HEAD").stdout.strip()
    out = _sweep(dev_ledger, root, dw, since=since)

    # The id-bearing count derives from the SAME pattern + git log the sweep
    # sees — never a literal. A count the test invents cannot catch the
    # classification drifting from the real pattern. The window matches what
    # sweep examines (`since..HEAD`), so the seed commit outside it is not
    # counted either.
    rng = [f"{since}..HEAD"]
    subjects = [
        line.split("\x1f", 1)[1] for line in _git(
            root, "log", "--format=%h\x1f%s", *rng).stdout.splitlines()
        if "\x1f" in line]
    expected_idb = sum(
        1 for s in subjects if dev_ledger.SWEEP_SUBJECT.match(s))

    assert f"({expected_idb} id-bearing" in out, (
        f"the header must state how many examined commits it actually matched "
        f"— examined≠understood (#682, #671 one layer in): {out!r}")
    assert f"{len(subjects) - expected_idb} skipped" in out, (
        f"and the skip count, so a {expected_idb}-of-{len(subjects)} sweep "
        f"does not read as an all-clear: {out!r}")
    assert "mostly " in out, (
        f"the dominant skip shape must be named, not dropped silently: {out!r}")


def test_sweep_subtracts_a_cited_sha_read_from_the_store_body(
        migrate, dev_ledger, tmp_path):
    """DIRECTION-2 CLOSURE for the test above, and it covers real ground.

    "The planted landing is named" is satisfied by a sweep that names
    EVERYTHING, including the landings entries already cite — #404's
    suppression convention ("cite the sha, the row disappears") failing open,
    which is #612's volume failure arriving through the store. Subtraction also
    rides a DIFFERENT part of the projection than the id set does: the bodies,
    whose `- **#N**` heads `ledger_view` SYNTHESIZES for headless store rows
    (#557). A projection that produced the right ids and unparseable bodies
    would pass the test above and fail here.

    PRODUCTION LINE: `if sha in bodies.get(tid, ""): continue` in `sweep`, now
    reached with store bodies. RED: drop the `continue` and the cited id is
    named too, failing the exact-set assertion.
    """
    root, dw = _sweep_fixture(migrate, tmp_path)
    ids = sorted(int(i) for i in _fixture_ids()[0])
    assert len(ids) >= 2, "fixture needs two open ids to tell the halves apart"
    uncited, cited = ids[0], ids[1]

    _plant(root, f"fix(#{uncited}): a landing the entry does not cite")
    cited_sha = _plant(root, f"fix(#{cited}): a landing the entry DOES cite")
    rc, _, err = _run(dev_ledger, [
        "note", str(cited), "--note", f"landed {cited_sha}",
        "--ledger", str(dw / "tasks.md")])
    assert rc == 0, f"the note verb must have written the citation: {err!r}"

    # The gap is DERIVED from the projection the sweep will read, not assumed:
    # one body carries the sha, the other does not.
    text, source = lint.ledger_view(dw)
    bodies = {t: b for tids, b in ledger_parse.ledger_entries(
        ledger_parse.open_section_text(text) or "") for t in tids}
    assert cited_sha in bodies.get(cited, ""), (
        f"precondition: #{cited}'s store body must carry {cited_sha}")
    assert cited_sha not in bodies.get(uncited, ""), \
        f"precondition: #{uncited}'s body must not carry it"

    out = _sweep(dev_ledger, root, dw)

    assert _named_ids(out) == {uncited}, (
        f"exactly the uncited landing may be named — #{cited} cites its sha "
        f"({cited_sha}) in the store body and must be subtracted: {out!r}")


def test_sweep_that_read_no_entries_refuses_to_call_it_nothing_to_review(
        migrate, dev_ledger, tmp_path):
    """#404's ruled contract: "'cannot check' must never read as 'nothing to
    fix'". `ledger_view` fails CLOSED TOWARD MARKDOWN on any store error, and
    in a cut-over checkout the markdown is the #458 shim — so a store that
    stops resolving reproduces #671 exactly, through the fix's own fallback.
    The zero-entries case therefore has to say it did not review.

    This is the MAIN-CHECKOUT shape: #667's gate is a linked-worktree gate by
    construction (`shared_store_for_worktree`), so it does not fire here and
    cannot cover this. Verified below rather than argued.

    PRODUCTION LINE: the `if not open_ids and not landed_ids:` branch in
    `sweep_text`. RED: delete it and the report says "nothing to review" over
    an empty ledger — #671 verbatim.
    """
    root, dw = _sweep_fixture(migrate, tmp_path)
    store = ledger_parse.store_path(dw)
    store.unlink()
    for suffix in ("-wal", "-shm"):
        side = Path(str(store) + suffix)
        if side.exists():
            side.unlink()
    # Derived: the ledger really does yield nothing now, and #667's gate really
    # is not the thing answering (this is a main checkout, not a worktree).
    text, _source = lint.ledger_view(dw)
    md_open, md_landed = watch.parse_ledger(text)
    assert not md_open and not md_landed, (
        f"precondition: the ledger must yield no entries at all: {text!r}")
    assert lint.shared_store_for_worktree(dw) is None, \
        "precondition: #667's worktree gate must not be what answers here"
    _plant(root, "fix(#10): a landing nothing can be correlated against")

    out = _sweep(dev_ledger, root, dw)

    assert "nothing to review" not in out, (
        f"a sweep that read no entries must not report nothing to review — "
        f"that is the #671 sentence verbatim: {out!r}")
    assert "DID NOT REVIEW" in out, f"it must say it could not check: {out!r}"
    assert "against 0 open ids" in out, (
        f"and the count that makes it checkable must be printed: {out!r}")


def test_sweep_ignores_store_landed_ids_and_ids_the_ledger_does_not_hold(
        migrate, dev_ledger, tmp_path):
    """DIRECTION-2 CLOSURE, found by construction rather than by reasoning.

    With only the three tests above, dropping sweep's `if str(tid) not in
    open_ids: continue` left ALL of them GREEN while the tool named landed ids
    and ids the ledger has never held — #612's volume failure arriving through
    the store, and the exact shape trap 2 warns about: "the planted landing is
    named" is satisfied by a sweep that names everything.

    #404's `test_sweep_ignores_landed_ids_and_reports_multi_id_subjects` does
    catch that injection — over a MARKDOWN fixture. What it cannot reach is the
    thing #671 introduced: post-cutover the open/landed split is no longer read
    from headings a human wrote, it is SYNTHESIZED by `ledger_view` from
    `store_ids_by_state`. A projection that filed landed rows under `## Open`
    would leave that markdown test untouched and green while the live sweep
    flagged already-folded work every tick.

    PRODUCTION LINE: `open_bodies = [... if str(ids[0]) in oset]` in
    `lint.ledger_view`. RED: widen it to `oset | lset` and the landed id is
    named. Also red on dropping sweep's membership filter — the injection this
    test exists because of.

    THE EMPTY SET IS ONLY MEANINGFUL WITH THE HEADER ASSERTION, which is this
    whole task's lesson turned on my own test: "sweep named nothing" is equally
    true of a sweep that read nothing, so the non-vacuity claim — it correlated
    against the real open ids, and it examined the planted commits — is
    asserted rather than assumed.
    """
    root, dw = _sweep_fixture(migrate, tmp_path)
    open_ids, landed_ids = _fixture_ids()
    landed = sorted(int(i) for i in landed_ids)[0]
    unknown = max(int(i) for i in open_ids | landed_ids) + 1000
    assert str(unknown) not in open_ids | landed_ids, \
        "precondition: the unknown id must genuinely be absent from the ledger"

    _plant(root, f"fix(#{landed}): a landing for an id that already landed")
    _plant(root, f"docs(#{unknown}): a landing for an id the ledger never held")

    out = _sweep(dev_ledger, root, dw)

    # Non-vacuity FIRST: an empty finding set means nothing unless the sweep
    # can be shown to have read the ledger and examined the commits.
    assert f"against {len(open_ids)} open ids (store)" in out, (
        f"the sweep must be shown to have read the store before its silence "
        f"counts for anything: {out!r}")
    assert "examined 3 commits" in out, (
        f"and to have examined the planted commits: {out!r}")

    assert _named_ids(out) == set(), (
        f"neither the already-landed #{landed} nor the unheld #{unknown} may "
        f"be flagged as an open landing: {out!r}")


def test_sweep_report_names_the_coordinator_merge_form_with_a_confidence_class(
        migrate, dev_ledger, tmp_path):
    """DIRECTION-1 for the #707 report split, fixture not live repo.

    A `Merge #NNN:` landing for an OPEN id the entry does not cite is the
    exact class #707 measured invisible (every coordinator merge commit). The
    widened pattern now finds it (#404's primary route recovering ~1697
    historical commits), AND the report carries its verb so a reader can
    dismiss it without opening the commit.

    PRODUCTION LINE: `_subject_class` + the widened-class summary line in
    `sweep_text`. RED: revert SWEEP_SUBJECT to verb(#N)-only and #NNN no
    longer appears AND the summary line vanishes.

    THE DISCRIMINATING ASSERTION is the CONFIDENCE-CLASS wording, not the
    count: a report that folded Merge/#N into the verb findings would name
    the id (the count goes up) but hide that it is lower confidence — which
    is exactly the trap the #707 brief warns about. The summary must carry a
    SEPARATE line for the widened forms.
    """
    root, dw = _sweep_fixture(migrate, tmp_path)
    open_ids = sorted(int(i) for i in _fixture_ids()[0])
    tid = open_ids[0]
    sha = _plant(root, f"Merge #{tid}: a coordinator landing the entry omits")

    out = _sweep(dev_ledger, root, dw)

    # (1) the id is NAMED with its sha and subject — Direction 1 proper.
    assert tid in _named_ids(out), (
        f"the Merge #{tid} landing ({sha}) must now be named — #707 measured "
        f"this class invisible to the primary route: {out!r}")
    assert sha in out and f"Merge #{tid}" in out, (
        f"the evidence (sha + subject) must be printed so the verb is visible: "
        f"{out!r}")
    # (2) the DISCRIMINATING assertion: a separate, lower-confidence summary.
    assert "lower confidence" in out, (
        f"the widened forms must carry their own confidence-class line, not be "
        f"folded into the verb findings — #707's central design point: {out!r}")


def test_sweep_report_splits_verb_findings_from_widened_findings(
        migrate, dev_ledger, tmp_path):
    """The two confidence classes must render as SEPARATE summary lines, or
    widening silently merges the classes (#707's trap).

    With one verb(#N) finding and one Merge #N finding, the report must carry
    BOTH summary lines — the verb line AND the widened line. Folding them into
    one count is exactly the false-attribution hazard the brief warns against:
    `Merge #688:` is likely already-folded, `fix(#688):` is a landing, and
    conflating them makes the report unreadable (#612).

    PRODUCTION LINE: the two-armed summary in `sweep_text` (verb_rows +
    widened_rows). RED: collapse to a single summary line and one class
    vanishes — the reader can no longer tell a landing from a post-landing
    marker at a glance.
    """
    root, dw = _sweep_fixture(migrate, tmp_path)
    ids = sorted(int(i) for i in _fixture_ids()[0])
    assert len(ids) >= 2, "fixture needs two open ids to split the classes"
    verb_tid, merge_tid = ids[0], ids[1]
    _plant(root, f"fix(#{verb_tid}): a verb-form landing")
    _plant(root, f"Merge #{merge_tid}: a coordinator landing")

    out = _sweep(dev_ledger, root, dw)

    # PRECONDITION: both forms matched (else the split is untestable).
    assert dev_ledger.SWEEP_SUBJECT.match(f"Merge #{merge_tid}: x"), (
        "precondition: the Merge form must match post-widening")
    # Both summary lines present, separately — the discriminating assertion.
    assert "verb form" in out, (
        f"the high-confidence verb findings get their own summary line: {out!r}")
    assert "widened form" in out, (
        f"the lower-confidence widened findings get a SEPARATE line, not folded "
        f"in — #707's whole point: {out!r}")


def test_ledger_view_refuses_the_ledger_file_with_a_named_mistake(tmp_path):
    """#697: the name reads as 'view of the ledger', so a caller passes the
    ledger FILE and assigns one name, then hits a late ``AttributeError`` on
    ``.splitlines`` deep in a check — not a clear error at the call site. The
    guard turns passing ``tasks.md`` into a ``TypeError`` that names the
    directory and the tuple unpack.

    PRODUCTION LINE: the ``str(dw).endswith(".md")`` guard in ``ledger_view``.
    RED: delete it and the call returns ``(None, 'markdown')`` silently.
    """
    dw = tmp_path / ".dreamwork"
    dw.mkdir()
    tasks_md = dw / "tasks.md"
    tasks_md.write_text("# ledger\n")  # the file a caller mistakes for dw
    with pytest.raises(TypeError, match=r"\.dreamwork.*not tasks\.md.*tuple"):
        lint.ledger_view(tasks_md)
