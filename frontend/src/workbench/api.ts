const pending = new Set<string>();
export async function request<T = any>(path: string, options?: RequestInit): Promise<T> {
  const mutation = !!options?.method && !['GET','HEAD'].includes(options.method.toUpperCase());
  if (mutation) {
    if (pending.has(path)) throw new Error('此操作正在處理，請等待伺服器結果。');
    if (!window.dispatchEvent(new CustomEvent('workbench:before-write', {cancelable:true, detail:{path}})))
      throw new Error('目前版本或階段資訊不可操作，請先重新核對伺服器狀態。');
    pending.add(path);
  }
  try {
  const response = await fetch(path, {...options, cache:'no-store'});
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
