"""Bound Windows child trees to a job; only processes created here can be terminated."""
import ctypes
from ctypes import wintypes
import os
import subprocess
import threading
import time

# Telemetry helpers the MSVC tools start in the background and leave running after a compile finished (vctip.exe
# lives on for minutes). They produce no part of a check result, so once the checked process itself has exited and
# only they are left in the job, the job is ended instead of waiting for them until the check's time limit.
DETACHED_HELPERS=('vctip.exe',)

# Own one process tree so successful completion includes all descendants.
class OwnedProcess:
    # Create the Windows job before allowing the child to execute.
    def __init__(self, command, **kwargs):
        self.job=None
        if os.name=='nt':
            self.api=ctypes.WinDLL('kernel32',use_last_error=True)
            self.api.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR]
            self.api.CreateJobObjectW.restype=wintypes.HANDLE
            self.api.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]
            self.api.QueryInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p]
            self.api.TerminateJobObject.argtypes=[wintypes.HANDLE,wintypes.UINT]
            self.api.CloseHandle.argtypes=[wintypes.HANDLE]
            self.job=self.api.CreateJobObjectW(None,None)
            if not self.job:
                raise ctypes.WinError(ctypes.get_last_error())
            self.api.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
            limits=ctypes.create_string_buffer(144 if ctypes.sizeof(ctypes.c_void_p)==8 else 112)
            ctypes.c_uint32.from_buffer(limits,16).value=0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not self.api.SetInformationJobObject(self.job,9,limits,len(limits)):
                self.api.CloseHandle(self.job)
                raise ctypes.WinError(ctypes.get_last_error())
            kwargs['creationflags']=kwargs.get('creationflags',0)|4
        try:
            self.process=subprocess.Popen(command,**kwargs)
        except BaseException:
            if self.job:
                self.api.CloseHandle(self.job)
            raise
        if self.job:
            if not self.api.AssignProcessToJobObject(self.job,int(self.process._handle)):
                self.process.kill(); self.process.wait(); self.api.CloseHandle(self.job)
                raise ctypes.WinError(ctypes.get_last_error())
            resume=ctypes.WinDLL('ntdll').NtResumeProcess
            resume.argtypes=[wintypes.HANDLE]
            if resume(int(self.process._handle))!=0:
                self.stop(); self.process.wait(); self.api.CloseHandle(self.job)
                raise RuntimeError('Cannot resume owned child')

    # Query the kernel's count rather than guessing completion from parent exit.
    def active(self):
        if not self.job:
            return int(self.process.poll() is None)
        data=ctypes.create_string_buffer(48)
        if not self.api.QueryInformationJobObject(self.job,1,data,len(data),None):
            raise ctypes.WinError(ctypes.get_last_error())
        return ctypes.c_uint32.from_buffer(data,40).value

    # Image names (lower case) of the processes still in the job; '?' for one whose name cannot be read.
    def job_process_names(self):
        if not self.job:
            return []
        data=ctypes.create_string_buffer(8+8*256)
        if not self.api.QueryInformationJobObject(self.job,3,data,len(data),None):
            raise ctypes.WinError(ctypes.get_last_error())
        count=ctypes.c_uint32.from_buffer(data,4).value
        self.api.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        self.api.OpenProcess.restype=wintypes.HANDLE
        self.api.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
        names=[]
        for index in range(min(count,256)):
            pid=ctypes.c_size_t.from_buffer(data,8+8*index).value
            handle=self.api.OpenProcess(0x1000,False,pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                names.append('?'); continue
            size=wintypes.DWORD(260); name=ctypes.create_unicode_buffer(260)
            ok=self.api.QueryFullProcessImageNameW(handle,0,name,ctypes.byref(size))
            self.api.CloseHandle(handle)
            names.append(os.path.basename(name.value).lower() if ok else '?')
        return names

    # True when the checked process has exited and only detached tool helpers (DETACHED_HELPERS) are left.
    def only_detached_helpers(self):
        if (self.process.poll() is None) or not self.job:
            return False
        names=self.job_process_names()
        return bool(names) and all(name in DETACHED_HELPERS for name in names)

    # Terminate only this newly-created job after its configured deadline.
    def stop(self):
        if self.job:
            if not self.api.TerminateJobObject(self.job,124):
                raise ctypes.WinError(ctypes.get_last_error())
        elif self.process.poll() is None:
            self.process.kill()

    # Collect all output and reap descendants before exposing any result or release marker. The output is read by a
    # thread in both modes (stream also forwards it at once), so that a detached helper holding the output pipe open
    # does not block the wait for the checked process.
    def collect(self, timeout, stream=False):
        start=time.monotonic(); timed_out=False
        chunks=[]
        output=''
        # Forward compile/deploy output immediately while retaining its complete durable result.
        def forward():
            for line in self.process.stdout:
                chunks.append(line)
                if stream:
                    print(line,end='',flush=True)
        reader=threading.Thread(target=forward) if self.process.stdout is not None else None
        if reader:
            reader.start()
        try:
            try:
                self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out=True; self.stop()
                self.process.wait()
            helpers_ended=False
            while self.active():
                if time.monotonic()-start>=timeout:
                    timed_out=True; self.stop()
                elif not helpers_ended and self.only_detached_helpers():
                    # The check itself is complete; its result and exit code are those of the checked process
                    helpers_ended=True; self.stop()
                threading.Event().wait(0.02)
            if reader:
                reader.join(timeout=5)
                if reader.is_alive():
                    raise RuntimeError('Owned output reader did not finish')
                output=''.join(chunks)
            code=self.process.returncode
            if timed_out:
                output='CHECK TIMEOUT; owned process exit='+str(code)+'; all descendants reaped\n'+output
            return code if code else (124 if timed_out else 0),output
        finally:
            if self.job:
                if self.active():
                    self.stop(); self.process.wait()
                self.api.CloseHandle(self.job)
