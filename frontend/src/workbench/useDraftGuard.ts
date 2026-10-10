import {useEffect, useRef} from 'react';

export function useDraftGuard(dirty:boolean, busy:boolean, notify:(message:string)=>void) {
  const state=useRef({dirty,busy,notify}); state.current={dirty,busy,notify};
  useEffect(()=>{
    const before=(e:Event)=>{
      const s=state.current;
      if(!s.dirty&&!s.busy)return;
      e.preventDefault();
      if(e.type!=='beforeunload')s.notify(s.busy?'操作處理中，請等待結果；不會自動重送。':'尚有未儲存內容，請先儲存草稿、建立新版或取消修改；輸入已保留。');
      else (e as BeforeUnloadEvent).returnValue='';
    };
    window.addEventListener('beforeunload',before);
    window.addEventListener('workbench:before-navigate',before);
    return()=>{window.removeEventListener('beforeunload',before);window.removeEventListener('workbench:before-navigate',before)};
  },[]);
}
