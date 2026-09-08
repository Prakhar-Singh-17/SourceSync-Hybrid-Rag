import { useEffect } from "react";

import { ensureSession } from "./api.js";
import HealthChecks from "./components/HealthChecks.jsx";
import IngestionPanel from "./components/IngestionPanel.jsx";
import QueryPanel from "./components/QueryPanel.jsx";

export default function App() {
  useEffect(() => {
    void ensureSession();
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 font-serif px-6 py-16 text-slate-100 sm:px-10">
      <div className="mx-auto max-w-4xl">
        <section className="max-w-2xl">
          <p className="text-sm font-bold uppercase tracking-[0.2em] text-emerald-300">Hybrid retrieval for code and documents</p>
          <h1 className="mt-5 text-6xl font-black tracking-tight text-white sm:text-8xl">SourceSync</h1>
          <p className="mt-6 max-w-xl text-lg leading-8 text-slate-300">Ask grounded questions about uploaded English documents and public GitHub repositories.</p>
        </section>
        <HealthChecks />
        <IngestionPanel />
        <QueryPanel />
      </div>
    </main>
  );
}
