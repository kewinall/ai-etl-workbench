from uuid import uuid4
import pytest
import psycopg
from test_run_queue_integration import context
from test_specification_api_integration import prepared, pytestmark


def test_sdm_metadata_binding_immutable_and_legacy_preserved(context):
    queue, task_id, run, spec, naming, api = prepared(context)
    base = f'/api/tasks/{task_id}/runs/{run["run_id"]}/specifications'
    saved = api.post(base, json=spec).json()
    assert api.post(base+'/'+saved['specification_id']+'/approve',json={'content_checksum':saved['content_checksum']}).status_code==200
    with queue.conn() as conn:
        approval=conn.execute('SELECT approval_id FROM platform.specification_approval WHERE specification_id=%s',(saved['specification_id'],)).fetchone()['approval_id']
        project=conn.execute('SELECT project_id FROM platform.task WHERE task_id=%s',(task_id,)).fetchone()['project_id']
    sql='''INSERT INTO platform.sdm_artifact(sdm_id,task_id,file_path,checksum,project_id,run_id,specification_id,specification_approval_id,naming_contract_id,specification_checksum,naming_checksum,file_size,renderer_version,status)
     VALUES(%s,%s,'synthetic/no-file.xlsx',%s,%s,%s,%s,%s,%s,%s,%s,123,'openpyxl-sdm-v1','CANDIDATE_NOT_RELEASED')'''
    identity=uuid4()
    values=[identity,task_id,'a'*64,project,run['run_id'],saved['specification_id'],approval,naming['contract_id'],saved['content_checksum'],naming['checksum']]
    try:
        with queue.conn() as conn: conn.execute(sql,values)
        with pytest.raises(psycopg.Error,match='immutable'):
            with queue.conn() as conn: conn.execute("UPDATE platform.sdm_artifact SET checksum=%s WHERE sdm_id=%s",('b'*64,identity))
        invalid=values.copy();invalid[0]=uuid4();invalid[2]='b'*64;invalid[8]='b'*64
        with pytest.raises(psycopg.Error,match='SDM_VERSION_BINDING_MISMATCH'):
            with queue.conn() as conn: conn.execute(sql,invalid)
        with pytest.raises(psycopg.errors.UniqueViolation):
            duplicate=values.copy();duplicate[0]=uuid4()
            with queue.conn() as conn: conn.execute(sql,duplicate)
        with queue.conn() as conn:
            conn.execute("INSERT INTO platform.sdm_artifact(sdm_id,task_id,file_path,checksum) VALUES(%s,%s,'old/path.xlsx','legacy-checksum')",(uuid4(),task_id))
            row=conn.execute("SELECT file_path,checksum,status FROM platform.sdm_artifact WHERE task_id=%s AND status='LEGACY_UNVERIFIED'",(task_id,)).fetchone()
            assert dict(row)=={'file_path':'old/path.xlsx','checksum':'legacy-checksum','status':'LEGACY_UNVERIFIED'}
    finally:
        with queue.conn() as conn: conn.execute('DELETE FROM platform.sdm_artifact WHERE task_id=%s',(task_id,))
