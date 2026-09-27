import {test,expect} from '@playwright/test';
import {validateSdmOrder} from '../src/workbench/sdmOrder';

function document(){return {version:3,source_ref:'source.0',filters:[],aggregation:null,
 source_order:{version:1,source_ref:'source.0',direction:'ASC',semantics:'LOGICAL_CSV_RECORD_POSITION',ordinal_column:'source_position'},
 mappings:[{operation:'SOURCE_ORDINAL',target_column:'source_position',target_type:'BIGINT',source_columns:[]}]};}

test('SDM 顯示接受完整來源序號契約，保留原內容',()=>{
 const value=document(),before=structuredClone(value);
 expect(()=>validateSdmOrder(value)).not.toThrow();expect(value).toEqual(before);
 for(const version of [1,2])expect(()=>validateSdmOrder({version})).not.toThrow();
});

test('SDM 顯示拒絕錯誤或缺少的序號對照',()=>{
 const variants:any[]=[];
 let value:any=document();value.source_order=null;variants.push(value);
 value=document();value.source_order.direction='DESC';variants.push(value);
 value=document();value.mappings=[];variants.push(value);
 value=document();value.mappings[0].target_type='VARCHAR(32)';variants.push(value);
 value=document();value.mappings[0].target_column='record_id';variants.push(value);
 value=document();value.mappings[0].source_columns=[{original_name:'position'}];variants.push(value);
 value=document();value.mappings.push({...value.mappings[0]});variants.push(value);
 value=document();value.filters=[{}];variants.push(value);
 value=document();value.aggregation={};variants.push(value);
 for(const candidate of variants)expect(()=>validateSdmOrder(candidate)).toThrow('來源順序契約');
});
