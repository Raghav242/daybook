import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { api } from '../api/client';
import { RecordEditor } from './RecordEditor';
import type { Settings } from '../api/contracts';

const settings: Settings = {timezone: 'America/New_York', default_currency: 'USD', enabled_modules: ['tasks', 'calendar', 'groceries', 'bills']};
test('failed save preserves typed input and allows retry', async () => {
  const save = vi.spyOn(api, 'save').mockRejectedValueOnce(new Error('Connection interrupted')).mockResolvedValueOnce({id: '1'} as never);
  const saved = vi.fn();
  render(<RecordEditor initialModule="tasks" settings={settings} onClose={vi.fn()} onSaved={saved} />);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText('Title'), 'Submit essay');
  await user.click(screen.getByRole('button', {name: 'Add task'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Connection interrupted');
  expect(screen.getByLabelText('Title')).toHaveValue('Submit essay');
  await user.click(screen.getByRole('button', {name: 'Add task'}));
  await waitFor(() => expect(saved).toHaveBeenCalledOnce());
  expect(save).toHaveBeenCalledTimes(2);
});
test('keyboard can choose record type and submit a bill with a date-only deadline', async () => {
  const save = vi.spyOn(api, 'save').mockResolvedValue({id: '1'} as never);
  render(<RecordEditor settings={settings} onClose={vi.fn()} onSaved={vi.fn()} />);
  const user = userEvent.setup();
  screen.getByLabelText('Record type').focus();
  await user.selectOptions(screen.getByLabelText('Record type'), 'bills');
  expect(screen.getByLabelText('Name')).toHaveFocus();
  await user.type(screen.getByLabelText('Name'), 'Internet');
  await user.tab();
  await user.keyboard('54.99');
  await user.type(screen.getByLabelText('Due date'), '2026-10-08');
  await user.tab();
  await user.tab();
  await user.keyboard('{Enter}');
  expect(save).toHaveBeenCalledWith('bills', {name: 'Internet', amount: '54.99', currency: 'USD', due_date: '2026-10-08', paid: false}, undefined);
});
test('pending save disables duplicate submissions', async () => {
  vi.spyOn(api, 'save').mockImplementation(() => new Promise(() => {}));
  render(<RecordEditor initialModule="tasks" settings={settings} onClose={vi.fn()} onSaved={vi.fn()} />);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText('Title'), 'Read a chapter');
  await user.click(screen.getByRole('button', {name: 'Add task'}));
  expect(screen.getByRole('button', {name: 'Saving…'})).toBeDisabled();
  expect(screen.getByLabelText('Title')).toBeDisabled();
});

