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
  // Whether the session has been read at least once. Without this, "no sources
  // yet" and "we have not asked yet" look identical, and the app renders the
  // empty state for the second before the first response lands, then jumps to
  // the workspace. Unknown is its own state, not a zero.
  const [loaded, setLoaded] = useState(false);

  const applySession = useCallback((session) => {
    setIndexed({
      passageCount: session.passage_count ?? 0,
      sources: session.sources ?? [],
    });
    setLoaded(true);
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

  const toggleEntry = useCallback((id) => {
    setHistory((current) =>
      current.map((entry) =>
        entry.id === id ? { ...entry, collapsed: !entry.collapsed } : entry,
      ),
    );
  }, []);

  async function handleAsk(question) {
    const id = Date.now();
    const patch = (changes) =>
      setHistory((current) =>
        current.map((entry) => (entry.id === id ? { ...entry, ...changes } : entry)),
      );

    setBusy(true);
    setHistory((current) => [
      { id, question, streaming: true, stage: "embedding", answer: "", citations: [], collapsed: false },
      // Asking a new question folds the previous answers away, so a long
      // session stays readable. They are one click from reopening.
      ...current.map((entry) => ({ ...entry, collapsed: true })),
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
    <div className="min-h-screen bg-white font-sans text-slate-900 antialiased dark:bg-slate-950 dark:text-slate-100">
      {/* Sticky so the connection state stays visible while reading long answers.
          The translucent background plus blur keeps content legible underneath. */}
      <nav className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur-md dark:border-slate-800 dark:bg-slate-950/80">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3.5">
          <div className="flex items-center gap-2.5">
            <img src="/logo.png" alt="" className="h-7 w-7 rounded-md" />
            <span className="text-base font-semibold tracking-tight">SourceSync</span>
          </div>
          <StatusDot status={status} message={statusMessage} onRetry={connect} />
        </div>
      </nav>

      <div className="mx-auto max-w-5xl px-6 py-12 sm:py-16">
        {!loaded ? (
          <FirstLoad status={status} message={statusMessage} onRetry={connect} />
        ) : !hasSources ? (
          <>
            <header className="text-center">
              <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
                Ask your sources.
              </h1>
              <p className="mx-auto mt-4 max-w-lg text-[15px] leading-7 text-slate-500 dark:text-slate-400">
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
            <AskPanel
              history={history}
              busy={busy}
              onAsk={handleAsk}
              onToggle={toggleEntry}
            />
          </main>
        )}

        <footer className="mt-24 border-t border-slate-200 pt-8 text-[13px] leading-6 text-slate-400 dark:border-slate-800 dark:text-slate-500">
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

/** Shown until the first session response decides which layout is correct. */
function FirstLoad({ status, message, onRetry }) {
  if (status === "error") {
    return (
      <div className="py-24 text-center">
        <p className="text-sm text-slate-500 dark:text-slate-400">{message}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 dark:bg-indigo-500 dark:hover:bg-indigo-400"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="py-24" role="status" aria-live="polite">
      <div className="mx-auto max-w-sm animate-pulse space-y-3">
        <div className="h-2.5 w-2/3 rounded-full bg-slate-100 dark:bg-slate-900" />
        <div className="h-2.5 w-full rounded-full bg-slate-100 dark:bg-slate-900" />
        <div className="h-2.5 w-1/2 rounded-full bg-slate-100 dark:bg-slate-900" />
      </div>
      <p className="mt-6 text-center text-xs text-slate-400 dark:text-slate-500">
        {status === "connecting" && message === "Waking the server"
          ? "Waking the server — this can take up to a minute"
          : "Loading your session"}
      </p>
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
    <span className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
      <span
        className={`h-1.5 w-1.5 rounded-full ${dot} ${status === "connecting" ? "animate-pulse" : ""}`}
      />
      {status === "error" ? (
        <button
          type="button"
          onClick={onRetry}
          title={message}
          className="underline decoration-slate-300 underline-offset-4 transition hover:text-slate-900 dark:decoration-slate-700 dark:hover:text-slate-100"
        >
          Offline — retry
        </button>
      ) : (
        <span>{message}</span>
      )}
    </span>
  );
}
