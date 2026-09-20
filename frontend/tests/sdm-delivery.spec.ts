import {test,expect} from '@playwright/test';
test('SDM 交付條件、成功提示與衝突清除（合成 API）',async({page})=>{
 const task=process.env.WORKBENCH_BOUND_RESULT_TASK,run=process.env.WORKBENCH_BOUND_RESULT_RUN,project=process.env.WORKBENCH_BOUND_RESULT_PROJECT;
 test.skip(!task||!run||!project,'Requires existing navigation');
 let eligible=false,conflict=false;
 await page.route(`**/api/tasks/${task}/runs/${run}/qa-approval`,r=>r.fulfill({json:{status:eligible?'APPROVED_CURRENT':'NOT_ELIGIBLE',binding:{checksum:'a'.repeat(64)}}}));
 await page.route(`**/api/tasks/${task}/runs/${run}/sdm-delivery`,r=>{
  expect(r.request().postDataJSON()).toEqual({qa_binding_checksum:'a'.repeat(64)});
  return conflict?r.fulfill({status:409,json:{detail:{message:'版本已變更'}}}):r.fulfill({json:{document:{sdm_id:'synthetic'},qa_binding:{status:'QA_LINKED_NOT_RELEASED'},release_ready:false}});
 });
 await page.goto(`/#/projects/${project}/tasks/${task}/delivery`);
 const panel=page.getByRole('region',{name:'SDM 交付準備',exact:true});
 const create=panel.getByRole('button',{name:'產生／取得 QA 關聯 SDM',exact:true});
 await expect(create).toBeDisabled();
 eligible=true;await panel.getByRole('button',{name:'重新核對交付條件'}).click();
 await expect(create).toBeEnabled();await create.click();
 await expect(panel).toContainText('SDM 已保存並關聯 QA');
 await expect(panel.getByRole('region',{name:'SDM 候選文件歷史',exact:true})).toHaveCount(1);
 await expect(panel.getByRole('region',{name:'正式 Release',exact:true})).toHaveCount(1);
 conflict=true;await create.click();
 await expect(panel.getByRole('alert')).toContainText('版本已變更');
 await expect(create).toBeDisabled();await expect(panel).not.toContainText('SDM 已保存並關聯 QA');
 await page.setViewportSize({width:390,height:900});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
 await expect(panel.getByRole('region',{name:'SDM 候選文件歷史'})).toBeVisible();
});
