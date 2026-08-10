# Third-party notices

SimTrail depends on open-source software distributed under its own licenses.
The dependency metadata in `pyproject.toml` is the authoritative dependency
list for a source installation.

## Runtime dependencies

- **Python** — Python Software Foundation License.
- **PySide6 / Qt for Python** — available under LGPL-3.0-only, GPL-3.0-only,
  or applicable commercial Qt terms. SimTrail uses the dynamically loaded
  PySide6 libraries and does not modify Qt.
- **openpyxl** — MIT License.

## Build and development dependencies

- **PyInstaller** — GPL-2.0-or-later with the PyInstaller exception for
  distributing bundled applications.
- **pytest** — MIT License.
- **Ruff** — MIT License.

Binary distributions ship this notice, the SimTrail `LICENSE` and `NOTICE`,
and the applicable texts under `licenses/`. Qt for Python is used under the
LGPL-3.0 option; both the LGPL-3.0 and incorporated GPL-3.0 texts are included.
A downstream distributor is responsible for confirming that its chosen
packaging method continues to satisfy all applicable obligations, including
the LGPL requirements for relinking/replacement and reverse engineering for
debugging modifications to the LGPL-covered libraries.

Ansys software is not included with SimTrail. Users install and license Ansys
products separately under their agreements with Ansys.
