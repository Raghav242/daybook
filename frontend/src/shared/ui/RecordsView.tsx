import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { ArrowLeft, ArrowRight, Plus } from 'lucide-react';
import { api } from '../api/client';
import type { Module } from '../api/contracts';
import { moduleNames, singular } from '../domain';
import { useResource } from '../hooks/useResource';
import { RecordRow, type RowActions } from './RecordRow';

export type ViewProps = RowActions & { revision: number; zone: string; today?: string; onAdd: (module: Module) => void };

/** Page title with a single, consistent secondary Add action. */
export function PageHead({ title, count, action }: { title: string; count?: string; action?: ReactNode }) {
  return <header className="page-head split"><div><h1 id="view-title" className="page-title">{title}</h1>{count && <p className="page-date">{count}</p>}</div>{action}</header>;
}

export function Pagination({ offset, total, loading, onChange }: { offset: number; total: number; loading: boolean; onChange: (offset: number) => void }) {
  if (total <= 25) return null;
  return <nav className="pagination" aria-label="Pages"><button className="button secondary small" disabled={loading || offset === 0} onClick={() => onChange(offset - 25)}><ArrowLeft size={16} />Previous</button><span>{offset + 1}–{Math.min(offset + 25, total)} of {total}</span><button className="button secondary small" disabled={loading || offset + 25 >= total} onClick={() => onChange(offset + 25)}>Next<ArrowRight size={16} /></button></nav>;
}

export function Filters<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: [T, string][]; onChange: (value: T) => void }) {
  return <div className="segmented" role="group" aria-label={label}>{options.map(([key, text]) => <button key={key} aria-pressed={value === key} onClick={() => onChange(key)}>{text}</button>)}</div>;
}

export function RecordsView({ module, revision, zone, today, onAdd, ...actions }: ViewProps & { module: Module }) {
  const [offset, setOffset] = useState(0);
  const [filter, setFilter] = useState<'' | 'false' | 'true'>(module === 'calendar' ? '' : 'false');
  const [retry, setRetry] = useState(0);
  const load = useCallback((signal: AbortSignal) => api.list(module, offset, filter, signal), [module, offset, filter]);
  const { data, loading, error } = useResource(load, revision + retry);
  useEffect(() => {
    if (data && offset > 0 && offset >= data.total)
      setOffset(Math.max(0, Math.floor((data.total - 1) / 25) * 25));
  }, [data, offset]);
  const labels = module === 'tasks' ? ['To do', 'Done'] : module === 'groceries' ? ['To buy', 'Bought'] : ['Unpaid', 'Paid'];
  return <section aria-labelledby="view-title">
    <PageHead title={moduleNames[module]} count={data ? data.total + ' ' + (filter === 'false' ? labels[0].toLowerCase() : filter === 'true' ? labels[1].toLowerCase() : 'in all') : undefined}
      action={<button className="button secondary small" onClick={() => onAdd(module)}><Plus size={16} />Add {singular[module]}</button>} />
    <Filters label={'Filter ' + moduleNames[module].toLowerCase()} value={filter} options={[['false', labels[0]], ['true', labels[1]], ['', 'All']]} onChange={value => { setFilter(value); setOffset(0); }} />
    {error && <div role="alert" className="error">{error}<button className="text-button" onClick={() => setRetry(r => r + 1)}>Try again</button></div>}
    {loading && !data && <p role="status" className="loading">Loading…</p>}
    {!error && data && (data.items.length ? <ul className="rows" aria-busy={loading}>{data.items.map(item => <RecordRow key={item.id} module={module} item={item} zone={zone} today={today} {...actions} />)}</ul>
      : <div className="empty"><p>{filter === 'true' ? 'Nothing here yet.' : filter === 'false' ? 'All clear.' : 'No ' + moduleNames[module].toLowerCase() + ' yet.'}</p>{filter !== 'true' && <button className="text-button" onClick={() => onAdd(module)}><Plus size={15} />Add {singular[module]}</button>}</div>)}
    {data && <Pagination offset={offset} total={data.total} loading={loading} onChange={setOffset} />}
  </section>;
}
