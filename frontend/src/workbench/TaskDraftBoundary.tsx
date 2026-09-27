import {createContext,useCallback,useContext,useEffect,useRef,useState,Fragment,type ReactNode} from 'react';
import {OperationLatch} from './operationLatch';

type DraftState={dirty:boolean;busy:boolean};
const DraftContext=createContext<((id:string,value:DraftState|null)=>void)|null>(null);
const OperationContext=createContext<OperationLatch|null>(null);
export function useTaskOperation(){const shared=useContext(OperationContext);const local=useRef(new OperationLatch());return shared??local.current}

export function useTaskDraft(id:string,snapshot:unknown,busy:boolean) {
  const report=useContext(DraftContext);
  const serialized=JSON.stringify(snapshot);
  const initial=useRef(serialized);
  useEffect(()=>{report?.(id,{dirty:serialized!==initial.current,busy});return()=>report?.(id,null)},[id,serialized,busy,report]);
}

export function TaskDraftBoundary({children}:{children:(complete:()=>void)=>ReactNode}) {
  const records=useRef(new Map<string,DraftState>());
  const operation=useRef(new OperationLatch());
  const completed=useRef(false);
  const [revision,setRevision]=useState(0),[message,setMessage]=useState(''),[,refresh]=useState(0);
  const report=useCallback((id:string,value:DraftState|null)=>{
    if(value)records.current.set(id,value);else records.current.delete(id);
    refresh(n=>n+1);
  },[]);
  const current=()=>({dirty:[...records.current.values()].some(x=>x.dirty),busy:[...records.current.values()].some(x=>x.busy)});
  useEffect(()=>{
    const leave=(event:Event)=>{
      const state=current();if(completed.current||(!state.dirty&&!state.busy))return;
      event.preventDefault();setMessage(state.busy?'正在上傳或建立 Task，請等待結果，不能取消或離開。':'尚未離開：新建 Task 草稿已保留，包含另一種模式。請完成建立，或先取消全部草稿。');
    };
    const unload=(event:BeforeUnloadEvent)=>{const state=current();if(!completed.current&&(state.dirty||state.busy)){event.preventDefault();event.returnValue=''}};
    window.addEventListener('workbench:before-navigate',leave);window.addEventListener('beforeunload',unload);
    return()=>{window.removeEventListener('workbench:before-navigate',leave);window.removeEventListener('beforeunload',unload)};
  },[]);
  const state=current();
  return <DraftContext.Provider value={report}>
    {(state.dirty||state.busy)&&<section className="panel" aria-label="新建 Task 草稿保護">
      <p role="status">有未建立的 Task 草稿；切換模式會保留內容，重新整理仍可能丟失草稿。</p>
      {message&&<p role="alert">{state.busy?'正在上傳或建立 Task，請等待結果，不能取消或離開。':'尚未離開：新建 Task 草稿已保留，包含另一種模式。請完成建立，或先取消全部草稿。'}</p>}
      <button disabled={state.busy} onClick={()=>{records.current.clear();completed.current=false;setMessage('');setRevision(n=>n+1)}}>取消全部 Task 草稿</button>
      <p>取消只清除兩種模式的表單，不刪除已上傳的伺服器檔案；上傳檔案依既有到期政策處理。</p>
    </section>}
    <OperationContext.Provider value={operation.current}>
      <fieldset disabled={state.busy} style={{border:0,padding:0,margin:0,minWidth:0}} aria-label="Task 建立表單">
        <Fragment key={revision}>{children(()=>{completed.current=true;records.current.clear()})}</Fragment>
      </fieldset>
    </OperationContext.Provider>
  </DraftContext.Provider>;
}
