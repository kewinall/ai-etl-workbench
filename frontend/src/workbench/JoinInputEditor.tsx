export function JoinInputEditor({sources,value,onChange,disabled}:{sources:any[];value:any;onChange:(value:any)=>void;disabled:boolean}) {
  if(sources.length!==2)return null;
  const join=value?.joins?.[0];
  const update=(patch:any)=>onChange({version:1,joins:[{...join,...patch}]});
  return <fieldset disabled={disabled} aria-label="Join 條件補正"><legend>左右表 Join 規則</legend>
    <p>{sources[0].label} → {sources[1].label}。僅支援雙來源等值 INNER／LEFT Join；修正後重新審查與核准。</p>
    {!join?<button type="button" data-field="join" onClick={()=>onChange({version:1,joins:[{id:'join_main',left_source:'source.0',right_source:'source.1',join_type:'',keys:[{left_column:'',right_column:''}],null_key_policy:'',duplicate_key_policy:'',string_comparison:''}]})}>設定 Join 條件</button>:<>
      <label>Join 類型<select data-field="join" required value={join.join_type} onChange={e=>update({join_type:e.target.value})}><option value="">請選擇</option><option value="INNER">INNER：僅保留匹配列</option><option value="LEFT">LEFT：保留所有左表列</option></select></label>
      {join.keys.map((key:any,index:number)=><div key={index}>{(['left','right'] as const).map((side,i)=><label key={side}>{sources[i].label}鍵欄位<select required value={key[side+'_column']} onChange={e=>update({keys:join.keys.map((k:any,n:number)=>n===index?{...k,[side+'_column']:e.target.value}:k)})}><option value="">請選擇</option>{sources[i].fields.map((field:any)=><option key={field.name} value={field.name}>{field.name}</option>)}</select></label>)}<button type="button" disabled={join.keys.length===1} onClick={()=>update({keys:join.keys.filter((_:any,n:number)=>n!==index)})}>移除此組鍵</button></div>)}
      <button type="button" disabled={join.keys.length>=32} onClick={()=>update({keys:[...join.keys,{left_column:'',right_column:''}]})}>新增等值鍵</button>
      <label>NULL 鍵<select required value={join.null_key_policy} onChange={e=>update({null_key_policy:e.target.value})}><option value="">請確認</option><option value="NEVER_MATCH">NULL 不匹配</option></select></label>
      <label>重複鍵<select required value={join.duplicate_key_policy} onChange={e=>update({duplicate_key_policy:e.target.value})}><option value="">請確認</option><option value="EXPAND">展開所有匹配組合</option></select></label>
      <label>字串比對<select required value={join.string_comparison} onChange={e=>update({string_comparison:e.target.value})}><option value="">請確認</option><option value="CASE_SENSITIVE_NO_TRIM">區分大小寫，保留前後空白</option></select></label>
    </>}
  </fieldset>;
}
