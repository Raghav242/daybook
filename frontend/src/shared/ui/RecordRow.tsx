import { Pencil, Trash2 } from 'lucide-react';
import type { Module, RecordItem } from '../api/contracts';
import { eventLabel, money, taskDeadline, titleOf } from '../domain';

export interface RowActions { onEdit: (module: Module, item: RecordItem) => void; onDelete: (module: Module, item: RecordItem) => void; onToggle: (module: Module, item: RecordItem) => void; busy: boolean }
export function RecordRow({ module, item, zone, compact = false, onEdit, onDelete, onToggle, busy }: RowActions & { module: Module; item: RecordItem; zone: string; compact?: boolean }) {
  const done = 'completed' in item ? item.completed : 'purchased' in item ? item.purchased : 'paid' in item ? item.paid : false;
  const title = titleOf(item);
  const verb = module === 'tasks' ? 'complete' : module === 'groceries' ? 'purchased' : 'paid';
  let detail = '';
  if ('priority' in item) detail = [taskDeadline(item, zone), item.category, item.priority === 'high' ? 'High priority' : item.priority === 'low' ? 'Low priority' : ''].filter(Boolean).join(' · ');
  if ('start' in item) detail = eventLabel(item, zone);
  if ('quantity' in item) detail = [Number(item.quantity) + ' ' + item.unit, item.category].filter(Boolean).join(' · ');
  if ('amount' in item) detail = 'Due ' + taskDeadline({ ...item, title: item.name, notes: '', due_at: null, category: '', priority: 'normal', completed: item.paid }, zone);
  return <li className={'record-row' + (done ? ' done' : '')}>
    {module !== 'calendar' && <input className="record-check" type="checkbox" checked={done} disabled={busy} aria-label={'Mark ' + title + ' ' + (done ? 'not ' : '') + verb} onChange={() => onToggle(module, item)} />}
    {module === 'calendar' && <span className="agenda-marker" aria-hidden="true" />}
    <div className="record-copy"><button className="record-title" disabled={busy} onClick={() => onEdit(module, item)}>{title}</button><span className="record-detail">{detail}</span></div>
    {'amount' in item && <span className="record-amount">{money(item.amount, item.currency)}</span>}
    {!compact && <div className="row-actions"><button className="icon-button" aria-label={'Edit ' + title} disabled={busy} onClick={() => onEdit(module, item)}><Pencil size={16} /></button><button className="icon-button" aria-label={'Delete ' + title} disabled={busy} onClick={() => onDelete(module, item)}><Trash2 size={16} /></button></div>}
  </li>;
}

