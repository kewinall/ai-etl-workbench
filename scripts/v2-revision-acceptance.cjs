// Explicitly authorized new revision case only. Website writes; no model or Hop retries.
const {chromium,expect}=require('../frontend/node_modules/@playwright/test');
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),origin='http://127.0.0.1:5197',project='346e9419-4b0e-4ba7-ad29-1756ca7da833';
const source=Buffer.from('record_key,label\nA,alpha\nB,beta\n');
const checksum=crypto.createHash('sha256').update(source).digest('hex');
const output=path.join(root,'runtime-temp/v2-revision-live-state.json');
const name='v2 20261011 失敗修正版實際驗收';let target='ui_accept_revision_20261011_v1';
const requirement='讀取上傳的 record_key、label CSV，全部資料原值輸出，無篩選、無 Join、無聚合。輸出 record_key、label，型別沿用已上傳來源；所有目標欄位允許 NULL。CSV UTF-8、逗號、第一列欄名，多餘欄位 REJECT，空欄位為 SQL NULL，不 trim，轉換錯誤及超長值 FAIL。APPEND 到全新 ai_sample 測試表。事前固定答案兩筆：A/alpha、B/beta。此獨立案例已授權在新空目標注入受控缺欄位錯誤一次，保存失敗與0筆證據；結案後只使用新的 v2 目標，不重試 v1。';
const state=fs.existsSync(output)?JSON.parse(fs.readFileSync(output,'utf8').replace(/^\uFEFF/,'')):{project_id:project,name,target,source_sha256:checksum,expected_rows:[{record_key:'A',label:'alpha'},{record_key:'B',label:'beta'}],actions:[],errors:[]};
if(state.project_id!==project||state.source_sha256!==checksum||state.name!==name)throw Error('CASE_BINDING_CHANGED');
if(!['ui_accept_revision_20261011_v1','ui_accept_revision_20261011_v2'].includes(state.target))throw Error('TARGET_OUT_OF_SCOPE');
target=state.target;
const persist=()=>fs.writeFileSync(output,JSON.stringify(state,null,2));
const get=async p=>{const r=await fetch(origin+'/api'+p);if(!r.ok)throw Error('GET_'+r.status);return r.json()};
async function main(){
 const phase=process.argv[2];
 if(!['create','recover-create','prepare','input','revise','sa-fix','failed-revision','sa','sa-approve','naming','developer','spec','oracle','hop','close','qa','qa-approve','sdm','candidate','release','inspect'].includes(phase))throw Error('UNKNOWN_PHASE');
 if(process.env.WORKBENCH_REVISION_ACCEPTANCE!=='authorized-v2-revision-20261011')throw Error('EXPLICIT_CASE_AUTHORIZATION_REQUIRED');
 const p=await get('/projects/'+project),ready=await get('/ready');
 if(p.default_ai_profile!=='ui-accept-native'||ready.status!=='ready'||ready.execution_enabled!==true)throw Error('ACCEPTANCE_NOT_READY');
 const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:768,height:1000}});
 page.setDefaultTimeout(15000);
 page.on('response',r=>{if(r.url().startsWith(origin+'/api/')&&r.request().method()!=='GET'){state.actions.push({method:r.request().method(),path:new URL(r.url()).pathname,status:r.status(),at:new Date().toISOString()});persist()}});
 try{
  if(phase==='recover-create'){
   const matches=(await get('/projects/'+project+'/tasks')).filter(t=>t.name===name);
   if(matches.length!==1)throw Error('CREATION_NOT_UNAMBIGUOUS');
   const task=await get('/tasks/'+matches[0].id),sources=task.source_config?.sources;
   if(task.project_id!==project||task.target_config?.schema!=='ai_sample'||task.target_config?.table!==target
       ||sources?.length!==1||sources[0].checksum!==checksum
       ||(task.requirement??task.requirement_text)!==requirement)throw Error('CREATION_BINDING_NOT_CONFIRMED');
   state.task_id=task.id;state.creation_recovered_by_get=true;persist();
   console.log('RECOVERED_WITHOUT_POST '+task.id);return;
  }
  if(phase==='create'){
   if(state.task_id){console.log('EXISTING_TASK '+state.task_id);return}
   const matches=(await get('/projects/'+project+'/tasks')).filter(t=>t.name===name);
   if(matches.length||state.creation_attempted)throw Error('READ_SERVER_CREATION_STATE_BEFORE_RESUBMIT');
   state.creation_attempted=true;persist();
   await page.goto(origin+'/#/projects/'+project+'/tasks/new');
   await page.getByRole('textbox',{name:'Task 名稱',exact:true}).fill(name);
   await page.getByRole('textbox',{name:'需求描述',exact:true}).fill(requirement);
   const uploaded=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/task-sources/upload'&&r.request().method()==='POST');
   await page.locator('input[type="file"]:visible').setInputFiles({name:'ui-accept-revision.csv',mimeType:'text/csv',buffer:source});
   const upload=await uploaded;if(!upload.ok())throw Error('UPLOAD_FAILED');
   const profile=await upload.json();if(profile.checksum!==checksum)throw Error('SOURCE_CHECKSUM_CHANGED');
   state.upload_id=profile.upload_id;persist();
   await page.getByRole('textbox',{name:'Vertica Schema',exact:true}).fill('ai_sample');
   await page.getByRole('textbox',{name:'Vertica Table',exact:true}).fill(target);
   const [saved]=await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api/tasks'&&r.request().method()==='POST'),page.getByRole('button',{name:'建立 Task',exact:true}).click()]);
   if(saved.status()!==201)throw Error('TASK_CREATE_'+saved.status());
   const task=await saved.json();if(task.project_id!==project)throw Error('PROJECT_MISMATCH');
   state.task_id=task.id;persist();
   await expect(page).toHaveURL(new RegExp('/tasks/'+task.id+'(?:/|$)'));
   console.log('CREATED '+task.id);return;
  }
  if(!state.task_id)throw Error('CREATE_FIRST');
  const task=await get('/tasks/'+state.task_id);
  if(task.project_id!==project||task.name!==name||task.target_config.table!==target)throw Error('TASK_BINDING_CHANGED');
  const base='/tasks/'+state.task_id,runs=(await get(base+'/runs')).runs;
  await page.goto(origin+'/#/projects/'+project+base+'/requirements'+(state.run_id?'/'+state.run_id:''));
  if(phase==='prepare'){
   if(runs.length)throw Error('READ_EXISTING_RUN_BEFORE_RESUBMIT');
   const [saved]=await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+base+'/runs'&&r.request().method()==='POST'),page.getByRole('button',{name:'建立準備版本',exact:true}).click()]);
   if(!saved.ok())throw Error('PREPARE_'+saved.status());state.run_id=(await saved.json()).run_id;persist();console.log('PREPARED '+state.run_id);return;
  }
  if(!state.run_id||runs[0]?.run_id!==state.run_id)throw Error('CURRENT_RUN_CHANGED');
  const run=await get(base+'/runs/'+state.run_id);
  const rb=base+'/runs/'+state.run_id;
  if(phase==='spec'){
   const dev=(await get(rb+'/developer')).invocation,s=(await get(rb+'/specifications')).items[0],doc=s?.spec_json;
   if(dev?.status!=='VALIDATED_NOT_APPROVED'||!s?.is_current||!s.reviewable||doc.run_id!==state.run_id
       ||doc.target_schema!=='ai_sample'||doc.target_table!==target||doc.write_mode!=='APPEND'
       ||doc.filters?.length!==0||doc.aggregation!==null||(doc.joins?.length??0)!==0
       ||doc.output_columns.join()!=='record_key,label')throw Error('SPEC_BINDING_CHANGED');
   if(s.approval_effective){state.specification_id=s.specification_id;persist();console.log('SPEC_ALREADY_APPROVED');return}
   await page.goto(origin+'/#/projects/'+project+base+'/design/'+state.run_id);
   await page.getByRole('checkbox',{name:/我已檢查來源.*確認此規格/}).check();
   const [saved]=await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+rb+'/specifications/'+s.specification_id+'/approve'&&r.request().method()==='POST'),page.getByRole('button',{name:'核准此版規格',exact:true}).click()]);
   if(!saved.ok()||!(await get(rb+'/specifications')).items[0].approval_effective)throw Error('SPEC_APPROVAL_NOT_CONFIRMED');
   state.specification_id=s.specification_id;persist();console.log('SPEC_APPROVED');return;
  }
  if(phase==='oracle'){
   const s=(await get(rb+'/specifications')).items[0];
   if(!s?.approval_effective||s.specification_id!==state.specification_id)throw Error('ORACLE_SPEC_REQUIRED');
   const ob=rb+'/specifications/'+s.specification_id,history=await get(ob+'/oracles');
   if(history.items.length)throw Error('READ_EXISTING_ORACLE_BEFORE_RESUBMIT');
   const rows=[{record_key:'A',label:'alpha'},{record_key:'B',label:'beta'}];
   if(JSON.stringify(rows)!==JSON.stringify(state.expected_rows))throw Error('FIXED_ANSWER_CHANGED');
   await page.goto(origin+'/#/projects/'+project+base+'/confirm/'+state.run_id);
   const editor=page.getByRole('region',{name:'標準答案輸入',exact:true});
   for(let i=0;i<rows.length;i++){
    await editor.getByRole('button',{name:'新增答案資料列',exact:true}).click();
    for(const [col,value] of Object.entries(rows[i]))await editor.getByLabel('第 '+(i+1)+' 筆 '+col,{exact:true}).fill(value);
   }
   const [saved]=await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+ob+'/oracles'&&r.request().method()==='POST'),editor.getByRole('button',{name:'保存答案版本',exact:true}).click()]);
   if(!saved.ok())throw Error('ORACLE_SAVE_'+saved.status());
   const answer=await saved.json();state.oracle_id=answer.oracle_id;state.oracle_checksum=answer.document_checksum;persist();
   await editor.getByRole('checkbox',{name:'我已確認上方答案內容與版本，核准供後續 QA 比對',exact:true}).check();
   const [approved]=await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+ob+'/oracles/'+answer.oracle_id+'/approve'&&r.request().method()==='POST'),editor.getByRole('button',{name:'核准此答案版本',exact:true}).click()]);
   if(!approved.ok())throw Error('ORACLE_APPROVAL_'+approved.status());
   const current=(await get(ob+'/oracles')).items[0];
   if(current.oracle_id!==answer.oracle_id||current.document_checksum!==answer.document_checksum||!current.approval_recorded)throw Error('ORACLE_APPROVAL_NOT_CONFIRMED');
   state.oracle_approved=true;persist();console.log('FIXED_ORACLE_APPROVED');return;
  }
  if(['qa','qa-approve','sdm','candidate','release'].includes(phase)){
   if(target!=='ui_accept_revision_20261011_v2')throw Error('FAILED_VERSION_CANNOT_DELIVER');
   if(phase==='qa'){
    const prior=await get(rb+'/qa-authorization');
    if(prior.invocation){console.log('EXISTING_QA '+prior.invocation.status);return}
    const proof=JSON.parse(fs.readFileSync(path.join(root,'runtime-temp/v2-revision-native-readback.json'),'utf8'));
    if(!prior.eligible||proof.run_id!==state.run_id||proof.status!=='PASS'||!proof.independent_fixed_multiset_match||proof.write_started_count!==1)throw Error('NATIVE_READBACK_REQUIRED');
    await page.goto(origin+'/#/projects/'+project+base+'/quality/'+state.run_id);
    await page.getByRole('checkbox',{name:'我同意此版本 QA 單次模型呼叫與用量',exact:true}).check();
    const [saved]=await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+rb+'/qa-authorization'&&r.request().method()==='POST'),page.getByRole('button',{name:'授權 QA 證據審查',exact:true}).click()]);
    if(!saved.ok())throw Error('QA_AUTHORIZE_'+saved.status());console.log('QA_AUTHORIZED');return;
   }
   if(phase==='qa-approve'){
    const prior=await get(rb+'/qa-approval');if(prior.status==='APPROVED_CURRENT'){console.log('QA_ALREADY_APPROVED');return}
    if(prior.status!=='AWAITING_CONFIRMATION')throw Error('QA_NOT_PASS');
    await page.goto(origin+'/#/projects/'+project+base+'/quality/'+state.run_id);
    await page.getByRole('checkbox',{name:'我已檢視本 Run 的規格、執行與 QA 證據，確認此版本',exact:true}).check();
    const [saved]=await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+rb+'/qa-approval'&&r.request().method()==='POST'),page.getByRole('button',{name:'核准此版本 QA',exact:true}).click()]);
    if(!saved.ok()||(await get(rb+'/qa-approval')).status!=='APPROVED_CURRENT')throw Error('QA_APPROVAL_NOT_CONFIRMED');console.log('QA_APPROVED');return;
   }
   const delivery=await get(rb+'/release');
   if(phase==='sdm'){
    if((await get(rb+'/qa-approval')).status!=='APPROVED_CURRENT')throw Error('SDM_QA_REQUIRED');
    if(delivery.candidate||delivery.release_ready||state.sdm){console.log('EXISTING_SDM_OR_DELIVERY');return}
    await page.goto(origin+'/#/projects/'+project+base+'/delivery/'+state.run_id);
    const [saved]=await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname.startsWith('/api'+rb+'/sdm')&&r.request().method()==='POST'),page.getByRole('button',{name:'產生／取得 QA 關聯 SDM',exact:true}).click()]);
    if(!saved.ok())throw Error('SDM_'+saved.status());state.sdm=await saved.json();persist();console.log('SDM_SAVED');return;
   }
   if(phase==='candidate'&&delivery.candidate||phase==='release'&&delivery.release_ready){console.log('EXISTING_DELIVERY '+delivery.status);return}
   if(phase==='candidate'&&delivery.status!=='SDM_AND_CANDIDATE_REQUIRED')throw Error('CANDIDATE_NOT_ELIGIBLE');
   if(phase==='release'){
    const proof=JSON.parse(fs.readFileSync(path.join(root,'runtime-temp/v2-revision-portable-readback.json'),'utf8'));
    if(delivery.status!=='AWAITING_RELEASE_APPROVAL'||delivery.portability?.status!=='PASS'||proof.run_id!==state.run_id||proof.status!=='PASS'||!proof.original_destination_separate||proof.independent_isolated_read?.status!=='MATCH')throw Error('PORTABLE_READBACK_REQUIRED');
   }
   await page.goto(origin+'/#/projects/'+project+base+'/delivery/'+state.run_id);
   await page.getByRole('checkbox',{name:phase==='candidate'?'確認建立候選包並要求一次隔離可攜驗證':'確認此版本的 QA、SDM、候選包與可攜驗證證據，同意正式交付',exact:true}).check();
   const [saved]=await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+rb+'/release/'+(phase==='candidate'?'candidate':'approve')&&r.request().method()==='POST'),page.getByRole('button',{name:phase==='candidate'?'保存候選 ZIP 並要求驗證':'核准並保存正式 Release',exact:true}).click()]);
   if(!saved.ok())throw Error('DELIVERY_'+saved.status());state[phase]=await saved.json();persist();console.log(phase.toUpperCase()+'_SAVED');return;
  }
  if(phase==='close'){
   const proof=JSON.parse(fs.readFileSync(path.join(root,'runtime-temp/v2-revision-failure-readback.json'),'utf8'));
   if(proof.task_id!==state.task_id||proof.run_id!==state.run_id||proof.status!=='PASS'||proof.write_started_count!==1||proof.engine_stopped!==true||proof.independent_select?.observed_row_count!==0||run.outcome_code!=='HOP_EXECUTION_FAILED')throw Error('FAILURE_READBACK_REQUIRED');
   const prior=await get(rb+'/reconciliation');
   if(prior.status==='CLOSED_WITHOUT_RETRY'){console.log('ALREADY_CLOSED');return}
   if(prior.status!=='AWAITING_RECONCILIATION')throw Error('CLOSURE_NOT_ELIGIBLE');
   await page.goto(origin+'/#/projects/'+project+base+'/results/'+state.run_id);
   const panel=page.getByRole('region',{name:'執行結果人工核對',exact:true});
   await panel.getByLabel('核對時目標筆數',{exact:true}).fill('0');
   await panel.getByRole('checkbox',{name:'我已確認本次執行停止，目標核對結果正確，同意結案並保留原結果',exact:true}).check();
   const [saved]=await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+rb+'/reconciliation'&&r.request().method()==='POST'),panel.getByRole('button',{name:'確認結案，保留結果',exact:true}).click()]);
   if(!saved.ok()||(await get(rb+'/reconciliation')).status!=='CLOSED_WITHOUT_RETRY')throw Error('CLOSURE_NOT_CONFIRMED');
   state.failure_closed=true;persist();console.log('FAILED_RUN_CLOSED_WITHOUT_RETRY');return;
  }
  if(phase==='hop'){
   const dispatch=await get(rb+'/hop-dispatch');
   if(dispatch.request){console.log('EXISTING_HOP '+dispatch.request.status);return}
   const preflight=JSON.parse(fs.readFileSync(path.join(root,'runtime-temp/v2-revision-target-preflight.json'),'utf8'));
   const fresh=preflight.targets?.find(t=>t.target==='ai_sample.'+target);
   if(preflight.task_id!==state.task_id||preflight.run_id!==state.run_id||preflight.target!==target||preflight.status!=='PASS'||preflight.source_sha256!==checksum||preflight.write_started!==false||fresh?.exists!==false||!state.oracle_approved||run.write_started)throw Error('HOP_PREFLIGHT_BINDING_CHANGED');
   if(!dispatch.offer||dispatch.offer.binding_checksum!==state.hop_binding_checksum||dispatch.offer.target_table!==target||dispatch.offer.specification_id!==state.specification_id)throw Error('HOP_OFFER_CHANGED');
   await page.goto(origin+'/#/projects/'+project+base+'/confirm/'+state.run_id);
   await page.getByRole('checkbox',{name:'我已核對規格、標準答案及 DDL，同意新建此測試表並執行一次 Hop 寫入；失敗不自動重跑',exact:true}).check();
   const [saved]=await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+rb+'/hop-dispatch'&&r.request().method()==='POST'),page.getByRole('button',{name:'授權並排入 Hop 執行',exact:true}).click()]);
   if(!saved.ok())throw Error('HOP_AUTHORIZE_'+saved.status());
   state.hop_request_id=(await get(rb+'/hop-dispatch')).request?.request_id;persist();console.log('HOP_AUTHORIZED');return;
  }
  if(phase==='sa-approve'){
   const record=(await get(rb+'/sa-invocation')).invocation,approval=await get(rb+'/sa-approval');
   if(approval.status==='APPROVED_CURRENT'){console.log('SA_ALREADY_APPROVED');return}
   if(record?.status!=='VALIDATED_NOT_APPROVED'||record.review?.status!=='READY_FOR_REVIEW'||approval.status!=='AWAITING_CONFIRMATION')throw Error('SA_NOT_REVIEW_READY');
   await page.goto(origin+'/#/projects/'+project+base+'/review/'+state.run_id);
   await page.getByRole('checkbox',{name:'我已檢視 SA 建議與原需求，確認此版本可交給 Developer',exact:true}).check();
   const [saved]=await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+rb+'/sa-approval'&&r.request().method()==='POST'),page.getByRole('button',{name:'確認 SA 建議並交接',exact:true}).click()]);
   if(!saved.ok()||(await get(rb+'/sa-approval')).status!=='APPROVED_CURRENT')throw Error('SA_APPROVAL_NOT_CONFIRMED');
   console.log('SA_APPROVED');return;
  }
  if(phase==='naming'){
   if((await get(rb+'/sa-approval')).status!=='APPROVED_CURRENT'||(await get(rb+'/developer')).invocation)throw Error('NAMING_NOT_ELIGIBLE');
   const prior=(await get(base+'/naming-contract')).contract;
   if(prior?.status==='CONFIRMED'){
    if(prior.contract_json?.columns?.map(c=>c.english_name).join()!=='record_key,label')throw Error('NAMING_BINDING_CHANGED');
    state.naming_contract_id=prior.contract_id;persist();console.log('NAMING_ALREADY_CONFIRMED');return;
   }
   await page.goto(origin+'/#/projects/'+project+base+'/design/'+state.run_id);
   const panel=page.getByRole('region',{name:'欄位命名確認',exact:true}),edit=panel.getByRole('button',{name:'修改並建立命名新版',exact:true});
   if(await edit.count())await edit.click();
   for(const [i,value] of [[1,'record_key'],[2,'label']])await panel.getByLabel('命名英文 '+i,{exact:true}).fill(value);
   await panel.getByRole('checkbox',{name:'我已核對原名、英文名稱與型別',exact:true}).check();
   const [saved]=await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+base+'/naming-contract/confirm'&&r.request().method()==='POST'),panel.getByRole('button',{name:'確認並保存命名版本',exact:true}).click()]);
   if(!saved.ok())throw Error('NAMING_'+saved.status());
   const contract=(await get(base+'/naming-contract')).contract;
   if(contract.status!=='CONFIRMED'||contract.contract_json?.columns?.map(c=>c.english_name).join()!=='record_key,label')throw Error('NAMING_NOT_CONFIRMED');
   state.naming_contract_id=contract.contract_id;persist();console.log('NAMING_CONFIRMED');return;
  }
  if(phase==='developer'){
   const offer=await get(rb+'/developer');
   if(offer.invocation){console.log('EXISTING_DEVELOPER '+offer.invocation.status);return}
   if(!offer.eligible)throw Error('DEVELOPER_NOT_ELIGIBLE');
   await page.goto(origin+'/#/projects/'+project+base+'/design/'+state.run_id);
   await page.getByRole('checkbox',{name:'我同意此版本的 Developer 單次模型呼叫與用量',exact:true}).check();
   const [saved]=await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+rb+'/developer/authorize'&&r.request().method()==='POST'),page.getByRole('button',{name:'授權 Developer 設計',exact:true}).click()]);
   if(!saved.ok())throw Error('DEVELOPER_AUTHORIZE_'+saved.status());
   state.developer_invocation_id=(await get(rb+'/developer')).invocation?.invocation_id;persist();console.log('DEVELOPER_AUTHORIZED');return;
  }
  if(phase==='revise'||phase==='sa-fix'||phase==='failed-revision'){
   if(phase==='failed-revision'){
    if(target!=='ui_accept_revision_20261011_v1'||!run.failed_revision_available||!state.failure_closed||!run.write_started)throw Error('FAILED_REVISION_NOT_ELIGIBLE');
   }else if(run.write_started||run.state!=='NEEDS_REVIEW'||run.phase!=='REQUIREMENT_GATE')throw Error('REVISION_NOT_ELIGIBLE');
   if(phase==='sa-fix'&&(await get(base+'/runs/'+state.run_id+'/sa-invocation')).invocation?.review?.status!=='NEEDS_INPUT')throw Error('SA_FIX_NOT_REQUIRED');
   const show=page.getByText('查看完整輸入、版本操作與控制紀錄',{exact:true});
   if(await show.isVisible())await show.click();
   await page.locator('[data-revision-start]').click();
   const form=page.getByRole('form',{name:'需求補正',exact:true});
   if(phase==='failed-revision'){
    await form.locator('[data-field="requirement_text"]').fill(run.input_summary.requirement_text.replaceAll('ui_accept_revision_20261011_v1','ui_accept_revision_20261011_v2'));
    await form.locator('[data-field="target_table"]').fill('ui_accept_revision_20261011_v2');
   }else if(phase==='sa-fix'){
    await form.locator('[data-field="requirement_text"]').fill('讀取上傳的 record_key、label CSV，全部資料原值輸出，無篩選、無 Join、無聚合。輸出 record_key、label，型別沿用已上傳來源；所有目標欄位允許 NULL。CSV UTF-8、逗號、第一列欄名，多餘欄位 REJECT，空欄位為 SQL NULL，不 trim，轉換錯誤及超長值 FAIL。此 Run 只 APPEND 到全新 ai_sample.ui_accept_revision_20261011_v1。事前固定答案兩筆：record_key=A、label=alpha；record_key=B、label=beta。');
   }else{
    await form.locator('[data-field="write_mode"]').selectOption('APPEND');
    await form.locator('[data-field="date_scope"]').selectOption('ALL');
    await form.getByRole('button',{name:'設定 CSV 輸入契約',exact:true}).click();
    for(const [name,value] of [['CSV 編碼','UTF-8'],['CSV 分隔符號',','],['CSV 標題列','true'],['CSV 額外欄位','REJECT']])await form.getByLabel(name).selectOption(value);
   }
   await form.getByRole('button',{name:'預覽修訂差異',exact:true}).click();
   await form.getByRole('checkbox',{name:'已核對差異，同意建立待需求確認的新版',exact:true}).check();
   const [saved]=await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+base+'/runs/'+state.run_id+'/revisions'&&r.request().method()==='POST'),form.getByRole('button',{name:'保存補正並建立新版',exact:true}).click()]);
   if(!saved.ok())throw Error('REVISION_'+saved.status());
   const child=await saved.json();if(child.parent_run_id!==state.run_id||child.approval||child.write_started)throw Error('REVISION_BINDING_INVALID');
   (state.retained_runs??=[]).push(state.run_id);
   if(phase==='failed-revision'){
    state.failed_execution={run_id:state.run_id,target,hop_request_id:state.hop_request_id,specification_id:state.specification_id,oracle_id:state.oracle_id,log_checksum:JSON.parse(fs.readFileSync(path.join(root,'runtime-temp/v2-revision-failure-readback.json'),'utf8')).log_checksum};
    state.target='ui_accept_revision_20261011_v2';
    for(const key of ['sa_invocation_id','developer_invocation_id','specification_id','oracle_id','oracle_checksum','oracle_approved','hop_binding_checksum','hop_request_id'])delete state[key];
   }
   state.run_id=child.run_id;persist();console.log('REVISED '+state.run_id);return;
  }
  if(phase==='sa'){
   if(run.gate_result?.status!=='CHECKED'||!run.approval||run.write_started)throw Error('SA_PREREQUISITES_MISSING');
   const rb=base+'/runs/'+state.run_id,record=(await get(rb+'/sa-invocation')).invocation;
   if(record){console.log('EXISTING_SA '+record.status);return}
   const offer=await get(rb+'/sa-authorization');if(!offer.eligible||!offer.dispatch_enabled)throw Error('SA_NOT_ELIGIBLE');
   await page.goto(origin+'/#/projects/'+project+base+'/review/'+state.run_id);
   await page.getByRole('checkbox',{name:'我同意此版本的 SA 模型呼叫及上述用量限制',exact:true}).check();
   const [saved]=await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+rb+'/sa-authorization'&&r.request().method()==='POST'),page.getByRole('button',{name:'授權並排入 SA 工作',exact:true}).click()]);
   if(!saved.ok())throw Error('SA_AUTHORIZE_'+saved.status());
   state.sa_invocation_id=(await get(rb+'/sa-invocation')).invocation?.invocation_id;persist();console.log('SA_AUTHORIZED');return;
  }
  if(phase==='input'){
   if(run.approval){console.log('ALREADY_CONFIRMED');return}
   await page.getByLabel('我已核對本次需求及設定版本',{exact:true}).check();
   const [saved]=await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+base+'/approvals'&&r.request().method()==='POST'),page.getByRole('button',{name:'確認此版輸入',exact:true}).click()]);
   if(!saved.ok())throw Error('INPUT_'+saved.status());console.log('INPUT_CONFIRMED');return;
  }
  console.log(JSON.stringify({task_id:state.task_id,run_id:state.run_id,state:run.state,gate:run.gate_result?.status,issues:run.gate_result?.issues,write_started:run.write_started}));
 }catch(error){state.errors.push({phase,url:page.url(),code:'STOPPED_FOR_READBACK'});persist();await page.screenshot({path:path.join(root,'runtime-temp/v2-revision-stopped.png'),fullPage:true}).catch(()=>{});throw error}
 finally{persist();await browser.close()}
}
main().catch(e=>{console.error(e.message);process.exitCode=1});
