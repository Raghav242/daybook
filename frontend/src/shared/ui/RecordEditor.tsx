import { useEffect, useState, type FormEvent } from 'react';
import { Repeat } from 'lucide-react';
import { api } from '../api/client';
import type { Bill, BillSeriesInput, CalendarEntry, Frequency, Grocery, Module, RecordInput, RecordItem, Recurrence, Settings, Task, TaskSeriesInput } from '../api/contracts';
import { CategorySelect } from '../categories';
import { localInput, repeatLabel, singular, zonedInstant } from '../domain';
import { Dialog, MoreDetails } from './Dialog';

type Scope = 'this' | 'future';
const repeatOptions: [Frequency | 'none', string][] = [['none', 'Does not repeat'], ['daily', 'Daily'], ['weekly', 'Weekly'], ['monthly', 'Monthly']];
const placeholders: Record<Module, string> = { tasks: 'What needs doing?', calendar: 'What’s happening?', groceries: 'e.g. Whole grain bread', bills: 'e.g. Internet' };

export interface FormProps { onCancel: () => void; onSaved: (message?: string) => void; onPendingChange?: (pending: boolean) => void }

/** Add or edit one task, event, grocery item or bill. Essential fields first; the rest on request. */
export function RecordForm({ module, item, settings, onCancel, onSaved, onPendingChange }: FormProps & { module: Module; item?: RecordItem; settings: Settings }) {
  const [pending, setPendingState] = useState(false);
  const setPending = (value: boolean) => { setPendingState(value); onPendingChange?.(value); };
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
    const categoryId = text('category_id') || null;
    setError('');
    try {
      if (recurringForm) {
        const recurrence: Recurrence = { frequency: repeat as Frequency, interval: Number(text('interval') || '1'), start_date: text('start_date'), until_date: text('until_date') || null };
        const value = module === 'tasks'
          ? { ...recurrence, title: text('title'), notes: text('notes'), category_id: categoryId, priority: (text('priority') || 'normal') as Task['priority'] } satisfies TaskSeriesInput
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
          value = { title: text('title'), notes: text('notes'), category_id: categoryId, priority: (text('priority') || 'normal') as Task['priority'], completed: task?.completed || false, due_date: deadline === 'date' ? text('due_date') : null, due_at: deadline === 'time' ? zonedInstant(text('due_at'), settings.timezone) : null };
          break;
        case 'calendar':
          value = { title: text('title'), description: text('description'), all_day: allDay, start_date: allDay ? text('start_date') : null, end_date: allDay ? text('end_date') : null, start: zonedInstant(allDay ? text('start_date') + 'T00:00' : text('start'), settings.timezone), end: zonedInstant(allDay ? text('end_date') + 'T00:00' : text('end'), settings.timezone) };
          break;
        case 'groceries':
          value = { name: text('name'), quantity: text('quantity'), unit: text('unit'), category_id: categoryId, purchased: grocery?.purchased || false };
          break;
        case 'bills':
          value = { name: text('name'), amount: text('amount'), currency: text('currency').toUpperCase(), due_date: text('due_date'), paid: bill?.paid || false };
      }
      setPending(true);
      await api.save(module, value, item?.id);
      onSaved(item ? 'Changes saved.' : singular[module][0].toUpperCase() + singular[module].slice(1) + ' added.');
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
      <label>Every<input type="number" name="interval" min="1" max="99" step="1" required defaultValue={rule?.interval || 1} key={'interval-' + (rule?.interval || 1)} inputMode="numeric" /></label>
      <label>Ends (optional)<input type="date" name="until_date" defaultValue={rule?.until_date || ''} key={'until-' + (rule?.until_date || '')} /></label>
    </div>}
    {recurringForm && <p className="form-hint">{repeat === 'monthly' ? 'Dates past the end of a short month fall on its last day.' : repeat === 'weekly' ? 'Repeats on the same weekday as the first date.' : 'Each occurrence is tracked on its own.'} Past dates are not filled in.</p>}
  </>;
  const nameField = module === 'tasks' || module === 'calendar' ? 'title' : 'name';
  return <form onSubmit={submit} className="record-form">
    {seriesId && <fieldset className="scope-choice" disabled={pending}><legend><Repeat size={14} aria-hidden="true" />{rule ? repeatLabel(rule) : 'Repeating ' + singular[module]}</legend>
      <label className="choice"><input type="radio" name="scope" checked={scope === 'this'} onChange={() => setScope('this')} />Only this occurrence</label>
      <label className="choice"><input type="radio" name="scope" checked={scope === 'future'} onChange={() => setScope('future')} />This and future occurrences</label>
    </fieldset>}
    <fieldset disabled={pending || (scope === 'future' && !rule)} key={module}>
      <label>{nameField === 'title' ? 'Title' : 'Name'}<input name={nameField} autoFocus required maxLength={200} defaultValue={item ? 'title' in item ? item.title : item.name : ''} placeholder={placeholders[module]} enterKeyHint="next" /></label>
      {module === 'tasks' && <>
        {recurringForm ? <label>{item ? 'From' : 'Starts on'}<input type="date" name="start_date" required defaultValue={dateDefault} /></label>
          : <div className="form-pair">
            <label>Due<select value={deadline} onChange={e => setDeadline(e.target.value)}><option value="none">No date</option><option value="date">On a date</option><option value="time">At a time</option></select></label>
            {deadline === 'date' && <label>Due date<input type="date" name="due_date" required defaultValue={task?.due_date || ''} /></label>}
            {deadline === 'time' && <label>Due at<input type="datetime-local" name="due_at" required defaultValue={task?.due_at ? localInput(task.due_at, settings.timezone) : ''} /></label>}
          </div>}
        <CategorySelect scope="task" label="Category" defaultValue={task?.category_id ?? null} />
        <MoreDetails open={Boolean(task?.notes || (task && task.priority !== 'normal'))} locked={recurringForm}>
          <label>Notes<textarea name="notes" maxLength={10000} defaultValue={task?.notes} rows={3} /></label>
          <label>Priority<select name="priority" defaultValue={task?.priority || 'normal'}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option></select></label>
          {repeatFields}
        </MoreDetails>
      </>}
      {module === 'calendar' && <>
        <label className="choice"><input type="checkbox" checked={allDay} onChange={e => setAllDay(e.target.checked)} />All day</label>
        <div className="form-pair">
          <label>Starts<input name={allDay ? 'start_date' : 'start'} type={allDay ? 'date' : 'datetime-local'} required key={'start-' + allDay} defaultValue={event ? allDay ? event.start_date || '' : localInput(event.start, settings.timezone) : ''} /></label>
          <label>Ends<input name={allDay ? 'end_date' : 'end'} type={allDay ? 'date' : 'datetime-local'} required key={'end-' + allDay} defaultValue={event ? allDay ? event.end_date || '' : localInput(event.end, settings.timezone) : ''} /></label>
        </div>
        <p className="form-hint">{allDay ? 'The end date is exclusive: for a single day, choose the next day.' : 'Times are in ' + settings.timezone + '.'}</p>
        <MoreDetails open={Boolean(event?.description)}>
          <label>Description<textarea name="description" maxLength={10000} rows={3} defaultValue={event?.description} /></label>
        </MoreDetails>
      </>}
      {module === 'groceries' && <>
        <div className="form-pair"><label>Quantity<input type="number" name="quantity" min="0.001" step="0.001" required defaultValue={grocery?.quantity ? String(Number(grocery.quantity)) : '1'} inputMode="decimal" /></label><label>Unit<input name="unit" maxLength={40} defaultValue={grocery?.unit} placeholder="e.g. packs" /></label></div>
        <CategorySelect scope="grocery" label="Aisle" defaultValue={grocery?.category_id ?? null} />
      </>}
      {module === 'bills' && <>
        <div className="form-pair amount-pair"><label>Amount<input type="number" name="amount" min="0" step="0.01" required defaultValue={bill?.amount} inputMode="decimal" /></label><label>Currency<input name="currency" required pattern="[A-Za-z]{3}" maxLength={3} defaultValue={bill?.currency || settings.default_currency} autoCapitalize="characters" /></label></div>
        <label>{recurringForm ? item ? 'From' : 'First due date' : 'Due date'}<input type="date" name={dateName} required key={dateName} defaultValue={bill?.due_date} /></label>
        {repeatFields}
      </>}
    </fieldset>
    {scope === 'future' && <p className="form-hint">Earlier occurrences keep their details. Completed and paid occurrences are never changed.</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {stopping && <div className="inline-confirm" role="group" aria-label="Stop repeating"><p>Upcoming open occurrences will be removed. Completed, paid and overdue items stay.</p><div><button type="button" className="button secondary" disabled={pending} onClick={() => setStopping(false)}>Keep repeating</button><button type="button" className="button danger" disabled={pending} onClick={stop}>Stop repeating</button></div></div>}
    <div className="dialog-actions">{seriesId && !stopping && <button type="button" className="text-button stop-link" disabled={pending} onClick={() => setStopping(true)}>Stop repeating…</button>}<button type="button" className="button secondary" disabled={pending} onClick={onCancel}>Cancel</button><button className="button primary" disabled={pending || (scope === 'future' && !rule)}>{pending ? 'Saving…' : item ? 'Save changes' : 'Add ' + singular[module]}</button></div>
  </form>;
}

export function RecordEditor({ initialModule, item, settings, onClose, onSaved }: { initialModule: Module; item?: RecordItem; settings: Settings; onClose: () => void; onSaved: (message?: string) => void }) {
  const [pending, setPending] = useState(false);
  return <Dialog title={(item ? 'Edit ' : 'Add ') + singular[initialModule]} onClose={onClose} pending={pending}>
    <RecordForm module={initialModule} item={item} settings={settings} onCancel={onClose} onSaved={onSaved} onPendingChange={setPending} />
  </Dialog>;
}
