import {test,expect} from '@playwright/test';
import {requireDedicatedReconciliationURL as guard} from './fixtures/dedicatedReconciliation';

test('失聯實測前提：明確相同獨立loopback環境才允許接續',()=>{
 for(const port of [5201,5202,5299])expect(()=>guard(`http://127.0.0.1:${port}`,`http://127.0.0.1:${port}/`)).not.toThrow();
});
for(const value of [undefined,'http://127.0.0.1:5183','http://127.0.0.1:5197','http://127.0.0.1:5196',
 'http://127.0.0.1:5199','http://127.0.0.1:5200','http://localhost:5202','https://127.0.0.1:5202',
 'http://user:secret@127.0.0.1:5202','http://127.0.0.1:5202/api','http://127.0.0.1:5202/?x=1',
 'http://127.0.0.1:5202/#unsafe','http://127.0.0.1:5300'])test(`失聯實測拒絕非獨立URL：${value??'missing'}`,()=>{
 expect(()=>guard(value,value)).toThrow();
});
test('失聯實測拒絕選錯環境或漏填明確URL',()=>{
 expect(()=>guard('http://127.0.0.1:5202','http://127.0.0.1:5203')).toThrow(/does not match/);
 expect(()=>guard('http://127.0.0.1:5202',undefined)).toThrow(/required/);
});
