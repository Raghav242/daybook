import { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, ArrowRight, Plus } from 'lucide-react';
import { api } from '../api/client';
import type { Module } from '../api/contracts';
import { moduleNames, singular } from '../domain';
import { useResource } from '../hooks/useResource';
import { RecordRow, type RowActions } from './RecordRow';

const subtitles: Record<Module, string> = {
  tasks: 'Make room for what matters. One thing at a time.',
  calendar: 'A clear view of your plans, in the order they happen.',
  groceries: 'A small list for your next trip to the store.',
  bills: 'Keep track of what’s due and what’s taken care of.',
};
export function RecordsView({ module, revision, zone, onAdd, ...actions }: RowActions & { module: Module; revision: number; zone: string; onAdd: (module: Module) => void }) {
  const [offset, setOffset] = useState(0);
  const [filter, setFilter] = useState('');
  const [retry, setRetry] = useState(0);
  const load = useCallback((signal: AbortSignal) => api.list(module, offset, filter, signal), [module, offset, filter]);
  const { data, loading, error } = useResource(load, revision + retry);
  useEffect(() => {
    if (data && offset > 0 && offset >= data.total)
      setOffset(Math.max(0, Math.floor((data.total - 1) / 25) * 25));
  }, [data, offset]);
  const labels = module === 'tasks' ? ['To do', 'Completed'] : module === 'groceries' ? ['To buy', 'Purchased'] : ['Unpaid', 'Paid'];
  return <section className="page-section" aria-labelledby="view-title">
    <div className="page-heading"><div><p className="eyebrow">YOUR DAYBOOK</p><h1 id="view-title">{moduleNames[module]}</h1><p className="page-subtitle">{subtitles[module]}</p></div><button className="button primary" onClick={() => onAdd(module)}><Plus size={17} />Add {singular[module]}</button></div>
    <div className="list-toolbar">{module !== 'calendar' && <div className="tabs" aria-label="Filter records">{[['', 'All'], ['false', labels[0]], ['true', labels[1]]].map(([value, label]) => <button key={value} aria-pressed={filter === value} className={filter === value ? 'active' : ''} onClick={() => { setFilter(value); setOffset(0); }}>{label}</button>)}</div>}<span className="muted">{data ? data.total + ' ' + (data.total === 1 ? 'record' : 'records') : ''}</span></div>
    {error && <div role="alert" className="error">{error}<button className="text-button" onClick={() => setRetry(r => r + 1)}>Try again</button></div>}
    {loading && !data && <p role="status" className="loading">Loading {moduleNames[module].toLowerCase()}…</p>}
    {!error && data && (data.items.length ? <ul className="records-list" aria-busy={loading}>{data.items.map(item => <RecordRow key={item.id} module={module} item={item} zone={zone} {...actions} />)}</ul> : <div className="empty-state"><h2>{filter ? 'Nothing in this view' : 'A fresh start'}</h2><p>{filter ? 'Try another filter, or add a new record.' : 'Add your first ' + singular[module] + ' to get started.'}</p><button className="button secondary" onClick={() => onAdd(module)}><Plus size={16} />Add {singular[module]}</button></div>)}
    {data && data.total > 25 && <div className="pagination"><button className="button secondary" disabled={loading || offset === 0} onClick={() => setOffset(o => o - 25)}><ArrowLeft size={16} />Previous</button><span>{offset + 1}–{Math.min(offset + 25, data.total)} of {data.total}</span><button className="button secondary" disabled={loading || offset + 25 >= data.total} onClick={() => setOffset(o => o + 25)}>Next<ArrowRight size={16} /></button></div>}
  </section>;
}

