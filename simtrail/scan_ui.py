from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .database import RunRepository
from .live_connection import WorkbenchConnectionManager
from .models import Run, diff_runs
from .process_detection import is_workbench_running
from .workbench import (
    WorkbenchProject,
    WorkbenchScanError,
    WorkbenchSystem,
    load_workbench_scan,
    suggest_reference,
    system_to_run,
)


class WorkbenchScanPage(QWidget):
    runs_imported = Signal(int)

    def __init__(self, repository: RunRepository, example_path: Path, bridge: WorkbenchConnectionManager):
        super().__init__()
        self.repository = repository
        self.example_path = example_path
        self.bridge = bridge
        self.project: WorkbenchProject | None = None
        self.context_by_id: dict[str, dict[str, str]] = {}
        self.extracted_results_by_id: dict[str, dict] = {}
        self._editing_id = ""
        self.checkboxes: dict[str, QCheckBox] = {}
        self.pending_actions: dict[str, tuple[str, str]] = {}
        self._last_connection_id = ""
        self._rescan_timer = QTimer(self)
        self._rescan_timer.setSingleShot(True)
        self._rescan_timer.setInterval(600)
        self._rescan_timer.timeout.connect(self._request_live_scan)
        self._process_timer = QTimer(self)
        self._process_timer.setInterval(5000)
        self._process_timer.timeout.connect(self._update_disconnected_status)
        self._process_timer.start()
        self._build_ui()
        self.bridge.connection_changed.connect(self._connection_changed)
        self.bridge.project_received.connect(self.set_project)
        self.bridge.command_completed.connect(self._command_completed)
        self.bridge.event_received.connect(self._workbench_event)
        self.bridge.error_received.connect(self._bridge_error)
        self._connection_changed()

    def _build_ui(self) -> None:
        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        top = QFrame()
        top.setObjectName("topbar")
        top.setFixedHeight(88)
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(25, 15, 25, 15)
        heading = QVBoxLayout()
        title = QLabel("Workbench project scan")
        title.setObjectName("title")
        subtitle = QLabel("Discover analysis systems, confirm a reference, and capture engineering context.")
        subtitle.setObjectName("subtitle")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        top_layout.addLayout(heading)
        top_layout.addStretch()
        self.connection_status = QLabel("Workbench disconnected")
        self.connection_status.setStyleSheet(
            "background:#EDF1F4;color:#718095;padding:8px 12px;border-radius:7px;font-weight:600;"
        )
        self.instance_selector = QComboBox()
        self.instance_selector.setMinimumWidth(170)
        self.instance_selector.currentIndexChanged.connect(self._instance_selected)
        self.instance_selector.hide()
        demo = QPushButton("Load example")
        demo.clicked.connect(self.load_example)
        load = QPushButton("Load scan file…")
        load.clicked.connect(self.load_file)
        self.scan_button = QPushButton("Scan Workbench")
        self.scan_button.setObjectName("primary")
        self.scan_button.clicked.connect(self.scan_workbench)
        top_layout.addWidget(self.connection_status)
        top_layout.addWidget(self.instance_selector)
        top_layout.addWidget(demo)
        top_layout.addWidget(load)
        top_layout.addWidget(self.scan_button)
        shell.addWidget(top)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 20)
        content_layout.setSpacing(14)
        self.project_card = QFrame()
        self.project_card.setObjectName("card")
        project_layout = QHBoxLayout(self.project_card)
        project_layout.setContentsMargins(18, 14, 18, 14)
        project_text = QVBoxLayout()
        self.project_name = QLabel("No Workbench project scanned")
        self.project_name.setObjectName("dialogTitle")
        self.project_meta = QLabel("Install and enable SimTrailConnector in Workbench, or load a saved scan file.")
        self.project_meta.setObjectName("subtitle")
        project_text.addWidget(self.project_name)
        project_text.addWidget(self.project_meta)
        project_layout.addLayout(project_text, 1)
        self.scan_summary = QLabel("0 systems")
        self.scan_summary.setObjectName("metricHint")
        project_layout.addWidget(self.scan_summary)
        self.extract_button = QPushButton("Extract existing results")
        self.extract_button.setEnabled(False)
        self.extract_button.clicked.connect(self.extract_existing_results)
        project_layout.addWidget(self.extract_button)
        self.import_button = QPushButton("Import selected systems")
        self.import_button.setObjectName("primary")
        self.import_button.setEnabled(False)
        self.import_button.clicked.connect(self.import_selected)
        project_layout.addWidget(self.import_button)
        content_layout.addWidget(self.project_card)

        body = QHBoxLayout()
        body.setSpacing(14)
        table_card = QFrame()
        table_card.setObjectName("card")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ("Include", "System", "Analysis type", "Family / source", "State", "Changes vs reference")
        )
        self.table.horizontalHeaderItem(5).setToolTip(
            "Number of extracted engineering fields that differ from the selected reference. "
            "Analyst notes are not counted."
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in (0, 2, 3, 4, 5):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        table_layout.addWidget(self.table)
        body.addWidget(table_card, 1)
        body.addWidget(self._context_panel())
        content_layout.addLayout(body, 1)
        shell.addWidget(content, 1)

    def _context_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("card")
        panel.setMinimumWidth(330)
        panel.setMaximumWidth(390)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(0)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        scroll.setStyleSheet("QScrollArea { border: none; background: white; }")
        form = QWidget()
        form.setStyleSheet("background: white;")
        layout = QVBoxLayout(form)
        layout.setContentsMargins(18, 17, 18, 12)
        layout.setSpacing(6)
        title = QLabel("REFERENCE & CONTEXT")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        self.reference = QComboBox()
        self.reference.currentIndexChanged.connect(self._reference_changed)
        layout.addWidget(QLabel("Reference system"))
        layout.addWidget(self.reference)
        self.reference_reason = QLabel("Load a scan to receive a reference suggestion.")
        self.reference_reason.setWordWrap(True)
        self.reference_reason.setObjectName("metricHint")
        layout.addWidget(self.reference_reason)
        self.selected_label = QLabel("Select an analysis system")
        self.selected_label.setObjectName("dialogTitle")
        self.selected_label.setWordWrap(True)
        layout.addSpacing(9)
        layout.addWidget(self.selected_label)
        self.analyst = QLineEdit()
        self.analyst.setPlaceholderText("Analyst for this system")
        layout.addWidget(QLabel("Analyst"))
        layout.addWidget(self.analyst)
        self.workbench_name = QLineEdit()
        self.workbench_name.setPlaceholderText("Workbench system display name")
        self.rename_button = QPushButton("Apply name in Workbench")
        self.rename_button.setObjectName("secondary")
        self.rename_button.clicked.connect(self._rename_in_workbench)
        self.rename_button.setEnabled(False)
        self.workbench_notes = QTextEdit()
        self.workbench_notes.setPlaceholderText("Workbench system notes")
        self.workbench_notes.setFixedHeight(48)
        self.notes_button = QPushButton("Apply note in Workbench")
        self.notes_button.setObjectName("secondary")
        self.notes_button.clicked.connect(self._notes_in_workbench)
        self.notes_button.setEnabled(False)
        self.workbench_name.setEnabled(False)
        self.workbench_notes.setEnabled(False)
        layout.addWidget(QLabel("Live Workbench name"))
        layout.addWidget(self.workbench_name)
        layout.addWidget(self.rename_button)
        layout.addWidget(QLabel("Live Workbench note"))
        layout.addWidget(self.workbench_notes)
        layout.addWidget(self.notes_button)
        self.purpose = QLineEdit()
        self.purpose.setPlaceholderText("Why was this system created?")
        self.expected = QTextEdit()
        self.expected.setPlaceholderText("What changes did you intend?")
        self.expected.setFixedHeight(52)
        self.conclusion = QTextEdit()
        self.conclusion.setPlaceholderText("What did the analysis show?")
        self.conclusion.setFixedHeight(52)
        self.decision = QComboBox()
        self.decision.addItems(("Review", "Candidate", "Accepted", "Rejected", "Needs review"))
        for label, widget in (("Purpose", self.purpose), ("Expected changes", self.expected),
                              ("Conclusion", self.conclusion), ("Decision", self.decision)):
            layout.addWidget(QLabel(label))
            layout.addWidget(widget)
        layout.addStretch()
        scroll.setWidget(form)
        outer.addWidget(scroll, 1)
        return panel

    def load_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Workbench project scan", "", "SimTrail Workbench scan (*.simtrail-workbench.json *.json)"
        )
        if path:
            self.load_scan(Path(path))

    def load_example(self) -> None:
        self.load_scan(self.example_path)

    def scan_workbench(self) -> None:
        if not self.bridge.connected:
            QMessageBox.information(
                self, "Workbench connector not connected",
                "Open Workbench and enable the SimTrailConnector ACT extension. "
                "It reconnects automatically while SimTrail is running.",
            )
            return
        self._request_live_scan()

    def _request_live_scan(self) -> None:
        request_id = self.bridge.request_scan()
        if request_id:
            self.pending_actions[request_id] = ("scan", "")
            self.scan_button.setEnabled(False)
            self.scan_button.setText("Scanning…")

    def load_scan(self, path: Path) -> None:
        try:
            project = load_workbench_scan(path)
        except WorkbenchScanError as exc:
            QMessageBox.warning(self, "Scan not loaded", str(exc))
            return
        self.set_project(project)

    def set_project(self, project: WorkbenchProject) -> None:
        previous_context = self.context_by_id
        for system in project.systems:
            cached = self.extracted_results_by_id.get(system.system_id)
            if cached:
                system.results.update(cached)
        self.project = project
        self.context_by_id = previous_context
        self.project_name.setText(project.name)
        self.project_meta.setText(f"{project.path}  ·  Ansys {project.ansys_version}  ·  scanned {project.scanned_at:%d %b %Y, %H:%M}")
        analyses = sum(system.is_analysis for system in project.systems)
        solved = sum(system.solved for system in project.systems)
        self.scan_summary.setText(f"{len(project.systems)} systems · {analyses} analyses · {solved} solved")
        self.reference.blockSignals(True)
        self.reference.clear()
        for system in project.systems:
            if system.is_analysis:
                self.reference.addItem(f"{system.system_id} — {system.name}", system.system_id)
        suggestion, reason = suggest_reference(project.systems)
        if suggestion:
            index = self.reference.findData(suggestion.system_id)
            self.reference.setCurrentIndex(max(0, index))
            self.reference_reason.setText(f"Suggested {suggestion.system_id}: {reason}. Please confirm.")
        self.reference.blockSignals(False)
        self._populate()
        self.import_button.setEnabled(analyses > 0)
        active = self.bridge.active_instance
        self.extract_button.setEnabled(
            analyses > 0 and bool(active and active.supports("extract_results"))
        )

    def extract_existing_results(self) -> None:
        if not self.project or not self.bridge.connected:
            return
        active = self.bridge.active_instance
        if not active or not active.supports("extract_results"):
            QMessageBox.information(
                self, "Connector update required",
                "The connected Workbench extension is an older in-memory version. "
                "Restart Workbench and enable the installed SimTrailConnector again.",
            )
            return
        self._save_context()
        selected_ids = [
            system.system_id for system in self.project.systems
            if system.is_analysis and self.checkboxes.get(system.system_id)
            and self.checkboxes[system.system_id].isChecked()
        ]
        if not selected_ids:
            QMessageBox.information(
                self, "Nothing selected", "Select at least one analysis system to extract."
            )
            return
        request_id = self.bridge.extract_results(selected_ids)
        if request_id:
            self.pending_actions[request_id] = ("extract_results", "")
            self.extract_button.setEnabled(False)
            self.extract_button.setText("Extracting…")

    def _populate(self) -> None:
        if not self.project:
            return
        previous_selected = self._editing_id
        previous_checks = {system_id: checkbox.isChecked() for system_id, checkbox in self.checkboxes.items()}
        reference = self._reference_system()
        reference_run = self._temporary_run(reference) if reference else None
        self.table.setRowCount(len(self.project.systems))
        self.checkboxes.clear()
        for row, system in enumerate(self.project.systems):
            checkbox = QCheckBox()
            checkbox.setChecked(previous_checks.get(system.system_id, system.is_analysis))
            checkbox.setEnabled(system.is_analysis)
            holder = QWidget()
            holder_layout = QHBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            holder_layout.addWidget(checkbox)
            self.table.setCellWidget(row, 0, holder)
            self.checkboxes[system.system_id] = checkbox
            change_count = "—"
            change_tooltip = "Only analysis systems are compared."
            if system.is_analysis and reference_run:
                if system.system_id == reference.system_id:
                    change_count = "Reference"
                    change_tooltip = "This is the selected comparison reference."
                else:
                    count = len(diff_runs(reference_run, self._temporary_run(system)))
                    change_count = str(count)
                    change_tooltip = (
                        f"{count} extracted engineering field(s) differ from {reference.name}. "
                        "Analyst notes are not counted."
                    )
            values = (system.name, system.analysis_type, system.shared_source or system.family,
                      system.display_state, change_count)
            for offset, value in enumerate(values, 1):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, system.system_id)
                if offset == 1:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                if offset == 5:
                    item.setToolTip(change_tooltip)
                self.table.setItem(row, offset, item)
        if self.project.systems:
            selected_row = next(
                (i for i, item in enumerate(self.project.systems) if item.system_id == previous_selected),
                next((i for i, item in enumerate(self.project.systems) if item.is_analysis), 0),
            )
            self.table.selectRow(selected_row)

    @staticmethod
    def _temporary_run(system: WorkbenchSystem) -> Run:
        from datetime import datetime
        inputs = dict(system.inputs)
        inputs.update({
            "Analysis type": system.analysis_type,
            "Shared source": system.shared_source or "Independent",
            "Workbench state basis": system.state_source or "Unspecified",
        })
        if system.cell_states:
            inputs["Workbench cell states"] = "; ".join(
                f"{key}: {value}" for key, value in system.cell_states.items()
            )
        return Run(system.name, "", "", datetime.now(), inputs=inputs, results=system.results)

    def _reference_system(self) -> WorkbenchSystem | None:
        if not self.project:
            return None
        system_id = self.reference.currentData()
        return next((system for system in self.project.systems if system.system_id == system_id), None)

    def _reference_changed(self) -> None:
        if self.project:
            selected = self._reference_system()
            if selected:
                self.reference_reason.setText(f"Confirmed reference: {selected.system_id} — {selected.name}")
            self._save_context()
            self._populate()

    def _selected_system(self) -> WorkbenchSystem | None:
        if not self.project or not self.table.selectedItems():
            return None
        row = self.table.currentRow()
        item = self.table.item(row, 1)
        system_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        return next((system for system in self.project.systems if system.system_id == system_id), None)

    def _save_context(self) -> None:
        if not self._editing_id:
            return
        self.context_by_id[self._editing_id] = {
            "analyst": self.analyst.text(),
            "purpose": self.purpose.text(),
            "expected_changes": self.expected.toPlainText(),
            "conclusion": self.conclusion.toPlainText(),
            "decision": self.decision.currentText(),
        }

    def _selection_changed(self) -> None:
        self._save_context()
        system = self._selected_system()
        if not system:
            return
        self._editing_id = system.system_id
        self.selected_label.setText(f"{system.system_id} — {system.name}")
        self.workbench_name.setText(system.name)
        self.workbench_notes.setPlainText(system.notes)
        context = self.context_by_id.get(system.system_id, {})
        self.analyst.setText(context.get("analyst", ""))
        self.purpose.setText(context.get("purpose", ""))
        self.expected.setPlainText(context.get("expected_changes", ""))
        self.conclusion.setPlainText(context.get("conclusion", ""))
        self.decision.setCurrentText(context.get("decision", "Review"))
        enabled = system.is_analysis
        for widget in (self.analyst, self.purpose, self.expected, self.conclusion, self.decision):
            widget.setEnabled(enabled)
        live_enabled = self.bridge.connected
        for widget in (self.workbench_name, self.workbench_notes, self.rename_button, self.notes_button):
            widget.setEnabled(live_enabled)

    def _connection_changed(self) -> None:
        instances = list(self.bridge.instances.values())
        active = self.bridge.active_instance
        self.instance_selector.blockSignals(True)
        self.instance_selector.clear()
        for instance in instances:
            label = instance.project_name or f"Workbench PID {instance.process_id}"
            self.instance_selector.addItem(label, instance.instance_id)
        if active:
            index = self.instance_selector.findData(active.instance_id)
            self.instance_selector.setCurrentIndex(max(0, index))
        self.instance_selector.setVisible(len(instances) > 1)
        self.instance_selector.blockSignals(False)
        if active:
            label = active.project_name or f"PID {active.process_id}"
            current_connector = active.supports("extract_results")
            if current_connector:
                self.connection_status.setText(
                    f"● Connected · {label} · connector v{active.connector_version}"
                )
                self.connection_status.setStyleSheet(
                    "background:#E8F8F5;color:#087E72;padding:8px 12px;"
                    "border-radius:7px;font-weight:700;"
                )
            else:
                self.connection_status.setText(f"● Connected · {label} · connector update required")
                self.connection_status.setStyleSheet(
                    "background:#FFF4DC;color:#91620B;padding:8px 12px;"
                    "border-radius:7px;font-weight:700;"
                )
            self.scan_button.setEnabled(True)
            self.extract_button.setEnabled(bool(current_connector and self.project and any(
                system.is_analysis for system in self.project.systems
            )))
            if active.instance_id != self._last_connection_id:
                self._last_connection_id = active.instance_id
                QTimer.singleShot(250, self._request_live_scan)
        else:
            self._last_connection_id = ""
            self._update_disconnected_status()
            self.scan_button.setEnabled(False)
            self.extract_button.setEnabled(False)
        self._selection_changed()

    def _update_disconnected_status(self) -> None:
        if self.bridge.connected:
            return
        if is_workbench_running():
            self.connection_status.setText("◐ Workbench detected · connector unavailable")
            self.connection_status.setStyleSheet(
                "background:#FFF4DC;color:#91620B;padding:8px 12px;border-radius:7px;font-weight:600;"
            )
        else:
            self.connection_status.setText("○ Workbench not running")
            self.connection_status.setStyleSheet(
                "background:#EDF1F4;color:#718095;padding:8px 12px;border-radius:7px;font-weight:600;"
            )

    def _instance_selected(self) -> None:
        instance_id = self.instance_selector.currentData()
        if instance_id:
            self.bridge.set_active_instance(str(instance_id))

    def _rename_in_workbench(self) -> None:
        system = self._selected_system()
        if not system:
            return
        new_name = self.workbench_name.text().strip()
        if not new_name:
            QMessageBox.information(self, "Name required", "The Workbench system name cannot be empty.")
            return
        request_id = self.bridge.rename_system(system.system_id, system.name, new_name)
        if request_id:
            self.pending_actions[request_id] = ("rename", system.system_id)
            self.rename_button.setEnabled(False)
            self.rename_button.setText("Applying…")

    def _notes_in_workbench(self) -> None:
        system = self._selected_system()
        if not system:
            return
        request_id = self.bridge.set_system_notes(system.system_id, self.workbench_notes.toPlainText())
        if request_id:
            self.pending_actions[request_id] = ("notes", system.system_id)
            self.notes_button.setEnabled(False)
            self.notes_button.setText("Applying…")

    def _command_completed(self, message: dict) -> None:
        request_id = str(message.get("request_id") or "")
        action, system_id = self.pending_actions.pop(
            request_id, (str(message.get("command") or ""), "")
        )
        if action == "scan":
            self.scan_button.setText("Scan Workbench")
            self.scan_button.setEnabled(self.bridge.connected)
        elif action == "rename":
            self.rename_button.setText("Apply name in Workbench")
            self.rename_button.setEnabled(self.bridge.connected)
        elif action == "notes":
            self.notes_button.setText("Apply note in Workbench")
            self.notes_button.setEnabled(self.bridge.connected)
        elif action == "extract_results":
            self.extract_button.setText("Extract existing results")
            active = self.bridge.active_instance
            self.extract_button.setEnabled(bool(
                active and active.supports("extract_results") and self.project
                and any(item.is_analysis for item in self.project.systems)
            ))
        if not message.get("ok"):
            QMessageBox.warning(self, "Workbench command failed", str(message.get("error") or "Unknown error"))
            return
        result = message.get("result") or {}
        system = next(
            (item for item in self.project.systems if item.system_id == system_id), None
        ) if self.project else None
        if system and action == "rename":
            system.name = str(result.get("name") or system.name)
            self._populate()
        elif system and action == "notes":
            system.notes = str(result.get("notes") or "")
            self._selection_changed()
        elif action == "extract_results":
            captured = 0
            empty = 0
            failed: list[str] = []
            for item in result.get("systems") or []:
                item_id = str(item.get("id") or "")
                extracted = dict(item.get("results") or {})
                target = next(
                    (entry for entry in self.project.systems if entry.system_id == item_id), None
                ) if self.project else None
                if extracted:
                    self.extracted_results_by_id.setdefault(item_id, {}).update(extracted)
                    if target:
                        target.results.update(extracted)
                    captured += 1
                elif item.get("status") == "Failed":
                    failed.append(f"{item_id}: {item.get('error') or 'unknown error'}")
                else:
                    empty += 1
            self._populate()
            message_text = (
                f"Captured existing scalar results from {captured} system(s).\n"
                f"No evaluated scalar results in {empty} system(s)."
            )
            if failed:
                message_text += "\n\nFailed:\n" + "\n".join(failed[:5])
            QMessageBox.information(self, "Result extraction complete", message_text)

    def _workbench_event(self, message: dict) -> None:
        if message.get("event") in {"project_changed", "project_loaded", "project_saved"}:
            self._rescan_timer.start()

    def _bridge_error(self, message: str) -> None:
        self.connection_status.setText("! " + message)
        self.connection_status.setStyleSheet(
            "background:#FDEFF1;color:#A43C4C;padding:8px 12px;border-radius:7px;font-weight:600;"
        )

    def import_selected(self) -> None:
        if not self.project:
            return
        self._save_context()
        reference_id = str(self.reference.currentData() or "")
        selected = [system for system in self.project.systems
                    if self.checkboxes.get(system.system_id) and self.checkboxes[system.system_id].isChecked()]
        if not selected:
            QMessageBox.information(self, "Nothing selected", "Select at least one analysis system.")
            return
        added = 0
        matched = 0
        for system in selected:
            context = self.context_by_id.get(system.system_id, {})
            run = system_to_run(
                self.project, system, context.get("analyst", ""), reference_id, context,
            )
            _, created = self.repository.add_or_update(run)
            if created:
                added += 1
            else:
                matched += 1
        self.runs_imported.emit(len(selected))
        QMessageBox.information(
            self, "Systems imported",
            f"Added {added} new snapshot(s); refreshed {matched} existing snapshot(s)."
            "\n\nWorkbench and model files were not modified.",
        )
