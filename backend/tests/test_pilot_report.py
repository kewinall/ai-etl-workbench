from copy import deepcopy
from unittest.mock import Mock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.pilot_report import render
from app.project_api import create_project_router
from test_pilot_measurements import cohort, measure, ready


def snapshot():
    group = measure(cohort(), ready)
    group['scenario_evidence_matched_count'] = 19
    return {'project_id': str(uuid4()), 'checked_from': 'start', 'checked_until': 'end',
            'limitations': ['固定分母，不排除失敗'], 'cohorts': [group]}


def test_escape_allowlist_fixed_denominator_and_unknowns():
    data = snapshot()
    data['cohorts'][0]['name'] = '<script>alert(1)</script>'
    data['cohorts'][0]['cases'][0]['private_log'] = 'SECRET_MARKER'
    original = deepcopy(data)
    html = render(data)
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert 'SECRET_MARKER' not in html
    assert html.count('<article>') == 20
    assert '可交付 20 / 20' in html and '凍結情境證據 19 / 20' in html
    assert '尚無完整量測' in html and '非人工工時' in html
    assert data == original


def test_invalid_population_rejected():
    data = snapshot()
    data['cohorts'][0]['cases'].pop()
    with pytest.raises(ValueError, match='POPULATION_INVALID'):
        render(data)


def test_partial_usage_and_effort_never_imply_complete_measurement():
    data = snapshot()
    group = data['cohorts'][0]
    group['effort'] = {'status':'RECORDED_INTERVALS_ONLY','modes':{
        'WORKBENCH':{'recorded_seconds':12,'cases_with_recorded_intervals':1,'cases_without_recorded_intervals':19},
        'MANUAL_BASELINE':{'recorded_seconds':None,'cases_with_recorded_intervals':0,'cases_without_recorded_intervals':20}},
        'excluded_nonhuman_sessions':2,'abandoned_sessions':1,'has_open_session':True}
    from app.pilot_usage import METRICS
    metrics = {key:{'reported_sum':None,'reported_invocations':0,'missing_invocations':2,'complete_sum':None} for key in METRICS}
    metrics['ai_credits'].update(reported_sum=1.25,reported_invocations=1,missing_invocations=1)
    group['usage'] = {'limitations':['不估算成本'], 'groups':[{'provider':'test','model':'model',
        'journal_invocations':2,'nonaccepted_invocations':1,'provider_partial_records':1,'metrics':metrics}]}
    html = render(data)
    assert '工作台操作：已記錄 12 秒' in html
    assert '人工基準：尚未量測' in html
    assert '有區間紀錄 1 / 20 案，未記錄 19 案' in html
    assert '排除代理／功能測試 2 段' in html
    assert 'AI credits：已回報合計 1.25；覆蓋 1 / 2 筆，缺 1 筆；完整總量不可用' in html
    assert '總 Token：未回報' in html


def test_report_route_scope_headers_and_safe_failure(monkeypatch):
    data = snapshot()
    repo = Mock()
    repo.get_project.return_value = {'project_id': data['project_id']}
    app = FastAPI()
    app.include_router(create_project_router(repo))
    client = TestClient(app)
    read = Mock(return_value=data)
    monkeypatch.setattr('app.pilot_measurements.read', read)
    url = f'/api/projects/{data["project_id"]}/pilot-report'
    response = client.get(url)
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert "default-src 'none'" in response.headers['content-security-policy']
    read.assert_called_once_with(repo, data['project_id'])
    read.side_effect = RuntimeError('SECRET_MARKER')
    response = client.get(url)
    assert response.status_code == 503 and 'SECRET_MARKER' not in response.text
    repo.get_project.return_value = None
    assert client.get(url).status_code == 404
