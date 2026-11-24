import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import type { Dashboard, FeatureModule, Task } from '../../shared/api/contracts';
import TodayView from '.';

const task = (id: string, title: string, extra: Partial<Task> = {}): Task => ({id, title, notes: '', due_date: null, due_at: null, priority: 'normal', category_id: null, completed: false, ...extra});
const empty: Dashboard = {
  today: '2026-11-23', timezone: 'UTC', bill_horizon: '2026-12-23', has_records: true,
  counts: {tasks_today: 0, tasks_overdue: 0, tasks_unscheduled: 0, groceries_remaining: 0, bills_overdue: 0},
  overdue_tasks: [], due_today: [], unscheduled: [], upcoming_tasks: [], agenda: [], upcoming: [], groceries: [],
  overdue_bills: [], upcoming_bills: [], bill_totals: {}, meals_today: [], spending: {month: '2026-11-01', totals: [], expected_bills: [], over_budget: []},
};
const full: Dashboard = {
  ...empty,
  counts: {tasks_today: 2, tasks_overdue: 7, tasks_unscheduled: 4, groceries_remaining: 6, bills_overdue: 1},
  overdue_tasks: [task('o1', 'Return library books', {due_date: '2026-11-20'})],
  due_today: [task('d1', 'Submit essay', {due_date: '2026-11-23', category: 'Study'}), task('d2', 'Call the clinic', {due_at: '2026-11-23T15:30:00Z'})],
  unscheduled: [task('u1', 'Sort the photos')],
  upcoming_tasks: [task('r1', 'Laundry', {due_date: '2026-11-30', series_id: 's1'})],
  agenda: [
    {id: 'e2', title: 'Study group', description: 'Chapter 4', start: '2026-11-23T10:00:00Z', end: '2026-11-23T11:00:00Z', all_day: false, start_date: null, end_date: null},
    {id: 'e1', title: 'Holiday market', description: '', start: '2026-11-23T00:00:00Z', end: '2026-11-24T00:00:00Z', all_day: true, start_date: '2026-11-23', end_date: '2026-11-24'},
  ],
  upcoming: [{id: 'e3', title: 'Dentist', description: '', start: '2026-11-24T09:00:00Z', end: '2026-11-24T10:00:00Z', all_day: false, start_date: null, end_date: null}],
  groceries: [{id: 'g1', name: 'Apples', quantity: '6', unit: '', category_id: null, purchased: false}],
  overdue_bills: [{id: 'b1', name: 'Electricity', amount: '42.80', currency: 'USD', due_date: '2026-11-21', paid: false}],
  upcoming_bills: [{id: 'b2', name: 'Internet', amount: '54.99', currency: 'USD', due_date: '2026-11-26', paid: false}],
  meals_today: [{id: 'm1', plan_date: '2026-11-23', meal: 'dinner', recipe_id: 'r1', recipe_name: 'Lentil soup', servings: 2, added_to_groceries: false}],
  spending: {month: '2026-11-01', totals: [
    {currency: 'EUR', income: '0.00', spent: '12.00', net: '-12.00', budgeted: '0.00', budgeted_spent: '0.00', remaining: '0.00', unbudgeted: '12.00'},
    {currency: 'USD', income: '1000.00', spent: '50.00', net: '950.00', budgeted: '40.00', budgeted_spent: '50.00', remaining: '-10.00', unbudgeted: '0.00'},
  ], expected_bills: [{currency: 'USD', amount: '54.99', count: 1}], over_budget: [{category_id: 'c1', category: 'Dining', currency: 'USD', budget_id: 'x', budgeted: '40.00', spent: '50.00', remaining: '-10.00'}]},
};
const all: FeatureModule[] = ['tasks', 'calendar', 'groceries', 'bills', 'meals', 'budget'];
function view(data: Dashboard, enabled_modules = all) {
  const actions = {onAdd: vi.fn(), onEdit: vi.fn(), onDelete: vi.fn(), onToggle: vi.fn(), busy: false};
  render(<TodayView data={data} settings={{timezone: 'UTC', default_currency: 'USD', enabled_modules}} {...actions} />);
  return actions;
}

test('a new account sees one starting state, not a page of empty sections', async () => {
  const actions = view({...empty, has_records: false});
  expect(screen.getByRole('heading', {level: 1, name: 'Today'})).toBeInTheDocument();
  expect(screen.getByText('Monday, November 23')).toBeInTheDocument();
  expect(screen.getAllByRole('heading', {level: 2}).map(h => h.textContent)).toEqual(['Start with one thing']);
  await userEvent.setup().click(screen.getByRole('button', {name: 'Record an expense'}));
  expect(actions.onAdd).toHaveBeenCalledWith('expense');
});

test('a quiet day shows a single schedule line and no attention block', () => {
  view(empty);
  expect(screen.queryByRole('heading', {name: 'Needs attention'})).not.toBeInTheDocument();
  expect(screen.getByText('Nothing scheduled for today.')).toBeInTheDocument();
  expect(screen.queryByRole('heading', {name: 'Coming up'})).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', {name: 'At a glance'})).not.toBeInTheDocument();
});

test('the day combines timed events, timed tasks and date-only items in a readable order', () => {
  view(full);
  const schedule = screen.getByRole('heading', {name: 'Schedule'}).closest('section')!;
  const slots = within(schedule).getAllByRole('listitem').map(li => li.textContent);
  expect(slots[0]).toMatch(/^All day.*Holiday market/);
  expect(slots[1]).toMatch(/^10:00 AM11:00 AM.*Study group/);
  expect(slots[2]).toMatch(/^3:30 PM.*Call the clinic.*Task due/);
  // Date-only tasks are under "Due today" with no invented time.
  expect(within(schedule).getByRole('heading', {name: 'Due today'})).toBeInTheDocument();
  expect(within(schedule).getByRole('button', {name: 'Submit essay'}).closest('li')!.textContent).not.toMatch(/AM|PM/);
  // Unscheduled tasks stay out of the timeline.
  expect(within(schedule).queryByText('Sort the photos')).not.toBeInTheDocument();
  expect(screen.getByRole('heading', {name: 'Anytime'})).toBeInTheDocument();
  expect(screen.getByRole('link', {name: /View all 4/})).toHaveAttribute('href', '#tasks');
});

test('needs attention lists actionable items with links to the rest', () => {
  view(full);
  const attention = screen.getByRole('heading', {name: 'Needs attention'}).closest('section')!;
  expect(within(attention).getByText('Return library books')).toBeInTheDocument();
  expect(within(attention).getByText(/Overdue · Nov 20/)).toBeInTheDocument();
  expect(within(attention).getByText('Electricity')).toBeInTheDocument();
  expect(within(attention).getByRole('link', {name: 'Dining is over budget'})).toHaveAttribute('href', '#money');
  expect(within(attention).getByText('$10.00 over this month')).toBeInTheDocument();
  expect(within(attention).getByRole('link', {name: /All 7 overdue tasks/})).toHaveAttribute('href', '#tasks');
});

test('coming up merges events, repeating tasks and bills; summaries keep currencies apart', () => {
  view(full);
  const upcoming = screen.getByRole('heading', {name: 'Coming up'}).closest('section')!;
  expect(within(upcoming).getAllByRole('listitem').map(li => li.textContent)).toEqual([
    'TomorrowDentist9:00 AM', 'Thu 26InternetBill · $54.99', 'Mon 30LaundryTask',
  ]);
  expect(within(upcoming).getByLabelText('Repeats')).toBeInTheDocument();
  const glance = screen.getByRole('heading', {name: 'At a glance'}).closest('section')!;
  expect(within(glance).getByText('Dinner: Lentil soup')).toBeInTheDocument();
  expect(within(glance).getByText(/6 to buy · Apples/)).toBeInTheDocument();
  expect(within(glance).getByText('€12.00 spent')).toBeInTheDocument();
  expect(within(glance).getByText('$50.00 spent · $1,000.00 received')).toBeInTheDocument();
  expect(within(glance).getByText(/1 unpaid bill · \$54.99 still due/)).toBeInTheDocument();
});

test('disabled modules are left out entirely', () => {
  view(full, ['tasks']);
  expect(screen.queryByText('Holiday market')).not.toBeInTheDocument();
  expect(screen.queryByText('Electricity')).not.toBeInTheDocument();
  expect(screen.queryByText('Dining is over budget')).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', {name: 'At a glance'})).not.toBeInTheDocument();
  expect(screen.getByText('Laundry')).toBeInTheDocument();
});
