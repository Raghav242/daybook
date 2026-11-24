import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { api } from '../api/client';
import type { Grocery } from '../api/contracts';
import { categoriesLoaded, renderWithCategories, settings } from '../../test-utils';
import { RecordEditor } from './RecordEditor';

test('failed save preserves typed input, including the category, and allows retry', async () => {
  const save = vi.spyOn(api, 'save').mockRejectedValueOnce(new Error('Connection interrupted')).mockResolvedValueOnce({id: '1'} as never);
  const saved = vi.fn();
  renderWithCategories(<RecordEditor initialModule="tasks" settings={settings} onClose={vi.fn()} onSaved={saved} />);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText('Title'), 'Submit essay');
  await categoriesLoaded();
  await user.selectOptions(await screen.findByLabelText('Category'), 'Study');
  await user.click(screen.getByRole('button', {name: 'Add task'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Connection interrupted');
  expect(screen.getByLabelText('Title')).toHaveValue('Submit essay');
  expect(screen.getByLabelText('Category')).toHaveValue('task:Study');
  await user.click(screen.getByRole('button', {name: 'Add task'}));
  await waitFor(() => expect(saved).toHaveBeenCalledOnce());
  expect(save).toHaveBeenCalledTimes(2);
  expect(save.mock.calls[1][1]).toMatchObject({title: 'Submit essay', category_id: 'task:Study', due_date: null, due_at: null});
});

test('a bill can be entered with the keyboard only', async () => {
  const save = vi.spyOn(api, 'save').mockResolvedValue({id: '1'} as never);
  renderWithCategories(<RecordEditor initialModule="bills" settings={settings} onClose={vi.fn()} onSaved={vi.fn()} />);
  const user = userEvent.setup();
  expect(screen.getByLabelText('Name')).toHaveFocus();
  await user.keyboard('Internet');
  await user.tab();
  await user.keyboard('54.99');
  await user.type(screen.getByLabelText('Due date'), '2026-10-08');
  screen.getByLabelText('Due date').focus();
  await user.keyboard('{Enter}');
  expect(save).toHaveBeenCalledWith('bills', {name: 'Internet', amount: '54.99', currency: 'USD', due_date: '2026-10-08', paid: false}, undefined);
});

test('pending save disables duplicate submissions', async () => {
  vi.spyOn(api, 'save').mockImplementation(() => new Promise(() => {}));
  renderWithCategories(<RecordEditor initialModule="tasks" settings={settings} onClose={vi.fn()} onSaved={vi.fn()} />);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText('Title'), 'Read a chapter');
  await user.click(screen.getByRole('button', {name: 'Add task'}));
  expect(screen.getByRole('button', {name: 'Saving…'})).toBeDisabled();
  expect(screen.getByLabelText('Title')).toBeDisabled();
  expect(screen.getByRole('button', {name: 'Close'})).toBeDisabled();
});

test('optional details stay hidden until asked for, and keep existing values when editing', async () => {
  const save = vi.spyOn(api, 'save').mockResolvedValue({} as never);
  const grocery: Grocery = {id: 'g1', name: 'Apples', quantity: '6.000', unit: 'pieces', category_id: 'grocery:Old aisle', category: 'Old aisle', purchased: false};
  // The grocery's aisle has been archived: it stays on this item without being offered elsewhere.
  renderWithCategories(<RecordEditor initialModule="groceries" item={grocery} settings={settings} onClose={vi.fn()} onSaved={vi.fn()} />,
    [{id: 'grocery:Produce', scope: 'grocery', name: 'Produce', archived: false}, {id: 'grocery:Old aisle', scope: 'grocery', name: 'Old aisle', archived: true}]);
  const user = userEvent.setup();
  await categoriesLoaded();
  const aisle = await screen.findByLabelText('Aisle');
  expect(aisle).toHaveValue('grocery:Old aisle');
  expect(screen.getByRole('option', {name: 'Old aisle (archived)'})).toBeInTheDocument();
  await user.click(screen.getByRole('button', {name: 'Save changes'}));
  await waitFor(() => expect(save).toHaveBeenCalledOnce());
  expect(save.mock.calls[0][1]).toEqual({name: 'Apples', quantity: '6', unit: 'pieces', category_id: 'grocery:Old aisle', purchased: false});
});
