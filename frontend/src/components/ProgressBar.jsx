/**
 * An indeterminate progress bar for work whose duration is not known upfront.
 *
 * Deliberately indeterminate rather than a fake percentage: indexing time
 * depends on how many passages a source turns into and how the embedding API
 * responds, neither of which the browser can predict. A bar that crept to 90%
 * and stalled would be worse than one that plainly says "still working".
 */
export default function ProgressBar({ label, hint }) {
  return (
    <div className="mt-4" role="status" aria-live="polite">
      <div className="h-1 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
        <div className="h-full w-2/5 rounded-full bg-indigo-500 animate-indeterminate dark:bg-indigo-400" />
      </div>
      {label && (
        <p className="mt-2.5 text-xs text-slate-600 dark:text-slate-300">
          {label}
          <span className="animate-pulse">…</span>
        </p>
      )}
      {hint && <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">{hint}</p>}
    </div>
  );
}
