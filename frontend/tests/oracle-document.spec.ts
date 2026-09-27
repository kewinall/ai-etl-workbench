import {test,expect} from '@playwright/test';
import {oracleDocument,type OracleColumn} from '../src/workbench/oracleDocument';

const context={specification_checksum:'a'.repeat(64),naming_checksum:'b'.repeat(64),max_rows:10000,max_document_bytes:8*1024*1024};
const columns:OracleColumn[]=[{name:'count',kind:'INTEGER',nullable:false},{name:'amount',kind:'DECIMAL',nullable:false},{name:'label',kind:'TEXT',nullable:true},{name:'active',kind:'BOOLEAN',nullable:false}];
const row=[{value:'9223372036854775807',isNull:false},{value:'12345678901234567890.123456789012345678',isNull:false},{value:'',isNull:false},{value:'false',isNull:false}];

const orderedContext={...context,version:2,comparison:'EXACT_SOURCE_SEQUENCE',ordinal_column:'source_position'};
const orderedColumns:OracleColumn[]=[{name:'record_id',kind:'INTEGER',nullable:false},{name:'source_position',kind:'INTEGER',nullable:false}];
const orderedRows=[['9','1'],['2','2'],['9','3']].map(row=>row.map(value=>({value,isNull:false})));

test('順序答案保留版本、序號與原始列序，不依業務鍵排序',()=>{
  const document=JSON.parse(oracleDocument(orderedContext,orderedColumns,orderedRows));
  expect(document.version).toBe(2);
  expect(document.comparison).toBe('EXACT_SOURCE_SEQUENCE');
  expect(document.ordinal_column).toBe('source_position');
  expect(document.rows).toEqual([{record_id:9,source_position:1},{record_id:2,source_position:2},{record_id:9,source_position:3}]);
  expect(JSON.parse(oracleDocument(context,columns,[]))).not.toHaveProperty('comparison');
});

test('順序答案拒絕錯序、缺序號、NULL、降版與未知版本',()=>{
  expect(()=>oracleDocument(orderedContext,orderedColumns,[...orderedRows].reverse())).toThrow('不會自動排序');
  expect(()=>oracleDocument(orderedContext,orderedColumns,[orderedRows[1]])).toThrow();
  expect(()=>oracleDocument(orderedContext,orderedColumns.slice(0,1),orderedRows)).toThrow();
  expect(()=>oracleDocument(orderedContext,orderedColumns.map(c=>({...c,nullable:true})),orderedRows)).toThrow();
  expect(()=>oracleDocument({...orderedContext,version:1},orderedColumns,orderedRows)).toThrow();
  expect(()=>oracleDocument({...orderedContext,version:3},orderedColumns,orderedRows)).toThrow();
  expect(()=>oracleDocument({...orderedContext,comparison:'EXACT_MULTISET'},orderedColumns,orderedRows)).toThrow();
});

test('答案序列化保留 BIGINT、小數精度及空字串／NULL 差異',()=>{
  const document=oracleDocument(context,columns,[row]);
  expect(document).toContain('"count":9223372036854775807');
  expect(document).toContain('"amount":"12345678901234567890.123456789012345678"');
  expect(document).toContain('"label":"","active":false');
  expect(oracleDocument(context,columns,[row.map((cell,i)=>i===2?{...cell,isNull:true}:cell)])).toContain('"label":null');
  expect(oracleDocument(context,columns,[])).toContain('"rows":[]');
});

test('答案序列化拒絕溢位、科學記號、不明布林及超量',()=>{
  expect(()=>oracleDocument(context,columns,[row.map((cell,i)=>i===0?{...cell,value:'-9223372036854775808'}:cell)])).toThrow();
  for(const [index,value] of [[0,'9223372036854775808'],[0,'1.1'],[1,'1e3'],[3,''] ] as const)
    expect(()=>oracleDocument(context,columns,[row.map((cell,i)=>i===index?{...cell,value}:cell)])).toThrow();
  expect(()=>oracleDocument({...context,max_rows:0},columns,[row])).toThrow();
  expect(()=>oracleDocument({...context,max_document_bytes:20},columns,[row])).toThrow();
});

test('依目標 DDL 拒絕小數四捨五入及 UTF-8 截斷',()=>{
  const bounded={...context,output_types:{amount:'NUMERIC(5,2)',label:'VARCHAR(5)'}};
  const valid=row.map((cell,i)=>i===1?{...cell,value:'001.2300'}:cell);
  expect(()=>oracleDocument(bounded,columns,[valid])).not.toThrow();
  expect(()=>oracleDocument(bounded,columns,[valid.map((cell,i)=>i===1?{...cell,value:'1.234'}:cell)])).toThrow();
  expect(()=>oracleDocument(bounded,columns,[valid.map((cell,i)=>i===2?{...cell,value:'中文'}:cell)])).toThrow();
});
