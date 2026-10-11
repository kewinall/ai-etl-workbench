import {test,expect} from '@playwright/test';

test('保存一個 AI Profile 不覆寫另一個草稿（合成 API，無模型呼叫）',async({page})=>{
  let profiles=['draft-a','draft-b'].map(profile_id=>({profile_id,display_name:profile_id,provider_type:'LITELLM_BEDROCK',region:'us-east-1',endpoint:null,enabled:true,updated_at:'2026-10-11T00:00:00Z',model_routes:{requirement_gate:'synthetic',etl_specification:'synthetic',qa_review:'synthetic'}}));
  // Saves are optimistic-concurrency writes: the fixture carries the persisted version the page must send back.
  let releaseSave!:()=>void;
  const saving=new Promise<void>(resolve=>{releaseSave=resolve});
  await page.route('**/api/settings/ai-profiles',route=>route.fulfill({json:profiles}));
  await page.route('**/api/settings/ai-profiles/draft-b',async route=>{
    expect(route.request().method()).toBe('PUT');
    expect(route.request().headers()['x-settings-version']).toBe('2026-10-11T00:00:00Z');
    await saving;
    profiles=profiles.map(p=>p.profile_id==='draft-b'?{...p,...route.request().postDataJSON(),updated_at:'2026-10-11T00:00:01Z'}:p);
    await route.fulfill({json:profiles[1]});
  });
  await page.goto('/#/system');
  const a=page.getByRole('region',{name:'AI Profile draft-a',exact:true});
  const b=page.getByRole('region',{name:'AI Profile draft-b',exact:true});
  await a.getByLabel('AWS Region',{exact:true}).fill('unsaved-region-a');
  await b.getByLabel('AWS Region',{exact:true}).fill('us-west-2');
  await expect(page.getByText('有 2 個 AI Profile 尚未儲存')).toBeVisible();
  await b.getByRole('button',{name:'儲存 AI Profile'}).click();
  await expect(b.getByLabel('AWS Region',{exact:true})).toBeDisabled();
  await expect(b.getByLabel('更新 AI 機密',{exact:true})).toBeDisabled();
  await expect(a.getByLabel('AWS Region',{exact:true})).toBeEnabled();
  releaseSave();
  await expect(b.getByRole('status')).toContainText('已儲存');
  await expect(b.getByLabel('AWS Region',{exact:true})).toBeEnabled();
  await expect(a.getByLabel('AWS Region',{exact:true})).toHaveValue('unsaved-region-a');
  await expect(page.getByText('有 1 個 AI Profile 尚未儲存')).toBeVisible();
  await a.getByRole('button',{name:'取消 AI 變更'}).click();
  await expect(a.getByLabel('AWS Region',{exact:true})).toHaveValue('us-east-1');
});
