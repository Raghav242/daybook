import type { AuthSession, Dashboard, Module, Page, RecordInput, Records, Settings } from './contracts';

const apiBase = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
let csrfToken = '';
let authEpoch = 0;
export function clearSession() { csrfToken = ''; authEpoch++; }
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const epoch = authEpoch;
  const headers = new Headers(init?.headers);
  headers.set('Content-Type', 'application/json');
  if (init?.method && !['GET', 'HEAD', 'OPTIONS'].includes(init.method)) headers.set('X-CSRF-Token', csrfToken);
  let response: Response;
  try {
    response = await fetch(apiBase + path, { ...init, headers, credentials: 'include', cache: 'no-store' });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new Error('Could not reach Daybook. Check your connection and try again.');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const details = body.error?.details?.map((d: {field: string; message: string}) => d.field + ': ' + d.message).join(' ');
    if (response.status === 401 && !path.startsWith('/auth/') && epoch === authEpoch) {
      clearSession(); window.dispatchEvent(new Event('daybook:session-expired'));
    }
    throw new ApiError(details || body.error?.message || 'The request failed. Please try again.', response.status);
  }
  return response.status === 204 ? undefined as T : response.json();
}
async function authenticate(mode: 'login' | 'register', username: string, password: string) {
  const csrf = await request<{csrf_token: string}>('/auth/csrf');
  csrfToken = csrf.csrf_token;
  const session = await request<AuthSession>('/auth/' + mode, {method: 'POST', body: JSON.stringify({username, password})});
  clearSession(); csrfToken = session.csrf_token;
  return session;
}
export const api = {
  me: async (signal?: AbortSignal) => {
    const epoch = authEpoch;
    const session = await request<AuthSession>('/auth/me', {signal});
    if (!signal?.aborted && epoch === authEpoch) csrfToken = session.csrf_token;
    return session;
  },
  login: (username: string, password: string) => authenticate('login', username, password),
  register: (username: string, password: string) => authenticate('register', username, password),
  logout: async () => { await request<void>('/auth/logout', {method: 'POST'}); clearSession(); },
  dashboard: (signal?: AbortSignal) => request<Dashboard>('/dashboard', { signal }),
  settings: (signal?: AbortSignal) => request<Settings>('/settings', { signal }),
  updateSettings: (value: Settings) => request<Settings>('/settings', { method: 'PUT', body: JSON.stringify(value) }),
  list: <K extends Module>(module: K, offset = 0, filter = '', signal?: AbortSignal) => {
    const status = { tasks: 'completed', calendar: '', groceries: 'purchased', bills: 'paid' }[module];
    const query = new URLSearchParams({ offset: String(offset), limit: '25' });
    if (status && filter) query.set(status, filter);
    if (module === 'calendar' && filter) query.set('period', filter);
    return request<Page<Records[K]>>('/' + module + '?' + query, { signal });
  },
  save: <K extends Module>(module: K, value: RecordInput, id?: string) =>
    request<Records[K]>('/' + module + (id ? '/' + id : ''), { method: id ? 'PUT' : 'POST', body: JSON.stringify(value) }),
  delete: (module: Module, id: string) => request<void>('/' + module + '/' + id, { method: 'DELETE' }),
};

