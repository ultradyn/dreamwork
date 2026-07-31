#!/usr/bin/env python3
"""#314 — the styleguide audit, re-grounded on the DIFF not the filename.

THE PROBLEM (the evidence for #314)
  `audit-styleguide` was RED half a day after #313 scoped it to a green
  baseline, and not because anyone got sloppy. The recipe asked "did this
  commit touch watch.py?" and demanded a watch-design.md / file-formats.md
  entry nearby. But watch.py is one file holding the HTTP server, the git
  and ledger parsers, AND the whole UI (#124 is the split). So the filter
  could not tell a stylesheet change from a regex fix, and it accrued
  failures for work it was never about until "ignore me" was the only
  lesson a standing MISS could teach (#203's family — a check that reddens
  for the wrong reason trains everyone to overlook the right one).

  Verified by reading each commit's DIFF, not its file list:
    NOT real misses (parser / server / git framing):
      06eacad  parse_ledger combined-mention        (lines ~6270-6401)
      1d089ad  ledger section anchoring             (parser regexes)
      db1a1bc  git history NUL framing              (server)
      e51da7e  quieting expected peer disconnects   (server)
    REAL misses (genuine UI changes):
      a6e98cc  review-dock a11y label + 44px send floor  (STYLE + JS consts)
      bfa561f  title count                                (FAVICON_JS region)
      cdb89df  /answers per-route tint + turbulence seed  (ROUTER_JS)

THE FIX — filter on the DIFF, not the filename
  watch.py's UI lives in line-bounded module constants: the triple-quoted
  strings whose contents are served verbatim to the browser as HTML/CSS/JS.
  Everything else in the file is server, parser, or helper. So "did this
  commit change presentation?" IS mechanically answerable: does the commit's
  diff touch a line inside one of those constants? UI_CONSTANTS names them;
  the eight are the complete set of module-level triple-quoted strings in
  watch.py today (STYLE, APP_BODY, COMPONENTS_JS, VIEWS_JS, FAVICON_JS,
  ROUTER_JS, COMMAND_JS, SHADER_JS).

  CRITICAL: the constants' boundaries are resolved AT THE COMMIT BEING
  AUDITED, never at HEAD. Line numbers move; `git show <sha>:watch.py` is
  that commit's own file, and the diff's new-side hunks live in the same
  coordinate system as that file. A check that judges last week's commit
  with today's line numbers is the "literal with an expiry date" trap this
  repo keeps paying for (CLAUDE.md / .dreamwork/lessons.md). ast parses the
  string literal's [lineno, end_lineno] authoritatively — including the case
  where the closing triple-quote shares a line with content (STYLE ends with
  `</style>` then the triple-quote, on one line), which a naive scan for a
  lone triple-quote line gets wrong.

WHY NOT THE OTHER TWO OPTIONS (so this is not re-litigated)
  - Split watch.py (#124): the real cure, a large separate task. Not here.
  - A blanket `Styleguide: n/a` trailer as the primary mechanism: rejected
    (#203 established that "ask for more care" is not a fix when three
    consecutive agents already believed they were being careful). It is kept
    ONLY as a narrow escape hatch for a genuine judgement case the diff filter
    calls wrong — never how an ordinary non-UI commit passes (a non-UI commit
    passes by not touching a UI constant).

#320 — WHAT THE WINDOW COUNTS, and what may vouch for a change
  #314's diff filter fixed WHICH commits are asked the question; it left the
  adjacency window counting raw commits, which measures this repo's commit
  RATE rather than documentation adjacency. The coordinator lands a ledger
  update between every increment, so `cdb89df` and the commit documenting it
  sat SIX purely-bookkeeping commits apart — genuinely adjacent, reported as
  undocumented. So the window's UNIT is now relevant commits (touching
  watch.py or a styleguide file); see window_positions.

  That change ALONE is a monotone weakening — a strict superset of the old
  search — and applied by itself it took the pre-baseline from 11 misses to
  4, silencing `a6e98cc` and `bfa561f` above. It therefore ships with a
  RESTRICTING companion rule (nearest_entry): the search may not reach past
  another UI commit, and a neighbouring UI commit never supplies the entry
  even when it carries a styleguide file, because that entry is its own.
  Only the two real shapes pass — same commit, or a nearby docs-only commit.

  The two rules are checked against each other, not just asserted: each is
  reintroduced as a bug in test_styleguide_audit.py's red proofs. The first
  version of those tests built the relevant-commit list itself and stayed
  green when the unit was reverted — a check outside the decision it named.

#321 — CLOSING A MISS AFTER ITS WINDOW SHUTS
  Adjacency has no path from red to green once the window closes: a miss is
  permanent, and the only remedies are the two this check exists to prevent
  (back-fill a doc entry, or advance the baseline again — #313 did that and
  reddened in half a day). Three visits to that wall was the evidence.

  `cdb89df` was the case, and it was documented all along: `watch-design.md`
  names #302 explicitly in its per-route-tables contract line. That entry
  lives in `34131c7`, itself a UI commit, and #320's blocker rule makes a UI
  commit's entry its own — right in general, wrong for an entry documenting
  TWO changes. Rather than weaken the blocker, the audit now reads a second,
  stronger signal (documented_by_id): a styleguide entry that NAMES a task id
  documents that task's commits, at any distance.

  It falls out of a convention the repo already keeps — every subject is
  `type(#id): …` — so it needs no new file, no new trailer, and nothing
  remembered at commit time, which is what killed the hatch as a general
  remedy. Credits are reported LOUDLY (a DOC-BY-ID line, as EXEMPT is) so the
  softer signal stays visible and countable, never a silent pass.

  It is a stronger claim than adjacency and it was measured for hollowness
  rather than argued: over the pre-baseline it credits 7 commits and leaves 4
  MISSES standing, including `a6e98cc` (#273) and `bfa561f` (#181) — the two
  verified BY READING as genuinely undocumented. Its four #290 credits are one
  feature documented once in `2f0e7ea`, which added 86 lines and a whole
  run-mode section. That is the shape it exists for.

WHAT IT PROVES — and still does not
  Mostly adjacency, not coverage: a styleguide entry NEAR the code documents
  it, but the check cannot tell whether the doc describes the change. A
  whitespace edit to watch-design.md still satisfies that half. The DOC-BY-ID
  half is genuinely coverage — the doc names the task — but it cannot tell a
  substantive entry from a passing mention of the number. Both residuals are
  accepted and stated (the first was true before #314 too); the
  prompt-to-look intent (#155) survives, which is why nothing here is silent.

NOT GATED in `just test` — making adjacency mandatory was always worse than
  the status quo. This is a prompt to look, not a proof. Run it by hand:
  `just audit-styleguide`, or over a wider range: `just audit-styleguide d1df255..HEAD`.
"""

import argparse
import ast
import re
import subprocess
import sys

# The UI-bearing module constants of watch.py: the complete set of
# module-level triple-quoted strings, served verbatim to the browser as
# HTML/CSS/JS. Renamed or added constants should be reflected here; the test
# suite asserts this set against watch.py at HEAD so a drift is loud, not
# silent. Resolved per-commit (see ui_ranges), so a name absent from an old
# revision is simply skipped.
UI_CONSTANTS = (
    "STYLE",
    "APP_BODY",
    "COMPONENTS_JS",
    "VIEWS_JS",
    "FAVICON_JS",
    "ROUTER_JS",
    "COMMAND_JS",
    "SHADER_JS",
)

# #397: since the extraction those constants are LOADED from files rather
# than declared as literals, so a UI change is a diff to `client/` and no
# longer a diff inside watch.py. Both shapes must keep working, because this
# audit walks history ACROSS the extraction commit: revisions before it are
# classified by `ui_ranges` over watch.py, revisions after it by this prefix.
# Dropping the old path would silently reclassify every historical UI commit
# as non-UI and turn the audit green for the wrong reason.
CLIENT_PREFIX = "client/"

# #653: `client/dist/` sits under that prefix but is BUILD OUTPUT — generated
# by `just build-client` from the assets above and committed because deploy
# ships committed state. It carries no presentation decision: whatever design
# choice it embodies was made in the source it was compiled from, and that
# source is already classified by the prefix. Counting it would demand a
# styleguide entry for a file nobody authored — and since a rebuild rides
# along with every UI commit, the entry would be demanded for the derived copy
# of a change that is already documented through its real input.
DERIVED_PREFIX = "client/dist/"

assert DERIVED_PREFIX.startswith(CLIENT_PREFIX), (
    "DERIVED_PREFIX must be a subtree of CLIENT_PREFIX, or excluding it "
    "excludes nothing and this exclusion is silently inert"
)


def is_ui_asset(path):
    """Is `path` a hand-authored client asset — i.e. presentation SOURCE?

    One predicate, three call sites (`classify_ui`, `touches_ui_source`,
    `is_relevant`). They had three copies of the same `startswith` test, and
    an exclusion applied to two of three would have classified a commit as
    non-UI while still counting it as a window unit — a disagreement with no
    symptom until an audit came out wrong.
    """
    return path.startswith(CLIENT_PREFIX) and not path.startswith(DERIVED_PREFIX)

# The assets the extraction produced, one per former constant. Used only to
# refuse a vacuous filter at HEAD (see main) — the classification itself is
# prefix-based so a NEW client file is covered the day it is added, without
# an edit here.
CLIENT_ASSETS = (
    "client/style.css",
    "client/app_body.html",
    "client/components.js",
    "client/views.js",
    "client/favicon.js",
    "client/router.js",
    "client/command.js",
    "client/shader.js",
)

# Tie the two together. The vacuous-filter guard in main() tests these literal
# paths against the git tree, while every classification goes through
# CLIENT_PREFIX — so a typo in the PREFIX alone ("clients/") would classify
# every commit non-UI while the guard still found all eight assets and passed.
# That is precisely the hollow mode the guard claims to prevent, so state the
# dependency instead of assuming it.
assert all(a.startswith(CLIENT_PREFIX) for a in CLIENT_ASSETS), (
    f"CLIENT_ASSETS must all live under CLIENT_PREFIX={CLIENT_PREFIX!r}; "
    f"the vacuous-filter guard is meaningless otherwise"
)

STYLEGUIDE_FILES = ("watch-design.md", "file-formats.md")

# Baseline anchors, retained from #313 for continuity. The DEFAULT RANGE is
# BASELINE_ANCHOR..HEAD: everything after the last historical miss is audited,
# the pre-baseline burst (BASELINE_LOW..BASELINE_ANCHOR) is reported as a count
# only and is NOT back-filled — reconstructing entries after the fact is the
# fabrication this check exists to prevent. These are SHAs, not round numbers,
# derived from history (d1df255 = where watch-design.md became authoritative;
# 1d089ad = the last miss under #313's scoping). Under #314's diff filter the
# pre-baseline count is recomputed and will differ from #313's "11" — that is
# honest, not a regression: parser/server false positives drop out, real UI
# misses remain.
BASELINE_LOW = "d1df255"
BASELINE_ANCHOR = "1d089ad"

# `Styleguide: n/a` — the narrow escape hatch. A UI commit that the diff filter
# flags but a human judges not to need an entry may carry this trailer instead.
# It is reported loudly (EXEMPT line) so the hatch stays auditable, and it is
# never how an ordinary non-UI commit passes.
HATCH_RE = re.compile(r"^Styleguide:\s*n/a\s*$", re.IGNORECASE | re.MULTILINE)

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def git(*args, check=True):
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=check
    )


def commit_list(revrange):
    out = git("log", "--format=%H%x00%h", revrange, check=False).stdout
    pairs = []
    for line in out.splitlines():
        if not line:
            continue
        full, short = line.split("\x00", 1)
        pairs.append((full, short))
    return pairs


def touched_files(sha):
    out = git("show", "--stat", "--format=", "--name-only", sha, check=False).stdout
    return frozenset(line for line in out.splitlines() if line.strip())


def commit_subject(sha):
    return git("log", "-1", "--format=%s", sha).stdout.strip()


def commit_body(sha):
    return git("log", "-1", "--format=%B", sha).stdout


def has_escape_hatch(sha):
    return bool(HATCH_RE.search(commit_body(sha)))


def watchpy_source_at(sha):
    r = git("show", f"{sha}:watch.py", check=False)
    return r.stdout if r.returncode == 0 and r.stdout else None


def ui_ranges(src):
    """[(name, start, end)] for each UI constant present in this watch.py src.

    start/end are 1-based, inclusive, spanning the triple-quoted string literal
    (the closing line included, even when the triple-quote shares it with
    content). ast is the authority; a text scan is the fallback if a historical revision does not
    parse (committed watch.py does, but the audit walks history).
    """
    ranges = []
    try:
        tree = ast.parse(src)
        for node in tree.body:
            if not (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in UI_CONSTANTS
            ):
                continue
            val = node.value
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                ranges.append((node.targets[0].id, val.lineno, val.end_lineno))
        if ranges:
            return ranges
    except SyntaxError:
        pass
    # Text fallback: open on `^NAME = """`, close on the next line holding `"""`.
    # The UI constants' contents (CSS/JS/HTML) do not contain `"""`, so the next
    # occurrence after the open is the close. Robust to `</style>"""` closings.
    lines = src.splitlines()
    for name in UI_CONSTANTS:
        start = None
        for i, line in enumerate(lines, 1):
            if re.match(rf"^{re.escape(name)}\s*=\s*\"\"\"", line):
                start = i
                break
        if start is None:
            continue
        end = None
        for j in range(start + 1, len(lines) + 1):
            if '"""' in lines[j - 1]:
                end = j
                break
        if end is not None:
            ranges.append((name, start, end))
    return ranges


def diff_new_spans(sha):
    """New-image line spans [start, end] (1-based, inclusive) touched by this
    commit's watch.py diff, measured in <sha>'s own watch.py (the post-image).
    Diffed against the first parent; the root commit (no parent) and commits
    that did not touch watch.py yield no spans. Merges diff against first
    parent — the UI work they bring in was classified in the branch commits.
    """
    if git("rev-parse", "--verify", f"{sha}^", check=False).returncode != 0:
        return []
    r = git("diff", f"{sha}^", sha, "--", "watch.py", check=False)
    spans = []
    for line in r.stdout.splitlines():
        m = HUNK_RE.match(line)
        if not m:
            continue
        start = int(m.group(1))
        length = int(m.group(2)) if m.group(2) is not None else 1
        if length > 0:
            spans.append((start, start + length - 1))
    return spans


def touched_constants(spans, ranges):
    """Names of UI constants whose [start,end] overlaps any new-image span.

    Pure on purpose so the test suite can pin it without git: a commit changes
    presentation iff a diff hunk lands inside a UI constant. `spans` are the
    diff's post-image line spans [(s,e)], `ranges` are [(name,start,end)] from
    ui_ranges (same coordinate system — both describe <sha>'s own watch.py).
    """
    touched = []
    for (s, e) in spans:
        for (name, rs, re_) in ranges:
            if s <= re_ and e >= rs and name not in touched:
                touched.append(name)
    return touched


def classify_ui(sha):
    """(is_ui, [touched constant/asset names]) for one commit, at <sha>.

    Two shapes, because the client moved out of watch.py at #397 and this
    audit walks history on both sides of that commit:

    - POST-extraction: the commit touches any file under `client/`. That IS
      the presentation change; nothing in watch.py needs to move with it.
    - PRE-extraction: its diff's new-image spans overlap a UI constant's
      range in <sha>'s own watch.py. Pure deletions still overlap via their
      surrounding context lines, so removing UI counts as touching UI.

    A commit may be both — the two name lists simply merge. In practice only
    a commit that adds `client/` files while its own watch.py still holds the
    constants can be, and the extraction commit is NOT one: at its own rev
    the literals are already gone, so `ui_ranges` finds nothing and only the
    eight `client/` names come back.
    """
    touched = [f for f in sorted(touched_files(sha)) if is_ui_asset(f)]
    src = watchpy_source_at(sha)
    if src is not None:
        ranges = ui_ranges(src)
        spans = diff_new_spans(sha)
        if ranges and spans:
            touched += touched_constants(spans, ranges)
    return bool(touched), touched


def touches_ui_source(files):
    """Could this commit have changed presentation — i.e. is classify_ui
    worth asking about it at all?

    Post-#397 that is watch.py OR any `client/` asset, and the `or` is the
    whole point: a normal UI commit after the extraction touches ONLY
    `client/`. Gating on watch.py alone made classify_ui's client/ branch
    unreachable for exactly the commits it was written for, and the audit
    counted them `untouched` — permanently green over the shape the
    extraction created.

    Narrower than is_relevant on purpose: that one also admits a
    styleguide-only commit, which belongs in the window unit but must not be
    handed to classify_ui as a UI candidate.
    """
    return "watch.py" in files or any(is_ui_asset(f) for f in files)


def is_relevant(files):
    """Could this commit participate in the audit's question at all?

    True iff it touches watch.py, a `client/` asset, or a styleguide file.
    Everything else — a ledger update, a merge, a fix to `reaper.py` — is
    invisible to the question "was this UI change documented?", and it is the
    UNIT the window is counted in (see window_positions).

    `client/` joined this set at #397: a post-extraction UI commit need not
    touch watch.py at all, and leaving it out would drop those commits from
    the window entirely — the entry could then sit arbitrarily far away and
    still read as adjacent.
    """
    return ("watch.py" in files
            or any(is_ui_asset(f) for f in files)
            or bool(files & frozenset(STYLEGUIDE_FILES)))


def window_positions(commits, files_of):
    """Index -> position among the RELEVANT commits, plus that ordered list.

    The window is +-N *relevant* commits, not +-N commits, and that
    distinction is the whole of #320. Counted over all commits it measures
    the repo's commit RATE, not documentation adjacency: this repo's
    coordinator commits a ledger update between every increment, so a UI
    change and the styleguide entry that documents it are routinely six
    ledger/merge commits apart while being genuinely adjacent in the only
    sense the audit cares about. `cdb89df` (#302's per-route tint) and
    `34131c7` (which documents it) had SIX commits between them, NONE of
    which touched watch.py or any styleguide file — an unbroken run of
    bookkeeping. Under an all-commits window that reads as undocumented;
    under this one, the entry is the very next relevant commit.

    Skipping bookkeeping is NOT sufficient on its own, and this was measured,
    not reasoned: the relevant-only window is a strict superset of the
    all-commits window, so misses can only ever FALL — monotone weakening,
    the same move #313 made. Applied alone it took the pre-baseline from 7
    misses to 0, silencing `a6e98cc` and `bfa561f`, both verified BY READING
    as genuine undocumented UI changes. A filter that cannot fail on the
    cases it was built from is hollow however good its rationale sounds.

    So the window carries a second, RESTRICTING rule that the old one lacked
    (see nearest_entry): it may not cross another UI commit. An entry cannot
    document this change if a different UI change sits between them claiming
    it. That is what keeps a burst of UI work from stretching one stray
    styleguide touch across all of it, and it is why this is not merely a
    wider window: it newly catches cases the all-commits window passed.
    """
    rel = [i for i, (full, _) in enumerate(commits) if is_relevant(files_of(full))]
    return {i: p for p, i in enumerate(rel)}, rel


TASK_ID_RE = re.compile(r"#(\d+)")


def styleguide_added_text(sha):
    """The lines a commit ADDS to a styleguide file, as one string.

    Added only — a removed or context line is not this commit documenting
    anything. Restricted to the styleguide files so a task id mentioned in
    `watch.py`'s own comments cannot vouch for the code beside it.
    """
    out = git("show", "--format=", "-U0", sha, "--", *STYLEGUIDE_FILES,
              check=False).stdout
    return added_lines(out)


def added_lines(diff_text):
    """The `+` lines of a diff, minus the `+++` file header.

    Separate and pure so the "added only" rule is checkable without git. The
    `+++` exclusion is load-bearing rather than cosmetic: that header carries
    the FILE PATH, and this repo's styleguide paths do not contain a `#`, but
    a diff header for a renamed or oddly-named file could — and then the
    header itself would vouch for a task nobody documented.
    """
    return "\n".join(
        ln for ln in diff_text.splitlines()
        if ln.startswith("+") and not ln.startswith("+++")
    )


def documented_by_id(sha, commits, files_of):
    """(short sha, id) of a commit whose styleguide entry NAMES sha's task.

    The one place this audit can offer coverage rather than adjacency, and it
    falls out of a convention the repo already keeps: every commit subject is
    `type(#id): …`, and a styleguide entry that discusses task #N says "#N".
    So when `watch-design.md` gains a line naming #302, that line documents
    #302's commits — the doc states what it covers, and nobody has to be
    near anything.

    This exists because adjacency alone has no way to close a miss after its
    window shuts (#321): `cdb89df` (`fix(#302)`) is documented by `34131c7`,
    whose added styleguide lines name #302 — but `34131c7` is itself a UI
    commit, and #320's blocker rule correctly makes a UI commit's entry its
    own. That rule has no exception for an entry documenting TWO changes,
    which is what this reads instead of weakening it.

    Deliberately NOT distance-bounded: the evidence is the doc naming the
    task, and a window would only add a way for real evidence to expire.
    Bounded by the audited range, which is the natural limit.
    """
    ids = TASK_ID_RE.findall(commit_subject(sha))
    if not ids:
        return None
    for full, short in commits:
        if not (files_of(full) & frozenset(STYLEGUIDE_FILES)):
            continue
        added = styleguide_added_text(full)
        for i in ids:
            if f"#{i}" in added:
                return short, i
    return None


def nearest_entry(p, rel, window, has_entry, is_ui_at):
    """Short sha of the styleguide entry creditable to relevant-position ``p``.

    Two rules, and the second is the one that keeps this honest:

    1. Search at most ``window`` relevant commits either side (bookkeeping
       already excluded — see window_positions).
    2. **Stop a direction the moment it reaches another UI commit.** That
       commit's own claim on any further entry comes first, so an entry
       beyond it cannot be credited here.

    Only ``p`` itself, or a NON-UI neighbour, can supply the entry. A
    neighbouring UI commit always blocks, even when it carries a styleguide
    file — because that entry is its OWN. Getting this backwards (checking
    entry before blocker for neighbours too) is what let `a6e98cc` be
    credited to `f17f307`, a UI commit documenting its own #250/#251 work;
    the two changes have nothing to do with each other. So the only shapes
    that pass are the two real ones: document it in the same commit, or in a
    nearby docs-only commit.

    Rule 2 is what distinguishes this from a widened window. In a burst of UI
    work, rule 1 alone lets one stray styleguide touch vouch for every commit
    around it; with rule 2 a run of undocumented UI commits blocks itself and
    each one stays a MISS. Verified: without it the pre-baseline reports 0
    misses, with it 7.
    """
    if has_entry(rel[p]):
        return True, p
    for step in (-1, 1):
        for k in range(1, window + 1):
            q = p + step * k
            if q < 0 or q >= len(rel):
                break
            if is_ui_at(rel[q]):
                break  # its entry, if any, is its own; do not reach past it
            if has_entry(rel[q]):
                return True, q
    return False, None


def classify_range(revrange, window):
    """Classify every commit in revrange. Returns a structured result.

    A watch.py commit is one whose file list includes watch.py. Among those:
      - non-UI  : diff touches no UI constant (server/parser/helper). Passes.
      - UI ok   : a styleguide entry is creditable to it (nearest_entry).
      - UI exempt: no styleguide entry, but carries `Styleguide: n/a`. Passes.
      - UI miss : UI change, no entry, no hatch. FAILS the audit.
    The styleguide-window search is bounded by the range's own commit list, so
    a UI commit whose entry sits just outside the range can be a false miss at
    the boundary — same limitation the pre-#314 recipe had; pass a wider range.
    """
    commits = commit_list(revrange)
    cache, ui_cache = {}, {}

    def files_of(full):
        if full not in cache:
            cache[full] = touched_files(full)
        return cache[full]

    def ui_of(full):
        """(is_ui, consts), memoised — nearest_entry asks about neighbours."""
        if full not in ui_cache:
            if not touches_ui_source(files_of(full)):
                ui_cache[full] = (False, [])
            else:
                ui_cache[full] = classify_ui(full)
        return ui_cache[full]

    def has_entry(i):
        return bool(files_of(commits[i][0]) & frozenset(STYLEGUIDE_FILES))

    def is_ui_at(i):
        return ui_of(commits[i][0])[0]

    pos_of, rel = window_positions(commits, files_of)
    ui_ok, ui_by_id, ui_exempt, ui_miss = [], [], [], []
    non_ui, untouched = 0, 0
    for i, (full, short) in enumerate(commits):
        files = files_of(full)
        if not touches_ui_source(files):
            untouched += 1
            continue
        is_ui, consts = ui_of(full)
        if not is_ui:
            non_ui += 1
            continue
        found, q = nearest_entry(pos_of[i], rel, window, has_entry, is_ui_at)
        entry = commits[rel[q]][1] if found else None
        if entry is not None:
            ui_ok.append((short, consts, entry))
            continue
        by_id = documented_by_id(full, commits, files_of)
        if by_id is not None:
            ui_by_id.append((short, consts, by_id[0], by_id[1]))
        elif has_escape_hatch(full):
            ui_exempt.append((short, consts))
        else:
            ui_miss.append((short, consts))
    return {
        "commits": commits,
        "relevant": rel,
        "ui_ok": ui_ok,
        "ui_by_id": ui_by_id,
        "ui_exempt": ui_exempt,
        "ui_miss": ui_miss,
        "non_ui": non_ui,
        "untouched": untouched,
    }


def _fmt_consts(consts):
    return ",".join(consts) if consts else "watch.py"


def print_report(res, revrange, window, out=sys.stdout):
    for short, consts in res["ui_miss"]:
        subj = commit_subject(short)
        print(f"MISS  {short} [{_fmt_consts(consts)}] {subj[:60]}", file=out)
    for short, consts, by, tid in res["ui_by_id"]:
        subj = commit_subject(short)
        print(f"DOC-BY-ID {short} [{_fmt_consts(consts)}] {subj[:44]}"
              f"  (#{tid} named in {by})", file=out)
    for short, consts in res["ui_exempt"]:
        subj = commit_subject(short)
        print(f"EXEMPT {short} [{_fmt_consts(consts)}] {subj[:54]}  (Styleguide: n/a)",
              file=out)

    ui_total = (len(res["ui_ok"]) + len(res["ui_by_id"])
                + len(res["ui_exempt"]) + len(res["ui_miss"]))
    print(file=out)
    print(
        # "dashboard", not "watch.py": since #397 a UI commit usually touches
        # only client/, so naming the file would describe the wrong set — and
        # this line is the one a reader takes the count from.
        f"dashboard commits: {ui_total} UI "
        f"({len(res['ui_ok'])} with a styleguide entry within {window} "
        f"relevant commits, "
        f"{len(res['ui_by_id'])} documented by task id named in the doc, "
        f"{len(res['ui_exempt'])} exempt via Styleguide: n/a, "
        f"{len(res['ui_miss'])} without), "
        f"{res['non_ui']} non-UI (server/parser/helper, not subject to the audit)",
        file=out,
    )
    print(
        f"window unit: {len(res['relevant'])} of {len(res['commits'])} commits in "
        f"range touch watch.py or a styleguide file; the other "
        f"{len(res['commits']) - len(res['relevant'])} (ledger, merges, unrelated "
        f"fixes) cannot carry an entry and are not counted toward the window",
        file=out,
    )
    print(
        "(a nearby entry is adjacency, not coverage — it cannot prove the doc "
        "describes the change; DOC-BY-ID is coverage but cannot tell a real "
        "entry from a passing mention. See dev/styleguide_audit.py.)",
        file=out,
    )

    # Pre-baseline visibility — silently narrowing coverage is its own
    # dishonesty (CLAUDE.md). The count is DERIVED at runtime under this
    # filter; a hardcoded literal would carry today's truth into next week.
    if (
        git("rev-parse", "--verify", "-q", BASELINE_ANCHOR, check=False).returncode == 0
        and git("rev-parse", "--verify", "-q", BASELINE_LOW, check=False).returncode == 0
    ):
        pre = classify_range(f"{BASELINE_LOW}..{BASELINE_ANCHOR}", window)
        pre_ui = len(pre["ui_ok"]) + len(pre["ui_exempt"]) + len(pre["ui_miss"])
        print(
            f"pre-baseline ({BASELINE_LOW}..{BASELINE_ANCHOR}): "
            f"{pre_ui} UI watch.py commits, {len(pre['ui_miss'])} without a "
            f"styleguide entry (not back-filled — see dev/styleguide_audit.py)",
            file=out,
        )
        print(
            f"  list them in full: just audit-styleguide {BASELINE_LOW}..HEAD",
            file=out,
        )
    return len(res["ui_miss"])


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="audit-styleguide",
        description="Is a watch.py UI change documented nearby? (#314 diff filter)",
    )
    ap.add_argument(
        "range",
        nargs="?",
        default=f"{BASELINE_ANCHOR}..HEAD",
        help="git range to audit (default: %(default)s)",
    )
    ap.add_argument(
        "--window",
        type=int,
        default=3,
        help="commits either side that may hold the styleguide entry (default: %(default)s)",
    )
    args = ap.parse_args(argv)

    # Refuse a vacuous filter up front. The UI must be findable at HEAD by ONE
    # of the two shapes this audit understands, or every commit classifies
    # non-UI and the audit goes permanently green for the wrong reason —
    # exactly the hollow-check failure mode this repo has paid for three times.
    #
    # Post-#397 the client is files, so the check is that those files exist and
    # are tracked. Pre-#397 it is that UI_CONSTANTS still name literals in
    # watch.py. Either satisfies; NEITHER is the refusal.
    tracked = set(
        git("ls-tree", "-r", "--name-only", "HEAD", check=False)
        .stdout.splitlines()
    )
    assets_present = [a for a in CLIENT_ASSETS if a in tracked]
    head_src = watchpy_source_at("HEAD")
    consts_present = set()
    if head_src:
        consts_present = {name for name, _, _ in ui_ranges(head_src)}

    if len(assets_present) != len(CLIENT_ASSETS):
        missing_consts = [c for c in UI_CONSTANTS if c not in consts_present]
        if missing_consts:
            missing_assets = [a for a in CLIENT_ASSETS if a not in tracked]
            print(
                f"audit-styleguide: the UI is not findable at HEAD by either "
                f"shape. client/ assets missing: "
                f"{', '.join(missing_assets) or 'none'}; UI_CONSTANTS not "
                f"found in watch.py: {', '.join(missing_consts) or 'none'}. "
                f"A rename or a move likely landed without updating "
                f"dev/styleguide_audit.py — the filter would now miss UI "
                f"changes entirely. Fix it and re-run.",
                file=sys.stderr,
            )
            return 2

    res = classify_range(args.range, args.window)
    misses = print_report(res, args.range, args.window)
    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main())
