import {test,expect} from '@playwright/test';

test('工具路徑讀取可恢復，不完整回讀不可冒充儲存成功',async({page})=>{
  let mode='fail';
  await page.route('**/api/settings/groups',route=>mode==='fail'
    ?route.fulfill({status:503,json:{detail:'合成工具設定讀取失敗'}})
    :route.fulfill({json:{values:mode==='missing'?{}:{execution_tool_paths:{hop_run_path:'/synthetic/hop'}}}}));
  await page.route('**/api/settings/groups/execution_tool_paths',async route=>{
    mode='missing';await route.fulfill({json:{ok:true}});
  });
  await page.goto('/#/system');
  await page.getByRole('button',{name:'執行環境與路徑',exact:true}).click();
  const input=page.getByLabel('Apache Hop 執行檔',{exact:true});
  await expect(input).toBeDisabled();
  await expect(page.getByRole('status').filter({hasText:'合成工具設定讀取失敗'})).toBeVisible();
  mode='ready';await page.getByRole('button',{name:'重新讀取工具路徑',exact:true}).click();
  await expect(input).toHaveValue('/synthetic/hop');await expect(input).toBeEnabled();
  await input.fill('/synthetic/changed');
  await page.getByRole('button',{name:'儲存工具路徑',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'儲存或回讀未完成：工具路徑設定回應不完整'})).toBeVisible();
  await expect(input).toHaveValue('/synthetic/changed');
  await expect(input).toBeEnabled();
  await expect(page.getByText('執行環境設定已儲存並重新讀取',{exact:true})).toHaveCount(0);
});
