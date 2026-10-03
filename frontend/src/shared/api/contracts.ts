export type Module = 'tasks' | 'calendar' | 'groceries' | 'bills';
export type View = 'dashboard' | Module | 'settings';
export interface Task { id: string; title: string; notes: string; due_date: string | null; due_at: string | null; priority: 'low' | 'normal' | 'high'; category: string; completed: boolean }
export interface CalendarEntry { id: string; title: string; description: string; start: string; end: string; all_day: boolean; start_date: string | null; end_date: string | null }
export interface Grocery { id: string; name: string; quantity: string; unit: string; category: string; purchased: boolean }
export interface Bill { id: string; name: string; amount: string; currency: string; due_date: string; paid: boolean }
export interface Records { tasks: Task; calendar: CalendarEntry; groceries: Grocery; bills: Bill }
export type RecordItem = Records[Module];
export type RecordInput = Omit<Task, 'id'> | Omit<CalendarEntry, 'id'> | Omit<Grocery, 'id'> | Omit<Bill, 'id'>;
export interface Page<T> { items: T[]; total: number; offset: number; limit: number }
export interface Settings { timezone: string; default_currency: string; enabled_modules: Module[] }
export interface Dashboard {
  today: string; timezone: string; bill_horizon: string;
  counts: { tasks_today: number; tasks_overdue: number; groceries_remaining: number; bills_overdue: number };
  tasks: Task[]; agenda: CalendarEntry[]; upcoming: CalendarEntry[]; groceries: Grocery[]; bills: Bill[]; bill_totals: Record<string, string>;
}

