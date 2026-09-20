import {test,expect} from '@playwright/test';
test('人工 QA 確認、提交、重載與衝突清除（合成 API）',async({page})=>{
  const task=process.env.WORKBENCH_BOUND_RESULT_TASK,run=process.env.WORKBENCH_BOUND_RESULT_RUN,project=process.env.WORKBENCH_BOUND_RESULT_PROJECT;
  test.skip(!task||!run||!project,'Requires existing navigation');
  let approved=false,conflict=false,posts=0;
  await page.route(`**/api/tasks/${task}/runs/${run}/qa-approval`,async route=>{
    if(route.request().method()==='POST'){
      posts++;expect(route.request().postDataJSON()).toEqual({confirmed:true,binding_checksum:'a'.repeat(64)});
      if(conflict)return route.fulfill({status:409,json:{detail:{message:'版本已變更，請重新載入'}}});
      approved=true;return route.fulfill({json:{qa_approved:true,release_ready:false}});
    }
    return route.fulfill({json:{status:approved?'APPROVED_CURRENT':'AWAITING_CONFIRMATION',
      binding:{checksum:'a'.repeat(64),specification_checksum:'b'.repeat(64),review_checksum:'c'.repeat(64)},
      approval:approved?{approval_id:'synthetic-only'}:null,qa_approved:approved,release_ready:false}});
  });
  await page.goto(`/#/projects/${project}/tasks/${task}/execution`);
  const panel=page.getByRole('region',{name:'人工 QA 核准',exact:true});
  await expect(panel.getByRole('button',{name:'核准此版本 QA'})).toBeDisabled();
  await panel.getByRole('checkbox').check();await panel.getByRole('button',{name:'核准此版本 QA'}).click();
  await expect(panel).toContainText('目前版本已由操作者核准');expect(posts).toBe(1);
  approved=false;conflict=true;await panel.getByRole('button',{name:'重新讀取核准狀態'}).click();
  await panel.getByRole('checkbox').check();await panel.getByRole('button',{name:'核准此版本 QA'}).click();
  await expect(panel.getByRole('alert')).toContainText('版本已變更');
  await expect(panel.getByRole('checkbox')).toHaveCount(0);
  await page.setViewportSize({width:390,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
});
