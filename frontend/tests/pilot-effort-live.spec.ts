import {test,expect} from '@playwright/test';

test('隔離真實 API/DB 計時開始結束與中斷放棄',async({page,request,baseURL})=>{
  test.skip(process.env.WORKBENCH_ALLOW_SYNTHETIC_UI!=='1','Explicit isolated write permission required');
  expect(baseURL).toBe('http://127.0.0.1:5195');
  const created=await request.post('/api/projects',{data:{project_name:`Synthetic effort ${Date.now()}`}});
  expect(created.ok()).toBe(true);const project=(await created.json()).project_id;
  const template=await (await request.get(`/api/projects/${project}/pilot-cohort-template`)).json();
  const registered=await request.post(`/api/projects/${project}/pilot-cohorts`,{data:template.plan});
  expect(registered.ok()).toBe(true);const cohort=(await registered.json()).cohort_id;
  const item=template.plan.cases[0],path=`/api/projects/${project}/pilot-cohorts/${cohort}/cases/${item.case_key}/effort`;
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`/#/projects/${project}/evaluation`);
  const expand=async()=>{await page.locator('summary').filter({hasText:`1. ${item.title}`}).click()};
  await expand();
  const region=page.getByRole('region',{name:`案例 ${item.case_key} 操作時間`,exact:true});
  const load=region.getByRole('button',{name:'查看／重新讀取計時紀錄',exact:true});
  await load.click();
  const confirm=()=>region.getByLabel('我確認操作者來源及區間；本人操作為自行聲明').check();
  const start=async()=>{
    await region.getByRole('combobox',{name:/^操作者來源/}).selectOption('FUNCTIONAL_TEST');await confirm();
    await region.getByRole('button',{name:'開始操作區間',exact:true}).click();
    await expect(region.getByRole('button',{name:'放棄本區間',exact:true})).toBeVisible();
  };
  await start();await confirm();
  await region.getByLabel('本段全程主動操作，未含等待或閒置').check();
  await region.getByRole('button',{name:'結束並保存區間',exact:true}).click();
  await expect(region).toContainText('代理／功能測試區間：1 段');
  await start();
  await page.evaluate(()=>window.dispatchEvent(new Event('offline')));
  await page.reload();await expand();await load.click();await confirm();
  await region.getByLabel('本段全程主動操作，未含等待或閒置').check();
  await expect(region.getByRole('button',{name:'結束並保存區間',exact:true})).toBeDisabled();
  await region.getByRole('button',{name:'放棄本區間',exact:true}).click();
  await expect(region).toContainText('放棄區間：1 段');
  const saved=await (await request.get(path)).json();
  expect(saved.events.map((e:any)=>e.action)).toEqual(['START','STOP','START','ABANDON']);
  expect(saved.events.every((e:any)=>e.actor==='FUNCTIONAL_TEST')).toBe(true);
  expect(saved.summary.totals.WORKBENCH.recorded_human_seconds).toBeNull();
  expect(saved.recovery).toBeNull();expect(saved.comparison_ready).toBe(false);
  for(const width of [390,768,1440]){
    await page.setViewportSize({width,height:1000});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  }
  expect(errors).toEqual([]);
});
