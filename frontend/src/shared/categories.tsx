import { useCallback, useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { api } from './api/client';
import type { Category, CategoryScope } from './api/contracts';
import { CategoriesContext, SEARCH_THRESHOLD, useCategories } from './useCategories';

/** One shared, lazily loaded category list for the signed-in account. */
export function CategoriesProvider({ revision, children }: { revision: number; children: ReactNode }) {
  const [categories, setCategories] = useState<Category[]>();
  const [error, setError] = useState('');
  const wanted = useRef(false);
  const [attempt, setAttempt] = useState(0);
  const load = useCallback(() => { if (!wanted.current) { wanted.current = true; setAttempt(a => a + 1); } }, []);
  useEffect(() => {
    if (!wanted.current) return;
    const controller = new AbortController();
    setError('');
    api.categories(controller.signal).then(list => { if (!controller.signal.aborted) setCategories(list); })
      .catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Could not load categories.'); });
    return () => controller.abort();
  }, [revision, attempt]);
  const replace = useCallback((category: Category) => setCategories(list => {
    const rest = (list || []).filter(c => c.id !== category.id);
    return [...rest, category];
  }), []);
  const add = useCallback(async (scope: CategoryScope, name: string) => {
    const category = await api.createCategory(scope, name);
    replace(category);
    return category;
  }, [replace]);
  const value = useMemo(() => ({ categories, error, load, add, replace }), [categories, error, load, add, replace]);
  return <CategoriesContext.Provider value={value}>{children}</CategoriesContext.Provider>;
}

const ADD = '__add__';
const scopeNoun: Record<CategoryScope, string> = { task: 'category', expense: 'category', income: 'source', grocery: 'aisle' };

/**
 * Pick a category, or add one without leaving the form. Short lists use a native select;
 * longer lists become a searchable combobox. The chosen id is posted under `name`.
 * A record's archived category stays selectable for that record only.
 */
export function CategorySelect({ scope, name = 'category_id', label, defaultValue = null, required = false, hideLabel = false, onChange }: { scope: CategoryScope; name?: string; label: string; defaultValue?: string | null; required?: boolean; hideLabel?: boolean; onChange?: (id: string | null) => void }) {
  const { all, active, loading, error, add } = useCategories(scope);
  const [value, setValue] = useState<string | null>(defaultValue);
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState('');
  const [addError, setAddError] = useState('');
  const [pending, setPending] = useState(false);
  const id = useId();
  const current = all.find(c => c.id === value);
  const options = current && current.archived ? [...active, current] : active;
  const choose = (next: string | null) => { setValue(next); onChange?.(next); };
  async function create(text = draft) {
    const trimmed = text.trim();
    if (!trimmed || pending) return;
    setPending(true); setAddError('');
    try { const category = await add(scope, trimmed); choose(category.id); setAdding(false); setDraft(''); }
    catch (err) { setAddError(err instanceof Error ? err.message : 'Could not add that.'); }
    finally { setPending(false); }
  }
  const enterAdds = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') { event.preventDefault(); void create(); }
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); setAdding(false); }
  };
  const noun = scopeNoun[scope];
  const labelText = <span className={hideLabel ? 'visually-hidden' : undefined}>{label}</span>;
  if (loading) return <label className="category-field">{labelText}<select disabled aria-busy="true"><option>Loading…</option></select></label>;
  return <div className="category-field">
    <input type="hidden" name={name} value={value || ''} />
    {options.length > SEARCH_THRESHOLD && !adding
      ? <CategoryCombobox id={id} label={labelText} options={options} value={value} required={required} onChoose={choose} onAdd={text => { setDraft(text); setAdding(true); }} noun={noun} />
      : !adding && <label htmlFor={id}>{labelText}<select id={id} value={value || ''} required={required} onChange={e => { if (e.target.value === ADD) { setAdding(true); setAddError(''); } else choose(e.target.value || null); }}>
        <option value="" disabled={required}>{required ? 'Choose a ' + noun : 'None'}</option>
        {options.map(c => <option key={c.id} value={c.id}>{c.name}{c.archived ? ' (archived)' : ''}</option>)}
        <option value={ADD}>+ Add {noun}…</option>
      </select></label>}
    {adding && <div className="category-add">
      <label htmlFor={id + '-new'}>{hideLabel ? <span className="visually-hidden">{'New ' + noun}</span> : 'New ' + noun}</label>
      <div className="category-add-row">
        <input id={id + '-new'} autoFocus value={draft} maxLength={80} disabled={pending} placeholder={'Name the ' + noun} onChange={e => setDraft(e.target.value)} onKeyDown={enterAdds} />
        <button type="button" className="button secondary small" disabled={pending || !draft.trim()} onClick={() => create()}>{pending ? 'Adding…' : 'Add'}</button>
        <button type="button" className="text-button" disabled={pending} onClick={() => { setAdding(false); setAddError(''); }}>Cancel</button>
      </div>
    </div>}
    {(addError || error) && <p className="field-error" role="alert">{addError || error}</p>}
  </div>;
}

function CategoryCombobox({ id, label, options, value, required, onChoose, onAdd, noun }: { id: string; label: ReactNode; options: Category[]; value: string | null; required: boolean; onChoose: (id: string | null) => void; onAdd: (text: string) => void; noun: string }) {
  const selected = options.find(c => c.id === value);
  const [text, setText] = useState(selected?.name || '');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const query = text.trim().toLocaleLowerCase();
  const matches = query && text !== selected?.name ? options.filter(c => c.name.toLocaleLowerCase().includes(query)) : options;
  const exact = options.some(c => c.name.toLocaleLowerCase() === query);
  const items: { key: string; label: string; pick: () => void }[] = [
    ...matches.map(c => ({ key: c.id, label: c.name + (c.archived ? ' (archived)' : ''), pick: () => { onChoose(c.id); setText(c.name); setOpen(false); } })),
    { key: ADD, label: query && !exact ? `+ Add “${text.trim()}”` : `+ Add ${noun}…`, pick: () => { setOpen(false); onAdd(exact ? '' : text.trim()); } },
  ];
  const listId = id + '-list';
  function keyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown') { event.preventDefault(); setOpen(true); setActive(a => Math.min(items.length - 1, open ? a + 1 : 0)); }
    else if (event.key === 'ArrowUp') { event.preventDefault(); setActive(a => Math.max(0, a - 1)); }
    else if (event.key === 'Enter' && open) { event.preventDefault(); (items[active] || (matches.length === 1 ? items[0] : undefined))?.pick(); }
    else if (event.key === 'Escape' && open) { event.preventDefault(); event.stopPropagation(); setOpen(false); setText(selected?.name || ''); }
  }
  return <div className="combobox">
    <label htmlFor={id}>{label}</label>
    <input id={id} role="combobox" aria-expanded={open} aria-controls={listId} aria-autocomplete="list" autoComplete="off" required={required}
      aria-activedescendant={open && active >= 0 ? id + '-' + active : undefined} value={text} placeholder={'Search or add a ' + noun}
      onFocus={() => { setOpen(true); setActive(-1); }} onClick={() => setOpen(true)} onKeyDown={keyDown}
      onBlur={() => { setOpen(false); if (!text.trim()) onChoose(null); else if (selected) setText(selected.name); }}
      onChange={e => { setText(e.target.value); setOpen(true); setActive(-1); }} />
    {open && <ul id={listId} role="listbox" className="combobox-list">{items.map((item, index) =>
      <li key={item.key} id={id + '-' + index} role="option" aria-selected={item.key === value} className={index === active ? 'active' : ''}
        onMouseDown={event => { event.preventDefault(); item.pick(); }}>{item.label}</li>)}</ul>}
  </div>;
}
