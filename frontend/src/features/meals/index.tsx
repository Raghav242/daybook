import { useCallback, useMemo, useState } from 'react';
import { ArrowLeft, ArrowRight, Check, Pencil, Plus, ShoppingBasket, Trash2 } from 'lucide-react';
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
    <div className="page-heading"><div><p className="eyebrow">YOUR DAYBOOK</p><h1 id="view-title">Meals</h1><p className="page-subtitle">Plan the week, then turn it into a grocery list you can review.</p></div><button className="button primary" disabled={!recipeList.length} onClick={() => setEditing({ kind: 'meal', day: today >= start && today <= days[6] ? today : start })}><Plus size={17} />Plan a meal</button></div>
    <div className="list-toolbar"><div className="week-nav"><button className="icon-button" aria-label="Previous week" onClick={() => setStart(s => addDays(s, -7))}><ArrowLeft size={16} /></button><h2 aria-live="polite">{dateLabel(days[0])} – {dateLabel(days[6])}</h2><button className="icon-button" aria-label="Next week" onClick={() => setStart(s => addDays(s, 7))}><ArrowRight size={16} /></button>{start !== weekStart(today) && <button className="text-button" onClick={() => setStart(weekStart(today))}>This week</button>}</div>
      <button className="button secondary" disabled={!selected.length} onClick={() => setEditing({ kind: 'preview', entryIds: selected })}><ShoppingBasket size={16} />Make grocery list{selected.length ? ' (' + selected.length + ')' : ''}</button></div>
    {week.error && <div role="alert" className="error">{week.error}<button className="text-button" onClick={() => setLocal(r => r + 1)}>Try again</button></div>}
    {week.loading && !week.data && <p role="status" className="loading">Loading your week…</p>}
    {week.data && <ol className="week-plan" aria-busy={week.loading}>{days.map(day => { const meals = week.data!.filter(e => e.plan_date === day); return <li key={day} className={day === today ? 'is-today' : ''}>
      <div className="week-day"><strong>{weekdayLabel(day)}</strong><span>{dateLabel(day)}</span></div>
      <div className="week-meals">{meals.length ? <ul>{meals.map(entry => <li key={entry.id} className="meal-row">
        {entry.added_to_groceries ? <span className="meal-added" title="Groceries added"><Check size={14} aria-label="Groceries already added" /></span> : <input type="checkbox" className="record-check" checked={!unselected.has(entry.id)} aria-label={'Include ' + entry.recipe_name + ' on ' + dateLabel(day) + ' in the grocery list'} onChange={() => toggle(entry.id)} />}
        <span className="meal-name">{mealNames[entry.meal]}</span><button className="record-title" onClick={() => setEditing({ kind: 'meal', entry, day })}>{entry.recipe_name}</button><span className="record-detail">{entry.servings} {entry.servings === 1 ? 'serving' : 'servings'}</span>
        <button className="icon-button" aria-label={'Delete ' + entry.recipe_name + ' on ' + dateLabel(day)} onClick={() => setEditing({ kind: 'delete-meal', entry })}><Trash2 size={15} /></button>
      </li>)}</ul> : null}
        {recipeList.length > 0 && <button className="text-button" onClick={() => setEditing({ kind: 'meal', day })}><Plus size={13} />Add</button>}</div>
    </li>; })}</ol>}
    <section className="recipes-section" aria-labelledby="recipes-title"><div className="section-heading"><h2 id="recipes-title">Saved recipes</h2><button className="button secondary" onClick={() => setEditing({ kind: 'recipe' })}><Plus size={16} />Add recipe</button></div>
      {recipes.error && <div role="alert" className="error">{recipes.error}</div>}
      {recipes.data && (recipeList.length ? <ul className="records-list">{recipeList.map(recipe => <li key={recipe.id} className="record-row"><div className="record-copy"><button className="record-title" onClick={() => setEditing({ kind: 'recipe', recipe })}>{recipe.name}</button><span className="record-detail">Serves {recipe.servings} · {recipe.ingredients.length} {recipe.ingredients.length === 1 ? 'ingredient' : 'ingredients'}</span></div><div className="row-actions"><button className="icon-button" aria-label={'Edit ' + recipe.name} onClick={() => setEditing({ kind: 'recipe', recipe })}><Pencil size={16} /></button><button className="icon-button" aria-label={'Delete ' + recipe.name} onClick={() => setEditing({ kind: 'delete-recipe', recipe })}><Trash2 size={16} /></button></div></li>)}</ul>
        : <div className="empty-state compact"><h2>Start with a favorite</h2><p>Save a recipe with its servings and ingredients, then plan it into your week.</p><button className="button secondary" onClick={() => setEditing({ kind: 'recipe' })}><Plus size={16} />Add recipe</button></div>)}
      {recipes.data && recipes.data.total > recipeList.length && <p className="muted">Showing the first {recipeList.length} of {recipes.data.total} recipes.</p>}
    </section>
    {editing?.kind === 'recipe' && <RecipeEditor recipe={editing.recipe} onClose={() => setEditing(undefined)} onSaved={done} />}
    {editing?.kind === 'meal' && <MealEditor entry={editing.entry} day={editing.day} recipes={recipeList} onClose={() => setEditing(undefined)} onSaved={done} />}
    {editing?.kind === 'preview' && <GroceryPreviewDialog entryIds={editing.entryIds} onClose={() => setEditing(undefined)} onAdded={done} />}
    {editing?.kind === 'delete-recipe' && <ConfirmDialog title="Delete this recipe?" body={`“${editing.recipe.name}” and its planned meals will be removed. Groceries you already added stay on your list.`} action="Delete recipe" onClose={() => setEditing(undefined)} onConfirm={async () => { await api.deleteRecipe(editing.recipe.id); done('Recipe deleted.'); }} />}
    {editing?.kind === 'delete-meal' && <ConfirmDialog title="Remove this meal?" body={`${mealNames[editing.entry.meal]} · ${editing.entry.recipe_name} on ${dateLabel(editing.entry.plan_date)} will be removed from your plan.`} action="Remove meal" onClose={() => setEditing(undefined)} onConfirm={async () => { await api.deleteMeal(editing.entry.id); done('Meal removed.'); }} />}
  </section>;
}
