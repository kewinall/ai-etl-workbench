import {test,expect} from '@playwright/test';

test('失敗診斷與結案後修訂入口（合成 API，不重跑 ETL）',async({page,request})=>{
 const task=process.env.WORKBENCH_BOUND_RESULT_TASK,run=process.env.WORKBENCH_BOUND_RESULT_RUN,project=process.env.WORKBENCH_BOUND_RESULT_PROJECT;
 test.skip(!task||!run||!project,'Requires existing navigation');
 const base=`/api/tasks/${task}/runs/${run}`;
 const original=await (await request.get(base)).json();
 let saved:any=null;
 await page.route(`**${base}`,r=>r.fulfill({json:{...original,state:'FAILED',outcome_code:'HOP_EXECUTION_FAILED',matches_current:true,failed_revision_available:true}}));
 await page.route(`**${base}/diagnosis`,r=>r.fulfill({json:{status:'EVIDENCE_REVIEW_REQUIRED',limitation:'需核對實際資料庫，不是回滾證明。',findings:[{code:'COLUMN_NOT_FOUND',message:'日誌指出欄位不存在',line_numbers:[12]}],next_steps:['先核對再建立新版本'],log_checksum:'a'.repeat(64)}}));
 await page.route(`**${base}/reconciliation`,r=>r.fulfill({json:{status:'CLOSED_WITHOUT_RETRY',observed_row_count:0,evidence_sha256:'b'.repeat(64),created_at:'2026-09-26T00:00:00Z',original_outcome:'HOP_EXECUTION_FAILED'}}));
 await page.route(`**${base}/revisions`,r=>{saved=r.request().postDataJSON();return r.fulfill({json:{run_id:'synthetic-child'}})});
 await page.goto(`/#/projects/${project}/tasks/${task}/requirements`);
 await expect(page.getByRole('region',{name:'失敗診斷證據'})).toContainText('程式規則，非 AI');
 await expect(page.getByRole('region',{name:'失敗診斷證據'})).toContainText('行號：12');
 await page.getByRole('button',{name:'補正需求並建立新版',exact:true}).click();
 const form=page.getByRole('form',{name:'需求補正'});
 await form.getByLabel('目標 Table',{exact:true}).fill('synthetic_revised_target');
 await form.getByRole('button',{name:'保存補正並建立新版',exact:true}).click();
 await expect.poll(()=>saved?.target_table).toBe('synthetic_revised_target');
 expect(saved.input_checksum).toBe(original.input_checksum);
 await page.reload();await page.setViewportSize({width:390,height:900});
 await expect(page.getByRole('region',{name:'失敗診斷證據'})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
});
