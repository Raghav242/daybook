import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { api, ApiError } from '../shared/api/client';
import type { AuthSession, Dashboard } from '../shared/api/contracts';
import App from './App';

vi.mock('../shared/api/client', async importOriginal => {
  const original = await importOriginal<typeof import('../shared/api/client')>();
  return {...original, api: {...original.api, me: vi.fn(), login: vi.fn(), register: vi.fn(), logout: vi.fn(), settings: vi.fn(), dashboard: vi.fn()}};
});
vi.mock('../features/dashboard', () => ({default: ({data}: {data: Dashboard}) => <div>{data.tasks.map(task => <p key={task.id}>{task.title}</p>)}</div>}));
const alice = {id: 'alice', username: 'Alice'};
const bob = {id: 'bob', username: 'Bob'};
const settings = {timezone: 'UTC', default_currency: 'USD', enabled_modules: []};
afterEach(() => {vi.resetAllMocks();});

test('private content waits for session validation', async () => {
  let complete!: (value: AuthSession) => void;
  vi.mocked(api.me).mockReturnValue(new Promise(resolve => {complete = resolve;}));
  vi.mocked(api.settings).mockResolvedValue(settings);
  vi.mocked(api.dashboard).mockResolvedValue({tasks: []} as unknown as Dashboard);
  render(<App/>);
  expect(screen.getByRole('status')).toHaveTextContent('Opening your Daybook');
  expect(api.settings).not.toHaveBeenCalled();
  expect(screen.queryByText('Quick capture')).not.toBeInTheDocument();
  await act(async () => complete({user: alice, csrf_token: 'csrf'}));
  expect(await screen.findByText('Alice')).toBeInTheDocument();
});

test('logout and account changes discard cached private records, including late responses', async () => {
  const user = userEvent.setup();
  vi.mocked(api.me).mockResolvedValue({user: alice, csrf_token: 'csrf'});
  vi.mocked(api.settings).mockResolvedValue(settings);
  vi.mocked(api.dashboard).mockResolvedValue({tasks: [{id: 'a', title: 'Alice private record'}]} as unknown as Dashboard);
  vi.mocked(api.logout).mockResolvedValue(undefined);
  vi.mocked(api.login).mockResolvedValue({user: bob, csrf_token: 'bob-csrf'});
  render(<App/>);
  expect(await screen.findByText('Alice private record')).toBeInTheDocument();
  await user.click(screen.getByRole('button', {name: 'Log out'}));
  expect(await screen.findByRole('button', {name: 'Sign in'})).toBeInTheDocument();
  expect(screen.queryByText('Alice private record')).not.toBeInTheDocument();
  let complete!: (value: Dashboard) => void;
  vi.mocked(api.dashboard).mockReturnValue(new Promise(resolve => {complete = resolve;}));
  await user.type(screen.getByLabelText('Username'), 'Bob');
  await user.type(screen.getByLabelText('Password'), 'test-passphrase-123');
  await user.click(screen.getByRole('button', {name: 'Sign in'}));
  expect(await screen.findByText('Bob')).toBeInTheDocument();
  expect(screen.queryByText('Alice private record')).not.toBeInTheDocument();
  await act(async () => complete({tasks: [{id: 'b', title: 'Bob private record'}]} as unknown as Dashboard));
  expect(await screen.findByText('Bob private record')).toBeInTheDocument();
  expect(screen.queryByText('Alice private record')).not.toBeInTheDocument();
});

test('expired sessions unmount private data and preserve usernames after invalid login', async () => {
  const user = userEvent.setup();
  vi.mocked(api.me).mockResolvedValue({user: alice, csrf_token: 'csrf'});
  vi.mocked(api.settings).mockResolvedValue(settings);
  vi.mocked(api.dashboard).mockResolvedValue({tasks: [{id: 'a', title: 'Alice private record'}]} as unknown as Dashboard);
  vi.mocked(api.login).mockRejectedValue(new ApiError('Invalid username or password.', 401));
  render(<App/>);
  await screen.findByText('Alice private record');
  act(() => window.dispatchEvent(new Event('daybook:session-expired')));
  expect(screen.queryByText('Alice private record')).not.toBeInTheDocument();
  expect(screen.getByText(/Your session has ended/)).toBeInTheDocument();
  await user.type(screen.getByLabelText('Username'), 'Alice');
  await user.type(screen.getByLabelText('Password'), 'wrong-password');
  await user.click(screen.getByRole('button', {name: 'Sign in'}));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Invalid username or password.'));
  expect(screen.getByLabelText('Username')).toHaveValue('Alice');
  expect(screen.getByLabelText('Password')).toHaveAttribute('autocomplete', 'current-password');
  await user.click(screen.getByRole('button', {name: 'Create an account'}));
  expect(screen.getByLabelText('Password')).toHaveAttribute('autocomplete', 'new-password');
  expect(screen.getByLabelText('Password')).toHaveAttribute('minlength', '5');
});

test('an old account request completing after a new login cannot repopulate private views', async () => {
  const user = userEvent.setup();
  let completeOldRequest!: (value: Dashboard) => void;
  vi.mocked(api.me).mockResolvedValue({user: alice, csrf_token: 'csrf'});
  vi.mocked(api.settings).mockResolvedValue(settings);
  vi.mocked(api.dashboard)
    .mockReturnValueOnce(new Promise(resolve => {completeOldRequest = resolve;}))
    .mockResolvedValue({tasks: [{id: 'b', title: 'Bob current record'}]} as unknown as Dashboard);
  vi.mocked(api.logout).mockResolvedValue(undefined);
  vi.mocked(api.login).mockResolvedValue({user: bob, csrf_token: 'bob-csrf'});
  render(<App/>);
  await screen.findByText('Alice');
  await user.click(screen.getByRole('button', {name: 'Log out'}));
  await user.type(await screen.findByLabelText('Username'), 'Bob');
  await user.type(screen.getByLabelText('Password'), 'test-passphrase-123');
  await user.click(screen.getByRole('button', {name: 'Sign in'}));
  await screen.findByText('Bob current record');
  await act(async () => completeOldRequest({tasks: [{id: 'a', title: 'Alice late private record'}]} as unknown as Dashboard));
  expect(screen.queryByText('Alice late private record')).not.toBeInTheDocument();
  expect(screen.getByText('Bob current record')).toBeInTheDocument();
});

test('duplicate registration preserves its error and draft after a browser dialog restores focus', async () => {
  const user = userEvent.setup();
  vi.mocked(api.me).mockRejectedValue(new ApiError('Please sign in.', 401));
  vi.mocked(api.register).mockRejectedValue(new ApiError('That username is unavailable.', 409));
  render(<App/>);
  await user.click(await screen.findByRole('button', {name: 'Create an account'}));
  await user.type(screen.getByLabelText('Username'), 'ExistingUser');
  await user.type(screen.getByLabelText('Password'), 'example-passphrase');
  await user.click(screen.getByRole('button', {name: 'Create account'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('That username is unavailable.');
  const checks = vi.mocked(api.me).mock.calls.length;
  act(() => window.dispatchEvent(new FocusEvent('focus')));
  expect(screen.getByRole('alert')).toHaveTextContent('That username is unavailable.');
  expect(screen.getByLabelText('Username')).toHaveValue('ExistingUser');
  expect(screen.getByLabelText('Password')).toHaveValue('example-passphrase');
  expect(api.me).toHaveBeenCalledTimes(checks);
});
