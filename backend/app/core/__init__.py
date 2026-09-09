"""Pure retrieval logic.

Nothing in this package opens a socket, reads a file, or imports FastAPI.  Every
function here is deterministic: given the same input it returns the same output.
That is what makes the interesting parts of the system -- chunking, lexical
scoring and rank fusion -- straightforward to unit test without an API key.

Anything that talks to Qdrant, Gemini or GitHub lives in ``app.services``.
"""
