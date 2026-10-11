import {test,expect} from '@playwright/test';
import fs from 'node:fs';

const file=process.env.WORKBENCH_RETAINED_HISTORY_PROOF;
const cases=file?JSON.parse(fs.readFileSync(file,'utf8').replace(/^\uFEFF/,'')):[];
test('retained history requires explicit fixed GET-only source',()=>{
  test.skip(!file,'Retained fixed QA/crash source required; never creates or runs a Task');
  expect(cases.map((item:any)=>item.case)).toEqual(['qa_reassessment','native_crash']);
  expect(new Set(cases.map((item:any)=>item.run)).size).toBe(2);
});
for(const item of cases)test(`原真實 ${item.case} 在目前品質／結果階段唯讀查閱`,async({page,request,baseURL})=>{
  test.setTimeout(60000);
  expect(new URL(baseURL!).origin).toBe('http://127.0.0.1:5204');
  const base=`/api/tasks/${item.task}/runs/${item.run}`;
  const before=await(await request.get(base)).json();
  expect(before.task_id).toBe(item.task);expect(before.run_id).toBe(item.run);
  const recordPath=base+(item.case==='qa_reassessment'?'/qa-review':'/reconciliation');
  const record=await(await request.get(recordPath)).json();
  const workflow=await(await request.get(base+'/workflow-status')).json();
  expect(workflow.read_only_source).toBe(true);
  expect(workflow.stages.every((stage:any)=>stage.can_operate===false)).toBe(true);
  expect(Object.values(workflow.operation_qualifications).filter((op:any)=>op.type!=='DOWNLOAD').every((op:any)=>op.enabled===false)).toBe(true);
  const mutations:string[]=[],errors:string[]=[];
  page.on('request',r=>{if(!['GET','HEAD','OPTIONS'].includes(r.method()))mutations.push(r.method()+' '+new URL(r.url()).pathname)});
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/**',route=>['GET','HEAD','OPTIONS'].includes(route.request().method())?route.continue():route.abort());
  const stage=item.case==='qa_reassessment'?'quality':'results';
  await page.goto(`/#/projects/${item.project}/tasks/${item.task}/${stage}/${item.run}`);
  if(item.case==='qa_reassessment'){
    expect(record.history).toHaveLength(2);
    expect(record.history[0].review.status).toBe('PASS');
    expect(record.history[1].review.status).toBe('NEEDS_REVIEW');
    expect(record.history[0].reassesses_invocation_id).toBe(record.history[1].invocation_id);
    const fold=page.getByText('查看歷次 QA 模型紀錄與核准詳情',{exact:true});
    await expect(fold).toBeVisible();await fold.click();
    const panel=page.getByRole('region',{name:'QA 審查紀錄',exact:true});
    await expect(panel).toContainText('人工 QA 已核准，已正式交付');
    const records=panel.locator('article.wb-record');
    await expect(records).toHaveCount(2);
    await expect(records.nth(0)).toContainText('QA 建議：PASS');
    await expect(records.nth(0)).toContainText('複核自 '+record.history[1].invocation_id);
    await expect(records.nth(1)).toContainText('QA 建議：NEEDS_REVIEW');
  }else{
    expect(before.state).toBe('FAILED');expect(before.outcome_code).toBe('HOP_RESULT_UNKNOWN');
    expect(record.status).toBe('CLOSED_WITHOUT_RETRY');expect(record.observed_row_count).toBe(1);
    const panel=page.getByRole('region',{name:'執行結果人工核對',exact:true});
    await expect(panel).toContainText('已人工結案，未重跑、未核准 QA 或交付');
    await expect(panel).toContainText('目標筆數：1');
    await expect(panel.getByRole('button',{name:'確認結案，保留結果'})).toHaveCount(0);
    await expect(panel.locator('input[type="file"]')).toHaveCount(0);
  }
  for(const width of [390,768,1440]){
    await page.setViewportSize({width,height:1000});
    await expect(page.getByLabel('共用 Run 版本')).toHaveValue(item.run);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),`${item.case} ${width}px`).toBe(true);
    await expect(page.locator('input[type="checkbox"]:visible:enabled')).toHaveCount(0);
  }
  await page.getByRole('button',{name:'重新核對狀態',exact:true}).focus();
  await page.keyboard.press('Enter');await expect(page.getByLabel('共用 Run 版本')).toHaveValue(item.run);
  await page.reload();await expect(page.getByLabel('共用 Run 版本')).toHaveValue(item.run);
  if(item.case==='qa_reassessment'){
    await page.getByText('查看歷次 QA 模型紀錄與核准詳情',{exact:true}).click();
    await expect(page.getByRole('region',{name:'QA 審查紀錄',exact:true})).toContainText('QA 建議：NEEDS_REVIEW');
  }else await expect(page.getByRole('region',{name:'執行結果人工核對',exact:true})).toContainText('目標筆數：1');
  expect(await(await request.get(base)).json()).toEqual(before);
  expect(await(await request.get(recordPath)).json()).toEqual(record);
  expect(mutations).toEqual([]);expect(errors).toEqual([]);
});
