export function historyPage<T>(rows:T[],requested:number,size=25){
  if(!Number.isInteger(size)||size<1)throw new Error('Invalid page size');
  const pages=Math.max(1,Math.ceil(rows.length/size));
  const page=Math.min(pages,Math.max(1,Number.isFinite(requested)?Math.floor(requested):1));
  const start=(page-1)*size;
  return {page,pages,rows:rows.slice(start,start+size),start:rows.length?start+1:0,end:Math.min(start+size,rows.length)};
}
