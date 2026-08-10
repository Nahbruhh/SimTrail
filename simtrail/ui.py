from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .database import RunRepository
from .exporters import export_comparison_xlsx, export_runs_xlsx
from .importers import SnapshotFormatError, discover_snapshots, load_snapshot
from .live_connection import WorkbenchConnectionManager
from .models import Difference, Run, diff_runs
from .project_io import ProjectBundleError, load_project_bundle, save_project_bundle
from .resources import resource_path
from .sample_data import demo_runs
from .scan_ui import WorkbenchScanPage


def text_value(value: Any) -> str:
    if value is None:
        return "Not set"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


SORT_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class SortableItem(QTableWidgetItem):
    def __lt__(self, other: QTableWidgetItem) -> bool:
        left = self.data(SORT_ROLE)
        right = other.data(SORT_ROLE)
        if left is not None and right is not None:
            return left < right
        return super().__lt__(other)


def numeric_sort_value(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text_value(value))
    return float(match.group(0)) if match else float("-inf")


class MetricCard(QFrame):
    def __init__(self, label: str, value: str, hint: str):
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 13, 16, 13)
        layout.setSpacing(2)
        label_widget = QLabel(label.upper())
        label_widget.setObjectName("metricLabel")
        self.value_widget = QLabel(value)
        self.value_widget.setObjectName("metric")
        self.hint_widget = QLabel(hint)
        self.hint_widget.setObjectName("metricHint")
        layout.addWidget(label_widget)
        layout.addWidget(self.value_widget)
        layout.addWidget(self.hint_widget)

    def update_value(self, value: str, hint: str | None = None) -> None:
        self.value_widget.setText(value)
        if hint is not None:
            self.hint_widget.setText(hint)


class DetailPanel(QFrame):
    compare_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        self.setMinimumWidth(300)
        self.setMaximumWidth(350)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)
        heading = QLabel("RUN DETAILS")
        heading.setObjectName("sectionTitle")
        self.name = QLabel("Select a run")
        self.name.setObjectName("dialogTitle")
        self.name.setWordWrap(True)
        self.meta = QLabel("Inputs and results will appear here.")
        self.meta.setObjectName("subtitle")
        self.meta.setWordWrap(True)
        root.addWidget(heading)
        root.addWidget(self.name)
        root.addWidget(self.meta)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        self.content = QVBoxLayout(body)
        self.content.setContentsMargins(0, 0, 4, 0)
        self.content.setSpacing(8)
        self.content.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        self.open_source = QPushButton("Open source location")
        self.open_source.clicked.connect(self._open_source)
        self.open_source.setEnabled(False)
        root.addWidget(self.open_source)
        self._source = ""

    def _clear(self) -> None:
        while self.content.count():
            item = self.content.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def show_run(self, run: Run | None) -> None:
        self._clear()
        if run is None:
            self.name.setText("Select a run")
            self.meta.setText("Inputs and results will appear here.")
            self._source = ""
            self.open_source.setEnabled(False)
            return
        self.name.setText(run.name)
        self.meta.setText(f"{run.project}\n{run.analyst} · {run.created_at:%d %b %Y, %H:%M}")
        context_keys = (
            ("Purpose", "Analyst purpose"),
            ("Workbench note", "Analyst Workbench note"),
            ("Expected changes", "Analyst expected changes"),
            ("Conclusion", "Analyst conclusion"),
            ("Decision", "Analyst decision"),
        )
        context_values = [
            (label, text_value(run.inputs.get(key))) for label, key in context_keys if run.inputs.get(key)
        ]
        if context_values or run.notes:
            context_title = QLabel("ENGINEERING CONTEXT")
            context_title.setObjectName("sectionTitle")
            self.content.addWidget(context_title)
            for label, value in context_values:
                self.content.addWidget(self._field(label, value, label == "Decision"))
            if run.notes and not context_values:
                self.content.addWidget(self._field("Notes", run.notes))
        result_title = QLabel("HEADLINE RESULTS")
        result_title.setObjectName("sectionTitle")
        self.content.addSpacing(7)
        self.content.addWidget(result_title)
        headline_keys = ("Max equivalent stress", "Max total deformation", "Minimum safety factor", "Solve time")
        headline_found = False
        for key in headline_keys:
            if key in run.results:
                self.content.addWidget(self._field(key, text_value(run.results[key]), key == "Minimum safety factor"))
                headline_found = True
        if not headline_found:
            self.content.addWidget(self._field("Status", "No headline result captured"))
        other_results = [(key, value) for key, value in run.results.items() if key not in headline_keys]
        if other_results:
            all_result_title = QLabel("ALL CAPTURED RESULTS")
            all_result_title.setObjectName("sectionTitle")
            self.content.addSpacing(7)
            self.content.addWidget(all_result_title)
            for key, value in sorted(other_results):
                self.content.addWidget(self._field(key, text_value(value)))
        input_title = QLabel("KEY INPUTS")
        input_title.setObjectName("sectionTitle")
        self.content.addSpacing(7)
        self.content.addWidget(input_title)
        context_input_names = {key for _, key in context_keys}
        for key in sorted(run.inputs):
            if key in context_input_names:
                continue
            self.content.addWidget(self._field(key, text_value(run.inputs[key])))
        self.content.addStretch()
        self._source = run.source_path
        self.open_source.setEnabled(bool(run.source_path))

    @staticmethod
    def _field(name: str, value: str, accent: bool = False) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 1, 0, 3)
        layout.setSpacing(2)
        key = QLabel(name)
        key.setObjectName("subtitle")
        key.setWordWrap(True)
        val = QLabel(value)
        val.setWordWrap(True)
        val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        val.setStyleSheet("font-weight: 700; color: #168C81;" if accent else "font-weight: 600;")
        layout.addWidget(key)
        layout.addWidget(val)
        return widget

    def _open_source(self) -> None:
        if not self._source:
            return
        source = Path(self._source)
        target = source.parent if source.suffix else source
        if target.exists():
            QDesktopServices.openUrl(target.as_uri())
        else:
            QMessageBox.information(self, "Source unavailable", f"The recorded source path does not exist on this machine:\n\n{target}")


class ComparisonDialog(QDialog):
    def __init__(self, before: Run, after: Run, parent: QWidget | None = None):
        super().__init__(parent)
        self.before = before
        self.after = after
        self.setWindowTitle("Compare runs — SimTrail")
        self.resize(940, 700)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)
        top = QHBoxLayout()
        labels = QVBoxLayout()
        title = QLabel("What changed?")
        title.setObjectName("dialogTitle")
        subtitle = QLabel(f"{before.name}  →  {after.name}")
        subtitle.setObjectName("subtitle")
        labels.addWidget(title)
        labels.addWidget(subtitle)
        top.addLayout(labels, 1)
        export = QPushButton("Export comparison")
        export.setObjectName("primary")
        export.clicked.connect(self._export)
        top.addWidget(export)
        root.addLayout(top)
        differences = diff_runs(before, after)
        summary = QLabel(f"{len(differences)} changed fields · unchanged fields are hidden")
        summary.setObjectName("metricHint")
        root.addWidget(summary)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(1)
        if not differences:
            empty = QLabel("These runs have identical captured inputs and results.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setMinimumHeight(200)
            body_layout.addWidget(empty)
        else:
            last_section = None
            for difference in differences:
                if difference.section != last_section:
                    section = QLabel(difference.section.upper())
                    section.setObjectName("sectionTitle")
                    section.setContentsMargins(4, 14, 0, 5)
                    body_layout.addWidget(section)
                    last_section = difference.section
                body_layout.addWidget(self._diff_row(difference))
        body_layout.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(close)
        root.addLayout(bottom)

    @staticmethod
    def _diff_row(difference: Difference) -> QFrame:
        row = QFrame()
        row.setObjectName("diffRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 10, 12, 10)
        name = QLabel(difference.field)
        name.setWordWrap(True)
        name.setMinimumWidth(190)
        before = QLabel(text_value(difference.before))
        before.setObjectName("before")
        before.setWordWrap(True)
        after = QLabel(text_value(difference.after))
        after.setObjectName("after")
        after.setWordWrap(True)
        arrow = QLabel("→")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name, 2)
        layout.addWidget(before, 3)
        layout.addWidget(arrow)
        layout.addWidget(after, 3)
        return row

    def _export(self) -> None:
        default = f"{self.before.name}_vs_{self.after.name}.xlsx".replace("·", "-").replace("/", "-")
        path, _ = QFileDialog.getSaveFileName(self, "Export comparison", default, "Excel workbook (*.xlsx)")
        if path:
            export_comparison_xlsx(self.before, self.after, path)
            QMessageBox.information(self, "Export complete", f"Comparison saved to:\n{path}")


class MainWindow(QMainWindow):
    COLUMNS = ("Run", "Project", "Status", "Captured", "Max stress", "Deformation", "Safety factor", "Analyst")

    def __init__(self, repository: RunRepository, bridge: WorkbenchConnectionManager | None = None):
        super().__init__()
        self.repository = repository
        self._owns_bridge = bridge is None
        self.bridge = bridge or WorkbenchConnectionManager(parent=self)
        if self._owns_bridge:
            self.bridge.start()
        self.runs: list[Run] = []
        self.filtered_runs: list[Run] = []
        self.setWindowTitle("SimTrail — FEA run provenance")
        self.setMinimumSize(1120, 720)
        self.resize(1460, 890)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        shell.addWidget(self._sidebar())
        self.pages = QStackedWidget()
        run_page = QWidget()
        run_layout = QVBoxLayout(run_page)
        run_layout.setContentsMargins(0, 0, 0, 0)
        run_layout.setSpacing(0)
        run_layout.addWidget(self._topbar())
        run_layout.addWidget(self._content(), 1)
        self.pages.addWidget(run_page)
        example_path = resource_path("examples", "workbench-project.simtrail-workbench.json")
        self.scan_page = WorkbenchScanPage(self.repository, example_path, self.bridge)
        self.scan_page.runs_imported.connect(self._scan_runs_imported)
        self.pages.addWidget(self.scan_page)
        shell.addWidget(self.pages, 1)
        status = QStatusBar()
        status.showMessage("Local-only database · no model files are modified")
        self.setStatusBar(status)

    def _sidebar(self) -> QFrame:
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(210)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(18, 23, 18, 18)
        layout.setSpacing(7)
        brand_row = QHBoxLayout()
        dot = QLabel("●")
        dot.setObjectName("brandDot")
        brand = QLabel("SimTrail")
        brand.setObjectName("brand")
        brand_row.addWidget(dot)
        brand_row.addWidget(brand)
        brand_row.addStretch()
        layout.addLayout(brand_row)
        caption = QLabel("FEA PROVENANCE")
        caption.setObjectName("caption")
        layout.addWidget(caption)
        layout.addSpacing(22)
        self.nav_buttons = []
        entries = (("▦   Run register", 0), ("◎   Workbench scan", 1),
                   ("⌕   Archive search  · soon", None), ("✓   Reviews  · soon", None),
                   ("⚙   Settings  · soon", None))
        for text, page_index in entries:
            button = QPushButton(text)
            button.setObjectName("nav")
            button.setProperty("active", page_index == 0)
            if page_index is not None:
                button.clicked.connect(lambda _, index=page_index: self.set_page(index))
                self.nav_buttons.append((button, page_index))
            else:
                button.setEnabled(False)
            layout.addWidget(button)
        layout.addStretch()
        trust = QLabel("READ-ONLY BY DESIGN\nModels stay on this machine")
        trust.setObjectName("sideFoot")
        trust.setWordWrap(True)
        layout.addWidget(trust)
        return side

    def set_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        for button, button_index in self.nav_buttons:
            button.setProperty("active", button_index == index)
            button.style().unpolish(button)
            button.style().polish(button)

    def _scan_runs_imported(self, count: int) -> None:
        self.refresh()
        self.set_page(0)
        self.statusBar().showMessage(f"Imported {count} Workbench analysis system(s)", 6000)

    def _topbar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(88)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(25, 15, 25, 15)
        heading = QVBoxLayout()
        heading.setSpacing(2)
        title = QLabel("Simulation run register")
        title.setObjectName("title")
        subtitle = QLabel("Know what changed. Prove what happened.")
        subtitle.setObjectName("subtitle")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        layout.addLayout(heading)
        layout.addStretch()
        self.compare_button = QPushButton("Compare selected")
        self.compare_button.setObjectName("secondary")
        self.compare_button.setEnabled(False)
        self.compare_button.clicked.connect(self.compare_selected)
        layout.addWidget(self.compare_button)
        clear = QPushButton("Clear everything")
        clear.setObjectName("danger")
        clear.clicked.connect(self.clear_everything)
        layout.addWidget(clear)
        save = QPushButton("Save project")
        save.clicked.connect(self.save_project)
        layout.addWidget(save)
        export = QPushButton("Export register")
        export.clicked.connect(self.export_register)
        layout.addWidget(export)
        snapshot = QPushButton("+  Capture snapshot")
        snapshot.setObjectName("primary")
        menu = QMenu(snapshot)
        file_action = QAction("Import snapshot file…", self)
        file_action.triggered.connect(self.import_file)
        project_action = QAction("Open saved SimTrail project…", self)
        project_action.triggered.connect(self.open_saved_project)
        folder_action = QAction("Scan project folder…", self)
        folder_action.triggered.connect(self.import_folder)
        sample_action = QAction("Add demo project", self)
        sample_action.triggered.connect(self.add_demo_data)
        menu.addActions([project_action, file_action, folder_action])
        menu.addSeparator()
        menu.addAction(sample_action)
        snapshot.setMenu(menu)
        layout.addWidget(snapshot)
        return bar

    def _content(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(15)
        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.metric_runs = MetricCard("Tracked runs", "0", "across all projects")
        self.metric_projects = MetricCard("Active projects", "0", "in this local store")
        self.metric_solved = MetricCard("Solved / reviewed", "0%", "capture coverage")
        self.metric_recent = MetricCard("Recent activity", "0", "runs in the last 7 days")
        for card in (self.metric_runs, self.metric_projects, self.metric_solved, self.metric_recent):
            cards.addWidget(card, 1)
        layout.addLayout(cards)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search runs, analyst, material, loads…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.apply_filters)
        self.search.setMinimumWidth(250)
        self.project_filter = QComboBox()
        self.project_filter.setMinimumWidth(190)
        self.project_filter.currentTextChanged.connect(self.apply_filters)
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All statuses", "Solved", "Candidate", "Review", "Needs review", "Approved reference"])
        self.status_filter.currentTextChanged.connect(self.apply_filters)
        self.analyst_filter = QComboBox()
        self.analyst_filter.setMinimumWidth(135)
        self.analyst_filter.currentTextChanged.connect(self.apply_filters)
        self.results_filter = QComboBox()
        self.results_filter.addItems(["All results", "Has results", "No results"])
        self.results_filter.currentTextChanged.connect(self.apply_filters)
        self.columns_button = QPushButton("Columns")
        self.columns_button.setToolTip("Choose which register columns are visible")
        self.clear_filters_button = QPushButton("Clear filters")
        self.clear_filters_button.clicked.connect(self.clear_filters)
        self.selection_hint = QLabel("Select two rows to compare")
        self.selection_hint.setObjectName("subtitle")
        filters.addWidget(self.search, 1)
        filters.addWidget(self.project_filter)
        filters.addWidget(self.status_filter)
        filters.addWidget(self.analyst_filter)
        filters.addWidget(self.results_filter)
        filters.addWidget(self.columns_button)
        filters.addWidget(self.clear_filters_button)
        filters.addWidget(self.selection_hint)
        layout.addLayout(filters)
        lower = QHBoxLayout()
        lower.setSpacing(15)
        table_card = QFrame()
        table_card.setObjectName("card")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.setWordWrap(False)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.sectionDoubleClicked.connect(self.table.resizeColumnToContents)
        for column, width in enumerate((280, 170, 140, 165, 150, 150, 130, 145)):
            self.table.setColumnWidth(column, width)
        self._setup_column_menu()
        self.table.itemSelectionChanged.connect(self.selection_changed)
        self.table.itemDoubleClicked.connect(lambda _: self.compare_selected() if len(self.selected_runs()) == 2 else None)
        table_layout.addWidget(self.table)
        lower.addWidget(table_card, 1)
        self.details = DetailPanel()
        lower.addWidget(self.details)
        layout.addLayout(lower, 1)
        return content

    def refresh(self) -> None:
        self.runs = self.repository.all()
        current_project = self.project_filter.currentText() if self.project_filter.count() else "All projects"
        current_status = self.status_filter.currentText() if self.status_filter.count() else "All statuses"
        current_analyst = self.analyst_filter.currentText() if self.analyst_filter.count() else "All analysts"
        self.project_filter.blockSignals(True)
        self.project_filter.clear()
        self.project_filter.addItem("All projects")
        self.project_filter.addItems(sorted({run.project for run in self.runs}))
        index = self.project_filter.findText(current_project)
        self.project_filter.setCurrentIndex(max(0, index))
        self.project_filter.blockSignals(False)
        self.status_filter.blockSignals(True)
        self.status_filter.clear()
        self.status_filter.addItem("All statuses")
        self.status_filter.addItems(sorted({run.status for run in self.runs if run.status}))
        status_index = self.status_filter.findText(current_status)
        self.status_filter.setCurrentIndex(max(0, status_index))
        self.status_filter.blockSignals(False)
        self.analyst_filter.blockSignals(True)
        self.analyst_filter.clear()
        self.analyst_filter.addItem("All analysts")
        self.analyst_filter.addItems(sorted({run.analyst for run in self.runs if run.analyst}))
        analyst_index = self.analyst_filter.findText(current_analyst)
        self.analyst_filter.setCurrentIndex(max(0, analyst_index))
        self.analyst_filter.blockSignals(False)
        self.metric_runs.update_value(str(len(self.runs)))
        self.metric_projects.update_value(str(len({run.project for run in self.runs})))
        done = sum(run.status.lower() not in {"needs review", "failed"} for run in self.runs)
        percent = round(done / len(self.runs) * 100) if self.runs else 0
        self.metric_solved.update_value(f"{percent}%")
        from datetime import datetime, timedelta
        recent = sum(run.created_at >= datetime.now() - timedelta(days=7) for run in self.runs)
        self.metric_recent.update_value(str(recent))
        self.apply_filters()

    def apply_filters(self) -> None:
        query = self.search.text().strip().lower()
        project = self.project_filter.currentText()
        status = self.status_filter.currentText()
        analyst = self.analyst_filter.currentText()
        results_choice = self.results_filter.currentText()
        self.filtered_runs = []
        for run in self.runs:
            haystack = " ".join([run.name, run.project, run.analyst, run.status, run.notes]
                                + [text_value(v) for v in run.inputs.values()]
                                + [text_value(v) for v in run.results.values()]).lower()
            if query and query not in haystack:
                continue
            if project and project != "All projects" and run.project != project:
                continue
            if status != "All statuses" and run.status != status:
                continue
            if analyst and analyst != "All analysts" and run.analyst != analyst:
                continue
            if results_choice == "Has results" and not run.results:
                continue
            if results_choice == "No results" and run.results:
                continue
            self.filtered_runs.append(run)
        self._populate_table()

    def clear_filters(self) -> None:
        self.search.clear()
        self.project_filter.setCurrentIndex(0)
        self.status_filter.setCurrentIndex(0)
        self.analyst_filter.setCurrentIndex(0)
        self.results_filter.setCurrentIndex(0)
        self.apply_filters()

    def _setup_column_menu(self) -> None:
        menu = QMenu(self.columns_button)
        self.column_actions: list[QAction] = []
        for column, label in enumerate(self.COLUMNS):
            action = QAction(label, menu)
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(
                lambda visible, index=column: self.table.setColumnHidden(index, not visible)
            )
            menu.addAction(action)
            self.column_actions.append(action)
        self.columns_button.setMenu(menu)

    def _populate_table(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.filtered_runs))
        for row, run in enumerate(self.filtered_runs):
            raw_values = (run.name, run.project, run.status, run.created_at,
                          run.max_stress, run.max_deformation, run.safety_factor, run.analyst)
            display_values = (run.name, run.project, run.status, run.created_at.strftime("%d %b %Y · %H:%M"),
                              text_value(run.max_stress), text_value(run.max_deformation),
                              text_value(run.safety_factor), run.analyst)
            for column, (raw_value, value) in enumerate(zip(raw_values, display_values, strict=True)):
                item = SortableItem(value)
                item.setData(Qt.ItemDataRole.UserRole, run.id)
                if column == 3:
                    sort_value = run.created_at.timestamp()
                elif column in (4, 5, 6):
                    sort_value = numeric_sort_value(raw_value)
                else:
                    sort_value = value.casefold()
                item.setData(SORT_ROLE, sort_value)
                if column == 0:
                    item.setToolTip(run.name + (f"\n\n{run.notes}" if run.notes else ""))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                if column == 2:
                    if run.status in {"Approved reference", "Candidate", "Solved"}:
                        item.setForeground(QColor("#168C81"))
                    elif run.status == "Needs review":
                        item.setForeground(QColor("#B04B5A"))
                self.table.setItem(row, column, item)
        self.table.setSortingEnabled(True)
        self.selection_changed()

    def selected_runs(self) -> list[Run]:
        selected: list[Run] = []
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        for row in rows:
            run_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            run = next((item for item in self.runs if item.id == run_id), None)
            if run:
                selected.append(run)
        return selected

    def selection_changed(self) -> None:
        selected = self.selected_runs()
        self.compare_button.setEnabled(len(selected) == 2)
        self.selection_hint.setText(f"{len(selected)} selected" if selected else "Select two rows to compare")
        self.details.show_run(selected[-1] if selected else None)

    def compare_selected(self) -> None:
        selected = sorted(self.selected_runs(), key=lambda run: run.created_at)
        if len(selected) != 2:
            return
        ComparisonDialog(selected[0], selected[1], self).exec()

    def import_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import SimTrail snapshot", "", "SimTrail snapshots (*.simtrail.json *.json)")
        if not path:
            return
        try:
            run = load_snapshot(path)
            self.repository.add_or_update(run)
        except SnapshotFormatError as exc:
            QMessageBox.warning(self, "Snapshot not imported", str(exc))
            return
        self.refresh()
        self.statusBar().showMessage(f"Captured {run.name} — source model was not modified", 6000)

    def import_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Scan a project folder")
        if not folder:
            return
        paths = discover_snapshots(folder)
        imported = 0
        errors: list[str] = []
        for path in paths:
            try:
                self.repository.add_or_update(load_snapshot(path))
                imported += 1
            except SnapshotFormatError as exc:
                errors.append(f"{path.name}: {exc}")
        self.refresh()
        if not paths:
            QMessageBox.information(self, "No snapshots found", "No *.simtrail.json files were found in this folder.\n\nThe live Ansys extractor is intentionally isolated from this prototype; use the documented JSON format to test ingestion.")
        else:
            message = f"Imported {imported} of {len(paths)} snapshots."
            if errors:
                message += "\n\n" + "\n".join(errors[:5])
            QMessageBox.information(self, "Folder scan complete", message)

    def add_demo_data(self) -> None:
        for run in demo_runs():
            self.repository.add_or_update(run)
        self.refresh()
        self.statusBar().showMessage("Demo project added", 4000)

    def export_register(self) -> None:
        if not self.filtered_runs:
            QMessageBox.information(self, "Nothing to export", "No runs match the current filters.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export run register", "simtrail-run-register.xlsx", "Excel workbook (*.xlsx)")
        if path:
            export_runs_xlsx(self.filtered_runs, path)
            self.statusBar().showMessage(f"Exported {len(self.filtered_runs)} runs to {path}", 6000)

    def save_project(self) -> None:
        selected_project = self.project_filter.currentText()
        runs_to_save = [
            run for run in self.runs
            if not selected_project or selected_project == "All projects" or run.project == selected_project
        ]
        if not runs_to_save:
            QMessageBox.information(self, "Nothing to save", "The selected project has no tracked runs.")
            return
        title = selected_project if selected_project and selected_project != "All projects" else "SimTrail run register"
        safe_name = "".join(character if character.isalnum() or character in "-_ " else "-" for character in title).strip()
        default = f"{safe_name or 'simtrail-project'}.simtrail-project.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save SimTrail project", default, "SimTrail project (*.simtrail-project.json)"
        )
        if not path:
            return
        try:
            save_project_bundle(runs_to_save, path, title)
        except OSError as exc:
            QMessageBox.warning(self, "Project not saved", str(exc))
            return
        self.statusBar().showMessage(f"Saved {len(runs_to_save)} runs to {path}", 6000)

    def open_saved_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open saved SimTrail project", "", "SimTrail project (*.simtrail-project.json *.json)"
        )
        if not path:
            return
        try:
            title, runs = load_project_bundle(path)
        except ProjectBundleError as exc:
            QMessageBox.warning(self, "Project not opened", str(exc))
            return
        added = 0
        matched = 0
        for run in runs:
            _, created = self.repository.add_or_update(run)
            added += int(created)
            matched += int(not created)
        self.refresh()
        self.statusBar().showMessage(f"Opened {title}: {added} added, {matched} already tracked", 7000)

    def clear_everything(self) -> None:
        count = self.repository.count()
        if not count:
            self.statusBar().showMessage("The run register is already empty", 4000)
            return
        answer = QMessageBox.question(
            self,
            "Clear the entire run register?",
            f"This will remove all {count} locally tracked runs.\n\n"
            "Workbench projects, model files, and saved SimTrail project files are not affected.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        removed = self.repository.clear()
        self.refresh()
        self.statusBar().showMessage(f"Cleared {removed} tracked runs", 6000)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._owns_bridge:
            self.bridge.stop()
        self.repository.close()
        super().closeEvent(event)
