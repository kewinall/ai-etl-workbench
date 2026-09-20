// Development renderer; the bundled authoring runtime is not a server dependency.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';

const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
const digest=value=>createHash('sha256').update(value).digest('hex');
const text=value=>{
  if(typeof value!=='string'||value.length>2048||/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(value))throw Error('SDM_CELL_TEXT_INVALID');
  return /^[=+\-@]/.test(value)?"'"+value:value;
};

export function candidateTables(candidate){
  const d=candidate.document;
  if(candidate.status!=='SDM_CANDIDATE_NOT_RELEASED'||candidate.qa_passed!==false||candidate.release_ready!==false||d?.version!==1||d.document_type!=='SDM_CANDIDATE'||digest(JSON.stringify(canonical(d)))!==candidate.checksum)throw Error('SDM_CANDIDATE_INVALID');
  if(d.target.write_mode!=='APPEND'||d.filter_logic!=='ALL'||d.filter_null_policy!=='EXCLUDE_UNKNOWN'||!Array.isArray(d.mappings)||!d.mappings.length||d.mappings.length>128||!Array.isArray(d.filters))throw Error('SDM_POLICY_UNSUPPORTED');
  const operations={DIRECT:'直接對應',GROUP_KEY:'分組欄位',SUM:'加總',COUNT_ROWS:'計算資料筆數',COUNT_NON_NULL:'計算非空值筆數'};
  const mappings=d.mappings.map((m,i)=>{
    if(m.position!==i+1||!operations[m.operation]||!Array.isArray(m.source_columns))throw Error('SDM_MAPPING_INVALID');
    return [i+1,text(m.target_column),text(m.target_type),operations[m.operation],
      text(m.source_columns.map(s=>s.original_name).join('、')),
      text(m.source_columns.length?m.source_columns.map(s=>s.stream_name).join('、'):'整筆資料計數，無單一來源欄位')];
  });
  const rules=[['來源識別',d.source_ref],['目標表',`${d.target.schema}.${d.target.table}`],['寫入模式','APPEND（附加資料）'],
    ['篩選邏輯','ALL（全部成立）；EXCLUDE_UNKNOWN（排除比較結果未知的資料）'],
    ...d.filters.map((f,i)=>[`條件 ${i+1}`,`${f.column} ${f.operator}${f.constant?` ${f.constant.value===''?'空字串':String(f.constant.value)} (${f.constant.type})`:''}`]),
    ...(!d.filters.length?[['篩選條件','無篩選，保留全部來源資料']]:[]),
    ['分組欄位',d.aggregation?(d.aggregation.group_by.join('、')||'無分組欄位（整體聚合）'):'不聚合'],
    ['Run ID',d.run_id],['Naming 版本',String(d.naming.version)],['Naming ID',d.naming.contract_id],
    ['Naming SHA-256',d.naming.checksum],['Specification SHA-256',d.specification_checksum],['SDM SHA-256',candidate.checksum]];
  return {mappings,rules:rules.map(row=>row.map(text))};
}

async function main(){
  const runtime=process.env.WORKBENCH_ARTIFACT_NODE_MODULES;
  if(!runtime)throw Error('WORKBENCH_ARTIFACT_NODE_MODULES_REQUIRED');
  const out=path.resolve(process.argv[2]||'');
  if(!process.argv[2])throw Error('OUTPUT_DIRECTORY_REQUIRED');
  let input='';for await(const chunk of process.stdin){input+=chunk;if(Buffer.byteLength(input)>8*1024*1024)throw Error('SDM_INPUT_TOO_LARGE');}
  const tables=candidateTables(JSON.parse(input));
  const modulePath=createRequire(import.meta.url).resolve('@oai/artifact-tool',{paths:[runtime]});
  const {Workbook,SpreadsheetFile}=await import(pathToFileURL(modulePath).href);
  await fs.mkdir(out,{recursive:true});
  // Refuse overwriting a prior candidate or validation image.
  for(const name of ['SDM-candidate.xlsx','mapping.png','rules.png']){
    try{await fs.access(path.join(out,name));throw Error('SDM_OUTPUT_EXISTS');}catch(e){if(e.code!=='ENOENT')throw e;}
  }
  const book=Workbook.create();
  const mapping=book.worksheets.add('欄位對照'),rules=book.worksheets.add('規則及版本');
  for(const sheet of [mapping,rules])sheet.showGridLines=false;
  mapping.getRange('A2').values=[['SDM 欄位對照']];
  mapping.getRange('A3').values=[['候選文件：未完成 QA，尚不可交付']];
  mapping.getRange('A5:F5').values=[['順序','輸出欄位','目標型別','轉換方式','來源原名','來源英文欄位']];
  mapping.getRangeByIndexes(5,0,tables.mappings.length,6).values=tables.mappings;
  const widths=[8,24,24,24,30,38];
  widths.forEach((w,i)=>mapping.getRangeByIndexes(0,i,tables.mappings.length+5,1).format.columnWidth=w);
  mapping.freezePanes.freezeRows(5);
  rules.getRange('A2').values=[['SDM 規則及版本']];
  rules.getRange('A3').values=[['候選文件：不含執行證據或核准結果']];
  rules.getRange('A5:B5').values=[['項目','已確認規格內容']];
  rules.getRangeByIndexes(5,0,tables.rules.length,2).values=tables.rules;
  rules.getRange(`A1:A${tables.rules.length+5}`).format.columnWidth=28;
  rules.getRange(`B1:B${tables.rules.length+5}`).format.columnWidth=100;
  rules.freezePanes.freezeRows(5);
  for(const [sheet,cols,count] of [[mapping,6,tables.mappings.length],[rules,2,tables.rules.length]]){
    const all=sheet.getRangeByIndexes(0,0,count+5,cols);
    all.format.font={name:'Arial',size:11,color:'#243247'};
    all.format.rowHeight=28;
    sheet.getRange('A2').format.font={name:'Arial',size:15,bold:true,color:'#243247'};
    sheet.getRange('A3').format.font={name:'Arial',size:11,color:'#9C5700'};
    sheet.getRangeByIndexes(4,0,1,cols).format={fill:'#243247',font:{name:'Arial',size:11,color:'#FFFFFF',bold:true}};
    const body=sheet.getRangeByIndexes(5,0,count,cols);
    body.format.wrapText=true;body.format.verticalAlignment='center';body.format.autofitRows();
  }
  book.recalculate();
  console.log((await book.inspect({kind:'table',range:'欄位對照!A5:F8',include:'values,formulas',tableMaxRows:4,tableMaxCols:6,maxChars:1800})).ndjson);
  console.log((await book.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:20},maxChars:1000})).ndjson);
  for(const [sheet,name] of [[mapping,'mapping.png'],[rules,'rules.png']]){
    const preview=await book.render({sheetName:sheet.name,autoCrop:'all',scale:1,format:'png'});
    await fs.writeFile(path.join(out,name),new Uint8Array(await preview.arrayBuffer()));
  }
  const file=await SpreadsheetFile.exportXlsx(book);await file.save(path.join(out,'SDM-candidate.xlsx'));
  console.log('SDM_CANDIDATE_EXPORTED_NOT_RELEASED');
}
if(process.argv[1]&&pathToFileURL(path.resolve(process.argv[1])).href===import.meta.url)await main();
