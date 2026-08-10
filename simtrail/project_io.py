from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .models import Run


class ProjectBundleError(ValueError):
    pass


def save_project_bundle(runs: list[Run], path: str | Path, title: str) -> None:
    payload = {
        "format": "simtrail-project",
        "schema_version": 1,
        "title": title,
        "saved_at": datetime.now().isoformat(),
        "runs": [
            {
                "name": run.name,
                "project": run.project,
                "analyst": run.analyst,
                "created_at": run.created_at.isoformat(),
                "status": run.status,
                "solver": run.solver,
                "source_path": run.source_path,
                "notes": run.notes,
                "inputs": run.inputs,
                "results": run.results,
            }
            for run in runs
        ],
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_project_bundle(path: str | Path) -> tuple[str, list[Run]]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectBundleError(f"Could not read saved project: {exc}") from exc
    if payload.get("format") != "simtrail-project" or not isinstance(payload.get("runs"), list):
        raise ProjectBundleError("This is not a SimTrail project file")
    runs: list[Run] = []
    try:
        for item in payload["runs"]:
            runs.append(Run(
                name=str(item["name"]), project=str(item["project"]), analyst=str(item.get("analyst", "Unknown")),
                created_at=datetime.fromisoformat(item["created_at"]), status=str(item.get("status", "Solved")),
                solver=str(item.get("solver", "Ansys Mechanical")), source_path=str(item.get("source_path", "")),
                notes=str(item.get("notes", "")), inputs=dict(item.get("inputs") or {}),
                results=dict(item.get("results") or {}),
            ))
    except (KeyError, TypeError, ValueError) as exc:
        raise ProjectBundleError(f"Saved project contains an invalid run: {exc}") from exc
    return str(payload.get("title") or source.stem), runs
