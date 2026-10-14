"""Windows Job Object with KILL_ON_JOB_CLOSE: every AI CLI process (and its children) dies when AATPO exits or
crashes, so a crash cannot leave a half-finished agent still editing files behind our back. Best effort:
if the job cannot be created/assigned (older Windows, nested-job restrictions) we simply carry on."""
from __future__ import annotations

import sys

_job = None
_failed = False


def _create():
    import ctypes
    from ctypes import wintypes as w

    k = ctypes.WinDLL("kernel32", use_last_error=True)

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                                      "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", w.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", w.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", w.DWORD), ("SchedulingClass", w.DWORD)]

    class EXTENDED(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO_COUNTERS), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    k.CreateJobObjectW.restype = w.HANDLE
    k.OpenProcess.restype = w.HANDLE
    h = k.CreateJobObjectW(None, None)
    if not h:
        raise OSError(ctypes.get_last_error())
    info = EXTENDED()
    info.BasicLimitInformation.LimitFlags = 0x2000   # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not k.SetInformationJobObject(w.HANDLE(h), 9, ctypes.byref(info), ctypes.sizeof(info)):   # 9 = ExtendedLimitInformation
        raise OSError(ctypes.get_last_error())
    return k, h


def assign(pid: int) -> bool:
    """Put a freshly spawned child into the kill-on-close job. Returns False if unavailable (never raises)."""
    global _job, _failed
    if sys.platform != "win32" or _failed:
        return False
    try:
        import ctypes
        from ctypes import wintypes as w
        if _job is None:
            _job = _create()
        k, h = _job
        proc = k.OpenProcess(0x0100 | 0x0001, False, pid)      # PROCESS_SET_QUOTA | PROCESS_TERMINATE
        if not proc:
            return False
        ok = bool(k.AssignProcessToJobObject(w.HANDLE(h), w.HANDLE(proc)))
        k.CloseHandle(w.HANDLE(proc))
        return ok
    except Exception:
        _failed = True
        return False
