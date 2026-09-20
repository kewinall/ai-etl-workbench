import {test, expect} from '@playwright/test';
import {spawn, ChildProcess} from 'node:child_process';
import {mkdir, writeFile} from 'node:fs/promises';
import path from 'node:path';

test('本機 Worker 觀察模式：網站心跳、正常停止、異常離線與重新啟動', async ({page, request}) => {
  test.skip(process.env.WORKBENCH_TEST_NATIVE_WORKER_LIFECYCLE !== '1', 'Opt-in local Windows/WSL lifecycle test; never dispatches a model');
  test.setTimeout(160000);
  const status = async () => (await (await request.get('/api/runtime/workers')).json()).workers.find((row: any) => row.kind === 'SA_COPILOT');
  test.skip((await status()).active_instances > 0, 'Do not interrupt a pre-existing native worker');
  const root = path.resolve('..');
  await mkdir(test.info().outputDir, {recursive: true});
  let processHandle: ChildProcess | undefined;
  let stopPath = '';
  const start = (name: string) => {
    stopPath = test.info().outputPath(name+'.stop');
    processHandle = spawn(path.join(root, '.venv', 'Scripts', 'python.exe'),
      ['-u', '-m', 'app.local_sa_worker', '--serve', '--stop-file', stopPath],
      {cwd: path.join(root, 'backend'), windowsHide: true, stdio: 'ignore'});
  };
  const stopCleanly = async () => {
    await writeFile(stopPath, 'stop');
    await expect.poll(() => processHandle?.exitCode, {timeout: 45000}).toBe(0);
    await expect.poll(async () => (await status()).status, {timeout: 15000}).toBe('OFFLINE');
  };
  try {
    start('first');
    await expect.poll(async () => (await status()).status, {timeout: 25000}).toBe('ONLINE');
    expect((await status()).can_dispatch).toBe(false);
    await page.goto('/#/system');
    await page.getByRole('button', {name: '執行環境與路徑', exact: true}).click();
    const section = page.getByRole('region', {name: 'Worker 存活狀態', exact: true});
    await expect(section).toContainText('近期有心跳・僅觀察，不派發');
    await page.setViewportSize({width: 390, height: 844});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await stopCleanly();
    await section.getByRole('button', {name: '更新 Worker 狀態'}).click();
    await expect(section.locator('li').filter({hasText: 'Windows Copilot Worker'})).toContainText('離線或已停止');
    start('crash');
    await expect.poll(async () => (await status()).status, {timeout: 25000}).toBe('ONLINE');
    processHandle!.kill(); // Only this test-owned OBSERVE process; no model may be in flight.
    await expect.poll(() => processHandle?.exitCode !== null || processHandle?.signalCode !== null, {timeout: 15000}).toBe(true);
    await expect.poll(async () => (await status()).status, {timeout: 60000}).toBe('OFFLINE');
    start('restart');
    await expect.poll(async () => (await status()).status, {timeout: 25000}).toBe('ONLINE');
    expect((await status()).can_dispatch).toBe(false);
    await stopCleanly();
  } finally {
    if (processHandle?.exitCode === null && processHandle.signalCode === null) {
      await writeFile(stopPath, 'stop');
      await expect.poll(() => processHandle?.exitCode, {timeout: 45000}).toBe(0);
    }
  }
});
