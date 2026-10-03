import { eventLabel, taskDeadline, toggleInput, zonedInstant } from './domain';
import type { Task } from './api/contracts';
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

