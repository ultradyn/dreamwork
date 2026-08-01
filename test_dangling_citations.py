"""Narrow tests for `dev/dangling_citations.py`.

Selection is kept NARROW on purpose: an over-broad named-test selection widens
the flake surface of every gate it touches (#916).  Three tests cover the load-
bearing behaviour only — detection, the on-disk exclusion, and the loud-vacuity
fault — and each fixture is hand-written so the expectation is independent of
the scanner under test (#906).
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

from dev import dangling_citations as dc


def _git(root: Path, *args: str) -> None:
    """Run git in ``root``; fail loud so a broken fixture does not silently pass."""
    subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    )


def _make_repo(root: Path, files: dict[str, str]) -> None:
    """Create a throwaway git repo at ``root`` with ``files`` committed at HEAD."""
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(body))
        _git(root, "add", "-f", rel)
    _git(root, "commit", "-q", "-m", "fixture")


# A citation to a file that does not exist and was never tracked.  The literal
# below is the INDEPENDENT expectation (hand-written, not scanner-derived).
DANGLING_PATH = "dev/this_file_does_not_exist.py"


def test_dangling_citation_is_caught(tmp_path: Path) -> None:
    """A backticked repo-relative path naming no real file is reported dangling.

    Expectation source: the literal ``DANGLING_PATH`` above (hand-written
    fixture content), not the scanner's own output (#906).
    """
    _make_repo(
        tmp_path,
        {
            "doc/notes.md": (
                f"See `{DANGLING_PATH}` for the resolver and "
                f"`{DANGLING_PATH}:4-11` for the table.\n"
            ),
            "dev/real.py": "# present so `dev/` is a real dir\n",
        },
    )
    docs, cites, dangling = dc.scan(tmp_path)
    assert docs == 1, f"expected 1 doc scanned, saw {docs}"
    assert cites >= 2, f"expected >=2 citations seen, saw {cites}"
    found = {h.path for h in dangling}
    assert DANGLING_PATH in found, (
        f"dangling citation {DANGLING_PATH!r} not caught; saw {sorted(found)}"
    )


def test_present_on_disk_is_not_dangling(tmp_path: Path) -> None:
    """A path present on disk (even untracked) is not dangling — the rule that
    keeps a gitignored-but-present file like ``.dreamwork/status.json`` clean."""
    _make_repo(
        tmp_path,
        {
            "doc/notes.md": "The store lives at `staging/store.json`.\n",
        },
    )
    # Present on disk but NOT tracked (mirrors a gitignored-but-present file).
    (tmp_path / "staging").mkdir(exist_ok=True)
    (tmp_path / "staging" / "store.json").write_text("{}\n")
    _docs, _cites, dangling = dc.scan(tmp_path)
    assert "staging/store.json" not in {h.path for h in dangling}


def test_empty_root_faults_loudly_not_green_zero(tmp_path: Path) -> None:
    """An empty root must fault at exit 2, not report a green ``0 dangling``.

    This is the degrade-to-zero guard (#868): a regex that silently stops
    matching reads identically to a clean scan, so a zero-denominator run is a
    loud ERROR.
    """
    _make_repo(tmp_path, {"README.md": "# nothing to cite here\n"})
    rc = dc.report(tmp_path)
    assert rc == 2, "a run that saw zero citations must exit 2 (loud vacuity)"
