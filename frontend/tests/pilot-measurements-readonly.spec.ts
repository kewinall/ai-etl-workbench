import {test,expect} from '@playwright/test';

test('正式集合量測與逐案 gate 一致，保留分母且無寫入',async({page,request})=>{
  const project=process.env.WORKBENCH_MEASUREMENT_PROJECT;
  test.skip(!project,'Requires a real enrolled cohort');
  const endpoint=`/api/projects/${project}/pilot-measurements`;
  const response=await request.get(endpoint);expect(response.ok()).toBe(true);
  const measured=await response.json();expect(measured.cohorts.length).toBeGreaterThan(0);
  const errors:string[]=[],mutations:string[]=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(!['GET','HEAD','OPTIONS'].includes(r.method()))mutations.push(r.url())});
  const eventsBefore:Record<string,unknown>={};
  for(const cohort of measured.cohorts){
    expect(cohort.denominator).toBe(20);expect(cohort.cases).toHaveLength(20);
    let ready=0;
    for(const row of cohort.cases){
      if(!row.run_id)continue;
      const base=`/api/tasks/${row.task_id}/runs/${row.run_id}`;
      const release=await (await request.get(`${base}/release`)).json();
      expect(row.status).toBe(release.status);ready+=Number(release.status==='RELEASE_READY');
      eventsBefore[base]=(await (await request.get(base)).json()).events;
    }
    expect(cohort.release_ready_count).toBe(ready);
    expect(cohort.scenario_evidence_matched_count).toBe(cohort.cases.filter((r:any)=>r.scenario_acceptance_verified).length);
    for(const row of cohort.cases){
      const proof=row.scenario_evidence;
      if(row.scenario_acceptance_verified){
        expect(proof.status).toBe('SCENARIO_EVIDENCE_MATCHED');
        expect(row.status).toBe('RELEASE_READY');expect(proof.source_verified).toBe(true);expect(proof.frozen_oracle_verified).toBe(true);
      }
      if(proof.precondition?.event_id){
        const prior=await (await request.get(`/api/tasks/${row.task_id}/runs/${proof.precondition.run_id}`)).json();
        const event=prior.events.find((e:any)=>e.event_id===proof.precondition.event_id);
        expect(event).toBeTruthy();
        if(row.scenario==='EXECUTION_RECOVERY'){
          expect(event.event_type).toBe('HOP_EXECUTION_FAILED');expect(prior.state).toBe('FAILED');
        }else{
          expect(prior.write_started).toBe(false);
          expect(event.event_type).toBe(row.scenario==='REQUIREMENT_GAP'?'REQUIREMENT_NEEDS_INPUT':'SPECIFICATION_SEMANTIC_REJECTED');
        }
      }
    }
    expect(cohort.first_pass_rate).toBeNull();expect(cohort.human_active_seconds).toBeNull();
    expect(cohort.usage.basis).toBe('ALL_BOUND_RUN_JOURNAL_RECORDS');
    expect(cohort.usage.groups.reduce((n:number,g:any)=>n+g.journal_invocations,0)).toBe(
      Object.values(cohort.usage.cases).reduce((n:number,c:any)=>n+c.journal_invocations,0));
    for(const group of cohort.usage.groups){
      expect(group.cost).toBeNull();
      for(const metric of Object.values(group.metrics) as any[]){
        expect(metric.reported_invocations+metric.missing_invocations).toBe(group.journal_invocations);
        if(metric.missing_invocations)expect(metric.complete_sum).toBeNull();
      }
    }
  }
  await page.goto(`/#/projects/${project}/evaluation`);
  const inventory=await (await request.get(`/api/projects/${project}/pilot-cohorts`)).json();
  const changed=inventory.cohorts.flatMap((c:any)=>c.cases).filter((c:any)=>
    c.runs.some((r:any)=>r.source_order_scope==='CHANGED_REQUIRES_PROTOCOL_REVIEW'));
  for(const item of changed){
    const details=page.locator('details').filter({has:page.locator('summary', {hasText:`${item.ordinal}. ${item.definition.title}`})});
    await details.locator('summary').click();
    await expect(details).toContainText('順序需求已變更：須另行審核，不代表原凍結案例通過。');
    for(const width of [390,768,1440]){
      await page.setViewportSize({width,height:1000});
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
    }
    await details.locator('summary').click();
  }
  const region=page.getByRole('region',{name:'正式案例量測',exact:true});
  await region.getByRole('button',{name:'重新量測正式案例',exact:true}).click();
  await expect(region).toContainText(`目前可交付：${measured.cohorts[0].release_ready_count} / 20`);
  await expect(region).toContainText(`符合凍結情境證據：${measured.cohorts[0].scenario_evidence_matched_count} / 20`);
  await expect(region).toContainText('尚無完整量測');
  await expect(region.getByRole('region',{name:'模型用量覆蓋'}).first()).toBeVisible();
  for(const width of [390,768,1440]){
    await page.setViewportSize({width,height:1000});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  }
  const first=measured.cohorts[0].cases.find((r:any)=>r.run_id);
  await region.getByRole('button',{name:'查看量測版本證據',exact:true}).first().click();
  await expect(page).toHaveURL(new RegExp(`/execution/${first.run_id}$`));
  await page.goBack();await expect(region).toBeVisible();
  for(const [base,events] of Object.entries(eventsBefore))expect((await (await request.get(base)).json()).events).toEqual(events);
  expect(errors).toEqual([]);expect(mutations).toEqual([]);
});
