import {useState} from 'react';
import {request, jsonBody} from './api';

export function SpecificationEditor({base, initial, onSaved, onCancel}: {base: string; initial?: any; onSaved: () => Promise<void>; onCancel: () => void}) {
  const [context, setContext] = useState<any>(null);
  const [filters, setFilters] = useState<any[]>(initial?.filters?.map((f: any) => ({column: f.column, operator: f.operator, value: f.constant === null ? '' : String(f.constant.value)})) || []);
  const [filterMode, setFilterMode] = useState(initial ? initial.filters.length ? 'FILTER' : 'ALL' : '');
  const [groups, setGroups] = useState<string[]>(initial?.aggregation?.group_by || []);
  const [metrics, setMetrics] = useState<any[]>(initial?.aggregation?.metrics || []);
  const [outputs, setOutputs] = useState<string[]>(initial?.output_columns || []);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [issues, setIssues] = useState<any[]>([]);
  const action = async (work: () => Promise<void>) => {setBusy(true); setError(''); setIssues([]); try {await work()} catch (e: any) {setError(e.message)} finally {setBusy(false)}};
  const options = context?.source_columns || [];
  const hasMetrics = !!context?.metric_columns?.length;
  const available = hasMetrics ? [...groups, ...metrics.map(m => m.output_column)] : options.map((c: any) => c.name);
  const changeFilter = (index: number, values: any) => {setFilters(filters.map((f, i) => i === index ? {...f, ...values} : f)); setConfirmed(false)};
  const save = () => action(async () => {
    if (!confirmed || !filterMode || (filterMode === 'FILTER' && !filters.length)) throw new Error('請明確選擇篩選方式並確認規格。');
    const predicates = filterMode === 'ALL' ? [] : filters.map(f => {
      const kind = options.find((c: any) => c.name === f.column)?.constant_type;
      if (['IS_NULL','IS_NOT_NULL'].includes(f.operator)) return {column: f.column, operator: f.operator, constant: null};
      let value: any = f.value;
      if (kind === 'INTEGER') {if (!/^-?\d+$/.test(value) || !Number.isSafeInteger(Number(value))) throw new Error('整數常數超出此編輯器可精確表示範圍，請勿四捨五入。'); value = Number(value)}
      if (kind === 'BOOLEAN') {if (!['true','false'].includes(value)) throw new Error('布林常數請選擇 true 或 false。'); value = value === 'true'}
      if (!kind || kind === 'TIMESTAMP') throw new Error('此欄位尚不支援值比較；可使用空值條件。');
      return {column: f.column, operator: f.operator, constant: {type: kind, value}};
    });
    const body = {...context.binding, filters: predicates, aggregation: hasMetrics ? {group_by: groups, metrics: metrics.map(m => ({...m, column: m.function === 'COUNT_ROWS' ? null : m.column})), null_policy: 'SQL_NULLS'} : null, output_columns: outputs};
    const result = await request(`${base}/specifications`, jsonBody('POST', body));
    if (result.status === 'INVALID') {setIssues(result.issues); setConfirmed(false); return}
    await onSaved();
  });
  return <section aria-label="編輯 ETL 規格" className="specification-history">
    <h4>{initial ? '以此規格建立新版' : '建立 ETL 規格'}</h4>
    <p>這是人工提出的設計，不代表 SA／Developer 已審查。保存後另行核准；不會執行 ETL。</p>
    {!context && <button disabled={busy} onClick={() => action(async () => {
      const result = await request(`${base}/specification/editor-context`);
      if (result.status !== 'EDITOR_CONTEXT_READY') {setIssues(result.issues); return}
      setContext(result);
      setMetrics(result.metric_columns.map((m: any) => initial?.aggregation?.metrics.find((old: any) => old.id === m.id && old.output_column === m.output_column) || {id: m.id, output_column: m.output_column, function: '', column: ''}));
    })}>讀取已確認欄位</button>}
    {error && <p role="alert">{error}</p>}
    {!!issues.length && <ul role="alert">{issues.map((issue: any, i: number) => <li key={i}>{issue.message} {issue.field_path}</li>)}</ul>}
    {context && <>
      <p>固定目標：{context.binding.target_schema}.{context.binding.target_table} · {context.binding.write_mode}。變更目標需先補正 Run。</p>
      <p>欄位：{options.map((c: any) => `${c.source_name} → ${c.name} (${c.data_type})`).join('、')}</p>
      <label>篩選方式<select disabled={busy} value={filterMode} onChange={e => {setFilterMode(e.target.value); setConfirmed(false)}}><option value="">請明確選擇</option><option value="ALL">不篩選，保留全部資料</option><option value="FILTER">全部條件皆符合才保留</option></select></label>
      {filterMode === 'FILTER' && <>
        {filters.map((filter, index) => <fieldset key={index} disabled={busy}><legend>條件 {index+1}</legend>
          <label>條件欄位<select value={filter.column} onChange={e => changeFilter(index, {column: e.target.value, value: ''})}><option value="">請選擇</option>{options.map((c: any) => <option key={c.name}>{c.name}</option>)}</select></label>
          <label>比較方式<select value={filter.operator} onChange={e => changeFilter(index, {operator: e.target.value})}><option value="">請選擇</option>{Object.entries({EQ:'等於',NE:'不等於',GT:'大於',GE:'大於或等於',LT:'小於',LE:'小於或等於',IS_NULL:'為空值',IS_NOT_NULL:'非空值'}).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          {!['IS_NULL','IS_NOT_NULL'].includes(filter.operator) && <label>比較值（日期 YYYY-MM-DD，布林 true／false）<input value={filter.value} onChange={e => changeFilter(index, {value: e.target.value})}/></label>}
          <button onClick={() => {setFilters(filters.filter((_,i) => i !== index)); setConfirmed(false)}}>移除此條件</button>
        </fieldset>)}
        <button disabled={busy || filters.length >= 100} onClick={() => {setFilters([...filters, {column: '', operator: '', value: ''}]); setConfirmed(false)}}>新增篩選條件</button>
      </>}
      <h5>分組與聚合</h5>
      {!hasMetrics ? <p>目前命名契約沒有聚合輸出，因此為明細設計；如需聚合，請先補齊並確認聚合欄位命名。</p> : <>
        <p>選擇分組欄位，並為命名契約中的每個聚合輸出指定計算方式。</p>
        {options.map((c: any) => <label key={c.name}><input type="checkbox" disabled={busy} checked={groups.includes(c.name)} onChange={e => {setGroups(e.target.checked ? [...groups,c.name] : groups.filter(name => name !== c.name)); setConfirmed(false)}}/>以 {c.name} 分組</label>)}
        {metrics.map((metric,index) => <fieldset key={metric.id} disabled={busy}><legend>聚合輸出 {metric.output_column}</legend>
          <label>聚合方式<select value={metric.function} onChange={e => {setMetrics(metrics.map((m,i) => i === index ? {...m,function:e.target.value} : m)); setConfirmed(false)}}><option value="">請選擇</option>{Object.entries({SUM:'加總',COUNT_ROWS:'資料筆數',COUNT_NON_NULL:'非空值筆數',MIN:'最小值',MAX:'最大值'}).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          {metric.function !== 'COUNT_ROWS' && <label>聚合來源欄位<select value={metric.column || ''} onChange={e => {setMetrics(metrics.map((m,i) => i === index ? {...m,column:e.target.value} : m)); setConfirmed(false)}}><option value="">請選擇</option>{options.map((c: any) => <option key={c.name}>{c.name}</option>)}</select></label>}
        </fieldset>)}
      </>}
      <h5>輸出欄位（依勾選順序）</h5>
      {available.map((name: string) => <label key={name}><input disabled={busy} type="checkbox" checked={outputs.includes(name)} onChange={e => {setOutputs(e.target.checked ? [...outputs,name] : outputs.filter(n => n !== name)); setConfirmed(false)}}/>{name}</label>)}
      <p>目前順序：{outputs.join(' → ') || '尚未選擇'}。取消後重新勾選可移至最後；不在可用欄位的舊選擇將由伺服器拒絕。</p>
      <label><input disabled={busy} type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)}/>我已確認篩選、分組、聚合及輸出順序，保存為待核准規格。</label>
      <button disabled={busy || !confirmed || !filterMode || !outputs.length} onClick={save}>驗證並保存規格新版</button>
    </>}
    <button disabled={busy} onClick={onCancel}>取消規格編輯</button>
  </section>;
}
