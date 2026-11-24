import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import { api } from '../../shared/api/client';
import type { MealPlanEntry } from '../../shared/api/contracts';
import MealsView from '.';

const entry = (id: string, meal: MealPlanEntry['meal'], name: string, added: boolean): MealPlanEntry =>
  ({ id, plan_date: '2026-11-23', meal, recipe_id: 'r-' + id, recipe_name: name, servings: 2, added_to_groceries: added });

test('a meal already on the grocery list shows a badge, not a tick that looks like a selected checkbox', async () => {
  vi.spyOn(api, 'mealPlan').mockResolvedValue([entry('a', 'lunch', 'Lentil soup', true), entry('b', 'dinner', 'Pasta', false)]);
  vi.spyOn(api, 'recipes').mockResolvedValue({ items: [], total: 0, offset: 0, limit: 100 });
  render(<MealsView revision={0} today="2026-11-23" onChanged={vi.fn()} />);
  expect(await screen.findByRole('img', { name: 'Lentil soup is already on the grocery list' })).toBeInTheDocument();
  expect(screen.queryByRole('checkbox', { name: /Lentil soup/ })).not.toBeInTheDocument();
  expect(screen.getByRole('checkbox', { name: /Include Pasta/ })).toBeChecked();
  expect(screen.getByRole('button', { name: /Make grocery list \(1\)/ })).toBeEnabled();
});
