from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from .workbench import WorkbenchScanError, parse_workbench_scan

PROTOCOL_VERSION = 1
DEFAULT_PIPE_NAME = "SimTrail.Workbench.v1"


@dataclass(slots=True)
class WorkbenchInstance:
    instance_id: str
    process_id: int
    ansys_version: str = "Unknown"
    project_path: str = ""
    project_name: str = ""
    connector_version: int = 1
    capabilities: tuple[str, ...] = ()
    last_seen: float = field(default_factory=time.monotonic)

    def supports(self, command: str) -> bool:
        return command in self.capabilities


class WorkbenchConnectionManager(QObject):
    connection_changed = Signal()
    project_received = Signal(object)
    command_completed = Signal(object)
    event_received = Signal(object)
    error_received = Signal(str)

    def __init__(self, pipe_name: str = DEFAULT_PIPE_NAME, parent: QObject | None = None):
        super().__init__(parent)
        self.pipe_name = pipe_name
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._accept_connections)
        self._buffers: dict[QLocalSocket, bytearray] = {}
        self._socket_instances: dict[QLocalSocket, str] = {}
        self._instance_sockets: dict[str, QLocalSocket] = {}
        self.instances: dict[str, WorkbenchInstance] = {}
        self.pending: dict[str, str] = {}
        self.active_instance_id = ""
        self._heartbeat = QTimer(self)
        self._heartbeat.setInterval(2000)
        self._heartbeat.timeout.connect(self._check_heartbeats)

    def start(self) -> bool:
        if self.server.isListening():
            return True
        QLocalServer.removeServer(self.pipe_name)
        if not self.server.listen(self.pipe_name):
            self.error_received.emit(f"Could not start Workbench connector: {self.server.errorString()}")
            return False
        self._heartbeat.start()
        return True

    def stop(self) -> None:
        self._heartbeat.stop()
        for socket in list(self._buffers):
            socket.disconnectFromServer()
        self.server.close()
        QLocalServer.removeServer(self.pipe_name)

    @property
    def connected(self) -> bool:
        return bool(self.instances)

    @property
    def active_instance(self) -> WorkbenchInstance | None:
        if self.active_instance_id in self.instances:
            return self.instances[self.active_instance_id]
        return next(iter(self.instances.values()), None)

    def set_active_instance(self, instance_id: str) -> None:
        if instance_id in self.instances:
            self.active_instance_id = instance_id
            self.connection_changed.emit()

    def request_scan(self, instance_id: str | None = None) -> str | None:
        return self.send_command("scan_project", {}, instance_id)

    def rename_system(
        self, system_id: str, expected_name: str, new_name: str, instance_id: str | None = None
    ) -> str | None:
        return self.send_command("rename_system", {
            "system_id": system_id, "expected_name": expected_name, "new_name": new_name,
        }, instance_id)

    def set_system_notes(self, system_id: str, notes: str, instance_id: str | None = None) -> str | None:
        return self.send_command("set_system_notes", {"system_id": system_id, "notes": notes}, instance_id)

    def extract_results(self, system_ids: list[str], instance_id: str | None = None) -> str | None:
        return self.send_command("extract_results", {"system_ids": system_ids}, instance_id)

    def send_command(self, command: str, payload: dict[str, Any], instance_id: str | None = None) -> str | None:
        target = instance_id or self.active_instance_id
        if not target and self.instances:
            target = next(iter(self.instances))
        socket = self._instance_sockets.get(target)
        if not socket or socket.state() != QLocalSocket.LocalSocketState.ConnectedState:
            self.error_received.emit("No connected Workbench instance")
            return None
        request_id = uuid.uuid4().hex
        message = {"type": "command", "protocol": PROTOCOL_VERSION, "request_id": request_id,
                   "command": command, "payload": payload}
        self.pending[request_id] = command
        self._write(socket, message)
        return request_id

    def _accept_connections(self) -> None:
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            self._buffers[socket] = bytearray()
            socket.readyRead.connect(lambda current=socket: self._read_socket(current))
            socket.disconnected.connect(lambda current=socket: self._remove_socket(current))

    def _read_socket(self, socket: QLocalSocket) -> None:
        buffer = self._buffers.get(socket)
        if buffer is None:
            return
        buffer.extend(bytes(socket.readAll()))
        while b"\n" in buffer:
            line, remainder = buffer.split(b"\n", 1)
            buffer[:] = remainder
            if not line.strip():
                continue
            try:
                message = json.loads(line.decode("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                self.error_received.emit(f"Invalid Workbench connector message: {exc}")
                continue
            self._handle_message(socket, message)

    def _handle_message(self, socket: QLocalSocket, message: dict[str, Any]) -> None:
        message_type = message.get("type")
        if message_type == "hello":
            if int(message.get("protocol", 0)) != PROTOCOL_VERSION:
                self._write(socket, {"type": "error", "message": "Unsupported protocol version"})
                socket.disconnectFromServer()
                return
            instance_id = str(message.get("instance_id") or message.get("process_id") or uuid.uuid4().hex)
            instance = WorkbenchInstance(
                instance_id=instance_id,
                process_id=int(message.get("process_id") or 0),
                ansys_version=str(message.get("ansys_version") or "Unknown"),
                project_path=str(message.get("project_path") or ""),
                project_name=str(message.get("project_name") or ""),
                connector_version=int(message.get("connector_version") or 1),
                capabilities=tuple(str(value) for value in (message.get("capabilities") or [])),
            )
            self.instances[instance_id] = instance
            self._socket_instances[socket] = instance_id
            self._instance_sockets[instance_id] = socket
            if not self.active_instance_id:
                self.active_instance_id = instance_id
            self._write(socket, {"type": "hello_ack", "protocol": PROTOCOL_VERSION})
            self.connection_changed.emit()
            return
        instance_id = self._socket_instances.get(socket, "")
        if instance_id in self.instances:
            self.instances[instance_id].last_seen = time.monotonic()
        if message_type == "heartbeat":
            self._write(socket, {"type": "heartbeat_ack", "timestamp": time.time()})
        elif message_type == "response":
            request_id = str(message.get("request_id") or "")
            command = self.pending.pop(request_id, "")
            message["command"] = command
            message["instance_id"] = instance_id
            if message.get("ok") and command == "scan_project":
                try:
                    project = parse_workbench_scan(message.get("result") or {}, "live Workbench")
                except WorkbenchScanError as exc:
                    self.error_received.emit(str(exc))
                else:
                    self.project_received.emit(project)
            self.command_completed.emit(message)
        elif message_type == "event":
            message["instance_id"] = instance_id
            self.event_received.emit(message)
        elif message_type == "error":
            self.error_received.emit(str(message.get("message") or "Workbench connector error"))

    @staticmethod
    def _write(socket: QLocalSocket, message: dict[str, Any]) -> None:
        socket.write((json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
        socket.flush()

    def _remove_socket(self, socket: QLocalSocket) -> None:
        instance_id = self._socket_instances.pop(socket, "")
        self._buffers.pop(socket, None)
        if instance_id:
            self.instances.pop(instance_id, None)
            self._instance_sockets.pop(instance_id, None)
            if self.active_instance_id == instance_id:
                self.active_instance_id = next(iter(self.instances), "")
        # Never leave the UI stuck in a pending state when Workbench exits or
        # reconnects while a command is running.
        for request_id, command in list(self.pending.items()):
            self.pending.pop(request_id, None)
            self.command_completed.emit({
                "type": "response",
                "request_id": request_id,
                "command": command,
                "instance_id": instance_id,
                "ok": False,
                "error": "Workbench disconnected before the command completed",
            })
        try:
            socket.deleteLater()
        except RuntimeError:
            # Qt may already own/delete the socket while the parent window is closing.
            pass
        self.connection_changed.emit()

    def _check_heartbeats(self) -> None:
        cutoff = time.monotonic() - 10.0
        for instance_id, instance in list(self.instances.items()):
            socket = self._instance_sockets.get(instance_id)
            if instance.last_seen < cutoff and socket:
                socket.abort()
