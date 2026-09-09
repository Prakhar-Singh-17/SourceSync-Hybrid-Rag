import { useState } from "react";

import AnswerCard from "./AnswerCard.jsx";

const EXAMPLES = [
  "What does this project do, and how is it structured?",
  "How is authentication handled?",
  "What are the main limitations?",
];

/** The question box and the running history of answers. */
export default function AskPanel({ history, busy, hasSources, onAsk }) {
  const [question, setQuestion] = useState("");

  function submit(event) {
    event.preventDefault();
    const trimmed = question.trim();
    if (trimmed.length < 3 || busy) return;
    onAsk(trimmed);
    setQuestion("");
  }

  return (
    <section className="mt-6">
      <form onSubmit={submit} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 sm:p-6">
        <label htmlFor="question" className="text-lg font-semibold text-slate-100">
          Ask a question
        </label>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row">
          <input
            id="question"
            type="text"
            value={question}
            disabled={!hasSources}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={
              hasSources ? "Ask anything about your sources..." : "Add a source above to begin"
            }
            className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-emerald-400 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={busy || !hasSources || question.trim().length < 3}
            className="rounded-lg bg-emerald-400 px-5 py-2.5 font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? "Thinking..." : "Ask"}
          </button>
        </div>

        {hasSources && history.length === 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => setQuestion(example)}
                className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-400 transition hover:border-emerald-400/60 hover:text-emerald-300"
              >
                {example}
              </button>
            ))}
          </div>
        )}
      </form>

      <div className="mt-6 space-y-4">
        {history.map((entry) => (
          <AnswerCard key={entry.id} entry={entry} />
        ))}
      </div>
    </section>
  );
}
