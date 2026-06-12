# Quick Start Guide

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/mcp-memory-benchmark.git
   cd mcp-memory-benchmark
   ```

2. **Run setup script**:
   ```bash
   ./setup.sh
   ```

3. **Activate virtual environment**:
   ```bash
   source venv/bin/activate
   ```

## Running Benchmarks

### Basic Comparison (git-mem vs engram)
```bash
python3 run_benchmark.py
```

### Async Writes Test (git-mem sync vs async)
```bash
python3 run_async_benchmark.py
```

### Performance Analysis
```bash
# Compare before/after performance improvements
python3 compare_performance.py

# Analyze performance evolution
python3 compare_evolution.py
```

## Customizing Benchmarks

Edit `config/benchmark_config.json` to:
- Add new MCP servers
- Change test parameters
- Enable/disable specific tests

## Results

Benchmark results are saved in `results/raw/` directory. Key findings are summarized in:
- `results/RESULTS_SUMMARY.md` - Executive summary
- `docs/final_report/` - Detailed analysis reports
- `results/processed/` - Aggregated comparison data

## Adding New MCP Servers

1. Install the MCP server
2. Add configuration to `config/benchmark_config.json`
3. Test with benchmark framework
4. Run comparison analysis

## Repository Structure

```
mcp-memory-benchmark/
├── README.md                    # Main documentation
├── setup.sh                     # Setup script
├── requirements.txt             # Python dependencies
├── config/                      # Benchmark configurations
├── test_harness/                # Benchmark framework
├── run_benchmark.py            # Main benchmark runner
├── run_async_benchmark.py      # Async writes benchmark
├── compare_performance.py      # Performance comparison
├── compare_evolution.py        # Evolution analysis
├── results/                    # Benchmark results
└── docs/                       # Analysis reports
```

## Requirements

- Python 3.10+
- git-mem (`go install github.com/imran31415/git-mem/cmd/git-mem@latest`)
- engram (`go install github.com/Gentleman-Programming/engram/cmd/engram@latest`)
- Optional: psutil for resource monitoring

## Contributing

1. Fork the repository
2. Add new test scenarios or MCP servers
3. Submit pull request

## License

Open source - see LICENSE file