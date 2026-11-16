"""Owned Windows jobs for bounded helpers and child cleanup; no shell or ports."""
import ctypes as C
from ctypes import wintypes as W
import os,subprocess,time

class IO_COUNTERS(C.Structure):
    _fields_=[(name,C.c_ulonglong) for name in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
class BASIC_LIMITS(C.Structure):
    _fields_=[('PerProcessUserTimeLimit',C.c_longlong),('PerJobUserTimeLimit',C.c_longlong),('LimitFlags',W.DWORD),('MinimumWorkingSetSize',C.c_size_t),('MaximumWorkingSetSize',C.c_size_t),('ActiveProcessLimit',W.DWORD),('Affinity',C.c_size_t),('PriorityClass',W.DWORD),('SchedulingClass',W.DWORD)]
class EXTENDED_LIMITS(C.Structure):
    _fields_=[('BasicLimitInformation',BASIC_LIMITS),('IoInfo',IO_COUNTERS),('ProcessMemoryLimit',C.c_size_t),('JobMemoryLimit',C.c_size_t),('PeakProcessMemoryUsed',C.c_size_t),('PeakJobMemoryUsed',C.c_size_t)]
class STARTUPINFO(C.Structure):
    _fields_=[('cb',W.DWORD),('lpReserved',W.LPWSTR),('lpDesktop',W.LPWSTR),('lpTitle',W.LPWSTR),('dwX',W.DWORD),('dwY',W.DWORD),('dwXSize',W.DWORD),('dwYSize',W.DWORD),('dwXCountChars',W.DWORD),('dwYCountChars',W.DWORD),('dwFillAttribute',W.DWORD),('dwFlags',W.DWORD),('wShowWindow',W.WORD),('cbReserved2',W.WORD),('lpReserved2',C.POINTER(C.c_byte)),('hStdInput',W.HANDLE),('hStdOutput',W.HANDLE),('hStdError',W.HANDLE)]
class PROCESS_INFORMATION(C.Structure):
    _fields_=[('hProcess',W.HANDLE),('hThread',W.HANDLE),('dwProcessId',W.DWORD),('dwThreadId',W.DWORD)]

def api():
    if os.name!='nt':raise OSError('Windows process supervision requires Windows')
    k=C.WinDLL('kernel32',use_last_error=True)
    for name,args,result in [
        ('CreateJobObjectW',[C.c_void_p,W.LPCWSTR],W.HANDLE),('SetInformationJobObject',[W.HANDLE,C.c_int,C.c_void_p,W.DWORD],W.BOOL),
        ('AssignProcessToJobObject',[W.HANDLE,W.HANDLE],W.BOOL),('CloseHandle',[W.HANDLE],W.BOOL),('GetCurrentProcess',[],W.HANDLE),
        ('OpenProcess',[W.DWORD,W.BOOL,W.DWORD],W.HANDLE),('GetExitCodeProcess',[W.HANDLE,C.POINTER(W.DWORD)],W.BOOL),
        ('WaitForSingleObject',[W.HANDLE,W.DWORD],W.DWORD),('TerminateJobObject',[W.HANDLE,W.UINT],W.BOOL),
        ('TerminateProcess',[W.HANDLE,W.UINT],W.BOOL),('ResumeThread',[W.HANDLE],W.DWORD),
        ('CreateProcessW',[W.LPCWSTR,W.LPWSTR,C.c_void_p,C.c_void_p,W.BOOL,W.DWORD,C.c_void_p,W.LPCWSTR,C.POINTER(STARTUPINFO),C.POINTER(PROCESS_INFORMATION)],W.BOOL)]:
        f=getattr(k,name);f.argtypes=args;f.restype=result
    return k

def job(k,memory=1024*1024*1024,cpu_seconds=90,kill_on_close=True):
    handle=k.CreateJobObjectW(None,None)
    if not handle:raise OSError('Windows job creation failed')
    limits=EXTENDED_LIMITS();limits.BasicLimitInformation.LimitFlags=0x100|0x2|(0x2000 if kill_on_close else 0)
    limits.ProcessMemoryLimit=memory;limits.BasicLimitInformation.PerProcessUserTimeLimit=int(cpu_seconds*10_000_000)
    if not k.SetInformationJobObject(handle,9,C.byref(limits),C.sizeof(limits)):
        k.CloseHandle(handle);raise OSError('Windows job limits unavailable')
    return handle

_parser_job=None
def limit_current_process():
    global _parser_job
    k=api();handle=job(k,memory=768*1024*1024,cpu_seconds=90,kill_on_close=True)
    if not k.AssignProcessToJobObject(handle,k.GetCurrentProcess()):k.CloseHandle(handle);raise OSError('Windows parser job could not be assigned')
    _parser_job=(k,handle)

def pid_alive(pid):
    k=api();handle=k.OpenProcess(0x1000,False,int(pid))
    if not handle:return C.get_last_error()==5
    try:
        code=W.DWORD();return bool(k.GetExitCodeProcess(handle,C.byref(code))) and code.value==259
    finally:k.CloseHandle(handle)

class Child:
    """Create suspended, assign to owned job, then resume. Closing parent kills job."""
    def __init__(self,args,output):
        import msvcrt
        self.args=args;self.k=api();self.job=job(self.k);self.process=None
        startup=STARTUPINFO();startup.cb=C.sizeof(startup);startup.dwFlags=0x100;process=PROCESS_INFORMATION()
        try:
            with open(os.devnull,'r+b') as null:
                descriptors=(output.fileno(),null.fileno());previous=[os.get_inheritable(fd) for fd in descriptors]
                try:
                    for fd in descriptors:os.set_inheritable(fd,True)
                    startup.hStdInput=msvcrt.get_osfhandle(null.fileno());startup.hStdError=startup.hStdInput;startup.hStdOutput=msvcrt.get_osfhandle(output.fileno())
                    command=C.create_unicode_buffer(subprocess.list2cmdline([str(a) for a in args]))
                    if not self.k.CreateProcessW(str(args[0]),command,None,None,True,0x4|0x08000000,None,None,C.byref(startup),C.byref(process)):raise OSError('Windows engine could not start')
                finally:
                    for fd,value in zip(descriptors,previous):os.set_inheritable(fd,value)
            self.process=process.hProcess;self.pid=int(process.dwProcessId)
            if not self.k.AssignProcessToJobObject(self.job,self.process):raise OSError('Windows engine supervision could not be assigned')
            if self.k.ResumeThread(process.hThread)==0xffffffff:raise OSError('Windows engine could not resume')
        except BaseException:
            if process.hProcess:self.k.TerminateProcess(process.hProcess,1)
            self.close();raise
        finally:
            if process.hThread:self.k.CloseHandle(process.hThread)
    def poll(self):
        if self.k.WaitForSingleObject(self.process,0)==0x102:return None
        code=W.DWORD()
        if not self.k.GetExitCodeProcess(self.process,C.byref(code)):raise OSError('Windows engine status unavailable')
        return int(code.value)
    def wait(self,timeout=None):
        if self.k.WaitForSingleObject(self.process,0xffffffff if timeout is None else max(0,int(timeout*1000)))==0x102:raise subprocess.TimeoutExpired(self.args,timeout)
        return self.poll()
    def terminate(self):self.k.TerminateJobObject(self.job,1)
    kill=terminate
    def close(self):
        if self.job:self.k.CloseHandle(self.job);self.job=None
        if self.process:
            self.k.WaitForSingleObject(self.process,2000)
            self.k.CloseHandle(self.process);self.process=None
