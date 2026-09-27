"""Prospective Pilot registration. No caller-supplied success or timing claims."""
from hashlib import sha256
import json
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from psycopg.types.json import Jsonb
from psycopg.errors import UniqueViolation


class PilotEnrollmentConflict(ValueError):
    pass


class PilotTaskBinding(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    task_id: str = Field(min_length=1, max_length=160)


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
            cases = conn.execute('''SELECT c.case_key,c.ordinal,c.definition,b.task_id,b.enrolled_at
                FROM platform.pilot_cohort_case c LEFT JOIN platform.pilot_case_task b
                USING(cohort_id,case_key) WHERE c.cohort_id=%s ORDER BY c.ordinal''',
                (cohort['cohort_id'],)).fetchall()
            if len(cases) != 20:
                raise ValueError('PILOT_COHORT_INCOMPLETE')
            for case in cases:
                # No latest-only selection: failed/cancelled and every revision remain visible.
                case['runs'] = [dict(row) for row in conn.execute('''SELECT run_id,parent_run_id,
                    state,phase,outcome_code,created_at FROM platform.task_run
                    WHERE task_id=%s ORDER BY created_at,run_id''', (case['task_id'],)).fetchall()] if case['task_id'] else []
            result.append({**dict(cohort), 'registered_cases': 20,
                           'bound_cases': sum(case['task_id'] is not None for case in cases),
                           'cases': [dict(case) for case in cases],
                           'execution_verified': False, 'comparison_ready': False,
                           'limitations': ['登錄或綁定不等於樣本指紋已核對或執行通過；尚待情境證據與人工基準。']})
    return {'project_id': str(project_id), 'cohorts': result}


def bind_task(repo, project_id, cohort_id, case_key, task_id):
    try:
        with repo.conn() as conn:
            # Match enqueue's task lock, closing the bind-vs-first-run race.
            task = conn.execute('SELECT project_id FROM platform.task WHERE task_id=%s FOR UPDATE',
                                (task_id,)).fetchone()
            case = conn.execute('''SELECT c.case_key FROM platform.pilot_cohort_case c
                JOIN platform.pilot_cohort p USING(cohort_id)
                WHERE c.cohort_id=%s AND c.case_key=%s AND p.project_id=%s''',
                (cohort_id, case_key, project_id)).fetchone()
            if not task or str(task['project_id']) != str(project_id) or not case:
                raise PilotEnrollmentConflict('案例與 Task 必須存在且屬於相同專案')
            previous = conn.execute('''SELECT * FROM platform.pilot_case_task
                WHERE cohort_id=%s AND case_key=%s''', (cohort_id, case_key)).fetchone()
            if previous:
                if previous['task_id'] == task_id:
                    return dict(previous)
                raise PilotEnrollmentConflict('案例已綁定，不可改選其他 Task')
            if conn.execute('SELECT 1 FROM platform.task_run WHERE task_id=%s LIMIT 1', (task_id,)).fetchone():
                raise PilotEnrollmentConflict('Task 已開始執行準備，不可事後納入前瞻比較')
            return dict(conn.execute('''INSERT INTO platform.pilot_case_task(cohort_id,case_key,task_id)
                VALUES(%s,%s,%s) RETURNING *''', (cohort_id, case_key, task_id)).fetchone())
    except UniqueViolation:
        raise PilotEnrollmentConflict('案例或 Task 已綁定，不可重複計入') from None
