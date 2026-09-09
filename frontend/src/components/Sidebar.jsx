import { useState } from "react";

import { clearSession } from "../api.js";
import SourceForm from "./SourceForm.jsx";

/**
 * The left rail: what is indexed, and how to add more.
 *
 * Kept visible beside the answers so it is always clear what a question is
 * being asked against. On narrow screens it stacks above the conversation and
 * collapses to a summary line, since a sidebar that eats half a phone screen
 * is worse than no sidebar.
 */
export default function Sidebar({ sources, passageCount, onChanged, loading = false, connecting = false }) {
  const [open, setOpen] = useState(false);
  const [clearing, setClearing] = useState(false);

  async function handleClear() {
    setClearing(true);
    try {
      await clearSession();
      await onChanged();
    } finally {
      setClearing(false);
    }
  }

  return (
    <aside className="lg:sticky lg:top-24 lg:self-start">
      <div className="flex items-baseline justify-between">
        <h2 className="text-xs font-medium uppercase tracking-[0.08em] text-slate-400 dark:text-slate-500">
          Sources
        </h2>
        {!loading && (
          <span className="font-mono text-xs text-slate-400 dark:text-slate-500">
            {passageCount} passages
          </span>
        )}
      </div>

      {loading && (
        <ul className="mt-4 space-y-2.5" aria-hidden="true">
          <li className="h-3 w-3/4 animate-pulse rounded-full bg-slate-100 dark:bg-slate-900" />
          <li className="h-3 w-1/2 animate-pulse rounded-full bg-slate-100 dark:bg-slate-900" />
        </ul>
      )}

      <ul className="mt-4 space-y-px">
        {sources.map((source) => (
          <li
            key={source.name}
            className="flex items-baseline gap-2 rounded-lg py-1.5 text-[13px]"
          >
            <span className="truncate" title={source.name}>
              {source.name}
            </span>
            <span className="ml-auto shrink-0 font-mono text-[11px] text-slate-400 dark:text-slate-500">
              {source.passage_count}
            </span>
          </li>
        ))}
      </ul>

      {/* The form is always available on desktop, and behind a toggle on mobile
          so the conversation stays the first thing on screen. */}
      <div className="mt-4">
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="w-full rounded-lg border border-slate-200 py-2 text-[13px] font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-900 lg:hidden dark:border-slate-800 dark:text-slate-400 dark:hover:border-slate-700 dark:hover:text-slate-100"
        >
          {open ? "Done" : "Add another source"}
        </button>
        <div className={`${open ? "mt-3 block" : "hidden"} lg:mt-0 lg:block`}>
          <SourceForm variant="panel" onIndexed={onChanged} connecting={connecting} />
        </div>
      </div>

      <button
        type="button"
        onClick={handleClear}
        disabled={clearing}
        className="mt-4 text-xs text-slate-400 underline decoration-slate-200 underline-offset-4 transition hover:text-red-600 disabled:opacity-50 dark:text-slate-500 dark:decoration-slate-700 dark:hover:text-red-400"
      >
        {clearing ? "Clearing…" : "Clear all sources"}
      </button>
    </aside>
  );
}
