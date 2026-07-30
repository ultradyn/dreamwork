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
import os
import pathlib

import watch

ROOT = pathlib.Path(__file__).resolve().parent
CLIENT = ROOT / "client"


def _assets():
    return list(watch._CLIENT_ASSETS)


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
    want = {"client/" + n for n in _assets()}
    missing = sorted(want - set(declared))
    assert not missing, (
        "DATA_SIBLINGS does not declare %r — `just deploy` would not ship "
        "them and the deployed dashboard would serve a broken page" % missing
    )
    # the vendored reconciler must stay first: _load_morphdom_js indexes [0]
    assert declared[0] == "vendor/morphdom.min.js", (
        "DATA_SIBLINGS[0] is %r, but _load_morphdom_js reads index 0"
        % (declared[0],)
    )


def test_client_dir_resolves_beside_the_link_not_through_it():
    """#425: watch.py becomes a symlink to deprecated/watch.py.

    `abspath` keeps the link's own directory (the repo root, where client/
    lives); `realpath` would resolve into deprecated/ and the assets would
    vanish. Pin the property rather than the spelling.
    """
    assert watch.CLIENT_DIR == os.path.join(
        os.path.dirname(os.path.abspath(watch.__file__)), "client")
    assert os.path.isdir(watch.CLIENT_DIR)


def test_autoreload_watches_the_assets_not_just_watch_py():
    """Editing client/style.css must re-exec `--autoreload`, or a design
    lane edits css and sees nothing until a manual restart."""
    watched = set(watch._autoreload_sources())
    for name in _assets():
        assert os.path.join(watch.CLIENT_DIR, name) in watched, (
            "client/%s is not in the autoreload watch set" % name
        )
    assert watch.__file__ in watched or os.path.abspath(
        watch.__file__) in {os.path.abspath(p) for p in watched}, (
        "watch.py itself dropped out of the autoreload watch set"
    )
