export function SavedJoinSummary({contract}:{contract:any}){
  if(!contract)return null;
  if(contract.version!==1||!Array.isArray(contract.joins))return <p role="alert">保存的 Join 設定格式不支援，不能推定 Join 語意。</p>;
  return <section aria-label="已保存 Join 設定"><h3>已保存 Join 設定</h3>
    <p>以下為建立 Task 時保存的條件，不代表規格已核准或流程已執行。</p>
    {contract.joins.map((join:any,index:number)=><article key={join.id||index} style={{overflowWrap:'anywhere'}}>
      <h4>{join.id||`Join ${index+1}`} · {join.join_type}</h4>
      <p>左側：{join.left_source}；右側：{join.right_source}</p>
      <ul>{Array.isArray(join.keys)&&join.keys.map((key:any,i:number)=><li key={i}>{key.left_column} = {key.right_column}</li>)}</ul>
      <p>空鍵值：{join.null_key_policy}；重複鍵：{join.duplicate_key_policy}；字串比較：{join.string_comparison}</p>
    </article>)}
  </section>;
}
