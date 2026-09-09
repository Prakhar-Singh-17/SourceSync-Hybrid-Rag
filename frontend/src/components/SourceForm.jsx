import { useRef, useState } from "react";

import { ingestDocument, ingestRepository } from "../api.js";
import ProgressBar from "./ProgressBar.jsx";

/**
 * Adding a source, in two sizes.
 *
 * The same two affordances appear in the empty state and in the sidebar, so
 * they live in one component rather than being written twice and drifting.
 * `variant="hero"` is the roomy first-run version; `"panel"` is the compact
 * one that sits in the rail afterwards.
 */
export default function SourceForm({ variant = "panel", onIndexed, connecting = false }) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const fileInput = useRef(null);

  const hero = variant === "hero";

  async function run(kind, action) {
    setBusy(kind);
    setError(null);
    try {
      await action();
      await onIndexed();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(null);
    }
  }

  async function handleFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    await run("document", () => ingestDocument(file));
    if (fileInput.current) fileInput.current.value = "";
  }

  async function handleRepository(event) {
    event.preventDefault();
    await run("repository", () => ingestRepository(url));
    setUrl("");
  }

  return (
    <div>
      <label
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed text-center transition ${
          hero ? "px-4 py-8" : "px-3 py-5"
        } ${
          busy === "document"
            ? "border-indigo-500 bg-indigo-500/5"
            : "border-slate-300 hover:border-slate-400 hover:bg-slate-50 dark:border-slate-700 dark:hover:border-slate-600 dark:hover:bg-slate-900"
        }`}
      >
        <span className={hero ? "text-sm font-medium" : "text-[13px] font-medium"}>
          {busy === "document" ? (connecting ? "Waking the server…" : "Indexing…") : "Upload a document"}
        </span>
        <span className="mt-1 text-xs text-slate-400 dark:text-slate-500">
          {hero ? "PDF, TXT or Markdown · up to 15 MB" : "PDF, TXT or MD"}
        </span>
        <input
          ref={fileInput}
          className="sr-only"
          type="file"
          accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
          disabled={Boolean(busy)}
          onChange={handleFile}
        />
      </label>

      <div className="my-3 flex items-center gap-3">
        <span className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
        <span className="text-[11px] uppercase tracking-wide text-slate-400 dark:text-slate-500">
          or
        </span>
        <span className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
      </div>

      <form onSubmit={handleRepository}>
        <input
          type="url"
          required
          disabled={Boolean(busy)}
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="github.com/owner/repository"
          aria-label="Public GitHub repository URL"
          className={`w-full rounded-lg border border-slate-200 bg-white text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-600 dark:focus:border-indigo-400 dark:focus:ring-indigo-400/10 ${
            hero ? "px-3.5 py-2.5 text-sm" : "px-3 py-2 text-[13px]"
          }`}
        />
        <button
          type="submit"
          disabled={Boolean(busy) || url.trim().length === 0}
          className={`mt-2 w-full rounded-lg bg-indigo-600 font-medium text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-indigo-500 dark:hover:bg-indigo-400 ${
            hero ? "py-2.5 text-sm" : "py-2 text-[13px]"
          }`}
        >
          {busy === "repository" ? (connecting ? "Waking the server…" : "Indexing…") : "Index repository"}
        </button>
      </form>

      {error && (
        <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-[13px] leading-5 text-red-700 dark:bg-red-500/10 dark:text-red-300">
          {error}
        </p>
      )}

      {busy && (
        <ProgressBar
          label={
            connecting
              ? "Waiting for the server to wake up"
              : busy === "document"
                ? "Extracting text and embedding passages"
                : "Downloading, filtering and embedding files"
          }
          hint={
            connecting
              ? "Your source will be indexed as soon as it responds."
              : busy === "repository"
                ? "Large repositories can take a minute."
                : null
          }
        />
      )}
    </div>
  );
}
