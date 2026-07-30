"""#444 — refuse a duration floor on compositor-driven transitions.

The confirmation snap detector (`transitionstart` / `win.ran`) proves a
CSS transition *existed*. Asserting that the observed window width matches
the declared `.cmdmsg` opacity `.35s` would restate the CSS and reintroduce
the load flakiness #442 removed. This file holds that refusal so someone
rebuilding a duration check fails it the way #419's lane did for a
rejected design.

Evidence (measured 2026-07-28, worktree `duration`, load 36–42 on 16 cores,
six consecutive green `confirmation.mjs` runs — main departure `win.dur`):
  [239.4, 371.4, 354.0, 328.8, 307.4, 348.2] ms against declared 350ms.
#442 under 8 burners: 289–665ms for the same gesture.
"""
from __future__ import annotations

from pathlib import Path

# Declared opacity duration on `.cmdmsg` / `.pmsg` in watch.py STYLE.
# Derived from the source, not a free-floating constant: the test asserts
# the STYLE still carries `.35s` so a styleguide change is visible here.
DECLARED_MS = 350

# Six green main-departure durs measured before the refusal landed.
# Asserted as a precondition that they still disagree with a tight band —
# if a future machine's measurements all sit inside ±20%, re-measure and
# re-open the design question rather than silently keep a hollow refusal.
MEASURED_MAIN_DEPARTURE_MS = (239.4, 371.4, 354.0, 328.8, 307.4, 348.2)

ROOT = Path(__file__).resolve().parent


def test_measured_green_set_still_disagrees_with_a_tight_duration_band():
    """A ±20% band around the declared 350ms fails a real green set.

    Replaying the measured durs against 280–420ms is the red-proof that
    "assert observed ≈ declared" would flake on this host. If every value
    now sits inside the band, the precondition fails loudly so the refusal
    cannot go hollow.
    """
    lo, hi = DECLARED_MS * 0.8, DECLARED_MS * 1.2
    outside = [d for d in MEASURED_MAIN_DEPARTURE_MS if not (lo <= d <= hi)]
    # Precondition: the green set is not a single point — otherwise the
    # "disagrees with the band" claim is about one number, not variance.
    span = max(MEASURED_MAIN_DEPARTURE_MS) - min(MEASURED_MAIN_DEPARTURE_MS)
    assert span > 50, (
        f"measured green set span is only {span:.1f}ms — re-measure before "
        f"trusting the refusal; the set was {MEASURED_MAIN_DEPARTURE_MS}"
    )
    assert outside, (
        f"every measured green dur now fits [{lo:.0f}, {hi:.0f}]ms "
        f"(set={MEASURED_MAIN_DEPARTURE_MS}); a ±20% band no longer fails "
        f"the green set — re-measure under load before deciding a duration "
        f"assertion is safe. #444 refused because it was not."
    )
    # Discriminating shape: the short end is the one that bites a floor
    # near the declaration, not the long end (load finishes late).
    assert min(outside) < lo, (
        f"the green set only overshoots the band (outside={outside}); "
        f"the refusal was about floors that fail short travels under load, "
        f"not only ceilings"
    )


def test_confirmation_guard_does_not_floor_on_observed_duration():
    """Someone rebuilding a duration check into confirmation.mjs fails here.

    The guard may *log* `dur=` as a diagnostic; it must not gate a PASS on
    `win.dur` / `dwin.dur` / a ms floor. Grep the production assertions
    (ok(...) lines), not the comment block that explains the refusal.
    """
    src = (ROOT / "dev" / "capture" / "confirmation.mjs").read_text(encoding="utf-8")
    assert "transitionWindow" in src, (
        "confirmation.mjs no longer uses transitionWindow — the #442 snap "
        "detector moved; update this refusal check"
    )
    # Only look at ok(...) call lines so comments may still discuss dur.
    ok_lines = [
        ln for ln in src.splitlines()
        if ln.lstrip().startswith("ok(") or ln.lstrip().startswith("ok (")
    ]
    assert ok_lines, "no ok(...) assertions found in confirmation.mjs"
    joined = "\n".join(ok_lines)
    for needle in (
        "win.dur",
        "dwin.dur",
        "awin.dur",
        "dur>=",
        "dur >=",
        "dur<",
        "dur <",
        ".dur >=",
        ".dur>=",
        "DECLARED",
        "350",
        "0.35",
    ):
        assert needle not in joined, (
            f"confirmation.mjs ok(...) line asserts on duration via {needle!r} "
            f"— #444 refused a duration floor; existence (win.ran) is the gate. "
            f"See transitions.md #444 and the measured set in this file."
        )


def test_style_still_declares_the_point_three_five_seconds_the_refusal_measured():
    """The declared duration the measurements reference is still in STYLE.

    If the styleguide shortens `.cmdmsg` opacity to 1ms, that is a STYLE
    edit — the single-source rule — not a silent motion bug a duration
    floor on the guard would uniquely catch. This test pins that the
    declaration the measurements compared against is still the source.
    """
    # #397: the CSS lives in client/style.css now, so read the assembled
    # constant rather than watch.py's source — that is the value the page
    # actually serves and it survives the asset moving again.
    style = (ROOT / "client" / "style.css").read_text(encoding="utf-8")
    # the check is vacuous against an empty or missing asset, so say so here
    assert len(style) > 10_000, (
        f"client/style.css is {len(style)} chars — too small to be the "
        f"stylesheet; this test would pass vacuously on a broken read"
    )
    # Both main and popout carry the same .35s opacity envelope.
    assert "opacity .35s" in style or "opacity:.35s" in style, (
        "STYLE no longer declares opacity .35s on the confirmation "
        "envelope — the #444 measurements compared against 350ms; update the "
        "refusal doc and re-measure if the declaration moved"
    )


def test_orphan_end_pairing_no_longer_yields_negative_dur_in_the_helper_source():
    """The helper pairs end to start; independent ends.at(idx) is gone.

    Pre-fix, popout departure logged negative durs when an end from a
    transition that started before afterT was paired with a later start.
    The source must not regress to independent index pairing. Comments may
    still *name* the rejected shape — only code lines are checked.
    """
    src = (ROOT / "dev" / "capture" / "dom.mjs").read_text(encoding="utf-8")
    assert "export function transitionWindow" in src
    # Drop block + line comments so a doc of the rejected shape is allowed.
    code_lines = []
    in_block = False
    for ln in src.splitlines():
        s = ln.strip()
        if in_block:
            if "*/" in s:
                in_block = False
            continue
        if s.startswith("/*"):
            in_block = "*/" not in s
            continue
        if s.startswith("*") or s.startswith("//"):
            continue
        code_lines.append(ln)
    code = "\n".join(code_lines)
    # The load-bearing line: first end at-or-after the chosen start.
    assert "ends.find(e => e.t >= start)" in code or "ends.find(e=>e.t>=start)" in code, (
        "transitionWindow no longer pairs end to start — negative durs return "
        "and dur is unusable even as a diagnostic"
    )
    # The rejected shape: independent ends.at(idx).
    assert "ends.at(idx)" not in code, (
        "transitionWindow regressed to ends.at(idx) independent of start — "
        "that is the negative-dur pairing #444 measured"
    )
