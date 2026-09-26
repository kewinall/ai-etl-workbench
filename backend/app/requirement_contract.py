"""Operator-supplied conditions; never infer business values or execute SQL."""
import re
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class RequirementConditionsV1(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    version: Literal[1] = 1
    write_mode: Literal['APPEND', 'REPLACE', 'UPSERT'] | None = None
    date_scope: Literal['ALL', 'RANGE'] | None = None
    date_column: str = Field(default='', max_length=120)
    start_date: str = Field(default='', max_length=10)
    end_date_exclusive: str = Field(default='', max_length=10)
    key_columns: list[str] = Field(default_factory=list, max_length=32)


def condition_issues(snapshot):
    raw = (snapshot.get('target_config') or {}).get('requirements_v1') or {}
    issues = []
    def issue(kind, field, message):
        issues.append(dict(issue_type=kind, field_path='requirements_v1.' + field, message=message,
                           suggestion={'required': True}))
    try:
        values = RequirementConditionsV1.model_validate(raw)
    except Exception:
        issue('UNSUPPORTED', 'version', '需求條件格式不合法，請重新填寫結構化條件')
        return issues
    if not values.write_mode:
        issue('MISSING', 'write_mode', '請明確選擇新增、覆寫或鍵值合併；平台不會自行推測寫入模式')
    recent = re.search(r'最近|近期|最新|\brecent\b|\blatest\b', snapshot.get('requirement_text', ''), re.I)
    if not values.date_scope:
        issue('AMBIGUOUS' if recent else 'MISSING', 'date_scope', '請指定資料期間；「最近」等文字不能替代明確期間' if recent else '請確認使用全部資料或指定日期範圍')
    if recent and values.date_scope == 'ALL':
        issue('CONFLICT', 'date_scope', '需求含相對時間用語，但選擇全部資料；請修正文字或指定日期範圍')
    sources = (snapshot.get('source_config') or {}).get('sources') or []
    fields = [field.get('name') for source in sources for field in source.get('fields', [])]
    # Gate validates intent; execution capabilities are checked separately by
    # the runtime authorization path, never granted by CHECKED alone.
    from .join_contract import join_condition_issues
    issues.extend(join_condition_issues(snapshot))
    if values.date_scope == 'ALL' and any((values.date_column, values.start_date, values.end_date_exclusive)):
        issue('CONFLICT', 'date_scope', '全部資料不可同時指定日期篩選條件')
    if values.date_scope == 'RANGE':
        if not values.date_column or fields.count(values.date_column) != 1:
            issue('MISSING', 'date_column', '請選擇來源中唯一存在的日期欄位；缺少欄位 metadata 時不可繼續')
        dates = []
        for field in ('start_date', 'end_date_exclusive'):
            value = getattr(values, field)
            try:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                    raise ValueError()
                dates.append(date.fromisoformat(value))
            except ValueError:
                issue('MISSING', field, '請填寫有效 YYYY-MM-DD 日期；起日包含、迄日不包含')
        if len(dates) == 2 and dates[0] >= dates[1]:
            issue('CONFLICT', 'end_date_exclusive', '不包含的迄日必須晚於起日')
    if values.write_mode == 'UPSERT':
        if not values.key_columns or len(set(values.key_columns)) != len(values.key_columns) or any(fields.count(key) != 1 for key in values.key_columns):
            issue('MISSING', 'key_columns', '鍵值合併須指定不重複且存在於來源的鍵欄位')
    return issues
