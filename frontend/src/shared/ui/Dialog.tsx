import { useEffect, useRef, useState, type ReactNode } from 'react';
import { ChevronDown, X } from 'lucide-react';

/**
 * Modal dialog. On narrow screens the same element is styled as a bottom sheet: it scrolls
 * internally, its actions stay visible, and it respects safe-area insets.
 */
export function Dialog({ title, children, onClose, pending = false }: { title: string; children: ReactNode; onClose: () => void; pending?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    const previous = document.activeElement as HTMLElement | null;
    dialog.showModal();
    dialog.querySelector<HTMLElement>('[autofocus], input:not([type=hidden]):not([type=radio]), select, textarea')?.focus();
    return () => { dialog.close(); previous?.focus(); };
  }, []);
  // Escape closes (unless saving); tapping the backdrop does not, so typed input is never lost.
  return <dialog ref={ref} aria-labelledby="dialog-title" onCancel={e => { e.preventDefault(); if (!pending) onClose(); }}>
    <div className="dialog-body">
      <div className="dialog-heading"><h2 id="dialog-title">{title}</h2><button type="button" className="icon-button" aria-label="Close" disabled={pending} onClick={onClose}><X size={20} /></button></div>
      {children}
    </div>
  </dialog>;
}

/** Optional fields, hidden until asked for. Inputs stay mounted so their values are kept. */
export function MoreDetails({ open: initiallyOpen = false, locked = false, label = 'More details', children }: { open?: boolean; locked?: boolean; label?: string; children: ReactNode }) {
  const [open, setOpen] = useState(initiallyOpen);
  const shown = open || locked;
  return <div className="more-details">
    <button type="button" className="disclosure" aria-expanded={shown} disabled={locked} onClick={() => setOpen(o => !o)}><ChevronDown size={16} aria-hidden="true" />{label}</button>
    <div hidden={!shown} className="more-details-body">{children}</div>
  </div>;
}
