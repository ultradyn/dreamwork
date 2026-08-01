from pathlib import Path

from dev.reanchor_citations import (
    Citation,
    cited_line_contains_symbol,
    find_definitions,
    format_resolution,
    named_symbols,
    resolve,
)


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
    """Every citation re-anchored by increments 2+3: the target line must
    contain the named token.  This is necessary but NOT sufficient — it
    proves the line holds the symbol, not that the symbol is the prose's
    referent.  The wrong-referent defence is human review, named honestly
    in test_a_wrong_referent_passes_the_token_check."""
    anchors = [
        # increment 2 — 28 anchors
        ("watch.py", 342, "COMMANDS"),
        ("watch.py", 3683, "track_question_updates"),
        ("watch.py", 3717, "_store_algo"),
        ("watch.py", 3726, "seen_at"),
        ("watch.py", 3728, "digest"),
        ("watch.py", 3735, "return"),
        ("watch.py", 3737, "dirty"),
        ("watch.py", 3752, "digest"),
        ("watch.py", 3765, "emits_wake"),
        ("watch.py", 3792, "os.replace"),
        ("watch.py", 3797, "collect"),
        ("watch.py", 3812, "track_question_updates"),
        ("watch.py", 4538, "DELIVERY_DEFAULT"),
        ("watch.py", 4563, "PREEMPT_KINDS"),
        ("watch.py", 4566, "delivery_mode"),
        ("watch.py", 4575, "emits_wake"),
        ("watch.py", 4585, "DELIVERY_DEFAULT"),
        ("watch.py", 4621, "log_event"),
        ("watch.py", 4632, "OSError"),
        ("watch.py", 4668, "_journal_receive"),
        ("watch.py", 4685, "_journal_record_health"),
        ("watch.py", 4847, "command_line"),
        ("watch.py", 4963, "_journal_receive"),
        ("watch.py", 5457, "_journal_receive"),
        ("watch.py", 5672, "_handle_command"),
        ("watch.py", 5834, "_handle_run_mode"),
        ("watch.py", 5863, "_handle_posture"),
        ("watch.py", 6077, "WRITE_ROUTE_HANDLERS"),
        # increment 3 — 36 anchors (8 rejected proposals corrected by review,
        # 4 ambiguous refusals disambiguated, 24 accepted tool proposals)
        ("watch.py", 2667, "append_human_question"),
        ("watch.py", 909, "read_bytes"),
        ("watch.py", 5139, "_send_bytes"),
        ("watch.py", 804, "read_text"),
        ("watch.py", 974, "detect_file_kind"),
        ("watch.py", 4606, "resolve_confined"),
        ("watch.py", 947, "INLINE_IMAGE_EXTS"),
        ("watch.py", 4860, "_expected_disconnect"),
        ("watch.py", 5190, "do_GET"),
        ("watch.py", 5081, "_send"),
        ("watch.py", 4313, "parse_posture_text"),
        ("watch.py", 4394, "resolve_posture"),
        ("watch.py", 4437, "write_posture"),
        ("watch.py", 4505, "posture_line"),
        ("watch.py", 5533, "_handle_answer"),
        ("ledger_parse.py", 66, "ledger_entries"),
        ("ledger_parse.py", 37, "ENTRY_HEAD"),
        ("watch.py", 2042, "ledger_series"),
        ("watch.py", 1619, "_LEDGER_SNAPS"),
        ("watch.py", 1540, "LEDGER_ENTRY"),
        ("watch.py", 1570, "LEDGER_COMBINED_MENTION"),
        ("watch.py", 1623, "parse_ledger"),
        ("watch.py", 1648, "_open_ids"),
        ("watch.py", 4721, "log_submission"),
        ("watch.py", 5380, "do_POST"),
        ("watch.py", 4639, "MAX_BODY"),
        ("watch.py", 2561, "atomic_write_text"),
        ("watch.py", 4603, "ANSWER_LOCK"),
        ("watch.py", 5366, "_read_json"),
        ("watch.py", 4164, "WATCHED_MTIME_IGNORED"),
        ("watch.py", 4264, "write_tint"),
        ("watch.py", 4207, "watched_mtime"),
        ("watch.py", 4280, "read_run_mode"),
        ("watch.py", 1360, "serving_cached"),
        ("watch.py", 3553, "skill_identity"),
        ("watch.py", 6087, "_handle_posture"),
        # increment 3 continued — 9 anchors added by review of the previous
        # session's bulk apply: 2 wrong-referent corrections (reload-signal
        # citations point at route handlers, not the functions they call),
        # 3 ledger_write.py:190→38 (note_task moved during refactor), and
        # 4 refusal resolutions by prose reading.
        ("watch.py", 5205, "data.json"),
        ("watch.py", 5235, "mtime"),
        ("ledger_write.py", 38, "note_task"),
        ("watch.py", 2485, "parse_open_answers"),
        ("watch.py", 5312, "reviewraw"),
        ("watch.py", 5199, "parsed.path"),
        ("watch.py", 5574, "_handle_comment"),
        ("client/router.js", 1638, "reconciliation"),
        ("client/router.js", 1750, "morphdom"),
        ("dreamwork_db/migrate.py", 28, "MIGRATIONS"),
    ]
    # Precondition: the anchor list grew by exactly 46 across increments 2+3.
    # A literal count would rot; this asserts the size the check depends on.
    assert len(anchors) == 74, f"expected 74 anchors (28 i2 + 46 i3), got {len(anchors)}"
    missing = [
        f"{path}:{line} lacks {symbol}"
        for path, line, symbol in anchors
        if not cited_line_contains_symbol(Path.cwd(), path, line, symbol)
    ]
    assert missing == []


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
