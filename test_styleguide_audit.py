"""Tests for dev/styleguide_audit.py (#314).

The audit walks git history, but the DECISION it makes is pure: does a diff's
post-image line spans overlap a UI constant's range (resolved per-commit), and
does the escape hatch match. These tests pin that logic on synthetic fixtures
so a regression is caught without depending on history that shifts. The first
test is the one that matters most — a check that has never been red proves
nothing, and this repo has caught three that were passing on their own bug.
"""

import ast

import dev.styleguide_audit as a


# ─── ui_ranges: the per-commit boundary resolution ──────────────────────────

# Mirrors watch.py's real shapes: STYLE closes with `</style>` AND the triple-
# quote on one line (ast must catch this; a lone-triple-quote-line scan would
# not), APP_BODY closes the same way, a *_JS block closes on its own line, and
# there is non-UI Python (server/parser) between and around them.
SAMPLE_WATCHPY = """\
#!/usr/bin/env python3
import re

SERVER_REGEX = re.compile(r"foo")

STYLE = \"\"\"<style>
  .qa textarea { padding:.4rem; }
</style>\"\"\"

APP_BODY = \"\"\"<canvas id="dreambg"></canvas>
<div id="root"></div>\"\"\"

def parse_ledger(text):
    return set()

ROUTER_JS = \"\"\"
const TINT = { dashboard: 0.0, questions: 0.14 };
function go() { return TINT; }
\"\"\"

COMMAND_JS = \"\"\"
const send = () => {};
\"\"\"

PAGE = page_shell('dreamwork watch', APP_BODY)
"""


def test_ui_ranges_uses_ast_and_handles_shared_line_close():
    ranges = {name: (s, e) for name, s, e in a.ui_ranges(SAMPLE_WATCHPY)}
    # STYLE spans from its `STYLE = """` line through the `</style>"""` line.
    assert ranges["STYLE"] == (6, 8)
    # APP_BODY closes on the line carrying `</div>` + the triple-quote.
    assert ranges["APP_BODY"] == (10, 11)
    # A *_JS block closing on its own triple-quote line is still bounded right.
    assert ranges["ROUTER_JS"] == (16, 19)
    assert ranges["COMMAND_JS"] == (21, 23)
    # Non-UI module names are never returned even though they are assignments.
    assert "SERVER_REGEX" not in ranges
    assert "PAGE" not in ranges  # a call, not a triple-quoted literal


def test_ui_ranges_text_fallback_when_unparseable():
    # A historical revision that does not parse must still resolve boundaries.
    # Inject a syntax error; ast bails, the text fallback takes over and lands
    # the SAME ranges (the closing-triple-quote scan is robust to </style>\"\"\").
    broken = SAMPLE_WATCHPY.replace("import re", "import !!! broken", 1)
    assert "import !!! broken" in broken  # the precondition the test depends on
    via_ast = a.ui_ranges(SAMPLE_WATCHPY)
    via_fallback = a.ui_ranges(broken)
    assert via_ast == via_fallback


# ─── touched_constants: the diff-vs-UI overlap decision ─────────────────────

RANGES = [
    ("STYLE", 6, 9),
    ("APP_BODY", 11, 12),
    ("ROUTER_JS", 17, 20),
]


def test_overlap_inside_constant_is_ui():
    # A hunk editing CSS inside STYLE (post-image lines 7..7) -> touches STYLE.
    assert a.touched_constants([(7, 7)], RANGES) == ["STYLE"]


def test_overlap_outside_every_constant_is_not_ui():
    # A hunk editing parse_ledger (line 14, between APP_BODY and ROUTER_JS) ->
    # server/parser work, no UI constant touched.
    assert a.touched_constants([(14, 15)], RANGES) == []


def test_overlap_at_constant_boundary_is_ui():
    # Editing the line that opens ROUTER_JS (line 17) is UI, even though the
    # hunk's only changed line is the `ROUTER_JS = \"\"\"` header itself.
    assert a.touched_constants([(17, 17)], RANGES) == ["ROUTER_JS"]


def test_pure_deletion_via_context_still_overlaps():
    # A hunk that only removes a CSS rule still carries context lines inside
    # the constant, so its post-image span overlaps. This is why the filter
    # tests the hunk span (not only `+` lines): deleting UI counts as UI.
    assert a.touched_constants([(6, 8)], RANGES) == ["STYLE"]


def test_multiple_constants_touched_in_order():
    # A sprawling hunk spanning STYLE into ROUTER_JS names both, once each,
    # in source order.
    assert a.touched_constants([(8, 18)], RANGES) == ["STYLE", "APP_BODY", "ROUTER_JS"]


# ─── the escape hatch: narrow, auditable, never the default path ────────────

def test_hatch_matches_trailer_in_body():
    body = "fix(#999): a thing\n\nStyleguide: n/a\n"
    assert a.HATCH_RE.search(body) is not None


def test_hatch_is_case_insensitive_and_allows_inner_space():
    assert a.HATCH_RE.search("Styleguide:n/a\n") is not None
    assert a.HATCH_RE.search("styleguide: N/A\n") is not None


def test_hatch_does_not_match_prose_or_other_trailers():
    # The phrase inside a sentence must not trigger the hatch — it is a trailer.
    assert a.HATCH_RE.search("We set the styleguide: n/a is not a real trailer here.\n") is None
    assert a.HATCH_RE.search("Migration: drop the old table\n") is None
    # A doc file literally named in prose is not a hatch.
    assert a.HATCH_RE.search("see watch-design.md for the styleguide\n") is None


# ─── anti-vacuity: UI_CONSTANTS must track watch.py at HEAD ─────────────────
# If a UI constant is renamed, the filter would silently miss UI changes in it
# — every commit would classify non-UI and the audit would go permanently green
# for the wrong reason. This is the hollow-check failure mode this repo has
# paid for three times, pinned at the source. (A genuinely NEW UI block added
# under a non-UI-y name is a residual a reviewer catches; the common case — a
# rename or removal of a known UI constant — is what this guards.)

def test_ui_constants_track_watch_py_at_head():
    src = open("watch.py").read()
    tree = ast.parse(src)
    present = set()
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            present.add(node.targets[0].id)
    # Every tracked UI constant still exists (a rename removes the old name).
    assert set(a.UI_CONSTANTS) <= present, (
        "a UI constant in UI_CONSTANTS is gone from watch.py — likely renamed; "
        "update dev/styleguide_audit.py. missing=%r"
        % sorted(set(a.UI_CONSTANTS) - present)
    )
    # Every UI-SHAPED module string (ends in _JS, or is STYLE/APP_BODY) is
    # tracked — a new UI block added under a UI-y name must be registered.
    ui_shaped = {
        n for n in present if n.endswith("_JS") or n in ("STYLE", "APP_BODY")
    }
    assert ui_shaped == set(a.UI_CONSTANTS), (
        "watch.py's UI-shaped module strings drifted from UI_CONSTANTS — "
        "update dev/styleguide_audit.py so the filter does not silently miss "
        "UI changes. ui_shaped=%r UI_CONSTANTS=%r"
        % (sorted(ui_shaped), list(a.UI_CONSTANTS))
    )


# ─── nearest_entry: the window's unit, and what may vouch for a change (#320) ─

def _fixture(spec):
    """Build (rel, has_entry, is_ui_at) from a compact spec string.

    One character per commit in history order: `.` bookkeeping (ledger, merge —
    irrelevant, excluded from the window), `u` a UI commit with no styleguide
    file, `U` a UI commit that also carries one, `d` a docs-only commit (a
    styleguide file, no UI), `w` a non-UI watch.py commit (parser/server — it
    IS relevant so it consumes window budget, but it neither documents nor
    blocks). Indices are positions in the full history, so the fixture
    exercises the very thing #320 is about: the gap between "commits" and
    "commits the window counts".

    `rel` is derived by calling the REAL window_positions, never rebuilt here.
    That is load-bearing and was learned the hard way: an earlier version of
    this fixture computed `rel` itself, and reverting the window's unit back
    to raw commits left all of these tests GREEN — they were exercising
    nearest_entry's walk over a list the test itself had already filtered,
    so the one decision #320 is about was outside the check entirely.
    """
    files = {
        ".": frozenset({"README.md"}),          # ledger/merge: irrelevant
        "u": frozenset({"watch.py"}),
        "U": frozenset({"watch.py", "watch-design.md"}),
        "d": frozenset({"watch-design.md"}),
        "w": frozenset({"watch.py"}),           # UI-ness is a diff property
    }
    commits = [(str(i), str(i)) for i in range(len(spec))]
    _, rel = a.window_positions(commits, lambda full: files[spec[int(full)]])
    return (
        rel,
        lambda i: bool(files[spec[i]] & frozenset(a.STYLEGUIDE_FILES)),
        lambda i: spec[i] in ("u", "U"),
    )


def test_bookkeeping_between_a_change_and_its_entry_does_not_hide_it():
    # The #320 case, verbatim in shape: cdb89df (a UI change) then SIX
    # bookkeeping commits then the commit documenting it. Counted in raw
    # commits the entry is 7 away and invisible at window=3; counted in
    # relevant commits it is the very next one.
    spec = "u......d"
    rel, has_entry, is_ui = _fixture(spec)
    # Precondition, asserted rather than assumed: the gap must actually
    # EXCEED the window in raw commits, or this test proves nothing. A
    # fixture edit that shortens the run would otherwise pass vacuously.
    raw_gap = spec.index("d") - spec.index("u")
    assert raw_gap > 3, f"fixture no longer spans past window=3 (gap {raw_gap})"
    found, q = a.nearest_entry(rel.index(0), rel, 3, has_entry, is_ui)
    assert found, "a UI change lost its entry to a run of ledger commits"
    assert rel[q] == spec.index("d")


def test_a_neighbouring_ui_commit_never_vouches_for_this_one():
    # The a6e98cc/f17f307 case: the next relevant commit is a UI commit that
    # carries a styleguide file. That entry documents ITS OWN change, so it
    # must not clear this one. This is the assertion that keeps the filter
    # from being a pure widening of the window — without it the pre-baseline
    # reports 0 misses instead of 11.
    rel, has_entry, is_ui = _fixture("uU")
    found, _ = a.nearest_entry(0, rel, 3, has_entry, is_ui)
    assert not found, (
        "a different UI commit's styleguide entry was credited to this "
        "change — sideways credit makes the audit unable to fail"
    )


def test_a_ui_commit_blocks_the_search_from_reaching_past_it():
    # Undocumented UI, then another undocumented UI, then a docs commit. The
    # docs commit belongs to the nearer UI change; the far one stays a MISS.
    rel, has_entry, is_ui = _fixture("uud")
    assert a.nearest_entry(1, rel, 3, has_entry, is_ui)[0], "nearer one owns it"
    assert not a.nearest_entry(0, rel, 3, has_entry, is_ui)[0], (
        "the search reached past an intervening UI commit"
    )


def test_documenting_in_the_same_commit_is_the_ideal_and_passes():
    rel, has_entry, is_ui = _fixture("U")
    assert a.nearest_entry(0, rel, 3, has_entry, is_ui)[0]


def test_window_is_still_finite_in_relevant_commits():
    # Not an unbounded search: the count of N is unchanged, only its unit.
    # Spaced with `w` (relevant, so it consumes window budget, but neither
    # documenting nor blocking) so the ONLY thing under test is distance.
    rel, has_entry, is_ui = _fixture("uwwwwd")
    assert not a.nearest_entry(0, rel, 3, has_entry, is_ui)[0], (
        "an entry 5 relevant commits away was credited at window=3"
    )
    # And the same shape just inside the window IS found — otherwise the
    # assertion above could be passing for any reason at all.
    rel, has_entry, is_ui = _fixture("uwwd")
    assert a.nearest_entry(0, rel, 3, has_entry, is_ui)[0], (
        "an entry 3 relevant commits away should be inside window=3"
    )


# ─── documented_by_id: coverage, not adjacency (#321) ───────────────────────

def test_added_lines_keeps_plus_lines_and_drops_the_file_header():
    diff = "\n".join([
        "--- a/watch-design.md",
        "+++ b/watch-design.md",       # carries a path — must NOT be evidence
        "@@ -1,0 +1,2 @@",
        "+the /answers atmosphere (#302) gets its own hue",
        "-a removed line mentioning #999",
        " a context line mentioning #998",
    ])
    got = a.added_lines(diff)
    assert "#302" in got
    assert "#999" not in got, "a REMOVED line documented nothing"
    assert "#998" not in got, "a CONTEXT line documented nothing"
    assert "+++" not in got, "the diff's own file header is not documentation"


def _by_id(subject, diffs, non_styleguide=()):
    """Run documented_by_id over a synthetic history.

    `diffs` maps a commit's full sha -> the text it added. Shas listed in
    `non_styleguide` touch `watch.py` instead of a styleguide file, and
    CRITICALLY their diff text is still returned by the patched
    styleguide_added_text — so the only thing that can reject them is the
    file filter under test.

    That detail is the test, not scaffolding. The first version made the fake
    return "" for those commits, which meant deleting the file filter
    entirely left the test GREEN: it was asserting a property of the patch.
    Same failure as the #320 fixture, two hours apart, so it is written down.
    """
    commits = [(k, k) for k in diffs]
    files = {
        k: frozenset({"watch.py"} if k in non_styleguide else {"watch-design.md"})
        for k in diffs
    }
    real_subject, real_added = a.commit_subject, a.styleguide_added_text
    a.commit_subject = lambda sha: subject
    a.styleguide_added_text = lambda sha: diffs.get(sha) or ""
    try:
        return a.documented_by_id("target", commits, lambda f: files[f])
    finally:
        a.commit_subject, a.styleguide_added_text = real_subject, real_added


def test_a_styleguide_entry_naming_the_task_documents_it_at_any_distance():
    # The #321 case: cdb89df is fix(#302) and 34131c7's added styleguide lines
    # name #302. No adjacency at all — the doc states what it covers.
    got = _by_id("fix(#302): /answers gets its own tint", {
        "far": "the /answers atmosphere (#302) gets its own hue and seed",
    })
    assert got == ("far", "302"), got


def test_an_id_named_only_outside_a_styleguide_file_documents_nothing():
    # A task id in watch.py's own comments must not vouch for the code beside
    # it — otherwise every commit documents itself by mentioning its number.
    # The diff text DOES name #302; only the file filter may reject it.
    got = _by_id(
        "fix(#302): /answers gets its own tint",
        {"other": "# see #302 for why this tint exists"},
        non_styleguide=("other",),
    )
    assert got is None, (
        "an id named in watch.py's own diff was credited as documentation"
    )


def test_a_different_task_id_in_the_doc_does_not_vouch():
    got = _by_id("fix(#302): /answers gets its own tint", {
        "far": "the /review dock (#273) grows a send floor",
    })
    assert got is None, got


def test_a_subject_with_no_task_id_gets_no_credit():
    # Nothing to match on, so it must fall through to MISS rather than match
    # everything. `fix(watch): …` commits exist in this history.
    got = _by_id("fix(watch): harden answers channel contracts", {
        "far": "some styleguide prose mentioning #231",
    })
    assert got is None, got


def test_any_id_of_a_combined_subject_can_carry_the_credit():
    # Real shape in this history: `fix(#157,#222,#223): …` is documented by an
    # entry naming only #157.
    got = _by_id("fix(#157,#222,#223): link only reachable destinations", {
        "far": "links point only where the page can go (#157)",
    })
    assert got == ("far", "157"), got
