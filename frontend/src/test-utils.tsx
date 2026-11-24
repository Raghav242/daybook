import { render, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { vi } from 'vitest';
import { api } from './shared/api/client';
import type { Category, CategoryScope, Settings } from './shared/api/contracts';
import { CategoriesProvider } from './shared/categories';

export const settings: Settings = { timezone: 'America/New_York', default_currency: 'USD', enabled_modules: ['tasks', 'calendar', 'groceries', 'bills', 'meals', 'budget'] };

export const category = (scope: CategoryScope, name: string, archived = false): Category => ({ id: scope + ':' + name, scope, name, archived });
export const defaultCategories: Category[] = [
  ...['Personal', 'Study', 'Work'].map(name => category('task', name)),
  ...['Housing', 'Groceries', 'Dining', 'Utilities', 'Other'].map(name => category('expense', name)),
  ...['Salary', 'Scholarship', 'Gift'].map(name => category('income', name)),
  ...['Produce', 'Pantry'].map(name => category('grocery', name)),
];

/** Render inside the category store, with categories served from memory. */
export function renderWithCategories(ui: ReactElement, categories: Category[] = defaultCategories) {
  vi.spyOn(api, 'categories').mockResolvedValue(categories);
  return render(<CategoriesProvider revision={0}>{ui}</CategoriesProvider>);
}

/** Wait until every category selector has finished loading. */
export const categoriesLoaded = () => waitFor(() => {
  if (document.querySelector('select[aria-busy="true"]')) throw new Error('Categories are still loading.');
});
