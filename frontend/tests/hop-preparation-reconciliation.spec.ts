import {test,expect} from '@playwright/test';
import {authorizationWorkspace} from './fixtures/authorizationWorkspace';

for(const exists of [false,true])test(`準備失聯核對：目標${exists?'存在':'不存在'}、一次確認與重載（合成 API）`,async({page})=>{
 const fixture=await authorizationWorkspace(page,'results'),{task,run}=fixture;
 const base=`**/api/tasks/${task}/runs/${run}`;let closed=false,posts=0;
 await page.route(base+'/hop-dispatch',r=>r.fulfill({json:{request:{status:closed?'NEEDS_REVIEW':'CLAIMED',overdue:true},offer:null}}));
 await page.route(base+'/hop-preparation-reconciliation',async r=>{
  if(r.request().method()==='POST'){
   posts++;expect(r.request().postDataJSON()).toEqual({binding_checksum:'a'.repeat(64),target_exists:exists,observed_row_count:exists?0:null,engine_stopped:true,target_checked:true,confirmed:true});closed=true;
  }
  return r.fulfill({json:closed?{status:'CLOSED_WITHOUT_RETRY',target_exists:exists,observed_row_count:exists?0:null,evidence_sha256:null}:{status:'AWAITING_RECONCILIATION',binding:{checksum:'a'.repeat(64)}}});
 });
 await page.goto(`${fixture.base}/results/${run}`);
 const panel=page.getByRole('region',{name:'Hop 準備失聯人工核對',exact:true}),save=panel.getByRole('button',{name:'確認結案，保留結果',exact:true});
 await expect(panel.locator('input[type=file]')).toHaveCount(0);await expect(panel.getByRole('checkbox')).toHaveCount(1);
 await expect(save).toBeDisabled();await panel.getByLabel('目標表是否存在').selectOption(exists?'yes':'no');
 if(exists){await expect(save).toBeDisabled();await panel.getByLabel('核對時目標筆數').fill('0')}
 else await expect(panel.getByLabel('核對時目標筆數')).toHaveCount(0);
 await expect(save).toBeDisabled();await panel.getByLabel('我已確認本次執行與 Worker停止，目標核對結果正確，同意結案並保留原結果').check();
 await expect(save).toBeEnabled();await page.setViewportSize({width:390,height:900});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
 await save.click({clickCount:2});await expect(panel.getByRole('status')).toContainText('已人工結案');
 await page.reload();await expect(panel.getByRole('status')).toContainText('已人工結案');
 await expect(panel).toContainText(exists?'核對時目標筆數：0':'目標不存在（不是零筆）');
 expect(posts).toBe(1);fixture.assertNoUnexpectedWrites();
});