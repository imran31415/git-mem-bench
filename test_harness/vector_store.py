#!/usr/bin/env python3
"""
In-process vector retrieval store for the benchmark.

Unlike the other systems under test (git-mem, engram, mcp-server-memory), a
vector store is not an MCP subprocess — it is an embedded library. To compare
it fairly on the *same* logical operations (WRITE/READ/SEARCH/DELETE/LIST), we
wrap a small in-process store in a client-shaped object so the existing
BenchmarkRunner can time it exactly like an MCP server.

What makes a vector store different — and what this benchmark is designed to
expose honestly:

  * WRITE pays an **embedding cost** on every insert (text → dense vector).
    This is the price of admission and the reason writes are slower than a
    plain key-value store.
  * SEARCH is **semantic / similarity** search (nearest neighbours by cosine
    distance), not substring matching. This is the thing a vector store is
    actually for, and the only operation where it has a structural advantage.
  * READ / DELETE / LIST are ordinary id-keyed dictionary operations and carry
    no embedding cost.

Backends, selected automatically (best available wins):

  Vector index:
    - chromadb            — a real embedded vector database, if installed
    - numpy (brute force) — always available; exact cosine over a dense matrix

  Embedder (text → vector):
    - sentence-transformers — real semantic embeddings, if installed
    - hashing bag-of-words  — always available; deterministic, NON-semantic
                              (fast, dependency-free, but only matches on shared
                              tokens — clearly labelled as such in the report)

Out of the box, with only numpy present, you get the numpy index + hashing
embedder. Installing `sentence-transformers` and/or `chromadb` upgrades the
relevant layer with no other changes.
"""
import hashlib
import json
import re
import threading
from typing import Any, Dict, List, Optional

import numpy as np


# ---------------------------------------------------------------------------
# Embedders: text -> unit-norm dense vector
# ---------------------------------------------------------------------------

class HashingEmbedder:
    """
    Deterministic, dependency-free bag-of-words hashing embedder.

    Tokens are hashed into a fixed-dimension vector (the "hashing trick"). It is
    fast and requires no model download, but it is NOT semantic: two documents
    are only "close" if they literally share tokens. We label it as such so the
    SEARCH numbers are never mistaken for true semantic recall.
    """

    semantic = False

    def __init__(self, dim: int = 384):
        self.dim = dim
        self.name = f"hashing-bow/{dim}d (deterministic, non-semantic)"

    def embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for tok in re.findall(r"[a-z0-9]+", text.lower()):
            h = int(hashlib.blake2b(tok.encode(), digest_size=8).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        return np.vstack([self.embed(t) for t in texts])


class SentenceTransformerEmbedder:
    """Real semantic embeddings via sentence-transformers (if installed)."""

    semantic = True

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer  # lazy import

        self._model = SentenceTransformer(model_name)
        self.dim = self._model.get_sentence_embedding_dimension()
        self.name = f"sentence-transformers/{model_name} ({self.dim}d, semantic)"

    def embed(self, text: str) -> np.ndarray:
        return self._model.encode(
            text, normalize_embeddings=True
        ).astype(np.float32)

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        return self._model.encode(
            texts, normalize_embeddings=True
        ).astype(np.float32)


def build_embedder(kind: str = "auto", dim: int = 384):
    """Pick an embedder. 'auto' prefers a real semantic model if available."""
    if kind in ("auto", "sentence-transformers"):
        try:
            return SentenceTransformerEmbedder()
        except Exception:
            if kind == "sentence-transformers":
                raise
            # fall through to hashing
    return HashingEmbedder(dim=dim)


# ---------------------------------------------------------------------------
# Vector index backends
# ---------------------------------------------------------------------------

class NumpyVectorStore:
    """
    Exact (brute-force) cosine-similarity store over a dense numpy matrix.

    WRITE  — embed text, append a row.            O(embed) + amortised append
    READ   — id → payload dict lookup.            O(1)
    SEARCH — embed query, score every row.        O(N · dim)
    DELETE — drop the row + payload.              O(N) (matrix rebuild)
    LIST   — return all keys.                     O(N)
    """

    backend_name = "numpy (exact brute-force cosine)"

    def __init__(self, embedder):
        self.embedder = embedder
        self._matrix: Optional[np.ndarray] = None  # shape (N, dim)
        self._keys: List[str] = []
        self._pos: Dict[str, int] = {}
        self._payloads: Dict[str, Any] = {}
        # the matrix is mutated in place (vstack/delete); guard for the
        # concurrent multi-agent scenarios that share one store across threads
        self._lock = threading.Lock()

    @staticmethod
    def _to_text(key: str, value: Any) -> str:
        body = value if isinstance(value, str) else json.dumps(value)
        return f"{key} {body}"

    def add(self, key: str, value: Any) -> Dict:
        # embed outside the lock — it is the expensive part and is pure
        vec = self.embedder.embed(self._to_text(key, value)).reshape(1, -1)
        with self._lock:
            if key in self._pos:
                self._matrix[self._pos[key]] = vec
            else:
                self._pos[key] = len(self._keys)
                self._keys.append(key)
                self._matrix = vec if self._matrix is None else np.vstack([self._matrix, vec])
            self._payloads[key] = value
            return {"ok": True, "key": key, "count": len(self._keys)}

    def get(self, key: str) -> Dict:
        with self._lock:
            if key not in self._payloads:
                return {"found": False, "key": key}
            return {"found": True, "key": key, "value": self._payloads[key]}

    def search(self, query: str, top_k: int = 10) -> Dict:
        qvec = self.embedder.embed(query)
        with self._lock:
            if self._matrix is None or len(self._keys) == 0:
                return {"matches": []}
            scores = self._matrix @ qvec  # cosine: rows + query are unit-norm
            keys = self._keys
            k = min(top_k, len(keys))
            top = np.argpartition(-scores, k - 1)[:k]
            top = top[np.argsort(-scores[top])]
            return {
                "matches": [
                    {"key": keys[i], "score": float(scores[i])} for i in top
                ]
            }

    def delete(self, key: str) -> Dict:
        with self._lock:
            if key not in self._pos:
                return {"ok": False, "key": key, "reason": "not found"}
            idx = self._pos.pop(key)
            self._keys.pop(idx)
            self._payloads.pop(key, None)
            self._matrix = np.delete(self._matrix, idx, axis=0)
            if self._matrix.shape[0] == 0:
                self._matrix = None
            # reindex positions after the removed row
            for k, p in self._pos.items():
                if p > idx:
                    self._pos[k] = p - 1
            return {"ok": True, "key": key, "count": len(self._keys)}

    def list_all(self) -> Dict:
        with self._lock:
            return {"keys": list(self._keys), "count": len(self._keys)}


class ChromaVectorStore:
    """
    Wrapper around an embedded chromadb collection (if installed).

    chromadb owns its own ANN index and persistence; we feed it our embedder so
    the embedding cost is measured on the same footing as the numpy backend.
    """

    backend_name = "chromadb (embedded HNSW index)"

    def __init__(self, embedder, collection_name: str = "benchmark"):
        import chromadb  # lazy import

        self.embedder = embedder
        self._client = chromadb.EphemeralClient()
        # cosine space to match the numpy backend's metric
        self._col = self._client.create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )
        self._payloads: Dict[str, Any] = {}

    @staticmethod
    def _to_text(key: str, value: Any) -> str:
        body = value if isinstance(value, str) else json.dumps(value)
        return f"{key} {body}"

    def add(self, key: str, value: Any) -> Dict:
        emb = self.embedder.embed(self._to_text(key, value)).tolist()
        self._col.upsert(ids=[key], embeddings=[emb])
        self._payloads[key] = value
        return {"ok": True, "key": key, "count": self._col.count()}

    def get(self, key: str) -> Dict:
        if key not in self._payloads:
            return {"found": False, "key": key}
        return {"found": True, "key": key, "value": self._payloads[key]}

    def search(self, query: str, top_k: int = 10) -> Dict:
        emb = self.embedder.embed(query).tolist()
        n = min(top_k, max(1, self._col.count()))
        res = self._col.query(query_embeddings=[emb], n_results=n)
        ids = (res.get("ids") or [[]])[0]
        dists = (res.get("distances") or [[None] * len(ids)])[0]
        return {
            "matches": [
                {"key": i, "score": (1.0 - d) if d is not None else None}
                for i, d in zip(ids, dists)
            ]
        }

    def delete(self, key: str) -> Dict:
        if key not in self._payloads:
            return {"ok": False, "key": key, "reason": "not found"}
        self._col.delete(ids=[key])
        self._payloads.pop(key, None)
        return {"ok": True, "key": key, "count": self._col.count()}

    def list_all(self) -> Dict:
        keys = list(self._payloads.keys())
        return {"keys": keys, "count": len(keys)}


def build_store(backend: str = "auto", embedder: str = "auto", dim: int = 384):
    """Construct a vector store. 'auto' prefers chromadb, then numpy."""
    emb = build_embedder(embedder, dim=dim)
    if backend in ("auto", "chromadb"):
        try:
            return ChromaVectorStore(emb)
        except Exception:
            if backend == "chromadb":
                raise
    return NumpyVectorStore(emb)


# ---------------------------------------------------------------------------
# Client-shaped wrapper so the existing BenchmarkRunner can time it
# ---------------------------------------------------------------------------

class VectorStoreClient:
    """
    In-process stand-in for an MCPClient.

    Exposes just enough surface (start/stop/list_tools, a null `process`) for
    BenchmarkRunner to treat it like any other server. There is no subprocess,
    so the psutil per-process sampling in the runner is simply skipped.
    """

    def __init__(self, name: str, backend: str = "auto",
                 embedder: str = "auto", dim: int = 384):
        self.name = name
        self.process = None  # no subprocess -> runner's psutil path is skipped
        self.store = build_store(backend=backend, embedder=embedder, dim=dim)

    @property
    def backend_name(self) -> str:
        return self.store.backend_name

    @property
    def embedder_name(self) -> str:
        return self.store.embedder.name

    @property
    def is_semantic(self) -> bool:
        return getattr(self.store.embedder, "semantic", False)

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        # nothing to tear down; drop references to free memory
        self.store = None

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {"name": "vadd", "description": "embed + insert a document"},
            {"name": "vget", "description": "fetch a document by id"},
            {"name": "vsearch", "description": "semantic nearest-neighbour search"},
            {"name": "vdelete", "description": "remove a document by id"},
            {"name": "vlist", "description": "list document ids"},
        ]
