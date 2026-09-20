"""Read-only deployment preflight; never claim or execute the portable candidate."""
import json
import vertica_python
from .release_replay_worker import destination


def preflight():
    target, secret = destination()
    config = {key: target[key] for key in ('host', 'port', 'database', 'user', 'tlsmode')}
    config.update(password=secret, connection_timeout=10)
    try:
        with vertica_python.connect(**config) as db:
            cursor = db.cursor()
            cursor.execute('SELECT version(), current_database()')
            version, database = cursor.fetchone()
            if database != target['database']:
                raise ValueError('DESTINATION_IDENTITY_MISMATCH')
            cursor.execute("SELECT count(*) FROM v_catalog.tables WHERE table_schema='ai_sample'")
            tables = cursor.fetchone()[0]
        return dict(status='CONNECTED', read_only=True, version=version, sample_table_count=tables)
    finally:
        config.clear()
        secret = None


if __name__ == '__main__':
    try:
        print(json.dumps(preflight()))
    except Exception as error:
        code = str(error) if str(error) == 'DESTINATION_IDENTITY_MISMATCH' else type(error).__name__
        raise SystemExit('PORTABILITY_DESTINATION_NOT_READY:' + code) from None
