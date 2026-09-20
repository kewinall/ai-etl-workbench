import {test,expect} from '@playwright/test';

test('QA 與 Hop 授權需確認、保存後禁止重送（合成 API）',async({page})=>{
  const task=process.env.WORKBENCH_BOUND_RESULT_TASK,run=process.env.WORKBENCH_BOUND_RESULT_RUN,project=process.env.WORKBENCH_BOUND_RESULT_PROJECT;
  test.skip(!task||!run||!project,'Requires existing navigation');
  let qa=false,hop=false,qaPosts=0,hopPosts=0;
  await page.route(`**/api/tasks/${task}/runs/${run}/qa-authorization`,async route=>{
    if(route.request().method()==='POST'){
      qaPosts++;expect(route.request().postDataJSON().confirmed).toBe(true);qa=true;
      return route.fulfill({json:{status:'QA_RESERVED'}});
    }
    return route.fulfill({json:{eligible:true,dispatch_enabled:true,context_checksum:'a'.repeat(64),prompt_checksum:'b'.repeat(64),schema_checksum:'c'.repeat(64),
      comparison_id:'00000000-0000-4000-8000-000000000001',model:'copilot/test',invocation:qa?{status:'QA_RESERVED'}:null}});
  });
  await page.route(`**/api/tasks/${task}/runs/${run}/hop-dispatch`,async route=>{
    if(route.request().method()==='POST'){
      hopPosts++;expect(route.request().postDataJSON().confirmed).toBe(true);hop=true;
      return route.fulfill({json:{status:'QUEUED'}});
    }
    return route.fulfill({json:{dispatch_enabled:true,request:hop?{status:'QUEUED'}:null,
      offer:{specification_id:'00000000-0000-4000-8000-000000000002',binding_checksum:'d'.repeat(64),
        target_schema:'ai_sample',target_table:'synthetic_only',ddl:'CREATE TABLE "ai_sample"."synthetic_only" (id BIGINT);'}}});
  });
  await page.goto(`/#/projects/${project}/tasks/${task}/execution`);
  const qaPanel=page.getByRole('region',{name:'QA 模型呼叫授權',exact:true});
  await expect(qaPanel.getByRole('button',{name:'授權 QA 證據審查'})).toBeDisabled();
  await qaPanel.getByRole('checkbox').check();await qaPanel.getByRole('button',{name:'授權 QA 證據審查'}).click();
  await expect(qaPanel).toContainText('已有 QA 呼叫紀錄');expect(qaPosts).toBe(1);
  await page.getByRole('tab',{name:'需求與規格',exact:true}).click();
  const hopPanel=page.getByRole('region',{name:'Hop 單次執行',exact:true});
  await expect(hopPanel.getByRole('button',{name:'授權並排入 Hop 執行'})).toBeDisabled();
  await hopPanel.getByText('檢視即將執行的建表 DDL').click();await expect(hopPanel.locator('pre')).toContainText('CREATE TABLE');
  await hopPanel.getByRole('checkbox').check();await hopPanel.getByRole('button',{name:'授權並排入 Hop 執行'}).click();
  await expect(hopPanel).toContainText('QUEUED');expect(hopPosts).toBe(1);
  await expect(hopPanel.getByRole('checkbox')).toHaveCount(0);
  await page.setViewportSize({width:390,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
});
