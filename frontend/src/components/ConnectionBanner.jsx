/**
 * A slim strip under the navbar while the session is being established.
 *
 * The page no longer waits for the session before rendering, so this is what
 * tells the visitor that something is still happening — without taking the
 * interface away from them. It reuses the same indeterminate sweep as the
 * indexing bar so the two read as one system.
 */
export default function ConnectionBanner({ status, message, onRetry }) {
  const failed = status === "error";

  return (
    <div
      role="status"
      aria-live="polite"
      className="border-b border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-900/60"
    >
      {!failed && (
        <div className="h-0.5 w-full overflow-hidden bg-slate-200 dark:bg-slate-800">
          <div className="h-full w-1/3 rounded-full bg-indigo-500 animate-indeterminate dark:bg-indigo-400" />
        </div>
      )}

      <div className="mx-auto flex max-w-5xl items-center gap-2 px-6 py-2 text-xs">
        {failed ? (
          <>
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-red-500" />
            <span className="text-slate-600 dark:text-slate-300">{message}</span>
            <button
              type="button"
              onClick={onRetry}
              className="ml-auto shrink-0 font-medium text-indigo-600 underline-offset-4 transition hover:underline dark:text-indigo-400"
            >
              Retry
            </button>
          </>
        ) : (
          <span className="text-slate-500 dark:text-slate-400">
            {message === "Waking the server"
              ? "Waking the server — a free instance can take up to a minute. You can add a source in the meantime."
              : "Connecting to the server"}
            <span className="animate-pulse">…</span>
          </span>
        )}
      </div>
    </div>
  );
}
