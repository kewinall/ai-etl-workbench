"""Explicit two-source equijoin intent, not permission to compile or execute.

Keep this separate from RequirementConditionsV1 so existing single-source
canonical documents and approval checksums do not acquire new default fields.
The initial contract covers one INNER/LEFT join; all choices are required.
"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


class JoinKeyV1(BaseModel):
    model_config = ConfigDict(extra='forbid')
    left_column: StrictStr = Field(min_length=1, max_length=120)
    right_column: StrictStr = Field(min_length=1, max_length=120)

    @field_validator('left_column', 'right_column')
    @classmethod
    def valid_column(cls, value):
        if not value.strip() or '\x00' in value:
            raise ValueError('JOIN_COLUMN_REQUIRED')
        return value


class JoinV1(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[a-z_][a-z0-9_]{0,62}$')
    left_source: Literal['source.0']
    right_source: Literal['source.1']
    join_type: Literal['INNER', 'LEFT']
    keys: list[JoinKeyV1] = Field(min_length=1, max_length=32)
    null_key_policy: Literal['NEVER_MATCH']
    duplicate_key_policy: Literal['EXPAND']
    string_comparison: Literal['CASE_SENSITIVE_NO_TRIM']


class JoinContractV1(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: Literal[1]
    joins: list[JoinV1] = Field(min_length=1, max_length=1)

    @field_validator('version', mode='before')
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError('INTEGER_VERSION_REQUIRED')
        return value


def join_condition_issues(snapshot):
    sources = (snapshot.get('source_config') or {}).get('sources') or []
    raw = (snapshot.get('target_config') or {}).get('join_contract_v1')
    if len(sources) <= 1 and raw is None:
        return []
    issues = []

    def issue(kind, path, message):
        issues.append(dict(issue_type=kind, field_path='join_contract_v1' + path,
                           message=message, suggestion={'required': True}))

    if raw is None:
        issue('MISSING', '', '多來源必須明確指定 Join 類型、左右來源、鍵值與 null／重複鍵政策')
        return issues
    try:
        contract = JoinContractV1.model_validate(raw)
    except ValueError:
        issue('UNSUPPORTED', '', 'Join 契約格式不合法；僅接受明確的雙來源 INNER／LEFT 等值 Join，不接受 SQL 或推測預設值')
        return issues
    if len(sources) != 2:
        issue('UNSUPPORTED', '.joins', '此版本 Join 契約必須恰有兩個來源，不可省略或忽略其他來源')
        return issues
    join = contract.joins[0]
    for side, source in [('left', sources[0]), ('right', sources[1])]:
        fields = [field.get('name') for field in source.get('fields') or []]
        seen = set()
        for index, key in enumerate(join.keys):
            name = getattr(key, side + '_column')
            path = f'.joins.0.keys.{index}.{side}_column'
            if fields.count(name) != 1:
                issue('CONFLICT', path, 'Join 鍵必須在指定側來源中唯一存在；不可跨來源猜測同名欄位')
            if name in seen:
                issue('CONFLICT', path, '同側 Join 鍵不可重複')
            seen.add(name)
    return issues


def join_evidence(snapshot):
    """Only schema-checked semantic fields, never opaque target settings."""
    raw = (snapshot.get('target_config') or {}).get('join_contract_v1')
    sources = (snapshot.get('source_config') or {}).get('sources') or []
    if raw is None:
        return {'contract_status': 'MISSING'} if len(sources) > 1 else None
    try:
        value = JoinContractV1.model_validate(raw).model_dump()
    except ValueError:
        return {'contract_status': 'INVALID'}
    return {**value, 'contract_status': 'INVALID' if join_condition_issues(snapshot) else 'INPUT_ONLY_NOT_EXECUTION'}
