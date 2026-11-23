export type Module = 'tasks' | 'calendar' | 'groceries' | 'bills';
export type FeatureModule = Module | 'meals' | 'budget';
export type View = 'dashboard' | FeatureModule | 'settings';
export type Frequency = 'daily' | 'weekly' | 'monthly';
/** Read-only links to a repeating definition. Echoed back on PUT, ignored by the server. */
export interface OccurrenceLink { series_id?: string | null; occurrence_date?: string | null }
export interface Task extends OccurrenceLink { id: string; title: string; notes: string; due_date: string | null; due_at: string | null; priority: 'low' | 'normal' | 'high'; category: string; completed: boolean }
export interface CalendarEntry { id: string; title: string; description: string; start: string; end: string; all_day: boolean; start_date: string | null; end_date: string | null }
export interface Grocery { id: string; name: string; quantity: string; unit: string; category: string; purchased: boolean }
export interface Bill extends OccurrenceLink { id: string; name: string; amount: string; currency: string; due_date: string; paid: boolean; expense_id?: string | null }
export interface Records { tasks: Task; calendar: CalendarEntry; groceries: Grocery; bills: Bill }
export type RecordItem = Records[Module];
export type RecordInput = Omit<Task, 'id'> | Omit<CalendarEntry, 'id'> | Omit<Grocery, 'id'> | Omit<Bill, 'id'>;
export interface Page<T> { items: T[]; total: number; offset: number; limit: number }
export interface Settings { timezone: string; default_currency: string; enabled_modules: FeatureModule[] }

export interface Recurrence { frequency: Frequency; interval: number; start_date: string; until_date: string | null }
export interface TaskSeriesInput extends Recurrence { title: string; notes: string; priority: Task['priority']; category: string }
export interface BillSeriesInput extends Recurrence { name: string; amount: string; currency: string }
export interface SeriesInputs { tasks: TaskSeriesInput; bills: BillSeriesInput }
export type RepeatingModule = keyof SeriesInputs;
export type Series<K extends RepeatingModule> = SeriesInputs[K] & { id: string };
export interface PayInput { paid_on: string; record_expense: boolean; category: string; note: string }

export interface Ingredient { id?: string; name: string; quantity: string; unit: string; category: string }
export interface Recipe { id: string; name: string; servings: number; notes: string; ingredients: Ingredient[] }
export type RecipeInput = Omit<Recipe, 'id'>;
export type Meal = 'breakfast' | 'lunch' | 'dinner' | 'snack';
export interface MealPlanEntry { id: string; plan_date: string; meal: Meal; recipe_id: string; recipe_name: string; servings: number; added_to_groceries: boolean }
export interface MealPlanInput { plan_date: string; meal: Meal; recipe_id: string; servings: number }
export interface PreviewLine { key: string; name: string; unit: string; quantity: string; category: string; sources: string[]; other_units: boolean; on_list: string | null }
export interface GroceryPreview { entries: MealPlanEntry[]; items: PreviewLine[]; skipped_entry_ids: string[] }
export interface GroceryAdditionItem { name: string; quantity: string; unit: string; category: string }
export interface GroceryAdditionResult { request_id: string; created: boolean; added: number }

export interface Expense { id: string; amount: string; currency: string; category: string; spent_on: string; note: string; bill_id: string | null }
export type ExpenseInput = Omit<Expense, 'id' | 'bill_id'>;
export interface Budget { id: string; category: string; amount: string; currency: string }
export type BudgetInput = Omit<Budget, 'id'>;
export interface CategoryLine { category: string; currency: string; budget_id: string | null; budgeted: string | null; spent: string; remaining: string | null }
/** One currency's figures. Different currencies are never added together. */
export interface CurrencyTotal { currency: string; spent: string; budgeted: string; budgeted_spent: string; remaining: string; unbudgeted: string }
export interface ExpectedBills { currency: string; amount: string; count: number }
export interface BudgetSummary { month: string; month_end: string; today: string; categories: CategoryLine[]; totals: CurrencyTotal[]; expected_bills: ExpectedBills[]; unpaid_bills: Bill[] }

export interface RecurringItem { kind: 'task' | 'bill'; id: string; title: string; due_date: string; amount: string | null; currency: string | null; overdue: boolean }
export interface Dashboard {
  today: string; timezone: string; bill_horizon: string;
  counts: { tasks_today: number; tasks_overdue: number; groceries_remaining: number; bills_overdue: number };
  tasks: Task[]; agenda: CalendarEntry[]; upcoming: CalendarEntry[]; groceries: Grocery[]; bills: Bill[]; bill_totals: Record<string, string>;
  recurring: RecurringItem[]; meals_today: MealPlanEntry[];
  spending: { month: string; totals: CurrencyTotal[]; expected_bills: ExpectedBills[] } | null;
}

export interface User { id: string; username: string }
export interface AuthSession { user: User; csrf_token: string }
