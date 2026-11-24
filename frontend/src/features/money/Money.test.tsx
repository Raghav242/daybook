import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { api } from '../../shared/api/client';
import type { BudgetSummary, Page, Transaction } from '../../shared/api/contracts';
import { renderWithCategories } from '../../test-utils';
import { MoneyOverview, TransactionsView } from '.';

const summary: BudgetSummary = {
  month: '2026-11-01', month_end: '2026-11-30', today: '2026-11-23',
  categories: [
    {category_id: 'dining', category: 'Dining', currency: 'USD', budget_id: 'b1', budgeted: '40.00', spent: '54.50', remaining: '-14.50'},
    {category_id: 'gifts', category: 'Gifts', currency: 'USD', budget_id: null, budgeted: null, spent: '20.00', remaining: null},
    {category_id: 'dining', category: 'Dining', currency: 'EUR', budget_id: null, budgeted: null, spent: '9.00', remaining: null},
  ],
  totals: [
    {currency: 'EUR', income: '0.00', spent: '9.00', net: '-9.00', budgeted: '0.00', budgeted_spent: '0.00', remaining: '0.00', unbudgeted: '9.00'},
    {currency: 'USD', income: '1200.00', spent: '74.50', net: '1125.50', budgeted: '40.00', budgeted_spent: '54.50', remaining: '-14.50', unbudgeted: '20.00'},
  ],
  expected_bills: [{currency: 'USD', amount: '54.99', count: 1}],
  unpaid_bills: [{id: 'bill', name: 'Internet', amount: '54.99', currency: 'USD', due_date: '2026-11-26', paid: false}],
};
const props = {revision: 0, today: '2026-11-23', currency: 'USD', month: '2026-11', onMonth: vi.fn(), onAdd: vi.fn(), onChanged: vi.fn()};

test('the overview shows income, expenses and net per currency, with bills kept separate', async () => {
  vi.spyOn(api, 'budgetSummary').mockResolvedValue(summary);
  renderWithCategories(<MoneyOverview {...props} />);
  const user = userEvent.setup();
  const figures = await screen.findByText('Income received');
  const list = figures.closest('dl')!;
  expect(within(list).getByText('$1,200.00')).toBeInTheDocument();
  expect(within(list).getByText('$74.50')).toBeInTheDocument();
  expect(within(list).getByText('+$1,125.50')).toBeInTheDocument();
  expect(screen.getByText(/It is not a bank balance/)).toBeInTheDocument();
  expect(screen.getByText(/1 unpaid bill · \$54.99 · not counted as spending/)).toBeInTheDocument();
  expect(screen.getByText('$54.50 of $40.00 · $14.50 over')).toBeInTheDocument();
  expect(screen.getByRole('meter', {name: 'Dining budget used'})).toBeInTheDocument();
  expect(screen.getByRole('heading', {name: 'Spending without a budget'})).toBeInTheDocument();
  // Switching currency never mixes amounts.
  await user.click(screen.getByRole('button', {name: 'EUR'}));
  expect(within(list).getByText('−€9.00')).toBeInTheDocument();
  expect(screen.queryByText('$1,200.00')).not.toBeInTheDocument();
  expect(screen.getByText(/No unpaid EUR bills/)).toBeInTheDocument();
});

test('transactions combine expenses and income, filter by kind, and confirm before deleting', async () => {
  const items: Transaction[] = [
    {kind: 'expense', id: 'x1', amount: '14.50', currency: 'USD', category_id: 'dining', category: 'Dining', date: '2026-11-22', note: 'Lunch', bill_id: null},
    {kind: 'income', id: 'i1', amount: '1200.00', currency: 'USD', category_id: 'salary', category: 'Salary', date: '2026-11-15', note: '', bill_id: null},
  ];
  const page = (list: Transaction[]): Page<Transaction> => ({items: list, total: list.length, offset: 0, limit: 25});
  const load = vi.spyOn(api, 'transactions').mockImplementation(async (_month, kind) => page(kind === 'all' ? items : items.filter(t => t.kind === kind)));
  const remove = vi.spyOn(api, 'deleteIncome').mockResolvedValue(undefined);
  renderWithCategories(<TransactionsView {...props} />);
  const user = userEvent.setup();
  expect(await screen.findByText('Lunch')).toBeInTheDocument();
  expect(screen.getByText('+$1,200.00')).toBeInTheDocument();
  await user.click(screen.getByRole('button', {name: 'Income'}));
  await waitFor(() => expect(screen.queryByText('Lunch')).not.toBeInTheDocument());
  expect(load).toHaveBeenLastCalledWith('2026-11', 'income', 0, expect.anything());
  await user.click(screen.getByRole('button', {name: 'Delete Salary'}));
  expect(remove).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button', {name: 'Delete'}));
  await waitFor(() => expect(remove).toHaveBeenCalledWith('i1'));
  expect(props.onChanged).toHaveBeenCalledWith('Income deleted.');
});
