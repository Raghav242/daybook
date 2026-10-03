import { RecordsView } from '../../shared/ui/RecordsView';
import type { ComponentProps } from 'react';
export default function TasksView(props: Omit<ComponentProps<typeof RecordsView>, 'module'>) {
  return <RecordsView {...props} module="tasks" />;
}

