import {test,expect,type Page} from '@playwright/test';
// 合成 API：受管理 Task 工作區在操作資格缺漏、非布林 true 或版本不一致時一律停用寫入。不是後端寫入拒絕驗收。
const project='00000000-0000-0000-0000-0000000000e1',taskId='TASK-ELIGIBILITY',runId='44444444-4444-4444-8444-444444444444';
const keys=['requirements','review','design','confirm','results','quality','delivery'];
const base=`/#/projects/${project}/tasks/${taskId}`;
function run(){return {run_id:runId,task_id:taskId,created_at:'2026-10-11T00:00:00Z',updated_at:'2026-10-11T00:00:00Z',state:'QUEUED',phase:'PREFLIGHT',matches_current:true,write_started:false,approval:null,
 input_checksum:'a'.repeat(64),settings_checksum:'b'.repeat(64),gate_result:null,events:[],settings_summary:{},failed_revision_available:false,qa_revision:null,
 input_summary:{requirement_text:'資格測試',target_schema:'ai_sample',target_table:'eligibility',requirements_v1:{write_mode:'APPEND',date_scope:'ALL'},sources:[{label:'來源 1',type:'CSV',fields:[{name:'id',type:'BIGINT'}]}]}}}
function status(quals:any,id=runId){return {task_id:taskId,run_id:id,current_stage:'requirements',updated_at:'2026-10-11T00:00:00Z',historical:false,matches_current:true,category:'待你確認',effective_status:'待確認此版輸入',
 owner:'你',completed:[],waiting:false,issues:[],milestones:{},stages:keys.map((key,n)=>({key,number:n+1,label:key,status:n?'blocked':'current',can_operate:n===0,blocked_reason:n?'先完成前一階段':null})),
 next_action:{label:'確認需求版本',stage:'requirements',enabled:true},source_scope_note:'合成',...(quals===undefined?{}:{operation_qualifications:quals})}}
async function fixture(page:Page,quals:any,statusRun=runId){
 const writes:string[]=[];
 await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(route.request().method()!=='GET'){writes.push(path);return route.fulfill({status:409,json:{detail:'synthetic'}})}
  if(path.endsWith('/workflow-status'))return route.fulfill({json:status(quals,statusRun)});
  if(path==='/api/projects')return route.fulfill({json:[{project_id:project,project_name:'資格測試',description:'',naming_rules:{},default_ai_profile:'t',default_connection:'t'}]});
  if(path==='/api/tasks')return route.fulfill({json:[]});
  if(path==='/api/health')return route.fulfill({json:{mode:'postgres'}});
  if(path==='/api/ready')return route.fulfill({json:{execution_enabled:false}});
  if(path===`/api/tasks/${taskId}`)return route.fulfill({json:{id:taskId,project_id:project,name:'資格測試 Task',source:'CSV',target:'VERTICA',source_config:{sources:[]},target_config:{},nodes:[],logs:[]}});
  if(path.endsWith('/runs'))return route.fulfill({json:{runs:[run()]}});
  if(path.match(/\/runs\/[^/]+$/))return route.fulfill({json:run()});
  return route.fulfill({json:{}});
 });
 return writes;
}
const all=(enabled:any)=>({prepare_run:{type:'CREATE_RUN',enabled:false,blocked_reason:'已有待處理版本'},input_confirm:{type:'CONFIRM_INPUT',enabled,blocked_reason:enabled===true?null:'x'},
 input_cancel:{type:'CANCEL_RUN',enabled,blocked_reason:enabled===true?null:'x'}});

test('對照組：資格明確為 true 時才顯示確認與取消',async({page})=>{
 await fixture(page,all(true));await page.goto(`${base}/requirements/${runId}`);
 await expect(page.getByRole('button',{name:'確認此版輸入'})).toBeVisible();
 await expect(page.getByRole('button',{name:'取消未執行版本'})).toBeEnabled();
});

test('缺少 operation_qualifications 欄位：顯示操作資格尚未確認，寫入全部停用',async({page})=>{
 const writes=await fixture(page,undefined);await page.goto(`${base}/requirements/${runId}`);
 await expect(page.getByRole('alert').filter({hasText:'操作資格尚未確認'})).toBeVisible();
 await expect(page.getByRole('button',{name:'確認此版輸入'})).toHaveCount(0);
 await expect(page.getByRole('button',{name:'取消未執行版本'})).toBeDisabled();
 await expect(page.getByRole('button',{name:'建立準備版本'})).toBeDisabled();
 expect(writes).toEqual([]);
});

test('缺少單項資格：只停用該操作，不推定可操作',async({page})=>{
 const quals=all(true);delete (quals as any).input_confirm;
 await fixture(page,quals);await page.goto(`${base}/requirements/${runId}`);
 await expect(page.getByRole('button',{name:'取消未執行版本'})).toBeEnabled();
 await expect(page.getByRole('button',{name:'確認此版輸入'})).toHaveCount(0);
});

test('enabled 不是布林 true（字串、null）時停用',async({page})=>{
 for(const value of ['true',null,1]){
  await page.unrouteAll();await fixture(page,all(value));await page.goto(`${base}/requirements/${runId}`);
  await expect(page.getByLabel('共用 Run 版本')).toHaveValue(runId);
  await expect(page.getByRole('button',{name:'確認此版輸入'})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'取消未執行版本'})).toBeDisabled();
 }
});

test('workflow-status 回應版本不一致：停用並提示，不改用其他版本',async({page})=>{
 const writes=await fixture(page,all(true),'55555555-5555-4555-8555-555555555555');await page.goto(`${base}/requirements/${runId}`);
 await expect(page.getByRole('alert').filter({hasText:'版本回應不一致'})).toBeVisible();
 await expect(page.getByRole('button',{name:'確認此版輸入'})).toHaveCount(0);
 await expect(page.getByRole('button',{name:'取消未執行版本'})).toHaveCount(0);
 expect(writes).toEqual([]);
});
