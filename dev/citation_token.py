#!/usr/bin/env python3
"""The single definition of a glossed task-citation token.

Two tools recognise a ``#NNN — <wording>`` citation in brief prose:

* ``dev/brief.py`` — the generation-time citation-authority report.
* ``dev/citation_audit.py`` — the standalone corpus audit.

They once each carried their own copy of the token shape, and the copies
drifted apart silently: ``citation_audit.py`` dropped the Markdown bold
wrappers and matched ZERO of the 181 house-style ``**#N** — gloss`` citations
in the corpus — the exact form ``briefs/boilerplate.md`` itself models (#1156).
Nothing failed and nothing warned; the audit reported confidently on a corpus
missing its most authoritative specimens.  This module defines the token ONCE
so the two cannot drift again.

Only the TOKEN SHAPE — the bold-aware ``**#NNN**`` id — is shared.  How each
tool captures the gloss that follows, and what it reports, stays separate: the
generation-time reporter and the standalone audit answer different questions
and are deliberately not merged (#996).

WHY THIS HOME IS STABLE.  The module imports nothing — not even ``re`` — so
the import edge from either tool can never be broken "to fix a cycle": a
module that imports nothing cannot participate in one.  The earlier drift was
a *second definition* of one concept; this is the single definition both read.
"""

from __future__ import annotations

# The ``**#NNN**`` citation token: optional Markdown bold before and after a
# ``#``-prefixed task id.  The ``task`` group is NAMED so both consumers read
# the id by name rather than by positional index, which drifts when the
# surrounding grammar gains or loses a capturing group.  Embed this inside a
# larger compiled pattern via an f-string; it carries no flags of its own.
GLOSSED_CITATION_TOKEN = r"(?:\*\*)?#(?P<task>\d+)(?:\*\*)?"
