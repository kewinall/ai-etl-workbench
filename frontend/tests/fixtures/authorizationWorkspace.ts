import {expect,type Page} from '@playwright/test';
import {workflowStatus} from './workflow';

// Browser-only authorization controls. All reads and writes are intercepted;
// synthetic eligibility is UI input, never evidence of server/provider acceptance.
export async function authorizationWorkspace(page:Page,initialStage:string){
  const project='10000000-0000-4000-8000-000000000010';
  const task='TASK-AUTHORIZATION-UI';
  const run='10000000-0000-4000-8000-000000000011';
  let stage=initialStage;
  const unexpectedWrites:string[]=[];
  const record={run_id:run,task_id:task,state:'NEEDS_REVIEW',phase:'REQUIREMENT_GATE',matches_current:true,
    created_at:'2026-10-11T00:00:00Z',write_started:false,events:[],settings_summary:{},
    input_summary:{requirement_text:'只測試授權操作',target_schema:'ai_sample',target_table:'synthetic_only',source_fields:[]}};
  const projectData={project_id:project,project_name:'合成授權專案',description:'',naming_rules:{}};
  const taskData={id:task,project_id:project,name:'合成授權操作',source:'CSV',target:'VERTICA',source_config:{sources:[]},target_config:{},nodes:[],logs:[]};
  await page.route('**/api/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname;
    if(req.method()!=='GET'){
      unexpectedWrites.push(req.method()+' '+path);
      return route.abort();
    }
    let json:any={};
    if(path==='/api/projects')json=[projectData];
    else if(path===`/api/projects/${project}`)json=projectData;
    else if(path===`/api/projects/${project}/tasks`)json=[taskData];
    else if(path===`/api/tasks/${task}`)json=taskData;
    else if(path.endsWith('/workflow-status'))json=workflowStatus(task,run,{stage});
    else if(path.endsWith('/runs'))json={runs:[record]};
    else if(path===`/api/tasks/${task}/runs/${run}`)json=record;
    else if(path.endsWith('/history-assets'))json={jobs:[],sql:[],hop_logs:[]};
    else if(['/specifications','/comparisons','/oracles','/sdm','/sdm-candidates'].some(s=>path.endsWith(s)))json={items:[]};
    else if(path.endsWith('/qa-review')||path.endsWith('/sa-invocation'))json={invocation:null,history:[]};
    else if(path.endsWith('/naming-contract'))json={contract:null};
    else if(path.endsWith('/workers'))json={workers:[]};
    return route.fulfill({json});
  });
  return {project,task,run,record,base:`/#/projects/${project}/tasks/${task}`,setStage:(next:string)=>{stage=next},
    assertNoUnexpectedWrites:()=>expect(unexpectedWrites).toEqual([])};
}
