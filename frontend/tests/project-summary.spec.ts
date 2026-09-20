import {test,expect} from '@playwright/test';

test('專案摘要真實空清單與 Task 回讀，錯誤不冒充零筆',async({page,request})=>{
 const project=await(await request.post('/api/projects',{data:{project_name:'摘要驗收-'+Date.now()}})).json();
 await page.goto(`/#/projects/${project.project_id}/settings`);
 const panel=page.getByRole('region',{name:'專案進度摘要'});
 await expect(panel).toContainText('共 0 個 Task');
 const created=await request.post(`/api/projects/${project.project_id}/tasks`,{data:{name:'摘要 Task',requirement:'合成資料只測摘要，不執行 ETL',source_config:{sources:[{type:'CSV',has_actual_data:false,fields:[{name:'id',type:'BIGINT'}]}]},target_schema:'ai_sample',target_table:'summary_only'}});
 expect(created.status()).toBe(201);
 await panel.getByRole('button',{name:'更新專案摘要'}).click();
 await expect(panel).toContainText('共 1 個 Task');
 await expect(panel).toContainText('尚未建立準備版本');
 const api=await(await request.get(`/api/projects/${project.project_id}/summary`)).json();
 expect(api.states).toEqual([{state:'NO_RUN',count:1}]);
 expect(api.release_evaluated).toBe(false);
 await page.route(`**/api/projects/${project.project_id}/summary`,r=>r.fulfill({status:503,json:{detail:{message:'合成摘要暫時失敗'}}}));
 await panel.getByRole('button',{name:'更新專案摘要'}).click();
 await expect(panel.getByRole('alert')).toBeVisible();
 await expect(panel.getByText('共 1 個 Task',{exact:true})).toHaveCount(0);
 await expect(panel.getByText('共 0 個 Task',{exact:true})).toHaveCount(0);
 await page.unroute(`**/api/projects/${project.project_id}/summary`);
 await panel.getByRole('button',{name:'更新專案摘要'}).click();
 await expect(panel).toContainText('共 1 個 Task');
 await page.setViewportSize({width:390,height:1000});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2)).toBe(true);
});
