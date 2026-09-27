import {test, expect} from '@playwright/test';

// Explicit existing evidence only. No model, database write, or fixture mutation.
const taskId = process.env.WORKBENCH_SEMANTIC_TASK;
const runId = process.env.WORKBENCH_SEMANTIC_REJECTED_RUN;
test('已保存語意攔截：歷史版本、節點差異、窄版面及返回（唯讀）', async ({page, request}) => {
  test.skip(!taskId || !runId, '需指定已保存語意攔截的 Task 與 Run；不自建或偽造證據');
  const endpoint = `/api/tasks/${taskId}/runs/${runId}`;
  const before = await (await request.get(endpoint)).json();
  const rejected = before.events.filter((event: any) => event.event_type === 'SPECIFICATION_SEMANTIC_REJECTED');
  expect(rejected).toHaveLength(1);
  expect(before.write_started).toBe(false);
  const task = await (await request.get(`/api/tasks/${taskId}`)).json();
  const errors: string[] = [];
  const mutations: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', req => {if (!['GET', 'HEAD', 'OPTIONS'].includes(req.method())) mutations.push(req.method() + ' ' + new URL(req.url()).pathname)});
  await page.goto(`/#/projects/${task.project_id}/tasks/${taskId}/collaboration`);
  await page.getByLabel('查看協作版本').selectOption(runId!);
  const evidence = page.getByRole('region', {name: '規格語意攔截證據'});
  await expect(evidence).toHaveCount(1);
  await expect(evidence).toContainText('未授權執行');
  for (const issue of rejected[0].event_context.issues) {
    await expect(evidence).toContainText(issue.field_path);
    await expect(evidence).toContainText('節點 ' + issue.node_id);
    await expect(evidence).toContainText('預期 ' + JSON.stringify(issue.expected));
    await expect(evidence).toContainText('實際 ' + JSON.stringify(issue.actual));
  }
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({width, height: 1000});
    await expect(evidence).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2), `${width}px`).toBe(true);
  }
  await page.getByRole('tab', {name: '需求與規格', exact: true}).click();
  await page.goBack();
  await expect(page.getByRole('tab', {name: '協作紀錄', exact: true})).toHaveAttribute('aria-selected', 'true');
  await page.getByLabel('查看協作版本').selectOption(runId!);
  await expect(evidence).toBeVisible();
  const after = await (await request.get(endpoint)).json();
  expect(after.events).toEqual(before.events);
  expect(after.write_started).toBe(false);
  expect(mutations).toEqual([]);
  expect(errors).toEqual([]);
});
