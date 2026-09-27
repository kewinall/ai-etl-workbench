"""HTTP-to-PostgreSQL acceptance; all declarations are synthetic and rolled back."""
import os
from contextlib import contextmanager
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.project_api import create_project_router
from app.pilot_cohort import PilotCohortPlan, register
from app.pilot_effort_coverage import read as read_coverage
from test_pilot_cohort import plan_payload

pytestmark = pytest.mark.skipif(os.getenv('WORKBENCH_ALLOW_DATABASE_TESTS') != '1', reason='Isolated PostgreSQL required')


@pytest.mark.parametrize('actor', ['FUNCTIONAL_TEST','HUMAN_SELF_REPORTED'])
def test_http_records_bound_server_time_and_recovers(actor):
    assert os.environ['DATABASE_HOST']=='postgres'
    with psycopg.connect(os.environ['DATABASE_URL'],row_factory=dict_row) as conn:
        with conn.transaction(force_rollback=True):
            project=uuid4()
            conn.execute('INSERT INTO platform.project(project_id,project_name) VALUES(%s,%s)',(project,'Synthetic HTTP effort'))
            class Repo:
                @contextmanager
                def conn(self):
                    with conn.transaction(): yield conn
                def get_project(self, value):
                    return {'project_id':str(project)} if value==str(project) else None
            repo=Repo()
            cohort=register(repo,project,PilotCohortPlan(**plan_payload()))
            app=FastAPI();app.include_router(create_project_router(repo))
            with TestClient(app) as client:
                url=f"/api/projects/{project}/pilot-cohorts/{cohort['cohort_id']}/cases/case-00/effort"
                body=dict(request_key='http-effort-start',action='START',actor=actor,mode='WORKBENCH',
                    expected_protocol_checksum=cohort['plan_checksum'],confirmed=True,
                    human_attested=actor=='HUMAN_SELF_REPORTED')
                assert client.post(url,json=body|{'expected_protocol_checksum':'0'*64}).status_code==409
                assert client.post(url,json=body|{'recorded_at':'2026-01-01'}).status_code==422
                assert client.get(url).json()['events']==[]
                started=client.post(url,json=body)
                assert started.status_code==200
                first=started.json()
                assert first['human_attested']==(actor=='HUMAN_SELF_REPORTED')
                assert client.post(url,json=body).json()==first
                assert client.get(url).json()['recovery']['session_id']==first['session_id']
                end=body|dict(request_key='http-effort-stop',action='STOP',session_id=first['session_id'])
                stopped=client.post(url,json=end)
                assert stopped.status_code==200 and stopped.json()['action']=='STOP'
                assert client.post(url,json=end).json()==stopped.json()
                result=client.get(url)
                assert result.headers['cache-control']=='no-store'
                saved=result.json()
                assert len(saved['events'])==2 and saved['recovery'] is None
                assert saved['identity_verified'] is False and saved['comparison_ready'] is False
                seconds=saved['summary']['totals']['WORKBENCH']['recorded_human_seconds']
                if actor=='FUNCTIONAL_TEST': assert seconds is None
                else: assert isinstance(seconds,(float,int)) and seconds>=0
                coverage=read_coverage(repo,project,cohort['cohort_id'])
                assert coverage['denominator']==20 and coverage['complete_case_count']==0
                work=coverage['modes']['WORKBENCH']
                assert work['recorded_seconds']==seconds
                assert work['cases_with_recorded_intervals']==(1 if actor=='HUMAN_SELF_REPORTED' else 0)
                assert coverage['comparison_ready'] is False
                with pytest.raises(ValueError): read_coverage(repo,uuid4(),cohort['cohort_id'])
