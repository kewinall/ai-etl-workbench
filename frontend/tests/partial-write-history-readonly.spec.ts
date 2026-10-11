import {test,expect} from '@playwright/test';

test('保留真實部分提交：新版只讀結果、重載與390/768/1440，不重送結案',async({page,request})=>{
 const task=process.env.WORKBENCH_PARTIAL_HISTORY_TASK,run=process.env.WORKBENCH_PARTIAL_HISTORY_RUN;
 test.skip(!task||!run,'Fixed retained partial-write GET-only harness required; never creates a Run');
 expect(task).toMatch(/^partial-worker-[a-f0-9]{32}$/);
 const base=`/api/tasks/${task}/runs/${run}`;
 const identity=await(await request.get(`/api/tasks/${task}`)).json();
 const before=await(await request.get(base)).json();
 const receipt=await(await request.get(base+'/reconciliation')).json();
 const workflow=await(await request.get(base+'/workflow-status')).json();
 expect(before.state).toBe('FAILED');expect(before.outcome_code).toBe('HOP_RESULT_UNKNOWN');expect(before.write_started).toBe(true);
 expect(receipt.status).toBe('CLOSED_WITHOUT_RETRY');expect(receipt.observed_row_count).toBe(1000);
 expect(receipt.automatic_retry_allowed).toBe(false);expect(receipt.qa_approved).toBe(false);expect(receipt.release_ready).toBe(false);
 expect(workflow.read_only_source).toBe(true);expect(workflow.current_stage).toBe('results');
 expect(Object.values(workflow.operation_qualifications).every((op:any)=>op.enabled===false)).toBe(true);
 const mutations:string[]=[];
 page.on('request',r=>{if(!['GET','HEAD','OPTIONS'].includes(r.method()))mutations.push(r.method()+' '+new URL(r.url()).pathname)});
 await page.route('**/api/**',route=>['GET','HEAD','OPTIONS'].includes(route.request().method())?route.continue():route.abort());
 await page.goto(`/#/projects/${identity.project_id}/tasks/${task}/results/${run}`);
 const panel=page.getByRole('region',{name:'執行結果人工核對',exact:true});
 await expect(panel).toContainText('已人工結案，未重跑、未核准 QA 或交付');
 await expect(panel).toContainText('目標筆數：1000');
 await expect(panel.locator('input[type="file"]')).toHaveCount(0);
 await expect(panel.getByRole('button',{name:'確認結案，保留結果'})).toHaveCount(0);
 for(const width of [390,768,1440]){
  await page.setViewportSize({width,height:1000});
  await expect(page.getByLabel('共用 Run 版本')).toHaveValue(run!);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),`${width}px`).toBe(true);
  await page.reload();await expect(panel).toContainText('目標筆數：1000');
 }
 expect(await(await request.get(base)).json()).toEqual(before);
 expect(await(await request.get(base+'/reconciliation')).json()).toEqual(receipt);
 expect(mutations).toEqual([]);
});
