// Three fresh, explicitly authorized synthetic acceptance Tasks on 5197 only.
// Website writes only; inspect persisted state after an unclear response, never resend.
const {chromium,expect}=require('../frontend/node_modules/@playwright/test');
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),origin='http://127.0.0.1:5197';
const project='346e9419-4b0e-4ba7-ad29-1756ca7da833';
const output=path.join(root,'runtime-temp/v2-followup-live-state.json');
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
const definitions=[
 {key:'csv',files:['filter.csv'],target:'ui_accept_csv_20261011_v2',
  requirement:'讀取已上傳 category、amount CSV。amount > 100，NULL 不通過；按 category 分組，SUM(amount) 為 sum_amount，COUNT_ROWS 為 row_count。輸出 category、sum_amount、row_count。全部資料，APPEND 至全新測試表。CSV UTF-8、逗號、第一列欄名，多餘欄位 REJECT；空欄位為 SQL NULL，不 trim，轉換錯誤及超長值 FAIL。所有目標欄位允許 NULL。固定答案在執行前另行確認，不從實際結果反推。'},
 {key:'excel',files:['filter.xlsx'],target:'ui_accept_excel_20261011_v2',
  requirement:'讀取已上傳 Excel「明細」工作表，第 2 列為欄名，整列空白 SKIP，空 amount 為 SQL NULL，拒絕公式與多餘欄位，不 trim，錯誤及超長值 FAIL。amount > 100，NULL 不通過；按 category 分組，SUM(amount) 為 sum_amount，COUNT_ROWS 為 row_count。輸出 category、sum_amount、row_count。全部資料，APPEND 至全新測試表，所有目標欄位允許 NULL。固定答案在執行前另行確認。'},
 {key:'join',files:['left.csv','right.csv'],target:'ui_accept_join_20261011_v2',
  requirement:'左表四列、右表三列，依左 id = 右 id 做 LEFT JOIN。NULL 鍵 NEVER_MATCH，重複鍵 EXPAND，CASE_SENSITIVE_NO_TRIM。輸出 source.0.id → id、source.0.left_value → left_value、source.1.id → id_2、source.1.right_value → right_value；兩個 id BIGINT，字串型別沿用已上傳來源型別，目標四欄均 nullable。空 id 為 SQL NULL，不是文字 NULL 或 0；空字串為 NULL，不 trim，轉換錯誤及超長值 FAIL。CSV UTF-8、逗號、第一列欄名，多餘欄位 REJECT。全部資料，APPEND 新測試表。固定答案共五列，保留未匹配及 NULL 左列，執行前另行核准。'}
];
const expected=fs.readFileSync(path.join(root,'examples/ui-acceptance/expected.json'));
const state=fs.existsSync(output)?JSON.parse(fs.readFileSync(output,'utf8')):
 {project_id:project,source_commit:'a7a666f',expected_sha256:digest(expected),cases:{},actions:[],errors:[]};
if(state.project_id!==project||state.expected_sha256!==digest(expected))throw Error('ACCEPTANCE_BINDING_CHANGED');
const persist=()=>fs.writeFileSync(output,JSON.stringify(state,null,2));
const get=async p=>{const r=await fetch(origin+'/api'+p);if(!r.ok)throw Error('GET_'+r.status);return r.json()};
async function main(){
 const phase=process.argv[2],key=process.argv[3];
 if(!['create','prepare','input','revise','sa','sa-fix','sa-approve','naming','developer','spec','oracle','hop','qa','qa-approve','sdm','candidate','release','inspect'].includes(phase))throw Error('UNKNOWN_PHASE');
 if(key&&!definitions.some(c=>c.key===key))throw Error('UNKNOWN_CASE');
 const ready=await get('/ready');if(ready.status!=='ready'||ready.execution_enabled!==true)throw Error('ACCEPTANCE_NOT_READY');
 const p=await get('/projects/'+project);if(p.default_ai_profile!=='ui-accept-native')throw Error('NATIVE_PROFILE_REQUIRED');
 const browser=await chromium.launch({headless:true}),page=await browser.newPage();page.setDefaultTimeout(15000);
 const taskPage=async(item,stage='requirements')=>{
  await page.goto(origin+'/#/projects/'+project+'/tasks/'+item.task_id+'/'+stage+(item.run_id?'/'+item.run_id:''));
  await expect(page.locator('.workflow-heading small')).toContainText(item.task_id);
 };
 page.on('pageerror',()=>{state.errors.push({type:'PAGE_ERROR'});persist()});
 page.on('response',r=>{if(r.url().startsWith(origin+'/api/')&&r.request().method()!=='GET'){
  state.actions.push({path:new URL(r.url()).pathname,method:r.request().method(),status:r.status(),at:new Date().toISOString()});persist();
 }});
 try{for(const c of definitions.filter(c=>!key||c.key===key)){
  const name='v2 20261011 '+c.key.toUpperCase()+' 真實驗收';
  let item=state.cases[c.key];
  if(phase==='create'){
   if(item?.task_id){console.log(c.key+' ALREADY_CREATED '+item.task_id);continue}
   const tasks=await get('/projects/'+project+'/tasks');
   const existing=tasks.filter(t=>t.name===name);
   if(existing.length)throw Error('TASK_EXISTS_READ_BACK_BEFORE_ANY_RESUBMIT');
   state.cases[c.key]={key:c.key,name,target:'ai_sample.'+c.target,source_files:c.files.map(f=>({name:f,sha256:digest(fs.readFileSync(path.join(root,'examples/ui-acceptance',f)))})),creation_attempted:true};persist();
   await page.goto(origin+'/#/projects/'+project+'/tasks/new');
   if(c.key==='join')await page.getByRole('button',{name:'雙 CSV Join',exact:true}).click();
   await page.getByRole('textbox',{name:'Task 名稱',exact:true}).fill(name);
   await page.getByRole('textbox',{name:'需求描述',exact:true}).fill(c.requirement);
   if(c.key==='join'){
    await page.getByLabel('左側 CSV',{exact:true}).setInputFiles(path.join(root,'examples/ui-acceptance/left.csv'));
    await expect(page.getByText('left.csv · 2 欄')).toBeVisible();
    await page.getByLabel('右側 CSV',{exact:true}).setInputFiles(path.join(root,'examples/ui-acceptance/right.csv'));
    await expect(page.getByText('right.csv · 2 欄')).toBeVisible();
    await page.getByLabel('Join 類型',{exact:true}).selectOption('LEFT');
    await page.getByLabel('左側鍵值',{exact:true}).selectOption('id');
    await page.getByLabel('右側鍵值',{exact:true}).selectOption('id');
    await page.getByRole('checkbox',{name:'我已確認左右來源、檔案格式、Join 類型、鍵值與上述三項規則',exact:true}).check();
   }else{
    const uploaded=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/task-sources/upload'&&r.request().method()==='POST');
    await page.locator('input[type="file"]:visible').setInputFiles(path.join(root,'examples/ui-acceptance',c.files[0]));
    if(!(await uploaded).ok())throw Error('UPLOAD_FAILED');
    if(c.key==='excel'){
     const selection=page.getByRole('region',{name:'Excel 工作表與標頭確認',exact:true});
     await selection.getByLabel('Excel 工作表').selectOption('明細');
     await selection.getByLabel('Excel 標頭列',{exact:true}).fill('2');
     await selection.getByRole('button',{name:'解析並確認此工作表',exact:true}).click();
     await expect(selection.getByRole('status')).toContainText('第 2 列標頭');
    }
   }
   await page.getByRole('textbox',{name:'Vertica Schema',exact:true}).fill('ai_sample');
   await page.getByRole('textbox',{name:'Vertica Table',exact:true}).fill(c.target);
   const saved=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/tasks')&&r.request().method()==='POST');
   await page.getByRole('button',{name:c.key==='join'?'建立雙 CSV Task':'建立 Task',exact:true}).click();
   const reply=await saved;if(reply.status()!==201)throw Error('TASK_CREATE_'+reply.status());
   const task=await reply.json();if(task.project_id!==project)throw Error('PROJECT_MISMATCH');
   Object.assign(state.cases[c.key],{task_id:task.id,created_at:new Date().toISOString()});persist();
   // Wait for the website's completed creation transition before opening the next form.
   await expect(page).toHaveURL(new RegExp('/tasks/'+task.id+'(?:/|$)'));
   console.log(c.key+' CREATED '+task.id);continue;
  }
  if(!item?.task_id)throw Error('CREATE_CASE_FIRST');
  const task=await get('/tasks/'+item.task_id);
  if(task.project_id!==project||task.name!==name)throw Error('TASK_BINDING_MISMATCH');
  const runs=(await get('/tasks/'+item.task_id+'/runs')).runs;
  if(phase==='prepare'){
   if(runs.length){if(item.run_id!==runs[0].run_id)throw Error('RUN_EXISTS_READ_BACK_BEFORE_RESUBMIT');console.log(c.key+' ALREADY_PREPARED');continue}
   await taskPage(item);
   const [r]=await Promise.all([
    page.waitForResponse(r=>new URL(r.url()).pathname==='/api/tasks/'+item.task_id+'/runs'&&r.request().method()==='POST'),
    page.getByRole('button',{name:'建立準備版本',exact:true}).click()
   ]);if(!r.ok())throw Error('PREPARE_'+r.status());
   item.run_id=(await r.json()).run_id;persist();console.log(c.key+' PREPARED '+item.run_id);continue;
  }
  if(!item.run_id||runs[0]?.run_id!==item.run_id)throw Error('LATEST_RUN_CHANGED');
  const detail=await get('/tasks/'+item.task_id+'/runs/'+item.run_id);
  if(detail.input_summary.target_schema!=='ai_sample'||detail.input_summary.target_table!==c.target)throw Error('TARGET_MISMATCH');
  if(phase==='revise'){
   if(item.contracts_confirmed){console.log(c.key+' ALREADY_REVISED');continue}
   if(detail.write_started||detail.state!=='NEEDS_REVIEW'||detail.phase!=='REQUIREMENT_GATE')throw Error('REVISION_NOT_ELIGIBLE');
   await taskPage(item);
   const show=page.getByText('查看完整輸入、版本操作與控制紀錄',{exact:true});
   if(await show.isVisible())await show.click();
   await page.locator('[data-revision-start]').click();
   const form=page.getByRole('form',{name:'需求補正',exact:true});
   await form.locator('[data-field="write_mode"]').selectOption('APPEND');
   await form.locator('[data-field="date_scope"]').selectOption('ALL');
   if(c.key!=='join'){
    if(c.key==='csv'){
     await form.getByRole('button',{name:'設定 CSV 輸入契約',exact:true}).click();
     for(const [name,value] of [['CSV 編碼','UTF-8'],['CSV 分隔符號',','],['CSV 標題列','true'],['CSV 額外欄位','REJECT']])await form.getByLabel(name).selectOption(value);
    }else{
     await form.getByRole('button',{name:'設定 Excel 讀取契約',exact:true}).click();
     await form.getByLabel('Excel 空白列處理').selectOption('SKIP');
    }
    await form.getByRole('button',{name:'新增轉換意圖',exact:true}).click();
    await form.getByRole('button',{name:'新增篩選',exact:true}).click();
    for(const [name,value] of [['篩選欄位 1','source.0.amount'],['比較方式 1','GT'],['常數型別 1','DECIMAL']])await form.getByLabel(name).selectOption(value);
    await form.getByLabel('常數值 1',{exact:true}).fill('100');
    await form.getByLabel('聚合方式').selectOption('GROUP');
    await form.getByRole('checkbox',{name:'source.0.category',exact:true}).check();
    for(const [i,id,fn] of [[1,'sum_amount','SUM'],[2,'row_count','COUNT_ROWS']]){
     await form.getByRole('button',{name:'新增聚合指標',exact:true}).click();
     await form.getByLabel('指標識別 '+i,{exact:true}).fill(id);
     await form.getByLabel('聚合函數 '+i).selectOption(fn);
     if(fn==='SUM')await form.getByLabel('聚合來源 '+i).selectOption('source.0.amount');
    }
    for(const [i,col] of [[1,'source.0.category'],[2,'$metric.sum_amount'],[3,'$metric.row_count']]){
     await form.getByRole('button',{name:'新增輸出欄位',exact:true}).click();
     await form.getByLabel('輸出欄位 '+i).selectOption(col);
    }
   }
   await form.getByRole('button',{name:'預覽修訂差異',exact:true}).click();
   await form.getByRole('checkbox',{name:'已核對差異，同意建立待需求確認的新版',exact:true}).check();
   const [saved]=await Promise.all([
    page.waitForResponse(r=>new URL(r.url()).pathname==='/api/tasks/'+item.task_id+'/runs/'+item.run_id+'/revisions'&&r.request().method()==='POST'),
    form.getByRole('button',{name:'保存補正並建立新版',exact:true}).click()
   ]);if(!saved.ok())throw Error('REVISION_'+saved.status());
   const child=await saved.json();
   if(child.approval||child.write_started||child.parent_run_id!==item.run_id)throw Error('REVISION_STATE_INVALID');
   (item.retained_runs??=[]).push(item.run_id);item.run_id=child.run_id;item.contracts_confirmed=true;persist();
   console.log(c.key+' REVISED '+item.run_id);
  }else if(phase==='sa-fix'){
   if(c.key!=='csv'||detail.write_started)throw Error('SA_FIX_OUTSIDE_SCOPE');
   const review=(await get('/tasks/'+item.task_id+'/runs/'+item.run_id+'/sa-invocation')).invocation?.review;
   if(review?.status!=='NEEDS_INPUT')throw Error('SA_FIX_NOT_REQUIRED');
   await taskPage(item);
   const show=page.getByText('查看完整輸入、版本操作與控制紀錄',{exact:true});
   if(await show.isVisible())await show.click();
   await page.locator('[data-revision-start]').click();
   const form=page.getByRole('form',{name:'需求補正',exact:true});
   await form.locator('[data-field="requirement_text"]').fill(detail.input_summary.requirement_text+
    ' 明確目的表契約：category VARCHAR(32) nullable、sum_amount NUMERIC(24,4) nullable、row_count BIGINT nullable。由受控 Hop Worker 依後續已核准規格與 DDL 新建全新目的表，再 APPEND 一次；目的表已存在即停止，不使用已存在表、不 DROP 或 TRUNCATE。SUM 不降精度、不截斷，COUNT_ROWS 計算通過篩選的所有列。');
   await form.getByRole('button',{name:'預覽修訂差異',exact:true}).click();
   await form.getByRole('checkbox',{name:'已核對差異，同意建立待需求確認的新版',exact:true}).check();
   const [saved]=await Promise.all([
    page.waitForResponse(r=>new URL(r.url()).pathname==='/api/tasks/'+item.task_id+'/runs/'+item.run_id+'/revisions'&&r.request().method()==='POST'),
    form.getByRole('button',{name:'保存補正並建立新版',exact:true}).click()
   ]);if(!saved.ok())throw Error('SA_REVISION_'+saved.status());
   const child=await saved.json();if(child.approval||child.write_started||child.parent_run_id!==item.run_id)throw Error('SA_REVISION_INVALID');
   item.retained_runs.push(item.run_id);item.run_id=child.run_id;persist();console.log(c.key+' SA_FIXED_NEW_RUN '+item.run_id);
  }else if(phase==='sa'){
   if(detail.gate_result?.status!=='CHECKED'||!detail.approval||detail.write_started)throw Error('SA_PREREQUISITES_MISSING');
   const base='/tasks/'+item.task_id+'/runs/'+item.run_id;
   const prior=(await get(base+'/sa-invocation')).invocation;
   if(prior){console.log(c.key+' EXISTING_SA '+prior.status);continue}
   const offer=await get(base+'/sa-authorization');
   if(!offer.eligible||!offer.dispatch_enabled)throw Error('SA_NOT_ELIGIBLE');
   await taskPage(item,'review');
   await page.getByRole('checkbox',{name:'我同意此版本的 SA 模型呼叫及上述用量限制',exact:true}).check();
   const [saved]=await Promise.all([
    page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+base+'/sa-authorization'&&r.request().method()==='POST'),
    page.getByRole('button',{name:'授權並排入 SA 工作',exact:true}).click()
   ]);if(!saved.ok())throw Error('SA_AUTHORIZE_'+saved.status());
   item.sa_invocation_id=(await get(base+'/sa-invocation')).invocation?.invocation_id;persist();
   console.log(c.key+' SA_AUTHORIZED');
  }else if(phase==='sa-approve'){
   const base='/tasks/'+item.task_id+'/runs/'+item.run_id;
   const inv=(await get(base+'/sa-invocation')).invocation;
   if(inv?.status!=='VALIDATED_NOT_APPROVED'||inv.review?.status!=='READY_FOR_REVIEW')throw Error('SA_NOT_READY');
   const prior=await get(base+'/sa-approval');
   if(prior.status==='APPROVED_CURRENT'){console.log(c.key+' SA_ALREADY_APPROVED');continue}
   if(prior.status!=='AWAITING_CONFIRMATION')throw Error('SA_APPROVAL_NOT_ELIGIBLE');
   await taskPage(item,'review');
   await page.getByRole('checkbox',{name:'我已檢視 SA 建議與原需求，確認此版本可交給 Developer',exact:true}).check();
   const [saved]=await Promise.all([
    page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+base+'/sa-approval'&&r.request().method()==='POST'),
    page.getByRole('button',{name:'確認 SA 建議並交接',exact:true}).click()
   ]);if(!saved.ok())throw Error('SA_APPROVAL_'+saved.status());
   if((await get(base+'/sa-approval')).status!=='APPROVED_CURRENT')throw Error('SA_APPROVAL_READBACK');
   item.sa_invocation_id=inv.invocation_id;persist();console.log(c.key+' SA_APPROVED');
  }else if(phase==='naming'){
   const base='/tasks/'+item.task_id+'/runs/'+item.run_id;
   if((await get(base+'/sa-approval')).status!=='APPROVED_CURRENT')throw Error('NAMING_SA_REQUIRED');
   if((await get(base+'/developer')).invocation)throw Error('NAMING_DEVELOPER_ALREADY_DISPATCHED');
   const prior=await get('/tasks/'+item.task_id+'/naming-contract');
   if(prior.contract?.status==='CONFIRMED'){item.naming_contract=prior.contract;persist();console.log(c.key+' NAMING_ALREADY_CONFIRMED');continue}
   await taskPage(item,'design');
   const section=page.getByRole('region',{name:'欄位命名確認',exact:true});
   const edit=section.getByRole('button',{name:'修改並建立命名新版',exact:true});
   if(await edit.count())await edit.click();
   await section.getByLabel('命名來源 1',{exact:true}).waitFor();
   if(c.key!=='join')for(const [i,src,name,type] of [[3,'$metric.sum_amount','sum_amount','NUMERIC(24,4)'],[4,'$metric.row_count','row_count','BIGINT']]){
    if(!await section.getByLabel('命名來源 '+i,{exact:true}).count())await section.getByRole('button',{name:'新增聚合輸出命名',exact:true}).click();
    await section.getByLabel('命名來源 '+i,{exact:true}).fill(src);
    await section.getByLabel('命名英文 '+i,{exact:true}).fill(name);
    await section.getByLabel('命名型別 '+i,{exact:true}).fill(type);
   }
   else{
    await section.getByLabel('命名英文 3',{exact:true}).fill('id_2');
   }
   await section.getByRole('checkbox',{name:'我已核對原名、英文名稱與型別',exact:true}).check();
   const [saved]=await Promise.all([
    page.waitForResponse(r=>new URL(r.url()).pathname==='/api/tasks/'+item.task_id+'/naming-contract/confirm'&&r.request().method()==='POST'),
    section.getByRole('button',{name:'確認並保存命名版本',exact:true}).click()
   ]);if(!saved.ok())throw Error('NAMING_'+saved.status());
   item.naming_contract=(await get('/tasks/'+item.task_id+'/naming-contract')).contract;persist();console.log(c.key+' NAMING_CONFIRMED');
  }else if(phase==='developer'){
   const base='/tasks/'+item.task_id+'/runs/'+item.run_id;
   const offer=await get(base+'/developer');
   if(offer.invocation){console.log(c.key+' EXISTING_DEVELOPER '+offer.invocation.status);continue}
   if(!offer.eligible)throw Error('DEVELOPER_NOT_ELIGIBLE');
   await taskPage(item,'design');
   await page.getByRole('checkbox',{name:'我同意此版本的 Developer 單次模型呼叫與用量',exact:true}).check();
   const [saved]=await Promise.all([
    page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+base+'/developer/authorize'&&r.request().method()==='POST'),
    page.getByRole('button',{name:'授權 Developer 設計',exact:true}).click()
   ]);if(!saved.ok())throw Error('DEVELOPER_AUTHORIZE_'+saved.status());
   item.developer_invocation_id=(await get(base+'/developer')).invocation?.invocation_id;persist();console.log(c.key+' DEVELOPER_AUTHORIZED');
  }else if(phase==='spec'){
   const base='/tasks/'+item.task_id+'/runs/'+item.run_id;
   const dev=(await get(base+'/developer')).invocation;
   if(dev?.status!=='VALIDATED_NOT_APPROVED')throw Error('DEVELOPER_NOT_VALIDATED');
   const s=(await get(base+'/specifications')).items[0],doc=s?.spec_json;
   if(!s?.is_current||!s.reviewable||doc.run_id!==item.run_id||doc.target_schema!=='ai_sample'||doc.target_table!==c.target||doc.write_mode!=='APPEND')throw Error('SPEC_BINDING_MISMATCH');
   if(c.key==='join'){
    if(doc.joins?.length!==1||doc.joins[0].join_type!=='LEFT'||doc.joins[0].null_key_policy!=='NEVER_MATCH'||doc.joins[0].duplicate_key_policy!=='EXPAND'||doc.output_columns.join()!=='id,left_value,id_2,right_value')throw Error('JOIN_SPEC_MISMATCH');
   }else if(doc.filters?.length!==1||doc.filters[0].column!=='amount'||doc.filters[0].operator!=='GT'||String(doc.filters[0].constant.value)!=='100'||doc.filter_null_policy!=='EXCLUDE_UNKNOWN'||doc.aggregation.group_by.join()!=='category'||doc.aggregation.null_policy!=='SQL_NULLS'||doc.aggregation.metrics.map(m=>m.function).join()!=='SUM,COUNT_ROWS'||doc.output_columns.join()!=='category,sum_amount,row_count')throw Error('AGGREGATION_SPEC_MISMATCH');
   if(s.approval_effective){item.specification_id=s.specification_id;persist();console.log(c.key+' SPEC_ALREADY_APPROVED');continue}
   await taskPage(item,'design');
   await page.getByRole('checkbox',{name:/我已檢查來源.*確認此規格/}).check();
   const [saved]=await Promise.all([
    page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+base+'/specifications/'+s.specification_id+'/approve'&&r.request().method()==='POST'),
    page.getByRole('button',{name:'核准此版規格',exact:true}).click()
   ]);if(!saved.ok())throw Error('SPEC_APPROVAL_'+saved.status());
   if(!(await get(base+'/specifications')).items[0].approval_effective)throw Error('SPEC_APPROVAL_READBACK');
   item.specification_id=s.specification_id;persist();console.log(c.key+' SPEC_APPROVED');
  }else if(phase==='oracle'){
   const base='/tasks/'+item.task_id+'/runs/'+item.run_id;
   const s=(await get(base+'/specifications')).items[0];if(!s?.approval_effective)throw Error('ORACLE_SPEC_REQUIRED');
   const ob=base+'/specifications/'+s.specification_id;
   const history=await get(ob+'/oracles');if(history.items.length)throw Error('ORACLE_EXISTS_READBACK_REQUIRED');
   const fixed=JSON.parse(expected);
   const rows=c.key==='join'?fixed.join.rows.map(r=>({id:r.left_id,left_value:r.left_value,id_2:r.right_id,right_value:r.right_value})):fixed.csv_and_excel.rows.map(r=>({category:r.category,sum_amount:r.sum_amount,row_count:r.count_rows}));
   await taskPage(item,'confirm');const editor=page.getByRole('region',{name:'標準答案輸入',exact:true});
   await editor.getByRole('button',{name:'新增答案資料列',exact:true}).waitFor();
   if(c.key==='join')for(const col of ['id','id_2','right_value'])await editor.getByRole('checkbox',{name:new RegExp('^'+col+'（')}).check();
   for(let i=0;i<rows.length;i++){
    await editor.getByRole('button',{name:'新增答案資料列',exact:true}).click();
    for(const [col,val] of Object.entries(rows[i])){
     const label=`第 ${i+1} 筆 ${col}`;
     if(val===null)await editor.getByRole('checkbox',{name:label+' NULL',exact:true}).check();
     else await editor.getByLabel(label,{exact:true}).fill(String(val));
    }
   }
   const [saved]=await Promise.all([
    page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+ob+'/oracles'&&r.request().method()==='POST'),
    editor.getByRole('button',{name:'保存答案版本',exact:true}).click()
   ]);if(!saved.ok())throw Error('ORACLE_SAVE_'+saved.status());
   const oracle=await saved.json();item.oracle_id=oracle.oracle_id;item.oracle_checksum=oracle.document_checksum;persist();
   await editor.getByRole('checkbox',{name:'我已確認上方答案內容與版本，核准供後續 QA 比對',exact:true}).check();
   const [approval]=await Promise.all([
    page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+ob+'/oracles/'+oracle.oracle_id+'/approve'&&r.request().method()==='POST'),
    editor.getByRole('button',{name:'核准此答案版本',exact:true}).click()
   ]);if(!approval.ok())throw Error('ORACLE_APPROVE_'+approval.status());
   const current=(await get(ob+'/oracles')).items[0];
   if(current.oracle_id!==oracle.oracle_id||current.document_checksum!==oracle.document_checksum||!current.approval_recorded)throw Error('ORACLE_APPROVAL_READBACK');
   item.fixed_rows=rows;persist();console.log(c.key+' FIXED_ORACLE_APPROVED');
  }else if(phase==='hop'){
   const base='/tasks/'+item.task_id+'/runs/'+item.run_id;
   const d=await get(base+'/hop-dispatch');
   if(d.request){console.log(c.key+' EXISTING_HOP '+d.request.status);continue}
   if(!d.offer||!item.oracle_id||!item.fixed_rows)throw Error('HOP_PREREQUISITES_MISSING');
   const preflight=JSON.parse(fs.readFileSync(path.join(root,'runtime-temp/v2-followup-target-preflight.json'),'utf8')).find(v=>v.key===c.key);
   if(preflight?.task_id!==item.task_id||preflight.run_id!==item.run_id||preflight.target!==item.target||preflight.table_exists!==false||preflight.write_started!==false)throw Error('FRESH_TARGET_PREFLIGHT_REQUIRED');
   const s=(await get(base+'/specifications')).items[0];
   if(!s?.approval_effective||s.specification_id!==item.specification_id||s.spec_json.target_table!==c.target||s.spec_json.write_mode!=='APPEND')throw Error('HOP_TARGET_BINDING_CHANGED');
   await taskPage(item,'confirm');
   await page.getByRole('checkbox',{name:'我已核對規格、標準答案及 DDL，同意新建此測試表並執行一次 Hop 寫入；失敗不自動重跑',exact:true}).check();
   const [saved]=await Promise.all([
    page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+base+'/hop-dispatch'&&r.request().method()==='POST'),
    page.getByRole('button',{name:'授權並排入 Hop 執行',exact:true}).click()
   ]);if(!saved.ok())throw Error('HOP_AUTHORIZE_'+saved.status());
   item.hop_request_id=(await get(base+'/hop-dispatch')).request?.request_id;persist();console.log(c.key+' HOP_AUTHORIZED');
  }else if(phase==='qa'){
   const base='/tasks/'+item.task_id+'/runs/'+item.run_id;
   const d=await get(base+'/qa-authorization');
   if(d.invocation){console.log(c.key+' EXISTING_QA '+d.invocation.status);continue}
   if(!d.eligible)throw Error('QA_NOT_ELIGIBLE');
   const proof=JSON.parse(fs.readFileSync(path.join(root,'docs/verification/v2-followup-native-readback-2026-10-11.json'),'utf8')).cases.find(v=>v.key===c.key);
   if(proof?.run_id!==item.run_id||!proof.independent_fixed_multiset_match||proof.write_started_count!==1)throw Error('INDEPENDENT_RESULT_CHECK_REQUIRED');
   await taskPage(item,'quality');
   await page.getByRole('checkbox',{name:'我同意此版本 QA 單次模型呼叫與用量',exact:true}).check();
   const [saved]=await Promise.all([
    page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+base+'/qa-authorization'&&r.request().method()==='POST'),
    page.getByRole('button',{name:'授權 QA 證據審查',exact:true}).click()
   ]);if(!saved.ok())throw Error('QA_AUTHORIZE_'+saved.status());
   item.qa_invocation_id=(await get(base+'/qa-review')).invocation?.invocation_id;persist();console.log(c.key+' QA_AUTHORIZED');
  }else if(phase==='qa-approve'){
   const base='/tasks/'+item.task_id+'/runs/'+item.run_id;
   const d=await get(base+'/qa-approval');
   if(d.status==='APPROVED_CURRENT'){console.log(c.key+' QA_ALREADY_APPROVED');continue}
   if(d.status!=='AWAITING_CONFIRMATION')throw Error('QA_NOT_PASS_'+d.status);
   await taskPage(item,'quality');
   await page.getByRole('checkbox',{name:'我已檢視本 Run 的規格、執行與 QA 證據，確認此版本',exact:true}).check();
   const [saved]=await Promise.all([
    page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+base+'/qa-approval'&&r.request().method()==='POST'),
    page.getByRole('button',{name:'核准此版本 QA',exact:true}).click()
   ]);if(!saved.ok())throw Error('QA_APPROVE_'+saved.status());
   if((await get(base+'/qa-approval')).status!=='APPROVED_CURRENT')throw Error('QA_APPROVAL_READBACK');
   console.log(c.key+' QA_APPROVED');
  }else if(phase==='sdm'){
   const base='/tasks/'+item.task_id+'/runs/'+item.run_id;
   if((await get(base+'/qa-approval')).status!=='APPROVED_CURRENT')throw Error('SDM_QA_REQUIRED');
   const d=await get(base+'/release');if(d.candidate||d.release_ready)throw Error('SDM_ALREADY_BOUND_READBACK_REQUIRED');
   await taskPage(item,'delivery');
   const [saved]=await Promise.all([
    page.waitForResponse(r=>new URL(r.url()).pathname.startsWith('/api'+base+'/sdm')&&r.request().method()==='POST'),
    page.getByRole('button',{name:'產生／取得 QA 關聯 SDM',exact:true}).click()
   ]);if(!saved.ok())throw Error('SDM_SAVE_'+saved.status());
   item.sdm=await saved.json();persist();console.log(c.key+' SDM_SAVED');
  }else if(phase==='candidate'||phase==='release'){
   const base='/tasks/'+item.task_id+'/runs/'+item.run_id;
   const d=await get(base+'/release');
   if(phase==='candidate'&&d.candidate){console.log(c.key+' EXISTING_CANDIDATE '+d.status);continue}
   if(phase==='release'&&d.release_ready){console.log(c.key+' EXISTING_RELEASE '+d.status);continue}
   if(phase==='candidate'&&d.status!=='SDM_AND_CANDIDATE_REQUIRED')throw Error('CANDIDATE_NOT_ELIGIBLE');
   if(phase==='release'&&(d.status!=='AWAITING_RELEASE_APPROVAL'||d.portability?.status!=='PASS'))throw Error('PORTABILITY_NOT_PASS');
   if(phase==='release'){
    const proof=JSON.parse(fs.readFileSync(path.join(root,'docs/verification/v2-followup-portability-2026-10-11.json'),'utf8')).cases.find(v=>v.key===c.key);
    if(proof?.run_id!==item.run_id||proof.status!=='PASS'||!proof.original_destination_separate||proof.independent_isolated_read.status!=='MATCH'||!proof.workflow.workflow_completed)throw Error('INDEPENDENT_PORTABLE_READBACK_REQUIRED');
   }
   await taskPage(item,'delivery');
   await page.getByRole('checkbox',{name:phase==='candidate'?'確認建立候選包並要求一次隔離可攜驗證':'確認此版本的 QA、SDM、候選包與可攜驗證證據，同意正式交付',exact:true}).check();
   const [saved]=await Promise.all([
    page.waitForResponse(r=>new URL(r.url()).pathname==='/api'+base+'/release/'+(phase==='candidate'?'candidate':'approve')&&r.request().method()==='POST'),
    page.getByRole('button',{name:phase==='candidate'?'保存候選 ZIP 並要求驗證':'核准並保存正式 Release',exact:true}).click()
   ]);if(!saved.ok())throw Error('RELEASE_'+phase+'_'+saved.status());
   item[phase]=await saved.json();persist();console.log(c.key+' '+phase.toUpperCase()+'_SAVED');
  }else if(phase==='input'){
   if(detail.approval){console.log(c.key+' ALREADY_CONFIRMED');continue}
   await taskPage(item);
   await page.getByLabel('我已核對本次需求及設定版本',{exact:true}).check();
   const [saved]=await Promise.all([
    page.waitForResponse(r=>new URL(r.url()).pathname==='/api/tasks/'+item.task_id+'/approvals'&&r.request().method()==='POST'),
    page.getByRole('button',{name:'確認此版輸入',exact:true}).click()
   ]);
   if(!saved.ok())throw Error('INPUT_CONFIRM_FAILED');console.log(c.key+' INPUT_CONFIRMED');
  }else console.log(JSON.stringify({case:c.key,task:item.task_id,run:item.run_id,state:detail.state,outcome:detail.outcome_code,gate:detail.gate_result?.status,issues:detail.gate_result?.issues,write_started:detail.write_started}));
 }}catch(error){
  state.errors.push({type:'STOPPED_FOR_READBACK',phase,key:key||null,url:page.url()});persist();
  await page.screenshot({path:path.join(root,'runtime-temp/v2-followup-live-stopped.png'),fullPage:true}).catch(()=>{});
  throw error;
 }finally{persist();await browser.close()}
}
main().catch(e=>{console.error(e.message);process.exitCode=1});
