#!/usr/bin/env python3
"""Run pytest with lightweight coverage enforcement.

This script uses Python's built-in ``trace`` module so that we do not rely on
third-party tooling that may not be present in every environment.  After the
unit tests finish we measure the executed lines for each tracked component and
verify that they satisfy the configured coverage thresholds.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from trace import Trace
from typing import Iterable

import pytest


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Component:
    name: str
    paths: tuple[Path, ...]
    threshold: float
    description: str


CRITICAL_COMPONENTS: tuple[Component, ...] = (
    Component(
        name="name_service",
        paths=(ROOT / "core" / "name_service.py",),
        threshold=0.80,
        description="Name generation orchestration and storage interactions.",
    ),
    Component(
        name="user_settings",
        paths=(ROOT / "core" / "user_settings.py",),
        threshold=0.80,
        description="User preference management for default values.",
    ),
    Component(
        name="name_generation_core",
        paths=(
            ROOT / "core" / "name_generator.py",
            ROOT / "core" / "naming_rules.py",
            ROOT / "core" / "validation.py",
        ),
        threshold=0.80,
        description="Rules and helpers that build and validate resource names.",
    ),
)

NON_CRITICAL_COMPONENT_NOTES = {
    "azure_functions": (
        (
            ROOT / "audit_bulk",
            ROOT / "audit_name",
            ROOT / "claim_name",
            ROOT / "release_name",
            ROOT / "slug_sync",
            ROOT / "slug_sync_timer",
        ),
        "Azure Function entry points that delegate to the shared utilities. Their behaviour is covered through"
        " the critical components, so we classify them as non-critical for coverage enforcement.",
    ),
    "supporting_utilities": (
        (
            ROOT / "adapters" / "audit_logs.py",
            ROOT / "adapters" / "release_name.py",
            ROOT / "adapters" / "slug.py",
            ROOT / "adapters" / "slug_fetcher.py",
            ROOT / "adapters" / "slug_loader.py",
            ROOT / "adapters" / "storage.py",
            ROOT / "core" / "auth.py",
        ),
        "Supporting helpers that interact with external services. They require extensive integration"
        " testing and are exercised indirectly via higher-level components, so they are currently"
        " marked as non-critical.",
    ),
}


def _iter_python_files(paths: Iterable[Path]) -> Iterable[Path]:
    for base in paths:
        if base.is_file() and base.suffix == ".py":
            yield base
        elif base.is_dir():
            yield from (p for p in base.rglob("*.py") if p.is_file())


def _executable_lines(path: Path) -> set[int]:
    source = path.read_text(encoding="utf-8")
    try:
        code = compile(source, str(path), "exec")
    except SyntaxError:
        return set()

    source_lines = source.splitlines()
    executable: set[int] = set()

    def visit(code_object: object) -> None:
        if not hasattr(code_object, "co_consts"):
            return
        first_line = getattr(code_object, "co_firstlineno", None)
        if first_line and 0 < first_line <= len(source_lines):
            header_text = source_lines[first_line - 1].strip()
            if "pragma: no cover" in header_text:
                return
        for entry in code_object.co_lines():  # type: ignore[attr-defined]
            if isinstance(entry, tuple):
                *_, line_no = entry
            else:  # pragma: no cover - defensive; co_lines should yield tuples
                line_no = int(entry)
            if line_no is None:
                continue
            if line_no <= 0 or line_no - 1 >= len(source_lines):
                continue
            text = source_lines[line_no - 1].strip()
            if not text:
                continue
            if text.startswith("#"):
                continue
            if "pragma: no cover" in text:
                continue
            if text == "...":
                continue
            executable.add(line_no)
        for const in code_object.co_consts:  # type: ignore[attr-defined]
            if hasattr(const, "co_consts"):
                visit(const)

    visit(code)
    return executable


def main() -> int:
    tracer = Trace(count=True, trace=False, ignoredirs=[str(Path(sys.prefix))])
    test_exit_code = tracer.runfunc(pytest.main, ["tests"])
    if test_exit_code != 0:
        return test_exit_code

    results = tracer.results()
    executed_by_file: dict[Path, set[int]] = defaultdict(set)
    for (filename, lineno), _count in results.counts.items():
        path = Path(filename)
        try:
            path.relative_to(ROOT)
        except ValueError:
            continue
        executed_by_file[path].add(lineno)

    summary: dict[str, dict[str, object]] = {}
    failure_messages: list[str] = []

    for component in CRITICAL_COMPONENTS:
        files = list(_iter_python_files(component.paths))
        total_executable = 0
        total_executed = 0
        per_file: list[dict[str, object]] = []

        for file_path in sorted(files):
            executable_lines = _executable_lines(file_path)
            if not executable_lines:
                continue
            executed_lines = executed_by_file.get(file_path, set()) & executable_lines
            total_executable += len(executable_lines)
            total_executed += len(executed_lines)
            coverage = 0.0
            if executable_lines:
                coverage = len(executed_lines) / len(executable_lines)
            per_file.append(
                {
                    "file": str(file_path.relative_to(ROOT)),
                    "executed": len(executed_lines),
                    "executable": len(executable_lines),
                    "coverage": round(coverage * 100, 2),
                }
            )

        component_coverage = 100.0
        if total_executable:
            component_coverage = round(total_executed / total_executable * 100, 2)

        summary[component.name] = {
            "description": component.description,
            "coverage": component_coverage,
            "threshold": component.threshold * 100,
            "files": per_file,
        }

        print(f"Component: {component.name}")
        print(f"  Description: {component.description}")
        print(f"  Coverage: {component_coverage:.2f}% (threshold {component.threshold * 100:.0f}%)")
        for file_info in per_file:
            print(
                "    - {file}: {coverage:.2f}% ({executed}/{executable} lines)".format(
                    **file_info
                )
            )
        print()

        if component_coverage < component.threshold * 100:
            failure_messages.append(
                f"Component '{component.name}' coverage {component_coverage:.2f}% is below the"
                f" required {component.threshold * 100:.0f}% threshold."
            )

    print("Non-critical components:")
    for label, (paths, reason) in NON_CRITICAL_COMPONENT_NOTES.items():
        rel_paths = ", ".join(str(path.relative_to(ROOT)) for path in paths if path.exists())
        print(f"  - {label}: {reason} ({rel_paths})")
    print()

    output_path = ROOT / "coverage-summary.json"
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Coverage summary written to {output_path.relative_to(ROOT)}")

    if failure_messages:
        for message in failure_messages:
            print(message, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
