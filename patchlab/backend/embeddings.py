"""
PatchLab — Embeddings + VectorAI Writer

Slices the fused 1-Hz DataFrame into 10-second windows, converts each
window into a structured text string, embeds it with bge-large-en
(via sentence-transformers), and stores the resulting vectors in
Actian VectorAI for cross-session semantic search.

This enables queries like:
  "Find all 10-second windows where frustration > 0.8 in the pit state"

Public API (called by main.py or post-session pipeline):
    embed_and_store(session_id, project_id, fused_df, dfa_config) -> int
    similarity_search(query_text, top_k, filters) -> List[Dict]

Set MOCK_MODE=true to skip embedding model loading and VectorAI calls.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from config import (
    EMBEDDING_WINDOW_SEC,
    MOCK_MODE,
    VECTORAI_API_KEY,
    VECTORAI_COLLECTION,
    VECTORAI_URL,
)

logger = logging.getLogger(__name__)

# ── Embedding model (lazy-loaded on first use) ────────────────────────────────
_MODEL = None
EMBEDDING_MODEL_NAME = "BAAI/bge-large-en"


def _get_model():
    """
    Lazy-load the bge-large-en sentence embedding model.
    Uses GPU if available, otherwise CPU.
    Caches the model after first load so subsequent calls are instant.
    """
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    try:
        from sentence_transformers import SentenceTransformer
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"[embeddings] Loading {EMBEDDING_MODEL_NAME} on {device}")
        _MODEL = SentenceTransformer(EMBEDDING_MODEL_NAME, device=device)
        logger.info(f"[embeddings] Model loaded — embedding dim: {_MODEL.get_sentence_embedding_dimension()}")
        return _MODEL
    except ImportError:
        raise RuntimeError(
            "sentence-transformers not installed. Run: pip install sentence-transformers"
        )


# ── VectorAI client (lazy-loaded on first use) ────────────────────────────────
_VECTORAI_CLIENT = None


def _get_vectorai_client():
    """
    Returns a connected VectorAI client.
    Raises RuntimeError if VECTORAI_URL is not set.
    """
    global _VECTORAI_CLIENT
    if _VECTORAI_CLIENT is not None:
        return _VECTORAI_CLIENT

    if not VECTORAI_URL:
        raise RuntimeError(
            "VECTORAI_URL not set in .env. Cannot connect to VectorAI."
        )

    try:
        # VectorAI connection — adjust import/init to match your actual SDK version
        # This follows the standard insert/similarity_search interface described in
        # the Actian VectorAI docs.
        import vectorai  # noqa: F401  — package name may vary by version
        from vectorai import VectorAIClient
        _VECTORAI_CLIENT = VectorAIClient(
            url=VECTORAI_URL,
            api_key=VECTORAI_API_KEY,
            collection=VECTORAI_COLLECTION,
        )
        logger.info(f"[embeddings] VectorAI connected: {VECTORAI_URL}")
        return _VECTORAI_CLIENT
    except ImportError:
        raise RuntimeError(
            "VectorAI client package not installed. "
            "Install the correct package for your VectorAI instance."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Window serialization
# ─────────────────────────────────────────────────────────────────────────────

def _serialize_window(window_df: pd.DataFrame) -> str:
    """
    Convert a 10-second window of the fused DataFrame into a structured
    text string for embedding. Uses the mean of each column across the window.

    Format (exactly as specified):
        "state: {state} | t: {t} | frustration: {val} | confusion: {val} |
         delight: {val} | boredom: {val} | HR: {val} | HRV: {val} | intent_delta: {val}"

    Uses the most common state in the window (mode) and the start timestamp.
    """
    state = str(window_df["state"].mode()[0]) if len(window_df) > 0 else "unknown"
    t_start = int(window_df["t"].iloc[0])

    avg = window_df[["frustration", "confusion", "delight", "boredom",
                      "hr", "hrv_rmssd", "intent_delta"]].mean()

    return (
        f"state: {state} | "
        f"t: {t_start} | "
        f"frustration: {avg['frustration']:.3f} | "
        f"confusion: {avg['confusion']:.3f} | "
        f"delight: {avg['delight']:.3f} | "
        f"boredom: {avg['boredom']:.3f} | "
        f"HR: {avg['hr']:.1f} | "
        f"HRV: {avg['hrv_rmssd']:.1f} | "
        f"intent_delta: {avg['intent_delta']:.3f}"
    )


def _build_windows(
    fused_df: pd.DataFrame,
    window_sec: int = EMBEDDING_WINDOW_SEC,
) -> List[Dict]:
    """
    Slice the fused DataFrame into non-overlapping windows of `window_sec` seconds.

    Returns a list of dicts, each containing:
        t_start:   int — session second where this window starts
        t_end:     int — session second where this window ends (exclusive)
        state:     str — dominant state in this window
        text:      str — serialized text representation for embedding
        meta:      dict — stats for storage alongside the vector
    """
    windows = []
    total = len(fused_df)

    for start in range(0, total, window_sec):
        end = min(start + window_sec, total)
        window = fused_df.iloc[start:end]

        if window.empty:
            continue

        state = str(window["state"].mode()[0]) if len(window) > 0 else "unknown"
        text  = _serialize_window(window)

        meta = {
            "t_start":          start,
            "t_end":            end,
            "state":            state,
            "frustration_avg":  round(float(window["frustration"].mean()), 4),
            "confusion_avg":    round(float(window["confusion"].mean()), 4),
            "delight_avg":      round(float(window["delight"].mean()), 4),
            "boredom_avg":      round(float(window["boredom"].mean()), 4),
            "hr_avg":           round(float(window["hr"].mean()), 2),
            "hrv_avg":          round(float(window["hrv_rmssd"].mean()), 2),
            "intent_delta_avg": round(float(window["intent_delta"].mean()), 4),
            "data_quality_avg": round(float(window["data_quality"].mean()), 3),
        }

        windows.append({"text": text, "meta": meta})

    return windows


# ─────────────────────────────────────────────────────────────────────────────
# Embedding computation
# ─────────────────────────────────────────────────────────────────────────────

def _embed_texts(texts: List[str]) -> np.ndarray:
    """
    Run the bge-large-en model over a list of text strings.
    Returns a (N, D) float32 numpy array where D = 1024 for bge-large-en.

    Uses batch encoding for efficiency.
    """
    model = _get_model()
    # bge models benefit from a query prefix — for document embedding use no prefix
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        normalize_embeddings=True,   # unit-normalize for cosine similarity
        convert_to_numpy=True,
    )
    return embeddings.astype(np.float32)


def _mock_embed_texts(texts: List[str]) -> np.ndarray:
    """
    Returns random unit-normalized vectors of dim 1024 (same shape as bge-large-en).
    Used when MOCK_MODE = True to avoid loading the full model.
    """
    rng = np.random.default_rng(seed=42)
    vecs = rng.standard_normal((len(texts), 1024)).astype(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / np.maximum(norms, 1e-9)


# ─────────────────────────────────────────────────────────────────────────────
# VectorAI storage
# ─────────────────────────────────────────────────────────────────────────────

def _store_vectors(
    session_id: str,
    project_id: str,
    windows: List[Dict],
    vectors: np.ndarray,
) -> int:
    """
    Insert each (vector, metadata) pair into VectorAI.

    Each document stored has:
        id:         "{session_id}_{t_start}"
        vector:     List[float] of length 1024
        session_id, project_id, and all meta fields (for filtering)
    """
    client = _get_vectorai_client()

    documents = []
    for i, (window, vec) in enumerate(zip(windows, vectors)):
        doc = {
            "id":         f"{session_id}_{window['meta']['t_start']}",
            "vector":     vec.tolist(),
            "session_id": session_id,
            "project_id": project_id,
            "text":       window["text"],
            **window["meta"],
        }
        documents.append(doc)

    client.insert(documents)
    logger.info(f"[embeddings] Stored {len(documents)} vectors for session {session_id}")
    return len(documents)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def embed_and_store(
    session_id: str,
    project_id: str,
    fused_df: pd.DataFrame,
    window_sec: int = EMBEDDING_WINDOW_SEC,
) -> int:
    """
    Full pipeline: slice → serialize → embed → store.

    Args:
        session_id:  Session identifier (used as partition key in VectorAI).
        project_id:  Project identifier (stored as metadata for filtering).
        fused_df:    Clean 1-Hz fused DataFrame from fusion.fuse_streams().
        window_sec:  Size of each embedding window in seconds (default 10).

    Returns:
        Number of vectors stored.

    In MOCK_MODE: computes real windows and text serialization (verifiable),
    but uses random vectors and skips VectorAI insertion.
    """
    if fused_df.empty:
        logger.warning(f"[embeddings] Empty DataFrame for session {session_id} — nothing to embed")
        return 0

    # Step 1: Slice into windows and serialize
    windows = _build_windows(fused_df, window_sec=window_sec)
    if not windows:
        return 0

    texts = [w["text"] for w in windows]
    logger.info(f"[embeddings] {len(texts)} windows to embed for session {session_id}")

    # Step 2: Embed
    if MOCK_MODE:
        vectors = _mock_embed_texts(texts)
        logger.info(f"[embeddings][MOCK] Generated {len(vectors)} mock vectors (shape={vectors.shape})")
        # Log a sample so devs can see the format
        for i, (w, txt) in enumerate(zip(windows[:2], texts[:2])):
            logger.debug(f"[embeddings][MOCK] window {i}: {txt}")
        return len(windows)

    # Real mode: load model + embed
    vectors = _embed_texts(texts)

    # Step 3: Store in VectorAI
    return _store_vectors(session_id, project_id, windows, vectors)


def similarity_search(
    query_text: str,
    top_k: int = 10,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """
    Embed a natural-language query and find the most similar windows
    across all sessions in VectorAI.

    Example:
        results = similarity_search(
            "frustration > 0.8 in pit state",
            top_k=5,
            filters={"project_id": "proj-abc"},
        )

    Args:
        query_text: Natural language description of the pattern to find.
        top_k:      Number of results to return.
        filters:    Optional metadata filters (e.g. {"state": "pit"}).

    Returns:
        List of dicts with keys: id, session_id, text, score, and all meta fields.
    """
    if MOCK_MODE:
        logger.info(f"[embeddings][MOCK] similarity_search: '{query_text}' top_k={top_k}")
        return [{
            "id":               f"mock_session_{i}_0",
            "session_id":       f"mock_session_{i}",
            "text":             f"state: pit | t: {i*10} | frustration: 0.82 | "
                                f"confusion: 0.45 | delight: 0.12 | boredom: 0.20 | "
                                f"HR: 88.0 | HRV: 38.5 | intent_delta: 0.37",
            "score":            round(0.95 - i * 0.04, 3),
            "frustration_avg":  0.82,
            "state":            "pit",
        } for i in range(min(top_k, 3))]

    # Real mode
    query_vec = _embed_texts([query_text])[0]
    client = _get_vectorai_client()
    results = client.similarity_search(
        vector=query_vec.tolist(),
        top_k=top_k,
        filters=filters or {},
    )
    return results
