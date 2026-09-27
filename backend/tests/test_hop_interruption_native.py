"""Real in-flight Hop cancellation with Dummy sink; not Vertica write recovery."""
import os
from pathlib import Path
import subprocess
from xml.etree.ElementTree import fromstring, tostring
import pytest
from app.hpl_compiler import compile_hpl
from test_source_order_compilation import ordered_design
from test_join_native import wsl_path

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_NATIVE_INTERRUPTION_TEST') != '1',
    reason='Explicit isolated in-flight Hop cancellation probe required')


def test_running_hop_cancelled_without_success_or_retry(tmp_path):
    root = fromstring(compile_hpl(*ordered_design())['hpl'])
    root.find("./transform[name='source']/filename").text = '/candidate/input.csv'
    target = root.find("./transform[name='target']")
    for child in list(target):
        if child.tag not in ('name', 'type', 'copies', 'distribute', 'GUI'):
            target.remove(child)
    target.find('type').text = 'Dummy'
    (tmp_path/'candidate.hpl').write_bytes(tostring(root, encoding='utf-8'))
    (tmp_path/'input.csv').write_text('類別,金額\nZ,30\nA,10\n', encoding='utf-8')
    repo = Path(__file__).resolve().parents[2]
    script = '''
import os,time,json
from pathlib import Path
from threading import Event,Thread
from app.managed_process import run_managed
from app.hop_log_evidence import hop_log_evidence
cancel=Event(); stop=Event(); observed=Event()
marker=Path('/tmp/hop-interruption-ready')
assert not marker.exists()
def watch():
    while not stop.wait(.02):
        if marker.exists():
            observed.set(); cancel.set(); return
thread=Thread(target=watch); thread.start()
try:
    result=run_managed(['java','-cp','lib/core/*:lib/beam/*:lib/swt/linux/x86_64/*',
        '/validation/ExecuteSourceOrderProbe.java','--interrupt-probe'],
        cwd='/opt/hop',env=os.environ.copy(),cancelled=cancel,timeout_seconds=45)
finally:
    stop.set(); thread.join(2)
assert observed.is_set(), 'No in-flight Hop row was observed'
assert result['reason']=='CANCELLED' and result['exit_code']<0
assert b'SOURCE_ORDER_COLLECTED' not in result['output']
evidence=hop_log_evidence(result,['source','target'])
assert evidence['result']['status']=='UNKNOWN' and not evidence['qa_passed']
print('INFLIGHT_HOP_CANCEL_PASS database=false release=false')
'''
    command = ['wsl','-d','RockyLinux9','-u','root','--','docker','run','--rm',
        '--pull','never','--network','none','--hostname','hop-validation',
        '--add-host','hop-validation:127.0.0.1','--entrypoint','python',
        '-v',wsl_path(repo/'backend')+':/app/backend:ro',
        '-v',wsl_path(repo/'scripts/hop')+':/validation:ro',
        '-v',wsl_path(tmp_path)+':/candidate:ro',
        'ai-etl-workbench-worker:dev','-c',script]
    result = subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=75)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'INFLIGHT_HOP_CANCEL_PASS database=false release=false' in result.stdout
