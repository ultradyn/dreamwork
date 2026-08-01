"""#376 — guards refuse a port passed as the output directory.

Every dev/capture guard is `node <g>.mjs <outdir> [port]`. The one-argument
mistake (a port where the outdir belongs) used to mkdirSync a directory named
after the port and screenshot into it. These tests bind the shared `outdir()`
helper (unit + real-guard wiring) and pin the sweep so it cannot silently shrink.

Red-proof shape (the repo's two rules): each assertion is shown red by the
injection it names — the helper neutered to `return argv[2]` for the refusal
tests, one guard reverted for the drift guard — watched to fail, then restored
byte-identical with `cp`. See `.dreamwork/lessons.md`.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CAP = ROOT / "dev" / "capture"
HELPER = CAP / "outdir.mjs"

# Files that are NOT outdir-shaped and must NOT be forced onto the helper:
# above_fold.mjs is a flag-parsing CLI whose argv[2] is a file/url target, not
# an outdir; the rest are imported libraries / a server that read no argv[2].
EXEMPT = {
    "above_fold.mjs",
    "dom.mjs", "report.mjs", "optrace.mjs", "posturekeys.mjs", "serve.mjs",
    "outdir.mjs",  # the helper itself
}


def _guard_files():
    return sorted(p.name for p in CAP.glob("*.mjs"))


# --- helper unit (fast, no browser) ----------------------------------------

def _node_e(src):
    """Run a node ESM snippet (cwd = repo root) and return CompletedProcess."""
    return subprocess.run(
        ["node", "--input-type=module", "-e", src],
        cwd=str(ROOT), capture_output=True, text=True, timeout=60,
    )


def test_outdir_missing_refuses():
    src = "import { outdir } from './dev/capture/outdir.mjs'; outdir(['node','draft.mjs']);"
    r = _node_e(src)
    assert r.returncode != 0, r.stderr
    assert "usage:" in r.stderr, r.stderr
    assert "<outdir>" in r.stderr, r.stderr
    assert "draft.mjs" in r.stderr, r.stderr  # name derived from argv[1]


def test_outdir_all_digits_refuses():
    src = "import { outdir } from './dev/capture/outdir.mjs'; outdir(['node','draft.mjs','39898']);"
    r = _node_e(src)
    assert r.returncode != 0, r.stderr
    assert "39898" in r.stderr, r.stderr
    assert "usage:" in r.stderr, r.stderr


def test_outdir_all_digits_refused_even_with_default():
    src = ("import { outdir } from './dev/capture/outdir.mjs'; "
           "outdir(['node','reviewask.mjs','39898'], { default: '.' });")
    r = _node_e(src)
    assert r.returncode != 0, r.stderr
    assert "usage:" in r.stderr, r.stderr


def test_outdir_accepts_real_dirname():
    src = ("import { outdir } from './dev/capture/outdir.mjs'; "
           "process.stdout.write(outdir(['node','draft.mjs','my-output']));")
    r = _node_e(src)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "my-output", r.stdout


def test_outdir_default_when_missing():
    src = ("import { outdir } from './dev/capture/outdir.mjs'; "
           "process.stdout.write(outdir(['node','qsignal.mjs'], { default: '/tmp/x' }));")
    r = _node_e(src)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "/tmp/x", r.stdout


# --- guard-level wiring: the helper is actually called in a real guard ------

def _run_guard(guard, args, cwd):
    return subprocess.run(
        ["node", str(CAP / f"{guard}.mjs"), *args],
        cwd=str(cwd), capture_output=True, text=True, timeout=30,
    )


def _assert_port_refused(guard, tmp_path):
    # Precondition the check depends on: the guard actually calls outdir().
    # Name the production line that would have to change for this to pass when
    # it shouldn't — the `outdir(process.argv)` call / the helper's refusal.
    src = (CAP / f"{guard}.mjs").read_text()
    assert re.search(r"\boutdir\(", src), f"{guard}.mjs does not call outdir() — nothing under test"
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    r = _run_guard(guard, ["39898"], cwd=scratch)
    # (a) nonzero exit, (b) usage on stderr, (c) NO directory named after the port.
    assert r.returncode != 0, f"{guard}: port-as-outdir was ACCEPTED (exit 0)\n{r.stdout}"
    assert "usage:" in r.stderr, f"{guard}: no usage line on stderr\n{r.stderr}"
    assert not (scratch / "39898").exists(), (
        f"{guard}: created a directory NAMED AFTER THE PORT — the exact #376 defect")


def test_draft_refuses_port_as_outdir(tmp_path):
    _assert_port_refused("draft", tmp_path)  # Shape A: OUT,PORT=argv[3]||'39899'


def test_answers_refuses_port_as_outdir(tmp_path):
    _assert_port_refused("answers", tmp_path)  # Shape B: PORT=+(argv[3]||39890)


def test_reviewask_refuses_port_as_outdir(tmp_path):
    _assert_port_refused("reviewask", tmp_path)  # Shape D: OUT=argv[2]||'.' default


# --- drift guard: the sweep cannot silently shrink -------------------------

def test_no_guard_reads_argv2_directly():
    """After the sweep, no outdir-shaped guard reads process.argv[2] bare —
    every one routes through outdir(). A reverted guard reappears here."""
    violators = [
        name for name in _guard_files()
        if name not in EXEMPT
        and re.search(r"process\.argv\[2\]", (CAP / name).read_text())
    ]
    assert violators == [], f"guards bypassing outdir() (reading argv[2] bare): {violators}"


def test_outdir_sweep_count():
    """Every derived outdir-shaped guard imports the shared parser."""
    guard_files = set(_guard_files()) - EXEMPT
    assert {"draft.mjs", "wisp.mjs"} <= guard_files, (
        "outdir guard derivation found no plausible population: "
        f"missing sentinels {sorted({'draft.mjs', 'wisp.mjs'} - guard_files)}")
    importers = {
        name for name in _guard_files()
        if re.search(
            r"^import \{ outdir \} from './outdir\.mjs';$",
            (CAP / name).read_text(),
            re.MULTILINE,
        )
    }
    assert importers == guard_files, (
        f"guards missing shared outdir import: {sorted(guard_files - importers)}; "
        f"unexpected importers: {sorted(importers - guard_files)}")
