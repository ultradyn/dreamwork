"""Red-first tests for user_events.digest (lane A, increments A1 and A2).

Named production lines whose deletion must fail each test (plan §Lane A):
- length prefix write in length_framed  → test_framing_boundary_cannot_be_shifted
- .lower() on media-type subtype        → test_case_and_parameter_order_do_not_fork_a_digest
- parameter sorted()                    → same test, alone, with .lower() restored

Must not fake: no hand-built framed bytes; no direct hash library use in this file.
"""

from __future__ import annotations

from user_events.digest import length_framed, request_digest


def test_framing_boundary_cannot_be_shifted():
    """Field boundaries cannot be shifted to collide under length framing.

    Classic delimiter collision: naive concat of ("ab","c") equals that of
    ("a","bc"). Digests of those splits must still differ because
    length_framed prefixes each part. The precondition is derived at runtime
    — if the pairs do not collide under naive concat, this test proves nothing.
    """
    left = ("ab", "c")
    right = ("a", "bc")
    naive_left = left[0] + left[1]
    naive_right = right[0] + right[1]
    assert naive_left == naive_right, (
        "precondition failed: naive concatenations of "
        f"{left!r} and {right!r} must be equal for this test to prove "
        f"framing (got {naive_left!r} vs {naive_right!r}); the fixture "
        "no longer expresses a boundary collision"
    )

    # Production path only — call length_framed (must not assemble framing here).
    framed_left = length_framed(left[0], left[1])
    framed_right = length_framed(right[0], right[1])
    assert framed_left != framed_right, (
        "length_framed outputs must differ for boundary-shifted splits"
    )

    # Digests via request_digest. The colliding pair must occupy *adjacent*
    # framed fields that are not asymmetrically transformed — content_type
    # (lowercased as a whole when slash-free) and body sit next to each other
    # in the frame. Putting the pair across method would break the red: method
    # uppercasing makes "ab"+"C" and "a"+"BC" differ even without prefixes.
    d_left = request_digest(
        protocol_version="1",
        method="POST",
        route="/answer",
        content_type=left[0],
        body=left[1].encode("utf-8"),
    )
    d_right = request_digest(
        protocol_version="1",
        method="POST",
        route="/answer",
        content_type=right[0],
        body=right[1].encode("utf-8"),
    )
    assert d_left != d_right, (
        "request digests of boundary-shifted field splits must differ; "
        "if they match, length framing is not protecting delimiters"
    )


