import { useState } from 'react';
import type { Settings } from '../../shared/api/contracts';
import { entryKinds, type EntryKind } from './kinds';
import { Dialog } from '../../shared/ui/Dialog';
import { RecordForm } from '../../shared/ui/RecordEditor';
import { TransactionForm } from '../money/TransactionForm';

/** The one Add action: choose a type, then fill in only what that type needs. */
export function QuickAdd({ settings, today, initial, onClose, onSaved }: { settings: Settings; today: string; initial?: EntryKind; onClose: () => void; onSaved: (message?: string) => void }) {
  const available = entryKinds(settings.enabled_modules);
  const [kind, setKind] = useState<EntryKind>(initial && available.some(k => k.kind === initial) ? initial : available[0]?.kind);
  const [pending, setPending] = useState(false);
  const label = available.find(k => k.kind === kind)?.label.toLowerCase() || 'entry';
  return <Dialog title={'Add ' + (kind ? label : 'to Daybook')} onClose={onClose} pending={pending}>
    {available.length > 1 && <fieldset className="kind-picker" disabled={pending}>
      <legend className="visually-hidden">What are you adding?</legend>
      {available.map(k => <label key={k.kind} className={'kind-chip' + (k.kind === kind ? ' selected' : '')}>
        <input type="radio" name="entry-kind" value={k.kind} checked={k.kind === kind} onChange={() => setKind(k.kind)} />{k.label}
      </label>)}
    </fieldset>}
    {!kind && <p className="muted">Turn on a module in Settings to start adding things.</p>}
    {(kind === 'expense' || kind === 'income')
      ? <TransactionForm key={kind} kind={kind} today={today} currency={settings.default_currency} onCancel={onClose} onSaved={onSaved} onPendingChange={setPending} />
      : kind && <RecordForm key={kind} module={kind} settings={settings} onCancel={onClose} onSaved={onSaved} onPendingChange={setPending} />}
  </Dialog>;
}
