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
import hashlib
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

# A body may use these without inventing anything, so the template must carry
# them. Without this, a fidelity failure could be "fixed" by deleting the rule.
CORE_SELECTORS = (
    ":root", "body", "a", "code", "pre", "h1", "h2", "h3", ".wrap", ".read",
    ".skip", ".toprail", ".toprail-in", ".identity", ".topactions", ".status",
    "main", "section", ".label", ".quiet", ".dim", ".dimmer", ".kicker",
    ".proposal", ".sub", ".lead", ".hero-grid", ".version-mark", ".call",
    ".notice", ".facts", ".fact", "table", "th", "td", ".scroller",
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


# The no-marks render, stamp-normalised, captured BEFORE this increment touched
# review_artifact.py (2026-07-28, rendered through review_artifact.py at the
# pre-change HEAD). The byte-identity test re-derives the pre-change output from
# git and confirms this constant matches it, so it cannot have been recomputed
# with the new code — the exact hollow-green trap criterion 3 exists for.
_NO_MARKS_RENDER_DIGEST = (
    "0eb232e800467837a3500ed7c98f450f2f799c7dc00aa759f53531cadda36af6")
_STAMP_NORMALISE_RE = re.compile(r"v\d+\+[0-9a-f]{8}")


def _normalise_stamp(document):
    """Blank the derived template stamp so a frame edit does not masquerade as
    a content change. Everything else must be byte-identical."""
    return _STAMP_NORMALISE_RE.sub("v<N>+<stamp>", document)


def _prechange_review_artifact():
    """The committed review_artifact.py from BEFORE essential-marks landed.

    Resolved by CONTENT, not a pinned SHA: the newest commit whose
    review_artifact.py lacks the essential-marks constant, so it survives a
    rebase that rewrites the SHA. Returns (module, ref) or (None, None) when no
    pre-change copy is reachable in git (then the frozen digest is the
    evidence). Used only to PROVE the frozen digest was captured honestly."""
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


def test_a_source_with_no_marks_renders_byte_identically_apart_from_the_stamp(template):
    """The whole point of increment 1: the frame gains the mark machinery and
    NOTHING ELSE changes.

    The expected side is INDEPENDENT of the code under test. The trap this
    exists for is recomputing both sides with the new code, which makes them
    move together and the check prove nothing (it has produced two false greens
    in this repo). So: the frozen digest was captured from the pre-change
    builder, and the test re-runs that pre-change builder out of git to PROVE
    the digest is honest, then compares the new builder against it.

    Production line that must change for this to FAIL on a regression: any new
    code path in render() that touches `out` (or the fields it fills from) when
    `essential_marks` returns an empty list — a tab, a class, a script, a
    wrapper. The check passes while those paths stay inert for a no-marks body.
    """
    # Precondition, derived not assumed: the fixture genuinely declares no
    # mark, or this assertion is vacuous.
    assert "data-mark" not in ra.parse_source(SOURCE)["body"]
    now = _normalise_stamp(ra.render(ra.parse_source(SOURCE), template=template))
    assert hashlib.sha256(now.encode()).hexdigest() == _NO_MARKS_RENDER_DIGEST, (
        "a no-marks source no longer renders byte-identically — the marks "
        "machinery altered output it must leave untouched")
    # Honesty proof: the frozen digest really IS the pre-change render. The
    # pre-change builder is checked out of git and re-run; if it disagrees, the
    # frozen constant was stale or fabricated rather than captured beforehand.
    old, ref = _prechange_review_artifact()
    if old is not None:
        assert not hasattr(old, "essential_marks"), (
            "resolved ref %s already carries essential marks — the resolver "
            "picked the wrong commit, so the comparison would be new-vs-new "
            "and prove nothing" % ref)
        pre = _normalise_stamp(
            old.render(old.parse_source(SOURCE), template=template))
        assert hashlib.sha256(pre.encode()).hexdigest() == _NO_MARKS_RENDER_DIGEST, (
            "the frozen digest no longer matches the pre-change builder at %s "
            "— re-capture it after an intentional template change" % ref)


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
    labels, no_id, blanks = ra.essential_marks(body)
    assert labels == ["zulu last", "alpha first", "mike middle"], labels
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
    labels, no_id, blanks = ra.essential_marks(element)
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
    labels, no_id, blanks = ra.essential_marks(padded)
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
    labels, no_id, blanks = ra.essential_marks("<p data-mark>stray</p>")
    assert (labels, no_id, blanks) == ([], [], []), (labels, no_id, blanks)
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
