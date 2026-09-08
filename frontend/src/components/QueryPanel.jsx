import { useState } from "react";

import { querySources } from "../api.js";

const buttonClasses = "rounded-md bg-emerald-300 px-4 py-2.5 font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-wait disabled:opacity-60";

export default function QueryPanel() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState([]);
  const [askingQuestion, setAskingQuestion] = useState(false);

  async function askQuestion(event) {
    event.preventDefault();
    setAskingQuestion(true);
    setAnswer("Searching your indexed sources...");
    setSources([]);
    try {
      const result = await querySources(question);
      setAnswer(result.answer);
      setSources(result.sources);
    } catch (error) {
      setAnswer(error.message);
    } finally {
      setAskingQuestion(false);
    }
  }

  return (
    <section className="mt-8 rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl shadow-slate-950/40 sm:p-8" aria-labelledby="ask-heading">
      <h2 id="ask-heading" className="text-2xl font-bold text-white">Ask your sources</h2>
      <form className="mt-6 flex flex-col gap-3 sm:flex-row" onSubmit={askQuestion}>
        <label className="sr-only" htmlFor="question">Question</label>
        <input className="min-w-0 flex-1 rounded-md border border-slate-600 bg-slate-950 px-3 py-2.5 text-slate-100 outline-none focus:border-emerald-300" id="question" type="text" placeholder="What does this project do?" value={question} onChange={(event) => setQuestion(event.target.value)} required />
        <button className={buttonClasses} disabled={askingQuestion} type="submit">{askingQuestion ? "Searching..." : "Ask question"}</button>
      </form>
      {answer && <div className="mt-8 border-t border-slate-700 pt-6"><p className="whitespace-pre-wrap leading-7 text-slate-200">{answer}</p>{sources.length > 0 && <p className="mt-5 text-sm text-slate-400">Sources: {sources.join(", ")}</p>}</div>}
    </section>
  );
}
