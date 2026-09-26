"""Versioned ETL design contract and pure validation; no SQL, files, model or execution.

V1's implemented design subset is one CSV, AND predicates, optional grouped
aggregates, explicit projection and APPEND. Unsupported capabilities fail closed.
Derived naming entries use source_name='$metric.<metric id>' in the existing
NamingContractV1. This module never confirms a draft naming contract or design.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator
from .csv_contract import CsvInputContractV1, validated_csv_contracts
from .control_worker import check_requirements
from .platform_harness import checksum as naming_checksum
from .sa_contract import digest
from .join_contract import JoinV1
from .join_semantics import validate_join_semantics

IDENTIFIER = r'^[a-z_][a-z0-9_]{0,62}$'
SHA256 = r'^[a-f0-9]{64}$'


class ContractModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class NamingReferenceV1(ContractModel):
    contract_id: UUID
    version: StrictInt = Field(ge=1)
    checksum: str = Field(pattern=SHA256)


class FilterConstantV1(ContractModel):
    type: Literal['INTEGER', 'DECIMAL', 'STRING', 'BOOLEAN', 'DATE']
    value: StrictInt | StrictBool | str

    @model_validator(mode='after')
    def exact_value(self):
        value = self.value
        if self.type == 'INTEGER' and (type(value) is not int or not -(2**63) <= value < 2**63):
            raise ValueError('INTEGER_LITERAL_REQUIRED')
        if self.type == 'BOOLEAN' and type(value) is not bool:
            raise ValueError('BOOLEAN_LITERAL_REQUIRED')
        if self.type == 'STRING' and (type(value) is not str or len(value) > 2000 or '\x00' in value):
            raise ValueError('STRING_LITERAL_REQUIRED')
        if self.type == 'DECIMAL':
            if type(value) is not str or not re.fullmatch(r'-?\d{1,38}(?:\.\d{1,18})?', value):
                raise ValueError('EXACT_DECIMAL_STRING_REQUIRED')
            try:
                if not Decimal(value).is_finite():
                    raise ValueError('FINITE_DECIMAL_REQUIRED')
            except InvalidOperation:
                raise ValueError('EXACT_DECIMAL_STRING_REQUIRED') from None
        if self.type == 'DATE':
            if type(value) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                raise ValueError('ISO_DATE_REQUIRED')
            date.fromisoformat(value)
        return self


class FilterPredicateV1(ContractModel):
    column: str = Field(pattern=IDENTIFIER)
    operator: Literal['EQ', 'NE', 'LT', 'LE', 'GT', 'GE', 'IS_NULL', 'IS_NOT_NULL']
    constant: FilterConstantV1 | None

    @model_validator(mode='after')
    def constant_scope(self):
        if (self.operator in ('IS_NULL', 'IS_NOT_NULL')) != (self.constant is None):
            raise ValueError('FILTER_CONSTANT_SCOPE_MISMATCH')
        return self


class MetricV1(ContractModel):
    id: str = Field(pattern=IDENTIFIER)
    function: Literal['SUM', 'COUNT_ROWS', 'COUNT_NON_NULL', 'MIN', 'MAX']
    column: str | None = Field(pattern=IDENTIFIER)
    output_column: str = Field(pattern=IDENTIFIER)

    @model_validator(mode='after')
    def source_scope(self):
        if (self.function == 'COUNT_ROWS') != (self.column is None):
            raise ValueError('METRIC_SOURCE_SCOPE_MISMATCH')
        return self


class AggregationV1(ContractModel):
    group_by: list[str] = Field(min_length=1, max_length=32)
    metrics: list[MetricV1] = Field(min_length=1, max_length=100)
    null_policy: Literal['SQL_NULLS']


class EtlSpecificationV1(ContractModel):
    version: Literal[1]
    run_id: UUID
    input_checksum: str = Field(pattern=SHA256)
    settings_checksum: str = Field(pattern=SHA256)
    naming: NamingReferenceV1
    source_ref: Literal['source.0']
    target_schema: str = Field(pattern=IDENTIFIER)
    target_table: str = Field(pattern=IDENTIFIER)
    write_mode: Literal['APPEND', 'REPLACE', 'UPSERT']
    filters: list[FilterPredicateV1] = Field(max_length=100)
    filter_logic: Literal['ALL']
    # Ordinary comparisons discard null operands. IS_NULL is explicit.
    filter_null_policy: Literal['EXCLUDE_UNKNOWN']
    aggregation: AggregationV1 | None
    output_columns: list[str] = Field(min_length=1, max_length=200)

    @field_validator('version', mode='before')
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError('INTEGER_VERSION_REQUIRED')
        return value


class EtlSpecificationV2(ContractModel):
    """Two-source Join design. V1 model/canonical output remains unchanged."""
    version: Literal[2]
    run_id: UUID
    input_checksum: str = Field(pattern=SHA256)
    settings_checksum: str = Field(pattern=SHA256)
    naming: NamingReferenceV1
    source_refs: list[Literal['source.0', 'source.1']] = Field(min_length=2, max_length=2)
    joins: list[JoinV1] = Field(min_length=1, max_length=1)
    target_schema: str = Field(pattern=IDENTIFIER)
    target_table: str = Field(pattern=IDENTIFIER)
    write_mode: Literal['APPEND', 'REPLACE', 'UPSERT']
    filters: list[FilterPredicateV1] = Field(max_length=100)
    filter_logic: Literal['ALL']
    filter_null_policy: Literal['EXCLUDE_UNKNOWN']
    aggregation: AggregationV1 | None
    output_columns: list[str] = Field(min_length=1, max_length=200)

    @field_validator('version', mode='before')
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError('INTEGER_VERSION_REQUIRED')
        return value

    @field_validator('source_refs')
    @classmethod
    def exact_sources(cls, value):
        if value != ['source.0', 'source.1']:
            raise ValueError('JOIN_SOURCE_ORDER_MISMATCH')
        return value


def _type(value):
    """Compiler subset, not a claim to support all Vertica SQL types."""
    if not isinstance(value, str):
        return None
    value = value.upper()
    # File profiling emits DECIMAL; it is the same exact precision/scale
    # family as NUMERIC, not a cast or permission to narrow the source.
    value = re.sub(r'^DECIMAL\(', 'NUMERIC(', value)
    if value in ('INTEGER', 'INT', 'BIGINT'):
        return ('INTEGER', value, None, None)
    if value in ('BOOLEAN', 'DATE', 'TIMESTAMP'):
        return (value, value, None, None)
    match = re.fullmatch(r'NUMERIC\(([1-9]\d?),([0-9]\d?)\)', value)
    if match:
        precision, scale = map(int, match.groups())
        if precision <= 38 and scale <= min(precision, 18):
            return ('DECIMAL', value, precision, scale)
    match = re.fullmatch(r'VARCHAR\(([1-9]\d{0,4})\)', value)
    if match and int(match[1]) <= 65000:
        return ('STRING', value, int(match[1]), None)
    return None


def validate_specification(payload, run, naming):
    """Return inspectable errors and a bound validated design; never grant execution.

The caller must load run and naming from trusted storage, not model/user claims.
Full SQL semantics against business intent still require human review and QA.
"""
    issues = []
    def issue(code, path, message):
        issues.append({'code': code, 'field_path': path, 'message': message})
    try:
        model = EtlSpecificationV2 if isinstance(payload, dict) and payload.get('version') == 2 else EtlSpecificationV1
        spec = model.model_validate(payload)
    except ValueError:
        return {'status': 'INVALID', 'issues': [{'code': 'SPEC_SCHEMA_INVALID', 'field_path': 'specification', 'message': '規格格式不合法或包含不支援的 SQL／轉換欄位'}], 'execution_authorized': False}
    snapshot = run['input_snapshot']
    multi = isinstance(spec, EtlSpecificationV2)
    if multi:
        issues.extend(validate_join_semantics([join.model_dump() for join in spec.joins], snapshot))
    if str(spec.run_id) != str(run['run_id']) or spec.input_checksum != run['input_checksum'] or spec.settings_checksum != run['settings_snapshot']['checksum']:
        issue('SPEC_VERSION_MISMATCH', 'run_id', '規格與輸入或設定版本不一致')
    if run.get('matches_current') is not True or (run.get('approval') or {}).get('decision') != 'APPROVE' or run.get('state') != 'NEEDS_REVIEW' or run.get('write_started') is not False:
        issue('SPEC_INPUT_NOT_APPROVED', 'run_id', '須為目前未寫入、已確認輸入並等待人工檢查的版本')
    if check_requirements(snapshot)['status'] != 'CHECKED' or (run.get('gate_result') or {}).get('status') != 'CHECKED':
        issue('SPEC_GATE_BLOCKED', 'run_id', '目前需求檢查未通過，不可由規格覆蓋阻擋')
    target = snapshot.get('target_config') or {}
    conditions = target.get('requirements_v1') or {}
    if (spec.target_schema, spec.target_table, spec.write_mode) != (target.get('schema'), target.get('table'), conditions.get('write_mode')):
        issue('SPEC_TARGET_MISMATCH', 'target_table', '目標或寫入模式與已確認輸入不一致')
    if spec.write_mode != 'APPEND':
        issue('SPEC_WRITE_MODE_UNSUPPORTED', 'write_mode', '新版編譯接點尚未支援覆寫或合併，不會改成新增模式')
    source_config = snapshot.get('source_config') or {}
    sources = source_config.get('sources') or []
    if len(sources) != (2 if multi else 1) or any(source.get('type') != 'CSV' for source in sources):
        issue('SPEC_SOURCE_UNSUPPORTED', 'source_ref', '來源數量或型別不符合規格版本；V1 單 CSV、V2 雙 CSV，不得忽略來源')
    columns = (naming.get('contract_json') or {}).get('columns') or []
    if naming.get('status') != 'CONFIRMED' or naming.get('task_id') != run.get('task_id') or not run.get('task_id'):
        issue('SPEC_NAMING_UNCONFIRMED', 'naming', '命名契約未確認或不屬於此 Task')
    if str(spec.naming.contract_id) != str(naming.get('contract_id')) or spec.naming.version != naming.get('version') or spec.naming.checksum != naming.get('checksum') or naming_checksum(columns) != spec.naming.checksum:
        issue('SPEC_NAMING_VERSION_MISMATCH', 'naming', '命名契約版本或 checksum 不一致')
    by_source, by_name, types = {}, {}, {}
    for index, column in enumerate(columns):
        original, name = column.get('source_name'), column.get('english_name')
        if not isinstance(original, str) or not isinstance(name, str) or not re.fullmatch(IDENTIFIER, name) or original in by_source or name in by_name:
            issue('SPEC_NAMING_COLLISION', f'naming.columns.{index}', '命名格式不合法或重複')
            continue
        by_source[original] = name; by_name[name] = column
        types[name] = _type(column.get('vertica_type'))
        if not types[name]:
            issue('SPEC_TYPE_UNSUPPORTED', f'naming.columns.{index}', '型別不在新版編譯支援範圍，不能自行降級為字串')
    source_names = []
    if any(not isinstance(field.get('name'), str) or not field['name'] or '\x00' in field['name']
           for source in sources for field in source.get('fields', [])):
        issue('SPEC_SOURCE_FIELDS_INVALID', 'source_ref', '來源欄位名稱缺漏或不合法，不可忽略該欄位')
    source_fields = [(f'source.{index}.' + field['name'] if multi else field['name'], field)
                     for index, source in enumerate(sources) for field in source.get('fields', [])
                     if isinstance(field.get('name'), str)]
    for source_name, field in source_fields:
        mapped = by_source.get(source_name)
        if not mapped:
            issue('SPEC_SOURCE_NAMING_MISSING', 'naming.columns', '來源欄位缺少已確認的英文命名')
        else:
            source_names.append(mapped)
            declared = str(field.get('type') or '').upper()
            declared_type = _type(declared)
            family = declared_type[0] if declared_type else {'NUMERIC': 'DECIMAL', 'VARCHAR': 'STRING'}.get(declared)
            named_type = types.get(mapped)
            if not family or (named_type and family != named_type[0]):
                issue('SPEC_SOURCE_TYPE_MISMATCH', 'naming.columns', '來源與命名契約型別不同；必須明確補正，不可隱含轉型')
            if declared_type and named_type and family == named_type[0]:
                if (family == 'DECIMAL' and (named_type[2] < declared_type[2] or named_type[3] != declared_type[3])) or (family == 'STRING' and named_type[2] < declared_type[2]) or (family == 'INTEGER' and declared_type[1] == 'BIGINT' and named_type[1] != 'BIGINT'):
                    issue('SPEC_SOURCE_TYPE_NARROWING', 'naming.columns', '命名契約不能縮減來源宣告的精度或字串長度')
    if not source_names or len(set(source_names)) != len(source_names):
        issue('SPEC_SOURCE_FIELDS_INVALID', 'source_ref', '來源欄位不存在或重複')
    if multi:
        join = spec.joins[0]
        reserved = {'source_0', 'source_1', 'join_right_filter', 'join_discard', 'join_left_sort',
                    'join_right_sort', 'filter', 'discard', 'sort', 'aggregate', 'projection', 'target'}
        if join.id in reserved:
            issue('SPEC_JOIN_NODE_ID_RESERVED', 'joins.0.id', 'Join 節點名稱與程式產生的節點衝突')
        for index, key in enumerate(join.keys):
            left = by_source.get(join.left_source + '.' + key.left_column)
            right = by_source.get(join.right_source + '.' + key.right_column)
            if left not in source_names or right not in source_names:
                issue('SPEC_JOIN_KEY_NAMING_MISSING', f'joins.0.keys.{index}', 'Join 鍵缺少來源限定的命名對應')
            elif not types.get(left) or not types.get(right) or types[left][0] != types[right][0]:
                issue('SPEC_JOIN_KEY_TYPE_MISMATCH', f'joins.0.keys.{index}', 'Join 鍵型別不相容，不可隱含轉型')
    range_column = None
    if conditions.get('date_scope') == 'RANGE':
        range_column = by_source.get(conditions.get('date_column'))
        if multi:
            matching = [name for name, field in source_fields if field['name'] == conditions.get('date_column')]
            range_column = by_source.get(matching[0]) if len(matching) == 1 else None
        range_type = types.get(range_column)
        if range_column not in source_names or not range_type or range_type[0] not in ('DATE', 'TIMESTAMP'):
            issue('SPEC_DATE_RANGE_COLUMN_TYPE', 'filters', '日期範圍須引用已確認來源 DATE／TIMESTAMP 欄位，不可用字串隱含比較')
        # Exactly two predicates on this column. Extra predicates could silently
        # narrow the approved interval; duplicates also require correction.
        expected = {('GE', 'DATE', conditions.get('start_date')),
                    ('LT', 'DATE', conditions.get('end_date_exclusive'))}
        actual = [p for p in spec.filters if p.column == range_column]
        observed = {(p.operator, p.constant.type, p.constant.value) for p in actual if p.constant}
        if len(actual) != 2 or observed != expected:
            issue('SPEC_DATE_RANGE_FILTER_MISMATCH', 'filters', '日期 Filter 必須恰為已確認起日的 >= 與不包含迄日的 <；不得省略、改值或追加同欄位條件')
    for index, predicate in enumerate(spec.filters):
        path = f'filters.{index}'
        kind = types.get(predicate.column)
        if predicate.column not in source_names:
            issue('SPEC_FILTER_COLUMN_UNKNOWN', path, 'Filter 必須引用來源中的已確認欄位')
        elif predicate.constant and kind:
            # A RANGE uses date boundaries at midnight in the same local
            # timestamp domain as CSVInput; no timezone conversion is inferred.
            range_midnight = (predicate.column == range_column and kind[0] == 'TIMESTAMP'
                              and predicate.constant.type == 'DATE')
            if predicate.constant.type != kind[0] and not range_midnight:
                issue('SPEC_FILTER_TYPE_MISMATCH', path, 'Filter 常數型別與欄位型別不同')
            if kind[0] == 'BOOLEAN' and predicate.operator not in ('EQ', 'NE'):
                issue('SPEC_BOOLEAN_ORDER_UNSUPPORTED', path, '布林欄位不能使用大小排序比較')
    available = set(source_names)
    expected_metric_names = set()
    if spec.aggregation:
        aggregation = spec.aggregation
        if len(set(aggregation.group_by)) != len(aggregation.group_by) or any(name not in available for name in aggregation.group_by):
            issue('SPEC_GROUP_COLUMNS_INVALID', 'aggregation.group_by', '分組欄位須不重複且存在於來源')
        metric_ids = set()
        available = set(aggregation.group_by)
        for index, metric in enumerate(aggregation.metrics):
            path = f'aggregation.metrics.{index}'
            ref = '$metric.' + metric.id
            expected_metric_names.add(ref)
            if metric.id in metric_ids or metric.output_column in available or metric.output_column in source_names:
                issue('SPEC_METRIC_COLLISION', path, '聚合 ID 或輸出名稱重複，不能覆蓋來源欄位')
            metric_ids.add(metric.id); available.add(metric.output_column)
            if by_source.get(ref) != metric.output_column:
                issue('SPEC_METRIC_NAMING_MISSING', path, '聚合輸出須包含於同一已確認命名契約')
            src_type, out_type = types.get(metric.column), types.get(metric.output_column)
            if metric.column is not None and metric.column not in source_names:
                issue('SPEC_METRIC_COLUMN_UNKNOWN', path, '聚合輸入欄位不存在於來源')
            if metric.function in ('COUNT_ROWS', 'COUNT_NON_NULL'):
                valid_type = out_type and out_type[1] == 'BIGINT'
            elif metric.function == 'SUM':
                valid_type = src_type and out_type and ((src_type[0] == 'INTEGER' and out_type[1] == 'BIGINT') or (src_type[0] == out_type[0] == 'DECIMAL' and out_type[2] >= src_type[2] and out_type[3] == src_type[3]))
            else:
                valid_type = src_type and out_type and src_type == out_type
            if not valid_type:
                issue('SPEC_METRIC_TYPE_MISMATCH', path, '聚合輸出型別不相容或存在精度縮減')
    expected_sources = {name for name, field in source_fields}
    if set(by_source) != expected_sources | expected_metric_names:
        issue('SPEC_NAMING_COVERAGE_MISMATCH', 'naming.columns', '命名契約必須恰好涵蓋來源與聚合輸出，不得夾帶其他欄位')
    if len(set(spec.output_columns)) != len(spec.output_columns) or any(name not in available for name in spec.output_columns):
        issue('SPEC_OUTPUT_COLUMNS_INVALID', 'output_columns', '輸出欄位重複，或引用聚合後不再存在的來源欄位')
    result = {'status': 'INVALID' if issues else 'VALIDATED_NOT_APPROVED', 'issues': issues, 'execution_authorized': False}
    if not issues:
        canonical = spec.model_dump(mode='json')
        csv_contract = ({'csv_input_contracts': validated_csv_contracts(source_config)['sources']} if multi else
                        {'csv_input_contract': CsvInputContractV1.model_validate(source_config['csv_input_contract_v1']).model_dump()})
        result.update(specification=canonical, specification_checksum=digest(canonical), **csv_contract,
                      output_types={name: by_name[name]['vertica_type'] for name in spec.output_columns})
    return result


def compilation_plan(payload, run, naming):
    """A deterministic compiler input plan, not HPL, an artifact or engine result."""
    result = validate_specification(payload, run, naming)
    if result['status'] != 'VALIDATED_NOT_APPROVED':
        return result
    spec = result['specification']
    by_source = {column['source_name']: column for column in naming['contract_json']['columns']}
    if spec['version'] == 2:
        return _join_compilation_plan(result, run, by_source)
    fields = [{'source_name': field['name'], 'stream_name': by_source[field['name']]['english_name'], 'data_type': by_source[field['name']]['vertica_type']}
              for field in run['input_snapshot']['source_config']['sources'][0]['fields']]
    stages = [{'id': 'source', 'component': 'CSVInput', 'source_ref': spec['source_ref'], 'contract': result['csv_input_contract'], 'fields': fields}]
    if spec['filters']:
        stages.append({'id': 'filter', 'component': 'FilterRows', 'logic': spec['filter_logic'], 'null_policy': spec['filter_null_policy'], 'predicates': spec['filters'], 'on_false': 'DISCARD'})
    if spec['aggregation']:
        stages.extend([{'id': 'sort', 'component': 'SortRows', 'columns': spec['aggregation']['group_by'], 'case_sensitive': True},
                       {'id': 'aggregate', 'component': 'GroupBy', **spec['aggregation']}])
    stages.extend([{'id': 'projection', 'component': 'SelectValues', 'columns': spec['output_columns']},
                   {'id': 'target', 'component': 'TableOutput', 'schema': spec['target_schema'], 'table': spec['target_table'], 'write_mode': spec['write_mode']}])
    plan = {'version': 1, 'specification_checksum': result['specification_checksum'], 'naming_checksum': spec['naming']['checksum'], 'stages': stages,
            'edges': [{'from': stages[i]['id'], 'to': stages[i+1]['id']} for i in range(len(stages)-1)]}
    return {**result, 'plan': plan, 'plan_checksum': digest(plan), 'compiler_status': 'PLAN_ONLY_HPL_NOT_GENERATED'}


def _join_compilation_plan(result, run, by_source):
    spec = result['specification']; join = spec['joins'][0]
    stages = []
    for index, source in enumerate(run['input_snapshot']['source_config']['sources']):
        ref = f'source.{index}'
        fields = [{'source_name': field['name'], 'stream_name': by_source[ref + '.' + field['name']]['english_name'],
                   'data_type': by_source[ref + '.' + field['name']]['vertica_type']} for field in source['fields']]
        stages.append({'id': f'source_{index}', 'component': 'CSVInput', 'source_ref': ref,
                       'parameter': f'SOURCE_CSV_{index}', 'contract': result['csv_input_contracts'][ref], 'fields': fields})
    left_keys = [by_source[join['left_source'] + '.' + key['left_column']]['english_name'] for key in join['keys']]
    right_keys = [by_source[join['right_source'] + '.' + key['right_column']]['english_name'] for key in join['keys']]
    stages.extend([
        {'id': 'join_right_filter', 'component': 'FilterRows', 'logic': 'ALL', 'null_policy': 'EXCLUDE_UNKNOWN',
         'predicates': [{'column': key, 'operator': 'IS_NOT_NULL', 'constant': None} for key in right_keys],
         'on_false': 'DISCARD', 'discard_id': 'join_discard'},
        {'id': 'join_left_sort', 'component': 'SortRows', 'columns': left_keys, 'case_sensitive': True},
        {'id': 'join_right_sort', 'component': 'SortRows', 'columns': right_keys, 'case_sensitive': True},
        {'id': join['id'], 'component': 'MergeJoin', 'join_type': join['join_type'],
         'left_transform': 'join_left_sort', 'right_transform': 'join_right_sort',
         'left_keys': left_keys, 'right_keys': right_keys}])
    edges = [{'from': a, 'to': b} for a,b in [('source_0', 'join_left_sort'), ('source_1', 'join_right_filter'),
        ('join_right_filter', 'join_right_sort'), ('join_left_sort', join['id']), ('join_right_sort', join['id'])]]
    tail = []
    if spec['filters']:
        tail.append({'id': 'filter', 'component': 'FilterRows', 'logic': 'ALL', 'null_policy': spec['filter_null_policy'],
                     'predicates': spec['filters'], 'on_false': 'DISCARD'})
    if spec['aggregation']:
        tail.extend([{'id': 'sort', 'component': 'SortRows', 'columns': spec['aggregation']['group_by'], 'case_sensitive': True},
                     {'id': 'aggregate', 'component': 'GroupBy', **spec['aggregation']}])
    tail.extend([{'id': 'projection', 'component': 'SelectValues', 'columns': spec['output_columns']},
                 {'id': 'target', 'component': 'TableOutput', 'schema': spec['target_schema'],
                  'table': spec['target_table'], 'write_mode': spec['write_mode']}])
    previous = join['id']
    for stage in tail:
        edges.append({'from': previous, 'to': stage['id']}); previous = stage['id']
    plan = {'version': 2, 'specification_checksum': result['specification_checksum'],
            'naming_checksum': spec['naming']['checksum'], 'stages': stages + tail, 'edges': edges}
    return {**result, 'plan': plan, 'plan_checksum': digest(plan), 'compiler_status': 'PLAN_ONLY_HPL_NOT_GENERATED'}
