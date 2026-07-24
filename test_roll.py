#!/usr/bin/env python3
"""Regression tests for roll.py. Run: python3 test_roll.py"""

import contextlib
import io
import tempfile
import unittest

import roll


def run(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        roll.main(["--no-staleness"] + argv)
    return buf.getvalue().rstrip("\n")


def pick(argv):
    return run(argv).splitlines()[-1]


class TestRoll(unittest.TestCase):
    def test_seeded_determinism(self):
        a = run(["--seed", "7"])
        b = run(["--seed", "7"])
        self.assertEqual(a, b)

    def test_quiet_is_single_parseable_line(self):
        out = run(["--quiet", "--seed", "3"])
        self.assertEqual(len(out.splitlines()), 1)
        self.assertTrue(out == "backlog" or out.startswith("maintenance: "))

    def test_last_line_matches_quiet(self):
        for seed in ("1", "2", "3", "80", "81"):
            self.assertEqual(pick(["--seed", seed]),
                             run(["--quiet", "--seed", seed]))

    def test_no_backlog_never_backlog(self):
        for seed in range(30):
            self.assertTrue(
                pick(["--no-backlog", "--seed", str(seed)])
                .startswith("maintenance: "))

    def test_zero_weight_removes_item(self):
        for seed in range(40):
            self.assertNotEqual(
                pick(["--no-backlog", "--weight", "docs=0",
                      "--seed", str(seed)]),
                "maintenance: docs")

    def test_unknown_item_exits(self):
        with self.assertRaises(SystemExit):
            run(["--weight", "bogus=3"])

    def test_goal_alignment_not_rollable(self):
        # M1 regression: alignment is deterministic-first, never in the pool.
        with self.assertRaises(SystemExit):
            run(["--weight", "goal-alignment=1"])

    def test_default_pool_scales_with_items(self):
        # 6 items x5 = 30; removing one item shrinks the pool to 25.
        self.assertIn("maintenance-pool: 30", run(["--list"]))
        self.assertIn("maintenance-pool: 25",
                      run(["--list", "--weight", "docs=0"]))

    def test_apply_staleness_hunger(self):
        weights = {"a": 3, "b": 3}
        ages = {"a": 0, "b": roll.STALE_WINDOW}
        eff = roll.apply_staleness(weights, ages)
        self.assertEqual(eff["a"], 3)          # fresh: x1
        self.assertEqual(eff["b"], 27)         # starved: x9

    def test_marker_ages_none_outside_git(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(roll.marker_ages(d, ["docs"]))


if __name__ == "__main__":
    unittest.main()
