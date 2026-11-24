import { useCallback, useEffect, useState } from 'react';
import { formatInTimeZone } from 'date-fns-tz';
import { Plus } from 'lucide-react';
import type { CalendarEntry } from '../../shared/api/contracts';
import { api } from '../../shared/api/client';
import { longDate } from '../../shared/domain';
import { useResource } from '../../shared/hooks/useResource';
import { RecordRow } from '../../shared/ui/RecordRow';
import { Filters, PageHead, Pagination, type ViewProps } from '../../shared/ui/RecordsView';

export default function CalendarView({ revision, zone, onAdd, ...actions }: ViewProps) {
  const [offset, setOffset] = useState(0);
  const [period, setPeriod] = useState<'upcoming' | 'past' | 'all'>('upcoming');
  const [retry, setRetry] = useState(0);
  const load = useCallback((signal: AbortSignal) => api.list('calendar', offset, period, signal), [offset, period]);
  const { data, loading, error } = useResource(load, revision + retry);
  useEffect(() => {
    if (data && offset > 0 && offset >= data.total)
      setOffset(Math.max(0, Math.floor((data.total - 1) / 25) * 25));
  }, [data, offset]);
  const days = Object.entries((data?.items || []).reduce<Record<string, CalendarEntry[]>>((groups, event) => {
    const day = event.all_day ? event.start_date! : formatInTimeZone(event.start, zone, 'yyyy-MM-dd');
    (groups[day] ||= []).push(event);
    return groups;
  }, {}));
  return <section aria-labelledby="view-title">
    <PageHead title="Calendar" count={'Times in ' + zone} action={<button className="button secondary small" onClick={() => onAdd('calendar')}><Plus size={16} />Add event</button>} />
    <Filters label="Filter calendar" value={period} options={[['upcoming', 'Upcoming'], ['past', 'Past'], ['all', 'All']]} onChange={value => { setPeriod(value); setOffset(0); }} />
    {error && <div className="error" role="alert">{error}<button className="text-button" onClick={() => setRetry(r => r + 1)}>Try again</button></div>}
    {loading && !data && <p role="status" className="loading">Loading…</p>}
    {!error && data && (days.length ? <div aria-busy={loading}>{days.map(([day, events]) => <section key={day} className="day-group" aria-label={longDate(day)}>
      <h2 className="day-heading">{longDate(day)}</h2>
      <ul className="rows">{events.map(event => <RecordRow key={event.id} module="calendar" item={event} zone={zone} {...actions} />)}</ul>
    </section>)}</div> : <div className="empty"><p>No {period === 'all' ? '' : period + ' '}events.</p><button className="text-button" onClick={() => onAdd('calendar')}><Plus size={15} />Add event</button></div>)}
    {data && <Pagination offset={offset} total={data.total} loading={loading} onChange={setOffset} />}
  </section>;
}
