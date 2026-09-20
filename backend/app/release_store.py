"""Persisted candidate, isolated replay gate, human approval and exact-byte download."""
import os
from uuid import uuid4
from hashlib import sha256
from psycopg.types.json import Jsonb
from . import release_files
from .release_candidate import assemble_release_candidate
from .delivery_context import load_delivery_context
from .release_portability import validate_portability
from .formal_release_bundle import candidate_parts,build_formal_bundle
from .sa_contract import digest
from .specification_store import context as specification_context
from .sdm_renderer import render_sdm_xlsx
from .release_bundle import BundleArtifact,MEMBERS
from .release_content_gate import check_release_content
from .release_secret_screen import run_forbidden_values
from .hop_dispatch import require_sa_trace
from .developer_journal import checked_trace
from .execution_oracle import load_execution_oracle
from .result_oracle import compare_oracle_document


def storage_root(root):
    value=root or os.getenv('WORKBENCH_ARTIFACT_ROOT')
    if not value:raise ValueError('RELEASE_STORAGE_NOT_CONFIGURED')
    return value


def require_lineage(conn,run_id,specification_checksum):
    job=conn.execute("SELECT * FROM platform.hop_dispatch_request WHERE run_id=%s AND status='COMPLETED' AND outcome_code='HOP_EXECUTED_QA_REQUIRED'",(run_id,)).fetchone()
    if not job:raise ValueError('RELEASE_WEBSITE_EXECUTION_REQUIRED')
    sa=conn.execute("SELECT * FROM platform.agent_invocation WHERE run_id=%s AND role='pilot_sa'",(run_id,)).fetchone()
    require_sa_trace(sa)
    dev=conn.execute("SELECT * FROM platform.agent_invocation WHERE run_id=%s AND role='pilot_developer'",(run_id,)).fetchone()
    if not dev or dev['status']!='VALIDATED_NOT_APPROVED':raise ValueError('RELEASE_DEVELOPER_REQUIRED')
    output=dev['output_json'];checked_trace(output['trace'],dev,output['proposal'])
    if (output['specification']['content_checksum']!=specification_checksum
            or str(sa['invocation_id'])!=job['binding']['sa_invocation_id']
            or str(dev['invocation_id'])!=job['binding']['developer_invocation_id']):raise ValueError('RELEASE_LINEAGE_CHANGED')


def prepare(queue,repo,task_id,run_id,qa_checksum,*,root=None):
    root=storage_root(root)
    with queue.conn() as conn:
        delivery=load_delivery_context(queue,task_id,run_id,connection=conn)
        if delivery['qa_binding_checksum']!=qa_checksum:raise ValueError('RELEASE_QA_VERSION_CONFLICT')
        require_lineage(conn,run_id,delivery['specification_checksum'])
        sdm=conn.execute('''SELECT s.* FROM platform.sdm_artifact s JOIN platform.sdm_qa_binding b USING(sdm_id)
            WHERE s.run_id=%s AND b.qa_approval_id=%s ORDER BY s.created_at DESC,s.sdm_id DESC LIMIT 1''',(run_id,delivery['qa_approval_id'])).fetchone()
        if not sdm:raise ValueError('RELEASE_QA_LINKED_SDM_REQUIRED')
        candidate=assemble_release_candidate(queue,task_id,run_id,sdm['sdm_id'],qa_checksum,repo=repo,root=root,connection=conn)
        row=conn.execute('SELECT * FROM platform.release_candidate_record WHERE run_id=%s AND checksum=%s AND qa_binding_checksum=%s',
            (run_id,candidate['checksum'],qa_checksum)).fetchone()
        if row:
            release_files.read(root,row['project_id'],run_id,row['candidate_id'],row['checksum'],row['file_size'])
        else:
            identity=uuid4();saved=release_files.save(root,delivery['project_id'],run_id,identity,candidate['content'])
            row=conn.execute('''INSERT INTO platform.release_candidate_record
                (candidate_id,run_id,task_id,project_id,sdm_id,qa_binding_checksum,checksum,file_size,manifest)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                (identity,run_id,task_id,delivery['project_id'],sdm['sdm_id'],qa_checksum,saved['checksum'],saved['file_size'],Jsonb(candidate['manifest']))).fetchone()
            queue.event(conn,run_id,'RELEASE_CANDIDATE_SAVED','RELEASE_VALIDATION',{'candidate_id':str(identity),'checksum':saved['checksum'],'release_ready':False})
    return {'candidate_id':str(row['candidate_id']),'checksum':row['checksum'],'status':'PORTABILITY_REQUIRED','release_ready':False}


def approval_offer(queue,repo,conn,task_id,run_id,candidate_id,*,root=None):
    delivery=load_delivery_context(queue,task_id,run_id,connection=conn)
    require_lineage(conn,run_id,delivery['specification_checksum'])
    candidate=conn.execute('SELECT * FROM platform.release_candidate_record WHERE candidate_id=%s AND run_id=%s AND task_id=%s',
        (candidate_id,run_id,task_id)).fetchone()
    if not candidate or candidate['qa_binding_checksum']!=delivery['qa_binding_checksum']:raise ValueError('RELEASE_CANDIDATE_STALE')
    auth=conn.execute('SELECT binding FROM platform.task_run_execution_authorization WHERE run_id=%s',(run_id,)).fetchone()['binding']
    proof=conn.execute('SELECT * FROM platform.release_portability_check WHERE candidate_id=%s',(candidate_id,)).fetchone()
    oracle=load_execution_oracle(queue,task_id,run_id,connection=conn)
    expected=compare_oracle_document(oracle['content'],[],document_checksum=oracle['document_checksum'],
        specification_checksum=auth['specification_checksum'],naming_checksum=delivery['specification']['naming']['checksum'])
    validate_portability(proof,candidate,auth['source_checksum'],
        expected_checksum=expected['expected_checksum'],expected_count=expected['expected_count'])
    sdm=conn.execute('SELECT checksum FROM platform.sdm_artifact WHERE sdm_id=%s',(candidate['sdm_id'],)).fetchone()
    fresh=assemble_release_candidate(queue,task_id,run_id,candidate['sdm_id'],candidate['qa_binding_checksum'],repo=repo,root=root,connection=conn)
    content=release_files.read(storage_root(root),candidate['project_id'],run_id,candidate_id,candidate['checksum'],candidate['file_size'])
    if fresh['content']!=content:raise ValueError('RELEASE_CANDIDATE_CHANGED')
    candidate_parts(content,candidate['manifest'])
    binding={'version':1,'run_id':str(run_id),'candidate_id':str(candidate_id),'candidate_checksum':candidate['checksum'],
        'specification_checksum':delivery['specification_checksum'],'qa_binding_checksum':delivery['qa_binding_checksum'],
        'source_sdm_checksum':sdm['checksum'],'portability_check_id':str(proof['check_id']),'portability_checksum':proof['checksum']}
    return {'binding':binding,'binding_checksum':digest(binding),'candidate':candidate,'content':content}


def approve(queue,repo,task_id,run_id,candidate_id,binding_checksum,confirmed,*,root=None):
    if confirmed is not True:raise ValueError('RELEASE_HUMAN_CONFIRMATION_REQUIRED')
    root=storage_root(root)
    with queue.conn() as conn:
        offer=approval_offer(queue,repo,conn,task_id,run_id,candidate_id,root=root)
        if offer['binding_checksum']!=binding_checksum:raise ValueError('RELEASE_APPROVAL_VERSION_CHANGED')
        old=conn.execute('SELECT * FROM platform.release_delivery WHERE candidate_id=%s',(candidate_id,)).fetchone()
        if old:
            if old['binding_checksum']!=binding_checksum:raise ValueError('RELEASE_APPROVAL_VERSION_CHANGED')
            release_files.read(root,offer['candidate']['project_id'],run_id,old['release_id'],old['checksum'],old['file_size'])
            return {'release_id':str(old['release_id']),'checksum':old['checksum'],'status':'RELEASE_READY','release_ready':True}
        run,naming=specification_context(queue,conn,task_id,run_id)
        spec=load_delivery_context(queue,task_id,run_id,connection=conn)['specification']
        doc_binding={key:offer['binding'][key] for key in ('version','run_id','specification_checksum','qa_binding_checksum','source_sdm_checksum','portability_checksum')}
        final_sdm=render_sdm_xlsx(spec,{**run,'write_started':False},naming,release_binding=doc_binding)['content']
        result=build_formal_bundle(offer['content'],offer['candidate']['manifest'],final_sdm,offer['binding'])
        parts=candidate_parts(result['content'],result['manifest'])
        artifacts=[BundleArtifact(kind,parts[name],sha256(parts[name]).hexdigest(),str(run_id),offer['binding']['specification_checksum'],naming['checksum']) for kind,name in MEMBERS.items()]
        with run_forbidden_values(repo,run['settings_snapshot']) as forbidden:check_release_content(artifacts,forbidden_values=forbidden)
        operator=conn.execute('SELECT operator_id FROM platform.operator_profile ORDER BY created_at,operator_id LIMIT 1').fetchone()
        if not operator:raise ValueError('OPERATOR_NOT_CONFIGURED')
        identity=uuid4();saved=release_files.save(root,run['project_id'],run_id,identity,result['content'])
        conn.execute('''INSERT INTO platform.release_delivery
            (release_id,candidate_id,check_id,operator_id,binding,binding_checksum,checksum,file_size,manifest)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''',(identity,candidate_id,offer['binding']['portability_check_id'],operator['operator_id'],
                Jsonb(offer['binding']),binding_checksum,saved['checksum'],saved['file_size'],Jsonb(result['manifest'])))
        queue.event(conn,run_id,'RELEASE_HUMAN_APPROVED','RELEASE_READY',{'release_id':str(identity),'binding_checksum':binding_checksum,'checksum':saved['checksum']})
    return {'release_id':str(identity),'checksum':saved['checksum'],'status':'RELEASE_READY','release_ready':True}


def download(queue,repo,task_id,run_id,release_id,*,root=None):
    with queue.conn() as conn:
        queue.locked_task(conn,task_id)
        row=conn.execute('''SELECT d.*,c.project_id FROM platform.release_delivery d
            JOIN platform.release_candidate_record c USING(candidate_id)
            WHERE d.release_id=%s AND c.task_id=%s AND c.run_id=%s''',(release_id,task_id,run_id)).fetchone()
        if not row:raise ValueError('RELEASE_NOT_FOUND')
        current=approval_offer(queue,repo,conn,task_id,run_id,row['candidate_id'],root=root)
        if row['binding']!=current['binding'] or row['binding_checksum']!=current['binding_checksum']:raise ValueError('RELEASE_APPROVAL_STALE')
        content=release_files.read(storage_root(root),row['project_id'],run_id,release_id,row['checksum'],row['file_size'])
        candidate_parts(content,row['manifest'])
        if row['manifest'].get('status')!='RELEASE_READY' or row['manifest'].get('approval_binding_checksum')!=row['binding_checksum']:
            raise ValueError('RELEASE_MANIFEST_CHANGED')
    return content


def status(queue,repo,task_id,run_id,*,root=None):
    """Public allowlist only; no paths, source data, credentials or raw errors."""
    with queue.conn() as conn:
        queue.locked_task(conn,task_id)
        if not conn.execute('SELECT 1 FROM platform.task_run WHERE task_id=%s AND run_id=%s',(task_id,run_id)).fetchone():
            raise ValueError('RUN_NOT_FOUND')
        result={'status':'PREREQUISITES_REQUIRED','release_ready':False,'candidate':None,'portability':None,'approval':None,'release':None}
        try:
            delivery=load_delivery_context(queue,task_id,run_id,connection=conn)
            require_lineage(conn,run_id,delivery['specification_checksum'])
        except ValueError:return result
        result.update(status='SDM_AND_CANDIDATE_REQUIRED',qa_binding_checksum=delivery['qa_binding_checksum'])
        row=conn.execute('''SELECT * FROM platform.release_candidate_record WHERE task_id=%s AND run_id=%s
            AND qa_binding_checksum=%s ORDER BY created_at DESC,candidate_id DESC LIMIT 1''',
            (task_id,run_id,delivery['qa_binding_checksum'])).fetchone()
        if not row:return result
        result['candidate']={'candidate_id':str(row['candidate_id']),'checksum':row['checksum'],'created_at':row['created_at']}
        proof=conn.execute('''SELECT *,started_at<clock_timestamp()-interval '10 minutes' AS overdue
            FROM platform.release_portability_check WHERE candidate_id=%s''',(row['candidate_id'],)).fetchone()
        result['status']='PORTABILITY_REQUIRED'
        if proof:
            result['portability']={'status':proof['status'],'checksum':proof['checksum'],'started_at':proof['started_at'],
                'finished_at':proof['finished_at'],'overdue':proof['status']=='RUNNING' and proof['overdue']}
        if not proof or proof['status']!='PASS':return result
        try:offer=approval_offer(queue,repo,conn,task_id,run_id,row['candidate_id'],root=root)
        except ValueError:
            result['status']='EVIDENCE_CHANGED';return result
        result.update(status='AWAITING_RELEASE_APPROVAL',approval={'binding':offer['binding'],'binding_checksum':offer['binding_checksum']})
        saved=conn.execute('SELECT * FROM platform.release_delivery WHERE candidate_id=%s',(row['candidate_id'],)).fetchone()
        if saved and saved['binding_checksum']==offer['binding_checksum']:
            try:release_files.read(storage_root(root),row['project_id'],run_id,saved['release_id'],saved['checksum'],saved['file_size'])
            except ValueError:
                result['status']='EVIDENCE_CHANGED';return result
            result.update(status='RELEASE_READY',release_ready=True,release={'release_id':str(saved['release_id']),
                'checksum':saved['checksum'],'file_size':saved['file_size'],'approved_at':saved['approved_at']})
        return result
