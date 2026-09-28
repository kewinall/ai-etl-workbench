"""Opt-in actual isolated upload HTTP path; no model, Run or engine calls."""
import hashlib
import json
from io import BytesIO
import os

import httpx
import pytest
from openpyxl import Workbook

pytestmark = pytest.mark.skipif(
    os.getenv('WORKBENCH_UPLOAD_HTTP_TEST') != 'isolated-ui-5195',
    reason='Requires explicitly deployed isolated UI API on 5195')


@pytest.mark.parametrize('kind', ['csv', 'json', 'xlsx'])
def test_real_upload_preserves_identifiers_precision_and_utf8_width(kind):
    text = '中文' * 10
    amount = '12345678901234567890.123456'
    if kind == 'csv':
        content = f'客戶編號,金額,說明\n001,{amount},{text}\n'.encode()
    elif kind == 'json':
        # Numeric token, not a pre-rounded Python float or a JSON string.
        content = ('[{"客戶編號":"001","金額":' + amount + ',"說明":"' + text + '"}]').encode()
    else:
        book = Workbook()
        book.active.append(['客戶編號', '金額', '說明'])
        # Excel text preserves digits; this does not claim to recover rounded
        # numeric cells from an already-lossy source workbook.
        book.active.append(['001', amount, text])
        stream = BytesIO()
        book.save(stream)
        book.close()
        content = stream.getvalue()
    with httpx.Client(base_url='http://127.0.0.1:5195', trust_env=False,
                      follow_redirects=False, timeout=15) as client:
        ready = client.get('/api/ready')
        assert ready.status_code == 200
        assert ready.json()['execution_enabled'] is False
        response = client.post('/api/task-sources/upload', files={'file': (f'synthetic.{kind}', content)})
        assert response.status_code == 200, response.status_code
        result = response.json()
        if kind == 'xlsx':
            assert result['worksheet'] is None and result['fields'] == []
            chosen = client.post(f"/api/task-sources/{result['upload_id']}/excel-profile", json={
                'checksum': result['checksum'], 'size': result['size'],
                'worksheet': result['worksheets'][0], 'header_row': 1})
            assert chosen.status_code == 200
            result.update(chosen.json())
        assert result['source_type'] == {'csv': 'CSV', 'json': 'JSON', 'xlsx': 'EXCEL'}[kind]
        assert result['size'] == len(content)
        assert result['checksum'] == hashlib.sha256(content).hexdigest()
        assert result['fields'] == [
            {'name': '客戶編號', 'type': 'VARCHAR(32)'},
            {'name': '金額', 'type': 'DECIMAL(26,6)'},
            {'name': '說明', 'type': 'VARCHAR(60)'},
        ]
        assert result['sample_rows'][0]['客戶編號'] == '001'
        assert result['sample_rows'][0]['金額'] == amount


def test_real_upload_rejects_nested_json_instead_of_guessing_text():
    with httpx.Client(base_url='http://127.0.0.1:5195', trust_env=False, timeout=15) as client:
        assert client.get('/api/ready').json()['execution_enabled'] is False
        response = client.post('/api/task-sources/upload', files={
            'file': ('nested.json', b'[{"nested":{"value":1}}]', 'application/json')})
        assert response.status_code == 422
        assert '巢狀欄位需要明確展開規格' in response.json()['detail']


def test_json_full_scan_and_null_statistics_through_http():
    records = [{'id': '001', 'amount': 1} for _ in range(20)]
    records += [{'id': '002', 'amount': 'changed', 'late': None},
                {'id': '003', 'late': ''}]
    content = json.dumps(records).encode()
    with httpx.Client(base_url='http://127.0.0.1:5195', trust_env=False, timeout=15) as client:
        assert client.get('/api/ready').json()['execution_enabled'] is False
        response = client.post('/api/task-sources/upload', files={
            'file': ('synthetic.json', content, 'application/json')})
        assert response.status_code == 200
        profile = response.json()
        assert profile['profile_scope'] == 'ALL_RECORDS' and profile['row_count'] == 22
        assert profile['fields'][1] == {'name': 'amount', 'type': 'VARCHAR(32)'}
        assert profile['fields'][2] == {'name': 'late', 'type': 'VARCHAR(255)'}
        assert profile['column_statistics'][2] == {
            'name': 'late', 'missing_count': 20, 'explicit_null_count': 1,
            'null_ratio': 21 / 22, 'empty_string_count': 1}
        assert profile['checksum'] == hashlib.sha256(content).hexdigest()


@pytest.mark.parametrize('content,code', [
    (b'{"x":1,"x":2}', 'JSON_DUPLICATE_KEY'),
    (b'{"x":NaN}', 'JSON_NON_FINITE_NUMBER'),
    (b'{"x":"\\ud800"}', 'JSON_INVALID_UNICODE'),
    (b'{"x":1e99999999999999999999999999}', 'JSON_INVALID_DOCUMENT'),
])
def test_json_invalid_documents_are_422_not_silent_loss_or_500(content, code):
    with httpx.Client(base_url='http://127.0.0.1:5195', trust_env=False, timeout=15) as client:
        assert client.get('/api/ready').json()['execution_enabled'] is False
        response = client.post('/api/task-sources/upload', files={
            'file': ('synthetic-invalid.json', content, 'application/json')})
        assert response.status_code == 422
        assert code in response.json()['detail']
