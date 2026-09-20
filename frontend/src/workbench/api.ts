export async function request<T = any>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    const message = typeof detail === 'string' ? detail : Array.isArray(detail)
      ? detail.map((item: any) => `${item.loc?.slice(1).join('.') || '欄位'}：${item.msg}`).join('；')
      : detail?.message || `請求失敗 (${response.status})`;
    throw new Error(message);
  }
  return body;
}

export function jsonBody(method: string, value: unknown): RequestInit {
  return {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(value)};
}
