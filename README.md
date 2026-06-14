# git-mem Benchmark Suite

performance comparison of MCP memory servers** — git-mem vs engram vs @modelcontextprotocol/server-memory.

The goal is a clear, reproducible picture of the **performance tradeoffs** so you can make an informed choice. git-mem is not the fastest option on raw latency, but it offers something the others don't: your entire memory store lives in a git repository that you can clone, branch, diff, and restore from any machine.

---

## Systems compared

| System | Storage model | Portability | Tested via |
|---|---|---|---|
| **git-mem (sync)** | Key-value + git commits | Highest — full git history, push to any host | `memSet` / `memGet` / `memSearch` / `memDelete` |
| **git-mem (async)** | Key-value + git commits (batched 10 ms) | Highest | Same tools, async flush |
| **engram** | Session / observation + SQLite | Medium — portable SQLite file | `mem_save` / `mem_search` / `mem_delete` |
| **mcp-server-memory** | Knowledge graph + JSONL file | Medium — single file, no versioning | `create_entities` / `open_nodes` / `search_nodes` / `delete_entities` |

> **Important note on engram READ:** engram has no direct key-lookup. The benchmark's READ operation is implemented as `mem_search(query=key, limit=1)`, which includes full-text search overhead. All other READ timings use direct key access.

---

## Latest results (2026-06-14)

```
Op        git-mem-sync               git-mem-async              engram                     mcp-server-memory
------------------------------------------------------------------------------------------------------------------------------------------
WRITE      1.85ms  p95= 2.90   541/s  *0.53ms  p95= 1.00  1885/s   6.67ms  p95=12.27   150/s   1.80ms  p95= 2.39   556/s
READ      *0.14ms  p95= 0.18  7016/s   0.15ms  p95= 0.27  6479/s   6.00ms  p95= 9.39   167/s   1.00ms  p95= 1.65  1003/s
SEARCH     9.69ms  p95=11.57   103/s  10.60ms  p95=13.03    94/s   5.68ms  p95= 6.90   176/s  *1.94ms  p95= 2.72   515/s
DELETE     1.32ms  p95= 2.22   756/s  *0.45ms  p95= 0.60  2203/s   0.20ms  p95= 0.32  5029/s   1.48ms  p95= 2.37   678/s
LIST      *0.28ms  p95= 0.28  3555/s   0.49ms  p95= 0.49  2027/s   1.78ms  p95= 1.78   561/s   1.43ms  p95= 1.43   700/s

* = fastest for this operation
```

### What the numbers mean

**WRITE** — git-mem-async wins (0.53 ms). Every git-mem write commits to git; async mode batches those commits over a 10 ms window, giving 3.5× the throughput of sync mode. engram is slowest here (6.67 ms) because it opens a SQLite transaction and runs FTS index updates. mcp-server-memory writes to a JSONL file and is comparable to git-mem-sync.

**READ** — git-mem wins decisively (0.14 ms, ~7 000 ops/s) because it caches values in memory and serves reads without hitting disk. mcp-server-memory is 7× slower (file scan). engram is 43× slower — because it has no direct key lookup; this benchmark measures search-by-title latency instead.

**SEARCH** — mcp-server-memory wins (1.94 ms). engram is 3× slower than mcp-server-memory. Both git-mem variants are 5-6× slower than mcp-server-memory; git-mem's full-text search scans git blobs rather than an index.

**DELETE** — engram is fastest (0.20 ms) because its deletes are soft-deletes (a flag flip in SQLite). git-mem-async batches the removal commit (0.45 ms). mcp-server-memory rewrites the JSONL file on delete (1.48 ms). git-mem-sync commits synchronously (1.32 ms).

**LIST** — git-mem-async is fastest (0.28 ms, memory-resident key index). Everything else takes >1 ms.

---

## When to use what

| You want… | Best choice |
|---|---|
| Memory that survives pod restarts, can be cloned to another machine, and has full audit history | **git-mem** |
| Best raw write throughput and you're OK with a SQLite file | **engram** (but note slow reads-by-key) |
| Structured entity/relation graph, not just K/V | **mcp-server-memory** |
| Fastest full-text search | **mcp-server-memory** |
| Fastest direct key reads | **git-mem** |

---

## Quick start

```bash
# Install dependencies
pip install -r requirements.txt

# Run basic benchmark (all 4 systems)
python3 run_benchmark.py

# Run multi-agent benchmarks (simulates real-world MCP scenarios)
python3 run_multi_agent_benchmark.py

# Results are saved to results/raw/benchmark_<timestamp>.json
```

### Multi-Agent Scenarios

The `run_multi_agent_benchmark.py` script simulates real-world MCP multi-turn use cases with:

| Scenario | Description | Agents | Operations |
|----------|-------------|--------|------------|
| **Long Conversation** | Single agent maintaining context across turns | 1 | ~50 |
| **Multi-Agent Collaborative** | Multiple agents sharing memory | 3-15 | ~50 |
| **Agent Handoff** | Task escalation across handlers | 4 | ~30 |
| **Session Recovery** | Agent resuming from previous sessions | 5 | ~60 |
| **Concurrent Contention** | Agents contending for shared keys | 10 | ~100 |
| **Error Recovery** | Agents recovering from failures | 5 | ~30 |
| **Complex Search** | Multiple search patterns | 3 | ~30 |
| **Batch vs Streaming** | Batched vs individual writes | 1 | ~100 |
| **Large Payloads** | Testing large data storage | 1 | ~6 |
| **Special Characters** | Unicode, emojis, edge cases | 1 | ~12 |
| **Hierarchical Structure** | Coordinator + workers | 5 | ~25 |
| **Memory Eviction** | Write/delete cycles | 1 | ~140 |

Each scenario includes mock LLM decision making with realistic think times and simulated agent behavior.

### Prerequisites

| System | Install |
|---|---|
| git-mem | `go install github.com/git-mem/git-mem@latest` or [releases](https://github.com/git-mem/git-mem/releases) |
| engram | `go install github.com/Gentleman-Programming/engram/cmd/engram@latest` |
| mcp-server-memory | auto-fetched via `npx -y @modelcontextprotocol/server-memory` (Node.js required) |

---

## How the benchmark works

The framework uses a **per-server adapter** (`test_harness/adapters.py`) that maps four logical operations to each system's actual MCP tools:

| Logical op | git-mem | engram | mcp-server-memory |
|---|---|---|---|
| WRITE | `memSet` | `mem_save` | `create_entities` |
| READ | `memGet` | `mem_search(key, limit=1)` ¹ | `open_nodes` |
| SEARCH | `memSearch` | `mem_search` | `search_nodes` |
| DELETE | `memDelete` | `mem_delete(obs_id)` ² | `delete_entities` |
| LIST | `memList` | `mem_context` | `read_graph` |

¹ engram has no key-based read; we search by title. This inflates read latency for engram.  
² engram deletes by observation_id returned at write time; the adapter tracks this mapping.

Each operation is measured with `time.perf_counter`, and stats include mean, median, p75, p95, p99, and throughput (ops/s).

---

## Repository structure

```
git-mem-bench/
├── run_benchmark.py               # Main entry point (basic benchmarks)
├── run_multi_agent_benchmark.py  # Multi-agent scenario benchmarks
├── config/
│   ├── benchmark_config.json     # Server commands, adapter types
│   └── multi_agent_config.json    # Multi-agent scenario configuration
├── test_harness/
│   ├── adapters.py               # Per-server operation adapters
│   ├── benchmark_suite.py        # Basic test orchestration
│   ├── mcp_client.py             # MCP JSON-RPC client + stats
│   └── multi_agent_benchmark.py  # Multi-agent benchmark suite
└── results/
    └── raw/                       # JSON output from each run
```

---

## Reproducing results

```bash
# Clean state
rm -rf /tmp/benchmark-git-mem-*  /tmp/benchmark-mcp-server-memory.jsonl

# Run
python3 run_benchmark.py
```

Results vary by hardware and load. On this machine (Linux container, 2-3 vCPU):
- git-mem latencies are dominated by git process spawn + commit overhead
- engram latencies include SQLite FTS index maintenance
- mcp-server-memory latencies include Node.js startup (amortised after warm-up)

---

## License

MIT
