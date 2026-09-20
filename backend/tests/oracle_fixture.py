"""Explicit synthetic expected answer for isolated control tests, never a model."""
import json
from app.oracle_store import oracle_editor_context,save_oracle,approve_oracle


def approved_answer(queue,task_id,run_id,specification_id,rows=None,approve=True):
    context=oracle_editor_context(queue,task_id,run_id,specification_id)
    document={key:context[key] for key in ('version','specification_checksum','naming_checksum','columns')}
    document['rows']=rows if rows is not None else [{'category':'A','total_amount':'101.25','row_count':1}]
    saved=save_oracle(queue,task_id,run_id,specification_id,json.dumps(document).encode())
    if approve:approve_oracle(queue,task_id,run_id,specification_id,saved['oracle_id'],saved['document_checksum'])
    return saved
