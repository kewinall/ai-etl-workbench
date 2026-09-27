"""Prospective Pilot registration. No caller-supplied success or timing claims."""
from hashlib import sha256
import json
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from psycopg.types.json import Jsonb


class PilotCase(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    case_key: str = Field(pattern=r'^[a-z][a-z0-9_-]{1,59}$')
    title: str = Field(min_length=2, max_length=160)
    scenario: Literal['SUCCESS', 'REQUIREMENT_GAP', 'SEMANTIC_DEFECT', 'EXECUTION_RECOVERY']
    acceptance: str = Field(min_length=10, max_length=4000)
    # References are labels, never fetched or executed by registration.
    fixture_reference: str = Field(min_length=1, max_length=240)
    oracle_reference: str = Field(min_length=1, max_length=240)
    fixture_checksum: str = Field(pattern=r'^[a-f0-9]{64}$')
    oracle_checksum: str = Field(pattern=r'^[a-f0-9]{64}$')


class PilotCohortPlan(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=120)
    protocol_version: Literal['pilot-v1'] = 'pilot-v1'
    cases: list[PilotCase] = Field(min_length=20, max_length=20)

    @model_validator(mode='after')
    def fixed_population(self):
        if len({case.case_key for case in self.cases}) != 20:
            raise ValueError('案例代碼不可重複')
        required = {'SUCCESS', 'REQUIREMENT_GAP', 'SEMANTIC_DEFECT', 'EXECUTION_RECOVERY'}
        if {case.scenario for case in self.cases} != required:
            raise ValueError('必須涵蓋成功、需求缺口、語意缺陷與失敗修復四種情境')
        return self


def fingerprint(plan):
    return sha256(json.dumps(plan.model_dump(), ensure_ascii=False, sort_keys=True,
                             separators=(',', ':')).encode()).hexdigest()


def register(repo, project_id, plan):
    digest = fingerprint(plan)
    with repo.conn() as conn:
        # Atomic/idempotent for a retry after a lost HTTP response.
        row = conn.execute('''INSERT INTO platform.pilot_cohort
            (cohort_id,project_id,name,protocol_version,plan_checksum)
            VALUES(%s,%s,%s,%s,%s) ON CONFLICT(project_id,plan_checksum) DO NOTHING
            RETURNING *''', (uuid4(), project_id, plan.name, plan.protocol_version, digest)).fetchone()
        if row:
            for ordinal, case in enumerate(plan.cases, 1):
                conn.execute('''INSERT INTO platform.pilot_cohort_case
                    (cohort_id,case_key,ordinal,definition) VALUES(%s,%s,%s,%s)''',
                    (row['cohort_id'], case.case_key, ordinal, Jsonb(case.model_dump())))
        else:
            row = conn.execute('''SELECT * FROM platform.pilot_cohort
                WHERE project_id=%s AND plan_checksum=%s''', (project_id, digest)).fetchone()
    return {**dict(row), 'registered_cases': 20, 'execution_verified': False}


def inventory(repo, project_id):
    with repo.conn() as conn:
        cohorts = conn.execute('''SELECT * FROM platform.pilot_cohort
            WHERE project_id=%s ORDER BY created_at DESC,cohort_id''', (project_id,)).fetchall()
        result = []
        for cohort in cohorts:
            cases = conn.execute('''SELECT case_key,ordinal,definition
                FROM platform.pilot_cohort_case WHERE cohort_id=%s ORDER BY ordinal''',
                (cohort['cohort_id'],)).fetchall()
            if len(cases) != 20:
                raise ValueError('PILOT_COHORT_INCOMPLETE')
            result.append({**dict(cohort), 'registered_cases': 20,
                           'cases': [dict(case) for case in cases],
                           'execution_verified': False, 'comparison_ready': False,
                           'limitations': ['登錄不等於執行通過；尚待案例 Task 綁定、執行證據與人工基準。']})
    return {'project_id': str(project_id), 'cohorts': result}
