import httpx
import pytest
import socket
from urllib.parse import urlsplit
from fastapi import FastAPI

from app.recovery_server import serve


@pytest.mark.parametrize('raise_inside', [False, True])
def test_loopback_readonly_and_cleanup(raise_inside):
    app = FastAPI()
    path = '/api/projects/00000000-0000-0000-0000-000000000001/pilot-measurements'
    calls = []
    @app.api_route(path, methods=['GET', 'POST'])
    def endpoint():
        calls.append(True)
        return {'synthetic': True}
    try:
        with serve(app) as url:
            with httpx.Client(base_url=url, trust_env=False) as client:
                assert client.get(path).json() == {'synthetic': True}
                assert client.post(path).status_code == 405
                assert client.get('/api/settings').status_code == 405
            assert len(calls) == 1
            if raise_inside:
                raise RuntimeError('synthetic failure')
    except RuntimeError:
        assert raise_inside
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', urlsplit(url).port))
    with pytest.raises((httpx.ConnectError, httpx.ConnectTimeout)):
        httpx.get(url + path, timeout=1, trust_env=False)
