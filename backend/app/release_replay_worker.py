"""One-shot isolated HWF replay of a website-requested candidate. Never DROP/retry.

Destination configuration is deployment-owned and separate from Task settings.
Raw logs are private local files; only checksums/counts enter the public proof.
"""
import argparse
import json
import os
from hashlib import sha256
from pathlib import Path
from threading import Event
from uuid import uuid4,UUID
from xml.etree import ElementTree as ET
import vertica_python
from psycopg.types.json import Jsonb
from .run_queue import RunQueue
from .repository import PostgresRepository
from . import release_store,release_files
from .release_candidate import assemble_release_candidate
from .formal_release_bundle import candidate_parts
from .release_bundle import MEMBERS
from .release_portability import validate_portability
from .delivery_context import load_delivery_context
from .source_staging import stage_csv_source,stage_csv_sources
from .source_binding import execution_sources
from .bound_result_query import load_bound_result_query,execute_bound_result_query
from .result_oracle import compare_oracle_document
from .result_reader import read_result_rows
from .expected_result import ResultColumn
from .hop_metadata import vertica_metadata_json
from .hop_command import hop_command
from .workflow_log_evidence import workflow_log_evidence
from .managed_process import run_managed
from .sa_contract import digest


def destination():
    if os.getenv('WORKBENCH_PORTABILITY_ENABLED')!='true':raise ValueError('PORTABILITY_DISABLED')
    config={'type':'VERTICA','host':os.environ['WORKBENCH_PORTABILITY_HOST'],
        'port':int(os.environ['WORKBENCH_PORTABILITY_PORT']),'database':os.environ['WORKBENCH_PORTABILITY_DATABASE'],
        'user':os.environ['WORKBENCH_PORTABILITY_USER'],'tlsmode':os.environ['WORKBENCH_PORTABILITY_TLSMODE']}
    vertica_metadata_json(config)  # Same strict allowlist as the original adapter.
    secret_file=Path(os.environ['WORKBENCH_PORTABILITY_PASSWORD_FILE'])
    if not secret_file.is_absolute() or secret_file.is_symlink():raise ValueError('PORTABILITY_SECRET_FILE_INVALID')
    secret=secret_file.read_text().rstrip('\r\n')
    if not secret or len(secret)>4096 or '\x00' in secret:raise ValueError('PORTABILITY_SECRET_UNAVAILABLE')
    return config,secret


def replay_context(queue,repo,conn,task_id,run_id,candidate_id,root):
    delivery=load_delivery_context(queue,task_id,run_id,connection=conn)
    release_store.require_lineage(conn,run_id,delivery['specification_checksum'])
    candidate=conn.execute('SELECT * FROM platform.release_candidate_record WHERE candidate_id=%s AND task_id=%s AND run_id=%s',
        (candidate_id,task_id,run_id)).fetchone()
    if not candidate or candidate['qa_binding_checksum']!=delivery['qa_binding_checksum']:raise ValueError('RELEASE_CANDIDATE_STALE')
    fresh=assemble_release_candidate(queue,task_id,run_id,candidate['sdm_id'],candidate['qa_binding_checksum'],repo=repo,root=root,connection=conn)
    content=release_files.read(root,candidate['project_id'],run_id,candidate_id,candidate['checksum'],candidate['file_size'])
    if content!=fresh['content']:raise ValueError('RELEASE_CANDIDATE_CHANGED')
    run=conn.execute('SELECT * FROM platform.task_run WHERE run_id=%s',(run_id,)).fetchone()
    return candidate,candidate_parts(content,candidate['manifest']),run,delivery['specification']


def replay(queue,repo,task_id,run_id,candidate_id,*,root=None):
    root=release_store.storage_root(root)
    target,secret=destination()
    # Pin query/oracle before claiming. This is a READ of the original run, not
    # permission to issue any writes against its connection.
    query,oracle=load_bound_result_query(queue,task_id,run_id)
    with queue.conn() as conn:
        candidate,parts,run,spec=replay_context(queue,repo,conn,task_id,run_id,candidate_id,root)
        source_config=run['input_snapshot']['source_config']
        source_binding=execution_sources(source_config,spec['version'])
        auth=conn.execute('SELECT binding FROM platform.task_run_execution_authorization WHERE run_id=%s',(run_id,)).fetchone()
        if not auth or any(auth['binding'].get(key)!=value for key,value in source_binding.items()):
            raise ValueError('PORTABILITY_EXECUTED_SOURCE_CHANGED')
        original=run['settings_snapshot']['connection']
        if all(str(target[k]).lower()==str(original[k]).lower() for k in ('host','port','database')):
            raise ValueError('PORTABILITY_SEPARATE_DESTINATION_REQUIRED')
        if spec['target_schema']!='ai_sample':raise ValueError('PORTABILITY_SAMPLE_SCHEMA_REQUIRED')
        check_id,token=uuid4(),uuid4()
        row=conn.execute('''INSERT INTO platform.release_portability_check(check_id,candidate_id,claim_token,status)
            VALUES(%s,%s,%s,'RUNNING') ON CONFLICT(candidate_id) DO NOTHING RETURNING check_id''',(check_id,candidate_id,token)).fetchone()
        if not row:return {'status':'ALREADY_CLAIMED_NO_RETRY'}
        queue.event(conn,run_id,'RELEASE_PORTABILITY_STARTED','RELEASE_VALIDATION',{'candidate_id':str(candidate_id),'check_id':str(check_id)})
    status='UNKNOWN';evidence={'version':1,'code':'PORTABILITY_INCOMPLETE_NO_RETRY'}
    config={key:target[key] for key in ('host','port','database','user','tlsmode')}
    config.update(password=secret,connection_timeout=10)
    try:
        sources=source_config['sources'];multi=spec['version']==2
        staging=(stage_csv_sources(run_id,source_config) if multi else
                 stage_csv_source(run_id,sources[0],source_config['csv_input_contract_v1']))
        with staging as staged:
            directory=staged['directory'];(directory/'hop').mkdir()
            for name,data in parts.items():
                with (directory/name).open('xb') as stream:stream.write(data)
            metadata=json.loads(vertica_metadata_json(target))
            metadata['workflow-run-configuration']=[{'name':'local','defaultSelection':False,'engineRunConfiguration':{'Local':{'safe_mode':False}}}]
            with (directory/'metadata.json').open('x') as stream:json.dump(metadata,stream)
            with vertica_python.connect(**config) as db:
                cursor=db.cursor()
                cursor.execute('SELECT 1 FROM v_catalog.tables WHERE table_schema=%s AND table_name=%s',('ai_sample',spec['target_table']))
                if cursor.fetchone() is not None:raise ValueError('PORTABILITY_DESTINATION_TABLE_EXISTS')
                cursor.execute('CREATE SCHEMA IF NOT EXISTS ai_sample')
                cursor.execute(parts[MEMBERS['DDL']].decode('utf-8'));db.commit()
            command=hop_command(directory.as_posix(),credential_launcher=True,source_count=2 if multi else 1)
            command=[('--file='+str(directory/MEMBERS['HWF'])) if arg.startswith('--file=') else arg for arg in command]
            environment={key:os.environ[key] for key in ('PATH','HOME','JAVA_HOME','LANG','LC_ALL') if key in os.environ}
            environment.update(HOP_HOME='/opt/hop',HOP_SHARED_JDBC_FOLDERS='/opt/hop/lib/jdbc',WORKBENCH_VERTICA_PASSWORD=secret)
            try:process=run_managed(command,cwd='/opt/hop',env=environment,cancelled=Event(),timeout_seconds=180)
            finally:environment.clear()
            # Unique exclusive filename and private mode; never included in ZIP.
            log_dir=Path(root)/'portability-private'/str(UUID(str(run_id)));log_dir.mkdir(parents=True,exist_ok=True)
            with os.fdopen(os.open(log_dir/(str(check_id)+'.log'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as stream:
                stream.write(process['output']);stream.flush();os.fsync(stream.fileno())
            nodes=[n.findtext('name') for n in ET.fromstring(parts[MEMBERS['HPL']]).findall('transform')]
            workflow_name=ET.fromstring(parts[MEMBERS['HWF']]).findtext('name')
            hop=workflow_log_evidence(process,nodes,workflow_name)
            if hop['result']['status']!='COMPLETED' or not hop['workflow_completed']:
                raise ValueError('PORTABILITY_HOP_NOT_COMPLETED')
            if any((directory/name).read_bytes()!=content for name,content in parts.items()):raise ValueError('PORTABILITY_ARTIFACT_CHANGED')
            source_paths=({ref:item['path'] for ref,item in staged['sources'].items()} if multi else {'source.0':staged['path']})
            for i,source in enumerate(sources):
                if sha256(source_paths[f'source.{i}'].read_bytes()).hexdigest()!=source['checksum']:
                    raise ValueError('PORTABILITY_SOURCE_CHANGED')
            document=json.loads(oracle['content'])
            with vertica_python.connect(**config) as db:
                cursor=db.cursor();execute_bound_result_query(cursor,query,oracle)
                rows=read_result_rows(cursor,[ResultColumn(**column) for column in document['columns']])
            comparison=compare_oracle_document(oracle['content'],rows,document_checksum=oracle['document_checksum'],
                specification_checksum=digest(spec),naming_checksum=spec['naming']['checksum'])
            if comparison['status']!='MATCH':raise ValueError('PORTABILITY_RESULT_MISMATCH')
            evidence=dict(version=2 if multi else 1,candidate_checksum=candidate['checksum'],**source_binding,
                hop_log_checksum=hop['result']['log_checksum'],result_expected_checksum=comparison['expected_checksum'],
                result_actual_checksum=comparison['actual_checksum'],expected_count=comparison['expected_count'],actual_count=comparison['actual_count'],
                exit_code=0,isolated_target_created=True,original_artifacts_unmodified=True,workflow_completed=hop['workflow_completed'],
                **{kind.lower()+'_checksum':sha256(parts[MEMBERS[kind]]).hexdigest() for kind in ('HPL','HWF','DDL')})
            validate_portability({'status':'PASS','evidence':evidence,'checksum':digest(evidence)},candidate,source_binding['source_checksum'],
                expected_checksum=comparison['expected_checksum'],expected_count=comparison['expected_count'],
                source_checksums=source_binding.get('source_checksums'))
            with queue.conn() as conn:
                current=replay_context(queue,repo,conn,task_id,run_id,candidate_id,root)
                if current[0]['checksum']!=candidate['checksum']:raise ValueError('PORTABILITY_UPSTREAM_CHANGED')
            status='PASS'
    except ValueError as error:
        # Only constant internal codes are safe. Driver exception text is never
        # written to public proof, as it may contain SQL/connection information.
        status='FAIL' if str(error) in ('PORTABILITY_DESTINATION_TABLE_EXISTS','PORTABILITY_RESULT_MISMATCH') else 'UNKNOWN'
        evidence={'version':1,'code':str(error) if str(error).startswith('PORTABILITY_') else 'PORTABILITY_CHECK_FAILED_NO_RETRY'}
    except Exception:
        status='UNKNOWN';evidence={'version':1,'code':'PORTABILITY_EXECUTION_FAILED_NO_RETRY'}
    finally:
        config.clear();secret=None
    with queue.conn() as conn:
        queue.locked_task(conn,task_id)
        updated=conn.execute('''UPDATE platform.release_portability_check SET status=%s,evidence=%s,checksum=%s,finished_at=clock_timestamp()
            WHERE check_id=%s AND claim_token=%s AND status='RUNNING' RETURNING check_id''',(status,Jsonb(evidence),digest(evidence),check_id,token)).fetchone()
        if not updated:raise ValueError('PORTABILITY_CLAIM_LOST')
        queue.event(conn,run_id,'RELEASE_PORTABILITY_FINISHED','RELEASE_VALIDATION',{'check_id':str(check_id),'status':status,'checksum':digest(evidence)})
    return {'status':status,'check_id':str(check_id),'checksum':digest(evidence),'release_ready':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--task-id',required=True);parser.add_argument('--run-id',required=True,type=UUID)
    parser.add_argument('--candidate-id',required=True,type=UUID);args=parser.parse_args()
    try:print(replay(RunQueue(os.environ['DATABASE_URL']),PostgresRepository(os.environ['DATABASE_URL']),args.task_id,args.run_id,args.candidate_id),flush=True)
    except Exception:raise SystemExit('PORTABILITY_NOT_STARTED_CHECK_CONFIGURATION_OR_CURRENT_APPROVAL') from None


if __name__=='__main__':main()
