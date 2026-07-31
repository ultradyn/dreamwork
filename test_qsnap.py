"""#632 — the out-of-band snapshot net for `.dreamwork/questions.md`.

Git was the only witness to twelve answered entries disappearing, and it was
an accidental one: a commit happened to sit twelve minutes earlier. Git is
also the WRONG net for the case that matters, because the dangerous sequence
is "he types an answer, it lands, then the bug fires" — restoring from the
last commit there reverts his answer and trades one loss for another.

So the net observes the FILE, not the repo, and it is deliberately dumb: no
lock, no import of watch.py, no hook, and above all no restart of the running
server — a guard that needed the suspect process to cooperate could not have
been armed while that process was still the thing under diagnosis.

These tests pin the two halves separately: that it PRESERVES (content-
addressed, oldest-pruned-last) and that it DETECTS (answered-count drop).
"""

import gzip
import importlib.util
import json
import os

_SPEC = importlib.util.spec_from_file_location(
    "qsnap_under_test", os.path.join(os.path.dirname(__file__), "qsnap.py"))
qsnap = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(qsnap)


def _questions(open_n, answered_n):
    """A questions.md with the given entry counts, in the real shape."""
    out = ["# Questions for the human", "", "## Open", ""]
    for i in range(open_n):
        out += [f"- **P1 open entry {i}**", f"  body of open {i}", ""]
    out += ["## Answered", ""]
    for i in range(answered_n):
        out += [f"- **P1 answered entry {i}**",
                f"  → answered (2026-07-31 10:00): resolved {i}", ""]
    return "\n".join(out) + "\n"


def _alerts(store_dir):
    path = os.path.join(store_dir, "alerts.log")
    if not os.path.exists(path):
        return []
    return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]


def _index(store_dir):
    path = os.path.join(store_dir, "index.log")
    return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]


def test_counts_read_the_two_sections_independently():
    """Defends: `answered_count` / `open_count` splitting at `## Answered`.

    Both numbers are needed to tell a fold from a deletion, which is the whole
    discrimination this net exists to make: a fold raises answered and lowers
    open, a truncation lowers answered and leaves open alone.
    """
    text = _questions(7, 63)
    assert qsnap.open_count(text) == 7
    assert qsnap.answered_count(text) == 63


def test_a_file_with_no_answered_heading_counts_zero_rather_than_failing():
    """A file we cannot parse is still a file worth keeping.

    Defends the early return in `answered_count`. Refusing to snapshot an
    unparseable file would remove the net exactly when the file is in an
    unexpected state — which is when it is most likely to be being damaged.
    """
    assert qsnap.answered_count("# Questions\n\n## Open\n\n- **x**\n") == 0
    assert qsnap.answered_count("") == 0
    assert qsnap.answered_count(None) == 0


def test_a_deletion_alerts_and_names_what_it_lost(tmp_path):
    """THE DETECTOR. Answered drops with open unchanged — the #632 signature.

    Defends: the drop branch in `Store.record`. Red-proof: remove the alert
    append and this fails; the snapshot would still be taken, which is exactly
    the "preserved but silent" state that let the original incident run.
    """
    store = qsnap.Store(str(tmp_path / "store"))
    state = {}
    path = tmp_path / "questions.md"

    path.write_text(_questions(6, 63), encoding="utf-8")
    qsnap.snapshot_once(str(path), store, state, settle=0.0)
    path.write_text(_questions(6, 51), encoding="utf-8")
    qsnap.snapshot_once(str(path), store, state, settle=0.0)

    alerts = _alerts(str(tmp_path / "store"))
    assert len(alerts) == 1, "a 12-entry deletion must raise exactly one alert"
    assert alerts[0]["lost"] == 12
    assert alerts[0]["from"] == 63 and alerts[0]["to"] == 51
    assert alerts[0]["open_from"] == alerts[0]["open_to"] == 6


def test_a_fold_is_silent(tmp_path):
    """THE FALSE POSITIVE THAT WOULD HAVE KILLED THE NET.

    A fold moves an entry Open → Answered: answered goes UP. A naive
    "answered count changed" rule would fire on every fold, and an alert that
    fires constantly is one nobody reads — so the next real one is missed too.
    Defends: `drop > 0` rather than `drop != 0` in `Store.record`.
    """
    store = qsnap.Store(str(tmp_path / "store"))
    state = {}
    path = tmp_path / "questions.md"
    path.write_text(_questions(7, 63), encoding="utf-8")
    qsnap.snapshot_once(str(path), store, state, settle=0.0)
    path.write_text(_questions(6, 64), encoding="utf-8")   # the fold
    qsnap.snapshot_once(str(path), store, state, settle=0.0)

    assert _alerts(str(tmp_path / "store")) == []
    assert [r["answered"] for r in _index(str(tmp_path / "store"))] == [63, 64]


def test_the_prior_content_is_recoverable_verbatim(tmp_path):
    """THE POINT OF THE WHOLE THING: get his answer back after the damage.

    Defends: the gzip blob written in `Store.record`. A detector that noticed
    the loss but could not undo it would still leave him retyping.
    """
    store = qsnap.Store(str(tmp_path / "store"))
    state = {}
    path = tmp_path / "questions.md"
    good = _questions(6, 64)
    path.write_text(good, encoding="utf-8")
    rec = qsnap.snapshot_once(str(path), store, state, settle=0.0)
    path.write_text(_questions(6, 52), encoding="utf-8")
    qsnap.snapshot_once(str(path), store, state, settle=0.0)

    blob = os.path.join(str(tmp_path / "store"), "snaps", rec["file"])
    assert gzip.open(blob, "rb").read().decode("utf-8") == good


def test_unchanged_content_is_not_snapshotted_twice(tmp_path):
    """Content-addressed: an idle file costs nothing.

    Defends: the sha comparison in `snapshot_once`. Without it a 1s poll would
    write 86,400 identical snapshots a day and the cap would then evict the
    history that matters.
    """
    store = qsnap.Store(str(tmp_path / "store"))
    state = {}
    path = tmp_path / "questions.md"
    path.write_text(_questions(6, 63), encoding="utf-8")
    assert qsnap.snapshot_once(str(path), store, state, settle=0.0) is not None
    assert qsnap.snapshot_once(str(path), store, state, settle=0.0) is None
    assert len(_index(str(tmp_path / "store"))) == 1


def test_an_absent_file_is_not_read_as_a_loss(tmp_path):
    """The rename window must not look like a deletion.

    `atomic_write_text` replaces via `os.replace`, and a caller doing
    temp-then-rename briefly leaves the path missing. Treating that as "the
    file became empty" would record a phantom loss and cry wolf. Defends:
    `read_bytes` returning None and `snapshot_once` skipping.
    """
    store = qsnap.Store(str(tmp_path / "store"))
    state = {}
    assert qsnap.snapshot_once(str(tmp_path / "gone.md"), store, state,
                               settle=0.0) is None
    assert _alerts(str(tmp_path / "store")) == []


def test_prune_deletes_the_oldest_and_keeps_the_newest(tmp_path):
    """A cap on a safety net must evict the OLDEST, never the newest.

    Defends: the slice direction in `Store.prune`. Getting this backwards
    would leave the store full while discarding the recent past, which is the
    only part of it anyone will ever need.
    """
    store = qsnap.Store(str(tmp_path / "store"), keep=3)
    state = {}
    path = tmp_path / "questions.md"
    for n in range(6):
        path.write_text(_questions(6, 60 + n), encoding="utf-8")
        qsnap.snapshot_once(str(path), store, state, settle=0.0)

    kept = sorted(os.listdir(os.path.join(str(tmp_path / "store"), "snaps")))
    assert len(kept) == 3
    # the survivors are the three most recent contents
    survivors = {gzip.open(os.path.join(str(tmp_path / "store"), "snaps", n),
                           "rb").read().decode("utf-8") for n in kept}
    assert survivors == {_questions(6, 63), _questions(6, 64),
                         _questions(6, 65)}
