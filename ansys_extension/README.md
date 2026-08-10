# SimTrail Workbench ACT connector

This extension maintains a local, persistent named-pipe connection between Workbench and the SimTrail desktop app. It supports live project inventory, read-only extraction of existing evaluated Mechanical scalar results, Workbench system rename, system notes, heartbeats, and Project Schematic change notifications.

## Install

Close Workbench, then run from PowerShell using your installed release folder, for example:

```powershell
.\ansys_extension\install_extension.ps1 -AnsysVersion v261
```

Restart Workbench and enable **SimTrailConnector** in **Extensions → Manage Extensions**. Enable the option to load the extension by default if your Workbench version presents it.

The connector automatically retries while SimTrail is closed. Once SimTrail starts, the Workbench Scan page shows the connected project. Communication is local to the Windows named pipe `SimTrail.Workbench.v1`; there is no network listener.

## Uninstall

Close Workbench and run:

```powershell
.\ansys_extension\install_extension.ps1 -AnsysVersion v261 -Uninstall
```

## Safety boundary

The current command allowlist is `scan_project`, `extract_results`, `rename_system`, `set_system_notes`, and `ping`. Result extraction reads existing values and never calls solve or result evaluation, but it can start Mechanical in hidden mode and use a Mechanical license. Rename uses an expected-current-name check to prevent overwriting concurrent changes. The connector never saves the Workbench project automatically.
