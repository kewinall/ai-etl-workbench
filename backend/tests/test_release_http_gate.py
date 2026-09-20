"""Exercise the actual legacy endpoint bodies without importing host DB startup."""
import ast
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


@pytest.mark.parametrize('enabled', ['true', 'false'])
def test_legacy_release_cannot_bypass_revision_approval(monkeypatch, enabled):
    monkeypatch.setenv('WORKBENCH_EXECUTION_ENABLED', enabled)
    source = Path(__file__).parents[1] / 'app' / 'main.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    endpoints = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {'build_release', 'download_release'}]
    assert len(endpoints) == 2
    app = FastAPI()
    # Deliberately no repo/file functions: neither endpoint may reach control DB or filesystem.
    scope = {'app': app, 'HTTPException': HTTPException}
    exec(compile(ast.Module(body=endpoints, type_ignores=[]), str(source), 'exec'), scope)
    client = TestClient(app)
    for response in (client.post('/api/tasks/legacy-success/release'),
                     client.get('/api/tasks/legacy-success/release/legacy-ready/download')):
        assert response.status_code == 409
        assert response.json()['detail']['code'] == 'RELEASE_PIPELINE_NOT_READY'
        assert 'file_path' not in response.text
