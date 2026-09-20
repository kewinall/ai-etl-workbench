import {useEffect, useState} from 'react';
import {request, jsonBody} from './api';

export function useSettingsDraft() {
  const [v,setV]=useState<any>(null);
  const [saved,setSaved]=useState<any>(null);
  const [msg,setMsg]=useState('');
  const [busy,setBusy]=useState(false);
  const [loadAttempt,setLoadAttempt]=useState(0);
  const dirty=v!==null && saved!==null && JSON.stringify(v)!==JSON.stringify(saved);
  useEffect(()=>{
    let active=true;
    setMsg('');
    request('/api/settings/groups').then(x=>{
      if(!x.values || typeof x.values!=='object' || Array.isArray(x.values))throw new Error('設定回應格式不正確');
      if(active){setV(x.values);setSaved(x.values)}
    })
      .catch(e=>{if(active)setMsg(e.message)});
    return()=>{active=false};
  },[loadAttempt]);
  useEffect(()=>{
    if(!dirty&&!busy)return;
    const leave=(event:Event)=>{
      if(event.defaultPrevented)return;
      if(busy){event.preventDefault();window.alert('設定正在儲存，請等待結果後再離開。');return;}
      if(!window.confirm('平台設定尚未儲存，確定放棄修改並離開？'))event.preventDefault();
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
      await request(`/api/settings/groups/${group}`,jsonBody('PUT',v[group]));
      const result=await request('/api/settings/groups');
      if(!Object.prototype.hasOwnProperty.call(result.values||{},group))throw new Error('已儲存的設定無法重新讀取');
      const value=result.values[group];
      // Only replace the saved group: other categories may contain unsaved edits.
      setV((current:any)=>({...current,[group]:value}));
      setSaved((current:any)=>({...current,[group]:value}));
      setMsg('設定已儲存並重新讀取');
    }catch(e:any){setMsg('儲存或回讀未完成：'+e.message)}finally{setBusy(false)}
  };
  const cancel=(group:string)=>{
    if(busy||!saved)return;
    setV((current:any)=>({...current,[group]:saved[group]}));setMsg('');
  };
  const retryLoad=()=>{if(v===null)setLoadAttempt(attempt=>attempt+1)};
  return {v,setV,msg,busy,dirty,save,cancel,retryLoad};
}
