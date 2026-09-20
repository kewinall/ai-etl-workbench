import {test,expect} from '@playwright/test';

test('專案保存期間鎖定基本欄位、預設與字典；完成後可再編輯',async({page,request})=>{
  const response=await request.post('/api/projects',{data:{project_name:'儲存中保護-'+Date.now()}});
  expect(response.status()).toBe(201);
  const project=await response.json();
  await page.goto(`/#/projects/${project.project_id}/settings`);
  await page.getByLabel('專案說明',{exact:true}).fill('延遲保存驗收');
  await page.getByRole('button',{name:'新增對照',exact:true}).click();
  await page.getByLabel('原始名稱 1',{exact:true}).fill('編號');
  await page.getByLabel('英文名稱 1',{exact:true}).fill('id');
  let release!:()=>void;const held=new Promise<void>(resolve=>{release=resolve});
  await page.route(`**/api/projects/${project.project_id}`,async route=>{
    if(route.request().method()==='PUT')await held;
    await route.continue();
  });
  try {
    await page.getByRole('button',{name:'儲存設定',exact:true}).click();
    for(const label of ['專案說明','原始名稱 1','英文名稱 1'])await expect(page.getByLabel(label,{exact:true})).toBeDisabled();
    await expect(page.getByRole('combobox',{name:'預設 AI Profile',exact:true})).toBeDisabled();
    await expect(page.getByRole('combobox',{name:'預設資料連線',exact:true})).toBeDisabled();
    await expect(page.getByRole('button',{name:'新增對照',exact:true})).toBeDisabled();
    await expect(page.getByRole('button',{name:'建立 Task',exact:true})).toBeDisabled();
  }finally{release()}
  await expect(page.getByRole('status').filter({hasText:'已儲存；重新載入後仍可保留設定'})).toBeVisible();
  await expect(page.getByLabel('專案說明',{exact:true})).toBeEnabled();
  const saved=await (await request.get(`/api/projects/${project.project_id}`)).json();
  expect(saved.description).toBe('延遲保存驗收');expect(saved.naming_rules.column_aliases['編號']).toBe('id');
});
