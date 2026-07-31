#!/usr/bin/env python3
"""Red-first contract tests for dev/guard_preflight.py (#606).

The defect under test is a SILENT wrong call on the wrong-answer regime, in
the flavours the brief names: a load threshold that fires at the wrong place
(refuses on a clean run, or waves through the failure regime); a missing
reading that renders as a calm zero (#671/#136); a refusal that says nothing
the reader can act on (#136); and a verdict line the justfile cannot grep.

The readers are injectable via classify()/render() taking plain values, so
these run against synthetic readings and never touch the real machine — the
assertion binds the rendered message, not an exit code (the instrument exits 0
always; the justfile owns the refusal).

PRODUCTION LINES WHOSE REVERSION REDS EACH TEST: the threshold constants and
comparisons in classify(), the None branches in classify() and render(), and
the force-flag string in _recommendation(). Name one, change it, watch red.
"""
import importlib.machinery
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent
CLI_PATH = REPO / "dev" / "guard_preflight.py"


def _load():
    loader = importlib.machinery.SourceFileLoader("guard_preflight", str(CLI_PATH))
    spec = importlib.util.spec_from_loader("guard_preflight", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


gp = _load()


# ── band boundaries (the measured thresholds) ──────────────────────────

class TestBands:
    """The three bands derive from measured data (boilerplate): single guards
    clean at 22.79, four-server health clean at 23.72, failures at 38-42."""

    def test_low_load_no_lanes_is_ok(self):
        # 22.79 was a confirmed-clean single-guard run. Assertion that would
        # fail: raising LOAD_OK below 23 makes this CAUTION.
        assert gp.classify(22.79, 16, 0) == gp.OK

    def test_confirmed_clean_health_run_is_ok(self):
        # 23.72 was health (four servers) running clean end-to-end. This pins
        # LOAD_OK >= 24 with margin — the boilerplate says "do not refuse on
        # low-to-mid 20s" and a #690 lane declined at 21-25 over-cautiously.
        assert gp.classify(23.72, 16, 0) == gp.OK

    def test_just_below_risk_is_caution(self):
        # 31.99 is one tick below the failure regime's lower bound. Assertion
        # that would fail: lowering LOAD_RISK below 32 makes this RISK.
        assert gp.classify(31.99, 16, 4) == gp.CAUTION

    def test_failure_regime_is_risk(self):
        # 38.0 is inside the measured 38-42 failure band. Assertion that would
        # fail: raising LOAD_RISK above 38 makes this CAUTION (waves through
        # the exact regime the gate exists to catch).
        assert gp.classify(38.0, 16, 4) == gp.RISK

    def test_risk_lower_bound(self):
        # 32.0 is the lower bound of the observed failure regime (#666 third
        # note: load 32.17 with six lanes). Pin the boundary inclusive.
        assert gp.classify(32.0, 16, 6) == gp.RISK

    def test_ok_boundary_exclusive(self):
        # LOAD_OK itself lands in CAUTION (it is the first "grey zone" value).
        assert gp.classify(gp.LOAD_OK, 16, 0) == gp.CAUTION


# ── None readings never render as zero (#671/#136) ─────────────────────

class TestNoneReadings:
    """A missing reading must name itself, never render as a calm zero."""

    def test_missing_load_with_lanes_is_caution(self):
        # The cause (fleet) is present even if the confirmation (load) is
        # absent. Assertion that would fail: returning OK on None load.
        assert gp.classify(None, 16, 3) == gp.CAUTION

    def test_missing_load_no_lanes_is_ok(self):
        # Nothing to act on. Assertion that would fail: returning CAUTION or
        # RISK on None load with no lanes (refuses when blind).
        assert gp.classify(None, 16, 0) == gp.OK

    def test_missing_lanes_renders_question_not_zero(self):
        # #675: discover_lanes sees only ccc. A None must NOT read as "0 lanes".
        # #728: '?' alone reads as one unknown beside a confident verdict; the
        # render must NAME the count unavailable so a reader knows the verdict
        # rests on load alone (the count half of #606's two legs is gone).
        msg = gp.render(gp.OK, 20.0, 16, None)
        assert "0 ccc lane" not in msg
        assert "?" in msg and "#675" in msg
        assert "unavailable" in msg

    def test_missing_load_renders_question_not_zero(self):
        msg = gp.render(gp.CAUTION, None, 16, 2)
        assert "load 0.0" not in msg
        assert "load ?" in msg


# ── the verdict line is greppable + actionable (#136) ──────────────────

class TestRenderContract:
    """The justfile greps on the leading verdict token; the RISK line must
    name the escape hatch or the refusal trains override (#136)."""

    def test_verdict_token_leads_the_line(self):
        # The justfile does `case "$_preflight" in *WRONG-ANSWER-RISK*)`.
        msg = gp.render(gp.RISK, 38.0, 16, 4)
        assert msg.startswith("guard preflight: WRONG-ANSWER-RISK ")

    def test_risk_names_the_force_escape_hatch(self):
        # #136: a refusal that does not say what to do trains override. The
        # brief: "there must remain a way to run deliberately under load."
        msg = gp.render(gp.RISK, 38.0, 16, 4)
        assert "DREAMWORK_GUARDS_FORCE=1" in msg

    def test_risk_names_a_subset_escape_hatch(self):
        msg = gp.render(gp.RISK, 38.0, 16, 4)
        assert "DREAMWORK_GUARDS=" in msg

    def test_caution_with_fleet_names_the_actionable_lever(self):
        # The lane count is the lever; "wait for the fleet" is actionable.
        msg = gp.render(gp.CAUTION, 28.0, 16, 3)
        assert "fleet" in msg

    def test_facts_bracket_carries_load_cores_lanes(self):
        msg = gp.render(gp.OK, 20.0, 16, 2)
        assert "[load 20.00" in msg
        assert "16 cores" in msg
        assert "2 ccc lane" in msg


# ── main is an instrument, not a gate ──────────────────────────────────

class TestMainExitsZero:
    """The instrument exits 0 always; the justfile owns the refusal. A Python
    exit code is the wrong layer for a refusal that must also print a banner
    and honor a force flag."""

    def test_main_exits_zero(self, capsys):
        rc = gp.main([])
        out = capsys.readouterr().out
        assert rc == 0
        assert "guard preflight:" in out


# ── #728: the except is narrowed; a contract break is loud (#136) ──────

class TestCountLanesExceptNarrowing:
    """#728: a contract break (TypeError/ValueError from the accessor's shape
    changing) must NOT be caught by the same handler as an OSError from /proc.
    #136: those are different facts — the first is a bug that must be loud, the
    second a legitimate unknown that returns None. The bare 'except Exception'
    that used to live here turned #675's arity change into a silent '?'."""

    def test_proc_unreadable_returns_none_not_raises(self, monkeypatch):
        # /proc unreadable => OSError => None (a legitimate unknown). The
        # production line whose reversion reds this: the 'except OSError:
        # return None' arm in count_lanes. Widen it back to 'except
        # Exception' and the contract-break test below still passes — THIS
        # one is the one that pins the OSError-only narrowing.
        import status_sync

        def boom_oserror(*a, **k):
            raise OSError("permission denied")

        monkeypatch.setattr(status_sync, "live_lane_count", boom_oserror)
        assert gp.count_lanes(Path("/tmp")) is None

    def test_contract_break_propagates_not_swallowed(self, monkeypatch):
        # THE DISCRIMINATING ASSERTION for #728 item 2: a ValueError (the
        # accessor's shape changed underneath the caller) MUST propagate,
        # not degrade to None. Reintroduce 'except Exception: return None'
        # in count_lanes and this reds (returns None instead of raising) —
        # which is exactly the defect that hid #675's arity change.
        import status_sync

        def boom_value(*a, **k):
            raise ValueError("not enough values to unpack (expected 3)")

        monkeypatch.setattr(status_sync, "live_lane_count", boom_value)
        import pytest
        with pytest.raises(ValueError):
            gp.count_lanes(Path("/tmp"))


class TestCountBrokenRender:
    """#728: when the accessor's contract breaks, main() renders a
    COUNT-BROKEN line that names the error and marks the verdict as resting
    on load alone — distinct from render()'s '?' (an unreadable /proc)."""

    def test_count_broken_names_the_error_type(self):
        msg = gp.render_count_broken(ValueError("arity changed"), 38.0, 16)
        assert msg.startswith("guard preflight: COUNT-BROKEN ")
        assert "ValueError" in msg
        assert "arity changed" in msg

    def test_count_broken_says_verdict_rests_on_load_alone(self):
        msg = gp.render_count_broken(TypeError("bad shape"), 38.0, 16)
        assert "LOAD ALONE" in msg
        # Still carries the load verdict token so the justfile RISK grep holds.
        assert "WRONG-ANSWER-RISK" in msg

    def test_main_prints_count_broken_on_contract_break(self, capsys,
                                                        monkeypatch):
        def boom(*a, **k):
            raise ValueError("discover_lanes arity changed")

        monkeypatch.setattr(gp, "count_lanes", boom)
        rc = gp.main([])
        out = capsys.readouterr().out
        assert rc == 0
        assert "COUNT-BROKEN" in out
        assert "ValueError" in out
        assert "LOAD ALONE" in out
