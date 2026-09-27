import {useEffect, useState} from 'react';
import {request, jsonBody} from './api';

export function useSettingsDraft() {
  const [v,setV]=useState<any>(null);
  const [saved,setSaved]=useState<any>(null);
  const [versions,setVersions]=useState<Record<string,string>>({});
  const [msg,setMsg]=useState('');
  const [busy,setBusy]=useState(false);
  const [loadAttempt,setLoadAttempt]=useState(0);
  const dirty=v!==null && saved!==null && JSON.stringify(v)!==JSON.stringify(saved);
  useEffect(()=>{
    let active=true;
    setMsg('');
    request('/api/settings/groups').then(x=>{
      if(!x.values || typeof x.values!=='object' || Array.isArray(x.values))throw new Error('設定回應格式不正確');
      if(active){setV(x.values);setSaved(x.values);setVersions(x.versions||{})}
    })
      .catch(e=>{if(active)setMsg(e.message)});
    return()=>{active=false};
  },[loadAttempt]);
  useEffect(()=>{
    if(!dirty&&!busy)return;
    const leave=(event:Event)=>{
      if(event.defaultPrevented)return;
      event.preventDefault();
      setMsg(busy?'設定正在儲存，請等待結果後再離開。':'尚未離開：平台設定草稿已保留。請先儲存或取消各分組的修改，再選擇目的頁面。');
    };
    const unload=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue=''};
    window.addEventListener('workbench:before-navigate',leave);
    window.addEventListener('beforeunload',unload);
    return()=>{window.removeEventListener('workbench:before-navigate',leave);window.removeEventListener('beforeunload',unload)};
  },[dirty,busy]);
  const save=async(group:string)=>{
    if(busy||!v)return;
    setBusy(true);setMsg('');
    try {
      if(!versions[group])throw new Error('缺少設定版本，請重新載入設定後再儲存');
      const options=jsonBody('PUT',v[group]);
      await request(`/api/settings/groups/${group}`,{...options,headers:{...options.headers,'X-Settings-Version':versions[group]}});
      const result=await request('/api/settings/groups');
      if(!Object.prototype.hasOwnProperty.call(result.values||{},group))throw new Error('已儲存的設定無法重新讀取');
      const value=result.values[group];
      // Only replace the saved group: other categories may contain unsaved edits.
      setV((current:any)=>({...current,[group]:value}));
      setSaved((current:any)=>({...current,[group]:value}));
      setVersions(current=>({...current,[group]:result.versions?.[group]}));
      setMsg('設定已儲存並重新讀取');
    }catch(e:any){setMsg('儲存或回讀未完成：'+e.message)}finally{setBusy(false)}
  };
  const cancel=(group:string)=>{
    if(busy||!saved)return;
    setV((current:any)=>({...current,[group]:saved[group]}));setMsg('');
  };
  const retryLoad=()=>{if(v===null)setLoadAttempt(attempt=>attempt+1)};
  const adopt=(group:string,value:any,version:string)=>{
    if(busy)return;
    setV((current:any)=>({...current,[group]:value}));
    setSaved((current:any)=>({...current,[group]:value}));
    setVersions(current=>({...current,[group]:version}));
    setMsg('已採用此分類的比較版本，其他分類草稿保留；尚未寫入設定。');
  };
  return {v,setV,msg,busy,dirty,save,cancel,retryLoad,adopt};
}
