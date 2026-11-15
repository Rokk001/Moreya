"""Bound Windows child trees to a job; only processes created here can be terminated."""
import ctypes
from ctypes import wintypes
import os
import subprocess
import threading
import time

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

    # Terminate only this newly-created job after its configured deadline.
    def stop(self):
        if self.job:
            if not self.api.TerminateJobObject(self.job,124):
                raise ctypes.WinError(ctypes.get_last_error())
        elif self.process.poll() is None:
            self.process.kill()

    # Collect all output and reap descendants before exposing any result or release marker.
    def collect(self, timeout, stream=False):
        start=time.monotonic(); timed_out=False
        chunks=[]
        # Forward compile/deploy output immediately while retaining its complete durable result.
        def forward():
            for line in self.process.stdout:
                chunks.append(line)
                print(line,end='',flush=True)
        reader=threading.Thread(target=forward) if stream else None
        if reader:
            reader.start()
        try:
            try:
                if stream:
                    self.process.wait(timeout=timeout)
                else:
                    output,_=self.process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out=True; self.stop()
                if stream:
                    self.process.wait()
                else:
                    output,_=self.process.communicate()
            while self.active():
                if time.monotonic()-start>=timeout:
                    timed_out=True; self.stop()
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
