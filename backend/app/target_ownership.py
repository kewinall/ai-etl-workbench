"""Permanent per-Run Pilot target claim; not proof against external DB writers."""
from .approved_candidate import load_approved_candidate
from .delivery_compiler import compile_delivery_components
from . import specification_store
from contextlib import contextmanager


def lock_target(conn, schema, table):
    conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))',
        ('workbench-target:' + schema + '.' + table,))


@contextmanager
def target_rebuild_guard(repo, schema, table):
    with repo.conn() as conn:
        lock_target(conn, schema, table)
        if conn.execute('SELECT 1 FROM platform.task_run_target_claim WHERE schema_name=%s AND table_name=%s',
                (schema, table)).fetchone():
            raise ValueError('RUN_TARGET_CANNOT_BE_REBUILT')
        yield


def claim_target(queue, task_id, run_id, specification_id):
    with queue.conn() as conn:
        candidate = load_approved_candidate(queue, conn, task_id, run_id, specification_id)
        run, naming = specification_store.context(queue, conn, task_id, run_id)
        compiled = compile_delivery_components(candidate['compiled']['specification'], run, naming)
        spec = compiled['specification']
        if spec['target_schema'] != 'ai_sample':
            raise ValueError('PILOT_TARGET_SCHEMA_REQUIRED')
        lock_target(conn, spec['target_schema'], spec['target_table'])
        registry = conn.execute('''SELECT * FROM platform.platform_sample_table
            WHERE project_id=%s AND schema_name=%s AND table_name=%s FOR SHARE''',
            (run['project_id'], spec['target_schema'], spec['target_table'])).fetchone()
        if (not registry or registry['task_id'] != task_id
                or registry['ddl_checksum'] != compiled['ddl_checksum']):
            raise ValueError('REGISTERED_PROJECT_TARGET_REQUIRED')
        values = dict(run_id=run_id, project_id=run['project_id'], task_id=task_id,
            schema_name=spec['target_schema'], table_name=spec['target_table'],
            settings_checksum=run['settings_snapshot']['checksum'],
            specification_checksum=candidate['specification_checksum'],
            hpl_checksum=compiled['hpl_checksum'], ddl_checksum=compiled['ddl_checksum'],
            registry_created_at=registry['created_at'], registry_rebuilt_at=registry['rebuilt_at'])
        columns = ','.join(values)
        placeholders = ','.join(['%s'] * len(values))
        row = conn.execute(f'''INSERT INTO platform.task_run_target_claim ({columns})
            VALUES({placeholders}) ON CONFLICT DO NOTHING RETURNING *''', tuple(values.values())).fetchone()
        if not row:
            row = conn.execute('SELECT * FROM platform.task_run_target_claim WHERE run_id=%s FOR SHARE', (run_id,)).fetchone()
            if not row or any(str(row[key]) != str(value) for key,value in values.items()):
                raise ValueError('TARGET_ALREADY_CLAIMED_OR_CHANGED')
        else:
            queue.event(conn,run_id,'TARGET_CLAIMED','HOP_PREPARATION',
                {'scope':'PLATFORM_RUN_EXCLUSIVE','specification_checksum':values['specification_checksum']})
    return {'status':'TARGET_CLAIMED_NOT_EXECUTED','run_id':str(run_id)}


def check_target_claim(repo, binding):
    with repo.conn() as conn:
        claim = conn.execute('SELECT * FROM platform.task_run_target_claim WHERE run_id=%s FOR SHARE',
            (binding['run_id'],)).fetchone()
        if not claim:
            raise ValueError('PRE_EXECUTION_TARGET_CLAIM_REQUIRED')
        if any(claim[key] != binding[key] for key in ('settings_checksum','specification_checksum','hpl_checksum')):
            raise ValueError('TARGET_CLAIM_BINDING_CHANGED')
        registry = conn.execute('''SELECT * FROM platform.platform_sample_table
            WHERE project_id=%s AND schema_name=%s AND table_name=%s FOR SHARE''',
            (claim['project_id'],claim['schema_name'],claim['table_name'])).fetchone()
        if (not registry or registry['task_id'] != claim['task_id']
                or registry['ddl_checksum'] != claim['ddl_checksum']
                or registry['created_at'] != claim['registry_created_at']
                or registry['rebuilt_at'] != claim['registry_rebuilt_at']):
            raise ValueError('REGISTERED_TARGET_CHANGED')
    return dict(claim)
