export type Module = 'tasks' | 'calendar' | 'groceries' | 'bills';
/** Settings module keys. "budget" is presented as Money (expenses, income and budgets). */
export type FeatureModule = Module | 'meals' | 'budget';
export type Frequency = 'daily' | 'weekly' | 'monthly';
/** Read-only links to a repeating definition. Echoed back on PUT, ignored by the server. */
export interface OccurrenceLink { series_id?: string | null; occurrence_date?: string | null }

export type CategoryScope = 'task' | 'expense' | 'income' | 'grocery';
export interface Category { id: string; scope: CategoryScope; name: string; archived: boolean }
/** A category reference plus its read-only display name (ignored by the server on writes). */
export interface Categorized { category_id: string | null; category?: string | null }

export interface Task extends OccurrenceLink, Categorized { id: string; title: string; notes: string; due_date: string | null; due_at: string | null; priority: 'low' | 'normal' | 'high'; completed: boolean }
export interface CalendarEntry { id: string; title: string; description: string; start: string; end: string; all_day: boolean; start_date: string | null; end_date: string | null }
export interface Grocery extends Categorized { id: string; name: string; quantity: string; unit: string; purchased: boolean }
export interface Bill extends OccurrenceLink { id: string; name: string; amount: string; currency: string; due_date: string; paid: boolean; expense_id?: string | null }
export interface Records { tasks: Task; calendar: CalendarEntry; groceries: Grocery; bills: Bill }
export type RecordItem = Records[Module];
export type RecordInput = Omit<Task, 'id'> | Omit<CalendarEntry, 'id'> | Omit<Grocery, 'id'> | Omit<Bill, 'id'>;
export interface Page<T> { items: T[]; total: number; offset: number; limit: number }
export interface Settings { timezone: string; default_currency: string; enabled_modules: FeatureModule[] }

export interface Recurrence { frequency: Frequency; interval: number; start_date: string; until_date: string | null }
export interface TaskSeriesInput extends Recurrence { title: string; notes: string; priority: Task['priority']; category_id: string | null }
export interface BillSeriesInput extends Recurrence { name: string; amount: string; currency: string }
export interface SeriesInputs { tasks: TaskSeriesInput; bills: BillSeriesInput }
export type RepeatingModule = keyof SeriesInputs;
export type Series<K extends RepeatingModule> = SeriesInputs[K] & { id: string };
export interface PayInput { paid_on: string; record_expense: boolean; category_id: string | null; note: string }

export interface Ingredient { id?: string; name: string; quantity: string; unit: string; category_id: string | null; category?: string | null }
export interface Recipe { id: string; name: string; servings: number; notes: string; ingredients: Ingredient[] }
export type RecipeInput = Omit<Recipe, 'id'>;
export type Meal = 'breakfast' | 'lunch' | 'dinner' | 'snack';
export interface MealPlanEntry { id: string; plan_date: string; meal: Meal; recipe_id: string; recipe_name: string; servings: number; added_to_groceries: boolean }
export interface MealPlanInput { plan_date: string; meal: Meal; recipe_id: string; servings: number }
export interface PreviewLine { key: string; name: string; unit: string; quantity: string; category_id: string | null; category: string; sources: string[]; other_units: boolean; on_list: string | null }
export interface GroceryPreview { entries: MealPlanEntry[]; items: PreviewLine[]; skipped_entry_ids: string[] }
export interface GroceryAdditionItem { name: string; quantity: string; unit: string; category_id: string | null }
export interface GroceryAdditionResult { request_id: string; created: boolean; added: number }

export interface Expense { id: string; amount: string; currency: string; category_id: string; category: string; spent_on: string; note: string; bill_id: string | null }
export interface ExpenseInput { amount: string; currency: string; category_id: string; spent_on: string; note: string }
export interface Income { id: string; amount: string; currency: string; category_id: string; category: string; received_on: string; note: string }
export interface IncomeInput { amount: string; currency: string; category_id: string; received_on: string; note: string }
export type TransactionKind = 'expense' | 'income';
export interface Transaction { kind: TransactionKind; id: string; amount: string; currency: string; category_id: string; category: string; date: string; note: string; bill_id: string | null }
export interface Budget { id: string; category_id: string; category: string; amount: string; currency: string }
export interface BudgetInput { category_id: string; amount: string; currency: string }
export interface CategoryLine { category_id: string; category: string; currency: string; budget_id: string | null; budgeted: string | null; spent: string; remaining: string | null }
/** One currency's figures. Different currencies are never added together.
 *  `net` is recorded income minus recorded expenses for the month, not a balance. */
export interface CurrencyTotal { currency: string; income: string; spent: string; net: string; budgeted: string; budgeted_spent: string; remaining: string; unbudgeted: string }
export interface ExpectedBills { currency: string; amount: string; count: number }
export interface BudgetSummary { month: string; month_end: string; today: string; categories: CategoryLine[]; totals: CurrencyTotal[]; expected_bills: ExpectedBills[]; unpaid_bills: Bill[] }

export interface Dashboard {
  today: string; timezone: string; bill_horizon: string; has_records: boolean;
  counts: { tasks_today: number; tasks_overdue: number; tasks_unscheduled: number; groceries_remaining: number; bills_overdue: number };
  overdue_tasks: Task[]; due_today: Task[]; unscheduled: Task[]; upcoming_tasks: Task[];
  agenda: CalendarEntry[]; upcoming: CalendarEntry[]; groceries: Grocery[];
  overdue_bills: Bill[]; upcoming_bills: Bill[]; bill_totals: Record<string, string>;
  meals_today: MealPlanEntry[];
  spending: { month: string; totals: CurrencyTotal[]; expected_bills: ExpectedBills[]; over_budget: CategoryLine[] } | null;
}

export interface User { id: string; username: string }
export interface AuthSession { user: User; csrf_token: string }
