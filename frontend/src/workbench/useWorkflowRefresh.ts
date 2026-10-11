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

// Per-operation eligibility from the server projection. Enabled here never bypasses backend validation;
// outside the stage workspace (no projection) only the read-only flag applies.
export function useOperation(name:string):{enabled:boolean;reason:string;known:boolean}{
  const readOnly=useContext(WorkflowReadOnly);
  const item=useContext(WorkflowQualifications)[name];
  if(!item)return {enabled:!readOnly,reason:'',known:false};
  return {enabled:!readOnly&&item.enabled!==false,reason:item.enabled===false?item.blocked_reason||'目前不可操作。':'',known:true};
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
