import {useEffect,useRef,useState,type ComponentType} from 'react';
import {Boxes,BookOpen,BarChart3,Settings,SlidersHorizontal,ClipboardCheck,ChevronDown} from 'lucide-react';
import type {Route} from './routes';

type Item={key:string;label:string;path:string;Icon:ComponentType<any>;active:boolean};

// Primary navigation keeps daily work (projects, guide) visible; settings and evaluation live under one
// expandable 管理 group. Existing URLs (#/pilot, #/system, #/projects/{id}/settings|evaluation) are unchanged.
export function MainNav({route,navigate}:{route:Route;navigate:(path:string)=>void}){
  const project=route.projectId&&route.projectId!=='new'?route.projectId:'';
  const onProjectTab=(tab:string)=>route.page==='projects'&&!!project&&route.tab===tab;
  const manage:Item[]=[
    ...(project?[{key:'project-settings',label:'專案設定',path:`/projects/${project}/settings`,Icon:SlidersHorizontal,active:onProjectTab('settings')},
                {key:'project-evaluation',label:'Pilot 評估',path:`/projects/${project}/evaluation`,Icon:ClipboardCheck,active:onProjectTab('evaluation')}]:[]),
    {key:'pilot',label:'Pilot 成果',path:'/pilot',Icon:BarChart3,active:route.page==='pilot'},
    {key:'system',label:'平台設定中心',path:'/system',Icon:Settings,active:route.page==='system'},
  ];
  const managing=manage.some(i=>i.active);
  const [open,setOpen]=useState(managing);
  // Follow the route: open on management pages, collapse when the user moves back to daily work.
  useEffect(()=>{setOpen(managing)},[managing,route.page,route.tab,route.projectId]);
  const toggle=useRef<HTMLButtonElement>(null);
  const primary=[
    {key:'projects',label:'專案工作區',path:'/projects',Icon:Boxes,active:['projects','task','new'].includes(route.page)&&!managing},
    {key:'guide',label:'操作指南',path:'/guide',Icon:BookOpen,active:route.page==='guide'},
  ];
  const link=(i:Item,sub=false)=><button key={i.key} type="button" title={i.label} className={`${i.active?'active':''}${sub?' nav-sub':''}`} aria-current={i.active?'page':undefined} onClick={()=>navigate(i.path)}><i.Icon/>{i.label}</button>;
  return <nav aria-label="主要導覽">
    {primary.map(i=>link(i))}
    <button ref={toggle} type="button" title="管理" className={`nav-manage${managing?' active':''}`} aria-expanded={open} aria-controls="nav-manage-group" onClick={()=>setOpen(x=>!x)}><Settings/>管理<ChevronDown className="nav-caret"/></button>
    <div id="nav-manage-group" role="group" aria-label="管理" className="nav-manage-group" hidden={!open}
      onKeyDown={e=>{if(e.key==='Escape'){e.preventDefault();setOpen(false);toggle.current?.focus()}}}>
      {manage.map(i=>link(i,true))}
      {!project&&<small className="nav-note">專案設定與 Pilot 評估：請先進入專案</small>}
    </div>
  </nav>;
}
