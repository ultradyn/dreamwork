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
    anchors = [
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
    ]
    missing = [
        f"{path}:{line} lacks {symbol}"
        for path, line, symbol in anchors
        if not cited_line_contains_symbol(Path.cwd(), path, line, symbol)
    ]
    assert missing == []


def test_shipped_render_plan_is_explicitly_historical():
    from lint import HISTORICAL_DOC_PATHS

    path = ".dreamwork/docs/plans/render-architecture.md"
    assert path in HISTORICAL_DOC_PATHS
    text = Path(path).read_text()
    assert "I5 landed" in text
    assert "historical record" in text
