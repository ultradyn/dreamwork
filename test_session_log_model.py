import pytest

from session_log import ModelError, SessionEvent, SessionNode, SourceRef


def _node(**overrides):
    values = {
        "id": "sess:s1/pg:0/turn:t1/step:tool-1",
        "parent": "sess:s1/pg:0/turn:t1",
        "kind": "step.tool",
        "seq": 8,
        "ts": "2026-08-01T02:03:04.005Z",
        "label": "$ just pytest test_session_log_model.py",
        "state": "live",
        "n_children": 0,
        "ref": SourceRef(line=17, byte=840, length=121),
    }
    values.update(overrides)
    return SessionNode(**values)


def test_event_serialises_to_the_exact_standardised_wire_shape():
    event = SessionEvent("open", _node())
    wire = event.to_wire()

    assert wire["node"]["ref"] == {"line": 17, "byte": 840, "len": 121}, (
        "source ref must spell its wire length field 'len', not expose the "
        "Python attribute name")
    assert wire == {
        "ev": "open",
        "node": {
            "id": "sess:s1/pg:0/turn:t1/step:tool-1",
            "parent": "sess:s1/pg:0/turn:t1",
            "kind": "step.tool",
            "seq": 8,
            "ts": "2026-08-01T02:03:04.005Z",
            "label": "$ just pytest test_session_log_model.py",
            "state": "live",
            "n_children": 0,
            "ref": {"line": 17, "byte": 840, "len": 121},
        },
    }


def test_unmeasured_optional_fields_are_omitted_not_serialised_as_null():
    wire = _node(n_children=None, ref=None).to_wire()

    assert "n_children" not in wire
    assert "ref" not in wire
    assert wire["ts"] == "2026-08-01T02:03:04.005Z"


@pytest.mark.parametrize("field,value,message", [
    ("kind", "step.spelling-error", "unknown node kind"),
    ("state", "waiting", "unknown node state"),
    ("seq", -1, "node.seq must be"),
    ("n_children", -1, "node.n_children must be"),
])
def test_node_refuses_values_outside_the_wire_contract(field, value, message):
    with pytest.raises(ModelError, match=message):
        _node(**{field: value})


def test_event_vocabulary_is_closed():
    with pytest.raises(ModelError, match="unknown event type"):
        SessionEvent("replace", _node())


@pytest.mark.parametrize("values,message", [
    ({"line": 0, "byte": 0, "length": 1}, "ref.line"),
    ({"line": 1, "byte": -1, "length": 1}, "ref.byte"),
    ({"line": 1, "byte": 0, "length": 0}, "ref.len"),
])
def test_source_ranges_cannot_point_outside_a_complete_record(values, message):
    with pytest.raises(ModelError, match=message):
        SourceRef(**values)
