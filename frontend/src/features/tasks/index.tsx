import { RecordsView, type ViewProps } from '../../shared/ui/RecordsView';

export default function View(props: ViewProps) {
  return <RecordsView {...props} module="tasks" />;
}
