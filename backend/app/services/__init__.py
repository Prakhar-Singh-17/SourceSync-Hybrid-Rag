"""Everything that talks to the outside world.

One module per external system: Gemini embeddings, Gemini generation, Qdrant,
GitHub.  Each exposes a small class with plain arguments and plain return
values, so a test can substitute a fake without patching internals.

The orchestration that strings them together lives in :mod:`app.services.pipeline`.
"""
