import { useCallback, useEffect, useState } from "react";

import { askQuestion, startSession } from "./api.js";
import AskPanel from "./components/AskPanel.jsx";
import SourcesPanel from "./components/SourcesPanel.jsx";

// A free Render service sleeps after inactivity and takes the better part of a
// minute to wake. Retrying quietly turns "failed to fetch" on a cold start into
// a short wait with an explanation.
const CONNECT_ATTEMPTS = 4;
const RETRY_DELAY_MS = 4000;

export default function App() {
  const [status, setStatus] = useState("connecting");
  const [statusMessage, setStatusMessage] = useState("Connecting...");
  const [passageCount, setPassageCount] = useState(0);
  const [sources, setSources] = useState([]);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);

  const connect = useCallback(async () => {
    setStatus("connecting");
    for (let attempt = 1; attempt <= CONNECT_ATTEMPTS; attempt += 1) {
      try {
        const session = await startSession();
        setPassageCount(session.passage_count ?? 0);
        setStatus("ready");
        setStatusMessage("Session active");
        return;
      } catch (error) {
        if (attempt === CONNECT_ATTEMPTS) {
          setStatus("error");
          setStatusMessage(error.message);
          return;
        }
        setStatusMessage("Waking the server, this can take up to a minute...");
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
      }
    }
  }, []);

  useEffect(() => {
    void connect();
  }, [connect]);

  function handleIndexed(result) {
    setSources((current) => [...current, { ...result, key: `${result.source_name}-${Date.now()}` }]);
    setPassageCount(result.total_passages ?? 0);
  }

  function handleCleared() {
    setSources([]);
    setPassageCount(0);
    setHistory([]);
  }

  async function handleAsk(question) {
    const id = Date.now();
    setBusy(true);
    setHistory((current) => [{ id, question, pending: true, citations: [] }, ...current]);
    try {
      const result = await askQuestion(question);
      setHistory((current) =>
        current.map((entry) => (entry.id === id ? { id, question, ...result } : entry)),
      );
    } catch (error) {
      setHistory((current) =>
        current.map((entry) =>
          entry.id === id ? { id, question, error: error.message, citations: [] } : entry,
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-3xl px-5 py-12 sm:px-8 sm:py-16">
        <header>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">SourceSync</h1>
            <StatusPill status={status} message={statusMessage} onRetry={connect} />
          </div>
          <p className="mt-3 max-w-xl leading-7 text-slate-400">
            Ask questions about your own documents and public GitHub repositories. Answers are built
            only from what you index, and every claim links back to the passage it came from.
          </p>
        </header>

        <main className="mt-8">
          <SourcesPanel
            sources={sources}
            passageCount={passageCount}
            onIndexed={handleIndexed}
            onCleared={handleCleared}
          />
          <AskPanel
            history={history}
            busy={busy}
            hasSources={passageCount > 0}
            onAsk={handleAsk}
          />
        </main>

        <footer className="mt-14 border-t border-slate-800 pt-6 text-xs leading-6 text-slate-500">
          <p>
            Each question runs two searches at once — semantic (vector) and keyword (BM25) — merges
            them with reciprocal rank fusion, reranks the result with Gemini, and answers only from
            the passages that survive.
          </p>
          <p className="mt-2">
            Sessions are anonymous and expire after 60 minutes, along with everything indexed in them.
          </p>
        </footer>
      </div>
    </div>
  );
}

function StatusPill({ status, message, onRetry }) {
  const colour = {
    connecting: "bg-amber-400",
    ready: "bg-emerald-400",
    error: "bg-rose-500",
  }[status];

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border border-slate-800 bg-slate-900 px-2.5 py-1 text-xs text-slate-400"
      title={message}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${colour} ${status === "connecting" ? "animate-pulse" : ""}`} />
      {status === "error" ? (
        <button type="button" onClick={onRetry} className="hover:text-emerald-300">
          Offline — retry
        </button>
      ) : (
        <span>{status === "ready" ? "Connected" : "Connecting"}</span>
      )}
    </span>
  );
}
