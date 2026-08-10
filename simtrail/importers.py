from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Run


class SnapshotFormatError(ValueError):
    pass


def load_snapshot(path: str | Path) -> Run:
    source = Path(path)
    try:
        payload: dict[str, Any] = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotFormatError(f"Could not read snapshot: {exc}") from exc
    missing = [key for key in ("name", "project", "inputs", "results") if key not in payload]
    if missing:
        raise SnapshotFormatError("Missing required fields: " + ", ".join(missing))
    if not isinstance(payload["inputs"], dict) or not isinstance(payload["results"], dict):
        raise SnapshotFormatError("'inputs' and 'results' must be JSON objects")
    try:
        created = datetime.fromisoformat(payload.get("created_at", datetime.now().isoformat()))
    except ValueError as exc:
        raise SnapshotFormatError("'created_at' must be an ISO date/time") from exc
    return Run(
        name=str(payload["name"]), project=str(payload["project"]),
        analyst=str(payload.get("analyst", "Unknown")), created_at=created,
        status=str(payload.get("status", "Solved")),
        solver=str(payload.get("solver", "Ansys Mechanical")), source_path=str(source),
        notes=str(payload.get("notes", "")), inputs=payload["inputs"], results=payload["results"],
    )


def discover_snapshots(folder: str | Path) -> list[Path]:
    return sorted(Path(folder).rglob("*.simtrail.json"))

