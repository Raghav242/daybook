import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError, clearSession } from '../shared/api/client';
import type { Bill, Module, RecordItem, User } from '../shared/api/contracts';
import { AuthScreen } from '../features/auth/AuthScreen';
import { titleOf, todayIn, toggleInput } from '../shared/domain';
import { useResource } from '../shared/hooks/useResource';
import { CategoriesProvider } from '../shared/categories';
import { Dialog } from '../shared/ui/Dialog';
import { RecordEditor } from '../shared/ui/RecordEditor';
import TodayView from '../features/today';
import TasksView from '../features/tasks';
import CalendarView from '../features/calendar';
import GroceriesView from '../features/groceries';
import BillsView from '../features/bills';
import SettingsView from '../features/settings';
import MealsView from '../features/meals';
import LibraryView from '../features/library';
import { BudgetsView, MoneyOverview, TransactionsView } from '../features/money';
import { PayDialog } from '../features/bills/PayDialog';
import { QuickAdd } from '../features/capture/QuickAdd';
import { entryKinds, type EntryKind } from '../features/capture/kinds';
import { enabledRoute, parseRoute, routeModule, routeTitles, type Route } from './routes';
import { AddButton, Shell } from './Shell';

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [revision, setRevision] = useState(0);
  const [checking, setChecking] = useState(0);
  const sessionVersion = useRef(0);
  const [tabId] = useState(() => crypto.randomUUID());
  useEffect(() => {
    const controller = new AbortController();
    const version = sessionVersion.current;
    api.me(controller.signal).then(session => {
      if (!controller.signal.aborted && version === sessionVersion.current) {setUser(session.user); setError('');}
    }).catch(err => {
      if (!controller.signal.aborted && version === sessionVersion.current) {
        setUser(null); clearSession();
        if (!(err instanceof ApiError && err.status === 401)) setError(err instanceof Error ? err.message : 'Could not check your session.');
      }
    }).finally(() => {if (!controller.signal.aborted && version === sessionVersion.current) setLoading(false);});
    return () => controller.abort();
  }, [checking]);
  useEffect(() => {
    const expired = () => {sessionVersion.current++; setUser(null); setLoading(false); setRevision(r => r + 1); setMessage('Your session has ended. Sign in again to continue.');};
    window.addEventListener('daybook:session-expired', expired);
    const channel = typeof BroadcastChannel === 'undefined' ? null : new BroadcastChannel('daybook-account');
    const recheck = () => {sessionVersion.current++; clearSession(); setUser(null); setLoading(true); setRevision(r => r + 1); setChecking(r => r + 1);};
    if (channel) channel.onmessage = event => {if (event.data?.sender !== tabId) recheck();};
    // Revalidate after returning to this tab, including changes made in another tab.
    // Browser password-manager dialogs can restore window focus. Preserve guest drafts/errors.
    const focused = (event: FocusEvent) => {if (event.target === window && user) recheck();};
    window.addEventListener('focus', focused);
    return () => {window.removeEventListener('daybook:session-expired', expired); window.removeEventListener('focus', focused); channel?.close();};
  }, [tabId, user]);
  function changed(next: User | null) {
    sessionVersion.current++; setLoading(false); setUser(next); setRevision(r => r + 1); setMessage('');
    if (typeof BroadcastChannel !== 'undefined') {const channel = new BroadcastChannel('daybook-account'); channel.postMessage({sender: tabId}); channel.close();}
  }
  if (loading) return <main className="auth-shell"><p role="status">Opening your Daybook…</p></main>;
  if (error) return <main className="auth-shell"><div role="alert"><p>{error}</p><button className="button secondary" onClick={() => {setError(''); setLoading(true); setChecking(r => r + 1);}}>Try again</button></div></main>;
  if (!user) return <AuthScreen message={message} onSignedIn={next => changed(next)}/>;
  // Unmounting the complete private tree discards resources, drafts and dialogs.
  return <PrivateApp key={user.id + ':' + revision} user={user} onLoggedOut={() => changed(null)}/>;
}

type Adding = { kind?: EntryKind };

function PrivateApp({user, onLoggedOut}: {user: User; onLoggedOut: () => void}) {
  const [hash, setHash] = useState(() => window.location.hash);
  const [revision, setRevision] = useState(0);
  const [adding, setAdding] = useState<Adding>();
  const [editor, setEditor] = useState<{module: Module; item: RecordItem}>();
  const [deleting, setDeleting] = useState<{module: Module; item: RecordItem}>();
  const [paying, setPaying] = useState<Bill>();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [mutationError, setMutationError] = useState('');
  const [month, setMonth] = useState('');
  async function logout() {
    if (busy) return;
    setBusy(true); setMutationError('');
    try {await api.logout(); onLoggedOut();}
    catch (err) {
      if (err instanceof ApiError && err.status === 401) {clearSession(); onLoggedOut();}
      else setMutationError(err instanceof Error ? err.message : 'Could not sign out.');
    }
    finally {setBusy(false);}
  }
  const settingsLoad = useCallback((signal: AbortSignal) => api.settings(signal), []);
  const dashboardLoad = useCallback((signal: AbortSignal) => api.dashboard(signal), []);
  const settingsResource = useResource(settingsLoad, revision);
  const dashboard = useResource(dashboardLoad, revision);
  const settings = settingsResource.data;
  useEffect(() => {
    const navigate = () => { if (window.location.hash === '#main-content') return; setHash(window.location.hash); setMutationError(''); window.scrollTo({top: 0}); };
    window.addEventListener('hashchange', navigate);
    return () => window.removeEventListener('hashchange', navigate);
  }, []);
  useEffect(() => { if (!notice) return; const timer = setTimeout(() => setNotice(''), 5000); return () => clearTimeout(timer); }, [notice]);
  // Refresh date-sensitive summaries across local midnight and after returning to the app.
  useEffect(() => {
    const refresh = () => setRevision(r => r + 1);
    const visible = () => { if (document.visibilityState === 'visible') refresh(); };
    const timer = setInterval(refresh, 60000);
    document.addEventListener('visibilitychange', visible);
    return () => { clearInterval(timer); document.removeEventListener('visibilitychange', visible); };
  }, []);
  const enabled = settings?.enabled_modules || [];
  const route: Route = parseRoute(hash, enabled);
  useEffect(() => { document.title = routeTitles[route] + ' · Daybook'; }, [route]);
  function saved(message = 'Saved.') { setRevision(r => r + 1); setAdding(undefined); setEditor(undefined); setPaying(undefined); setNotice(message); setMutationError(''); }
  async function toggle(module: Module, item: RecordItem) {
    if (busy) return;
    // Marking a bill paid asks whether to record the payment as spending.
    if (module === 'bills' && 'paid' in item && !item.paid) { setMutationError(''); setPaying(item); return; }
    setBusy(true); setMutationError('');
    try {
      await api.save(module, toggleInput(item), item.id);
      const done = 'completed' in item ? !item.completed : 'purchased' in item ? !item.purchased : 'paid' in item ? !item.paid : false;
      saved(done ? '“' + titleOf(item) + '” done.' : '“' + titleOf(item) + '” reopened.');
    }
    catch (err) { setMutationError(err instanceof Error ? err.message : 'Could not update status.'); }
    finally { setBusy(false); }
  }
  async function remove() {
    if (!deleting || busy) return;
    setBusy(true); setMutationError('');
    try { await api.delete(deleting.module, deleting.item.id); setDeleting(undefined); saved('Deleted “' + titleOf(deleting.item) + '”.'); requestAnimationFrame(() => document.getElementById('main-content')?.focus()); }
    catch (err) { setMutationError(err instanceof Error ? err.message : 'Could not delete.'); }
    finally { setBusy(false); }
  }
  const actions = { onEdit: (module: Module, item: RecordItem) => setEditor({module, item}), onDelete: (module: Module, item: RecordItem) => { setMutationError(''); setDeleting({module, item}); }, onToggle: toggle, busy };
  const today = dashboard.data?.today || (settings ? todayIn(settings.timezone) : '');
  const currentMonth = month || today.slice(0, 7);
  const canAdd = settings ? entryKinds(enabled).length > 0 : false;
  const add = (kind?: EntryKind) => setAdding({kind});
  const listProps = { revision, zone: settings?.timezone || 'UTC', today, onAdd: (module: Module) => add(module), ...actions };
  const moneyProps = { revision, today, currency: settings?.default_currency || 'USD', month: currentMonth, onMonth: setMonth, onAdd: add, onChanged: (message?: string) => saved(message) };
  const routeOff = settings && !enabledRoute(route, enabled);
  return <CategoriesProvider revision={revision}>
    <Shell route={route} user={user} enabled={enabled} busy={busy} onLogout={logout} addButton={<AddButton disabled={!canAdd} onClick={() => add()} />}>
      {notice && <p className="toast" role="status"><span>{notice}</span><button className="icon-button" aria-label="Dismiss" onClick={() => setNotice('')}>×</button></p>}
      {mutationError && !deleting && <p className="error" role="alert">{mutationError}</p>}
      {settingsResource.error && <div className="error" role="alert">{settingsResource.error}<button className="text-button" onClick={() => setRevision(r => r + 1)}>Try again</button></div>}
      {!settings && settingsResource.loading && <p role="status" className="loading">Opening your Daybook…</p>}
      {routeOff && <div className="empty"><h1 className="page-title">{routeTitles[route]} is turned off</h1><p>Your records are kept. Turn the {routeModule[route] === 'budget' ? 'Money' : routeTitles[route]} module on in Settings to see them.</p><a href="#settings" className="button secondary small">Open settings</a></div>}
      {settings && !routeOff && <>
        {route === 'today' && <>{dashboard.error && <div role="alert" className="error">{dashboard.error}<button className="text-button" onClick={() => setRevision(r => r + 1)}>Try again</button></div>}{!dashboard.data && dashboard.loading && <p role="status" className="loading">Gathering your day…</p>}{dashboard.data && <TodayView data={dashboard.data} settings={settings} onAdd={add} {...actions} />}</>}
        {route === 'tasks' && <TasksView {...listProps} />}
        {route === 'calendar' && <CalendarView {...listProps} />}
        {route === 'groceries' && <GroceriesView {...listProps} />}
        {route === 'bills' && <BillsView {...listProps} />}
        {route === 'meals' && <MealsView revision={revision} today={today} onChanged={saved} />}
        {route === 'money' && <MoneyOverview {...moneyProps} />}
        {route === 'transactions' && <TransactionsView {...moneyProps} />}
        {route === 'budgets' && <BudgetsView {...moneyProps} />}
        {route === 'library' && <LibraryView />}
        {route === 'settings' && <SettingsView settings={settings} onSaved={message => saved(message)} />}
      </>}
    </Shell>
    {adding && settings && <QuickAdd settings={settings} today={today} initial={adding.kind} onClose={() => setAdding(undefined)} onSaved={saved} />}
    {editor && settings && <RecordEditor initialModule={editor.module} item={editor.item} settings={settings} onClose={() => setEditor(undefined)} onSaved={saved} />}
    {paying && settings && <PayDialog bill={paying} today={today} budgetEnabled={enabled.includes('budget')} onClose={() => setPaying(undefined)} onPaid={saved} />}
    {deleting && <Dialog title="Delete this?" pending={busy} onClose={() => { setDeleting(undefined); setMutationError(''); }}><p className="dialog-lead">“{titleOf(deleting.item)}” will be permanently deleted.</p>{mutationError && <p className="error" role="alert">{mutationError}</p>}<div className="dialog-actions"><button className="button secondary" disabled={busy} onClick={() => { setDeleting(undefined); setMutationError(''); }}>Keep it</button><button className="button danger" disabled={busy} onClick={remove}>{busy ? 'Deleting…' : 'Delete'}</button></div></Dialog>}
  </CategoriesProvider>;
}
