import { useState, type FormEvent } from 'react';
import { api } from '../../shared/api/client';
import type { Bill } from '../../shared/api/contracts';
import { CategorySelect } from '../../shared/categories';
import { useCategories } from '../../shared/useCategories';
import { money } from '../../shared/domain';
import { Dialog } from '../../shared/ui/Dialog';

/** Records a payment made elsewhere. Optionally logs it once as a linked expense. */
export function PayDialog({ bill, today, budgetEnabled, onClose, onPaid }: { bill: Bill; today: string; budgetEnabled: boolean; onClose: () => void; onPaid: (message: string) => void }) {
  const [record, setRecord] = useState(budgetEnabled && Number(bill.amount) > 0 && !bill.expense_id);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const { active, loading } = useCategories('expense');
  // A visible, editable starting choice; the user decides.
  const suggested = active.find(c => c.name.toLowerCase() === 'utilities')?.id ?? null;
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (pending) return;
    const form = new FormData(e.currentTarget);
    const categoryId = String(form.get('category_id') || '') || null;
    if (record && !categoryId) { setError('Choose a category for this expense.'); return; }
    setPending(true); setError('');
    try {
      await api.payBill(bill.id, { paid_on: String(form.get('paid_on')), record_expense: record, category_id: record ? categoryId : null, note: String(form.get('note') || '').trim() });
      onPaid(record ? 'Marked paid and recorded as an expense.' : 'Marked paid.');
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not mark this bill paid.'); }
    finally { setPending(false); }
  }
  return <Dialog title="Mark bill paid" onClose={onClose} pending={pending}>
    <form onSubmit={submit} className="record-form">
      <p className="dialog-lead"><strong>{bill.name}</strong> · {money(bill.amount, bill.currency)}</p>
      <fieldset disabled={pending}>
        <label>Paid on<input type="date" name="paid_on" required defaultValue={today} /></label>
        {bill.expense_id ? <p className="form-hint">This payment is already recorded as an expense.</p> : <>
          <label className="choice"><input type="checkbox" checked={record} disabled={Number(bill.amount) <= 0 || !budgetEnabled} onChange={e => setRecord(e.target.checked)} />Also record it as an expense</label>
          {record && !loading && <CategorySelect key={suggested || 'none'} scope="expense" label="Expense category" required defaultValue={suggested} />}
          {record && <label>Note (optional)<input name="note" maxLength={500} placeholder={bill.name} /></label>}
          <p className="form-hint">{record ? 'Recorded once per bill, even if you submit again.' : 'The bill stays out of your spending totals.'} Daybook never moves money.</p>
        </>}
      </fieldset>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="dialog-actions"><button type="button" className="button secondary" disabled={pending} onClick={onClose}>Cancel</button><button className="button primary" disabled={pending}>{pending ? 'Saving…' : 'Mark paid'}</button></div>
    </form>
  </Dialog>;
}
