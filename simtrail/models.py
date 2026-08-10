from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Run:
    name: str
    project: str
    analyst: str
    created_at: datetime
    status: str = "Solved"
    solver: str = "Ansys Mechanical"
    source_path: str = ""
    notes: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    id: int | None = None

    @property
    def max_stress(self) -> Any:
        return self.results.get("Max equivalent stress")

    @property
    def max_deformation(self) -> Any:
        return self.results.get("Max total deformation")

    @property
    def safety_factor(self) -> Any:
        return self.results.get("Minimum safety factor")

    def fingerprint(self) -> str:
        """Stable identity for one exact solver snapshot, excluding analyst metadata."""
        automatic_inputs = {
            key: value for key, value in self.inputs.items()
            if not key.lower().startswith("analyst ")
        }
        payload = {
            "project": self.project,
            "source_path": self.source_path,
            "solver": self.solver,
            "workbench_system": self.inputs.get("Workbench system", ""),
            "inputs": automatic_inputs,
            "results": self.results,
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(slots=True, frozen=True)
class Difference:
    section: str
    field: str
    before: Any
    after: Any


def diff_runs(before: Run, after: Run) -> list[Difference]:
    differences: list[Difference] = []
    sections = (("Inputs", before.inputs, after.inputs), ("Results", before.results, after.results))
    for section, left, right in sections:
        for key in sorted(set(left) | set(right)):
            if left.get(key) != right.get(key):
                differences.append(Difference(section, key, left.get(key), right.get(key)))
    for attribute, label in (("solver", "Solver"), ("status", "Status")):
        if getattr(before, attribute) != getattr(after, attribute):
            differences.insert(0, Difference("Run", label, getattr(before, attribute), getattr(after, attribute)))
    return differences
