import {test,expect} from '@playwright/test';

test('設定讀取失敗顯示原因，可重讀且保留其他元件草稿',async({page})=>{
  let fail=true;
  await page.route('**/api/settings/groups',route=>fail
    ?route.fulfill({status:503,json:{detail:'合成測試服務暫停'}})
    :route.fulfill({json:{values:{ai_provider_model_strategy:{default_profile:'nova-default'},data_connections_targets:{etl_qa:{host:'synthetic-host'}},execution_tool_paths:{}}}}));
  await page.goto('/#/system');
  await expect(page.getByRole('alert').filter({hasText:'平台設定讀取失敗'})).toContainText('合成測試服務暫停');
  await page.getByRole('button',{name:'機密與部署安全',exact:true}).click();
  await page.getByLabel('密碼或 Token',{exact:true}).fill('synthetic-draft');
  fail=false;
  await page.getByRole('button',{name:'重新讀取平台設定',exact:true}).click();
  await expect(page.getByRole('alert').filter({hasText:'平台設定讀取失敗'})).toHaveCount(0);
  await expect(page.getByLabel('密碼或 Token',{exact:true})).toHaveValue('synthetic-draft');
  await page.getByRole('button',{name:'資料連線與目標',exact:true}).click();
  await expect(page.getByLabel('Host',{exact:true})).toHaveValue('synthetic-host');
  await expect(page.getByLabel('Host',{exact:true})).toBeEnabled();
});
