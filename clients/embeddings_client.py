from typing import List, Optional

from google import genai
from google.genai import types

import config

EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768

_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not config.LLM_API_KEY:
            raise RuntimeError("Please set the LLM_API_KEY environment variable.")
        _client = genai.Client(api_key=config.LLM_API_KEY)
    return _client


def embed_text(text: Optional[str]) -> Optional[str]:
    """Embeds `text` and returns it as a CockroachDB VECTOR literal string
    (e.g. "[0.01,-0.02,...]"), ready to pass straight through as a query
    parameter for an INSERT or a <-> comparison. Returns None for empty
    input rather than embedding a meaningless empty string."""
    if not text:
        return None

    response = _get_client().models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS),
    )
    values: List[float] = response.embeddings[0].values
    return "[" + ",".join(repr(v) for v in values) + "]"
