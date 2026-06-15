# git-mem Benchmark Suite

Honest performance comparison of MCP memory servers — **git-mem** vs **engram** vs **@modelcontextprotocol/server-memory** — plus a **vector retrieval store** on the semantic-search axis.

git-mem is not the fastest option on raw latency, but it offers something the others don't: your entire memory store lives in a git repository that you can clone, branch, diff, and restore from any machine.

---

## Benchmark Results (2026-06-15)

50 operations per test, 100-item dataset, Linux container (2–3 vCPU). All five systems in one run, including the **vector retrieval store**.

> **These are CRUD micro-operations on tiny synthetic data.** The `vector-store ‡` column runs in-process with the *non-semantic hashing* embedder, so its numbers are a best-case floor — embedding (the dominant real cost) is essentially free here and SEARCH isn't doing semantic work. **For the honest vector-store evaluation — a real `sentence-transformers` model on a real corpus, scored on recall — see [Real-world retrieval: semantic vs keyword](#real-world-retrieval-semantic-vs-keyword-measured).** Read the column below for operation *shape* (‡), not as a latency win.

### Latency (mean ms) — lower is better

| Operation | git-mem sync | git-mem async | engram | mcp-server-memory | vector-store ‡ |
|---|---|---|---|---|---|
| **WRITE** | 2.32 ms | 0.50 ms ★ | 7.25 ms | 1.97 ms | 0.39 ms |
| **READ** | 0.12 ms ★ † | 0.40 ms | 7.09 ms | 1.03 ms | 0.00 ms |
| **SEARCH** | 1.20 ms ★ | 2.30 ms | 12.11 ms | 6.82 ms | 1.00 ms |
| **DELETE** | 1.55 ms | 0.33 ms | 0.23 ms ★ | 2.66 ms | 0.02 ms |
| **LIST** | 0.19 ms | 0.13 ms ★ | 2.79 ms | 4.47 ms | 0.00 ms |

### Throughput (ops/s) — higher is better

| Operation | git-mem sync | git-mem async | engram | mcp-server-memory | vector-store ‡ |
|---|---|---|---|---|---|
| **WRITE** | 431 | 2,019 ★ | 138 | 507 | 2,588 |
| **READ** | 8,049 ★ | 2,494 | 141 | 974 | 363,598 |
| **SEARCH** | 836 ★ | 435 | 83 | 147 | 1,001 |
| **DELETE** | 646 | 2,991 | 4,289 ★ | 376 | 50,933 |
| **LIST** | 5,157 | 7,502 ★ | 358 | 224 | 249,432 |

### p95 latency (ms) — tail behaviour

| Operation | git-mem sync | git-mem async | engram | mcp-server-memory | vector-store ‡ |
|---|---|---|---|---|---|
| **WRITE** | 4.63 | 0.91 ★ | 15.65 | 4.58 | 0.26 |
| **READ** | 0.28 ★ | 2.64 | 16.47 | 2.97 | 0.01 |
| **SEARCH** | 1.61 ★ | 5.76 | 18.43 | 14.86 | 3.11 |
| **DELETE** | 5.87 | 0.35 | 0.28 ★ | 5.57 | 0.06 |
| **LIST** | 0.19 | 0.13 ★ | 2.79 | 4.47 | 0.00 |

★ = fastest of the four **MCP-transport** systems (apples-to-apples; the vector store is excluded from ★ — see ‡).  
† engram has no direct key lookup — READ is `mem_search(query=key, limit=1)`, which includes full-text search overhead.  
‡ **The vector store runs in-process (no MCP JSON-RPC round-trip) and, in this run, uses the cheap non-semantic hashing embedder.** Its absolute latencies are therefore *not directly comparable* to the subprocess-based MCP servers — most of its apparent edge is the missing IPC hop, not algorithmic superiority. Read its column for **operation *shape*** (note WRITE and SEARCH carry the embedding cost while READ/DELETE/LIST are near-free id lookups), not for a latency win. With a real `sentence-transformers` model, WRITE and SEARCH would be **markedly slower** — that is the true price of semantic retrieval.

---

## What the numbers mean

**WRITE** — git-mem-async leads the MCP systems (0.50 ms) by batching commits in a 10 ms window; git-mem-sync pays per-write commit cost (2.32 ms). engram is slowest (7.25 ms) — a SQLite transaction plus FTS index update per write. The vector store's 0.39 ms is in-process *and* uses the cheap hashing embedder; a semantic model would dominate this number.

**READ** — git-mem-sync is fastest among MCP systems (0.12 ms) via in-memory cache. mcp-server-memory is ~8× slower (file scan); engram ~60× slower because it has no direct key lookup (read = full-text search). The vector store's READ is a bare dict lookup, so it carries no embedding cost at all.

**SEARCH** — this is the operation that matters. Among MCP systems git-mem scans git blobs fastest (1.20 ms); mcp-server-memory (6.82 ms) and engram (12.11 ms) run heavier full-text passes. The vector store does *semantic* nearest-neighbour search — a fundamentally different query (match on meaning, not tokens) — but only when backed by a real embedding model. In this run the hashing embedder makes it keyword-overlap-ish, so treat its 1.00 ms as a floor, not a representative semantic-search cost.

**DELETE** — engram is fastest (0.23 ms, soft-delete flag flip); git-mem-async batches removal commits (0.33 ms). mcp-server-memory rewrites its whole JSONL file (2.66 ms). The vector store drops a row + payload.

**LIST** — git-mem-async leads the MCP systems (0.13 ms, memory-resident key index); engram and mcp-server-memory both exceed 2 ms.

> **Run-to-run variance** on this shared container is significant (±2× on sub-millisecond ops is normal). Treat these as order-of-magnitude, and reproduce with `python3 run_benchmark.py`.

---

## Why choose git-mem despite slower writes?

| You want… | Best choice |
|---|---|
| Memory that survives restarts, is clonable, branchable, and has full audit history | **git-mem** |
| Fastest writes and reads; SQLite file is OK | **git-mem-async** (if git) or **mcp-server-memory** |
| Structured entity/relation graph, not just K/V | **mcp-server-memory** |
| Fastest full-text search | **mcp-server-memory** |
| Session-scoped observations with soft-delete | **engram** |

---

## Systems compared

| System | Storage model | Portability |
|---|---|---|
| **git-mem (sync)** | Key-value + git commits | Highest — full git history, push/pull to any git host |
| **git-mem (async)** | Key-value + git commits (batched 10 ms) | Highest |
| **engram** | Session / observation + SQLite | Medium — portable file, no versioning |
| **mcp-server-memory** | Knowledge graph + JSONL file | Medium — portable file, no versioning |
| **vector-store** | Dense vectors + similarity index | Low — opaque embeddings, no git history |

---

## Vector retrieval store

The fifth system is a **vector retrieval store** — the storage model behind RAG. It is not an MCP subprocess but an embedded, in-process index (`test_harness/vector_store.py`) wrapped in the same adapter interface so it is timed identically to the MCP servers.

The point of including it is to make the real tradeoff explicit. A vector store does one thing the key-value systems can't: **semantic SEARCH**. It pays for that on every WRITE.

| Operation | What the vector store does | Cost shape |
|---|---|---|
| **WRITE** | Embed the document (text → dense vector), then insert | Slowest op — embedding dominates |
| **READ** | id-keyed dictionary lookup | O(1), no embedding |
| **SEARCH** | Embed the query, return nearest neighbours by cosine similarity | The one op it's built to win — *semantic*, not substring |
| **DELETE** | id-keyed removal from the index | O(1)–O(N) |
| **LIST** | Enumerate ids | O(N) |

**Honest framing:** WRITE is structurally slower than a plain K/V store because of the embedding step, and SEARCH is the only place a vector store has an inherent advantage — it matches on *meaning*, where git-mem/engram/mcp-server-memory match on *tokens*. For the workloads in this suite (key-value CRUD), that advantage doesn't show up; this system is here to mark the boundary of what the others are *not* designed to do.

**Backends (auto-selected, best available wins):**

| Layer | Preferred | Fallback (always available) |
|---|---|---|
| Vector index | `chromadb` (embedded HNSW) | numpy exact brute-force cosine |
| Embedder | `sentence-transformers` (real semantic) | hashing bag-of-words (deterministic, **non-semantic**) |

Out of the box, with only numpy installed, you get the numpy index + hashing embedder — fully runnable with **zero extra dependencies**. The hashing embedder only matches documents that share literal tokens, so its SEARCH results approximate keyword overlap rather than true semantic recall; the runner prints a clear note when it is in use. Installing `sentence-transformers` and/or `chromadb` (see `requirements.txt`) upgrades the respective layer with no other changes. Configure via the `vector` block in `config/benchmark_config.json` (`backend`, `embedder`, `dim`).

> ⚠️ **The vector-store column in the CRUD tables above is a best-case floor, not a real vector system.** Run in-process with the *non-semantic hashing* embedder over tiny synthetic data, it measures "numpy + a token hash" — embedding (the dominant real cost) is essentially free and SEARCH isn't doing semantic work. For an honest measurement with a **real embedding model on a real corpus**, see the next section.

---

## Real-world retrieval: semantic vs keyword (measured)

To answer "is the vector store actually any good?" the CRUD floor above is useless — it uses a non-semantic embedder over random strings. `run_retrieval_benchmark.py` instead runs a real retrieval workload and scores **retrieval quality**, not just speed:

- **Corpus:** [BeIR/scifact](https://github.com/beir-cellar/beir) — real scientific abstracts + natural-language claim queries with **human relevance judgments** (qrels), so recall is measurable.
- **Semantic:** `sentence-transformers/all-MiniLM-L6-v2` (384-dim) embeddings → **chromadb** HNSW index.
- **Keyword baseline:** in-process **BM25** — the same token-matching family that git-mem / engram / mcp-server-memory full-text search are built on.
- **Metrics:** index throughput, search latency, and **recall@k / MRR@10** against the qrels.

### Results — 500 docs, 50 labelled queries (2026-06-15)

CPU-only, 4-vCPU shared container, `all-MiniLM-L6-v2`.

| Metric | BM25 keyword | Semantic (MiniLM + chromadb) |
|---|---|---|
| **Index throughput** | 3,439 docs/s | **6 docs/s** |
| **Search latency (mean)** | **0.67 ms** | 203 ms |
| **Search latency (p95)** | **1.11 ms** | 654 ms |
| **recall@10** | 0.931 | **0.940** |
| **recall@100** | 0.980 | **1.000** |
| **MRR@10** | 0.879 | **0.895** |

### What this actually shows

- **Embedding is the real, dominant write cost.** Indexing is ~570× slower for the vector store (6 vs 3,439 docs/s), and **≈100 % of that time is the embedding model** — not chromadb. On this CPU that's ~170 ms/doc. The earlier CRUD "WRITE = 0.39 ms" number was the *hashing* embedder; a real model is ~400× slower. This is the price of admission, and it's why production systems batch embeddings or push them to a GPU/API.
- **Semantic search is real but not free.** ~200 ms/query of CPU inference vs sub-millisecond BM25 — a ~300× latency gap on this hardware. A GPU, a smaller model, or a hosted embedding API changes the absolute numbers a lot, but the *shape* (embed-then-search) stays.
- **Quality edge is real but modest here.** Semantic wins every quality metric (recall@10 +0.009, recall@100 +0.020, MRR@10 +0.016) — it retrieves *every* relevant doc by rank 100 where BM25 misses 2 %. But scifact is a **keyword-friendly** corpus (claims reuse the abstract's terminology), so this *understates* the semantic advantage you'd see on paraphrase-heavy or cross-vocabulary queries. The honest takeaway: on lexically-aligned data, a good keyword index is a very strong, far cheaper baseline; the vector store earns its cost as queries drift from the documents' wording.

> **Caveats:** single 500-doc run on a CPU-only shared box; absolute latencies are hardware-bound (expect 10–50× faster index/query on a GPU or batched API embedder). recall@k depends on the corpus — scifact favours keywords. Reproduce with `.venv/bin/python run_retrieval_benchmark.py --docs 500`.

---

## Quick start

```bash
pip install -r requirements.txt

# Basic CRUD benchmark (all 5 systems, incl. the vector retrieval store)
python3 run_benchmark.py

# Multi-agent scenario benchmarks
python3 run_multi_agent_benchmark.py

# Results saved to results/raw/benchmark_<timestamp>.json
```

**Real-world retrieval benchmark** (real embeddings + a real corpus — semantic vs keyword). This needs `sentence-transformers`, `chromadb`, and `datasets`, which pull in torch; on a PEP 668 system use a venv:

```bash
python3 -m venv .venv
.venv/bin/pip install sentence-transformers chromadb datasets

# Semantic (MiniLM + chromadb) vs BM25 keyword, scored on recall@k with
# human relevance labels over ~5k real scientific abstracts (BeIR/scifact)
.venv/bin/python run_retrieval_benchmark.py --docs 500     # ~500 docs, quick
.venv/bin/python run_retrieval_benchmark.py --docs 5000    # fuller corpus (slow on CPU)
```

### Multi-agent scenarios

`run_multi_agent_benchmark.py` simulates real-world multi-turn MCP usage:

| Scenario | Description | Agents | Ops |
|----------|-------------|--------|-----|
| Long Conversation | Single agent across many turns | 1 | ~50 |
| Multi-Agent Collaborative | Multiple agents sharing memory | 3–15 | ~50 |
| Agent Handoff | Task escalation across handlers | 4 | ~30 |
| Session Recovery | Agent resuming from previous session | 5 | ~60 |
| Concurrent Contention | Agents contending for shared keys | 10 | ~100 |
| Error Recovery | Agents recovering from failures | 5 | ~30 |
| Complex Search | Multiple search patterns | 3 | ~30 |
| Batch vs Streaming | Batched vs individual writes | 1 | ~100 |
| Large Payloads | Large data storage | 1 | ~6 |
| Special Characters | Unicode, emojis, edge cases | 1 | ~12 |
| Hierarchical Structure | Coordinator + workers | 5 | ~25 |
| Memory Eviction | Write/delete cycles | 1 | ~140 |

### Prerequisites

| System | Install |
|---|---|
| git-mem | `go install github.com/git-mem/git-mem@latest` |
| engram | `go install github.com/Gentleman-Programming/engram/cmd/engram@latest` |
| mcp-server-memory | fetched automatically via `npx -y @modelcontextprotocol/server-memory` (requires Node.js) |
| vector-store (CRUD) | none required (numpy only); optional `pip install sentence-transformers chromadb` for semantic embeddings + ANN index |
| retrieval benchmark | `sentence-transformers`, `chromadb`, `datasets` (see venv note in Quick start) |

---

## How it works

Each system is tested via its own native MCP tools through a per-server adapter (`test_harness/adapters.py`):

| Operation | git-mem | engram | mcp-server-memory | vector-store |
|---|---|---|---|---|
| WRITE | `memSet` | `mem_save` | `create_entities` | `embed + add` |
| READ | `memGet` | `mem_search(key, limit=1)` † | `open_nodes` | `get(id)` |
| SEARCH | `memSearch` | `mem_search` | `search_nodes` | `embed + nearest-neighbour` |
| DELETE | `memDelete` | `mem_delete(obs_id)` | `delete_entities` | `delete(id)` |
| LIST | `memList` | `mem_context` | `read_graph` | `list ids` |

† engram has no key-based read; we search by title. This inflates its read latency relative to the others.

The vector-store column is an in-process embedded index, not an MCP subprocess — see [Vector retrieval store](#vector-retrieval-store) above. Its WRITE and SEARCH both pay an embedding cost; the other three operations are plain id-keyed dictionary work.

Stats collected per operation: mean, median, p75, p95, p99 latency and throughput (ops/s).

---

## Reproducing results

```bash
rm -rf /tmp/benchmark-git-mem-* /tmp/benchmark-mcp-server-memory.jsonl
python3 run_benchmark.py
```

---

## Repository structure

```
git-mem-bench/
├── run_benchmark.py               # Basic CRUD benchmark entry point
├── run_multi_agent_benchmark.py   # Multi-agent scenario entry point
├── run_retrieval_benchmark.py     # Real-world retrieval: semantic vs keyword
├── config/
│   ├── benchmark_config.json      # Server commands and adapter types
│   └── multi_agent_config.json    # Multi-agent scenario configuration
├── test_harness/
│   ├── adapters.py                # Per-server operation adapters
│   ├── benchmark_suite.py         # Basic test orchestration
│   ├── mcp_client.py              # MCP JSON-RPC client + stats
│   ├── vector_store.py            # In-process vector retrieval store + embedders
│   ├── corpus.py                  # Real-text corpus loader (BeIR/scifact, ag_news)
│   └── multi_agent_benchmark.py   # Multi-agent benchmark suite
└── results/
    └── raw/                       # JSON output from each run
```

---

## License

MIT
