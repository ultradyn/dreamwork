import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from dev import startup_benchmark
from dev.startup_benchmark import (
    BASELINE_SCHEMA,
    Comparison,
    REGRESSION_TOLERANCE,
    capture_context,
    compare_records,
    make_baseline,
    read_baseline_file,
)


def _env_with(path):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(path)
    return env


def test_module_contract_models_negligible_useful_work_without_a_bound_claim():
    assert (
        "models a future ``version`` verb whose useful\nwork is negligible"
        in startup_benchmark.__doc__
    ), "startup benchmark contract must state the workload it actually models"
    assert "upper bound" not in startup_benchmark.__doc__


def test_broken_timed_path_refuses_instead_of_reporting_a_fast_number(tmp_path):
    with pytest.raises(startup_benchmark.BenchmarkError) as caught:
        startup_benchmark.benchmark_module(
            "module_that_does_not_exist",
            runs=5,
            warmups=0,
            cwd=tmp_path,
        )
    assert "benchmark target failed before yielding a sample" in str(caught.value)
    assert "ModuleNotFoundError" in str(caught.value)


def test_fresh_samples_reimport_but_warm_samples_share_one_import(tmp_path):
    (tmp_path / "counted.py").write_text(
        "from pathlib import Path\n"
        "p = Path(__file__).with_suffix('.count')\n"
        "p.write_text(str(int(p.read_text()) + 1) if p.exists() else '1')\n"
    )
    result = startup_benchmark.benchmark_module(
        "counted",
        runs=5,
        warmups=0,
        cwd=tmp_path,
        env=_env_with(tmp_path),
    )
    # First-observed + five fresh samples + one warm worker.  If the harness
    # reused an interpreter between fresh samples this would be 2, not 7.
    assert (tmp_path / "counted.count").read_text() == "7"
    assert result["fresh_process"]["samples"] == 5
    assert result["warm_import"]["samples"] == 5


def test_interpreter_floor_is_reported_and_subtracted(tmp_path):
    (tmp_path / "empty_target.py").write_text("VALUE = 'version'\n")
    result = startup_benchmark.benchmark_module(
        "empty_target",
        runs=5,
        warmups=0,
        cwd=tmp_path,
        env=_env_with(tmp_path),
    )
    fresh = result["fresh_process"]["p50_ms"]
    control = result["interpreter_control"]["p50_ms"]
    assert result["target_minus_interpreter_p50_ms"] == pytest.approx(
        fresh - control
    )
    assert result["controls"]["kernel_page_cache"] == "uncontrolled"
    assert "not proof of an OS-cold read" in startup_benchmark.format_report(result)


def test_cli_json_contains_distributions_and_controls(tmp_path):
    (tmp_path / "target.py").write_text("VALUE = 'version'\n")
    completed = subprocess.run(
        [
            sys.executable,
            str(startup_benchmark.__file__),
            "target",
            "--runs", "5",
            "--warmups", "0",
            "--cwd", str(tmp_path),
            "--json",
        ],
        env=_env_with(tmp_path),
        text=True,
        capture_output=True,
        check=True,
    )
    report = json.loads(completed.stdout)
    assert report["fresh_process"]["samples"] == 5
    assert report["interpreter_control"]["samples"] == 5
    assert report["warm_import"]["samples"] == 5
    assert report["controls"]["fresh_python_import_state_each_sample"] is True


# ---------------------------------------------------------------------------
# Baseline recording and comparison — deterministic, fed fixed sample arrays.
# ---------------------------------------------------------------------------

_CTX_A = {
    "python_version": "3.14.6",
    "python_major_minor": "3.14",
    "platform": "Linux 7.1.3 x86_64",
    "hostname": "test-host",
    "cpu_count": 16,
    "loadavg_1m": 20.0,
    "loadavg_5m": 20.0,
    "loadavg_15m": 20.0,
}
_CTX_A_COPY = dict(_CTX_A)  # same conditions, independent dict

_CTX_DIFF_PY = {
    "python_version": "3.13.0",
    "python_major_minor": "3.13",
    "platform": "Linux 7.1.3 x86_64",
    "hostname": "test-host",
    "cpu_count": 16,
    "loadavg_1m": 20.0,
    "loadavg_5m": 20.0,
    "loadavg_15m": 20.0,
}


def _result(
    module: str = "watch",
    *,
    target_ns: list[int] | None = None,
    control_ns: list[int] | None = None,
    runs: int = 5,
) -> dict:
    """Build a benchmark result dict from fixed nanosecond sample arrays."""
    if target_ns is None:
        target_ns = [150_000_000] * runs  # 150 ms
    if control_ns is None:
        control_ns = [50_000_000] * runs  # 50 ms
    t = startup_benchmark.distribution(target_ns)
    c = startup_benchmark.distribution(control_ns)
    w = startup_benchmark.distribution([1_000] * runs)
    return {
        "schema": 1,
        "module": module,
        "python": sys.executable,
        "runs": runs,
        "warmups": 0,
        "first_observed_process_ms": target_ns[0] / 1_000_000,
        "fresh_process": asdict(t),
        "interpreter_control": asdict(c),
        "warm_import": asdict(w),
        "target_minus_interpreter_p50_ms": t.p50_ms - c.p50_ms,
        "controls": {},
    }


def test_make_baseline_wraps_full_distribution_not_a_scalar():
    # Sorted ms: [100, 110, 120, 130, 140] → p50=120, p95=138.
    result = _result(target_ns=[100_000_000, 110_000_000, 120_000_000,
                                130_000_000, 140_000_000])
    record = make_baseline(result, _CTX_A)
    assert record["schema"] == BASELINE_SCHEMA
    assert record["kind"] == "startup-baseline"
    fp = record["measured"]["fresh_process"]
    # The distribution carries sample count, p50 and p95 — a scalar would not.
    assert fp["samples"] == 5, "sample count must be recorded"
    assert fp["p50_ms"] == 120.0, "p50 must be recorded exactly"
    assert fp["p95_ms"] == pytest.approx(138.0), (
        "p95 must be distinct from p50 or the record cannot falsify a shift"
    )
    # control p50 is 50 ms → net = 70 ms
    assert record["measured"]["target_minus_interpreter_p50_ms"] == pytest.approx(70.0)


def test_make_baseline_records_load_and_host_context():
    result = _result()
    record = make_baseline(result, _CTX_A)
    ctx = record["context"]
    assert ctx["python_major_minor"] == "3.14"
    assert ctx["loadavg_1m"] == 20.0
    assert ctx["cpu_count"] == 16
    assert "hostname" in ctx


def test_capture_context_is_live_and_complete():
    ctx = capture_context()
    assert "." in ctx["python_major_minor"], "must carry at least major.minor"
    assert isinstance(ctx["loadavg_1m"], float)
    assert ctx["cpu_count"] is not None


def test_read_baseline_file_distinguishes_absent_empty_broken_ok(tmp_path):
    # absent
    state, data = read_baseline_file(tmp_path / "nope.json")
    assert state == "absent" and data is None
    # empty
    p = tmp_path / "empty.json"
    p.write_text("")
    state, data = read_baseline_file(p)
    assert state == "empty" and data is None
    # broken (unparseable)
    p = tmp_path / "broken.json"
    p.write_text("{not json")
    state, data = read_baseline_file(p)
    assert state == "broken" and data is None
    # broken (wrong schema)
    p = tmp_path / "wrong.json"
    p.write_text(json.dumps({"schema": 1, "kind": "other"}))
    state, data = read_baseline_file(p)
    assert state == "broken" and data is None
    # ok
    record = make_baseline(_result(), _CTX_A)
    p = tmp_path / "good.json"
    p.write_text(json.dumps(record))
    state, data = read_baseline_file(p)
    assert state == "ok"
    assert data is not None
    assert data["measured"]["module"] == "watch"


def test_compare_reports_regression_when_net_p50_exceeds_tolerance():
    # net p50 = 100 ms in both; measured doubles to 200 ms.
    baseline = make_baseline(_result(), _CTX_A)
    measured = make_baseline(
        _result(target_ns=[300_000_000] * 5),  # net = 300 - 50 = 250 ms
        _CTX_A_COPY,
    )
    cmp = compare_records(measured, baseline)
    assert cmp.state == "regression"
    assert cmp.baseline_p50_ms == 100.0
    assert cmp.measured_p50_ms == 250.0
    assert cmp.delta_ms == pytest.approx(150.0)
    assert cmp.exit_code() == 1


def test_compare_reports_no_regression_within_tolerance():
    baseline = make_baseline(_result(), _CTX_A)
    # net p50 moves from 100 to 110 ms (10 %, well within 25 %).
    measured = make_baseline(
        _result(target_ns=[160_000_000] * 5),  # net = 160 - 50 = 110 ms
        _CTX_A_COPY,
    )
    cmp = compare_records(measured, baseline)
    assert cmp.state == "no_regression"
    assert cmp.delta_ms == pytest.approx(10.0)
    assert cmp.exit_code() == 0


def test_compare_refuses_when_python_version_differs():
    baseline = make_baseline(_result(), _CTX_A)
    measured = make_baseline(_result(), _CTX_DIFF_PY)
    cmp = compare_records(measured, baseline)
    assert cmp.state == "conditions_not_comparable"
    assert "python major.minor mismatch" in cmp.detail
    assert cmp.exit_code() == 3


def test_compare_refuses_when_module_differs():
    baseline = make_baseline(_result("watch"), _CTX_A)
    measured = make_baseline(_result("dreamwork_db"), _CTX_A_COPY)
    cmp = compare_records(measured, baseline)
    assert cmp.state == "conditions_not_comparable"
    assert "module mismatch" in cmp.detail
    assert cmp.exit_code() == 3


def test_compare_uses_target_minus_interpreter_not_end_to_end():
    """End-to-end improved but target-minus-interpreter regressed: the
    comparison must catch the regression because it compares the part the
    codebase controls, not the floor that moved."""
    # Baseline: interpreter 50 ms, target 150 ms → net 100 ms.
    baseline = make_baseline(_result(), _CTX_A)
    # Measured: interpreter 20 ms (faster machine), target 180 ms → net 160 ms.
    # End-to-end improved (150→180 is worse actually... let me reconsider)
    # Measured: interpreter 10 ms, target 140 ms → net 130 ms.
    # End-to-end improved (150→140), but net regressed (100→130, +30%).
    measured = make_baseline(
        _result(target_ns=[140_000_000] * 5, control_ns=[10_000_000] * 5),
        _CTX_A_COPY,
    )
    cmp = compare_records(measured, baseline)
    assert cmp.state == "regression", (
        "net p50 went 100→130 (+30 %, above 25 % tolerance) even though "
        "end-to-end improved 150→140"
    )
    assert cmp.measured_p50_ms == pytest.approx(130.0)
    assert cmp.baseline_p50_ms == pytest.approx(100.0)


def test_cli_record_and_compare_round_trip(tmp_path):
    record_path = tmp_path / "baseline.json"
    result = _result(target_ns=[150_000_000] * 5)
    record = make_baseline(result, _CTX_A)
    record_path.write_text(json.dumps(record))
    state, data = read_baseline_file(record_path)
    assert state == "ok"
    cmp = compare_records(make_baseline(result, _CTX_A_COPY), data)
    assert cmp.state == "no_regression"
    assert cmp.delta_ms == pytest.approx(0.0)
