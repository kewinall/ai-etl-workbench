import {useState} from 'react';
import {request, jsonBody} from './api';
import {SpecificationEditor} from './SpecificationEditor';
import {SdmPreview} from './SdmPreview';
import {SdmHistory} from './SdmHistory';

const operators: Record<string, string> = {EQ: '等於', NE: '不等於', GT: '大於', GE: '大於或等於', LT: '小於', LE: '小於或等於', IS_NULL: '為空值', IS_NOT_NULL: '非空值'};
const functions: Record<string, string> = {SUM: '加總', COUNT_ROWS: '筆數', COUNT_NON_NULL: '非空值筆數', MIN: '最小值', MAX: '最大值'};

export function SpecificationHistory({taskId, runId}: {taskId: string; runId: string}) {
  const [items, setItems] = useState<any[] | null>(null);
  const [selected, setSelected] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [preview, setPreview] = useState<any>(null);
  const [editing, setEditing] = useState(false);
  const [editSource, setEditSource] = useState<any>(undefined);
  const base = `/api/tasks/${encodeURIComponent(taskId)}/runs/${encodeURIComponent(runId)}`;
  const load = async () => {
    const result = await request(`${base}/specifications`);
    setItems(result.items);
    setSelected(current => result.items.some((item: any) => item.specification_id === current) ? current : result.items[0]?.specification_id || '');
    setConfirmed(false); setPreview(null);
  };
  const action = async (operation: () => Promise<void>) => {
    setBusy(true); setError(''); setMessage('');
    try {await operation()} catch (error: any) {setError(error.message); setConfirmed(false)} finally {setBusy(false)}
  };
  const current = items?.find(item => item.specification_id === selected);
  const spec = current?.spec_json;
  return <section className="specification-history" aria-label="ETL 規格版本">
    <h4>ETL 規格版本</h4>
    <p>查看已保存的規格與核准。規格核准不代表 Hop 已執行、QA 通過或可交付。</p>
    <button disabled={busy} onClick={() => action(load)}>{items === null ? '載入規格版本' : '重新整理規格版本'}</button>
    <button disabled={busy || editing} onClick={() => {setEditSource(undefined); setEditing(true)}}>建立規格</button>
    {editing && <SpecificationEditor base={base} initial={editSource} onCancel={() => setEditing(false)} onSaved={async () => {await load(); setEditing(false); setMessage('已保存待核准規格，沒有執行 ETL。')}}/>}
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {items?.length === 0 && <p>此準備版本尚無已保存規格。請先確認命名契約，再建立規格；不會自行產生或假設需求。</p>}
    {!!items?.length && <label>選擇規格版本<select disabled={busy} value={selected} onChange={event => {setSelected(event.target.value); setConfirmed(false); setPreview(null); setMessage(''); setError('')}}>
      {items.map(item => <option key={item.specification_id} value={item.specification_id}>第 {item.version} 版 · {item.approval_effective ? '規格核准有效' : item.approval_id ? '歷史核准已失效' : '尚未核准'}</option>)}
    </select></label>}
    {spec && <>
      <button disabled={busy || editing || !current.reviewable} onClick={() => {setEditSource(spec); setEditing(true)}}>以此規格編輯新版</button>
      <dl>
        <div><dt>目標資料表</dt><dd>{spec.target_schema}.{spec.target_table}</dd></div>
        <div><dt>寫入方式</dt><dd>{spec.write_mode === 'APPEND' ? '附加資料（APPEND）' : spec.write_mode}</dd></div>
        <div><dt>來源參照</dt><dd>{spec.source_ref}</dd></div>
        <div><dt>命名版本</dt><dd>第 {spec.naming.version} 版</dd></div>
        <div><dt>規格識別碼</dt><dd className="spec-checksum">{current.content_checksum}</dd></div>
      </dl>
      <h5>篩選條件（全部符合）</h5>
      {spec.filters.length ? <ul>{spec.filters.map((filter: any, index: number) => <li key={index}>{filter.column} {operators[filter.operator] || filter.operator} {filter.constant ? String(filter.constant.value) : ''}</li>)}</ul> : <p>不篩選資料。</p>}
      <p>空值比較結果不明時排除該筆資料；明確的「為空值」條件除外。</p>
      <h5>分組與聚合</h5>
      {spec.aggregation ? <><p>分組欄位：{spec.aggregation.group_by.join('、')}</p><ul>{spec.aggregation.metrics.map((metric: any) => <li key={metric.id}>{metric.output_column}：{functions[metric.function] || metric.function}{metric.column ? `（${metric.column}）` : ''}</li>)}</ul></> : <p>不聚合，保留明細。</p>}
      <h5>輸出欄位順序</h5><ol>{spec.output_columns.map((name: string) => <li key={name}>{name}</li>)}</ol>
      {current.approval_effective&&<SdmPreview key={current.specification_id} url={`${base}/specifications/${current.specification_id}/sdm-preview`} specificationChecksum={current.content_checksum}/>}
      <p>{current.approval_effective ? '此規格核准目前有效；尚未授權執行或 Release。' : current.approval_id ? '歷史核准已失效，紀錄仍保留。請檢查最新規格及上游內容。' : current.reviewable ? '可檢閱後核准此規格。' : '此版本目前不可核准，請檢查需求、設定與命名版本。'}</p>
      {current.reviewable && !current.approval_effective && <>
        <label><input type="checkbox" checked={confirmed} disabled={busy} onChange={event => setConfirmed(event.target.checked)}/>我已檢查目標、篩選、分組與輸出，確認此規格；這不是執行授權。</label>
        <button disabled={busy || !confirmed} onClick={() => action(async () => {
          await request(`${base}/specifications/${current.specification_id}/approve`, jsonBody('POST', {content_checksum: current.content_checksum}));
          await load(); setMessage('規格核准已保存；未啟動 Hop 或產生 Release。');
        })}>核准此版規格</button>
      </>}
      <button disabled={busy || !current.reviewable} onClick={() => action(async () => {setPreview(null); setPreview(await request(`${base}/specification/compile-preview`, jsonBody('POST', spec)))} )}>檢查 Hop 編譯預覽</button>
      {preview && (preview.status === 'INVALID' ? <ul role="alert">{preview.issues.map((issue: any, index: number) => <li key={index}>{issue.message}</li>)}</ul> : <div>
        <p>已產生編譯候選，尚未執行。原生驗證、資料來源綁定及 QA／交付條件仍須檢查。</p>
        <ol>{preview.plan.stages.map((stage: any) => <li key={stage.id}>{stage.id} · 程式工具 {stage.component}</li>)}</ol>
        <details><summary>查看 HPL 候選（非交付產物）</summary><pre>{preview.hpl}</pre></details>
        <details><summary>查看 HWF 候選（非交付產物）</summary><p>Start → Pipeline，等待完成，不自動重試。引用同目錄 pipeline.hpl；執行時仍須提供已驗證的來源與連線。</p><pre>{preview.hwf}</pre></details>
        <details><summary>查看 DDL 候選（未執行）</summary><p>只包含此規格的輸出欄位。不會自動建表、刪表或重建既有表；仍須確認目標環境及核准。</p><pre>{preview.ddl}</pre></details>
        <details><summary>查看參數範本與環境需求</summary><p>SOURCE_CSV 須在執行時指定，不隨包附帶資料。目的環境需另設 local 執行設定與 etl_target 連線；此範本不會由 Hop 自動載入，也不含平台密鑰。</p><pre>{preview.parameters}</pre><p className="spec-checksum">參數範本指紋：{preview.parameters_checksum}</p></details>
        <details><summary>Hop 候選指紋</summary><p className="spec-checksum">HPL：{preview.hpl_checksum}</p><p className="spec-checksum">HWF：{preview.hwf_checksum}</p><p className="spec-checksum">DDL：{preview.ddl_checksum}</p></details>
      </div>)}
    </>}
    <SdmHistory key={base} base={base}/>
  </section>;
}
