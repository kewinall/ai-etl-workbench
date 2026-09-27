import {test,expect} from '@playwright/test';

test('隔離報告入口、固定二十案與列印版面',async({page,request,baseURL})=>{
  test.skip(process.env.WORKBENCH_ALLOW_SYNTHETIC_UI!=='1','Explicit isolated write permission required');
  expect(baseURL).toBe('http://127.0.0.1:5195');
  const created=await request.post('/api/projects',{data:{project_name:`Synthetic report ${Date.now()}`}});
  expect(created.ok()).toBe(true);const project=(await created.json()).project_id;
  const template=await (await request.get(`/api/projects/${project}/pilot-cohort-template`)).json();
  expect((await request.post(`/api/projects/${project}/pilot-cohorts`,{data:template.plan})).ok()).toBe(true);
  await page.goto(`/#/projects/${project}/evaluation`);
  const popup=page.waitForEvent('popup');
  await page.getByRole('link',{name:'開啟可列印成果報告'}).click();
  const report=await popup;await report.waitForLoadState();
  await expect(report.getByRole('heading',{level:1})).toHaveText('Pilot 成果與證據報告');
  await expect(report.locator('article')).toHaveCount(20);
  await expect(report.locator('body')).toContainText('目前可交付 0 / 20');
  await expect(report.locator('body')).toContainText('尚無完整量測');
  await expect(report.locator('body')).toContainText('人工基準：尚未量測');
  await expect(report.locator('body')).toContainText('尚無模型用量紀錄，不推定為零消耗');
  for(const width of [390,768,1440]){
    await report.setViewportSize({width,height:1000});
    expect(await report.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  }
  await report.emulateMedia({media:'print'});
  await expect(report.locator('article')).toHaveCount(20);
  expect(await report.locator('article').first().evaluate(e=>getComputedStyle(e).breakInside)).toBe('avoid');
  await report.screenshot({path:'test-results/pilot-report-print.png',fullPage:true});
  const response=await request.get(`/api/projects/${project}/pilot-report`);
  expect(response.headers()['cache-control']).toBe('no-store');
});

test('Windows HTTP 路徑保留報告原始安全標頭',async({request,baseURL})=>{
  test.skip(process.env.WORKBENCH_ALLOW_SYNTHETIC_UI!=='1','Explicit isolated environment required');
  expect(baseURL).toBe('http://127.0.0.1:5195');
  const projects=await (await request.get('/api/projects')).json();
  const project=projects.find((p:any)=>p.project_name.startsWith('Synthetic report '));
  expect(project).toBeTruthy();
  const response=await request.get(`/api/projects/${project.project_id}/pilot-report`);
  expect(response.status()).toBe(200);
  expect(response.headers()['content-security-policy']).toBe("default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'");
});
