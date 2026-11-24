import { formatInTimeZone } from 'date-fns-tz';
import { ArrowRight, Repeat } from 'lucide-react';
import type { Bill, CalendarEntry, Dashboard, FeatureModule, Module, Settings, Task } from '../../shared/api/contracts';
import { addDays, dateLabel, longDate, mealNames, money, monthLabel, timeLabel, weekdayLabel } from '../../shared/domain';
import { RecordRow, type RowActions } from '../../shared/ui/RecordRow';
import type { EntryKind } from '../capture/kinds';

type Props = RowActions & { data: Dashboard; settings: Settings; onAdd: (kind?: EntryKind) => void };

function ViewAll({ href, label }: { href: string; label: string }) {
  return <a className="view-all" href={href}>{label}<ArrowRight size={14} aria-hidden="true" /></a>;
}

export default function TodayView({ data, settings, onAdd, ...actions }: Props) {
  const on = (module: FeatureModule) => settings.enabled_modules.includes(module);
  const zone = data.timezone;
  const localDay = (instant: string) => formatInTimeZone(instant, zone, 'yyyy-MM-dd');

  if (!data.has_records) return <section className="today" aria-labelledby="view-title">
    <header className="page-head"><h1 id="view-title" className="page-title">Today</h1><p className="page-date">{longDate(data.today)}</p></header>
    <div className="starter">
      <h2>Start with one thing</h2>
      <p>Your day fills in as you add tasks, plans, groceries and money. Everything stays in your account.</p>
      <div className="starter-actions">
        {on('tasks') && <button className="button primary" onClick={() => onAdd('tasks')}>Add a task</button>}
        {on('calendar') && <button className="button secondary" onClick={() => onAdd('calendar')}>Add an event</button>}
        {on('budget') && <button className="button secondary" onClick={() => onAdd('expense')}>Record an expense</button>}
      </div>
    </div>
  </section>;

  // Needs attention: only actionable items, and only when there are some.
  const overdueTasks = on('tasks') ? data.overdue_tasks : [];
  const overdueBills = on('bills') ? data.overdue_bills : [];
  const overBudget = on('budget') ? data.spending?.over_budget || [] : [];
  const attention = overdueTasks.length + overdueBills.length + overBudget.length > 0;

  // One daily agenda: timed items on a timeline, date-only items below it.
  type Slot = { key: string; sort: string; time: string; end?: string; event?: CalendarEntry; task?: Task };
  const timeline: Slot[] = [
    ...(on('calendar') ? data.agenda : []).map(event => ({
      key: 'e' + event.id, event,
      sort: event.all_day ? '0' : event.start,
      time: event.all_day ? 'All day' : localDay(event.start) < data.today ? 'Earlier' : timeLabel(event.start, zone),
      end: event.all_day ? undefined : localDay(event.end) > data.today ? 'Continues' : timeLabel(event.end, zone),
    })),
    ...(on('tasks') ? data.due_today.filter(t => t.due_at) : []).map(task => ({ key: 't' + task.id, task, sort: task.due_at!, time: timeLabel(task.due_at!, zone) })),
  ].sort((a, b) => a.sort.localeCompare(b.sort));
  const dueToday: { module: Module; item: Task | Bill }[] = [
    ...(on('tasks') ? data.due_today.filter(t => !t.due_at) : []).map(item => ({ module: 'tasks' as Module, item })),
    ...(on('bills') ? data.upcoming_bills.filter(b => b.due_date === data.today) : []).map(item => ({ module: 'bills' as Module, item })),
  ];
  const unscheduled = on('tasks') ? data.unscheduled : [];

  // One upcoming list: events, dated tasks (including repeating ones) and bills.
  type Upcoming = { key: string; day: string; sort: string; title: string; meta: string; repeats: boolean; open: () => void };
  const upcoming: Upcoming[] = [
    ...(on('calendar') ? data.upcoming : []).map(event => {
      const day = event.all_day ? event.start_date! : localDay(event.start);
      return { key: 'e' + event.id, day, sort: day + (event.all_day ? '0' : event.start), title: event.title, meta: event.all_day ? 'All day' : timeLabel(event.start, zone), repeats: false, open: () => actions.onEdit('calendar', event) };
    }),
    ...(on('tasks') ? data.upcoming_tasks : []).map(task => {
      const day = task.due_date || localDay(task.due_at!);
      return { key: 't' + task.id, day, sort: day + '1', title: task.title, meta: task.due_at ? 'Task · ' + timeLabel(task.due_at, zone) : 'Task', repeats: Boolean(task.series_id), open: () => actions.onEdit('tasks', task) };
    }),
    ...(on('bills') ? data.upcoming_bills.filter(b => b.due_date > data.today) : []).map(bill => ({
      key: 'b' + bill.id, day: bill.due_date, sort: bill.due_date + '2', title: bill.name, meta: 'Bill · ' + money(bill.amount, bill.currency), repeats: Boolean(bill.series_id), open: () => actions.onEdit('bills', bill),
    })),
  ].sort((a, b) => a.sort.localeCompare(b.sort)).slice(0, 6);
  const dayName = (day: string) => day === addDays(data.today, 1) ? 'Tomorrow' : weekdayLabel(day) + ' ' + Number(day.slice(8));

  const meals = on('meals') ? data.meals_today : [];
  const groceries = on('groceries') && data.counts.groceries_remaining > 0;
  const spending = on('budget') ? data.spending : null;
  const billTotals = !spending && on('bills') ? Object.entries(data.bill_totals) : [];
  const moneyLines = spending ? spending.totals.filter(t => Number(t.spent) || Number(t.income)) : [];
  const glance = meals.length > 0 || groceries || moneyLines.length > 0 || (spending?.expected_bills.length || 0) > 0 || billTotals.length > 0;
  const scheduleShown = on('calendar') || on('tasks') || on('bills');

  return <section className="today" aria-labelledby="view-title">
    <header className="page-head"><h1 id="view-title" className="page-title">Today</h1><p className="page-date">{longDate(data.today)}</p></header>

    {attention && <section className="attention" aria-labelledby="attention-title">
      <h2 id="attention-title" className="section-title">Needs attention</h2>
      <ul className="rows">
        {overdueTasks.map(task => <RecordRow key={task.id} module="tasks" item={task} zone={zone} today={data.today} compact {...actions} />)}
        {overdueBills.map(bill => <RecordRow key={bill.id} module="bills" item={bill} zone={zone} today={data.today} compact {...actions} />)}
        {overBudget.map(line => <li key={line.category_id + line.currency} className="row note-row"><span className="status-dot warn" aria-hidden="true" /><div className="row-copy"><a className="row-title" href="#money">{line.category} is over budget</a><span className="row-meta">{money(String(Math.abs(Number(line.remaining))), line.currency)} over this month</span></div></li>)}
      </ul>
      {data.counts.tasks_overdue > overdueTasks.length && on('tasks') && <ViewAll href="#tasks" label={'All ' + data.counts.tasks_overdue + ' overdue tasks'} />}
      {data.counts.bills_overdue > overdueBills.length && on('bills') && <ViewAll href="#bills" label="All unpaid bills" />}
    </section>}

    {scheduleShown && <section aria-labelledby="schedule-title">
      <div className="section-head"><h2 id="schedule-title" className="section-title">Schedule</h2>{on('calendar') && <ViewAll href="#calendar" label="Calendar" />}</div>
      {timeline.length > 0 && <ol className="timeline">{timeline.map(slot => <li key={slot.key} className={'slot' + (slot.task ? ' slot-task' : '')}>
        <span className="slot-time">{slot.time}{slot.end && <small>{slot.end}</small>}</span>
        {slot.event
          ? <div className="slot-body"><button className="row-title" onClick={() => actions.onEdit('calendar', slot.event!)}>{slot.event.title}</button>{slot.event.description && <span className="row-meta clamp">{slot.event.description}</span>}</div>
          : <div className="slot-body slot-check"><input type="checkbox" className="check" checked={false} disabled={actions.busy} aria-label={'Mark ' + slot.task!.title + ' complete'} onChange={() => actions.onToggle('tasks', slot.task!)} /><div><button className="row-title" onClick={() => actions.onEdit('tasks', slot.task!)}>{slot.task!.title}</button><span className="row-meta">Task due</span></div></div>}
      </li>)}</ol>}
      {dueToday.length > 0 && <>
        <h3 className="subhead">Due today</h3>
        <ul className="rows">{dueToday.map(({ module, item }) => <RecordRow key={item.id} module={module} item={item} zone={zone} today={data.today} compact {...actions} />)}</ul>
      </>}
      {!timeline.length && !dueToday.length && <p className="quiet">Nothing scheduled for today.</p>}
    </section>}

    {unscheduled.length > 0 && <section aria-labelledby="anytime-title">
      <div className="section-head"><h2 id="anytime-title" className="section-title">Anytime</h2>{data.counts.tasks_unscheduled > unscheduled.length && <ViewAll href="#tasks" label={'View all ' + data.counts.tasks_unscheduled} />}</div>
      <ul className="rows">{unscheduled.map(task => <RecordRow key={task.id} module="tasks" item={task} zone={zone} today={data.today} compact {...actions} />)}</ul>
    </section>}

    {upcoming.length > 0 && <section aria-labelledby="upcoming-title">
      <div className="section-head"><h2 id="upcoming-title" className="section-title">Coming up</h2>{on('calendar') && <ViewAll href="#calendar" label="View all" />}</div>
      <ul className="rows upcoming">{upcoming.map(item => <li key={item.key} className="row">
        <span className="row-day">{dayName(item.day)}</span>
        <div className="row-copy"><button className="row-title" onClick={item.open}>{item.title}</button><span className="row-meta">{item.repeats && <Repeat size={12} aria-label="Repeats" className="inline-icon" />}{item.meta}</span></div>
      </li>)}</ul>
    </section>}

    {glance && <section aria-labelledby="glance-title">
      <h2 id="glance-title" className="section-title">At a glance</h2>
      <dl className="glance">
        {meals.length > 0 && <div><dt>Meals</dt><dd>{meals.slice(0, 3).map(m => mealNames[m.meal] + ': ' + m.recipe_name).join(' · ')}</dd><dd className="glance-link"><a href="#meals">Meal plan</a></dd></div>}
        {groceries && <div><dt>Groceries</dt><dd>{data.counts.groceries_remaining} to buy{data.groceries.length > 0 && ' · ' + data.groceries.slice(0, 3).map(g => g.name).join(', ')}</dd><dd className="glance-link"><a href="#groceries">List</a></dd></div>}
        {spending && (moneyLines.length > 0 || spending.expected_bills.length > 0) && <div><dt>{monthLabel(spending.month).split(' ')[0]}</dt>
          {moneyLines.map(t => <dd key={t.currency}>{money(t.spent, t.currency)} spent{Number(t.income) > 0 && ' · ' + money(t.income, t.currency) + ' received'}</dd>)}
          {spending.expected_bills.map(b => <dd key={'b' + b.currency} className="muted">{b.count} unpaid {b.count === 1 ? 'bill' : 'bills'} · {money(b.amount, b.currency)} still due</dd>)}
          <dd className="glance-link"><a href="#money">Money</a></dd></div>}
        {billTotals.length > 0 && <div><dt>Bills</dt>{billTotals.map(([currency, amount]) => <dd key={currency}>{money(amount, currency)} unpaid through {dateLabel(data.bill_horizon)}</dd>)}<dd className="glance-link"><a href="#bills">Bills</a></dd></div>}
      </dl>
    </section>}
  </section>;
}
