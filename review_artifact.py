#!/usr/bin/env python3
"""review_artifact.py — build a review artifact from the one template (#325).

Every request for a review ships a self-contained HTML artifact (his rule,
2026-07-25), so that page is the surface the loop's proposals are read on. Left
to per-artifact authorship it reinvented itself every time: the twelve artifacts
in `.dreamwork/review/` carry FIVE distinct `font-family` declarations and eight
page backgrounds all meaning "the dark one". His words on 2026-07-27 21:38 were
that `tasks-page.html` "is nice and a good example. We should save it as a
template so we can include it in the bundle and also so we can iterate on it and
perfect it as a template."

So this is a builder, not a documented block to copy. A block asks every future
author to remember, which is the mechanism `#203` ruled out and the drift above
is what it produces. The template — `review-artifact.template.html` beside this
file, so it ships with the skill and is reachable from whatever project the loop
is running on — owns the head, the palette, the frame and the footer. The source
owns the words.

    build     python3 review_artifact.py build .dreamwork/review/src/<slug>.html
    check     python3 review_artifact.py check .dreamwork/review/*.html
    version   python3 review_artifact.py version

THE SOURCE, and why it is a second file rather than the artifact itself: the
template must be able to change. `build` is re-runnable over every source in a
directory, so "iterate on it and perfect it" means editing the template and
rebuilding — which is impossible if the only copy of an artifact's words is
inside its built output. Sources live in `.dreamwork/review/src/` and the built
artifact lands beside that directory as `.dreamwork/review/<slug>.html`. The
subdirectory is load-bearing: `watch.py`'s `list_reviews` is a non-recursive
`os.listdir` filtered on `.html`, so a source in `src/` is invisible to it while
a source sitting next to the artifacts would be listed and served as one.

FAIL LOUD, in both directions. A missing required slot is an error and so is an
unknown key, because the failure mode of every template system is a typo that
silently drops a section — and an artifact missing its own recommendation still
looks finished. Output that would fetch anything is refused rather than warned
about, since offline-clean is the artifact's contract with a laptop on a plane.

VERSIONING is content-derived: the stamp is `v<series>+<8 hex of the template
file>`, written into a `<meta>` and into the footer. Nothing has to remember to
bump it, and after the template changes every artifact built before says so —
`check` reports `stale`. Artifacts built before this existed report
`untemplated`; they are not migrated (that is a separate call, deliberately).

The format contract is in `file-formats.md`; the checks are in
`test_review_artifact.py`.
"""
import argparse
import hashlib
import html.parser
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(HERE, "review-artifact.template.html")

# The series is declared in the template's own opening comment, so a breaking
# reshape of the slot set is announced where an author is already looking. The
# hash beside it is what actually detects staleness.
SERIES_RE = re.compile(r"<!--dreamwork-review-template:\s*(v\d+)")
# That opening comment is documentation FOR AN AUTHOR — it names the slots and
# shows the region syntax, so it necessarily contains text the region matcher
# would read as a region. It is stripped on the way out, which also keeps
# builder instructions out of a page the human is trying to read; a one-line
# provenance comment replaces it. The stamp is computed BEFORE the strip, so it
# still covers every byte of the template including its docs.
TEMPLATE_DOC_RE = re.compile(r"<!--dreamwork-review-template:.*?-->\n?", re.S)

REQUIRED = ("title", "identity", "headline", "lead", "body", "footer")
OPTIONAL = ("context", "status", "tag", "sub", "call", "aside", "nav",
            "skip", "skip_href", "aside_label")
# Filled by the builder from the others; an author who sets one is corrected
# rather than quietly overridden.
DERIVED = ("TEMPLATE_STAMP", "hero_solo")

HEADER_OPEN = "<!--dreamwork-review-source"
BLOCK_RE = re.compile(r"^<!--#([a-z_]+)-->[ \t]*$", re.M)
SCALAR_RE = re.compile(r"^([a-z_]+):[ \t]*(.*)$")
SLOT_RE = re.compile(r"\{\{([A-Za-z_]+)\}\}")
REGION_RE = re.compile(r"<!--\?([a-z_]+)-->(.*?)<!--/\?\1-->", re.S)

# Attributes the browser fetches on load. `href` on <a> is deliberately absent:
# a link in prose is not a fetch, and a check that forbade it would push authors
# into writing bare URLs as text, which is worse for the reader and no safer.
FETCHING = {
    "link": ("href",), "script": ("src",), "img": ("src", "srcset"),
    "image": ("href", "xlink:href"), "use": ("href", "xlink:href"),
    "iframe": ("src",), "frame": ("src",), "embed": ("src",),
    "object": ("data",), "source": ("src", "srcset"), "track": ("src",),
    "video": ("src", "poster"), "audio": ("src",), "input": ("src",),
    "body": ("background",), "table": ("background",), "td": ("background",),
}
REMOTE_RE = re.compile(r"""(?:^|[\s'"(])(?:https?:)?//""", re.I)
CSS_FETCH_RE = re.compile(r"@import\b|url\(\s*['\"]?(?:https?:)?//", re.I)


class ArtifactError(Exception):
    """A source or an output that must not be written."""


# ── the template ──────────────────────────────────────────────────────────


def read_template(path=None):
    with open(path or TEMPLATE_PATH, encoding="utf-8") as handle:
        return handle.read()


def template_stamp(template):
    """`v1+ab12cd34` — the series it declares, plus a digest of its bytes.

    Derived from the text it is handed, never from a constant: the whole point
    is that editing the template changes this without anyone remembering to.
    """
    match = SERIES_RE.search(template)
    if not match:
        raise ArtifactError(
            "template declares no series — expected a leading "
            "'<!--dreamwork-review-template: v<N>' comment")
    digest = hashlib.sha256(template.encode("utf-8")).hexdigest()[:8]
    return "%s+%s" % (match.group(1), digest)


def check_template(template):
    """The authoring comment must be ONE comment, and end where it looks like it does.

    Learned by writing the bug: that comment documents the region syntax, and a
    literal close-comment sequence inside it ends the comment early — the rest
    of the prose then leaves the comment and renders as text at the top of the
    page. It is invisible in the source and obvious to a reader, which is the
    worst combination, so it is refused here rather than described in a note.
    """
    start = template.find("<!--dreamwork-review-template:")
    if start < 0:
        raise ArtifactError("template has no authoring comment")
    end = template.find("-->", start)
    tail = template[end + 3:].lstrip()
    if not tail.startswith("<html"):
        raise ArtifactError(
            "the template's authoring comment ends early — it contains a "
            "close-comment sequence, so %r would render as page text"
            % tail[:60])
    return template


# ── the source ────────────────────────────────────────────────────────────


def parse_source(text):
    """Scalars from the header comment, blocks from `<!--#name-->` markers."""
    # A source without the header has no title, so it cannot be built at all.
    if not text.startswith(HEADER_OPEN):
        raise ArtifactError(
            "source must open with %s (see file-formats.md)" % HEADER_OPEN)
    end = text.find("-->", len(HEADER_OPEN))
    if end < 0:
        raise ArtifactError("source header comment is never closed")
    fields = {}
    for lineno, line in enumerate(text[len(HEADER_OPEN):end].splitlines(), 2):
        if not line.strip():
            continue
        match = SCALAR_RE.match(line.strip())
        if not match:
            raise ArtifactError(
                "source header line %d is not `key: value`: %r" % (lineno, line))
        key, value = match.group(1), match.group(2).strip()
        if key in fields:
            raise ArtifactError("source sets %r twice" % key)
        fields[key] = value

    rest = text[end + 3:]
    marks = list(BLOCK_RE.finditer(rest))
    for index, mark in enumerate(marks):
        key = mark.group(1)
        stop = marks[index + 1].start() if index + 1 < len(marks) else len(rest)
        if key in fields:
            raise ArtifactError("source sets %r twice" % key)
        fields[key] = rest[mark.end():stop].strip("\n")
    leading = rest[:marks[0].start()] if marks else rest
    if leading.strip():
        raise ArtifactError(
            "source has content before its first <!--#block--> marker: %r"
            % leading.strip()[:60])
    return fields


def validate(fields):
    for key in DERIVED:
        if key in fields:
            raise ArtifactError(
                "%r is derived by the builder; remove it from the source" % key)
    unknown = sorted(set(fields) - set(REQUIRED) - set(OPTIONAL))
    if unknown:
        raise ArtifactError(
            "source sets unknown slot(s): %s (known: %s)"
            % (", ".join(unknown), ", ".join(sorted(REQUIRED + OPTIONAL))))
    missing = [key for key in REQUIRED if not fields.get(key, "").strip()]
    if missing:
        raise ArtifactError("source is missing required slot(s): %s"
                            % ", ".join(missing))
    if fields.get("skip", "").strip() and not fields.get("skip_href", "").strip():
        raise ArtifactError("skip needs skip_href — a skip link to nowhere is "
                            "worse than none")
    return fields


# ── offline-clean ─────────────────────────────────────────────────────────


class _FetchScan(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hits = []
        self._style_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "style":
            self._style_depth += 1
        for name, value in attrs:
            if not value:
                continue
            if name in FETCHING.get(tag, ()) and REMOTE_RE.search(" " + value):
                self.hits.append("<%s %s=%r>" % (tag, name, value[:60]))
            if name == "style" and CSS_FETCH_RE.search(value):
                self.hits.append("style attribute on <%s>: %r" % (tag, value[:60]))

    def handle_endtag(self, tag):
        if tag == "style" and self._style_depth:
            self._style_depth -= 1

    def handle_data(self, data):
        if self._style_depth and CSS_FETCH_RE.search(data):
            found = CSS_FETCH_RE.search(data)
            start = max(0, found.start() - 20)
            self.hits.append("<style>: %r" % data[start:found.end() + 40])


def fetch_violations(document):
    """Everything in `document` a browser would go to the network for."""
    scan = _FetchScan()
    scan.feed(document)
    scan.close()
    return scan.hits


# ── the component vocabulary, enforced (#347-adjacent) ────────────────────
#
# The template's opening comment names the components a body may use and the
# classes each one takes. That list is documentation FOR AN AUTHOR and nothing
# read it, which is the same mechanism #325 exists to end: a block that asks
# every future author to remember produces drift. It duly did — a source wrote
# `<div class="fact"><strong>122</strong><small>open ids…</small></div>`, which
# is plausible HTML the template styles not at all, so the number ran straight
# into its caption as `122open ids…`. `check` said `current` and the build
# exited 0, because neither has ever looked at the words.
#
# TWO FINDINGS, TWO TREATMENTS, and conflating them would produce a check that
# is confidently wrong later:
#
#  1. A child of a documented component that carries none of that component's
#     classes is an unambiguous contract violation — the template styles
#     `.fact .number` and `.fact .caption` and nothing else, so there is no
#     legitimate third form. That REFUSES THE BUILD, exactly as an outward
#     fetch does.
#  2. An item count that does not fill the grid's last row is NOT a contract
#     violation. It is legal HTML rendering with a dead track, and the column
#     count is a fact about the TEMPLATE's stylesheet — a file this module must
#     be able to change. So it WARNS, and the number is READ FROM THE TEMPLATE
#     rather than written here; a literal `4` would be a check with an
#     invisible expiry date the first time the grid is reshaped.
#
# A component earns a rule by MEASUREMENT, never by looking like it should have
# one: rules for usage nobody counted would be guessing, and this module's whole
# complaint is about assertions nobody checked. `.fact` was the only entry until
# #365 counted every component across all 16 built artifacts; that count added
# two and refused three, including both of the two the task had named in
# advance. The counts and the refusals are recorded beside the dict, because the
# next person will reach for the same guesses.

COMPONENT_CHILDREN = {
    # component class -> the classes its direct children may carry
    "fact": ("number", "caption"),
    # #365's two additions, and they are the ones the MEASUREMENT supported
    # rather than the ones the task guessed. Counted across all 16 built
    # artifacts with this module's own depth-aware scan: `.spine-row` appears 25
    # times in 4 files and carries exactly `.spine-key`, `.spine-rail` and
    # `.spine-body` in all 25; `.spine-rail` carries exactly `.spine-dot` in all
    # 25. Unanimous and closed, which is what a rule here requires.
    "spine-row": ("spine-key", "spine-rail", "spine-body"),
    "spine-rail": ("spine-dot",),
}
# DELIBERATELY ABSENT, because measuring refuted them (#365 named both as the
# obvious next candidates): `.summary-line` has 37 uses across 5 files in THREE
# different idioms — bare `<span>`s in two files, `.key` + `<span>` in one,
# `.key` + `<div>` in two — so a rule would refuse three of the five. `.choice`
# and `.answer` are prose containers: 47 uses across 12 files, `.choice-grid` in
# four of them and inline `<b>`/`<code>/`<strong>`/`<em>` in the rest. A rule
# there would refuse most of the corpus. The guess and the measurement
# disagreed, which is the reason the task said measure first.
# The container whose item count is measured, and what its items are called.
GRID_COMPONENTS = {"facts": "fact"}
# `.facts{…grid-template-columns:repeat(4,…)}` in the template, including the
# narrower counts inside media queries; the widest is the one a dead track is
# visible at. `[^}]*` cannot cross a rule boundary, so this reads declarations
# of `.facts` itself and not of whatever follows it.
GRID_COLUMNS_RE = r"\.%s\s*\{[^}]*grid-template-columns\s*:\s*repeat\(\s*(\d+)"

# Tags that never take a closing tag, so they must not enter the depth stack.
_VOID = frozenset(
    "area base br col embed hr img input link meta param source track wbr".split())


def grid_columns(template, container="facts"):
    """The widest column count `container` declares, or None if it declares none.

    Derived, never constant: the point is that reshaping the grid in the
    template moves this without anyone remembering to. None is a real answer
    and disables the count check rather than inventing a default — a check that
    guesses its own premise is worse than an absent one.
    """
    found = re.findall(GRID_COLUMNS_RE % re.escape(container), template, re.S)
    return max(int(n) for n in found) if found else None


class _ComponentScan(html.parser.HTMLParser):
    """Direct children of a documented component, and items per grid row.

    HTML-aware rather than pattern-matched, because both questions are about
    depth: a `<code>` nested inside a caption is fine and a `<strong>` sitting
    beside one is not, and those look identical to a regex that cannot see
    nesting. Bare text directly inside a component counts as a child for the
    same reason it renders wrong — the styling lives on the class, so an
    unwrapped number is the same defect as a wrongly wrapped one.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []        # [(tag, classes)] of currently open elements
        self.bad = []          # (component, description) for each stray child
        self.rows = []         # (container, item count) per closed grid row
        self._open_rows = []   # [[container, depth, count]] still open

    # -- the two questions, asked once per element regardless of self-closing --

    def _enter(self, tag, attrs):
        classes = frozenset((dict(attrs).get("class") or "").split())
        self._check_child(tag, classes)
        for container, item in GRID_COMPONENTS.items():
            if container in classes:
                self._open_rows.append([container, len(self.stack), 0])
            if item in classes and self._open_rows:
                self._open_rows[-1][2] += 1

    def _check_child(self, tag, classes):
        if not self.stack:
            return
        _, parent_classes = self.stack[-1]
        for component, allowed in COMPONENT_CHILDREN.items():
            if component in parent_classes and not classes.intersection(allowed):
                self.bad.append((component, "<%s%s>" % (
                    tag, " class=%r" % " ".join(sorted(classes)) if classes else "")))

    # -- depth bookkeeping --

    def handle_starttag(self, tag, attrs):
        self._enter(tag, attrs)
        if tag not in _VOID:
            self.stack.append((tag, frozenset(
                (dict(attrs).get("class") or "").split())))

    def handle_startendtag(self, tag, attrs):
        self._enter(tag, attrs)          # `<x/>` closes itself; never stacked

    def handle_endtag(self, tag):
        # Pop to the matching tag rather than assuming balance: a source with a
        # stray `</div>` must still yield a usable reading instead of throwing.
        while self.stack:
            popped, _ = self.stack.pop()
            if popped == tag:
                break
        self._close_rows()

    def handle_data(self, data):
        if data.strip() and self.stack:
            _, parent_classes = self.stack[-1]
            for component in COMPONENT_CHILDREN:
                if component in parent_classes:
                    self.bad.append(
                        (component, "bare text %r" % data.strip()[:30]))

    def _close_rows(self):
        while self._open_rows and self._open_rows[-1][1] >= len(self.stack):
            container, _, count = self._open_rows.pop()
            self.rows.append((container, count))

    def close(self):
        super().close()
        self.stack = []
        self._close_rows()          # an unclosed container still gets counted


def component_violations(document):
    """Children of a documented component that carry none of its classes.

    Fatal: the template styles the documented classes and nothing else, so this
    renders wrong with no other symptom.
    """
    scan = _ComponentScan()
    scan.feed(document)
    scan.close()
    out = []
    for component, description in scan.bad:
        allowed = COMPONENT_CHILDREN[component]
        # "is neither `.spine-dot`" is what a `nor`-join produces for a
        # single-child component, and #365 added the first one. An author reading
        # a broken sentence wonders whether the tool is broken too.
        names = " nor ".join("`.%s`" % name for name in allowed)
        out.append("a `.%s` has a child that is %s %s: %s" % (
            component, "neither" if len(allowed) > 1 else "not", names,
            description))
    return out


def grid_warnings(document, template):
    """Grid rows whose item count leaves the last row short.

    Advisory: the row renders, it simply shows the container's own background
    where the missing items would be. The column count comes from `template`,
    so this follows a reshaped grid instead of asserting yesterday's number.
    """
    scan = _ComponentScan()
    scan.feed(document)
    scan.close()
    out = []
    for container, count in scan.rows:
        columns = grid_columns(template, container)
        if not columns or not count or count % columns == 0:
            continue
        out.append(
            "a `.%s` row carries %d `.%s` item(s) in a %d-column grid, so its "
            "last row shows %d empty track(s) — the count wants a multiple of "
            "%d (columns read from the template, not assumed)"
            % (container, count, GRID_COMPONENTS[container], columns,
               columns - count % columns, columns))
    return out


# ── syntax highlighting (build-time, #339) ────────────────────────────────
#
# A review artifact is a frozen record read offline, so highlighting is done
# once at BUILD time, not on every read: this emits <span class="tok-…"> into
# marked <pre><code class="language-…"> blocks and ships only the CSS for those
# classes in the template. No script in the artifact, no runtime cost, and a
# token class whose CSS is ever lost degrades to the block's own colour —
# never to broken code.
#
# Never guess the language. Only a block that DECLARES its language is coloured;
# an unmarked block, or one whose language is not supported below, is left
# byte-identical. A misdetected language colours code wrongly, which is worse
# than leaving it plain.
#
# Each language is a flat, leftmost-match scanner: an ordered list of
# (class, pattern) plus a trailing anonymous `.` fallback that guarantees the
# scan covers every byte — so the concatenation of every emitted token is
# exactly the source, which is the round-trip property the tests hold. The
# order is the precedence (comments and strings before keywords, keywords
# before identifiers). The set is deliberately small and honest — five
# languages cover what review artifacts actually carry; this is not a
# general-purpose highlighter.


def _scanner(spec):
    """Compile an ordered (class, pattern) spec into (master, names).

    A trailing anonymous `.` is appended so a single .match always advances:
    without it, a pattern gap would either loop forever or silently drop a
    character, and the latter is the bug the round-trip check exists to catch.
    """
    parts, names = [], []
    for name, pattern in spec:
        parts.append("(?P<g%d>%s)" % (len(names), pattern))
        names.append(name)
    parts.append("(?P<g%d>.)" % len(names))   # fallback: any one char
    names.append(None)
    return re.compile("|".join(parts), re.S), names


def _scan(master, names, src):
    """(class, text) left-to-right, covering every char of src."""
    out, pos = [], 0
    end = len(src)
    while pos < end:
        m = master.match(src, pos)
        out.append((names[m.lastindex - 1], m.group()))
        pos = m.end()
    return out


# _PY: triple-quoted strings first (so they are not split into line tokens),
# then decorators (the @ is also an operator, so dec must precede op), then
# keywords before builtins before call-names before bare identifiers.
_PY = [
    ("com", r"#[^\n]*"),
    ("str", r"[rbfuRBFU]{0,2}(?:\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?'''"
            r"|\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*')"),
    ("dec", r"@[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*"),
    ("kw", r"\b(?:def|class|return|if|elif|else|for|while|break|continue|"
           r"pass|raise|try|except|finally|with|as|import|from|global|"
           r"nonlocal|lambda|yield|del|assert|in|is|not|and|or|await|"
           r"async|match|case)\b"),
    ("typ", r"\b(?:True|False|None|self|cls|int|str|float|bool|list|dict|"
            r"set|tuple|bytes|range|type|object|frozenset|Exception|"
            r"ValueError|KeyError|AttributeError|TypeError)\b"),
    ("num", r"\b(?:0[xX][0-9a-fA-F]+|0[bB][01]+|0[oO][0-7]+|"
            r"\d+\.?\d*(?:[eE][+-]?\d+)?)\b"),
    ("fn", r"\b[A-Za-z_]\w*(?=\s*\()"),
    ("op", r"[-+*/%=<>!&|^~@:;,.(){}\[\]]+|->"),
    ("var", r"[A-Za-z_]\w*"),
]

_JSON = [
    ("str", r"\"(?:\\.|[^\"\\\n])*\""),
    ("num", r"-?\d+\.?\d*(?:[eE][+-]?\d+)?"),
    ("kw", r"\b(?:true|false|null)\b"),
    ("op", r"[{}\[\]:,]"),
]

_BASH = [
    ("com", r"#[^\n]*"),
    ("str", r"\"(?:\\.|[^\"\\\n])*\"|'[^']*'"),
    ("var", r"\$\{?[A-Za-z_]\w*\}?|\$\("),
    ("kw", r"\b(?:if|then|elif|else|fi|for|in|do|done|while|until|case|"
           r"esac|function|return|local|export|unset|set|shift|break|"
           r"continue|exit|echo|printf|read|cd|test|source|true|false)\b"),
    ("num", r"\b\d+\b"),
    ("op", r"\|\||&&|[|&;()<>]+"),
]

_JS = [
    ("com", r"//[^\n]*|/\*[\s\S]*?\*/"),
    ("str", r"`(?:\\.|[^`\\])*`|\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'"),
    ("kw", r"\b(?:var|let|const|function|return|if|else|for|while|do|break|"
           r"continue|switch|case|default|try|catch|finally|throw|new|class|"
           r"extends|super|this|typeof|instanceof|in|of|void|delete|yield|"
           r"await|async|import|export|from|as|null|undefined|true|false)\b"),
    ("num", r"\b\d+\.?\d*(?:[eE][+-]?\d+)?\b"),
    ("fn", r"\b[A-Za-z_$][\w$]*(?=\s*\()"),
    ("op", r"[-+*/%=<>!&|^~?:;,.(){}\[\]]+|=>"),
    ("var", r"[A-Za-z_$][\w$]*"),
]

# _HTML: a tag's name and its attribute names are coloured; text nodes and
# entities are not (they take the block's own colour). The tag pattern's
# lookahead requires what follows the name to be whitespace, `/` or `>`, so a
# bare `<` in text never starts a tag token.
_HTML = [
    ("com", r"<!--[\s\S]*?-->"),
    ("str", r"\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'"),
    ("tag", r"</?[A-Za-z][\w-]*(?=[\s>/])"),
    ("attr", r"\b[A-Za-z_][\w-]*(?=\s*=)"),
    ("op", r"</+>|[<>=]"),
]

# SQL is CASE-INSENSITIVE and both cases are real: schema designs here write
# `CREATE TABLE` and prose writes `select`. The scoped `(?i:…)` flag is used
# rather than compiling the master pattern with re.IGNORECASE, because that
# flag would apply to every OTHER language's spec too — and `_PY`'s
# `("typ", r"\b(?:True|False|None|…)")` must not start matching `none`.
#
# Order is load-bearing twice: `com` precedes `op` because `--` opens a comment
# while `-` is also an operator character, and `kw`/`typ` precede `var` because
# every keyword also matches a bare identifier.
_SQL = [
    ("com", r"--[^\n]*|/\*[\s\S]*?\*/"),
    ("str", r"'(?:''|[^'])*'"),
    ("kw", r"\b(?i:create|table|index|view|trigger|temporary|if|primary|key|"
           r"foreign|references|not|null|unique|check|default|constraint|"
           r"autoincrement|select|insert|update|delete|into|values|set|from|"
           r"where|group|by|having|order|limit|offset|join|left|right|inner|"
           r"outer|cross|natural|using|on|as|and|or|in|is|like|glob|between|"
           r"exists|case|when|then|else|end|begin|commit|rollback|savepoint|"
           r"transaction|drop|alter|rename|add|column|distinct|union|intersect|"
           r"except|all|asc|desc|pragma|with|recursive|collate|conflict|"
           r"replace|abort|ignore|deferrable|initially|immediate|deferred|"
           r"cascade|restrict|action|generated|always|stored|virtual|"
           r"returning|explain|analyze|vacuum|attach|detach|cast|nulls|first|"
           r"last|window|over|partition|filter|do|nothing|of|for|each|row)\b"),
    ("typ", r"\b(?i:integer|int|bigint|smallint|tinyint|text|varchar|char|"
            r"clob|blob|real|double|precision|float|numeric|decimal|boolean|"
            r"date|datetime|timestamp|time|json|uuid)\b"),
    ("num", r"\b(?:0[xX][0-9a-fA-F]+|\d+\.?\d*(?:[eE][+-]?\d+)?)\b"),
    ("fn", r"\b[A-Za-z_]\w*(?=\s*\()"),
    ("op", r"->>|->|\|\||[-+*/%=<>!,.;:(){}\[\]]+"),
    ("var", r"[A-Za-z_]\w*"),
]

_TOKENIZERS = {
    "python": _scanner(_PY),
    "json": _scanner(_JSON),
    "bash": _scanner(_BASH),
    "javascript": _scanner(_JS),
    "html": _scanner(_HTML),
    "sql": _scanner(_SQL),
}
SUPPORTED_LANGUAGES = frozenset(_TOKENIZERS)

_PRE_CODE_RE = re.compile(
    r'<pre><code(?P<attrs>[^>]*)>(?P<inner>.*?)</code></pre>', re.S)
_CLASS_ATTR_RE = re.compile(r'class\s*=\s*"([^"]*)"')
_LANG_RE = re.compile(r"\blanguage-([A-Za-z_][-\w]*)")


def _highlight_inner(inner_html, language):
    """Tokenise the (HTML-escaped) inner of one <code> block; return it wrapped
    in <span class="tok-…">, or None if the language is not supported (caller
    leaves that block untouched). Raises if a scan ever fails to cover every
    byte — partial markup that drops code is worse than no markup."""
    tokenizer = _TOKENIZERS.get(language)
    if tokenizer is None:
        return None
    master, names = tokenizer
    src = html.unescape(inner_html)        # the real code, entities resolved
    tokens = _scan(master, names, src)
    if "".join(text for _, text in tokens) != src:
        raise ArtifactError(
            "highlighter for %r did not cover every character — refusing to "
            "emit partial markup" % language)
    out = []
    for cls, text in tokens:
        escaped = html.escape(text, quote=False)
        if cls is None:
            out.append(escaped)
        else:
            out.append('<span class="tok-%s">%s</span>' % (cls, escaped))
    return "".join(out)


def highlight(document):
    """Colour every <pre><code class="language-…"> block whose language is
    supported. A block with no language marker, or one whose language is not
    supported, is returned byte-identical. Ships only spans; the CSS lives in
    the template."""
    def rewrite(match):
        attrs, inner = match.group("attrs"), match.group("inner")
        cls_match = _CLASS_ATTR_RE.search(attrs)
        if not cls_match:
            return match.group(0)
        lang_match = _LANG_RE.search(cls_match.group(1))
        if not lang_match:
            return match.group(0)
        coloured = _highlight_inner(inner, lang_match.group(1))
        if coloured is None:
            return match.group(0)
        return '<pre><code%s>%s</code></pre>' % (attrs, coloured)
    return _PRE_CODE_RE.sub(rewrite, document)


# ── the build ─────────────────────────────────────────────────────────────


def render(fields, template=None, warn=None):
    """Fill the template. Raises rather than writing anything questionable.

    `warn` is called once per advisory finding — things that render, but not the
    way the author meant. They are not errors because refusing a build over a
    stylistic reading would make this module the arbiter of taste; they are not
    silent because that is how the defect they describe reached twelve
    artifacts.
    """
    template = read_template() if template is None else template
    fields = dict(validate(dict(fields)))
    fields["TEMPLATE_STAMP"] = template_stamp(template)
    fields["hero_solo"] = "" if fields.get("aside", "").strip() else " solo"
    if not fields.get("aside_label", "").strip():
        fields["aside_label"] = "At a glance"

    check_template(template)
    stamped = TEMPLATE_DOC_RE.sub(
        "<!--Built from the dreamwork review template %s "
        "(review-artifact.template.html). Edit the source in "
        ".dreamwork/review/src/ and rebuild; edits here are lost.-->\n"
        % fields["TEMPLATE_STAMP"], template, count=1)
    if stamped == template:
        raise ArtifactError("template has no authoring comment to replace")
    template = stamped

    def region(match):
        key = match.group(1)
        if key not in REQUIRED + OPTIONAL + DERIVED:
            raise ArtifactError("template names an unknown region %r" % key)
        return match.group(2) if fields.get(key, "").strip() else ""

    framed = REGION_RE.sub(region, template)

    def slot(match):
        key = match.group(1)
        if key in fields:
            # Continuation lines pick up the slot's own indentation, so the
            # built file still reads as HTML when he opens it through /file.
            # Cosmetic to the browser, load-bearing to a reader and a diff.
            line = framed[framed.rfind("\n", 0, match.start()) + 1:match.start()]
            value = fields[key]
            if "\n" in value and not line.strip():
                value = value.replace("\n", "\n" + line)
            return value
        if key in OPTIONAL:
            # Reached only if the template moved an optional slot out of its
            # region, which would render the word "None" at a reader.
            raise ArtifactError(
                "template uses optional slot %r outside a <!--?%s--> region"
                % (key, key))
        raise ArtifactError("template names an unknown slot %r" % key)

    out = SLOT_RE.sub(slot, framed)

    left = SLOT_RE.findall(out) or REGION_RE.findall(out) or re.findall(
        r"<!--/?\?[a-z_]+-->", out)
    if left:
        raise ArtifactError("output still carries template markers: %r" % (left[:4],))
    # #339 — build-time syntax highlighting: emits <span class="tok-…"> into
    # marked code blocks. Runs after slot fill (so it sees authored code) and
    # before the fetch check (so its spans are held to the offline contract).
    out = highlight(out)
    # #379 — advisories are emitted BEFORE any refusal, so a source with two
    # faults reports both on one run. This used to sit below both `raise`s, which
    # meant an author whose source had a component violation and a short grid row
    # saw the error, fixed it, rebuilt, and only then learned about the dead
    # track. The priority is deliberately unchanged: a refusal still refuses and
    # still writes nothing. What changed is that it no longer discards advice
    # already computed from the same document.
    if warn is not None:
        for message in grid_warnings(out, template):
            warn(message)
    violations = fetch_violations(out)
    if violations:
        raise ArtifactError(
            "output would fetch %d thing(s) — an artifact must be readable "
            "offline:\n  %s" % (len(violations), "\n  ".join(violations)))
    # The component vocabulary (#347-adjacent). Held against the BUILT output
    # rather than the source, so a component the template itself emits is
    # covered too and there is one answer rather than two.
    strays = component_violations(out)
    if strays:
        raise ArtifactError(
            "output misuses %d documented component(s) — the template styles "
            "the documented classes and nothing else, so this renders wrong "
            "with no other symptom:\n  %s" % (len(strays), "\n  ".join(strays)))
    return out


def build_path(source):
    """`review/src/<slug>.html` -> `review/<slug>.html`."""
    directory, name = os.path.split(os.path.abspath(source))
    if os.path.basename(directory) != "src":
        raise ArtifactError(
            "sources live in a `src/` directory beside the artifacts "
            "(watch.py lists every *.html next to them); got %s" % source)
    return os.path.join(os.path.dirname(directory), name)


def build(source, out=None, template=None, warn=None):
    with open(source, encoding="utf-8") as handle:
        fields = parse_source(handle.read())
    document = render(fields, template=template, warn=warn)
    out = out or build_path(source)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(document)
    os.replace(tmp, out)
    return out


# ── the stamp, read back ──────────────────────────────────────────────────

STAMP_RE = re.compile(
    r"""<meta\s+name=["']dreamwork-review-template["']\s+content=["']([^"']+)["']""")


def artifact_stamp(document):
    match = STAMP_RE.search(document)
    return match.group(1) if match else None


def classify(document, template=None):
    """`current` / `stale <stamp>` / `untemplated` — never a silent pass."""
    current = template_stamp(read_template() if template is None else template)
    stamp = artifact_stamp(document)
    if stamp is None:
        return "untemplated"
    return "current" if stamp == current else "stale"


# ── cli ───────────────────────────────────────────────────────────────────


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    make = sub.add_parser("build", help="render source(s) into artifact(s)")
    make.add_argument("source", nargs="+")
    make.add_argument("-o", "--out", help="output path (one source only)")
    look = sub.add_parser("check", help="which template each artifact came from")
    look.add_argument("path", nargs="+")
    sub.add_parser("version", help="print the current template stamp")
    args = parser.parse_args(argv)

    if args.cmd == "version":
        print(template_stamp(read_template()))
        return 0
    if args.cmd == "build":
        if args.out and len(args.source) > 1:
            print("review_artifact: --out takes one source", file=sys.stderr)
            return 1
        for source in args.source:
            def warn(message, source=source):
                print("review_artifact: %s: warning: %s" % (source, message),
                      file=sys.stderr)
            try:
                out = build(source, out=args.out, warn=warn)
            except ArtifactError as error:
                print("review_artifact: %s: %s" % (source, error), file=sys.stderr)
                return 1
            print("%s -> %s (%s)" % (source, out, template_stamp(read_template())))
        return 0

    worst = 0
    for path in args.path:
        try:
            with open(path, encoding="utf-8") as handle:
                document = handle.read()
        except OSError as error:
            print("  ERROR       %s (%s)" % (path, error))
            worst = 1
            continue
        verdict = classify(document)
        print("  %-11s %s%s" % (verdict, path,
                                "" if verdict != "stale"
                                else "  (built from %s)" % artifact_stamp(document)))
        if verdict == "stale":
            worst = 1
    return worst


if __name__ == "__main__":
    sys.exit(main())
