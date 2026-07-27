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


# ── the build ─────────────────────────────────────────────────────────────


def render(fields, template=None):
    """Fill the template. Raises rather than writing anything questionable."""
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
    violations = fetch_violations(out)
    if violations:
        raise ArtifactError(
            "output would fetch %d thing(s) — an artifact must be readable "
            "offline:\n  %s" % (len(violations), "\n  ".join(violations)))
    return out


def build_path(source):
    """`review/src/<slug>.html` -> `review/<slug>.html`."""
    directory, name = os.path.split(os.path.abspath(source))
    if os.path.basename(directory) != "src":
        raise ArtifactError(
            "sources live in a `src/` directory beside the artifacts "
            "(watch.py lists every *.html next to them); got %s" % source)
    return os.path.join(os.path.dirname(directory), name)


def build(source, out=None, template=None):
    with open(source, encoding="utf-8") as handle:
        fields = parse_source(handle.read())
    document = render(fields, template=template)
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
            try:
                out = build(source, out=args.out)
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
