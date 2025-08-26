// Unified API client with basic error handling and abort support
export interface ApiError extends Error { status?: number; }

const DEFAULT_TIMEOUT = 8000;

export async function api<T>(path: string, options: RequestInit = {}, timeout = DEFAULT_TIMEOUT): Promise<T> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await fetch(path.startsWith('http') ? path : `/api${path}`, {
      headers: { 'Content-Type': 'application/json', ...(options.headers||{}) },
      signal: controller.signal,
      ...options,
    });
    if(!res.ok){
      let msg: string;
      try { const data = await res.json(); msg = data.detail || JSON.stringify(data); } catch { msg = res.statusText; }
      const err: ApiError = Object.assign(new Error(msg), { status: res.status });
      throw err;
    }
    if(res.status === 204) return undefined as unknown as T;
    const ct = res.headers.get('content-type') || '';
    if(!ct.includes('application/json')) return (await res.text()) as unknown as T;
    return await res.json();
  } finally { clearTimeout(id); }
}

export function delay(ms: number){ return new Promise(r=> setTimeout(r, ms)); }

export async function retry<T>(fn: ()=>Promise<T>, attempts=3, baseDelay=300): Promise<T> {
  let lastErr: any;
  for(let i=0;i<attempts;i++){
    try { return await fn(); } catch(e){ lastErr=e; await delay(baseDelay * (i+1)); }
  }
  throw lastErr;
}
