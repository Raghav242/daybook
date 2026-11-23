import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import type { Dashboard, FeatureModule } from '../../shared/api/contracts';
import DashboardView from '.';

const data: Dashboard = {
  today: '2026-11-23', timezone: 'UTC', bill_horizon: '2026-12-23',
  counts: {tasks_today: 0, tasks_overdue: 0, groceries_remaining: 0, bills_overdue: 0},
  tasks: [], agenda: [], upcoming: [], groceries: [], bills: [], bill_totals: {},
  recurring: [
    {kind: 'bill', id: 'b1', title: 'Rent', due_date: '2026-11-20', amount: '900.00', currency: 'USD', overdue: true},
    {kind: 'task', id: 't1', title: 'Laundry', due_date: '2026-11-24', amount: null, currency: null, overdue: false},
  ],
  meals_today: [{id: 'm1', plan_date: '2026-11-23', meal: 'dinner', recipe_id: 'r1', recipe_name: 'Lentil soup', servings: 2, added_to_groceries: false}],
  spending: {month: '2026-11-01', totals: [
    {currency: 'EUR', spent: '12.00', budgeted: '0.00', budgeted_spent: '0.00', remaining: '0.00', unbudgeted: '12.00'},
    {currency: 'USD', spent: '50.00', budgeted: '200.00', budgeted_spent: '50.00', remaining: '150.00', unbudgeted: '0.00'},
  ], expected_bills: []},
};
const view = (enabled_modules: FeatureModule[]) => render(<DashboardView data={data} settings={{timezone: 'UTC', default_currency: 'USD', enabled_modules}} onAdd={vi.fn()} onEdit={vi.fn()} onDelete={vi.fn()} onToggle={vi.fn()} busy={false} />);

test('dashboard shows meals, repeating items and per-currency spending when enabled', () => {
  view(['tasks', 'bills', 'groceries', 'meals', 'budget']);
  expect(screen.getByRole('heading', {name: 'On the table today'})).toBeInTheDocument();
  expect(screen.getByText('Lentil soup')).toBeInTheDocument();
  expect(screen.getByText(/Overdue · Nov 20 · \$900.00/)).toBeInTheDocument();
  expect(screen.getByRole('link', {name: 'Laundry'})).toHaveAttribute('href', '#tasks');
  expect(screen.getByText('€12.00')).toBeInTheDocument();
  expect(screen.getByText('$150.00 left of $200.00')).toBeInTheDocument();
  expect(screen.getByText(/Still due, not yet spent/)).toBeInTheDocument();
});

test('disabled modules are left out of the dashboard', () => {
  view(['tasks']);
  expect(screen.queryByRole('heading', {name: 'On the table today'})).not.toBeInTheDocument();
  expect(screen.queryByText('Money this month')).not.toBeInTheDocument();
  expect(screen.queryByText('Rent')).not.toBeInTheDocument();
  expect(screen.getByRole('link', {name: 'Laundry'})).toBeInTheDocument();
});
