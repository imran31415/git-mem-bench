#!/usr/bin/env python3
"""
Updated MCP Memory Benchmark Runner with async writes testing
"""
import json
import time
import sys
from datetime import datetime

# Add current directory to path to import local modules
sys.path.insert(0, '/home/dev/t/mcp-memory-benchmark/test_harness')

try:
    from benchmark_suite import MCPMemoryBenchmark, generate_test_data
except ImportError:
    print("Error: Could not import benchmark_suite module")
    print("Make sure you're running from the correct directory")
    sys.exit(1)

def load_config(config_file="config/benchmark_config.json"):
    """Load benchmark configuration"""
    with open(config_file, 'r') as f:
        return json.load(f)

def main():
    """Main benchmark runner with async writes testing"""
    print("MCP Memory Server Benchmark - Async Writes Test")
    print("="*80)
    
    # Load configuration
    config = load_config()
    
    # Initialize benchmark
    benchmark = MCPMemoryBenchmark()
    
    # Set up each server from config
    servers = config["servers"]
    benchmark_config = config["benchmark"]
    
    successful_setups = 0
    
    for server_name, server_config in servers.items():
        if server_config.get("enabled", False):
            print(f"\nSetting up {server_name}...")
            print(f"  Description: {server_config.get('description', 'No description')}")
            print(f"  Command: {' '.join(server_config['command'])}")
            
            if benchmark.setup_client(server_name, server_config["command"]):
                print(f"  ✓ {server_name} setup successful")
                successful_setups += 1
            else:
                print(f"  ✗ {server_name} setup failed")
    
    if successful_setups == 0:
        print("\nNo servers successfully set up. Exiting.")
        return
    
    # Update benchmark parameters from config
    benchmark.test_data = generate_test_data(benchmark_config["test_data_size"])
    
    print(f"\nBenchmark Configuration:")
    print(f"  Test data size: {benchmark_config['test_data_size']}")
    print(f"  CRUD operations: {benchmark_config['crud_operations']}")
    print(f"  Concurrent threads: {benchmark_config['concurrent_threads']}")
    print(f"  Search queries: {', '.join(benchmark_config['search_queries'])}")
    print(f"  git-mem changes: {benchmark_config.get('git_mem_changes', 'unknown')}")
    
    # Run benchmarks for each client
    all_results = {}
    
    for client_name in benchmark.runner.clients.keys():
        print(f"\n{'='*80}")
        print(f"BENCHMARKING: {client_name}")
        print(f"{'='*80}")
        
        start_time = time.time()
        
        # Run tests
        benchmark.test_basic_crud(client_name, benchmark.test_data[:benchmark_config["crud_operations"]])
        benchmark.test_search(client_name)
        benchmark.test_concurrent_operations(client_name, num_threads=benchmark_config["concurrent_threads"])
        
        end_time = time.time()
        
        print(f"\nBenchmark completed in {end_time - start_time:.2f} seconds")
        
        # Get summary for this client
        client_summary = {}
        operations = set(r.operation.split('_')[0] for _, r in benchmark.runner.results 
                        if _.startswith(client_name))
        
        for op in sorted(operations):
            stats = benchmark.runner.get_summary_stats(client_name, op)
            if stats:
                client_summary[op] = stats
        
        all_results[client_name] = client_summary
    
    # Print comparative summary
    print("\n" + "="*80)
    print("COMPARATIVE SUMMARY")
    print("="*80)
    
    # Compare git-mem sync vs async
    gitmem_variants = [name for name in all_results.keys() if "git-mem" in name]
    if len(gitmem_variants) > 1:
        print("\ngit-mem Sync vs Async Performance Comparison:")
        print("  " + "-" * 60)
        
        for op in ["set", "get", "delete", "list"]:
            print(f"\n  {op.upper()}:")
            for variant in sorted(gitmem_variants):
                if op in all_results[variant]:
                    stats = all_results[variant][op]
                    if stats.get("latency_mean_ms", 0) > 0:
                        throughput = 1000 / stats["latency_mean_ms"]
                        async_flag = "(async)" if "async" in variant.lower() else "(sync)"
                        print(f"    {variant:<20} {stats['latency_mean_ms']:7.2f} ms | "
                              f"{throughput:6.1f} ops/sec | Success: {stats.get('success_rate', 0):.1f}% {async_flag}")
    
    # Compare with engram
    print("\nPerformance vs engram (lower latency is better):")
    print("  " + "-" * 60)
    
    for op in ["set", "get", "delete", "list"]:
        print(f"\n  {op.upper()}:")
        # Find engram metrics
        engram_stats = None
        for client_name, summary in all_results.items():
            if "engram" in client_name.lower() and op in summary:
                engram_stats = summary[op]
                break
        
        if engram_stats:
            engram_latency = engram_stats.get("latency_mean_ms", 0)
            engram_throughput = 1000 / engram_latency if engram_latency > 0 else 0
            
            print(f"    engram{' ' * 17} {engram_latency:7.2f} ms | "
                  f"{engram_throughput:6.1f} ops/sec | Success: {engram_stats.get('success_rate', 0):.1f}%")
            
            # Compare each git-mem variant
            for variant in sorted(gitmem_variants):
                if op in all_results[variant]:
                    stats = all_results[variant][op]
                    if stats.get("latency_mean_ms", 0) > 0:
                        ratio = stats["latency_mean_ms"] / engram_latency if engram_latency > 0 else float('inf')
                        async_flag = "(async)" if "async" in variant.lower() else "(sync)"
                        print(f"    {variant:<20} {stats['latency_mean_ms']:7.2f} ms | "
                              f"{ratio:5.1f}x slower {async_flag}")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"{benchmark_config['output_directory']}/raw/async_benchmark_{timestamp}.json"
    
    comparative_results = {
        "timestamp": timestamp,
        "config": benchmark_config,
        "servers": {name: config for name, config in servers.items() if config.get("enabled", False)},
        "results": all_results,
        "raw_results": [
            {
                "client": client_name,
                "operation": result.operation,
                "success": result.success,
                "latency_ms": result.latency_ms,
                "memory_usage_mb": result.memory_usage_mb,
                "cpu_percent": result.cpu_percent,
                "error_message": result.error_message,
            }
            for client_name, result in benchmark.runner.results
        ]
    }
    
    with open(results_file, 'w') as f:
        json.dump(comparative_results, f, indent=2)
    
    print(f"\nResults saved to: {results_file}")
    
    # Cleanup
    benchmark.cleanup()
    
    print("\n" + "="*80)
    print("BENCHMARK COMPLETED")
    print("="*80)
    
    # Quick analysis
    print("\nQUICK ANALYSIS:")
    print("-" * 40)
    
    # Check if async writes improve performance
    gitmem_sync = None
    gitmem_async = None
    
    for variant in gitmem_variants:
        if "sync" in variant.lower():
            gitmem_sync = variant
        elif "async" in variant.lower():
            gitmem_async = variant
    
    if gitmem_sync and gitmem_async:
        print("\ngit-mem Async vs Sync Comparison:")
        for op in ["set", "get", "delete", "list"]:
            if op in all_results.get(gitmem_sync, {}) and op in all_results.get(gitmem_async, {}):
                sync_latency = all_results[gitmem_sync][op].get("latency_mean_ms", 0)
                async_latency = all_results[gitmem_async][op].get("latency_mean_ms", 0)
                
                if sync_latency > 0 and async_latency > 0:
                    improvement = ((sync_latency - async_latency) / sync_latency) * 100
                    print(f"  {op.upper()}: {sync_latency:.2f}ms → {async_latency:.2f}ms ({improvement:+.1f}%)")

if __name__ == "__main__":
    main()