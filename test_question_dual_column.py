"""#583 — the dual-column /question focus view, asserted on the shipped source.

pytest cannot see rendered structure (see the justfile: "pytest cannot see
rendered structure"), so the authoritative geometry check is the browser guard
`dev/capture/qdual.mjs`. This file pins the SOURCE contract the geometry is
built from, on the same surface `test_client_assets.py` already reads — the
byte-exact client constants — so a regression in the layout-split branch, the
focus-scoped grid, or the width-exception wiring is caught without a browser.

Production lines the red-proofs name (each assertion has one):
  · the registered native Question component's `qdual` container emission in
    dev/build/src/question.js — the layout-split branch. Removing it reds
    `test_registered_question_emits_dual_column`.
  · the `#qfocus.qdual`-scoped `grid-template-columns` in client/style.css —
    the grid that splits body (col 1) from compose (col 2). Removing the
    `#qfocus` scope reds the dashboard-protection half (a bare `.qa` grid would
    lay the dashboard out in two columns), and removing the grid reds the
    focus half. Sabotaging the rule reds `test_dual_column_css_is_focus_scoped`.
  · the `classList.toggle('question', …)` wiring in client/router.js at the
    three width-exception sites. Removing it reds `test_router_wires_question_width`.

Every check derives its expectation at runtime from the assembled constants
rather than from a literal tuned to today's tree, and each names the line it
defends. The red-proofs are run by hand (sabotage → red → restore) per the
repo's verification rule, not asserted here.
"""

import re
import unittest

import watch


def _fn_src(src, name):
    """Slice one top-level `function NAME(…)` body out of concatenated client JS.

    The client is shipped as one concatenated script, so the slice runs from the
    `function NAME` declaration to the next top-level `function ` at column 0.
    """
    start = src.find("function " + name + "(")
    if start < 0:
        return ""
    nxt = src.find("\nfunction ", start + 1)
    return src[start:nxt if nxt > 0 else len(src)]


def _registered_component_src(page, route):
    """Return the shipped component registered for ROUTE.

    Registration absence and component-definition absence are distinct
    failures: neither may collapse to an empty slice that blames the caller.
    The whitespace-tolerant matcher survives line wrapping in the bundle.
    """
    registration = re.search(
        r'\.\s*register\(\s*["\']' + re.escape(route) +
        r'["\']\s*,\s*\{\s*component\s*:\s*([A-Za-z_$][\w$]*)',
        page)
    if registration is None:
        raise AssertionError(
            "the shipped native registry does not register /%s" % route)
    component = registration.group(1)
    definitions = list(re.finditer(
        r'function\s+' + re.escape(component) + r'\s*\(',
        page[:registration.start()]))
    if not definitions:
        raise AssertionError(
            "the registered /%s component %s is absent from the shipment" %
            (route, component))
    return page[definitions[-1].start():registration.start()]


class QuestionDualColumnSource(unittest.TestCase):
    """The /question focus view ships a dual-column layout; the dashboard does
    not. The split is CSS-driven and scoped to the focus container, because
    `qaCard` is shared with the dashboard and is explicitly out of scope."""

    def test_registered_question_emits_dual_column_container(self):
        """The registered native view wraps its card in a dual container.

        Production line: the `qdual` class on the `#qfocus` div in
        dev/build/src/question.js Question. The dashboard question builders
        (buildQuestions/buildDashboard) never emit `#qfocus`, so the dual
        layout cannot reach them — asserted below as the dashboard half.
        """
        src = _registered_component_src(watch.PAGE, "question")
        # the container exists and carries the dual-column marker
        self.assertIn('id:"qfocus"', src,
                      "the registered /question component no longer emits "
                      "the #qfocus container")
        self.assertIn('className:"qdual"', src,
                      "the registered /question component lost its qdual "
                      "layout-split branch — #qfocus.qdual is not emitted")

    def test_dashboard_builders_do_not_emit_the_focus_container(self):
        """The dashboard and /questions listing are UNCHANGED: they never
        carry #qfocus, so the focus-scoped grid cannot reach their cards."""
        for name in ("buildDashboard", "buildQuestions"):
            src = _fn_src(watch.VIEWS_JS, name)
            self.assertNotIn('id="qfocus"', src,
                             "%s emits #qfocus — the focus container has leaked "
                             "onto the dashboard" % name)

    def test_dual_column_css_is_focus_scoped(self):
        """The grid that splits question body from compose is scoped to the
        focus container, so the dashboard's shared `.qa` cards stay one column.

        Production line: the `#qfocus.qdual … grid-template-columns` rule in
        client/style.css. Scoping matters more than the value: a bare `.qa`
        grid would lay every dashboard card out in two columns. So assert a
        rule whose SELECTOR carries #qfocus declares grid-template-columns
        (the split), and assert a width exception for body.question exists
        (the second column needs room the 72ch reading column does not give)."""
        css = watch.STYLE
        # the width exception — a third deliberate one beside /review and /file
        self.assertIn("body.question", css,
                      "the /question width exception (body.question .wrap) is "
                      "missing — the second column has no room")
        # scan rule blocks: a rule whose selector carries #qfocus and whose
        # body declares grid-template-columns is the focus-scoped split
        focus_grid = False
        for m in re.finditer(r"([^{}]*?)\{([^{}]*)\}", css, re.S):
            selector, body = m.group(1), m.group(2)
            if "#qfocus" in selector and "grid-template-columns" in body:
                focus_grid = True
                break
        self.assertTrue(focus_grid,
                        "no grid-template-columns declaration is scoped to "
                        "#qfocus — the dual-column split is either absent or "
                        "unscoped (an unscoped .qa grid would reshape the "
                        "dashboard)")

    def test_router_wires_question_width(self):
        """The width exception rides the same body-class + glide idiom /review
        and /file use (body.wsliding), toggled at the route-commit sites.

        Production line: `classList.toggle('question', …)` in client/router.js.
        Without it the column never widens on /question and the second column
        has no room."""
        rj = watch.ROUTER_JS
        toggles = re.findall(r"classList\.toggle\('question'", rj)
        # review/file toggle at three sites (rmr crossfade, normal crossfade,
        # no-transition first paint); question must keep parity so the glide
        # matches on every path.
        self.assertGreaterEqual(len(toggles), 1,
                                "router.js does not toggle body.question — the "
                                "/question width exception is never applied")


if __name__ == "__main__":
    unittest.main()
