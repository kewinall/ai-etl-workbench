import {createContext,useContext,useEffect,useRef} from 'react';
export const WorkflowReadOnly=createContext(false);
export const WorkflowCanCancel=createContext(true);
export const useWorkflowCanCancel=()=>useContext(WorkflowCanCancel);
export const WorkflowCanPrepare=createContext(true);
export const useWorkflowCanPrepare=()=>useContext(WorkflowCanPrepare);
export const WorkflowQualifications=createContext<Record<string,any>>({});
export const useServiceBlocker=(operation:string)=>useContext(WorkflowQualifications)[operation]?.blocked_reason||'';
export const useWorkflowReadOnly=()=>useContext(WorkflowReadOnly);
// Shared read-only workflow projection (milestones, effective status). Null outside the stage workspace.
export const WorkflowStatus=createContext<any>(null);
export const useWorkflowStatus=()=>useContext(WorkflowStatus);
// Inside the stage workspace one shared "重新核對狀態" refreshes every reader; component buttons only appear for retry after a failed GET.
export const WorkflowManagedRefresh=createContext(false);
export const useManagedRefresh=()=>useContext(WorkflowManagedRefresh);

// Per-operation eligibility from the server projection. Enabled here never bypasses backend validation.
// Inside the managed stage workspace a missing projection, a missing entry or anything but enabled===true
// disables the operation ("操作資格尚未確認"). Only components rendered outside that workspace keep the
// legacy read-only fallback.
export const UNCONFIRMED='操作資格尚未確認；請按「重新核對狀態」，未確認前不提供此操作。';
export function useOperation(name:string,{ignoreReadOnly=false}:{ignoreReadOnly?:boolean}={}):{enabled:boolean;reason:string;known:boolean}{
  const readOnly=useContext(WorkflowReadOnly)&&!ignoreReadOnly;
  const managed=useContext(WorkflowManagedRefresh);
  const status=useContext(WorkflowStatus);
  const item=useContext(WorkflowQualifications)[name];
  if(!managed&&!item)return {enabled:!readOnly,reason:'',known:false};
  if(managed&&(!status||!item))return {enabled:false,reason:UNCONFIRMED,known:true};
  const ok=item.enabled===true;
  return {enabled:!readOnly&&ok,reason:ok?'':item.blocked_reason||UNCONFIRMED,known:true};
}

// Only re-read server state. Never invoke a write or reset an open editor.
export function useWorkflowRefresh(base:string,read:()=>unknown,editing=false) {
  const latest=useRef({read,editing});latest.current={read,editing};
  useEffect(()=>{
    const refreshed=(e:Event)=>{
      const path=(e as CustomEvent).detail?.path||'';
      if(!document.hidden&&!latest.current.editing&&base.startsWith(path))void latest.current.read();
    };
    window.addEventListener('workbench:read-refresh',refreshed);
    return()=>window.removeEventListener('workbench:read-refresh',refreshed);
  },[base]);
}

// Visible note when an operation is disabled only because its eligibility could not be confirmed.
export const unconfirmed=(op:{enabled:boolean;reason:string})=>!op.enabled&&op.reason===UNCONFIRMED;
