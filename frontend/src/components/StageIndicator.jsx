const STAGES = [
  ["embedding", "Embedding"],
  ["searching", "Searching"],
  ["reranking", "Reranking"],
  ["writing", "Writing"],
];

/**
 * Where the pipeline has got to, driven by real events from the server.
 *
 * Every step here corresponds to a stage the backend actually announces as it
 * begins, so the progress is observed rather than animated on a timer. A
 * decorative version would be misleading exactly when it matters most, which is
 * when something is unusually slow.
 */
export default function StageIndicator({ stage }) {
  const current = Math.max(
    0,
    STAGES.findIndex(([key]) => key === stage),
  );

  return (
    <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-2">
      {STAGES.map(([key, label], index) => {
        const done = index < current;
        const active = index === current;
        return (
          <li key={key} className="flex items-center gap-1.5">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                active
                  ? "animate-pulse bg-indigo-500 dark:bg-indigo-400"
                  : done
                    ? "bg-slate-400 dark:bg-slate-500"
                    : "bg-slate-200 dark:bg-slate-800"
              }`}
            />
            <span
              className={`text-xs ${
                active
                  ? "text-slate-900 dark:text-slate-100"
                  : done
                    ? "text-slate-400 dark:text-slate-500"
                    : "text-slate-300 dark:text-slate-700"
              }`}
            >
              {label}
            </span>
            {index < STAGES.length - 1 && (
              <span
                className={`ml-0.5 h-px w-4 ${
                  done ? "bg-slate-300 dark:bg-slate-700" : "bg-slate-200 dark:bg-slate-800"
                }`}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
