import {test,expect,type Page} from '@playwright/test';
// 合成 API 回應：驗證已交付 Run 的狀態一致性與只讀操作。不是 Native 模型／Hop／Release 驗收。
const project='00000000-0000-0000-0000-0000000000d1';
const keys=['requirements','review','design','confirm','results','quality','delivery'];
const labels=['需求與資料規格','需求審查','流程設計審查','執行確認','執行與結果','品質審查','成果交付'];
const cases=[
 {id:'TASK-DELIVERED-CSV',run:'11111111-1111-4111-8111-1111111111d1',name:'CSV 已交付',source:'CSV'},
 {id:'TASK-DELIVERED-XLSX',run:'11111111-1111-4111-8111-1111111111d2',name:'Excel 已交付',source:'EXCEL'},
 {id:'TASK-DELIVERED-JOIN',run:'11111111-1111-4111-8111-1111111111d3',name:'Join 已交付',source:'CSV'},
];
const ops=['prepare_run','input_confirm','input_cancel','requirement_revision','sa_authorize','sa_approve','naming_confirm','developer_authorize','specification_create','specification_approve','oracle_save','oracle_approve','hop_execute','execution_close','comparison_recovery','qa_authorize','qa_approve','sdm_prepare','release_candidate','release_approve'];
const blocked='此版已正式交付；只能查看與下載。目前不能從已交付版本建立修正版或新的準備版本，也不會回到原版本修改。';
const milestones={input_confirmed:true,sa_approved:true,specification_approved:true,executed:true,execution_started:true,qa_approved:true,delivered:true};
function workflow(c:any){return {task_id:c.id,run_id:c.run,current_stage:'delivery',updated_at:'2026-10-10T13:52:32Z',historical:false,matches_current:true,
 category:'可交付',effective_status:'已正式交付',delivered:true,milestones,owner:'你',completed:labels,waiting:false,issues:[],
 stages:keys.map((key,n)=>({key,number:n+1,label:labels[n],status:'complete',can_operate:false,blocked_reason:null})),
 next_action:{label:'下載正式交付',stage:'delivery',enabled:true,type:'DOWNLOAD',operation_enabled:true,blocked_reason:null},
 operation_qualifications:{...Object.fromEntries(ops.map(op=>[op,{type:'SAVE',enabled:false,blocked_reason:blocked}])),release_download:{type:'DOWNLOAD',enabled:true,blocked_reason:null},
  sa:{type:'AUTHORIZE_MODEL',service_ready:true,blocked_reason:null},hop:{type:'EXECUTE_WRITE',service_ready:true,blocked_reason:null}},
 source_types:[c.source],source_scope_note:`${c.source} 來源已有真實七階段驗收案例；本版是否通過仍以本版的執行、比對、QA 與交付證據為準。`,
 release_status:'RELEASE_READY',release:{release_id:'r-'+c.run},execution_authorized:false}}
function run(c:any){return {run_id:c.run,task_id:c.id,project_id:project,created_at:'2026-10-10T13:42:53Z',updated_at:'2026-10-10T13:52:32Z',state:'NEEDS_REVIEW',phase:'RELEASE_READY',matches_current:true,write_started:true,
 outcome_code:'HOP_EXECUTED_QA_REQUIRED',approval:{decision:'APPROVE'},input_checksum:'a'.repeat(64),settings_checksum:'b'.repeat(64),gate_result:{status:'CHECKED',issues:[]},events:[],
 settings_summary:{ai_profile_id:'ui-accept-native',connection_id:'ui-accept-vertica'},failed_revision_available:false,qa_revision:null,
 input_summary:{requirement_text:'合成已交付需求',target_schema:'ai_sample',target_table:'delivered_'+c.source.toLowerCase(),requirements_v1:{write_mode:'APPEND',date_scope:'ALL'},sources:[{label:'來源 1',type:c.source,fields:[{name:'category',type:'VARCHAR'}]}]}}}
const spec={target_schema:'ai_sample',target_table:'delivered',write_mode:'APPEND',version:1,source_ref:'source.0',naming:{version:1},filters:[],aggregation:null,output_columns:['category']};
async function fixture(page:Page,{summaryFails=false}={}){
 const writes:string[]=[];
 await page.route('**/api/**',async route=>{
  const url=new URL(route.request().url());const path=url.pathname;
  if(route.request().method()!=='GET'){writes.push(path);return route.fulfill({status:409,json:{detail:'synthetic write blocked'}})}
  const c=cases.find(x=>path.includes('/'+x.id))||cases[0];
  if(path==='/api/projects')return route.fulfill({json:[{project_id:project,project_name:'已交付一致性',description:'',naming_rules:{},default_ai_profile:'t',default_connection:'t'}]});
  if(path===`/api/projects/${project}/tasks`)return route.fulfill({json:cases.map(x=>({id:x.id,name:x.name,project_id:project,source:x.source,target:'VERTICA',latest_run:{run_id:x.run}}))});
  if(path===`/api/projects/${project}/evaluation`)return route.fulfill({json:{project_id:project,basis:'ALL_PERSISTED_RUNS',cases:cases.map(x=>({task_id:x.id,run_id:x.run,state:'NEEDS_REVIEW'}))}});
  if(path===`/api/projects/${project}/summary`){if(summaryFails)return route.fulfill({status:503,json:{detail:{message:'合成摘要失敗'}}});
   return route.fulfill({json:{project_id:project,basis:'LATEST_RUN_PER_TASK',task_count:3,states:[{state:'NEEDS_REVIEW',count:3}],qa_evaluated:false,release_evaluated:false,
    workflow_basis:'WORKFLOW_STATUS_LATEST_RUN',workflow_evaluated:true,workflow_counts:{'可交付':3},workflow_unverified:0,
    tasks:cases.map(x=>({task_id:x.id,run_id:x.run,category:'可交付',current_stage:'delivery',next_action:'下載正式交付',effective_status:'已正式交付',delivered:true,waiting:false,stale:false}))}})}
  if(path.endsWith('/workflow-status'))return route.fulfill({json:workflow(c)});
  if(path==='/api/tasks')return route.fulfill({json:[]});
  if(path==='/api/health')return route.fulfill({json:{mode:'postgres'}});
  if(path==='/api/ready')return route.fulfill({json:{execution_enabled:true}});
  if(path===`/api/tasks/${c.id}`)return route.fulfill({json:{id:c.id,project_id:project,name:c.name,source:c.source,target:'VERTICA',source_config:{sources:[]},target_config:{},nodes:[],logs:[]}});
  if(path.endsWith('/runs'))return route.fulfill({json:{runs:[run(c)]}});
  if(path.match(/\/runs\/[^/]+$/))return route.fulfill({json:run(c)});
  if(path.endsWith('/specifications'))return route.fulfill({json:{items:[{specification_id:'s1',version:1,spec_json:spec,content_checksum:'c'.repeat(64),approval_id:'a1',approval_effective:true,reviewable:true,bound_naming:null}]}});
  if(path.endsWith('/comparisons')||path.endsWith('/oracles'))return route.fulfill({json:{items:[]}});
  if(path.endsWith('/sa-authorization'))return route.fulfill({json:{eligible:false,dispatch_enabled:true,authorization:{policy_version:'copilot-cli-once-v1'}}});
  if(path.endsWith('/sa-approval'))return route.fulfill({json:{status:'APPROVED_CURRENT',developer_authorized:false}});
  if(path.endsWith('/qa-approval'))return route.fulfill({json:{status:'APPROVED_CURRENT',approval:{approval_id:'qa-approval'},binding:{checksum:'d'.repeat(64)}}});
  if(path.endsWith('/sa-invocation'))return route.fulfill({json:{invocation:{status:'VALIDATED_NOT_APPROVED',invocation_id:'sa',provider:'LOCAL_COPILOT',model:'copilot/gpt-5.4',context_checksum:'e'.repeat(64),usage:{},review:{status:'READY_FOR_REVIEW',summary:'可交接',evidence_ids:[],issues:[]}},matches_current:true}});
  if(path.endsWith('/developer'))return route.fulfill({json:{invocation:{status:'VALIDATED_NOT_APPROVED',model:'copilot/gpt-5.4',usage:{}},eligible:false,dispatch_enabled:true,matches_current:true}});
  if(path.endsWith('/qa-review'))return route.fulfill({json:{matches_current:true,invocation:{invocation_id:'qa',status:'VALIDATED_NOT_APPROVED',prompt_version:'v',model:'copilot/gpt-5.4',created_at:'2026-10-10T13:50:19Z',usage:{},review:{status:'PASS',summary:'證據完整',issues:[]},context:{evidence:[],specification_checksum:'c'.repeat(64)},context_checksum:'f'.repeat(64)}}});
  if(path.endsWith('/qa-authorization'))return route.fulfill({json:{eligible:false,dispatch_enabled:true,invocation:{invocation_id:'qa',status:'VALIDATED_NOT_APPROVED'}}});
  if(path.endsWith('/artifacts'))return route.fulfill({json:{status:'NO_AUTHORIZED_COMPILER_ARTIFACTS'}});
  if(path.endsWith('/hop-dispatch'))return route.fulfill({json:{request:{status:'COMPLETED',outcome_code:'HOP_EXECUTED_QA_REQUIRED'},offer:null,dispatch_enabled:true}});
  if(path.endsWith('/release'))return route.fulfill({json:{status:'RELEASE_READY',release_ready:true,candidate:{candidate_id:'cand',checksum:'9'.repeat(64)},portability:{status:'PASS'},release:{release_id:'rel',checksum:'8'.repeat(64),file_size:10452,
   documents:[{name:'pipeline.hpl',type:'HPL',checksum:'1'.repeat(64),size_bytes:100},{name:'release-manifest.json',type:'MANIFEST',checksum:'2'.repeat(64),size_bytes:50}]}}});
  if(path.endsWith('/sdm-candidates'))return route.fulfill({json:{items:[{sdm_id:'11111111-2222-4333-8444-555555555555',status:'CANDIDATE_NOT_RELEASED',release_ready:false,created_at:'2026-10-10',file_size:1,checksum:'7'.repeat(64),specification_checksum:'c'.repeat(64)}],release_ready:false}});
  if(path.endsWith('/naming-contract'))return route.fulfill({json:{contract:null}});
  if(path.endsWith('/workers'))return route.fulfill({json:{workers:[]}});
  return route.fulfill({json:{}});
 });
 return writes;
}
const writeButton=/^(授權|核准|確認|建立|保存|產生|取消未執行|補正|以此規格|編輯修正版|取得來源命名|修改並建立|新增)/;

test('專案摘要、篩選與 Task 卡片一致；已交付不再顯示待補正（合成 API）',async({page})=>{
 const writes=await fixture(page);await page.goto(`/#/projects/${project}/history`);
 const summary=page.getByRole('region',{name:'專案進度摘要'});
 await expect(summary).toContainText('共 3 個 Task');await expect(summary.locator('dl').first()).toContainText('可交付3');
 await expect(summary.getByText('等待檢閱或補正')).toHaveCount(0);
 const history=page.getByRole('region',{name:'專案歷史 Task'});
 await expect(history.locator('.wb-history-row')).toHaveCount(3);
 for(const c of cases)await expect(history.locator('.wb-history-row',{hasText:c.name})).toContainText('可交付 · 已正式交付');
 await expect(history).not.toContainText('需修正');await expect(history).not.toContainText('待補正');
 const options=await page.getByLabel('篩選 Task 狀態').locator('option').allTextContents();
 expect(options).toEqual(['全部狀態','可交付（3）']);
 await page.getByLabel('篩選 Task 狀態').selectOption('可交付');await expect(history.locator('.wb-history-row')).toHaveCount(3);
 await history.getByRole('button',{name:'查看 Join 已交付'}).click();
 await expect(page).toHaveURL(new RegExp(`/tasks/TASK-DELIVERED-JOIN/delivery/${cases[2].run}`));
 expect(writes).toEqual([]);
});

test('摘要讀取失敗顯示待確認，不當成零筆或完成（合成 API）',async({page})=>{
 await fixture(page,{summaryFails:true});await page.goto(`/#/projects/${project}/history`);
 const history=page.getByRole('region',{name:'專案歷史 Task'});
 await expect(history.locator('.wb-history-row')).toHaveCount(3);
 const options=await page.getByLabel('篩選 Task 狀態').locator('option').allTextContents();
 expect(options).toEqual(['全部狀態','待確認（3）']);
 await expect(page.getByRole('region',{name:'專案進度摘要'}).getByRole('alert')).toBeVisible();
 // Cards still re-read their own Task workflow instead of guessing.
 await expect(history.locator('.wb-history-row',{hasText:'CSV 已交付'})).toContainText('可交付');
});

for(const c of cases)test(`${c.name}：七階段顯示已完成，原 Run 沒有可用修改操作（合成 API）`,async({page})=>{
 const writes=await fixture(page);const base=`/#/projects/${project}/tasks/${c.id}`;
 await page.goto(`${base}/requirements/${c.run}`);
 const next=page.getByRole('region',{name:'目前狀態與下一步'});
 await expect(next).toContainText('目前查看：第 1 階段（需求與資料規格）');
 await expect(next).toContainText('目前有效狀態：已正式交付');
 await expect(page.getByText('Hop 執行完成，仍待 QA 驗證')).toHaveCount(0);
 const req=page.getByLabel('需求摘要');
 for(const title of ['來源','轉換','目標','預期結果'])await expect(req.getByRole('heading',{name:title,exact:true})).toBeVisible();
 // Full input record is collapsed; opening it shows the immutable execution record beside the current status.
 await page.getByText('查看完整輸入、版本操作與控制紀錄').click();
 await expect(page.getByRole('status',{name:'執行結果與目前狀態'})).toContainText('目前有效狀態：已正式交付');
 await expect(page.getByRole('button',{name:'建立準備版本'})).toHaveCount(0);
 // Delivered versions state the limitation instead of pointing at a revision path that does not exist.
 await expect(page.getByRole('note',{name:'已交付版本限制'})).toContainText('目前不能直接從已交付版本建立修正版');
 await expect(page.getByRole('button',{name:/修正版/})).toHaveCount(0);
 for(const key of keys){
  await page.getByRole('tab',{name:new RegExp(`${keys.indexOf(key)+1} ·`)}).click();
  await expect(page).toHaveURL(new RegExp(`/${key}/${c.run}`));
  await expect(page.getByRole('tab',{name:new RegExp(`${keys.indexOf(key)+1} ·`)})).toContainText('已完成');
  await page.waitForLoadState('networkidle');
  const enabled=await page.locator('main button:enabled').allTextContents();
  expect(enabled.filter(name=>writeButton.test(name.trim())),key).toEqual([]);
  await expect(page.locator('main input[type=checkbox]:enabled')).toHaveCount(0);
 }
 await page.getByRole('tab',{name:/6 · 品質審查/}).click();
 await expect(page.getByLabel('品質審查摘要')).toContainText('已核准（目前有效）');
 await expect(page.getByLabel('品質審查摘要')).toContainText('通過');
 await page.getByText('查看歷次 QA 模型紀錄與核准詳情').click();
 await expect(page.getByRole('region',{name:'QA 審查紀錄'})).toContainText('目前有效狀態：人工 QA 已核准，已正式交付');
 await expect(page.getByRole('region',{name:'QA 審查紀錄'})).not.toContainText('尚未核准');
 await expect(page.getByRole('button',{name:'核准此版本 QA'})).toHaveCount(0);
 await page.getByRole('tab',{name:/3 · 流程設計/}).click();
 await expect(page.getByRole('button',{name:'建立規格'})).toHaveCount(0);
 await page.getByRole('tab',{name:/7 · 成果交付/}).click();
 await expect(next.getByRole('button',{name:/前往成果交付/})).toHaveCount(0);
 const final=page.getByRole('region',{name:'正式交付成果'});
 await expect(final.getByRole('link',{name:'下載正式 Release ZIP'})).toBeVisible();
 await expect(final).toContainText('pipeline.hpl');await expect(final).toContainText('release-manifest.json');
 await expect(page.getByRole('button',{name:/產生／取得 QA 關聯 SDM/})).toBeHidden();
 await expect(page.getByRole('button',{name:/重新核對交付條件|重新核對 Release|載入／重新整理 SDM 歷史/})).toHaveCount(0);
 await expect(next).not.toContainText('JSON');
 expect(writes).toEqual([]);
});

for(const width of [390,768,1440])test(`${width}px 已交付頁面精簡：無橫向溢出、無 console error（合成 API）`,async({page})=>{
 const errors:string[]=[];page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('ERR_TUNNEL_CONNECTION_FAILED'))errors.push(m.text())});page.on('pageerror',e=>errors.push(e.message));
 await fixture(page);await page.setViewportSize({width,height:1000});
 const c=cases[2],base=`/#/projects/${project}/tasks/${c.id}`;const heights:Record<string,number>={};
 for(const key of keys){
  await page.goto(`${base}/${key}/${c.run}`);await expect(page.getByRole('region',{name:'目前狀態與下一步'})).toBeVisible();await page.waitForLoadState('networkidle');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),key).toBe(true);
  heights[key]=await page.evaluate(()=>document.documentElement.scrollHeight);
  await page.screenshot({path:test.info().outputPath(`delivered-${key}-${width}.png`),fullPage:true});
 }
 test.info().annotations.push({type:'page-heights',description:JSON.stringify(heights)});
 console.log(`HEIGHTS ${width} ${JSON.stringify(heights)}`);
 expect(heights.requirements).toBeLessThan(width<=390?3200:2200);
 expect(errors).toEqual([]);
 await page.goto(`/#/projects/${project}`);await expect(page).toHaveURL(new RegExp(`/projects/${project}$`));
 await expect(page.getByRole('region',{name:'專案歷史 Task'})).toBeVisible();
 await page.screenshot({path:test.info().outputPath(`project-worklist-${width}.png`),fullPage:true});
});

test.describe('實機手機版面（isMobile）',()=>{
 test.use({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
 test('手機以裝置寬度排版，不退回 980px 桌面寬度（合成 API）',async({page})=>{
  await fixture(page);const c=cases[2];
  await page.goto(`/#/projects/${project}/tasks/${c.id}/requirements/${c.run}`);await expect(page.getByRole('region',{name:'目前狀態與下一步'})).toBeVisible();
  expect(await page.evaluate(()=>innerWidth)).toBe(390);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  await expect(page.getByRole('button',{name:/目前查看：第 1 階段/})).toBeVisible();
 });
});
