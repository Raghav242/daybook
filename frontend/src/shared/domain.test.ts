import { addDays, eventLabel, repeatLabel, shiftMonth, taskDeadline, toggleInput, weekStart, zonedInstant } from './domain';
import type { Bill, Task } from './api/contracts';
test('date-only deadlines do not shift across timezones', () => {
  const task: Task = {id: '1', title: 'Essay', notes: '', due_date: '2026-10-02', due_at: null, priority: 'normal', category: '', completed: false};
  expect(taskDeadline(task, 'Pacific/Honolulu')).toBe('Oct 2');
  expect(taskDeadline(task, 'Asia/Tokyo')).toBe('Oct 2');
  expect(toggleInput(task)).toEqual({...task, id: undefined, completed: true});
});
test('timed deadlines convert from the configured timezone and reject missing DST times', () => {
  expect(zonedInstant('2026-10-02T10:00', 'America/New_York')).toBe('2026-10-02T14:00:00.000Z');
  expect(() => zonedInstant('2026-03-08T02:30', 'America/New_York')).toThrow('does not exist');
});
test('all-day event date stays fixed when the timezone changes', () => {
  expect(eventLabel({id: '1', title: 'Holiday', description: '', start: '2026-10-01T22:00:00Z', end: '2026-10-02T22:00:00Z', all_day: true, start_date: '2026-10-02', end_date: '2026-10-03'}, 'America/Los_Angeles')).toBe('Oct 2 · All day');
});

test('calendar-date helpers do not depend on the browser timezone', () => {
  expect(addDays('2026-02-28', 1)).toBe('2026-03-01');
  expect(addDays('2024-02-28', 1)).toBe('2024-02-29');
  expect(weekStart('2026-11-29')).toBe('2026-11-23'); // Sunday belongs to the week starting Monday
  expect(weekStart('2026-11-23')).toBe('2026-11-23');
  expect(shiftMonth('2026-12', 1)).toBe('2027-01');
  expect(shiftMonth('2026-01', -1)).toBe('2025-12');
  expect(repeatLabel({frequency: 'monthly', interval: 1, start_date: '2026-01-31', until_date: null})).toBe('Monthly');
  expect(repeatLabel({frequency: 'weekly', interval: 2, start_date: '2026-01-31', until_date: '2026-06-01'})).toBe('Every 2 weeks until Jun 1');
});
test('status toggles never send read-only recurrence or expense links', () => {
  const bill: Bill = {id: 'b', name: 'Rent', amount: '1.00', currency: 'USD', due_date: '2026-11-01', paid: true, series_id: 's', occurrence_date: '2026-11-01', expense_id: null};
  expect(toggleInput(bill)).toEqual({name: 'Rent', amount: '1.00', currency: 'USD', due_date: '2026-11-01', paid: false});
});
