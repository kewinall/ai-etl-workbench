"""Opt-in disposable DB probe, not platform QA approval or release evidence.

Fixed portability-only destination, fresh tables, no DROP/TRUNCATE. Never load
platform PostgreSQL/AI configuration or accept arbitrary connection arguments.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from uuid import uuid4
from xml.etree import ElementTree as ET
import vertica_python
from app.delivery_compiler import compile_delivery_components
from app.hop_command import hop_command
from app.hop_metadata import vertica_metadata_json
from app.hop_log_evidence import hop_log_evidence
from test_join_semantics import join_design


def main():
    if os.getenv('WORKBENCH_DISPOSABLE_WIDTH_PROBE')!='1':
        raise SystemExit('EXPLICIT_DISPOSABLE_TEST_REQUIRED')
    secret=Path('/run/portability-secrets/password').read_text().strip()
    connection=dict(type='VERTICA',host='portability-vertica',port=5433,
                    database='WorkbenchPortable',user='dbadmin',tlsmode='disable')
    config={k:v for k,v in connection.items() if k!='type'}
    config.update(password=secret,connection_timeout=10)
    with vertica_python.connect(**config) as db:
        cur=db.cursor();cur.execute('SELECT VERSION()');version=cur.fetchone()[0]
        cur.execute('CREATE SCHEMA IF NOT EXISTS ai_sample')
    for case,value,should_fail in [('ascii32','x'*32,False),('ascii33','x'*33,True),('utf8_33','界'*11,True)]:
        name='qa_width_'+uuid4().hex
        spec,run,naming=join_design()
        spec.update(target_schema='ai_sample',target_table=name)
        run['input_snapshot']['target_config'].update(schema='ai_sample',table=name)
        compiled=compile_delivery_components(spec,run,naming)
        assert compiled['status']=='VALIDATED_NOT_APPROVED'
        with vertica_python.connect(**config) as db:
            cur=db.cursor();cur.execute(compiled['ddl']);db.commit()
        with tempfile.TemporaryDirectory(prefix='width-probe-') as root:
            directory=Path(root)
            (directory/'candidate.hpl').write_text(compiled['hpl'],encoding='utf-8')
            (directory/'metadata.json').write_text(vertica_metadata_json(connection),encoding='utf-8')
            # Exercise the discard branch too; zero-row Hop nodes omit BASIC
            # summaries and are separately tracked as an evidence-reader gap.
            for i,text in enumerate(('客戶編號,名稱\nA,'+value+'\n','客戶編號|名稱\nA|right\n|null_right\n')):
                source=directory/f'source-{i}';source.mkdir()
                (source/'source.csv').write_text(text,encoding='utf-8')
            environment={key:os.environ[key] for key in ('PATH','HOME','JAVA_HOME','LANG') if key in os.environ}
            environment.update(WORKBENCH_VERTICA_PASSWORD=secret,HOP_HOME='/opt/hop',HOP_SHARED_JDBC_FOLDERS='/opt/hop/lib/jdbc')
            result=subprocess.run(hop_command(root,credential_launcher=True,source_count=2),
                cwd='/opt/hop',capture_output=True,env=environment,timeout=60)
            environment.clear()
            nodes=[node.findtext('name') for node in ET.fromstring(compiled['hpl']).findall('transform')]
            evidence=hop_log_evidence(dict(started=True,reason='EXITED',exit_code=result.returncode,
                output=result.stdout+result.stderr),nodes)
        # Fresh session verifies committed values, not an engine-side buffer.
        with vertica_python.connect(**config) as db:
            cur=db.cursor();cur.execute(f'SELECT left_value FROM "ai_sample"."{name}"');rows=cur.fetchall()
        failed=evidence['result']['status']=='FAILED'
        ok=(failed and rows==[]) if should_fail else (evidence['result']['status']=='COMPLETED' and rows==[[value]])
        # Only synthetic table identifier, hashes and counts; never raw driver/Hop logs.
        print(json.dumps(dict(case=case,passed=ok,version=version,table=name,
            result=evidence['result'],persisted_rows=len(rows),synthetic_only=True,release_ready=False)),flush=True)
        if not ok:
            print(json.dumps({'expected_nodes':nodes,'observed_nodes':evidence['nodes'],
                'processing_lines':[line for line in (result.stdout+result.stderr).decode('utf-8',errors='replace').splitlines() if 'Finished processing (' in line]}),flush=True)
            raise SystemExit('WIDTH_PROBE_EXPECTATION_FAILED_NO_RETRY')
    config.clear();secret=None


if __name__=='__main__':main()
