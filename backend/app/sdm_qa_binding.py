"""Associate existing SDM with current QA. Never edits a workbook or grants release."""
from .delivery_context import load_delivery_context
from .sdm_files import read_sdm_bytes
from .sdm_xlsx_semantics import validate_sdm_xlsx
from .specification_store import context
import os


def verify_document(queue,conn,task_id,run_id,row,delivery,root):
    storage=root if root is not None else os.getenv('WORKBENCH_ARTIFACT_ROOT')
    if not storage:raise ValueError('SDM_STORAGE_NOT_CONFIGURED')
    content=read_sdm_bytes(storage,row['project_id'],run_id,row['sdm_id'],
        checksum=row['checksum'],file_size=row['file_size'])
    run,naming=context(queue,conn,task_id,run_id)
    return validate_sdm_xlsx(content,delivery['specification'],{**run,'write_started':False},naming)


def bind_sdm_qa(queue,task_id,run_id,sdm_id,expected_qa_checksum,*,root=None,connection=None):
    from contextlib import nullcontext
    with nullcontext(connection) if connection is not None else queue.conn() as conn:
        delivery=load_delivery_context(queue,task_id,run_id,connection=conn)
        if delivery['qa_binding_checksum']!=expected_qa_checksum:
            raise ValueError('SDM_QA_VERSION_CONFLICT')
        row=conn.execute('''SELECT * FROM platform.sdm_artifact
            WHERE sdm_id=%s AND task_id=%s AND run_id=%s FOR SHARE''',(sdm_id,task_id,run_id)).fetchone()
        if (not row or row['status']!='CANDIDATE_NOT_RELEASED'
                or str(row['specification_id'])!=delivery['specification_id']
                or row['specification_checksum']!=delivery['specification_checksum']):
            raise ValueError('SDM_QA_CANDIDATE_MISMATCH')
        verify_document(queue,conn,task_id,run_id,row,delivery,root)
        existing=conn.execute('SELECT * FROM platform.sdm_qa_binding WHERE sdm_id=%s',(sdm_id,)).fetchone()
        if existing:
            if str(existing['qa_approval_id'])!=delivery['qa_approval_id']:raise ValueError('SDM_QA_VERSION_CONFLICT')
        else:
            conn.execute('INSERT INTO platform.sdm_qa_binding(sdm_id,qa_approval_id,run_id) VALUES(%s,%s,%s)',
                (sdm_id,delivery['qa_approval_id'],run_id))
            queue.event(conn,run_id,'SDM_QA_LINKED','SDM_GENERATION',
                {'sdm_id':str(sdm_id),'qa_approval_id':delivery['qa_approval_id'],'release_ready':False})
        return {'sdm_id':str(sdm_id),'qa_approval_id':delivery['qa_approval_id'],
            'status':'QA_LINKED_NOT_RELEASED','release_ready':False}
