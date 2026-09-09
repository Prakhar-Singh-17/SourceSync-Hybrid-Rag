import { useState } from "react";

/**
 * One answer, its citations, and how retrieval produced them.
 *
 * The retrieval detail is the point of the whole interface: a citation shows
 * whether its passage was found by semantic search, by keyword search, or by
 * both, which is the clearest way to see what hybrid retrieval is actually
 * contributing over a plain vector search.
 */
export default function AnswerCard({ entry }) {
  const [activeCitation, setActiveCitation] = useState(null);
  const [showDetail, setShowDetail] = useState(false);
  const { question, answer, citations = [], timings, error } = entry;

  return (
    <article className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 sm:p-6">
      <h3 className="text-base font-semibold text-slate-100">{question}</h3>

      {entry.pending ? (
        <p className="mt-4 flex items-center gap-2 text-sm text-slate-400">
          <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
          Searching, reranking and drafting an answer...
        </p>
      ) : error ? (
        <p className="mt-4 rounded-lg border border-rose-900/60 bg-rose-950/40 px-3 py-2 text-sm text-rose-200">
          {error}
        </p>
      ) : (
        <>
          <p className="mt-4 whitespace-pre-wrap text-[15px] leading-7 text-slate-200">
            <CitedText text={answer} citations={citations} onHover={setActiveCitation} />
          </p>

          {citations.length > 0 && (
            <ol className="mt-6 space-y-2 border-t border-slate-800 pt-5">
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
            <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
              <button
                type="button"
                onClick={() => setShowDetail((open) => !open)}
                className="font-medium text-slate-400 underline-offset-4 hover:text-emerald-300 hover:underline"
              >
                {showDetail ? "Hide" : "How was this retrieved?"}
              </button>
              <span>{timings.total_ms} ms total</span>
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
        className="mx-0.5 cursor-default rounded bg-emerald-400/15 px-1 py-0.5 text-[11px] font-semibold text-emerald-300"
      >
        {number}
      </sup>
    );
  });
}

function CitationRow({ citation, active }) {
  const foundBy = [
    citation.dense_rank !== null && "semantic",
    citation.sparse_rank !== null && "keyword",
  ].filter(Boolean);

  return (
    <li
      className={`rounded-lg border px-3 py-2.5 transition ${
        active ? "border-emerald-400/60 bg-emerald-400/5" : "border-slate-800 bg-slate-950/40"
      }`}
    >
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[11px] font-semibold text-emerald-300">
          {citation.number}
        </span>
        <span className="break-all text-sm font-medium text-slate-200">{citation.location}</span>
        <span
          className="ml-auto text-[11px] text-slate-500"
          title="Which of the two searches returned this passage"
        >
          found by {foundBy.join(" + ") || "fusion"}
        </span>
      </div>
      <p className="mt-1.5 text-xs leading-5 text-slate-400">{citation.snippet}</p>
    </li>
  );
}

function RetrievalDetail({ entry }) {
  const { timings, candidates_considered, dense_hits, sparse_hits, reranked } = entry;
  const stages = [
    ["Embed question", timings.embed_ms],
    ["Search (dense + sparse)", timings.search_ms],
    ["Rerank", timings.rerank_ms],
    ["Generate answer", timings.generate_ms],
  ];

  return (
    <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-xs text-slate-400">
      <p className="leading-5">
        Semantic search returned <strong className="text-slate-200">{dense_hits}</strong> passages and
        keyword search returned <strong className="text-slate-200">{sparse_hits}</strong>. Reciprocal rank
        fusion merged them into{" "}
        <strong className="text-slate-200">{candidates_considered}</strong> candidates,
        {reranked
          ? " which the model then reranked"
          : " which were used in fusion order (reranking was skipped or unavailable)"}
        , keeping the top <strong className="text-slate-200">{entry.citations.length}</strong> as context.
      </p>
      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-4">
        {stages.map(([label, value]) => (
          <div key={label}>
            <dt className="text-slate-500">{label}</dt>
            <dd className="font-mono text-slate-300">{value} ms</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
