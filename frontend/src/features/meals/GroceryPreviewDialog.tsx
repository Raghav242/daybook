import { useCallback, useState } from 'react';
import { api } from '../../shared/api/client';
import type { GroceryPreview, PreviewLine } from '../../shared/api/contracts';
import { quantity } from '../../shared/domain';
import { useResource } from '../../shared/hooks/useResource';
import { Dialog } from '../../shared/ui/Dialog';

type Draft = { include: boolean; quantity: string };

/** Review scaled ingredient quantities before anything is added to groceries. */
export function GroceryPreviewDialog({ entryIds, onClose, onAdded }: { entryIds: string[]; onClose: () => void; onAdded: (message: string) => void }) {
  // One id per review: retries and double submits are recognized by the server.
  const [requestId] = useState(() => crypto.randomUUID());
  const load = useCallback((signal: AbortSignal) => api.groceryPreview(entryIds, signal), [entryIds]);
  const { data, error: loadError, loading } = useResource<GroceryPreview>(load, 0);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const draft = (line: PreviewLine): Draft => drafts[line.key] || { include: true, quantity: quantity(line.quantity) };
  const update = (line: PreviewLine, change: Partial<Draft>) => setDrafts(d => ({ ...d, [line.key]: { ...draft(line), ...change } }));
  const pendingEntries = data ? data.entries.filter(e => !e.added_to_groceries).map(e => e.id) : [];
  const chosen = data ? data.items.filter(line => draft(line).include) : [];
  async function add() {
    if (pending || !data || !chosen.length) return;
    const invalid = chosen.find(line => !(Number(draft(line).quantity) > 0));
    if (invalid) { setError('Enter a quantity above zero for ' + invalid.name + ', or leave it out.'); return; }
    setPending(true); setError('');
    try {
      const result = await api.addGroceries(requestId, pendingEntries, chosen.map(line => ({ name: line.name, unit: line.unit, category: line.category, quantity: draft(line).quantity })));
      onAdded(result.created ? `Added ${result.added} ${result.added === 1 ? 'item' : 'items'} to groceries.` : 'These groceries were already added.');
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not add groceries.'); }
    finally { setPending(false); }
  }
  return <Dialog title="Review grocery list" onClose={onClose} pending={pending}>
    {loading && !data && <p role="status" className="loading">Gathering ingredients…</p>}
    {loadError && <p className="error" role="alert">{loadError}</p>}
    {data && <>
      <p className="dialog-lead">From {pendingEntries.length} planned {pendingEntries.length === 1 ? 'meal' : 'meals'}, scaled to their servings. Adjust anything before adding. Your existing list is left as it is.</p>
      {data.skipped_entry_ids.length > 0 && <p className="form-hint">{data.skipped_entry_ids.length} {data.skipped_entry_ids.length === 1 ? 'meal was' : 'meals were'} already added and {data.skipped_entry_ids.length === 1 ? 'is' : 'are'} not counted again.</p>}
      {data.items.length ? <ul className="preview-list">{data.items.map(line => { const d = draft(line); return <li key={line.key} className={d.include ? '' : 'excluded'}>
        <input type="checkbox" className="record-check" checked={d.include} disabled={pending} aria-label={'Include ' + line.name + (line.unit ? ' (' + line.unit + ')' : '')} onChange={e => update(line, { include: e.target.checked })} />
        <div className="preview-copy"><strong>{line.name}</strong><span>{line.sources.join(', ')}{line.on_list ? ' · ' + quantity(line.on_list) + (line.unit ? ' ' + line.unit : '') + ' already on your list' : ''}{line.other_units ? ' · Kept separate: different units' : ''}</span></div>
        <label className="preview-quantity"><span className="visually-hidden">Quantity of {line.name}</span><input type="number" min="0.001" step="0.001" value={d.quantity} disabled={pending || !d.include} onChange={e => update(line, { quantity: e.target.value })} /></label>
        <span className="preview-unit">{line.unit}</span>
      </li>; })}</ul> : <p className="muted lower-empty">Nothing new to add from these meals.</p>}
    </>}
    {error && <p className="error" role="alert">{error}</p>}
    <div className="dialog-actions"><button type="button" className="button secondary" disabled={pending} onClick={onClose}>Cancel</button><button className="button primary" disabled={pending || !chosen.length || !pendingEntries.length} onClick={add}>{pending ? 'Adding…' : `Add ${chosen.length} to groceries`}</button></div>
  </Dialog>;
}
