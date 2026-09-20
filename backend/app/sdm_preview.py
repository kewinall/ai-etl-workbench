"""Read-only SDM preview for the current saved/approved specification."""
from .approved_candidate import load_approved_candidate
from .sdm_specification import build_sdm_candidate


def approved_sdm_preview(queue,task_id,run_id,specification_id):
    with queue.conn() as conn:
        candidate=load_approved_candidate(queue,conn,task_id,run_id,specification_id)
        spec=candidate['compiled']['specification']
        naming=conn.execute('SELECT * FROM platform.naming_contract WHERE task_id=%s AND contract_id=%s FOR SHARE',
            (task_id,spec['naming']['contract_id'])).fetchone()
        result=build_sdm_candidate(spec,candidate['run'],naming)
        if result['document']['specification_checksum']!=candidate['specification_checksum']:
            raise ValueError('SDM_SPECIFICATION_CHANGED')
    return {**result,'specification_id':candidate['specification_id'],
        'specification_approval_id':candidate['approval_id'],'execution_authorized':False}
