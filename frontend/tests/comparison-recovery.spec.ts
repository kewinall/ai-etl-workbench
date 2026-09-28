import {test,expect} from '@playwright/test';

for(const outcome of ['MATCH','MISMATCH','FAILED','CONFLICT'])test(`只比對不重跑：${outcome}、確認與重載（合成回應）`,async({page,request})=>{
  test.skip(!process.env.WORKBENCH_TEST_URL?.includes(':5195'),'Isolated UI API required');
  const project=await(await request.post('/api/projects',{data:{project_name:'比對恢復UI-'+Date.now()}})).json();
  const created=await request.post(`/api/projects/${project.project_id}/tasks`,{data:{name:'合成互動測試',requirement:'UI only',source_config:{sources:[{type:'CSV',has_actual_data:false,fields:[{name:'id',type:'BIGINT'}]}]},target_schema:'ai_sample',target_table:'ui_only'}});
  expect(created.status()).toBe(201);
  const task=await created.json(),runId='00000000-0000-4000-8000-000000000001';
  const base=`**/api/tasks/${task.id}/runs`,url=`${base}/${runId}`;
  const run={run_id:runId,state:'NEEDS_REVIEW',created_at:'2026-09-28T00:00:00Z',input_summary:{},settings_summary:{},events:[],matches_current:true};
  await page.route(base,r=>r.fulfill({json:{runs:[run]}}));
  await page.route(url,r=>r.fulfill({json:run}));
  await page.route(url+'/hop-dispatch',r=>r.fulfill({json:{request:{status:'NEEDS_REVIEW',outcome_code:'HOP_PREPARATION_OR_COMPARISON_FAILED'},offer:null}}));
  await page.route(url+'/hop-preparation-reconciliation',r=>r.fulfill({json:{status:'NOT_ELIGIBLE'}}));
  let posts=0,status='AWAITING_CONFIRMATION';
  await page.route(url+'/comparison-recovery',async route=>{
    if(route.request().method()==='POST'){
      posts++;
      expect(route.request().postDataJSON()).toEqual({confirmed:true,binding_checksum:'a'.repeat(64)});
      if(outcome==='CONFLICT'){await route.fulfill({status:409,json:{detail:'版本已變更，不能恢復'}});return}
      status=outcome==='FAILED'?'FAILED':'COMPLETED';
    }
    await route.fulfill({json:{status,enabled:true,binding_checksum:'a'.repeat(64),outcome_code:`RESULT_${outcome}_QA_REQUIRED`,qa_passed:false,release_ready:false}});
  });
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`/#/projects/${project.project_id}/tasks/${task.id}/requirements`);
  const panel=page.getByRole('region',{name:'只重新比對結果',exact:true});
  const save=panel.getByRole('button',{name:'授權重新比對（不重跑 ETL）',exact:true});
  await expect(save).toBeDisabled();
  await panel.getByRole('checkbox').check();await expect(save).toBeEnabled();
  await page.setViewportSize({width:390,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  await save.click();
  if(outcome==='CONFLICT'){
    await expect(panel.getByRole('alert')).toContainText('版本已變更');
    await expect(save).toHaveCount(0);
    await panel.getByRole('button',{name:'重新核對比對恢復狀態'}).click();
    await expect(save).toBeDisabled();
  }else{
    const text=outcome==='MATCH'?'結果比對一致':outcome==='MISMATCH'?'結果比對不一致':'本次比對恢復未成功';
    await expect(panel).toContainText(text);
    await page.reload();await expect(panel).toContainText(text);
    await expect(save).toHaveCount(0);
    await expect(page.getByRole('region',{name:'Hop 單次執行',exact:true})).toContainText('HOP_PREPARATION_OR_COMPARISON_FAILED');
  }
  expect(posts).toBe(1);expect(errors).toEqual([]);
});
