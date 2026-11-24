import { Pencil, Repeat, Trash2 } from 'lucide-react';
import type { Module, RecordItem } from '../api/contracts';
import { dateLabel, eventLabel, isOverdue, money, quantity, taskDeadline, titleOf } from '../domain';

export interface RowActions { onEdit: (module: Module, item: RecordItem) => void; onDelete: (module: Module, item: RecordItem) => void; onToggle: (module: Module, item: RecordItem) => void; busy: boolean }

export function RecordRow({ module, item, zone, today, compact = false, onEdit, onDelete, onToggle, busy }: RowActions & { module: Module; item: RecordItem; zone: string; today?: string; compact?: boolean }) {
  const done = 'completed' in item ? item.completed : 'purchased' in item ? item.purchased : 'paid' in item ? item.paid : false;
  const title = titleOf(item);
  const verb = module === 'tasks' ? 'complete' : module === 'groceries' ? 'purchased' : 'paid';
  const overdue = !done && today !== undefined && (module === 'tasks' || module === 'bills') && isOverdue(item as never, today);
  let parts: string[] = [];
  if ('priority' in item) parts = [item.due_date === today ? 'Today' : item.due_date || item.due_at ? (overdue ? 'Overdue · ' : '') + taskDeadline(item, zone) : '', item.category || '', item.priority === 'high' ? 'High priority' : ''];
  if ('start' in item) parts = [eventLabel(item, zone)];
  if ('purchased' in item) parts = [[quantity(item.quantity), item.unit].filter(Boolean).join(' '), item.category || ''];
  if ('amount' in item) parts = [!done && item.due_date === today ? 'Due today' : (overdue ? 'Overdue · ' : done ? 'Was due ' : 'Due ') + dateLabel(item.due_date), item.expense_id ? 'Recorded as spending' : ''];
  const repeats = 'series_id' in item && Boolean(item.series_id);
  return <li className={'row' + (done ? ' done' : '') + (overdue ? ' overdue' : '')}>
    {module === 'calendar' ? <span className="status-dot" aria-hidden="true" />
      : <input className="check" type="checkbox" checked={done} disabled={busy} aria-label={'Mark ' + title + ' ' + (done ? 'not ' : '') + verb} onChange={() => onToggle(module, item)} />}
    <div className="row-copy">
      <button className="row-title" disabled={busy} onClick={() => onEdit(module, item)}>{title}</button>
      <span className="row-meta">{repeats && <Repeat size={12} className="inline-icon" aria-label="Repeats" />}<span className={overdue ? 'warn-text' : undefined}>{parts.filter(Boolean).join(' · ')}</span></span>
    </div>
    {'amount' in item && <span className="row-amount">{money(item.amount, item.currency)}</span>}
    {!compact && <div className="row-actions"><button className="icon-button" aria-label={'Edit ' + title} disabled={busy} onClick={() => onEdit(module, item)}><Pencil size={16} /></button><button className="icon-button" aria-label={'Delete ' + title} disabled={busy} onClick={() => onDelete(module, item)}><Trash2 size={16} /></button></div>}
  </li>;
}
