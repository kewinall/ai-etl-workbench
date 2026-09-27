import {test,expect} from '@playwright/test';

test('正式報告逐案對照即時量測及證據且不寫入',async({page,request})=>{
  const project=process.env.WORKBENCH_MEASUREMENT_PROJECT;
  test.skip(!project,'Requires a real enrolled cohort');
  const before=await (await request.get(`/api/projects/${project}/pilot-measurements`)).json();
  const events:Record<string,unknown>={};
  for(const c of before.cohorts)for(const r of c.cases){
    if(r.run_id){const url=`/api/tasks/${r.task_id}/runs/${r.run_id}`;events[url]=(await (await request.get(url)).json()).events;}
  }
  const mutations:string[]=[],errors:string[]=[];
  page.on('request',r=>{if(!['GET','HEAD','OPTIONS'].includes(r.method()))mutations.push(r.url())});
  page.on('pageerror',e=>errors.push(e.message));
  const response=await page.goto(`/api/projects/${project}/pilot-report`);
  expect(response?.status()).toBe(200);
  expect(response?.headers()['cache-control']).toBe('no-store');
  await expect(page.locator('article')).toHaveCount(before.cohorts.length*20);
  for(const c of before.cohorts){
    await expect(page.locator('body')).toContainText(`目前可交付 ${c.release_ready_count} / 20`);
    await expect(page.locator('body')).toContainText(`符合凍結情境證據 ${c.scenario_evidence_matched_count} / 20`);
    for(const r of c.cases){
      const article=page.locator('article').filter({has:page.getByRole('heading',{name:r.title,exact:true})});
      await expect(article).toContainText(r.status);
      await expect(article).toContainText(r.scenario_evidence.status);
      if(r.release_checksum)await expect(article).toContainText(r.release_checksum);
      if(r.scenario_evidence.precondition?.event_id)await expect(article).toContainText(String(r.scenario_evidence.precondition.event_id));
    }
    for(const g of c.usage.groups){
      await expect(page.locator('body')).toContainText(`${g.provider} / ${g.model}`);
      for(const m of Object.values(g.metrics) as any[])
        await expect(page.locator('body')).toContainText(`覆蓋 ${m.reported_invocations} / ${g.journal_invocations} 筆，缺 ${m.missing_invocations} 筆`);
    }
  }
  for(const width of [390,768,1440]){
    await page.setViewportSize({width,height:1000});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  }
  await page.emulateMedia({media:'print'});
  await page.screenshot({path:'test-results/formal-report-preview.png'});
  for(const [url,recorded] of Object.entries(events))expect((await (await request.get(url)).json()).events).toEqual(recorded);
  expect(mutations).toEqual([]);expect(errors).toEqual([]);
});
