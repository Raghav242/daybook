import { useCallback, useMemo, useState } from 'react';
import { ArrowLeft, ArrowRight, Pencil, Plus, ShoppingBasket, Trash2 } from 'lucide-react';
import { api } from '../../shared/api/client';
import type { MealPlanEntry, Recipe } from '../../shared/api/contracts';
import { addDays, dateLabel, mealNames, weekdayLabel, weekStart } from '../../shared/domain';
import { useResource } from '../../shared/hooks/useResource';
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog';
import { GroceryPreviewDialog } from './GroceryPreviewDialog';
import { MealEditor, RecipeEditor } from './editors';

type Editing = { kind: 'recipe'; recipe?: Recipe } | { kind: 'meal'; entry?: MealPlanEntry; day: string } | { kind: 'preview'; entryIds: string[] } | { kind: 'delete-recipe'; recipe: Recipe } | { kind: 'delete-meal'; entry: MealPlanEntry };

export default function MealsView({ revision, today, onChanged }: { revision: number; today: string; onChanged: (message: string) => void }) {
  const [start, setStart] = useState(() => weekStart(today));
  const [local, setLocal] = useState(0);
  const [editing, setEditing] = useState<Editing>();
  const [unselected, setUnselected] = useState<Set<string>>(new Set());
  const loadWeek = useCallback((signal: AbortSignal) => api.mealPlan(start, signal), [start]);
  const loadRecipes = useCallback((signal: AbortSignal) => api.recipes(0, signal), []);
  const week = useResource(loadWeek, revision + local);
  const recipes = useResource(loadRecipes, revision + local);
  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => addDays(start, i)), [start]);
  const pending = (week.data || []).filter(e => !e.added_to_groceries);
  const selected = pending.filter(e => !unselected.has(e.id)).map(e => e.id);
  function done(message: string) { setEditing(undefined); setLocal(r => r + 1); onChanged(message); }
  const toggle = (id: string) => setUnselected(s => { const next = new Set(s); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  const recipeList = recipes.data?.items || [];
  return <section aria-labelledby="view-title">
    <header className="page-head split"><h1 id="view-title" className="page-title">Meals</h1><button className="button secondary small" disabled={!recipeList.length} onClick={() => setEditing({ kind: 'meal', day: today >= start && today <= days[6] ? today : start })}><Plus size={16} />Plan a meal</button></header>
    <div className="week-toolbar"><div className="month-nav"><button className="icon-button" aria-label="Previous week" onClick={() => setStart(s => addDays(s, -7))}><ArrowLeft size={18} /></button><h2 aria-live="polite">{dateLabel(days[0])} – {dateLabel(days[6])}</h2><button className="icon-button" aria-label="Next week" onClick={() => setStart(s => addDays(s, 7))}><ArrowRight size={18} /></button>{start !== weekStart(today) && <button className="text-button" onClick={() => setStart(weekStart(today))}>This week</button>}</div>
      <button className="button primary small" disabled={!selected.length} onClick={() => setEditing({ kind: 'preview', entryIds: selected })}><ShoppingBasket size={16} />Make grocery list{selected.length ? ' (' + selected.length + ')' : ''}</button></div>
    {week.error && <div role="alert" className="error">{week.error}<button className="text-button" onClick={() => setLocal(r => r + 1)}>Try again</button></div>}
    {week.loading && !week.data && <p role="status" className="loading">Loading your week…</p>}
    {week.data && <ol className="week-plan" aria-busy={week.loading}>{days.map(day => { const meals = week.data!.filter(e => e.plan_date === day); return <li key={day} className={day === today ? 'is-today' : ''}>
      <div className="week-day"><strong>{weekdayLabel(day)}</strong><span>{dateLabel(day)}</span></div>
      <div className="week-meals">{meals.length ? <ul>{meals.map(entry => <li key={entry.id} className="meal-row">
        {entry.added_to_groceries ? <span className="meal-added" title="Already on the grocery list" role="img" aria-label={entry.recipe_name + ' is already on the grocery list'}><ShoppingBasket size={15} aria-hidden="true" /></span> : <input type="checkbox" className="check" checked={!unselected.has(entry.id)} aria-label={'Include ' + entry.recipe_name + ' on ' + dateLabel(day) + ' in the grocery list'} onChange={() => toggle(entry.id)} />}
        <div className="row-copy"><button className="row-title" onClick={() => setEditing({ kind: 'meal', entry, day })}>{entry.recipe_name}</button><span className="row-meta">{mealNames[entry.meal]} · {entry.servings} {entry.servings === 1 ? 'serving' : 'servings'}{entry.added_to_groceries ? ' · on the list' : ''}</span></div>
        <button className="icon-button" aria-label={'Delete ' + entry.recipe_name + ' on ' + dateLabel(day)} onClick={() => setEditing({ kind: 'delete-meal', entry })}><Trash2 size={15} /></button>
      </li>)}</ul> : null}
        {recipeList.length > 0 && <button className="text-button add-meal" onClick={() => setEditing({ kind: 'meal', day })} aria-label={'Plan a meal on ' + dateLabel(day)}><Plus size={14} />Add</button>}</div>
    </li>; })}</ol>}
    <section className="recipes-section" aria-labelledby="recipes-title"><div className="section-head"><h2 id="recipes-title" className="section-title">Recipes</h2><button className="button secondary small" onClick={() => setEditing({ kind: 'recipe' })}><Plus size={16} />Add recipe</button></div>
      {recipes.error && <div role="alert" className="error">{recipes.error}</div>}
      {recipes.data && (recipeList.length ? <ul className="rows">{recipeList.map(recipe => <li key={recipe.id} className="row"><div className="row-copy"><button className="row-title" onClick={() => setEditing({ kind: 'recipe', recipe })}>{recipe.name}</button><span className="row-meta">Serves {recipe.servings} · {recipe.ingredients.length} {recipe.ingredients.length === 1 ? 'ingredient' : 'ingredients'}</span></div><div className="row-actions"><button className="icon-button" aria-label={'Edit ' + recipe.name} onClick={() => setEditing({ kind: 'recipe', recipe })}><Pencil size={16} /></button><button className="icon-button" aria-label={'Delete ' + recipe.name} onClick={() => setEditing({ kind: 'delete-recipe', recipe })}><Trash2 size={16} /></button></div></li>)}</ul>
        : <div className="empty"><p>Save a recipe with its servings and ingredients, then plan it into your week.</p><button className="text-button" onClick={() => setEditing({ kind: 'recipe' })}><Plus size={15} />Add recipe</button></div>)}
      {recipes.data && recipes.data.total > recipeList.length && <p className="muted">Showing the first {recipeList.length} of {recipes.data.total} recipes.</p>}
    </section>
    {editing?.kind === 'recipe' && <RecipeEditor recipe={editing.recipe} onClose={() => setEditing(undefined)} onSaved={done} />}
    {editing?.kind === 'meal' && <MealEditor entry={editing.entry} day={editing.day} recipes={recipeList} onClose={() => setEditing(undefined)} onSaved={done} />}
    {editing?.kind === 'preview' && <GroceryPreviewDialog entryIds={editing.entryIds} onClose={() => setEditing(undefined)} onAdded={done} />}
    {editing?.kind === 'delete-recipe' && <ConfirmDialog title="Delete this recipe?" body={`“${editing.recipe.name}” and its planned meals will be removed. Groceries you already added stay on your list.`} action="Delete recipe" onClose={() => setEditing(undefined)} onConfirm={async () => { await api.deleteRecipe(editing.recipe.id); done('Recipe deleted.'); }} />}
    {editing?.kind === 'delete-meal' && <ConfirmDialog title="Remove this meal?" body={`${mealNames[editing.entry.meal]} · ${editing.entry.recipe_name} on ${dateLabel(editing.entry.plan_date)} will be removed from your plan.`} action="Remove meal" onClose={() => setEditing(undefined)} onConfirm={async () => { await api.deleteMeal(editing.entry.id); done('Meal removed.'); }} />}
  </section>;
}
