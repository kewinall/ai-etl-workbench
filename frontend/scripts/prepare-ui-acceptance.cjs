// Creates genuine Tasks through the deployed website; never approves or executes.
const {chromium,expect}=require('@playwright/test');
const fs=require('fs');
const path=require('path');
const root=path.resolve(__dirname,'../..');
const origin='http://127.0.0.1:5197';
const project=fs.readFileSync(path.join(root,'runtime-temp/ui-accept-project-id.txt'),'utf8').trim();
const cases=[
 {key:'csv',name:'CSV 篩選聚合｜真實新版驗收',file:'filter.csv',table:'ui_accept_csv_20261010',requirement:'六筆 category/amount；amount > 100，NULL 排除。依 category 計算 SUM(amount) 與 COUNT_ROWS，SQL NULL 政策。輸出 category,sum_amount,row_count。APPEND 至新目標；固定標準答案必須在執行前另行核准。'},
 {key:'excel',name:'Excel 篩選聚合｜真實新版驗收',file:'filter.xlsx',table:'ui_accept_excel_20261010',requirement:'Excel 明細工作表，第 2 列標題，空白列 SKIP，缺值 NULL，拒絕公式與額外欄位、不 trim、錯誤 FAIL。amount > 100，NULL 排除；依 category 計算 SUM(amount) 與 COUNT_ROWS，輸出 category,sum_amount,row_count。固定標準答案於執行前另行核准。APPEND 新目標。'},
 {key:'join',name:'雙 CSV LEFT JOIN｜真實新版驗收',table:'ui_accept_join_20261010',requirement:'左表四筆、右表三筆，LEFT 等值 Join：左 id=右 id；NULL 鍵 NEVER_MATCH，重複鍵 EXPAND，CASE_SENSITIVE_NO_TRIM。輸出 source.0.id,source.0.left_value,source.1.id,source.1.right_value；保留未匹配左列與 NULL 左列，固定答案共五列，在執行前另行核准。APPEND 新目標。'}
];
(async()=>{
 const browser=await chromium.launch({headless:true});const results=[];
 try{
  for(const item of cases){
   const page=await browser.newPage();
   const existing=await (await page.request.get(origin+'/api/projects/'+project+'/tasks')).json();
   let task=existing.find(t=>t.name===item.name);
   if(!task){
    await page.goto(origin+'/#/projects/'+project+'/tasks/new');
    if(item.key==='join')await page.getByRole('button',{name:'雙 CSV Join',exact:true}).click();
    await page.getByRole('textbox',{name:'Task 名稱',exact:true}).filter({visible:true}).fill(item.name);
    await page.getByLabel('需求描述',{exact:true}).filter({visible:true}).fill(item.requirement);
    if(item.key==='join'){
     await page.getByLabel('左側 CSV',{exact:true}).setInputFiles(path.join(root,'examples/ui-acceptance/left.csv'));
     await page.getByText(/left\.csv · 2 欄/).waitFor();
     await page.getByLabel('右側 CSV',{exact:true}).setInputFiles(path.join(root,'examples/ui-acceptance/right.csv'));
     await page.getByText(/right\.csv · 2 欄/).waitFor();
     await page.getByLabel('Join 類型',{exact:true}).selectOption('LEFT');
     await page.getByLabel('左側鍵值',{exact:true}).selectOption('id');await page.getByLabel('右側鍵值',{exact:true}).selectOption('id');
     await page.getByRole('checkbox',{name:/我已確認左右來源/}).check();
    }else{
     await page.locator('input[type=file]').filter({visible:true}).setInputFiles(path.join(root,'examples/ui-acceptance',item.file));
     if(item.key==='excel'){
      await page.getByLabel('Excel 標頭列',{exact:true}).fill('2');
      await page.getByRole('button',{name:'解析並確認此工作表',exact:true}).click();
      await page.getByText(/已確認：明細/).waitFor();
     }else await page.getByText('filter.csv',{exact:true}).waitFor();
    }
    await page.getByLabel('Vertica Schema',{exact:true}).filter({visible:true}).fill('ai_sample');
    await page.getByLabel('Vertica Table',{exact:true}).filter({visible:true}).fill(item.table);
    const saved=page.waitForResponse(r=>(r.url().endsWith('/api/projects/'+project+'/tasks')||r.url().endsWith('/api/tasks'))&&r.request().method()==='POST');
    await page.getByRole('button',{name:item.key==='join'?'建立雙 CSV Task':'建立 Task',exact:true}).filter({visible:true}).click();
    const response=await saved;if(!response.ok())throw Error('Task creation failed: '+response.status());task=await response.json();
   }
   await page.goto(origin+'/#/projects/'+project+'/tasks/'+task.id+'/requirements');
   const runs=await (await page.request.get(origin+'/api/tasks/'+task.id+'/runs')).json();
   const secret=await (await page.request.get(origin+'/api/settings/connections/ui-accept-vertica/secret-status')).json();
   if(!runs.runs.length&&secret.secret_configured){await page.getByRole('button',{name:'建立準備版本',exact:true}).click();await page.getByLabel('共用 Run 版本').waitFor();}
   if(secret.secret_configured)await expect(page.getByLabel('共用 Run 版本')).not.toHaveValue('');
   const run=secret.secret_configured?await page.getByLabel('共用 Run 版本').inputValue():null;
   await page.screenshot({path:path.join(root,'runtime-temp/ui-accept-'+item.key+'.png'),fullPage:true});
   results.push({key:item.key,task_id:task.id,run_id:run,target:'ai_sample.'+item.table,url:origin+'/#/projects/'+project+'/tasks/'+task.id+'/requirements'+(run?'/'+run:''),status:run?'AWAITING_HUMAN_INPUT_APPROVAL':'WAITING_ACCEPTANCE_CONNECTION_SECRET'});
   fs.writeFileSync(path.join(root,'docs/verification/ui-acceptance-cases-2026-10-10.json'),JSON.stringify({project_id:project,cases:results,full_chain_accepted:false},null,2));
   await page.close();
  }
  console.log(JSON.stringify(results,null,2));
 }finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exitCode=1});
