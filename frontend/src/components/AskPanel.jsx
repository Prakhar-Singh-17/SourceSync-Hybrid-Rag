import { useState } from "react";

import AnswerCard from "./AnswerCard.jsx";

const EXAMPLES = [
  "What does this project do?",
  "How is authentication handled?",
  "What are the main limitations?",
];

/** The question box and the running history of answers. */
export default function AskPanel({ history, busy, onAsk }) {
  const [question, setQuestion] = useState("");

  function submit(event) {
    event.preventDefault();
    const trimmed = question.trim();
    if (trimmed.length < 3 || busy) return;
    onAsk(trimmed);
    setQuestion("");
  }

  return (
    <section>
      {/* Sticky so a second question never means scrolling back past a long
          answer. It sits below the navbar, which is 57px tall. */}
      <form
        onSubmit={submit}
        className="sticky top-[57px] z-[5] -mt-2 bg-white pb-4 pt-2 dark:bg-slate-950"
      >
        <div className="flex gap-2">
          <input
            id="question"
            type="text"
            value={question}
            autoFocus
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask anything about your sources…"
            className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white px-4 py-3 text-[15px] outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 dark:border-slate-800 dark:bg-slate-900 dark:placeholder:text-slate-600 dark:focus:border-indigo-400 dark:focus:ring-indigo-400/10"
          />
          <button
            type="submit"
            disabled={busy || question.trim().length < 3}
            className="shrink-0 rounded-xl bg-indigo-600 px-5 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-indigo-500 dark:hover:bg-indigo-400"
          >
            {busy ? "…" : "Ask"}
          </button>
        </div>

        {history.length === 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => setQuestion(example)}
                className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-500 transition hover:border-slate-300 hover:text-slate-900 dark:border-slate-800 dark:text-slate-400 dark:hover:border-slate-700 dark:hover:text-slate-100"
              >
                {example}
              </button>
            ))}
          </div>
        )}
      </form>

      {history.length === 0 ? (
        <p className="mt-8 text-sm leading-6 text-slate-400 dark:text-slate-500">
          Ask a question and the answer will appear here, with the passages it drew on.
        </p>
      ) : (
        <div className="space-y-10">
          {history.map((entry) => (
            <AnswerCard key={entry.id} entry={entry} />
          ))}
        </div>
      )}
    </section>
  );
}
