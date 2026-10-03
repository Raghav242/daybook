import { useState, type FormEvent } from 'react';
import { api } from '../../shared/api/client';
import type { Module, Settings } from '../../shared/api/contracts';
import { moduleNames } from '../../shared/domain';

export default function SettingsView({ settings, onSaved }: { settings: Settings; onSaved: () => void }) {
  const [value, setValue] = useState(settings);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  async function save(e: FormEvent) {
    e.preventDefault();
    if (pending) return;
    setPending(true); setError(''); setSuccess('');
    try { await api.updateSettings(value); setSuccess('Settings saved.'); onSaved(); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not save settings.'); }
    finally { setPending(false); }
  }
  return <section aria-labelledby="view-title"><div className="page-heading"><div><p className="eyebrow">MAKE IT YOURS</p><h1 id="view-title">Settings</h1><p className="page-subtitle">A few preferences for your everyday life.</p></div></div>
    <form className="settings-form" onSubmit={save}><fieldset disabled={pending}><h2>Time & currency</h2><p className="muted">Dates stay dates. Event times follow your timezone.</p><label>Timezone<input value={value.timezone} onChange={e => setValue({...value, timezone: e.target.value})} list="timezones" required placeholder="America/New_York" /></label><datalist id="timezones">{['America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles', 'Europe/London', 'Europe/Paris', 'Asia/Kolkata', 'Asia/Tokyo', 'Australia/Sydney', 'UTC'].map(zone => <option key={zone} value={zone} />)}</datalist><label>Default currency<input required pattern="[A-Z]{3}" maxLength={3} value={value.default_currency} onChange={e => setValue({...value, default_currency: e.target.value.toUpperCase()})} /></label><p className="form-hint">Use a three-letter currency code, such as USD, EUR or INR. Existing bills keep their currency.</p>
      <h2 className="settings-subheading">Your modules</h2><p className="muted">Choose what appears in your navigation and dashboard. Turning a module off preserves its records.</p><div className="module-options">{(Object.keys(moduleNames) as Module[]).map(module => <label key={module} className="checkbox-label"><input type="checkbox" checked={value.enabled_modules.includes(module)} onChange={e => setValue({...value, enabled_modules: e.target.checked ? [...value.enabled_modules, module] : value.enabled_modules.filter(m => m !== module)})} />{moduleNames[module]}</label>)}</div></fieldset>
      {error && <p role="alert" className="error">{error}</p>}{success && <p role="status" className="success">{success}</p>}<button className="button primary" disabled={pending}>{pending ? 'Saving…' : 'Save settings'}</button>
    </form><div className="local-note"><h2>Your personal Daybook</h2><p>These preferences belong to your account. Documents and the assistant are planned for a later phase.</p></div>
  </section>;
}

