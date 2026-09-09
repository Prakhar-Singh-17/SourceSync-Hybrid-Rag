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
export default function Sidebar({ sources, passageCount, onChanged }) {
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
        <h2 className="text-xs font-medium uppercase tracking-[0.08em] text-zinc-400 dark:text-zinc-500">
          Sources
        </h2>
        <span className="font-mono text-xs text-zinc-400 dark:text-zinc-500">
          {passageCount} passages
        </span>
      </div>

      <ul className="mt-4 space-y-px">
        {sources.map((source) => (
          <li
            key={source.name}
            className="flex items-baseline gap-2 rounded-lg py-1.5 text-[13px]"
          >
            <span className="truncate" title={source.name}>
              {source.name}
            </span>
            <span className="ml-auto shrink-0 font-mono text-[11px] text-zinc-400 dark:text-zinc-500">
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
          className="w-full rounded-lg border border-zinc-200 py-2 text-[13px] font-medium text-zinc-600 transition hover:border-zinc-300 hover:text-zinc-900 lg:hidden dark:border-zinc-800 dark:text-zinc-400 dark:hover:border-zinc-700 dark:hover:text-zinc-100"
        >
          {open ? "Done" : "Add another source"}
        </button>
        <div className={`${open ? "mt-3 block" : "hidden"} lg:mt-0 lg:block`}>
          <SourceForm variant="panel" onIndexed={onChanged} />
        </div>
      </div>

      <button
        type="button"
        onClick={handleClear}
        disabled={clearing}
        className="mt-4 text-xs text-zinc-400 underline decoration-zinc-200 underline-offset-4 transition hover:text-red-600 disabled:opacity-50 dark:text-zinc-500 dark:decoration-zinc-700 dark:hover:text-red-400"
      >
        {clearing ? "Clearing…" : "Clear all sources"}
      </button>
    </aside>
  );
}
