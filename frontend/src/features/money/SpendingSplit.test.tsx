import { render, screen, within } from '@testing-library/react';
import type { CategoryLine } from '../../shared/api/contracts';
import { SpendingSplit } from './SpendingSplit';
import { shareLabel, splitParts } from './split';

const line = (name: string, spent: string): CategoryLine => ({ category_id: name.toLowerCase(), category: name, currency: 'USD', budget_id: null, budgeted: null, spent, remaining: null });

test('the split lists each category with its amount and share, in a stable alphabetical order', () => {
  render(<SpendingSplit lines={[line('Groceries', '30.00'), line('Dining', '70.00'), line('Unused', '0.00')]} currency="USD" />);
  const items = within(screen.getByRole('list')).getAllByRole('listitem');
  expect(items.map(i => i.textContent)).toEqual(['Dining$70.0070%', 'Groceries$30.0030%']);
  expect(screen.getByRole('img', { name: 'Spending by category: Dining: $70.00, 70%; Groceries: $30.00, 30%' })).toBeInTheDocument();
});

test('nothing renders when nothing was spent', () => {
  const { container } = render(<SpendingSplit lines={[line('Dining', '0.00')]} currency="USD" />);
  expect(container).toBeEmptyDOMElement();
});

test('past eight categories, the smallest fold into Other', () => {
  const lines = 'ABCDEFGHIJ'.split('').map((c, i) => line(c, String(10 - i)));
  const parts = splitParts(lines);
  expect(parts).toHaveLength(8);
  expect(parts.at(-1)).toMatchObject({ name: 'Other', amount: 6 });
  expect(shareLabel(0.004)).toBe('<1%');
});
