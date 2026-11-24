import { useState, type FormEvent } from 'react';
import { api } from '../../shared/api/client';
import type { Category, CategoryScope, FeatureModule, Settings } from '../../shared/api/contracts';
import { useCategories } from '../../shared/useCategories';
import { featureNames } from '../../shared/domain';
import { Filters } from '../../shared/ui/RecordsView';

export default function SettingsView({ settings, onSaved }: { settings: Settings; onSaved: (message?: string) => void }) {
  const [value, setValue] = useState(settings);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  async function save(e: FormEvent) {
    e.preventDefault();
    if (pending) return;
    setPending(true); setError('');
    try { await api.updateSettings(value); onSaved('Settings saved.'); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not save settings.'); }
    finally { setPending(false); }
  }
  return <section aria-labelledby="view-title" className="settings">
    <header className="page-head"><h1 id="view-title" className="page-title">Settings</h1></header>
    <form className="settings-form" onSubmit={save}><fieldset disabled={pending}>
      <h2 className="section-title">Time and currency</h2>
      <label>Timezone<input value={value.timezone} onChange={e => setValue({ ...value, timezone: e.target.value })} list="timezones" required placeholder="America/New_York" /></label>
      <datalist id="timezones">{['America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles', 'Europe/London', 'Europe/Paris', 'Asia/Kolkata', 'Asia/Tokyo', 'Australia/Sydney', 'UTC'].map(zone => <option key={zone} value={zone} />)}</datalist>
      <label>Default currency<input required pattern="[A-Z]{3}" maxLength={3} value={value.default_currency} onChange={e => setValue({ ...value, default_currency: e.target.value.toUpperCase() })} /></label>
      <p className="form-hint">A three-letter code such as USD, EUR or INR. Existing records keep their own currency.</p>
      <h2 className="section-title">Modules</h2>
      <p className="form-hint">Turning a module off hides it. Its records are kept.</p>
      <div className="module-options">{(Object.keys(featureNames) as FeatureModule[]).map(module => <label key={module} className="choice"><input type="checkbox" checked={value.enabled_modules.includes(module)} onChange={e => setValue({ ...value, enabled_modules: e.target.checked ? [...value.enabled_modules, module] : value.enabled_modules.filter(m => m !== module) })} />{featureNames[module]}</label>)}</div>
    </fieldset>
      {error && <p role="alert" className="error">{error}</p>}
      <div className="form-actions"><button className="button primary" disabled={pending}>{pending ? 'Saving…' : 'Save settings'}</button></div>
    </form>
    <CategoryManager />
  </section>;
}

const scopes: [CategoryScope, string][] = [['task', 'Tasks'], ['expense', 'Expenses'], ['income', 'Income'], ['grocery', 'Groceries']];

/** Rename, archive and restore categories. Archived ones stay on the records that use them. */
function CategoryManager() {
  const [scope, setScope] = useState<CategoryScope>('expense');
  const { all, error, loading, add } = useCategories(scope);
  const [name, setName] = useState('');
  const [message, setMessage] = useState('');
  const [failure, setFailure] = useState('');
  const [pending, setPending] = useState(false);
  async function create(e: FormEvent) {
    e.preventDefault();
    if (pending || !name.trim()) return;
    setPending(true); setFailure(''); setMessage('');
    try { const category = await add(scope, name.trim()); setName(''); setMessage('“' + category.name + '” is in the list.'); }
    catch (err) { setFailure(err instanceof Error ? err.message : 'Could not add the category.'); }
    finally { setPending(false); }
  }
  const sorted = [...all].sort((a, b) => Number(a.archived) - Number(b.archived));
  return <section aria-labelledby="categories-title" className="category-manager">
    <h2 id="categories-title" className="section-title">Categories</h2>
    <p className="form-hint">Expenses and budgets share one list. Archiving keeps a category on existing records but stops offering it for new ones.</p>
    <Filters label="Category list" value={scope} options={scopes} onChange={value => { setScope(value); setMessage(''); setFailure(''); }} />
    {error && <p role="alert" className="error">{error}</p>}
    {loading && <p role="status" className="loading">Loading…</p>}
    <ul className="rows">{sorted.map(category => <CategoryRow key={category.id} category={category} onDone={setMessage} />)}</ul>
    <form className="inline-form" onSubmit={create}>
      <label>New category<input value={name} maxLength={80} disabled={pending} onChange={e => setName(e.target.value)} /></label>
      <button className="button secondary small" disabled={pending || !name.trim()}>{pending ? 'Adding…' : 'Add'}</button>
    </form>
    {failure && <p role="alert" className="error">{failure}</p>}
    {message && <p role="status" className="success">{message}</p>}
  </section>;
}

function CategoryRow({ category, onDone }: { category: Category; onDone: (message: string) => void }) {
  const { replace } = useCategories();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(category.name);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  async function update(nextName: string, archived: boolean, message: string) {
    if (pending) return;
    setPending(true); setError('');
    try { const saved = await api.updateCategory(category.id, nextName, archived); replace(saved); setEditing(false); onDone(message); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not update the category.'); }
    finally { setPending(false); }
  }
  return <li className={'row category-row' + (category.archived ? ' done' : '')}>
    {editing
      ? <form className="inline-form grow" onSubmit={e => { e.preventDefault(); void update(name.trim(), category.archived, 'Renamed to “' + name.trim() + '”.'); }}>
        <label><span className="visually-hidden">Rename {category.name}</span><input value={name} autoFocus maxLength={80} required disabled={pending} onChange={e => setName(e.target.value)} onKeyDown={e => { if (e.key === 'Escape') { e.preventDefault(); setEditing(false); setName(category.name); } }} /></label>
        <button className="button secondary small" disabled={pending || !name.trim()}>Save</button>
        <button type="button" className="text-button" disabled={pending} onClick={() => { setEditing(false); setName(category.name); }}>Cancel</button>
      </form>
      : <div className="row-copy"><span className="row-title static">{category.name}</span>{category.archived && <span className="row-meta">Archived</span>}</div>}
    {!editing && <div className="row-actions visible">
      <button className="text-button" disabled={pending} onClick={() => setEditing(true)} aria-label={'Rename ' + category.name}>Rename</button>
      <button className="text-button" disabled={pending} onClick={() => update(category.name, !category.archived, (category.archived ? 'Restored “' : 'Archived “') + category.name + '”.')} aria-label={(category.archived ? 'Restore ' : 'Archive ') + category.name}>{category.archived ? 'Restore' : 'Archive'}</button>
    </div>}
    {error && <p role="alert" className="field-error full">{error}</p>}
  </li>;
}
