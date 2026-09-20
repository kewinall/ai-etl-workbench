import {test,expect} from '@playwright/test';

test('專案清單讀取失敗不是空清單，重試保留新增草稿',async({page})=>{
  let failed=true;
  await page.route('**/api/projects',route=>failed?route.fulfill({status:503,json:{detail:'合成專案服務失敗'}}):route.fulfill({json:[]}));
  await page.goto('/#/projects');
  await expect(page.getByRole('alert').filter({hasText:'專案清單讀取失敗'})).toBeVisible();
  await expect(page.getByText('尚無專案，請先建立第一個專案。',{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'新增專案',exact:true}).click();
  await page.getByLabel('專案名稱',{exact:false}).fill('尚未保存的名稱');
  await page.getByLabel('專案說明',{exact:true}).fill('保留草稿');
  await expect(page.getByRole('button',{name:'重新讀取專案清單'})).toBeVisible();
  failed=false;await page.getByRole('button',{name:'重新讀取專案清單'}).click();
  await expect(page.getByRole('alert').filter({hasText:'專案清單讀取失敗'})).toHaveCount(0);
  await expect(page.getByLabel('專案名稱',{exact:false})).toHaveValue('尚未保存的名稱');
  await expect(page.getByLabel('專案說明',{exact:true})).toHaveValue('保留草稿');
});
