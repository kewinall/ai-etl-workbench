// Explicit user authorization: automatically complete the three isolated 5197 cases.
// All writes use existing website controls; failures stop for server-state inspection.
const {chromium}=require('../frontend/node_modules/@playwright/test');
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..'),manifest=JSON.parse(fs.readFileSync(path.join(root,'docs/verification/ui-acceptance-cases-2026-10-10.json'),'utf8'));
const project=manifest.project_id,origin='http://127.0.0.1:5197';
if(project!=='346e9419-4b0e-4ba7-ad29-1756ca7da833'||manifest.cases.some(c=>!['TASK-20261010-0017','TASK-20261010-0018','TASK-20261010-0019'].includes(c.task_id)))throw Error('FIXED_ACCEPTANCE_SCOPE_REQUIRED');
const output=path.join(root,'runtime-temp/ui-accept-auto-state.json');
const state=fs.existsSync(output)?JSON.parse(fs.readFileSync(output,'utf8')):{project_id:project,cases:{},actions:[],errors:[]};
const persist=()=>fs.writeFileSync(output,JSON.stringify(state,null,2));
async function get(url){const r=await fetch(origin+'/api'+url);if(!r.ok)throw Error('GET_STATUS_'+r.status);return r.json()}
async function main(){
 const browser=await chromium.launch({headless:true}),page=await browser.newPage();
 page.on('pageerror',e=>{state.errors.push({code:'PAGE_ERROR'});persist()});
 page.on('response',r=>{if(r.request().method()!=='GET'&&r.url().startsWith(origin+'/api/')){state.actions.push({url:r.url().slice(origin.length),method:r.request().method(),status:r.status(),at:new Date().toISOString()});persist()}});
 const button=n=>page.getByRole('button',{name:n,exact:true});
 const mutations=new Set(['確認此版輸入','授權並排入 SA 工作','確認 SA 建議並交接','確認並保存命名版本','授權 Developer 設計','核准此版規格','保存答案版本','核准此答案版本','授權並排入 Hop 執行','授權 QA 證據審查','核准此版本 QA','產生／取得 QA 關聯 SDM','保存候選 ZIP 並要求驗證','核准並保存正式 Release']);
 const click=async n=>{const response=mutations.has(n)?page.waitForResponse(r=>r.request().method()==='POST'&&r.url().startsWith(origin+'/api/')):null;await button(n).click({timeout:20000});if(response){const r=await response;await r.finished();if(!r.ok())throw Error('WRITE_RESPONSE_'+r.status());await page.waitForTimeout(250)}};
 const goto=async(c,stage)=>{await page.goto(`${origin}/#/projects/${project}/tasks/${c.task_id}/${stage}/${c.run_id}`);await page.waitForTimeout(1200);};
 const phase=process.argv[2],key=process.argv[3];
 try{for(const original of manifest.cases.filter(c=>!key||c.key===key)){
   const c={...original,...state.cases[original.key]},base=()=>`/tasks/${c.task_id}/runs/${c.run_id}`;
   let detail=await get(base(''));
   if(detail.run_id!==c.run_id||detail.input_summary.target_schema!=='ai_sample'||!/^ui_accept_(csv|excel|join)_20261010(?:_r[35])?$/.test(detail.input_summary.target_table))throw Error('FIXED_ACCEPTANCE_TARGET_REQUIRED');
   if(phase==='join-target-fix'){
     if(c.key!=='join'||!detail.qa_revision)throw Error('QA_REVISION_NOT_ELIGIBLE');
     await goto(c,'requirements');await page.locator('[data-revision-start]').click();
     await page.locator('[data-field="target_table"]').fill('ui_accept_join_20261010_r5');
     await page.locator('[data-field="requirement_text"]').fill(detail.input_summary.requirement_text.replace('left_value VARCHAR(32) not null','left_value VARCHAR(32) nullable')+' 本次目的表四欄均允許 NULL，與既有受支援編譯器 DDL 一致。固定五筆答案中 left_value 均非 NULL，但這不等同目的表 NOT NULL 約束。');
     await click('預覽修訂差異');await page.getByRole('checkbox',{name:'已核對差異，同意建立待需求確認的新版',exact:true}).check();
     const response=page.waitForResponse(r=>r.url().endsWith('/revisions')&&r.request().method()==='POST');await click('保存補正並建立新版');const r=await response;if(!r.ok())throw Error('REVISION_STATUS_'+r.status());const child=await r.json();state.cases[c.key]={...state.cases[c.key],run_id:child.run_id,parent_run_id:c.run_id,target:'ai_sample.ui_accept_join_20261010_r5'};persist();console.log('join QA_FIX_REVISION '+child.run_id);
   }else if(phase==='join-fix'){
     if(c.key!=='join')continue;
     await goto(c,'requirements');await page.locator('[data-revision-start]').click();
     await page.locator('[data-field="requirement_text"]').fill(detail.input_summary.requirement_text+' 明確目標契約與 mapping：source.0.id → id BIGINT nullable；source.0.left_value → left_value VARCHAR(32) not null；source.1.id → id_2 BIGINT nullable；source.1.right_value → right_value VARCHAR(32) nullable。CSV 的 BIGINT id 空欄位讀為 NULL；不是文字 NULL，也不是 0，NULL 鍵依 NEVER_MATCH 不匹配。左右字串不 trim，空字串讀為 NULL，超長或型別解析錯誤 FAIL，不截斷。');
     await click('預覽修訂差異');await page.getByRole('checkbox',{name:'已核對差異，同意建立待需求確認的新版',exact:true}).check();
     const response=page.waitForResponse(r=>r.url().endsWith('/revisions')&&r.request().method()==='POST');await click('保存補正並建立新版');const r=await response;if(!r.ok())throw Error('REVISION_STATUS_'+r.status());const child=await r.json();state.cases[c.key]={...state.cases[c.key],run_id:child.run_id,parent_run_id:c.run_id};persist();console.log('join SA_FIX_REVISION '+child.run_id);
   }else if(phase==='revise'){
     const runs=(await get(`/tasks/${c.task_id}/runs`)).runs;
     if(runs[0].run_id!==c.run_id)throw Error('LATEST_RUN_CHANGED_READ_BEFORE_MUTATION');
     if(c.key==='join'&&detail.input_summary.target_table==='ui_accept_join_20261010_r3'||c.key!=='join'&&detail.input_summary.transformation_contract_v1&&detail.input_summary.requirements_v1){console.log(c.key+' ALREADY_REVISED');continue}
     await goto(c,'requirements');await page.locator('[data-revision-start]').click();
     await page.locator('[data-field="write_mode"]').selectOption('APPEND');await page.locator('[data-field="date_scope"]').selectOption('ALL');
     if(c.key==='join')await page.locator('[data-field="target_table"]').fill('ui_accept_join_20261010_r3');
     else{
       if(c.key==='csv'){await click('設定 CSV 輸入契約');for(const [label,val] of [['CSV 編碼','UTF-8-SIG'],['CSV 分隔符號',','],['CSV 標題列','true'],['CSV 額外欄位','REJECT']])await page.getByLabel(label,{exact:false}).selectOption(val)}
       else{await click('設定 Excel 讀取契約');await page.getByLabel('Excel 空白列處理',{exact:false}).selectOption('SKIP')}
       await click('新增轉換意圖');await click('新增篩選');
       for(const [label,val] of [['篩選欄位 1','source.0.amount'],['比較方式 1','GT'],['常數型別 1','DECIMAL']])await page.getByLabel(label,{exact:false}).selectOption(val);
       await page.getByLabel('常數值 1',{exact:true}).fill('100');await page.getByLabel('聚合方式',{exact:false}).selectOption('GROUP');
       await page.getByRole('checkbox',{name:'source.0.category',exact:true}).check();
       for(const [i,id,fn] of [[1,'sum_amount','SUM'],[2,'row_count','COUNT_ROWS']]){await click('新增聚合指標');await page.getByLabel('指標識別 '+i,{exact:true}).fill(id);await page.getByLabel('聚合函數 '+i,{exact:true}).selectOption(fn);if(fn==='SUM')await page.getByLabel('聚合來源 '+i,{exact:true}).selectOption('source.0.amount')}
       for(const [i,col] of [[1,'source.0.category'],[2,'$metric.sum_amount'],[3,'$metric.row_count']]){await click('新增輸出欄位');await page.getByLabel('輸出欄位 '+i,{exact:true}).selectOption(col)}
     }
     await click('預覽修訂差異');await page.getByRole('checkbox',{name:'已核對差異，同意建立待需求確認的新版',exact:true}).check();
     const response=page.waitForResponse(r=>r.url().endsWith('/revisions')&&r.request().method()==='POST');await click('保存補正並建立新版');const r=await response;if(!r.ok())throw Error('REVISION_STATUS_'+r.status());const child=await r.json();c.run_id=child.run_id;
     state.cases[c.key]={task_id:c.task_id,run_id:c.run_id,parent_run_id:detail.run_id,target:c.key==='join'?'ai_sample.ui_accept_join_20261010_r3':c.target};persist();console.log(c.key+' REVISION_SAVED '+c.run_id);
   }else if(phase==='input'){
     if(!detail.approval){await goto(c,'requirements');await page.getByRole('checkbox',{name:'我已核對本次需求及設定版本',exact:true}).check();await click('確認此版輸入');}
     console.log(c.key+' INPUT '+(await get(base())).approval?.decision);
   }else if(phase==='sa'){
     const inv=(await get(base()+'/sa-invocation')).invocation;
     if(!inv){await goto(c,'review');await page.getByRole('checkbox',{name:'我同意此版本的 SA 模型呼叫及上述用量限制',exact:true}).check();await click('授權並排入 SA 工作')}
     console.log(c.key+' SA '+JSON.stringify((await get(base()+'/sa-invocation')).invocation?.status));
   }else if(phase==='sa-approve'){
     const inv=(await get(base()+'/sa-invocation')).invocation;
     if(!inv?.review||inv.review.status!=='READY_FOR_REVIEW')throw Error(c.key+' SA_NOT_READY '+JSON.stringify(inv?.review));
     const a=await get(base()+'/sa-approval');if(a.status!=='APPROVED_CURRENT'){await goto(c,'review');await page.getByRole('checkbox',{name:'我已檢視 SA 建議與原需求，確認此版本可交給 Developer',exact:true}).check();await click('確認 SA 建議並交接')}
     console.log(c.key+' SA_APPROVAL '+(await get(base()+'/sa-approval')).status);
   }else if(phase==='naming'){
     await goto(c,'design');const section=page.getByRole('region',{name:'欄位命名確認',exact:true});
     const confirmed=await get(`/tasks/${c.task_id}/naming-contract`);
     // Never replace a confirmed naming contract after Developer dispatch.
     if(confirmed.contract?.status==='CONFIRMED'){console.log(c.key+' NAMING_ALREADY_CONFIRMED');continue}
     const edit=button('修改並建立命名新版');if(await edit.count())await edit.click();
     await page.getByLabel('命名來源 1',{exact:true}).waitFor();
     if(c.key!=='join'){
       for(const [i,src,name,type] of [[3,'$metric.sum_amount','sum_amount','NUMERIC(24,4)'],[4,'$metric.row_count','row_count','BIGINT']]){
         if(!await page.getByLabel('命名來源 '+i,{exact:true}).count())await click('新增聚合輸出命名');
         await page.getByLabel('命名來源 '+i,{exact:true}).fill(src);await page.getByLabel('命名英文 '+i,{exact:true}).fill(name);await page.getByLabel('命名型別 '+i,{exact:true}).fill(type);
       }
     }
     await page.getByRole('checkbox',{name:'我已核對原名、英文名稱與型別',exact:true}).check();await click('確認並保存命名版本');console.log(c.key+' NAMING_SAVED');
   }else if(phase==='developer'){
     const d=await get(base()+'/developer');if(!d.invocation){if(!d.eligible)throw Error(c.key+' DEVELOPER_NOT_ELIGIBLE');await goto(c,'design');await page.getByRole('checkbox',{name:'我同意此版本的 Developer 單次模型呼叫與用量',exact:true}).check();await click('授權 Developer 設計')}
     console.log(c.key+' DEVELOPER '+(await get(base()+'/developer')).invocation?.status);
   }else if(phase==='spec'){
     const d=await get(base()+'/developer');if(d.invocation?.status!=='VALIDATED_NOT_APPROVED')throw Error(c.key+' DEVELOPER_NOT_VALIDATED');
     const s=(await get(base()+'/specifications')).items[0];if(!s)throw Error('SPEC_MISSING');const doc=s.spec_json;
     if(doc.target_schema!=='ai_sample'||doc.target_table!==c.target.split('.')[1]||doc.write_mode!=='APPEND')throw Error('SPEC_TARGET_MISMATCH');
     if(c.key==='join'){if(doc.joins[0].join_type!=='LEFT'||doc.joins[0].null_key_policy!=='NEVER_MATCH'||doc.joins[0].duplicate_key_policy!=='EXPAND'||doc.output_columns.length!==4)throw Error('JOIN_SPEC_MISMATCH')}
     else{if(doc.filters.length!==1||doc.filters[0].operator!=='GT'||String(doc.filters[0].constant.value)!=='100'||doc.aggregation.metrics.map(m=>m.function).join()!=='SUM,COUNT_ROWS'||doc.output_columns.join()!=='category,sum_amount,row_count')throw Error('AGG_SPEC_MISMATCH')}
     if(!s.approval_effective){await goto(c,'design');await page.getByRole('checkbox',{name:/我已檢查來源.*確認此規格/}).check();await click('核准此版規格')}
     state.cases[c.key].specification_id=s.specification_id;persist();console.log(c.key+' SPEC_APPROVED '+s.specification_id);
   }else if(phase==='oracle'){
     const s=(await get(base()+'/specifications')).items[0];if(!s?.approval_effective)throw Error('SPEC_NOT_APPROVED');
     const history=await get(base()+'/specifications/'+s.specification_id+'/oracles');if(history.items.length)throw Error('ORACLE_EXISTS_VERIFY_NOT_DUPLICATE');
     const fixed=JSON.parse(fs.readFileSync(path.join(root,'examples/ui-acceptance/expected.json'),'utf8'));
     const rows=c.key==='join'?fixed.join.rows.map(r=>({id:r.left_id,left_value:r.left_value,id_2:r.right_id,right_value:r.right_value})):fixed.csv_and_excel.rows.map(r=>({category:r.category,sum_amount:r.sum_amount,row_count:r.count_rows}));
     await goto(c,'confirm');const editor=page.getByRole('region',{name:'標準答案輸入',exact:true});
     await editor.getByRole('button',{name:'新增答案資料列',exact:true}).waitFor();
     if(c.key==='join')for(const col of ['id','id_2','right_value'])await editor.getByRole('checkbox',{name:new RegExp('^'+col+'（')}).check();
     for(let i=0;i<rows.length;i++){await click('新增答案資料列');for(const [col,val] of Object.entries(rows[i])){const label=`第 ${i+1} 筆 ${col}`;if(val===null)await editor.getByRole('checkbox',{name:label+' NULL',exact:true}).check();else await editor.getByLabel(label,{exact:true}).fill(String(val))}}
     await click('保存答案版本');await editor.getByRole('checkbox',{name:'我已確認上方答案內容與版本，核准供後續 QA 比對',exact:true}).check();await click('核准此答案版本');
     console.log(c.key+' FIXED_ORACLE_SAVED_APPROVED');
   }else if(phase==='hop'){
     const d=await get(base()+'/hop-dispatch');if(!d.request){if(!d.offer)throw Error(c.key+' HOP_NOT_ELIGIBLE '+d.blocked_reason);await goto(c,'confirm');await page.getByRole('checkbox',{name:'我已核對規格、標準答案及 DDL，同意新建此測試表並執行一次 Hop 寫入；失敗不自動重跑',exact:true}).check();await click('授權並排入 Hop 執行')}
     console.log(c.key+' HOP '+(await get(base()+'/hop-dispatch')).request?.status);
   }else if(phase==='qa'){
     const d=await get(base()+'/qa-authorization');if(!d.invocation){if(!d.eligible)throw Error(c.key+' QA_NOT_ELIGIBLE');await goto(c,'quality');await page.getByRole('checkbox',{name:'我同意此版本 QA 單次模型呼叫與用量',exact:true}).check();await click('授權 QA 證據審查')}
     console.log(c.key+' QA '+(await get(base()+'/qa-review')).invocation?.status);
   }else if(phase==='qa-approve'){
     const d=await get(base()+'/qa-approval');if(d.status!=='APPROVED_CURRENT'){if(d.status!=='AWAITING_CONFIRMATION')throw Error(c.key+' QA_NOT_PASS '+d.status);await goto(c,'quality');await page.getByRole('checkbox',{name:'我已檢視本 Run 的規格、執行與 QA 證據，確認此版本',exact:true}).check();await click('核准此版本 QA')}
     console.log(c.key+' QA_APPROVED');
   }else if(phase==='sdm'){
     if((await get(base()+'/qa-approval')).status!=='APPROVED_CURRENT')throw Error('QA_NOT_APPROVED');await goto(c,'delivery');await click('產生／取得 QA 關聯 SDM');console.log(c.key+' SDM_SAVED');
   }else if(phase==='candidate'){
     const d=await get(base()+'/release');if(!d.candidate){if(d.status!=='SDM_AND_CANDIDATE_REQUIRED')throw Error('CANDIDATE_NOT_ELIGIBLE');await goto(c,'delivery');await page.getByRole('checkbox',{name:'確認建立候選包並要求一次隔離可攜驗證',exact:true}).check();await click('保存候選 ZIP 並要求驗證')}
     console.log(c.key+' CANDIDATE '+(await get(base()+'/release')).status);
   }else if(phase==='release'){
     const d=await get(base()+'/release');if(!d.release_ready){if(d.status!=='AWAITING_RELEASE_APPROVAL'||d.portability?.status!=='PASS')throw Error('PORTABILITY_NOT_PASS');await goto(c,'delivery');await page.getByRole('checkbox',{name:'確認此版本的 QA、SDM、候選包與可攜驗證證據，同意正式交付',exact:true}).check();await click('核准並保存正式 Release')}
     console.log(c.key+' RELEASE '+(await get(base()+'/release')).status);
   }else if(phase==='inspect'){
     await goto(c,process.argv[4]||'design');await page.waitForTimeout(2000);console.log(c.key+' '+await page.locator('body').innerText());
   }
 }}finally{persist();await browser.close()}
}
main().catch(e=>{console.error(e.message);process.exitCode=1});



