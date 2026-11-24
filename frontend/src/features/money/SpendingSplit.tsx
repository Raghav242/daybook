import { useState } from 'react';
import type { CategoryLine } from '../../shared/api/contracts';
import { money } from '../../shared/domain';
import { shareLabel, splitParts, type SplitPart } from './split';

export function SpendingSplit({ lines, currency }: { lines: CategoryLine[]; currency: string }) {
  const [active, setActive] = useState<string>();
  const parts = splitParts(lines);
  if (!parts.length) return null;
  const describe = (p: SplitPart) => `${p.name}: ${money(String(p.amount), currency)}, ${shareLabel(p.share)}`;
  return <section aria-labelledby="split-title" className="split">
    <div className="section-head"><h2 id="split-title" className="section-title">Where it went</h2></div>
    <div className="split-bar" role="img" aria-label={'Spending by category: ' + parts.map(describe).join('; ')} onMouseLeave={() => setActive(undefined)}>
      {parts.map(p => <span key={p.key} title={describe(p)} className={active && active !== p.key ? 'dim' : ''} style={{ flexGrow: p.amount, background: p.color }} onMouseEnter={() => setActive(p.key)} />)}
    </div>
    <ul className="split-legend" onMouseLeave={() => setActive(undefined)}>
      {parts.map(p => <li key={p.key} className={active === p.key ? 'active' : ''} onMouseEnter={() => setActive(p.key)}>
        <span className="split-swatch" style={{ background: p.color }} aria-hidden="true" />
        <span className="split-name">{p.name}</span>
        <span className="split-amount">{money(String(p.amount), currency)}</span>
        <span className="split-share">{shareLabel(p.share)}</span>
      </li>)}
    </ul>
  </section>;
}
