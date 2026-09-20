"""Private POSIX process lifecycle for the Docker Hop adapter; no shell API.

Commands and environment must come from a trusted adapter, never HTTP input.
Output is private/unredacted and MUST NOT be returned by an API or released.
"""
import os
import signal
import subprocess
import time
import select
from threading import Event, Thread


def run_managed(argv, *, cwd, env, cancelled, timeout_seconds=180, max_output_bytes=1024*1024):
    if os.name != 'posix':
        raise ValueError('POSIX_EXECUTION_REQUIRED')
    if not isinstance(argv, list) or not argv or any(not isinstance(v,str) or '\x00' in v for v in argv):
        raise ValueError('INVALID_PROCESS_COMMAND')
    if type(timeout_seconds) not in (int,float) or not 0 < timeout_seconds <= 3600:
        raise ValueError('INVALID_PROCESS_TIMEOUT')
    if type(max_output_bytes) is not int or not 1 <= max_output_bytes <= 10*1024*1024:
        raise ValueError('INVALID_PROCESS_OUTPUT_LIMIT')
    if cancelled.is_set():
        return {'started':False,'reason':'CANCELLED','exit_code':None,'output':b''}
    output=bytearray()
    overflow,read_error,reader_stop,output_closed=Event(),Event(),Event(),Event()
    process=subprocess.Popen(argv,cwd=cwd,env=env,stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                             start_new_session=True,shell=False)
    def kill_group():
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
    def read_output():
        try:
            descriptor=process.stdout.fileno()
            os.set_blocking(descriptor,False)
            while not reader_stop.is_set():
                if not select.select([descriptor],[],[],0.05)[0]:
                    continue
                try: chunk=os.read(descriptor,65536)
                except BlockingIOError: continue
                if not chunk:
                    output_closed.set()
                    return
                remaining=max_output_bytes-len(output)
                output.extend(chunk[:remaining])
                if len(chunk)>remaining:
                    overflow.set()
                    kill_group()
        except Exception:
            read_error.set()
            kill_group()
    reader=Thread(target=read_output,daemon=True)
    reason='EXITED'
    deadline=time.monotonic()+timeout_seconds
    try:
        reader.start()
        while process.poll() is None:
            if cancelled.is_set(): reason='CANCELLED';break
            if time.monotonic()>=deadline: reason='TIMEOUT';break
            if overflow.is_set(): reason='OUTPUT_LIMIT';break
            if read_error.is_set(): reason='OUTPUT_READ_FAILED';break
            cancelled.wait(0.05)
    finally:
        # A descendant can escape its process group. Deployment still needs a
        # container boundary; do not block forever on an inherited output pipe.
        kill_group()
        process.wait()
        if reader.ident is not None:
            reader.join(timeout=0.5)
            reader_stop.set()
            reader.join()
        process.stdout.close()
    if overflow.is_set(): reason='OUTPUT_LIMIT'
    elif read_error.is_set(): reason='OUTPUT_READ_FAILED'
    elif not output_closed.is_set(): reason='OUTPUT_NOT_CLOSED'
    return {'started':True,'reason':reason,'exit_code':process.returncode,'output':bytes(output)}
