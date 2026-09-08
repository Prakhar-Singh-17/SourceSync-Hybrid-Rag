import { useState } from "react";

import { ingestDocument, ingestRepository } from "../api.js";

const buttonClasses = "rounded-md bg-emerald-300 px-4 py-2.5 font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-wait disabled:opacity-60";

export default function IngestionPanel() {
  const [documentStatus, setDocumentStatus] = useState("No document selected");
  const [indexingDocument, setIndexingDocument] = useState(false);
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [repositoryStatus, setRepositoryStatus] = useState("No repository selected");
  const [indexingRepository, setIndexingRepository] = useState(false);

  async function indexDocument(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setIndexingDocument(true);
    setDocumentStatus("Uploading and indexing...");
    try {
      const result = await ingestDocument(file);
      setDocumentStatus(`${result.filename} indexed: ${result.chunk_count} chunks`);
    } catch (error) {
      setDocumentStatus(error.message);
    } finally {
      setIndexingDocument(false);
    }
  }

  async function indexRepository(event) {
    event.preventDefault();
    setIndexingRepository(true);
    setRepositoryStatus("Downloading and indexing...");
    try {
      const result = await ingestRepository(repositoryUrl);
      setRepositoryStatus(`${result.repository} indexed: ${result.file_count} files, ${result.chunk_count} chunks`);
    } catch (error) {
      setRepositoryStatus(error.message);
    } finally {
      setIndexingRepository(false);
    }
  }

  return (
    <section className="mt-8 grid gap-8 rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl shadow-slate-950/40 sm:p-8 md:grid-cols-2">
      <div>
        <h2 className="text-2xl font-bold text-white">Add a document</h2>
        <p className="mt-3 leading-7 text-slate-300">PDF up to 25 MB and 150 pages, or UTF-8 TXT.</p>
        <label className="mt-6 block cursor-pointer rounded-md border border-dashed border-slate-600 px-4 py-5 text-center font-semibold text-emerald-300 transition hover:border-emerald-300">
          Choose and index PDF or TXT
          <input className="sr-only" disabled={indexingDocument} type="file" accept=".pdf,.txt,application/pdf,text/plain" onChange={indexDocument} />
        </label>
        {indexingDocument && <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-slate-700" aria-label="Document indexing in progress"><div className="h-full w-1/3 animate-pulse rounded-full bg-emerald-300" /></div>}
        <p className="mt-4 break-words text-sm text-slate-400" role="status">{documentStatus}</p>
      </div>
      <form onSubmit={indexRepository}>
        <h2 className="text-2xl font-bold text-white">Add a repository</h2>
        <p className="mt-3 leading-7 text-slate-300">Public GitHub repositories only.</p>
        <label className="mt-6 block text-sm font-semibold text-slate-300" htmlFor="repository-url">Repository URL</label>
        <input className="mt-2 w-full rounded-md border border-slate-600 bg-slate-950 px-3 py-2.5 text-slate-100 outline-none focus:border-emerald-300" id="repository-url" type="url" placeholder="https://github.com/owner/repository" value={repositoryUrl} onChange={(event) => setRepositoryUrl(event.target.value)} required />
        <button className={`${buttonClasses} mt-4`} disabled={indexingRepository} type="submit">{indexingRepository ? "Indexing..." : "Index repository"}</button>
        {indexingRepository && <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-slate-700" aria-label="Repository indexing in progress"><div className="h-full w-1/3 animate-pulse rounded-full bg-emerald-300" /></div>}
        <p className="mt-4 break-words text-sm text-slate-400" role="status">{repositoryStatus}</p>
      </form>
    </section>
  );
}
