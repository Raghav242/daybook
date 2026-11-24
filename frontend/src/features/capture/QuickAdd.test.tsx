import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { api } from '../../shared/api/client';
import { categoriesLoaded, renderWithCategories, settings } from '../../test-utils';
import { QuickAdd } from './QuickAdd';

const kinds = () => screen.getAllByRole('radio').map(radio => radio.closest('label')!.textContent);

test('one Add dialog offers every enabled type, including expense and income', () => {
  renderWithCategories(<QuickAdd settings={settings} today="2026-11-23" onClose={vi.fn()} onSaved={vi.fn()} />);
  expect(kinds()).toEqual(['Task', 'Event', 'Grocery', 'Expense', 'Income', 'Bill']);
  expect(screen.getByRole('radio', {name: 'Task'})).toBeChecked();
});

test('types follow the enabled modules', () => {
  renderWithCategories(<QuickAdd settings={{...settings, enabled_modules: ['calendar', 'budget']}} today="2026-11-23" onClose={vi.fn()} onSaved={vi.fn()} />);
  expect(kinds()).toEqual(['Event', 'Expense', 'Income']);
});

test('income is recorded with its source, date and exact amount', async () => {
  const saveIncome = vi.spyOn(api, 'saveIncome').mockResolvedValue({} as never);
  const saved = vi.fn();
  renderWithCategories(<QuickAdd settings={settings} today="2026-11-23" initial="income" onClose={vi.fn()} onSaved={saved} />);
  const user = userEvent.setup();
  expect(screen.getByRole('dialog', {name: 'Add income'})).toBeInTheDocument();
  await user.type(screen.getByLabelText('Amount'), '1250.75');
  await categoriesLoaded();
  await user.selectOptions(await screen.findByLabelText('Source'), 'Scholarship');
  expect(screen.getByLabelText('Received on')).toHaveValue('2026-11-23');
  expect(screen.getByText(/Refunds and transfers between your own accounts are not income/)).toBeInTheDocument();
  await user.click(screen.getByRole('button', {name: 'Add income'}));
  await waitFor(() => expect(saved).toHaveBeenCalledWith('Income recorded.'));
  expect(saveIncome).toHaveBeenCalledWith({amount: '1250.75', currency: 'USD', category_id: 'income:Scholarship', received_on: '2026-11-23', note: ''}, undefined);
});

test('a failed expense keeps every typed value and can be retried once', async () => {
  const saveExpense = vi.spyOn(api, 'saveExpense').mockRejectedValueOnce(new Error('Could not reach Daybook.')).mockImplementationOnce(() => new Promise(() => {}));
  renderWithCategories(<QuickAdd settings={settings} today="2026-11-23" onClose={vi.fn()} onSaved={vi.fn()} />);
  const user = userEvent.setup();
  await user.click(screen.getByRole('radio', {name: 'Expense'}));
  await user.type(screen.getByLabelText('Amount'), '14.25');
  await categoriesLoaded();
  await user.selectOptions(await screen.findByLabelText('Category'), 'Dining');
  await user.click(screen.getByRole('button', {name: 'Add a note'}));
  await user.type(screen.getByLabelText('Note'), 'Lunch');
  await user.click(screen.getByRole('button', {name: 'Add expense'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not reach Daybook.');
  expect(screen.getByLabelText('Amount')).toHaveValue(14.25);
  expect(screen.getByLabelText('Category')).toHaveValue('expense:Dining');
  expect(screen.getByLabelText('Note')).toHaveValue('Lunch');
  await user.click(screen.getByRole('button', {name: 'Add expense'}));
  expect(screen.getByRole('button', {name: 'Saving…'})).toBeDisabled();
  await user.click(screen.getByRole('button', {name: 'Saving…'}));
  expect(saveExpense).toHaveBeenCalledTimes(2);
  expect(saveExpense.mock.calls[1][0]).toEqual({amount: '14.25', currency: 'USD', category_id: 'expense:Dining', spent_on: '2026-11-23', note: 'Lunch'});
});

test('an expense needs a category before anything is sent', async () => {
  const saveExpense = vi.spyOn(api, 'saveExpense');
  renderWithCategories(<QuickAdd settings={settings} today="2026-11-23" initial="expense" onClose={vi.fn()} onSaved={vi.fn()} />);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText('Amount'), '3');
  await categoriesLoaded();
  const category = await screen.findByLabelText('Category');
  expect(category).toBeRequired();
  await user.click(screen.getByRole('button', {name: 'Add expense'}));
  expect(saveExpense).not.toHaveBeenCalled();
});
