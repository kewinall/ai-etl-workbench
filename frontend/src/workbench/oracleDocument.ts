export type OracleColumn={name:string;kind:'TEXT'|'INTEGER'|'DECIMAL'|'BOOLEAN';nullable:boolean};
export type OracleCell={value:string;isNull:boolean};
export function oracleDocument(context:any,columns:OracleColumn[],rows:OracleCell[][]):string {
  if(rows.length>context.max_rows)throw new Error('答案筆數超過上限');
  const values=rows.map((row,index)=>'{'+columns.map((column,i)=>{
    const cell=row[i];let value:string;
    if(cell.isNull){if(!column.nullable)throw new Error(`${column.name} 未允許 NULL`);value='null'}
    else if(column.kind==='INTEGER'){
      if(!/^-?\d+$/.test(cell.value))throw new Error(`第 ${index+1} 筆 ${column.name} 必須是整數`);
      const integer=BigInt(cell.value);
      if(integer<=-(2n**63n)||integer>2n**63n-1n)throw new Error(`${column.name} 超過 Vertica BIGINT 範圍（最小值保留給 NULL）`);
      value=integer.toString();
    }else if(column.kind==='DECIMAL'){
      if(!/^-?\d+(?:\.\d+)?$/.test(cell.value)||cell.value.length>2048)throw new Error(`第 ${index+1} 筆 ${column.name} 必須是十進位數字（不接受科學記號）`);
      value=JSON.stringify(cell.value);
    }else if(column.kind==='BOOLEAN'){
      if(!['true','false'].includes(cell.value))throw new Error(`${column.name} 請選擇 true 或 false`);
      value=cell.value;
    }else{
      if(cell.value.length>16384)throw new Error(`${column.name} 文字過長`);
      value=JSON.stringify(cell.value);
    }
    const declared=context.output_types?.[column.name];
    if(!cell.isNull&&declared){
      const numeric=/^NUMERIC\((\d+),(\d+)\)$/.exec(declared);
      const varchar=/^VARCHAR\((\d+)\)$/.exec(declared);
      if(numeric){
        const [integer,fraction='']=cell.value.replace(/^-/,'').split('.');
        if(integer.replace(/^0+/,'').length>Number(numeric[1])-Number(numeric[2])||fraction.replace(/0+$/,'').length>Number(numeric[2]))
          throw new Error(`第 ${index+1} 筆 ${column.name} 無法精確存入 ${declared}；不會自動四捨五入`);
      }
      if(varchar&&new TextEncoder().encode(cell.value).length>Number(varchar[1]))
        throw new Error(`第 ${index+1} 筆 ${column.name} 超過 ${declared} 的 UTF-8 位元組上限`);
    }
    return JSON.stringify(column.name)+':'+value;
  }).join(',')+'}');
  const header=JSON.stringify({version:1,specification_checksum:context.specification_checksum,naming_checksum:context.naming_checksum,columns});
  const document=header.slice(0,-1)+',"rows":['+values.join(',')+']}';
  if(new TextEncoder().encode(document).length>context.max_document_bytes)throw new Error('答案文件超過容量上限');
  return document;
}
