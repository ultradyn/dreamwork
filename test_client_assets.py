"""#397 — the client assets, and the seam that loads them.

The extraction's one claim is that it changed nothing the browser sees: the
page assembled from `client/` is byte-for-byte what the string literals
produced. That was proven once, at the migration, by capturing the page
before and comparing after (sha256 08d4e0bf33cb02cb…, 576217 bytes). A
recorded hash is no use here — every legitimate UI edit changes it — so what
this file pins instead is every way the seam could go wrong AFTERWARDS:

  - the loader could stop being faithful to the file (encoding, newline
    translation, a strip() someone adds for tidiness);
  - STYLE's re-wrap could drift from the shape the extraction asserted;
  - an asset could be dropped from the page assembly and still load fine;
  - DATA_SIBLINGS could fall out of step with the asset list, so `just
    deploy` ships a page missing a file and the dashboard serves blank.

Every check derives its expectations at runtime. A literal tuned to today's
tree is a check with an expiry date nobody can see.
"""

import ast
import importlib.util
import os
import pathlib
import re
import shutil

import watch

ROOT = pathlib.Path(__file__).resolve().parent
CLIENT = ROOT / "client"


def _assets():
    return list(watch._CLIENT_ASSETS)


def _rules(css, want):
    """Declarations of every rule whose selector list satisfies `want`.

    Comments are stripped first — this stylesheet's prose discusses selectors
    and braces, and a scan that reads a comment as a rule finds values nobody
    ships. Selectors are compared whole, so `.taskpreview` never matches
    `#task-ref-preview.taskpreview`; that distinction is the entire point of
    the specificity check below.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        sels = [s.strip() for s in match.group(1).split(",") if s.strip()]
        if any(want(s) for s in sels):
            out.append(match.group(2))
    return out


_COLOUR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\([^)]*\)")


def test_the_task_ref_hover_is_stated_in_tokens_and_outranks_its_injected_block():
    """#1007 — the #282 hover panel must keep matching the site, not merely
    have matched it once.

    Two ways this silently dies, one check each.

    SPECIFICITY. `client/components.js` injects a self-contained `<style>` for
    the panel and appends it to `<head>` AFTER this sheet, so a class-level
    rule here loses the source-order tie and the panel reverts to that block's
    literals with nothing rendering wrong enough to notice. The rules are
    therefore id-qualified, and a bare `.taskpreview` rule in this file would
    be inert — which is worse than absent, because it reads as styling.

    A LITERAL THAT MATCHES TODAY. `#334155` and `var(--border)` render
    identically until the token moves, and then only one of them still matches
    the page. So every colour this lane states must come through a `var()`
    that `:root` actually declares — with the sole exception of a literal the
    surface being matched states ITSELF, which is read back out of that rule
    rather than repeated here.
    """
    css = (CLIENT / "style.css").read_text(encoding="utf-8")
    components = (CLIENT / "components.js").read_text(encoding="utf-8")

    injected = re.search(r"style\.textContent\s*=\s*`(.*?)`;", components, re.S)
    # ...and it must be the rule that STATES the surface: a reduced-motion
    # `.taskpreview{transition:none}` also satisfies "a class-level rule
    # exists" while saying nothing about the appearance being matched.
    assert injected and [b for b in _rules(injected.group(1), lambda s: s == ".taskpreview")
                         if "background" in b], (
        "client/components.js no longer injects a CLASS-specificity "
        "`.taskpreview` rule declaring a background — the id-qualification "
        "below is answering a question nobody asks, and this check cannot "
        "tell you whether the panel still matches the site"
    )

    ours = _rules(css, lambda s: "task-ref-preview" in s or "taskref" in s)
    assert ours, (
        "client/style.css states nothing about the task-ref hover, so the "
        "panel is whatever client/components.js hardcoded (#1007)"
    )
    assert not _rules(css, lambda s: s == ".taskpreview"), (
        "client/style.css declares a bare `.taskpreview` rule — same "
        "specificity as the block components.js appends to <head> after this "
        "sheet, so it loses the source-order tie and styles nothing"
    )

    # The surface being matched, and it must be the rule that STATES the
    # surface: #cmdpalette also appears in a reduced-motion selector list that
    # declares only `transition:none`, and reading that one instead would
    # silently empty the permitted-literal set and blame the hover for it.
    source = [b for b in _rules(css, lambda s: s == "#cmdpalette") if "box-shadow" in b]
    assert source, (
        "no #cmdpalette rule in client/style.css declares a box-shadow — it is "
        "one of the two statements of the floating-overlay idiom the hover was "
        "matched to, so nothing below can be derived from it"
    )
    allowed = set(_COLOUR_LITERAL.findall(" ".join(source)))
    assert allowed, (
        "#cmdpalette states no colour literal, so the permitted set is empty "
        "and the loop below would reject every literal the hover legitimately "
        "shares with it — a refusal about the wrong file"
    )
    declared = set(re.findall(r"(--[a-z0-9-]+)\s*:", " ".join(_rules(css, lambda s: s == ":root"))))
    assert declared, ":root declares no custom property; every var() below would be vacuous"

    for block in ours:
        for literal in _COLOUR_LITERAL.findall(block):
            assert literal in allowed, (
                "the task-ref hover states the colour literal %s, which "
                "#cmdpalette — the surface it is matched to — does not state "
                "either. A literal that happens to match a token today stops "
                "matching the day the token moves (#1007)" % literal
            )
        for name in re.findall(r"var\((--[a-z0-9-]+)", block):
            assert name in declared, (
                "the task-ref hover reads %s, which :root does not declare — "
                "the property resolves to nothing and the panel silently "
                "falls back to the client/components.js literal" % name
            )

    panel = _rules(css, lambda s: s == "#task-ref-preview.taskpreview")
    assert panel, "the task-ref panel rule is no longer id-qualified"
    for prop in ("box-shadow", "border-radius"):
        mine = re.search(prop + r"\s*:\s*([^;}]+)", panel[0])
        theirs = re.search(prop + r"\s*:\s*([^;}]+)", source[0])
        assert mine and theirs and mine.group(1).strip() == theirs.group(1).strip(), (
            "the task-ref hover's %s is %r and #cmdpalette's is %r — the two "
            "floating overlays no longer agree, so the hover has stopped "
            "matching the surface #1007 matched it to" % (
                prop,
                mine.group(1).strip() if mine else None,
                theirs.group(1).strip() if theirs else None,
            )
        )


def test_the_asset_list_is_not_empty_and_every_file_exists():
    """The precondition every other test here leans on."""
    assets = _assets()
    assert len(assets) >= 8, (
        "watch._CLIENT_ASSETS has %d entries — the extraction produced 8, so "
        "something removed assets from the list rather than from the page; "
        "every check below would go vacuous first" % len(assets)
    )
    for name in assets:
        p = CLIENT / name
        assert p.is_file(), "client/%s is missing" % name
        assert p.stat().st_size > 0, (
            "client/%s is empty — the page would assemble around a blank "
            "asset and the content checks below would pass on nothing" % name
        )


def test_each_constant_is_exactly_its_file():
    """The loader is faithful — no translation, no stripping, no re-encode.

    Read as bytes here deliberately: comparing `read_text()` to the constant
    would use the same text-mode path the loader does, so a newline
    translation bug would agree with itself and this would pass over it.
    """
    pairs = {
        "style.css": None,          # wrapped; checked separately below
        "app_body.html": "APP_BODY",
        "components.js": "COMPONENTS_JS",
        "views.js": "VIEWS_JS",
        "favicon.js": "FAVICON_JS",
        "router.js": "ROUTER_JS",
        "command.js": "COMMAND_JS",
        "shader.js": "SHADER_JS",
    }
    checked = 0
    for name, const in pairs.items():
        if const is None:
            continue
        raw = (CLIENT / name).read_bytes().decode("utf-8")
        assert getattr(watch, const) == raw, (
            "watch.%s is not byte-identical to client/%s — the loader is "
            "transforming the asset" % (const, name)
        )
        checked += 1
    assert checked == 7, "expected 7 unwrapped assets, checked %d" % checked


def test_style_rewrap_is_exact_and_the_file_is_real_css():
    """STYLE is the one asset the loader transforms, so pin the transform.

    The file must NOT carry the tags (or style.css is not css and the whole
    point of extracting it is lost), and the constant MUST carry them (or the
    page ships raw css as text).
    """
    raw = (CLIENT / "style.css").read_bytes().decode("utf-8")
    assert "<style>" not in raw and "</style>" not in raw, (
        "client/style.css contains its own <style> tags — the loader adds "
        "them, so the page would get them twice"
    )
    assert watch.STYLE == "<style>" + raw + "</style>", (
        "STYLE is no longer exactly the file inside a <style> wrapper"
    )
    assert watch.STYLE.startswith("<style>")
    assert watch.STYLE.endswith("</style>")


def test_task_provenance_and_group_progress_share_one_split_bar_component():
    """#440/#836: one supported bar implementation, two callers."""
    components = (CLIENT / "components.js").read_text(encoding="utf-8")
    views = (CLIENT / "views.js").read_text(encoding="utf-8")
    assert components.count('function splitBar(') == 1, (
        "client/components.js must define exactly one splitBar component")
    assert views.count("splitBar(") == 2, (
        "client/views.js must route provenance and group progress through "
        "the same splitBar component")
    assert '<div class="provbar' not in views, (
        "client/views.js hand-built a second bar instead of using splitBar")


def test_every_asset_actually_reaches_the_assembled_page():
    """A faithful loader is not enough — the asset must be IN the page.

    Dropping `SHADER_JS` from the page template would leave every check above
    green: the file exists, the constant matches it, and only the browser
    would notice. So assert against the assembled page, and use a distinctive
    slice of each asset rather than its whole body (the page interpolates the
    posture vocab into the middle of the JS).
    """
    page = watch._get_page()
    assert len(page) > 100_000, (
        "the assembled page is %d chars — too small to be the dashboard; "
        "the containment checks below would be meaningless" % len(page)
    )
    for name in _assets():
        raw = (CLIENT / name).read_bytes().decode("utf-8")
        # a mid-file slice: avoids leading/trailing whitespace and any
        # wrapper the loader adds at the edges
        mid = len(raw) // 2
        probe = raw[mid:mid + 200]
        assert probe.strip(), "client/%s has no usable probe slice" % name
        assert probe in page, (
            "content from client/%s is not in the assembled page — the "
            "asset loads but is never concatenated into it" % name
        )


def test_data_siblings_ships_every_client_asset():
    """`just deploy` ships DATA_SIBLINGS; a gap here deploys a blank page.

    deploy_state.py reads DATA_SIBLINGS with ast.literal_eval, so it cannot
    be computed from _CLIENT_ASSETS — which means the two can drift. This is
    the check that stops that, and it reads the literal the same way deploy
    does rather than importing the value, so a computed tuple (invisible to
    deploy) fails here too.
    """
    src = (ROOT / "watch.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    declared = None
    for node in tree.body:
        if (isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "DATA_SIBLINGS"):
            declared = ast.literal_eval(node.value)
    assert declared is not None, (
        "DATA_SIBLINGS is not a module-level literal ast.literal_eval can "
        "read — dev/deploy_state.py would find nothing and deploy would ship "
        "no client assets at all"
    )
    assets = _assets()
    assert assets, (
        "_assets() returned %r; examined 0 client assets, so this deploy "
        "check would pass without checking anything" % (assets,)
    )
    want = {"client/" + n for n in assets}
    missing = sorted(want - set(declared))
    assert not missing, (
        "DATA_SIBLINGS does not declare %r — `just deploy` would not ship "
        "them and the deployed dashboard would serve a broken page" % missing
    )


def test_morphdom_loader_reads_the_vendored_reconciler():
    """A different valid script must not masquerade as morphdom."""
    expected = (ROOT / "vendor/morphdom.min.js").read_text(encoding="utf-8")
    assert expected, "vendor/morphdom.min.js is empty; examined 0 bytes"
    assert watch._load_morphdom_js() == expected, (
        "_load_morphdom_js did not read vendor/morphdom.min.js; valid but "
        "unrelated JavaScript would parse while leaving morphdom undefined"
    )


def test_client_dir_resolves_beside_the_link_not_through_it(tmp_path):
    """#425: watch.py becomes a symlink to deprecated/watch.py.

    `abspath` keeps the LINK's own directory (the repo root, where client/
    lives); `realpath` would resolve into deprecated/ and the assets would
    vanish. This is the load-bearing choice of the whole extraction, so it is
    checked under the layout that makes it load-bearing.

    An earlier version of this test asserted `CLIENT_DIR == dirname(abspath(
    watch.__file__)) + "/client"`, which restated the implementation and — on
    today's tree, where watch.py is a regular file — could not fail: abspath
    and realpath agree until a symlink exists, so swapping the production call
    to `realpath` left it GREEN. So build #425's layout for real: the module
    under deprecated/, a symlink at the root, the assets beside the LINK.

    Production line: `CLIENT_DIR`'s `os.path.abspath(__file__)` in watch.py.
    Change it to `realpath` and the import below raises FileNotFoundError.
    """
    root = tmp_path / "root"
    (root / "deprecated").mkdir(parents=True)
    shutil.copy(watch.__file__, root / "deprecated" / "watch.py")
    # Every sibling watch.py resolves relative to itself, taken from
    # DATA_SIBLINGS rather than listed here — vendor/morphdom.min.js is also
    # read at import, and a future addition must not turn this test red for
    # the wrong reason.
    for rel in watch.DATA_SIBLINGS:
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, dst)
    link = root / "watch.py"
    link.symlink_to(pathlib.Path("deprecated") / "watch.py")

    # Preconditions: the layout must really be #425's, or this proves nothing.
    assert link.is_symlink(), "fixture did not create a symlink"
    assert os.path.realpath(link) != str(link), "symlink does not redirect"
    assert not (root / "deprecated" / "client").exists(), (
        "fixture put client/ where realpath would ALSO find it — the two "
        "spellings would agree and the test could not fail"
    )

    spec = importlib.util.spec_from_file_location("watch_via_link", str(link))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # raises if CLIENT_DIR resolved wrong

    assert mod.CLIENT_DIR == str(root / "client"), (
        "CLIENT_DIR resolved to %r, not beside the link at %r — #425 would "
        "deploy a dashboard with no css or js" % (mod.CLIENT_DIR, root / "client")
    )
    # and it genuinely loaded through that path, rather than resolving to a
    # plausible directory nobody read
    assert mod.STYLE == watch.STYLE and mod.ROUTER_JS == watch.ROUTER_JS


def test_autoreload_watches_the_assets_not_just_watch_py():
    """Editing client/style.css must re-exec `--autoreload`, or a design
    lane edits css and sees nothing until a manual restart."""
    watched = set(watch._autoreload_sources())
    for name in _assets():
        assert os.path.join(watch.CLIENT_DIR, name) in watched, (
            "client/%s is not in the autoreload watch set" % name
        )
    assert os.path.abspath(watch.__file__) in watched, (
        "watch.py itself dropped out of the autoreload watch set"
    )
    # every entry is absolute: a relative path here survives until someone
    # chdirs, and _sources_mtime's OSError handling would then hide the fact
    # that watch.py had stopped being watched at all
    assert all(os.path.isabs(p) for p in watched), (
        "relative paths in the autoreload watch set: %r"
        % sorted(p for p in watched if not os.path.isabs(p))
    )


def test_a_vanished_source_pauses_autoreload_instead_of_re_execing(tmp_path):
    """The rename window, which the previous mitigation documented but did
    not implement.

    An editor saving `client/style.css` via rename unlinks it for an instant.
    Re-execing then imports a file that is not there — FileNotFoundError, dev
    server dead, no supervisor to bring it back. `_sources_mtime` must return
    None (meaning "do not judge this tick") rather than a value the caller
    will compare.

    The old version took `max()` over whatever it could read, which DROPS
    when the absent file is the newest — and the absent file is the one being
    edited, so it dropped in exactly the window it was written for. Production
    line: the `return None` in `_sources_mtime`'s except branch. Restore
    `continue` + `max(stamps)` and this goes red.
    """
    real = watch._autoreload_sources()
    assert len(real) > 1, "watch set has nothing to lose"

    gone = os.path.join(str(tmp_path), "vanished-during-rename.css")
    assert not os.path.exists(gone)

    # Precondition: the vanished file must be the NEWEST of the set, or max()
    # would not have dropped and the old code would have passed this too.
    baseline = watch._sources_mtime()
    assert baseline is not None, "watch set unreadable before the injection"
    newest = max(baseline.values())

    watched = real + [gone]
    saved = watch._autoreload_sources
    watch._autoreload_sources = lambda: watched
    try:
        os.utime(real[0], (newest + 100, newest + 100))
        assert watch._sources_mtime() is None, (
            "a watched path that is currently absent did not pause the "
            "watcher — --autoreload would re-exec into a missing asset"
        )
    finally:
        watch._autoreload_sources = saved
        os.utime(real[0], (newest, newest))


def test_an_empty_asset_is_refused_rather_than_served_silently(tmp_path):
    """A mangled client used to be a mangled watch.py, which would not parse.

    Read from a file it is silent instead: an empty style.css assembles to
    `<style></style>`, the page still returns 200, and the dashboard comes up
    unstyled with nothing saying why. `--assert-importable` cannot catch it
    either — the module imports fine. Production line: the `if not raw: raise`
    in `_read_client`.
    """
    (tmp_path / "style.css").write_bytes(b"")
    saved = watch.CLIENT_DIR
    watch.CLIENT_DIR = str(tmp_path)
    try:
        # precondition: the file exists and is readable, so this is the EMPTY
        # case and not the already-loud missing/unreadable one
        assert (tmp_path / "style.css").is_file()
        assert (tmp_path / "style.css").stat().st_size == 0
        try:
            watch._read_client("style.css")
        except OSError as exc:
            assert "style.css" in str(exc), (
                "the refusal does not name the file: %s" % exc
            )
        else:
            raise AssertionError(
                "an empty client asset loaded without complaint — the page "
                "would serve broken with HTTP 200"
            )
    finally:
        watch.CLIENT_DIR = saved
