# Governance

SimTrail currently uses a maintainer-led governance model.

## Maintainers

Maintainers review contributions, manage releases, moderate project spaces,
and protect compatibility and engineering-data integrity. New maintainers may
be invited after sustained, constructive contributions and demonstrated care
in sensitive areas of the codebase.

## Decisions

Routine changes are decided through pull-request review. Changes affecting the
database schema, snapshot identity, connector protocol, supported platforms,
licensing, or project governance require a public design issue before
implementation. Important decisions should be recorded under `docs/decisions`.

## Releases

SimTrail follows semantic versioning. Before version 1.0, minor versions may
contain breaking changes when they are documented with migration guidance.
Release artifacts are generated from tagged commits by the repository's public
automation where practical.

## Independence

The project is independent of solver vendors. Vendor-specific behavior belongs
in adapters or connectors; the provenance model and run register should remain
solver-neutral.

## Project sustainability

The maintainers may fund development through optional official support,
training, integration work, and future enterprise offerings. These activities
must follow the public commitments in `PROJECT_MODEL.md` and must not revoke
the Apache-2.0 rights granted for published community code.
