import { useState } from 'react';
import { Dialog } from './Dialog';

/** Explicit confirmation for a destructive action; errors stay inside the dialog. */
export function ConfirmDialog({ title, body, action, onConfirm, onClose }: { title: string; body: string; action: string; onConfirm: () => Promise<void>; onClose: () => void }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  async function confirm() {
    if (pending) return;
    setPending(true); setError('');
    try { await onConfirm(); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not complete that.'); setPending(false); }
  }
  return <Dialog title={title} pending={pending} onClose={onClose}>
    <p className="delete-copy">{body}</p>
    {error && <p className="error" role="alert">{error}</p>}
    <div className="dialog-actions"><button className="button secondary" disabled={pending} onClick={onClose}>Cancel</button><button className="button danger" disabled={pending} onClick={confirm}>{pending ? 'Working…' : action}</button></div>
  </Dialog>;
}
