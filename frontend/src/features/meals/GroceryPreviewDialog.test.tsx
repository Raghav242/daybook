import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { api } from '../../shared/api/client';
import type { GroceryPreview } from '../../shared/api/contracts';
import { GroceryPreviewDialog } from './GroceryPreviewDialog';

const preview: GroceryPreview = {
  entries: [
    {id: 'e1', plan_date: '2026-11-23', meal: 'dinner', recipe_id: 'r1', recipe_name: 'Soup', servings: 4, added_to_groceries: false},
    {id: 'e2', plan_date: '2026-11-24', meal: 'lunch', recipe_id: 'r1', recipe_name: 'Soup', servings: 2, added_to_groceries: true},
  ],
  items: [
    {key: 'flour|cup', name: 'Flour', unit: 'cup', quantity: '1.500', category_id: 'g:pantry', category: 'Pantry', sources: ['Soup'], other_units: true, on_list: null},
    {key: 'flour|g', name: 'Flour', unit: 'g', quantity: '200.000', category_id: 'g:pantry', category: 'Pantry', sources: ['Soup'], other_units: true, on_list: '100.000'},
    {key: 'salt|', name: 'Salt', unit: '', quantity: '1.000', category_id: null, category: '', sources: ['Soup'], other_units: false, on_list: null},
  ],
  skipped_entry_ids: ['e2'],
};

test('review lets the user adjust and exclude lines, and retries reuse one request id', async () => {
  vi.spyOn(api, 'groceryPreview').mockResolvedValue(preview);
  const add = vi.spyOn(api, 'addGroceries').mockRejectedValueOnce(new Error('Connection interrupted')).mockResolvedValueOnce({request_id: 'x', created: true, added: 2});
  const added = vi.fn();
  render(<GroceryPreviewDialog entryIds={['e1', 'e2']} onClose={vi.fn()} onAdded={added} />);
  const user = userEvent.setup();
  expect(await screen.findByText(/From 1 planned meal/)).toBeInTheDocument();
  expect(screen.getByText(/1 meal was already added/)).toBeInTheDocument();
  expect(screen.getAllByText(/Kept separate: different units/)).toHaveLength(2);
  expect(screen.getByText(/100 g already on your list/)).toBeInTheDocument();
  const [cups, gramsInput] = screen.getAllByLabelText('Quantity of Flour');
  expect(cups).toHaveValue(1.5);
  await user.click(screen.getByLabelText('Include Salt'));
  expect(screen.getByRole('button', {name: 'Add 2 to groceries'})).toBeEnabled();
  await user.clear(gramsInput);
  await user.type(gramsInput, '150');
  await user.click(screen.getByRole('button', {name: 'Add 2 to groceries'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Connection interrupted');
  await user.click(screen.getByRole('button', {name: 'Add 2 to groceries'}));
  await waitFor(() => expect(added).toHaveBeenCalledWith('Added 2 items to groceries.'));
  expect(add).toHaveBeenCalledTimes(2);
  expect(add.mock.calls[0][0]).toBe(add.mock.calls[1][0]);
  expect(add.mock.calls[1][1]).toEqual(['e1']);
  expect(add.mock.calls[1][2]).toEqual([
    {name: 'Flour', unit: 'cup', category_id: 'g:pantry', quantity: '1.5'},
    {name: 'Flour', unit: 'g', category_id: 'g:pantry', quantity: '150'},
  ]);
});

test('a pending submission cannot be sent twice', async () => {
  vi.spyOn(api, 'groceryPreview').mockResolvedValue(preview);
  const add = vi.spyOn(api, 'addGroceries').mockImplementation(() => new Promise(() => {}));
  render(<GroceryPreviewDialog entryIds={['e1']} onClose={vi.fn()} onAdded={vi.fn()} />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', {name: 'Add 3 to groceries'}));
  expect(screen.getByRole('button', {name: 'Adding…'})).toBeDisabled();
  await user.click(screen.getByRole('button', {name: 'Adding…'}));
  expect(add).toHaveBeenCalledOnce();
});
