import {test,expect} from '@playwright/test';
import {authorizationWorkspace} from './fixtures/authorizationWorkspace';

for(const outcome of ['SUCCESS','CONFLICT','LOST_RESPONSE'])test(`人工 QA 核准 ${outcome}：確認、單次提交、背景讀回與重載（合成 API）`,async({page})=>{
 const fixture=await authorizationWorkspace(page,'quality'),{task,run}=fixture;let approved=false,posts=0,reads=0;
 await page.route(`**/api/tasks/${task}/runs/${run}/qa-approval`,async route=>{
  if(route.request().method()==='POST'){
   posts++;expect(route.request().postDataJSON()).toEqual({confirmed:true,binding_checksum:'a'.repeat(64)});
   if(outcome==='CONFLICT')return route.fulfill({status:409,json:{detail:{message:'版本已變更，請重新載入'}}});
   approved=true;if(outcome==='LOST_RESPONSE')return route.abort();
   return route.fulfill({json:{qa_approved:true,release_ready:false}});
  }
  reads++;return route.fulfill({json:{status:approved?'APPROVED_CURRENT':'AWAITING_CONFIRMATION',binding:{checksum:'a'.repeat(64),specification_checksum:'b'.repeat(64),review_checksum:'c'.repeat(64)},approval:approved?{approval_id:'synthetic-only'}:null,qa_approved:approved,release_ready:false}});
 });
 await page.goto(`${fixture.base}/quality/${run}`);
 const panel=page.getByRole('region',{name:'人工 QA 核准',exact:true}),save=panel.getByRole('button',{name:'核准此版本 QA',exact:true});
 await expect(save).toBeDisabled();await panel.getByRole('checkbox').check();await save.click();
 if(outcome==='SUCCESS')await expect(panel).toContainText('目前版本已由操作者核准');
 else{
  await expect(panel.getByRole('alert')).toBeVisible();
  const before=reads;await page.getByRole('button',{name:'重新核對狀態',exact:true}).click();
  await expect.poll(()=>reads).toBeGreaterThan(before);await expect(panel.getByRole('alert')).toBeVisible();
  await expect(panel.getByRole('checkbox')).toHaveCount(0);
  await panel.getByRole('button',{name:'重試讀取核准狀態',exact:true}).click();
  if(approved)await expect(panel).toContainText('目前版本已由操作者核准');else await expect(save).toBeDisabled();
 }
 await page.setViewportSize({width:390,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
 await page.reload();if(approved)await expect(panel).toContainText('目前版本已由操作者核准');else await expect(save).toBeDisabled();
 expect(posts).toBe(1);fixture.assertNoUnexpectedWrites();
});