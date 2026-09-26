"""Synthetic project persistence acceptance; use only an isolated local deployment.

setup creates/edits one project and writes a non-secret receipt. Restart the
isolated Compose services, then verify performs read-only checks against it.
No Task, model, ETL, deletion, or release operation is performed.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['setup', 'verify'])
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    url = urlparse(args.base_url)
    if (url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost')
            or url.username or url.password or url.path not in ('', '/')
            or url.query or url.fragment or url.port != 5194):
        raise SystemExit('Only the dedicated local acceptance port 5194 is allowed')
    base = args.base_url.rstrip('/')

    def request(path, data=None, method=None):
        req = Request(base + path, method=method,
                      data=None if data is None else json.dumps(data).encode(),
                      headers={'Content-Type': 'application/json'})
        with urlopen(req, timeout=15) as response:
            return json.load(response)

    ready = request('/api/ready')
    assert ready == {'status': 'ready', 'execution_enabled': False}, ready
    workers = request('/api/runtime/workers')['workers']
    assert any(w['kind'] == 'CONTROL' and w['status'] == 'ONLINE' for w in workers), workers
    if args.phase == 'setup':
        if args.receipt.exists():
            raise SystemExit('Receipt already exists; use verify or a new receipt')
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        payload = {'project_name': 'Deployment acceptance ' + uuid4().hex[:12],
                   'description': 'Synthetic isolated persistence fixture',
                   'default_ai_profile': '', 'default_connection': '',
                   'naming_rules': {'column_aliases': {'測試欄位': 'test_field'}}}
        created = request('/api/projects', payload, 'POST')
        # Persist the receipt before edit so a failed update is recoverable.
        receipt = {'base_url': base, 'project_id': created['project_id'],
                   'expected': {**payload, 'description': 'Edited before restart'}}
        with args.receipt.open('x', encoding='utf-8') as stream:
            json.dump(receipt, stream, ensure_ascii=False, indent=2)
        request('/api/projects/' + receipt['project_id'],
                {**receipt['expected'], 'expected_updated_at': created['updated_at']}, 'PUT')
    else:
        receipt = json.loads(args.receipt.read_text(encoding='utf-8'))
        assert receipt['base_url'] == base
    actual = request('/api/projects/' + receipt['project_id'])
    for key, value in receipt['expected'].items():
        assert actual[key] == value, key
    assert request('/api/projects/' + receipt['project_id'] + '/tasks') == []
    print(json.dumps({'status': 'PASS', 'phase': args.phase,
                      'project_id': receipt['project_id'],
                      'execution_enabled': False, 'control_worker_online': True}))


if __name__ == '__main__':
    main()
