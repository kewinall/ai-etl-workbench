import {test,expect} from '@playwright/test';
import {authorizationWorkspace} from './fixtures/authorizationWorkspace';
import {workflowStatus} from './fixtures/workflow';

test('失敗診斷與結案後修訂入口（合成 API，不重跑 ETL）',async({page})=>{
 const fixture=await authorizationWorkspace(page,'results');
 const {task,run}=fixture;
 const base=`/api/tasks/${task}/runs/${run}`;
 const original={...fixture.record,input_checksum:'c'.repeat(64),state:'FAILED',write_started:true,
   outcome_code:'HOP_EXECUTION_FAILED',matches_current:true,failed_revision_available:true};
 const childId='10000000-0000-4000-8000-000000000012';
 const records:any[]=[original];
 let saved:any=null;
 await page.route(`**/api/tasks/${task}/runs`,r=>r.fulfill({json:{runs:records}}));
 await page.route(`**${base}`,r=>r.fulfill({json:original}));
 await page.route(`**/api/tasks/${task}/runs/${childId}`,r=>r.fulfill({json:records[0]}));
 await page.route(`**/workflow-status`,r=>{
   const id=new URL(r.request().url()).pathname.split('/').at(-2)!;
   return r.fulfill({json:workflowStatus(task,id,{stage:id===run?'results':'requirements',historical:records[0].run_id!==id,
     overrides:{next_action:{stage:'requirements',label:'此版已結案；可建立修正版',enabled:true}}})});
 });
 await page.route(`**${base}/diagnosis`,r=>r.fulfill({json:{status:'EVIDENCE_REVIEW_REQUIRED',limitation:'需核對實際資料庫，不是回滾證明。',findings:[{code:'COLUMN_NOT_FOUND',message:'日誌指出欄位不存在',line_numbers:[12]}],next_steps:['先核對再建立新版本'],log_checksum:'a'.repeat(64)}}));
 await page.route(`**${base}/reconciliation`,r=>r.fulfill({json:{status:'CLOSED_WITHOUT_RETRY',observed_row_count:0,evidence_sha256:'b'.repeat(64),created_at:'2026-09-26T00:00:00Z',original_outcome:'HOP_EXECUTION_FAILED'}}));
 await page.route(`**${base}/revisions`,r=>{saved=r.request().postDataJSON();const child={...fixture.record,run_id:childId,parent_run_id:run,state:'QUEUED',approval:null,
   input_summary:{...original.input_summary,target_table:saved.target_table}};records.unshift(child);return r.fulfill({status:201,json:child})});
 await page.goto(`${fixture.base}/results/${run}`);
 await expect(page.getByRole('region',{name:'失敗診斷證據'})).toHaveCount(1);
 await expect(page.getByRole('region',{name:'失敗診斷證據'})).toContainText('程式規則，非 AI');
 await expect(page.getByRole('region',{name:'失敗診斷證據'})).toContainText('行號：12');
 await page.getByRole('button',{name:'建立修正版（保留此版結果）',exact:true}).click();
 const form=page.getByRole('form',{name:'需求補正'});
 await form.getByLabel('目標 Table',{exact:true}).fill('synthetic_revised_target');
 await form.getByRole('button',{name:'預覽修訂差異',exact:true}).click();
 await form.getByRole('checkbox',{name:'已核對差異，同意建立待需求確認的新版',exact:true}).check();
 await form.getByRole('button',{name:'保存補正並建立新版',exact:true}).click();
 await expect.poll(()=>saved?.target_table).toBe('synthetic_revised_target');
 expect(saved.input_checksum).toBe(original.input_checksum);
 expect(records[1]).toEqual(original);expect(records[0].approval).toBeNull();expect(records[0].write_started).toBe(false);
 await page.goto(`${fixture.base}/results/${run}`);
 await page.reload();await page.setViewportSize({width:390,height:900});
 await expect(page.getByRole('region',{name:'失敗診斷證據'})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
 fixture.assertNoUnexpectedWrites();
});
