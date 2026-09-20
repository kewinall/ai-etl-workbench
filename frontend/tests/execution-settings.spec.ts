import {test,expect} from '@playwright/test';

test('工具路徑草稿、儲存鎖定、回讀與機密清除（合成 API）',async({page})=>{
  let tools={hop_run_path:'/test/hop',hop_project_path:'/test/project',runtime_temp_path:'/test/tmp'};
  let release!:()=>void; const pending=new Promise<void>(resolve=>{release=resolve});
  await page.route('**/api/settings/groups',route=>route.fulfill({json:{values:{execution_tool_paths:tools}}}));
  await page.route('**/api/settings/groups/execution_tool_paths',async route=>{
    await pending;tools=route.request().postDataJSON();await route.fulfill({json:{ok:true}});
  });
  await page.goto('/#/system');
  await page.getByRole('button',{name:'執行環境與路徑',exact:true}).click();
  const input=page.getByLabel('Apache Hop 執行檔',{exact:true});
  await expect(input).toHaveValue('/test/hop');await input.fill('/test/new-hop');
  page.once('dialog',dialog=>dialog.dismiss());
  await page.locator('.shell > aside nav').getByRole('button',{name:'專案工作區',exact:true}).click();
  await expect(input).toHaveValue('/test/new-hop');
  await page.getByRole('button',{name:'儲存工具路徑',exact:true}).click();
  await expect(input).toBeDisabled();release();
  await expect(page.getByRole('status').filter({hasText:'執行環境設定已儲存並重新讀取'})).toBeVisible();
  await expect(input).toBeEnabled();
  await page.reload();await page.getByRole('button',{name:'執行環境與路徑',exact:true}).click();
  await expect(input).toHaveValue('/test/new-hop');
  await page.getByRole('button',{name:'機密與部署安全',exact:true}).click();
  await page.getByLabel('密碼或 Token',{exact:true}).fill('synthetic-not-a-real-secret');
  page.once('dialog',dialog=>dialog.dismiss());
  await page.locator('.shell > aside nav').getByRole('button',{name:'專案工作區',exact:true}).click();
  await expect(page).toHaveURL(/#\/system$/);
  await page.getByRole('button',{name:'清除未儲存機密'}).click();
  await expect(page.getByLabel('密碼或 Token',{exact:true})).toHaveValue('');
  await page.locator('.shell > aside nav').getByRole('button',{name:'專案工作區',exact:true}).click();
  await expect(page).not.toHaveURL(/#\/system$/);
});
