import {test} from 'node:test';
import assert from 'node:assert/strict';
import {OperationLatch} from '../src/workbench/operationLatch.ts';
test('reject concurrent operations until completion or failure releases',async()=>{
  const lock=new OperationLatch();let calls=0;let finish;
  const pending=new Promise(resolve=>finish=resolve);
  async function attempt(){if(!lock.acquire())return;try{calls++;await pending}finally{lock.release()}}
  const first=attempt();await attempt();assert.equal(calls,1);
  finish();await first;assert.equal(lock.acquire(),true);lock.release();
  assert.equal(lock.acquire(),true);try{throw Error('synthetic')}catch{}finally{lock.release()}
  assert.equal(lock.acquire(),true);
});
