import type { CategoryLine } from '../../shared/api/contracts';

/** Eight categorical slots are validated; past that, the smallest categories fold into "Other". */
const MAX_SLOTS = 8;

export interface SplitPart { key: string; name: string; amount: number; share: number; color: string }

export function splitParts(lines: CategoryLine[]): SplitPart[] {
  const spent = lines.map(l => ({ key: l.category_id, name: l.category, amount: Number(l.spent) })).filter(p => p.amount > 0);
  const total = spent.reduce((sum, p) => sum + p.amount, 0);
  if (!total) return [];
  let kept = spent;
  let other = 0;
  if (spent.length > MAX_SLOTS) {
    const bySize = [...spent].sort((a, b) => b.amount - a.amount);
    kept = bySize.slice(0, MAX_SLOTS - 1);
    other = bySize.slice(MAX_SLOTS - 1).reduce((sum, p) => sum + p.amount, 0);
  }
  // A fixed (alphabetical) order keeps each category's colour and position stable as amounts change.
  const ordered = [...kept].sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));
  const parts = ordered.map((p, i) => ({ ...p, share: p.amount / total, color: `var(--series-${i + 1})` }));
  if (other) parts.push({ key: 'other', name: 'Other', amount: other, share: other / total, color: 'var(--series-other)' });
  return parts;
}

export function shareLabel(share: number) {
  if (share > 0 && share < 0.01) return '<1%';
  return Math.round(share * 100) + '%';
}
