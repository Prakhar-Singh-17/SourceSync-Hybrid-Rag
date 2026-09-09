import { useRef, useState } from "react";

import { clearSession, ingestDocument, ingestRepository } from "../api.js";

const BUTTON =
  "rounded-lg bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-50";

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
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold text-slate-100">Sources</h2>
        {passageCount > 0 && (
          <span className="text-xs text-slate-500">
            {passageCount} passage{passageCount === 1 ? "" : "s"} indexed
          </span>
        )}
      </div>

      <div className="mt-5 grid gap-5 md:grid-cols-2">
        <div>
          <label
            className={`flex h-full min-h-24 cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed px-4 py-5 text-center transition ${
              busy === "document"
                ? "border-emerald-400/60 bg-emerald-400/5"
                : "border-slate-700 hover:border-emerald-400/60 hover:bg-slate-800/40"
            }`}
          >
            <span className="text-sm font-semibold text-emerald-300">
              {busy === "document" ? "Indexing document..." : "Upload a document"}
            </span>
            <span className="mt-1 text-xs text-slate-500">PDF, TXT or Markdown, up to 15 MB</span>
            <input
              ref={fileInput}
              className="sr-only"
              type="file"
              accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
              disabled={Boolean(busy)}
              onChange={handleFile}
            />
          </label>
        </div>

        <form onSubmit={handleRepository} className="flex flex-col">
          <label htmlFor="repository-url" className="text-xs font-medium text-slate-400">
            Public GitHub repository
          </label>
          <input
            id="repository-url"
            type="url"
            required
            disabled={Boolean(busy)}
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://github.com/owner/repository"
            className="mt-1.5 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-emerald-400"
          />
          <button type="submit" disabled={Boolean(busy)} className={`${BUTTON} mt-2.5 self-start`}>
            {busy === "repository" ? "Indexing repository..." : "Index repository"}
          </button>
        </form>
      </div>

      {error && (
        <p className="mt-4 rounded-lg border border-rose-900/60 bg-rose-950/40 px-3 py-2 text-sm text-rose-200">
          {error}
        </p>
      )}

      {sources.length > 0 && (
        <div className="mt-5 border-t border-slate-800 pt-4">
          <ul className="space-y-1.5">
            {sources.map((source) => (
              <li key={source.key} className="flex items-baseline gap-2 text-sm">
                <span className="text-emerald-400">+</span>
                <span className="break-all text-slate-200">{source.source_name}</span>
                <span className="ml-auto shrink-0 text-xs text-slate-500">
                  {source.file_count ? `${source.file_count} files, ` : ""}
                  {source.passage_count} passages
                </span>
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={handleClear}
            disabled={Boolean(busy)}
            className="mt-4 text-xs text-slate-500 underline-offset-4 transition hover:text-rose-300 hover:underline disabled:opacity-50"
          >
            {busy === "clear" ? "Clearing..." : "Clear all sources"}
          </button>
        </div>
      )}
    </section>
  );
}
