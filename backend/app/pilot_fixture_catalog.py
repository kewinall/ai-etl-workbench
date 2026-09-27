"""Versioned synthetic corpus. Reference answers are literal, not ETL results.

Never executes a fault, SQL, model, or engine. The prospective runner must bind
these bytes to a task before using this corpus as measured acceptance evidence.
"""
from copy import deepcopy
from hashlib import sha256
import json
from io import BytesIO
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
from .pilot_cohort import PilotCohortPlan

VERSION = 'standard-v1'
CSV = {'version': 1, 'encoding': 'UTF-8', 'delimiter': ',', 'header': True, 'extra_columns': 'REJECT'}
SALES = 'record_id,category,amount,event_date\n1,A,10,2026-01-01\n2,A,20,2026-01-31\n3,B,5,2025-12-31\n4,B,30,2026-02-01\n5,B,15,2026-01-15\n6,A,10,2026-01-01\n'
SALES_FIELDS = [['record_id','BIGINT'], ['category','VARCHAR(32)'], ['amount','BIGINT'], ['event_date','DATE']]


def source(name, content, fields):
    return {'filename': name, 'content': content, 'fields': fields, 'csv_contract': deepcopy(CSV)}


BASES = [
    {'key': 'filter-aggregate', 'title': '門檻篩選後依類別加總',
     'sources': [source('sales.csv', SALES, SALES_FIELDS)],
     'requirement': '保留 amount >= 10；依 category 分組，SUM(amount) 為 total_amount、COUNT_ROWS 為 row_count；输出依序 category,total_amount,row_count。',
     'columns': [['category','VARCHAR(32)'],['total_amount','BIGINT'],['row_count','BIGINT']],
     'rows': [['A',40,3],['B',45,2]],
     'gap': {'field': 'requirements_v1.write_mode', 'initial': None, 'corrected': 'APPEND'},
     'mutation': {'node': 'filter', 'change': 'amount GE 10 -> amount GT 10'}},
    {'key': 'date-boundaries', 'title': '日期起迄邊界',
     'sources': [source('sales.csv', SALES, SALES_FIELDS)],
     'requirement': '只取 event_date >= 2026-01-01 且 event_date < 2026-02-01；输出 record_id。起日包含、迄日不包含。',
     'columns': [['record_id','BIGINT']], 'rows': [[1],[2],[5],[6]],
     'gap': {'field': 'requirements_v1.end_date_exclusive', 'initial': '', 'corrected': '2026-02-01'},
     'mutation': {'node': 'filter', 'change': 'event_date LT 2026-02-01 -> event_date LE 2026-02-01'}},
    {'key': 'left-join', 'title': '左連接與一對多展開',
     'sources': [source('customers.csv','customer_id,name\n1,Alpha\n2,Beta\n3,Gamma\n', [['customer_id','BIGINT'],['name','VARCHAR(32)']]),
                 source('orders.csv','customer_id,order_code\n1,X\n1,Y\n2,Z\n', [['customer_id','BIGINT'],['order_code','VARCHAR(32)']])],
     'requirement': 'source.0 LEFT JOIN source.1，以左右 customer_id 等值連接；NULL 鍵 NEVER_MATCH、重複鍵 EXPAND、CASE_SENSITIVE_NO_TRIM；输出左側 customer_id 與右側 order_code。保留未配對左列。',
     'columns': [['customer_id','BIGINT'],['order_code','VARCHAR(32)']], 'rows': [[1,'X'],[1,'Y'],[2,'Z'],[3,None]],
     'gap': {'field': 'join.keys', 'initial': [], 'corrected': [['source.0.customer_id','source.1.customer_id']]},
     'mutation': {'node': 'join', 'change': 'LEFT -> INNER'}},
    {'key': 'empty-result', 'title': '零列結果不誤判缺證據',
     'sources': [source('sales.csv', SALES, SALES_FIELDS)],
     'requirement': '保留 amount > 100；输出 record_id。標準答案為零列，仍須完整節點及結果來源證據。',
     'columns': [['record_id','BIGINT']], 'rows': [],
     'gap': {'field': 'requirements_v1.date_scope', 'initial': None, 'corrected': 'ALL'},
     'mutation': {'node': 'filter', 'change': 'amount GT 100 -> amount GT 20'}},
    {'key': 'null-group', 'title': 'NULL 分組與列數',
     'sources': [source('nullable.csv','record_id,category\n1,\n2,A\n3,\n', [['record_id','BIGINT'],['category','VARCHAR(32)']])],
     'requirement': '依 category 分組，空字串按 CSV 契約轉 NULL；COUNT_ROWS 為 row_count，不可用 COUNT_NON_NULL(category)。输出 category,row_count。',
     'columns': [['category','VARCHAR(32)'],['row_count','BIGINT']], 'rows': [[None,2],['A',1]],
     'gap': {'field': 'csv_input_contract_v1.encoding', 'initial': None, 'corrected': 'UTF-8'},
     'mutation': {'node': 'aggregation', 'change': 'COUNT_ROWS -> COUNT_NON_NULL(category)'}},
]


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def corpus():
    result = []
    for scenario, prefix in [('SUCCESS','success'),('REQUIREMENT_GAP','gap'),
                             ('SEMANTIC_DEFECT','semantic'),('EXECUTION_RECOVERY','recovery')]:
        for base in BASES:
            if scenario == 'EXECUTION_RECOVERY' and base['key'] == 'empty-result':
                base = {**base, 'key': 'full-projection', 'title': '非空投影目標缺欄位',
                        'requirement': '不篩選、不彙總；依序輸出全部來源的 record_id。',
                        'rows': [[1],[2],[3],[4],[5],[6]]}
            key = f'{prefix}-{base["key"]}'
            fixture = {'catalog_version': VERSION, 'case_key': key, 'scenario': scenario,
                       'sources': deepcopy(base['sources']),
                       'confirmed_requirement': base['requirement'] + ' 使用 APPEND；無主鍵、無 UPSERT；不 trim、額外欄位 REJECT；日期以 YYYY-MM-DD。除指定日期案例外使用全部期間。所有輸出欄位可為 NULL。',
                       'initial_change': None, 'fault_scope': 'SYNTHETIC_MANAGED_TARGET_ONLY'}
            acceptance = '真實 Hop 成功、精確多重集合比對一致、QA 證據與人工交付核准及可攜 Release 全部通過。'
            if scenario == 'REQUIREMENT_GAP':
                fixture['initial_change'] = deepcopy(base['gap'])
                acceptance = '初始缺口必須在執行前 NEEDS_INPUT；補正建立新 revision，保留缺口歷史；' + acceptance
            elif scenario == 'SEMANTIC_DEFECT':
                fixture['initial_change'] = deepcopy(base['mutation'])
                acceptance = '植入所列單一設計差異，必須於 Hop 寫入前攔截並引用規格與節點；修正須新 revision；' + acceptance
            elif scenario == 'EXECUTION_RECOVERY':
                fixture['initial_change'] = {'change': 'omit_target_column', 'column': base['columns'][0][0],
                    'restriction': '只在本案例新建、平台登錄、同專案 ai_sample 目標製造缺欄位；不得改動已交付資料表。'}
                acceptance = '專用測試目標缺欄位須保存失敗證據；若更早攔截則記錄不同結果，不冒充 Hop 失敗。人工核准修正到新目標與 revision，失敗歷史不可移除；' + acceptance
            oracle = {'version': 1, 'comparison': 'EXACT_MULTISET',
                      'columns': deepcopy(base['columns']), 'rows': deepcopy(base['rows']),
                      'meaning': 'AFTER_CONFIRMED_CORRECTION_NOT_INITIAL_FAULT',
                      'notes': '忽略列序，保留重複、型別與 NULL；零列不是缺少答案。'}
            definition = {'case_key': key, 'title': base['title'] + '／' + prefix,
                          'scenario': scenario, 'acceptance': acceptance,
                          'fixture_reference': f'{VERSION}/{key}/fixture.json',
                          'oracle_reference': f'{VERSION}/{key}/oracle.json',
                          'fixture_checksum': sha256(canonical_bytes(fixture)).hexdigest(),
                          'oracle_checksum': sha256(canonical_bytes(oracle)).hexdigest()}
            result.append({'definition': definition, 'fixture': fixture, 'oracle': oracle})
    return result


def template():
    return PilotCohortPlan(name='Pilot 20 案 standard-v1', cases=[case['definition'] for case in corpus()])


def bundle():
    """Reproducible test data ZIP, explicitly not a deployable Release."""
    files = {'plan.json': canonical_bytes(template().model_dump()),
             'README.txt': 'Synthetic Pilot test data only. Not a Release or proof of acceptance.\n'.encode()}
    for case in corpus():
        prefix = f'{VERSION}/{case["definition"]["case_key"]}/'
        files[prefix+'fixture.json'] = canonical_bytes(case['fixture'])
        files[prefix+'oracle.json'] = canonical_bytes(case['oracle'])
        for item in case['fixture']['sources']:
            files[prefix+item['filename']] = item['content'].encode('utf-8')
    output = BytesIO()
    with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            entry = ZipInfo(name, date_time=(1980,1,1,0,0,0))
            entry.compress_type = ZIP_DEFLATED
            archive.writestr(entry, content)
    return output.getvalue()
