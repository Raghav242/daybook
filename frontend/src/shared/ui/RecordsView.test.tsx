import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { api } from '../api/client';
import type { Task } from '../api/contracts';
import { RecordsView } from './RecordsView';

test('deleting the final row on a later page returns to an available page', async () => {
  const task = (i: number): Task => ({id: String(i), title: 'Task ' + i, notes: '', due_date: null, due_at: null, priority: 'normal', category: '', completed: false});
  let deleted = false;
  vi.spyOn(api, 'list').mockImplementation(async (_module, offset = 0) => ({
    items: offset === 0 ? Array.from({length:25}, (_, i) => task(i)) : deleted ? [] : [task(25)],
    total: deleted ? 25 : 26, offset, limit: 25,
  }) as never);
  const props = {module: 'tasks' as const, zone: 'UTC', busy: false, onAdd: vi.fn(), onEdit: vi.fn(), onDelete: vi.fn(), onToggle: vi.fn()};
  const {rerender} = render(<RecordsView {...props} revision={0} />);
  await screen.findByRole('button', {name:'Task 0'});
  await userEvent.setup().click(screen.getByRole('button', {name:'Next'}));
  await screen.findByRole('button', {name:'Task 25'});
  deleted = true;
  rerender(<RecordsView {...props} revision={1} />);
  await waitFor(() => expect(screen.getByRole('button', {name:'Task 0'})).toBeVisible());
  expect(screen.queryByRole('button', {name:'Task 25'})).not.toBeInTheDocument();
});

