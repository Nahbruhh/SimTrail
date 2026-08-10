# Security policy

## Supported versions

SimTrail is currently a technical preview. Security fixes are provided only for
the newest tagged release and the default development branch.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub's private
vulnerability reporting feature for this repository. Include:

- affected version or commit;
- operating system and Ansys release, if relevant;
- reproduction steps or a minimal proof of concept;
- potential impact; and
- any suggested mitigation.

Do not include proprietary models or customer data. Maintainers will aim to
acknowledge a complete report within seven days. Response and release timing
depends on severity and maintainer availability.

## Security boundary

SimTrail stores data locally and communicates with its Workbench connector over
a local Windows named pipe. It does not currently provide authentication,
authorization, encryption at rest, network synchronization, or multi-user
isolation. Do not treat the technical preview as an access-control boundary.

The connector can rename Workbench systems and update system notes after an
explicit user action. It does not intentionally modify Mechanical physics,
solve a model, evaluate results, or save a Workbench project automatically.
