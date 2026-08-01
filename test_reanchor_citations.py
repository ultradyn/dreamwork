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


def test_wrong_in_range_line_is_not_symbol_evidence(tmp_path: Path):
    (tmp_path / "router.js").write_text("const nearby = true;\nfunction tick() {}\n")
    assert not cited_line_contains_symbol(tmp_path, "router.js", 1, "tick")
    assert cited_line_contains_symbol(tmp_path, "router.js", 2, "tick")

