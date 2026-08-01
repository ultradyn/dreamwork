from pathlib import Path

from dev.reanchor_citations import (
    Citation,
    cited_line_contains_symbol,
    find_definitions,
    format_resolution,
    named_symbols,
    resolve,
)
from dev.apply_reanchors_i3 import ANCHORS, ReviewedAnchor, resolve_all


def citation(context: str, old_line: int = 9000) -> Citation:
    own = context.splitlines()[0]
    start = own.index("watch.py:")
    return Citation("doc.md", 1, "watch.py", old_line, start, start + 13, context)


def test_nearby_backticked_symbol_is_extracted_not_the_path():
    item = citation("`tick()` (`watch.py:9000`) snapshots state")
    assert named_symbols(item) == ["tick"]


def test_unique_definition_is_the_only_kind_that_proposes(tmp_path: Path, monkeypatch):
    (tmp_path / "router.js").write_text("function tick() {\n  tick();\n}\n")
    monkeypatch.setattr("dev.reanchor_citations.source_files", lambda _root: ["router.js"])
    item = resolve(tmp_path, citation("`tick()` (`watch.py:9000`) snapshots state"))
    assert item.reason == "unique definition"
    assert item.definitions[0].line == 1
    assert "router.js:1  (tick, high)" in format_resolution(item)


def test_a_call_site_or_comment_is_not_a_definition(tmp_path: Path, monkeypatch):
    (tmp_path / "router.js").write_text("// tick handles refresh\ntick();\n")
    monkeypatch.setattr("dev.reanchor_citations.source_files", lambda _root: ["router.js"])
    item = resolve(tmp_path, citation("`tick()` (`watch.py:9000`) snapshots state"))
    assert item.reason == "cannot resolve named symbol"
    assert "CANNOT RESOLVE" in format_resolution(item)


def test_multiple_definitions_are_reported_not_picked(tmp_path: Path, monkeypatch):
    (tmp_path / "a.js").write_text("function tick() {}\n")
    (tmp_path / "b.py").write_text("def tick():\n    pass\n")
    monkeypatch.setattr("dev.reanchor_citations.source_files", lambda _root: ["a.js", "b.py"])
    item = resolve(tmp_path, citation("`tick()` (`watch.py:9000`) snapshots state"))
    assert item.reason == "ambiguous definitions"
    assert {d.path for d in item.definitions} == {"a.js", "b.py"}


def test_plain_snake_case_subject_is_resolved_at_medium_confidence(tmp_path: Path, monkeypatch):
    (tmp_path / "watch.py").write_text("def append_human_question():\n    pass\n")
    monkeypatch.setattr("dev.reanchor_citations.source_files", lambda _root: ["watch.py"])
    item = resolve(tmp_path, citation("append_human_question (watch.py:9000) builds the title"))
    assert item.symbol == "append_human_question"
    assert item.confidence == "medium"


def test_css_selector_resolves_to_its_definition(tmp_path: Path, monkeypatch):
    (tmp_path / "style.css").write_text(".qaghost { opacity: 0; }\n")
    monkeypatch.setattr("dev.reanchor_citations.source_files", lambda _root: ["style.css"])
    assert find_definitions(tmp_path, ".qaghost")[0].line == 1


def test_wrong_in_range_line_is_not_symbol_evidence(tmp_path: Path):
    (tmp_path / "router.js").write_text("const nearby = true;\nfunction tick() {}\n")
    assert not cited_line_contains_symbol(tmp_path, "router.js", 1, "tick")
    assert cited_line_contains_symbol(tmp_path, "router.js", 2, "tick")


def test_renamed_definition_is_a_refusal_not_a_nearby_proposal(tmp_path: Path, monkeypatch):
    source = tmp_path / "router.js"
    source.write_text("function tick() {}\nconst nearby = 1;\n")
    monkeypatch.setattr("dev.reanchor_citations.source_files", lambda _root: ["router.js"])
    named = citation("`tick()` (`watch.py:9000`) snapshots state")
    assert resolve(tmp_path, named).reason == "unique definition"
    source.write_text("function refreshTick() {}\nconst nearby = 1;\n")
    assert resolve(tmp_path, named).reason == "cannot resolve named symbol"


def test_the_two_live_plans_have_no_past_eof_citations():
    from dev.reanchor_citations import dangling_citations

    docs = [
        ".dreamwork/docs/plans/question-updated-wake.md",
        ".dreamwork/docs/plans/delivery-modes.md",
    ]
    assert dangling_citations(Path.cwd(), docs) == []


def test_each_reviewed_anchor_line_contains_the_named_evidence():
    """Movement is healthy; missing or ambiguous reviewed evidence is not."""
    assert len(ANCHORS) == 74, f"expected 74 reviewed anchors, got {len(ANCHORS)}"
    resolved = resolve_all(Path.cwd())
    assert len(resolved) == 74
    track = next(item for item in resolved if item.symbol == "track_question_updates")
    assert (track.reviewed_line, track.current_line, track.drift) == (3683, 3695, 12)


def test_ambiguous_reanchor_names_the_anchor_and_each_drift(tmp_path: Path):
    source = tmp_path / "watch.py"
    source.write_text("# inserted\ndef tick():\n    pass\ndef tick():\n    pass\n")
    anchor = ReviewedAnchor("watch.py", 1, "tick", "def tick():")
    try:
        anchor.resolve(tmp_path)
    except ValueError as exc:
        assert str(exc) == (
            "watch.py:1 (tick) is ambiguous: "
            "line 2 (drift +1), line 4 (drift +3)"
        )
    else:
        raise AssertionError("ambiguous reviewed evidence was silently reanchored")


def test_unanticipated_watch_insertion_keeps_lines_derived(tmp_path: Path):
    """Direction 2: a scratch insertion shifts an anchor by an unknown amount."""
    lines = Path("watch.py").read_text().splitlines()
    lines[3000:3000] = [f"# unanticipated insertion {n}" for n in range(7)]
    (tmp_path / "watch.py").write_text("\n".join(lines) + "\n")
    before = ANCHORS[0].resolve(tmp_path)
    track_anchor = next(a for a in ANCHORS if a.symbol == "track_question_updates")
    after = track_anchor.resolve(tmp_path)
    assert (before.current_line, before.drift) == (342, 0)
    assert (after.current_line, after.drift) == (3702, 19)


def test_transplanted_evidence_is_the_open_false_green(tmp_path: Path):
    """Direction 2 limit: exact evidence cannot prove its surrounding meaning."""
    (tmp_path / "watch.py").write_text(
        "def unrelated_handler():\n"
        "    data = read_bytes(full)  # exact line moved under the wrong owner\n"
    )
    anchor = ReviewedAnchor(
        "watch.py",
        90,
        "read_bytes",
        "    data = read_bytes(full)  # exact line moved under the wrong owner",
    )
    resolved = anchor.resolve(tmp_path)
    assert (resolved.current_line, resolved.drift) == (2, -88), (
        "open false-green: byte-identical reviewed evidence was transplanted "
        "into a different semantic owner; movement alone cannot distinguish it"
    )


def test_a_wrong_referent_passes_the_token_check(tmp_path: Path):
    """Direction 2 false-green: cited_line_contains_symbol verifies the token
    is on the line, NOT that the token is the prose's referent.  A citation
    whose named symbol exists uniquely elsewhere and whose anchor is the
    wrong referent still passes — review is the only defence (#651).

    Constructed example: read_bytes is the referent the prose names, but
    _send_bytes (whose definition line also contains the substring on a
    nearby line) would pass the token check if mis-paired."""
    (tmp_path / "watch.py").write_text(
        "def _send_bytes(self, full, rel, *, inline):\n"
        "    data = b'chunked'\n"
        "    self.wfile.write(data)\n"
        "\n"
        "def read_bytes(path):\n"
        "    return Path(path).read_bytes()\n"
    )
    # _send_bytes:1 contains the substring "send_bytes" — so a citation
    # naming read_bytes at line 1 would still pass the TOKEN check.
    assert cited_line_contains_symbol(tmp_path, "watch.py", 1, "_send_bytes")
    # But the same line does NOT contain read_bytes — the token check
    # catches a mis-pair where the anchor line names a DIFFERENT symbol.
    assert not cited_line_contains_symbol(tmp_path, "watch.py", 1, "read_bytes")
    # The honest gap: if the wrong-referent line coincidentally contains the
    # token (e.g. a call to read_bytes inside _send_bytes), the check passes.
    (tmp_path / "watch.py").write_text(
        "def _send_bytes(self, full, rel, *, inline):\n"
        "    data = read_bytes(full)  # wrong referent, token present\n"
    )
    assert cited_line_contains_symbol(tmp_path, "watch.py", 1, "_send_bytes")
    # read_bytes appears as a CALL on line 2 — the token check passes even
    # though the citation's referent is the DEFINITION at a different line.
    # This is the open gap: review is the only defence, and this test says so.
    assert cited_line_contains_symbol(tmp_path, "watch.py", 2, "read_bytes"), (
        "false-green: read_bytes is a CALL on line 2, not the definition; "
        "the token check passes because the substring is present, not because "
        "the line IS the referent the prose intended (#651)"
    )


def test_shipped_render_plan_is_explicitly_historical():
    from lint import HISTORICAL_DOC_PATHS

    path = ".dreamwork/docs/plans/render-architecture.md"
    assert path in HISTORICAL_DOC_PATHS
    text = Path(path).read_text()
    assert "I5 landed" in text
    assert "historical record" in text
