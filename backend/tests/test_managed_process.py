"""Real local child processes, no Hop, database, model or network."""
import os
import sys
import time
import signal
from threading import Event, Timer
import pytest
from app.managed_process import run_managed

pytestmark=pytest.mark.skipif(os.name!='posix',reason='Docker POSIX process lifecycle')


def run(tmp_path,script,**kwargs):
    return run_managed([sys.executable,'-c',script],cwd=tmp_path,env={'PATH':os.environ.get('PATH','')},
                       cancelled=kwargs.pop('cancelled',Event()),**kwargs)


def test_normal_and_failed_exit(tmp_path):
    result=run(tmp_path,"print('hello')")
    assert result['reason']=='EXITED' and result['exit_code']==0 and result['output']==b'hello\n'
    assert run(tmp_path,'raise SystemExit(7)')['exit_code']==7


def test_timeout_terminates_process(tmp_path):
    result=run(tmp_path,'import time;time.sleep(30)',timeout_seconds=.15)
    assert result['reason']=='TIMEOUT' and result['exit_code']<0


def test_cancel_before_and_during_start(tmp_path):
    cancel=Event();cancel.set()
    assert run(tmp_path,'raise Exception()',cancelled=cancel)['started'] is False
    cancel.clear()
    timer=Timer(.15,cancel.set);timer.start()
    try:
        result=run(tmp_path,'import time;time.sleep(30)',cancelled=cancel)
        assert result['reason']=='CANCELLED' and result['exit_code']<0
    finally:timer.join()


def test_output_limit_is_bounded(tmp_path):
    result=run(tmp_path,"import sys;sys.stdout.write('x'*200000)",max_output_bytes=1000)
    assert result['reason']=='OUTPUT_LIMIT' and len(result['output'])==1000


def test_descendant_cannot_keep_pipe_open(tmp_path):
    result=run(tmp_path,"import subprocess,sys;subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);print('parent done')",timeout_seconds=2)
    assert result['reason']=='EXITED' and b'parent done' in result['output']


def test_escaped_descendant_does_not_hang_reader(tmp_path):
    started=time.monotonic()
    result=run(tmp_path,"import subprocess,sys;child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)'],start_new_session=True);print(child.pid,flush=True)",timeout_seconds=2)
    pid=int(result['output'].strip())
    try:
        assert result['reason']=='OUTPUT_NOT_CLOSED'
        assert time.monotonic()-started<3
    finally:
        # Only the exact synthetic child created above, never a discovered PID.
        try:os.kill(pid,signal.SIGKILL)
        except ProcessLookupError:pass
