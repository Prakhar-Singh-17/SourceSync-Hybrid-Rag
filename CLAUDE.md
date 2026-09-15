# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All backend commands run from `backend/`. On Windows the interpreter is
`.venv/Scripts/python.exe`; substitute `.venv/bin/python` elsewhere.

```bash
# Backend dev server
uv run uvicorn app.main:app --reload --port 8000

# Frontend dev server (from frontend/)
npm run dev

# Frontend production build — the only frontend check that exists
npm run build

# Full test suite (50 tests, no credentials required)
python -m unittest discover -s tests -v

# One module, one class, or one test
python -m unittest tests.test_core
python -m unittest tests.test_pipeline.AskStreamTests
python -m unittest tests.test_core.FusionTests.test_rrf_scores_match_the_formula

# Retrieval evaluation — needs .env credentials, costs API calls
python -m evaluation.evaluate
```

Tests run with no API key and no Qdrant. `test_core.py` covers pure functions
directly, `test_pipeline.py` runs the whole query flow against stand-in services,
and `test_api.py` uses `TestClient(app)` *without* a context manager so the
lifespan never executes and no clients are built. Keep it that way — CI has no
credentials.

## Architecture

### Three layers, and the reason for them

```
backend/app/
  core/      Pure logic. No network, no database, no FastAPI import.
  services/  One class per external system (Gemini, Qdrant, GitHub).
  routers/   HTTP only — translate results and errors, no logic.
```

`core/` raises plain `SourceError` / `SourceTooLarge` (see `core/errors.py`);
`main.py` registers exception handlers mapping them to 422 and 413. Do not
import FastAPI into `core/`.

The layering is what makes the tests credential-free: `Pipeline` receives its
store, embedder and LLM as constructor arguments, so tests substitute fakes.
Anything that constructs its own dependencies breaks that.

### The query pipeline

`services/pipeline.py` is the one place the flow is written down in order. Read
it first. `ask_stream()` is the real implementation — an async generator — and
`ask()` simply drains it, so the JSON and streaming endpoints cannot diverge.

```
question -> embed (dense) + sparse_vector (local)
         -> Qdrant dense search + sparse search, concurrently
         -> reciprocal_rank_fusion  (core/fusion.py)
         -> LLM rerank (20 candidates -> 6)
         -> streamed answer with [n] citations
```

### Streaming event contract

`ask_stream()` yields dicts consumed by `routers/query.py` (as SSE) and parsed in
`frontend/src/api.js`. Changing these event shapes requires changing both sides.

| `type` | Payload |
| --- | --- |
| `stage` | `stage`: embedding / searching / reranking / writing |
| `context` | `citations`, `reranked`, `candidates_considered`, `dense_hits`, `sparse_hits` |
| `token` | `text` — a fragment of the answer |
| `done` | `timings` |
| `error` | `detail` |

`context` is emitted **before** the first `token` on purpose — the UI shows
citations while the answer is still being written. `tests/test_pipeline.py`
asserts that ordering.

### Qdrant collection layout

Each passage is stored once with two **named** vectors:

- `dense` — Gemini embedding, cosine distance
- `sparse` — BM25 term frequencies, with `Modifier.IDF` so Qdrant computes the
  IDF half server-side from the live corpus

A collection created before hybrid search has an incompatible layout;
`VectorStore._verify_collection` detects this and raises rather than
misbehaving. Point `QDRANT_COLLECTION` at a new name instead of migrating.

One collection serves all sessions. Isolation is a mandatory `session_id`
filter, indexed with `is_tenant=True`. Never add a search path that omits it.

### Sessions

Signed cookies, no server-side store (`app/sessions.py`). The cookie carries the
session id and expiry, HMAC-signed with `SESSION_SECRET`. This survives restarts
and multiple workers, which an in-memory store did not on a free instance that
sleeps every 15 minutes.

Every stored passage carries its session's `expires_at`. Cleanup is one filtered
delete, run at startup and every `PURGE_INTERVAL_MINUTES` by a background
`asyncio` task started in the lifespan. There is no worker process or queue.

## Constraints that will bite you

These are all load-bearing and were each found by breaking something.

- **`embed_content` does not batch.** Given several texts it returns *one*
  embedding, silently. `services/embeddings.py` sends one text per request and
  gets throughput from concurrency instead. The length check there is what
  catches this class of failure; keep it.
- **Free-tier request quotas are per model per day.** `gemini-3.5-flash` allows
  20 generate calls a day — about ten questions once reranking is counted. The
  default is `gemini-3.5-flash-lite`.
- **The `-lite` models reject `thinking_budget=0`** with HTTP 400.
  `ANSWER_THINKING_BUDGET=-1` means "send no thinking config", the only value
  safe on every model. See `thinking_config()` in `services/llm.py`.
- **429 is two different failures.** A per-minute rate limit is retried with
  backoff; a per-day quota is not, because each retry spends another unit of the
  budget for the same error. `services/retry.py` distinguishes them.
- **Sparse term ids use CRC32, not `hash()`.** Python randomises string hashing
  per process, which would assign a term one dimension at ingest and a different
  one at query time.
- **Embeddings are truncated 3072 -> 768** via `output_dimensionality`. The model
  supports this natively and returns already-normalised vectors.

## Frontend

React + Vite + Tailwind v4. Tailwind is configured in CSS: `src/styles.css` is
the Tailwind import plus an `@theme` block (two fonts, one custom animation).
There is no `tailwind.config.js` and no bespoke CSS — everything else is a stock
utility class.

Dark mode is `prefers-color-scheme` via `dark:` variants; there is no toggle.
Palette is slate neutrals with indigo as the accent. Colour carries meaning in
exactly one place — the semantic/keyword citation badges — which is why the rest
stays neutral.

The page renders before the session resolves. Actions await an in-flight session
promise inside `api.js` rather than the page blocking on it, and which layout to
show is seeded from a `localStorage` hint stored with the session expiry.

## Deployment

`render.yaml` defines the API and the static frontend. A service created by hand
in the dashboard does not pick up `render.yaml` changes — set env vars there
directly. `SESSION_SECRET` uses `generateValue: true` so it stays stable across
deploys.
