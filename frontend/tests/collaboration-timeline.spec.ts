import {test, expect} from '@playwright/test';
import {routeWorkflow} from './fixtures/workflow';

// Collaboration timeline in the stage workspace: historical event wording, shared refresh and retry on failure.
// Synthetic browser responses only; this is not evidence of a real Run's history.
for (const delivered of [false, true]) test(`時間軸描述當時事件、跟隨共用更新（${delivered ? '已交付' : '未交付'}）`, async ({page, request}) => {
  const project = await (await request.post('/api/projects', {data: {project_name: '時間軸-' + Date.now()}})).json();
  const created = await request.post(`/api/projects/${project.project_id}/tasks`, {data: {name: '時間軸', requirement: 'UI only',
    source_config: {sources: [{type: 'CSV', has_actual_data: false, fields: [{name: 'id', type: 'BIGINT'}]}]}, target_schema: 'ai_sample', target_table: 'ui_only'}});
  expect(created.status()).toBe(201);
  const task = await created.json();
  const runId = '00000000-0000-4000-8000-0000000000c3';
  const base = `**/api/tasks/${task.id}/runs`;
  const at = '2026-10-10T01:00:00Z';
  const events: any[] = [
    {event_id: 1, event_type: 'ENQUEUED', phase: 'PREFLIGHT', created_at: at, event_context: {}},
    {event_id: 2, event_type: 'PIPELINE_NOT_READY', phase: 'REQUIREMENT_GATE', created_at: at, event_context: {}}];
  const run = () => ({run_id: runId, state: delivered ? 'COMPLETED' : 'NEEDS_REVIEW', write_started: delivered, created_at: at,
    input_checksum: 'f'.repeat(64), input_summary: {}, settings_summary: {}, events, matches_current: true, approval: {decision: 'APPROVE'}});
  let saFails = false;
  await page.route(base, route => route.fulfill({json: {runs: [run()]}}));
  await page.route(`${base}/${runId}`, route => route.fulfill({json: run()}));
  await page.route(`${base}/${runId}/sa-invocation`, route => saFails
    ? route.fulfill({status: 503, json: {detail: '合成 SA 紀錄讀取失敗'}}) : route.fulfill({json: {invocation: null}}));
  await page.route(`${base}/${runId}/developer`, route => route.fulfill({json: {invocation: null, eligible: false, dispatch_enabled: false}}));
  await page.route(`${base}/${runId}/qa-review`, route => route.fulfill({json: {invocation: null}}));
  await routeWorkflow(page, task.id, {stage: delivered ? 'delivery' : 'review'});
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`/#/projects/${project.project_id}/tasks/${task.id}/review/${runId}`);
  await page.getByText('審查／修訂時間軸與技術詳情', {exact: true}).click();
  const timeline = page.getByRole('region', {name: '版本協作紀錄'});
  await expect(timeline).toContainText('當時初步需求檢查完成，等待後續審查');
  await expect(timeline).toContainText('PIPELINE_NOT_READY');            // original event code kept in the details
  await expect(timeline).not.toContainText('尚未接通');
  // Normal state: the shared「重新核對狀態」is the only refresh control.
  await expect(timeline.getByRole('button')).toHaveCount(0);
  events.push({event_id: 3, event_type: 'SA_QUEUED', phase: 'REQUIREMENT_GATE', created_at: at, event_context: {}});
  await page.getByRole('button', {name: '重新核對狀態'}).click();
  await expect(timeline).toContainText('人工授權 SA 並排隊');
  // A failed read keeps the last records and offers a keyboard-operable retry.
  saFails = true;
  await expect(page.getByRole('button', {name: '重新核對狀態'})).toBeEnabled();
  await page.getByRole('button', {name: '重新核對狀態'}).click();
  await expect(timeline.getByRole('alert')).toContainText('合成 SA 紀錄讀取失敗');
  await expect(timeline).toContainText('人工授權 SA 並排隊');
  const retry = timeline.getByRole('button', {name: '重試讀取此版本紀錄'});
  saFails = false;
  await retry.focus();
  await page.keyboard.press('Enter');
  await expect(timeline.getByRole('alert')).toHaveCount(0);
  await expect(timeline.getByRole('button')).toHaveCount(0);
  await page.setViewportSize({width: 390, height: 1000});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
  expect(errors).toEqual([]);
});
