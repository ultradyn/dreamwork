#!/usr/bin/env python3
"""Red-first tests for dev/handoffs_drain.py — the handoffs drain (#875).

The drain is a thin composition over the ALREADY-LANDED ``watch.parse_handoffs``
projection (the grammar lint and the dashboard share) plus
``watch.pending_handoff_records`` (the dashboard's ``(id, sha)`` view).  These
tests do NOT re-prove ``parse_handoffs`` (that is test_watch.py's job); they
prove the drain COMPOSES it into an HONEST JOIN — one that names its key and
both denominators on every path, the property the measured defect violated.

The measured defect (#875): a tick joined ``## Pending`` against ``## Folded``
on SHA and reported "120 unfolded"; the same file joined on task id reported 0;
ground truth was 0.  Nothing in either output said what it had joined on, and
neither printed its denominators.  These tests pin the three properties the
brief requires — (1) joins on task id by default and SAYS SO, (2) prints both
denominators on every path, (3) refuses rather than guesses on an entry it
cannot key — plus the two red-proof directions.

DIRECTION 1 (the production seam is dev/handoffs_drain.py's default-key
selection): a fixture where every pending id is folded must report 0 with its
key and both denominators; sabotaging the default key to SHA (the original
wrong key) must fail the key-token assertion.  The expectation is derived from
the FIXTURE (constructed counts), never from the tool's own output.

DIRECTION 2 (false-green construction): the substring trap — a folded ``#862``
must NOT fold a pending ``#86`` — is the sharpest candidate ("the likely real
bug in any fix here"); a naive substring impl false-greens it and the exact-
membership join catches it.  Empty/absent ``## Folded`` and a duplicate pending
id are covered too.
"""
import importlib.machinery
import importlib.util
import io
from pathlib import Path

REPO = Path(__file__).resolve().parent
CLI_PATH = REPO / "dev" / "handoffs_drain.py"


def _load():
    """Load dev/handoffs_drain.py as a module (it lives in dev/, not the root).

    SourceFileLoader mirrors how test_journal_consume.py loads
    dev/journal_consume.py and test_ledger_dispatch.py loads dev/ledger.py.
    """
    loader = importlib.machinery.SourceFileLoader("handoffs_drain", str(CLI_PATH))
    spec = importlib.util.spec_from_loader("handoffs_drain", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _run(cli, argv):
    """Invoke the CLI's main with captured streams; return (rc, out, err)."""
    out = io.StringIO()
    err = io.StringIO()
    rc = cli.main(list(argv), out, err)
    return rc, out.getvalue(), err.getvalue()


def _handoffs(folded=(), pending=()):
    """Build a handoffs.md body from folded/pending id+sha tuples.

    ``folded`` entries are ``(id, merge_sha)`` — the fold cites ONLY the merge
    sha, the real-world shape (#409: "most folds cite the MERGE commit, not the
    work sha a pending landed").  ``pending`` entries are ``(id, work_sha,
    claimer, what)`` — the pending lands the WORK sha.  This is the exact shape
    that makes a SHA join report a large false number while an id join reports
    0: the two populations never share a sha.
    """
    lines = ["## Folded"]
    for fid, msha in folded:
        lines.append(f"- **#{fid}** → folded (2026-08-01 20:00): merged `{msha}`")
    lines.append("")
    lines.append("## Pending")
    for pid, wsha, claimer, what in pending:
        lines.append(
            f"- **#{pid}** · landed `{wsha}` · 2026-08-01 19:50 · by {claimer} — {what}")
    return "\n".join(lines) + "\n"


def test_default_key_is_id_and_prints_key_and_both_denominators(tmp_path):
    """Direction 1 green: every pending id folded → 0, with key + denominators.

    Production seam: dev/handoffs_drain.py default key (``--key`` default and
    the KEY_LABEL printed in the headline).  Sabotaging the default to SHA must
    fail the ``joined on task id`` assertion — the key IS the defect.
    """
    cli = _load()
    # Six pending landings, every id folded.  Expectation derived from THIS
    # fixture: len(pending) pending entries, len(folded) folded ids, 0 unfolded
    # under the id key.  Folds cite merge shas; pending lands work shas, so the
    # two sha populations are disjoint (the sha-join demonstration below).
    pending = [(f"10{i}", f"work{i}11111", f"lane-{i}", f"what {i}") for i in range(6)]
    folded = [(f"10{i}", f"merge{i}99999") for i in range(6)]
    body = _handoffs(folded=folded, pending=pending)
    path = tmp_path / "handoffs.md"
    path.write_text(body)
    rc, out, err = _run(cli, ["pending", "--handoffs", str(path)])
    assert rc == 0, err
    head = out.splitlines()[0]
    # The three properties the brief requires, each asserted by name:
    assert "joined on task id" in head, head          # (1) key named — the defect
    assert f"examined {len(pending)} pending" in head, head   # (2) denominator A
    assert f"{len(folded)} folded ids" in head, head          # (2) denominator B
    assert "0 unfolded" in head, head                 # the right answer
    # No UNFOLDED detail line when the remainder is genuinely empty.
    assert "UNFOLDED" not in out, out


def test_sha_key_reports_large_false_number_on_same_fixture(tmp_path):
    """Direction 1 demonstration: same fixture, --key sha → false large number.

    The id key reported 0 (above).  The sha key — the ORIGINAL WRONG KEY —
    reports every pending unfolded, because the folded merge shas never match
    the pending work shas.  The key is printed, so the two outputs are visibly
    different statements about different joins, not two readings of one.
    """
    cli = _load()
    pending = [(f"10{i}", f"work{i}11111", f"lane-{i}", f"what {i}") for i in range(6)]
    folded = [(f"10{i}", f"merge{i}99999") for i in range(6)]
    path = tmp_path / "handoffs.md"
    path.write_text(_handoffs(folded=folded, pending=pending))
    rc, out, err = _run(cli, ["pending", "--handoffs", str(path), "--key", "sha"])
    assert rc == 0, err
    head = out.splitlines()[0]
    assert "joined on sha" in head, head              # key visible on the wrong key too
    # The false alarm: ALL len(pending) are unfolded under sha, vs 0 under id.
    assert f"{len(pending)} unfolded" in head, head
    # Precondition the false alarm depends on: the sha populations are disjoint.
    # If a fixture revision ever made them overlap, this test would no longer
    # demonstrate the wrong key, so assert the gap at runtime (#794).
    folded_shas = {f"merge{i}99999" for i in range(6)}
    pending_shas = {f"work{i}11111" for i in range(6)}
    assert not (folded_shas & pending_shas), "fixture invariant: disjoint sha sets"


def test_direction2_substring_does_not_overfold(tmp_path):
    """Direction 2 (sharpest): a folded #862 must NOT fold a pending #86.

    A naive substring test (``"#86" in folded_text``) wrongly folds #86 and
    reports 0 unfolded — the false green.  The drain joins by EXACT set
    membership (``row.id in folded_ids``, a set of normalised tokens), so #86
    ∉ {"862"} and #86 stays unfolded.  This constructs the broken impl, shows
    it false-greens, then shows the real drain catches it.
    """
    cli = _load()
    body = _handoffs(
        folded=[("862", "aaaa1111")],
        pending=[("86", "bbbb2222", "lane-86", "the substring victim"),
                 ("862", "cccc3333", "lane-862", "genuinely folded")],
    )
    path = tmp_path / "handoffs.md"
    path.write_text(body)
    # The broken impl: substring membership.  It WOULD report 0 unfolded
    # (false green) because "#86" is a substring of "#862" in the text.
    folded_text = "## Folded\n- **#862**"
    naive_unfolded = [pid for pid in ("86", "862") if f"#{pid}" not in folded_text]
    assert naive_unfolded == [], "naive substring false-greens: #86 wrongly folded"
    # The real drain: exact membership.  #86 stays unfolded.
    rc, out, err = _run(cli, ["pending", "--handoffs", str(path)])
    assert rc == 0, err
    assert any("UNFOLDED\t#86\t" in ln for ln in out.splitlines()), out
    assert not any("UNFOLDED\t#862\t" in ln for ln in out.splitlines()), out
    head = out.splitlines()[0]
    assert "1 unfolded" in head, head  # only #86


def test_direction2_empty_folded_prints_zero_denominator(tmp_path):
    """Direction 2: an absent ## Folded must print '0 folded ids', not stay silent.

    Without a Folded section every pending id is genuinely unfolded, and the
    tool must SAY it read zero folded ids rather than report the remainder
    without its denominator (#868: a zero denominator and a zero remainder must
    not print alike).
    """
    cli = _load()
    body = _handoffs(folded=[], pending=[("100", "bbbb2222", "lane", "what")])
    path = tmp_path / "handoffs.md"
    path.write_text(body)
    rc, out, err = _run(cli, ["pending", "--handoffs", str(path)])
    assert rc == 0, err
    head = out.splitlines()[0]
    assert "0 folded ids" in head, head          # denominator printed, not silent
    assert "joined on task id" in head, head
    assert "1 unfolded" in head, head


def test_direction2_duplicate_pending_id_reports_distinct_count(tmp_path):
    """Direction 2: a duplicate id in ## Pending — count rows AND distinct ids.

    Two pending rows under one id, neither folded.  The drain reports both rows
    unfolded (2) AND the distinct id count (1), so a reader sees the duplicate
    rather than a count that silently halves or doubles it.
    """
    cli = _load()
    body = _handoffs(
        folded=[],
        pending=[("100", "bbbb2222", "lane-a", "first landing"),
                 ("100", "cccc3333", "lane-b", "second landing (dupe)")],
    )
    path = tmp_path / "handoffs.md"
    path.write_text(body)
    rc, out, err = _run(cli, ["pending", "--handoffs", str(path)])
    assert rc == 0, err
    head = out.splitlines()[0]
    assert "2 unfolded" in head, head
    assert "1 distinct id" in head, head


def test_absent_file_prints_zero_denominators_with_key(tmp_path):
    """An absent handoffs.md prints 0/0 with its key — did-not-run discriminability.

    A fresh target has no hand-offs; the drain reports 0 pending + 0 folded with
    the key named, so 'found nothing' (this) differs from a future 'did not run'
    only by the operator's knowledge there was a file to read (#404/#671).
    """
    cli = _load()
    rc, out, err = _run(
        cli, ["pending", "--handoffs", str(tmp_path / "absent.md")])
    assert rc == 0, err
    head = out.splitlines()[0]
    assert "examined 0 pending + 0 folded ids" in head, head
    assert "joined on task id" in head, head


def test_malformed_and_unkeyable_listed_not_dropped(tmp_path):
    """Refuses rather than guesses: unkeyable AND malformed lines are listed.

    Two distinct refusal channels, both surfaced: (1) UNKEYABLE — a Pending
    entry whose bold head carries NO id (``**no-hash**``), which
    ``parse_handoffs`` silently drops and this drain's coverage scan recovers
    (the exact #875 case: "a pending line with no id must be reported as
    unkeyable, not silently dropped"); (2) MALFORMED — a ``**#…**`` head the
    full grammar rejects (``**#bad**`` with no ``landed``/``folded``), which
    ``parse_handoffs`` flags.  Neither is dropped from the join's accounting.
    """
    cli = _load()
    body = (
        "## Folded\n"
        "- **#100** → folded (2026-08-01 20:00): merged `aaaa1111`\n\n"
        "## Pending\n"
        "- **#100** · landed `bbbb2222` · 2026-08-01 19:50 · by lane — ok\n"
        "- **no-hash** · landed `cccc3333` · 2026-08-01 19:50 · by lane — no id\n"
        "- **#bad** · landed `dddd4444` · 2026-08-01 19:50 · by lane — non-digit id\n"
    )
    path = tmp_path / "handoffs.md"
    path.write_text(body)
    rc, out, err = _run(cli, ["pending", "--handoffs", str(path)])
    assert rc == 0, err
    head = out.splitlines()[0]
    assert "1 unkeyable" in head, head
    assert "1 malformed" in head, head
    assert any("UNKEYABLE" in ln and "no-hash" in ln for ln in out.splitlines()), out
    assert any("MALFORMED" in ln and "#bad" in ln for ln in out.splitlines()), out


def test_dashboard_correlation_line_under_id_key_only(tmp_path):
    """The dashboard (id, sha) view prints under --key id and is suppressed under sha.

    Under the id key the drain also reports the status panel's ``(id, sha)``
    count so the two never silently disagree.  Under the sha key (the
    demonstration key) it is suppressed — beside a deliberately-wrong remainder
    it would be noise.
    """
    cli = _load()
    body = _handoffs(
        folded=[("100", "aaaa1111")],
        pending=[("100", "bbbb2222", "lane", "what")],
    )
    path = tmp_path / "handoffs.md"
    path.write_text(body)
    rc, out_id, _ = _run(cli, ["pending", "--handoffs", str(path)])
    assert rc == 0
    assert "dashboard (id, sha) correlation" in out_id, out_id
    rc, out_sha, _ = _run(cli, ["pending", "--handoffs", str(path), "--key", "sha"])
    assert rc == 0
    assert "dashboard (id, sha) correlation" not in out_sha, out_sha
