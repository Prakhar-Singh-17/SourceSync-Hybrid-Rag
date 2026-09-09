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
export default function AnswerCard({ entry }) {
  const [activeCitation, setActiveCitation] = useState(null);
  const [showDetail, setShowDetail] = useState(false);
  const { question, answer = "", citations = [], timings, error, streaming, stage } = entry;

  return (
    <article className="border-t border-zinc-100 pt-8 dark:border-zinc-800/70">
      <h3 className="text-[15px] font-medium leading-6">{question}</h3>

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
            <p className="mt-5 whitespace-pre-wrap text-[15px] leading-7 text-zinc-700 dark:text-zinc-300">
              <CitedText text={answer} citations={citations} onHover={setActiveCitation} />
              {streaming && (
                <span
                  aria-hidden="true"
                  className="ml-0.5 inline-block h-[1.05em] w-[2px] translate-y-[0.15em] animate-pulse bg-blue-500 dark:bg-blue-400"
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
            <div className="mt-5 flex items-center gap-3 text-xs text-zinc-400 dark:text-zinc-500">
              <button
                type="button"
                onClick={() => setShowDetail((open) => !open)}
                className="underline decoration-zinc-200 underline-offset-4 transition hover:text-zinc-900 dark:decoration-zinc-700 dark:hover:text-zinc-100"
              >
                {showDetail ? "Hide detail" : "How was this retrieved?"}
              </button>
              <span className="font-mono">{timings.total_ms} ms</span>
            </div>
          )}

          {showDetail && <RetrievalDetail entry={entry} />}
        </>
      )}
    </article>
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
        className="mx-0.5 cursor-default font-mono text-[10px] font-medium text-blue-600 dark:text-blue-400"
      >
        {number}
      </sup>
    );
  });
}

function CitationRow({ citation, active }) {
  const foundBy = [
    citation.dense_rank !== null && "Semantic",
    citation.sparse_rank !== null && "Keyword",
  ].filter(Boolean);

  return (
    <li
      className={`-mx-3 rounded-lg px-3 py-2.5 transition ${
        active ? "bg-blue-50 dark:bg-blue-500/10" : ""
      }`}
    >
      <div className="flex items-baseline gap-2.5">
        <span className="font-mono text-[11px] text-blue-600 dark:text-blue-400">
          {citation.number}
        </span>
        <span className="truncate text-[13px] font-medium">{citation.location}</span>
        <span className="ml-auto flex shrink-0 gap-1">
          {foundBy.map((label) => (
            <span
              key={label}
              title="Which search returned this passage"
              className="rounded border border-zinc-200 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-zinc-400 dark:border-zinc-800 dark:text-zinc-500"
            >
              {label}
            </span>
          ))}
        </span>
      </div>
      <p className="mt-1.5 pl-[22px] text-[13px] leading-5 text-zinc-500 dark:text-zinc-400">
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
    <div className="mt-4 rounded-xl bg-zinc-50 p-4 text-[13px] text-zinc-500 dark:bg-zinc-900 dark:text-zinc-400">
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
            <dt className="text-[11px] uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
              {label}
            </dt>
            <dd className="mt-0.5 font-mono text-zinc-700 dark:text-zinc-300">{value} ms</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function Value({ children }) {
  return <span className="font-mono text-zinc-900 dark:text-zinc-100">{children}</span>;
}
