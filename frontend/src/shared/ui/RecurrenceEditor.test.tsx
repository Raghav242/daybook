import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { api } from '../api/client';
import type { Bill, Task } from '../api/contracts';
import { categoriesLoaded, renderWithCategories, settings } from '../../test-utils';
import { RecordEditor } from './RecordEditor';

test('a repeating bill is created as a series with its rule', async () => {
  const create = vi.spyOn(api, 'createSeries').mockResolvedValue({id: 's1'} as never);
  const save = vi.spyOn(api, 'save');
  const saved = vi.fn();
  renderWithCategories(<RecordEditor initialModule="bills" settings={settings} onClose={vi.fn()} onSaved={saved} />);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText('Name'), 'Rent');
  await user.type(screen.getByLabelText('Amount'), '1200');
  await user.selectOptions(screen.getByLabelText('Repeats'), 'monthly');
  expect(screen.getByText(/last day/)).toBeInTheDocument();
  await user.type(screen.getByLabelText('First due date'), '2026-01-31');
  await user.click(screen.getByRole('button', {name: 'Add bill'}));
  await waitFor(() => expect(saved).toHaveBeenCalledWith('Repeating bill added.'));
  expect(create).toHaveBeenCalledWith('bills', {name: 'Rent', amount: '1200', currency: 'USD', frequency: 'monthly', interval: 1, start_date: '2026-01-31', until_date: null});
  expect(save).not.toHaveBeenCalled();
});

test('a repeating task is set up from the optional details with its category', async () => {
  const create = vi.spyOn(api, 'createSeries').mockResolvedValue({id: 's1'} as never);
  renderWithCategories(<RecordEditor initialModule="tasks" settings={settings} onClose={vi.fn()} onSaved={vi.fn()} />);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText('Title'), 'Laundry');
  await categoriesLoaded();
  await user.selectOptions(await screen.findByLabelText('Category'), 'Personal');
  expect(screen.getByLabelText('Repeats')).not.toBeVisible();
  await user.click(screen.getByRole('button', {name: 'More details'}));
  await user.selectOptions(screen.getByLabelText('Repeats'), 'weekly');
  // Repeat fields cannot be hidden while they are in use.
  expect(screen.getByRole('button', {name: 'More details'})).toBeDisabled();
  await user.type(screen.getByLabelText('Starts on'), '2026-11-23');
  await user.click(screen.getByRole('button', {name: 'Add task'}));
  await waitFor(() => expect(create).toHaveBeenCalledOnce());
  expect(create.mock.calls[0][1]).toEqual({title: 'Laundry', notes: '', category_id: 'task:Personal', priority: 'normal', frequency: 'weekly', interval: 1, start_date: '2026-11-23', until_date: null});
});

test('editing an occurrence defaults to this one only', async () => {
  const save = vi.spyOn(api, 'save').mockResolvedValue({} as never);
  const future = vi.spyOn(api, 'updateFuture');
  const task: Task = {id: 't1', title: 'Water plants', notes: '', due_date: '2026-11-30', due_at: null, priority: 'normal', category_id: null, completed: false, series_id: 's1', occurrence_date: '2026-11-30'};
  renderWithCategories(<RecordEditor initialModule="tasks" item={task} settings={settings} onClose={vi.fn()} onSaved={vi.fn()} />);
  const user = userEvent.setup();
  expect(screen.getByLabelText('Only this occurrence')).toBeChecked();
  await user.clear(screen.getByLabelText('Title'));
  await user.type(screen.getByLabelText('Title'), 'Water ferns');
  await categoriesLoaded();
  await screen.findByLabelText('Category');
  await user.click(screen.getByRole('button', {name: 'Save changes'}));
  await waitFor(() => expect(save).toHaveBeenCalledOnce());
  expect(save.mock.calls[0][1]).not.toHaveProperty('series_id');
  expect(save.mock.calls[0][1]).toMatchObject({title: 'Water ferns', due_date: '2026-11-30', category_id: null});
  expect(future).not.toHaveBeenCalled();
});

test('this and future loads the rule and sends the edited definition', async () => {
  vi.spyOn(api, 'series').mockResolvedValue({id: 's2', name: 'Phone', amount: '30.00', currency: 'USD', frequency: 'weekly', interval: 2, start_date: '2026-11-02', until_date: null} as never);
  const future = vi.spyOn(api, 'updateFuture').mockResolvedValue({} as never);
  const saved = vi.fn();
  const bill: Bill = {id: 'b1', name: 'Phone', amount: '30.00', currency: 'USD', due_date: '2026-11-16', paid: false, series_id: 's2', occurrence_date: '2026-11-16'};
  renderWithCategories(<RecordEditor initialModule="bills" item={bill} settings={settings} onClose={vi.fn()} onSaved={saved} />);
  const user = userEvent.setup();
  await user.click(screen.getByLabelText('This and future occurrences'));
  await screen.findByText('Every 2 weeks');
  expect(screen.getByLabelText('Every')).toHaveValue(2);
  await user.clear(screen.getByLabelText('Amount'));
  await user.type(screen.getByLabelText('Amount'), '35');
  await user.click(screen.getByRole('button', {name: 'Save changes'}));
  await waitFor(() => expect(saved).toHaveBeenCalledWith('Updated this and future occurrences.'));
  expect(future).toHaveBeenCalledWith('bills', 'b1', {name: 'Phone', amount: '35', currency: 'USD', frequency: 'weekly', interval: 2, start_date: '2026-11-16', until_date: null});
});

test('stopping a series requires confirmation', async () => {
  const stop = vi.spyOn(api, 'stopSeries').mockResolvedValue(undefined);
  const task: Task = {id: 't1', title: 'Laundry', notes: '', due_date: '2026-11-30', due_at: null, priority: 'normal', category_id: null, completed: false, series_id: 's1', occurrence_date: '2026-11-30'};
  renderWithCategories(<RecordEditor initialModule="tasks" item={task} settings={settings} onClose={vi.fn()} onSaved={vi.fn()} />);
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', {name: 'Stop repeating…'}));
  expect(stop).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button', {name: 'Stop repeating'}));
  expect(stop).toHaveBeenCalledWith('tasks', 's1');
});
