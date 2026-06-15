# git-mem Benchmark Suite

Honest performance comparison of MCP memory servers — **git-mem** vs **engram** vs **@modelcontextprotocol/server-memory** — plus a **vector retrieval store** on the semantic-search axis.

git-mem is not the fastest option on raw latency, but it offers something the others don't: your entire memory store lives in a git repository that you can clone, branch, diff, and restore from any machine.

---

## Benchmark Results (2026-06-14)

50 operations per test, 100-item dataset, Linux container (2–3 vCPU).

### Latency (mean ms) — lower is better

| Operation | git-mem sync | git-mem async | engram | mcp-server-memory |
|-----------|-------------|--------------|--------|-------------------|
| **WRITE** | 1.69 ms | **0.39 ms** ★ | 32.73 ms | 1.72 ms |
| **READ** | 0.11 ms | **0.09 ms** ★ | 38.55 ms † | 1.10 ms |
| **SEARCH** | 2.18 ms | 2.38 ms | 36.58 ms | **1.74 ms** ★ |
| **DELETE** | 1.50 ms | **0.20 ms** ★ | 0.23 ms | 3.43 ms |
| **LIST** | 0.21 ms | **0.17 ms** ★ | 3.48 ms | 1.52 ms |

### Throughput (ops/s) — higher is better

| Operation | git-mem sync | git-mem async | engram | mcp-server-memory |
|-----------|-------------|--------------|--------|-------------------|
| **WRITE** | 592 | **2,562** ★ | 31 | 580 |
| **READ** | 9,304 | **10,783** ★ | 26 | 907 |
| **SEARCH** | 459 | 421 | 27 | **573** ★ |
| **DELETE** | 667 | **4,925** ★ | 4,383 | 292 |
| **LIST** | 4,803 | **5,793** ★ | 287 | 656 |

### p95 latency (ms) — tail behaviour

| Operation | git-mem sync | git-mem async | engram | mcp-server-memory |
|-----------|-------------|--------------|--------|-------------------|
| **WRITE** | 2.95 | **0.55** ★ | 59.83 | 2.65 |
| **READ** | 0.17 | **0.16** ★ | 55.62 | 1.57 |
| **SEARCH** | 2.54 | 2.84 | 47.91 | **2.09** ★ |
| **DELETE** | 2.93 | **0.31** ★ | 0.34 | 15.16 |
| **LIST** | 0.21 | **0.17** ★ | 3.48 | 1.52 |

★ = fastest for this operation  
† engram has no direct key lookup — READ is implemented as `mem_search(query=key, limit=1)`, which includes full-text search overhead.

---

## What the numbers mean

**WRITE** — git-mem-async is 4× faster than git-mem-sync (0.39 ms vs 1.69 ms) by batching commits in a 10 ms window. engram is by far the slowest (32 ms) because it opens a SQLite transaction and updates FTS indexes on every write. mcp-server-memory is comparable to git-mem-sync.

**READ** — Both git-mem variants are fastest (~0.1 ms, ~10 000 ops/s) via in-memory cache. mcp-server-memory is 12× slower (file scan). engram is 430× slower because it has no direct key lookup — read latency reflects a full-text search.

**SEARCH** — mcp-server-memory is fastest (1.74 ms) scanning its JSONL file. git-mem scans git blobs (2.2 ms). engram is ~21× slower than the fastest because it runs FTS across its SQLite store.

**DELETE** — git-mem-async batches removal commits (0.20 ms). engram does a soft-delete by flag flip in SQLite (0.23 ms, nearly as fast). mcp-server-memory rewrites the whole JSONL file on each delete (3.43 ms, highest p95 at 15 ms).

**LIST** — git-mem-async is fastest (0.17 ms, memory-resident key index). engram and mcp-server-memory both take >1 ms.

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

---

## Quick start

```bash
pip install -r requirements.txt

# Basic benchmark (all 5 systems, incl. the vector retrieval store)
python3 run_benchmark.py

# Multi-agent scenario benchmarks
python3 run_multi_agent_benchmark.py

# Results saved to results/raw/benchmark_<timestamp>.json
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
| vector-store | none required (numpy only); optional `pip install sentence-transformers chromadb` for semantic embeddings + ANN index |

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
├── run_benchmark.py               # Basic benchmark entry point
├── run_multi_agent_benchmark.py   # Multi-agent scenario entry point
├── config/
│   ├── benchmark_config.json      # Server commands and adapter types
│   └── multi_agent_config.json    # Multi-agent scenario configuration
├── test_harness/
│   ├── adapters.py                # Per-server operation adapters
│   ├── benchmark_suite.py         # Basic test orchestration
│   ├── mcp_client.py              # MCP JSON-RPC client + stats
│   ├── vector_store.py            # In-process vector retrieval store + embedders
│   └── multi_agent_benchmark.py   # Multi-agent benchmark suite
└── results/
    └── raw/                       # JSON output from each run
```

---

## License

MIT
