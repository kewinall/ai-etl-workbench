"""Opt-in primitive: real Hop partial commit, separate SQL observation, cancellation.

Uses only the dedicated portability DB, creates a unique synthetic table, never
drops/reuses it. Does not create platform approvals, call AI, or certify a Run.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4
from xml.etree.ElementTree import fromstring

import vertica_python
from app.delivery_compiler import compile_delivery_components
from app.hop_metadata import vertica_metadata_json
from app.managed_process import run_managed
from app.hop_log_evidence import hop_log_evidence
from test_source_order_compilation import ordered_design


def main():
    scope = 'dedicated-portability-database-v1'
    if os.getenv('WORKBENCH_PARTIAL_WRITE_PROBE') != scope:
        raise ValueError('Explicit isolated probe required')
    folder = Path('/candidate')
    if any(folder.iterdir()):
        raise ValueError('Fresh private candidate directory required')
    secret = Path('/run/portability-secrets/password').read_text().strip()
    config = dict(host='portability-vertica', port=5433, database='WorkbenchPortable',
                  user='dbadmin', password=secret, tlsmode='disable', connection_timeout=10)
    table = 'interrupt_' + uuid4().hex
    spec, run, naming = ordered_design()
    spec['target_table'] = table
    run['input_snapshot']['target_config']['table'] = table
    compiled = compile_delivery_components(spec, run, naming)
    assert 'ddl' in compiled and not compiled['qa_passed'] and not compiled['release_ready']
    root = fromstring(compiled['hpl'])
    target = root.find("./transform[name='target']")
    assert target.findtext('commit') == '1000' and target.findtext('truncate') == 'N'
    metadata = vertica_metadata_json({key: value for key, value in config.items() if key not in ('password','connection_timeout')} | {'type':'VERTICA'})
    (folder/'metadata.json').write_text(metadata)
    (folder/'candidate.hpl').write_text(compiled['hpl'])
    (folder/'input.csv').write_text('類別,金額\n' + ''.join(f'R{i:04d},1.00\n' for i in range(1,2001)), encoding='utf-8')
    report = dict(scope='NATIVE_HOP_PARTIAL_COMMIT_NOT_PLATFORM_QUEUE', table=table,
                  rows_requested=2000, status='PREPARED_NOT_VERIFIED', qa_passed=False, release_ready=False)
    (folder/'probe.json').write_text(json.dumps(report))
    with vertica_python.connect(**config) as db:
        cursor = db.cursor()
        cursor.execute('SELECT version()')
        version = cursor.fetchone()[0]
        assert '25.3' in version
        cursor.execute('CREATE SCHEMA IF NOT EXISTS ai_sample')
        cursor.execute(compiled['ddl'])
        db.commit()
    cancelled, finished, observed = Event(), Event(), Event()
    failures, counts = [], []
    def watch():
        while not finished.wait(.1):
            if not (folder/'partial-ready').exists():
                continue
            try:
                # A new independent connection proves visibility outside Hop's transaction.
                with vertica_python.connect(**config) as db:
                    cursor = db.cursor()
                    cursor.execute(f'SELECT COUNT(*) FROM "ai_sample"."{table}"')
                    count = cursor.fetchone()[0]
                counts.append(count)
                if count == 1000:
                    observed.set()
                    cancelled.set()
                    return
            except Exception as error:
                failures.append(type(error).__name__)
                cancelled.set()
                return
    thread = Thread(target=watch)
    thread.start()
    environment = {key: os.environ[key] for key in ('PATH','HOME','LANG','HOP_HOME') if key in os.environ}
    environment.update(WORKBENCH_PARTIAL_WRITE_PROBE=scope, WORKBENCH_VERTICA_PASSWORD=secret)
    try:
        result = run_managed(['java','-cp','lib/core/*:lib/beam/*:lib/swt/linux/x86_64/*:lib/jdbc/vertica-jdbc.jar',
                              '/validation/ExecutePartialWriteProbe.java'], cwd='/opt/hop',
                             env=environment, cancelled=cancelled, timeout_seconds=45)
    finally:
        finished.set()
        thread.join(15)
        environment.clear()
    # Retain private sanitized evidence even when the probe fails.
    result['output'] = result['output'].replace(secret.encode(), b'<REDACTED>')
    (folder/'hop.log').write_bytes(result['output'])
    report.update(status='FAILED', reason=result['reason'], exit_code=result['exit_code'], observed_counts=counts,
                  log_checksum=sha256(result['output']).hexdigest(), observer_errors=failures)
    (folder/'probe.json').write_text(json.dumps(report))
    assert not thread.is_alive() and not failures and observed.is_set()
    assert result['reason'] == 'CANCELLED' and result['exit_code'] < 0
    evidence = hop_log_evidence(result, [node.findtext('name') for node in root.findall('transform')])
    assert evidence['result']['status'] == 'UNKNOWN' and not evidence['qa_passed']
    with vertica_python.connect(**config) as db:
        cursor = db.cursor()
        cursor.execute(f'SELECT COUNT(*), COUNT(DISTINCT source_position), MIN(source_position), MAX(source_position), SUM(source_position) FROM "ai_sample"."{table}"')
        actual = list(cursor.fetchone())
    assert actual == [1000,1000,1,1000,500500], actual
    report.update(status='PASS', persisted_rows=1000, duplicates=0,
                  execution_status='UNKNOWN', etl_replayed=False, vertica_version=version)
    (folder/'probe.json').write_text(json.dumps(report))
    print(json.dumps({key: report[key] for key in ('status','scope','persisted_rows','rows_requested','execution_status','qa_passed','release_ready','etl_replayed')}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status':'FAILED','error_type':type(error).__name__,
                          'detail':'Retain private probe evidence; no retry or cleanup was performed'}))
        raise SystemExit(1)
