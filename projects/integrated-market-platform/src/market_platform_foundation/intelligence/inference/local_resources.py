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
    empty={k:None for k in ('available_bytes','process_bytes','total_bytes','commit_total_bytes',
        'commit_available_bytes','memory_load_percent','process_commit_bytes','process_peak_bytes','process_peak_commit_bytes')}
    if os.name!="nt":
        return empty
    class Memory(ctypes.Structure):
        _fields_=[("length",wintypes.DWORD),("load",wintypes.DWORD)]+[(n,ctypes.c_ulonglong) for n in
            ("total","available","page_total","page_available","virtual_total","virtual_available","extended")]
    state=Memory()
    state.length=ctypes.sizeof(state)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
        return empty
    rss=committed=peak=peak_commit=None
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
            committed=int(counters.page)
            peak=int(counters.peak)
            peak_commit=int(counters.peak_page)
    return {"available_bytes":int(state.available),"process_bytes":rss,'total_bytes':int(state.total),
        'commit_total_bytes':int(state.page_total),'commit_available_bytes':int(state.page_available),
        'memory_load_percent':int(state.load),'process_commit_bytes':committed,
        'process_peak_bytes':peak,'process_peak_commit_bytes':peak_commit}

class ResourceMonitor:
    def __init__(self,server,should_stop=lambda:False,deadline=None):
        self.server=server
        self.should_stop=should_stop
        self.deadline=deadline
        self.end=threading.Event()
        self.failure=None
        self.peak_bytes=0
        self.peak_commit_bytes=0
        self.samples=[]
        self.thread=None
        self.closed=False
    def check(self):
        sample=memory_sample(getattr(self.server,"_process",None))
        self.peak_bytes=max(self.peak_bytes,sample.get('process_peak_bytes') or sample["process_bytes"] or 0)
        self.last_sample=sample
        self.peak_commit_bytes=max(self.peak_commit_bytes,sample.get('process_peak_commit_bytes') or sample.get('process_commit_bytes') or 0)
        if len(self.samples)<32: self.samples.append(sample)
        if sample["process_bytes"] is not None and sample["process_bytes"]>MAX_PROCESS_BYTES:
            self.failure="LOCAL_RESOURCE_MEMORY_LIMIT"
        elif sample["available_bytes"] is not None and sample["available_bytes"]<MIN_AVAILABLE_BYTES:
            self.failure="LOCAL_RESOURCE_INSUFFICIENT_MEMORY"
        elif sample.get('process_commit_bytes') is not None and sample['process_commit_bytes']>MAX_PROCESS_BYTES:
            self.failure='LOCAL_RESOURCE_COMMIT_LIMIT'
        elif sample.get('commit_available_bytes') is not None and sample['commit_available_bytes']<MIN_AVAILABLE_BYTES:
            self.failure='LOCAL_RESOURCE_COMMIT_HEADROOM'
        elif sample['available_bytes'] is None or sample.get('commit_available_bytes') is None:
            self.failure='LOCAL_RESOURCE_TELEMETRY_UNAVAILABLE'
        elif getattr(self.server,'_process',None) is not None and self.server._process.poll() is None and (
                sample['process_bytes'] is None or sample.get('process_commit_bytes') is None):
            self.failure='LOCAL_RESOURCE_TELEMETRY_UNAVAILABLE'
        elif self.should_stop():
            self.failure='STOPPED_BY_OPERATOR'
        elif self.deadline is not None:
            import time
            if time.monotonic()>=self.deadline:self.failure='LOCAL_MODEL_TIMEOUT'
        return self.failure
    def start(self):
        self.check()
        def watch():
            while not self.end.wait(.25):
                if self.check():
                    # Only a process owned by this server object may be terminated.
                    process=getattr(self.server,'_process',None)
                    if process is not None and process.poll() is None:
                        try: process.terminate()
                        except OSError: pass
                    return
        self.thread=threading.Thread(target=watch,name="local-inference-memory",daemon=True)
        self.thread.start()
    def close(self):
        if self.closed:return
        self.end.set()
        if self.thread: self.thread.join(timeout=2)
        self.check()
        self.closed=True
