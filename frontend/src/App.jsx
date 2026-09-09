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
  const [statusMessage, setStatusMessage] = useState("Connecting");
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
        setStatusMessage("Connected");
        return;
      } catch (error) {
        if (attempt === CONNECT_ATTEMPTS) {
          setStatus("error");
          setStatusMessage(error.message);
          return;
        }
        setStatusMessage("Waking the server");
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
    <div className="min-h-screen bg-white font-sans text-zinc-900 antialiased dark:bg-zinc-950 dark:text-zinc-100">
      {/* Sticky so the connection state stays visible while reading long answers.
          The translucent background plus blur keeps content legible underneath. */}
      <nav className="sticky top-0 z-10 border-b border-zinc-200 bg-white/80 backdrop-blur-md dark:border-zinc-800 dark:bg-zinc-950/80">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-3.5">
          <div className="flex items-center gap-2.5">
            {/* Swap in your own logo: replace public/logo.svg, or point src at a
                new file. alt stays empty on purpose -- the wordmark beside it
                already names the site, so a screen reader would otherwise
                announce it twice. */}
            <img src="/logo.svg" alt="" className="h-7 w-7 rounded-md" />
            <span className="text-base font-semibold tracking-tight">SourceSync</span>
          </div>
          <StatusDot status={status} message={statusMessage} onRetry={connect} />
        </div>
      </nav>

      <div className="mx-auto max-w-3xl px-6 py-14 sm:py-20">
        <header>
          <h1 className="text-5xl font-semibold tracking-tight sm:text-6xl">Ask your sources.</h1>
          <p className="mt-5 max-w-lg text-[15px] leading-7 text-zinc-500 dark:text-zinc-400">
            Index your own documents or any public GitHub repository, then ask questions about
            them. Every answer is built only from what you indexed, and each claim cites the
            passage it came from.
          </p>
        </header>

        <main className="mt-16 space-y-16">
          <SourcesPanel
            sources={sources}
            passageCount={passageCount}
            onIndexed={handleIndexed}
            onCleared={handleCleared}
          />
          <AskPanel history={history} busy={busy} hasSources={passageCount > 0} onAsk={handleAsk} />
        </main>

        <footer className="mt-24 border-t border-zinc-200 pt-8 text-[13px] leading-6 text-zinc-400 dark:border-zinc-800 dark:text-zinc-500">
          <p className="max-w-xl">
            Each question runs a semantic search and a keyword search at once, merges the two
            rankings with reciprocal rank fusion, reranks what survives, and answers only from
            those passages.
          </p>
          <p className="mt-2">Sessions are anonymous and expire after 60 minutes.</p>
        </footer>
      </div>
    </div>
  );
}

function StatusDot({ status, message, onRetry }) {
  const dot = {
    connecting: "bg-amber-500",
    ready: "bg-emerald-500",
    error: "bg-red-500",
  }[status];

  return (
    <span className="flex items-center gap-2 text-xs text-zinc-400 dark:text-zinc-500">
      <span
        className={`h-1.5 w-1.5 rounded-full ${dot} ${status === "connecting" ? "animate-pulse" : ""}`}
      />
      {status === "error" ? (
        <button
          type="button"
          onClick={onRetry}
          title={message}
          className="underline decoration-zinc-300 underline-offset-4 transition hover:text-zinc-900 dark:decoration-zinc-700 dark:hover:text-zinc-100"
        >
          Offline — retry
        </button>
      ) : (
        <span>{message}</span>
      )}
    </span>
  );
}
