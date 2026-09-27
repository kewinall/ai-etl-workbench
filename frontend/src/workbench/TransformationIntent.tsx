// Source identities remain stable across English naming changes.
export function intentPayload(value: any) {
  if (!value) return null;
  const result = structuredClone(value);
  result.filters = result.filters.map((filter: any) => {
    if (['IS_NULL', 'IS_NOT_NULL'].includes(filter.operator)) return {...filter, constant: null};
    const constant = {...filter.constant};
    if (constant.type === 'INTEGER') {
      const text = String(constant.value);
      if (!/^-?\d+$/.test(text) || !Number.isSafeInteger(Number(text))) throw new Error('整數常數須為可精確表示的整數；不得四捨五入。');
      constant.value = Number(text);
    } else if (constant.type === 'BOOLEAN') {
      if (![true, false, 'true', 'false'].includes(constant.value)) throw new Error('請明確選擇布林常數。');
      constant.value = constant.value === true || constant.value === 'true';
    }
    return {...filter, constant};
  });
  return result;
}

export function TransformationSummary({value}: {value: any}) {
  if (!value) return <p>此版本沒有結構化轉換意圖；一般數值門檻及聚合語意仍需人工核對，不能視為已由程式逐項驗證。</p>;
  if (value.invalid) return <p role="alert">轉換意圖不合法；請補正並建立新版本。</p>;
  return <section aria-label="已保存轉換意圖"><h4>已保存轉換意圖</h4>
    <p>綁定本次輸入版本；保存不等於核准或執行。來源使用原始欄位識別，編譯時才套用已確認英文命名。</p>
    <p>篩選：全部條件均成立，排除未知值（NULL 比較）；{value.filters.length ? '' : '無篩選。'}</p>
    {!!value.filters.length && <ul>{value.filters.map((f: any, i: number) => <li key={i}>{f.column} {f.operator} {f.constant ? `${f.constant.type} ${String(f.constant.value)}` : ''}</li>)}</ul>}
    {value.aggregation ? <><p>分組：{value.aggregation.group_by.join('、')}；NULL 視為同組。</p><ul>{value.aggregation.metrics.map((m: any) => <li key={m.id}>{m.id}：{m.function} {m.column || '所有列，包含 NULL 列'}</li>)}</ul></> : <p>無聚合，保留符合條件的重複列。</p>}
    <p>輸出順序：{value.output_columns.join(' → ')}</p>
  </section>;
}

export function TransformationEditor({value, sources, disabled, onChange}: {value: any; sources: string[]; disabled: boolean; onChange: (value: any) => void}) {
  const patch = (changes: any) => onChange({...value, ...changes});
  const select = (label: string, current: string, choices: string[], change: (v: string) => void) => <label>{label}<select aria-label={label} required value={current} onChange={e => change(e.target.value)}><option value="">請選擇</option>{choices.map(v => <option key={v} value={v}>{v}</option>)}</select></label>;
  if (!value || value.invalid) return <fieldset disabled={disabled}><legend>結構化轉換意圖</legend>
    <p>明確指定篩選、分組、計數方式與輸出順序；不從模型設計或標準答案自動填入。</p>
    <button type="button" disabled={!sources.length} onClick={() => onChange({version: 1, filters: [], filter_logic: 'ALL', filter_null_policy: 'EXCLUDE_UNKNOWN', aggregation: null, output_columns: []})}>新增轉換意圖</button>
  </fieldset>;
  const agg = value.aggregation;
  const outputs = agg ? [...agg.group_by, ...agg.metrics.filter((m: any) => m.id).map((m: any) => '$metric.' + m.id)] : sources;
  return <fieldset disabled={disabled}><legend>結構化轉換意圖</legend>
    <p>全部篩選條件以 AND 結合；一般比較排除 NULL。沒有條件代表不篩選。欄位包含來源編號，避免同名欄位混淆。</p>
    {value.filters.map((f: any, index: number) => {
      const change = (changes: any) => patch({filters: value.filters.map((item: any, i: number) => i === index ? {...item, ...changes} : item)});
      return <fieldset key={index}><legend>篩選 {index + 1}</legend>
        {select(`篩選欄位 ${index + 1}`, f.column, sources, column => change({column}))}
        {select(`比較方式 ${index + 1}`, f.operator, ['EQ','NE','LT','LE','GT','GE','IS_NULL','IS_NOT_NULL'], operator => change({operator, constant: ['IS_NULL','IS_NOT_NULL'].includes(operator) ? null : f.constant || {type: '', value: ''}}))}
        {f.constant && <>
          {select(`常數型別 ${index + 1}`, f.constant.type, ['INTEGER','DECIMAL','STRING','BOOLEAN','DATE'], type => change({constant: {type, value: ''}}))}
          {f.constant.type === 'BOOLEAN' ? select(`常數值 ${index + 1}`, String(f.constant.value), ['true','false'], v => change({constant: {...f.constant, value: v}})) : <label>常數值 {index + 1}<input required={f.constant.type !== 'STRING'} maxLength={2000} type={f.constant.type === 'DATE' ? 'date' : 'text'} value={String(f.constant.value)} onChange={e => change({constant: {...f.constant, value: e.target.value}})}/></label>}
        </>}
        <button type="button" onClick={() => patch({filters: value.filters.filter((_: any, i: number) => i !== index)})}>移除篩選 {index + 1}</button>
      </fieldset>;
    })}
    <button type="button" disabled={value.filters.length >= 100} onClick={() => patch({filters: [...value.filters, {column: '', operator: '', constant: {type: '', value: ''}}]})}>新增篩選</button>
    <label>聚合方式<select value={agg ? 'GROUP' : 'NONE'} onChange={e => patch({aggregation: e.target.value === 'GROUP' ? {group_by: [], metrics: [], null_policy: 'SQL_NULLS'} : null, output_columns: []})}><option value="NONE">不聚合</option><option value="GROUP">依欄位分組</option></select></label>
    {agg && <>
      <p>分組欄位至少一個；NULL 歸為同組。COUNT_ROWS 包含 NULL 列，COUNT_NON_NULL 只計指定欄位非 NULL 的列。</p>
      {sources.map(ref => <label key={ref}><input type="checkbox" checked={agg.group_by.includes(ref)} onChange={e => patch({aggregation: {...agg, group_by: e.target.checked ? [...agg.group_by, ref] : agg.group_by.filter((v: string) => v !== ref)}, output_columns: []})}/>{ref}</label>)}
      {agg.metrics.map((m: any, index: number) => {
        const change = (changes: any) => patch({aggregation: {...agg, metrics: agg.metrics.map((item: any, i: number) => i === index ? {...item, ...changes} : item)}});
        return <fieldset key={index}><legend>聚合指標 {index + 1}</legend>
          <label>指標識別 {index + 1}<input required pattern="[a-z_][a-z0-9_]{0,62}" value={m.id} onChange={e => change({id: e.target.value})}/></label>
          {select(`聚合函數 ${index + 1}`, m.function, ['SUM','COUNT_ROWS','COUNT_NON_NULL','MIN','MAX'], fn => change({function: fn, column: fn === 'COUNT_ROWS' ? null : ''}))}
          {m.function !== 'COUNT_ROWS' && select(`聚合來源 ${index + 1}`, m.column || '', sources, column => change({column}))}
          <button type="button" onClick={() => patch({aggregation: {...agg, metrics: agg.metrics.filter((_: any, i: number) => i !== index)}, output_columns: []})}>移除指標 {index + 1}</button>
        </fieldset>;
      })}
      <button type="button" disabled={agg.metrics.length >= 100} onClick={() => patch({aggregation: {...agg, metrics: [...agg.metrics, {id: '', function: '', column: ''}]}})}>新增聚合指標</button>
      <p>每個指標需在命名契約中確認 $metric.指標識別 的英文名稱與型別；不能只改模型輸出。</p>
    </>}
    <p>逐項指定輸出順序；若修改來源或指標，請重新核對所有輸出。至少一欄。</p>
    {value.output_columns.map((ref: string, index: number) => <div key={index}>
      {select(`輸出欄位 ${index + 1}`, ref, outputs, column => patch({output_columns: value.output_columns.map((v: string, i: number) => i === index ? column : v)}))}
      <button type="button" onClick={() => patch({output_columns: value.output_columns.filter((_: string, i: number) => i !== index)})}>移除輸出 {index + 1}</button>
    </div>)}
    <button type="button" disabled={value.output_columns.length >= 200} onClick={() => patch({output_columns: [...value.output_columns, '']})}>新增輸出欄位</button>
  </fieldset>;
}
