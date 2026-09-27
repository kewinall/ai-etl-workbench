import {test} from 'node:test';
import assert from 'node:assert/strict';
import {CreationRequest} from '../src/workbench/creationRequest.ts';
test('retry reuses key; changed content and new form get new keys',()=>{
  let n=0;const create=()=>String(++n);const draft=new CreationRequest(create);
  const first=draft.bind({name:'first',source:{id:1}});
  assert.equal(draft.bind({name:'first',source:{id:1}}).creation_request_key,first.creation_request_key);
  assert.notEqual(draft.bind({name:'second',source:{id:1}}).creation_request_key,first.creation_request_key);
  assert.notEqual(new CreationRequest(create).bind({name:'first',source:{id:1}}).creation_request_key,first.creation_request_key);
});
