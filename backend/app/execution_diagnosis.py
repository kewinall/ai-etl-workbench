"""Read-only deterministic failure hints. Never publishes raw private log text."""
from hashlib import sha256
import re
from .run_queue import RunConflict
from .private_log_store import read_private_log
from .sa_contract import digest


def diagnose(content,expected_checksum,run_id):
    if not isinstance(content,bytes) or sha256(content).hexdigest()!=expected_checksum:
        raise ValueError('DIAGNOSIS_LOG_BINDING_CHANGED')
    findings=[]
    # Constant signatures only; names, SQL, credentials and arbitrary exception text stay private.
    rules=[('COLUMN_NOT_FOUND',re.compile(r'\bcolumn\b.{0,250}\b(?:does not exist|not found)\b',re.I),
            '日誌指出欄位不存在；請核對已核准輸出欄位與本次實際目標結構。'),
           ('VALUE_TOO_LONG',re.compile(r'\b(?:value too long|exceeds? (?:the )?(?:maximum|length)|string data.{0,40}truncation)\b',re.I),
            '日誌指出欄位長度限制；請核對來源值長度與規格型別，不應截斷或忽略錯誤列。'),
           ('SOURCE_FILE_MISSING',re.compile(r'(?:file.{0,180}(?:does not exist|not found)|no filename is specified)',re.I),
            '日誌指出來源檔案缺失；請核對此版本來源與暫存證據。')]
    lines=content.decode('utf-8',errors='replace').splitlines()
    for code,pattern,message in rules:
        refs=[i for i,line in enumerate(lines,1) if pattern.search(line)]
        if refs:findings.append(dict(code=code,message=message,line_numbers=refs[:20]))
    result=dict(version=1,run_id=str(run_id),role='DETERMINISTIC_DIAGNOSTIC',log_checksum=expected_checksum,
        status='EVIDENCE_REVIEW_REQUIRED',findings=findings,
        limitation='這是日誌訊號，不是已證明的根因或資料庫回滾證明；需核對實際資料庫與規格。',
        next_steps=['確認 Hop 程序已停止並保存目標結構及筆數證據。',
                    '完成人工核對結案後，使用新目標建立修正 revision，再重新核准。'],
        automatic_retry_allowed=False,database_mutation_allowed=False,release_ready=False)
    return {**result,'checksum':digest(result)}


def read(queue,task_id,run_id):
    run=queue.detail(task_id,run_id)
    if (run['phase']!='HOP_EXECUTION' or run['state'] not in ('NEEDS_REVIEW','FAILED')
            or run['outcome_code'] not in ('HOP_EXECUTION_FAILED','HOP_RESULT_UNKNOWN') or run['lease_token'] is not None):
        raise RunConflict('DIAGNOSIS_NOT_ELIGIBLE')
    events=[e for e in run['events'] if e['event_type']==run['outcome_code']]
    checksum=(events[-1]['event_context'].get('log_checksum') if events else None)
    if not checksum:return {'status':'LOG_EVIDENCE_UNAVAILABLE','automatic_retry_allowed':False,'release_ready':False}
    return diagnose(read_private_log(queue,task_id,run_id),checksum,run_id)
