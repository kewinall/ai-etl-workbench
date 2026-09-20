"""Version-bound candidate storage; never grants QA or release approval."""
import os
from uuid import uuid4

from .approved_candidate import load_approved_candidate
from .sdm_files import save_sdm_bytes, read_sdm_bytes
from .sdm_renderer import render_sdm_xlsx


def public_metadata(row):
    return {**{key: value for key, value in row.items() if key != 'file_path'},
            'qa_passed': False, 'release_ready': False}


def candidate_history(queue, task_id, run_id):
    with queue.conn() as conn:
        if not conn.execute('SELECT 1 FROM platform.task_run WHERE task_id=%s AND run_id=%s', (task_id, run_id)).fetchone():
            raise ValueError('SDM_NOT_FOUND')
        rows = conn.execute('''SELECT * FROM platform.sdm_artifact WHERE task_id=%s AND run_id=%s
            AND status='CANDIDATE_NOT_RELEASED' ORDER BY created_at DESC,sdm_id DESC''',
            (task_id, run_id)).fetchall()
    return {'items': [public_metadata(row) for row in rows], 'release_ready': False}


def _root(root):
    value = root if root is not None else os.environ.get('WORKBENCH_ARTIFACT_ROOT')
    if not value:
        raise ValueError('SDM_STORAGE_NOT_CONFIGURED')
    return value


def download_candidate(queue, task_id, run_id, sdm_id, *, root=None):
    with queue.conn() as conn:
        row = conn.execute('''SELECT * FROM platform.sdm_artifact
            WHERE task_id=%s AND run_id=%s AND sdm_id=%s
            AND status='CANDIDATE_NOT_RELEASED' ''', (task_id, run_id, sdm_id)).fetchone()
        if not row:
            raise ValueError('SDM_NOT_FOUND')
        content = read_sdm_bytes(_root(root), row['project_id'], run_id, sdm_id,
                                checksum=row['checksum'], file_size=row['file_size'])
    return public_metadata(row), content


def save_candidate(queue, task_id, run_id, specification_id, expected_checksum, *, root=None):
    return _save_candidate(queue,task_id,run_id,specification_id,expected_checksum,
        root=root,loader=load_approved_candidate)


def save_delivery_candidate(queue,task_id,run_id,specification_id,expected_checksum,expected_qa_checksum,*,root=None,connection=None):
    from .delivery_context import load_delivery_context
    from .specification_store import context
    from .hpl_compiler import compile_hpl
    def loader(q,conn,task,run,spec_id):
        delivery=load_delivery_context(q,task,run,connection=conn)
        if delivery['qa_binding_checksum']!=expected_qa_checksum:
            raise ValueError('SDM_QA_VERSION_CONFLICT')
        if delivery['specification_id']!=str(spec_id):raise ValueError('SDM_SPECIFICATION_CHANGED')
        actual,naming=context(q,conn,task,run)
        # Renderer/spec validation is read-only; never reset persisted write_started.
        document_run={**actual,'write_started':False}
        compiled=compile_hpl(delivery['specification'],document_run,naming)
        if compiled['status']!='VALIDATED_NOT_APPROVED' or compiled['specification_checksum']!=expected_checksum:
            raise ValueError('SDM_SPECIFICATION_CHANGED')
        approval=conn.execute('SELECT approval_id,content_checksum FROM platform.specification_approval WHERE specification_id=%s FOR SHARE',(spec_id,)).fetchone()
        if not approval or approval['content_checksum']!=expected_checksum:raise ValueError('SPECIFICATION_APPROVAL_REQUIRED')
        return {'run':document_run,'compiled':compiled,'specification_checksum':expected_checksum,'approval_id':str(approval['approval_id'])}
    return _save_candidate(queue,task_id,run_id,specification_id,expected_checksum,root=root,loader=loader,connection=connection)


def _save_candidate(queue,task_id,run_id,specification_id,expected_checksum,*,root,loader,connection=None):
    storage_root = _root(root)
    # The existing candidate loader locks the Task. Keep that lock through
    # validation, file generation and INSERT, so revisions cannot race saving.
    # A failed commit may leave an unregistered file; downloads require DB metadata.
    from contextlib import nullcontext
    with nullcontext(connection) if connection is not None else queue.conn() as conn:
        candidate = loader(queue, conn, task_id, run_id, specification_id)
        if candidate['specification_checksum'] != expected_checksum:
            raise ValueError('SDM_SPECIFICATION_CHANGED')
        spec = candidate['compiled']['specification']
        naming = conn.execute('SELECT * FROM platform.naming_contract WHERE task_id=%s AND contract_id=%s FOR SHARE',
                              (task_id, spec['naming']['contract_id'])).fetchone()
        existing = conn.execute('''SELECT * FROM platform.sdm_artifact WHERE task_id=%s AND run_id=%s
            AND specification_id=%s AND specification_approval_id=%s AND naming_contract_id=%s
            AND renderer_version='openpyxl-sdm-v1' AND status='CANDIDATE_NOT_RELEASED' ''',
            (task_id, run_id, specification_id, candidate['approval_id'], naming['contract_id'])).fetchall()
        if existing:
            if len(existing) != 1:
                raise ValueError('SDM_VERSION_AMBIGUOUS')
            row = existing[0]
            read_sdm_bytes(storage_root, row['project_id'], run_id, row['sdm_id'],
                           checksum=row['checksum'], file_size=row['file_size'])
            return public_metadata(row)
        project_id = conn.execute('SELECT project_id FROM platform.task WHERE task_id=%s', (task_id,)).fetchone()['project_id']
        rendered = render_sdm_xlsx(spec, candidate['run'], naming)
        identity = uuid4()
        stored = save_sdm_bytes(storage_root, project_id, run_id, identity, rendered['content'])
        row = conn.execute('''INSERT INTO platform.sdm_artifact
            (sdm_id,task_id,project_id,run_id,specification_id,specification_approval_id,
             naming_contract_id,specification_checksum,naming_checksum,file_path,checksum,file_size,renderer_version,status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'openpyxl-sdm-v1','CANDIDATE_NOT_RELEASED') RETURNING *''',
            (identity, task_id, project_id, run_id, specification_id, candidate['approval_id'],
             naming['contract_id'], expected_checksum, naming['checksum'], stored['file_path'],
             stored['checksum'], stored['file_size'])).fetchone()
        queue.event(conn, run_id, 'SDM_CANDIDATE_SAVED', 'SDM_GENERATION',
                    {'sdm_id': str(identity), 'specification_id': str(specification_id),
                     'specification_checksum': expected_checksum, 'checksum': stored['checksum'],
                     'status': 'CANDIDATE_NOT_RELEASED'})
        return public_metadata(row)
