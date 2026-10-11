import {test,expect} from '@playwright/test';
import {authorizationWorkspace} from './fixtures/authorizationWorkspace';

for(const outcome of ['SUCCESS','CONFLICT','LOST_RESPONSE'])test(`人工核對 ${outcome}：保留输入、只结案一次、不需证据文件（合成 API）`,async({page})=>{
 const fixture=await authorizationWorkspace(page,'results'),{task,run}=fixture;
 Object.assign(fixture.record,{write_started:true,outcome_code:'HOP_RESULT_UNKNOWN'});
 const base=`**/api/tasks/${task}/runs/${run}`;
 await page.route(base+'/hop-dispatch',r=>r.fulfill({json:{request:{status:'COMPLETED'},offer:null}}));
 let closed=false,posts=0;
 await page.route(base+'/reconciliation',async r=>{
  if(r.request().method()==='POST'){
   posts++;expect(r.request().postDataJSON()).toEqual({binding_checksum:'a'.repeat(64),observed_row_count:1,engine_stopped:true,target_checked:true,confirmed:true});
   if(outcome==='CONFLICT')return r.fulfill({status:409,json:{detail:{message:'版本已變更'}}});
   closed=true;if(outcome==='LOST_RESPONSE')return r.abort();
  }
  return r.fulfill({json:closed?{status:'CLOSED_WITHOUT_RETRY',observed_row_count:1,evidence_sha256:null,original_outcome:'HOP_RESULT_UNKNOWN'}:{status:'AWAITING_RECONCILIATION',binding:{checksum:'a'.repeat(64)}}});
 });
 await page.goto(`${fixture.base}/results/${run}`);
 const panel=page.getByRole('region',{name:'執行結果人工核對',exact:true});
 const save=panel.getByRole('button',{name:'確認結案，保留結果',exact:true});
 await expect(panel.locator('input[type=file]')).toHaveCount(0);await expect(panel.getByRole('checkbox')).toHaveCount(1);
 await expect(save).toBeDisabled();await panel.getByLabel('核對時目標筆數').fill('1');await expect(save).toBeDisabled();
 await panel.getByLabel('我已確認本次執行停止，目標核對結果正確，同意結案並保留原結果').check();await expect(save).toBeEnabled();
 await page.setViewportSize({width:390,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
 await save.click({clickCount:2});
 if(outcome==='SUCCESS')await expect(panel.getByRole('status')).toContainText('已人工結案，未重跑');
 else{
  await expect(panel.getByRole('alert')).toContainText('結案結果尚未確認');
  await expect(panel.getByLabel('核對時目標筆數')).toHaveValue('1');await expect(save).toBeDisabled();
  await page.getByRole('button',{name:'重新核對狀態',exact:true}).click();
  await expect(panel.getByRole('alert')).toBeVisible();await expect(save).toBeDisabled();
  await panel.getByRole('button',{name:'重新讀取結案狀態',exact:true}).click();
  if(closed)await expect(panel.getByRole('status')).toContainText('已人工結案');
  else{await expect(save).toBeDisabled();await expect(panel.getByLabel('核對時目標筆數')).toHaveValue('1')}
 }
 await page.reload();
 if(closed)await expect(panel.getByRole('status')).toContainText('已人工結案');
 else await expect(save).toBeDisabled();
 expect(posts).toBe(1);fixture.assertNoUnexpectedWrites();
});