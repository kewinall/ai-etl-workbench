import {test,expect} from '@playwright/test';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';

test('真實 Excel：原節點、SDM 歷史、核准與正式 ZIP 下載',async({page,request})=>{
  const task=process.env.WORKBENCH_BOUND_RESULT_TASK,run=process.env.WORKBENCH_BOUND_RESULT_RUN,project=process.env.WORKBENCH_BOUND_RESULT_PROJECT;
  test.skip(!task||!run||!project,'Explicit existing synthetic Excel Pilot run required');
  const base=`/api/tasks/${task}/runs/${run}`;
  const before=await(await request.get(base)).json();
  expect(before.run_id).toBe(run);expect(before.write_started).toBe(true);
  const artifacts=await(await request.get(base+'/artifacts')).json();
  expect(artifacts.execution.complete_node_evidence).toBe(true);
  expect(artifacts.nodes.find((n:any)=>n.id==='source').component).toBe('ExcelInput');
  expect(artifacts.nodes).toHaveLength(7);
  for(const node of artifacts.nodes)expect(node.counters.errors).toBe(0);
  const status=await(await request.get(base+'/release')).json();
  expect(status.portability.status).toBe('PASS');
  if(status.status==='AWAITING_RELEASE_APPROVAL')expect(process.env.WORKBENCH_RELEASE_WRITE_CONSENT).toBe('1');
  else expect(status.status).toBe('RELEASE_READY');
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));let posts=0;
  page.on('request',r=>{if(r.method()==='POST'){
    expect(new URL(r.url()).pathname).toBe(base+'/release/approve');posts++;
  }});
  await page.goto(`/#/projects/${project}/tasks/${task}/artifacts`);
  const flow=page.getByRole('region',{name:'版本流程與產物',exact:true});
  await flow.getByLabel('流程版本').selectOption(run!);
  for(const node of artifacts.nodes){
    await flow.getByRole('button').filter({hasText:node.component}).filter({hasText:node.id}).click();
    await expect(flow.getByRole('article',{name:'Run 節點詳細資訊'})).toContainText(node.component);
  }
  await page.getByRole('tab',{name:'交付',exact:true}).click();
  const history=page.getByRole('region',{name:'SDM 候選文件歷史',exact:true});
  await history.getByRole('button',{name:'載入／重新整理 SDM 歷史'}).click();
  await expect(history.getByRole('button',{name:'下載歷史候選 Excel（非 Release）'})).toHaveCount(1);
  const panel=page.getByRole('region',{name:'正式 Release',exact:true});
  if(status.status==='AWAITING_RELEASE_APPROVAL'){
    const save=panel.getByRole('button',{name:'核准並保存正式 Release',exact:true});
    await expect(save).toBeDisabled();await panel.getByRole('checkbox').check();
    await save.click();await expect(panel).toContainText('正式交付已核准');expect(posts).toBe(1);
  }else expect(posts).toBe(0);
  await page.reload();await expect(panel).toContainText('正式交付已核准');
  const saved=await(await request.get(base+'/release')).json();
  expect(saved.status).toBe('RELEASE_READY');expect(saved.release_ready).toBe(true);
  const [download]=await Promise.all([page.waitForEvent('download'),panel.getByRole('link',{name:'下載正式 Release ZIP'}).click()]);
  expect(await download.failure()).toBeNull();
  const bytes=await readFile((await download.path())!);
  expect(createHash('sha256').update(bytes).digest('hex')).toBe(saved.release.checksum);
  expect(bytes.subarray(0,2).toString()).toBe('PK');
  await page.setViewportSize({width:390,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  const after=await(await request.get(base)).json();
  expect(after.events.filter((e:any)=>e.event_type==='WRITE_STARTED')).toEqual(before.events.filter((e:any)=>e.event_type==='WRITE_STARTED'));
  expect(errors).toEqual([]);
});
