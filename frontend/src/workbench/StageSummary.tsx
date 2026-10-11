import {useEffect,useState,type ReactNode} from 'react';
import {request,sourcePath} from './api';
import {useWorkflowRefresh} from './useWorkflowRefresh';

// Read-only stage summaries. Every value comes from an existing GET; nothing here writes or infers success.
const ops:Record<string,string>={EQ:'=',NE:'≠',GT:'>',GE:'≥',LT:'<',LE:'≤',IS_NULL:'為空值',IS_NOT_NULL:'非空值'};
const fns:Record<string,string>={SUM:'加總',COUNT_ROWS:'筆數',COUNT_NON_NULL:'非空值筆數',MIN:'最小值',MAX:'最大值'};
const writeModes:Record<string,string>={APPEND:'新增資料（APPEND）',REPLACE:'覆寫（REPLACE，未支援執行）',UPSERT:'依鍵值合併（UPSERT，未支援執行）'};
const time=(v?:string)=>v?new Date(v).toLocaleString('zh-TW',{timeZone:'Asia/Taipei'}):'未記錄';

function useReads(base:string,paths:string[]){
  const [data,setData]=useState<Record<string,any>>({}),[error,setError]=useState(''),[attempt,setAttempt]=useState(0);
  const key=paths.join('|');
  useEffect(()=>{
    let live=true;setError('');
    Promise.all(paths.map(p=>request(base+p).then(v=>[p,v] as const))).then(rows=>{if(live)setData(Object.fromEntries(rows))})
      .catch(e=>{if(live){setData({});setError(e.message)}});
    return()=>{live=false};
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[base,key,attempt]);
  useWorkflowRefresh(base,()=>setAttempt(n=>n+1));
  return {data,error,retry:()=>setAttempt(n=>n+1)};
}

function Card({title,children}:{title:string;children:ReactNode}){return <article className="wb-summary-card"><h4>{title}</h4>{children}</article>}
function Failed({error,retry}:{error:string;retry:()=>void}){return error?<p role="alert">摘要讀取失敗：{error} <button type="button" onClick={retry}>重試讀取摘要</button></p>:null}

export const label=(ref:string,labels:Record<string,string>={})=>String(ref||'').replace(/source\.\d+/g,key=>labels[key]||key).replace(/^\$metric\./,'計算 ').replace(/^\$source_order\./,'來源序號 ');

export function RequirementSummary({detail}:{detail:any}){
  const s=detail.input_summary||{},labels=s.source_labels||{},t=s.transformation_contract_v1,r=s.requirements_v1||{};
  const sources=s.sources||[];
  return <div className="wb-summary-grid" aria-label="需求摘要">
    <Card title="來源">{sources.length?<ul>{sources.map((src:any,i:number)=><li key={i}><b>{src.label}</b> · {src.type}<small>{(src.fields||[]).map((f:any)=>f.name).join('、')||'尚未提供欄位'}</small></li>)}</ul>:<p>{s.source_type||'未記錄來源'}</p>}
      {s.join_contract_v1?.joins?.map((j:any,i:number)=><p key={i}>{j.join_type} JOIN：{(j.keys||[]).map((k:any)=>`${label(j.left_source,labels)}.${k.left_column} = ${label(j.right_source,labels)}.${k.right_column}`).join('、')||'條件見完整紀錄'}</p>)}</Card>
    <Card title="轉換">{!t?<p>沒有結構化轉換意圖。</p>:t.invalid?<p role="alert">轉換意圖不合法。</p>:<>
      <p>篩選：{t.filters?.length?t.filters.map((f:any)=>`${label(f.column,labels)} ${ops[f.operator]||f.operator}${f.constant?' '+String(f.constant.value):''}`).join('；'):'無'}</p>
      <p>{t.aggregation?`分組：${t.aggregation.group_by.map((g:string)=>label(g,labels)).join('、')||'整體'}；計算：${t.aggregation.metrics.map((m:any)=>`${m.id}=${fns[m.function]||m.function}`).join('、')}`:'不聚合，保留明細'}</p></>}</Card>
    <Card title="目標"><p>{s.target_schema||'未指定'}.{s.target_table||'未指定'}</p><p>{writeModes[r.write_mode]||'寫入方式未確認'} · {r.date_scope==='RANGE'?`${r.date_column}：${r.start_date}（含）～${r.end_date_exclusive}（不含）`:r.date_scope==='ALL'?'全部資料':'資料期間未確認'}</p>
      {!!r.key_columns?.filter(Boolean).length&&<p>鍵欄位：{r.key_columns.join('、')}</p>}</Card>
    <Card title="預期結果">{t?.output_columns?.length?<p>輸出欄位：{t.output_columns.map((c:string)=>label(c,labels)).join(' → ')}</p>:<p>輸出欄位依核准規格。</p>}
      <p>{s.requirement_text?String(s.requirement_text).slice(0,160)+(String(s.requirement_text).length>160?'…':''):'無需求說明'}</p></Card>
  </div>;
}

export function ReviewSummary({base}:{base:string}){
  const {data,error,retry}=useReads(base,['/sa-invocation','/sa-approval']);
  const item=data['/sa-invocation']?.invocation,approval=data['/sa-approval'];
  return <div className="wb-summary-grid" aria-label="需求審查摘要"><Failed error={error} retry={retry}/>
    <Card title="SA 審查">{!item?<p>尚無 SA 審查紀錄。</p>:<><p>{item.review?.status==='NEEDS_INPUT'?'退回：需要補正需求':item.review?'通過：可交人工確認':'結果待核對'}</p>
      <p>問題 {item.review?.issues?.length||0} 項 · {item.model||'模型未記錄'}</p></>}</Card>
    <Card title="人工確認"><p>{approval?.status==='APPROVED_CURRENT'?'已確認，交接給流程設計':approval?.status==='AWAITING_CONFIRMATION'?'待你確認 SA 建議':approval?.status==='STALE_APPROVAL'?'歷史確認已失效':'尚不可確認'}</p></Card>
    {!!item?.review?.issues?.length&&<Card title="可處理問題"><ul>{item.review.issues.map((x:any,i:number)=><li key={i}>{x.message}</li>)}</ul></Card>}
  </div>;
}

function specDiff(current:any,previous:any){
  if(!previous)return [];
  const keys=['target_schema','target_table','write_mode','filters','aggregation','output_columns','joins','source_order'];
  const names:Record<string,string>={target_schema:'目標 Schema',target_table:'目標資料表',write_mode:'寫入方式',filters:'篩選',aggregation:'分組與計算',output_columns:'輸出欄位',joins:'Join',source_order:'來源序號'};
  return keys.filter(k=>JSON.stringify(current?.[k]??null)!==JSON.stringify(previous?.[k]??null)).map(k=>names[k]);
}

export function DesignSummary({base,labels}:{base:string;labels:Record<string,string>}){
  const {data,error,retry}=useReads(base,['/specifications','/developer']);
  const items:any[]=data['/specifications']?.items||[];
  const spec=items.find(i=>i.approval_effective)||items.find(i=>i.approval_id)||items[0];
  const previous=spec&&items.find(i=>i.version===spec.version-1);
  const j=spec?.spec_json,diff=specDiff(j,previous?.spec_json);
  const dev=data['/developer']?.invocation;
  return <div className="wb-summary-grid" aria-label="流程設計摘要"><Failed error={error} retry={retry}/>
    <Card title="來源到目標">{!j?<p>尚無已保存規格。</p>:<p>{(j.version===2?j.source_refs:[j.source_ref]).map((r:string)=>label(r,labels)).join(' ＋ ')} → {j.filters?.length?`篩選 ${j.filters.length} 項 → `:''}{j.aggregation?`分組計算 ${j.aggregation.metrics.length} 項 → `:''}{j.target_schema}.{j.target_table}</p>}</Card>
    <Card title="規格版本">{!spec?<p>尚無規格。</p>:<><p>第 {spec.version} 版 · {spec.approval_effective?'核准有效':spec.approval_id?'曾核准（目前作為歷史紀錄）':'尚待核准'}</p>
      <p>{previous?(diff.length?`與第 ${previous.version} 版差異：${diff.join('、')}`:`與第 ${previous.version} 版內容相同`):'第一個規格版本'}</p></>}</Card>
    <Card title="輸出">{j?<p>{j.output_columns?.join(' → ')}</p>:<p>依規格產生。</p>}<p>Developer：{dev?dev.status==='VALIDATED_NOT_APPROVED'?'已提出設計':dev.status:'未使用模型設計'}</p></Card>
  </div>;
}

export function ConfirmSummary({base,detail,workflow}:{base:string;detail:any;workflow:any}){
  const {data,error,retry}=useReads(base,['/hop-dispatch']);
  const hop=data['/hop-dispatch'],q=workflow?.operation_qualifications?.hop_execute;
  const s=detail.input_summary||{};
  return <div className="wb-summary-grid" aria-label="執行確認摘要"><Failed error={error} retry={retry}/>
    <Card title="目標與副作用"><p>{s.target_schema}.{s.target_table}</p><p>只新建專用目標表並執行一次 Hop；表已存在即停止，不刪表、不清空、不自動重試。</p></Card>
    <Card title="執行狀態"><p>{hop?.request?`已於 ${time(hop.request.created_at)} 授權執行一次（${hop.request.status}）`:hop?.offer?'前置條件已齊備，待你確認執行一次':'前置條件尚未齊備'}</p>
      {!hop?.request&&q?.blocked_reason&&<p>{q.blocked_reason}</p>}</Card>
    <Card title="固定標準答案"><p>{workflow?.milestones?.execution_started?'已在執行前核准並鎖定，執行後不可替換。':'須在執行前保存並核准；不從結果倒推。'}</p></Card>
  </div>;
}

export function ResultsSummary({base,detail}:{base:string;detail:any}){
  const {data,error,retry}=useReads(base,['/comparisons','/hop-dispatch']);
  const c=data['/comparisons']?.items?.[0]?.evidence,hop=data['/hop-dispatch']?.request;
  const outcome:Record<string,string>={HOP_EXECUTED_QA_REQUIRED:'Hop 已完成',HOP_EXECUTION_FAILED:'Hop 回報失敗',HOP_RESULT_UNKNOWN:'結果不明'};
  return <div className="wb-summary-grid" aria-label="執行結果摘要"><Failed error={error} retry={retry}/>
    <Card title="執行狀態"><p>{outcome[detail.outcome_code]||(hop?hop.status:'尚未執行')}</p>{hop?.finished_at&&<p>完成時間：{time(hop.finished_at)}</p>}</Card>
    <Card title="預期／實際筆數">{c?<p>預期 {c.expected_count} · 實際 {c.actual_count}</p>:<p>尚無結果比對。</p>}</Card>
    <Card title="比對結果">{c?<p>{c.status==='MATCH'?'一致（非正式 QA）':c.status==='MISMATCH'?`有差異：缺少 ${c.missing_count}、多出 ${c.unexpected_count}`:'狀態未知'}</p>:<p>—</p>}</Card>
    {['HOP_EXECUTION_FAILED','HOP_RESULT_UNKNOWN'].includes(detail.outcome_code)&&<Card title="異常處理"><p>{detail.failed_revision_available?'已人工核對結案；可建立修正版（新目標）':'需人工核對目標資料並結案；不提供一般重試'}</p></Card>}
  </div>;
}

export function QualitySummary({base}:{base:string}){
  const {data,error,retry}=useReads(base,['/qa-review','/qa-approval']);
  const item=data['/qa-review']?.invocation,approval=data['/qa-approval'];
  return <div className="wb-summary-grid" aria-label="品質審查摘要"><Failed error={error} retry={retry}/>
    <Card title="最新 QA 意見">{item?.review?<><p>{item.review.status==='PASS'?'通過':item.review.status==='FAIL'?'不通過':'需補充證據'} · {time(item.created_at)}</p><p>{item.review.summary}</p></>:<p>尚無 QA 模型審查。</p>}</Card>
    <Card title="有效人工核准"><p>{approval?.status==='APPROVED_CURRENT'?'已核准（目前有效）':approval?.status==='AWAITING_CONFIRMATION'?'待你核准':approval?.status==='STALE_APPROVAL'?'歷史核准已失效':'尚無有效人工核准'}</p></Card>
    {!!item?.review?.issues?.length&&<Card title="QA 意見"><ul>{item.review.issues.map((x:any,i:number)=><li key={i}>{x.message}</li>)}</ul></Card>}
  </div>;
}

export function DeliverySummary({base}:{base:string}){
  const {data,error,retry}=useReads(base,['/release']);
  const r=data['/release'];
  if(error)return <Failed error={error} retry={retry}/>;
  if(!r?.release_ready||!r.release)return null;
  const docs:any[]=r.release.documents||[];
  return <section className="wb-delivery-final" aria-label="正式交付成果">
    <h3>正式交付已核准</h3>
    <p>核准時間：{time(r.release.approved_at)} · {r.release.file_size} bytes</p>
    <a className="primary-link" href={sourcePath(`${base}/release/${r.release.release_id}/download`)}>下載正式 Release ZIP</a>
    <h4>包內文件（依保存的 Release Manifest）</h4>
    {docs.length?<ul>{docs.map(d=><li key={d.name}><b>{d.name}</b> · {d.type}{d.size_bytes!=null?` · ${d.size_bytes} bytes`:''}</li>)}</ul>:<p>此 Release 未提供文件清單；請下載後核對 release-manifest.json，不以檔名推測。</p>}
    <details><summary>技術指紋</summary><p>ZIP SHA-256：<code>{r.release.checksum}</code></p>{docs.filter(d=>d.checksum).map(d=><p key={d.name}>{d.name}：<code>{d.checksum}</code></p>)}</details>
  </section>;
}
