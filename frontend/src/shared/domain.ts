import { formatInTimeZone, fromZonedTime } from 'date-fns-tz';
import type { Bill, CalendarEntry, Module, RecordInput, RecordItem, Task } from './api/contracts';

export const moduleNames: Record<Module, string> = { tasks: 'Tasks', calendar: 'Calendar', groceries: 'Groceries', bills: 'Bills' };
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
  if ('completed' in value) value.completed = !value.completed;
  if ('purchased' in value) value.purchased = !value.purchased;
  if ('paid' in value) value.paid = !value.paid;
  return value;
}

