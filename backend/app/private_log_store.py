"""Internal encrypted Hop log storage. Deliberately no public download API."""
from .private_hop_log import encrypt_hop_log,decrypt_hop_log
from .run_queue import RunConflict


def save_private_log(queue,run_id,token,content):
    encrypted=encrypt_hop_log(run_id,content)
    with queue.conn() as conn:
        run=conn.execute("SELECT run_id FROM platform.task_run WHERE run_id=%s AND state='RUNNING' AND phase='HOP_EXECUTION' AND write_started AND lease_token=%s AND lease_until>clock_timestamp() FOR UPDATE",(run_id,token)).fetchone()
        if not run:raise RunConflict('PRIVATE_LOG_LEASE_INVALID')
        existing=conn.execute('SELECT checksum,size FROM platform.task_run_private_log WHERE run_id=%s',(run_id,)).fetchone()
        if existing:
            if existing['checksum']!=encrypted['checksum'] or existing['size']!=encrypted['size']:
                raise RunConflict('PRIVATE_LOG_ALREADY_RECORDED')
        else:
            conn.execute('INSERT INTO platform.task_run_private_log(run_id,cipher_text,nonce,checksum,size) VALUES(%s,%s,%s,%s,%s)',(run_id,encrypted['cipher_text'],encrypted['nonce'],encrypted['checksum'],encrypted['size']))
            queue.event(conn,run_id,'PRIVATE_HOP_LOG_RECORDED','HOP_EXECUTION',{'checksum':encrypted['checksum'],'size':encrypted['size'],'release_included':False})
    return {'checksum':encrypted['checksum'],'size':encrypted['size']}


def read_private_log(queue,task_id,run_id):
    with queue.conn() as conn:
        row=conn.execute('SELECT l.* FROM platform.task_run_private_log l JOIN platform.task_run r USING(run_id) WHERE r.task_id=%s AND r.run_id=%s',(task_id,run_id)).fetchone()
        if not row:raise RunConflict('PRIVATE_LOG_NOT_FOUND')
    return decrypt_hop_log(run_id,row)
