# MCP Memory Solutions Benchmark Framework

A comprehensive benchmarking framework for evaluating MCP (Model Context Protocol) memory servers. This repository contains tools, scripts, and results for benchmarking git-mem against other MCP memory solutions like engram.

## Overview

This benchmark suite helps compare performance characteristics of different MCP memory servers, focusing on:
- **Basic CRUD operations** (SET, GET, DELETE, LIST)
- **Search performance** 
- **Concurrent access** 
- **Special features** (git-mem code mode, engram full-text search)

## Benchmarked Solutions

1. **git-mem** (https://github.com/imran31415/git-mem)
   - Git-backed memory with version control
   - Unique "code mode" for batch operations
   - Tested with sync and async writes (`-async-writes` flag)

2. **engram** (https://github.com/Gentleman-Programming/engram)
   - SQLite-based memory with FTS5 full-text search
   - 19 MCP tools in agent profile
   - HTTP API, CLI, and TUI interfaces

## Key Findings

### Performance Comparison Summary

| Operation | git-mem (async) | engram | Ratio | Notes |
|-----------|-----------------|--------|-------|-------|
| **SET** | 0.73 ms | 0.50 ms | 1.5x slower | Async writes provide 2.5x speedup |
| **GET** | 0.23 ms | 0.12 ms | 2.0x slower | |
| **DELETE** | 0.33 ms | 0.19 ms | 1.7x slower | Async provides 3.0x speedup |
| **LIST** | 0.19 ms | 0.09 ms | 2.2x slower | |
| **SEARCH** | **~4.2 ms** | ~6.2 ms | **1.5x faster** | git-mem advantage |

### Performance Evolution (git-mem)
1. **Original**: SET @ 22.16ms (baseline)
2. **After perf improvements**: SET @ 2.57ms (**8.6x faster**)
3. **After async writes**: SET @ 0.73ms (**30x faster** than original)

## Repository Structure

```
mcp-memory-benchmark/
├── README.md                    # This file
├── run_benchmark.py            # Main benchmark runner
├── run_async_benchmark.py      # Async writes benchmark
├── compare_performance.py      # Performance comparison script
├── compare_evolution.py        # Performance evolution analysis
├── config/
│   └── benchmark_config.json   # Server configurations
├── test_harness/
│   ├── mcp_client.py          # Generic MCP client wrapper
│   └── benchmark_suite.py     # Benchmark test suite
├── results/
│   ├── raw/                   # Raw benchmark data (JSON)
│   ├── processed/             # Processed comparison data
│   └── visualizations/        # Charts and graphs (to be added)
└── docs/
    └── final_report/          # Comprehensive analysis reports
```

## Quick Start

### Prerequisites
- Python 3.10+
- git-mem installed (`go install github.com/imran31415/git-mem/cmd/git-mem@latest`)
- engram installed (`go install github.com/Gentleman-Programming/engram/cmd/engram@latest`)

### Running Benchmarks

1. **Basic benchmark** (git-mem vs engram):
   ```bash
   python3 run_benchmark.py
   ```

2. **Async writes benchmark** (git-mem sync vs async):
   ```bash
   python3 run_async_benchmark.py
   ```

3. **Compare results**:
   ```bash
   python3 compare_performance.py
   ```

4. **Performance evolution analysis**:
   ```bash
   python3 compare_evolution.py
   ```

## Configuration

Edit `config/benchmark_config.json` to:
- Add/remove MCP servers
- Configure test parameters
- Enable/disable specific tests

Example configuration:
```json
{
  "servers": {
    "git-mem-sync": {
      "command": ["git-mem", "-repo", "/tmp/benchmark-git-mem-sync"],
      "enabled": true,
      "description": "git-mem with synchronous writes"
    },
    "git-mem-async": {
      "command": ["git-mem", "-repo", "/tmp/benchmark-git-mem-async", "-async-writes", "10ms"],
      "enabled": true,
      "description": "git-mem with async writes (10ms flush)"
    }
  },
  "benchmark": {
    "test_data_size": 100,
    "crud_operations": 50,
    "search_queries": ["test", "item", "document", "benchmark"],
    "concurrent_threads": greater3,
    "output_directory": "./results"
  }
}
```

## Test Methodology

### Test Categories
1. **Basic CRUD**: 50 SET/GET/DELETE/LIST operations each
2. **Search**: 4 different query patterns
3. **Concurrent Access**: 3 simultaneous clients
4. **Feature Testing**: Tool discovery and special features

### Test Data
- **Size**: 100 test items
- **Types**: Small, medium, and large values
- **Patterns**: Random keys, structured values
- **Generation**: Automated via `generate_test_data()`

### Measurement
- **Latency**: `time.perf_counter()` for nanosecond precision
- **Throughput**: Operations per second calculation
- **Success Rate**: Error tracking and recovery
- **Statistical Analysis**: Mean, median, std dev, percentiles

## Results Analysis

### Included Reports
1. **`docs/final_report/benchmark_analysis_report.md`**: Initial comparative analysis
2. **`docs/final_report/git_mem_performance_update_report.md`**: git-mem performance improvements
3. **`docs/final_report/async_writes_benchmark_report.md`**: Async writes feature analysis

### Raw Data
- **`results/raw/`**: Complete benchmark results in JSON format
- **`results/processed/`**: Aggregated comparison data

## Extending the Framework

### Adding New MCP Servers
1. Install the MCP server
2. Add configuration to `config/benchmark_config.json`
3. Test basic MCP protocol compliance
4. Run benchmark suite

### Adding New Test Scenarios
1. Create new test methods in `benchmark_suite.py`
2. Add to benchmark runner in `run_benchmark.py`
3. Update configuration for new parameters
4. Run and validate results

### Custom Analysis
1. Use raw JSON data in `results/raw/`
2. Create custom analysis scripts
3. Generate visualizations
4. Add to `docs/final_report/`

## Limitations

1. **Resource Monitoring**: Memory/CPU metrics not captured (psutil unavailable)
2. **Scale**: Limited to 100 items, 50 operations
3. **Concurrency**: Simplified 3-thread test
4. **Durability**: Crash recovery not tested

## Future Work

1. **Resource Monitoring**: Add psutil for memory/CPU tracking
2. **Scale Testing**: 10k+ entries, larger values
3. **Concurrency Stress**: 10+ simultaneous clients
4. **More Solutions**: Test SimpleMem, codebase-memory-mcp
5. **Visualizations**: Generate charts and graphs
6. **Automation**: CI/CD pipeline for regular benchmarking

## Contributing

1. Fork the repository
2. Add new MCP server configurations
3. Implement additional test scenarios
4. Improve analysis and visualization
5. Submit pull request

## License

This benchmark framework is open source and available for use and modification.

## Acknowledgments

- **git-mem**: https://github.com/imran31415/git-mem
- **engram**: https://github.com/Gentleman-Programming/engram
- **MCP Protocol**: https://modelcontextprotocol.io/

---

*Benchmark Framework Version: 1.0.0  
Last Updated: 2026-06-12  
Test Environment: Ubuntu 24.04, 4 vCPUs, 8GB RAM*