import { useCallback, useEffect, useState } from "react";

import { getSession, startSession, streamQuestion } from "./api.js";
import AskPanel from "./components/AskPanel.jsx";
import EmptyState from "./components/EmptyState.jsx";
import Sidebar from "./components/Sidebar.jsx";

// A free Render service sleeps after inactivity and takes the better part of a
// minute to wake. Retrying quietly turns "failed to fetch" on a cold start into
// a short wait with an explanation.
const CONNECT_ATTEMPTS = 4;
const RETRY_DELAY_MS = 4000;

export default function App() {
  const [status, setStatus] = useState("connecting");
  const [statusMessage, setStatusMessage] = useState("Connecting");
  const [indexed, setIndexed] = useState({ passageCount: 0, sources: [] });
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);

  const applySession = useCallback((session) => {
    setIndexed({
      passageCount: session.passage_count ?? 0,
      sources: session.sources ?? [],
    });
  }, []);

  const connect = useCallback(async () => {
    setStatus("connecting");
    for (let attempt = 1; attempt <= CONNECT_ATTEMPTS; attempt += 1) {
      try {
        applySession(await startSession());
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
  }, [applySession]);

  useEffect(() => {
    void connect();
  }, [connect]);

  // The server is the single source of truth for what is indexed, so every
  // change re-reads it rather than patching a local copy. That is what makes
  // the list correct after a page reload.
  const refresh = useCallback(async () => {
    applySession(await getSession());
  }, [applySession]);

  const handleCleared = useCallback(async () => {
    await refresh();
    setHistory([]);
  }, [refresh]);

  async function handleAsk(question) {
    const id = Date.now();
    const patch = (changes) =>
      setHistory((current) =>
        current.map((entry) => (entry.id === id ? { ...entry, ...changes } : entry)),
      );

    setBusy(true);
    setHistory((current) => [
      { id, question, streaming: true, stage: "embedding", answer: "", citations: [] },
      ...current,
    ]);

    try {
      await streamQuestion(question, (event) => {
        if (event.type === "stage") {
          patch({ stage: event.stage });
        } else if (event.type === "context") {
          patch({
            citations: event.citations,
            reranked: event.reranked,
            candidates_considered: event.candidates_considered,
            dense_hits: event.dense_hits,
            sparse_hits: event.sparse_hits,
          });
        } else if (event.type === "token") {
          // Appended through the updater so concurrent tokens cannot read a
          // stale answer and drop text.
          setHistory((current) =>
            current.map((entry) =>
              entry.id === id ? { ...entry, answer: entry.answer + event.text } : entry,
            ),
          );
        } else if (event.type === "done") {
          patch({ timings: event.timings, streaming: false });
        } else if (event.type === "error") {
          patch({ error: event.detail, streaming: false });
        }
      });
    } catch (error) {
      patch({ error: error.message });
    } finally {
      setBusy(false);
      patch({ streaming: false });
    }
  }

  const hasSources = indexed.passageCount > 0;

  return (
    <div className="min-h-screen bg-white font-sans text-zinc-900 antialiased dark:bg-zinc-950 dark:text-zinc-100">
      {/* Sticky so the connection state stays visible while reading long answers.
          The translucent background plus blur keeps content legible underneath. */}
      <nav className="sticky top-0 z-10 border-b border-zinc-200 bg-white/80 backdrop-blur-md dark:border-zinc-800 dark:bg-zinc-950/80">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3.5">
          <div className="flex items-center gap-2.5">
            <img src="/logo.png" alt="" className="h-7 w-7 rounded-md" />
            <span className="text-base font-semibold tracking-tight">SourceSync</span>
          </div>
          <StatusDot status={status} message={statusMessage} onRetry={connect} />
        </div>
      </nav>

      <div className="mx-auto max-w-5xl px-6 py-12 sm:py-16">
        {!hasSources ? (
          <>
            <header className="text-center">
              <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
                Ask your sources.
              </h1>
              <p className="mx-auto mt-4 max-w-lg text-[15px] leading-7 text-zinc-500 dark:text-zinc-400">
                Answers are built only from what you index, and every claim cites the passage it
                came from.
              </p>
            </header>
            <main className="mt-12">
              <EmptyState onIndexed={refresh} />
            </main>
          </>
        ) : (
          <main className="grid gap-10 lg:grid-cols-[240px_minmax(0,1fr)] lg:gap-14">
            <Sidebar
              sources={indexed.sources}
              passageCount={indexed.passageCount}
              onChanged={handleCleared}
            />
            <AskPanel history={history} busy={busy} onAsk={handleAsk} />
          </main>
        )}

        <footer className="mt-24 border-t border-zinc-200 pt-8 text-[13px] leading-6 text-zinc-400 dark:border-zinc-800 dark:text-zinc-500">
          <p className="max-w-xl">
            Each question runs a semantic search and a keyword search at once, merges the two
            rankings with reciprocal rank fusion, reranks what survives, and answers only from
            those passages.
          </p>
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
