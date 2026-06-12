# MCP Memory Benchmark Results Summary

## Overview
This document summarizes key findings from benchmarking git-mem against engram. Complete raw data is available in the `results/raw/` directory.

## Performance Metrics Summary

### Operation Latency (milliseconds, lower is better)

| Operation | git-mem (sync) | git-mem (async) | engram | Notes |
|-----------|----------------|-----------------|--------|-------|
| **SET** | 1.81 ms | **0.73 ms** | 0.50 ms | Async provides 2.5x speedup |
| **GET** | 0.24 ms | 0.23 ms | 0.12 ms | |
| **DELETE** | 0.98 ms | **0.33 ms** | 0.19 ms | Async provides 3.0x speedup |
| **LIST** | 0.18 ms | 0.19 ms | 0.09 ms | |
| **SEARCH** | ~4.2 ms | ~4.2 ms | ~6.2 ms | git-mem is 1.5x faster |

### Throughput (operations per second, higher is better)

| Operation | git-mem (sync) | git-mem (async) | engram |
|-----------|----------------|-----------------|--------|
| **SET** | 552 ops/sec | **1,365 ops/sec** | 1,981 ops/sec |
| **GET** | 4,085 ops/sec | 4,277 ops/sec | **8,552 ops/sec** |
| **DELETE** | 1,023 ops/sec | **3,056 ops/sec** | 5,245 ops/sec |
| **LIST** | 5,465 ops/sec | 5,146 ops/sec | **11,494 ops/sec** |

## Performance Evolution (git-mem SET Operations)

| Version | SET Latency | Improvement | Speedup |
|---------|-------------|-------------|---------|
| **Original** | 22.16 ms | Baseline | 1x |
| **v27fd005** (perf improvements) | 2.57 ms | +88.4% | 8.6x |
| **vdb7f982** (async writes) | 0.73 ms | +59.7% vs sync | 30x vs original |

## Key Findings

1. **Async writes provide significant performance gains**: 2.5x faster SET, 3.0x faster DELETE
2. **git-mem search outperforms engram**: 1.5x faster search operations
3. **Performance gap reduced**: git-mem with async writes is 1.5-3.6x slower than engram (vs 6-25x slower previously)
4. **GET operation regression**: git-mem GET slowed slightly from 0.17ms to 0.25ms through optimizations

## Benchmark Files

### Raw Data (Large JSON files - consider excluding from Git)
- `results/raw/async_benchmark_20260612_035921.json` - Async writes benchmark
- `results/raw/comparative_benchmark_20260612_030047.json` - Performance improvements benchmark  
- `results/raw/comparative_benchmark_20260611_225923.json` - Original benchmark

### Processed Results (Small JSON files - included in Git)
- `results/processed/git_mem_evolution_analysis.json` - Performance evolution analysis
- `results/processed/git_mem_performance_comparison.json` - Version comparison

## Recommendations

### For git-mem Users:
1. **Enable async writes**: Use `-async-writes` flag for production
2. **Tune flush interval**: Adjust based on write patterns
3. **Leverage search advantage**: git-mem search is faster than engram

### For git-mem Developers:
1. **Optimize LIST operations**: Slight regression in async mode
2. **Investigate GET regression**: Performance decreased through optimizations
3. **Consider selective async**: Different ops could have different sync/async preferences

## Test Configuration

- **Test data**: 100 items, 50 CRUD operations each
- **Concurrency**: 3 simultaneous threads
- **Search queries**: 4 different patterns
- **Environment**: Ubuntu 24.04, 4 vCPUs, 8GB RAM

## Analysis Reports

Complete analysis reports are available in `docs/final_report/`:
1. `benchmark_analysis_report.md` - Initial comparative analysis
2. `git_mem_performance_update_report.md` - Performance improvements analysis  
3. `async_writes_benchmark_report.md` - Async writes feature analysis

---

*Last Updated: 2026-06-12  
Benchmark Framework Version: 1.0.0*