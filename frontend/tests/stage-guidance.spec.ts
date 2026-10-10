import {test,expect,type Page} from '@playwright/test';
const project='00000000-0000-0000-0000-000000000010';
const taskId='TASK-STAGE-UI';
const current='11111111-1111-4111-8111-111111111111',old='22222222-2222-4222-8222-222222222222';
const keys=['requirements','review','design','confirm','results','quality','delivery'];
const labels=['需求與資料規格','需求審查','流程設計審查','執行確認','執行與結果','品質審查','成果交付'];
const base=`/#/projects/${project}/tasks/${taskId}`;
function run(id=current){return {run_id:id,task_id:taskId,created_at:'2026-10-10T00:00:00Z',state:'NEEDS_REVIEW',phase:'REQUIREMENT_GATE',matches_current:true,write_started:false,input_checksum:'a'.repeat(64),settings_checksum:'b'.repeat(64),events:[],gate_result:{status:'NEEDS_INPUT',issues:[{message:'請補正目標',field_path:'target.table'}]},settings_summary:{},input_summary:{requirement_text:'原始需求，其他內容必須保留',target_schema:'ai_sample',target_table:'original',source_fields:[],source_fields_editable:false,requirements_v1:{version:1,write_mode:'APPEND',date_scope:'ALL'},transformation_source_refs:[]}}}
function status(id=current,stage='requirements'){const i=keys.indexOf(stage);return {task_id:taskId,run_id:id,current_stage:stage,updated_at:'2026-10-10T00:00:00Z',historical:id===old,matches_current:true,category:'待你確認',owner:'你',completed:[],waiting:false,issues:[],stages:keys.map((key,n)=>({key,number:n+1,label:labels[n],status:n===i?'current':'blocked',can_operate:id!==old&&n<=i,blocked_reason:n>i?'先完成前一階段的必要核准與證據。':null})),next_action:{label:'確認需求版本',stage,enabled:id!==old},source_scope_note:'完整執行尚未驗收'};}
async function fixture(page:Page,options:{stage?:string;waiting?:boolean;issues?:any[];unknown?:boolean}={}) {
 let stale=false,reads=0,posts=0;const records=[run(),run(old)];
 await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(route.request().method()!=='GET'){
   posts++;
   if(path.endsWith('/revisions')){const child={...run('33333333-3333-4333-8333-333333333333'),state:'QUEUED',approval:null,parent_run_id:current,input_summary:{...run().input_summary,...route.request().postDataJSON()}};records.unshift(child);if(options.unknown)return route.abort();return route.fulfill({json:child,status:201})}
   return route.fulfill({json:{}});
  }
  if(path.endsWith('/workflow-status')){reads++;if(stale)return route.abort();const id=path.split('/').at(-2)!;return route.fulfill({json:{...status(id,options.stage),waiting:!!options.waiting,issues:options.issues||[]}})}
  if(path==='/api/tasks')return route.fulfill({json:[]});
  if(path==='/api/health')return route.fulfill({json:{mode:'postgres'}});
  if(path==='/api/ready')return route.fulfill({json:{execution_enabled:false}});
  if(path===`/api/tasks/${taskId}`)return route.fulfill({json:{id:taskId,project_id:project,name:'階段導引合成測試',source:'CSV',target:'VERTICA',source_config:{sources:[]},target_config:{},nodes:[],logs:[]}});
  if(path.endsWith('/runs'))return route.fulfill({json:{runs:records}});
  if(path.match(/\/runs\/[^/]+$/)){const selected=records.find(r=>r.run_id===path.split('/').at(-1));return route.fulfill({json:selected||{detail:'missing'},status:selected?200:404})}
  if(path.endsWith('/specifications')||path.endsWith('/comparisons')||path.endsWith('/oracles'))return route.fulfill({json:{items:[]}});
  if(path.endsWith('/sa-authorization'))return route.fulfill({json:{eligible:false,dispatch_enabled:false,authorization:{policy_version:'copilot-cli-once-v1'}}});
  if(path.endsWith('/sa-approval')||path.endsWith('/qa-approval'))return route.fulfill({json:{status:'NOT_ELIGIBLE'}});
  if(path.endsWith('/developer')||path.endsWith('/qa-review')||path.endsWith('/sa-invocation'))return route.fulfill({json:{invocation:null,history:[],eligible:false}});
  if(path.endsWith('/qa-authorization'))return route.fulfill({json:{eligible:false}});
  if(path.endsWith('/artifacts'))return route.fulfill({json:{status:'NO_AUTHORIZED_COMPILER_ARTIFACTS'}});
  if(path.endsWith('/hop-dispatch'))return route.fulfill({json:{request:null,offer:null,blocked_reason:'前置條件不足'}});
  if(path.endsWith('/release'))return route.fulfill({json:{status:'PREREQUISITES_REQUIRED',release_ready:false}});
  if(path.endsWith('/sdm'))return route.fulfill({json:{items:[]}});
  if(path.endsWith('/naming-contract'))return route.fulfill({json:{contract:null}});
  if(path.endsWith('/workers'))return route.fulfill({json:{workers:[]}});
  return route.fulfill({json:{}});
 });
 return {stale:()=>{stale=true},counts:()=>({reads,posts})};
}

test('真實隔離 API：新 Task 建立版本、確認輸入与唯讀狀態，未呼叫模型',async({page,request})=>{
 expect((await (await request.get('/api/ready')).json()).execution_enabled).toBe(false);
 const suffix=Date.now(),profile='stage-ui-'+suffix,connection='stage-conn-'+suffix;
 const settings=(await (await request.get('/api/settings/groups')).json()).values.data_connections_targets;
 expect((await request.put('/api/settings/ai-profiles/'+profile,{data:{display_name:'isolated stage UI',provider_type:'LITELLM_BEDROCK',region:'us-east-1',model_routes:{requirement_gate:'bedrock/synthetic',etl_specification:'bedrock/synthetic',qa_review:'bedrock/synthetic'},enabled:true}})).ok()).toBeTruthy();
 expect((await request.put('/api/settings/groups/data_connections_targets',{data:{...settings,etl_qa:{connection_id:connection,host:'synthetic-no-connection',port:5433,database:'synthetic',user:'synthetic'}}})).ok()).toBeTruthy();
 const p=await (await request.post('/api/projects',{data:{project_name:'stage guide '+suffix,default_ai_profile:profile,default_connection:connection}})).json();
 const t=await (await request.post(`/api/projects/${p.project_id}/tasks`,{data:{name:'合成階段導引',requirement:'只測試畫面核准流程，不執行 ETL',source_config:{sources:[{type:'CSV',alias:'synthetic',has_actual_data:false,fields:[{name:'id',type:'BIGINT'}]}]},target_schema:'ai_sample',target_table:'stage_ui'}})).json();
 await page.goto(`/#/projects/${p.project_id}/tasks/${t.id}/requirements`);
 await page.getByRole('button',{name:'建立準備版本',exact:true}).click();
 await expect(page.getByLabel('共用 Run 版本')).not.toHaveValue('');
 await page.getByLabel('我已核對本次需求及設定版本').check();
 await page.getByRole('button',{name:'確認此版輸入',exact:true}).click();
 await expect(page.getByRole('region',{name:'目前狀態與下一步'})).toContainText('等待需求審查');
 const id=await page.getByLabel('共用 Run 版本').inputValue();
 const d=await (await request.get(`/api/tasks/${t.id}/runs/${id}`)).json();
 expect(d.approval.decision).toBe('APPROVE');expect(d.write_started).toBe(false);
 expect((await (await request.get(`/api/tasks/${t.id}/runs/${id}/sa-invocation`)).json()).invocation).toBeNull();
});

test('歷史版跨階段、重載与返回版本一致；缺失版不替換',async({page})=>{
 await fixture(page);await page.goto(base+'/requirements/'+old);
 await expect(page.getByLabel('共用 Run 版本')).toHaveValue(old);
 await page.getByRole('tab',{name:/3 · 流程設計/}).click();await expect(page).toHaveURL(new RegExp('/design/'+old));
 await expect(page.getByRole('button',{name:'授權 Developer 設計'})).toHaveCount(0);
 await page.reload();await expect(page.getByLabel('共用 Run 版本')).toHaveValue(old);
 await page.goBack();await expect(page.getByLabel('共用 Run 版本')).toHaveValue(old);
 await page.goto(base+'/quality/missing');await expect(page.getByRole('alert')).toContainText('未改用最新版本');
 await expect(page.getByLabel('共用 Run 版本')).toHaveValue('missing');
});

test('舊 execution URL 相容導向保留版本',async({page})=>{
 await fixture(page);await page.goto(base+'/execution/'+old);await expect(page).toHaveURL(new RegExp('/results/'+old));
 await expect(page.getByLabel('共用 Run 版本')).toHaveValue(old);
});

test('修正保留輸入、阻止離開、預覽差異后只建立一版',async({page})=>{
 const f=await fixture(page,{issues:[{message:'目標待修正',field_path:'target.table'}]});await page.goto(base+'/review/'+current);
 await page.getByRole('button',{name:'前往修正'}).click();
 await expect(page.getByRole('form',{name:'需求補正'})).toBeVisible();
 await expect(page.getByLabel('補正後需求')).toHaveValue('原始需求，其他內容必須保留');
 await page.getByLabel('目標 Table',{exact:true}).fill('corrected');
 await page.getByRole('tab',{name:/2 · 需求審查/}).click();
 await expect(page.getByRole('form',{name:'需求補正'})).toBeVisible();
 await page.getByRole('button',{name:'預覽修訂差異'}).click();
 await expect(page.getByRole('region',{name:'修訂差異預覽'})).toContainText('original');
 await expect(page.getByRole('region',{name:'修訂差異預覽'})).toContainText('corrected');
 await page.getByLabel('已核對差異，同意建立待需求確認的新版').check();
 await page.getByRole('button',{name:'保存補正並建立新版'}).dblclick();
 await expect(page.getByLabel('共用 Run 版本')).toHaveValue('33333333-3333-4333-8333-333333333333');
 expect(f.counts().posts).toBe(1);
});

test('回應遺失先讀取已建立子版，不重送',async({page})=>{
 const f=await fixture(page,{unknown:true});await page.goto(base+'/requirements/'+current);
 await page.getByRole('button',{name:'補正需求並建立新版'}).click();await page.getByLabel('目標 Table',{exact:true}).fill('corrected');
 await page.getByRole('button',{name:'預覽修訂差異'}).click();await page.getByLabel('已核對差異，同意建立待需求確認的新版').check();
 await page.getByRole('button',{name:'保存補正並建立新版'}).click();
 await expect(page.getByRole('button',{name:'重新讀取新版建立結果'})).toBeVisible();
 await page.getByRole('button',{name:'重新讀取新版建立結果'}).click();
 await expect(page.getByLabel('共用 Run 版本')).toHaveValue('33333333-3333-4333-8333-333333333333');expect(f.counts().posts).toBe(1);
});

test('狀態過期停用操作；等待僅唯讀輪詢，隱藏時暫停',async({page})=>{
 const f=await fixture(page,{waiting:true});await page.goto(base+'/requirements/'+current);
 await expect(page.getByRole('button',{name:'補正需求並建立新版'})).toBeEnabled();
 const initial=f.counts().reads;
 await page.waitForTimeout(5500);expect(f.counts().reads).toBeGreaterThan(initial);
 await page.evaluate(()=>Object.defineProperty(document,'hidden',{configurable:true,get:()=>true}));const hidden=f.counts().reads;
 await page.waitForTimeout(5500);expect(f.counts().reads).toBe(hidden);expect(f.counts().posts).toBe(0);
 await page.evaluate(()=>Object.defineProperty(document,'hidden',{configurable:true,get:()=>false}));f.stale();
 await page.getByRole('button',{name:'重新核對狀態'}).click();await expect(page.getByRole('alert')).toContainText('資訊過期');
 await expect(page.getByRole('button',{name:'補正需求並建立新版'})).toBeDisabled();
});

for(const width of [390,768,1440])test(`${width}px 七階段鍵盤与版面`,async({page})=>{
 await fixture(page);await page.setViewportSize({width,height:1000});await page.goto(base+'/requirements/'+current);
 await expect(page.getByLabel('共用 Run 版本')).toHaveValue(current);
 await page.getByRole('tab',{name:/1 · 需求/}).focus();await page.keyboard.press('ArrowRight');await expect(page.getByRole('tab',{name:/2 · 需求審查/})).toBeFocused();
 for(const key of keys){await page.getByRole('tab',{name:new RegExp(`${keys.indexOf(key)+1} ·`)}).click();await expect(page).toHaveURL(new RegExp('/'+key+'/'+current));expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true)}
 await page.screenshot({path:test.info().outputPath(`stage-${width}.png`),fullPage:true});
});
