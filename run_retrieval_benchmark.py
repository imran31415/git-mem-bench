#!/usr/bin/env python3
"""
Real-world retrieval benchmark: semantic vector search vs keyword search.

This is the honest answer to "is the vector store actually any good?". Unlike
run_benchmark.py (which times CRUD on tiny synthetic data), this benchmark:

  * loads ~5k real documents (BeIR/scifact scientific abstracts),
  * indexes them with a REAL embedding model (sentence-transformers MiniLM)
    into a REAL vector index (chromadb HNSW),
  * compares against a BM25 keyword retriever — the same family of token
    matching that git-mem / engram / mcp-server-memory full-text search use,
  * and scores both on the actual thing you care about: did they retrieve the
    documents a human judged relevant? (recall@k, MRR), not just how fast.

It measures the real costs a production vector store pays — embedding time on
write, ANN query time on search — and the real benefit — semantic recall on
paraphrased queries that share no keywords with the answer.

Run:
    .venv/bin/python run_retrieval_benchmark.py [--docs 5000] [--model all-MiniLM-L6-v2]
"""
import argparse
import json
import math
import os
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Tuple

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO_ROOT, "test_harness"))

from corpus import load_corpus, Corpus


# ---------------------------------------------------------------------------
# Retrievers
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25Retriever:
    """
    Compact in-process BM25 keyword retriever.

    Stands in for the token/substring matching that git-mem, engram, and
    mcp-server-memory full-text search are built on. No embeddings: a query
    only matches documents that share literal terms.
    """

    name = "BM25 keyword (no embeddings)"
    semantic = False

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.doc_ids: List[str] = []
        self.doc_tokens: List[List[str]] = []
        self.df: Counter = Counter()
        self.idf: Dict[str, float] = {}
        self.doc_len: List[int] = []
        self.avg_len: float = 0.0
        self.postings: Dict[str, List[Tuple[int, int]]] = defaultdict(list)

    def index(self, items: List[Tuple[str, str]]) -> float:
        t0 = time.perf_counter()
        for did, text in items:
            toks = tokenize(text)
            idx = len(self.doc_ids)
            self.doc_ids.append(did)
            self.doc_tokens.append(toks)
            self.doc_len.append(len(toks))
            tf = Counter(toks)
            for term, c in tf.items():
                self.df[term] += 1
                self.postings[term].append((idx, c))
        n = len(self.doc_ids)
        self.avg_len = sum(self.doc_len) / n if n else 0.0
        for term, df in self.df.items():
            self.idf[term] = math.log(1 + (n - df + 0.5) / (df + 0.5))
        return (time.perf_counter() - t0) * 1000

    def search(self, query: str, top_k: int = 100) -> List[str]:
        q_terms = set(tokenize(query))
        scores: Dict[int, float] = defaultdict(float)
        for term in q_terms:
            idf = self.idf.get(term)
            if idf is None:
                continue
            for idx, c in self.postings[term]:
                dl = self.doc_len[idx]
                denom = c + self.k1 * (1 - self.b + self.b * dl / self.avg_len)
                scores[idx] += idf * (c * (self.k1 + 1)) / denom
        ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_k]
        return [self.doc_ids[i] for i, _ in ranked]


class SemanticRetriever:
    """Real semantic retriever: sentence-transformers MiniLM + chromadb HNSW."""

    semantic = True

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        import os as _os
        import torch
        from sentence_transformers import SentenceTransformer
        import chromadb

        # use all CPU cores for inference (no GPU on this box)
        torch.set_num_threads(_os.cpu_count() or 1)
        self.model = SentenceTransformer(model_name, device="cpu")
        # warm up: first encode pays JIT/alloc cost we don't want in the timings
        self.model.encode(["warmup"], normalize_embeddings=True)
        self.dim = self.model.get_embedding_dimension()
        self.name = f"semantic: {model_name} ({self.dim}d) + chromadb HNSW"
        self._client = chromadb.EphemeralClient()
        self._col = self._client.create_collection(
            name="retrieval", metadata={"hnsw:space": "cosine"}
        )
        self.embed_ms = 0.0
        self.index_ms = 0.0

    def index(self, items: List[Tuple[str, str]], batch_size: int = 256) -> float:
        t0 = time.perf_counter()
        ids = [d for d, _ in items]
        texts = [t for _, t in items]
        for i in range(0, len(items), batch_size):
            b_ids = ids[i:i + batch_size]
            b_txt = texts[i:i + batch_size]
            te = time.perf_counter()
            embs = self.model.encode(
                b_txt, normalize_embeddings=True, show_progress_bar=False
            ).tolist()
            self.embed_ms += (time.perf_counter() - te) * 1000
            self._col.add(ids=b_ids, embeddings=embs)
        self.index_ms = (time.perf_counter() - t0) * 1000
        return self.index_ms

    def search(self, query: str, top_k: int = 100) -> List[str]:
        emb = self.model.encode(query, normalize_embeddings=True).tolist()
        res = self._col.query(query_embeddings=[emb], n_results=top_k)
        return (res.get("ids") or [[]])[0]


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate(retriever, corpus: Corpus, k_values=(10, 100)) -> Dict:
    max_k = max(k_values)
    latencies: List[float] = []
    recalls = {k: [] for k in k_values}
    mrr10: List[float] = []

    for qid, qtext in corpus.queries.items():
        rel = corpus.qrels.get(qid, set())
        if not rel:
            continue
        t0 = time.perf_counter()
        ranked = retriever.search(qtext, top_k=max_k)
        latencies.append((time.perf_counter() - t0) * 1000)

        for k in k_values:
            hits = sum(1 for d in ranked[:k] if d in rel)
            recalls[k].append(hits / len(rel))

        rr = 0.0
        for rank, d in enumerate(ranked[:10], start=1):
            if d in rel:
                rr = 1.0 / rank
                break
        mrr10.append(rr)

    def pct(data, p):
        if not data:
            return 0.0
        s = sorted(data)
        i = min(int(len(s) * p / 100), len(s) - 1)
        return s[i]

    return {
        "queries_evaluated": len(latencies),
        "search_latency_mean_ms": statistics.mean(latencies) if latencies else 0,
        "search_latency_p95_ms": pct(latencies, 95),
        "recall": {f"@{k}": (statistics.mean(v) if v else 0) for k, v in recalls.items()},
        "mrr@10": statistics.mean(mrr10) if mrr10 else 0,
    }


def main():
    ap = argparse.ArgumentParser(description="Semantic vs keyword retrieval benchmark")
    ap.add_argument("--docs", type=int, default=5000)
    ap.add_argument("--queries", type=int, default=300)
    ap.add_argument("--model", default="all-MiniLM-L6-v2")
    ap.add_argument("--corpus", default="scifact")
    args = ap.parse_args()

    print("Real-World Retrieval Benchmark — semantic vs keyword")
    print("=" * 70)
    print(f"Loading corpus '{args.corpus}' (up to {args.docs} docs)...")
    corpus = load_corpus(prefer=args.corpus, max_docs=args.docs, max_queries=args.queries)
    print(f"  corpus: {corpus.name} — {len(corpus.docs)} docs, "
          f"{len(corpus.queries)} queries, relevance labels: {corpus.has_relevance}")
    if not corpus.has_relevance:
        print("  WARNING: no relevance labels — recall is not measurable, latency only.")

    items = corpus.doc_items

    results = {}

    # ---- BM25 keyword baseline -------------------------------------------
    print("\n[keyword] building BM25 index...")
    bm25 = BM25Retriever()
    bm25_index_ms = bm25.index(items)
    print(f"  indexed {len(items)} docs in {bm25_index_ms:.0f} ms "
          f"({len(items) / (bm25_index_ms/1000):.0f} docs/s)")
    bm25_eval = evaluate(bm25, corpus)
    results["bm25-keyword"] = {
        "name": bm25.name, "semantic": False,
        "index_ms": bm25_index_ms,
        "index_docs_per_s": len(items) / (bm25_index_ms / 1000) if bm25_index_ms else 0,
        **bm25_eval,
    }

    # ---- Semantic vector store -------------------------------------------
    print(f"\n[semantic] loading model '{args.model}' + indexing (embedding {len(items)} docs)...")
    sem = SemanticRetriever(model_name=args.model)
    sem_index_ms = sem.index(items)
    print(f"  indexed {len(items)} docs in {sem_index_ms/1000:.1f} s "
          f"(embedding {sem.embed_ms/1000:.1f} s = {sem.embed_ms/sem_index_ms*100:.0f}% of it; "
          f"{len(items) / (sem_index_ms/1000):.0f} docs/s)")
    sem_eval = evaluate(sem, corpus)
    results["semantic-vector"] = {
        "name": sem.name, "semantic": True,
        "index_ms": sem_index_ms,
        "embed_ms": sem.embed_ms,
        "embed_pct_of_index": sem.embed_ms / sem_index_ms * 100 if sem_index_ms else 0,
        "index_docs_per_s": len(items) / (sem_index_ms / 1000) if sem_index_ms else 0,
        **sem_eval,
    }

    # ---- Report ----------------------------------------------------------
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    hdr = f"{'metric':<26}{'BM25 keyword':>20}{'semantic vector':>20}"
    print(hdr)
    print("-" * len(hdr))
    b, s = results["bm25-keyword"], results["semantic-vector"]

    def row(label, bv, sv):
        print(f"{label:<26}{bv:>20}{sv:>20}")

    row("index throughput d/s", f"{b['index_docs_per_s']:.0f}", f"{s['index_docs_per_s']:.0f}")
    row("search latency mean ms", f"{b['search_latency_mean_ms']:.2f}", f"{s['search_latency_mean_ms']:.2f}")
    row("search latency p95 ms", f"{b['search_latency_p95_ms']:.2f}", f"{s['search_latency_p95_ms']:.2f}")
    if corpus.has_relevance:
        row("recall@10", f"{b['recall']['@10']:.3f}", f"{s['recall']['@10']:.3f}")
        row("recall@100", f"{b['recall']['@100']:.3f}", f"{s['recall']['@100']:.3f}")
        row("MRR@10", f"{b['mrr@10']:.3f}", f"{s['mrr@10']:.3f}")

    print("\nInterpretation:")
    print("  - Keyword index is ~free; semantic index pays the embedding cost (shown above).")
    if corpus.has_relevance:
        dr = s['recall']['@10'] - b['recall']['@10']
        print(f"  - Semantic recall@10 is {dr:+.3f} vs keyword — the retrieval-quality")
        print("    difference on real paraphrased queries is the reason to pay that cost.")

    out_dir = os.path.join(REPO_ROOT, "results", "raw")
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(out_dir, f"retrieval_{ts}.json")
    with open(out, "w") as f:
        json.dump({
            "timestamp": ts,
            "corpus": {"name": corpus.name, "docs": len(corpus.docs),
                       "queries": len(corpus.queries), "has_relevance": corpus.has_relevance},
            "model": args.model,
            "hardware": {"cpu_count": os.cpu_count(), "device": "cpu"},
            "results": results,
        }, f, indent=2)
    print(f"\nResults saved → {out}")


if __name__ == "__main__":
    main()
