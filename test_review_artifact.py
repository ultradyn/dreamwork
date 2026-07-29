"""Checks for the review-artifact template and its builder (#325).

Three properties are worth a check here, and each one is a way the template
could betray the reason it exists:

  FIDELITY   The human named `tasks-page.html` as the good one, so a template
             that renders something subtly different has failed even if it is
             prettier. Every selector the two files share is held to identical
             declarations, and the palette is compared token by token. Nothing
             here is a literal copy of today's values — both sides are parsed at
             runtime, so the check keeps meaning as the artifact ages.
  OFFLINE    An artifact is read on a laptop with no network. One external
             `<script src>` is enough to break it, and it breaks silently.
  PROVENANCE "Iterate on it and perfect it" only works if an artifact says
             which template it came from, and an older one stops claiming to be
             current the moment the template changes.

Every assertion that depends on a fixture property asserts that property too:
the CSS comparison would pass vacuously against two empty parses, so the parse
counts are floors, not decoration.
"""
import html
import os
import re
import subprocess
import sys
import types

import pytest

import review_artifact as ra

HERE = os.path.dirname(os.path.abspath(__file__))
REFERENCE = os.path.join(HERE, ".dreamwork", "review", "tasks-page.html")

# The template may diverge from the artifact it was cut from — but only on
# purpose, and only here. An entry costs one line and names the reason; silent
# drift is what this whole task exists to end.
TEMPLATE_ONLY = {
    # tasks-page.html always carries an aside; a template must render without.
    ".hero-grid.solo",
}
DECLARATION_DIVERGENCES = set()   # selectors allowed to differ. Empty today.
TOKEN_DIVERGENCES = set()         # `--name` allowed to differ. Empty today.

# #339 — token classes emitted at BUILD time by review_artifact.py.highlight().
# tasks-page.html predates highlighting, so every token selector is template-
# only by construction. Naming them here keeps test_template_adds_nothing_undeclared
# honest about what the template legitimately carries beyond the reference, and
# the companion test below holds this set and the template's set to the same
# shape so a dropped rule does not pass silently as "merely unstyled".
HIGHLIGHT_TOKENS = (
    "pre code .tok-kw", "pre code .tok-str", "pre code .tok-num",
    "pre code .tok-com", "pre code .tok-fn", "pre code .tok-typ",
    "pre code .tok-dec", "pre code .tok-op", "pre code .tok-tag",
    "pre code .tok-attr", "pre code .tok-var",
)
TEMPLATE_ONLY |= set(HIGHLIGHT_TOKENS)

# #367 — the essential-marks rail. Every selector here is NEW CSS the template
# carries beyond its hand-rolled reference (tasks-page.html predates marks and
# has no flag rules at all), so none of them collide with a shared selector and
# the reference is not edited for the rail. Asserted by computing the set at
# runtime below rather than trusting this list: if the template grows a mark
# selector this omits, test_template_adds_nothing_undeclared reddens.
MARK_RAIL_TOKENS = (
    ".is-marked", ".marktab", ".is-marked:target .marktab", ".markflag",
    ".markflag:hover", ".marknav", ".is-marked:target .marknav",
    ".marknav a", ".marknav a:hover", ".marknav a:focus-visible",
    ".marktab[data-stagger]",
)
TEMPLATE_ONLY |= set(MARK_RAIL_TOKENS)

# #455 — the if-silent one-sentence slot. New CSS beyond the hand-rolled
# reference (tasks-page.html has no cost-of-silence line). Grouped so a
# selector the template gains for #455 is declared here, not invented.
IF_SILENT_TOKENS = (
    "#if-silent,.if-silent",
    "#if-silent .key,.if-silent .key",
)
TEMPLATE_ONLY |= set(IF_SILENT_TOKENS)

# A body may use these without inventing anything, so the template must carry
# them. Without this, a fidelity failure could be "fixed" by deleting the rule.
CORE_SELECTORS = (
    ":root", "body", "a", "code", "pre", "h1", "h2", "h3", ".wrap", ".read",
    ".skip", ".toprail", ".toprail-in", ".identity", ".topactions", ".status",
    "main", "section", ".label", ".quiet", ".dim", ".dimmer", ".kicker",
    ".proposal", ".sub", ".lead", ".hero-grid", ".version-mark", ".call",
    ".notice", "#if-silent", ".facts", ".fact", "table", "th", "td", ".scroller",
    ".summary-line", ".key", "figure", "figcaption", ".spine", ".spine-row",
    ".checks", ".check", ".stages", ".stage", "details", "summary",
    ".details-in", "details::details-content", ".choice", ".choice-grid",
    ".answer", ".approval", "footer",
)

SOURCE = """<!--dreamwork-review-source
title: #999 · A fixture · proposal
identity: fixture · proposal
context: task #999 · the smallest artifact that is still an artifact
status: awaiting review
headline: One template, one builder.
tag: proposal only
sub: task #999 · 27 July 2026
skip: Skip to the decisions
skip_href: #decision
no_ask: fixture — a synthetic minimal artifact with no decision to make
no_if_silent: fixture — no decision to park; silence costs nothing
-->
<!--#nav-->
<a href="#decision">decisions</a>
<!--#lead-->
<p class="lead">The lead the reader starts on.</p>
<!--#call-->
<div class="call"><strong>Recommendation.</strong> Approve it.</div>
<!--#aside-->
<span class="big">5</span>
<small>font stacks across twelve artifacts</small>
<!--#body-->
<section aria-labelledby="crux-t">
  <div class="label" id="crux-t">The crux</div>
  <p class="read">The palette drifted because nothing owned it.</p>
</section>
<!--#footer-->
Prepared for task #999 · offline-clean, no external requests.
"""


# ── css comparison ────────────────────────────────────────────────────────


def _declarations(block):
    return frozenset(part.strip() for part in block.split(";") if part.strip())


def css_rules(text, context=""):
    """{(at-context, selector): frozenset(declarations)} for one stylesheet.

    Hand-rolled because the comparison has to see inside `@media` and
    `@starting-style`: a palette that agreed at top level and disagreed in the
    print block would be exactly the drift this check is for.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    rules, index, prelude = {}, 0, ""
    while index < len(text):
        char = text[index]
        if char == "{":
            depth, end = 1, index + 1
            while end < len(text) and depth:
                depth += {"{": 1, "}": -1}.get(text[end], 0)
                end += 1
            body, selector = text[index + 1:end - 1], prelude.strip()
            if selector.startswith("@") and "{" in body:
                for key, value in css_rules(body, context + selector).items():
                    rules[key] = value
            elif selector:
                key = (context, selector)
                rules[key] = rules.get(key, frozenset()) | _declarations(body)
            prelude, index = "", end
        else:
            prelude += char
            index += 1
    return rules


def tokens(rules):
    out = {}
    for (context, selector), declarations in rules.items():
        if selector != ":root":
            continue
        for declaration in declarations:
            if declaration.startswith("--"):
                name, _, value = declaration.partition(":")
                out[(context, name.strip())] = value.strip()
    return out


@pytest.fixture(scope="module")
def template():
    return ra.read_template()


@pytest.fixture(scope="module")
def reference():
    with open(REFERENCE, encoding="utf-8") as handle:
        return handle.read()


def style_of(document):
    start = document.index("<style>") + len("<style>")
    return document[start:document.index("</style>")]


# ── fidelity ──────────────────────────────────────────────────────────────


def test_template_palette_is_the_reference_palette(template, reference):
    ours, theirs = tokens(css_rules(style_of(template))), tokens(
        css_rules(style_of(reference)))
    # The precondition: two empty parses compare equal, which would make every
    # assertion below vacuous. tasks-page.html declares its palette in :root and
    # overrides it again under @media print, so both counts are well above this.
    assert len(theirs) >= 25, "reference palette did not parse: %r" % (theirs,)
    assert len(ours) >= 25, "template palette did not parse: %r" % (ours,)
    assert any(context for context, _ in theirs), \
        "no @media palette parsed — the print override should be in here"
    shared = (set(ours) & set(theirs)) - {
        (context, name) for context, name in ours if name in TOKEN_DIVERGENCES}
    differing = {key: (ours[key], theirs[key])
                 for key in shared if ours[key] != theirs[key]}
    assert not differing, "template palette drifted from tasks-page.html: %r" % differing
    assert not set(theirs) - set(ours), \
        "template is missing tokens the reference declares: %r" % sorted(
            set(theirs) - set(ours))


def test_template_rules_match_the_reference_rule_for_rule(template, reference):
    ours, theirs = css_rules(style_of(template)), css_rules(style_of(reference))
    shared = set(ours) & set(theirs)
    assert len(shared) >= 80, \
        "only %d shared selectors parsed — the comparison is not seeing the " \
        "stylesheets" % len(shared)
    differing = {
        key: sorted(ours[key] ^ theirs[key])
        for key in shared
        if ours[key] != theirs[key] and key[1] not in DECLARATION_DIVERGENCES}
    assert not differing, (
        "template rules drifted from tasks-page.html: %r\n\n"
        "If you just fixed a shared selector in review-artifact.template.html, "
        "the other half of the pair is .dreamwork/review/tasks-page.html — the "
        "hand-rolled reference the template was cut from. It is untemplated and "
        "never rebuilt, so the coupling is manual and this test is the only thing "
        "that tells you about it. Make the identical edit there, or add the "
        "selector to DECLARATION_DIVERGENCES with a reason." % differing)


def test_template_adds_nothing_undeclared(template, reference):
    ours, theirs = css_rules(style_of(template)), css_rules(style_of(reference))
    added = {selector for _, selector in set(ours) - set(theirs)}
    assert added <= TEMPLATE_ONLY, \
        "template invents selectors nobody declared: %r" % sorted(
            added - TEMPLATE_ONLY)
    # ...and the divergence ledger is not allowed to rot either.
    assert TEMPLATE_ONLY <= {selector for _, selector in ours}, \
        "TEMPLATE_ONLY names selectors the template no longer has: %r" % sorted(
            TEMPLATE_ONLY - {selector for _, selector in ours})


def test_template_carries_the_component_vocabulary(template):
    """Each documented component is STYLED at top level, not merely mentioned.

    Written the lax way first, and deleting `.notice` outright did not redden
    it: `.notice` also appears inside `@media print`'s
    `.frame,.call,.notice,.choice{break-inside:avoid}`, so "does this selector
    occur anywhere" was satisfied by a rule that gives the component no
    appearance at all. The context has to be the unconditional one, and the
    rule has to actually declare something.
    """
    styled = {}
    for (context, selector), declarations in css_rules(style_of(template)).items():
        if context or not declarations:
            continue
        for piece in selector.split(","):
            styled.setdefault(piece.strip(), set()).update(declarations)
    missing = [name for name in CORE_SELECTORS if name not in styled]
    assert not missing, "template dropped documented components: %r" % missing
    # The precondition: a parse that yielded nothing would report nothing
    # missing only because CORE_SELECTORS was checked against an empty map.
    assert len(styled) >= 80, \
        "only %d top-level selectors parsed — the check is not seeing the " \
        "stylesheet" % len(styled)


def test_reduced_motion_and_print_survive_into_the_build(template):
    built = ra.render(ra.parse_source(SOURCE), template=template)
    style = style_of(built)
    assert "@media(prefers-reduced-motion:reduce)" in style.replace(" ", "")
    assert "@media print" in style


# ── offline-clean ─────────────────────────────────────────────────────────


def test_build_output_fetches_nothing(template):
    built = ra.render(ra.parse_source(SOURCE), template=template)
    assert len(built) > 12000, "suspiciously small build: %d bytes" % len(built)
    assert "<style>" in built and "--bg:" in built, \
        "the build lost its stylesheet, so 'no external stylesheet' is vacuous"
    assert ra.fetch_violations(built) == []


@pytest.mark.parametrize("planted", [
    '<img src="https://example.com/chart.png" alt="">',
    '<script src="//cdn.example.com/x.js"></script>',
    '<link rel="stylesheet" href="https://fonts.example.com/x.css">',
    '<p style="background:url(https://example.com/x.png)">x</p>',
    '<svg><use href="https://example.com/s.svg#i"/></svg>',
    '<iframe src="https://example.com/"></iframe>',
])
def test_a_planted_fetch_refuses_the_build(template, planted):
    fields = ra.parse_source(SOURCE)
    fields["body"] = fields["body"] + "\n" + planted
    with pytest.raises(ra.ArtifactError, match="would fetch"):
        ra.render(fields, template=template)


def test_a_stylesheet_import_in_a_body_style_block_refuses_the_build(template):
    fields = ra.parse_source(SOURCE)
    fields["body"] += '\n<style>@import url("x.css");</style>'
    with pytest.raises(ra.ArtifactError, match="would fetch"):
        ra.render(fields, template=template)


def test_links_in_prose_are_not_fetches(template):
    """The check must discriminate, or authors route around it."""
    fields = ra.parse_source(SOURCE)
    fields["body"] += '\n<p><a href="https://example.com/rfc">the spec</a></p>'
    built = ra.render(fields, template=template)
    assert "https://example.com/rfc" in built


def test_the_reference_artifact_is_itself_offline_clean(reference):
    assert ra.fetch_violations(reference) == []


# ── the component vocabulary (#347-adjacent) ──────────────────────────────
#
# The template documents which classes each component's children take, and for
# two days nothing read that. `task-store-schema.html` duly wrote
# `<div class="fact"><strong>122</strong><small>…</small></div>` — plausible
# HTML the template styles not at all, so the number ran into its caption as
# `122open ids…` while the build exited 0 and `check` said `current`.
#
# Every test below states the production line that must change for it to fail,
# because a check over a component's markup is exactly the shape that passes
# vacuously: `render` would raise for a dozen unrelated reasons, so a bare
# `pytest.raises` proves nothing about which one fired.

FACT_ROW = ('<div class="facts">'
            + '<div class="fact"><span class="number">%d</span>'
              '<span class="caption">a caption</span></div>' * 4
            + '</div>')


def _with_facts(markup):
    fields = ra.parse_source(SOURCE)
    fields["body"] += "\n" + markup
    return fields


def test_a_stray_child_of_a_documented_component_refuses_the_build(template):
    """Break by emptying `COMPONENT_CHILDREN` — the refusal is that dict."""
    good = _with_facts(FACT_ROW % (1, 2, 3, 4))
    ra.render(good, template=template)          # the precondition: the ROW is fine
    bad = _with_facts('<div class="facts">'
                      + '<div class="fact"><strong>1</strong><small>a</small></div>' * 4
                      + '</div>')
    with pytest.raises(ra.ArtifactError, match=r"misuses .* documented component"):
        ra.render(bad, template=template)
    # …and it names WHICH children, or an author cannot act on it.
    assert ra.component_violations("<div class=\"fact\"><strong>1</strong></div>") == [
        "a `.fact` has a child that is neither `.number` nor `.caption`: <strong>"]


def test_bare_text_inside_a_component_is_the_same_defect(template):
    """An unwrapped number renders wrong for the identical reason — the styling
    lives on the class. Break by dropping `_ComponentScan.handle_data`."""
    fields = _with_facts('<div class="facts">'
                         + '<div class="fact">122<span class="caption">a</span></div>' * 4
                         + '</div>')
    with pytest.raises(ra.ArtifactError, match="bare text"):
        ra.render(fields, template=template)


def test_nesting_inside_a_documented_child_is_not_a_stray(template):
    """The check must discriminate by DEPTH or authors lose `<code>` in captions.

    Break by matching children with a regex instead of the parser: `<code>` and
    `<strong>` are indistinguishable to anything that cannot see nesting, and a
    check that forbids both is a check that gets deleted.
    """
    fields = _with_facts(
        '<div class="facts">'
        + ('<div class="fact"><span class="number">1</span>'
           '<span class="caption">a <code>path</code> and <em>emphasis</em>'
           '</span></div>') * 4
        + '</div>')
    built = ra.render(fields, template=template)
    assert "<code>path</code>" in built


def test_the_grid_column_count_is_read_from_the_template_not_assumed(template):
    """The decisive one: the verdict must INVERT when the template is reshaped.

    A hard-coded `4` passes every other test in this section. So the template is
    patched in memory to declare three columns, and a 3-item row must stop
    warning while a 4-item row must start. Break by replacing
    `grid_columns(template, container)` with a literal — this is the only test
    that can fail on it.
    """
    three = template.replace("grid-template-columns:repeat(4,minmax(0,1fr))",
                             "grid-template-columns:repeat(3,minmax(0,1fr))", 1)
    assert three != template, \
        "the template no longer declares repeat(4,…) for .facts — this test's " \
        "premise is gone, not merely its expectation"
    assert (ra.grid_columns(template), ra.grid_columns(three)) == (4, 3)

    row = lambda n: ('<div class="facts">'                       # noqa: E731
                     + '<div class="fact"><span class="number">1</span></div>' * n
                     + '</div>')
    assert ra.grid_warnings(row(3), template) and not ra.grid_warnings(row(3), three)
    assert ra.grid_warnings(row(4), three) and not ra.grid_warnings(row(4), template)


def test_an_undeclared_grid_container_disables_the_count_rather_than_guessing():
    """None is a real answer. Break by defaulting to 4 — a check that invents
    its own premise is worse than an absent one."""
    assert ra.grid_columns(ra.read_template(), "no-such-container") is None


def test_a_short_grid_row_warns_and_still_builds(template):
    """Advisory, not fatal: the row renders, it just shows an empty track. Break
    by raising instead — which would make a source nobody owns unbuildable."""
    warned = []
    fields = _with_facts('<div class="facts">'
                         + '<div class="fact"><span class="number">1</span></div>' * 3
                         + '</div>')
    built = ra.render(fields, template=template, warn=warned.append)
    assert len(built) > 12000
    assert len(warned) == 1 and "empty track" in warned[0]
    # and a full row is silent, or the warning means nothing
    assert ra.render(_with_facts(FACT_ROW % (1, 2, 3, 4)), template=template,
                     warn=warned.append) and len(warned) == 1


def test_a_refusal_still_reports_the_advice_it_had_already_computed(template):
    """#379: `render` raised on the component violation before ever calling
    `grid_warnings`, so a source with both faults showed the error on one run and
    the warning only on the next — after the author had already fixed and
    rebuilt.

    The priority is unchanged and must stay so: this asserts the refusal still
    happens. What changed is that it no longer swallows an advisory.

    The production line is the placement of the `warn(...)` loop relative to the
    two `raise`s. Move it back below them and this fails on `warned == []` while
    every other row here still passes.
    """
    warned = []
    # Three items in a four-column grid (the advisory) AND a stray child inside
    # one of them (the refusal). Both faults, one source.
    fields = _with_facts(
        '<div class="facts">'
        + '<div class="fact"><span class="number">1</span></div>' * 2
        + '<div class="fact"><strong>3</strong><span class="caption">c</span></div>'
        + '</div>')
    with pytest.raises(ra.ArtifactError) as caught:
        ra.render(fields, template=template, warn=warned.append)
    # Precondition, derived rather than assumed: the thing that refused really is
    # the component rule, not some earlier gate that would make the grid check
    # unreachable for a reason unrelated to #379.
    assert "documented component" in str(caught.value), caught.value
    assert len(warned) == 1, warned
    assert "empty track" in warned[0]
    # And the grid really was short — three items against the template's own
    # column count, read at runtime so a reshaped grid moves this with it.
    assert ra.grid_columns(template) == 4


def test_no_warn_callback_means_no_crash(template):
    """`warn=None` is the library default and must not be called."""
    fields = _with_facts('<div class="facts">'
                         + '<div class="fact"><span class="number">1</span></div>' * 3
                         + '</div>')
    assert ra.render(fields, template=template)


def test_every_live_source_is_free_of_stray_children(template):
    """The check's whole claim is about real files, so it is held to them.

    Warnings are deliberately NOT asserted here: a short row is a judgement
    about someone's prose, and pinning today's set would make this a test of
    the artifacts rather than of the builder.
    """
    src = os.path.join(HERE, ".dreamwork", "review", "src")
    sources = sorted(name for name in os.listdir(src) if name.endswith(".html"))
    assert len(sources) >= 3, \
        "only %d source(s) found under %s — the sweep is not seeing them" % (
            len(sources), src)
    offenders = {}
    for name in sources:
        with open(os.path.join(src, name), encoding="utf-8") as handle:
            fields = ra.parse_source(handle.read())
        built = ra.render(fields, template=template)
        strays = ra.component_violations(built)
        if strays:
            offenders[name] = strays
    assert not offenders, "sources misuse a documented component: %r" % offenders


# ── provenance ────────────────────────────────────────────────────────────


def test_the_stamp_is_written_where_both_a_tool_and_a_reader_find_it(template):
    """Deliberately NOT named for derivation: this passes against a hardcoded
    digest (proved — it did), so the derivation claim belongs to the staleness
    check below, which is the one that can fail on it."""
    built = ra.render(ra.parse_source(SOURCE), template=template)
    stamp = ra.artifact_stamp(built)
    assert stamp == ra.template_stamp(template)
    assert re.fullmatch(r"v\d+\+[0-9a-f]{8}", stamp), stamp
    assert stamp in built[built.index("<footer"):], \
        "the stamp is only in the head — a reader cannot see which template " \
        "the page came from"


def test_editing_the_template_makes_an_older_artifact_stale(template):
    built = ra.render(ra.parse_source(SOURCE), template=template)
    assert ra.classify(built, template=template) == "current"
    # One byte in a comment is enough: staleness must not depend on the edit
    # being visible, or an author gets to decide their change did not count.
    edited = template.replace("no artifact\nneeds", "no artifact needs", 1)
    assert edited != template, "the edit did not land — fixture text moved"
    assert ra.template_stamp(edited) != ra.template_stamp(template)
    assert ra.classify(built, template=edited) == "stale"


def test_an_artifact_built_before_the_template_is_untemplated(reference):
    # The twelve existing artifacts are deliberately NOT migrated, so `check`
    # has to have a third answer that is neither a pass nor a false alarm.
    assert ra.artifact_stamp(reference) is None
    assert ra.classify(reference) == "untemplated"


def test_the_build_is_deterministic(template):
    first = ra.render(ra.parse_source(SOURCE), template=template)
    second = ra.render(ra.parse_source(SOURCE), template=template)
    assert first == second


def test_the_authoring_comment_does_not_leak_into_the_artifact(template):
    built = ra.render(ra.parse_source(SOURCE), template=template)
    assert "HOW IT IS FILLED" in template
    assert "HOW IT IS FILLED" not in built
    assert "Built from the dreamwork review template" in built


def test_a_truncated_authoring_comment_refuses_the_build(template):
    """The bug this guard was written from: a close-comment inside the docs.

    It ends the comment early, and the rest of the authoring notes render as
    text at the top of the page — invisible in the source, obvious to him.
    """
    broken = template.replace("a slot; every one is filled",
                              "a slot, as in <!--?name--> here", 1)
    assert broken != template, "the injection did not land — fixture text moved"
    with pytest.raises(ra.ArtifactError, match="ends early"):
        ra.render(ra.parse_source(SOURCE), template=broken)


# ── fail loud ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("slot", ra.REQUIRED)
def test_a_missing_required_slot_refuses_the_build(template, slot):
    fields = ra.parse_source(SOURCE)
    assert fields.get(slot), "fixture never set %r, so removing it proves nothing" % slot
    del fields[slot]
    with pytest.raises(ra.ArtifactError, match="required slot"):
        ra.render(fields, template=template)


def test_an_unknown_slot_refuses_the_build(template):
    fields = ra.parse_source(SOURCE)
    fields["reccomendation"] = "a typo for call"
    with pytest.raises(ra.ArtifactError, match="unknown slot"):
        ra.render(fields, template=template)


def test_a_derived_slot_cannot_be_set_by_hand(template):
    fields = ra.parse_source(SOURCE)
    fields["TEMPLATE_STAMP"] = "v1+deadbeef"
    with pytest.raises(ra.ArtifactError, match="derived"):
        ra.render(fields, template=template)


def test_a_skip_link_needs_a_destination(template):
    fields = ra.parse_source(SOURCE)
    del fields["skip_href"]
    with pytest.raises(ra.ArtifactError, match="skip_href"):
        ra.render(fields, template=template)


def test_source_content_outside_a_block_is_refused():
    with pytest.raises(ra.ArtifactError, match="before its first"):
        ra.parse_source(SOURCE.replace("<!--#nav-->", "<p>stray</p>\n<!--#nav-->", 1))


def test_a_header_line_that_is_not_key_value_is_refused():
    with pytest.raises(ra.ArtifactError, match="not `key: value`"):
        ra.parse_source(SOURCE.replace("status: awaiting review",
                                       "awaiting review", 1))


# ── the optional half ─────────────────────────────────────────────────────


OPTIONAL_IN_FIXTURE = ("status", "aside", "skip", "skip_href", "tag", "sub",
                       "call", "nav", "context")


@pytest.mark.parametrize("how", ["absent", "empty"])
def test_an_omitted_region_leaves_no_empty_furniture(template, how):
    """Both ways an author says "not this one".

    `empty` is the realistic one — a header line written `status:` with nothing
    after it — and it is the case a builder that only tested `key in fields`
    would render as furniture with nothing in it.
    """
    fields = ra.parse_source(SOURCE)
    full = ra.render(dict(fields), template=template)
    assert 'class="status"' in full and 'class="version-mark"' in full and \
        'class="skip"' in full, "fixture lost an optional slot"
    for slot in OPTIONAL_IN_FIXTURE:
        assert slot in fields, "fixture never set %r" % slot
        if how == "absent":
            fields.pop(slot)
        else:
            fields[slot] = "  \n "
    bare = ra.render(fields, template=template)
    # An empty `.status` span renders its glowing dot with nothing beside it,
    # and an empty `.version-mark` holds a 240px column open.
    for gone in ('class="status"', 'class="version-mark"', 'class="skip"',
                 'class="proposal"', 'class="sub"'):
        assert gone not in bare, "%s survived with nothing in it" % gone
    assert "<!--?" not in bare and "<!--/?" not in bare
    assert "{{" not in bare
    assert 'class="hero-grid solo"' in bare, \
        "a hero with no aside must not hold the aside column open"
    assert "The lead the reader starts on." in bare and "The crux" in bare, \
        "dropping the optional half took content with it"


def test_the_full_build_places_every_block(template):
    built = ra.render(ra.parse_source(SOURCE), template=template)
    for expected in ("One template, one builder.", "The lead the reader starts on.",
                     "Recommendation.", "font stacks across twelve artifacts",
                     "The crux", "Prepared for task #999",
                     'href="#decision">decisions</a>',
                     "the smallest artifact that is still an artifact"):
        assert expected in built, "the build dropped %r" % expected


def test_indentation_of_a_multiline_block_follows_the_slot(template):
    """The CONTINUATION lines are the ones the builder has to indent.

    First written against the block's first line, which the template's own
    whitespace indents whether the builder does anything or not — so disabling
    the re-indent left it green. The second line is the only witness.
    """
    fields = ra.parse_source(SOURCE)
    first, _, rest = fields["aside"].partition("\n")
    assert first.strip() and rest.strip(), \
        "fixture aside is one line, so indentation of a block proves nothing"
    built = ra.render(fields, template=template)
    indent = built[built.rfind("\n", 0, built.index(first)) + 1:built.index(first)]
    assert indent and not indent.strip(), "fixture slot is not indented at all"
    assert "\n" + indent + rest.strip() in built, \
        "block continuation lines lost the slot's indentation (%r)" % indent


# ── the cli, and the on-disk shape ────────────────────────────────────────


def test_build_writes_beside_the_review_directory(tmp_path):
    src = tmp_path / "review" / "src"
    src.mkdir(parents=True)
    (src / "artifact-325.html").write_text(SOURCE, encoding="utf-8")
    out = ra.build(str(src / "artifact-325.html"))
    assert out == str(tmp_path / "review" / "artifact-325.html")
    assert os.path.exists(out)
    assert not [name for name in os.listdir(src) if name.endswith(".tmp")]


def test_a_source_outside_src_is_refused(tmp_path):
    """watch.py lists every *.html beside the artifacts, so a source there
    would be served to him as a half-built page."""
    stray = tmp_path / "artifact.html"
    stray.write_text(SOURCE, encoding="utf-8")
    with pytest.raises(ra.ArtifactError, match="src/"):
        ra.build(str(stray))


def test_cli_check_reports_and_exits_nonzero_on_stale(tmp_path, capsys):
    good = tmp_path / "good.html"
    good.write_text(ra.render(ra.parse_source(SOURCE)), encoding="utf-8")
    stale = tmp_path / "stale.html"
    stale.write_text(good.read_text(encoding="utf-8").replace(
        ra.template_stamp(ra.read_template()), "v1+00000000"), encoding="utf-8")
    assert ra.main(["check", str(good)]) == 0
    assert ra.main(["check", str(stale)]) == 1
    printed = capsys.readouterr().out
    assert "current" in printed and "stale" in printed


def test_cli_version_matches_the_module(capsys):
    assert ra.main(["version"]) == 0
    assert capsys.readouterr().out.strip() == ra.template_stamp(ra.read_template())


def test_module_runs_as_a_script():
    done = subprocess.run([sys.executable, os.path.join(HERE, "review_artifact.py"),
                           "version"], capture_output=True, text=True, cwd="/")
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == ra.template_stamp(ra.read_template())


# ── syntax highlighting (#339) ────────────────────────────────────────────
#
# Build-time tokenising, not a runtime highlighter: review_artifact.py emits
# <span class="tok-…"> into marked <pre><code class="language-…"> blocks when
# the artifact is built, and the template ships only the CSS for those
# classes. No script in the artifact (offline-clean), no work repeated at
# read time on a frozen record, and if the CSS is ever lost the code degrades
# to plain readable text.
#
# The rules these checks enforce, and why each is the failure it names:
#
#   DISCRIMINATE   only a block that DECLARES its language is coloured; an
#                  unmarked block is byte-identical. Asserted in one run on
#                  one document so the check cannot pass by forgetting one.
#   ROUND-TRIP     stripping the emitted spans and un-escaping recovers the
#                  original source, entities included. This is the one that
#                  catches a highlighter that tokenises escaped text and
#                  splits &lt; across tokens, re-escaping the &.
#   OFFLINE        highlighting adds no script, no remote URL, no @import.
#   PROVENANCE     editing the frame makes every built artifact stale, and
#                  rebuilding from source is what clears it.


# A code sample chosen to exercise what goes wrong: a keyword, a comment, a
# string, operators that are HTML entities when escaped (< > &), and a newline.
PY_SAMPLE = (
    "def greet(name):\n"
    "    # a < b means less, & means bitwise-and\n"
    "    return 'hi' if name else '<anonymous>'\n"
)


def _first_code_inner(doc, wrapper='class="language-python">'):
    """The text between the first <code …> opening and its </code></pre>."""
    at = doc.index(wrapper) + len(wrapper)
    return doc[at:doc.index("</code></pre>", at)]


def test_a_marked_block_gains_spans_and_an_unmarked_block_does_not(template):
    """The discriminating core of #339: in ONE document the block that
    declares its language is coloured and the block that does not is left
    alone. Both halves are asserted in the same run, and the contrast
    (spans present vs absent) is derived at runtime."""
    marked = '<pre><code class="language-python">%s</code></pre>' % PY_SAMPLE
    bare = '<pre><code>%s</code></pre>' % PY_SAMPLE      # no language at all
    plain = '<pre>%s</pre>' % PY_SAMPLE                  # not even a <code>
    # Precondition: the sample actually exercises the highlighter, or "no
    # spans" could pass because nothing was there to colour.
    assert "def " in PY_SAMPLE and "<" in PY_SAMPLE, \
        "sample is not exercising keyword + entity at once"
    fields = ra.parse_source(SOURCE)
    fields["body"] += "\n" + marked + "\n" + bare + "\n" + plain
    built = ra.render(fields, template=template)

    # the marked block gained token spans inside its <code>
    marked_inner = _first_code_inner(built)
    marked_count = len(re.findall(r'<span class="tok-', marked_inner))
    assert marked_count >= 3, \
        "marked python block gained no token markup: %r" % marked_inner[:140]

    # the two unmarked kinds are byte-identical to the input — located in the
    # built output, because "did it survive" is the claim
    assert bare in built, "an unmarked <pre><code> block was altered"
    assert plain in built, "a plain <pre> block (no <code>) was altered"

    # the bare block's inner has NO spans: derived from the located block, not
    # a literal. A check that only asserted "marked has spans" would pass while
    # silently colouring the bare one too — the contrast is the assertion.
    where = built.index(bare)
    bare_inner = built[where + len("<pre><code>"):
                       where + len("<pre><code>") + len(PY_SAMPLE)]
    bare_count = bare_inner.count("<span")
    assert bare_count == 0, \
        "unmarked block gained %d span(s) — the gate is not discriminating: %r" \
        % (bare_count, bare_inner[:140])


def test_highlighting_introduces_no_network_dependency():
    """Offline-clean is the artifact's contract with a laptop on a plane.
    Highlighting ships only spans + CSS, so it must add no script, no remote
    URL, no external @import. Samples carry no URLs, so absence == introduced."""
    doc = (
        '<pre><code class="language-python">x = 1  # one\n</code></pre>'
        '<pre><code class="language-json">{"n": 1}\n</code></pre>'
        '<pre><code class="language-bash">echo hi\n</code></pre>'
        '<pre><code class="language-javascript">var x = 1\n</code></pre>'
        '<pre><code class="language-html">&lt;p class="a"&gt;hi&lt;/p&gt;</code></pre>'
    )
    out = ra.highlight(doc)
    assert "tok-" in out, "fixture stopped exercising the highlighter"
    for needle in ("<script", "https://", "http://", "@import",
                   "<link", "<iframe", "src="):
        assert needle not in out, \
            "highlighter introduced %r into the output" % needle
    assert ra.fetch_violations(out) == []


def test_stripping_emitted_spans_recovers_the_source_with_entities_intact():
    """The round-trip proof. Feed each language source that contains <, >, &
    and whitespace; strip every span; un-escape; assert the original source is
    recovered exactly. A highlighter that tokenises the escaped text and
    splits &lt; across tokens would re-escape the & and fail here."""
    samples = {
        "python": 'def f(a, b):\n    # a < b means "less"\n    return a & b\n',
        "json": '{"prompt": "x < 1 & y > 2", "n": 3}\n',
        "bash": 'echo "$HOME < $PWD"\n# redirect & log\n',
        "javascript": 'var s = "a < b && c > d";\n',
        "html": '<p class="x">hello & goodbye</p>\n',
    }
    for language, src in samples.items():
        # Precondition: each sample must carry an entity-producing char, or the
        # round-trip proves nothing about entity handling for that language.
        assert any(c in src for c in "<>&"), \
            "%s sample has no entity char — round-trip is vacuous" % language
        inner = html.escape(src, quote=False)
        block = '<pre><code class="language-%s">%s</code></pre>' % (language, inner)
        out = ra.highlight(block)
        assert "tok-" in out, "%s block was not highlighted" % language
        stripped = re.sub(r'<span class="tok-[^"]*">', "", out)
        stripped = stripped.replace("</span>", "")
        recovered = html.unescape(stripped)
        wrapper = '<pre><code class="language-%s">' % language
        assert recovered.startswith(wrapper), \
            "%s: wrapper lost in round-trip" % language
        code = recovered[len(wrapper):].rsplit("</code></pre>", 1)[0]
        assert code == src, (
            "%s round-trip did not recover the source — entities were mangled.\n"
            "  wanted: %r\n  got:    %r" % (language, src, code))


def test_emitted_token_text_is_html_escaped():
    """The re-escape is load-bearing and NOTHING reached it (found validating #339).

    `_highlight_inner` unescapes the block, tokenises the real code, then
    re-escapes each token. Replacing `escaped = html.escape(text, quote=False)`
    with `escaped = text` left the whole suite green — raw markup straight into
    the artifact, undetected. Both adjacent tests look like they cover it and
    neither can:

    - the round-trip test calls `html.unescape` on the output before comparing,
      so a raw `<` and an escaped `&lt;` are the same string to it;
    - the offline-clean test asserts `"<script" not in out`, which is the right
      assertion over a sample that contains no `<script` to leak.

    So this asserts the property directly: strip the tags the highlighter is
    allowed to emit, and NO markup character may remain in what is left.

    The production line that must change for this to fail:
    `escaped = html.escape(text, quote=False)` in `_highlight_inner`.
    """
    src = 'x = "<script>alert(1)</script>"  # a <b>&</b> comment\n'
    inner = html.escape(src, quote=False)
    block = '<pre><code class="language-python">%s</code></pre>' % inner
    out = ra.highlight(block)
    assert "tok-" in out, "fixture stopped exercising the highlighter"

    # Precondition, derived rather than assumed: an entity must land INSIDE a
    # token span, or the escape under test was never reached and this is
    # vacuous. This is the assertion the two tests above are missing.
    spans = re.findall(r'<span class="tok-[^"]*">(.*?)</span>', out, re.S)
    assert spans, "no token spans emitted"
    assert any("&" in s for s in spans), (
        "no entity landed inside a token span, so the re-escape was never "
        "exercised — strengthen the sample, do not trust this test")

    residue = re.sub(r"</?(?:pre|code|span)(?:\s[^>]*)?>", "", out)
    for char in "<>":
        assert char not in residue, (
            "unescaped %r survived into the artifact body: %r" % (char, residue))
    bare = re.search(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#[xX][0-9a-fA-F]+);)",
                     residue)
    assert bare is None, (
        "a bare & survived into the artifact body at %d: %r"
        % (bare.start(), residue))


def test_rebuilding_a_stale_artifact_with_the_new_template_clears_it(template):
    """The consequence #339 must handle: editing the frame makes every built
    artifact stale, and rebuilding from source clears it. Proved on the
    classify() verdict — staleness is a stamp question, not byte-equality."""
    built = ra.render(ra.parse_source(SOURCE), template=template)
    assert ra.classify(built, template=template) == "current"
    edited = template.replace("no artifact\nneeds", "no artifact needs", 1)
    assert edited != template, "the edit did not land — fixture text moved"
    assert ra.template_stamp(edited) != ra.template_stamp(template), \
        "the frame edit did not change the stamp — staleness not exercised"
    assert ra.classify(built, template=edited) == "stale", \
        "the frame edit did not make the older build stale"
    rebuilt = ra.render(ra.parse_source(SOURCE), template=edited)
    assert ra.classify(rebuilt, template=edited) == "current", \
        "rebuilding did not clear the staleness"


def test_an_unsupported_language_marker_is_left_byte_identical():
    block = '<pre><code class="language-rust">fn main() {}</code></pre>'
    assert ra.highlight(block) == block, \
        "highlighter touched a block for a language it does not support"


def test_a_code_block_without_a_language_class_is_left_byte_identical():
    block = '<pre><code>def f(): pass</code></pre>'
    assert ra.highlight(block) == block, \
        "highlighter touched a block with no language class"


def test_the_language_marker_is_found_among_other_classes():
    block = '<pre><code class="hljs language-python foo">x = 1</code></pre>'
    out = ra.highlight(block)
    assert "tok-" in out, "language-X was not found when not the first class"


def test_the_code_wrapper_and_language_class_are_preserved():
    block = '<pre><code class="language-python">x = 1</code></pre>'
    out = ra.highlight(block)
    assert out.startswith('<pre><code class="language-python">'), \
        "the wrapper or language class was altered"
    assert out.endswith("</code></pre>")


def test_the_template_styles_every_token_class(template):
    """A span the highlighter emits with no matching rule degrades to plain
    text — acceptable, but silent drift. This holds the set the highlighter
    emits and the set the template styles to the same shape."""
    styled = {sel for (_ctx, sel) in css_rules(style_of(template))}
    for token in HIGHLIGHT_TOKENS:
        assert token in styled, \
            "template dropped a token style the highlighter emits: %r" % token


def test_the_supported_languages_are_the_advertised_set(template):
    """Scope discipline (#339): a small, honest set, named here so adding one
    is a deliberate act rather than silent scope growth.

    Strengthened for #348. The literal below is the deliberate act; the second
    assertion is what makes it more than bookkeeping — the template's own
    authoring comment advertises the list to whoever writes the next artifact,
    and a language supported in code but unadvertised is invisible, while one
    advertised but unsupported renders plain with no explanation. Derived from
    the template text at runtime rather than pinned, so the two cannot drift.
    """
    assert ra.SUPPORTED_LANGUAGES == frozenset(
        {"python", "json", "bash", "javascript", "html", "sql"})
    advertised = re.search(r"supported\s+languages:\s*([a-z\s]+?)\.", template)
    assert advertised, "the template no longer advertises a language list"
    assert set(advertised.group(1).split()) == set(ra.SUPPORTED_LANGUAGES), \
        "the template's advertised list and SUPPORTED_LANGUAGES disagree"


def test_sql_is_tokenised_in_both_cases_and_comments_win_over_operators():
    """#348 — SQL is case-insensitive and both cases are real here: schema
    designs write `CREATE TABLE`, prose writes `select`.

    Two hazards this pins, each with the production line that must change:

    - `(?i:…)` on the sql keyword/type patterns. Remove the flag and the
      lowercase half stops colouring.
    - `--` is a comment, and `("op", …)`'s character class also contains `-`.
      The ordered alternation puts `com` first. Move `op` above `com` in
      `_SQL` and the comment becomes two operators.
    """
    upper = 'CREATE TABLE entry (id INTEGER PRIMARY KEY NOT NULL);'
    lower = 'create table entry (id integer primary key not null);'
    got = {}
    for label, src in (("upper", upper), ("lower", lower)):
        out = ra.highlight(
            '<pre><code class="language-sql">%s</code></pre>'
            % html.escape(src, quote=False))
        got[label] = {
            cls for cls, _ in re.findall(
                r'<span class="tok-([^"]*)">(.*?)</span>', out, re.S)}
    assert "kw" in got["upper"] and "typ" in got["upper"]
    # The precondition that makes this test about case at all:
    assert upper.lower() == lower, "the two samples are not the same statement"
    assert got["upper"] == got["lower"], (
        "case changed which token classes were produced: %r vs %r"
        % (got["upper"], got["lower"]))

    commented = "-- id is not the entry\nselect 1;"
    out = ra.highlight(
        '<pre><code class="language-sql">%s</code></pre>'
        % html.escape(commented, quote=False))
    spans = re.findall(r'<span class="tok-([^"]*)">(.*?)</span>', out, re.S)
    coms = [text for cls, text in spans if cls == "com"]
    assert coms == ["-- id is not the entry"], (
        "`--` did not win over the operator class; got comments %r" % coms)


# ── the two rules the measurement supports, and the two it refuses (#365) ──
#
# `COMPONENT_CHILDREN` held one entry because rules for the rest would have been
# guessing, and #365 said measure real usage first. Measured across all 16 built
# artifacts with the same depth-aware parser the check uses:
#
#   .spine-row     25 uses, 4 files — spine-key 25, spine-rail 25, spine-body 25
#   .spine-rail    25 uses, 4 files — spine-dot 25
#   .summary-line  37 uses, 5 files — THREE idioms: bare <span> (2 files),
#                  .key + <span> (1), .key + <div> (2)
#   .choice        47 uses, 12 files — .choice-grid in 4, and inline
#                  <b>/<code>/<strong>/<em> prose in the other 8
#
# So the first two are unanimous and closed, and the two #365 NAMED as the
# obvious next candidates are refuted by the measurement: a `.summary-line` rule
# would refuse three of the five files that use it, and a `.choice` rule would
# refuse eight of twelve. That refutation is the point of measuring, and it is
# asserted below so nobody re-adds them from the entry's guess.

SPINE_ROW = ('<div class="spine-row"><div class="spine-key">k</div>'
             '<div class="spine-rail"><div class="spine-dot"></div></div>'
             '<div class="spine-body"><p>body</p></div></div>')


def test_a_stray_child_of_a_spine_row_refuses_the_build(template):
    """Break by removing `spine-row` from COMPONENT_CHILDREN — nothing else in
    this file can fail on that."""
    fields = _with_facts(SPINE_ROW)
    ra.render(fields, template=template)        # precondition: the good row builds
    bad = _with_facts(SPINE_ROW.replace('<div class="spine-key">k</div>',
                                        '<div class="spinekey">k</div>'))
    with pytest.raises(ra.ArtifactError, match=r"misuses .* documented component"):
        ra.render(bad, template=template)
    assert ra.component_violations(
        '<div class="spine-row"><div class="spinekey">k</div></div>') == [
        "a `.spine-row` has a child that is neither `.spine-key` nor "
        "`.spine-rail` nor `.spine-body`: <div class='spinekey'>"]


def test_a_stray_child_of_a_spine_rail_refuses_the_build(template):
    """Break by removing `spine-rail` from COMPONENT_CHILDREN."""
    assert ra.component_violations(
        '<div class="spine-rail"><span class="dot"></span></div>') == [
        "a `.spine-rail` has a child that is not `.spine-dot`: "
        "<span class='dot'>"]
    assert ra.component_violations(
        '<div class="spine-rail"><div class="spine-dot"></div></div>') == []


def test_every_shipped_artifact_still_satisfies_the_new_rules():
    """The rules are derived from these files, so this cannot be assumed: it is
    the assertion that the derivation was done on the real corpus and not on a
    remembered shape. Break by adding a rule the artifacts do not obey.
    """
    import pathlib
    built = sorted(pathlib.Path(".dreamwork/review").glob("*.html"))
    assert len(built) >= 15, f"only {len(built)} artifacts — the corpus moved"
    offenders = {}
    for f in built:
        # `.fact` in the one sourceless artifact is a KNOWN pre-existing
        # violation (#365): protected-service-boundary-288.html has an
        # `.eyebrow` and a bare `<div>` inside a `.fact`, it has no source, so
        # `build` never sees it. Excluded by NAME so it cannot mask a new one.
        bad = [v for v in ra.component_violations(f.read_text(encoding="utf-8"))
               if not (f.name == "protected-service-boundary-288.html"
                       and "`.fact`" in v)]
        if bad:
            offenders[f.name] = bad
    assert not offenders, offenders


def test_the_refuted_candidates_are_not_rules():
    """#365 named `.summary-line` and `.choice`/`.answer` as the obvious next
    candidates and the measurement refuted all three. Adding one would refuse
    artifacts that ship today, so this test exists to make that regression
    loud rather than to protect an opinion — it asserts the corpus, not taste.
    """
    for guessed in ("summary-line", "choice", "answer"):
        assert guessed not in ra.COMPONENT_CHILDREN, (
            f"`.{guessed}` was measured across the built artifacts and does NOT "
            f"have a closed child set; see the comment above SPINE_ROW for the "
            f"counts. A rule here would refuse files that ship.")


# ── essential marks (#367, increment 1) ───────────────────────────────────
#
# His idea: "those little thin postits that lawyers use to indicate key points
# and where you need to sign." A mark is a FLAGGED PASSAGE —
# `data-mark="<label>"` on an element inside the body — and it is a different
# axis from `nav` (structure). Increment 1 is the SAFETY NET, deliberately:
# parse, cap, require an id, and render NOTHING. A source that declares no mark
# must come out byte-for-byte the same as before (apart from the derived
# stamp), which is what lets the frame gain this machinery before any artifact
# uses it. No tabs, no CSS, no next/prev — those are later increments.
#
# VOCABULARY: review_artifact.parse_source already calls its <!--#name--> block
# markers "marks". Those are unrelated; these are *essential marks*, and the
# code and these tests say `essential_marks` / `labels` to avoid the collision.


# The no-marks BODY, stamp-normalised, is the property increment 2a retires the
# byte-identity digest for. Adding the rail's CSS to the template LEGITIMATELY
# changes a no-marks artifact (it gains <style> rules it does not use), so a
# whole-document digest can no longer hold — and the two obvious fixes are both
# wrong (deleting the check opens the frame to silent drift; re-capturing the
# digest breaks the companion that re-runs the pre-change builder out of git).
# The true property is narrower and stronger where it matters: a no-marks BODY
# is unchanged, and the output carries no rail/tab/control ELEMENT. The frame's
# CSS is held to tasks-page.html by the fidelity tests above; staleness by the
# stamp tests below. So this check catches the thing the digest existed for —
# the body being altered, or chrome leaking into a no-marks page — without
# false-failing on the CSS the template is supposed to gain.
_STAMP_NORMALISE_RE = re.compile(r"v\d+\+[0-9a-f]{8}")


def _normalise_stamp(document):
    """Blank the derived template stamp so a frame edit does not masquerade as
    a content change."""
    return _STAMP_NORMALISE_RE.sub("v<N>+<stamp>", document)


def _body_region(document):
    """The authored body, isolated from the frame.

    The body slot lands between `</header>` and `<footer`; everything outside
    that span is template-derived (head, toprail, header, footer, the stamp).
    Comparing this region across builders answers "did the body change" without
    being moved by frame CSS the template is allowed to gain.
    """
    start = document.find("</header>")
    end = document.find("<footer")
    if start < 0 or end < 0 or end < start:
        return document      # a degenerate build: return the whole thing
    return document[start:end]


def _prechange_review_artifact():
    """The committed review_artifact.py from BEFORE essential-marks landed.

    Resolved by CONTENT, not a pinned SHA: the newest commit whose
    review_artifact.py lacks the essential-marks constant, so it survives a
    rebase that rewrites the SHA. Returns (module, ref) or (None, None) when no
    pre-change copy is reachable in git. Used to PROVE the no-marks body this
    check asserts is the genuinely pre-change body, not one recomputed with the
    new code."""
    try:
        shas = subprocess.check_output(
            ["git", "log", "--format=%H", "--", "review_artifact.py"],
            cwd=HERE, stderr=subprocess.STDOUT).decode().split()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None, None
    for sha in shas:
        try:
            blob = subprocess.check_output(
                ["git", "show", "%s:review_artifact.py" % sha], cwd=HERE).decode()
        except subprocess.CalledProcessError:
            continue
        if "MARKS_WARN_AT" not in blob:            # predates essential marks
            mod = types.ModuleType("review_artifact_prechange")
            mod.__file__ = "<git:%s:review_artifact.py>" % sha
            exec(compile(blob, mod.__file__, "exec"), mod.__dict__)
            return mod, sha
    return None, None


def _body_with_marks(n):
    """SOURCE's body plus `n` flagged sections, each carrying a stable id."""
    fields = ra.parse_source(SOURCE)
    fields["body"] += "\n" + "".join(
        '<section id="m%d" data-mark="mark %d"><p>essential %d</p></section>'
        % (i, i, i) for i in range(n))
    return fields


def test_a_no_marks_artifact_renders_no_rail_tab_or_controls(template):
    """The property increment 1's byte-identity digest existed to enforce,
    stated for the increment that retires it: a source with no marks gains no
    rail, no tab, no next/prev — and its BODY is unchanged from the pre-change
    builder.

    Two wrong fixes for the digest trap this replaces (criterion 3 of the
    brief), and why this is not weaker than either:

    - Deleting the digest opens the frame to silent drift. This check still
      holds the body: a build that injected chrome into a no-marks page, or that
      rewrote the body's bytes, reddens here.
    - Re-capturing the digest breaks the companion below (it re-runs the
      pre-change builder and would no longer match). This check keeps that
      companion honest, because it compares the new builder's BODY to the
      pre-change builder's BODY rather than to a re-captured whole-document
      constant.

    The frame's CSS is allowed to change (that is the point of the increment)
    and is held to tasks-page.html by the fidelity tests; staleness is held by
    the stamp tests. So nothing this check stops checking was unguarded.

    Production line that must change for this to FAIL on a regression:
    `if labels: out = inject_mark_rail(out)` in render() — any code that adds an
    element to `out` for a no-marks body, or that rewrites the body's bytes.
    """
    # Precondition, derived not assumed: the fixture genuinely declares no
    # mark, or this assertion is vacuous.
    assert "data-mark" not in ra.parse_source(SOURCE)["body"]
    new = ra.render(ra.parse_source(SOURCE), template=template)
    # No rail/tab/control ELEMENT anywhere (these signatures are the injected
    # markup, not the CSS rules — `.marktab` in <style> is fine and expected).
    for needle in ("data-mid=", 'class="marktab"', 'class="is-marked"',
                   'class="markflag"', 'class="marknav"'):
        assert needle not in new, (
            "a no-marks artifact gained mark chrome %r — the rail rendered "
            "where it must be absent" % needle)
    # Honesty proof: the no-marks BODY is byte-identical to the pre-change
    # builder's body. The pre-change builder is checked out of git and re-run;
    # if it disagrees, the comparison was new-vs-new and proves nothing. Both
    # sides render against THIS template (the current one), so the only
    # difference can be code that touches the body — which is exactly the
    # regression the digest existed to catch.
    old, ref = _prechange_review_artifact()
    if old is not None:
        assert not hasattr(old, "essential_marks"), (
            "resolved ref %s already carries essential marks — the resolver "
            "picked the wrong commit, so the comparison would be new-vs-new "
            "and prove nothing" % ref)
        # The pre-change builder predates the #ask (#436) and if-silent (#455)
        # contracts, so it does not know those header scalars. Strip them
        # before handing the fields over: the comparison is about the BODY,
        # and leaving either in would make the old builder refuse on an
        # unknown slot rather than render.
        old_fields = old.parse_source(SOURCE)
        old_fields.pop("no_ask", None)
        old_fields.pop("no_if_silent", None)
        pre = _body_region(
            old.render(old_fields, template=template))
        assert pre == _body_region(new), (
            "a no-marks body no longer matches the pre-change builder at %s — "
            "the marks machinery altered body bytes it must leave untouched"
            % ref)


def test_marks_are_collected_in_document_order():
    """Document order is mark order — there is no explicit index to keep in
    sync. Break the collection (sort it, or gather via an unordered scan) and
    this fails: the labels are chosen so their document order is NOT their
    alphabetical order, so a sorted collection disagrees.

    Production line: the collection in `essential_marks()` — the HTMLParser
    visits start tags in document order, and the labels list must preserve that
    (do not sort)."""
    body = ('<section id="z" data-mark="zulu last"><p>z</p></section>'
            '<section id="a" data-mark="alpha first"><p>a</p></section>'
            '<section id="m" data-mark="mike middle"><p>m</p></section>')
    labels, no_id, blanks, inline = ra.essential_marks(body)
    assert labels == ["zulu last", "alpha first", "mike middle"], labels
    # Precondition, derived not assumed: every mark here is on a <section>
    # (block), so the inline refusal (a different axis) is not what this order
    # test is exercising — if any were inline, the assertion below could pass
    # for a reason unrelated to document order.
    assert inline == [], "fixture gained an inline mark — order test is muddied"
    # Precondition that makes this about ORDER rather than mere presence: a
    # sorted collection would pass the assertion above iff the input were
    # already alphabetical. It is deliberately not.
    assert labels != sorted(labels), \
        "labels are alphabetical — the order check cannot detect a sort"
    assert no_id == [], "every flagged element here has an id; precondition"
    assert blanks == [], "no blank labels here; precondition"


@pytest.mark.parametrize("attr, outcome", [
    ("data-mark", "ignored"),          # valueless (boolean form): not a mark
    ('data-mark=""', "refused"),       # empty label: authoring mistake
    ('data-mark="   "', "refused"),    # whitespace-only: authoring mistake
    ('data-mark="real"', "kept"),      # ordinary label: a mark
], ids=["valueless", "empty", "whitespace", "real"])
def test_a_mark_label_must_carry_readable_text(template, attr, outcome):
    """A mark is defined by its label — all four rows of #389's table.

    A valueless `data-mark` (the boolean-attribute form) is NOT a mark and is
    ignored; `data-mark=""` and a whitespace-only label reach the renderer and
    would render a blank tab, so they are REFUSED; an ordinary label is kept.
    Asserted at BOTH levels — `essential_marks` (where valueless yields no
    label while empty is recorded as a blank) and `render` (where the refusal
    bites, and valueless must still build).

    The trap this exists for, and why the valueless row is the discriminating
    half: a refusal written as a single falsy check (`if not label.strip()`,
    with no carve-out for valueless) refuses the valueless case too, because
    HTMLParser hands valueless as `None` and empty as `""` and a check that
    cannot tell them apart cannot keep one ignored while refusing the other.
    A test that only checked `""` would pass under that bug; the valueless row
    is what makes it fail.

    Production lines: `_EssentialMarkScan._see` — `label is None` returns
    BEFORE `not label.strip()` ever sees it (the carve-out a falsy check
    drops), and `render()` raises on the collected `blanks` list after the
    advisory channel.
    """
    element = '<section id="m" %s><p>the passage</p></section>' % attr

    # essential_marks is where the split lives: valueless yields no label and
    # no blank; empty/whitespace yield a blank and no label; real yields a label.
    labels, no_id, blanks, _inline = ra.essential_marks(element)
    if outcome == "ignored":
        assert labels == [] and blanks == [], (labels, blanks)
    elif outcome == "refused":
        assert blanks, "a blank label went undetected for %r" % attr
    else:  # kept
        assert labels == ["real"], labels
        assert blanks == []

    # render() is where the refusal bites — and where valueless must build.
    fields = ra.parse_source(SOURCE)
    fields["body"] += "\n" + element
    if outcome == "refused":
        with pytest.raises(ra.ArtifactError, match="readable text") as caught:
            ra.render(fields, template=template)
        # findable: the message names WHERE the blank mark is (its element id
        # here), because "a mark has an empty label" is not actionable alone.
        assert 'id="m"' in str(caught.value), caught.value
    else:
        ra.render(fields, template=template)


def test_a_label_with_padding_around_real_text_survives(template):
    """The #389 relay's second discriminating direction: a label that is REAL
    TEXT with whitespace around it (`"  the cliff  "`) must NOT be refused —
    only a label that is whitespace ALONE is blank. A heavy-handed refusal
    (rejecting any label that is not already trimmed) breaks this; the check is
    `not label.strip()`, which strips a padded label and leaves real text, so it
    falls through to the labels list.

    Production line: `if not label.strip()` in `_EssentialMarkScan._see`. Break
    by refusing when `label != label.strip()` (a "tidy" check) and the padded
    label is rejected.
    """
    padded = '<section id="cliff" data-mark="   the cliff   "><p>x</p></section>'
    labels, no_id, blanks, _inline = ra.essential_marks(padded)
    assert labels == ["   the cliff   "], labels    # stored verbatim, not trimmed
    assert blanks == []
    fields = ra.parse_source(SOURCE)
    fields["body"] += "\n" + padded
    ra.render(fields, template=template)            # builds — a padded label is a mark


def test_a_valueless_mark_on_an_id_less_element_is_not_a_no_id_error(template):
    """The #389 relay's neighbour 4: a valueless `data-mark` is not a mark, so
    even on an element with no id it must NOT trigger the no-id refusal — that
    rule is about marks, and there is no mark here. Refusing here would reject a
    harmless stray attribute. Today this is ([], [], []); keep it so.

    Production line: the `if label is None: return` carve-out in `_see` sits
    BEFORE the no-id collection, so a valueless attribute is gone before no-id
    ever sees it.
    """
    labels, no_id, blanks, inline = ra.essential_marks("<p data-mark>stray</p>")
    # valueless on a <p> (block): not a mark at all, so every axis is empty —
    # including the inline axis, which is the precondition that keeps this test
    # about the no-id rule rather than about the tag rule.
    assert (labels, no_id, blanks, inline) == ([], [], [], []), \
        (labels, no_id, blanks, inline)
    fields = ra.parse_source(SOURCE)
    fields["body"] += "\n<p data-mark>stray</p>"
    ra.render(fields, template=template)            # no-id refusal does NOT fire


def test_eight_marks_warn_and_fifteen_refuse(template):
    """The caps from his 2026-07-28 05:35 ruling (he overrode a five-and-refuse
    proposal): WARN at 8 or more through the advisory channel, REFUSE at 15 or
    more. The band between is deliberate.

    The boundaries are DERIVED from the constants, not hand-written — but each
    is asserted from BOTH sides, so a threshold set to 1 (or 99) fails one half
    or the other. Production lines: MARKS_WARN_AT and MARKS_REFUSE_AT and their
    comparisons in render()."""
    n_below_warn = ra.MARKS_WARN_AT - 1      # 7: must NOT warn
    n_at_warn = ra.MARKS_WARN_AT             # 8: must warn
    n_below_refuse = ra.MARKS_REFUSE_AT - 1  # 14: warns, must NOT refuse
    n_at_refuse = ra.MARKS_REFUSE_AT         # 15: must refuse
    # Precondition: the two caps are distinct bands, or the test is vacuous.
    assert ra.MARKS_REFUSE_AT > ra.MARKS_WARN_AT > 1

    def mark_warnings(warned):
        return [w for w in warned if "essential marks" in w]

    # 7 marks: silent
    warned = []
    ra.render(_body_with_marks(n_below_warn), template=template, warn=warned.append)
    assert mark_warnings(warned) == [], warned

    # 8 marks: warns, still builds
    warned = []
    built = ra.render(_body_with_marks(n_at_warn), template=template, warn=warned.append)
    assert len(built) > 12000 and len(mark_warnings(warned)) == 1, warned

    # 14 marks: warns but does NOT refuse
    warned = []
    ra.render(_body_with_marks(n_below_refuse), template=template, warn=warned.append)
    assert mark_warnings(warned), "14 marks should still warn"

    # 15 marks: refuses
    with pytest.raises(ra.ArtifactError, match="hard cap"):
        ra.render(_body_with_marks(n_at_refuse), template=template,
                  warn=lambda m: None)


def test_a_mark_without_an_id_is_refused(template):
    """A mark on an element with no stable id breaks next/prev — the builder
    must refuse rather than invent one. Break the id check (drop the no-id
    refusal) and this passes while shipping an unaddressable mark.

    Production line: the `if marks_no_id: raise ArtifactError(...)` in render(),
    fed by `_EssentialMarkScan` recording an element whose `data-mark` carries
    no `id`."""
    fields = ra.parse_source(SOURCE)
    fields["body"] += '\n<section data-mark="the cliff"><p>no id here</p></section>'
    with pytest.raises(ra.ArtifactError, match="no stable id"):
        ra.render(fields, template=template)
    # Precondition: the refusal is about the missing id, not the mark itself —
    # the same mark on an element that DOES carry an id builds fine. (render
    # copies fields internally, so the original body is intact to amend.)
    fields["body"] = fields["body"].replace(
        '<section data-mark="the cliff">',
        '<section id="cliff" data-mark="the cliff">')
    ra.render(fields, template=template)


# ── the visible rail (#367 increment 2a) ──────────────────────────────────
#
# The rail is CSS-only (the artifact is offline-clean, no script), so the
# boundary it shows at is a media query and the flag's width is a CSS value —
# both read FROM the template at runtime rather than re-stated here, so a
# reshaped flag or a moved cliff moves the check with it. The pixel truth (the
# flag actually fits at the cliff, flags never overlap) is the browser guard's
# job; these tests hold the structural properties the guard depends on.

# `.read` is `max-width:var(--measure)` = 78ch, which resolves to a FIXED
# 613.5px at the body font (.82rem, root 16px — the template sets no html
# font-size, so this is stable). Measured in
# .dreamwork/docs/measurements/367-two-line-tab-geometry.md and re-proven in
# pixels by dev/capture/markrail.mjs. This constant is the reading column's
# width, NOT the flag's: it tracks `.read`, and the guard catches drift.
_READ_COLUMN_PX = 613.5


def _cliff_px(template):
    """The viewport at/above which the rail shows, read from the template via
    the same css_rules parser the fidelity tests use. The cliff is the
    `@media(max-width:…)` block whose `.marktab` declares `display:none`; the
    rail shows above that value. Returns None when no such rule exists."""
    for (context, selector), decls in css_rules(style_of(template)).items():
        if selector != ".marktab" or not context.startswith("@media"):
            continue
        if not any(d.startswith("display:none") for d in decls):
            continue
        match = re.search(r"max-width\s*:\s*([0-9.]+)\s*px", context)
        if match:
            return float(match.group(1)) + 0.02
    return None


def _flag_maxwidth_px(template):
    """The worst-case flag width in px, read from `.markflag`'s max-width
    (rem → px at root 16). A ~6-word label fills it (measured). None if absent."""
    rules = css_rules(style_of(template))
    for decls in rules.get(("", ".markflag"), frozenset()):
        match = re.match(r"max-width\s*:\s*([0-9.]+)rem", decls)
        if match:
            return float(match.group(1)) * 16
    return None


def test_the_worst_case_tab_fits_inside_the_wrap_at_the_switch_boundary(template):
    """The cliff is where the rail shows, and the worst-case flag must fit
    inside `.wrap` there. Derived from the template at runtime — the cliff from
    its media query, the flag's width from `.markflag`'s `max-width` — so a
    reshaped flag or a moved cliff moves the arithmetic with it, and the
    literal here is the reading column (`.read`), not the flag.

    `.wrap` is `min(calc(100% - 2rem), 1120px)`, so at viewport V its width is
    `min(V - 32, 1120)`. The flag sits in the slack right of `.read`, a `4px`
    gap off the column's edge (the `.4ch` in the template). The worst-case
    two-line flag is its `max-width` (a ~6-word label fills it: measured).

    Production line: the `@media(max-width:…) .marktab{display:none}` rule
    (move the cliff below where the flag fits and this reddens), or
    `.markflag`'s `max-width` (widen the flag past the slack), or
    `.read`/`--measure` (narrow the column and the slack shrinks). The browser
    guard re-proves all three in pixels.
    """
    cliff = _cliff_px(template)
    assert cliff is not None, \
        "the template no longer hides .marktab below a max-width cliff — the " \
        "switch boundary this test reads is gone, not merely its value"
    flag_px = _flag_maxwidth_px(template)
    assert flag_px is not None, \
        ".markflag no longer declares a max-width — the worst-case flag width " \
        "this test reads is gone"
    gap_px = 4                                  # the .4ch off the column edge
    # At the cliff, .wrap is clamped by (100% - 2rem) until 1120 + 32 = 1152.
    wrap_px = min(cliff - 32, 1120)
    slack = wrap_px - _READ_COLUMN_PX - gap_px - flag_px
    assert slack >= 0, (
        "the worst-case flag (%.1fpx) does not fit inside .wrap at the cliff "
        "(%.0fpx): wrap %.0f − read %.1f − gap %d − flag %.1f = %.1fpx. Move "
        "the cliff up or narrow .markflag's max-width." % (
            flag_px, cliff, wrap_px, _READ_COLUMN_PX, gap_px, flag_px, slack))


def test_two_marks_closer_than_a_tab_height_do_not_overlap(template):
    """Two flags closer than a tab is tall (the measured densest pair: a
    section and its first marked child, ~29px against a ~32px tab) must not
    overlap. The builder cannot know pixel gaps (the artifact is script-free),
    so it staggers a flag NESTED inside another marked element — the honest
    structural proxy for "right next to" — and the template's CSS offsets a
    staggered flag down. The browser guard re-proves no two flags overlap in
    pixels on a built artifact.

    Production line: the `stagger = any(m for _, m in self._stack)` line in
    `_MarkInjectScan` (drop the nesting detection and the child keeps
    `data-mid="1"` with no `data-stagger`), or the `.marktab[data-stagger]`
    rule in the template (drop the offset and a staggered flag sits flush).
    """
    fields = ra.parse_source(SOURCE)
    fields["body"] += ('\n<section id="parent" data-mark="parent flag">'
                       '<p class="read" id="child" data-mark="child flag">'
                       'a passage close to its parent</p></section>')
    built = ra.render(fields, template=template)
    # Precondition, derived not assumed: both flags were planted, and the child
    # really is nested in the parent (the structural signal for "close"). If the
    # fixture stopped nesting, the stagger check below would be vacuous.
    assert built.count('class="marktab"') == 2, "two flags were not planted"
    parent_tab = built[built.index('data-mid="0"'):built.index('data-mid="1"')]
    child_tab = built[built.index('data-mid="1"'):]
    assert "data-stagger" not in parent_tab, \
        "the outer flag was staggered — stagger must mean nested-in-a-flag"
    assert "data-stagger" in child_tab, (
        "the nested flag was not staggered — two flags a tab-height apart would "
        "read as one chrome mass. The nesting detection in _MarkInjectScan "
        "stopped marking a flag whose ancestor carries a mark.")
    # And the template actually offsets a staggered flag, or the attribute is
    # decorative. The offset is a downward margin so the flag still anchors at
    # the reading column edge (a horizontal push would overflow the wrap below
    # ~1120px, measured).
    assert re.search(r"\.marktab\[data-stagger\]\s*\{[^}]*margin-top",
                     template), \
        "the template dropped the .marktab[data-stagger] offset — the stagger " \
        "attribute no longer moves the flag"


def test_marks_are_focusable_and_announce_the_current_one(template):
    """The flags are navigation, not edge art: each is a real focusable link,
    next/prev is reachable and labelled, and the current passage is announced.
    There is no script (the artifact is offline-clean), so "current" is
    `:target` — the passage navigated to — and the marked host carries
    `tabindex="-1"` so a screen reader announces it when fragment navigation
    lands there.

    Production line: `_mark_tab_html` (the flag link, the nav links and their
    aria-labels all come from it), and `_augment_open_tag` (the host's
    `tabindex="-1"`)."""
    fields = ra.parse_source(SOURCE)
    fields["body"] += ('\n<section id="m1" data-mark="the cliff"><p>one</p></section>'
                       '\n<section id="m2" data-mark="second finding"><p>two</p></section>'
                       '\n<section id="m3" data-mark="third mark"><p>three</p></section>')
    built = ra.render(fields, template=template)
    # Each flag is a real link to its own passage (focusable, keyboard-operable).
    flags = re.findall(r'<a class="markflag" href="#([^"]+)" aria-label="([^"]+)">',
                       built)
    assert [fid for fid, _ in flags] == ["m1", "m2", "m3"], flags
    # Every flag's aria-label names it as a mark and carries its position, so a
    # screen reader announces "essential mark N of M: …" rather than bare text.
    assert all("essential mark" in label and " of 3" in label for _, label in flags), \
        "a flag's aria-label stopped announcing its position: %r" % (flags,)
    # Next/prev are reachable, labelled links — and only the middle flag carries
    # both (the rail walks the list in document order).
    assert re.search(r'<a class="markprev" href="#m1"[^>]*aria-label="previous essential',
                     built), "prev control missing or unlabelled"
    assert re.search(r'<a class="marknext" href="#m3"[^>]*aria-label="next essential',
                     built), "next control missing or unlabelled"
    # The marked hosts are focusable (tabindex="-1") so fragment navigation
    # announces the current passage: this is the "announce the current one" half.
    hosts = re.findall(r'<section id="(m[123])"[^>]*>', built)
    assert len(hosts) == 3, hosts
    for hid in hosts:
        host_tag = re.search(r'<section id="%s"[^>]*>' % hid, built).group(0)
        assert 'tabindex="-1"' in host_tag, (
            "marked host %s is not focusable — the current passage cannot be "
            "announced on fragment navigation" % hid)


def test_the_rail_renders_nothing_below_the_cliff(template):
    """Below the cliff the rail (`.marktab`) is absent — not a broken flag.
    Increment 2b's strip is a separate surface; this check holds only the rail.

    Production line: the `@media(max-width:…) { .marktab{display:none} }` rule.
    Drop it and a narrow viewport renders clipped flags past the page edge."""
    assert _cliff_px(template) is not None, \
        "the cliff no longer hides .marktab — below it the rail would render"


# ── the strip below the cliff (#367 increment 2b) ─────────────────────────
#
# His ruling 2026-07-28 15:11: option C (the walk) + collapsible index —
# double chevron on RHS, expands to the labelled list, collapsed by default.
# transitions.md binds: expand/collapse reuses the page's details-content
# idiom. Offline-clean (no script): <details> is the control; aria-expanded
# documents the default-collapsed contract.


def _marks_fixture(n, template):
    """Build n marked sections; return (built_html, labels). Labels are derived
    at runtime so a fixture edit moves the assertions with it."""
    fields = ra.parse_source(SOURCE)
    labels = ["mark label %d of fixture" % (i + 1) for i in range(n)]
    for i, lab in enumerate(labels):
        fields["body"] += (
            '\n<section id="s%d" data-mark="%s"><p>passage %d</p></section>'
            % (i + 1, lab, i + 1))
    return ra.render(fields, template=template), labels


def test_markstrip_is_injected_only_when_marks_exist(template):
    """With marks, a `.markstrip` is planted; with none, it is absent — the
    same no-chrome safety property as the rail.

    Production line: `inject_mark_rail` (or its strip plant) — drop the plant
    and a marked build has no strip; plant unconditionally and a no-marks
    build gains chrome.
    """
    bare = ra.render(ra.parse_source(SOURCE), template=template)
    assert "data-mark" not in ra.parse_source(SOURCE)["body"]
    assert "markstrip" not in bare, \
        "a no-marks artifact gained markstrip chrome"
    built, labels = _marks_fixture(3, template)
    assert len(labels) == 3  # runtime-derived precondition
    assert 'class="markstrip"' in built or "class='markstrip'" in built, \
        "a marked artifact has no .markstrip — the strip below the cliff is absent"
    # Count of list links equals the fixture mark count (not a hardcoded 3).
    list_links = re.findall(
        r'class="markstrip-item"[^>]*href="#s\d+"', built)
    assert len(list_links) == len(labels), (
        "strip list has %d items but fixture declared %d marks"
        % (len(list_links), len(labels)))


def test_markstrip_is_collapsed_by_default_with_aria_and_chevron(template):
    """Collapsed by default at walk height; double chevron affordance on the
    RHS; aria-expanded=false documents the default. Keyboard parity is the
    native <details>/<summary> control (Enter/Space).

    Production line: `_mark_strip_html` — omit `aria-expanded`, the open
    attribute, or the chevron and this reddens.
    """
    built, labels = _marks_fixture(2, template)
    assert len(labels) == 2
    # The strip is a <details> with no open attribute (collapsed default).
    m = re.search(
        r'<details\b[^>]*class="[^"]*markstrip-panel[^"]*"[^>]*>', built)
    assert m, "markstrip is not a <details class=markstrip-panel>"
    assert " open" not in m.group(0) and not m.group(0).endswith("open>"), \
        "markstrip details carries open — must be collapsed by default"
    # aria-expanded=false on the summary (default-collapsed contract).
    assert re.search(
        r'<summary\b[^>]*aria-expanded="false"', built), \
        "markstrip summary lacks aria-expanded=false"
    # Double chevron affordance (» or ››) present, marked aria-hidden.
    assert re.search(
        r'class="markstrip-chev"[^>]*>\s*(»|››|&raquo;)\s*<', built), \
        "double chevron affordance missing from markstrip summary"


def test_markstrip_expand_reuses_details_content_transition(template):
    """Expand/collapse is a transition (transitions.md): the strip must reuse
    the page's details::details-content idiom, not invent a second gesture.

    Production line: the template's markstrip CSS — a display:none toggle with
    no details-content transition fails; the global details rule alone is not
    enough unless .markstrip-panel is a real <details>.
    """
    # Precondition: the page already has the details-content travel idiom.
    assert "details::details-content" in template, \
        "template lost the details-content transition the strip must reuse"
    assert "transition-behavior:allow-discrete" in template
    # And the strip is that element (a details), not a div-with-JS.
    built, labels = _marks_fixture(1, template)
    assert len(labels) == 1
    assert re.search(r'<details\b[^>]*markstrip-panel', built)
    # Scoped rules may restyle the panel but must not zero the travel: if the
    # template names .markstrip-panel::details-content it must still transition.
    scoped = re.search(
        r"\.markstrip-panel::details-content\s*\{([^}]+)\}", template)
    if scoped:
        assert "transition" in scoped.group(1), \
            ".markstrip-panel::details-content dropped its transition"


def test_markstrip_visible_only_below_the_cliff(template):
    """Above the cliff the rail shows and the strip is absent; below, the
    strip shows. Both boundaries are read from the template at runtime.

    Production line: the @media rule that shows .markstrip below the cliff
    (and hides it by default above). Drop the show rule and the strip is
    never visible; show it unconditionally and it doubles the rail above.
    """
    cliff = _cliff_px(template)
    assert cliff is not None, "cliff missing — strip boundary has no anchor"
    # Default (above cliff): .markstrip is display:none (or equivalent hide).
    rules = css_rules(style_of(template))
    base = rules.get(("", ".markstrip"), frozenset())
    assert any("display:none" in d for d in base), (
        ".markstrip is not hidden by default — it would double the rail "
        "above the cliff. Declarations: %r" % (base,))
    # Below the cliff media: .markstrip becomes visible.
    shown = False
    for (context, selector), decls in rules.items():
        if selector != ".markstrip" or not context.startswith("@media"):
            continue
        m = re.search(r"max-width\s*:\s*([0-9.]+)\s*px", context)
        if not m:
            continue
        # Same cliff family as the rail (within 1px of the marktab hide).
        if abs(float(m.group(1)) + 0.02 - cliff) > 1.0:
            continue
        if any(re.match(r"display\s*:\s*(block|flex|grid)", d) for d in decls):
            shown = True
    assert shown, (
        "no @media near the cliff (%.0fpx) shows .markstrip — below the "
        "cliff the strip would stay display:none" % cliff)


# ── the carried-over #389 limit: U+200B zero-width space (#367) ───────────
#
# #389 closed the empty-label hole but left one measured limit: the refusal is
# str.strip()-based, so it catches every Zs space (U+00A0, U+2003, U+3000) but
# NOT U+200B zero-width space, which is category Cf and therefore not
# whitespace to .strip(). A label of only zero-width spaces is accepted and
# would render a blank tab — which matters MORE now that tabs are rendered. The
# rule that matches file-formats.md's wording ("a label must carry readable
# text") is no character outside Unicode categories Z* and C*; the carve-out
# the valueless data-mark must still be ignored is the discriminating half.


def test_a_label_of_only_zero_width_spaces_is_refused(template):
    """A label of only U+200B zero-width spaces is category Cf, so str.strip()
    does not see it and #389's refusal let it through — rendering a blank tab.
    The rule is no character outside categories Z* and C*; a valueless
    data-mark must STILL be ignored (the naive widening swallows that carve-out
    and reddens the two #389 guards below).

    Production line: the blank-label refusal in render() (or the blank
    detection in `_EssentialMarkScan._see`). Widening `not label.strip()` to
    `not _readable(label)` where the latter rejects any char outside Z*/C*."""
    zwsp = "\u200b\u200b"            # two zero-width spaces — not whitespace to .strip()
    assert zwsp.strip() == zwsp, \
        "precondition: U+200B is not whitespace to str.strip — if this fails " \
        "the refusal under test is already covered by #389 and this is vacuous"
    element = '<section id="blank" data-mark="%s"><p>blank flag</p></section>' % zwsp
    fields = ra.parse_source(SOURCE)
    fields["body"] += "\n" + element
    with pytest.raises(ra.ArtifactError, match="readable text"):
        ra.render(fields, template=template)


# ── an inline data-mark is refused (#396) ─────────────────────────────────
#
# The geometry break #367 increment 2a shipped: a flag anchors with
# `left:calc(var(--measure) + .4ch)` against its own box, and for an INLINE
# element that box is the inline box — so `left` resolves from the inline
# box's offset, the flag drifts right, and it clips past the page edge
# (measured by the human: clipped by 151px at the 861px cliff; the flag does
# not reflow, clipping grows as the viewport shrinks). Block marks anchor at
# the column edge and are fine.
#
# The decision is a BUILD-TIME refusal, not support or a clamp — following the
# same idiom as the blank-label (#389) and no-id (#367) refusals. The gate is
# a BLOCK-ELEMENT ALLOWLIST (`MARKS_BLOCK_HOSTS`), not an inline denylist: an
# unknown tag refuses (fails closed) rather than silently clipping, and a
# denylist would fail open on every inline tag nobody thought of (abbr, kbd,
# mark, sub, ...). The browser guard (markrail) proved its anchor assertion
# sees an inline flag: with an inline mark as the worst flag, "the flag anchors
# at the reading column's right edge (within 2px)" went RED by 46.4px.


def test_an_inline_data_mark_is_refused(template):
    """A flag on an inline element anchors from the inline box's offset and
    clips past the page edge (#396), so the builder refuses at BUILD time
    rather than ship a silently clipped flag. Same idiom as the blank-label and
    no-id refusals: a loud build error, never a quiet clip.

    Production line: `if tag not in MARKS_BLOCK_HOSTS: self.inline.append(...)`
    in `_EssentialMarkScan._see` — drop the inline recording and an inline mark
    builds. The element carries an id, so the no-id refusal cannot be what
    fires; the refusal under test is the inline one.
    """
    # Precondition, derived not assumed: <span> is NOT in the block allowlist,
    # or the inline refusal can never fire on it and this test is vacuous.
    assert "span" not in ra.MARKS_BLOCK_HOSTS, \
        "<span> is in the block allowlist — the inline refusal cannot catch " \
        "it; pick a different inline tag for this test"
    fields = ra.parse_source(SOURCE)
    fields["body"] += ('\n<p class="read">prose with '
                       '<span id="phrase" data-mark="an inline phrase">'
                       'an inline flag</span> inside it</p>')
    with pytest.raises(ra.ArtifactError, match="inline element"):
        ra.render(fields, template=template)


def test_a_block_data_mark_is_still_accepted(template):
    """The refusal discriminates by tag — it does not forbid marks outright. A
    mark on a section (the commonest passage container) still builds and plants
    a flag, so the allowlist is not so narrow it refuses the case the feature
    is for.

    Production line: `MARKS_BLOCK_HOSTS` membership, read in `_see` — remove the
    marked tag (`section`) and the BUILD refuses, so this reddens on the render
    line. The precondition asserts a *representative* block tag (`p`), not the
    one marked below, deliberately: that keeps the red on the build behaviour
    rather than on this assert, which is the discrimination under test.
    """
    # Precondition, derived not assumed: the allowlist is real and holds block
    # tags (a representative one plus a size floor), or the refusal would be
    # total and this would pass for the wrong reason.
    assert "p" in ra.MARKS_BLOCK_HOSTS and len(ra.MARKS_BLOCK_HOSTS) > 5
    fields = ra.parse_source(SOURCE)
    fields["body"] += ('\n<section id="blk" data-mark="a block passage">'
                       '<p class="read">the body of the passage</p></section>')
    built = ra.render(fields, template=template)
    assert 'data-mid="0"' in built, "a block mark planted no flag"


def test_the_refusal_names_the_element_and_the_label(template):
    """An inline refusal that says only 'inline mark refused' makes an author
    hunt through a document for the offender. Match the existing refusals'
    detail: name the offending element (tag AND id, so it is findable) AND its
    label (so the author knows which flag). #389's blank refusal names WHERE;
    this one names WHERE and WHAT.

    Production line: the `%s carrying label %r` formatting in render()'s inline
    refusal — drop `where` (or `label`) from it and this fails on the substring
    that went missing.
    """
    # Precondition: <em> is inline (not in the allowlist) — derived, not
    # assumed, so a future allowlist widening cannot quietly un-test this.
    assert "em" not in ra.MARKS_BLOCK_HOSTS
    fields = ra.parse_source(SOURCE)
    fields["body"] += ('\n<p class="read">prose with '
                       '<em id="emphasis" data-mark="the emphasised bit">'
                       'an emphasis</em> inside it</p>')
    with pytest.raises(ra.ArtifactError) as caught:
        ra.render(fields, template=template)
    msg = str(caught.value)
    # the element: tag and id, so the author can find it in the source
    assert '<em id="emphasis">' in msg, \
        "the refusal does not name the offending element: %r" % msg
    # the label, so the author knows which flag it is
    assert "the emphasised bit" in msg, \
        "the refusal does not name the mark's label: %r" % msg


# ── the #ask contract (#436) ──────────────────────────────────────────────
#
# A criterion naming a selector most of the corpus lacks is a wish, not a
# standard. `above_fold.mjs` is the shared checker, but it reported `#ask
# MISSING` on 20 of 23 artifacts because `#ask` was a convention each lane
# either invented or didn't. The contract closes that: a source declares
# EXACTLY ONE of a meaningful `#ask` or a `no_ask:` exemption; both, neither,
# and a decoy are refused.
#
# The decoy refusal is the load-bearing one and the one the brief names
# explicitly — "an empty `#ask` passes the fold check on a page whose ask is
# still buried". Its production line is `enforce_ask_contract`'s
# `if not meaningful: raise` branch, backed by `scan_ask`'s
# `_saw_element_inside and any(s.strip() for s in self._text_inside)` test.

def test_a_source_with_no_ask_and_no_exemption_is_refused(template):
    """The contract: neither a real ask nor an exemption is a refusal.

    Production line: the `if not present: raise` branch in `enforce_ask_contract`.
    Drop it and a source with neither builds, planting no ask meta — the wish,
    not the standard, exactly as it was before #436.
    """
    fields = ra.parse_source(SOURCE)
    fields.pop("no_ask", None)         # the fixture carries the exemption
    assert "no_ask" not in fields, "fixture lost its exemption — test is vacuous"
    with pytest.raises(ra.ArtifactError, match="neither"):
        ra.render(fields, template=template)


def test_a_source_with_both_an_ask_and_an_exemption_is_refused(template):
    """Both is the same hollowness as neither, in a new place (#436).

    Production line: the `if no_ask and present: raise` branch in
    `enforce_ask_contract`.
    """
    fields = ra.parse_source(SOURCE)
    assert "no_ask" in fields, "fixture carries no exemption — cannot add the both case"
    fields["lead"] += ('\n<div id="ask" class="ask-block"><div class="label">Ask</div>'
                       '<p class="ask-q">A real decision, and an exemption too.</p></div>')
    with pytest.raises(ra.ArtifactError, match="both"):
        ra.render(fields, template=template)


def test_an_empty_or_decoy_ask_is_refused(template):
    """A decoy ask — present but wrapping no real decision — is the precise
    hollowness #436 exists to end: the fold check passes on a page whose ask
    is still buried. The proxy for "wraps the actual decision" is an element
    with at least one descendant element AND non-whitespace text.

    Production line: `scan_ask`'s `_saw_element_inside and any(s.strip() …)`
    settlement in `_AskScan.close`/`handle_endtag`, read by the
    `if not meaningful: raise` branch in `enforce_ask_contract`. Collapse the
    settlement to `meaningful = present` and this passes while the fold check
    measures an empty box.
    """
    fields = ra.parse_source(SOURCE)
    fields.pop("no_ask", None)
    for decoy, why in [
        ('<div id="ask"></div>', "empty"),
        ('<div id="ask">   </div>', "whitespace-only"),
        ('<div id="ask"><br></div>', "element but no text"),
        ('<div id="ask">just text, no element</div>', "text but no element"),
    ]:
        f = dict(fields)
        f["lead"] += "\n" + decoy
        with pytest.raises(ra.ArtifactError, match="no real decision") as caught:
            ra.render(f, template=template)
        assert why in str(caught.value) or "real decision" in str(caught.value), (
            "the refusal for %r did not fire: %r" % (why, caught.value))


def test_a_meaningful_ask_builds_and_carries_the_ask_meta(template):
    """The happy path: a real ask wraps the decision and the built artifact
    records `content="ask"` in the ask-status meta, beside the template stamp.

    Production line: `enforce_ask_contract` returns `"ask"`, `_inject_ask_meta`
    plants it. Drop either and the meta is absent (`ask_status` returns None),
    which a future walking guard reads as "untemplated / pre-#436" and skips.
    """
    fields = ra.parse_source(SOURCE)
    fields.pop("no_ask", None)
    fields["lead"] += ('\n<div id="ask" class="ask-block"><div class="label">Ask</div>'
                       '<p class="ask-q">One real decision, with structure.</p></div>')
    doc = ra.render(fields, template=template)
    assert ra.ask_status(doc) == "ask", "the ask meta was not written"
    present, meaningful = ra.scan_ask(doc)
    assert present and meaningful, "scan_ask did not find the meaningful ask"


def test_an_exempt_ask_builds_and_carries_the_exempt_meta(template):
    """The exemption: a page with no decision declares `no_ask:` and the built
    artifact records `content="exempt: <reason>"`. The reason is carried so a
    reader (or a walking guard) sees WHY the page is exempt, not just that it is.
    """
    fields = ra.parse_source(SOURCE)
    assert fields["no_ask"], "fixture carries no exemption — test is vacuous"
    doc = ra.render(fields, template=template)
    assert ra.ask_status(doc) == "exempt: " + fields["no_ask"], \
        "the exempt meta was not written or lost the reason"


def test_an_untemplated_artifact_has_no_ask_meta_and_is_not_asked_to_have_one():
    """The 12 pre-#436 artifacts carry no ask meta and cannot be rebuilt. A
    future walking guard reads `classify` first: `untemplated` is skipped by
    class, so `ask_status` returning None on them is correct, not a gap.

    Verified against the real corpus rather than a fixture: the test finds an
    untemplated artifact in `.dreamwork/review/` and asserts on it, so it
    cannot pass over an empty directory.
    """
    import glob
    untemplated = None
    for path in sorted(glob.glob(os.path.join(HERE, ".dreamwork", "review", "*.html"))):
        with open(path, encoding="utf-8") as handle:
            if ra.classify(handle.read()) == "untemplated":
                untemplated = path
                break
    assert untemplated, \
        "no untemplated artifact found in the corpus — the test is vacuous"
    with open(untemplated, encoding="utf-8") as handle:
        assert ra.ask_status(handle.read()) is None, \
            "%s is untemplated but carries an ask meta — the builder should not "
        "write one for artifacts it did not build"


def test_the_ask_meta_sits_beside_the_template_stamp_in_head(template):
    """The ask meta is anchored beside the template-stamp meta, in `<head>`,
    so the artifact is self-describing in one place. A meta written into the
    body would be valid HTML but a surprising place for a reader to find it.
    """
    fields = ra.parse_source(SOURCE)
    doc = ra.render(fields, template=template)
    head_end = doc.index("</head>")
    ask_meta_pos = doc.index(ra.ASK_META_NAME)
    stamp_pos = doc.index('dreamwork-review-template"')
    assert ask_meta_pos < head_end, "the ask meta is outside <head>"
    assert stamp_pos < head_end, "precondition: the stamp meta is in <head>"
    # beside = within the same <meta> block, ask after stamp (stamp first so a
    # reader scanning metas sees provenance before the ask contract)
    assert abs(ask_meta_pos - stamp_pos) < 200, \
        "the ask meta is far from the stamp meta — not 'beside' it"


# ── the if-silent contract (#455) ─────────────────────────────────────────
#
# Audit: ~16/27 first screens already answer ≥3 of 4 orientation questions;
# Q4 (cost of silence) is the structural hole (~4/27). The voice contract
# wants all four; the build enforces only Q4 — one sentence, refused when
# absent or empty, never on a word count. Same shape as #ask (#436).
#
# Production line: `enforce_if_silent_contract`'s three raise branches.


def test_a_source_with_no_if_silent_and_no_exemption_is_refused(template):
    """Neither a real if-silent sentence nor an exemption is a refusal.

    Production line: the `if not present: raise` branch in
    `enforce_if_silent_contract`. Drop it and a source with neither builds,
    planting no if-silent meta — the wish, not the standard.
    """
    fields = ra.parse_source(SOURCE)
    fields.pop("no_if_silent", None)
    assert "no_if_silent" not in fields, "fixture lost its exemption — test is vacuous"
    with pytest.raises(ra.ArtifactError, match="neither"):
        ra.render(fields, template=template)


def test_a_source_with_both_if_silent_and_an_exemption_is_refused(template):
    """Both is the same hollowness as neither, in a new place (#455).

    Production line: the `if no_if_silent and present: raise` branch.
    """
    fields = ra.parse_source(SOURCE)
    assert "no_if_silent" in fields, "fixture carries no exemption — cannot add both"
    fields["lead"] += (
        '\n<p id="if-silent"><span class="key">if you say nothing</span> '
        "the fixture parks — no default is taken.</p>")
    with pytest.raises(ra.ArtifactError, match="both"):
        ra.render(fields, template=template)


def test_an_empty_or_decoy_if_silent_is_refused(template):
    """A decoy if-silent — present but empty — is the hollowness #455 ends.

    Production line: `scan_if_silent`'s non-empty text settlement, read by
    the `if not meaningful: raise` branch. Collapse meaningful to present
    and this passes while the reader still does not know the cost of silence.
    Refuse on ABSENCE of text, never on a word or character count.
    """
    fields = ra.parse_source(SOURCE)
    fields.pop("no_if_silent", None)
    for decoy, why in [
        ('<p id="if-silent"></p>', "empty"),
        ('<p id="if-silent">   </p>', "whitespace-only"),
        ('<p id="if-silent"><br></p>', "element but no text"),
    ]:
        f = dict(fields)
        f["lead"] += "\n" + decoy
        with pytest.raises(ra.ArtifactError, match="empty|whitespace") as caught:
            ra.render(f, template=template)
        assert "if-silent" in str(caught.value).lower() or "silence" in str(caught.value).lower(), (
            "the refusal for %r did not name if-silent: %r" % (why, caught.value))


def test_a_meaningful_if_silent_builds_and_carries_the_meta(template):
    """Happy path: one real sentence and the built artifact records it.

    Production line: `enforce_if_silent_contract` returns `"if-silent"`,
    `_inject_if_silent_meta` plants it. Drop either and the meta is absent.
    """
    fields = ra.parse_source(SOURCE)
    fields.pop("no_if_silent", None)
    fields["lead"] += (
        '\n<p id="if-silent"><span class="key">if you say nothing</span> '
        "the fixture parks — no default is taken.</p>")
    doc = ra.render(fields, template=template)
    assert ra.if_silent_status(doc) == "if-silent", "the if-silent meta was not written"
    present, meaningful = ra.scan_if_silent(doc)
    assert present and meaningful, "scan_if_silent did not find the sentence"


def test_an_exempt_if_silent_builds_and_carries_the_exempt_meta(template):
    """Exemption: `no_if_silent:` and the built meta carries the reason."""
    fields = ra.parse_source(SOURCE)
    assert fields["no_if_silent"], "fixture carries no exemption — test is vacuous"
    doc = ra.render(fields, template=template)
    assert ra.if_silent_status(doc) == "exempt: " + fields["no_if_silent"], \
        "the exempt meta was not written or lost the reason"


def test_an_untemplated_artifact_has_no_if_silent_meta_and_is_not_asked_to_have_one():
    """Src-less artifacts cannot be rebuilt. A future walking guard reads
    `classify` first: `untemplated` is skipped by class. Verified against the
    real corpus so the test cannot pass over an empty directory.
    """
    import glob
    untemplated = None
    for path in sorted(glob.glob(os.path.join(HERE, ".dreamwork", "review", "*.html"))):
        with open(path, encoding="utf-8") as handle:
            if ra.classify(handle.read()) == "untemplated":
                untemplated = path
                break
    assert untemplated, \
        "no untemplated artifact found in the corpus — the test is vacuous"
    with open(untemplated, encoding="utf-8") as handle:
        assert ra.if_silent_status(handle.read()) is None, \
            "%s is untemplated but carries an if-silent meta" % untemplated


def test_if_silent_contract_precondition_at_least_one_src_is_checked():
    """Precondition: at least one buildable source exists under review/src/.

    A check that matches nothing passes forever. Derived at runtime so a
    fixture count cannot go stale.
    """
    src = os.path.join(HERE, ".dreamwork", "review", "src")
    assert os.path.isdir(src), "review/src/ is missing — the contract has no corpus"
    sources = [name for name in os.listdir(src) if name.endswith(".html")]
    assert sources, (
        "review/src/ has no .html sources — enforce_if_silent_contract would "
        "match nothing and pass forever")


def test_the_if_silent_meta_sits_beside_the_ask_meta_in_head(template):
    """If-silent meta is planted beside the ask meta / stamp, in `<head>`."""
    fields = ra.parse_source(SOURCE)
    doc = ra.render(fields, template=template)
    head_end = doc.index("</head>")
    silent_pos = doc.index(ra.IF_SILENT_META_NAME)
    ask_pos = doc.index(ra.ASK_META_NAME)
    assert silent_pos < head_end, "the if-silent meta is outside <head>"
    assert abs(silent_pos - ask_pos) < 250, \
        "the if-silent meta is far from the ask meta — not 'beside' it"


def test_no_meta_in_a_built_head_is_missing_its_close():
    """#436 and #455 each add a `<meta>` to the head by anchoring on the tag
    before it. Both anchors matched the tag *minus its own closing `>`*, so a
    substitution left the old `>` behind and an insertion at `.end()` landed
    before it — one stray `>` per meta, rendered as text at the top of the
    page. He reported it twice before it was traced, and suspected the
    template; the template was innocent. Production line: the `\\s*>` at the
    end of `ASK_META_RE` / `IF_SILENT_META_RE` and the two inline
    template-stamp anchors.
    """
    import glob
    built = sorted(glob.glob(os.path.join(HERE, ".dreamwork", "review", "*.html")))
    # PRECONDITION, derived: there is a corpus, and its artifacts actually
    # carry the metas whose insertion caused this. A pass over zero files, or
    # over files predating #436/#455, means nothing.
    assert built, "no built artifacts found to check"
    with_metas = [p for p in built
                  if ra.ASK_META_NAME in open(p, encoding="utf-8").read()]
    assert with_metas, (
        "no built artifact carries the #436 ask meta — this check has no "
        "subject and would pass forever (%d built files scanned)" % len(built))
    for path in with_metas:
        text = open(path, encoding="utf-8").read()
        head = text[:text.index("<title")]
        unclosed = re.findall(r"<meta[^<>]*(?=<)", head)
        assert unclosed == [], (
            "%s has a <meta> with no closing '>': %r" % (path, unclosed))
        assert ">>" not in head, (
            "%s head carries a stray '>' — the meta-anchor regexes must "
            "swallow the tag close (see ASK_META_RE)" % path)


# ── corpus coverage / walking guard (#436 remainder) ──────────────────────
#
# Every built artifact is checked (ask meta) or side-exempt with a reason.
# Sourceless is the set difference {built}−{src}, never |built|−|src|.
# Production line for strip-#ask: check_examined_artifact's "meta says ask but
# id=ask is MISSING" branch.


def test_corpus_coverage_equation_holds_on_the_real_tree():
    """The live corpus satisfies examined ∪ side_exempt == built as sets.

    PRECONDITION derived at runtime: built non-empty, side-file present, at
    least one examined and at least one side-exempt (today's shape). A pass
    over an empty review dir would be the silent-pass failure this closes.
    """
    review = os.path.join(HERE, ".dreamwork", "review")
    result = ra.corpus_contract_coverage(review_dir=review)
    assert result["built"], "no built artifacts — coverage would be vacuous"
    assert result["examined"], "no examined artifacts — ask meta missing on all"
    assert result["side_exempt"], (
        "no side-exempt artifacts — the untemplated half vanished or the "
        "side-file is empty; either way the equation's other arm is untested")
    # Sets, not counts:
    assert result["examined"] | result["side_exempt"] == result["built"], (
        "coverage equation failed: missing=%r extra=%r"
        % (sorted(result["built"] - (result["examined"] | result["side_exempt"])),
           sorted((result["examined"] | result["side_exempt"]) - result["built"])))
    assert result["examined"] & result["side_exempt"] == set(), (
        "examined ∩ side_exempt must be empty: %r"
        % sorted(result["examined"] & result["side_exempt"]))
    assert result["unaccounted"] == set(), (
        "unaccounted: %r" % sorted(result["unaccounted"]))
    assert result["unbuilt_src"] == set(), (
        "source(s) never built ({src}−{built}): %r — #329 does not catch these"
        % sorted(result["unbuilt_src"]))
    # Sourceless is the set difference, and today it equals the side-exempt set
    # (every untemplated page is side-exempt; every side-exempt is untemplated).
    assert result["sourceless"] == result["built"] - result["src"]
    assert result["ok"], "failures: %s" % result["failures"]


def test_sourceless_is_set_difference_not_count_subtraction():
    """|{built}| − |{src}| is only right when every src has a built twin.

    The production helpers expose both sets so a future unbuilt source cannot
    make the arithmetic look fine while sourceless is understated.
    """
    review = os.path.join(HERE, ".dreamwork", "review")
    built = ra.list_built_basenames(review)
    src = ra.list_src_basenames(review)
    assert built - src == ra.corpus_contract_coverage(review_dir=review)["sourceless"]
    # PRECONDITION: today every src is built, so the arithmetic happens to
    # match — assert that gap explicitly so the day it diverges is a finding.
    assert src - built == set(), (
        "unbuilt source(s) present: %r" % sorted(src - built))
    assert len(built) - len(src) == len(built - src), (
        "arithmetic and set difference diverged — an unbuilt src or a "
        "basename mismatch is hiding")


def test_stripping_ask_from_a_content_ask_artifact_reds_the_corpus_walk(tmp_path):
    """Red-proof: remove #ask from a content='ask' artifact → walk fails.

    Production line: `check_examined_artifact`'s branch
    `if ask == "ask": ... if not present: failures.append(...)`.
    A green red-run here is a finding — the meta alone must not pass.
    """
    review = os.path.join(HERE, ".dreamwork", "review")
    # PRECONDITION: find a real content=ask artifact with a real #ask element.
    victim_name = None
    victim_text = None
    for name in sorted(ra.list_built_basenames(review)):
        text = open(os.path.join(review, name), encoding="utf-8").read()
        if ra.ask_status(text) == "ask":
            present, meaningful = ra.scan_ask(text)
            if present and meaningful:
                victim_name = name
                victim_text = text
                break
    assert victim_name, (
        "no content=ask artifact with a meaningful #ask — strip red-proof "
        "has no subject")

    # Build a private corpus: copy every built file + the side-file, then
    # strip #ask only on the victim. The production walk must see the rest of
    # the corpus too or the coverage equation is untested.
    private = tmp_path / "review"
    private.mkdir()
    (private / "src").mkdir()
    import shutil
    for name in ra.list_built_basenames(review):
        shutil.copy2(os.path.join(review, name), private / name)
    for name in ra.list_src_basenames(review):
        shutil.copy2(os.path.join(review, "src", name), private / "src" / name)
    shutil.copy2(
        os.path.join(review, ra.LEGACY_EXEMPTIONS_NAME),
        private / ra.LEGACY_EXEMPTIONS_NAME)

    # Strip the outer id="ask" element. Leave the meta so a different branch
    # is not what reds.
    stripped, n = re.subn(
        r'<([a-zA-Z0-9]+)\b[^>]*\bid=["\']ask["\'][^>]*>.*?</\1>',
        '',
        victim_text,
        count=1,
        flags=re.S,
    )
    assert n == 1, "failed to strip exactly one #ask element from %s" % victim_name
    assert ra.ask_status(stripped) == "ask", (
        "strip must leave the meta in place — otherwise a different branch reds")
    present, _ = ra.scan_ask(stripped)
    assert not present, "strip did not remove #ask — red-proof is vacuous"
    (private / victim_name).write_text(stripped, encoding="utf-8")

    result = ra.corpus_contract_coverage(review_dir=str(private))
    assert not result["ok"], (
        "strip of #ask from %s left corpus ok — production line is wrong"
        % victim_name)
    joined = " ".join(result["failures"]).lower()
    assert "missing" in joined or "ask" in joined, (
        "failure did not name the missing ask: %r" % result["failures"])


def test_dropping_a_side_file_entry_leaves_an_unaccounted_artifact(tmp_path):
    """Red-proof of the coverage equation: omit one exempt → unaccounted.

    Production line: `unaccounted = built - examined - side_keys` in
    `corpus_contract_coverage`.
    """
    review = os.path.join(HERE, ".dreamwork", "review")
    full = ra.corpus_contract_coverage(review_dir=review)
    assert full["side_exempt"], "no side-exempt to drop — test is vacuous"
    drop = sorted(full["side_exempt"])[0]

    private = tmp_path / "review"
    private.mkdir()
    (private / "src").mkdir()
    import shutil
    for name in full["built"]:
        shutil.copy2(os.path.join(review, name), private / name)
    for name in full["src"]:
        shutil.copy2(os.path.join(review, "src", name), private / "src" / name)
    # Rewrite side-file without `drop`.
    lines = []
    with open(os.path.join(review, ra.LEGACY_EXEMPTIONS_NAME), encoding="utf-8") as handle:
        for line in handle:
            if line.strip().startswith(drop):
                continue
            lines.append(line)
    (private / ra.LEGACY_EXEMPTIONS_NAME).write_text("".join(lines), encoding="utf-8")

    result = ra.corpus_contract_coverage(review_dir=str(private))
    assert not result["ok"]
    assert drop in result["unaccounted"], (
        "dropped %s but unaccounted=%r" % (drop, sorted(result["unaccounted"])))


# ── #436 askmark residual: seal + pair precondition ───────────────────────
#
# Prior lanes landed the build-time contract and the side-file coverage
# equation. This brief's residual: (1) state what counts as an #ask without
# requiring sub-decision labels + rec + if-silent inside it; (2) seal the
# grandfather list so it cannot quietly absorb new artifacts.


def test_corpus_derives_both_an_ask_and_a_non_ask_subject():
    """PRECONDITION the brief names: both branches have a live corpus subject.

    Derive at runtime — a fixture with two hand-written cases that happen to
    differ today is a check with an invisible expiry date. Counts land on the
    OK path so a zero-match pass is visible.
    """
    review = os.path.join(HERE, ".dreamwork", "review")
    with_ask = []
    without_ask = []
    for name in sorted(ra.list_built_basenames(review)):
        text = open(os.path.join(review, name), encoding="utf-8").read()
        present, meaningful = ra.scan_ask(text)
        if present and meaningful:
            with_ask.append(name)
        else:
            without_ask.append(name)
    # Counts on the OK row — a silent empty scan would read the same as green.
    assert with_ask, (
        "no built artifact carries a meaningful #ask — the positive branch "
        "has no subject (built=%d)" % len(with_ask + without_ask))
    assert without_ask, (
        "every built artifact carries a meaningful #ask — the negative "
        "branch (side-exempt / no-ask / decided) has no subject")
    # And the coverage walk still accounts for every basename either way.
    result = ra.corpus_contract_coverage(review_dir=review)
    assert result["ok"], "failures: %s" % result["failures"]
    assert len(with_ask) >= 1 and len(without_ask) >= 1
    # Put the derived pair size where a hollow check would still print 0 of 0.
    assert len(with_ask) + len(without_ask) == len(result["built"]), (
        "pair partition missed basenames: with=%d without=%d built=%d"
        % (len(with_ask), len(without_ask), len(result["built"])))


def test_legacy_exemption_reason_must_open_with_pre_436(tmp_path):
    """Red-proof: a non-legacy reason is refused at parse time.

    Production line: `load_legacy_exemptions`'s
    `if not reason.startswith(LEGACY_REASON_PREFIX): raise` branch. Without
    it the side-file accepts any free-text reason and becomes a quiet landing
    pad for post-contract pages. A green red-run here is a finding.
    """
    path = tmp_path / ra.LEGACY_EXEMPTIONS_NAME
    path.write_text(
        "ghost-new.html: post-contract design note; no src/\n",
        encoding="utf-8",
    )
    with pytest.raises(ra.ArtifactError, match=re.escape(ra.LEGACY_REASON_PREFIX)):
        ra.load_legacy_exemptions(str(path))


def test_legacy_exemption_with_valid_prefix_still_loads(tmp_path):
    """Neighbour of the seal: a real pre-#436 reason still parses."""
    path = tmp_path / ra.LEGACY_EXEMPTIONS_NAME
    path.write_text(
        "tasks-page.html: pre-#436 untemplated; the hand-rolled reference\n",
        encoding="utf-8",
    )
    side = ra.load_legacy_exemptions(str(path))
    assert side == {
        "tasks-page.html": "pre-#436 untemplated; the hand-rolled reference"
    }


def test_side_file_entry_for_a_src_having_page_reds_coverage(tmp_path):
    """Red-proof: side-exempting a page that has a builder source fails.

    Production line: `side_with_src = (side_keys & built) & src` in
    `corpus_contract_coverage`. A page with src/ uses `no_ask:` at build
    time; listing it here is the quiet-growth path.
    """
    review = os.path.join(HERE, ".dreamwork", "review")
    full = ra.corpus_contract_coverage(review_dir=review)
    assert full["src"], "no src-having artifacts — seal red-proof has no subject"
    # Pick a src-having examined page (has ask meta) so the double-check alone
    # is not what reds — we also need a sourceless twin to keep coverage math
    # honest. Actually: listing an examined page also hits `double`. To isolate
    # the src-seal line, list a src-having page that we strip of its ask meta
    # so it is not examined, then put it in the side-file with a pre-#436 reason.
    victim = sorted(full["src"] & full["examined"])[0]
    private = tmp_path / "review"
    private.mkdir()
    (private / "src").mkdir()
    import shutil
    for name in full["built"]:
        shutil.copy2(os.path.join(review, name), private / name)
    for name in full["src"]:
        shutil.copy2(os.path.join(review, "src", name), private / "src" / name)
    # Strip ask meta so victim is not examined (else double reds first).
    victim_text = (private / victim).read_text(encoding="utf-8")
    stripped = re.sub(
        r'<meta\s+name=["\']%s["\']\s+content=["\'][^"\']*["\']\s*>\s*'
        % re.escape(ra.ASK_META_NAME),
        "",
        victim_text,
        count=1,
    )
    assert ra.ask_status(stripped) is None, "meta strip failed — wrong branch would red"
    (private / victim).write_text(stripped, encoding="utf-8")
    # Append victim to the side-file with a legacy-looking reason.
    side_src = open(
        os.path.join(review, ra.LEGACY_EXEMPTIONS_NAME), encoding="utf-8"
    ).read()
    (private / ra.LEGACY_EXEMPTIONS_NAME).write_text(
        side_src + "\n%s: pre-#436 quietly parked a src-having page\n" % victim,
        encoding="utf-8",
    )
    result = ra.corpus_contract_coverage(review_dir=str(private))
    assert not result["ok"], (
        "side-exempting src-having %s left corpus ok — production line is wrong"
        % victim)
    joined = " ".join(result["failures"])
    assert victim in joined and ("source" in joined.lower() or "src" in joined.lower()), (
        "failure did not name the src-having side-exempt: %r" % result["failures"])


def test_live_side_file_reasons_all_open_with_legacy_prefix():
    """Live corpus: every side-file reason is a sealed grandfather entry.

    Derived at runtime from the real file so a new free-text reason cannot
    land without this failing. Count on the OK row.
    """
    path = os.path.join(HERE, ".dreamwork", "review", ra.LEGACY_EXEMPTIONS_NAME)
    side = ra.load_legacy_exemptions(path)
    assert side, "side-file empty — seal has no subject"
    for name, reason in side.items():
        assert reason.startswith(ra.LEGACY_REASON_PREFIX), (
            "%s reason %r does not open with %r" % (name, reason, ra.LEGACY_REASON_PREFIX))
    # side_exempt ⊆ sourceless on the live tree
    result = ra.corpus_contract_coverage(
        review_dir=os.path.join(HERE, ".dreamwork", "review"))
    assert result["side_exempt"] <= result["sourceless"], (
        "side_exempt not ⊆ sourceless: %r"
        % sorted(result["side_exempt"] - result["sourceless"]))
    assert result["ok"], "failures: %s" % result["failures"]
    # Count on the OK path (hollow check would still print 0).
    assert len(side) == len(result["side_exempt"]) == len(result["sourceless"])


def test_single_decision_ask_is_meaningful_without_sub_decision_labels(template):
    """What counts as #ask: one decision, no alternatives, still builds.

    Requiring sub-decision labels / rec / if-silent *inside* #ask would force
    decoys on single-call pages. if-silent is #455 (separate element); rec and
    multi-option labels are voice, not the build floor.
    """
    fields = ra.parse_source(SOURCE)
    fields.pop("no_ask", None)
    fields.pop("no_if_silent", None)
    # Minimal meaningful ask: label + one question, no Q1/Q2, no rec line.
    fields["lead"] = (
        '<div id="ask" class="ask-block">'
        '<div class="label">Ask</div>'
        '<p class="ask-q">Ship it, or not — free text is fine.</p>'
        "</div>\n"
        '<p id="if-silent"><span class="key">if you say nothing</span> '
        "the page parks; no default is taken.</p>"
    )
    doc = ra.render(fields, template=template)
    assert ra.ask_status(doc) == "ask"
    present, meaningful = ra.scan_ask(doc)
    assert present and meaningful
    # Sub-decision markers and a rec line are voice, not the floor — absent here
    # and the build still accepts the ask.
    assert "Sub-decisions" not in doc
    assert 'class="ask-rec"' not in doc
