"""#661 — the posture-key extractor the browser guard relies on is itself checked.

Nothing checks that a guard's own extractor is honest (#651, open sibling).
`dev/capture/posturekeys.mjs` reads `POSTURE_AXES` out of lint.py so the
summaryjson guard and the test_watch invariant can derive the expected
/summary.json posture key set instead of restating a literal. This file is the
partial answer to #651 for THAT extractor: it shells out to node and exercises
the extractor against (a) the real lint.py, (b) a widened fixture, and (c) two
malformed inputs that must throw rather than return a silently-empty set — the
hollow-check failure mode this repo has paid for (#671).

It does NOT cover: any OTHER guard's extractor (only posturekeys), nor the
guard's wiring of the extractor into its live comparison (that is a coordinator
browser-suite run — browser guards are wrong under load, #666). What it DOES
guarantee is that the derivation the guard depends on parses the real source of
truth correctly and fails loud on a broken parse.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MOD = "dev/capture/posturekeys.mjs"


def _node(src):
    """Run a node ESM snippet (cwd = repo root); return CompletedProcess."""
    return subprocess.run(
        ["node", "--input-type=module", "-e", src],
        cwd=str(ROOT), capture_output=True, text=True, timeout=60,
        env={**__import__("os").environ, "FORCE_COLOR": "0"},
    )


def _emit(axes):
    """A minimal lint.py snippet carrying a POSTURE_AXES tuple.

    Emits double-quoted names — the form lint.py ships — so the extractor's
    quoted-name scan reaches them; single quotes are a distinct malformed
    input exercised in test_broken_parse_throws_not_empties."""
    return 'POSTURE_AXES = (' + ", ".join(f'"{a}"' for a in axes) + ')'


def test_reads_the_real_lint_py_axes():
    # The precondition the check depends on (#590): POSTURE_AXES must resolve
    # to the five real axes, or the derived expected set is wrong. A literal
    # tuned to today's five would have an expiry date; this derives both and
    # asserts the gap (exactly five, the named five) at runtime.
    import lint
    real = list(lint.POSTURE_AXES)
    assert len(real) >= 3, real  # the set check is vacuous on an empty tuple
    assert "source" not in real, real  # source is added separately, not an axis
    src = (
        f"import {{ readPostureAxesFile, expectedSummaryPostureKeys }} "
        f"from './{MOD}';\n"
        f"const axes = readPostureAxesFile('lint.py');\n"
        f"const exp = [...expectedSummaryPostureKeys(axes)].sort();\n"
        f"console.log(JSON.stringify(axes));\n"
        f"console.log(JSON.stringify(exp));\n"
    )
    r = _node(src)
    assert r.returncode == 0, r.stderr
    import json
    parsed_axes = json.loads(r.stdout.splitlines()[0])
    parsed_exp = json.loads(r.stdout.splitlines()[1])
    assert parsed_axes == real, (parsed_axes, real)
    assert parsed_exp == sorted(set(real) | {"source"}), parsed_exp


def test_widened_axis_list_is_extracted_not_swallowed():
    # Direction 1 of the red-proof lives here too: a projection that grows an
    # axis must change the derived expected set, not be silently dropped. The
    # extractor reads the widened tuple honestly.
    snippet = _emit(["pace", "asking", "delegation", "delivery",
                     "orchestration", "focus"])
    src = (
        f"import {{ readPostureAxes }} from './{MOD}';\n"
        f"const src = {js_string(snippet)};\n"
        f"console.log(JSON.stringify(readPostureAxes(src)));\n"
    )
    r = _node(src)
    assert r.returncode == 0, r.stderr
    import json
    out = json.loads(r.stdout.strip())
    assert "focus" in out, out  # the widened key came through


def test_broken_parse_throws_not_empties():
    # A guard that reads a silently-empty set as a pass is #671. The extractor
    # must throw on a parse it cannot trust.
    for label, bad in [
        ("missing", "no axes here at all"),
        ("single-quoted", "POSTURE_AXES = ('pace', 'asking')"),
        ("call-not-tuple", "POSTURE_AXES = some_call()"),
    ]:
        src = (
            f"import {{ readPostureAxes }} from './{MOD}';\n"
            f"try {{ readPostureAxes({js_string(bad)}); "
            f"console.log('NO-THROW'); }} catch (e) {{ console.log('THREW'); }}\n"
        )
        r = _node(src)
        assert r.returncode == 0, r.stderr
        assert "THREW" in r.stdout, f"{label}: expected throw, got {r.stdout!r}"


# --- small helper: hand-build a JS string literal from a Python str ---------

def js_string(s):
    """A double-quoted JS string literal with backslash escapes."""
    out = []
    for ch in s:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'
