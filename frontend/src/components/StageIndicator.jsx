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
                  ? "animate-pulse bg-blue-500 dark:bg-blue-400"
                  : done
                    ? "bg-zinc-400 dark:bg-zinc-500"
                    : "bg-zinc-200 dark:bg-zinc-800"
              }`}
            />
            <span
              className={`text-xs ${
                active
                  ? "text-zinc-900 dark:text-zinc-100"
                  : done
                    ? "text-zinc-400 dark:text-zinc-500"
                    : "text-zinc-300 dark:text-zinc-700"
              }`}
            >
              {label}
            </span>
            {index < STAGES.length - 1 && (
              <span
                className={`ml-0.5 h-px w-4 ${
                  done ? "bg-zinc-300 dark:bg-zinc-700" : "bg-zinc-200 dark:bg-zinc-800"
                }`}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
