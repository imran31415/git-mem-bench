#!/usr/bin/env python3
"""
Real-world corpus loader for the retrieval benchmark.

The CRUD benchmark (run_benchmark.py) uses tiny synthetic random-string data,
which is fine for measuring raw operation latency but tells you NOTHING about
semantic retrieval — random tokens have no meaning to embed or match. To judge
a vector store honestly you need (a) real natural-language documents and (b)
queries with known-relevant answers so you can measure retrieval *quality*, not
just speed.

This module loads BeIR/scifact: ~5k scientific abstracts, ~300 test queries
(natural-language claims), and human relevance judgments (qrels) mapping each
query to the abstracts that actually answer it. That lets the benchmark compute
recall@k for semantic search vs keyword search on the same corpus.

Falls back to ag_news (real news text, no relevance labels) if scifact can't be
fetched, in which case only latency — not recall — is meaningful.
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class Corpus:
    name: str
    docs: Dict[str, str]                     # doc_id -> text
    queries: Dict[str, str]                  # query_id -> query text
    qrels: Dict[str, set]                    # query_id -> {relevant doc_id, ...}
    has_relevance: bool = True
    meta: Dict = field(default_factory=dict)

    @property
    def doc_items(self) -> List[Tuple[str, str]]:
        return list(self.docs.items())


def _truncate(text: str, max_chars: int = 2000) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text[:max_chars]


def load_scifact(max_docs: Optional[int] = 5000,
                 max_queries: int = 300) -> Corpus:
    """Load BeIR/scifact via HuggingFace datasets."""
    from datasets import load_dataset

    corpus_ds = load_dataset("BeIR/scifact", "corpus")["corpus"]
    queries_ds = load_dataset("BeIR/scifact", "queries")["queries"]
    qrels_ds = load_dataset("BeIR/scifact-qrels")["test"]

    # qrels first, so we can guarantee every relevant doc is in the kept set
    qrels: Dict[str, set] = {}
    for row in qrels_ds:
        if int(row.get("score", 0)) <= 0:
            continue
        qid = str(row["query-id"])
        qrels.setdefault(qid, set()).add(str(row["corpus-id"]))

    docs: Dict[str, str] = {}
    for row in corpus_ds:
        did = str(row["_id"])
        title = row.get("title", "") or ""
        body = row.get("text", "") or ""
        docs[did] = _truncate(f"{title}. {body}")

    # keep test queries that have at least one judged-relevant doc
    queries: Dict[str, str] = {}
    q_text = {str(r["_id"]): r["text"] for r in queries_ds}
    for qid, rel in qrels.items():
        if qid in q_text and rel:
            queries[qid] = q_text[qid]
        if len(queries) >= max_queries:
            break

    # collect the docs we must keep (all relevant docs) then top up to max_docs
    must_keep = set()
    for qid in queries:
        must_keep |= qrels[qid]

    kept: Dict[str, str] = {d: docs[d] for d in must_keep if d in docs}
    if max_docs:
        for did, text in docs.items():
            if len(kept) >= max_docs:
                break
            kept.setdefault(did, text)
    else:
        kept = docs

    # prune qrels/queries to the kept doc set
    qrels = {q: {d for d in rel if d in kept} for q, rel in qrels.items() if q in queries}
    queries = {q: t for q, t in queries.items() if qrels.get(q)}

    return Corpus(
        name="BeIR/scifact",
        docs=kept,
        queries=queries,
        qrels=qrels,
        has_relevance=True,
        meta={"description": "scientific abstracts + claim queries with human relevance judgments"},
    )


def load_agnews(max_docs: int = 5000, max_queries: int = 50) -> Corpus:
    """Fallback: real news text, no relevance labels (latency-only)."""
    from datasets import load_dataset

    ds = load_dataset("ag_news", split=f"train[:{max_docs}]")
    docs = {str(i): _truncate(row["text"]) for i, row in enumerate(ds)}

    # synthesise topical queries (no ground truth -> recall not measurable)
    seed_queries = [
        "stock market and corporate earnings",
        "international diplomacy and conflict",
        "football championship results",
        "new technology product launch",
        "oil prices and energy markets",
        "election campaign and politics",
        "scientific discovery in space",
        "company merger and acquisition",
    ]
    queries = {str(i): q for i, q in enumerate(seed_queries[:max_queries])}

    return Corpus(
        name="ag_news",
        docs=docs,
        queries=queries,
        qrels={},
        has_relevance=False,
        meta={"description": "news articles; no relevance labels, latency only"},
    )


def load_corpus(prefer: str = "scifact", max_docs: int = 5000,
                max_queries: int = 300) -> Corpus:
    """Load the preferred corpus, falling back to ag_news on any failure."""
    if prefer == "scifact":
        try:
            return load_scifact(max_docs=max_docs, max_queries=max_queries)
        except Exception as e:
            print(f"[corpus] scifact unavailable ({e}); falling back to ag_news")
    return load_agnews(max_docs=max_docs, max_queries=max_queries)
