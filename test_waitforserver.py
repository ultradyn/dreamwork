"""#388 — waitForServer: honest server readiness at the navigation seam.

A guard whose own watch.py is starved at extreme load throws a raw
`TypeError: fetch failed [cause] ECONNREFUSED` before the server binds — the
worst class a guard has ("threw before finishing", neither pass nor fail).
`waitForServer` (dev/capture/dom.mjs) polls the endpoint until it responds or
throws a NAMED error on deadline, so the reader is sent to the infrastructure.

Measurement (#388): the failure is STARTUP, not mid-run. Once the kernel has
the listen socket the server never drops under CPU contention (0 drops in every
probe run), so a readiness poll is the correct primitive and a mid-run
death-detector would chase the wrong bug.

Red-proof shape (the repo's two rules): each assertion is shown red by the
injection it names — the helper sabotaged to swallow its error and return
instead of throwing, watched to fail the deadline assertions, then restored
byte-identical with `cp`. See `.dreamwork/lessons.md`.
"""
import os
import re
import socket
import time
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOM = ROOT / "dev" / "capture" / "dom.mjs"


def _dead_port():
    """A port nothing is listening on — bind, grab, close. The next connect
    to it produces ECONNREFUSED, the exact error waitForServer converts."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _node_e(src):
    """Run a node ESM snippet (cwd = repo root) and return CompletedProcess.

    `FORCE_COLOR=0` because this stdout is PARSED, not read. node colourises a
    bare number through util.inspect, so under any parent that exports
    FORCE_COLOR — agent CLIs do, which is how this was found — the deadline
    snippet's `console.log(elapsed)` arrives as `\\x1b[33m656\\x1b[39m` and
    `int()` dies on a run where the code under test was CORRECT: an
    environment-dependent red, the kind that gets dismissed as flake. Setting
    it here rather than in the one snippet keeps the next snippet honest too.
    `NO_COLOR`/`NODE_DISABLE_COLORS` cannot do this job — node ignores both
    when FORCE_COLOR is set, and says so on stderr.
    """
    return subprocess.run(
        ["node", "--input-type=module", "-e", src],
        cwd=str(ROOT), capture_output=True, text=True, timeout=60,
        env={**os.environ, "FORCE_COLOR": "0"},
    )


# --- the deadline path: named error, not raw ECONNREFUSED -------------------

def test_dead_port_throws_named_error():
    """The whole point of #388: a starved server surfaces as a NAMED error,
    not raw ECONNREFUSED. Point waitForServer at a port with nothing on it."""
    port = _dead_port()
    src = (
        "import { waitForServer } from './dev/capture/dom.mjs';\n"
        "try {\n"
        "  await waitForServer('http://127.0.0.1:%d', { timeoutMs: 800 });\n"
        "  console.log('NO_THROW');\n"
        "} catch (e) {\n"
        "  console.log('THREW:' + e.message);\n"
        "}" % port
    )
    r = _node_e(src)
    assert r.returncode == 0, r.stderr
    assert "THREW:" in r.stdout, (
        f"waitForServer did not throw on a dead port:\n{r.stdout}\n{r.stderr}")
    msg = r.stdout.split("THREW:", 1)[1].strip()
    assert "never came up" in msg, (
        f"error does not name the failure honestly:\n{msg}")
    assert "800ms" in msg, (
        f"error does not state the deadline it waited:\n{msg}")
    # The raw ECONNREFUSED must NOT be the top-level verdict — it is carried
    # as context inside the message, not thrown bare.
    assert "ECONNREFUSED" in msg, (
        f"error does not carry the underlying cause:\n{msg}")


def test_dead_port_within_deadline():
    """The named error arrives within roughly the deadline, not after a
    longer goto timeout — this is NOT a timeout bump, it is a bounded wait."""
    port = _dead_port()
    src = (
        "import { waitForServer } from './dev/capture/dom.mjs';\n"
        "const t0 = Date.now();\n"
        "try {\n"
        "  await waitForServer('http://127.0.0.1:%d', { timeoutMs: 600 });\n"
        "} catch (e) {}\n"
        "console.log(Date.now() - t0);" % port
    )
    r = _node_e(src)
    elapsed = int(r.stdout.strip())
    # Should be close to 600ms, not minutes. Generous upper bound to avoid
    # flake on a loaded CI box; the point is it is BOUNDED, not unbounded.
    assert elapsed < 5000, f"waitForServer took {elapsed}ms — not bounded by deadline"
    # And not suspiciously fast (that would mean it did not poll at all).
    assert elapsed >= 400, f"waitForServer took {elapsed}ms — did not poll until deadline"


# --- the live path: returns true when the server answers -------------------

def test_live_server_returns_true():
    """waitForServer returns true (does not throw) when something IS
    listening. Uses a tiny http server that answers immediately."""
    src = (
        "import { waitForServer } from './dev/capture/dom.mjs';\n"
        "import { createServer } from 'node:http';\n"
        "const s = createServer((req, res) => res.end('ok'));\n"
        "await new Promise(r => s.listen(0, '127.0.0.1', r));\n"
        "const port = s.address().port;\n"
        "const ok = await waitForServer(`http://127.0.0.1:${port}`, { timeoutMs: 5000 });\n"
        "console.log(ok ? 'READY' : 'NOT_READY');\n"
        "s.close();\n"
    )
    r = _node_e(src)
    assert r.returncode == 0, r.stderr
    assert "READY" in r.stdout, (
        f"waitForServer did not return true on a live server:\n{r.stdout}\n{r.stderr}")


# --- drift guard: the helper is exported and adopted -----------------------

def test_waitforserver_exported():
    """The helper exists and is named — a rename or accidental removal shows
    up here, not in a guard crash at 3am."""
    src = DOM.read_text()
    assert re.search(r"export\s+async\s+function\s+waitForServer\b", src), (
        "waitForServer is not exported from dom.mjs")
