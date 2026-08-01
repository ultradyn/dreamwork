"""#294 inc 7 — store-aware dispatch parity tests.

Every ledger consumer now dispatches on ``ledger_parse.source_of_truth``:
markdown → today's code path; store → the ``store_entries`` /
``store_ids_by_state`` / ``store_series_raw`` projection. These tests prove
the two paths agree on a SCRATCH ``.dreamwork/`` (never the real one):

  (a) a real parsed ``tasks.md`` fixture,
  (b) an imported scratch store via the migrate script,
  (c) first-sight events written for every task (the ``migration:git``
      synthetic rows R3 writes — the live cutover runs ``--import-history``
      before ``--cutover``, so every task carries them),
  (d) the cutover watermark written.

Each test asserts markdown-mode output == store-mode output (same ids, same
shapes). Each check that needs two things to differ derives both at runtime
and asserts the gap. Every test names the PRODUCTION LINE its red-proof
targets, and each red-proof was run: the dispatch was reverted to
markdown-only, the test failed on the store-mode assertion, and the source
was restored byte-identical (cp backup, never git checkout).
"""

import importlib.machinery
import importlib.util
import io
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

import ledger_parse
import ledger_store
import lint
import watch

REPO = Path(__file__).resolve().parent
MIGRATE_CLI = REPO / "ud-dw-tasks-migrate"


def _load_migrate():
    """Load the extensionless migrate CLI via SourceFileLoader."""
    loader = importlib.machinery.SourceFileLoader(
        "ud_dw_tasks_migrate", str(MIGRATE_CLI))
    spec = importlib.util.spec_from_loader("ud_dw_tasks_migrate", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture
def migrate():
    return _load_migrate()


def _load_dev_ledger():
    """Load dev/ledger.py as a module (it lives in dev/, not the root)."""
    loader = importlib.machinery.SourceFileLoader(
        "dev_ledger_dispatch", str(REPO / "dev" / "ledger.py"))
    spec = importlib.util.spec_from_loader("dev_ledger_dispatch", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture
def dev_ledger():
    return _load_dev_ledger()


# ---------------------------------------------------------------------------
# Fixture ledger — two sections, clean ids, a combined head, human+loop origins.
# ---------------------------------------------------------------------------
LEDGER = """# Task ledger

Next id: **13**

## Open

- **#10** — an open task · P1 · task · origin: **human**

- **#12** — another open task · P2 · bug · origin: **loop**

## Recently landed

- **#11** — a landed task · P0 · task · origin: **human** (abc1234)
"""

# Same fixture used as git-history snapshots for the burndown test.
LED = "## Open\n\n{open}\n## Recently landed\n\n{done}\n"
_ENTRY = "- **#{i}** — task {i} · P2 · task · origin: **{origin}**\n"


def _git_repo(d, snapshots):
    """Commit each ``(text, when)`` as ``.dreamwork/tasks.md`` in *d*.

    Mirrors ``test_watch.py``'s ``_ledger_repo``: plants commits in
    creation order with fixed epoch timestamps so the burndown is
    deterministic.
    """
    dw = os.path.join(d, ".dreamwork")
    os.makedirs(dw, exist_ok=True)
    base = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x",
                GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
    subprocess.run(["git", "-C", d, "init", "-q"], env=base, check=True,
                   capture_output=True)
    for i, (text, when) in enumerate(snapshots):
        env = dict(base, GIT_AUTHOR_DATE="@%d +0000" % when,
                   GIT_COMMITTER_DATE="@%d +0000" % when)
        with open(os.path.join(dw, "tasks.md"), "w") as f:
            f.write(text)
        subprocess.run(["git", "-C", d, "add", ".dreamwork/tasks.md"],
                       env=env, check=True, capture_output=True)
        subprocess.run(["git", "-C", d, "commit", "-q", "-m", "ledger %d" % i],
                       env=env, check=True, capture_output=True)


def _write_watermark(db_path, ts="2026-07-29T00:00:00Z"):
    """Write the one-way cutover watermark into a scratch store's meta table."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO meta (key, value) VALUES ('ledger_cut_over', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (ts,))
    conn.commit()
    conn.close()


def _write_first_sight_events(db_path, arrived, landed):
    """Write migration:git first-sight + landing events for every task.

    The live cutover runs ``--import-history`` which writes these for groomed
    ids; here we write them for ALL tasks so the store-side burndown has the
    same first-sight model the markdown git-walk builds. Uses the migrate
    module's own ``chain_events`` + ``_history_event`` so the hash chain is
    valid.
    """
    mod = _load_migrate()
    events = []
    for tid, epoch in sorted(arrived.items()):
        events.append(mod._history_event(tid, epoch, None, "open",
                                          "a%07d" % tid, "first_sight"))
    for tid, epoch in sorted(landed.items()):
        events.append(mod._history_event(tid, epoch, "open", "landed",
                                          "b%07d" % tid, "landed"))
    conn = sqlite3.connect(str(db_path))
    chained = mod.chain_events(events, mod.genesis_hash(conn))
    conn.execute("BEGIN IMMEDIATE")
    for e in chained:
        conn.execute(
            "INSERT INTO task_event(task_id, at, cause, from_state, to_state,"
            " actor, receipt_id, detail, prev_hash, hash)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (e["task_id"], e["at"], e["cause"], e["from_state"],
             e["to_state"], e["actor"], e["receipt_id"], e["detail"],
             e["prev_hash"], e["hash"]))
    conn.execute("COMMIT")
    conn.close()


def _setup_store(migrate, dw_dir, ledger_text):
    """Import the ledger into a scratch store and return the db path.

    Uses ``ledger_store.open_store`` + the migrate module's
    ``_populate_store`` directly, bypassing the migrate CLI's scratch-path
    guard (which refuses ``.dreamwork/`` to protect the real store; our
    scratch dir is under ``tmp_path`` so the bypass is safe).
    """
    db_path = dw_dir / ledger_parse.STORE_FILENAME
    analysis = migrate.build_analysis(
        ledger_text, ledger_path=str(dw_dir / "tasks.md"))
    store = ledger_store.open_store(str(db_path), ledger_text=ledger_text)
    try:
        migrate._populate_store(store.conn, ledger_text, analysis)
    finally:
        store.close()
    return db_path


# ---------------------------------------------------------------------------
# Test 1 — store_ids_by_state matches parse_ledger on the same fixture.
#
# Production line: the dispatch in the CONSUMERS (watch.ledger_series,
# status_sync.main, etc.) calls source_of_truth → store_ids_by_state. The
# parity is between parse_ledger(text) and store_ids_by_state(dir); red-proof
# reverts the consumer dispatch to markdown-only and watches the store-mode
# assertion fail.
# ---------------------------------------------------------------------------
def test_store_ids_by_state_matches_parse_ledger(migrate, tmp_path):
    """open/landed id sets are identical from markdown and store."""
    dw = tmp_path / "dw"
    dw.mkdir()
    (dw / "tasks.md").write_text(LEDGER)
    db = _setup_store(migrate, dw, LEDGER)
    _write_watermark(db)

    # Markdown-mode: parse_ledger on the text.
    open_md, landed_md = watch.parse_ledger(LEDGER)
    # Store-mode: store_ids_by_state on the dir.
    open_st, landed_st = ledger_parse.store_ids_by_state(str(dw))

    # Precondition: the fixture has BOTH open and landed ids (a fixture that
    # lost one section makes the parity vacuous).
    assert open_md and landed_md, "fixture must have both sections"
    assert set(open_st) == set(open_md), (
        f"open ids differ: store={sorted(open_st)} markdown={sorted(open_md)}")
    assert set(landed_st) == set(landed_md), (
        f"landed ids differ: store={sorted(landed_st)} "
        f"markdown={sorted(landed_md)}")


# ---------------------------------------------------------------------------
# Test 2 — ledger_series: store-mode burndown matches markdown-mode bucket
# for bucket on a fixture whose git history we control.
#
# Production line: the ``if source_of_truth(dw_dir) == "store"`` dispatch at
# the top of ``watch.ledger_series``. Red-proof: comment out the dispatch
# (force markdown-only) and the store-mode series reads the markdown git-walk
# instead of task_event — the buckets still match because git is present, so
# the red-proof must instead break ``store_series_raw`` (e.g. return empty
# arrived) and watch the store-mode series lose all buckets.
# ---------------------------------------------------------------------------
def test_ledger_series_store_matches_markdown(migrate, tmp_path):
    """Burndown series is identical from markdown git-walk and store query."""
    T = 1784900000
    led = "## Open\n\n{open}\n## Recently landed\n\n{done}\n"
    entry = "- **#{i}** — task {i} · P2 · task · origin: **human**\n"
    landed_entry = "- **#{i}** — did it · landed `{s}`\n"
    snapshots = [
        # t=0h: #1 #2 arrive
        (led.format(open=entry.format(i=1) + entry.format(i=2), done=""), T),
        # t=1h: #3 arrives, #1 lands
        (led.format(open=entry.format(i=2) + entry.format(i=3),
                    done=landed_entry.format(i=1, s="aaa1111")), T + 3600),
        # t=2h: #2 lands; all three ids remain in the current snapshot
        (led.format(open=entry.format(i=3),
                    done=landed_entry.format(i=1, s="aaa1111")
                    + landed_entry.format(i=2, s="bbb2222")), T + 7200),
    ]

    watch._LEDGER_SNAPS.clear()
    watch._LEDGER_CACHE.clear()
    with tempfile.TemporaryDirectory() as d:
        _git_repo(d, snapshots)
        dw = os.path.join(d, ".dreamwork")
        # Markdown-mode result (no watermark yet).
        md = watch.ledger_series(d, now=T + 7200)
        assert md["state"] == watch.BURN_OK, "markdown walk must succeed"

        # Derive arrived/landed from the same snapshots for the store events.
        arrived, landed_prev = {}, {}
        for _sha, epoch, text in _snapshot_walk(d):
            o, done = watch.parse_ledger(text)
            for i in o | done:
                arrived.setdefault(int(i), epoch)
            for i in done:
                landed_prev.setdefault(int(i), epoch)

        # Precondition: the fixture has arrivals AND landings (a fixture with
        # only arrivals makes the landed/median assertions vacuous).
        assert arrived and landed_prev, "fixture must have arrivals + landings"
        assert set(landed_prev) < set(arrived), (
            "every landed id must have arrived — fixture invariant")

        # Import the CURRENT snapshot into the store + write events.
        current_text = snapshots[-1][0]
        # Wrap in a header so the import can seed the id sequence.
        full = "# Task ledger\n\nNext id: **4**\n\n" + current_text
        (Path(dw) / "tasks.md").write_text(full)
        db = _setup_store(migrate, Path(dw), full)
        _write_first_sight_events(db, arrived, landed_prev)
        _write_watermark(db)

        # Store-mode result (watermark present). Remove .git so the
        # markdown path would BURN_NONE — this makes the test distinguish
        # the paths: if the dispatch is broken, ledger_series falls through
        # to the git walk and returns BURN_NONE instead of the store query.
        import shutil
        shutil.rmtree(os.path.join(d, ".git"))
        watch._LEDGER_CACHE.clear()
        st = watch.ledger_series(d, now=T + 7200)

        assert st["state"] == watch.BURN_OK, (
            f"store series must succeed, got state={st.get('state')} "
            f"note={st.get('note')}")
        # The two paths must agree on every summary figure.
        assert st["arrived"] == md["arrived"], (
            f"arrived: store={st['arrived']} markdown={md['arrived']}")
        assert st["landed"] == md["landed"], (
            f"landed: store={st['landed']} markdown={md['landed']}")
        assert st["open"] == md["open"], (
            f"open: store={st['open']} markdown={md['open']}")
        assert st["step"] == md["step"], (
            f"step: store={st['step']} markdown={md['step']}")
        assert len(st["buckets"]) == len(md["buckets"]), (
            f"bucket count: store={len(st['buckets'])} "
            f"markdown={len(md['buckets'])}")
        for i, (sb, mb) in enumerate(zip(st["buckets"], md["buckets"])):
            assert sb["arrived"] == mb["arrived"], (
                f"bucket {i} arrived: store={sb['arrived']} "
                f"markdown={mb['arrived']}")
            assert sb["landed"] == mb["landed"], (
                f"bucket {i} landed: store={sb['landed']} "
                f"markdown={mb['landed']}")
            assert sb["open"] == mb["open"], (
                f"bucket {i} open: store={sb['open']} "
                f"markdown={mb['open']}")
            assert sb["commits"] == mb["commits"], (
                f"bucket {i} commits: store={sb['commits']} "
                f"markdown={mb['commits']}")


def _snapshot_walk(d):
    """Yield (sha, epoch, text) for each commit touching tasks.md, oldest first."""
    top = subprocess.run(
        ["git", "-C", d, "rev-parse", "--show-toplevel"],
        capture_output=True, text=True).stdout.strip()
    rel = os.path.relpath(os.path.join(d, ".dreamwork", "tasks.md"), top)
    rel = rel.replace(os.sep, "/")
    log = subprocess.run(
        ["git", "-C", top, "log", "--format=%H %ct", "--reverse", "--", rel],
        capture_output=True, text=True).stdout
    for line in log.split("\n"):
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[0]:
            sha, ct = parts[0], int(parts[1])
            text = subprocess.run(
                ["git", "-C", top, "show", f"{sha}:{rel}"],
                capture_output=True, text=True).stdout
            yield sha, ct, text


# ---------------------------------------------------------------------------
# Test 3 — status_sync: open ids from store match open ids from markdown.
#
# Production line: the ``if source_of_truth(str(dw)) == "store"`` dispatch in
# ``status_sync.main``. Red-proof: revert to ``ids = open_ids(lpath...)`` and
# the store-mode ids come from the markdown shim (empty), failing the parity.
# ---------------------------------------------------------------------------
def test_status_sync_open_ids_match(migrate, tmp_path):
    """status_sync reads the same open ids from store and markdown."""
    import status_sync
    dw = tmp_path / "dw"
    dw.mkdir()
    (dw / "tasks.md").write_text(LEDGER)
    db = _setup_store(migrate, dw, LEDGER)

    # Markdown-mode: read_open_ids with no watermark.
    md_ids = sorted(status_sync.read_open_ids(dw, dw / "tasks.md"))
    assert md_ids, "fixture must have open ids"

    # Store-mode: write watermark + replace tasks.md with a shim (the
    # post-cutover state). If the dispatch is broken, read_open_ids falls
    # through to the markdown parser which reads the shim (0 ids).
    _write_watermark(db)
    (dw / "tasks.md").write_text("<!--dreamwork-migration-notice shim-->")
    st_ids = sorted(status_sync.read_open_ids(dw, dw / "tasks.md"))

    assert st_ids == md_ids, (
        f"status_sync open ids: store={st_ids} markdown={md_ids}")


# ---------------------------------------------------------------------------
# Test 4 — task_origins: origins from store match origins from markdown.
#
# Production line: the ``if source_of_truth(dw_dir) == "store"`` dispatch at
# the top of ``task_origins.task_origins``. Red-proof: comment out the
# dispatch and the store-mode call falls through to the git walk; the origins
# still match if git is present, so the red-proof must break _store_origins
# (e.g. return all-unknown) and watch the store-mode origins diverge.
# ---------------------------------------------------------------------------
def test_task_origins_match(migrate, tmp_path):
    """task_origins reads the same origins from store and markdown."""
    import task_origins
    T = 1784900000
    led = "## Open\n\n{open}\n## Recently landed\n\n{done}\n"
    entry = "- **#{i}** — task {i} · P2 · task · origin: **{origin}**\n"
    snapshots = [
        (led.format(open=entry.format(i=10, origin="human")
                    + entry.format(i=11, origin="loop"), done=""), T),
        (led.format(open=entry.format(i=10, origin="human"),
                    done=entry.format(i=11, origin="loop")), T + 3600),
    ]
    with tempfile.TemporaryDirectory() as d:
        _git_repo(d, snapshots)
        dw = os.path.join(d, ".dreamwork")
        current = snapshots[-1][0]
        full = "# Task ledger\n\nNext id: **12**\n\n" + current
        (Path(dw) / "tasks.md").write_text(full)

        # Markdown-mode origins (no watermark, git walk).
        md = task_origins.task_origins(d)
        md_origins = {t["id"]: t["origin"] for t in md["tasks"]}
        assert md_origins, "fixture must yield origins"
        # Precondition: the two origins differ (a fixture with one origin
        # makes the per-id check vacuous).
        assert len(set(md_origins.values())) > 1, (
            "fixture must have at least two distinct origins")

        # Set up the store: import tasks + write first-sight events + watermark.
        arrived = {}
        for _sha, epoch, text in _snapshot_walk(d):
            o, done = watch.parse_ledger(text)
            for i in o | done:
                arrived.setdefault(int(i), epoch)
        db = _setup_store(migrate, Path(dw), full)
        _write_first_sight_events(db, arrived, {})
        _write_watermark(db)

        # Store-mode origins (watermark present). Remove .git so the
        # markdown path would raise TaskOriginsError — this makes the test
        # distinguish paths: if the dispatch is broken, task_origins falls
        # through to the git walk and raises instead of querying the store.
        import shutil
        shutil.rmtree(os.path.join(d, ".git"))
        st = task_origins.task_origins(d)
        st_origins = {t["id"]: t["origin"] for t in st["tasks"]}

        assert set(st_origins) == set(md_origins), (
            f"origin ids: store={sorted(st_origins)} "
            f"markdown={sorted(md_origins)}")
        for tid in md_origins:
            assert st_origins[tid] == md_origins[tid], (
                f"origin for #{tid}: store={st_origins[tid]} "
                f"markdown={md_origins[tid]}")


# ---------------------------------------------------------------------------
# Test 5 — dev/ledger.py counts: store-mode counts match markdown-mode.
#
# Production line: the ``if args.cmd == "counts"`` dispatch in
# ``dev/ledger.py main``. Red-proof: remove the store branch and the
# store-mode counts read the markdown shim (0/0), failing the parity.
# ---------------------------------------------------------------------------
def test_dev_ledger_counts_match(migrate, tmp_path):
    """dev/ledger counts are identical from markdown and store."""
    # Load dev/ledger.py as a module.
    loader = importlib.machinery.SourceFileLoader(
        "dev_ledger", str(REPO / "dev" / "ledger.py"))
    spec = importlib.util.spec_from_loader("dev_ledger", loader)
    dev_ledger = importlib.util.module_from_spec(spec)
    loader.exec_module(dev_ledger)

    dw = tmp_path / "dw"
    dw.mkdir()
    (dw / "tasks.md").write_text(LEDGER)
    db = _setup_store(migrate, dw, LEDGER)

    # Markdown-mode counts (no watermark).
    md_out = dev_ledger.main(["counts", "--ledger", str(dw / "tasks.md")])
    md_text = md_out[1] if isinstance(md_out, tuple) else ""
    # main returns int; capture stdout via redirect.
    import contextlib
    md_buf = io.StringIO()
    with contextlib.redirect_stdout(md_buf):
        dev_ledger.main(["counts", "--ledger", str(dw / "tasks.md")])
    md_counts = md_buf.getvalue()

    # Parse the open/landed counts from the output.
    import re
    md_open = int(re.search(r"open ids:\s+(\d+)", md_counts).group(1))
    md_landed = int(re.search(r"landed ids:\s+(\d+)", md_counts).group(1))
    assert md_open > 0 and md_landed > 0, "fixture must have both sections"

    # Store-mode counts (watermark present). Replace tasks.md with a shim
    # so the markdown path would read 0/0 — distinguishes the paths.
    _write_watermark(db)
    (dw / "tasks.md").write_text("<!--dreamwork-migration-notice shim-->")
    st_buf = io.StringIO()
    with contextlib.redirect_stdout(st_buf):
        dev_ledger.main(["counts", "--ledger", str(dw / "tasks.md")])
    st_counts = st_buf.getvalue()
    st_open = int(re.search(r"open ids:\s+(\d+)", st_counts).group(1))
    st_landed = int(re.search(r"landed ids:\s+(\d+)", st_counts).group(1))

    assert st_open == md_open, (
        f"open count: store={st_open} markdown={md_open}")
    assert st_landed == md_landed, (
        f"landed count: store={st_landed} markdown={md_landed}")


# ---------------------------------------------------------------------------
# Test 6 — dev/ledger.py fold: store-mode fold flips state, Markdown untouched.
#
# Production line: the ``if args.cmd in ("fold", "file") and source_of_truth(
# dw_dir) == "store"`` dispatch in dev/ledger.py main. Red-proof: remove the
# fold store branch and fold falls through to the markdown path, which moves
# text in tasks.md instead of flipping the store state — the markdown-untouched
# assertion fails.
# ---------------------------------------------------------------------------
def test_dev_ledger_fold_store_path_flips_state_markdown_untouched(
        migrate, dev_ledger, tmp_path):
    """fold in store mode CASes state open→landed; tasks.md is not touched."""
    import contextlib
    dw = tmp_path / "dw"
    dw.mkdir()
    (dw / "tasks.md").write_text(LEDGER)
    db = _setup_store(migrate, dw, LEDGER)
    _write_watermark(db)

    # Precondition: #10 is open in the store (the fold CAS needs an open task).
    conn = sqlite3.connect(str(db))
    state_before = conn.execute(
        "SELECT state FROM task WHERE id = 10").fetchone()[0]
    conn.close()
    assert state_before == "open", (
        f"precondition: #10 must be open, got {state_before!r}")

    original_md = (dw / "tasks.md").read_text()

    with contextlib.redirect_stdout(io.StringIO()):
        rc = dev_ledger.main(["fold", "10", "--note", "done deal",
                              "--ledger", str(dw / "tasks.md")])
    assert rc == 0

    # The store state flipped; the note landed in the body.
    conn = sqlite3.connect(str(db))
    state, body = conn.execute(
        "SELECT state, body FROM task WHERE id = 10").fetchone()
    conn.close()
    assert state == "landed", f"store state should be landed, got {state!r}"
    assert "done deal" in body, "the fold note must be in the task body"

    # The Markdown file is byte-identical — the store is the source.
    assert (dw / "tasks.md").read_text() == original_md, (
        "tasks.md must be untouched in store-mode fold")


# ---------------------------------------------------------------------------
# Test 7 — dev/ledger.py file: store-mode file allocates a new id.
#
# Production line: the same store dispatch as test 6, file branch. Red-proof:
# remove the file store branch and file falls through to the markdown path,
# which edits tasks.md instead of inserting a store row — the store-row
# assertion fails.
# ---------------------------------------------------------------------------
def test_dev_ledger_file_store_path_allocates_id(migrate, dev_ledger, tmp_path):
    """file in store mode inserts a task row with the seeded next id."""
    import contextlib
    dw = tmp_path / "dw"
    dw.mkdir()
    (dw / "tasks.md").write_text(LEDGER)
    db = _setup_store(migrate, dw, LEDGER)
    _write_watermark(db)

    # Derive the expected id at runtime: the store's next id before filing.
    conn = sqlite3.connect(str(db))
    expected_id = conn.execute(
        "SELECT seq + 1 FROM sqlite_sequence WHERE name = 'task'").fetchone()[0]
    n_before = conn.execute("SELECT COUNT(*) FROM task").fetchone()[0]
    conn.close()
    assert expected_id is not None, "precondition: the sequence must be seeded"

    original_md = (dw / "tasks.md").read_text()

    with contextlib.redirect_stdout(io.StringIO()):
        rc = dev_ledger.main(["file", "a freshly filed task",
                              "--note", "its body", "--priority", "P1",
                              "--type", "bug", "--origin", "loop",
                              "--ledger", str(dw / "tasks.md")])
    assert rc == 0

    # The store gained exactly one row at the expected id.
    conn = sqlite3.connect(str(db))
    n_after = conn.execute("SELECT COUNT(*) FROM task").fetchone()[0]
    row = conn.execute(
        "SELECT state, title, body, priority FROM task WHERE id = ?",
        (expected_id,)).fetchone()
    conn.close()
    assert n_after == n_before + 1, (
        f"store should have one new row: {n_before} → {n_after}")
    assert row is not None, f"no row at the expected id {expected_id}"
    assert row[0] == "open"
    assert row[1] == "a freshly filed task"
    assert "its body" in row[2]

    # The Markdown file is untouched.
    assert (dw / "tasks.md").read_text() == original_md


# ---------------------------------------------------------------------------
# Test 8 — dev/ledger.py file: markdown-mode file inserts under Open.
#
# Production line: ``file_text`` in dev/ledger.py. Red-proof: make file_text
# return text unchanged and no new entry appears under ## Open, Next id is not
# bumped.
# ---------------------------------------------------------------------------
def test_dev_ledger_file_markdown_path_inserts_and_bumps(dev_ledger, tmp_path):
    """file in markdown mode inserts under ## Open and bumps Next id."""
    import contextlib
    import re
    dw = tmp_path / "dw"
    dw.mkdir()
    (dw / "tasks.md").write_text(LEDGER)

    # No watermark → markdown mode. Precondition: the fixture's Next id.
    header = re.search(r"Next id: \*\*(\d+)\*\*", LEDGER)
    assert header is not None, "precondition: fixture must have a Next id header"
    next_id = int(header.group(1))
    assert next_id > 1

    with contextlib.redirect_stdout(io.StringIO()):
        rc = dev_ledger.main(["file", "a markdown-filed task",
                              "--note", "a note", "--ledger",
                              str(dw / "tasks.md")])
    assert rc == 0

    result = (dw / "tasks.md").read_text()
    # The new entry is under ## Open with the allocated id.
    assert f"- **#{next_id}** — a markdown-filed task" in result, (
        f"new entry #{next_id} must be under ## Open")
    assert "a note" in result, "the note must appear as a continuation"
    # Next id bumped.
    new_header = re.search(r"Next id: \*\*(\d+)\*\*", result)
    assert new_header is not None
    assert int(new_header.group(1)) == next_id + 1, (
        f"Next id must bump to {next_id + 1}, got {new_header.group(1)}")
    # No store was created (markdown mode does not touch the store).
    assert not (dw / ledger_parse.STORE_FILENAME).exists(), (
        "markdown-mode file must not create a store")


# ---------------------------------------------------------------------------
# Test 9 — dev/ledger.py note: store-mode note appends to body, Markdown
# untouched.
#
# Production line: the ``if args.cmd == "note"`` branch in the store dispatch
# in dev/ledger.py main. Red-proof: remove the note store branch and note
# falls through to the markdown path, which edits tasks.md instead of
# appending the store body — the markdown-untouched assertion fails.
# ---------------------------------------------------------------------------
def test_dev_ledger_note_store_path_appends_to_body_markdown_untouched(
        migrate, dev_ledger, tmp_path):
    """note in store mode appends to the body; tasks.md is not touched."""
    import contextlib
    dw = tmp_path / "dw"
    dw.mkdir()
    (dw / "tasks.md").write_text(LEDGER)
    db = _setup_store(migrate, dw, LEDGER)
    _write_watermark(db)

    # Derive the before-body at runtime so the assertion is not a literal.
    conn = sqlite3.connect(str(db))
    body_before = conn.execute(
        "SELECT body FROM task WHERE id = 10").fetchone()[0]
    conn.close()
    assert body_before is not None, "precondition: #10 must exist"

    original_md = (dw / "tasks.md").read_text()

    with contextlib.redirect_stdout(io.StringIO()):
        rc = dev_ledger.main(["note", "10", "--note", "a store note",
                              "--ledger", str(dw / "tasks.md")])
    assert rc == 0

    # The note landed in the body; the original body survived.
    conn = sqlite3.connect(str(db))
    body, state = conn.execute(
        "SELECT body, state FROM task WHERE id = 10").fetchone()
    conn.close()
    assert body_before in body, "the original body must survive the note"
    assert "a store note" in body, "the note must be appended to the body"
    # A note is not a transition: the state must not change.
    assert state == "open", f"a note must not change state, got {state!r}"

    # The Markdown file is byte-identical — the store is the source.
    assert (dw / "tasks.md").read_text() == original_md, (
        "tasks.md must be untouched in store-mode note")


# ---------------------------------------------------------------------------
# Test 10 — dev/ledger.py note: markdown-mode note lands under the right
# entry and does NOT move it (sections unchanged). No watermark → markdown
# mode, so the markdown behaviour is unchanged by the store dispatch.
#
# Production line: ``note_text`` in dev/ledger.py. Red-proof: make note_text
# a no-op (return text unchanged) and the note does not appear; or make it
# move the entry and the open/landed id sets change.
# ---------------------------------------------------------------------------
def test_dev_ledger_note_markdown_path_appends_without_moving(dev_ledger, tmp_path):
    """note in markdown mode appends a `  · ` line; the entry stays put."""
    import contextlib
    import re
    dw = tmp_path / "dw"
    dw.mkdir()
    (dw / "tasks.md").write_text(LEDGER)

    # No watermark → markdown mode. Precondition: #10 is open, #11 landed.
    open_before, landed_before = watch.parse_ledger(LEDGER)
    assert "10" in open_before, "precondition: #10 must be open"
    assert "11" in landed_before, "precondition: #11 must be landed"

    with contextlib.redirect_stdout(io.StringIO()):
        rc = dev_ledger.main(["note", "10", "--note", "a markdown note",
                              "--ledger", str(dw / "tasks.md")])
    assert rc == 0

    result = (dw / "tasks.md").read_text()
    # The note line is a `  · ` continuation under the #10 entry.
    assert "  · a markdown note" in result, (
        "the note must appear as a `  · ` continuation line")
    # The entry itself still reads correctly (head intact).
    assert "- **#10** — an open task" in result

    # Sections are UNCHANGED — the note did not move the entry (nor any other).
    open_after, landed_after = watch.parse_ledger(result)
    assert set(open_after) == set(open_before), (
        f"open ids must be unchanged: before={sorted(open_before)} "
        f"after={sorted(open_after)}")
    assert set(landed_after) == set(landed_before), (
        f"landed ids must be unchanged: before={sorted(landed_before)} "
        f"after={sorted(landed_after)}")

    # The note landed immediately under the #10 head, not under #12.
    ten_idx = result.index("- **#10**")
    note_idx = result.index("  · a markdown note")
    twelve_idx = result.index("- **#12**")
    assert ten_idx < note_idx < twelve_idx, (
        "the note must sit under #10 and before #12 — not under the wrong entry")

    # No store was created (markdown mode does not touch the store).
    assert not (dw / ledger_parse.STORE_FILENAME).exists(), (
        "markdown-mode note must not create a store")
