import {useEffect, useState} from 'react';
import {request, jsonBody} from './api';
import {ConnectionTest} from './ConnectionTest';
import {ControlDatabaseStatus} from './ControlDatabaseStatus';
import {SettingsComparison} from './SettingsComparison';

function toolValues(result:any):Record<string,string> {
  const value=result?.values?.execution_tool_paths;
  if(!value || typeof value!=='object' || Array.isArray(value))throw new Error('工具路徑設定回應不完整');
  return value;
}

export function ExecutionSettings({group}:{group:string}) {
  const [tools,setTools]=useState<Record<string,string>>({});
  const [saved,setSaved]=useState<Record<string,string>|null>(null);
  const [version,setVersion]=useState('');
  const [connectionId,setConnectionId]=useState('vertica-default');
  const [secret,setSecret]=useState('');
  const [secretVersion,setSecretVersion]=useState<string|null>(null);
  const [busy,setBusy]=useState(false);
  const [toolMessage,setToolMessage]=useState('');
  const [secretMessage,setSecretMessage]=useState('');
  const [leaveMessage,setLeaveMessage]=useState('');
  const [loadAttempt,setLoadAttempt]=useState(0);
  const dirty=(saved!==null && JSON.stringify(tools)!==JSON.stringify(saved)) || !!secret;
  useEffect(()=>{let active=true;setToolMessage('');request('/api/settings/groups').then(x=>{
    const value=toolValues(x);
    if(active){setTools(value);setSaved(value);setVersion(x.versions?.execution_tool_paths||'');}
  }).catch(e=>{if(active)setToolMessage(e.message)});return()=>{active=false}},[loadAttempt]);
  useEffect(()=>{
    if(!dirty&&!busy)return;
    const leave=(event:Event)=>{
      if(event.defaultPrevented)return;
      event.preventDefault();
      setLeaveMessage(busy?'設定正在儲存，請等待結果後再離開。':'尚未離開：工具路徑或連線機密草稿已保留。請先儲存、取消路徑修改或清除未儲存機密，再選擇目的頁面。');
    };
    const unload=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue=''};
    window.addEventListener('workbench:before-navigate',leave);
    window.addEventListener('beforeunload',unload);
    return()=>{window.removeEventListener('workbench:before-navigate',leave);window.removeEventListener('beforeunload',unload)};
  },[dirty,busy]);
  const saveTools=async()=>{
    if(busy||saved===null)return;setBusy(true);setToolMessage('');
    try {
      if(!version)throw new Error('缺少設定版本，請重新載入設定後再儲存');
      const options=jsonBody('PUT',tools);
      await request('/api/settings/groups/execution_tool_paths',{...options,headers:{...options.headers,'X-Settings-Version':version}});
      const result=await request('/api/settings/groups');
      const value=toolValues(result);
      setVersion(result.versions?.execution_tool_paths||'');
      setTools(value);setSaved(value);setToolMessage('執行環境設定已儲存並重新讀取');
    }catch(e:any){setToolMessage('儲存或回讀未完成：'+e.message)}finally{setBusy(false)}
  };
  const saveSecret=async()=>{
    if(busy||!secret.trim()||!connectionId.trim()||!secretVersion)return;setBusy(true);setSecretMessage('');
    try {
      const options=jsonBody('POST',{secret_value:secret});
      await request(`/api/settings/connections/${encodeURIComponent(connectionId.trim())}/secret`,{...options,headers:{...options.headers,'X-Settings-Version':secretVersion}});
      setSecret('');setSecretMessage('資料庫連線機密已加密儲存，無法讀回');
    }catch(e:any){setSecretMessage(e.message)}finally{setBusy(false);setSecretVersion(null)}
  };
  const readSecretStatus=async()=>{
    if(busy||!connectionId.trim())return;
    setBusy(true);setSecretVersion(null);setSecretMessage('');
    try{
      const result=await request(`/api/settings/connections/${encodeURIComponent(connectionId.trim())}/secret-status`);
      if(result.connection_id!==connectionId.trim()||typeof result.version!=='string'||!result.version)throw new Error('機密版本回應不完整');
      setSecretVersion(result.version);
      setSecretMessage(result.secret_configured?'已有機密；已讀取版本，不讀取密碼。請確認本次覆蓋內容。':'尚未保存機密；已讀取版本，可建立。');
    }catch(e:any){setSecretMessage(e.message)}finally{setBusy(false)}
  };
  return <>
    {leaveMessage&&(dirty||busy)&&<p role="alert">{leaveMessage}</p>}
    {group==='connections'&&<><ControlDatabaseStatus/><ConnectionTest/></>}
    <section hidden={group!=='execution'} className="panel setting-card">
      <h2>執行環境與工具路徑</h2><p>指定 Apache Hop 與工作目錄。儲存路徑不代表 Worker 已具備該檔案，仍須通過執行環境驗證。</p>
      <fieldset disabled={busy||saved===null} style={{border:0,padding:0,margin:0,minWidth:0}}>
        <div className="settings-fields">{[['hop_run_path','Apache Hop 執行檔'],['hop_project_path','Hop 專案目錄'],['runtime_temp_path','暫存工作目錄']].map(([key,label])=><label className="setting-field" key={key}><b>{label}</b><input value={tools[key]||''} onChange={e=>setTools({...tools,[key]:e.target.value})}/></label>)}</div>
        <button className="primary" onClick={saveTools}>儲存工具路徑</button>
        <button onClick={()=>{setTools(saved||{});setToolMessage('')}}>取消路徑修改</button>
      </fieldset>
      {toolMessage&&<p role="status">{toolMessage}</p>}
      {saved!==null&&<SettingsComparison group="execution_tool_paths" draft={tools} disabled={busy} onAdopt={(value,revision)=>{setTools(value);setSaved(value);setVersion(revision);setToolMessage('已採用比較版本，尚未寫入設定')}}/>}
      {saved===null&&toolMessage&&<button onClick={()=>setLoadAttempt(attempt=>attempt+1)}>重新讀取工具路徑</button>}
    </section>
    <section hidden={group!=='security'} className="panel setting-card">
      <h2>資料庫連線機密</h2><p>密碼或 Token 只可寫入，不會由 API 或畫面回傳。儲存不會自動測試連線。</p>
      <fieldset disabled={busy} style={{border:0,padding:0,margin:0,minWidth:0}}>
        <div className="settings-fields"><label className="setting-field"><b>Connection ID</b><input value={connectionId} onChange={e=>{setConnectionId(e.target.value);setSecretVersion(null);setSecret('');setSecretMessage('連線已切換；請讀取版本後重新輸入機密')}}/></label>
        <label className="setting-field"><b>密碼或 Token</b><input type="password" aria-label="密碼或 Token" autoComplete="new-password" value={secret} onChange={e=>setSecret(e.target.value)}/><small>AES-256-GCM 加密保存</small></label></div>
        <button disabled={!connectionId.trim()} onClick={readSecretStatus}>讀取機密狀態與最新版本</button>
        <button className="primary" disabled={!secret.trim()||!connectionId.trim()||!secretVersion} onClick={saveSecret}>儲存資料庫機密</button>
        <button disabled={!secret} onClick={()=>{setSecret('');setSecretMessage('')}}>清除未儲存機密</button>
      </fieldset>
      {secretMessage&&<p role="status">{secretMessage}</p>}
    </section>
  </>;
}
