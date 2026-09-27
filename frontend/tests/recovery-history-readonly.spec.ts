import {test, expect} from '@playwright/test';

test('真實失敗與修正歷史、診斷、窄版面及返回（唯讀）', async ({page, request}) => {
  const task = process.env.WORKBENCH_RECOVERY_TASK;
  const failed = process.env.WORKBENCH_RECOVERY_FAILED_RUN;
  const corrected = process.env.WORKBENCH_RECOVERY_CORRECTED_RUN;
  test.skip(!task || !failed || !corrected, '需指定既有真實復原證據，不自建或偽造結果');
  const base = `/api/tasks/${task}/runs/`;
  const before = await (await request.get(base + failed)).json();
  const child = await (await request.get(base + corrected)).json();
  const diagnosis = await (await request.get(base + failed + '/diagnosis')).json();
  const reconciliation = await (await request.get(base + failed + '/reconciliation')).json();
  expect(before.outcome_code).toBe('HOP_EXECUTION_FAILED');
  expect(child.parent_run_id).toBe(failed);
  expect(reconciliation.status).toBe('CLOSED_WITHOUT_RETRY');
  expect(before.events.filter((e:any) => e.event_type === 'WRITE_STARTED')).toHaveLength(1);
  expect(diagnosis.findings.some((f:any) => f.code === 'COLUMN_NOT_FOUND')).toBe(true);
  const project = (await (await request.get(`/api/tasks/${task}`)).json()).project_id;
  const errors:string[] = [], mutations:string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => {if (!['GET','HEAD','OPTIONS'].includes(r.method())) mutations.push(r.method() + ' ' + new URL(r.url()).pathname)});
  await page.goto(`/#/projects/${project}/tasks/${task}/requirements`);
  const versions = page.getByRole('region', {name:'執行準備版本'});
  await versions.getByRole('button').filter({hasText:failed!}).first().click();
  const panel = page.getByRole('region', {name:'失敗診斷證據'});
  await expect(panel).toContainText('程式規則，非 AI');
  for (const finding of diagnosis.findings) await expect(panel).toContainText(finding.line_numbers.join('、'));
  await panel.getByText('日誌證據指紋', {exact:true}).click();
  await expect(panel).toContainText(diagnosis.log_checksum);
  await expect(page.getByRole('region', {name:'執行結果人工核對'})).toContainText('0');
  for (const width of [390,768,1440]) {
    await page.setViewportSize({width,height:1000});
    await expect(panel).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2), `${width}px`).toBe(true);
  }
  await versions.getByRole('button').filter({hasText:corrected!}).first().click();
  await expect(page.getByRole('article', {name:'版本內容'})).toContainText('補正自版本');
  await page.getByRole('tab', {name:'執行與 QA',exact:true}).click();
  await page.getByLabel('標準答案準備版本').selectOption(failed!);
  await expect(panel).toContainText('程式規則，非 AI');
  await page.goBack();
  await expect(page.getByRole('tab', {name:'執行與 QA',exact:true})).toHaveAttribute('aria-selected','true');
  expect((await (await request.get(base + failed)).json()).events).toEqual(before.events);
  expect(mutations).toEqual([]);
  expect(errors).toEqual([]);
});
