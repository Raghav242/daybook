import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, vi } from 'vitest';
import type { FeatureModule } from '../shared/api/contracts';
import { AddButton, Shell } from './Shell';

const all: FeatureModule[] = ['tasks', 'calendar', 'groceries', 'bills', 'meals', 'budget'];
const narrow = () => vi.stubGlobal('matchMedia', (query: string) => ({ matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
afterEach(() => vi.unstubAllGlobals());

function shell(route: Parameters<typeof Shell>[0]['route'], enabled = all, onLogout = vi.fn()) {
  render(<Shell route={route} user={{id: 'u', username: 'Alice'}} enabled={enabled} busy={false} onLogout={onLogout} addButton={<AddButton disabled={false} onClick={vi.fn()} />}><h1>Page</h1></Shell>);
  return onLogout;
}

test('phones get four labeled bottom tabs, section links and one Add button', () => {
  narrow();
  shell('budgets');
  const tabs = within(screen.getByRole('navigation', {name: 'Main'})).getAllByRole('link');
  expect(tabs.map(t => t.textContent)).toEqual(['Today', 'Plan', 'Money', 'Library']);
  expect(tabs.map(t => t.getAttribute('href'))).toEqual(['#today', '#tasks', '#money', '#library']);
  expect(screen.getByRole('link', {name: 'Money'})).toHaveAttribute('aria-current', 'page');
  const sections = within(screen.getByRole('navigation', {name: 'Money sections'})).getAllByRole('link');
  expect(sections.map(s => s.textContent)).toEqual(['Overview', 'Transactions', 'Budgets', 'Bills']);
  expect(within(screen.getByRole('navigation', {name: 'Money sections'})).getByRole('link', {name: 'Budgets'})).toHaveAttribute('aria-current', 'page');
  expect(screen.getAllByRole('button', {name: 'Add'})).toHaveLength(1);
});

test('tabs without any enabled page are hidden', () => {
  narrow();
  shell('today', ['tasks']);
  expect(within(screen.getByRole('navigation', {name: 'Main'})).getAllByRole('link').map(t => t.textContent)).toEqual(['Today', 'Plan', 'Library']);
});

test('desktop uses a sidebar with sub-pages and a profile menu for settings and logout', async () => {
  const onLogout = shell('groceries');
  const main = screen.getByRole('navigation', {name: 'Main'});
  expect(within(main).getByRole('link', {name: 'Groceries'})).toHaveAttribute('aria-current', 'page');
  expect(within(main).queryByRole('link', {name: 'Settings'})).not.toBeInTheDocument();
  const user = userEvent.setup();
  const button = screen.getByRole('button', {name: /account menu/});
  await user.click(button);
  expect(screen.getByRole('menuitem', {name: 'Settings'})).toHaveFocus();
  await user.keyboard('{ArrowDown}');
  expect(screen.getByRole('menuitem', {name: 'Log out'})).toHaveFocus();
  await user.keyboard('{Escape}');
  expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  expect(button).toHaveFocus();
  await user.click(button);
  await user.click(screen.getByRole('menuitem', {name: 'Log out'}));
  expect(onLogout).toHaveBeenCalledOnce();
});
