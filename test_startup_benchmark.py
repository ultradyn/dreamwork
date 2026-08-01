import json
import os
import subprocess
import sys

import pytest

from dev import startup_benchmark


def _env_with(path):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(path)
    return env


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
