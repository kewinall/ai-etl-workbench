export function JoinSummary({joins}: {joins?: any[]}) {
  if (!joins?.length) return null;
  return <section aria-label="Join 關聯規則" style={{overflowWrap: 'anywhere'}}>
    <h5>Join 關聯規則</h5>
    {joins.map(join => <div key={join.id}>
      <p>節點：<code>{join.id}</code> · {join.left_source} → {join.right_source}</p>
      <p>{join.join_type === 'LEFT' ? 'LEFT JOIN：保留左側未匹配資料，右側欄位為空值。' : join.join_type === 'INNER' ? 'INNER JOIN：只保留兩側匹配資料。' : `未支援的 Join 類型：${join.join_type}`}</p>
      <ul>{join.keys?.map((key: any, index: number) => <li key={index}>
        <code>{join.left_source}.{key.left_column}</code> ＝ <code>{join.right_source}.{key.right_column}</code>
      </li>)}</ul>
      <p>空鍵：{join.null_key_policy === 'NEVER_MATCH' ? 'NULL 不互相匹配（NEVER_MATCH）' : join.null_key_policy}。</p>
      <p>重複鍵：{join.duplicate_key_policy === 'EXPAND' ? '展開所有匹配組合（EXPAND）' : join.duplicate_key_policy}。</p>
      <p>字串比較：{join.string_comparison === 'CASE_SENSITIVE_NO_TRIM' ? '區分大小寫，不去除前後空白' : join.string_comparison}。</p>
    </div>)}
  </section>;
}
