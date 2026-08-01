#!/usr/bin/env python3
"""Propose symbol-backed repairs for past-EOF Markdown citations.

The command is deliberately read-only.  It prints proposals only when prose
names a symbol that has exactly one definition in the current production tree;
missing and ambiguous definitions are findings, never guessed line numbers.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lint import CITE_LINE, HISTORICAL_DOC_PATHS, HISTORICAL_DOC_PREFIXES  # noqa: E402


SOURCE_SUFFIXES = {".py", ".js", ".mjs", ".css"}
IGNORED_SOURCE_PARTS = {"dist", "vendor", "migrations", "__pycache__", "capture"}
CODE_SPAN = re.compile(r"`([^`\n]+)`")
IDENTIFIER = re.compile(
    r"^(?:[A-Za-z_$][\w$]*\.)*[A-Za-z_$][\w$]*(?:\(\))?$"
    r"|^[_A-Za-z][\w-]*$"
)
PATHISH = re.compile(r"(?:^|/)[\w.-]+\.(?:py|js|mjs|css|md)(?::\d+)?$")
NON_SYMBOL_CODE = {"if", "return", "for", "while", "true", "false", "none", "null"}


@dataclass(frozen=True)
class Citation:
    doc: str
    doc_line: int
    old_path: str
    old_line: int
    start: int
    end: int
    context: str


@dataclass(frozen=True)
class Definition:
    symbol: str
    path: str
    line: int
    text: str


@dataclass(frozen=True)
class Resolution:
    citation: Citation
    symbol: str | None
    definitions: tuple[Definition, ...]
    confidence: str
    reason: str


def _tracked(root: Path, pattern: str | None = None) -> list[str]:
    command = ["git", "ls-files"]
    if pattern:
        command.append(pattern)
    proc = subprocess.run(command, cwd=root, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git ls-files failed")
    return [line for line in proc.stdout.splitlines() if line]


def living_docs(root: Path) -> list[str]:
    return [
        rel
        for rel in _tracked(root, "*.md")
        if rel not in HISTORICAL_DOC_PATHS
        and not any(rel.startswith(prefix) for prefix in HISTORICAL_DOC_PREFIXES)
    ]


def _resolve_cited_path(pathpart: str, tracked: set[str]) -> str | None:
    if pathpart in tracked:
        return pathpart
    matches = [rel for rel in tracked if Path(rel).name == Path(pathpart).name]
    return matches[0] if len(matches) == 1 else None


def dangling_citations(root: Path, docs: Iterable[str]) -> list[Citation]:
    tracked = set(_tracked(root))
    result: list[Citation] = []
    for rel in docs:
        lines = (root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        for index, line in enumerate(lines):
            paragraph = "\n".join(lines[max(0, index - 1):min(len(lines), index + 2)])
            for match in CITE_LINE.finditer(line):
                target = _resolve_cited_path(match.group(1), tracked)
                if target is None:
                    continue
                count = len((root / target).read_text(encoding="utf-8", errors="replace").splitlines())
                cited = int(match.group(2))
                if cited <= count:
                    continue
                result.append(Citation(
                    rel, index + 1, match.group(1), cited,
                    match.start(), match.end(), paragraph,
                ))
    return result


def _normalise_symbol(raw: str) -> str | None:
    value = raw.strip().strip(".,;:")
    if value.endswith("()"):
        value = value[:-2]
    if (value.lower() in NON_SYMBOL_CODE or PATHISH.search(value)
            or " " in value or not IDENTIFIER.match(value)):
        return None
    return value


def named_symbols(citation: Citation) -> list[str]:
    """Return nearby backticked identifiers, nearest first."""
    line = citation.context.splitlines()[1 if citation.context.count("\n") == 2 else 0]
    ranked: list[tuple[int, str]] = []
    for match in CODE_SPAN.finditer(line):
        symbol = _normalise_symbol(match.group(1))
        if symbol is None:
            continue
        distance = min(abs(match.start() - citation.start), abs(match.end() - citation.end))
        ranked.append((distance, symbol))
    # Surrounding lines are evidence only when the citation's own line names
    # nothing.  Mixing paragraphs eagerly pairs a neighbour's symbol with the
    # wrong citation.
    if not ranked:
        for match in CODE_SPAN.finditer(citation.context):
            symbol = _normalise_symbol(match.group(1))
            if symbol is not None:
                ranked.append((1000 + match.start(), symbol))
    seen: set[str] = set()
    answer: list[str] = []
    for _, symbol in sorted(ranked):
        if symbol not in seen:
            answer.append(symbol)
            seen.add(symbol)
    return answer


def _definition_patterns(symbol: str) -> tuple[re.Pattern[str], ...]:
    leaf = symbol.rsplit(".", 1)[-1]
    q = re.escape(leaf)
    return (
        re.compile(rf"^\s*(?:async\s+)?def\s+{q}\b"),
        re.compile(rf"^\s*class\s+{q}\b"),
        re.compile(rf"^\s*(?:export\s+)?(?:async\s+)?function\s+{q}\b"),
        re.compile(rf"^\s*(?:export\s+)?(?:const|let|var)\s+{q}\s*="),
        re.compile(rf"^\s*(?:async\s+)?{q}\s*\([^;]*\)\s*\{{"),
        re.compile(rf"^\s*{q}\s*=\s*(?![=])"),
    )


def source_files(root: Path) -> list[str]:
    return [
        rel for rel in _tracked(root)
        if Path(rel).suffix in SOURCE_SUFFIXES
        and not any(part in IGNORED_SOURCE_PARTS for part in Path(rel).parts)
        and not Path(rel).name.startswith("test_")
    ]


def find_definitions(root: Path, symbol: str) -> list[Definition]:
    patterns = _definition_patterns(symbol)
    definitions: list[Definition] = []
    for rel in source_files(root):
        for line_no, text in enumerate(
            (root / rel).read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            if any(pattern.search(text) for pattern in patterns):
                definitions.append(Definition(symbol, rel, line_no, text.strip()))
    return definitions


def resolve(root: Path, citation: Citation) -> Resolution:
    symbols = named_symbols(citation)
    ambiguous: list[Definition] = []
    for rank, symbol in enumerate(symbols):
        definitions = find_definitions(root, symbol)
        if len(definitions) == 1:
            confidence = "high" if rank == 0 else "medium"
            return Resolution(citation, symbol, tuple(definitions), confidence, "unique definition")
        if definitions:
            ambiguous.extend(definitions)
    if ambiguous:
        return Resolution(citation, symbols[0] if symbols else None, tuple(ambiguous), "none", "ambiguous definitions")
    reason = "no named symbol" if not symbols else "cannot resolve named symbol"
    return Resolution(citation, symbols[0] if symbols else None, (), "none", reason)


def cited_line_contains_symbol(root: Path, path: str, line: int, symbol: str) -> bool:
    lines = (root / path).read_text(encoding="utf-8", errors="replace").splitlines()
    if line < 1 or line > len(lines):
        return False
    leaf = symbol.rsplit(".", 1)[-1].removesuffix("()")
    return re.search(rf"(?<![\w$]){re.escape(leaf)}(?![\w$])", lines[line - 1]) is not None


def format_resolution(item: Resolution) -> str:
    cite = item.citation
    old = f"{cite.old_path}:{cite.old_line}"
    prefix = f"{cite.doc}:{cite.doc_line}  {old}"
    if len(item.definitions) == 1:
        definition = item.definitions[0]
        return f"{prefix} -> {definition.path}:{definition.line}  ({item.symbol}, {item.confidence})"
    detail = ", ".join(f"{d.path}:{d.line}" for d in item.definitions)
    suffix = f": {detail}" if detail else ""
    return f"{prefix} -> CANNOT RESOLVE  ({item.symbol or 'no symbol'}, {item.reason}{suffix})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docs", nargs="*", help="tracked Markdown paths (default: every living doc)")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    docs = args.docs or living_docs(root)
    for citation in dangling_citations(root, docs):
        print(format_resolution(resolve(root, citation)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
