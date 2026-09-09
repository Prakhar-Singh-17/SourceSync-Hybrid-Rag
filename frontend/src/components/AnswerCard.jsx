import { useState } from "react";

import StageIndicator from "./StageIndicator.jsx";

/**
 * One answer, its citations, and how retrieval produced them.
 *
 * The retrieval detail is the point of the whole interface: a citation shows
 * whether its passage was found by semantic search, by keyword search, or by
 * both, which is the clearest way to see what hybrid retrieval contributes
 * over a plain vector search.
 */
export default function AnswerCard({ entry, onToggle }) {
  const [activeCitation, setActiveCitation] = useState(null);
  const [showDetail, setShowDetail] = useState(false);
  const { question, answer = "", citations = [], timings, error, streaming, stage } = entry;

  const collapsed = Boolean(entry.collapsed);
  const bodyId = `answer-${entry.id}`;

  return (
    <article className="border-t border-slate-100 pt-6 dark:border-slate-800/70">
      <h3>
        <button
          type="button"
          onClick={() => onToggle(entry.id)}
          aria-expanded={!collapsed}
          aria-controls={bodyId}
          className="flex w-full items-start gap-2.5 rounded-lg text-left transition hover:opacity-80"
        >
          <Chevron open={!collapsed} />
          <span className="flex-1 text-[15px] font-medium leading-6">{question}</span>
          {collapsed && !error && timings && (
            <span className="mt-0.5 shrink-0 font-mono text-[11px] text-slate-400 dark:text-slate-500">
              {citations.length} src · {timings.total_ms} ms
            </span>
          )}
        </button>
      </h3>

      <div id={bodyId} hidden={collapsed}>
      {error ? (
        <p className="mt-5 rounded-lg bg-red-50 px-3.5 py-2.5 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300">
          {error}
        </p>
      ) : (
        <>
          {streaming && (
            <div className="mt-4">
              <StageIndicator stage={stage} />
            </div>
          )}

          {answer && (
            <p className="mt-5 whitespace-pre-wrap text-[15px] leading-7 text-slate-700 dark:text-slate-300">
              <CitedText text={answer} citations={citations} onHover={setActiveCitation} />
              {streaming && (
                <span
                  aria-hidden="true"
                  className="ml-0.5 inline-block h-[1.05em] w-[2px] translate-y-[0.15em] animate-pulse bg-indigo-500 dark:bg-indigo-400"
                />
              )}
            </p>
          )}

          {citations.length > 0 && (
            <ol className="mt-8 space-y-px">
              {citations.map((citation) => (
                <CitationRow
                  key={citation.number}
                  citation={citation}
                  active={activeCitation === citation.number}
                />
              ))}
            </ol>
          )}

          {timings && (
            <div className="mt-5 flex items-center gap-3 text-xs text-slate-400 dark:text-slate-500">
              <button
                type="button"
                onClick={() => setShowDetail((open) => !open)}
                className="underline decoration-slate-200 underline-offset-4 transition hover:text-slate-900 dark:decoration-slate-700 dark:hover:text-slate-100"
              >
                {showDetail ? "Hide detail" : "How was this retrieved?"}
              </button>
              <span className="font-mono">{timings.total_ms} ms</span>
            </div>
          )}

          {showDetail && <RetrievalDetail entry={entry} />}
        </>
      )}
      </div>
    </article>
  );
}

function Chevron({ open }) {
  return (
    <svg
      viewBox="0 0 12 12"
      aria-hidden="true"
      className={`mt-1.5 h-3 w-3 shrink-0 text-slate-400 transition-transform dark:text-slate-500 ${
        open ? "rotate-90" : ""
      }`}
    >
      <path
        d="M4 2.5 L8 6 L4 9.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Renders [1] markers in the answer as chips linked to the citation list. */
function CitedText({ text, citations, onHover }) {
  const numbers = new Set(citations.map((citation) => citation.number));
  return text.split(/(\[\d+\])/g).map((part, index) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (!match || !numbers.has(Number(match[1]))) {
      return <span key={index}>{part}</span>;
    }
    const number = Number(match[1]);
    return (
      <sup
        key={index}
        onMouseEnter={() => onHover(number)}
        onMouseLeave={() => onHover(null)}
        className="mx-0.5 cursor-default font-mono text-[10px] font-medium text-indigo-600 dark:text-indigo-400"
      >
        {number}
      </sup>
    );
  });
}

// The two retrievers get distinct tints so it is legible at a glance whether a
// passage was found by meaning, by wording, or by both. This is the one place
// colour carries information rather than decoration, which is why the rest of
// the palette stays neutral.
const BADGE_TINTS = {
  Semantic: "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300",
  Keyword: "bg-pink-50 text-pink-700 dark:bg-pink-500/15 dark:text-pink-300",
};

function CitationRow({ citation, active }) {
  const foundBy = [
    citation.dense_rank !== null && "Semantic",
    citation.sparse_rank !== null && "Keyword",
  ].filter(Boolean);

  return (
    <li
      className={`-mx-3 rounded-lg px-3 py-2.5 transition ${
        active ? "bg-indigo-50 dark:bg-indigo-500/10" : ""
      }`}
    >
      <div className="flex items-baseline gap-2.5">
        <span className="font-mono text-[11px] text-indigo-600 dark:text-indigo-400">
          {citation.number}
        </span>
        <span className="truncate text-[13px] font-medium">{citation.location}</span>
        <span className="ml-auto flex shrink-0 gap-1">
          {foundBy.map((label) => (
            <span
              key={label}
              title="Which search returned this passage"
              className={`rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${BADGE_TINTS[label]}`}
            >
              {label}
            </span>
          ))}
        </span>
      </div>
      <p className="mt-1.5 pl-[22px] text-[13px] leading-5 text-slate-500 dark:text-slate-400">
        {citation.snippet}
      </p>
    </li>
  );
}

function RetrievalDetail({ entry }) {
  const { timings, candidates_considered, dense_hits, sparse_hits, reranked } = entry;
  const stages = [
    ["Embed", timings.embed_ms],
    ["Search", timings.search_ms],
    ["Rerank", timings.rerank_ms],
    ["Generate", timings.generate_ms],
  ];

  return (
    <div className="mt-4 rounded-xl bg-slate-50 p-4 text-[13px] text-slate-500 dark:bg-slate-900 dark:text-slate-400">
      <p className="leading-6">
        Semantic search returned <Value>{dense_hits}</Value> passages, keyword search returned{" "}
        <Value>{sparse_hits}</Value>. Fusion merged them into{" "}
        <Value>{candidates_considered}</Value> candidates
        {reranked ? ", reranked" : " (used in fusion order)"}, keeping the top{" "}
        <Value>{entry.citations.length}</Value> as context.
      </p>
      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
        {stages.map(([label, value]) => (
          <div key={label}>
            <dt className="text-[11px] uppercase tracking-wide text-slate-400 dark:text-slate-500">
              {label}
            </dt>
            <dd className="mt-0.5 font-mono text-slate-700 dark:text-slate-300">{value} ms</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function Value({ children }) {
  return <span className="font-mono text-slate-900 dark:text-slate-100">{children}</span>;
}
