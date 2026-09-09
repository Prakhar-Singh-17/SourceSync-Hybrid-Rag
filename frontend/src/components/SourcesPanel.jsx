import { useRef, useState } from "react";

import { clearSession, ingestDocument, ingestRepository } from "../api.js";

const LABEL = "text-xs font-medium uppercase tracking-[0.08em] text-zinc-400 dark:text-zinc-500";
const FIELD =
  "w-full rounded-lg border border-zinc-200 bg-white px-3.5 py-2.5 text-sm text-zinc-900 outline-none transition placeholder:text-zinc-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 disabled:opacity-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100 dark:placeholder:text-zinc-600 dark:focus:border-blue-400 dark:focus:ring-blue-400/10";
const SOLID_BUTTON =
  "rounded-lg bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-white dark:text-zinc-900 dark:hover:bg-zinc-200";

/** Adding sources to the session, and clearing them again. */
export default function SourcesPanel({ sources, passageCount, onIndexed, onCleared }) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const fileInput = useRef(null);

  async function run(kind, action) {
    setBusy(kind);
    setError(null);
    try {
      onIndexed(await action());
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

  async function handleClear() {
    setBusy("clear");
    setError(null);
    try {
      await clearSession();
      onCleared();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <section>
      <div className="flex items-baseline justify-between">
        <h2 className={LABEL}>Sources</h2>
        {passageCount > 0 && (
          <span className="font-mono text-xs text-zinc-400 dark:text-zinc-500">
            {passageCount} passages
          </span>
        )}
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <label
          className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed px-4 py-7 text-center transition ${
            busy === "document"
              ? "border-blue-500 bg-blue-500/5"
              : "border-zinc-300 hover:border-zinc-400 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:border-zinc-600 dark:hover:bg-zinc-900"
          }`}
        >
          <span className="text-sm font-medium">
            {busy === "document" ? "Indexing…" : "Upload a document"}
          </span>
          <span className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">
            PDF, TXT or Markdown · up to 15 MB
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

        <form
          onSubmit={handleRepository}
          className="flex flex-col justify-center rounded-xl border border-zinc-200 px-4 py-5 dark:border-zinc-800"
        >
          <label htmlFor="repository-url" className="text-sm font-medium">
            Index a repository
          </label>
          <input
            id="repository-url"
            type="url"
            required
            disabled={Boolean(busy)}
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="github.com/owner/repository"
            className={`${FIELD} mt-2.5`}
          />
          <button type="submit" disabled={Boolean(busy)} className={`${SOLID_BUTTON} mt-2.5`}>
            {busy === "repository" ? "Indexing…" : "Index"}
          </button>
        </form>
      </div>

      {error && (
        <p className="mt-4 rounded-lg bg-red-50 px-3.5 py-2.5 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300">
          {error}
        </p>
      )}

      {sources.length > 0 && (
        <div className="mt-6">
          <ul className="divide-y divide-zinc-100 border-y border-zinc-100 dark:divide-zinc-800/70 dark:border-zinc-800/70">
            {sources.map((source) => (
              <li key={source.key} className="flex items-baseline gap-3 py-2.5 text-sm">
                <span className="truncate">{source.source_name}</span>
                <span className="ml-auto shrink-0 font-mono text-xs text-zinc-400 dark:text-zinc-500">
                  {source.file_count ? `${source.file_count} files · ` : ""}
                  {source.passage_count} passages
                </span>
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={handleClear}
            disabled={Boolean(busy)}
            className="mt-3 text-xs text-zinc-400 underline decoration-zinc-200 underline-offset-4 transition hover:text-red-600 disabled:opacity-50 dark:text-zinc-500 dark:decoration-zinc-700 dark:hover:text-red-400"
          >
            {busy === "clear" ? "Clearing…" : "Clear all sources"}
          </button>
        </div>
      )}
    </section>
  );
}
