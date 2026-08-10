# SimTrail roadmap

SimTrail's destination is an open, local-first simulation project manager. Its
first supported integration is Ansys Workbench; the core remains
solver-neutral.

## 0.2 — Provenance integrity

- Scope cached context and results by project and system identity.
- Make solver snapshots immutable.
- Separate snapshots, capture events, and annotation revisions.
- Namespace extracted parameters and preserve duplicate result objects.
- Add explicit database migrations and automatic backup before migration.

## 0.3 — Connector reliability

- Marshal Workbench API calls onto the supported Workbench execution context.
- Isolate commands and events by Workbench instance.
- Add command timeouts, cancellation, reconnect, and diagnostics.
- Publish a tested Ansys-version compatibility matrix.

## 0.4 — Community MVP

- Add onboarding, backup/restore, tags, saved filters, and structured diffs.
- Publish the versioned snapshot schema and adapter contract.
- Improve accessibility and error explanations.

## 0.5 — Public beta

- Provide reproducible signed or checksum-verified Windows releases.
- Test with external analysts and sanitized real-world fixture projects.
- Establish a documented compatibility and deprecation policy.

## 1.0 — Stable local product

- Guarantee supported database and snapshot migrations.
- Meet the documented reliability gates in `docs/KNOWN_LIMITATIONS.md`.
- Support at least one additional solver adapter as proof of neutrality.

Team synchronization, cloud hosting, automatic model editing, optimization,
and AI assistance are intentionally outside the pre-1.0 critical path.

## Post-1.0 sustainability

After the community product reaches its reliability goals, the maintainers may
offer paid official support and optional enterprise capabilities such as SSO,
central administration, managed synchronization, and contractual compatibility
support. These offerings will follow the boundaries in `PROJECT_MODEL.md` and
will not retroactively change the Apache-2.0 license of published code.
