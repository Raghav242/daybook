import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { ArrowLeft, ArrowRight, Pencil, Plus, Trash2 } from 'lucide-react';
import { api } from '../../shared/api/client';
import type { Budget, BudgetSummary, CategoryLine, Expense, Income, Transaction, TransactionKind } from '../../shared/api/contracts';
import { CategorySelect } from '../../shared/categories';
import { dateLabel, money, monthLabel, shiftMonth, signedMoney } from '../../shared/domain';
import { useResource } from '../../shared/hooks/useResource';
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog';
import { Dialog } from '../../shared/ui/Dialog';
import { Filters, PageHead, Pagination } from '../../shared/ui/RecordsView';
import type { EntryKind } from '../capture/kinds';
import { SpendingSplit } from './SpendingSplit';
import { TransactionEditor } from './TransactionForm';

export interface MoneyProps { revision: number; today: string; currency: string; month: string; onMonth: (month: string) => void; onAdd: (kind?: EntryKind) => void; onChanged: (message?: string) => void }

export function MonthNav({ month, today, onMonth }: { month: string; today: string; onMonth: (month: string) => void }) {
  const current = today.slice(0, 7);
  return <div className="month-nav">
    <button className="icon-button" aria-label="Previous month" onClick={() => onMonth(shiftMonth(month, -1))}><ArrowLeft size={18} /></button>
    <h2 aria-live="polite">{monthLabel(month)}</h2>
    <button className="icon-button" aria-label="Next month" onClick={() => onMonth(shiftMonth(month, 1))}><ArrowRight size={18} /></button>
    {month !== current && <button className="text-button" onClick={() => onMonth(current)}>This month</button>}
  </div>;
}

/** Currencies with any figure this month. Each is shown on its own; none are converted. */
function currenciesOf(summary: BudgetSummary | undefined, preferred: string) {
  const found = new Set([...(summary?.totals || []).map(t => t.currency), ...(summary?.expected_bills || []).map(b => b.currency), ...(summary?.categories || []).map(c => c.currency)]);
  return [...found].sort((a, b) => a === preferred ? -1 : b === preferred ? 1 : a.localeCompare(b));
}

function useSummary(month: string, revision: number) {
  const load = useCallback((signal: AbortSignal) => api.budgetSummary(month, signal), [month]);
  return useResource(load, revision);
}

function BudgetMeter({ line }: { line: CategoryLine }) {
  if (line.budgeted === null) return null;
  const limit = Number(line.budgeted), spent = Number(line.spent);
  const ratio = limit > 0 ? Math.min(1, spent / limit) : spent > 0 ? 1 : 0;
  const over = Number(line.remaining) < 0;
  return <div className={'meter' + (over ? ' over' : ratio >= 0.85 ? ' near' : '')} role="meter" aria-valuemin={0} aria-valuemax={limit} aria-valuenow={Math.min(spent, limit)} aria-label={line.category + ' budget used'}><span style={{ width: ratio * 100 + '%' }} /></div>;
}

function remainingLabel(line: CategoryLine) {
  if (line.remaining === null) return money(line.spent, line.currency) + ' spent · no budget';
  const remaining = Number(line.remaining);
  return money(line.spent, line.currency) + ' of ' + money(line.budgeted!, line.currency) + ' · ' + money(String(Math.abs(remaining)), line.currency) + (remaining < 0 ? ' over' : ' left');
}

export function MoneyOverview({ revision, today, currency, month, onMonth, onAdd }: MoneyProps) {
  const summary = useSummary(month, revision);
  const s = summary.data;
  const currencies = useMemo(() => currenciesOf(s, currency), [s, currency]);
  const [chosen, setChosen] = useState(currency);
  const shown = currencies.includes(chosen) ? chosen : currencies[0] || currency;
  const total = s?.totals.find(t => t.currency === shown);
  const due = s?.expected_bills.find(b => b.currency === shown);
  const lines = (s?.categories || []).filter(c => c.currency === shown);
  const budgeted = lines.filter(l => l.budgeted !== null);
  const loose = lines.filter(l => l.budgeted === null);
  return <section aria-labelledby="view-title">
    <PageHead title="Money" action={<button className="button secondary small" onClick={() => onAdd('expense')}><Plus size={16} />Add</button>} />
    <MonthNav month={month} today={today} onMonth={onMonth} />
    {summary.error && <div role="alert" className="error">{summary.error}</div>}
    {summary.loading && !s && <p role="status" className="loading">Adding things up…</p>}
    {s && !currencies.length && <div className="empty"><p>Nothing recorded for {monthLabel(month)}.</p><div className="empty-actions"><button className="text-button" onClick={() => onAdd('expense')}><Plus size={15} />Add expense</button><button className="text-button" onClick={() => onAdd('income')}><Plus size={15} />Add income</button></div></div>}
    {s && currencies.length > 0 && <div aria-busy={summary.loading}>
      {currencies.length > 1 && <Filters label="Currency" value={shown} options={currencies.map(c => [c, c])} onChange={setChosen} />}
      <dl className="figures">
        <div><dt>Income received</dt><dd>{money(total?.income || '0', shown)}</dd></div>
        <div><dt>Expenses recorded</dt><dd>{money(total?.spent || '0', shown)}</dd></div>
        <div className={Number(total?.net || 0) < 0 ? 'negative' : ''}><dt>Net cash flow</dt><dd>{signedMoney(total?.net || '0', shown)}</dd></div>
      </dl>
      <p className="form-hint">Net cash flow is recorded income minus recorded expenses for {monthLabel(month)}. It is not a bank balance.</p>
      <SpendingSplit lines={lines} currency={shown} />
      <section aria-labelledby="due-title">
        <div className="section-head"><h2 id="due-title" className="section-title">Still due</h2><a className="view-all" href="#bills">Bills<ArrowRight size={14} aria-hidden="true" /></a></div>
        {due ? <>
          <p className="row-meta">{due.count} unpaid {due.count === 1 ? 'bill' : 'bills'} · {money(due.amount, shown)} · not counted as spending until paid</p>
          <ul className="rows">{s.unpaid_bills.filter(b => b.currency === shown).map(b => <li key={b.id} className={'row' + (b.due_date < today ? ' overdue' : '')}><div className="row-copy"><span className="row-title static">{b.name}</span><span className={'row-meta' + (b.due_date < today ? ' warn-text' : '')}>{b.due_date < today ? 'Overdue · ' : 'Due '}{dateLabel(b.due_date)}</span></div><span className="row-amount">{money(b.amount, b.currency)}</span></li>)}</ul>
        </> : <p className="quiet">No unpaid bills due in {monthLabel(month)}.</p>}
      </section>
      <section aria-labelledby="progress-title">
        <div className="section-head"><h2 id="progress-title" className="section-title">Budgets</h2><a className="view-all" href="#budgets">Manage<ArrowRight size={14} aria-hidden="true" /></a></div>
        {budgeted.length ? <ul className="rows budget-rows">{budgeted.map(line => <li key={line.category_id} className={'row budget-row' + (Number(line.remaining) < 0 ? ' overdue' : '')}>
          <div className="row-copy"><span className="row-title static">{line.category}</span><span className={'row-meta' + (Number(line.remaining) < 0 ? ' warn-text' : '')}>{remainingLabel(line)}</span><BudgetMeter line={line} /></div>
        </li>)}</ul> : <p className="quiet">No budgets yet. <a href="#budgets">Set one</a></p>}
        {loose.length > 0 && <>
          <h3 className="subhead">Spending without a budget</h3>
          <ul className="rows">{loose.map(line => <li key={line.category_id} className="row"><div className="row-copy"><span className="row-title static">{line.category}</span></div><span className="row-amount">{money(line.spent, line.currency)}</span></li>)}</ul>
        </>}
      </section>
    </div>}
  </section>;
}

const asRecord = (t: Transaction): Expense | Income => t.kind === 'expense'
  ? { id: t.id, amount: t.amount, currency: t.currency, category_id: t.category_id, category: t.category, spent_on: t.date, note: t.note, bill_id: t.bill_id }
  : { id: t.id, amount: t.amount, currency: t.currency, category_id: t.category_id, category: t.category, received_on: t.date, note: t.note };

export function TransactionsView({ revision, today, currency, month, onMonth, onAdd, onChanged }: MoneyProps) {
  const [kind, setKind] = useState<TransactionKind | 'all'>('all');
  const [offset, setOffset] = useState(0);
  const [local, setLocal] = useState(0);
  const [editing, setEditing] = useState<Transaction>();
  const [deleting, setDeleting] = useState<Transaction>();
  const load = useCallback((signal: AbortSignal) => api.transactions(month, kind, offset, signal), [month, kind, offset]);
  const page = useResource(load, revision + local);
  useEffect(() => { setOffset(0); }, [month, kind]);
  useEffect(() => { const data = page.data; if (data && offset > 0 && offset >= data.total) setOffset(Math.max(0, Math.floor((data.total - 1) / 25) * 25)); }, [page.data, offset]);
  function done(message?: string) { setEditing(undefined); setDeleting(undefined); setLocal(r => r + 1); onChanged(message); }
  const label = (t: Transaction) => t.note || t.category;
  return <section aria-labelledby="view-title">
    <PageHead title="Transactions" action={<button className="button secondary small" onClick={() => onAdd(kind === 'income' ? 'income' : 'expense')}><Plus size={16} />Add</button>} />
    <MonthNav month={month} today={today} onMonth={onMonth} />
    <Filters label="Show" value={kind} options={[['all', 'All'], ['expense', 'Expenses'], ['income', 'Income']]} onChange={setKind} />
    {page.error && <div role="alert" className="error">{page.error}<button className="text-button" onClick={() => setLocal(r => r + 1)}>Try again</button></div>}
    {page.loading && !page.data && <p role="status" className="loading">Loading…</p>}
    {page.data && (page.data.items.length ? <ul className="rows" aria-busy={page.loading}>{page.data.items.map(t => <li key={t.kind + t.id} className={'row transaction ' + t.kind}>
      <span className="row-day">{dateLabel(t.date)}</span>
      <div className="row-copy"><button className="row-title" onClick={() => setEditing(t)}>{label(t)}</button><span className="row-meta">{t.kind === 'income' ? 'Income' : 'Expense'}{t.note ? ' · ' + t.category : ''}{t.bill_id ? ' · From a paid bill' : ''}</span></div>
      <span className="row-amount">{t.kind === 'income' ? signedMoney(t.amount, t.currency) : money(t.amount, t.currency)}</span>
      <div className="row-actions"><button className="icon-button" aria-label={'Edit ' + label(t)} onClick={() => setEditing(t)}><Pencil size={16} /></button><button className="icon-button" aria-label={'Delete ' + label(t)} onClick={() => setDeleting(t)}><Trash2 size={16} /></button></div>
    </li>)}</ul> : <div className="empty"><p>No {kind === 'all' ? 'transactions' : kind === 'income' ? 'income' : 'expenses'} in {monthLabel(month)}.</p></div>)}
    {page.data && <Pagination offset={offset} total={page.data.total} loading={page.loading} onChange={setOffset} />}
    {editing && <TransactionEditor kind={editing.kind} record={asRecord(editing)} today={today} currency={currency} onClose={() => setEditing(undefined)} onSaved={done} />}
    {deleting && <ConfirmDialog title={deleting.kind === 'income' ? 'Delete this income?' : 'Delete this expense?'}
      body={deleting.bill_id ? 'This spending came from a paid bill. The bill stays marked paid; you can mark it unpaid afterward.' : `${money(deleting.amount, deleting.currency)} on ${dateLabel(deleting.date)} will be permanently removed.`}
      action="Delete" onClose={() => setDeleting(undefined)}
      onConfirm={async () => { if (deleting.kind === 'income') await api.deleteIncome(deleting.id); else await api.deleteExpense(deleting.id); done(deleting.kind === 'income' ? 'Income deleted.' : 'Expense deleted.'); }} />}
  </section>;
}

export function BudgetsView({ revision, today, currency, month, onMonth, onChanged }: MoneyProps) {
  const [local, setLocal] = useState(0);
  const [editing, setEditing] = useState<{ budget?: Budget }>();
  const [deleting, setDeleting] = useState<Budget>();
  const loadBudgets = useCallback((signal: AbortSignal) => api.budgets(signal), []);
  const budgets = useResource(loadBudgets, revision + local);
  const summary = useSummary(month, revision + local);
  function done(message?: string) { setEditing(undefined); setDeleting(undefined); setLocal(r => r + 1); onChanged(message); }
  const lineFor = (b: Budget) => summary.data?.categories.find(l => l.budget_id === b.id);
  return <section aria-labelledby="view-title">
    <PageHead title="Budgets" count="Monthly limits by expense category" action={<button className="button secondary small" onClick={() => setEditing({})}><Plus size={16} />Add budget</button>} />
    <MonthNav month={month} today={today} onMonth={onMonth} />
    {budgets.error && <div role="alert" className="error">{budgets.error}</div>}
    {budgets.loading && !budgets.data && <p role="status" className="loading">Loading…</p>}
    {budgets.data && (budgets.data.length ? <ul className="rows budget-rows">{budgets.data.map(b => { const line = lineFor(b); const over = line && Number(line.remaining) < 0; return <li key={b.id} className={'row budget-row' + (over ? ' overdue' : '')}>
      <div className="row-copy"><button className="row-title" onClick={() => setEditing({ budget: b })}>{b.category}</button>
        <span className={'row-meta' + (over ? ' warn-text' : '')}>{line ? remainingLabel(line) : money(b.amount, b.currency) + ' each month'}</span>{line && <BudgetMeter line={line} />}</div>
      <div className="row-actions"><button className="icon-button" aria-label={'Edit ' + b.category + ' budget'} onClick={() => setEditing({ budget: b })}><Pencil size={16} /></button><button className="icon-button" aria-label={'Delete ' + b.category + ' budget'} onClick={() => setDeleting(b)}><Trash2 size={16} /></button></div>
    </li>; })}</ul> : <div className="empty"><p>No budgets yet. A budget is a standing monthly limit for one expense category.</p><button className="text-button" onClick={() => setEditing({})}><Plus size={15} />Add budget</button></div>)}
    <p className="form-hint">Budgets apply to every month. Income never changes a budget, and amounts in different currencies are kept apart.</p>
    {editing && <BudgetEditor budget={editing.budget} currency={currency} onClose={() => setEditing(undefined)} onSaved={done} />}
    {deleting && <ConfirmDialog title="Remove this budget?" body={`The budget for “${deleting.category}” will be removed. Expenses are kept.`} action="Remove budget" onClose={() => setDeleting(undefined)} onConfirm={async () => { await api.deleteBudget(deleting.id); done('Budget removed.'); }} />}
  </section>;
}

function BudgetEditor({ budget, currency, onClose, onSaved }: { budget?: Budget; currency: string; onClose: () => void; onSaved: (message: string) => void }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (pending) return;
    const form = new FormData(e.currentTarget);
    const text = (key: string) => String(form.get(key) || '').trim();
    if (!text('category_id')) { setError('Choose a category.'); return; }
    setPending(true); setError('');
    try { await api.saveBudget({ category_id: text('category_id'), amount: text('amount'), currency: text('currency').toUpperCase() }, budget?.id); onSaved('Budget saved.'); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not save the budget.'); }
    finally { setPending(false); }
  }
  return <Dialog title={budget ? 'Edit budget' : 'Add budget'} onClose={onClose} pending={pending}>
    <form onSubmit={submit} className="record-form"><fieldset disabled={pending}>
      <CategorySelect scope="expense" label="Category" required defaultValue={budget?.category_id ?? null} />
      <div className="form-pair amount-pair"><label>Each month<input type="number" name="amount" min="0" step="0.01" required inputMode="decimal" defaultValue={budget?.amount} /></label><label>Currency<input name="currency" required pattern="[A-Za-z]{3}" maxLength={3} autoCapitalize="characters" defaultValue={budget?.currency || currency} /></label></div>
    </fieldset>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="dialog-actions"><button type="button" className="button secondary" disabled={pending} onClick={onClose}>Cancel</button><button className="button primary" disabled={pending}>{pending ? 'Saving…' : 'Save budget'}</button></div>
    </form>
  </Dialog>;
}
