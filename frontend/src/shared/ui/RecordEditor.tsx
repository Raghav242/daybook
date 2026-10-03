import { useState, type FormEvent } from 'react';
import { api } from '../api/client';
import type { Bill, CalendarEntry, Grocery, Module, RecordInput, RecordItem, Settings, Task } from '../api/contracts';
import { localInput, moduleNames, singular, zonedInstant } from '../domain';
import { Dialog } from './Dialog';

export function RecordEditor({ initialModule, item, settings, onClose, onSaved }: { initialModule?: Module; item?: RecordItem; settings: Settings; onClose: () => void; onSaved: () => void }) {
  const [module, setModule] = useState<Module>(initialModule || settings.enabled_modules[0] || 'tasks');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const task = item as Task | undefined, event = item as CalendarEntry | undefined, grocery = item as Grocery | undefined, bill = item as Bill | undefined;
  const [deadline, setDeadline] = useState(task?.due_at ? 'time' : task?.due_date ? 'date' : 'none');
  const [allDay, setAllDay] = useState(event?.all_day || false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (pending) return;
    const form = new FormData(e.currentTarget);
    const text = (key: string) => String(form.get(key) || '').trim();
    let value: RecordInput;
    setError('');
    try {
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
  return <Dialog title={item ? 'Edit ' + singular[module] : initialModule ? 'Add ' + singular[module] : 'Quick capture'} onClose={onClose} pending={pending}>
    <form onSubmit={submit}>
      {!initialModule && <label>Record type<select value={module} disabled={pending} onChange={e => { setModule(e.target.value as Module); setError(''); }}>{settings.enabled_modules.map(m => <option key={m} value={m}>{moduleNames[m]}</option>)}</select></label>}
      <fieldset disabled={pending} key={module}>
        <label>{module === 'tasks' || module === 'calendar' ? 'Title' : 'Name'}<input name={module === 'tasks' || module === 'calendar' ? 'title' : 'name'} autoFocus required maxLength={200} defaultValue={item ? 'title' in item ? item.title : item.name : ''} placeholder={module === 'tasks' ? 'What needs doing?' : module === 'calendar' ? 'What’s coming up?' : module === 'groceries' ? 'e.g. Whole grain bread' : 'e.g. Internet'} /></label>
        {module === 'tasks' && <>
          <label>Notes<textarea name="notes" maxLength={10000} defaultValue={task?.notes} rows={3} /></label>
          <div className="form-pair"><label>Priority<select name="priority" defaultValue={task?.priority || 'normal'}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option></select></label><label>Category<input name="category" maxLength={80} defaultValue={task?.category} placeholder="e.g. School" /></label></div>
          <label>Deadline<select value={deadline} onChange={e => setDeadline(e.target.value)}><option value="none">No deadline</option><option value="date">Date only</option><option value="time">Date and time</option></select></label>
          {deadline === 'date' && <label>Due date<input type="date" name="due_date" required defaultValue={task?.due_date || ''} /></label>}
          {deadline === 'time' && <label>Due at · {settings.timezone}<input type="datetime-local" name="due_at" required defaultValue={task?.due_at ? localInput(task.due_at, settings.timezone) : ''} /></label>}
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
          <label>Due date<input type="date" name="due_date" required defaultValue={bill?.due_date} /></label>
          <p className="form-hint">Track a bill and its paid status here.</p>
        </>}
      </fieldset>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="dialog-actions"><button type="button" className="button secondary" disabled={pending} onClick={onClose}>Cancel</button><button className="button primary" disabled={pending}>{pending ? 'Saving…' : item ? 'Save changes' : 'Add ' + singular[module]}</button></div>
    </form>
  </Dialog>;
}

