"""Shared pytest helpers for isolated repository fixtures."""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
from pathlib import Path


def _local_module_source(repo_root: Path, module: str) -> Path | None:
    module_path = repo_root.joinpath(*module.split("."))
    candidates = (module_path.with_suffix(".py"), module_path / "__init__.py")
    return next((path for path in candidates if path.is_file()), None)


def _module_name(repo_root: Path, source: Path) -> tuple[str, bool]:
    relative = source.relative_to(repo_root)
    if relative.name == "__init__.py":
        return ".".join(relative.parent.parts), True
    return ".".join(relative.with_suffix("").parts), False


def _module_scope_statements(body: list[ast.stmt]):
    """Yield statements reached at module scope, never function/class bodies."""
    for statement in body:
        yield statement
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for field in ("body", "orelse", "finalbody"):
            nested = getattr(statement, field, None)
            if isinstance(nested, list):
                yield from _module_scope_statements(nested)
        for handler in getattr(statement, "handlers", ()):
            yield from _module_scope_statements(handler.body)


def _local_import_sources(repo_root: Path, source: Path):
    module, is_package = _module_name(repo_root, source)
    package = module if is_package else module.rpartition(".")[0]
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    for statement in _module_scope_statements(tree.body):
        names: list[str] = []
        if isinstance(statement, ast.Import):
            names.extend(alias.name for alias in statement.names)
        elif isinstance(statement, ast.ImportFrom):
            if statement.level:
                parts = package.split(".") if package else []
                keep = len(parts) - (statement.level - 1)
                base = parts[:max(keep, 0)]
                if statement.module:
                    base.extend(statement.module.split("."))
                imported_from = ".".join(base)
            else:
                imported_from = statement.module or ""
            if imported_from:
                names.append(imported_from)
            names.extend(
                f"{imported_from}.{alias.name}" if imported_from else alias.name
                for alias in statement.names
            )
        for name in names:
            imported = _local_module_source(repo_root, name)
            if imported is not None:
                yield imported


def _repo_root_import_closure(repo_root: Path, entrypoint: Path) -> tuple[Path, ...]:
    """Derive local imports executed while importing ``entrypoint``."""
    pending = [entrypoint]
    examined: set[Path] = set()
    while pending:
        source = pending.pop()
        if source in examined:
            continue
        examined.add(source)
        pending.extend(
            imported for imported in _local_import_sources(repo_root, source)
            if imported not in examined
        )
    return tuple(sorted(
        source for source in examined
        if source.parent == repo_root and source != entrypoint
    ))


def assert_dispatch_fixture_imports(
        repo_root: Path, fixture_root: Path, dispatch: Path) -> None:
    """Prove dispatch imports inside the fixture without seeing the real checkout."""
    real_root = str(repo_root.resolve())
    probe = subprocess.run(
        [
            sys.executable, "-I", "-c",
            "import pathlib,runpy,sys\n"
            f"real_root = pathlib.Path({real_root!r})\n"
            "visible = {pathlib.Path(p).resolve() for p in sys.path if p}\n"
            "assert real_root not in visible, f'real repo root leaked onto sys.path: {visible}'\n"
            f"scope = runpy.run_path({str(dispatch)!r}, run_name='fixture_import_probe')\n"
            f"assert scope['ROOT'] == pathlib.Path({str(fixture_root)!r})\n"
            "print('fixture dispatch import probe: OK')\n",
        ],
        cwd=fixture_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        output = probe.stderr + probe.stdout
        missing = re.search(r"No module named ['\"]([^'\"]+)", output)
        subject = missing.group(1) if missing else "dev/dispatch_lane.py cleanly"
        raise AssertionError(
            f"fixture repo could not import {subject}\n"
            f"isolated import probe exited {probe.returncode}:\n{output}"
        )
    assert probe.stdout.strip() == "fixture dispatch import probe: OK", (
        "fixture dispatch import probe ran but did not report its examined subject: "
        f"stdout={probe.stdout!r} stderr={probe.stderr!r}"
    )


def install_dispatch_fixture_imports(
        repo_root: Path, fixture_root: Path, dispatch: Path) -> tuple[str, ...]:
    """Copy dispatch's derived root-module closure and prove isolated importability."""
    entrypoint = repo_root / "dev" / "dispatch_lane.py"
    sources = _repo_root_import_closure(repo_root, entrypoint)
    assert sources, "dispatch fixture import derivation examined zero repo-root modules"
    for source in sources:
        shutil.copy2(source, fixture_root / source.name)
    assert_dispatch_fixture_imports(repo_root, fixture_root, dispatch)
    return tuple(source.name for source in sources)
