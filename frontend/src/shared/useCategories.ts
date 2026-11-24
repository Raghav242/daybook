import { createContext, useContext, useEffect, useMemo } from 'react';
import type { Category, CategoryScope } from './api/contracts';

export const SEARCH_THRESHOLD = 12;
interface Store { categories: Category[] | undefined; error: string; load: () => void; add: (scope: CategoryScope, name: string) => Promise<Category>; replace: (category: Category) => void }
export const CategoriesContext = createContext<Store | null>(null);

export function useCategories(scope?: CategoryScope) {
  const store = useContext(CategoriesContext);
  if (!store) throw new Error('useCategories needs a CategoriesProvider.');
  const { load } = store;
  useEffect(() => { load(); }, [load]);
  const all = useMemo(() => (store.categories || []).filter(c => !scope || c.scope === scope), [store.categories, scope]);
  return { ...store, all, active: all.filter(c => !c.archived), loading: !store.categories && !store.error };
}

