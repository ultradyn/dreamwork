"""#653 — is `client/dist/` built from the tree that is here right now?

The #630 transition's build step emits `client/dist/` from `client/*.js` and
one hand-written file, and COMMITS the result (`just deploy` ships committed
state only, `justfile:418-423`, and the dashboard must come up from a plain
checkout with no node). Committed output has exactly one failure mode:
**staleness** — a bundle compiled from yesterday's builders.

Staleness cannot be made *impossible* without a serve-time build, which the
no-node-at-serve-time requirement refuses. So it is made impossible to MISS:
`build_client.py` records the sha256 of every input and every output, this
module recomputes them, `lint.py` goes ERROR on a mismatch, and
`watch.serving_report` carries the same reading. That is the honest property
and it is the one claimed — not "divergence is impossible".

Stdlib only, and deliberately: `watch.py` imports this, and the server
imports nothing outside the stdlib (ruled 2026-07-30, `watch-design.md:41-51`).

**Every function here RETURNS a reading and never raises.** The state this
module exists to describe is precisely the one where its subjects are absent
or unreadable — a crash there reads like silence and sends whoever debugs it
to the wrong subsystem (lessons.md:580, lessons.md:622).
"""

import ast
import glob
import hashlib
import json
import os

# Where the build writes, relative to the repo root. One spelling, shared by
# the builder, the checker and the tests — a second copy is a second truth.
DIST_DIR = "client/dist"
MANIFEST_REL = DIST_DIR + "/manifest.json"

# The design bundle's one hand-written build input. Named here rather than in
# the manifest's own key set, because "the manifest agrees with itself" is not
# the question: the question is whether it agrees with the TREE.
WRAPPER_EXPORTS_REL = "dev/build/wrapper-exports.js"
DS_SOURCE_DIR = "dev/build/ds-src"
DS_SOURCE_RELS = (
    DS_SOURCE_DIR + "/QaCard.d.ts",
    DS_SOURCE_DIR + "/QaCard.fixture.json",
    DS_SOURCE_DIR + "/QaCard.prompt.md",
)

# #630 P2: the native runtime's sources. A DIRECTORY rather than a tuple of
# names, deliberately — the native runtime will grow a file per converted
# surface from P3 on, and a hand-maintained list beside it is a second truth
# that goes stale on the first addition. `native_sources` globs it, so adding
# a file makes it a build input with no edit here and no edit to the manifest
# schema.
NATIVE_SRC_DIR = "dev/build/src"
NATIVE_ENTRY_REL = NATIVE_SRC_DIR + "/native-entry.js"

# What the build emits.
#   ds/index.js    the design-tool package: `client/*.js` CONCATENATED, so it
#                  carries their top-level side effects (harmless in a tool
#                  that has no dashboard running).
#   ds/styles.css  a byte copy of `client/style.css` — the design package
#                  ships the stylesheet the dashboard serves, not a fork.
#   native.js      the on-page runtime: React + the component registry, with
#                  the builders REFERENCED and never concatenated. The
#                  difference from ds/ is not a detail — see the header of
#                  `dev/build/src/native-entry.js`.
DS_DIR = DIST_DIR + "/ds"
NATIVE_REL = DIST_DIR + "/native.js"
OUTPUT_RELS = (DS_DIR + "/index.js", DS_DIR + "/styles.css", NATIVE_REL)

SCHEMA = 1

# reading states
OK = "ok"
STALE = "stale"
MISSING = "missing"          # no manifest at all — the build has never run
UNREADABLE = "unreadable"    # something the check itself needs is broken


def sha256_file(path):
    """Hex digest, or None when the file cannot be read.

    None is a reading ("I could not hash this"), never an exception: the
    caller's whole job is to report absence, and a raise here would destroy
    the report it exists to make.
    """
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def asset_order(root):
    """`watch._CLIENT_ASSETS`, read out of watch.py by AST — never imported.

    Same trick, and the same reason, as `deploy_state.data_sibling_paths`
    (`dev/deploy_state.py:292-315`): the build must be able to read the page's
    asset order without importing the server, and a computed value would parse
    to nothing — which is loud here (None) rather than silently empty.

    Returns the tuple as a list, or None if watch.py cannot be read or the
    name is not a module-level literal.
    """
    try:
        with open(os.path.join(root, "watch.py"), encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)
    except (OSError, SyntaxError, ValueError):
        return None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "_CLIENT_ASSETS"
                   for t in node.targets):
            continue
        try:
            val = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            return None
        if isinstance(val, (tuple, list)) and all(
                isinstance(p, str) for p in val):
            return list(val)
        return None
    return None


def native_sources(root):
    """`dev/build/src/*.js`, sorted, or None when there are none.

    None rather than `[]`, and that is the vacuity trap closed at the source:
    an empty list would drop the native runtime out of the input set entirely,
    and every hash comparison over the remaining keys would pass while
    `native.js` was built from files that are no longer here — or from nothing
    at all. A directory that has lost its contents is not a build with fewer
    inputs; it is a build whose inputs cannot be read, which is what
    UNREADABLE says.

    Sorted rather than in glob order: `glob` is filesystem-ordered, so the
    manifest's key set would depend on directory layout and a rebuild after an
    unrelated file operation could reorder it. The keys are compared as a SET
    by `check`, but the manifest is a committed artifact and a set that
    serialises differently on two machines is diff churn nobody can read.
    """
    found = sorted(glob.glob(os.path.join(root, NATIVE_SRC_DIR, "*.js")))
    if not found:
        return None
    return [os.path.relpath(p, root).replace(os.sep, "/") for p in found]


def expected_inputs(root):
    """Every file the build reads, or None.

    Derived from the tree, not from the manifest — so a manifest that simply
    forgot an asset is caught. That is the false-green this ordering closes:
    hashing only the paths the manifest names would pass happily on a dist
    built before a ninth asset joined the page.

    The `client/*` assets are inputs to BOTH bundles even though only `ds/`
    concatenates them: `native.js` delegates to those builders by name, so a
    renamed or deleted builder makes the committed `native.js` wrong in the
    way that matters most — it would throw at mount, on the surface it was
    built to render. Hashing them for both is what makes that a commit-time
    red instead of a runtime one.
    """
    order = asset_order(root)
    if order is None:
        return None
    native = native_sources(root)
    if native is None:
        return None
    return (["client/" + name for name in order]
            + [WRAPPER_EXPORTS_REL] + native)


def read_manifest(root):
    """(manifest, note). `manifest` is None when there is nothing usable."""
    path = os.path.join(root, MANIFEST_REL)
    try:
        with open(path, encoding="utf-8") as f:
            obj = json.load(f)
    except FileNotFoundError:
        return None, "no %s — `just build-client` has never run here" % MANIFEST_REL
    except (OSError, ValueError) as exc:
        return None, "%s is unreadable: %s" % (MANIFEST_REL, exc)
    if not isinstance(obj, dict):
        return None, "%s is not an object" % MANIFEST_REL
    return obj, None


def check(root):
    """Is `client/dist/` built from THIS tree?

    Returns ``{"state", "note", "stale", "fix"}``. `stale` names the paths
    that disagree, so the report can say which edit is unbuilt rather than
    only that one is.

    The order of the tests below is the order of the vacuity traps, closed
    outermost first — a hash comparison over an EMPTY key set passes on
    everything, so the key set is checked against the tree before any hash is
    compared at all.
    """
    out = {"state": None, "note": None, "stale": [],
           "fix": "run `just build-client`"}

    want = expected_inputs(root)
    if want is None:
        # WHICH half could not be read, because they fail for unrelated
        # reasons and send the reader to different files. A single note naming
        # only the AST half would point at watch.py for a missing build
        # directory — the wrong-subsystem diagnosis this module's header
        # refuses to make.
        out["state"] = UNREADABLE
        if asset_order(root) is None:
            out["note"] = ("cannot read watch._CLIENT_ASSETS as a "
                           "module-level literal, so the build inputs cannot "
                           "be derived")
        else:
            out["note"] = ("%s holds no .js file — the native runtime has no "
                           "source, so `client/dist/native.js` cannot be "
                           "checked against anything" % NATIVE_SRC_DIR)
        return out

    manifest, note = read_manifest(root)
    if manifest is None:
        out["state"] = MISSING
        out["note"] = note
        return out

    if manifest.get("schema") != SCHEMA:
        out["state"] = UNREADABLE
        out["note"] = ("%s declares schema %r, this checker speaks %d"
                       % (MANIFEST_REL, manifest.get("schema"), SCHEMA))
        return out

    inputs = manifest.get("inputs")
    outputs = manifest.get("outputs")
    if not isinstance(inputs, dict) or not isinstance(outputs, dict):
        out["state"] = UNREADABLE
        out["note"] = "%s has no inputs/outputs maps" % MANIFEST_REL
        return out

    # Vacuity, closed at the source: a manifest with no outputs would make
    # every output comparison below pass by having nothing to compare.
    if not outputs:
        out["state"] = STALE
        out["note"] = ("%s records no outputs — a dist that claims to have "
                       "built nothing" % MANIFEST_REL)
        return out

    # The key set, before any hash. A dist built from a DIFFERENT set of files
    # than the page now loads is stale in the way that matters most, and
    # comparing only the hashes of the paths the manifest happens to name
    # cannot see it.
    if sorted(inputs) != sorted(want):
        extra = sorted(set(inputs) - set(want))
        absent = sorted(set(want) - set(inputs))
        bits = []
        if absent:
            bits.append("built without %s" % ", ".join(absent))
        if extra:
            bits.append("built from %s, which the page no longer loads"
                        % ", ".join(extra))
        out["state"] = STALE
        out["note"] = "; ".join(bits)
        out["stale"] = absent + extra
        return out

    # Order is an input too: the page concatenates the assets in
    # `_CLIENT_ASSETS` order, so a reordering with identical bytes changes what
    # the bundle means while every hash still matches.
    order = asset_order(root)
    if list(manifest.get("asset_order") or []) != order:
        out["state"] = STALE
        out["note"] = ("built for asset order %r, watch.py now loads %r"
                       % (manifest.get("asset_order"), order))
        return out

    stale = []
    for rel, recorded in list(inputs.items()) + list(outputs.items()):
        actual = sha256_file(os.path.join(root, rel))
        if actual is None:
            stale.append("%s (unreadable)" % rel)
        elif actual != recorded:
            stale.append(rel)
    if stale:
        out["state"] = STALE
        out["stale"] = sorted(stale)
        out["note"] = ("client/dist was built from different bytes: %s"
                       % ", ".join(sorted(stale)))
        return out

    out["state"] = OK
    out["note"] = "client/dist matches %d inputs and %d outputs" % (
        len(inputs), len(outputs))
    out["fix"] = None
    return out
