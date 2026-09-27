"""Read-only HTTP assertions for an already isolated recovery API.

The caller must enforce network isolation and copied volumes before use.
No redirects, retries, writes, model calls or ETL dispatch are performed here.
"""
from hashlib import sha256
import io
from urllib.parse import urlsplit, quote
from uuid import UUID
import zipfile

import httpx


def verify_http(base_url, project_id, cohort_id, expected_releases, *, transport=None):
    parsed = urlsplit(base_url)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1'
            or parsed.username or parsed.password or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment):
        raise ValueError('RECOVERY_HTTP_SCOPE_REQUIRED')
    if type(expected_releases) is not int or not 1 <= expected_releases <= 20:
        raise ValueError('RECOVERY_HTTP_COUNT_REQUIRED')
    project_id, cohort_id = str(UUID(project_id)), str(UUID(cohort_id))
    with httpx.Client(base_url=base_url, timeout=30, follow_redirects=False,
                      trust_env=False, transport=transport) as client:
        response = client.get(f'/api/projects/{project_id}/pilot-measurements')
        if response.status_code != 200:
            raise ValueError('RECOVERY_HTTP_MEASUREMENTS_FAILED')
        cohorts = [c for c in response.json()['cohorts'] if c['cohort_id'] == cohort_id]
        if len(cohorts) != 1:
            raise ValueError('RECOVERY_HTTP_COHORT_REQUIRED')
        cohort = cohorts[0]
        if (cohort['denominator'] != 20 or len(cohort['cases']) != 20
                or cohort['release_ready_count'] != expected_releases
                or cohort['unverified_count']):
            raise ValueError('RECOVERY_HTTP_EVIDENCE_MISMATCH')
        verified = 0
        for row in cohort['cases']:
            if row['status'] != 'RELEASE_READY':
                continue
            task = quote(row['task_id'], safe='')
            run, release = str(UUID(row['run_id'])), str(UUID(row['release_id']))
            response = client.get(f'/api/tasks/{task}/runs/{run}/release/{release}/download')
            if (response.status_code != 200
                    or response.headers.get('content-type') != 'application/zip'
                    or response.headers.get('cache-control') != 'no-store'
                    or response.headers.get('x-content-type-options') != 'nosniff'
                    or response.headers.get('content-disposition') != f'attachment; filename="release-{release}.zip"'
                    or sha256(response.content).hexdigest() != row['release_checksum']):
                raise ValueError('RECOVERY_HTTP_DOWNLOAD_MISMATCH')
            with zipfile.ZipFile(io.BytesIO(response.content)) as bundle:
                if len(bundle.infolist()) != 6 or bundle.testzip() is not None:
                    raise ValueError('RECOVERY_HTTP_ZIP_INVALID')
            verified += 1
        if verified != expected_releases:
            raise ValueError('RECOVERY_HTTP_COUNT_MISMATCH')
    return {'http_verified': True, 'downloads_verified': verified,
            'frozen_scenario_matches': cohort['scenario_evidence_matched_count']}
