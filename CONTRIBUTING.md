# Contributing to SimTrail

Thank you for helping make simulation work easier to reproduce and review.
SimTrail welcomes bug reports, documentation, test fixtures, solver adapters,
and focused code contributions.

## Before opening a change

1. Search existing issues and discussions.
2. Open an issue before substantial UI, schema, protocol, or architecture work.
3. Never attach proprietary simulation models, customer data, license files,
   credentials, or confidential solver logs.
4. Use a minimal synthetic project when reproducing solver-specific behavior.

## Development setup

SimTrail requires Python 3.11 or later.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
python main.py --empty
```

On Linux or macOS, activate the virtual environment using the appropriate
`bin/activate` script. The Ansys Workbench connector and packaged desktop build
are Windows-specific, but the solver-neutral core should remain portable.

## Pull requests

- Keep changes focused and explain their user-visible effect.
- Add tests for bug fixes and new behavior.
- Preserve backward compatibility unless the change is explicitly approved.
- Update documentation for schema, protocol, installation, or UI changes.
- Run `python -m pytest` and `python -m ruff check .` before submission.
- Do not commit `dist`, `build`, databases, logs, result payloads, or `.wbex`
  packages. Attach generated artifacts to a release instead.

Every contribution is submitted under the repository's Apache-2.0 license.
No contributor license agreement is currently required.

## Sensitive areas

Changes to snapshot identity, database migrations, unit handling, result
extraction, and Workbench write commands require additional review. Incorrect
behavior in these areas can produce misleading engineering records.

## Testing with Ansys

Ansys is not required for most development. Public CI uses protocol fixtures
and synthetic project data. Contributors performing live Workbench tests must
use their own valid Ansys installation and license and should state the tested
Ansys release in the pull request.
