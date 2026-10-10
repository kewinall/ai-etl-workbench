import {createContext,useContext,useEffect,useRef} from 'react';
export const WorkflowReadOnly=createContext(false);
export const WorkflowCanCancel=createContext(true);
export const useWorkflowCanCancel=()=>useContext(WorkflowCanCancel);
export const WorkflowCanPrepare=createContext(true);
export const useWorkflowCanPrepare=()=>useContext(WorkflowCanPrepare);
export const WorkflowQualifications=createContext<Record<string,any>>({});
export const useServiceBlocker=(operation:string)=>useContext(WorkflowQualifications)[operation]?.blocked_reason||'';
export const useWorkflowReadOnly=()=>useContext(WorkflowReadOnly);

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
