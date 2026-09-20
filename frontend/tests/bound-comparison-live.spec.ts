import {test,expect} from '@playwright/test';

test('真實 Hop 結果的來源證據與舊紀錄區分，不授予 Release',async({page,request})=>{
  const task=process.env.WORKBENCH_BOUND_RESULT_TASK;
  const run=process.env.WORKBENCH_BOUND_RESULT_RUN;
  const project=process.env.WORKBENCH_BOUND_RESULT_PROJECT;
  test.skip(!task||!run||!project,'Requires explicitly selected real Hop evidence; never creates or executes a Run');
  const response=await request.get(`/api/tasks/${task}/runs/${run}/comparisons`);
  expect(response.ok()).toBeTruthy();
  const data=await response.json();
  expect(data.qa_passed).toBe(false);expect(data.release_ready).toBe(false);
  const evidence=data.items.find((item:any)=>item.provenance?.status==='BOUND_PLATFORM_TARGET');
  expect(evidence).toBeTruthy();expect(evidence.evidence.status).toBe('MATCH');
  await page.goto(`/#/projects/${project}/tasks/${task}/execution`);
  const panel=page.getByRole('region',{name:'結果比對證據',exact:true});
  await expect(panel.getByText(/來源已核對（平台管理目標）/)).toBeVisible();
  await expect(page.getByRole('region',{name:'QA 審查紀錄',exact:true})).toContainText('此 Run 尚無 QA 模型審查紀錄');
  await expect(panel.getByRole('region',{name:'結果來源核對'})).toContainText(evidence.provenance.query_checksum);
  await page.setViewportSize({width:390,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2)).toBe(true);
  await page.reload();await expect(panel.getByText(/來源已核對（平台管理目標）/)).toBeVisible();
  await page.getByRole('tab',{name:'交付',exact:true}).click();
  await expect(page.getByRole('link',{name:/Release ZIP/})).toHaveCount(0);
  expect((await request.post(`/api/tasks/${task}/release`)).status()).toBe(409);
});
