"""ud-dw-tasks-migrate — the parse-and-report half of #294's migration, exercised.

The CLI is loaded by path (no .py extension, the repo's bin/ convention) and
driven through ``main([...], out=...)`` so exit codes are the real integers,
matching test_user_events_cli.py's pattern.

Every expected conflict set below is DERIVED from the production parsers
(``watch.parse_ledger``, ``ledger_parse.ledger_entries``) at runtime — never a
literal — and each derivation is asserted non-empty first, because a fixture
that lost its injected shape would let the check pass over nothing (the repo's
documented hollow-check failure). Where no production reader exists for a
field (bands are prose fields in tasks.md — #346 measured them with its own
scan), the test-side scan is bound to the production branch by red-proof, not
by construction.
"""

import importlib.machinery
import importlib.util
import io
import re
import subprocess
from collections import Counter
from pathlib import Path

import pytest

import ledger_parse
import lint

REPO = Path(__file__).resolve().parent
CLI = REPO / "ud-dw-tasks-migrate"
LIVE_LEDGER = REPO / ".dreamwork" / "tasks.md"


def _load_cli():
    """Load the extensionless CLI via an explicit SourceFileLoader."""
    loader = importlib.machinery.SourceFileLoader("ud_dw_tasks_migrate", str(CLI))
    spec = importlib.util.spec_from_loader("ud_dw_tasks_migrate", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture
def module():
    return _load_cli()


# ---------------------------------------------------------------------------
# Fixture ledger — one of EACH conflict shape the dry-run must report.
# Ids are chosen so the header `Next id` (231) equals MAX(parsed id)+1 and
# exceeds every entry head, keeping the seed verifiable.
# ---------------------------------------------------------------------------
FIXTURE = """# Task ledger

Preamble prose. The header contract lives here.

- **#150** — a stray preamble entry · P2 · tooling · origin: **human**
  that never made it into a section.

Next id: **231**

## Open

- **#220** — a clean open entry · P1 · tooling · origin: **human**
  with a body cross-ref to #221 that is only a reference.

- **#221** — the open head of a duplicated id · P2 · tooling · origin: **loop**

- **#202** — the first twin of a within-section duplicate · P2 · tooling · origin: **loop**

- **#202** — the second twin of a within-section duplicate · P2 · tooling · origin: **loop**

- **#208** — a wholly-bolded band field · **P1** · tooling · origin: **loop**

- **#209** — title embeds **P2** as emphasis · tooling · origin: **human**

- **#222** — a compound-band entry · P0/P1 · bug · origin: **human**

- **#223** — an out-of-band entry · P4 · tooling · origin: **loop**

- **#224** — a bandless entry · tooling · origin: **human**

- **#225** — an out-of-vocabulary origin · P2 · tooling · origin: **robot**

- **#100** — a pre-216 entry with no origin and no band at all

- **#226** — a post-216 entry with no origin · P3 · tooling

- **#227** — dangling references · P2 · tooling · origin: **loop**
  · related: **#999, #220** · blocked on #998 until that lands

- **#228/#229** — a combined entry · P2 · tooling · origin: **loop**

## Recently landed

- **#230** — a clean landed entry · P1 · tooling · origin: **human** (abc1234)

- **#221** — the landed head of the duplicated id · P2 · tooling · origin: **loop** (def5678)
"""

# Test-side field scan for bands. tasks.md has no production band reader
# (#346's finding: bands live as prose `·`-fields); this scan's binding to the
# production branch is the red-proof, per the module docstring.
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
    open_ids, landed_ids = watch.parse_ledger(text)
    entries = ledger_parse.ledger_entries(text)
    head_counts = Counter(i for ids, _ in entries for i in ids)
    heads = set(head_counts)
    exists = heads | {int(x) for x in open_ids} | {int(x) for x in landed_ids}
    bodies = {tuple(ids): body for ids, body in entries}
    return {
        "open": {int(x) for x in open_ids},
        "landed": {int(x) for x in landed_ids},
        "entries": entries,
        "bodies": bodies,
        "dupes": {i for i, c in head_counts.items() if c > 1}
        | {int(x) for x in open_ids & landed_ids},
        "exists": exists,
        "compound": {ids[0] for ids, body in entries
                     if any("/" in b for b in _band_fields(body))},
        "out_of_band": {ids[0] for ids, body in entries
                        if any(b not in CLOSED_BANDS and "/" not in b
                               for b in _band_fields(body))},
        "bandless": {ids[0] for ids, body in entries
                     if len(ids) == 1 and not _band_fields(body)},
        "origin_marks": {ids[0]: ledger_parse.ORIGIN_MARK.findall(body)
                         for ids, body in entries if len(ids) == 1},
        "combined": [tuple(ids) for ids, _ in entries if len(ids) > 1],
        "stray": {i for ids, _ in entries for i in ids
                  if str(i) not in open_ids and str(i) not in landed_ids},
        "no_id": [body.splitlines()[0] for ids, body in entries if not ids],
    }


def _conflict_ids(analysis: dict, category: str) -> set:
    return {c["id"] for c in analysis["conflicts"].get(category, [])}


def _analyse(module, text: str = FIXTURE) -> dict:
    return module.build_analysis(text, ledger_path="<fixture>")


# ---------------------------------------------------------------------------
# Counts — the report's numbers are parse_ledger's numbers, exactly.
# ---------------------------------------------------------------------------
def test_counts_match_parse_ledger_exactly(module):
    d = _derived(FIXTURE)
    assert d["open"] and d["landed"], "fixture lost its two sections"
    a = _analyse(module)
    assert set(a["open_ids"]) == d["open"]
    assert set(a["landed_ids"]) == d["landed"]
    assert a["total_ids"] == len(d["open"] | d["landed"])
    assert len(a["entries"]) == len(d["entries"])
    assert a["open_count"] == len(d["open"])
    assert a["landed_count"] == len(d["landed"])


# ---------------------------------------------------------------------------
# Conflicts — one test per shape, each with a runtime-derived precondition.
# ---------------------------------------------------------------------------
def test_duplicate_ids_reported(module):
    d = _derived(FIXTURE)
    assert d["dupes"], "fixture lost its duplicate id — the check would pass over nothing"
    a = _analyse(module)
    assert _conflict_ids(a, "duplicate ids") == d["dupes"]
    assert a["disjoint"] is False  # the dup sits in both sections here


def test_compound_band_imports_lower_band_uncertain(module):
    d = _derived(FIXTURE)
    assert d["compound"], "fixture lost its compound band"
    a = _analyse(module)
    flagged = _conflict_ids(a, "band outside closed set")
    assert d["compound"] <= flagged
    for c in analysis_conflicts(a, "band outside closed set"):
        if c["id"] in d["compound"]:
            # S2: a compound imports as the LOWER band + priority_uncertain=1.
            assert "priority_uncertain=1" in c["detail"]
            lower = c["detail"].split("imports as ")[1].split(",")[0]
            assert lower in CLOSED_BANDS


def analysis_conflicts(analysis: dict, category: str) -> list:
    return analysis["conflicts"].get(category, [])


def test_band_outside_closed_set_reported(module):
    d = _derived(FIXTURE)
    assert d["out_of_band"], "fixture lost its out-of-band entry"
    a = _analyse(module)
    assert d["out_of_band"] <= _conflict_ids(a, "band outside closed set")


def test_missing_band_means_p2_by_contract(module):
    d = _derived(FIXTURE)
    assert d["bandless"], "fixture lost its bandless entries"
    a = _analyse(module)
    flagged = _conflict_ids(a, "missing band (P2 by contract)")
    assert flagged == d["bandless"]


def test_origin_outside_closed_set_reported(module):
    d = _derived(FIXTURE)
    # The contract vocabulary is lint.ORIGIN_VALUES (human|loop|unknown —
    # `unknown` is first-class), NOT ledger_parse.KNOWN_ORIGINS.
    bad = {i for i, marks in d["origin_marks"].items()
           if len(marks) == 1 and marks[0].strip() not in lint.ORIGIN_VALUES}
    assert bad, "fixture lost its out-of-vocabulary origin"
    a = _analyse(module)
    assert _conflict_ids(a, "origin outside closed set") == bad


def test_explicit_unknown_origin_is_legal(module):
    d = _derived(FIXTURE)
    assert not any(m.strip() == "unknown"
                   for marks in d["origin_marks"].values() for m in marks), (
        "fixture gained an explicit unknown origin — delete this test's inverse")
    text = FIXTURE.replace("origin: **human**\n  with a body cross-ref",
                           "origin: **unknown**\n  with a body cross-ref")
    d2 = _derived(text)
    assert any(m.strip() == "unknown" for marks in d2["origin_marks"].values()
               for m in marks), "unknown-origin injection never reached the fixture"
    a = _analyse(module, text)
    still_bad = {i for i, marks in d2["origin_marks"].items()
                 if len(marks) == 1 and marks[0].strip() not in lint.ORIGIN_VALUES}
    assert 220 not in still_bad and still_bad, "derivation lost its anchor"
    assert _conflict_ids(a, "origin outside closed set") == still_bad


def test_bolded_band_field_is_a_band_not_missing(module):
    d = _derived(FIXTURE)
    bolded = {ids[0] for ids, body in d["entries"]
              if len(ids) == 1 and re.search(r"· \*\*P\d+\*\* ·", body)}
    assert bolded, "fixture lost its wholly-bolded band field"
    assert not (bolded & d["bandless"]), "test scan cannot see the bolded field"
    a = _analyse(module)
    assert not (bolded & _conflict_ids(a, "missing band (P2 by contract)"))


def test_title_embedded_band_flagged_with_evidence(module):
    d = _derived(FIXTURE)
    embedded = {ids[0] for ids, body in d["entries"]
                if len(ids) == 1 and not _band_fields(body)
                and re.search(r"\*\*P\d+\*\*", body)}
    assert embedded, "fixture lost its title-embedded band"
    a = _analyse(module)
    rows = [c for c in analysis_conflicts(a, "missing band (P2 by contract)")
            if c["id"] in embedded]
    assert {c["id"] for c in rows} == embedded
    assert all("not as a `·`-field" in c["detail"] for c in rows)


def test_origin_absent_under_216_is_legal(module):
    d = _derived(FIXTURE)
    pre216 = {i for i, marks in d["origin_marks"].items() if not marks and i < 216}
    assert pre216, "fixture lost its legal pre-216 unmarked entry"
    a = _analyse(module)
    flagged = _conflict_ids(a, "origin absent at id >= 216")
    assert not (pre216 & flagged)


def test_origin_absent_over_216_flagged(module):
    d = _derived(FIXTURE)
    post = {i for i, marks in d["origin_marks"].items() if not marks and i >= 216}
    assert post, "fixture lost its post-216 unmarked entry"
    a = _analyse(module)
    assert post <= _conflict_ids(a, "origin absent at id >= 216")


def test_dangling_related_and_blocked_on_reported(module):
    d = _derived(FIXTURE)
    rel_dangling, blk_dangling = set(), set()
    for ids, body in d["entries"]:
        for m in lint.RELATED_MARKER.finditer(body):
            rel_dangling |= {int(x) for x in ledger_parse.ENTRY_ID.findall(m.group(1))
                             if int(x) not in d["exists"]}
        for m in re.finditer(r"blocked on (#\d+)", body, re.I):
            blk_dangling |= {int(m.group(1)[1:])} - d["exists"]
    assert rel_dangling and blk_dangling, "fixture lost its dangling references"
    assert {220} <= d["exists"] - rel_dangling, (
        "fixture lost its EXISTING related id — over-flagging would pass unseen")
    a = _analyse(module)
    # Equality, not subset: a check that flags existing ids (over-reports) or
    # none (under-reports) must both fail. The first red-proof here was green
    # because subset passed over a flag-everything injection.
    assert _conflict_ids(a, "related id does not exist") == rel_dangling
    assert _conflict_ids(a, "blocked-on id does not exist") == blk_dangling


def test_combined_entries_reported(module):
    d = _derived(FIXTURE)
    assert d["combined"], "fixture lost its combined head"
    a = _analyse(module)
    reported = {tuple(c["ids"]) for c in a["conflicts"].get("combined entries surviving", [])}
    assert reported == set(d["combined"])


def test_stray_entry_outside_both_sections(module):
    d = _derived(FIXTURE)
    assert d["stray"], "fixture lost its stray preamble entry"
    a = _analyse(module)
    assert _conflict_ids(a, "entry outside both sections") == d["stray"]


def test_no_id_head_reported_when_present(module):
    d = _derived(FIXTURE)
    a = _analyse(module)
    # The fixture carries no id-less head; the category must still exist, empty.
    assert a["conflicts"].get("entry head without an id", []) == []
    assert d["no_id"] == []


# ---------------------------------------------------------------------------
# Seed (R1) — derived, verified against the header, exceeding every id.
# ---------------------------------------------------------------------------
def test_seed_verified_and_exceeds_every_id(module):
    d = _derived(FIXTURE)
    derived = max(d["open"] | d["landed"]) + 1
    header = int(lint.NEXT_ID.search(FIXTURE).group(1))
    assert header == derived, "fixture's header drifted from its own parser"
    a = _analyse(module)
    assert a["seed"]["ok"] is True
    assert a["seed"]["seed"] == derived
    assert a["seed"]["header"] == header
    max_head = max(i for ids, _ in d["entries"] for i in ids)
    assert a["seed"]["seed"] > max_head


def test_seed_header_drift_is_a_conflict_not_a_crash(module):
    drifted = FIXTURE.replace("Next id: **231**", "Next id: **200**")
    d = _derived(drifted)
    derived = max(d["open"] | d["landed"]) + 1
    assert derived != 200, "drift injection never reached the fixture"
    a = _analyse(module, drifted)
    assert a["seed"]["ok"] is False
    assert a["conflicts"].get("seed verification"), "drifted header not reported"
    # …and the CLI still exits 0: drift is a conflict, not a parse failure.
    out = io.StringIO()
    rc = module.main(["--dry-run", "--ledger", _write(drifted)], out=out)
    assert rc == 0
    assert "seed" in out.getvalue()


def test_seed_must_exceed_stray_entry_heads(module):
    """A stray head above MAX(parsed id)+1 would mint a colliding id (R1)."""
    text = FIXTURE.replace(
        "- **#150** — a stray preamble entry",
        "- **#999** — a stray preamble entry")
    d = _derived(text)
    derived = max(d["open"] | d["landed"]) + 1
    max_head = max(i for ids, _ in d["entries"] for i in ids)
    assert max_head > derived, "fixture lost the stray-above-seed gap this test is named for"
    a = _analyse(module, text)
    assert a["seed"]["ok"] is False
    assert a["conflicts"].get("seed verification")


def _write(text: str, name: str = "tasks.md") -> str:
    import tempfile
    p = Path(tempfile.mkdtemp()) / name
    p.write_text(text)
    return str(p)


# ---------------------------------------------------------------------------
# Exit codes — nonzero ONLY on an unparseable ledger.
# ---------------------------------------------------------------------------
def test_missing_ledger_exits_66(module):
    rc = module.main(["--dry-run", "--ledger", "/nonexistent/tasks.md"], out=io.StringIO())
    assert rc == 66


def test_ledger_without_open_section_exits_65(module):
    rc = module.main(["--dry-run", "--ledger", _write("# no sections here\n")], out=io.StringIO())
    assert rc == 65


def test_ledger_with_no_ids_exits_65(module):
    text = "# Task ledger\n\n## Open\n\n## Recently landed\n"
    rc = module.main(["--dry-run", "--ledger", _write(text)], out=io.StringIO())
    assert rc == 65


def test_conflicted_ledger_still_exits_zero(module):
    a_rc = module.main(["--dry-run", "--ledger", _write(FIXTURE)], out=io.StringIO())
    assert a_rc == 0


# ---------------------------------------------------------------------------
# Digests — one per entry, of the verbatim body, so --import can prove bytes.
# ---------------------------------------------------------------------------
def test_per_entry_digests_cover_every_entry(module):
    import hashlib
    d = _derived(FIXTURE)
    a = _analyse(module)
    # Pairwise, not keyed: the duplicate id heads two entries with the same
    # id tuple, and a dict would silently collapse one (found by the red run).
    assert len(a["entries"]) == len(d["entries"])
    for entry, (ids, body) in zip(a["entries"], d["entries"]):
        assert entry["ids"] == ids
        assert entry["digest"] == hashlib.sha256(body.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Live-repo acceptance — this repo's real tasks.md (the brief's floors).
# ---------------------------------------------------------------------------
def test_live_ledger_acceptance(module):
    text = LIVE_LEDGER.read_text()
    d = _derived(text)
    assert d["open"] & d["landed"] == set(), "live ledger's sections overlap"
    out = io.StringIO()
    rc = module.main(["--dry-run", "--ledger", str(LIVE_LEDGER)], out=out)
    assert rc == 0
    a = module.build_analysis(text, ledger_path=str(LIVE_LEDGER))
    assert a["open_count"] == len(d["open"]) and a["open_count"] >= 130
    assert a["landed_count"] == len(d["landed"]) and a["landed_count"] >= 230
    assert a["disjoint"] is True
    assert a["conflicts"].get("entry outside both sections", []) == []
    assert a["conflicts"].get("entry head without an id", []) == []
    assert a["seed"]["ok"] is True
    report = out.getvalue()
    assert "DRY RUN" in report and "writes nothing" in report


# ---------------------------------------------------------------------------
# The extensionless-script surface (repo convention: one subprocess test).
# ---------------------------------------------------------------------------
def test_executable_and_help():
    assert CLI.exists() and CLI.stat().st_mode & 0o111
    r = subprocess.run(["python3", str(CLI), "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "migrate" in r.stdout
