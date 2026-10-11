import {test, expect} from '@playwright/test';
import {authorizationWorkspace} from './fixtures/authorizationWorkspace';

test('Developer 授權、保存回讀、409 與窄版（合成 API，不呼叫模型）', async ({page}) => {
  const fixture=await authorizationWorkspace(page,'design');
  const {task,run}=fixture;
  let saved=false, conflict=false, posts=0;
  await page.route(`**/api/tasks/${task}/runs/${run}/developer**`, async route => {
    if (route.request().method()==='POST') {
      posts++;
      expect(route.request().postDataJSON()).toEqual({confirmed:true, context_checksum:'a'.repeat(64),
        prompt_checksum:'b'.repeat(64), schema_checksum:'c'.repeat(64), model:'copilot/test-model'});
      if (conflict) return route.fulfill({status:409,json:{detail:'版本已變更'}});
      saved=true; return route.fulfill({json:{status:'DEVELOPER_RESERVED'}});
    }
    return route.fulfill({json:{eligible:true, dispatch_enabled:true, matches_current:true,
      context:{context_checksum:'a'.repeat(64)}, prompt_checksum:'b'.repeat(64), schema_checksum:'c'.repeat(64), model:'copilot/test-model',
      invocation:saved?{status:'VALIDATED_NOT_APPROVED',model:'copilot/test-model',proposal:{summary:'合成設計建議',evidence_ids:['requirement']},
        specification:{version:2},usage:{output_tokens:123,ai_credits:0.25}}:null}});
  });
  await page.goto(`${fixture.base}/design/${run}`);
  const panel=page.getByRole('region',{name:'Developer 設計協作',exact:true});
  await expect(panel.getByRole('button',{name:'授權 Developer 設計'})).toBeDisabled();
  await panel.getByRole('checkbox').check(); await panel.getByRole('button',{name:'授權 Developer 設計'}).click();
  await expect(panel).toContainText('合成設計建議'); expect(posts).toBe(1);
  await page.getByRole('button',{name:'重新核對狀態',exact:true}).click();
  await expect(panel).toContainText('規格版本 2 已保存');
  saved=false; conflict=true;
  await page.getByRole('button',{name:'重新核對狀態',exact:true}).click();
  await panel.getByRole('checkbox').check(); await panel.getByRole('button',{name:'授權 Developer 設計'}).click();
  await expect(panel.getByRole('alert')).toContainText('版本已變更');
  await expect(panel.getByRole('checkbox')).toHaveCount(0);
  await page.getByRole('button',{name:'重新核對狀態',exact:true}).click();
  await expect(panel.getByRole('alert')).toContainText('版本已變更');
  await expect(panel.getByRole('checkbox')).toHaveCount(0);
  await panel.getByRole('button',{name:'重試讀取 Developer 狀態',exact:true}).click();
  await expect(panel.getByRole('checkbox')).toBeVisible();
  await expect(panel.getByRole('alert')).toHaveCount(0);
  await page.setViewportSize({width:390,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  expect(posts).toBe(2);
  fixture.assertNoUnexpectedWrites();
});
