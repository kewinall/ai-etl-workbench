"""Operator-confirmed transformation intent, independent of model proposals.

Source references retain source.N.original_name; metrics use $metric.id.
No inference from prose, test answers, SQL, or previously generated designs.
Absent contracts retain legacy behavior, not a claim of semantic verification.
"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .etl_specification import FilterConstantV1, IDENTIFIER


class IntentModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class IntentFilterV1(IntentModel):
    column: str = Field(min_length=1, max_length=300)
    operator: Literal['EQ', 'NE', 'LT', 'LE', 'GT', 'GE', 'IS_NULL', 'IS_NOT_NULL']
    constant: FilterConstantV1 | None

    @model_validator(mode='after')
    def constant_scope(self):
        if (self.operator in ('IS_NULL', 'IS_NOT_NULL')) != (self.constant is None):
            raise ValueError('INTENT_FILTER_CONSTANT_REQUIRED')
        return self


class IntentMetricV1(IntentModel):
    id: str = Field(pattern=IDENTIFIER)
    function: Literal['SUM', 'COUNT_ROWS', 'COUNT_NON_NULL', 'MIN', 'MAX']
    column: str | None = Field(min_length=1, max_length=300)

    @model_validator(mode='after')
    def column_scope(self):
        if (self.function == 'COUNT_ROWS') != (self.column is None):
            raise ValueError('INTENT_METRIC_COLUMN_REQUIRED')
        return self


class IntentAggregationV1(IntentModel):
    group_by: list[str] = Field(min_length=1, max_length=32)
    metrics: list[IntentMetricV1] = Field(min_length=1, max_length=100)
    null_policy: Literal['SQL_NULLS']


class TransformationContractV1(IntentModel):
    version: Literal[1]
    filters: list[IntentFilterV1] = Field(max_length=100)
    filter_logic: Literal['ALL']
    filter_null_policy: Literal['EXCLUDE_UNKNOWN']
    aggregation: IntentAggregationV1 | None
    output_columns: list[str] = Field(min_length=1, max_length=200)

    @field_validator('version', mode='before')
    @classmethod
    def strict_version(cls, value):
        if type(value) is not int:
            raise ValueError('INTENT_INTEGER_VERSION_REQUIRED')
        return value


def source_refs(snapshot):
    return [f'source.{index}.{field.get("name", "")}'
            for index, source in enumerate((snapshot.get('source_config') or {}).get('sources') or [])
            for field in source.get('fields') or []]


def parsed_intent(snapshot):
    """Fail closed for present-but-null/invalid contracts; absence is legacy."""
    target = snapshot.get('target_config') or {}
    if 'transformation_contract_v1' not in target:
        return None
    value = TransformationContractV1.model_validate(target['transformation_contract_v1'])
    refs = source_refs(snapshot)
    if len(set(refs)) != len(refs) or not refs:
        raise ValueError('INTENT_SOURCE_IDENTITY_INVALID')
    if any(item.column not in refs for item in value.filters):
        raise ValueError('INTENT_FILTER_SOURCE_UNKNOWN')
    outputs = refs
    if value.aggregation:
        agg = value.aggregation
        ids = [metric.id for metric in agg.metrics]
        if len(set(ids)) != len(ids) or len(set(agg.group_by)) != len(agg.group_by):
            raise ValueError('INTENT_DUPLICATE_GROUP_OR_METRIC')
        if any(column not in refs for column in agg.group_by):
            raise ValueError('INTENT_GROUP_SOURCE_UNKNOWN')
        if any(metric.column is not None and metric.column not in refs for metric in agg.metrics):
            raise ValueError('INTENT_METRIC_SOURCE_UNKNOWN')
        outputs = agg.group_by + ['$metric.' + metric.id for metric in agg.metrics]
    if len(set(value.output_columns)) != len(value.output_columns) or any(column not in outputs for column in value.output_columns):
        raise ValueError('INTENT_OUTPUT_UNKNOWN_OR_DUPLICATE')
    return value


def intent_evidence(snapshot):
    try:
        value = parsed_intent(snapshot)
        return value.model_dump(mode='json') if value is not None else None
    except ValueError:
        return {'invalid': True}


def intent_issues(snapshot):
    try:
        parsed_intent(snapshot)
        return []
    except ValueError:
        return [dict(issue_type='UNSUPPORTED', field_path='target_config.transformation_contract_v1',
                     message='轉換意圖格式、來源欄位或輸出不合法；請補正後建立新版本',
                     suggestion={'required': True})]


def validate_intent(spec, snapshot, naming):
    try:
        intent = parsed_intent(snapshot)
    except ValueError:
        return [dict(code='SPEC_INTENT_INVALID', field_path='transformation_contract_v1',
                     message='已確認轉換意圖不合法，不可由設計自行取代')]
    if intent is None:
        return []
    multi = len((snapshot.get('source_config') or {}).get('sources') or []) > 1
    names = {column['source_name']: column['english_name'] for column in
             (naming.get('contract_json') or {}).get('columns') or []
             if isinstance(column.get('source_name'), str) and isinstance(column.get('english_name'), str)}
    def resolve(ref):
        key = ref if multi or ref.startswith('$metric.') else ref.removeprefix('source.0.')
        return names[key]
    try:
        wanted = intent.model_dump(mode='json')
        wanted.pop('version')
        for item in wanted['filters']:
            item['column'] = resolve(item['column'])
        if wanted['aggregation']:
            agg = wanted['aggregation']
            agg['group_by'] = [resolve(ref) for ref in agg['group_by']]
            for metric in agg['metrics']:
                metric['output_column'] = resolve('$metric.' + metric['id'])
                if metric['column'] is not None:
                    metric['column'] = resolve(metric['column'])
        wanted['output_columns'] = [resolve(ref) for ref in wanted['output_columns']]
    except KeyError:
        return [dict(code='SPEC_INTENT_NAMING_MISSING', field_path='naming',
                     message='轉換意圖欄位缺少已確認命名，不可猜測或忽略')]
    actual = spec.model_dump(mode='json')
    issues = []
    def compare(expected, observed, path):
        if type(expected) is type(observed) and expected == observed:
            return
        if isinstance(expected, dict) and isinstance(observed, dict) and expected.keys() == observed.keys():
            for key in expected:
                compare(expected[key], observed[key], path + '.' + key)
        elif isinstance(expected, list) and isinstance(observed, list) and len(expected) == len(observed):
            for index, (left, right) in enumerate(zip(expected, observed)):
                compare(left, right, path + '.' + str(index))
        else:
            issues.append(dict(code='SPEC_TRANSFORMATION_INTENT_MISMATCH', field_path=path,
                requirement_path='transformation_contract_v1.' + path,
                node_id='aggregate' if path.startswith('aggregation') else 'projection' if path.startswith('output_columns') else 'filter',
                expected=expected, actual=observed,
                message='設計與已確認轉換意圖不同；請修正规格或建立需求新版本'))
    for key in wanted:
        compare(wanted[key], actual[key], key)
    return issues
