import { BookOpen } from 'lucide-react';

/** Documents are not implemented yet; this page says so plainly instead of imitating them. */
export default function LibraryView() {
  return <section aria-labelledby="view-title">
    <header className="page-head"><h1 id="view-title" className="page-title">Library</h1></header>
    <div className="empty library-empty">
      <BookOpen size={28} strokeWidth={1.4} aria-hidden="true" />
      <h2>Nothing here yet</h2>
      <p>The Library will hold your documents and notes. It isn’t available in this version of Daybook, so there is nothing to upload or search yet.</p>
    </div>
  </section>;
}
