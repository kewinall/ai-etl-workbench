import type {Page} from '@playwright/test';
// Synthetic workflow-status for browser-only tests that mock a Task's Runs. It mirrors the server shape so the
// managed stage workspace can render; eligibility here is test input, not evidence of backend authorization.
export const STAGES=['requirements','review','design','confirm','results','quality','delivery'];
export const OPS=['prepare_run','input_confirm','input_cancel','requirement_revision','sa_authorize','sa_cancel','sa_approve',
  'naming_confirm','developer_authorize','specification_create','specification_approve','sdm_candidate','oracle_save','oracle_approve',
  'hop_execute','execution_close','preparation_close','comparison_recovery','qa_authorize','qa_approve','sdm_prepare',
  'release_candidate','release_approve','release_download'];

export function workflowStatus(taskId:string,runId:string,{stage='requirements',enabled=true,historical=false,overrides={}}:
  {stage?:string;enabled?:boolean|Record<string,boolean>;historical?:boolean;overrides?:Record<string,any>}={}){
  const index=STAGES.indexOf(stage);
  const allowed=(op:string)=>typeof enabled==='boolean'?enabled:enabled[op]??false;
  return {task_id:taskId,run_id:runId,current_stage:stage,updated_at:'2026-10-11T00:00:00Z',historical,matches_current:!historical,
    category:'待你確認',effective_status:'合成狀態',owner:'你',completed:[],waiting:false,issues:[],milestones:{},
    stages:STAGES.map((key,n)=>({key,number:n+1,label:key,status:n<index?'complete':n===index?'current':'blocked',can_operate:!historical&&n<=index,
      blocked_reason:n>index?'先完成前一階段的必要核准與證據。':null})),
    next_action:{label:'合成下一步',stage,enabled:true,type:'NAVIGATE'},source_scope_note:'合成資料',
    operation_qualifications:Object.fromEntries(OPS.map(op=>[op,{type:'SAVE',enabled:!historical&&allowed(op),blocked_reason:!historical&&allowed(op)?null:'合成：不可操作'}])),
    ...overrides};
}

// Route GET workflow-status for the given synthetic Runs of one Task.
export async function routeWorkflow(page:Page,taskId:string,options:{stage?:string;enabled?:boolean|Record<string,boolean>;latest?:string}={}){
  await page.route(`**/api/tasks/${taskId}/runs/*/workflow-status`,route=>{
    const runId=new URL(route.request().url()).pathname.split('/').at(-2)!;
    route.fulfill({json:workflowStatus(taskId,runId,{...options,historical:!!options.latest&&options.latest!==runId})});
  });
}
