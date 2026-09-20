"""Post-execution delivery gate. No files, SQL execution, or release permission."""
from .qa_approval import read_approval


def load_delivery_context(queue,task_id,run_id,*,connection=None):
    from contextlib import nullcontext
    with nullcontext(connection) if connection is not None else queue.conn() as conn:
        state=read_approval(queue,task_id,run_id,connection=conn)
        if state['status']!='APPROVED_CURRENT' or state['qa_approved'] is not True:
            raise ValueError('DELIVERY_CURRENT_QA_APPROVAL_REQUIRED')
        binding=state['binding']
        row=conn.execute('''SELECT s.specification_id,s.spec_json,s.content_checksum,a.binding
            FROM platform.specification s JOIN platform.task_run_execution_authorization a USING(specification_id)
            WHERE s.task_id=%s AND s.run_id=%s AND a.run_id=%s FOR SHARE OF s,a''',
            (task_id,run_id,run_id)).fetchone()
        if (not row or row['content_checksum']!=binding['specification_checksum']
                or row['binding']['specification_checksum']!=binding['specification_checksum']):
            raise ValueError('DELIVERY_SPECIFICATION_BINDING_CHANGED')
        return {'run_id':str(run_id),'task_id':task_id,'project_id':binding['project_id'],
            'specification_id':str(row['specification_id']),'specification':row['spec_json'],
            'qa_approval_id':state['approval']['approval_id'],'qa_binding_checksum':binding['checksum'],
            'specification_checksum':binding['specification_checksum'],
            'status':'QA_APPROVED_DELIVERY_INPUTS','release_ready':False}
