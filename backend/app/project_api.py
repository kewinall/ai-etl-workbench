"""Project API independent of the legacy application entrypoint."""
from datetime import datetime
from typing import Any
from uuid import UUID
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from psycopg.errors import UniqueViolation


class ProjectPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    project_name: str = Field(min_length=2, max_length=120)
    description: str = Field(default='', max_length=4000)
    default_ai_profile: str = Field(default='nova-default', max_length=120)
    default_connection: str = Field(default='vertica-default', max_length=120)
    naming_rules: dict[str, Any] = Field(default_factory=dict)
    expected_updated_at: datetime | None = None

    @field_validator('naming_rules')
    @classmethod
    def validate_dictionary(cls, value):
        aliases = value.get('column_aliases', {})
        if not isinstance(aliases, dict):
            raise ValueError('column_aliases 必須是名稱對照表')
        for source, target in aliases.items():
            if not isinstance(source, str) or not source.strip():
                raise ValueError('原始名稱不可空白')
            if not isinstance(target, str) or not re.fullmatch(r'[a-z_][a-z0-9_]{0,59}', target):
                raise ValueError('英文名稱必須是 1–60 字元的小寫 snake_case')
        return value


class ProjectConflict(Exception):
    pass


def create_project_router(repo) -> APIRouter:
    router = APIRouter(prefix='/api/projects', tags=['projects'])

    @router.get('')
    def list_projects():
        return repo.list_projects()

    @router.get('/{project_id}')
    def get_project(project_id: UUID):
        project = repo.get_project(str(project_id))
        if project is None:
            raise HTTPException(404, detail={'code': 'PROJECT_NOT_FOUND', 'message': '找不到此專案'})
        return project

    @router.get('/{project_id}/tasks')
    def list_project_tasks(project_id: UUID):
        get_project(project_id)
        return repo.list_tasks(project_id=str(project_id))

    @router.get('/{project_id}/summary')
    def summary(project_id: UUID):
        from .project_summary import project_summary
        try:
            get_project(project_id)
            return project_summary(repo,str(project_id))
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503,detail={'code':'PROJECT_SUMMARY_UNAVAILABLE','message':'專案摘要暫時無法讀取，請重試；不代表沒有 Task。'}) from None

    @router.post('', status_code=201)
    def create_project(data: ProjectPayload):
        try:
            return repo.create_project(data.model_dump(exclude={'expected_updated_at'}))
        except UniqueViolation:
            raise HTTPException(409, detail={'code': 'PROJECT_NAME_EXISTS', 'message': '此專案名稱已存在'}) from None

    @router.put('/{project_id}')
    def update_project(project_id: UUID, data: ProjectPayload):
        get_project(project_id)
        try:
            result = repo.update_project(str(project_id), data.model_dump())
        except UniqueViolation:
            raise HTTPException(409, detail={'code': 'PROJECT_NAME_EXISTS', 'message': '此專案名稱已存在'}) from None
        except ProjectConflict:
            raise HTTPException(409, detail={'code': 'PROJECT_CHANGED', 'message': '專案已被更新，請重新整理後再編輯'}) from None
        if result is None:
            raise HTTPException(404, detail={'code': 'PROJECT_NOT_FOUND', 'message': '找不到此專案'})
        return result

    return router
