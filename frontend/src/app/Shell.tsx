import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { BookOpen, CalendarCheck, Plus, Sun, Wallet } from 'lucide-react';
import type { FeatureModule, User } from '../shared/api/contracts';
import { routeTitles, tabOf, tabRoutes, type Route, type Tab } from './routes';

const WIDE = '(min-width: 960px)';
function useMediaQuery(query: string) {
  const supported = typeof window !== 'undefined' && typeof window.matchMedia === 'function';
  const [matches, setMatches] = useState(() => supported ? window.matchMedia(query).matches : true);
  useEffect(() => {
    if (!supported) return;
    const list = window.matchMedia(query);
    const change = () => setMatches(list.matches);
    change();
    list.addEventListener('change', change);
    return () => list.removeEventListener('change', change);
  }, [query, supported]);
  return matches;
}

const tabs: { tab: Tab; label: string; icon: typeof Sun }[] = [
  { tab: 'today', label: 'Today', icon: Sun },
  { tab: 'plan', label: 'Plan', icon: CalendarCheck },
  { tab: 'money', label: 'Money', icon: Wallet },
  { tab: 'library', label: 'Library', icon: BookOpen },
];

export function AddButton({ disabled, onClick }: { disabled: boolean; onClick: () => void }) {
  return <button className="button primary add-button" disabled={disabled} onClick={onClick} aria-haspopup="dialog"><Plus size={20} aria-hidden="true" />Add</button>;
}

/** Same information architecture everywhere: a compact sidebar when wide, bottom tabs when narrow. */
export function Shell({ route, user, enabled, busy, onLogout, addButton, children }: { route: Route; user: User; enabled: FeatureModule[]; busy: boolean; onLogout: () => void; addButton: ReactNode; children: ReactNode }) {
  const wide = useMediaQuery(WIDE);
  const current = tabOf(route);
  const visible = tabs.filter(t => tabRoutes(t.tab, enabled).length > 0);
  const sections = current === 'plan' || current === 'money' ? tabRoutes(current, enabled) : [];
  const href = (tab: Tab) => '#' + tabRoutes(tab, enabled)[0];
  const subnav = sections.length > 1 && <nav className="subnav" aria-label={(current === 'plan' ? 'Plan' : 'Money') + ' sections'}>
    {sections.map(r => <a key={r} href={'#' + r} aria-current={r === route ? 'page' : undefined}>{routeTitles[r]}</a>)}
  </nav>;
  return <div className={'shell ' + (wide ? 'wide' : 'narrow')}>
    <a className="skip-link" href="#main-content">Skip to content</a>
    {wide ? <aside className="sidebar">
      <a href="#today" className="brand">Daybook</a>
      {addButton}
      <nav aria-label="Main"><ul className="nav-list">{visible.map(({ tab, label, icon: Icon }) => {
        const children = tab === 'plan' || tab === 'money' ? tabRoutes(tab, enabled) : [];
        return <li key={tab}>
          <a href={href(tab)} className={'nav-item' + (current === tab ? ' active' : '')} aria-current={current === tab && children.length <= 1 ? 'page' : undefined}><Icon size={18} strokeWidth={1.8} aria-hidden="true" />{label}</a>
          {children.length > 1 && <ul className="nav-sub">{children.map(r => <li key={r}><a href={'#' + r} aria-current={route === r ? 'page' : undefined}>{routeTitles[r]}</a></li>)}</ul>}
        </li>;
      })}</ul></nav>
      <ProfileMenu user={user} busy={busy} onLogout={onLogout} active={route === 'settings'} placement="up" />
    </aside> : <header className="topbar">
      <a href="#today" className="brand">Daybook</a>
      <ProfileMenu user={user} busy={busy} onLogout={onLogout} active={route === 'settings'} placement="down" />
    </header>}
    <main id="main-content" tabIndex={-1} className="content">
      {subnav}
      {children}
    </main>
    {!wide && <>
      <div className="fab">{addButton}</div>
      <nav className="tabbar" aria-label="Main"><ul>{visible.map(({ tab, label, icon: Icon }) => <li key={tab}>
        <a href={href(tab)} aria-current={current === tab ? 'page' : undefined}><Icon size={22} strokeWidth={1.8} aria-hidden="true" /><span>{label}</span></a>
      </li>)}</ul></nav>
    </>}
  </div>;
}

/** Account actions live in one menu: Settings and Log out. */
function ProfileMenu({ user, busy, onLogout, active, placement }: { user: User; busy: boolean; onLogout: () => void; active: boolean; placement: 'up' | 'down' }) {
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const id = useId();
  useEffect(() => {
    if (!open) return;
    menu.current?.querySelector<HTMLElement>('[role=menuitem]')?.focus();
    const outside = (event: MouseEvent) => { if (!menu.current?.contains(event.target as Node) && !button.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', outside);
    return () => document.removeEventListener('mousedown', outside);
  }, [open]);
  function keys(event: KeyboardEvent) {
    const items = [...(menu.current?.querySelectorAll<HTMLElement>('[role=menuitem]') || [])];
    const index = items.indexOf(document.activeElement as HTMLElement);
    if (event.key === 'Escape') { event.preventDefault(); setOpen(false); button.current?.focus(); }
    if (event.key === 'ArrowDown') { event.preventDefault(); items[(index + 1) % items.length]?.focus(); }
    if (event.key === 'ArrowUp') { event.preventDefault(); items[(index - 1 + items.length) % items.length]?.focus(); }
    if (event.key === 'Tab') setOpen(false);
  }
  return <div className={'profile ' + placement}>
    <button ref={button} className={'profile-button' + (active ? ' active' : '')} aria-haspopup="menu" aria-expanded={open} aria-controls={id} onClick={() => setOpen(o => !o)}>
      <span className="avatar" aria-hidden="true">{user.username[0].toUpperCase()}</span><span className="profile-name">{user.username}</span>
      <span className="visually-hidden">, account menu</span>
    </button>
    {open && <div ref={menu} id={id} role="menu" aria-label="Account" className="menu" onKeyDown={keys}>
      <a role="menuitem" href="#settings" onClick={() => setOpen(false)}>Settings</a>
      <button role="menuitem" disabled={busy} onClick={() => { setOpen(false); onLogout(); }}>Log out</button>
    </div>}
  </div>;
}
