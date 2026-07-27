"""Length-framed request digests for the user-event journal.

request_digest = SHA-256(length_framed(
    protocol_version, UPPERCASE_method, canonical_route,
    canonical_content_type, exact_body_bytes))

Every field is length-prefixed so concatenation cannot collide at delimiters.
"""

from __future__ import annotations

import hashlib
from typing import Union

BytesLike = Union[bytes, bytearray, memoryview, str]


def _as_bytes(value: BytesLike) -> bytes:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    raise TypeError(f"expected bytes or str, got {type(value).__name__}")


def length_framed(*parts: BytesLike) -> bytes:
    """Concatenate parts, each preceded by an 8-byte big-endian length prefix.

    Deleting the length-prefix write collapses field boundaries: naive
    concatenation of ("ab","c") and ("a","bc") collides; with prefixes they
    cannot.
    """
    out = bytearray()
    for part in parts:
        data = _as_bytes(part)
        out.extend(len(data).to_bytes(8, "big"))
        out.extend(data)
    return bytes(out)


def canonical_method(method: str) -> str:
    """HTTP methods are case-insensitive; digests use the uppercase form."""
    return method.upper()


def canonical_route(route: str) -> str:
    """Exact registered path. Current write routes accept no semantic query.

    A bare path is returned as-is (no trailing slash invented). A query string,
    if present, is kept in the order given — write routes that forbid queries
    refuse them at the envelope layer, not here.
    """
    return route


def canonical_media_type(content_type: str) -> str:
    """Lower-cased type/subtype plus deterministically ordered parameters.

    ``Application/JSON; Charset=UTF-8`` and ``application/json;charset=utf-8``
    and a reordered two-parameter form all collapse to one string so they
    cannot fork a digest.
    """
    raw = content_type.strip()
    if not raw:
        return ""
    segments = raw.split(";")
    main = segments[0].strip()
    if "/" in main:
        typ, subtype = main.split("/", 1)
        # .lower() on the subtype is load-bearing for case-folding the media
        # type; deleting it alone must fail the canonicalisation test.
        base = f"{typ.strip().lower()}/{subtype.strip().lower()}"
    else:
        base = main.lower()

    params: list[tuple[str, str]] = []
    for segment in segments[1:]:
        piece = segment.strip()
        if not piece:
            continue
        if "=" in piece:
            key, value = piece.split("=", 1)
            params.append((key.strip().lower(), value.strip().lower()))
        else:
            params.append((piece.lower(), ""))

    # sorted() on parameters is load-bearing for order-independence; deleting
    # it alone must fail the canonicalisation test with .lower() restored.
    params = sorted(params)
    if not params:
        return base
    rendered = []
    for key, value in params:
        if value == "":
            rendered.append(key)
        else:
            rendered.append(f"{key}={value}")
    return base + ";" + ";".join(rendered)


def request_digest(
    *,
    protocol_version: BytesLike,
    method: str,
    route: str,
    content_type: str,
    body: BytesLike,
) -> str:
    """SHA-256 hex digest of the length-framed canonical request fields."""
    framed = length_framed(
        protocol_version,
        canonical_method(method),
        canonical_route(route),
        canonical_media_type(content_type),
        body,
    )
    return hashlib.sha256(framed).hexdigest()
