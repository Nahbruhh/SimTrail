# Known limitations

SimTrail 0.1 is a technical preview. It is suitable for demonstrations and
controlled evaluation, not certification evidence or the sole record of a
simulation program.

## Data integrity work planned for 0.2

- Analyst context and extracted-result caches are currently keyed by Workbench
  system ID and must be scoped by project before routine multi-project use.
- Reimporting an identical solver snapshot refreshes metadata in place; full
  immutable capture and annotation history is not yet implemented.
- Parameters with identical display names in different Workbench cells can
  overwrite one another in the flattened scan representation.
- Mechanical result objects with identical names can overwrite one another in
  the flattened headline-results representation.

## Connector reliability work planned for 0.3

- Workbench API command dispatch requires further thread-affinity validation.
- Multiple simultaneous Workbench instances are visible but not yet fully
  isolated for commands, events, and pending requests.
- Long-running commands do not yet have application-level timeout or cancel
  controls.
- Ansys release compatibility is not yet validated by automated licensed tests.

## Product boundaries

- Only Ansys Workbench has a live connector.
- Result extraction reads a limited set of scalar properties from existing
  Mechanical result objects. It does not capture contour fields.
- SimTrail does not solve, evaluate, or save Workbench projects automatically.
- Rename and note commands modify Workbench project metadata after user action.
- The local database has no authentication, encryption, or multi-user controls.
- Windows binaries are currently unsigned and may trigger SmartScreen.

Please report reproducible issues using synthetic or sanitized projects.
