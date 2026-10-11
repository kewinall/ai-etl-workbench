const pending = new Set<string>();
// POST endpoints that only compute a preview on the server (no persistence). They must not pass the write gate or
// trigger the workspace "state changed" re-read, which would discard the preview the operator just requested.
const READ_ONLY_POST = [/\/specification\/(compile-preview|validate)$/, /\/requirements\/validate$/, /\/naming-contract\/suggest$/];
export const isReadOnlyPost = (path: string) => READ_ONLY_POST.some(pattern => pattern.test(path.split('?')[0]));
export const evidenceMode=()=>new URLSearchParams(window.location.search).get('evidence')==='pilot';
export function sourcePath(path:string,method='GET') {
  if(!evidenceMode()||!path.startsWith('/api/'))return path;
  if(!['GET','HEAD'].includes(method.toUpperCase()))throw Error('既有真實案例為唯讀來源；不能核准、呼叫模型或執行。');
  return path.startsWith('/api/evidence/')?path:'/api/evidence/pilot'+path.slice(4);
}
export async function request<T = any>(path: string, options?: RequestInit): Promise<T> {
  const mutation = !!options?.method && !['GET','HEAD'].includes(options.method.toUpperCase()) && !isReadOnlyPost(path);
  if (mutation) {
    if (pending.has(path)) throw new Error('此操作正在處理，請等待伺服器結果。');
    if (!window.dispatchEvent(new CustomEvent('workbench:before-write', {cancelable:true, detail:{path}})))
      throw new Error('目前版本或階段資訊不可操作，請先重新核對伺服器狀態。');
    pending.add(path);
  }
  try {
  const response = await fetch(sourcePath(path,options?.method), {...options, cache:'no-store'});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    const message = typeof detail === 'string' ? detail : Array.isArray(detail)
      ? detail.map((item: any) => `${item.loc?.slice(1).join('.') || '欄位'}：${item.msg}`).join('；')
      : detail?.message || `請求失敗 (${response.status})`;
    throw new Error(message);
  }
  return body;
  } finally {
    if (mutation) {
      pending.delete(path);
      window.dispatchEvent(new CustomEvent('workbench:changed', {detail:{path}}));
    }
  }
}

export function jsonBody(method: string, value: unknown): RequestInit {
  return {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(value)};
}
