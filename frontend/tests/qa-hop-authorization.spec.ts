import {test,expect} from '@playwright/test';
import {authorizationWorkspace} from './fixtures/authorizationWorkspace';
import {workflowStatus} from './fixtures/workflow';

test('QA 與 Hop 授權需確認、保存後禁止重送（合成 API）',async({page})=>{
  const fixture=await authorizationWorkspace(page,'quality');
  const {task,run}=fixture;
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
  await page.goto(`${fixture.base}/quality/${run}`);
  const qaPanel=page.getByRole('region',{name:'QA 模型呼叫授權',exact:true});
  await expect(qaPanel.getByRole('button',{name:'授權 QA 證據審查'})).toBeDisabled();
  await qaPanel.getByRole('checkbox').check();await qaPanel.getByRole('button',{name:'授權 QA 證據審查'}).click();
  await expect(qaPanel).toContainText('已有 QA 呼叫紀錄');expect(qaPosts).toBe(1);
  await expect(qaPanel.getByRole('checkbox')).toHaveCount(0);
  fixture.setStage('confirm');
  await page.getByRole('tab',{name:/4 · 執行確認/}).click();
  const hopPanel=page.getByRole('region',{name:'Hop 單次執行',exact:true});
  await expect(hopPanel.getByRole('button',{name:'授權並排入 Hop 執行'})).toBeDisabled();
  await hopPanel.getByText('檢視即將執行的建表 DDL').click();await expect(hopPanel.locator('pre')).toContainText('CREATE TABLE');
  await hopPanel.getByRole('checkbox').check();await hopPanel.getByRole('button',{name:'授權並排入 Hop 執行'}).click();
  await expect(hopPanel).toContainText('QUEUED');expect(hopPosts).toBe(1);
  await expect(hopPanel.getByRole('checkbox')).toHaveCount(0);
  await page.setViewportSize({width:390,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  fixture.assertNoUnexpectedWrites();
});

for(const role of ['QA','Hop'])test(`${role} 服務離線顯示原因並禁止授權（合成 API）`,async({page})=>{
  const stage=role==='QA'?'quality':'confirm';
  const fixture=await authorizationWorkspace(page,stage),{task,run}=fixture;
  const status=workflowStatus(task,run,{stage});
  const key=role==='QA'?'qa':'hop',operation=role==='QA'?'qa_authorize':'hop_execute';
  status.operation_qualifications[key]={type:'SAVE',enabled:false,service_ready:false,blocked_reason:'執行服務未就緒；請由服務管理員啟動 '+role+' Worker。'} as any;
  status.operation_qualifications[operation].enabled=false;
  await page.route(`**/api/tasks/${task}/runs/${run}/workflow-status`,r=>r.fulfill({json:status}));
  await page.route(`**/api/tasks/${task}/runs/${run}/${role==='QA'?'qa-authorization':'hop-dispatch'}`,r=>r.fulfill({json:role==='QA'?{
    eligible:true,dispatch_enabled:true,invocation:null,model:'copilot/test',
  }:{dispatch_enabled:true,request:null,offer:{target_schema:'ai_sample',target_table:'synthetic_only',ddl:'test'}}}));
  await page.goto(`${fixture.base}/${stage}/${run}`);
  const panel=page.getByRole('region',{name:role==='QA'?'QA 模型呼叫授權':'Hop 單次執行',exact:true});
  await expect(panel).toContainText('執行服務未就緒');await expect(panel).toContainText('服務管理員');
  await panel.getByRole('checkbox').check();
  await expect(panel.getByRole('button',{name:role==='QA'?'授權 QA 證據審查':'授權並排入 Hop 執行',exact:true})).toBeDisabled();
  fixture.assertNoUnexpectedWrites();
});

test('QA 補證複核綁定前次 invocation，只預約一次新審查、不重跑 Hop（合成 API）',async({page})=>{
  const fixture=await authorizationWorkspace(page,'quality'),{task,run}=fixture;
  const old='00000000-0000-4000-8000-000000000081';let reserved=false,posts=0;
  await page.route(`**/api/tasks/${task}/runs/${run}/qa-authorization`,async route=>{
    if(route.request().method()==='POST'){
      posts++;expect(route.request().postDataJSON()).toMatchObject({confirmed:true,reassess_invocation_id:old,comparison_id:'00000000-0000-4000-8000-000000000082'});
      reserved=true;return route.fulfill({json:{status:'QA_RESERVED'}});
    }
    return route.fulfill({json:{eligible:!reserved,dispatch_enabled:true,
      invocation:{status:reserved?'QA_RESERVED':'VALIDATED_NOT_APPROVED',invocation_id:reserved?'new-synthetic':old},
      reassess_invocation_id:reserved?null:old,comparison_id:'00000000-0000-4000-8000-000000000082',
      context_checksum:'a'.repeat(64),prompt_checksum:'b'.repeat(64),schema_checksum:'c'.repeat(64),model:'copilot/test'}});
  });
  await page.goto(`${fixture.base}/quality/${run}`);
  const panel=page.getByRole('region',{name:'QA 模型呼叫授權',exact:true});
  await expect(panel).toContainText('前次 NEEDS_REVIEW 將永久保留');await expect(panel).toContainText('不重跑 Hop');
  const button=panel.getByRole('button',{name:'授權一次 QA 複核',exact:true});await expect(button).toBeDisabled();
  await panel.getByRole('checkbox').check();await button.click();
  await expect(panel).toContainText('QA_RESERVED');await expect(button).toHaveCount(0);
  await page.reload();await expect(panel).toContainText('QA_RESERVED');await expect(button).toHaveCount(0);
  expect(posts).toBe(1);fixture.assertNoUnexpectedWrites();
});

for(const role of ['QA','Hop'])for(const accepted of [false,true])test(`${role} 回應遺失：已保存=${accepted}，背景讀取保留警示且只提交一次（合成 API）`,async({page})=>{
  const fixture=await authorizationWorkspace(page,role==='QA'?'quality':'confirm');
  const {task,run}=fixture;
  const endpoint=role==='QA'?'qa-authorization':'hop-dispatch';
  let posts=0,reads=0,saved=false;
  await page.route(`**/api/tasks/${task}/runs/${run}/${endpoint}`,async route=>{
    if(route.request().method()==='POST'){
      posts++;saved=accepted;
      expect(route.request().postDataJSON().confirmed).toBe(true);
      return route.abort();
    }
    reads++;
    return route.fulfill({json:role==='QA'?{
      eligible:true,dispatch_enabled:true,context_checksum:'a'.repeat(64),prompt_checksum:'b'.repeat(64),schema_checksum:'c'.repeat(64),
      comparison_id:'00000000-0000-4000-8000-000000000001',model:'copilot/test',invocation:saved?{status:'QA_RESERVED'}:null,
    }:{dispatch_enabled:true,request:saved?{status:'QUEUED'}:null,
      offer:{specification_id:'00000000-0000-4000-8000-000000000002',binding_checksum:'d'.repeat(64),target_schema:'ai_sample',target_table:'synthetic_only',ddl:'CREATE TABLE synthetic_only (id BIGINT);'}}});
  });
  await page.goto(`${fixture.base}/${role==='QA'?'quality':'confirm'}/${run}`);
  const panel=page.getByRole('region',{name:role==='QA'?'QA 模型呼叫授權':'Hop 單次執行',exact:true});
  const submit=panel.getByRole('button',{name:role==='QA'?'授權 QA 證據審查':'授權並排入 Hop 執行',exact:true});
  await expect(submit).toBeDisabled();await panel.getByRole('checkbox').check();await submit.click();
  await expect(panel.getByRole('alert')).toBeVisible();
  const before=reads;await page.getByRole('button',{name:'重新核對狀態',exact:true}).click();
  await expect.poll(()=>reads).toBeGreaterThan(before);
  await expect(panel.getByRole('alert')).toBeVisible();await expect(panel.getByRole('checkbox')).toHaveCount(0);
  await panel.getByRole('button',{name:role==='QA'?'重試讀取 QA 派發條件':'重試讀取 Hop 執行條件',exact:true}).click();
  await expect(panel.getByRole('alert')).toHaveCount(0);
  if(accepted){await expect(panel).toContainText(role==='QA'?'QA_RESERVED':'QUEUED');await expect(submit).toHaveCount(0)}
  else await expect(submit).toBeDisabled();
  await page.reload();
  if(accepted){await expect(panel).toContainText(role==='QA'?'QA_RESERVED':'QUEUED');await expect(submit).toHaveCount(0)}
  else await expect(submit).toBeDisabled();
  expect(posts).toBe(1);fixture.assertNoUnexpectedWrites();
});
