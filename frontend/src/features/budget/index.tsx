import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { ArrowLeft, ArrowRight, Pencil, Plus, Trash2 } from 'lucide-react';
import { api } from '../../shared/api/client';
import type { Budget, CategoryLine, Expense } from '../../shared/api/contracts';
import { dateLabel, money, monthLabel, shiftMonth } from '../../shared/domain';
import { useResource } from '../../shared/hooks/useResource';
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog';
import { Dialog } from '../../shared/ui/Dialog';

type Editing = { kind: 'expense'; expense?: Expense } | { kind: 'budget'; budget?: Budget; category?: string; currency?: string } | { kind: 'delete-expense'; expense: Expense } | { kind: 'delete-budget'; budget: Budget };

export default function BudgetView({ revision, today, currency, onChanged }: { revision: number; today: string; currency: string; onChanged: (message: string) => void }) {
  const [month, setMonth] = useState(today.slice(0, 7));
  const [offset, setOffset] = useState(0);
  const [local, setLocal] = useState(0);
  const [editing, setEditing] = useState<Editing>();
  const loadSummary = useCallback((signal: AbortSignal) => api.budgetSummary(month, signal), [month]);
  const loadExpenses = useCallback((signal: AbortSignal) => api.expenses(month, offset, signal), [month, offset]);
  const loadBudgets = useCallback((signal: AbortSignal) => api.budgets(signal), []);
  const summary = useResource(loadSummary, revision + local);
  const expenses = useResource(loadExpenses, revision + local);
  const budgets = useResource(loadBudgets, revision + local);
  useEffect(() => { const data = expenses.data; if (data && offset > 0 && offset >= data.total) setOffset(Math.max(0, Math.floor((data.total - 1) / 25) * 25)); }, [expenses.data, offset]);
  function done(message: string) { setEditing(undefined); setLocal(r => r + 1); onChanged(message); }
  const budgetFor = (line: CategoryLine) => budgets.data?.find(b => b.id === line.budget_id);
  const s = summary.data;
  return <section aria-labelledby="view-title">
    <div className="page-heading"><div><p className="eyebrow">YOUR DAYBOOK</p><h1 id="view-title">Budget</h1><p className="page-subtitle">What you’ve spent, what’s left, and what’s still due. Tracking only — no bank connections.</p></div><button className="button primary" onClick={() => setEditing({ kind: 'expense' })}><Plus size={17} />Add expense</button></div>
    <div className="list-toolbar"><div className="week-nav"><button className="icon-button" aria-label="Previous month" onClick={() => { setMonth(m => shiftMonth(m, -1)); setOffset(0); }}><ArrowLeft size={16} /></button><h2 aria-live="polite">{monthLabel(month)}</h2><button className="icon-button" aria-label="Next month" onClick={() => { setMonth(m => shiftMonth(m, 1)); setOffset(0); }}><ArrowRight size={16} /></button>{month !== today.slice(0, 7) && <button className="text-button" onClick={() => setMonth(today.slice(0, 7))}>This month</button>}</div><button className="button secondary" onClick={() => setEditing({ kind: 'budget', currency })}><Plus size={16} />Set a budget</button></div>
    {summary.error && <div role="alert" className="error">{summary.error}<button className="text-button" onClick={() => setLocal(r => r + 1)}>Try again</button></div>}
    {summary.loading && !s && <p role="status" className="loading">Adding things up…</p>}
    {s && <div className="budget-overview" aria-busy={summary.loading}>
      <div className="budget-totals">{s.totals.length ? s.totals.map(t => <div key={t.currency} className="budget-total">
        <p className="eyebrow">SPENT · {t.currency}</p><strong>{money(t.spent, t.currency)}</strong>
        <span>{Number(t.budgeted) > 0 ? <>{money(String(Math.abs(Number(t.remaining))), t.currency)} {Number(t.remaining) < 0 ? 'over' : 'left'} of {money(t.budgeted, t.currency)} budgeted</> : 'No budget set in ' + t.currency}{Number(t.unbudgeted) > 0 && Number(t.budgeted) > 0 ? ' · ' + money(t.unbudgeted, t.currency) + ' outside budgets' : ''}</span>
      </div>) : <div className="budget-total"><p className="eyebrow">SPENT</p><strong>Nothing yet</strong><span>Recorded spending for {monthLabel(month)} appears here.</span></div>}</div>
      <aside className="expected-bills" aria-label="Unpaid bills this month"><p className="eyebrow">STILL DUE THIS MONTH</p>{s.expected_bills.length ? <>{s.expected_bills.map(b => <strong key={b.currency}>{money(b.amount, b.currency)}<span>{b.count} unpaid {b.count === 1 ? 'bill' : 'bills'} · {b.currency}</span></strong>)}<ul>{s.unpaid_bills.map(b => <li key={b.id}><span>{b.name}</span><span>{dateLabel(b.due_date)} · {money(b.amount, b.currency)}</span></li>)}</ul></> : <p className="muted">No unpaid bills due this month.</p>}<small>Expected payments are not counted as spending until paid and recorded.</small></aside>
    </div>}
    {s && <section className="budget-categories" aria-labelledby="categories-title"><div className="section-heading"><h2 id="categories-title">By category</h2></div>
      {s.categories.length ? <ul>{s.categories.map(line => { const budget = budgetFor(line); const ratio = line.budgeted && Number(line.budgeted) > 0 ? Math.min(1, Number(line.spent) / Number(line.budgeted)) : 0; const over = line.remaining !== null && Number(line.remaining) < 0; return <li key={line.category + line.currency} className={'category-row' + (over ? ' over' : '')}>
        <div className="category-copy"><span className="category-name">{line.category}<small>{line.currency}</small></span><span className="record-detail">{money(line.spent, line.currency)} spent{line.budgeted !== null ? ' of ' + money(line.budgeted, line.currency) : ' · no budget'}</span></div>
        {line.budgeted !== null && <div className="meter" role="img" aria-label={Math.round(ratio * 100) + '% of budget used'}><span style={{ width: ratio * 100 + '%' }} /></div>}
        <span className="record-amount">{line.remaining !== null ? money(String(Math.abs(Number(line.remaining))), line.currency) + (over ? ' over' : ' left') : ''}</span>
        <div className="row-actions">{budget ? <><button className="icon-button" aria-label={'Edit ' + line.category + ' budget'} onClick={() => setEditing({ kind: 'budget', budget })}><Pencil size={15} /></button><button className="icon-button" aria-label={'Delete ' + line.category + ' budget'} onClick={() => setEditing({ kind: 'delete-budget', budget })}><Trash2 size={15} /></button></> : <button className="text-button" onClick={() => setEditing({ kind: 'budget', category: line.category, currency: line.currency })}>Set budget</button>}</div>
      </li>; })}</ul> : <p className="muted lower-empty">Set a monthly budget for a category, or add an expense to get started.</p>}
    </section>}
    <section className="budget-expenses" aria-labelledby="expenses-title"><div className="section-heading"><h2 id="expenses-title">Expenses in {monthLabel(month)}</h2><span className="muted">{expenses.data ? expenses.data.total + ' recorded' : ''}</span></div>
      {expenses.error && <div role="alert" className="error">{expenses.error}</div>}
      {expenses.data && (expenses.data.items.length ? <ul className="records-list" aria-busy={expenses.loading}>{expenses.data.items.map(e => <li key={e.id} className="record-row"><div className="record-copy"><button className="record-title" onClick={() => setEditing({ kind: 'expense', expense: e })}>{e.note || e.category}</button><span className="record-detail">{[dateLabel(e.spent_on), e.category, e.bill_id ? 'From a paid bill' : ''].filter(Boolean).join(' · ')}</span></div><span className="record-amount">{money(e.amount, e.currency)}</span><div className="row-actions"><button className="icon-button" aria-label={'Edit expense ' + (e.note || e.category)} onClick={() => setEditing({ kind: 'expense', expense: e })}><Pencil size={16} /></button><button className="icon-button" aria-label={'Delete expense ' + (e.note || e.category)} onClick={() => setEditing({ kind: 'delete-expense', expense: e })}><Trash2 size={16} /></button></div></li>)}</ul> : <p className="muted lower-empty">No expenses recorded this month.</p>)}
      {expenses.data && expenses.data.total > 25 && <div className="pagination"><button className="button secondary" disabled={expenses.loading || offset === 0} onClick={() => setOffset(o => o - 25)}><ArrowLeft size={16} />Previous</button><span>{offset + 1}–{Math.min(offset + 25, expenses.data.total)} of {expenses.data.total}</span><button className="button secondary" disabled={expenses.loading || offset + 25 >= expenses.data.total} onClick={() => setOffset(o => o + 25)}>Next<ArrowRight size={16} /></button></div>}
    </section>
    {editing?.kind === 'expense' && <ExpenseEditor expense={editing.expense} today={today} currency={currency} onClose={() => setEditing(undefined)} onSaved={done} />}
    {editing?.kind === 'budget' && <BudgetEditor budget={editing.budget} category={editing.category} currency={editing.currency || currency} onClose={() => setEditing(undefined)} onSaved={done} />}
    {editing?.kind === 'delete-expense' && <ConfirmDialog title="Delete this expense?" body={editing.expense.bill_id ? 'This spending came from a paid bill. The bill stays marked paid; you can unmark it afterward.' : 'This recorded spending will be permanently removed.'} action="Delete expense" onClose={() => setEditing(undefined)} onConfirm={async () => { await api.deleteExpense(editing.expense.id); done('Expense deleted.'); }} />}
    {editing?.kind === 'delete-budget' && <ConfirmDialog title="Remove this budget?" body={`The ${editing.budget.currency} budget for “${editing.budget.category}” will be removed. Expenses are kept.`} action="Remove budget" onClose={() => setEditing(undefined)} onConfirm={async () => { await api.deleteBudget(editing.budget.id); done('Budget removed.'); }} />}
  </section>;
}

function ExpenseEditor({ expense, today, currency, onClose, onSaved }: { expense?: Expense; today: string; currency: string; onClose: () => void; onSaved: (message: string) => void }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (pending) return;
    const form = new FormData(e.currentTarget);
    const text = (key: string) => String(form.get(key) || '').trim();
    setPending(true); setError('');
    try { await api.saveExpense({ amount: text('amount'), currency: text('currency').toUpperCase(), category: text('category'), spent_on: text('spent_on'), note: text('note') }, expense?.id); onSaved(expense ? 'Expense updated.' : 'Expense recorded.'); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not save the expense.'); }
    finally { setPending(false); }
  }
  return <Dialog title={expense ? 'Edit expense' : 'Add expense'} onClose={onClose} pending={pending}>
    <form onSubmit={submit}><fieldset disabled={pending}>
      <div className="form-pair"><label>Amount<input type="number" name="amount" min="0.01" step="0.01" required defaultValue={expense?.amount} /></label><label>Currency<input name="currency" required pattern="[A-Za-z]{3}" maxLength={3} defaultValue={expense?.currency || currency} /></label></div>
      <div className="form-pair"><label>Category<input name="category" required maxLength={80} defaultValue={expense?.category} placeholder="e.g. Groceries" /></label><label>Date<input type="date" name="spent_on" required defaultValue={expense?.spent_on || today} /></label></div>
      <label>Note (optional)<input name="note" maxLength={500} defaultValue={expense?.note} placeholder="e.g. Farmers market" /></label>
      <p className="form-hint">Categories match regardless of capitalization. Amounts stay in their own currency.</p>
    </fieldset>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="dialog-actions"><button type="button" className="button secondary" disabled={pending} onClick={onClose}>Cancel</button><button className="button primary" disabled={pending}>{pending ? 'Saving…' : expense ? 'Save changes' : 'Add expense'}</button></div>
    </form>
  </Dialog>;
}

function BudgetEditor({ budget, category, currency, onClose, onSaved }: { budget?: Budget; category?: string; currency: string; onClose: () => void; onSaved: (message: string) => void }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (pending) return;
    const form = new FormData(e.currentTarget);
    const text = (key: string) => String(form.get(key) || '').trim();
    setPending(true); setError('');
    try { await api.saveBudget({ category: text('category'), amount: text('amount'), currency: text('currency').toUpperCase() }, budget?.id); onSaved('Budget saved.'); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not save the budget.'); }
    finally { setPending(false); }
  }
  return <Dialog title={budget ? 'Edit budget' : 'Set a monthly budget'} onClose={onClose} pending={pending}>
    <form onSubmit={submit}><fieldset disabled={pending}>
      <label>Category<input name="category" required maxLength={80} defaultValue={budget?.category || category} placeholder="e.g. Groceries" /></label>
      <div className="form-pair"><label>Each month<input type="number" name="amount" min="0" step="0.01" required defaultValue={budget?.amount} /></label><label>Currency<input name="currency" required pattern="[A-Za-z]{3}" maxLength={3} defaultValue={budget?.currency || currency} /></label></div>
      <p className="form-hint">A budget applies to every month. Spending in other currencies is tracked separately and never converted.</p>
    </fieldset>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="dialog-actions"><button type="button" className="button secondary" disabled={pending} onClick={onClose}>Cancel</button><button className="button primary" disabled={pending}>{pending ? 'Saving…' : 'Save budget'}</button></div>
    </form>
  </Dialog>;
}
