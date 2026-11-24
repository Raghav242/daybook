import type { FeatureModule } from '../shared/api/contracts';
import { enabledRoute, parseRoute, tabOf, tabRoutes } from './routes';

const all: FeatureModule[] = ['tasks', 'calendar', 'groceries', 'bills', 'meals', 'budget'];

test('every page has a deep link and earlier addresses still work', () => {
  expect(parseRoute('', all)).toBe('today');
  expect(parseRoute('#dashboard', all)).toBe('today');
  expect(parseRoute('#budget', all)).toBe('money');
  expect(parseRoute('#transactions', all)).toBe('transactions');
  expect(parseRoute('#/calendar', all)).toBe('calendar');
  expect(parseRoute('#settings', all)).toBe('settings');
  expect(parseRoute('#nothing-here', all)).toBe('today');
});

test('sections group pages into four tabs and skip disabled modules', () => {
  expect(tabRoutes('plan', all)).toEqual(['tasks', 'calendar', 'meals', 'groceries']);
  expect(tabRoutes('money', all)).toEqual(['money', 'transactions', 'budgets', 'bills']);
  expect(tabRoutes('money', ['bills'])).toEqual(['bills']);
  expect(tabRoutes('plan', ['budget'])).toEqual([]);
  expect(parseRoute('#plan', ['groceries', 'meals'])).toBe('meals');
  expect(tabOf('budgets')).toBe('money');
  expect(tabOf('groceries')).toBe('plan');
  expect(tabOf('settings')).toBeNull();
  expect(enabledRoute('transactions', ['tasks'])).toBe(false);
  expect(enabledRoute('library', [])).toBe(true);
});
