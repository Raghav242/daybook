import { useState, type FormEvent } from 'react';
import { Plus, X } from 'lucide-react';
import { api } from '../../shared/api/client';
import type { Ingredient, Meal, MealPlanEntry, Recipe } from '../../shared/api/contracts';
import { mealNames, quantity } from '../../shared/domain';
import { Dialog } from '../../shared/ui/Dialog';

const blank = (): Ingredient & { key: string } => ({ key: crypto.randomUUID(), name: '', quantity: '1', unit: '', category: '' });

export function RecipeEditor({ recipe, onClose, onSaved }: { recipe?: Recipe; onClose: () => void; onSaved: (message: string) => void }) {
  const [rows, setRows] = useState(() => recipe?.ingredients.length ? recipe.ingredients.map(i => ({ ...i, quantity: quantity(i.quantity), key: i.id || crypto.randomUUID() })) : [blank()]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const change = (key: string, field: keyof Ingredient, value: string) => setRows(r => r.map(row => row.key === key ? { ...row, [field]: value } : row));
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (pending) return;
    const form = new FormData(e.currentTarget);
    const ingredients = rows.filter(r => r.name.trim()).map(({ name, quantity, unit, category }) => ({ name: name.trim(), quantity, unit: unit.trim(), category: category.trim() }));
    setPending(true); setError('');
    try {
      await api.saveRecipe({ name: String(form.get('name')).trim(), servings: Number(form.get('servings')), notes: String(form.get('notes') || '').trim(), ingredients }, recipe?.id);
      onSaved(recipe ? 'Recipe updated.' : 'Recipe saved.');
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not save the recipe.'); }
    finally { setPending(false); }
  }
  return <Dialog title={recipe ? 'Edit recipe' : 'Add recipe'} onClose={onClose} pending={pending}>
    <form onSubmit={submit}><fieldset disabled={pending}>
      <div className="form-pair recipe-head"><label>Name<input name="name" required maxLength={200} defaultValue={recipe?.name} placeholder="e.g. Lentil soup" /></label><label>Serves<input name="servings" type="number" min="1" max="1000" step="1" required defaultValue={recipe?.servings || 4} /></label></div>
      <p className="field-group-label">Ingredients</p>
      <p className="form-hint">Quantities are for the servings above. Use the same unit spelling to let meals combine; different units are never converted.</p>
      <ul className="ingredient-rows">{rows.map((row, index) => <li key={row.key}>
        <label><span className="visually-hidden">Ingredient {index + 1}</span><input value={row.name} maxLength={200} placeholder="Ingredient" onChange={e => change(row.key, 'name', e.target.value)} /></label>
        <label><span className="visually-hidden">Quantity {index + 1}</span><input type="number" min="0.001" step="0.001" value={row.quantity} required={Boolean(row.name.trim())} onChange={e => change(row.key, 'quantity', e.target.value)} /></label>
        <label><span className="visually-hidden">Unit {index + 1}</span><input value={row.unit} maxLength={40} placeholder="unit" onChange={e => change(row.key, 'unit', e.target.value)} /></label>
        <label className="ingredient-category"><span className="visually-hidden">Grocery category {index + 1}</span><input value={row.category} maxLength={80} placeholder="aisle" onChange={e => change(row.key, 'category', e.target.value)} /></label>
        <button type="button" className="icon-button" aria-label={'Remove ingredient ' + (index + 1)} onClick={() => setRows(r => r.length > 1 ? r.filter(x => x.key !== row.key) : [blank()])}><X size={15} /></button>
      </li>)}</ul>
      <button type="button" className="text-button add-link" onClick={() => setRows(r => [...r, blank()])}><Plus size={14} />Add ingredient</button>
      <label className="spaced-label">Notes<textarea name="notes" rows={3} maxLength={10000} defaultValue={recipe?.notes} /></label>
    </fieldset>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="dialog-actions"><button type="button" className="button secondary" disabled={pending} onClick={onClose}>Cancel</button><button className="button primary" disabled={pending}>{pending ? 'Saving…' : recipe ? 'Save changes' : 'Save recipe'}</button></div>
    </form>
  </Dialog>;
}

export function MealEditor({ entry, day, recipes, onClose, onSaved }: { entry?: MealPlanEntry; day: string; recipes: Recipe[]; onClose: () => void; onSaved: (message: string) => void }) {
  const [recipeId, setRecipeId] = useState(entry?.recipe_id || recipes[0]?.id || '');
  const [servings, setServings] = useState(String(entry?.servings || recipes[0]?.servings || 2));
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (pending) return;
    const form = new FormData(e.currentTarget);
    setPending(true); setError('');
    try {
      await api.saveMeal({ plan_date: String(form.get('plan_date')), meal: String(form.get('meal')) as Meal, recipe_id: recipeId, servings: Number(servings) }, entry?.id);
      onSaved(entry ? 'Meal updated.' : 'Meal planned.');
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not save the meal.'); }
    finally { setPending(false); }
  }
  return <Dialog title={entry ? 'Edit meal' : 'Plan a meal'} onClose={onClose} pending={pending}>
    <form onSubmit={submit}><fieldset disabled={pending}>
      <label>Recipe<select value={recipeId} required onChange={e => { setRecipeId(e.target.value); if (!entry) setServings(String(recipes.find(r => r.id === e.target.value)?.servings || servings)); }}>{recipes.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
      <div className="form-pair"><label>Day<input type="date" name="plan_date" required defaultValue={entry?.plan_date || day} /></label><label>Meal<select name="meal" defaultValue={entry?.meal || 'dinner'}>{Object.entries(mealNames).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label></div>
      <label>Servings<input type="number" min="1" max="1000" step="1" required value={servings} onChange={e => setServings(e.target.value)} /></label>
      {entry?.added_to_groceries && <p className="form-hint">This meal’s groceries were already added. Changing servings will not adjust your grocery list.</p>}
    </fieldset>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="dialog-actions"><button type="button" className="button secondary" disabled={pending} onClick={onClose}>Cancel</button><button className="button primary" disabled={pending || !recipeId}>{pending ? 'Saving…' : entry ? 'Save changes' : 'Plan meal'}</button></div>
    </form>
  </Dialog>;
}
