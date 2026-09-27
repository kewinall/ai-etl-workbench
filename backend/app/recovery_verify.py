"""Opt-in offline recovery probe. Never dispatches models or ETL."""
import argparse
from hashlib import sha256
import io
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID
import zipfile


def check_scope(url, enabled):
    parsed = urlsplit(url)
    if (enabled != 'isolated-copy-v1' or parsed.scheme != 'postgresql'
            or parsed.hostname != '127.0.0.1' or parsed.username != 'workbench'
            or parsed.password is not None or parsed.query or parsed.fragment
            or not parsed.path.startswith('/restore_')):
        raise ValueError('RECOVERY_SCOPE_REQUIRED')


def verify(repo, project_id, cohort_id, expected_releases):
    from .pilot_measurements import read
    from .platform_harness import decrypt_secret
    from .release_store import download
    from .run_queue import RunQueue
    with repo.conn() as conn:
        before = conn.execute('SELECT count(*) AS n FROM platform.task_run_event').fetchone()['n']
        secrets = conn.execute('SELECT cipher_text,nonce FROM platform.secret_vault_entry').fetchall()
        for record in secrets:
            clear = decrypt_secret(bytes(record['cipher_text']), bytes(record['nonce']))
            if not isinstance(clear, str) or not clear:
                raise ValueError('RECOVERY_SECRET_CHECK_FAILED')
            del clear
    data = read(repo, str(UUID(project_id)))
    cohorts = [c for c in data['cohorts'] if c['cohort_id'] == str(UUID(cohort_id))]
    if len(cohorts) != 1:
        raise ValueError('RECOVERY_COHORT_REQUIRED')
    cohort = cohorts[0]
    if (cohort['denominator'] != 20 or len(cohort['cases']) != 20
            or cohort['release_ready_count'] != expected_releases or cohort['unverified_count']):
        raise ValueError('RECOVERY_EVIDENCE_MISMATCH')
    queue = RunQueue(repo.url)
    verified = 0
    for row in cohort['cases']:
        if row['status'] != 'RELEASE_READY':
            continue
        content = download(queue, repo, row['task_id'], row['run_id'], row['release_id'])
        if sha256(content).hexdigest() != row['release_checksum']:
            raise ValueError('RECOVERY_DOWNLOAD_MISMATCH')
        with zipfile.ZipFile(io.BytesIO(content)) as bundle:
            if len(bundle.infolist()) != 6 or bundle.testzip() is not None:
                raise ValueError('RECOVERY_ZIP_INVALID')
        verified += 1
    with repo.conn() as conn:
        after = conn.execute('SELECT count(*) AS n FROM platform.task_run_event').fetchone()['n']
    if before != after or verified != expected_releases:
        raise ValueError('RECOVERY_HISTORY_CHANGED')
    return {'status': 'PASS', 'secret_entries_verified': len(secrets),
            'denominator': 20, 'downloads_verified': verified,
            'frozen_scenario_matches': cohort['scenario_evidence_matched_count'],
            'events_unchanged': True, 'http_verified': False, 'etl_replayed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=UUID)
    parser.add_argument('--cohort', required=True, type=UUID)
    parser.add_argument('--expected-releases', required=True, type=int, choices=range(1, 21))
    parser.add_argument('--http', action='store_true', help='Also verify real loopback HTTP downloads; no Worker is started')
    args = parser.parse_args()
    try:
        url = os.environ.get('DATABASE_URL', '')
        check_scope(url, os.environ.get('WORKBENCH_RECOVERY_VERIFY'))
        # The launcher must additionally provide a network-none namespace and only copied volumes.
        routes = Path('/proc/net/route').read_text().splitlines()[1:]
        if any(line.split()[0] != 'lo' for line in routes if line.strip()):
            raise ValueError('RECOVERY_NETWORK_NOT_ISOLATED')
        routes6 = Path('/proc/net/ipv6_route').read_text().splitlines()
        if any(line.split()[-1] != 'lo' for line in routes6 if line.strip()):
            raise ValueError('RECOVERY_NETWORK_NOT_ISOLATED')
        for root in ('/run/workbench-secrets', '/app/runtime-temp', '/app/hop-project', '/app/outputs'):
            if not os.statvfs(root).f_flag & os.ST_RDONLY:
                raise ValueError('RECOVERY_FILES_MUST_BE_READONLY')
        os.environ['PLATFORM_SETTINGS_ENCRYPTION_KEY'] = Path('/run/workbench-secrets/settings_key').read_text().strip()
        os.environ['WORKBENCH_ARTIFACT_ROOT'] = '/app/outputs'
        from .repository import PostgresRepository
        repo = PostgresRepository(url)
        result = verify(repo, str(args.project), str(args.cohort), args.expected_releases)
        if args.http:
            for flag in ('WORKBENCH_EXECUTION_ENABLED', 'WORKBENCH_SA_DISPATCH_ENABLED',
                         'WORKBENCH_DEVELOPER_DISPATCH_ENABLED', 'WORKBENCH_QA_DISPATCH_ENABLED'):
                os.environ[flag] = 'false'
            from .main import app
            from .recovery_server import serve
            from .recovery_http import verify_http
            def counts():
                with repo.conn() as conn:
                    return tuple(conn.execute(f'SELECT count(*) AS n FROM platform.{table}').fetchone()['n']
                                 for table in ('task_run_event', 'pilot_effort_event'))
            before = counts()
            with serve(app) as base_url:
                http_result = verify_http(base_url, str(args.project), str(args.cohort), args.expected_releases)
            if counts() != before:
                raise ValueError('RECOVERY_HTTP_HISTORY_CHANGED')
            if any(http_result[key] != result[key] for key in ('downloads_verified', 'frozen_scenario_matches')):
                raise ValueError('RECOVERY_HTTP_SERVICE_MISMATCH')
            result.update(http_result, effort_events_unchanged=True)
    except Exception:
        # No exception text: database errors may contain paths or credentials.
        print(json.dumps({'status': 'FAILED', 'detail': 'Recovery scope or evidence check failed; inspect the isolated environment.'}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
