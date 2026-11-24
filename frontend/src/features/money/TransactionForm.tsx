import { useState, type FormEvent } from 'react';
import { api } from '../../shared/api/client';
import type { Expense, Income, TransactionKind } from '../../shared/api/contracts';
import { CategorySelect } from '../../shared/categories';
import { Dialog, MoreDetails } from '../../shared/ui/Dialog';
import type { FormProps } from '../../shared/ui/RecordEditor';

/** Record an expense or income. Amounts are exact decimals in one currency; nothing is converted. */
export function TransactionForm({ kind, record, today, currency, onCancel, onSaved, onPendingChange }: FormProps & { kind: TransactionKind; record?: Expense | Income; today: string; currency: string }) {
  const [pending, setPendingState] = useState(false);
  const setPending = (value: boolean) => { setPendingState(value); onPendingChange?.(value); };
  const [error, setError] = useState('');
  const income = kind === 'income';
  const day = record ? 'spent_on' in record ? record.spent_on : record.received_on : today;
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (pending) return;
    const form = new FormData(e.currentTarget);
    const text = (key: string) => String(form.get(key) || '').trim();
    if (!text('category_id')) { setError(income ? 'Choose where this income came from.' : 'Choose a category.'); return; }
    const base = { amount: text('amount'), currency: text('currency').toUpperCase(), category_id: text('category_id'), note: text('note') };
    setPending(true); setError('');
    try {
      if (income) await api.saveIncome({ ...base, received_on: text('date') }, record?.id);
      else await api.saveExpense({ ...base, spent_on: text('date') }, record?.id);
      onSaved(record ? 'Changes saved.' : income ? 'Income recorded.' : 'Expense recorded.');
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not save. Try again.'); }
    finally { setPending(false); }
  }
  return <form onSubmit={submit} className="record-form">
    <fieldset disabled={pending}>
      <div className="form-pair amount-pair">
        <label>Amount<input type="number" name="amount" min="0.01" step="0.01" required autoFocus inputMode="decimal" defaultValue={record?.amount} placeholder="0.00" /></label>
        <label>Currency<input name="currency" required pattern="[A-Za-z]{3}" maxLength={3} autoCapitalize="characters" defaultValue={record?.currency || currency} /></label>
      </div>
      <CategorySelect scope={kind} label={income ? 'Source' : 'Category'} required defaultValue={record?.category_id ?? null} />
      <label>{income ? 'Received on' : 'Date'}<input type="date" name="date" required defaultValue={day} /></label>
      <MoreDetails open={Boolean(record?.note)} label="Add a note">
        <label>Note<input name="note" maxLength={500} defaultValue={record?.note} placeholder={income ? 'e.g. November paycheck' : 'e.g. Farmers market'} /></label>
      </MoreDetails>
      <p className="form-hint">{income
        ? 'Money you earned or were given. Refunds and transfers between your own accounts are not income.'
        : 'Recorded spending. Daybook never connects to a bank or moves money.'}</p>
    </fieldset>
    {error && <p className="error" role="alert">{error}</p>}
    <div className="dialog-actions"><button type="button" className="button secondary" disabled={pending} onClick={onCancel}>Cancel</button><button className="button primary" disabled={pending}>{pending ? 'Saving…' : record ? 'Save changes' : income ? 'Add income' : 'Add expense'}</button></div>
  </form>;
}

export function TransactionEditor({ kind, record, today, currency, onClose, onSaved }: { kind: TransactionKind; record?: Expense | Income; today: string; currency: string; onClose: () => void; onSaved: (message?: string) => void }) {
  const [pending, setPending] = useState(false);
  return <Dialog title={(record ? 'Edit ' : 'Add ') + (kind === 'income' ? 'income' : 'expense')} onClose={onClose} pending={pending}>
    <TransactionForm kind={kind} record={record} today={today} currency={currency} onCancel={onClose} onSaved={onSaved} onPendingChange={setPending} />
  </Dialog>;
}
