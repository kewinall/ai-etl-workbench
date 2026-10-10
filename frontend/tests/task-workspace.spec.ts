import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';

test('七階段保留舊產物下載與 Release 閘門（隔離 UI，非 Hop E2E）',async({page,request})=>{
 expect((await(await request.get('/api/ready')).json()).execution_enabled).toBe(false);
 const project=await(await request.post('/api/projects',{data:{project_name:'歷史下載回歸-'+Date.now()}})).json();
 const response=await request.post(`/api/projects/${project.project_id}/tasks`,{data:{name:'歷史下載合成案例',requirement:'只測試 UI，不執行 ETL',source_config:{sources:[{type:'CSV',alias:'synthetic',has_actual_data:false,fields:[{name:'customer_id',type:'BIGINT'}]}]},target_schema:'ai_sample',target_table:'ui_only'}});
 expect(response.status()).toBe(201);const task=await response.json(),xml='<pipeline><name>synthetic_ui_only</name></pipeline>';
 await page.route(`**/api/tasks/${task.id}`,route=>route.fulfill({json:{...task,nodes:[{key:'compiler',label:'合成編譯節點',status:'SUCCEEDED',detail:{source_columns:['customer_id']}}],logs:[{node:'compiler',message:'合成歷史事件'}]}}));
 await page.route(`**/api/tasks/${task.id}/history-assets`,route=>route.fulfill({json:{jobs:[{artifact_id:'ui-fixture',name:'synthetic.hpl',version:1,content:xml,download_url:'/api/ui-fixture-download',transforms:[],hops:[]}],sql:[{artifact:'synthetic.hpl',node:'Output',sql:'SELECT customer_id FROM synthetic_ui_only'}],hop_logs:[{log_type:'stdout',log_content:'SYNTHETIC_HOP_LOG_NOT_EXECUTED'}]}}));
 await page.route('**/api/ui-fixture-download',route=>route.fulfill({body:xml,headers:{'Content-Type':'application/xml','Content-Disposition':'attachment; filename="synthetic.hpl"'}}));
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(`/#/projects/${project.project_id}/tasks/${task.id}/artifacts`);
 await expect(page).toHaveURL(/\/results$/);
 await page.getByText('舊版紀錄：Task 節點、Log、Hop、SQL 與下載',{exact:true}).click();
 await page.getByRole('button',{name:/合成編譯節點/}).click();await expect(page.getByRole('region',{name:'舊版節點詳情'})).toContainText('customer_id');
 await page.getByRole('button',{name:'讀取舊版產物'}).click();
 await page.getByText('XML／完整定義',{exact:true}).click();await expect(page.getByText(xml,{exact:true})).toBeVisible();
 const downloaded=page.waitForEvent('download');await page.getByRole('link',{name:'下載舊版 synthetic.hpl'}).click();const download=await downloaded;
 expect(download.suggestedFilename()).toBe('synthetic.hpl');expect(await readFile((await download.path())!,'utf8')).toBe(xml);
 for(const width of [390,768,1440]){await page.setViewportSize({width,height:1000});for(let n=1;n<=7;n++){await page.getByRole('tab',{name:new RegExp(`${n} ·`)}).click();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true)}}
 expect((await request.post(`/api/tasks/${task.id}/release`)).status()).toBe(409);
 expect((await request.get(`/api/tasks/${task.id}/release/legacy/download`)).status()).toBe(409);
 expect(errors).toEqual([]);expect((await(await request.get(`/api/tasks/${task.id}`)).json()).status).toBe('CREATED');
});
