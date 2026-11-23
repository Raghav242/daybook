import type { AuthSession, Bill, Budget, BudgetInput, BudgetSummary, Dashboard, Expense, ExpenseInput, GroceryAdditionItem, GroceryAdditionResult, GroceryPreview, MealPlanEntry, MealPlanInput, Module, Page, PayInput, Recipe, RecipeInput, RecordInput, Records, RepeatingModule, Series, SeriesInputs, Settings } from './contracts';

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
const seriesPath: Record<RepeatingModule, string> = { tasks: 'task-series', bills: 'bill-series' };
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

  // Repeating tasks and bills: a definition plus independent occurrence records.
  createSeries: <K extends RepeatingModule>(module: K, value: SeriesInputs[K]) =>
    request<Series<K>>('/' + seriesPath[module], { method: 'POST', body: JSON.stringify(value) }),
  series: <K extends RepeatingModule>(module: K, id: string, signal?: AbortSignal) => request<Series<K>>('/' + seriesPath[module] + '/' + id, { signal }),
  updateFuture: <K extends RepeatingModule>(module: K, occurrenceId: string, value: SeriesInputs[K]) =>
    request<Series<K>>('/' + module + '/' + occurrenceId + '/future', { method: 'PUT', body: JSON.stringify(value) }),
  stopSeries: (module: RepeatingModule, id: string) => request<void>('/' + seriesPath[module] + '/' + id, { method: 'DELETE' }),
  payBill: (id: string, value: PayInput) => request<Bill>('/bills/' + id + '/pay', { method: 'POST', body: JSON.stringify(value) }),

  recipes: (offset = 0, signal?: AbortSignal) => request<Page<Recipe>>('/recipes?' + new URLSearchParams({ offset: String(offset), limit: '100' }), { signal }),
  saveRecipe: (value: RecipeInput, id?: string) => request<Recipe>('/recipes' + (id ? '/' + id : ''), { method: id ? 'PUT' : 'POST', body: JSON.stringify(value) }),
  deleteRecipe: (id: string) => request<void>('/recipes/' + id, { method: 'DELETE' }),
  mealPlan: (start: string, signal?: AbortSignal) => request<MealPlanEntry[]>('/meal-plan?' + new URLSearchParams({ start, days: '7' }), { signal }),
  saveMeal: (value: MealPlanInput, id?: string) => request<MealPlanEntry>('/meal-plan' + (id ? '/' + id : ''), { method: id ? 'PUT' : 'POST', body: JSON.stringify(value) }),
  deleteMeal: (id: string) => request<void>('/meal-plan/' + id, { method: 'DELETE' }),
  groceryPreview: (entryIds: string[], signal?: AbortSignal) => request<GroceryPreview>('/meal-plan/grocery-preview', { method: 'POST', body: JSON.stringify({ entry_ids: entryIds }), signal }),
  addGroceries: (requestId: string, entryIds: string[], items: GroceryAdditionItem[]) =>
    request<GroceryAdditionResult>('/meal-plan/grocery-additions', { method: 'POST', body: JSON.stringify({ request_id: requestId, entry_ids: entryIds, items }) }),

  budgetSummary: (month: string, signal?: AbortSignal) => request<BudgetSummary>('/budget/summary?month=' + month, { signal }),
  expenses: (month: string, offset = 0, signal?: AbortSignal) => request<Page<Expense>>('/expenses?' + new URLSearchParams({ month, offset: String(offset), limit: '25' }), { signal }),
  saveExpense: (value: ExpenseInput, id?: string) => request<Expense>('/expenses' + (id ? '/' + id : ''), { method: id ? 'PUT' : 'POST', body: JSON.stringify(value) }),
  deleteExpense: (id: string) => request<void>('/expenses/' + id, { method: 'DELETE' }),
  budgets: (signal?: AbortSignal) => request<Budget[]>('/budgets', { signal }),
  saveBudget: (value: BudgetInput, id?: string) => request<Budget>('/budgets' + (id ? '/' + id : ''), { method: id ? 'PUT' : 'POST', body: JSON.stringify(value) }),
  deleteBudget: (id: string) => request<void>('/budgets/' + id, { method: 'DELETE' }),
};

