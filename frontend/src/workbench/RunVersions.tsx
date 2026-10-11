import {useEffect, useRef, useState} from 'react';
import {request, jsonBody} from './api';
import {SAEvidence} from './SAEvidence';
import {SAInvocation} from './SAInvocation';
import {DeveloperInvocation} from './DeveloperInvocation';
import {HopDispatch} from './HopDispatch';
import {NamingConfirmation} from './NamingConfirmation';
import {SpecificationHistory} from './SpecificationHistory';
import {SourceEvidence} from './SourceEvidence';
import {CsvReplacement} from './CsvReplacement';
import {HopOutcome} from './HopOutcome';
import {ExecutionReconciliation} from './ExecutionReconciliation';
import {ExecutionDiagnosis} from './ExecutionDiagnosis';
import {TransformationEditor, TransformationSummary, intentPayload} from './TransformationIntent';
import {SourceOrderEditor, SourceOrderSummary, ordinalRef, validateOrderDraft} from './SourceOrder';
import {ExcelInputEditor, ExcelInputSummary} from './ExcelInputContract';
import {JsonInputEditor, JsonInputSummary} from './JsonInputContract';
import {useDraftGuard} from './useDraftGuard';
import {OperationLatch} from './operationLatch';
import {useWorkflowReadOnly,useWorkflowRefresh,useWorkflowCanCancel,useWorkflowCanPrepare,useWorkflowStatus,useOperation,useManagedRefresh} from './useWorkflowRefresh';
import {JoinInputEditor} from './JoinInputEditor';

const sectionNames:Record<string,string>={requirement_text:'需求',target_schema:'目標 Schema',target_table:'目標資料表',requirements_v1:'寫入與資料期間',transformation_contract_v1:'轉換規則',source_fields_v1:'來源欄位',join_contract_v1:'Join 規則',source_order_v1:'來源序號',csv_input_contract_v1:'CSV 輸入契約',excel_input_contract_v1:'Excel 輸入契約',json_input_contract_v1:'JSON 輸入契約',csv_replacement_v1:'來源換檔'};
const leafNames:Record<string,string>={write_mode:'寫入方式',date_scope:'資料期間',date_column:'日期欄位',start_date:'起日',end_date_exclusive:'迄日（不含）',key_columns:'鍵欄位',filters:'篩選',aggregation:'分組與計算',output_columns:'輸出欄位',joins:'Join',encoding:'編碼',delimiter:'分隔符號',header:'標題列',extra_columns:'額外欄位'};
const show=(v:any)=>v===undefined||v===null||v===''?'（未提供）':typeof v==='object'?JSON.stringify(v):String(v);
// Field-level revision diff; precise JSON stays in a collapsed section.
export function revisionChanges(preview:any,original:any){
  const rows:{path:string;label:string;before:string;after:string}[]=[];
  for(const [key,value] of Object.entries(preview||{})){
    if(['request_key','input_checksum','qa_revision_checksum'].includes(key))continue;
    const before=original?.[key];
    if(JSON.stringify(value)===JSON.stringify(before))continue;
    const section=sectionNames[key]||key;
    if(value&&typeof value==='object'&&!Array.isArray(value)&&before&&typeof before==='object'&&!Array.isArray(before)){
      for(const leaf of Array.from(new Set([...Object.keys(value as any),...Object.keys(before)]))){
        if(['version','contract_status'].includes(leaf))continue;
        const a=(before as any)[leaf],b=(value as any)[leaf];
        if(JSON.stringify(a??null)!==JSON.stringify(b??null))rows.push({path:key+'.'+leaf,label:`${section}／${leafNames[leaf]||leaf}`,before:show(a),after:show(b)});
      }
    } else rows.push({path:key,label:section,before:show(before),after:show(value)});
  }
  return rows;
}

const states: Record<string, string> = {QUEUED: '待處理（未啟動）', RUNNING: '處理中', NEEDS_REVIEW: '需要人工檢查', SUCCEEDED: '流程已結束', FAILED: '失敗', CANCELLED: '已取消'};

export function RunVersions({taskId,requestedRunId,onSelectRun,notice,onNotice}: {taskId: string;requestedRunId?:string;onSelectRun?:(id:string)=>void;notice?:string;onNotice?:(message:string)=>void}) {
  const managed=useManagedRefresh();
  const readOnly=useWorkflowReadOnly();
  const canCancel=useWorkflowCanCancel();
  const canPrepare=useWorkflowCanPrepare();
  const workflow=useWorkflowStatus();
  const prepareOp=useOperation('prepare_run',{ignoreReadOnly:true}),confirmOp=useOperation('input_confirm'),cancelOp=useOperation('input_cancel',{ignoreReadOnly:true}),revisionOp=useOperation('requirement_revision');
  const [runs, setRuns] = useState<any[]>([]);
  const [detail, setDetail] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [mutating,setMutating]=useState(false);
  const [message, setMessage] = useState(notice||'');
  // Success notices are reported to the stage workspace so they survive the remount when it switches Runs.
  const report = (text: string) => {setMessage(text); onNotice?.(text)};
  const [confirmed, setConfirmed] = useState(false);
  const [editing, setEditing] = useState(false);
  const [conditions, setConditions] = useState<any>({});
  const [transformation, setTransformation] = useState<any>(null);
  const [sourceOrder, setSourceOrder] = useState<any>(null);
  const [sourceFields, setSourceFields] = useState<any[] | null>(null);
  const [csvContract, setCsvContract] = useState<any>(null);
  const [excelContract, setExcelContract] = useState<any>(null);
  const [jsonContract, setJsonContract] = useState<any>(null);
  const [joinContract,setJoinContract]=useState<any>(null);
  const [replacement, setReplacement] = useState<any>(null);
  const [replacementPending, setReplacementPending] = useState(false);
  const [draft, setDraft] = useState({requirement_text: '', target_schema: '', target_table: ''});
  const [preview,setPreview]=useState<any>(null),[diffConfirmed,setDiffConfirmed]=useState(false);
  const [uncertain,setUncertain]=useState(false);
  const [pendingRun,setPendingRun]=useState('');
  const latch=useRef(new OperationLatch());
  const savedDrafts=useRef(new Map<string,any>());
  useDraftGuard(editing,mutating,setMessage);
  useEffect(()=>{if(pendingRun&&!busy&&!editing){const id=pendingRun;setPendingRun('');onSelectRun?.(id)}},[pendingRun,busy,editing,onSelectRun]);
  const draftSignature=JSON.stringify({draft,conditions,transformation,sourceOrder,sourceFields,csvContract,excelContract,jsonContract,joinContract,replacement});
  useEffect(()=>{setPreview(null);setDiffConfirmed(false)},[draftSignature]);
  const revisionKey = useRef(crypto.randomUUID());
  useWorkflowRefresh(`/api/tasks/${encodeURIComponent(taskId)}/runs/${requestedRunId||''}`,async()=>{await load();if(detail)setDetail(await request(`/api/tasks/${taskId}/runs/${detail.run_id}`))},editing||busy);
  const requestKey = useRef(crypto.randomUUID());
  const load = async () => setRuns((await request(`/api/tasks/${taskId}/runs`)).runs);
  useEffect(() => {
    let active = true;
    setBusy(true);
    request(`/api/tasks/${taskId}/runs`).then(async value => {
      if (!active) return;
      setRuns(value.runs);
      if(requestedRunId&&!value.runs.some((r:any)=>r.run_id===requestedRunId))throw Error('指定版本不存在；未改用最新版本。');
      if (requestedRunId||value.runs[0]) await open(requestedRunId||value.runs[0].run_id);
    }).catch(error => {if (active) setMessage(error.message)})
      .finally(() => {if (active) setBusy(false)});
    return () => {active = false};
  }, [taskId,requestedRunId]);
  const action = async (operation: () => Promise<void>) => {
    if(!latch.current.acquire())return;
    setBusy(true);setMutating(true); setMessage(''); onNotice?.('');
    try {await operation()} catch (error: any) {setMessage(error.message)} finally {setBusy(false);setMutating(false);latch.current.release()}
  };
  const open = async (id: string) => {
    setDetail(null);
    setConfirmed(false);
    setEditing(false);
    const value = await request(`/api/tasks/${taskId}/runs/${id}`);
    if (value.run_id !== id) throw new Error('版本回應不一致，請重新載入；無法確認或核准此內容。');
    setDetail(value);
  };
  const revisionPayload = () => {
    if(replacementPending) throw new Error('請先確認或取消來源換檔');
    validateOrderDraft(sourceOrder, transformation);
    return {
      ...draft, requirements_v1: {version: 1, ...conditions}, ...(transformation ? {transformation_contract_v1: intentPayload(transformation)} : {}), ...(replacement ? {csv_replacement_v1:replacement} : sourceFields ? {source_fields_v1: {fields: sourceFields}} : {}), ...(csvContract ? {csv_input_contract_v1: {...csvContract, header: csvContract.header === 'true'}} : {}), request_key: revisionKey.current, input_checksum: detail.input_checksum,
      ...(detail.qa_revision ? {qa_revision_checksum: detail.qa_revision.checksum} : {}),
      ...(sourceOrder ? {source_order_v1: sourceOrder} : {}),
      ...(excelContract ? {excel_input_contract_v1: excelContract} : {}),
      ...(jsonContract ? {json_input_contract_v1: jsonContract} : {}),
      ...(joinContract ? {join_contract_v1: joinContract} : {}),
    };
  };
  const revise = () => action(async () => {
    if(!preview||!diffConfirmed||uncertain)throw Error('請先預覽差異並確認；結果不明時須先重新讀取伺服器狀態。');
    try {
      const child=await request(`/api/tasks/${taskId}/runs/${detail.run_id}/revisions`,jsonBody('POST',preview));
      setEditing(false);setPreview(null);setDiffConfirmed(false);savedDrafts.current.delete(detail.run_id);
      revisionKey.current=crypto.randomUUID();
      await load();await open(child.run_id);
      report('已建立新版，下一步是需求確認；舊版与核准紀錄保留，不自動執行。');
      if(onSelectRun)setPendingRun(child.run_id);else window.location.reload();
    } catch(e:any) {
      setUncertain(true);
      throw Error(`新版建立結果需要核對：${e.message}。輸入與 request key 保留，先重新讀取伺服器，不自動重送。`);
    }
  });
  const prepare = () => action(async () => {
    const run = await request(`/api/tasks/${taskId}/runs`, jsonBody('POST', {mode: 'PREPARE', request_key: requestKey.current}));
    requestKey.current = crypto.randomUUID();
    await load(); await open(run.run_id);
    setPendingRun(run.run_id);
    report('已保存本次輸入與設定快照；沒有啟動 ETL。');
  });
  const review = (decision: 'APPROVE' | 'REJECT') => action(async () => {
    await request(`/api/tasks/${taskId}/approvals`, jsonBody('POST', {run_id: detail.run_id, kind: 'INPUT_REVIEW', decision, input_checksum: detail.input_checksum, settings_checksum: detail.settings_checksum}));
    await load(); await open(detail.run_id);
    report(decision === 'APPROVE' ? '此版輸入已確認；尚未授權 Hop 執行或交付。' : '此版輸入已拒絕，準備版本已取消。');
  });
  const cancel = () => action(async () => {
    await request(`/api/tasks/${taskId}/runs/${detail.run_id}/cancel`, {method: 'POST'});
    await load(); await open(detail.run_id);
    report('已取消未執行的版本，歷史紀錄仍保留。');
  });
  const active = runs.some(run => ['QUEUED','RUNNING','NEEDS_REVIEW'].includes(run.state));
  return <section className="panel run-versions" aria-label="執行準備版本">
    <h3>執行準備版本</h3>
    <p>先保存需求與設定快照，再確認此版輸入。啟用控制 Worker 後，只進行初步需求檢查；不會啟動 Hop 或產生 Release。</p>
    <div className="run-actions">
      {!workflow?.delivered&&<button disabled={!canPrepare || !prepareOp.enabled&&prepareOp.known || busy || active} onClick={prepare}>建立準備版本</button>}
      {(!managed||!!message)&&<button disabled={busy} onClick={() => action(async () => {await load(); if (detail) await open(detail.run_id)})}>{managed?'重試讀取版本':'重新載入版本'}</button>}
    </div>
    {message && <p role="status">{message}</p>}
    {!runs.length && <p>尚無準備版本；有保存的舊資料時，可展開下方「舊版紀錄」查看。</p>}
    {!onSelectRun&&<div className="run-version-list">{runs.map(run => <button disabled={busy} key={run.run_id} onClick={() => action(() => open(run.run_id))} aria-pressed={detail?.run_id === run.run_id}>
      <b>{states[run.state] || run.state}</b><span>{new Date(run.created_at).toLocaleString()}</span><small>{run.run_id}</small>
    </button>)}</div>}
    {detail && <article aria-label="版本內容" className="run-version-detail">
      <h4>本次輸入與設定</h4>
      <HopOutcome code={detail.outcome_code} milestones={workflow?.run_id===detail.run_id?workflow.milestones:undefined}/>
      {['HOP_EXECUTION_FAILED','HOP_RESULT_UNKNOWN'].includes(detail.outcome_code)&&<ExecutionDiagnosis key={'diagnosis-'+detail.run_id} base={`/api/tasks/${encodeURIComponent(taskId)}/runs/${detail.run_id}`}/>}
      {['HOP_EXECUTION_FAILED','HOP_RESULT_UNKNOWN'].includes(detail.outcome_code)&&<ExecutionReconciliation key={'reconcile-'+detail.run_id} base={`/api/tasks/${encodeURIComponent(taskId)}/runs/${detail.run_id}`} onSaved={async()=>{await load();await open(detail.run_id)}}/>}
      {!onSelectRun&&<><SAEvidence key={detail.run_id} taskId={taskId} runId={detail.run_id}/>
      <SAInvocation key={'invocation-' + detail.run_id} taskId={taskId} runId={detail.run_id}/>
      <NamingConfirmation key={'naming-'+detail.run_id} taskId={taskId} editable={detail.matches_current&&!detail.write_started} sourceOrder={detail.input_summary.source_order_v1}/>
      <DeveloperInvocation key={'developer-' + detail.run_id} taskId={taskId} runId={detail.run_id}/>
      <SpecificationHistory key={'spec-' + detail.run_id} taskId={taskId} runId={detail.run_id}/>
      <HopDispatch key={'hop-'+detail.run_id} taskId={taskId} runId={detail.run_id} onReconciled={async()=>{await load();await open(detail.run_id)}}/></>}
      {detail.parent_run_id && <p>補正自版本：<button disabled={busy} onClick={() => onSelectRun?onSelectRun(detail.parent_run_id):action(() => open(detail.parent_run_id))}>{detail.parent_run_id}</button>。新版須重新確認，不沿用舊核准。</p>}
      {detail.outcome_code === 'SUPERSEDED_BY_REVISION' && <p>此版本已由補正版本取代；原始輸入、檢查及核准紀錄仍保留。</p>}
      {detail.gate_result && <section aria-label="初步需求檢查結果">
        <h4>初步需求檢查</h4>
        <p>{detail.gate_result.status === 'NEEDS_INPUT' ? '需求有缺漏或不安全內容，流程已暫停。' : detail.gate_result.status === 'CHECKED' ? '此版本已完成初步欄位檢查；後續 SA、規格、Hop 與 QA 各階段仍須分別查看及授權。' : '檢查發生錯誤，流程已暫停，請查閱控制紀錄。'}</p>
        <p>這不是 AI 語意審查、ETL 成功或交付核准。修改需求後必須建立並確認新版本。</p>
        {!!detail.gate_result.issues?.length && <ul>{detail.gate_result.issues.map((issue: any, index: number) => <li key={index}>{issue.message}（{issue.field_path}）</li>)}</ul>}
        <SourceEvidence items={detail.gate_result.source_evidence}/>
      </section>}
      <p>{detail.input_summary.requirement_text}</p>
      <TransformationSummary value={detail.input_summary.transformation_contract_v1} sourceLabels={detail.input_summary.source_labels}/>
      <SourceOrderSummary value={detail.input_summary.source_order_v1}/>
      <ExcelInputSummary value={detail.input_summary.excel_input_contract_v1}/>
      <JsonInputSummary value={detail.input_summary.json_input_contract_v1}/>
      <p>目標：{detail.input_summary.target_schema || '未指定'}.{detail.input_summary.target_table || '未指定'}</p>
      {detail.input_summary.sources?.length ? <section aria-label="本版來源與欄位"><h4>來源</h4>{detail.input_summary.sources.map((source:any,i:number)=><article key={i}><h5>{source.label} · {source.type}</h5><p>{source.fields.map((field:any)=>`${field.name} (${field.type||'未指定型別'})`).join('、')||'尚未提供欄位'}</p></article>)}</section> : !!detail.input_summary.source_fields?.length && <p>來源欄位：{detail.input_summary.source_fields.map((field: any) => `${field.name} (${field.type || '未指定型別'})`).join('、')}</p>}
      {detail.input_summary.csv_input_contract_v1 && <section aria-label="CSV 輸入契約摘要"><h4>CSV 輸入契約</h4>{detail.input_summary.csv_input_contract_v1.contract_status === 'CONFIRMED_INPUT_ONLY' ? <p>編碼：{detail.input_summary.csv_input_contract_v1.encoding}；分隔：{JSON.stringify(detail.input_summary.csv_input_contract_v1.delimiter)}；標題列：{detail.input_summary.csv_input_contract_v1.header ? '有' : '無'}；額外欄位：{detail.input_summary.csv_input_contract_v1.extra_columns === 'REJECT' ? '拒收' : '忽略'}。</p> : <p>尚未確認或格式不合法，請補正後建立新版。</p>}<p>綁定來源 source.0；只確認解析需求，不代表檔案已驗證或已執行匯入。</p></section>}
      <p>寫入模式：{detail.input_summary.requirements_v1?.write_mode || '尚未確認'}；資料期間：{detail.input_summary.requirements_v1?.date_scope || '尚未確認'}</p>
      {detail.input_summary.requirements_v1?.date_scope === 'RANGE' && <p>日期欄位：{detail.input_summary.requirements_v1.date_column}；{detail.input_summary.requirements_v1.start_date}（包含）至 {detail.input_summary.requirements_v1.end_date_exclusive}（不包含）</p>}
      {!!detail.input_summary.requirements_v1?.key_columns?.length && <p>鍵欄位：{detail.input_summary.requirements_v1.key_columns.join('、')}</p>}
      {detail.events?.some((event: any) => event.event_type === 'QA_REVISION_LINKED') && <p>此版本的 QA 審查已由補正版本接續；原 Hop 結果、QA 意見與證據保留，未重跑原寫入。</p>}
      {((detail.state === 'NEEDS_REVIEW' && detail.phase === 'REQUIREMENT_GATE' && detail.gate_result && !detail.write_started) || detail.failed_revision_available || detail.qa_revision) && detail.matches_current && <>
        {detail.qa_revision && <p>QA 尚未通過。保存補正會結束此版本的待審流程，保留原始執行與 QA 意見；必須指定 ai_sample 中不同的新目標，新版重新確認需求與核准，不會自動重跑 Hop。</p>}
        {detail.failed_revision_available && <p>此失敗版本已核對結案。修正後必須指定 ai_sample 中不同的新目標，重新通過需求與執行核准；不沿用舊核准、不重跑舊寫入，舊失敗與證據完整保留。</p>}
        {!editing && <button data-revision-start disabled={readOnly||!revisionOp.enabled||busy} onClick={() => {
          setDraft({requirement_text: detail.input_summary.requirement_text || '', target_schema: detail.input_summary.target_schema || '', target_table: detail.input_summary.target_table || ''});
          setConditions(detail.input_summary.requirements_v1 || {version: 1, write_mode: null, date_scope: null, date_column: '', start_date: '', end_date_exclusive: '', key_columns: []});
          setSourceFields(null);
          setTransformation(detail.input_summary.transformation_contract_v1 || null);
          setSourceOrder(detail.input_summary.source_order_v1 || null);
          setReplacement(null); setReplacementPending(false);
          setCsvContract(null);
          setExcelContract(null);
          setJsonContract(null);
          const originalJoin=detail.input_summary.join_contract_v1;
          setJoinContract(originalJoin?.joins ? {version:1,joins:originalJoin.joins} : null);
          const saved=savedDrafts.current.get(detail.run_id);
          if(saved){setDraft(saved.draft);setConditions(saved.conditions);setTransformation(saved.transformation);setSourceOrder(saved.sourceOrder);setSourceFields(saved.sourceFields);setCsvContract(saved.csvContract);setExcelContract(saved.excelContract);setJsonContract(saved.jsonContract);setJoinContract(saved.joinContract||null);setReplacement(saved.replacement);revisionKey.current=saved.requestKey}
          else revisionKey.current = crypto.randomUUID();
          setUncertain(false);setEditing(true);
        }}>{detail.failed_revision_available?'編輯修正版（沿用原需求）':'補正需求並建立新版'}</button>}
        {editing && <form aria-label="需求補正" onSubmit={event => {event.preventDefault();if(!preview){try{setPreview(revisionPayload());setDiffConfirmed(false)}catch(e:any){setMessage(e.message)}}else void revise()}}>
          <JoinInputEditor sources={detail.input_summary.sources||[]} value={joinContract} onChange={setJoinContract} disabled={busy}/>
          <div data-field="source" tabIndex={-1}><ExcelInputEditor selection={detail.input_summary.excel_selection} evidence={detail.input_summary.excel_input_contract_v1}
            value={excelContract} disabled={busy} onChange={setExcelContract}/>
          <JsonInputEditor profile={detail.input_summary.json_profile} value={jsonContract} disabled={busy} onChange={setJsonContract}/></div>
          <SourceOrderEditor value={sourceOrder} eligible={!!detail.input_summary.csv_contract_editable} disabled={busy} onChange={value => {
            setSourceOrder(value);
            const current = transformation && !transformation.invalid ? transformation : {version: 1, filters: [], filter_logic: 'ALL', filter_null_policy: 'EXCLUDE_UNKNOWN', aggregation: null, output_columns: []};
            setTransformation({...current, output_columns: current.output_columns.includes(ordinalRef) ? current.output_columns : [...current.output_columns, ordinalRef]});
          }}/>
          <div data-field="transformation"><TransformationEditor value={transformation} sourceLabels={detail.input_summary.source_labels} sources={(detail.input_summary.transformation_source_refs || []).filter((ref: string) => !ref.startsWith('$source_order.'))} generatedOutputs={sourceOrder ? [ordinalRef] : []} disabled={busy} onChange={setTransformation}/></div>
          {detail.input_summary.csv_contract_editable && <CsvReplacement disabled={busy} onChange={setReplacement} onPending={setReplacementPending}/>}
          <p>保存會保留舊版本，並建立待確認的新版本，不執行 ETL。僅單一且沒有實體／樣本資料的來源可補正欄位。</p>
          {detail.input_summary.csv_contract_editable && <fieldset data-field="source"><legend>CSV 輸入契約補正</legend>
            <p>指定編碼、分隔與欄位政策；不修改原始檔案，不傳送實際路徑給模型。額外欄位「忽略」表示只使用已定義欄位，「拒收」表示出現未定義欄位即失敗。</p>
            {!csvContract ? <button type="button" onClick={() => {
              const old = detail.input_summary.csv_input_contract_v1;
              setCsvContract(old?.contract_status === 'CONFIRMED_INPUT_ONLY' ? {version: 1, encoding: old.encoding, delimiter: old.delimiter, header: String(old.header), extra_columns: old.extra_columns} : {version: 1, encoding: '', delimiter: '', header: '', extra_columns: ''});
            }}>設定 CSV 輸入契約</button> : <>
              <label>CSV 編碼<select required value={csvContract.encoding} onChange={e => setCsvContract({...csvContract, encoding: e.target.value})}><option value="">請選擇</option>{['UTF-8','UTF-8-SIG','BIG5'].map(value => <option key={value}>{value}</option>)}</select></label>
              <label>CSV 分隔符號<select required value={csvContract.delimiter} onChange={e => setCsvContract({...csvContract, delimiter: e.target.value})}><option value="">請選擇</option><option value=",">逗號</option><option value=";">分號</option><option value={'\t'}>Tab</option><option value="|">直線</option></select></label>
              <label>CSV 標題列<select required value={csvContract.header} onChange={e => setCsvContract({...csvContract, header: e.target.value})}><option value="">請選擇</option><option value="true">有標題列</option><option value="false">無標題列（依欄位順序）</option></select></label>
              <label>CSV 額外欄位<select required value={csvContract.extra_columns} onChange={e => setCsvContract({...csvContract, extra_columns: e.target.value})}><option value="">請選擇</option><option value="REJECT">拒收整批資料</option><option value="IGNORE">忽略未定義欄位</option></select></label>
              <button type="button" onClick={() => setCsvContract(null)}>不變更 CSV 契約</button>
            </>}
          </fieldset>}
          {detail.input_summary.source_fields_editable ? <fieldset data-field="source"><legend>合成來源欄位</legend>
            {!sourceFields && <button type="button" onClick={() => setSourceFields(detail.input_summary.source_fields.map((field: any) => ({name: field.name || '', type: field.type || ''})))}>編輯來源欄位</button>}
            {sourceFields && <>
              {sourceFields.map((field, index) => <div key={index} className="run-actions">
                <label>欄位 {index + 1} 名稱<input required maxLength={120} value={field.name} onChange={event => setSourceFields(sourceFields.map((item, i) => i === index ? {...item, name: event.target.value} : item))}/></label>
                <label>欄位 {index + 1} 型別<select required value={field.type} onChange={event => setSourceFields(sourceFields.map((item, i) => i === index ? {...item, type: event.target.value} : item))}><option value="">請選擇</option>{['BIGINT','INTEGER','NUMERIC','FLOAT','VARCHAR','BOOLEAN','DATE','TIMESTAMP'].map(type => <option key={type}>{type}</option>)}</select></label>
                <button type="button" disabled={busy} onClick={() => setSourceFields(sourceFields.filter((_, i) => i !== index))}>移除欄位 {index + 1}</button>
              </div>)}
              <button type="button" disabled={busy || sourceFields.length >= 200} onClick={() => setSourceFields([...sourceFields, {name: '', type: ''}])}>新增來源欄位</button>
              <button type="button" disabled={busy} onClick={() => setSourceFields(null)}>保留原來源欄位</button>
              {!sourceFields.length && <p role="alert">至少保留一個來源欄位。</p>}
            </>}
          </fieldset> : <p>此來源不符合欄位編輯條件，原始來源與檔案保持不變。</p>}
          <label>補正後需求<textarea data-field="requirement_text" required maxLength={20000} rows={5} value={draft.requirement_text} onChange={event => setDraft({...draft, requirement_text: event.target.value})}/></label>
          <h4>目標與預期結果</h4>
          <label>目標 Schema<input data-field="target_schema" required pattern="[a-z_][a-z0-9_]{0,62}" value={draft.target_schema} onChange={event => setDraft({...draft, target_schema: event.target.value})}/></label>
          <label>目標 Table<input data-field="target_table" required pattern="[a-z_][a-z0-9_]{0,62}" value={draft.target_table} onChange={event => setDraft({...draft, target_table: event.target.value})}/></label>
          <p>目標名稱限英文小寫、數字與底線，不能以數字開頭；這裡只保存規格，不建立或刪除資料表。</p>
          <label>寫入模式<select data-field="write_mode" value={conditions.write_mode || ''} onChange={event => setConditions({...conditions, write_mode: event.target.value || null})}>
            <option value="">尚未確認</option><option value="APPEND">新增資料（APPEND）</option><option value="REPLACE" disabled={conditions.write_mode!=='REPLACE'}>覆寫目標（REPLACE，目前不支援執行）</option><option value="UPSERT" disabled={conditions.write_mode!=='UPSERT'}>依鍵值合併（UPSERT，目前不支援執行）</option>
          </select></label>
          <label>資料期間<select data-field="date_scope" value={conditions.date_scope || ''} onChange={event => setConditions({...conditions, date_scope: event.target.value || null, date_column: '', start_date: '', end_date_exclusive: ''})}>
            <option value="">尚未確認</option><option value="ALL">全部資料</option><option value="RANGE">指定日期範圍</option>
          </select></label>
          {conditions.date_scope === 'RANGE' && <>
            <label>日期欄位<input maxLength={120} value={conditions.date_column || ''} onChange={event => setConditions({...conditions, date_column: event.target.value})}/></label>
            <label>起日（包含）<input type="date" value={conditions.start_date || ''} onChange={event => setConditions({...conditions, start_date: event.target.value})}/></label>
            <label>迄日（不包含）<input type="date" value={conditions.end_date_exclusive || ''} onChange={event => setConditions({...conditions, end_date_exclusive: event.target.value})}/></label>
          </>}
          <label>鍵欄位（逗號分隔）<input data-field="key_columns" maxLength={2048} value={(conditions.key_columns || []).join(',')} onChange={event => setConditions({...conditions, key_columns: event.target.value.split(',')})}/></label>
          <p>目前編譯器只執行 APPEND；REPLACE／UPSERT 只保留既有版本的歷史意圖，不能選為新版的執行方式。UPSERT 必須提供來源中存在的鍵欄位；日期採起日包含、迄日不包含。不確定可保持「尚未確認」，重新檢查仍會暫停。覆寫意圖不等於核准刪表。</p>
          {preview&&<section aria-label="修訂差異預覽"><h4>建立新版前確認差異</h4><p>下游 SA、命名／設計、規格、執行與 QA 核准依後端規則重新核對；原版結果保留。</p><table><thead><tr><th>欄位</th><th>原值</th><th>新值</th></tr></thead><tbody>{revisionChanges(preview,detail.input_summary).map(row=><tr key={row.path}><td>{row.label}</td><td>{row.before}</td><td>{row.after}</td></tr>)}</tbody></table><details><summary>原始 JSON 差異</summary>{Object.entries(preview).filter(([key,value])=>!['request_key','input_checksum','qa_revision_checksum'].includes(key)&&JSON.stringify(value)!==JSON.stringify(detail.input_summary[key])).map(([key,value])=><div key={key}><b>{key}</b><pre>{JSON.stringify(detail.input_summary[key]??'原版未提供',null,2)}</pre><pre>{JSON.stringify(value,null,2)}</pre></div>)}</details><label><input type="checkbox" checked={diffConfirmed} onChange={e=>setDiffConfirmed(e.target.checked)}/>已核對差異，同意建立待需求確認的新版</label></section>}
          {uncertain&&<section role="alert"><p>送出結果待核對，不能再次提交。</p><button type="button" disabled={busy} onClick={()=>action(async()=>{const list=await request(`/api/tasks/${taskId}/runs`);setRuns(list.runs);const child=list.runs.find((r:any)=>r.parent_run_id===detail.run_id);if(child){setEditing(false);await open(child.run_id);setPendingRun(child.run_id)}else{setUncertain(false);setMessage('已重新核對：尚未找到子版本，保留同一 request key；仍需人工確認差異才可再次送出。')}})}>重新讀取新版建立結果</button></section>}
          <div className="run-actions"><button type="submit" disabled={busy || replacementPending || uncertain || !draft.requirement_text.trim() || !!preview&&!diffConfirmed}>{preview?'保存補正並建立新版':'預覽修訂差異'}</button><button type="button" disabled={busy||replacementPending||uncertain} onClick={()=>{savedDrafts.current.set(detail.run_id,{draft,conditions,transformation,sourceOrder,sourceFields,csvContract,excelContract,jsonContract,joinContract,replacement,requestKey:revisionKey.current});setEditing(false);setMessage('草稿已暫存於本頁；尚未建立新版或核准，重新整理會清除本頁草稿。')}}>儲存草稿</button><button type="button" disabled={busy || replacementPending||uncertain} onClick={() => setEditing(false)}>放棄補正</button></div>
        </form>}
      </>}
      <dl><dt>AI Profile</dt><dd>{detail.settings_summary.ai_profile_id}</dd><dt>資料連線</dt><dd>{detail.settings_summary.connection_id}</dd></dl>
      <details><summary>版本指紋</summary><dl><dt>輸入 checksum</dt><dd>{detail.input_checksum}</dd><dt>設定 checksum</dt><dd>{detail.settings_checksum}</dd></dl></details>
      <p>{detail.matches_current ? '與目前 Task／設定一致。' : '內容已變更，舊版確認不可沿用；請取消未執行版本後建立新版本。'}</p>
      {detail.approval && <p>已記錄輸入決定：{detail.approval.decision === 'APPROVE' ? '確認' : '拒絕'}（不等於執行／交付核准）</p>}
      {detail.state === 'QUEUED' && !detail.approval && detail.matches_current && !readOnly && confirmOp.enabled && <>
        <label><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)}/>我已核對本次需求及設定版本</label>
        <div className="run-actions"><button disabled={busy || !confirmed} onClick={() => review('APPROVE')}>確認此版輸入</button><button disabled={busy} onClick={() => review('REJECT')}>拒絕此版輸入</button></div>
      </>}
      {['QUEUED','NEEDS_REVIEW'].includes(detail.state) && !detail.write_started && <button disabled={!canCancel||!cancelOp.enabled&&cancelOp.known||busy} onClick={cancel}>取消未執行版本</button>}
      {!!detail.events?.length && <details><summary>控制流程紀錄（{detail.events.length} 筆）</summary><ol>{detail.events.map((event: any) => <li key={event.event_id}>{new Date(event.created_at).toLocaleString()} · {event.event_type} · {event.phase}</li>)}</ol></details>}
    </article>}
  </section>;
}
