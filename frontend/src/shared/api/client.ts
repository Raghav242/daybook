import type { Dashboard, Module, Page, RecordInput, Records, Settings } from './contracts';

const apiBase = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiBase + path, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new Error('Could not reach Daybook. Check that the local server is running and try again.');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const details = body.error?.details?.map((d: {field: string; message: string}) => d.field + ': ' + d.message).join(' ');
    throw new Error(details || body.error?.message || 'The request failed. Please try again.');
  }
  return response.status === 204 ? undefined as T : response.json();
}
export const api = {
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

