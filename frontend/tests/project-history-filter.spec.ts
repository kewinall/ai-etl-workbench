import {test,expect} from '@playwright/test';

test('專案歷史區分失敗與空清單，狀態及文字可交叉篩選',async({page})=>{
  const id='00000000-0000-4000-8000-000000000091';
  await page.route(`**/api/projects/${id}/summary`,route=>route.fulfill({json:{project_id:id,basis:'LATEST_RUN_PER_TASK',task_count:2,states:[{state:'NO_RUN',count:2}],qa_evaluated:false,release_evaluated:false}}));
  await page.route('**/api/projects',route=>route.fulfill({json:[{project_id:id,project_name:'合成歷史專案',description:'',naming_rules:{},default_ai_profile:'',default_connection:''}]}));
  let failed=true;
  await page.route(`**/api/projects/${id}/tasks`,route=>failed
    ?route.fulfill({status:503,json:{detail:'合成歷史服務失敗'}})
    :route.fulfill({json:[{id:'TEST-1',name:'待處理來源',status:'CREATED',source:'CSV',target:'Vertica'},{id:'TEST-2',name:'失敗來源',status:'FAILED',source:'CSV',target:'Vertica'}]}));
  await page.goto(`/#/projects/${id}/history`);
  await expect(page.getByRole('alert')).toContainText('歷史 Task 讀取失敗');
  await expect(page.getByText('此專案尚無 Task，可使用上方「建立 Task」。',{exact:true})).toHaveCount(0);
  failed=false;await page.getByRole('button',{name:'重新讀取歷史 Task',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'顯示 2 / 2 個 Task'})).toBeVisible();
  await page.getByLabel('篩選 Task 狀態',{exact:true}).selectOption('FAILED');
  await expect(page.getByRole('button',{name:/失敗來源/})).toBeVisible();
  await expect(page.getByRole('button',{name:/待處理來源/})).toHaveCount(0);
  await page.getByLabel('搜尋 Task',{exact:true}).fill('TEST-1');
  await expect(page.getByText('沒有符合搜尋或狀態條件的 Task。',{exact:true})).toBeVisible();
  await page.getByLabel('篩選 Task 狀態',{exact:true}).selectOption('');
  await expect(page.getByRole('button',{name:/待處理來源/})).toBeVisible();
  await page.getByRole('button',{name:/待處理來源/}).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${id}/tasks/TEST-1`));
});
