# -*- coding: utf-8 -*-
# SimTrail persistent Workbench connector
# Compatible with the IronPython runtime hosted by Ansys Workbench.

import datetime
import json
import os
import threading
import time

try:
    import Queue as queue
except ImportError:
    import queue

PIPE_NAME = "SimTrail.Workbench.v1"
PROTOCOL_VERSION = 1
CONNECTOR_VERSION = 2
CAPABILITIES = (
    "scan_project", "extract_results", "rename_system", "set_system_notes", "ping"
)
LOG_DIRECTORY = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "SimTrail")
LOG_PATH = os.path.join(LOG_DIRECTORY, "workbench-connector.log")


def log(message):
    try:
        if not os.path.isdir(LOG_DIRECTORY):
            os.makedirs(LOG_DIRECTORY)
        with open(LOG_PATH, "a") as stream:
            stream.write(datetime.datetime.now().isoformat() + " " + str(message) + "\n")
    except:
        pass


log("Loading SimTrailConnector module")
try:
    import clr
    # IronPython only exposes namespaces from assemblies that have been loaded.
    # System.IO.Pipes lives in System.Core.dll on the .NET Framework used by
    # Workbench 2024 R2, so load it explicitly before importing Pipes.
    clr.AddReference("System.Core")
    from System.IO import StreamReader, StreamWriter
    from System.IO.Pipes import NamedPipeClientStream, PipeDirection, PipeOptions
    from System.Text import UTF8Encoding
except Exception as bootstrap_error:
    log("Connector bootstrap failed: " + str(bootstrap_error))
    raise


def safe_value(obj, property_name, default=""):
    try:
        value = getattr(obj, property_name)
        return str(value) if value is not None else default
    except:
        return default


def safe_bool(obj, property_name, default=False):
    try:
        return bool(getattr(obj, property_name))
    except:
        return default


def get_component(system, name):
    try:
        return system.GetComponent(Name=name)
    except:
        return None


def component_state(component):
    if component is None:
        return "Not present"
    # Workbench schematic status is exposed by these global scripting
    # functions; the component itself does not reliably expose State or
    # IsUpToDate properties.
    for function_name in ("GetComponentState", "GetCellDisplayState"):
        try:
            state_object = globals()[function_name](component)
            value = safe_value(state_object, "State") or str(state_object)
            if value:
                return normalize_component_state(value)
        except:
            pass
    for property_name in ("State", "Status"):
        value = safe_value(component, property_name)
        if value:
            return normalize_component_state(value)
    if safe_bool(component, "IsUpToDate"):
        return "Up-to-date"
    return "Unknown"


def normalize_component_state(value):
    text = str(value).strip()
    key = "".join(character.lower() for character in text if character.isalnum())
    mappings = (
        ("upstreamchangespending", "Upstream changes pending"),
        ("refreshrequired", "Refresh required"),
        ("updaterequired", "Update required"),
        ("editrequired", "Edit required"),
        ("outofdate", "Out of date"),
        ("uptodate", "Up-to-date"),
        ("unfulfilled", "Unfulfilled"),
        ("interrupted", "Interrupted"),
        ("modified", "Modified"),
        ("disabled", "Disabled"),
        ("error", "Error"),
        ("unknown", "Unknown"),
    )
    for token, label in mappings:
        if token in key:
            return label
    return text or "Unknown"


def parameter_value(parameter):
    for property_name in ("Value", "Expression"):
        value = safe_value(parameter, property_name)
        if value:
            return value
    return ""


def container_parameters(system, component_name):
    values = {}
    try:
        container = system.GetContainer(ComponentName=component_name)
        for parameter in container.GetAllParameters():
            name = safe_value(parameter, "DisplayText") or safe_value(parameter, "Name", "Parameter")
            values[name] = parameter_value(parameter)
    except:
        pass
    return values


def project_file_path():
    for function_name in ("GetProjectFile", "GetProjectFileName"):
        try:
            return str(globals()[function_name]())
        except:
            pass
    try:
        return str(GetProjectDirectory())
    except:
        return ""


def project_name_and_path():
    path = project_file_path()
    name = os.path.splitext(os.path.basename(path))[0] if path else "Open Workbench project"
    return name, path


def find_system(system_id):
    for system in GetAllSystems():
        identifiers = (safe_value(system, "Name"), safe_value(system, "UserId"))
        if system_id in identifiers:
            return system
    return None


def build_project_scan():
    project_name, project_path = project_name_and_path()
    component_names = ("Engineering Data", "Geometry", "Model", "Setup", "Solution", "Results")
    systems_payload = []
    for index, system in enumerate(GetAllSystems()):
        system_id = safe_value(system, "Name") or safe_value(system, "UserId") or chr(65 + index)
        display_name = safe_value(system, "DisplayText", system_id)
        analysis_type = safe_value(system, "AnalysisType") or safe_value(system, "SystemType", display_name)
        states = {}
        components = {}
        for component_name in component_names:
            component = get_component(system, component_name)
            components[component_name] = component
            if component is not None:
                states[component_name] = component_state(component)
        geometry = components.get("Geometry")
        shared_source = safe_value(geometry, "UserId") if geometry is not None else ""
        # Report the state of the system's meaningful milestone. Geometry-only
        # systems are governed by Geometry. Analysis systems are governed by
        # Solution, with fallbacks for solver types that expose different cells.
        if analysis_type.strip().lower() == "geometry":
            preferred_state_cells = ("Geometry",)
        else:
            preferred_state_cells = ("Solution", "Results", "Setup", "Model", "Geometry")
        state_source = next(
            (cell_name for cell_name in preferred_state_cells if cell_name in states), ""
        )
        overall_state = states.get(state_source, "Unknown")
        solved = (
            state_source in ("Solution", "Results") and overall_state == "Up-to-date"
        )
        input_parameters = {}
        result_parameters = {}
        for component_name in ("Engineering Data", "Geometry", "Model", "Setup", "Solution"):
            input_parameters.update(container_parameters(system, component_name))
        result_parameters.update(container_parameters(system, "Results"))
        systems_payload.append({
            "id": system_id,
            "name": display_name,
            "notes": safe_value(system, "Notes"),
            "analysis_type": analysis_type,
            "state": overall_state,
            "state_source": state_source,
            "family": shared_source or analysis_type,
            "shared_source": shared_source,
            "derived_from": "",
            "solved": solved,
            "cell_states": states,
            "inputs": input_parameters,
            "results": result_parameters
        })
    version = safe_value(globals().get("ExtAPI", None), "ApplicationVersion", "Workbench")
    return {
        "schema_version": 1,
        "project_name": project_name,
        "project_path": project_path,
        "ansys_version": version,
        "scanned_at": datetime.datetime.now().isoformat(),
        "systems": systems_payload
    }


def _mechanical_result_script(output_path):
    """Build an IronPython script that reads evaluated Mechanical result properties."""
    return r'''
import json

OUTPUT_PATH = %r

def safe_attr(obj, name, default=None):
    try:
        return getattr(obj, name)
    except:
        return default

def text_value(value):
    if value is None:
        return None
    try:
        return str(value)
    except:
        return None

def children_of(obj):
    try:
        return list(obj.Children)
    except:
        return []

def walk(root):
    pending = list(children_of(root))
    seen = set()
    while pending:
        obj = pending.pop(0)
        object_id = safe_attr(obj, "ObjectId", id(obj))
        marker = str(object_id)
        if marker in seen:
            continue
        seen.add(marker)
        yield obj
        pending.extend(children_of(obj))

payload = {"analyses": [], "results": {}, "objects": []}
analyses = list(ExtAPI.DataModel.Project.Model.Analyses)
for analysis in analyses:
    analysis_name = text_value(safe_attr(analysis, "Name", "Analysis")) or "Analysis"
    payload["analyses"].append(analysis_name)
    solution = safe_attr(analysis, "Solution")
    if solution is None:
        continue
    for obj in walk(solution):
        metrics = {}
        for property_name in ("Minimum", "Maximum", "Average", "Total"):
            value = text_value(safe_attr(obj, property_name))
            if value not in (None, "", "None"):
                metrics[property_name] = value
        if not metrics:
            continue
        result_name = text_value(safe_attr(obj, "Name", obj.__class__.__name__)) or "Result"
        qualified_name = result_name if len(analyses) == 1 else analysis_name + " / " + result_name
        record = {
            "analysis": analysis_name,
            "name": result_name,
            "category": text_value(safe_attr(obj, "DataModelObjectCategory", "")) or "",
            "metrics": metrics,
            "time": text_value(safe_attr(obj, "Time")),
            "set_number": text_value(safe_attr(obj, "SetNumber")),
            "substep": text_value(safe_attr(obj, "Substep"))
        }
        payload["objects"].append(record)
        for metric_name, metric_value in metrics.items():
            payload["results"][qualified_name + " | " + metric_name] = metric_value
        lowered = result_name.lower()
        if "equivalent stress" in lowered and "Maximum" in metrics:
            payload["results"]["Max equivalent stress"] = metrics["Maximum"]
        if "total deformation" in lowered and "Maximum" in metrics:
            payload["results"]["Max total deformation"] = metrics["Maximum"]
        if "safety factor" in lowered and "Minimum" in metrics:
            payload["results"]["Minimum safety factor"] = metrics["Minimum"]

with open(OUTPUT_PATH, "w") as output_stream:
    json.dump(payload, output_stream, ensure_ascii=True)
''' % output_path


def extract_existing_results(system_ids):
    requested = set(str(value) for value in (system_ids or []))
    extracted = []
    if not os.path.isdir(LOG_DIRECTORY):
        os.makedirs(LOG_DIRECTORY)
    for system in GetAllSystems():
        system_id = safe_value(system, "Name") or safe_value(system, "UserId")
        if requested and system_id not in requested:
            continue
        item = {"id": system_id, "results": {}, "objects": [], "status": "Unavailable"}
        safe_system_id = "".join(
            character if character.isalnum() or character in ("-", "_") else "_"
            for character in system_id
        )
        output_path = os.path.join(
            LOG_DIRECTORY, "results-%s-%s.json" % (os.getpid(), safe_system_id)
        )
        try:
            if os.path.isfile(output_path):
                os.remove(output_path)
            model = system.GetContainer(ComponentName="Model")
            model.SendCommand(
                Language="Python", Command=_mechanical_result_script(output_path)
            )
            if not os.path.isfile(output_path):
                raise ValueError("Mechanical did not return a result payload")
            with open(output_path, "r") as result_stream:
                payload = json.load(result_stream)
            item["results"] = payload.get("results") or {}
            item["objects"] = payload.get("objects") or []
            item["analyses"] = payload.get("analyses") or []
            item["status"] = "Captured" if item["results"] else "No evaluated scalar results"
        except Exception as error:
            item["status"] = "Failed"
            item["error"] = str(error)
            log("Result extraction failed (" + system_id + "): " + str(error))
        finally:
            try:
                if os.path.isfile(output_path):
                    os.remove(output_path)
            except:
                pass
        extracted.append(item)
    return {"systems": extracted}


class Connector(object):
    def __init__(self):
        self._stop = False
        self._connected = False
        self._announced = False
        self._pipe = None
        self._reader = None
        self._writer = None
        self._write_lock = threading.RLock()
        self._commands = queue.Queue()
        self._thread = None
        self._heartbeat_thread = None
        self._last_heartbeat = 0.0
        self._last_connection_error = ""
        self._hello_data = {}

    @property
    def connected(self):
        return self._connected

    def start(self):
        if self._thread is not None:
            return
        self._stop = False
        # Capture Workbench-owned values on the callback/UI thread.  The pipe
        # worker can then announce the instance immediately after connecting
        # without calling Workbench APIs from a background thread.
        project_name, project_path = project_name_and_path()
        self._hello_data = {
            "type": "hello",
            "protocol": PROTOCOL_VERSION,
            "connector_version": CONNECTOR_VERSION,
            "capabilities": list(CAPABILITIES),
            "instance_id": str(os.getpid()),
            "process_id": os.getpid(),
            "ansys_version": safe_value(
                globals().get("ExtAPI", None), "ApplicationVersion", "Unknown"
            ),
            "project_name": project_name,
            "project_path": project_path
        }
        self._thread = threading.Thread(target=self._connection_loop)
        self._thread.daemon = True
        self._thread.start()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop)
        self._heartbeat_thread.daemon = True
        self._heartbeat_thread.start()
        log("Connector started")
        print("SimTrail connector started; waiting for the desktop application.")

    def stop(self):
        self._stop = True
        try:
            if self._pipe is not None:
                self._pipe.Close()
        except:
            pass
        self._connected = False
        self._thread = None
        self._heartbeat_thread = None
        log("Connector stopped")

    def _connection_loop(self):
        while not self._stop:
            pipe = None
            try:
                pipe = NamedPipeClientStream(
                    ".", PIPE_NAME, PipeDirection.InOut, PipeOptions.Asynchronous
                )
                pipe.Connect(1500)
                encoding = UTF8Encoding(False)
                reader = StreamReader(pipe, encoding)
                writer = StreamWriter(pipe, encoding)
                writer.AutoFlush = True
                self._pipe = pipe
                self._reader = reader
                self._writer = writer
                self._connected = True
                self._last_connection_error = ""
                log("Connected to SimTrail named pipe")
                self._announced = False
                if self.send(self._hello_data):
                    self._announced = True
                    log("Handshake sent to SimTrail")
                while not self._stop and pipe.IsConnected:
                    line = reader.ReadLine()
                    if line is None:
                        break
                    try:
                        message = json.loads(str(line))
                        if message.get("type") == "command":
                            log("Received command: " + str(message.get("command") or ""))
                        self._process_command(message)
                    except Exception as error:
                        self.send({"type": "error", "message": "Invalid command: " + str(error)})
            except Exception as error:
                message = str(error)
                if message != self._last_connection_error:
                    log("Connection unavailable: " + message)
                    self._last_connection_error = message
            finally:
                self._connected = False
                self._announced = False
                self._writer = None
                self._reader = None
                self._pipe = None
                try:
                    if pipe is not None:
                        pipe.Close()
                except:
                    pass
            if not self._stop:
                time.sleep(2.0)

    def _heartbeat_loop(self):
        while not self._stop:
            if self._connected:
                self.send({"type": "heartbeat", "timestamp": time.time()})
            time.sleep(2.0)

    def send(self, message):
        writer = self._writer
        if not self._connected or writer is None:
            return False
        try:
            serialized = json.dumps(message, ensure_ascii=True, separators=(",", ":"))
            with self._write_lock:
                writer.WriteLine(serialized)
            return True
        except Exception as error:
            log("Send failed: " + str(error))
            self._connected = False
            return False

    def _process_command(self, message):
        if message.get("type") not in ("command", "hello_ack", "heartbeat_ack"):
            return
        if message.get("type") != "command":
            return
        request_id = str(message.get("request_id") or "")
        command = str(message.get("command") or "")
        payload = message.get("payload") or {}
        try:
            if command == "scan_project":
                result = build_project_scan()
            elif command == "rename_system":
                result = self._rename_system(payload)
            elif command == "set_system_notes":
                result = self._set_system_notes(payload)
            elif command == "extract_results":
                result = extract_existing_results(payload.get("system_ids") or [])
            elif command == "ping":
                result = {"pong": True}
            else:
                raise ValueError("Unsupported command: " + command)
            self.send({"type": "response", "request_id": request_id, "ok": True, "result": result})
        except Exception as error:
            log("Command failed (" + command + "): " + str(error))
            self.send({
                "type": "response", "request_id": request_id, "ok": False,
                "error": str(error), "error_type": error.__class__.__name__
            })

    def _rename_system(self, payload):
        system_id = str(payload.get("system_id") or "")
        new_name = str(payload.get("new_name") or "").strip()
        expected_name = str(payload.get("expected_name") or "")
        if not new_name:
            raise ValueError("The new system name cannot be empty")
        system = find_system(system_id)
        if system is None:
            raise ValueError("Workbench system was not found: " + system_id)
        current_name = safe_value(system, "DisplayText")
        if expected_name and current_name != expected_name:
            raise ValueError("Rename conflict: Workbench now shows '" + current_name + "'")
        system.DisplayText = new_name
        actual_name = safe_value(system, "DisplayText", new_name)
        self.send_event("system_changed", {"system_id": system_id, "field": "name", "value": actual_name})
        return {"system_id": system_id, "name": actual_name}

    def _set_system_notes(self, payload):
        system_id = str(payload.get("system_id") or "")
        notes = str(payload.get("notes") or "")
        system = find_system(system_id)
        if system is None:
            raise ValueError("Workbench system was not found: " + system_id)
        system.Notes = notes
        actual_notes = safe_value(system, "Notes", notes)
        self.send_event("system_changed", {"system_id": system_id, "field": "notes", "value": actual_notes})
        return {"system_id": system_id, "notes": actual_notes}

    def send_event(self, event_name, data=None):
        self.send({"type": "event", "event": event_name, "data": data or {}, "timestamp": time.time()})


_connector = Connector()


def on_init(context):
    _connector.start()


def on_ready(context=None):
    _connector.start()


def on_load(currentFolder=None):
    _connector.send_event("project_loaded", {"path": project_file_path()})


def on_save(currentFolder=None):
    _connector.send_event("project_saved", {"path": project_file_path()})


def on_terminate(context=None):
    _connector.stop()


def on_project_action(task=None):
    data = {}
    if task is not None:
        data["task_name"] = safe_value(task, "Name")
        data["task_caption"] = safe_value(task, "DisplayText")
    _connector.send_event("project_changed", data)
