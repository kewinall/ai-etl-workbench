import {test,expect} from '@playwright/test';

test('真實版本：比對恢復確認或已保存結果；不重新派發 Hop',async({page,request})=>{
  const task=process.env.WORKBENCH_BOUND_RESULT_TASK,run=process.env.WORKBENCH_BOUND_RESULT_RUN,project=process.env.WORKBENCH_BOUND_RESULT_PROJECT;
  test.skip(!task||!run||!project,'Explicit existing synthetic Pilot run required');
  const base=`/api/tasks/${task}/runs/${run}`;
  const before=await(await request.get(base)).json();
  expect(before.run_id).toBe(run);expect(before.write_started).toBe(true);
  expect(before.outcome_code).toBe('HOP_EXECUTED_QA_REQUIRED');
  const job=await(await request.get(base+'/hop-dispatch')).json();
  expect(job.request.status).toBe('NEEDS_REVIEW');
  expect(job.request.outcome_code).toBe('HOP_PREPARATION_OR_COMPARISON_FAILED');
  const offered=await(await request.get(base+'/comparison-recovery')).json();
  if(offered.status==='AWAITING_CONFIRMATION')expect(process.env.WORKBENCH_RECOVERY_WRITE_CONSENT).toBe('1');
  else expect(['QUEUED','COMPLETED']).toContain(offered.status);
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  let posts=0;
  page.on('request',r=>{if(r.method()==='POST'){
    expect(new URL(r.url()).pathname).toBe(base+'/comparison-recovery');posts++;
  }});
  await page.goto(`/#/projects/${project}/tasks/${task}/requirements`);
  const versions=page.getByRole('region',{name:'執行準備版本',exact:true});
  await versions.getByRole('button').filter({hasText:run!}).first().click();
  const panel=page.getByRole('region',{name:'只重新比對結果',exact:true});
  if(offered.status==='AWAITING_CONFIRMATION'){
    const save=panel.getByRole('button',{name:'授權重新比對（不重跑 ETL）',exact:true});
    await expect(save).toBeDisabled();await panel.getByRole('checkbox').check();
    await save.click();await expect(panel).toContainText('已排入結果比對');expect(posts).toBe(1);
  }else expect(posts).toBe(0);
  await page.reload();
  await expect(panel).toContainText(offered.status==='COMPLETED'?'結果比對一致':'已排入結果比對');
  await expect(panel.getByRole('checkbox')).toHaveCount(0);
  await page.setViewportSize({width:390,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  const after=await(await request.get(base)).json();
  expect(after.events.filter((e:any)=>e.event_type==='WRITE_STARTED')).toEqual(before.events.filter((e:any)=>e.event_type==='WRITE_STARTED'));
  expect((await(await request.get(base+'/hop-dispatch')).json()).request).toEqual(job.request);
  expect(errors).toEqual([]);
});
