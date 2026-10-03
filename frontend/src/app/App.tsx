import { useCallback, useEffect, useRef, useState } from 'react';
import { BookOpen, CalendarDays, LayoutDashboard, ListTodo, Plus, Settings as SettingsIcon, ShoppingBasket, Wallet, ArrowUpRight } from 'lucide-react';
import { api, ApiError, clearSession } from '../shared/api/client';
import type { Module, RecordItem, User, View } from '../shared/api/contracts';
import { AuthScreen } from '../features/auth/AuthScreen';
import { moduleNames, titleOf, toggleInput } from '../shared/domain';
import { useResource } from '../shared/hooks/useResource';
import { Dialog } from '../shared/ui/Dialog';
import { RecordEditor } from '../shared/ui/RecordEditor';
import DashboardView from '../features/dashboard';
import TasksView from '../features/tasks';
import CalendarView from '../features/calendar';
import GroceriesView from '../features/groceries';
import BillsView from '../features/bills';
import SettingsView from '../features/settings';

const icons = { dashboard: LayoutDashboard, tasks: ListTodo, calendar: CalendarDays, groceries: ShoppingBasket, bills: Wallet, settings: SettingsIcon };
const viewFromHash = (): View => { const hash = window.location.hash.slice(1); return hash in icons ? hash as View : 'dashboard'; };
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

function PrivateApp({user, onLoggedOut}: {user: User; onLoggedOut: () => void}) {
  const [view, setView] = useState<View>(viewFromHash);
  const [revision, setRevision] = useState(0);
  const [editor, setEditor] = useState<{module?: Module; item?: RecordItem}>();
  const [deleting, setDeleting] = useState<{module: Module; item: RecordItem}>();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [mutationError, setMutationError] = useState('');
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
    const navigate = () => { if (window.location.hash === '#main-content') return; setView(viewFromHash()); setNotice(''); setMutationError(''); window.scrollTo({top: 0}); };
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
  function saved(message = 'Saved to your Daybook.') { setRevision(r => r + 1); setEditor(undefined); setNotice(message); setMutationError(''); }
  async function toggle(module: Module, item: RecordItem) {
    if (busy) return;
    setBusy(true); setMutationError('');
    try { await api.save(module, toggleInput(item), item.id); saved('Status updated.'); }
    catch (err) { setMutationError(err instanceof Error ? err.message : 'Could not update status.'); }
    finally { setBusy(false); }
  }
  async function remove() {
    if (!deleting || busy) return;
    setBusy(true); setMutationError('');
    try { await api.delete(deleting.module, deleting.item.id); setDeleting(undefined); saved('Record deleted.'); requestAnimationFrame(() => document.getElementById('main-content')?.focus()); }
    catch (err) { setMutationError(err instanceof Error ? err.message : 'Could not delete record.'); }
    finally { setBusy(false); }
  }
  const actions = { onEdit: (module: Module, item: RecordItem) => setEditor({module, item}), onDelete: (module: Module, item: RecordItem) => { setMutationError(''); setDeleting({module, item}); }, onToggle: toggle, busy };
  const onAdd = (module: Module) => setEditor({module});
  const nav = (['dashboard', ...(settings?.enabled_modules || []), 'settings'] as View[]);
  const RecordView = { tasks: TasksView, calendar: CalendarView, groceries: GroceriesView, bills: BillsView };
  const isRecordView = view !== 'dashboard' && view !== 'settings';
  const enabledView = !isRecordView || settings?.enabled_modules.includes(view as Module);
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <aside className="sidebar">
      <a href="#dashboard" className="brand"><span className="brand-mark"><BookOpen size={23} strokeWidth={1.5} /></span><span>daybook<span className="brand-caption">A place for your everyday.</span></span></a>
      <p className="nav-label">YOUR SPACE</p><nav aria-label="Main navigation">{nav.map(v => { const Icon = icons[v]; return <a key={v} href={'#' + v} className={'nav-item' + (view === v ? ' selected' : '')} aria-current={view === v ? 'page' : undefined}><Icon size={19} strokeWidth={1.7} /><span>{v === 'dashboard' ? 'Overview' : v === 'settings' ? 'Settings' : moduleNames[v]}</span></a>; })}</nav>
      <div className="sidebar-later"><p className="nav-label">ON THE HORIZON</p><span>Documents<ArrowUpRight size={14} /></span><span>Meal planning<ArrowUpRight size={14} /></span><small>More room for life, coming later.</small></div>
      <div className="sidebar-footer"><span className="profile-avatar">{user.username[0].toUpperCase()}</span><div><strong>{user.username}</strong><small>Your account</small></div></div>
    </aside>
    <div className="workspace"><header className="topbar"><span className="breadcrumb">Your space<span>/</span>{view === 'dashboard' ? 'Overview' : view === 'settings' ? 'Settings' : moduleNames[view]}</span><div className="topbar-actions"><button className="button secondary" disabled={busy} onClick={logout}>Log out</button><button className="button primary capture-button" disabled={!settings || !settings.enabled_modules.length} onClick={() => setEditor({})}><Plus size={17} />Quick capture</button></div></header>
      <main id="main-content" tabIndex={-1}>
        {notice && <p className="notice" role="status"><span>{notice}</span><button aria-label="Dismiss notification" onClick={() => setNotice('')}>×</button></p>}
        {mutationError && !deleting && <p className="error" role="alert">{mutationError}</p>}
        {settingsResource.error && <div className="error" role="alert">{settingsResource.error}<button className="text-button" onClick={() => setRevision(r => r + 1)}>Try again</button></div>}
        {!settings && settingsResource.loading && <p role="status" className="loading">Opening your Daybook…</p>}
        {settings && !enabledView && <div className="empty-state"><h1>This module is turned off</h1><p>Your records are still here. Enable this module in settings.</p><a href="#settings" className="button secondary">Open settings</a></div>}
        {settings && view === 'dashboard' && <>{dashboard.error && <div role="alert" className="error">{dashboard.error}<button className="text-button" onClick={() => setRevision(r => r + 1)}>Try again</button></div>}{!dashboard.data && dashboard.loading && <p role="status" className="loading">Gathering your day…</p>}{dashboard.data && <DashboardView data={dashboard.data} settings={settings} onAdd={onAdd} {...actions} />}</>}
        {settings && isRecordView && enabledView && (() => { const Component = RecordView[view as Module]; return <Component key={view} revision={revision} zone={settings.timezone} onAdd={onAdd} {...actions} />; })()}
        {settings && view === 'settings' && <SettingsView settings={settings} onSaved={() => setRevision(r => r + 1)} />}
        <footer className="page-footer"><span>Less to remember. More room to live.</span><span>Daybook · Local first</span></footer>
      </main>
    </div>
    {editor && settings && <RecordEditor initialModule={editor.module} item={editor.item} settings={settings} onClose={() => setEditor(undefined)} onSaved={() => saved()} />}
    {deleting && <Dialog title="Delete this record?" pending={busy} onClose={() => { setDeleting(undefined); setMutationError(''); }}><p className="delete-copy">“{titleOf(deleting.item)}” will be permanently removed from your Daybook.</p>{mutationError && <p className="error" role="alert">{mutationError}</p>}<div className="dialog-actions"><button className="button secondary" disabled={busy} onClick={() => { setDeleting(undefined); setMutationError(''); }}>Keep record</button><button className="button danger" disabled={busy} onClick={remove}>{busy ? 'Deleting…' : 'Delete record'}</button></div></Dialog>}
  </div>;
}

