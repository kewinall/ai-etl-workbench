"""Metadata-only contract checks inside the caller's rollback transaction; no XLSX."""
from pathlib import Path
from uuid import uuid4
import psycopg
import pytest
from app.sdm_qa_binding import bind_sdm_qa


def check_sdm_qa_database(queue,conn,task,run,delivery,approval,qa_checksum):
    if not conn.execute("SELECT to_regclass('platform.sdm_qa_binding') name").fetchone()['name']:
        conn.execute(Path('/app/database/migrations/043_sdm_qa_binding.sql').read_text())
    identity=uuid4()
    conn.execute('''INSERT INTO platform.sdm_artifact
        (sdm_id,task_id,project_id,run_id,specification_id,specification_approval_id,naming_contract_id,
         specification_checksum,naming_checksum,file_path,checksum,file_size,renderer_version,status)
        SELECT %s,s.task_id,%s,s.run_id,s.specification_id,a.approval_id,n.contract_id,
         s.content_checksum,n.checksum,'synthetic-metadata-no-file','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',1,
         'openpyxl-sdm-v1','CANDIDATE_NOT_RELEASED'
        FROM platform.specification s JOIN platform.specification_approval a USING(specification_id)
        JOIN platform.naming_contract n ON n.contract_id::text=s.spec_json->'naming'->>'contract_id'
        WHERE s.specification_id=%s''',(identity,delivery['project_id'],delivery['specification_id']))
    with pytest.raises(psycopg.Error,match='SDM_QA_BINDING_MISMATCH'):
        with conn.transaction():
            conn.execute('INSERT INTO platform.sdm_qa_binding(sdm_id,qa_approval_id,run_id) VALUES(%s,%s,%s)',
                (identity,approval['approval_id'],uuid4()))
    # This fixture is metadata only: production service must reject its absent file.
    with pytest.raises(ValueError,match='SDM_FILE_CHANGED_OR_UNAVAILABLE'):
        bind_sdm_qa(queue,task,run,identity,qa_checksum,root='/tmp')
    conn.execute('INSERT INTO platform.sdm_qa_binding(sdm_id,qa_approval_id,run_id) VALUES(%s,%s,%s)',
        (identity,approval['approval_id'],run))
    for sql in ('UPDATE platform.sdm_qa_binding SET run_id=run_id WHERE sdm_id=%s',
                'DELETE FROM platform.sdm_qa_binding WHERE sdm_id=%s'):
        with pytest.raises(psycopg.Error,match='immutable'):
            with conn.transaction():conn.execute(sql,(identity,))
