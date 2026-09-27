import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mergeProjectHistory} from '../src/workbench/projectHistory.ts';
const summary=cases=>({project_id:'p',basis:'ALL_PERSISTED_RUNS',cases});
test('explicit null run is NO_RUN; latest persisted run is retained',()=>{
  const rows=mergeProjectHistory('p',[{id:'a'},{id:'b'}],summary([
    {task_id:'a',run_id:null,state:null},
    {task_id:'b',run_id:'new',state:'FAILED'},
    {task_id:'b',run_id:'old',state:'QUEUED'}]));
  assert.equal(rows[0].display_state,'NO_RUN');
  assert.equal(rows[1].latest_run.run_id,'new');
  assert.equal(rows[1].display_state,'FAILED');
});
test('missing or extra task summary rejects inconsistent reads',()=>{
  assert.throws(()=>mergeProjectHistory('p',[{id:'a'}],summary([])),/更新時間不一致/);
  assert.throws(()=>mergeProjectHistory('p',[],summary([{task_id:'a'}])),/更新時間不一致/);
});
test('missing run state and wrong project never become NO_RUN',()=>{
  assert.throws(()=>mergeProjectHistory('p',[{id:'a'}],summary([{task_id:'a',run_id:'r',state:null}])),/狀態不完整/);
  assert.throws(()=>mergeProjectHistory('other',[],summary([])),/專案不一致/);
});
