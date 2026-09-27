import {test,expect} from '@playwright/test';

test('計時檢視：空值、逾時、案例錯配與讀取失敗不可假裝零工時',async({page,request})=>{
  const project=process.env.WORKBENCH_MEASUREMENT_PROJECT;
  test.skip(!project,'Requires explicit existing project for read-only navigation');
  const backend='http://127.0.0.1:5183';
  const response=await request.get(`${backend}/api/projects/${project}/pilot-cohorts`);
  expect(response.ok()).toBe(true);
  const inventory=await response.json(),cohort=inventory.cohorts[0],item=cohort.cases[0];
  let mode='empty';const mutations:string[]=[];const posts:any[]=[],events:any[]=[];
  const path=`/api/projects/${project}/pilot-cohorts/${cohort.cohort_id}/cases/${item.case_key}/effort`;
  await page.route('**/api/**',async route=>{
    const url=new URL(route.request().url());
    if(url.pathname===path&&route.request().method()==='POST'&&mode==='controls'){
      const body=route.request().postDataJSON();posts.push(body);
      if(posts.length===1)return route.fulfill({status:503,json:{detail:'synthetic response uncertainty'}});
      const saved={...body,cohort_id:cohort.cohort_id,case_key:item.case_key,session_id:'synthetic-session',
        sequence:events.length+1,recorded_at:'2026-09-27T12:00:00+08:00'};
      events.push(saved);return route.fulfill({json:saved});
    }
    if(route.request().method()!=='GET'){mutations.push(url.pathname);return route.fulfill({status:409,json:{detail:'Test write blocked'}})}
    if(url.pathname===path){
      if(mode==='error')return route.fulfill({status:503,json:{detail:'計時證據暫時無法讀取；不代表零工時'}});
      return route.fulfill({json:{project_id:mode==='wrong'?'wrong-project':project,cohort_id:cohort.cohort_id,case_key:item.case_key,
        protocol_checksum:'a'.repeat(64),comparison_ready:false,human_recording_enabled:mode==='controls',events,other_case_open:false,
        recovery:mode==='expired'?{status:'EXPIRED_REQUIRES_ABANDON'}:events.length===1?{status:'OPEN_REQUIRES_EXPLICIT_CLOSE',session_id:'synthetic-session'}:null,
        summary:{totals:{WORKBENCH:{recorded_human_seconds:null},MANUAL_BASELINE:{recorded_human_seconds:null}},
          excluded_nonhuman_sessions:0,abandoned_sessions:0}}});
    }
    return route.fulfill({response:await route.fetch({url:backend+url.pathname+url.search})});
  });
  await page.goto(`/#/projects/${project}/evaluation`);
  await page.locator('summary').filter({hasText:`${item.ordinal}. ${item.definition.title}`}).click();
  const region=page.getByRole('region',{name:`案例 ${item.case_key} 操作時間`,exact:true});
  const load=region.getByRole('button',{name:'查看／重新讀取計時紀錄',exact:true});
  await load.click();await expect(region).toContainText('尚無計時事件；不代表零工時。');
  await expect(region).toContainText('工作台真人操作：尚未量測');
  mode='expired';await load.click();await expect(region).toContainText('未結束區間已逾時，必須明確放棄');
  for(const width of [390,768,1440]){
    await page.setViewportSize({width,height:1000});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  }
  mode='wrong';await load.click();await expect(region.getByRole('alert')).toContainText('案例不符');
  await expect(region).not.toContainText('尚無計時事件');
  mode='error';await load.click();await expect(region.getByRole('alert')).toContainText('暫時無法讀取');
  mode='empty';await load.click();await expect(region).toContainText('尚無計時事件');
  mode='controls';await load.click();
  const start=region.getByRole('button',{name:'開始操作區間',exact:true});
  await expect(start).toBeDisabled();
  await region.getByRole('combobox',{name:/^操作者來源/}).selectOption('FUNCTIONAL_TEST');
  await region.getByLabel('我確認操作者來源及區間；本人操作為自行聲明').check();
  await start.click();await expect(region).toContainText('synthetic response uncertainty');
  await page.reload();
  await page.locator('summary').filter({hasText:`${item.ordinal}. ${item.definition.title}`}).click();
  await load.click();
  await region.getByRole('button',{name:'重試原計時請求',exact:true}).click();
  await expect(region.getByRole('button',{name:'結束並保存區間',exact:true})).toBeDisabled();
  expect(posts[0]).toEqual(posts[1]);expect(posts[1].human_attested).toBe(false);
  await region.getByLabel('我確認操作者來源及區間；本人操作為自行聲明').check();
  await region.getByLabel('本段全程主動操作，未含等待或閒置').check();
  await region.getByRole('button',{name:'結束並保存區間',exact:true}).click();
  await expect(start).toBeVisible();
  expect(posts[2].action).toBe('STOP');expect(posts[2].session_id).toBe('synthetic-session');
  expect(events).toHaveLength(2);
  expect(mutations).toEqual([]);
});
