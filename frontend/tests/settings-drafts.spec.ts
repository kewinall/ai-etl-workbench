import {test,expect} from '@playwright/test';

test('跨分類保存不覆寫草稿，失敗保留輸入並可取消（合成 API）',async({page})=>{
  const values:any={ai_provider_model_strategy:{default_profile:'nova-default'},data_connections_targets:{etl_qa:{connection_id:'test-vertica',host:'synthetic-host',port:5433,database:'test',user:'test'}},validation_release_policy:{sample_rows:5,require_naming_contract:true},execution_tool_paths:{}};
  let release!:()=>void;const pending=new Promise<void>(resolve=>{release=resolve});
  await page.route('**/api/settings/groups',route=>route.fulfill({json:{values}}));
  await page.route('**/api/settings/groups/validation_release_policy',async route=>{
    await pending;values.validation_release_policy=route.request().postDataJSON();await route.fulfill({json:{ok:true}});
  });
  await page.route('**/api/settings/groups/data_connections_targets',route=>route.fulfill({status:503,json:{detail:'合成測試：暫時無法儲存'}}));
  await page.goto('/#/system');
  await page.getByRole('button',{name:'資料連線與目標',exact:true}).click();
  await page.getByLabel('Host',{exact:true}).fill('unsaved-host');
  await page.getByRole('button',{name:'驗證與交付',exact:true}).click();
  await page.getByLabel('範例資料筆數',{exact:true}).fill('7');
  await page.getByRole('button',{name:'儲存驗證策略',exact:true}).click();
  await expect(page.getByLabel('範例資料筆數',{exact:true})).toBeDisabled();release();
  await expect(page.getByText('設定已儲存並重新讀取',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'資料連線與目標',exact:true}).click();
  await expect(page.getByLabel('Host',{exact:true})).toHaveValue('unsaved-host');
  page.once('dialog',dialog=>dialog.dismiss());
  await page.locator('.shell > aside nav').getByRole('button',{name:'專案工作區',exact:true}).click();
  await expect(page).toHaveURL(/#\/system$/);
  await page.getByRole('button',{name:'儲存資料連線',exact:true}).click();
  await expect(page.getByText('儲存或回讀未完成：合成測試：暫時無法儲存',{exact:true})).toBeVisible();
  await expect(page.getByLabel('Host',{exact:true})).toHaveValue('unsaved-host');
  await expect(page.getByLabel('Host',{exact:true})).toBeEnabled();
  await page.getByRole('button',{name:'取消此分類修改',exact:true}).click();
  await expect(page.getByLabel('Host',{exact:true})).toHaveValue('synthetic-host');
  await expect(page.getByText('有未儲存的平台設定',{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'驗證與交付',exact:true}).click();
  await expect(page.getByLabel('範例資料筆數',{exact:true})).toHaveValue('7');
});
