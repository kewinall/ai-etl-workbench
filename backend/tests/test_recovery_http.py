import io
from hashlib import sha256
from uuid import UUID
import zipfile

import httpx
import pytest

from app.recovery_http import verify_http

ID = str(UUID(int=1))


@pytest.mark.parametrize('url', ['https://127.0.0.1', 'http://localhost',
    'http://other', 'http://127.0.0.1/path', 'http://user@127.0.0.1',
    'http://127.0.0.1?host=other'])
def test_scope(url):
    with pytest.raises(ValueError, match='SCOPE'):
        verify_http(url, ID, ID, 20)


@pytest.mark.parametrize('fault', [None, 'redirect', 'checksum', 'header', 'count'])
def test_http_contract(fault):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as bundle:
        for n in range(6):
            bundle.writestr(str(n), 'synthetic')
    content = output.getvalue()
    row = dict(status='RELEASE_READY', task_id='synthetic', run_id=ID,
               release_id=ID, release_checksum=sha256(content).hexdigest())
    calls = []
    def handle(request):
        calls.append(request)
        assert request.method == 'GET'
        if request.url.path.endswith('pilot-measurements'):
            return httpx.Response(200, json={'cohorts': [dict(cohort_id=ID,
                denominator=20, cases=[row.copy() for _ in range(20)],
                release_ready_count=19 if fault == 'count' else 20,
                unverified_count=0, scenario_evidence_matched_count=19)]})
        return httpx.Response(302 if fault == 'redirect' else 200,
            content=b'changed' if fault == 'checksum' else content,
            headers={'content-type': 'application/zip', 'cache-control': 'no-store',
                'x-content-type-options': 'invalid' if fault == 'header' else 'nosniff',
                'content-disposition': f'attachment; filename="release-{ID}.zip"',
                'location': 'http://other/'})
    if fault:
        with pytest.raises(ValueError):
            verify_http('http://127.0.0.1:8000', ID, ID, 20, transport=httpx.MockTransport(handle))
        assert len(calls) <= 2
    else:
        result = verify_http('http://127.0.0.1:8000', ID, ID, 20, transport=httpx.MockTransport(handle))
        assert result == dict(http_verified=True, downloads_verified=20, frozen_scenario_matches=19)
        assert len(calls) == 21
