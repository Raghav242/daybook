import { ArrowRight, CalendarDays, Check, Plus, ShoppingBasket, Wallet, ListTodo } from 'lucide-react';
import type { Dashboard, Module, Settings } from '../../shared/api/contracts';
import { dateLabel, eventLabel, money, timeLabel } from '../../shared/domain';
import { RecordRow, type RowActions } from '../../shared/ui/RecordRow';

export default function DashboardView({ data, settings, onAdd, ...actions }: RowActions & { data: Dashboard; settings: Settings; onAdd: (module: Module) => void }) {
  const enabled = (module: Module) => settings.enabled_modules.includes(module);
  const attention = (enabled('tasks') ? data.counts.tasks_overdue : 0) + (enabled('bills') ? data.counts.bills_overdue : 0);
  return <section aria-labelledby="view-title" className="dashboard">
    <header className="page-heading dashboard-heading"><div><p className="eyebrow">{new Intl.DateTimeFormat('en-US', { weekday: 'long', timeZone: 'UTC' }).format(new Date(data.today + 'T12:00Z')).toUpperCase()} · {dateLabel(data.today, true).toUpperCase()}</p><h1 id="view-title">A little more organized.</h1><p className="page-subtitle">A quiet place for everything on your plate.</p></div><div className="today-stamp"><span>Today</span><strong>{data.today.slice(8)}</strong></div></header>
    <div className="dashboard-columns">
      <div className="main-column">
        {enabled('calendar') && <section className="agenda-section"><div className="section-heading"><h2><CalendarDays size={18} />Today’s agenda</h2><a href="#calendar">Full agenda<ArrowRight size={15} /></a></div>
          {data.agenda.length ? <ul className="agenda-list">{data.agenda.map(event => <li key={event.id}><div className="agenda-time">{event.all_day ? 'All day' : timeLabel(event.start, data.timezone)}<span>{event.all_day ? '' : timeLabel(event.end, data.timezone)}</span></div><div className="agenda-entry"><button onClick={() => actions.onEdit('calendar', event)}>{event.title}</button>{event.description && <p>{event.description}</p>}</div></li>)}</ul> : <div className="quiet-empty"><p>Your day has some breathing room.</p><button className="text-button" onClick={() => onAdd('calendar')}>Add a plan<Plus size={14} /></button></div>}
          {data.agenda.length === 8 && <a className="text-button" href="#calendar">See all agenda entries<ArrowRight size={14} /></a>}
        </section>}
        {enabled('tasks') && <section className="task-section"><div className="section-heading"><h2><ListTodo size={18} />Your next steps</h2><a href="#tasks">All tasks<ArrowRight size={15} /></a></div>
          <p className="section-note">{data.counts.tasks_today ? data.counts.tasks_today + ' open ' + (data.counts.tasks_today === 1 ? 'task needs' : 'tasks need') + ' attention today.' : 'Start with one small thing.'}</p>
          {data.tasks.length ? <ul className="records-list">{data.tasks.map(item => <RecordRow key={item.id} module="tasks" item={item} zone={data.timezone} compact {...actions} />)}</ul> : <div className="quiet-empty"><p>No open tasks. Enjoy the space.</p><button className="text-button" onClick={() => onAdd('tasks')}>Add a task<Plus size={14} /></button></div>}
        </section>}
      </div>
      <aside className="secondary-column" aria-label="Attention and upcoming plans">
        <section className="attention-section"><p className="eyebrow">A GENTLE CHECK-IN</p><h2>Needs attention</h2>
          {attention ? <><p className="attention-intro">A few things to come back to.</p>{enabled('tasks') && data.counts.tasks_overdue > 0 && <a className="attention-row" href="#tasks"><span className="attention-dot" /><span><strong>{data.counts.tasks_overdue} overdue {data.counts.tasks_overdue === 1 ? 'task' : 'tasks'}</strong><small>Take a look when you can</small></span><ArrowRight size={16} /></a>}{enabled('bills') && data.counts.bills_overdue > 0 && <a className="attention-row" href="#bills"><span className="attention-dot" /><span><strong>{data.counts.bills_overdue} overdue {data.counts.bills_overdue === 1 ? 'bill' : 'bills'}</strong><small>Review unpaid bills</small></span><ArrowRight size={16} /></a>}</> : <div className="all-clear"><Check size={20} /><p>You’re all caught up.<span>No overdue tasks or bills.</span></p></div>}
        </section>
        {enabled('calendar') && <section className="upcoming-section"><div className="section-heading"><h2>Coming up</h2><a href="#calendar" aria-label="View upcoming calendar entries"><ArrowRight size={16} /></a></div>{data.upcoming.length ? <ul>{data.upcoming.map(event => <li key={event.id}><button onClick={() => actions.onEdit('calendar', event)}>{event.title}</button><span>{eventLabel(event, data.timezone)}</span></li>)}</ul> : <p className="muted">No upcoming plans yet.</p>}</section>}
        <div className="margin-note"><span className="note-line" /><p>A day at a time.<br />A little less to keep in your head.</p></div>
      </aside>
    </div>
    {(enabled('groceries') || enabled('bills')) && <div className="dashboard-lower">
      {enabled('groceries') && <section><div className="section-heading"><h2><ShoppingBasket size={18} />The grocery list</h2><a href="#groceries">View list<ArrowRight size={15} /></a></div><p className="section-note">{data.counts.groceries_remaining} {data.counts.groceries_remaining === 1 ? 'item' : 'items'} left to pick up</p>{data.groceries.length ? <ul className="records-list">{data.groceries.map(item => <RecordRow key={item.id} module="groceries" item={item} zone={data.timezone} compact {...actions} />)}</ul> : <p className="muted lower-empty">Your list is clear. Add what you need for the week.</p>}<button className="text-button add-link" onClick={() => onAdd('groceries')}><Plus size={15} />Add an item</button></section>}
      {enabled('bills') && <section><div className="section-heading"><h2><Wallet size={18} />Upcoming bills</h2><a href="#bills">All bills<ArrowRight size={15} /></a></div><p className="section-note">Unpaid · through {dateLabel(data.bill_horizon)}</p>{Object.entries(data.bill_totals).length > 0 && <div className="bill-summary">{Object.entries(data.bill_totals).map(([currency, amount]) => <strong key={currency}>{money(amount, currency)}<span>{currency} total</span></strong>)}</div>}{data.bills.length ? <ul className="records-list">{data.bills.map(item => <RecordRow key={item.id} module="bills" item={item} zone={data.timezone} compact {...actions} />)}</ul> : <p className="muted lower-empty">No unpaid bills due in the next 30 days.</p>}</section>}
    </div>}
    {settings.enabled_modules.length === 0 && <div className="empty-state"><h2>Make Daybook your own</h2><p>Enable a module in settings to start organizing your day.</p><a href="#settings" className="button secondary">Open settings</a></div>}
  </section>;
}

