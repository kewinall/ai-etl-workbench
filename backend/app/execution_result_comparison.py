"""Internal comparison only; actual query provenance is NOT established here."""
import json
from .execution_oracle import load_execution_oracle
from .result_reader import read_result_rows
from .expected_result import ResultColumn
from .result_oracle import compare_oracle_document


def compare_execution_cursor(queue,task_id,run_id,cursor):
    pinned=load_execution_oracle(queue,task_id,run_id)
    document=json.loads(pinned['content'])
    actual=read_result_rows(cursor,[ResultColumn(**column) for column in document['columns']])
    result=compare_oracle_document(pinned['content'],actual,document_checksum=pinned['document_checksum'],
        specification_checksum=document['specification_checksum'],naming_checksum=document['naming_checksum'])
    return {**result,'run_id':str(run_id),'oracle_id':pinned['oracle_id'],
        'execution_binding_checksum':pinned['binding_checksum'],
        'hop_event_id':pinned['hop_event_id'],'hop_log_checksum':pinned['hop_log_checksum'],
        'actual_provenance':'NOT_VERIFIED','qa_passed':False,'release_ready':False}
