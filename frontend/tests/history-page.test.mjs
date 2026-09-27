import {test} from 'node:test';
import assert from 'node:assert/strict';
import {historyPage} from '../src/workbench/historyPage.ts';
test('history pages preserve all rows without duplication and clamp after filtering',()=>{
  const rows=Array.from({length:57},(_,i)=>({id:i}));
  const pages=[1,2,3].map(page=>historyPage(rows,page));
  assert.deepEqual(pages.map(p=>p.rows.length),[25,25,7]);
  assert.deepEqual(pages.flatMap(p=>p.rows),rows);
  const filtered=historyPage(rows.filter(r=>r.id===56),3);
  assert.equal(filtered.page,1);assert.equal(filtered.rows[0].id,56);
  assert.deepEqual(historyPage([],9),{page:1,pages:1,rows:[],start:0,end:0});
});
