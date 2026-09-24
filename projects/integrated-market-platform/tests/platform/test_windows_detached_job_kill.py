"""Disposable Windows job-close test for detached campaign children.

This does not touch a campaign state directory. It creates its own job object
and a short-lived parent. It does not assign the test runner to that job.
Non-Windows runs skip.
"""

from __future__ import annotations

import ctypes
import os
import sys
import tempfile
import time
import unittest
from ctypes import wintypes
from pathlib import Path

CREATE_SUSPENDED = 0x00000004
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
CREATE_BREAKAWAY_FROM_JOB = 0x01000000
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x00000800
JobObjectExtendedLimitInformation = 9
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


def _alive(kernel32, pid: int) -> bool:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    kernel32.CloseHandle(handle)
    return True


def _job_close_kills_child(*, breakaway: bool) -> bool:
    """Return True when the child is still alive after the parent job closes."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.BOOL,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        ctypes.POINTER(STARTUPINFOW),
        ctypes.POINTER(PROCESS_INFORMATION),
    ]
    kernel32.CreateProcessW.restype = wintypes.BOOL
    holder = tempfile.TemporaryDirectory(prefix="imp-job-kill-")
    try:
        directory = Path(holder.name)
        marker = directory / "child.txt"
        pid_path = directory / "child.pid"
        child_flags = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
        if breakaway:
            child_flags |= CREATE_BREAKAWAY_FROM_JOB
        parent_source = f"""
import subprocess, sys
from pathlib import Path
marker = {str(marker)!r}
pid_path = {str(pid_path)!r}
cmd = [sys.executable, "-c", "import pathlib,time; pathlib.Path(" + repr(marker) + ").write_text('up', encoding='utf-8'); time.sleep(20)"]
proc = subprocess.Popen(cmd, creationflags={child_flags}, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
Path(pid_path).write_text(str(proc.pid), encoding="utf-8")
proc._child_created = False
__import__("time").sleep(15)
"""
        parent_path = directory / "parent.py"
        parent_path.write_text(parent_source, encoding="utf-8")
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            raise OSError(ctypes.get_last_error())
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_BREAKAWAY_OK
        if not kernel32.SetInformationJobObject(
            job, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)
        ):
            raise OSError(ctypes.get_last_error())
        startup = STARTUPINFOW()
        startup.cb = ctypes.sizeof(startup)
        created = PROCESS_INFORMATION()
        command = ctypes.create_unicode_buffer(f'"{sys.executable}" "{parent_path}"')
        if not kernel32.CreateProcessW(
            None,
            command,
            None,
            None,
            False,
            CREATE_SUSPENDED | CREATE_NO_WINDOW,
            None,
            None,
            ctypes.byref(startup),
            ctypes.byref(created),
        ):
            raise OSError(ctypes.get_last_error())
        try:
            if not kernel32.AssignProcessToJobObject(job, created.hProcess):
                raise OSError(ctypes.get_last_error())
            if kernel32.ResumeThread(created.hThread) == 0xFFFFFFFF:
                raise OSError(ctypes.get_last_error())
            deadline = time.time() + 8
            while time.time() < deadline and not pid_path.is_file():
                time.sleep(0.05)
            if not pid_path.is_file():
                raise AssertionError("child pid was not recorded before job close")
            child_pid = int(pid_path.read_text(encoding="utf-8").strip())
            kernel32.TerminateProcess(created.hProcess, 1)
            kernel32.CloseHandle(job)
            job = None
            time.sleep(0.6)
            return _alive(kernel32, child_pid)
        finally:
            if job:
                kernel32.TerminateProcess(created.hProcess, 1)
                kernel32.CloseHandle(job)
            kernel32.CloseHandle(created.hThread)
            kernel32.CloseHandle(created.hProcess)
    finally:
        holder.cleanup()


@unittest.skipUnless(os.name == "nt", "Windows job objects are not used on this platform")
class WindowsDetachedJobKillTests(unittest.TestCase):
    def test_default_flags_do_not_survive_kill_on_job_close(self) -> None:
        survived = _job_close_kills_child(breakaway=False)
        self.assertFalse(survived)

    def test_breakaway_opt_in_survives_kill_on_job_close(self) -> None:
        survived = _job_close_kills_child(breakaway=True)
        self.assertTrue(survived)


if __name__ == "__main__":
    unittest.main()
