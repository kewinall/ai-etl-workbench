"""Bound real database empty-target check; no DDL, retries or permission grant."""
from hashlib import sha256
import re
import vertica_python
from .hop_connection_runtime import connection_runtime
from .target_ownership import check_target_claim
from .run_queue import RunQueue


def empty_target_sql(claim):
    if (claim.get('schema_name') != 'ai_sample'
            or not isinstance(claim.get('table_name'), str)
            or not re.fullmatch('[a-z][a-z0-9_]{0,62}', claim['table_name'])):
        raise ValueError('INVALID_CLAIMED_TARGET')
    return f'SELECT 1 FROM "ai_sample"."{claim["table_name"]}" LIMIT 1;'


def verify_empty_target(repo, binding, snapshot):
    claim = check_target_claim(repo, binding)
    sql = empty_target_sql(claim)
    with connection_runtime(repo, snapshot, binding['settings_checksum']) as runtime:
        config = {key:snapshot['connection'][key] for key in ('host','port','database','user','tlsmode')}
        config.update(password=runtime['environment']['WORKBENCH_VERTICA_PASSWORD'], connection_timeout=10)
        try:
            with vertica_python.connect(**config) as database:
                cursor=database.cursor()
                cursor.execute(sql)
                if cursor.fetchone() is not None:
                    raise ValueError('PILOT_TARGET_NOT_EMPTY')
        finally:
            config.clear()
    if check_target_claim(repo, binding) != claim:
        raise ValueError('TARGET_CLAIM_BINDING_CHANGED')
    with repo.conn() as conn:
        row=conn.execute('''INSERT INTO platform.task_run_target_empty_check
            (run_id,task_id,project_id,settings_checksum,hpl_checksum,sql_checksum)
            VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING run_id''',
            (binding['run_id'],claim['task_id'],claim['project_id'],binding['settings_checksum'],
             binding['hpl_checksum'],sha256(sql.encode()).hexdigest())).fetchone()
        if row:
            RunQueue.event(conn,binding['run_id'],'TARGET_EMPTY_CONFIRMED','HOP_PREPARATION',
                {'settings_checksum':binding['settings_checksum'],'sql_checksum':sha256(sql.encode()).hexdigest(),
                 'empty':True,'scope':'PLATFORM_RUN_EXCLUSIVE'})
    return require_empty_check(repo, binding)


def require_empty_check(repo, binding):
    with repo.conn() as conn:
        row=conn.execute('''SELECT *,created_at>clock_timestamp()-interval '5 minutes' AS fresh
            FROM platform.task_run_target_empty_check WHERE run_id=%s''',(binding['run_id'],)).fetchone()
    if (not row or not row['fresh'] or any(row[key] != binding[key] for key in ('settings_checksum','hpl_checksum'))):
        raise ValueError('FRESH_EMPTY_TARGET_CHECK_REQUIRED')
    return {'status':'EMPTY_TARGET_CONFIRMED_NOT_EXECUTED','run_id':str(binding['run_id'])}
