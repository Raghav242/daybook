import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { api } from './api/client';
import type { Category } from './api/contracts';
import { CategorySelect } from './categories';
import { SEARCH_THRESHOLD } from './useCategories';
import { categoriesLoaded, category, defaultCategories, renderWithCategories } from '../test-utils';

const posted = () => (document.querySelector('input[type=hidden][name=category_id]') as HTMLInputElement).value;

test('short lists use a select with only active categories and an Add option', async () => {
  const categories = [...defaultCategories, category('expense', 'Old rent', true)];
  renderWithCategories(<form><CategorySelect scope="expense" label="Category" required /></form>, categories);
  await categoriesLoaded();
  const select = await screen.findByLabelText('Category');
  const options = Array.from((select as HTMLSelectElement).options).map(o => o.textContent);
  expect(options).toEqual(['Choose a category', 'Housing', 'Groceries', 'Dining', 'Utilities', 'Other', '+ Add category…']);
  await userEvent.setup().selectOptions(select, 'Utilities');
  expect(posted()).toBe('expense:Utilities');
});

test('a custom category is added from inside the selector and selected', async () => {
  const created: Category = category('income', 'Tutoring');
  const create = vi.spyOn(api, 'createCategory').mockResolvedValue(created);
  const changed = vi.fn();
  renderWithCategories(<form><CategorySelect scope="income" label="Source" onChange={changed} /></form>);
  const user = userEvent.setup();
  await categoriesLoaded();
  await user.selectOptions(await screen.findByLabelText('Source'), '+ Add source…');
  const input = screen.getByLabelText('New source');
  expect(input).toHaveFocus();
  await user.type(input, '  Tutoring {Enter}');
  await waitFor(() => expect(create).toHaveBeenCalledWith('income', 'Tutoring'));
  await categoriesLoaded();
  expect(await screen.findByLabelText('Source')).toHaveValue('income:Tutoring');
  expect(changed).toHaveBeenLastCalledWith('income:Tutoring');
  expect(posted()).toBe('income:Tutoring');
});

test('a failed add keeps the typed name and explains why', async () => {
  vi.spyOn(api, 'createCategory').mockRejectedValue(new Error('Could not reach Daybook.'));
  renderWithCategories(<form><CategorySelect scope="task" label="Category" /></form>);
  const user = userEvent.setup();
  await categoriesLoaded();
  await user.selectOptions(await screen.findByLabelText('Category'), '+ Add category…');
  await user.type(screen.getByLabelText('New category'), 'Volunteering');
  await user.click(screen.getByRole('button', {name: 'Add'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not reach Daybook.');
  expect(screen.getByLabelText('New category')).toHaveValue('Volunteering');
});

test('long lists become a searchable combobox operable by keyboard', async () => {
  const many = Array.from({length: SEARCH_THRESHOLD + 3}, (_, i) => category('grocery', 'Aisle ' + String(i + 1).padStart(2, '0')));
  const create = vi.spyOn(api, 'createCategory').mockResolvedValue(category('grocery', 'Spices'));
  renderWithCategories(<form><CategorySelect scope="grocery" label="Aisle" /></form>, many);
  const user = userEvent.setup();
  await categoriesLoaded();
  const box = screen.getByRole('combobox', {name: 'Aisle'});
  await user.click(box);
  expect(screen.getAllByRole('option')).toHaveLength(many.length + 1);
  await user.type(box, '14');
  expect(screen.getAllByRole('option').map(o => o.textContent)).toEqual(['Aisle 14', '+ Add “14”']);
  await user.keyboard('{ArrowDown}{Enter}');
  expect(box).toHaveValue('Aisle 14');
  expect(posted()).toBe('grocery:Aisle 14');
  await user.clear(box);
  await user.type(box, 'Spices');
  await user.click(screen.getByRole('option', {name: '+ Add “Spices”'}));
  expect(screen.getByLabelText('New aisle')).toHaveValue('Spices');
  await user.click(screen.getByRole('button', {name: 'Add'}));
  await waitFor(() => expect(create).toHaveBeenCalledWith('grocery', 'Spices'));
});
