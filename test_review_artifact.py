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
    assert not differing, \
        "template rules drifted from tasks-page.html: %r" % differing


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


def test_the_supported_languages_are_the_advertised_set():
    """Scope discipline (#339): a small, honest set, named here so adding one
    is a deliberate act rather than silent scope growth."""
    assert ra.SUPPORTED_LANGUAGES == frozenset(
        {"python", "json", "bash", "javascript", "html"})
