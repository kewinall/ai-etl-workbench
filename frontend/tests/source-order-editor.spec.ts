import {test,expect} from '@playwright/test';

test('來源順序修訂與命名互動（攔截写入，不執行 ETL）',async({page,request})=>{
 const task=process.env.WORKBENCH_ORDER_TASK,run=process.env.WORKBENCH_ORDER_RUN,project=process.env.WORKBENCH_ORDER_PROJECT;
 test.skip(!task||!run||!project,'Explicit existing navigation required');
 const backend='http://127.0.0.1:5183';
 const base=`/api/tasks/${task}/runs/${run}`;
 const response=await request.get(backend+base);expect(response.ok()).toBe(true);
 const original=await response.json();
 let revision:any=null;let naming:any=null;let ordered=false;
 const order={version:1,source_ref:'source.0',ordinal_column:'source_position',direction:'ASC',semantics:'LOGICAL_CSV_RECORD_POSITION'};
 const input={...original.input_summary,csv_contract_editable:true,source_order_v1:null,
   transformation_source_refs:['source.0.record_id'],
   transformation_contract_v1:{version:1,filters:[],filter_logic:'ALL',filter_null_policy:'EXCLUDE_UNKNOWN',aggregation:null,output_columns:['source.0.record_id']}};
 const unexpected:string[]=[];
 await page.route('**/api/**',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname===base) return route.fulfill({json:{...original,state:'NEEDS_REVIEW',write_started:false,matches_current:true,
     input_summary:{...input,source_order_v1:ordered?order:null},gate_result:{status:'CHECKED',issues:[]}}});
   if(url.pathname===base+'/revisions'){revision=route.request().postDataJSON();ordered=true;return route.fulfill({json:{run_id:'synthetic-only'}})}
   if(url.pathname===`/api/tasks/${task}/naming-contract/suggest`)return route.fulfill({json:{contract:{columns:[{source_name:'record_id',english_name:'record_id',vertica_type:'BIGINT'}]}}});
   if(url.pathname===`/api/tasks/${task}/naming-contract/confirm`){naming=route.request().postDataJSON();return route.fulfill({json:{version:2,status:'CONFIRMED',checksum:'a'.repeat(64),contract_json:naming}})}
   if(route.request().method()!=='GET'){unexpected.push(url.pathname);return route.fulfill({status:409,json:{detail:'Test write blocked'}})}
   const fetched=await route.fetch({url:backend+url.pathname+url.search});return route.fulfill({response:fetched});
 });
 await page.goto(`/#/projects/${project}/tasks/${task}/requirements`);
 await page.getByRole('button',{name:'補正需求並建立新版',exact:true}).click();
 const form=page.getByRole('form',{name:'需求補正'});
 await form.getByRole('button',{name:'啟用保留來源順序',exact:true}).click();
 await expect(form.getByLabel('來源序號英文欄位')).toHaveValue('source_position');
 await expect(form.getByLabel('輸出欄位 2',{exact:true})).toHaveValue('$source_order.source.0');
 await form.getByRole('button',{name:'新增篩選',exact:true}).click();
 await form.getByLabel('篩選欄位 1',{exact:true}).selectOption('source.0.record_id');
 await form.getByLabel('比較方式 1',{exact:true}).selectOption('IS_NOT_NULL');
 await form.getByRole('button',{name:'保存補正並建立新版',exact:true}).click();
 await expect(page.getByText('保留來源順序須不篩選、不聚合，並在輸出欄位保留來源序號；請先補正轉換意圖。',{exact:true})).toBeVisible();
 expect(revision).toBeNull();
 await form.getByRole('button',{name:'移除篩選 1',exact:true}).click();
 for(const width of [390,768,1440]){await page.setViewportSize({width,height:950});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true)}
 await form.getByRole('button',{name:'保存補正並建立新版',exact:true}).click();
 await expect.poll(()=>revision?.source_order_v1).toEqual(order);
 expect(revision.transformation_contract_v1.output_columns).toEqual(['source.0.record_id','$source_order.source.0']);
 await expect(page.getByRole('region',{name:'來源順序設定',exact:true})).toContainText('source_position');
 const region=page.getByRole('region',{name:'欄位命名確認',exact:true});
 await region.getByRole('button',{name:'取得來源命名建議',exact:true}).click();
 await region.getByRole('button',{name:'加入來源序號命名',exact:true}).click();
 await expect(region.getByLabel('命名來源 2')).toHaveValue('$source_order.source.0');
 await expect(region.getByLabel('命名型別 2')).toHaveValue('BIGINT');
 await expect(region.getByRole('button',{name:'加入來源序號命名',exact:true})).toBeDisabled();
 await region.getByLabel('我已核對原名、英文名稱與型別').check();
 await region.getByRole('button',{name:'確認並保存命名版本',exact:true}).click();
 await expect.poll(()=>naming?.columns.length).toBe(2);
 expect(unexpected).toEqual([]);
});
