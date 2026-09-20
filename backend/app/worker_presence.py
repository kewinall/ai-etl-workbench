"""Database-clock liveness, separate from work ownership and model authorization."""
from threading import Event, Thread
from uuid import UUID
from .run_queue import RunConflict

KINDS = ('CONTROL', 'SA_LITELLM', 'SA_COPILOT')


class WorkerRegistry:
    def __init__(self, queue):
        self.queue = queue

    def touch(self, instance_id, kind, mode, activity):
        instance_id = UUID(str(instance_id))
        if kind not in KINDS or mode not in ('EXECUTE','OBSERVE') or activity not in ('IDLE','BUSY','STOPPED'):
            raise ValueError('INVALID_WORKER_PRESENCE')
        with self.queue.conn() as conn:
            row = conn.execute("""INSERT INTO platform.worker_presence(instance_id,kind,mode,activity)
                VALUES(%s,%s,%s,%s) ON CONFLICT(instance_id) DO UPDATE
                SET activity=excluded.activity,last_seen=clock_timestamp()
                WHERE worker_presence.kind=excluded.kind AND worker_presence.mode=excluded.mode
                AND worker_presence.activity<>'STOPPED' RETURNING instance_id""", (instance_id,kind,mode,activity)).fetchone()
            if not row:
                raise RunConflict('WORKER_IDENTITY_CANNOT_BE_REUSED')
        return {'status': 'RECORDED'}

    def snapshot(self):
        with self.queue.conn() as conn:
            rows = conn.execute("""SELECT kind,max(last_seen) AS last_seen,
                count(*) FILTER(WHERE activity<>'STOPPED' AND last_seen>clock_timestamp()-interval '45 seconds') AS active_instances,
                count(*) FILTER(WHERE activity<>'STOPPED' AND mode='EXECUTE' AND last_seen>clock_timestamp()-interval '45 seconds') AS dispatch_instances
                FROM platform.worker_presence GROUP BY kind""").fetchall()
            server_time = conn.execute('SELECT clock_timestamp() AS value').fetchone()['value']
        by_kind = {row['kind']: row for row in rows}
        result = []
        for kind in KINDS:
            row = by_kind.get(kind)
            active = row['active_instances'] if row else 0
            result.append({'kind': kind, 'status': 'ONLINE' if active else ('OFFLINE' if row else 'NOT_STARTED'),
                           'active_instances': active, 'can_dispatch': bool(row and row['dispatch_instances']),
                           'last_seen': row['last_seen'] if row else None})
        return {'workers': result, 'server_time': server_time, 'expires_after_seconds': 45,
                'scope': 'RECENT_HEARTBEAT_NOT_MODEL_OR_ETL_HEALTH'}


class PresenceReporter:
    def __init__(self, report, interval=10):
        if not 1 <= interval <= 10:
            raise ValueError('INVALID_PRESENCE_INTERVAL')
        self.report, self.interval = report, interval
        self.activity = 'IDLE'
        self.stop = Event()
        self.thread = Thread(target=self.loop, daemon=True)

    def loop(self):
        while not self.stop.wait(self.interval):
            try:
                self.report(self.activity)
            except Exception:
                pass  # No heartbeat means offline after TTL; never claim success locally.

    def __enter__(self):
        try:
            self.report(self.activity)
        except Exception:
            pass  # Startup during a DB restart stays alive and reconnects without dispatch replay.
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=26)
        try:
            self.report('STOPPED')
        except Exception:
            pass
