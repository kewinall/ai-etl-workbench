// Display guard only. Server validation remains authoritative.
export function validateSdmOrder(document:any) {
  if(document.version!==3)return;
  const order=document.source_order;
  const generated=document.mappings?.filter((m:any)=>m.operation==='SOURCE_ORDINAL');
  if(!order||order.version!==1||order.source_ref!=='source.0'||document.source_ref!=='source.0'||
    order.direction!=='ASC'||order.semantics!=='LOGICAL_CSV_RECORD_POSITION'||
    !/^[a-z_][a-z0-9_]{0,62}$/.test(order.ordinal_column||'')||
    !Array.isArray(document.filters)||document.filters.length||document.aggregation!==null||
    generated?.length!==1||generated[0].target_column!==order.ordinal_column||
    generated[0].target_type!=='BIGINT'||!Array.isArray(generated[0].source_columns)||generated[0].source_columns.length)
    throw new Error('SDM 來源順序契約或系統序號對照不完整，請重新核對規格。');
}
