import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { api } from '../api/client';
import type { Bill, Settings, Task } from '../api/contracts';
import { RecordEditor } from './RecordEditor';

const settings: Settings = {timezone: 'America/New_York', default_currency: 'USD', enabled_modules: ['tasks', 'calendar', 'groceries', 'bills', 'meals', 'budget']};

test('quick capture offers only record modules, not meals or budget', () => {
  render(<RecordEditor settings={settings} onClose={vi.fn()} onSaved={vi.fn()} />);
  const options = Array.from((screen.getByLabelText('Record type') as HTMLSelectElement).options).map(o => o.value);
  expect(options).toEqual(['tasks', 'calendar', 'groceries', 'bills']);
});

test('a repeating bill is created as a series with its rule', async () => {
  const create = vi.spyOn(api, 'createSeries').mockResolvedValue({id: 's1'} as never);
  const save = vi.spyOn(api, 'save');
  const saved = vi.fn();
  render(<RecordEditor initialModule="bills" settings={settings} onClose={vi.fn()} onSaved={saved} />);
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

test('editing an occurrence defaults to this one only', async () => {
  const save = vi.spyOn(api, 'save').mockResolvedValue({} as never);
  const future = vi.spyOn(api, 'updateFuture');
  const task: Task = {id: 't1', title: 'Water plants', notes: '', due_date: '2026-11-30', due_at: null, priority: 'normal', category: '', completed: false, series_id: 's1', occurrence_date: '2026-11-30'};
  render(<RecordEditor initialModule="tasks" item={task} settings={settings} onClose={vi.fn()} onSaved={vi.fn()} />);
  const user = userEvent.setup();
  expect(screen.getByLabelText('Only this occurrence')).toBeChecked();
  await user.clear(screen.getByLabelText('Title'));
  await user.type(screen.getByLabelText('Title'), 'Water ferns');
  await user.click(screen.getByRole('button', {name: 'Save changes'}));
  await waitFor(() => expect(save).toHaveBeenCalledOnce());
  expect(save.mock.calls[0][1]).not.toHaveProperty('series_id');
  expect(save.mock.calls[0][1]).toMatchObject({title: 'Water ferns', due_date: '2026-11-30'});
  expect(future).not.toHaveBeenCalled();
});

test('this and future loads the rule and sends the edited definition', async () => {
  vi.spyOn(api, 'series').mockResolvedValue({id: 's2', name: 'Phone', amount: '30.00', currency: 'USD', frequency: 'weekly', interval: 2, start_date: '2026-11-02', until_date: null} as never);
  const future = vi.spyOn(api, 'updateFuture').mockResolvedValue({} as never);
  const saved = vi.fn();
  const bill: Bill = {id: 'b1', name: 'Phone', amount: '30.00', currency: 'USD', due_date: '2026-11-16', paid: false, series_id: 's2', occurrence_date: '2026-11-16'};
  render(<RecordEditor initialModule="bills" item={bill} settings={settings} onClose={vi.fn()} onSaved={saved} />);
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
  const task: Task = {id: 't1', title: 'Laundry', notes: '', due_date: '2026-11-30', due_at: null, priority: 'normal', category: '', completed: false, series_id: 's1', occurrence_date: '2026-11-30'};
  render(<RecordEditor initialModule="tasks" item={task} settings={settings} onClose={vi.fn()} onSaved={vi.fn()} />);
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', {name: 'Stop repeating…'}));
  expect(stop).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button', {name: 'Stop repeating'}));
  expect(stop).toHaveBeenCalledWith('tasks', 's1');
});
