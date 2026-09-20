import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {candidateTables} from './render-candidate.mjs';
const sorted=v=>Array.isArray(v)?v.map(sorted):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,sorted(v[k])])):v;
function fixture(){
 const document={version:1,document_type:'SDM_CANDIDATE',run_id:'synthetic',specification_checksum:'a'.repeat(64),naming:{version:1,contract_id:'synthetic',checksum:'b'.repeat(64)},source_ref:'source.0',target:{schema:'ai_sample',table:'fixture',write_mode:'APPEND'},filter_logic:'ALL',filter_null_policy:'EXCLUDE_UNKNOWN',filters:[],aggregation:null,mappings:[{position:1,target_column:'name',target_type:'VARCHAR(32)',operation:'DIRECT',source_columns:[{original_name:'中文',stream_name:'name'}]}]};
 return sign({status:'SDM_CANDIDATE_NOT_RELEASED',qa_passed:false,release_ready:false,document});
}
function sign(c){c.checksum=createHash('sha256').update(JSON.stringify(sorted(c.document))).digest('hex');return c;}
test('mapping and rules preserve content without mutating candidate',()=>{
 const c=fixture(),before=JSON.stringify(c),result=candidateTables(c);
 assert.deepEqual(result.mappings[0],[1,'name','VARCHAR(32)','直接對應','中文','name']);
 assert.equal(JSON.stringify(c),before);
 assert.ok(result.rules.some(r=>r[1]==='無篩選，保留全部來源資料'));
});
test('formula-like original names remain literal text',()=>{
 for(const prefix of ['=','+','-','@']){
  const c=fixture();c.document.mappings[0].source_columns[0].original_name=prefix+'SUM(1,2)';sign(c);
  assert.equal(candidateTables(c).mappings[0][4],"'"+prefix+'SUM(1,2)');
 }
});
test('changed checksum or false release claims reject',()=>{
 for(const edit of [c=>c.document.target.table='changed',c=>c.qa_passed=true,c=>c.release_ready=true]){
  const c=fixture();edit(c);assert.throws(()=>candidateTables(c),/SDM_CANDIDATE_INVALID/);
 }
});
test('oversized or control-character cells reject, never silently truncate',()=>{
 for(const value of ['x'.repeat(2049),'bad\u0000value']){
  const c=fixture();c.document.mappings[0].source_columns[0].original_name=value;sign(c);
  assert.throws(()=>candidateTables(c),/SDM_CELL_TEXT_INVALID/);
 }
});
