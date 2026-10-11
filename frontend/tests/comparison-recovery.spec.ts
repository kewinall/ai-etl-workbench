import {test,expect} from '@playwright/test';
import {authorizationWorkspace} from './fixtures/authorizationWorkspace';

for(const outcome of ['MATCH','MISMATCH','FAILED','CONFLICT','LOST_RESPONSE'])test(`只比對不重跑：${outcome}、確認與重載（合成回應）`,async({page})=>{
  const fixture=await authorizationWorkspace(page,'results');
  const {task,run}=fixture,base=`**/api/tasks/${task}/runs/${run}`;
  fixture.record.write_started=true;
  await page.route(base+'/hop-dispatch',r=>r.fulfill({json:{request:{status:'NEEDS_REVIEW',outcome_code:'HOP_PREPARATION_OR_COMPARISON_FAILED'},offer:null}}));
  await page.route(base+'/hop-preparation-reconciliation',r=>r.fulfill({json:{status:'NOT_ELIGIBLE'}}));
  await page.route(base+'/execution-reconciliation',r=>r.fulfill({json:{status:'NOT_ELIGIBLE'}}));
  let posts=0,reads=0,status='AWAITING_CONFIRMATION';
  await page.route(base+'/comparison-recovery',async route=>{
    if(route.request().method()==='POST'){
      posts++;
      expect(route.request().postDataJSON()).toEqual({confirmed:true,binding_checksum:'a'.repeat(64)});
      if(outcome==='CONFLICT'){await route.fulfill({status:409,json:{detail:'版本已變更，不能恢復'}});return}
      status=outcome==='FAILED'?'FAILED':outcome==='LOST_RESPONSE'?'QUEUED':'COMPLETED';
      if(outcome==='LOST_RESPONSE'){await route.abort();return}
    }else reads++;
    await route.fulfill({json:{status,enabled:true,binding_checksum:'a'.repeat(64),outcome_code:`RESULT_${outcome}_QA_REQUIRED`,qa_passed:false,release_ready:false}});
  });
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`${fixture.base}/results/${run}`);
  const panel=page.getByRole('region',{name:'只重新比對結果',exact:true});
  const save=panel.getByRole('button',{name:'授權重新比對（不重跑 ETL）',exact:true});
  await expect(save).toBeDisabled();
  await panel.getByRole('checkbox').check();await expect(save).toBeEnabled();
  await page.setViewportSize({width:390,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  await save.click();
  if(['CONFLICT','LOST_RESPONSE'].includes(outcome)){
    await expect(panel.getByRole('alert')).toBeVisible();
    if(outcome==='CONFLICT')await expect(panel.getByRole('alert')).toContainText('版本已變更');
    const before=reads;
    await page.getByRole('button',{name:'重新核對狀態',exact:true}).click();
    await expect.poll(()=>reads).toBeGreaterThan(before);
    await expect(panel.getByRole('alert')).toBeVisible();
    await expect(save).toHaveCount(0);
    await panel.getByRole('button',{name:'重試讀取比對恢復狀態',exact:true}).click();
    if(outcome==='CONFLICT')await expect(save).toBeDisabled();
    else {await expect(panel).toContainText('已排入結果比對');await expect(save).toHaveCount(0)}
  }else{
    const text=outcome==='MATCH'?'結果比對一致':outcome==='MISMATCH'?'結果比對不一致':'本次比對恢復未成功';
    await expect(panel).toContainText(text);
    await page.reload();await expect(panel).toContainText(text);
    await expect(save).toHaveCount(0);
    await expect(page.getByRole('region',{name:'Hop 單次執行',exact:true})).toContainText('HOP_PREPARATION_OR_COMPARISON_FAILED');
  }
  expect(posts).toBe(1);expect(errors).toEqual([]);fixture.assertNoUnexpectedWrites();
});
