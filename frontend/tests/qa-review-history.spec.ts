import {test,expect} from '@playwright/test';
import {authorizationWorkspace} from './fixtures/authorizationWorkspace';

test('QA 紀錄的合成狀態、錯誤清除與窄版面，不呼叫模型',async({page})=>{
  const fixture=await authorizationWorkspace(page,'quality');
  const {task,run}=fixture;
  let status='VALIDATED_NOT_APPROVED',fail=false;
  await page.route(`**/api/tasks/${task}/runs/${run}/qa-review`,route=>fail?route.fulfill({status:503,json:{detail:{message:'合成讀取失敗'}}}):route.fulfill({json:{run_id:run,matches_current:status!=='STALE_RESULT_NEEDS_REVIEW',dispatch_available:false,approval_available:false,qa_approved:false,release_ready:false,invocation:{invocation_id:'synthetic-only',status,model:'synthetic-ui-not-called',created_at:'2026-09-13T00:00:00Z',context_checksum:'a'.repeat(64),duration_ms:null,usage:null,context:{specification_checksum:'b'.repeat(64),evidence:[{id:'result_source',status:'PASS',summary:'合成 UI 證據，不是實際模型審查'}]},review:status==='QA_OUTCOME_UNKNOWN'?null:{status:'PASS',summary:'合成 QA 建議',issues:[]}}}}));
  await page.goto(`${fixture.base}/quality/${run}`);
  const panel=page.getByRole('region',{name:'QA 審查紀錄',exact:true});
  await expect(panel).toContainText('合成 QA 建議');await expect(panel).toContainText('未提供');
  status='QA_OUTCOME_UNKNOWN';await page.getByRole('button',{name:'重新核對狀態',exact:true}).click();
  await expect(panel).toContainText('不會自動重送請求');await expect(panel).not.toContainText('合成 QA 建議');
  fail=true;await page.getByRole('button',{name:'重新核對狀態',exact:true}).click();
  await expect(panel.getByRole('alert')).toBeVisible();await expect(panel).not.toContainText('synthetic-ui-not-called');
  await expect(panel.getByRole('button',{name:'重試讀取 QA 審查',exact:true})).toHaveCount(1);
  fail=false;status='STALE_RESULT_NEEDS_REVIEW';await panel.getByRole('button',{name:'重試讀取 QA 審查',exact:true}).click();
  await expect(panel).toContainText('上游已變更');
  await page.setViewportSize({width:390,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2)).toBe(true);
  await expect(panel.getByRole('button',{name:/重試讀取 QA 審查|重新讀取 QA 審查/,exact:true})).toHaveCount(0);
  await expect(panel.getByRole('button',{name:/重試讀取核准狀態|重新讀取核准狀態/,exact:true})).toHaveCount(0);
  fixture.assertNoUnexpectedWrites();
});
