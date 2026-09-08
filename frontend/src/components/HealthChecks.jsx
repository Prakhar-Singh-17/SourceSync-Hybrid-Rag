import { useState } from "react";

import { getApiHealth, getQdrantHealth } from "../api.js";

const buttonClasses = "rounded-md bg-emerald-300 px-4 py-2.5 font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-wait disabled:opacity-60";
const rowClasses = "flex flex-col gap-3 border-t border-slate-700 pt-4 sm:flex-row sm:items-center sm:justify-between";

export default function HealthChecks() {
  const [apiStatus, setApiStatus] = useState("Not checked");
  const [qdrantStatus, setQdrantStatus] = useState("Not checked");
  const [checkingApi, setCheckingApi] = useState(false);
  const [checkingQdrant, setCheckingQdrant] = useState(false);

  async function checkApi() {
    setCheckingApi(true);
    setApiStatus("Checking...");
    try {
      const result = await getApiHealth();
      setApiStatus(`Connected (${result.service})`);
    } catch (error) {
      setApiStatus(error.message);
    } finally {
      setCheckingApi(false);
    }
  }

  async function checkQdrant() {
    setCheckingQdrant(true);
    setQdrantStatus("Checking...");
    try {
      const result = await getQdrantHealth();
      setQdrantStatus(`Connected (${result.service})`);
    } catch (error) {
      setQdrantStatus(error.message);
    } finally {
      setCheckingQdrant(false);
    }
  }

  return (
    <section className="mt-16 rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl shadow-slate-950/40 sm:p-8" aria-labelledby="foundation-heading">
      <h2 id="foundation-heading" className="text-2xl font-bold text-white">Phase 1: Foundation</h2>
      <p className="mt-3 max-w-2xl leading-7 text-slate-300">Verify that the browser can reach FastAPI and FastAPI can reach Qdrant before ingesting content.</p>
      <div className="mt-8 space-y-4">
        <div className={rowClasses}>
          <button className={buttonClasses} disabled={checkingApi} onClick={checkApi}>{checkingApi ? "Checking..." : "Check API"}</button>
          <output className="break-words text-slate-300 sm:text-right">{apiStatus}</output>
        </div>
        <div className={rowClasses}>
          <button className={buttonClasses} disabled={checkingQdrant} onClick={checkQdrant}>{checkingQdrant ? "Checking..." : "Check Qdrant"}</button>
          <output className="break-words text-slate-300 sm:text-right">{qdrantStatus}</output>
        </div>
      </div>
    </section>
  );
}
