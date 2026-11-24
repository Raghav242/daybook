import type { FeatureModule, Module, TransactionKind } from '../../shared/api/contracts';

export type EntryKind = Module | TransactionKind;
const kinds: { kind: EntryKind; label: string; module: FeatureModule }[] = [
  { kind: 'tasks', label: 'Task', module: 'tasks' },
  { kind: 'calendar', label: 'Event', module: 'calendar' },
  { kind: 'groceries', label: 'Grocery', module: 'groceries' },
  { kind: 'expense', label: 'Expense', module: 'budget' },
  { kind: 'income', label: 'Income', module: 'budget' },
  { kind: 'bills', label: 'Bill', module: 'bills' },
];
export const entryKinds = (enabled: FeatureModule[]) => kinds.filter(k => enabled.includes(k.module));
