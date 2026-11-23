import { useEffect, useState, type FormEvent } from 'react';
import { Repeat } from 'lucide-react';
import { api } from '../api/client';
import type { Bill, BillSeriesInput, CalendarEntry, Frequency, Grocery, Module, RecordInput, RecordItem, Recurrence, Settings, Task, TaskSeriesInput } from '../api/contracts';
import { localInput, moduleNames, recordModules, repeatLabel, singular, zonedInstant } from '../domain';
import { Dialog } from './Dialog';

type Scope = 'this' | 'future';
const repeatOptions: [Frequency | 'none', string][] = [['none', 'Does not repeat'], ['daily', 'Daily'], ['weekly', 'Weekly'], ['monthly', 'Monthly']];

export function RecordEditor({ initialModule, item, settings, onClose, onSaved }: { initialModule?: Module; item?: RecordItem; settings: Settings; onClose: () => void; onSaved: (message?: string) => void }) {
  const modules = recordModules(settings.enabled_modules);
  const [module, setModule] = useState<Module>(initialModule || modules[0] || 'tasks');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const task = item as Task | undefined, event = item as CalendarEntry | undefined, grocery = item as Grocery | undefined, bill = item as Bill | undefined;
  const [deadline, setDeadline] = useState(task?.due_at ? 'time' : task?.due_date ? 'date' : 'none');
  const [allDay, setAllDay] = useState(event?.all_day || false);
  const seriesId = item && 'series_id' in item ? item.series_id : null;
  const [scope, setScope] = useState<Scope>('this');
  const [repeat, setRepeat] = useState<Frequency | 'none'>('none');
  const [rule, setRule] = useState<Recurrence>();
  const [stopping, setStopping] = useState(false);
  const repeating = module === 'tasks' || module === 'bills';
  // Editing "this and future" needs the current definition to prefill its repeat rule.
  useEffect(() => {
    if (!seriesId || scope !== 'future' || rule || !repeating) return;
    const controller = new AbortController();
    api.series(module as 'tasks' | 'bills', seriesId, controller.signal).then(series => { setRule(series); setRepeat(series.frequency); })
      .catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Could not load the repeat rule.'); });
    return () => controller.abort();
  }, [seriesId, scope, rule, module, repeating]);
  const recurringForm = repeating && repeat !== 'none' && (!item || scope === 'future');

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (pending) return;
    const form = new FormData(e.currentTarget);
    const text = (key: string) => String(form.get(key) || '').trim();
    setError('');
    try {
      if (recurringForm) {
        const recurrence: Recurrence = { frequency: repeat as Frequency, interval: Number(text('interval') || '1'), start_date: text('start_date'), until_date: text('until_date') || null };
        const value = module === 'tasks'
          ? { ...recurrence, title: text('title'), notes: text('notes'), category: text('category'), priority: text('priority') as Task['priority'] } satisfies TaskSeriesInput
          : { ...recurrence, name: text('name'), amount: text('amount'), currency: text('currency').toUpperCase() } satisfies BillSeriesInput;
        setPending(true);
        if (item) await api.updateFuture(module as 'tasks', item.id, value as TaskSeriesInput);
        else await api.createSeries(module as 'tasks', value as TaskSeriesInput);
        onSaved(item ? 'Updated this and future occurrences.' : 'Repeating ' + singular[module] + ' added.');
        return;
      }
      let value: RecordInput;
      switch (module) {
        case 'tasks':
          value = { title: text('title'), notes: text('notes'), category: text('category'), priority: text('priority') as Task['priority'], completed: task?.completed || false, due_date: deadline === 'date' ? text('due_date') : null, due_at: deadline === 'time' ? zonedInstant(text('due_at'), settings.timezone) : null };
          break;
        case 'calendar':
          value = { title: text('title'), description: text('description'), all_day: allDay, start_date: allDay ? text('start_date') : null, end_date: allDay ? text('end_date') : null, start: zonedInstant(allDay ? text('start_date') + 'T00:00' : text('start'), settings.timezone), end: zonedInstant(allDay ? text('end_date') + 'T00:00' : text('end'), settings.timezone) };
          break;
        case 'groceries':
          value = { name: text('name'), quantity: text('quantity'), unit: text('unit'), category: text('category'), purchased: grocery?.purchased || false };
          break;
        case 'bills':
          value = { name: text('name'), amount: text('amount'), currency: text('currency').toUpperCase(), due_date: text('due_date'), paid: bill?.paid || false };
      }
      setPending(true);
      await api.save(module, value, item?.id);
      onSaved();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not save. Try again.'); }
    finally { setPending(false); }
  }
  async function stop() {
    if (!seriesId || pending) return;
    setPending(true); setError('');
    try { await api.stopSeries(module as 'tasks' | 'bills', seriesId); onSaved('Stopped repeating. Completed and overdue items were kept.'); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not stop repeating.'); }
    finally { setPending(false); }
  }
  const dateName = recurringForm ? 'start_date' : 'due_date';
  const dateDefault = item ? (task?.due_date || bill?.due_date || '') : '';
  const repeatFields = repeating && (!item || (seriesId && scope === 'future')) && <>
    <label>Repeats<select value={repeat} onChange={e => setRepeat(e.target.value as Frequency | 'none')}>{repeatOptions.filter(([value]) => !item || value !== 'none').map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    {recurringForm && <div className="form-pair">
      <label>Every<input type="number" name="interval" min="1" max="99" step="1" required defaultValue={rule?.interval || 1} key={'interval-' + (rule?.interval || 1)} /></label>
      <label>Ends (optional)<input type="date" name="until_date" defaultValue={rule?.until_date || ''} key={'until-' + (rule?.until_date || '')} /></label>
    </div>}
    {recurringForm && <p className="form-hint">{repeat === 'monthly' ? 'Dates past the end of a short month fall on its last day.' : repeat === 'weekly' ? 'Repeats on the same weekday as the first date.' : 'Each occurrence is tracked on its own.'} Past dates are not filled in.</p>}
  </>;
  return <Dialog title={item ? 'Edit ' + singular[module] : initialModule ? 'Add ' + singular[module] : 'Quick capture'} onClose={onClose} pending={pending}>
    <form onSubmit={submit}>
      {!initialModule && <label>Record type<select value={module} disabled={pending} onChange={e => { setModule(e.target.value as Module); setError(''); setRepeat('none'); }}>{modules.map(m => <option key={m} value={m}>{moduleNames[m]}</option>)}</select></label>}
      {seriesId && <fieldset className="scope-choice" disabled={pending}><legend><Repeat size={14} />{rule ? repeatLabel(rule) : 'Repeating ' + singular[module]}</legend>
        <label className="checkbox-label"><input type="radio" name="scope" checked={scope === 'this'} onChange={() => setScope('this')} />Only this occurrence</label>
        <label className="checkbox-label"><input type="radio" name="scope" checked={scope === 'future'} onChange={() => setScope('future')} />This and future occurrences</label>
      </fieldset>}
      <fieldset disabled={pending || (scope === 'future' && !rule)} key={module}>
        <label>{module === 'tasks' || module === 'calendar' ? 'Title' : 'Name'}<input name={module === 'tasks' || module === 'calendar' ? 'title' : 'name'} autoFocus required maxLength={200} defaultValue={item ? 'title' in item ? item.title : item.name : ''} placeholder={module === 'tasks' ? 'What needs doing?' : module === 'calendar' ? 'What’s coming up?' : module === 'groceries' ? 'e.g. Whole grain bread' : 'e.g. Internet'} /></label>
        {module === 'tasks' && <>
          <label>Notes<textarea name="notes" maxLength={10000} defaultValue={task?.notes} rows={3} /></label>
          <div className="form-pair"><label>Priority<select name="priority" defaultValue={task?.priority || 'normal'}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option></select></label><label>Category<input name="category" maxLength={80} defaultValue={task?.category} placeholder="e.g. School" /></label></div>
          {repeatFields}
          {recurringForm ? <label>{item ? 'From' : 'Starts on'}<input type="date" name="start_date" required defaultValue={dateDefault} /></label> : <>
            <label>Deadline<select value={deadline} onChange={e => setDeadline(e.target.value)}><option value="none">No deadline</option><option value="date">Date only</option><option value="time">Date and time</option></select></label>
            {deadline === 'date' && <label>Due date<input type="date" name="due_date" required defaultValue={task?.due_date || ''} /></label>}
            {deadline === 'time' && <label>Due at · {settings.timezone}<input type="datetime-local" name="due_at" required defaultValue={task?.due_at ? localInput(task.due_at, settings.timezone) : ''} /></label>}
          </>}
        </>}
        {module === 'calendar' && <>
          <label>Description<textarea name="description" maxLength={10000} rows={3} defaultValue={event?.description} /></label>
          <label className="checkbox-label"><input type="checkbox" checked={allDay} onChange={e => setAllDay(e.target.checked)} />All day</label>
          <p className="form-hint">{allDay ? 'End date is exclusive: for one day, choose the following day.' : 'Times are in ' + settings.timezone + '.'}</p>
          <div className="form-pair">
            <label>Start<input name={allDay ? 'start_date' : 'start'} type={allDay ? 'date' : 'datetime-local'} required key={'start-' + allDay} defaultValue={event ? allDay ? event.start_date || '' : localInput(event.start, settings.timezone) : ''} /></label>
            <label>End<input name={allDay ? 'end_date' : 'end'} type={allDay ? 'date' : 'datetime-local'} required key={'end-' + allDay} defaultValue={event ? allDay ? event.end_date || '' : localInput(event.end, settings.timezone) : ''} /></label>
          </div>
        </>}
        {module === 'groceries' && <>
          <div className="form-pair"><label>Quantity<input type="number" name="quantity" min="0.001" step="0.001" required defaultValue={grocery?.quantity || '1'} /></label><label>Unit<input name="unit" maxLength={40} defaultValue={grocery?.unit} placeholder="e.g. packs" /></label></div>
          <label>Category<input name="category" maxLength={80} defaultValue={grocery?.category} placeholder="e.g. Produce" /></label>
        </>}
        {module === 'bills' && <>
          <div className="form-pair"><label>Amount<input type="number" name="amount" min="0" step="0.01" required defaultValue={bill?.amount} /></label><label>Currency<input name="currency" required pattern="[A-Za-z]{3}" maxLength={3} defaultValue={bill?.currency || settings.default_currency} /></label></div>
          {repeatFields}
          <label>{recurringForm ? item ? 'From' : 'First due date' : 'Due date'}<input type="date" name={dateName} required key={dateName} defaultValue={bill?.due_date} /></label>
          <p className="form-hint">Track a bill and its paid status here. Daybook never moves money.</p>
        </>}
      </fieldset>
      {scope === 'future' && <p className="form-hint">Earlier occurrences keep their details. Completed and paid occurrences are never changed.</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {stopping && <div className="inline-confirm" role="group" aria-label="Stop repeating"><p>Upcoming open occurrences will be removed. Completed, paid and overdue items stay.</p><div><button type="button" className="button secondary" disabled={pending} onClick={() => setStopping(false)}>Keep repeating</button><button type="button" className="button danger" disabled={pending} onClick={stop}>Stop repeating</button></div></div>}
      <div className="dialog-actions">{seriesId && !stopping && <button type="button" className="text-button stop-link" disabled={pending} onClick={() => setStopping(true)}>Stop repeating…</button>}<button type="button" className="button secondary" disabled={pending} onClick={onClose}>Cancel</button><button className="button primary" disabled={pending || (scope === 'future' && !rule)}>{pending ? 'Saving…' : item ? 'Save changes' : 'Add ' + singular[module]}</button></div>
    </form>
  </Dialog>;
}
