# Architecture

SimTrail is a local-first desktop application with a solver-neutral core and
optional solver-specific adapters.

## Components

```text
Ansys Workbench ACT connector
        │ local named pipe
        ▼
Desktop connection manager ──► Workbench scan model
        │                              │
        └──────────────────────────────┤
                                       ▼
Snapshot conversion ──► Run model ──► SQLite repository
                              │              │
                              ├── diff       ├── register/search
                              └── export     └── project bundles
```

- `simtrail/models.py` defines solver-neutral runs and differences.
- `simtrail/database.py` owns local SQLite persistence.
- `simtrail/workbench.py` validates Workbench scans and converts systems.
- `simtrail/live_connection.py` implements the desktop side of the local pipe.
- `simtrail/scan_ui.py` presents live scanning and analyst context capture.
- `simtrail/ui.py` presents the run register, comparison, and export workflow.
- `ansys_extension/` contains the ACT connector source.
- `ansys_bridge/` contains legacy/manual Workbench journal extractors.

## Trust boundary

The SQLite database, snapshots, exports, and logs remain on the user's machine.
The connector creates no network listener. Workbench writes are limited to the
explicit command allowlist described in `ansys_extension/README.md`.

SimTrail is not yet an audit-qualified system. See `KNOWN_LIMITATIONS.md`.

## Design rules

1. Preserve solver-neutral domain objects.
2. Keep vendor APIs behind adapters.
3. Treat model physics as read-only unless a future capability is separately
   designed, reviewed, and explicitly enabled.
4. Never report missing or failed extraction as a zero result.
5. Version persisted schemas and connector protocols.
6. Prefer immutable snapshots and explicit annotation revisions.
