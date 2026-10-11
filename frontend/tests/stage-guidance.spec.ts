import {test,expect,type Page} from '@playwright/test';
const project='00000000-0000-0000-0000-000000000010';
const taskId='TASK-STAGE-UI';
const current='11111111-1111-4111-8111-111111111111',old='22222222-2222-4222-8222-222222222222';
const keys=['requirements','review','design','confirm','results','quality','delivery'];
const labels=['需求與資料規格','需求審查','流程設計審查','執行確認','執行與結果','品質審查','成果交付'];
const base=`/#/projects/${project}/tasks/${taskId}`;
const OPS=['prepare_run','input_confirm','input_cancel','requirement_revision','sa_authorize','sa_cancel','sa_approve','naming_confirm','developer_authorize','specification_create','specification_approve','sdm_candidate','oracle_save','oracle_approve','hop_execute','execution_close','preparation_close','comparison_recovery','qa_authorize','qa_approve','sdm_prepare','release_candidate','release_approve','release_download'];
function run(id=current){return {run_id:id,task_id:taskId,created_at:'2026-10-10T00:00:00Z',state:'NEEDS_REVIEW',phase:'REQUIREMENT_GATE',matches_current:true,write_started:false,input_checksum:'a'.repeat(64),settings_checksum:'b'.repeat(64),events:[],gate_result:{status:'NEEDS_INPUT',issues:[{message:'請補正目標',field_path:'target.table'}]},settings_summary:{},input_summary:{requirement_text:'原始需求，其他內容必須保留',target_schema:'ai_sample',target_table:'original',source_fields:[],source_fields_editable:false,requirements_v1:{version:1,write_mode:'APPEND',date_scope:'ALL'},transformation_source_refs:[]}}}
function status(id=current,stage='requirements'){const i=keys.indexOf(stage);return {task_id:taskId,run_id:id,current_stage:stage,updated_at:'2026-10-10T00:00:00Z',historical:id===old,matches_current:true,category:'待你確認',owner:'你',completed:[],waiting:false,issues:[],stages:keys.map((key,n)=>({key,number:n+1,label:labels[n],status:n===i?'current':'blocked',can_operate:id!==old&&n<=i,blocked_reason:n>i?'先完成前一階段的必要核准與證據。':null})),next_action:{label:'確認需求版本',stage,enabled:id!==old},source_scope_note:'完整執行尚未驗收',operation_qualifications:quals(id!==old)};}
// Synthetic eligibility: every operation allowed on the current version; real gating is tested in workflow-consistency.
function quals(enabled:boolean){return Object.fromEntries(OPS.map(op=>[op,{type:'SAVE',enabled,blocked_reason:enabled?null:'歷史版本只讀'}]))}
async function fixture(page:Page,options:{stage?:string;waiting?:boolean;issues?:any[];unknown?:boolean;actionLabel?:string;qaRevision?:boolean;join?:boolean;mismatch?:boolean;readOnlySource?:boolean;cancelled?:boolean}={}) {
 let stale=false,reads=0,posts=0;const records=[run(),run(old)];
 if(options.mismatch)records[0].matches_current=false;
 if(options.cancelled)records.forEach(r=>r.state='CANCELLED');
 if(options.join)Object.assign(records[0].input_summary,{sources:[{label:'左表',fields:[{name:'id',type:'BIGINT'}]},{label:'右表',fields:[{name:'id',type:'BIGINT'}]}]});
 if(options.qaRevision)Object.assign(records[0],{write_started:true,qa_revision:{checksum:'c'.repeat(64)}});
 await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(route.request().method()!=='GET'){
   posts++;
   if(path.endsWith('/revisions')){const child={...run('33333333-3333-4333-8333-333333333333'),state:'QUEUED',approval:null,parent_run_id:current,input_summary:{...run().input_summary,...route.request().postDataJSON()}};records.unshift(child);if(options.unknown)return route.abort();return route.fulfill({json:child,status:201})}
   if(path.endsWith('/cancel'))records.find(r=>r.run_id===path.split('/').at(-2))!.state='CANCELLED';
   return route.fulfill({json:{}});
  }
  if(path.endsWith('/workflow-status')){reads++;if(stale)return route.abort();const id=path.split('/').at(-2)!;const s=status(id,options.stage);return route.fulfill({json:{...s,matches_current:!options.mismatch,read_only_source:!!options.readOnlySource,next_action:{...s.next_action,label:options.actionLabel||s.next_action.label},waiting:!!options.waiting,issues:options.issues||[]}})}
  if(path==='/api/projects')return route.fulfill({json:[{project_id:project,project_name:'階段導引專案',description:'',naming_rules:{},default_ai_profile:'test',default_connection:'test'}]});
  if(path===`/api/projects/${project}/tasks`)return route.fulfill({json:[{id:taskId,name:'階段導引合成測試',project_id:project,source:'CSV',target:'VERTICA',latest_run:records[0]}]});
  if(path===`/api/projects/${project}/evaluation`)return route.fulfill({json:{project_id:project,basis:'ALL_PERSISTED_RUNS',cases:[{task_id:taskId,run_id:current,state:'NEEDS_REVIEW'}]}});
  if(path.endsWith('/history-assets'))return route.fulfill({json:{jobs:[{artifact_id:'legacy',name:'old.hpl',version:1,download_url:'/api/legacy-download',transforms:[],hops:[],content:'<pipeline/>'}],sql:[],hop_logs:[]}});
  if(path==='/api/tasks')return route.fulfill({json:[]});
  if(path==='/api/health')return route.fulfill({json:{mode:'postgres'}});
  if(path==='/api/ready')return route.fulfill({json:{execution_enabled:false}});
  // Requirements stage shows the Pilot readiness panel again; give it a complete synthetic answer.
  if(path.endsWith('/execution-settings'))return route.fulfill({json:{status:'CONFIGURED_NOT_TESTED',issues:[],execution_enabled:false,runtime_integration:'PENDING',credentials_and_connectivity:'NOT_TESTED'}});
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
  if(path.endsWith('/sdm-candidates'))return route.fulfill({json:{items:[],release_ready:false}});
  if(path.endsWith('/sdm'))return route.fulfill({json:{items:[]}});
  if(path.endsWith('/naming-contract'))return route.fulfill({json:{contract:null}});
  if(path.endsWith('/workers'))return route.fulfill({json:{workers:[]}});
  return route.fulfill({json:{}});
 });
 return {stale:()=>{stale=true},counts:()=>({reads,posts})};
}

test('真實隔離 API：新 Task 建立版本、確認輸入与唯讀狀態，未呼叫模型',async({page,request})=>{
 test.skip((await (await request.get('/api/ready')).json()).execution_enabled,'真實執行環境不安裝 synthetic Profile 或改寫資料連線');
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
 await expect(page.getByRole('region',{name:'目前狀態與下一步'})).toContainText('控制服務未就緒');
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
 await page.goBack();await expect(page).toHaveURL(new RegExp('/requirements/'+old));await expect(page.getByLabel('共用 Run 版本')).toHaveValue(old);
 await expect(page.getByRole('button',{name:'重新核對狀態'})).toBeEnabled();
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
 const toggle=page.getByRole('button',{name:/目前查看：第/});
 const openList=async()=>{if(width<=600){await expect(page.getByRole('tab',{name:/1 · 需求/})).toBeHidden();await toggle.click();await expect(toggle).toHaveAttribute('aria-expanded','true')}else await expect(toggle).toBeHidden()};
 await openList();
 await page.getByRole('tab',{name:/1 · 需求/}).focus();await page.keyboard.press('ArrowRight');await expect(page).toHaveURL(new RegExp('/review/'+current));
 if(width>600)await expect(page.getByRole('tab',{name:/2 · 需求審查/})).toBeFocused();else await expect(toggle).toContainText('第 2 階段 需求審查');
 for(const key of keys){await openList();await page.getByRole('tab',{name:new RegExp(`${keys.indexOf(key)+1} ·`)}).click();await expect(page).toHaveURL(new RegExp('/'+key+'/'+current));expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true)
  // Focused controls must not sit under the sticky header.
  const header=await page.locator('.workflow-heading').boundingBox();const panel=await page.locator(`#stage-panel-${key}`).boundingBox();
  if(header&&panel&&width>900)expect(panel.y+2>=header.y+header.height||panel.y>=0).toBe(true)}
 await page.screenshot({path:test.info().outputPath(`stage-${width}.png`),fullPage:true});
});

test('規格退回導向設計，QA 補證導向品質；不建立需求新版或重跑',async({page})=>{
 const f=await fixture(page,{stage:'quality',actionLabel:'補充證據並重新審查（不重跑 Hop）',issues:[{message:'缺同次執行證據',stage:'quality'},{message:'規格語意不符',stage:'design'}]});
 await page.goto(base+'/results/'+current);
 await page.getByRole('button',{name:'檢視 QA 意見與補證'}).click();await expect(page).toHaveURL(new RegExp('/quality/'+current));
 await expect(page.getByRole('region',{name:'目前狀態與下一步'})).toContainText('不重跑 Hop');
 await page.getByRole('button',{name:'檢視並修正规格'}).click();await expect(page).toHaveURL(new RegExp('/design/'+current));
 await expect(page.getByRole('form',{name:'需求補正'})).toHaveCount(0);expect(f.counts().posts).toBe(0);
});

test('待核對結果不提供導引重試；標準答案沿用共用 Run',async({page})=>{
 const f=await fixture(page,{stage:'results',actionLabel:'核對結果並結案'});await page.goto(base+'/results/'+current);
 await expect(page.getByRole('region',{name:'目前狀態與下一步'})).toContainText('核對結果並結案');
 await expect(page.getByRole('button',{name:/一般重試|重新執行/})).toHaveCount(0);
 await page.getByRole('tab',{name:/4 · 執行確認/}).click();await expect(page.getByLabel('標準答案準備版本')).toHaveCount(0);
 await expect(page.getByLabel('共用 Run 版本')).toHaveValue(current);expect(f.counts().posts).toBe(0);
});

test('專案接續開啟精確 Run 與階段；舊版下載保留',async({page})=>{
 await fixture(page,{stage:'design'});await page.goto(`/#/projects/${project}/history`);
 await page.getByRole('button',{name:'繼續處理 階段導引合成測試'}).click();await expect(page).toHaveURL(new RegExp('/design/'+current));
 await page.getByText('舊版紀錄：Task 節點、Log、Hop、SQL 與下載',{exact:true}).click();
 await page.getByRole('button',{name:'讀取舊版產物'}).click();await expect(page.getByRole('link',{name:'下載舊版 old.hpl'})).toHaveAttribute('href','/api/legacy-download');
});

test('離線停用操作，恢復連線只讀核對',async({page})=>{
 const f=await fixture(page);await page.goto(base+'/requirements/'+current);
 await expect(page.getByRole('button',{name:'補正需求並建立新版'})).toBeEnabled();
 await page.evaluate(()=>window.dispatchEvent(new Event('offline')));await expect(page.getByRole('alert')).toContainText('網路已斷線');
 await expect(page.getByRole('button',{name:'補正需求並建立新版'})).toBeDisabled();
 await page.evaluate(()=>window.dispatchEvent(new Event('online')));await expect(page.getByRole('button',{name:'補正需求並建立新版'})).toBeEnabled();expect(f.counts().posts).toBe(0);
});

test('QA 退回修正版保留已執行結果並要求新目標；不自動送出',async({page})=>{
 const f=await fixture(page,{stage:'quality',qaRevision:true});await page.goto(base+'/quality/'+current);
 await page.getByRole('button',{name:'建立修正版（保留原始執行，使用新目標）'}).click();
 await expect(page.getByRole('form',{name:'需求補正'})).toBeVisible();
 await expect(page.getByLabel('目標 Table',{exact:true})).toBeFocused();
 await expect(page.getByText(/必須指定 ai_sample 中不同的新目標/)).toBeVisible();expect(f.counts().posts).toBe(0);
});

 test('Join 修訂先預覽且保留原版，不自動送出',async({page})=>{
 const f=await fixture(page,{join:true});await page.goto(base+'/requirements/'+current);
 await page.getByRole('button',{name:'補正需求並建立新版'}).click();
 await page.getByRole('button',{name:'設定 Join 條件'}).click();
 await page.getByLabel('Join 類型').selectOption('LEFT');
 await page.getByLabel('左表鍵欄位').selectOption('id');await page.getByLabel('右表鍵欄位').selectOption('id');
 await page.getByLabel('NULL 鍵').selectOption('NEVER_MATCH');await page.getByLabel('重複鍵').selectOption('EXPAND');await page.getByLabel('字串比對').selectOption('CASE_SENSITIVE_NO_TRIM');
 await page.getByRole('button',{name:'預覽修訂差異'}).click();
 await expect(page.getByRole('region',{name:'修訂差異預覽'}).getByRole('cell',{name:/^Join 規則/}).first()).toBeVisible();
 await expect(page.getByText('join_contract_v1',{exact:false})).toBeHidden();expect(f.counts().posts).toBe(0);
 });

for (const [path,field] of [['requirements_v1.write_mode','write_mode'],['requirements_v1.date_scope','date_scope'],['requirements_v1.key_columns','key_columns']]) test(`缺漏問題定位實際欄位 ${field}`,async({page})=>{
 const f=await fixture(page,{issues:[{message:'必要欄位缺漏',field_path:path}]});
 await page.goto(base+'/review/'+current);
 await page.getByRole('button',{name:'前往修正',exact:true}).click();
 await expect(page.locator(`[data-field="${field}"]`)).toBeFocused();
 await expect(page.getByLabel('補正後需求')).toHaveValue('原始需求，其他內容必須保留');
 expect(f.counts().posts).toBe(0);
});

 test('失效最新輸入可取消，其他操作停用；歷史與來源只讀不能取消',async({page})=>{
 const f=await fixture(page,{mismatch:true});await page.goto(base+'/requirements/'+current);
 const cancel=page.getByRole('button',{name:'取消未執行版本',exact:true});
 await expect(cancel).toBeEnabled();
 await expect(page.getByRole('button',{name:'補正需求並建立新版',exact:true})).toHaveCount(0);
 await cancel.click();expect(f.counts().posts).toBe(1);
 await expect(page.getByText('已取消未執行的版本，歷史紀錄仍保留。',{exact:true})).toBeVisible();
 await page.getByLabel('共用 Run 版本').selectOption(old);await expect(page.getByLabel('共用 Run 版本')).toHaveValue(old);await expect(cancel).toBeDisabled();
 f.stale();await page.getByRole('button',{name:'重新核對狀態',exact:true}).click();await expect(page.getByRole('alert')).toBeVisible();await expect(cancel).toBeDisabled();
});
 test('原始證據來源即使是最新未執行版，也不得取消',async({page})=>{
 const f=await fixture(page,{mismatch:true,readOnlySource:true});await page.goto(base+'/requirements/'+current);
 await expect(page.getByRole('button',{name:'取消未執行版本',exact:true})).toBeDisabled();expect(f.counts().posts).toBe(0);
});

 test('失效版本全部取消後可建立新快照；歷史與來源只讀不能建立',async({page})=>{
 await fixture(page,{mismatch:true,cancelled:true});await page.goto(base+'/requirements/'+current);
 await expect(page.getByRole('button',{name:'建立準備版本',exact:true})).toBeEnabled();
 await page.goto(base+'/requirements/'+old);await expect(page.getByRole('button',{name:'建立準備版本',exact:true})).toBeDisabled();
});

 test('設計自動顯示唯讀命名建議，等待人工確認，不保存或授權模型',async({page})=>{
 const f=await fixture(page,{stage:'design'});let previews=0;
 await page.route('**/naming-contract/suggestion',route=>{previews++;return route.fulfill({json:{contract:{status:'DRAFT',columns:[{source_name:'source.0.id',english_name:'id',vertica_type:'BIGINT',confidence:1,reason:'deterministic_normalizer'}]}}})});
 await page.goto(base+'/design/'+current);
 await expect(page.getByLabel('命名英文 1',{exact:true})).toHaveValue('id');
 await expect(page.getByRole('button',{name:'確認並保存命名版本',exact:true})).toBeDisabled();
 await page.getByLabel('命名英文 1',{exact:true}).fill('left_id');
 await page.getByRole('button',{name:'重新核對狀態',exact:true}).click();
 await expect(page.getByLabel('命名英文 1',{exact:true})).toHaveValue('left_id');
 expect(previews).toBe(1);expect(f.counts().posts).toBe(0);
});

test('重新比對使用共用更新顯示結果，不重送授權（合成 UI）',async({page})=>{
 const tracker=await fixture(page,{stage:'results'});
 await page.route('**/hop-dispatch',r=>r.fulfill({json:{request:{status:'NEEDS_REVIEW',outcome_code:'HOP_PREPARATION_OR_COMPARISON_FAILED'},offer:null}}));
 let state='QUEUED';
 await page.route('**/comparison-recovery',r=>r.fulfill({json:{status:state,outcome_code:state==='FAILED'?'RESULT_NULL_NOT_ALLOWED':null}}));
 await page.goto(base+'/results/'+current);
 const panel=page.getByRole('region',{name:'只重新比對結果'});
 await expect(panel).toContainText('已排入結果比對');
 state='FAILED';
 await page.evaluate(path=>window.dispatchEvent(new CustomEvent('workbench:read-refresh',{detail:{path}})),`/api/tasks/${taskId}/runs/${current}`);
 await expect(panel).toContainText('實際結果含 NULL');
 await expect(panel.getByRole('button',{name:'授權重新比對（不重跑 ETL）'})).toHaveCount(0);
 expect(tracker.counts().posts).toBe(0);
});

test('空白標準答案必須明確確認零筆，新增資料列立即取消零筆確認（合成 UI）',async({page})=>{
 const tracker=await fixture(page,{stage:'confirm'});
 await page.route('**/specifications',r=>r.fulfill({json:{items:[{specification_id:'spec',version:1,approval_effective:true}]}}));
 await page.route('**/oracle-editor-context',r=>r.fulfill({json:{version:1,columns:[{name:'id',kind:'INTEGER',nullable:false}],max_rows:10000}}));
 await page.goto(base+'/confirm/'+current);
 const panel=page.getByRole('region',{name:'標準答案輸入'});
 await expect(panel.getByRole('button',{name:'保存答案版本'})).toBeDisabled();
 await panel.getByLabel('我確認預期結果確實為 0 筆').check();
 await expect(panel.getByRole('button',{name:'保存答案版本'})).toBeEnabled();
 await panel.getByRole('button',{name:'新增答案資料列'}).click();
 await expect(panel.getByLabel('第 1 筆 id',{exact:true})).toBeVisible();
 await panel.getByRole('button',{name:'刪除第 1 筆'}).click();
 await expect(panel.getByLabel('我確認預期結果確實為 0 筆')).not.toBeChecked();
 await expect(panel.getByRole('button',{name:'保存答案版本'})).toBeDisabled();
 expect(tracker.counts().posts).toBe(0);
});

for(const preparation of [false,true]) test(`人工結案簡化：${preparation?'準備':'已執行'}只需筆數與一次確認，不需檔案（合成 API）`,async({page})=>{
 await fixture(page,{stage:'results'});
 let closed=false,posts=0;
 const endpoint=preparation?'hop-preparation-reconciliation':'reconciliation';
 await page.route('**/hop-dispatch',r=>r.fulfill({json:{request:{status:preparation?'CLAIMED':'NEEDS_REVIEW',outcome_code:'HOP_PREPARATION_OR_COMPARISON_FAILED'},offer:null}}));
 await page.route('**/comparison-recovery',r=>r.fulfill({json:{status:preparation?'NOT_ELIGIBLE':'FAILED',outcome_code:'RESULT_NULL_NOT_ALLOWED'}}));
 await page.route('**/'+endpoint,async r=>{
  if(r.request().method()==='POST'){
   posts++;expect(r.request().postDataJSON()).toEqual({binding_checksum:'a'.repeat(64),observed_row_count:5,...(preparation?{target_exists:true}:{}),engine_stopped:true,target_checked:true,confirmed:true});closed=true;
  }
  await r.fulfill({json:closed?{status:'CLOSED_WITHOUT_RETRY',observed_row_count:5,target_exists:true,evidence_sha256:null}:{status:'AWAITING_RECONCILIATION',binding:{checksum:'a'.repeat(64)}}});
 });
 await page.goto(base+'/results/'+current);
 const panel=page.getByRole('region',{name:preparation?'Hop 準備失聯人工核對':'執行結果人工核對',exact:true});
 const save=panel.getByRole('button',{name:'確認結案，保留結果'});
 await expect(panel.locator('input[type=file]')).toHaveCount(0);
 await expect(panel.getByRole('checkbox')).toHaveCount(1);
 await expect(save).toBeDisabled();
 if(preparation)await panel.getByLabel('目標表是否存在').selectOption('yes');
 await panel.getByLabel('核對時目標筆數').fill('5');
 await expect(save).toBeDisabled();
 await panel.getByRole('checkbox').check();await expect(save).toBeEnabled();
 await save.click({clickCount:2});
 await expect(panel.getByRole('status')).toContainText('已人工結案');
 await page.reload();await expect(panel.getByRole('status')).toContainText('已人工結案');
 expect(posts).toBe(1);
});

test('結案仍顯示原結果階段，明確建立修正版才開啟沿用表單（合成 API）',async({page})=>{
 const tracker=await fixture(page,{stage:'results'});
 const closed={...run(),state:'FAILED',write_started:true,failed_revision_available:true,outcome_code:'HOP_EXECUTED_QA_REQUIRED'};
 await page.route(`**/runs/${current}`,r=>r.fulfill({json:closed}));
 await page.route('**/workflow-status',r=>r.fulfill({json:{...status(current,'results'),next_action:{stage:'requirements',label:'此版已結案；可建立修正版',enabled:true}}}));
 await page.goto(base+'/results/'+current);
 const next=page.getByRole('region',{name:'目前狀態與下一步'});
 await expect(next).toContainText('第 5 階段');
 await expect(next).toContainText('此次結案已保存');
 await expect(page.getByRole('form',{name:'需求補正'})).toHaveCount(0);
 await next.getByRole('button',{name:'建立修正版（保留此版結果）'}).click();
 await expect(page).toHaveURL(new RegExp('/requirements/'+current+'$'));
 await expect(page.getByRole('form',{name:'需求補正'})).toBeVisible();
 await expect(page.locator('[data-field="target_table"]')).toHaveValue('original');
 await expect(page.locator('[data-field="requirement_text"]')).toHaveValue('原始需求，其他內容必須保留');
 expect(tracker.counts().posts).toBe(0);
});

for(const hasDocument of [false,true])test(`交付頁自動讀取文件：${hasDocument?'已有候選文件立即顯示':'結案無文件顯示原因與結果入口'}（合成 API）`,async({page})=>{
 const tracker=await fixture(page,{stage:'delivery'});
 const closed={...run(),state:'FAILED',write_started:true,failed_revision_available:true,outcome_code:'HOP_EXECUTED_QA_REQUIRED'};
 if(!hasDocument)await page.route(`**/runs/${current}`,r=>r.fulfill({json:closed}));
 let reads=0;
 await page.route('**/sdm-candidates',r=>{reads++;return r.fulfill({json:{items:hasDocument?[{sdm_id:current,status:'CANDIDATE_NOT_RELEASED',release_ready:false,checksum:'a'.repeat(64),specification_checksum:'b'.repeat(64),file_size:100,created_at:'2026-10-10T00:00:00Z'}]:[],release_ready:false}})});
 await page.goto(base+'/delivery/'+current);
 const panel=page.getByRole('region',{name:'SDM 候選文件歷史'});
 if(hasDocument){await expect(panel.getByRole('button',{name:'下載歷史候選 Excel（非 Release）'})).toBeVisible();}
 else{
  await expect(panel).toContainText('尚無已保存的 SDM 候選文件');
  const blocked=page.getByRole('region',{name:'交付阻擋原因'});await expect(blocked).toContainText('結案不代表 QA 核准');
  await blocked.getByRole('button',{name:'查看此版流程與執行結果'}).click();await expect(page).toHaveURL(new RegExp('/results/'+current+'$'));
 }
 expect(reads).toBeGreaterThan(0);expect(tracker.counts().posts).toBe(0);
});

test('補正表單不提供 REPLACE／UPSERT 作為新版執行方式（合成 API）',async({page})=>{
 const f=await fixture(page);await page.goto(base+'/requirements/'+current);
 await page.getByRole('button',{name:'補正需求並建立新版'}).click();
 const mode=page.getByLabel('寫入模式');
 await expect(mode.locator('option[value="APPEND"]')).not.toHaveAttribute('disabled','');
 await expect(mode.locator('option[value="REPLACE"]')).toHaveAttribute('disabled','');await expect(mode.locator('option[value="UPSERT"]')).toHaveAttribute('disabled','');
 await expect(page.getByRole('form',{name:'需求補正'})).toContainText('目前編譯器只執行 APPEND');
 expect(f.counts().posts).toBe(0);
});


test('Hop 準備失敗不可沿用需求階段補正入口（合成 API）',async({page})=>{
 const f=await fixture(page);
 await page.route('**/api/tasks/'+taskId+'/runs/'+current,route=>route.fulfill({json:{...run(),phase:'HOP_PREPARATION',outcome_code:'HOP_PREPARATION_INVALID'}}));
 await page.goto(base+'/requirements/'+current);
 await expect(page.getByText('執行準備失敗，尚未啟動 Hop',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'補正需求並建立新版',exact:true})).toHaveCount(0);
 expect(f.counts().posts).toBe(0);
});
