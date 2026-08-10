from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

WORKBENCH_EXECUTABLES = {"runwb2.exe", "ansyswbu.exe", "framework.exe"}


def is_workbench_running() -> bool:
    """Best-effort Windows process check; a live connector remains authoritative."""
    if os.name != "nt":
        return False

    class ProcessEntry32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessEntry32W))
    kernel32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessEntry32W))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    invalid_handle = wintypes.HANDLE(-1).value
    if snapshot == invalid_handle:
        return False
    entry = ProcessEntry32W()
    entry.dwSize = ctypes.sizeof(entry)
    found = False
    try:
        success = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while success:
            if entry.szExeFile.lower() in WORKBENCH_EXECUTABLES:
                found = True
                break
            success = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return found
