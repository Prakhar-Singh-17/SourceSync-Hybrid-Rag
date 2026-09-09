import SourceForm from "./SourceForm.jsx";

/**
 * The first-run screen.
 *
 * Before anything is indexed there is exactly one useful action, so the page
 * shows only that. The previous layout put a disabled question box on screen
 * from the start, which invited people to type into a control that could not
 * respond.
 */
export default function EmptyState({ onIndexed }) {
  return (
    <div className="mx-auto max-w-md py-6 text-center">
      <h2 className="text-xl font-medium tracking-tight">Add your first source</h2>
      <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-slate-500 dark:text-slate-400">
        Upload a document or point at a public GitHub repository. Questions are answered only from
        what you index here.
      </p>

      <div className="mt-8 text-left">
        <SourceForm variant="hero" onIndexed={onIndexed} />
      </div>

      <p className="mt-8 text-xs leading-5 text-slate-400 dark:text-slate-500">
        Nothing is stored against an account. Your session and everything in it expires after 60
        minutes.
      </p>
    </div>
  );
}
