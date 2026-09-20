"""QA context from persisted execution evidence; no model or Vertica calls."""
from xml.etree import ElementTree as ET
from contextlib import nullcontext
from .qa_contract import build_qa_context
from .execution_oracle import load_execution_oracle
from .specification_store import context as specification_context
from .hpl_compiler import compile_hpl
from .hop_generation_rules import validate_pipeline_graph
from .private_log_store import read_private_log
from .hop_log_evidence import hop_log_evidence
from .comparison_store import checked_public_evidence
from .qa_execution_details import execution_details


def load_qa_context(queue,task_id,run_id,comparison_id,*,connection=None):
    with (nullcontext(connection) if connection is not None else queue.conn()) as conn:
        pinned=load_execution_oracle(queue,task_id,run_id,connection=conn)
        run,naming=specification_context(queue,conn,task_id,run_id)
        row=conn.execute('''SELECT s.* FROM platform.specification s
            JOIN platform.task_run_execution_authorization a USING(specification_id)
            WHERE s.task_id=%s AND s.run_id=%s AND a.run_id=%s FOR SHARE OF s,a''',
            (task_id,run_id,run_id)).fetchone()
        comparison=conn.execute('SELECT * FROM platform.task_run_result_comparison WHERE run_id=%s AND comparison_id=%s FOR SHARE',
            (run_id,comparison_id)).fetchone()
        if not row or not comparison:raise ValueError('QA_EVIDENCE_NOT_FOUND')
        evidence=checked_public_evidence(comparison['evidence'],comparison['checksum'],run_id)
        if (evidence['specification_checksum']!=row['content_checksum']
                or evidence['execution_binding_checksum']!=pinned['binding_checksum']
                or evidence['hop_log_checksum']!=pinned['hop_log_checksum']):
            raise ValueError('QA_EVIDENCE_BINDING_CHANGED')
        compiled=compile_hpl(row['spec_json'],{**run,'write_started':False},naming)
        if compiled['status']!='VALIDATED_NOT_APPROVED' or compiled['specification_checksum']!=row['content_checksum']:
            raise ValueError('QA_SPECIFICATION_STALE_OR_INVALID')
        auth=conn.execute('SELECT binding FROM platform.task_run_execution_authorization WHERE run_id=%s',(run_id,)).fetchone()['binding']
        if compiled['hpl_checksum']!=auth['hpl_checksum']:raise ValueError('QA_HPL_BINDING_CHANGED')
        provenance=conn.execute('SELECT * FROM platform.result_comparison_provenance WHERE comparison_id=%s AND run_id=%s',
            (comparison_id,run_id)).fetchone()
    root=ET.fromstring(compiled['hpl'])
    names=[node.findtext('name') for node in root.findall('transform')]
    errors=validate_pipeline_graph(root)
    if root.tag!='pipeline' or len(names)!=len(set(names)):errors.append('INVALID_PIPELINE_STRUCTURE')
    log=read_private_log(queue,task_id,run_id)
    execution=hop_log_evidence({'started':True,'reason':'EXITED','exit_code':0,'output':log},names)
    if execution['result']['log_checksum']!=pinned['hop_log_checksum']:raise ValueError('QA_LOG_BINDING_CHANGED')
    source_valid=bool(provenance and provenance['comparison_checksum']==comparison['checksum']
        and provenance['query_checksum']==pinned['result_query_checksum']
        and provenance['settings_checksum']==run['settings_snapshot']['checksum']
        and provenance['hop_event_id']==pinned['hop_event_id'])
    checks=[
        dict(id='specification',status='PASS',checksum=row['content_checksum'],
            summary='已核對目前需求、Naming Contract、設定版本與受支援規格；不代表模型語意審查完成。'),
        dict(id='static_validation',status='FAIL' if errors else 'PASS',checksum=compiled['hpl_checksum'],
            summary=f'重建 HPL 與執行核准指紋一致；XML、節點唯一性、元件目錄及 GroupBy 排序檢查：{len(errors)} 項錯誤。'+('；'.join(errors[:5])[:1200] if errors else '')),
        dict(id='hop_execution',status='PASS' if execution['result']['status']=='COMPLETED' else 'FAIL',checksum=pinned['hop_log_checksum'],
            summary=f'已保存的成功退出證據與解密日誌一致；預期 {len(names)} 個節點，完整節點紀錄：{execution["complete_node_evidence"]}。'),
        dict(id='result_comparison',status='PASS' if evidence['status']=='MATCH' else 'FAIL',checksum=comparison['checksum'],
            summary=f'EXACT_MULTISET：預期 {evidence["expected_count"]}、實際 {evidence["actual_count"]}、缺少 {evidence["missing_count"]}、多出 {evidence["unexpected_count"]}。'),
        dict(id='result_source',status='PASS' if source_valid else 'MISSING',checksum=pinned['result_query_checksum'],
            summary='已保存平台管理目標、空表及固定連線查詢來源證據；不保證外部 DBA 未改資料。' if source_valid else '沒有符合此比對版本的受控來源證據。')]
    semantics={'requirement':run['input_snapshot']['requirement_text'],
        'conditions':run['input_snapshot']['target_config']['requirements_v1'],
        'specification':row['spec_json'],
        'execution_details':execution_details(run,compiled,auth),
        'nodes':[{'id':node.findtext('name'),'component':node.findtext('type')} for node in root.findall('transform')]}
    return {'context':build_qa_context(run_id,row['content_checksum'],checks,semantics),'run':run,
        'comparison_id':str(comparison_id),'comparison_checksum':comparison['checksum'],
        'context_origin':'PERSISTED_EXECUTION_EVIDENCE','qa_approved':False,'release_ready':False}
