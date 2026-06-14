#!/usr/bin/env python3
"""
MCP Memory Benchmark Runner

Compares git-mem, engram, and @modelcontextprotocol/server-memory across
equivalent logical operations (WRITE, READ, SEARCH, DELETE, LIST).

Each system uses its native MCP tool API via a server-specific adapter,
so the benchmark tests real behaviour rather than forcing a common API.
"""
import json
import os
import sys
import time
from datetime import datetime

# Locate this file's directory and add the test_harness sibling to sys.path
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO_ROOT, "test_harness"))

try:
    from benchmark_suite import MCPMemoryBenchmark, generate_test_data
except ImportError as e:
    print(f"Error importing benchmark_suite: {e}")
    sys.exit(1)


def load_config(config_file: str = None) -> dict:
    if config_file is None:
        config_file = os.path.join(REPO_ROOT, "config", "benchmark_config.json")
    with open(config_file) as f:
        return json.load(f)


def print_comparison_table(all_results: dict) -> None:
    """Print a side-by-side latency and throughput table."""
    ops = ["write", "read", "search", "delete", "list"]
    servers = list(all_results.keys())

    col_w = 28
    label_w = 10

    divider = "-" * (label_w + col_w * len(servers))
    print("\n" + "=" * len(divider))
    print("LATENCY COMPARISON   mean / p95 / throughput   (* = fastest for this op)")
    print("=" * len(divider))

    # Header
    print(f"{'Op':<{label_w}}", end="")
    for s in servers:
        print(f"{s[:col_w-1]:<{col_w}}", end="")
    print()
    print(divider)

    for op in ops:
        # find best (lowest) non-zero mean
        means = {s: all_results[s].get(op, {}).get("latency_mean_ms", 0) for s in servers}
        valid = [m for m in means.values() if m > 0]
        best = min(valid) if valid else None

        print(f"{op.upper():<{label_w}}", end="")
        for s in servers:
            stats = all_results[s].get(op, {})
            mean = stats.get("latency_mean_ms", 0)
            p95  = stats.get("latency_p95_ms", 0)
            tput = stats.get("throughput_ops_sec", 0)
            sr   = stats.get("success_rate", 0)
            if mean == 0 and sr == 0:
                cell = "n/a"
            else:
                star = "*" if (best is not None and abs(mean - best) < 0.001) else " "
                cell = f"{star}{mean:6.2f}ms  p95={p95:5.2f}  {tput:5.0f}/s"
            print(f"{cell:<{col_w}}", end="")
        print()

    print(divider)


def print_tradeoff_summary(servers_config: dict) -> None:
    print("\n" + "=" * 70)
    print("SYSTEM TRADEOFF SUMMARY")
    print("=" * 70)
    for name, cfg in servers_config.items():
        if not cfg.get("enabled"):
            continue
        print(f"\n  {name}")
        print(f"    Storage : {cfg.get('storage_model', 'unknown')}")
        print(f"    Portable: {cfg.get('portability', 'unknown')}")
        print(f"    Notes   : {cfg.get('description', '')}")


def main() -> None:
    print("MCP Memory Server Benchmark")
    print("=" * 70)
    print(f"Comparing git-mem, engram, and @modelcontextprotocol/server-memory")
    print(f"Each system is tested via its own native MCP tool API.")
    print()

    config = load_config()
    bench_cfg = config["benchmark"]
    servers_cfg = config["servers"]

    benchmark = MCPMemoryBenchmark()
    benchmark.test_data = generate_test_data(bench_cfg["test_data_size"])

    print(f"Config: {bench_cfg['test_data_size']} test items, "
          f"{bench_cfg['crud_operations']} CRUD ops, "
          f"{len(bench_cfg['search_queries'])} search queries")
    print()

    # ----------------------------------------------------------------
    # Start servers
    # ----------------------------------------------------------------
    ok_servers = []
    for name, cfg in servers_cfg.items():
        if not cfg.get("enabled", False):
            continue
        print(f"Starting {name}...")
        env = cfg.get("env")
        if benchmark.setup_client(
            name, cfg["command"],
            adapter_type=cfg.get("adapter_type", "git-mem"),
            env=env,
        ):
            ok_servers.append(name)
            print(f"  ✓ {name} ready")
        else:
            print(f"  ✗ {name} failed to start")

    if not ok_servers:
        print("\nNo servers started — exiting.")
        return

    # ----------------------------------------------------------------
    # Run benchmarks
    # ----------------------------------------------------------------
    all_results: dict = {}

    for name in ok_servers:
        benchmark.run_benchmark(
            name,
            crud_count=bench_cfg["crud_operations"],
            search_queries=bench_cfg["search_queries"],
        )

        # Collect per-operation stats
        ops_in_results = {
            r.operation.rsplit("_", 1)[0]
            for _, r in benchmark.runner.results
            if _ == name
        }
        all_results[name] = {
            op: benchmark.runner.get_summary_stats(name, op)
            for op in ops_in_results
        }

    # ----------------------------------------------------------------
    # Report
    # ----------------------------------------------------------------
    print_comparison_table(all_results)
    print_tradeoff_summary(servers_cfg)

    # ----------------------------------------------------------------
    # Persist results
    # ----------------------------------------------------------------
    out_dir = bench_cfg["output_directory"]
    os.makedirs(os.path.join(out_dir, "raw"), exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(out_dir, "raw", f"benchmark_{timestamp}.json")

    export = {
        "timestamp": timestamp,
        "servers": {
            n: {k: v for k, v in c.items() if k != "env"}
            for n, c in servers_cfg.items()
            if c.get("enabled")
        },
        "results": all_results,
        "raw": [
            {
                "server": cn,
                "operation": r.operation,
                "success": r.success,
                "latency_ms": r.latency_ms,
                "error": r.error_message,
            }
            for cn, r in benchmark.runner.results
        ],
    }
    with open(out_file, "w") as f:
        json.dump(export, f, indent=2)

    print(f"\nResults saved → {out_file}")

    # ----------------------------------------------------------------
    # Cleanup
    # ----------------------------------------------------------------
    benchmark.cleanup()
    print("\nBenchmark complete.")


if __name__ == "__main__":
    main()
