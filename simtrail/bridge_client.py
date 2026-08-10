from __future__ import annotations

import os
import socket
from pathlib import Path

from .workbench import WorkbenchProject, WorkbenchScanError, load_workbench_scan

HOST = "127.0.0.1"
PORT = 51280


def default_bridge_scan() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    return root / "SimTrail" / "bridge" / "latest.simtrail-workbench.json"


def scan_connected_workbench(timeout: float = 4.0) -> WorkbenchProject:
    """Request one read-only inventory from the one-shot Workbench bridge."""
    chunks: list[bytes] = []
    try:
        with socket.create_connection((HOST, PORT), timeout=timeout) as connection:
            connection.sendall(b"SIMTRAIL_SCAN_V1\n")
            connection.settimeout(timeout)
            while True:
                chunk = connection.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                if sum(map(len, chunks)) > 20 * 1024 * 1024:
                    raise WorkbenchScanError("Workbench bridge response exceeded 20 MB")
    except OSError as exc:
        raise WorkbenchScanError(
            "No Workbench bridge is listening. In Workbench, run "
            "ansys_bridge/workbench_live_bridge.wbjn and click Scan Workbench again."
        ) from exc
    if not chunks:
        raise WorkbenchScanError("Workbench bridge returned an empty response")
    destination = default_bridge_scan()
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        destination.write_bytes(b"".join(chunks))
    except OSError as exc:
        raise WorkbenchScanError(f"Could not save the Workbench response: {exc}") from exc
    return load_workbench_scan(destination)

