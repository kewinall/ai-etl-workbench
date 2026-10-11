import {test,expect} from '@playwright/test';
import {authorizationWorkspace} from './fixtures/authorizationWorkspace';

for(const outcome of ['SUCCESS','CONFLICT','LOST_RESPONSE'])test(`SDM ${outcome}：單次提交與背景讀回（合成 API）`,async({page})=>{
 const fixture=await authorizationWorkspace(page,'delivery'),{task,run}=fixture;
 let eligible=false,posts=0,reads=0,savedOnServer=false;
 const sdmId='10000000-0000-4000-8000-000000000012';
 await page.route(`**/api/tasks/${task}/runs/${run}/sdm-candidates`,route=>route.fulfill({json:{items:savedOnServer?[{sdm_id:sdmId,status:'CANDIDATE_NOT_RELEASED',release_ready:false,checksum:'d'.repeat(64),created_at:'2026-10-11T00:00:00Z',file_size:123,specification_checksum:'b'.repeat(64)}]:[],release_ready:false}}));
 await page.route(`**/api/tasks/${task}/runs/${run}/release`,route=>route.fulfill({json:{status:'PREREQUISITES_REQUIRED',release_ready:false}}));
 await page.route(`**/api/tasks/${task}/runs/${run}/qa-approval`,route=>{
  reads++;return route.fulfill({json:{status:eligible?'APPROVED_CURRENT':'NOT_ELIGIBLE',binding:{checksum:'a'.repeat(64)}}});
 });
 await page.route(`**/api/tasks/${task}/runs/${run}/sdm-delivery`,route=>{
  posts++;expect(route.request().method()).toBe('POST');
  expect(route.request().postDataJSON()).toEqual({qa_binding_checksum:'a'.repeat(64)});
  if(outcome==='CONFLICT')return route.fulfill({status:409,json:{detail:{message:'版本已變更'}}});
  savedOnServer=true;
  if(outcome==='LOST_RESPONSE')return route.abort();
  return route.fulfill({json:{document:{sdm_id:sdmId},qa_binding:{status:'QA_LINKED_NOT_RELEASED'},release_ready:false}});
 });
 await page.goto(`${fixture.base}/delivery/${run}`);
 const panel=page.getByRole('region',{name:'SDM 交付準備',exact:true});
 const create=panel.getByRole('button',{name:'產生／取得 QA 關聯 SDM',exact:true});
 await expect(create).toBeDisabled();
 eligible=true;await page.getByRole('button',{name:'重新核對狀態',exact:true}).click();
 await expect(create).toBeEnabled();await create.click();
 if(outcome==='SUCCESS')await expect(panel).toContainText('SDM 已保存並關聯 QA');
 else {await expect(panel.getByRole('alert')).toBeVisible();await expect(create).toBeDisabled();}
 const before=reads;await page.getByRole('button',{name:'重新核對狀態',exact:true}).click();
 await expect.poll(()=>reads).toBeGreaterThan(before);
 if(outcome==='SUCCESS')await expect(panel).toContainText('SDM 已保存並關聯 QA');
 else {
  await expect(panel.getByRole('alert')).toBeVisible();await expect(create).toBeDisabled();
  await expect(panel).not.toContainText('SDM 已保存並關聯 QA');
  if(outcome==='CONFLICT')await expect(panel.getByRole('alert')).toContainText('版本已變更');
  const beforeRetry=reads;
  await panel.getByRole('button',{name:'重試讀取交付條件',exact:true}).click();
  await expect.poll(()=>reads).toBeGreaterThan(beforeRetry);
  await expect(panel.getByRole('alert')).toHaveCount(0);
  await expect(create).toBeEnabled();
 }
 await expect(panel.getByRole('region',{name:'SDM 候選文件歷史',exact:true})).toHaveCount(1);
 await expect(panel.getByRole('region',{name:'正式 Release',exact:true})).toHaveCount(1);
 if(outcome!=='CONFLICT')await expect(panel.getByRole('button',{name:'下載歷史候選 Excel（非 Release）',exact:true})).toBeVisible();
 await page.setViewportSize({width:390,height:900});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
 await expect(panel.getByRole('region',{name:'SDM 候選文件歷史',exact:true})).toBeVisible();
 expect(posts).toBe(1);fixture.assertNoUnexpectedWrites();
});
