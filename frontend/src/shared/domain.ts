import { formatInTimeZone, fromZonedTime } from 'date-fns-tz';
import type { Bill, CalendarEntry, FeatureModule, Frequency, Meal, Module, RecordInput, RecordItem, Recurrence, Task } from './api/contracts';

export const moduleNames: Record<Module, string> = { tasks: 'Tasks', calendar: 'Calendar', groceries: 'Groceries', bills: 'Bills' };
export const featureNames: Record<FeatureModule, string> = { ...moduleNames, meals: 'Meals', budget: 'Money' };
export const recordModules = (enabled: FeatureModule[]) => enabled.filter((m): m is Module => m in moduleNames);
export const singular: Record<Module, string> = { tasks: 'task', calendar: 'event', groceries: 'grocery item', bills: 'bill' };
export const titleOf = (item: RecordItem) => 'title' in item ? item.title : item.name;
export const dateLabel = (value: string, long = false) => new Intl.DateTimeFormat('en-US', {month: long ? 'long' : 'short', day: 'numeric', year: long ? 'numeric' : undefined, timeZone: 'UTC'}).format(new Date(value + 'T12:00:00Z'));
export const timeLabel = (value: string, zone: string) => formatInTimeZone(value, zone, 'h:mm a');
export const localInput = (value: string, zone: string) => formatInTimeZone(value, zone, "yyyy-MM-dd'T'HH:mm");
export const zonedInstant = (value: string, zone: string) => {
  const instant = fromZonedTime(value, zone);
  if (Number.isNaN(instant.getTime()) || localInput(instant.toISOString(), zone) !== value)
    throw new Error('That time does not exist in your timezone. Choose another time.');
  return instant.toISOString();
};
export const money = (amount: string, currency: string) => {
  try { return new Intl.NumberFormat('en-US', {style: 'currency', currency}).format(Number(amount)); }
  catch { return currency + ' ' + amount; }
};
/** "+$12.00" / "−$4.50" for flows; zero has no sign. */
export const signedMoney = (amount: string, currency: string) => {
  const value = Number(amount);
  return (value > 0 ? '+' : value < 0 ? '−' : '') + money(String(Math.abs(value)), currency);
};
/** "Monday, November 23" */
export const longDate = (day: string) => new Intl.DateTimeFormat('en-US', {weekday: 'long', month: 'long', day: 'numeric', timeZone: 'UTC'}).format(new Date(day + 'T12:00:00Z'));
export function taskDeadline(task: Task, zone: string) {
  return task.due_date ? dateLabel(task.due_date) : task.due_at ? formatInTimeZone(task.due_at, zone, 'MMM d · h:mm a') : 'No deadline';
}
export function eventLabel(event: CalendarEntry, zone: string) {
  return event.all_day ? dateLabel(event.start_date!) + ' · All day' : formatInTimeZone(event.start, zone, 'MMM d · h:mm a') + ' – ' + timeLabel(event.end, zone);
}
export function isOverdue(item: Task | Bill, today: string) {
  return item.due_date ? item.due_date < today : 'due_at' in item && item.due_at ? new Date(item.due_at).getTime() < Date.now() : false;
}
export function toggleInput(item: RecordItem): RecordInput {
  const value = { ...item };
  delete (value as Partial<RecordItem>).id;
  for (const key of ['series_id', 'occurrence_date', 'expense_id', 'category']) delete (value as Record<string, unknown>)[key];
  if ('completed' in value) value.completed = !value.completed;
  if ('purchased' in value) value.purchased = !value.purchased;
  if ('paid' in value) value.paid = !value.paid;
  return value;
}


// Calendar-date arithmetic on YYYY-MM-DD strings, independent of the browser timezone.
const utc = (day: string) => new Date(day + 'T12:00:00Z');
export const todayIn = (zone: string) => formatInTimeZone(new Date(), zone, 'yyyy-MM-dd');
export const addDays = (day: string, days: number) => { const d = utc(day); d.setUTCDate(d.getUTCDate() + days); return d.toISOString().slice(0, 10); };
export const weekStart = (day: string) => addDays(day, -((utc(day).getUTCDay() + 6) % 7));
export const weekdayLabel = (day: string) => new Intl.DateTimeFormat('en-US', {weekday: 'short', timeZone: 'UTC'}).format(utc(day));
export const shiftMonth = (month: string, delta: number) => { const d = new Date(month + '-01T12:00:00Z'); d.setUTCMonth(d.getUTCMonth() + delta); return d.toISOString().slice(0, 7); };
export const monthLabel = (month: string) => new Intl.DateTimeFormat('en-US', {month: 'long', year: 'numeric', timeZone: 'UTC'}).format(new Date(month.slice(0, 7) + '-01T12:00:00Z'));
export const quantity = (value: string) => String(Number(value));
export const mealNames: Record<Meal, string> = { breakfast: 'Breakfast', lunch: 'Lunch', dinner: 'Dinner', snack: 'Snack' };
const units: Record<Frequency, [string, string]> = { daily: ['day', 'Daily'], weekly: ['week', 'Weekly'], monthly: ['month', 'Monthly'] };
export function repeatLabel(rule: Recurrence) {
  const [unit, every] = units[rule.frequency];
  const base = rule.interval === 1 ? every : 'Every ' + rule.interval + ' ' + unit + 's';
  return base + (rule.until_date ? ' until ' + dateLabel(rule.until_date) : '');
}
