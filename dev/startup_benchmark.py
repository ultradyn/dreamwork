#!/usr/bin/env python3
"""Measure a Python module's version-style startup path without hiding the floor.

The target operation deliberately does almost nothing after import: it returns
the imported module's name.  This models a future ``version`` verb whose useful
work is negligible, while the paired interpreter control and warm-import probe
show where that time went.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


SENTINEL = "dreamwork-startup-probe-v1"
WARM_PREFIX = SENTINEL + ":"
DEFAULT_RUNS = 30
MIN_RUNS = 5

_TARGET_CODE = (
    "import importlib,sys; "
    "module=importlib.import_module(sys.argv[1]); "
    "value=module.__name__; "
    f"print({SENTINEL!r})"
)
_CONTROL_CODE = f"print({SENTINEL!r})"
_WARM_CODE = r"""
import importlib, json, sys, time
module = importlib.import_module(sys.argv[1])
warmups = int(sys.argv[2])
runs = int(sys.argv[3])
for _ in range(warmups):
    value = module.__name__
samples = []
for _ in range(runs):
    started = time.perf_counter_ns()
    value = module.__name__
    samples.append(time.perf_counter_ns() - started)
print("dreamwork-startup-probe-v1:" + json.dumps(samples))
"""


class BenchmarkError(RuntimeError):
    """The timed path did not produce a trustworthy observation."""


@dataclass(frozen=True)
class Distribution:
    samples: int
    minimum_ms: float
    p50_ms: float
    p95_ms: float
    maximum_ms: float
    mean_ms: float
    stdev_ms: float


# --- Baseline recording and comparison ----------------------------------
#
# The benchmark *measures* (noisy); recording and comparison are
# *deterministic* transforms over a result dict, so they are testable
# with fixed sample arrays — never by slowing the benchmark down.

BASELINE_SCHEMA = 2
REGRESSION_TOLERANCE = 0.25  # target-minus-interpreter p50 increase

_COMPARISON_EXIT_CODES = {
    "no_regression": 0,
    "regression": 1,
    "conditions_not_comparable": 3,
}


@dataclass(frozen=True)
class Comparison:
    """Structured result of comparing one measurement to a recorded baseline.

    The primary metric is always ``target_minus_interpreter_p50_ms``: the
    part of startup the codebase controls, with the interpreter floor
    subtracted so a machine change does not masquerade as a code change.
    """

    state: str
    metric: str
    baseline_p50_ms: float | None
    measured_p50_ms: float | None
    delta_ms: float | None
    delta_pct: float | None
    detail: str

    def exit_code(self) -> int:
        return _COMPARISON_EXIT_CODES[self.state]


def _percentile(sorted_values: Sequence[float], percentile: float) -> float:
    if not sorted_values:
        raise BenchmarkError("cannot summarise an empty sample set")
    position = (len(sorted_values) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] + (
        sorted_values[upper] - sorted_values[lower]
    ) * fraction


def distribution(samples_ns: Sequence[int]) -> Distribution:
    if not samples_ns:
        raise BenchmarkError("benchmark produced zero samples")
    values = sorted(value / 1_000_000 for value in samples_ns)
    return Distribution(
        samples=len(values),
        minimum_ms=values[0],
        p50_ms=statistics.median(values),
        p95_ms=_percentile(values, 0.95),
        maximum_ms=values[-1],
        mean_ms=statistics.fmean(values),
        stdev_ms=statistics.stdev(values) if len(values) > 1 else 0.0,
    )


def _run_timed(
    argv: Sequence[str], *, label: str, cwd: Path, env: dict[str, str]
) -> int:
    started = time.perf_counter_ns()
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    elapsed = time.perf_counter_ns() - started
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no output"
        raise BenchmarkError(
            f"{label} failed before yielding a sample "
            f"(exit {completed.returncode}): {detail}"
        )
    if completed.stdout.strip() != SENTINEL:
        raise BenchmarkError(
            f"{label} did not emit the required sentinel {SENTINEL!r}; "
            f"got {completed.stdout.strip()!r}"
        )
    return elapsed


def _run_warm(
    python: str,
    module: str,
    *,
    runs: int,
    warmups: int,
    cwd: Path,
    env: dict[str, str],
) -> list[int]:
    completed = subprocess.run(
        [python, "-c", _WARM_CODE, module, str(warmups), str(runs)],
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no output"
        raise BenchmarkError(
            "warm-import target failed before yielding samples "
            f"(exit {completed.returncode}): {detail}"
        )
    output = completed.stdout.strip()
    if not output.startswith(WARM_PREFIX):
        raise BenchmarkError(
            f"warm-import target did not emit prefix {WARM_PREFIX!r}; got {output!r}"
        )
    try:
        samples = json.loads(output[len(WARM_PREFIX):])
    except json.JSONDecodeError as exc:
        raise BenchmarkError("warm-import target emitted invalid sample JSON") from exc
    if (
        not isinstance(samples, list)
        or len(samples) != runs
        or any(not isinstance(value, int) or value < 0 for value in samples)
    ):
        raise BenchmarkError(
            f"warm-import target yielded {len(samples) if isinstance(samples, list) else 0} "
            f"valid-looking samples; expected exactly {runs}"
        )
    return samples


def benchmark_module(
    module: str,
    *,
    runs: int = DEFAULT_RUNS,
    warmups: int = 3,
    python: str = sys.executable,
    cwd: str | os.PathLike[str] = ".",
    env: dict[str, str] | None = None,
) -> dict[str, object]:
    """Benchmark one trivial response after importing ``module``.

    ``fresh_process`` starts a new interpreter for every observation, so
    Python's module cache cannot leak between samples.  It does *not* evict
    the kernel page cache.  ``warm_import`` imports once in one interpreter.
    """

    if runs < MIN_RUNS:
        raise BenchmarkError(f"runs must be at least {MIN_RUNS}, got {runs}")
    if warmups < 0:
        raise BenchmarkError(f"warmups must be non-negative, got {warmups}")
    if not module or any(not part.isidentifier() for part in module.split(".")):
        raise BenchmarkError(f"module must be a dotted Python name, got {module!r}")

    root = Path(cwd).resolve()
    child_env = dict(os.environ if env is None else env)
    target = [python, "-c", _TARGET_CODE, module]
    control = [python, "-c", _CONTROL_CODE]

    # This is intentionally the first child the harness starts.  It records
    # the only defensible "first observed" reading; it is not called OS-cold.
    first_observed_ns = _run_timed(
        target, label="benchmark target", cwd=root, env=child_env
    )

    for _ in range(warmups):
        _run_timed(control, label="interpreter control", cwd=root, env=child_env)
        _run_timed(target, label="benchmark target", cwd=root, env=child_env)

    target_samples: list[int] = []
    control_samples: list[int] = []
    for index in range(runs):
        pair = ((target, "benchmark target", target_samples),
                (control, "interpreter control", control_samples))
        if index % 2:
            pair = tuple(reversed(pair))
        for argv, label, destination in pair:
            destination.append(
                _run_timed(argv, label=label, cwd=root, env=child_env)
            )

    warm_samples = _run_warm(
        python, module, runs=runs, warmups=warmups, cwd=root, env=child_env
    )
    target_summary = distribution(target_samples)
    control_summary = distribution(control_samples)
    warm_summary = distribution(warm_samples)
    net_p50 = target_summary.p50_ms - control_summary.p50_ms

    return {
        "schema": 1,
        "module": module,
        "python": python,
        "runs": runs,
        "warmups": warmups,
        "first_observed_process_ms": first_observed_ns / 1_000_000,
        "fresh_process": asdict(target_summary),
        "interpreter_control": asdict(control_summary),
        "warm_import": asdict(warm_summary),
        "target_minus_interpreter_p50_ms": net_p50,
        "controls": {
            "fresh_python_import_state_each_sample": True,
            "paired_interpreter_control": True,
            "alternating_pair_order": True,
            "kernel_page_cache": "uncontrolled",
            "cpu_frequency_and_scheduler": "uncontrolled",
            "meaning_of_first_observed": (
                "first target child started by this invocation; page cache may predate it"
            ),
        },
    }


def format_report(result: dict[str, object]) -> str:
    def row(name: str, values: dict[str, object]) -> str:
        return (
            f"{name:20} n={values['samples']:>3}  "
            f"min={values['minimum_ms']:8.3f} ms  "
            f"p50={values['p50_ms']:8.3f} ms  "
            f"p95={values['p95_ms']:8.3f} ms  "
            f"max={values['maximum_ms']:8.3f} ms"
        )

    lines = [
        f"startup benchmark: import {result['module']} then return a trivial value",
        f"first observed process: {result['first_observed_process_ms']:.3f} ms",
        row("fresh process", result["fresh_process"]),  # type: ignore[arg-type]
        row("interpreter control", result["interpreter_control"]),  # type: ignore[arg-type]
        row("warm import", result["warm_import"]),  # type: ignore[arg-type]
        (
            "fresh p50 - interpreter p50: "
            f"{result['target_minus_interpreter_p50_ms']:.3f} ms"
        ),
        "controls: new interpreter per fresh sample; alternating target/control order; "
        "module imported once for warm samples",
        "not controlled: kernel page cache, CPU frequency, scheduler noise; "
        "the first observed process is not proof of an OS-cold read",
    ]
    return "\n".join(lines)


def capture_context() -> dict[str, object]:
    """Live host and load context for a baseline record.

    The load average conflates blocked-on-swap with running, so it is
    *context for human judgment*, never a gate the comparison refuses on.
    """
    uname = os.uname()
    load = os.getloadavg()
    return {
        "python_version": ".".join(str(v) for v in sys.version_info[:3]),
        "python_major_minor": ".".join(str(v) for v in sys.version_info[:2]),
        "platform": f"{uname.sysname} {uname.release} {uname.machine}",
        "hostname": uname.nodename,
        "cpu_count": os.cpu_count(),
        "loadavg_1m": load[0],
        "loadavg_5m": load[1],
        "loadavg_15m": load[2],
    }


def make_baseline(
    result: dict[str, object], context: dict[str, object] | None = None
) -> dict[str, object]:
    """Wrap a measurement *result* with host/load context into a baseline record.

    If *context* is ``None`` it is captured live; pass a fixed dict from a
    test to keep the function deterministic.
    """
    if context is None:
        context = capture_context()
    return {
        "schema": BASELINE_SCHEMA,
        "kind": "startup-baseline",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "context": context,
        "measured": result,
    }


def read_baseline_file(path: str | os.PathLike[str]) -> tuple[str, dict | None]:
    """Read a baseline file without raising for file-state issues.

    Returns ``(state, data)`` where *state* is one of ``'absent'``,
    ``'empty'``, ``'broken'``, ``'ok'``.  Only the ``'ok'`` state yields a
    populated *data* dict.
    """
    p = Path(path)
    if not p.exists():
        return ("absent", None)
    raw = p.read_text()
    if not raw.strip():
        return ("empty", None)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ("broken", None)
    if (
        not isinstance(data, dict)
        or data.get("schema") != BASELINE_SCHEMA
        or data.get("kind") != "startup-baseline"
        or "measured" not in data
        or "context" not in data
    ):
        return ("broken", None)
    return ("ok", data)


def compare_records(
    measured: dict[str, object], baseline: dict[str, object]
) -> Comparison:
    """Compare two baseline-shaped records by target-minus-interpreter p50.

    Refuses to judge (``conditions_not_comparable``) when the Python
    major.minor or the target module differs, because the interpreter floor
    or the import graph is no longer the same thing.  Load average is
    reported in *detail* for the human but never gates the verdict — any
    load threshold is a tuned literal that reds on a busy box for the wrong
    reason.
    """
    metric = "target_minus_interpreter_p50_ms"
    m = measured["measured"]
    b = baseline["measured"]
    m_ctx = measured["context"]
    b_ctx = baseline["context"]

    def _refuse(reason: str) -> Comparison:
        return Comparison(
            state="conditions_not_comparable",
            metric=metric,
            baseline_p50_ms=b.get("target_minus_interpreter_p50_ms"),
            measured_p50_ms=m.get("target_minus_interpreter_p50_ms"),
            delta_ms=None,
            delta_pct=None,
            detail=reason,
        )

    if m["module"] != b["module"]:
        return _refuse(
            f"module mismatch: measured {m['module']!r} vs baseline {b['module']!r}"
        )
    if m_ctx["python_major_minor"] != b_ctx["python_major_minor"]:
        return _refuse(
            f"python major.minor mismatch: measured "
            f"{m_ctx['python_major_minor']} vs baseline "
            f"{b_ctx['python_major_minor']} — interpreter floor moved"
        )

    m_net = m["target_minus_interpreter_p50_ms"]
    b_net = b["target_minus_interpreter_p50_ms"]
    delta = m_net - b_net
    pct = (delta / b_net * 100.0) if b_net else None
    m_load = m_ctx.get("loadavg_1m", float("nan"))
    b_load = b_ctx.get("loadavg_1m", float("nan"))
    load_note = (
        f"load 1m: measured {m_load:.2f}, baseline {b_load:.2f} "
        "(reported for judgment; not a gate)"
    )

    if delta > b_net * REGRESSION_TOLERANCE:
        return Comparison(
            state="regression",
            metric=metric,
            baseline_p50_ms=b_net,
            measured_p50_ms=m_net,
            delta_ms=delta,
            delta_pct=pct,
            detail=(
                f"target-minus-interpreter p50 regressed: "
                f"{b_net:.3f} → {m_net:.3f} ms (+{delta:.3f} ms). {load_note}"
            ),
        )
    direction = "improved" if delta < 0 else "within tolerance"
    return Comparison(
        state="no_regression",
        metric=metric,
        baseline_p50_ms=b_net,
        measured_p50_ms=m_net,
        delta_ms=delta,
        delta_pct=pct,
        detail=(
            f"target-minus-interpreter p50 {direction}: "
            f"{b_net:.3f} → {m_net:.3f} ms ({delta:+.3f} ms). {load_note}"
        ),
    )


def format_comparison(cmp: Comparison) -> str:
    lines = [
        f"startup comparison: {cmp.metric}",
        f"state: {cmp.state}",
    ]
    if cmp.baseline_p50_ms is not None:
        lines.append(f"baseline p50: {cmp.baseline_p50_ms:.3f} ms")
    if cmp.measured_p50_ms is not None:
        lines.append(f"measured p50: {cmp.measured_p50_ms:.3f} ms")
    if cmp.delta_ms is not None:
        lines.append(f"delta: {cmp.delta_ms:+.3f} ms ({cmp.delta_pct:+.1f}%)")
    lines.append(cmp.detail)
    return "\n".join(lines)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module", help="dotted module name to import")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--cwd",
        default=str(Path(__file__).resolve().parent.parent),
        help="working directory and import root (default: repository root)",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument(
        "--record",
        metavar="PATH",
        default=None,
        help="write the result as a dated baseline record to PATH",
    )
    parser.add_argument(
        "--compare",
        metavar="PATH",
        default=None,
        help="compare this run against the baseline record at PATH",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = benchmark_module(
            args.module,
            runs=args.runs,
            warmups=args.warmups,
            python=args.python,
            cwd=args.cwd,
        )
    except BenchmarkError as exc:
        print(f"startup_benchmark.py: REFUSED: {exc}", file=sys.stderr)
        return 2

    if args.record:
        record = make_baseline(result)
        Path(args.record).write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n"
        )
        print(f"baseline recorded → {args.record}", file=sys.stderr)

    if args.compare:
        state, data = read_baseline_file(args.compare)
        if state != "ok":
            code = {"absent": 4, "empty": 5, "broken": 6}[state]
            print(
                f"startup_benchmark.py: REFUSED: baseline {state}: "
                f"{args.compare}",
                file=sys.stderr,
            )
            return code
        measured_record = make_baseline(result)
        cmp = compare_records(measured_record, data)
        print(format_comparison(cmp))
        return cmp.exit_code()

    if args.as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(format_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
