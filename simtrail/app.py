from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SimTrail FEA run tracker")
    parser.add_argument("--version", action="version", version=f"SimTrail {__version__}")
    parser.add_argument("--db", type=Path, help="Path to the SQLite database")
    parser.add_argument("--empty", action="store_true", help="Do not seed an empty database with demo runs")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    # Keep GUI imports after argument parsing so metadata commands such as
    # ``simtrail --version`` work on headless systems without Qt platform
    # libraries. Normal desktop startup still loads the full PySide6 stack.
    from PySide6.QtCore import QStandardPaths
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication

    from .database import RunRepository
    from .sample_data import demo_runs
    from .theme import APP_STYLE
    from .ui import MainWindow

    app = QApplication(sys.argv[:1])
    app.setApplicationName("SimTrail")
    app.setOrganizationName("SimTrail")
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#F4F7FA"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#20B8A6"))
    app.setPalette(palette)
    app.setStyleSheet(APP_STYLE)
    if args.db:
        db_path = args.db
    elif os.getenv("SIMTRAIL_DB"):
        db_path = Path(os.environ["SIMTRAIL_DB"])
    else:
        app_data = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
        db_path = app_data / "simtrail.db"
    repository = RunRepository(db_path)
    if not repository.is_initialized():
        if repository.count() == 0 and not args.empty:
            for run in demo_runs():
                repository.add_or_update(run)
        repository.mark_initialized()
    window = MainWindow(repository)
    window.show()
    return app.exec()
