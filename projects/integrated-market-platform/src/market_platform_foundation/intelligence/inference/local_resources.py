"""Bounded local inference resources, shared across local synthesis and qualification."""
from __future__ import annotations
import ctypes
import os
import threading
from ctypes import wintypes

SLOT=threading.BoundedSemaphore(1)
ADMISSION=threading.BoundedSemaphore(2)  # one running, at most one waiting
GIB=1024**3
MAX_PROCESS_BYTES=6*GIB
MIN_AVAILABLE_BYTES=4*GIB

def memory_sample(process=None):
    if os.name!="nt":
        return {"available_bytes":None,"process_bytes":None}
    class Memory(ctypes.Structure):
        _fields_=[("length",wintypes.DWORD),("load",wintypes.DWORD)]+[(n,ctypes.c_ulonglong) for n in
            ("total","available","page_total","page_available","virtual_total","virtual_available","extended")]
    state=Memory()
    state.length=ctypes.sizeof(state)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
        return {"available_bytes":None,"process_bytes":None}
    rss=None
    if process is not None and process.poll() is None:
        class Counters(ctypes.Structure):
            _fields_=[("cb",wintypes.DWORD),("faults",wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in
                ("peak","working","quota_peak_paged","quota_paged","quota_peak_nonpaged","quota_nonpaged","page","peak_page")]
        counters=Counters()
        counters.cb=ctypes.sizeof(counters)
        query=ctypes.windll.psapi.GetProcessMemoryInfo
        query.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD]
        if query(wintypes.HANDLE(int(process._handle)),ctypes.byref(counters),counters.cb):
            rss=int(counters.working)
    return {"available_bytes":int(state.available),"process_bytes":rss}

class ResourceMonitor:
    def __init__(self,server):
        self.server=server
        self.end=threading.Event()
        self.failure=None
        self.peak_bytes=0
        self.thread=None
    def check(self):
        sample=memory_sample(getattr(self.server,"_process",None))
        self.peak_bytes=max(self.peak_bytes,sample["process_bytes"] or 0)
        if sample["process_bytes"] is not None and sample["process_bytes"]>MAX_PROCESS_BYTES:
            self.failure="LOCAL_RESOURCE_MEMORY_LIMIT"
        elif sample["available_bytes"] is not None and sample["available_bytes"]<MIN_AVAILABLE_BYTES:
            self.failure="LOCAL_RESOURCE_INSUFFICIENT_MEMORY"
        return self.failure
    def start(self):
        self.check()
        def watch():
            while not self.end.wait(.25):
                if self.check():
                    # Only a process owned by this server object may be terminated.
                    process=getattr(self.server,'_process',None)
                    if process is not None and process.poll() is None: process.terminate()
                    return
        self.thread=threading.Thread(target=watch,name="local-inference-memory",daemon=True)
        self.thread.start()
    def close(self):
        self.end.set()
        if self.thread: self.thread.join(timeout=2)
        self.check()
