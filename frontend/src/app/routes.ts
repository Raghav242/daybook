import type { FeatureModule } from '../shared/api/contracts';

/** Every page has its own hash, so links and reloads land on the same place. */
export type Route = 'today' | 'tasks' | 'calendar' | 'meals' | 'groceries' | 'money' | 'transactions' | 'budgets' | 'bills' | 'library' | 'settings';
export type Tab = 'today' | 'plan' | 'money' | 'library';

export const planRoutes = ['tasks', 'calendar', 'meals', 'groceries'] as const;
export const moneyRoutes = ['money', 'transactions', 'budgets', 'bills'] as const;
export const routeTitles: Record<Route, string> = {
  today: 'Today', tasks: 'Tasks', calendar: 'Calendar', meals: 'Meals', groceries: 'Groceries',
  money: 'Overview', transactions: 'Transactions', budgets: 'Budgets', bills: 'Bills', library: 'Library', settings: 'Settings',
};
/** Module that must be enabled for a page to show. */
export const routeModule: Partial<Record<Route, FeatureModule>> = {
  tasks: 'tasks', calendar: 'calendar', meals: 'meals', groceries: 'groceries',
  money: 'budget', transactions: 'budget', budgets: 'budget', bills: 'bills',
};
// Earlier addresses keep working.
const aliases: Record<string, Route | Tab> = { '': 'today', dashboard: 'today', overview: 'money', budget: 'money', expenses: 'transactions', income: 'transactions', plan: 'plan', documents: 'library' };
const routes = new Set<string>(Object.keys(routeTitles));

export const enabledRoute = (route: Route, enabled: FeatureModule[]) => !routeModule[route] || enabled.includes(routeModule[route]!);
export const tabRoutes = (tab: Tab, enabled: FeatureModule[]): Route[] =>
  tab === 'plan' ? planRoutes.filter(r => enabledRoute(r, enabled)) : tab === 'money' ? moneyRoutes.filter(r => enabledRoute(r, enabled)) : [tab];
export function tabOf(route: Route): Tab | null {
  if ((planRoutes as readonly string[]).includes(route)) return 'plan';
  if ((moneyRoutes as readonly string[]).includes(route)) return 'money';
  return route === 'today' || route === 'library' ? route : null;
}

/** Resolve a location hash; a section name opens its first enabled page. */
export function parseRoute(hash: string, enabled: FeatureModule[]): Route {
  const name = decodeURIComponent(hash.replace(/^#\/?/, '')).toLowerCase();
  const target = aliases[name] ?? (routes.has(name) ? name as Route : 'today');
  if (target === 'plan') return tabRoutes('plan', enabled)[0] || 'tasks';
  return target as Route;
}
