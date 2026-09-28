import {test,expect} from '@playwright/test';
import {validateSdmExcel} from '../src/workbench/sdmExcel';

export const excelPolicy={version:1,engine:'POI',worksheet:'明細',header_row:2,blank_rows:'SKIP',missing_cells:'NULL',extra_columns:'REJECT',formulas:'REJECT',trim_strings:'NONE',on_error:'FAIL'};
export const excelReference={content_checksum:'a'.repeat(64),profile_checksum:'b'.repeat(64),contract_checksum:'c'.repeat(64)};

test('SDM Excel 顯示保留契約，不將來源確認當作執行',()=>{
  const document={version:4,source_format:'XLSX',source_ref:'source.0',excel_input_contract:excelPolicy,excel_source:excelReference};
  const before=structuredClone(document);
  expect(()=>validateSdmExcel(document)).not.toThrow();expect(document).toEqual(before);
  for(const version of [1,2,3])expect(()=>validateSdmExcel({version})).not.toThrow();
  for(const changes of [{source_format:'CSV'},{excel_source:null},{source_ref:'source.1'},
    {excel_input_contract:{...excelPolicy,on_error:'IGNORE'}},{excel_input_contract:{...excelPolicy,header_row:0}},
    {excel_input_contract:{...excelPolicy,blank_rows:''}},{excel_source:{...excelReference,contract_checksum:'invalid'}}])
    expect(()=>validateSdmExcel({...document,...changes})).toThrow('Excel 來源指紋或讀取契約');
});
