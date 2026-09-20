"""One database transaction for SDM metadata and QA linkage. Not a release."""
from .delivery_context import load_delivery_context
from .sdm_store import save_delivery_candidate
from .sdm_qa_binding import bind_sdm_qa


def prepare_sdm_delivery(queue,task_id,run_id,qa_checksum,*,root=None):
    with queue.conn() as conn:
        delivery=load_delivery_context(queue,task_id,run_id,connection=conn)
        if delivery['qa_binding_checksum']!=qa_checksum:raise ValueError('SDM_QA_VERSION_CONFLICT')
        document=save_delivery_candidate(queue,task_id,run_id,delivery['specification_id'],
            delivery['specification_checksum'],qa_checksum,root=root,connection=conn)
        linked=bind_sdm_qa(queue,task_id,run_id,document['sdm_id'],qa_checksum,root=root,connection=conn)
        # Files are exclusive-create. A failed transaction can leave an orphan,
        # but no download is authorized without committed metadata.
        return {'document':document,'qa_binding':linked,'release_ready':False}
