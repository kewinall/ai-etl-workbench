import {test,expect} from '@playwright/test';

test('專案草稿：頁內攔截保留內容，取消變更後才離開',async({page,request})=>{
  const project=await(await request.post('/api/projects',{data:{project_name:`草稿驗證-${Date.now()}`}})).json();
  await page.goto(`/#/projects/${project.project_id}/settings`);
  const description=page.getByLabel('專案說明');
  await description.fill('尚未儲存的測試修改');
  await expect(page.getByText('有未儲存的專案設定')).toBeVisible();
  await page.getByRole('link',{name:'前往平台設定中心'}).click();
  await expect(description).toHaveValue('尚未儲存的測試修改');
  await expect(page).toHaveURL(new RegExp(`/projects/${project.project_id}/settings$`));
  await page.getByRole('tab',{name:'歷史 Task',exact:true}).click();
  await expect(description).toHaveValue('尚未儲存的測試修改');
  await expect(page.getByText('尚未離開：專案設定尚未儲存。請先「儲存設定」或「取消變更」，再選擇目的頁面；目前草稿已保留。')).toBeVisible();
  await page.getByRole('button',{name:'取消變更',exact:true}).click();
  await page.getByRole('tab',{name:'歷史 Task',exact:true}).click();
  await expect(page.getByRole('region',{name:'專案歷史 Task'})).toBeVisible();
  await page.getByRole('tab',{name:'設定',exact:true}).click();
  await expect(description).not.toHaveValue('尚未儲存的測試修改');
  await expect(page.getByText('有未儲存的專案設定')).toHaveCount(0);
  await description.fill('返回與全域導覽測試');
  await page.getByRole('button',{name:'平台設定中心',exact:true}).click();
  await expect(description).toHaveValue('返回與全域導覽測試');
  await page.evaluate(()=>window.history.back());
  await expect(page).toHaveURL(new RegExp(`/projects/${project.project_id}/settings$`));
  await expect(description).toHaveValue('返回與全域導覽測試');
  await page.getByRole('button',{name:'儲存設定',exact:true}).click();
  await expect(page.getByText('有未儲存的專案設定')).toHaveCount(0);
});
