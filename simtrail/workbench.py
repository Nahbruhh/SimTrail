from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Run


class WorkbenchScanError(ValueError):
    pass


@dataclass(slots=True)
class WorkbenchSystem:
    system_id: str
    name: str
    analysis_type: str
    state: str = "Unknown"
    state_source: str = ""
    family: str = "Ungrouped"
    shared_source: str = ""
    derived_from: str = ""
    notes: str = ""
    solved: bool = False
    cell_states: dict[str, str] = field(default_factory=dict)
    inputs: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)

    @property
    def is_analysis(self) -> bool:
        lowered = self.analysis_type.lower()
        if lowered.strip() == "geometry":
            return False
        analysis_cells = {"Model", "Setup", "Solution", "Results"}
        if analysis_cells.intersection(self.cell_states):
            return True
        return bool(self.results) or any(word in lowered for word in (
            "structural", "dynamics", "thermal", "modal", "mechanical", "fluent",
            "explicit", "lsdyna", "ls-dyna", "autodyn", "cfx", "static", "transient",
        ))

    @property
    def display_state(self) -> str:
        return f"{self.state_source}: {self.state}" if self.state_source else self.state


@dataclass(slots=True)
class WorkbenchProject:
    name: str
    path: str
    ansys_version: str
    scanned_at: datetime
    systems: list[WorkbenchSystem]


def load_workbench_scan(path: str | Path) -> WorkbenchProject:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkbenchScanError(f"Could not read Workbench scan: {exc}") from exc
    return parse_workbench_scan(payload, str(source))


def parse_workbench_scan(payload: dict[str, Any], source_label: str = "live Workbench") -> WorkbenchProject:
    if not isinstance(payload, dict) or not isinstance(payload.get("systems"), list):
        raise WorkbenchScanError("The scan must contain a 'systems' list")
    systems: list[WorkbenchSystem] = []
    for index, item in enumerate(payload["systems"]):
        if not isinstance(item, dict):
            raise WorkbenchScanError(f"System {index + 1} is not an object")
        system_id = str(item.get("id") or item.get("name") or f"SYS-{index + 1}")
        systems.append(WorkbenchSystem(
            system_id=system_id,
            name=str(item.get("name") or system_id),
            analysis_type=str(item.get("analysis_type") or "Unknown system"),
            state=str(item.get("state") or "Unknown"),
            state_source=str(item.get("state_source") or ""),
            family=str(item.get("family") or item.get("shared_source") or "Ungrouped"),
            shared_source=str(item.get("shared_source") or ""),
            derived_from=str(item.get("derived_from") or ""),
            notes=str(item.get("notes") or ""),
            solved=bool(item.get("solved", bool(item.get("results")))),
            cell_states=dict(item.get("cell_states") or {}),
            inputs=dict(item.get("inputs") or {}),
            results=dict(item.get("results") or {}),
        ))
    try:
        scanned_at = datetime.fromisoformat(str(payload.get("scanned_at") or datetime.now().isoformat()))
    except ValueError as exc:
        raise WorkbenchScanError("'scanned_at' must be an ISO date/time") from exc
    return WorkbenchProject(
        name=str(payload.get("project_name") or Path(source_label).stem),
        path=str(payload.get("project_path") or source_label),
        ansys_version=str(payload.get("ansys_version") or "Unknown"),
        scanned_at=scanned_at,
        systems=systems,
    )


def suggest_reference(systems: list[WorkbenchSystem]) -> tuple[WorkbenchSystem | None, str]:
    candidates = [system for system in systems if system.is_analysis]
    if not candidates:
        return None, "No analysis systems were detected."
    child_counts = {system.system_id: 0 for system in candidates}
    for system in systems:
        if system.derived_from in child_counts:
            child_counts[system.derived_from] += 1

    def score(system: WorkbenchSystem) -> int:
        lowered = system.name.lower()
        value = child_counts.get(system.system_id, 0) * 3
        value += 3 if any(word in lowered for word in ("baseline", "reference", "nominal", "approved")) else 0
        value += 2 if system.solved else 0
        value += 2 if system.state.lower() in {"up-to-date", "current", "solved"} else 0
        value -= 2 if "copy" in lowered else 0
        return value

    selected = max(candidates, key=lambda system: (score(system), -candidates.index(system)))
    reasons: list[str] = []
    descendants = child_counts.get(selected.system_id, 0)
    if descendants:
        reasons.append(f"{descendants} related system(s) derive from it")
    if selected.solved:
        reasons.append("it has solved results")
    if selected.state.lower() in {"up-to-date", "current", "solved"}:
        reasons.append("its cells are current")
    return selected, "; ".join(reasons) or "it is the strongest available analysis candidate"


def system_to_run(
    project: WorkbenchProject,
    system: WorkbenchSystem,
    analyst: str,
    reference_id: str,
    context: dict[str, str],
) -> Run:
    inputs = dict(system.inputs)
    inputs.update({
        "Workbench system": system.system_id,
        "Analysis type": system.analysis_type,
        "System family": system.family,
        "Shared source": system.shared_source or "Independent",
        "Reference system": reference_id,
        "Workbench state basis": system.state_source or "Unspecified",
    })
    if system.cell_states:
        inputs["Workbench cell states"] = "; ".join(f"{key}: {value}" for key, value in system.cell_states.items())
    context_fields = (
        ("Analyst purpose", "purpose"),
        ("Analyst expected changes", "expected_changes"),
        ("Analyst conclusion", "conclusion"),
        ("Analyst decision", "decision"),
    )
    for input_name, context_name in context_fields:
        value = context.get(context_name, "").strip()
        if value:
            inputs[input_name] = value
    if system.notes.strip():
        inputs["Analyst Workbench note"] = system.notes.strip()
    note_parts = []
    if system.notes.strip():
        note_parts.append(f"Workbench note: {system.notes.strip()}")
    for label, key in (("Purpose", "purpose"), ("Expected changes", "expected_changes"),
                       ("Conclusion", "conclusion"), ("Decision", "decision")):
        value = context.get(key, "").strip()
        if value:
            note_parts.append(f"{label}: {value}")
    is_reference = system.system_id == reference_id
    return Run(
        name=system.name,
        project=project.name,
        analyst=analyst.strip() or "Unknown",
        created_at=project.scanned_at,
        status="Approved reference" if is_reference else context.get("decision", "Review") or "Review",
        solver=f"Ansys {system.analysis_type} {project.ansys_version}".strip(),
        source_path=project.path,
        notes="\n".join(note_parts),
        inputs=inputs,
        results=dict(system.results),
    )
