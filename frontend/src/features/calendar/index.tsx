import { useCallback, useEffect, useState, type ComponentProps } from 'react';
import { formatInTimeZone } from 'date-fns-tz';
import { ArrowLeft, ArrowRight, Plus } from 'lucide-react';
import type { CalendarEntry } from '../../shared/api/contracts';
import { api } from '../../shared/api/client';
import { dateLabel } from '../../shared/domain';
import { useResource } from '../../shared/hooks/useResource';
import { RecordRow } from '../../shared/ui/RecordRow';
import { RecordsView } from '../../shared/ui/RecordsView';

export default function CalendarView({ revision, zone, onAdd, ...actions }: Omit<ComponentProps<typeof RecordsView>, 'module'>) {
  const [offset, setOffset] = useState(0);
  const [period, setPeriod] = useState('upcoming');
  const [retry, setRetry] = useState(0);
  const load = useCallback((signal: AbortSignal) => api.list('calendar', offset, period, signal), [offset, period]);
  const { data, loading, error } = useResource(load, revision + retry);
  useEffect(() => {
    if (data && offset > 0 && offset >= data.total)
      setOffset(Math.max(0, Math.floor((data.total - 1) / 25) * 25));
  }, [data, offset]);
  const entries = Object.entries((data?.items || []).reduce<Record<string, CalendarEntry[]>>((days, event) => {
    const day = event.all_day ? event.start_date! : formatInTimeZone(event.start, zone, 'yyyy-MM-dd');
    (days[day] ||= []).push(event);
    return days;
  }, {}));
  return <section aria-labelledby="view-title">
    <div className="page-heading"><div><p className="eyebrow">YOUR DAYBOOK</p><h1 id="view-title">Calendar</h1><p className="page-subtitle">Your plans, one day at a time. Times in {zone}.</p></div><button className="button primary" onClick={() => onAdd('calendar')}><Plus size={17} />Add event</button></div>
    <div className="list-toolbar"><div className="tabs" aria-label="Filter calendar">{[['upcoming', 'Upcoming'], ['past', 'Past'], ['all', 'All']].map(([value, label]) => <button key={value} aria-pressed={period === value} className={period === value ? 'active' : ''} onClick={() => {setPeriod(value); setOffset(0);}}>{label}</button>)}</div><span className="muted">{data?.total ?? 0} events</span></div>
    {error && <div className="error" role="alert">{error}<button className="text-button" onClick={() => setRetry(r => r + 1)}>Try again</button></div>}
    {loading && !data && <p role="status" className="loading">Loading your agenda…</p>}
    {!error && data && (entries.length ? <div className="calendar-days" aria-busy={loading}>{entries.map(([day, events]) => <section key={day} className="calendar-day"><h2>{dateLabel(day, true)}</h2><ul className="records-list">{events.map(event => <RecordRow key={event.id} module="calendar" item={event} zone={zone} {...actions} />)}</ul></section>)}</div> : <div className="empty-state"><h2>Room for a new plan</h2><p>No {period === 'all' ? '' : period + ' '}events here yet.</p><button className="button secondary" onClick={() => onAdd('calendar')}>Add event</button></div>)}
    {data && data.total > 25 && <div className="pagination"><button className="button secondary" disabled={loading || offset === 0} onClick={() => setOffset(o => o - 25)}><ArrowLeft size={16} />Previous</button><span>{offset + 1}–{Math.min(offset + 25, data.total)} of {data.total}</span><button className="button secondary" disabled={loading || offset + 25 >= data.total} onClick={() => setOffset(o => o + 25)}>Next<ArrowRight size={16} /></button></div>}
  </section>;
}

