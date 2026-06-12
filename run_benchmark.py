#!/usr/bin/env python3
"""
Updated MCP Memory Benchmark Runner
Reads configuration from JSON file
"""
import json
import time
import sys
from datetime import datetime

# Add current directory to path to import local modules
sys.path.insert(0, '/home/dev/t/mcp-memory-benchmark/test_harness')

try:
    from benchmark_suite import MCPMemoryBenchmark
except ImportError:
    print("Error: Could not import benchmark_suite module")
    print("Make sure you're running from the correct directory")
    sys.exit(1)

def load_config(config_file="config/benchmark_config.json"):
    """Load benchmark configuration"""
    with open(config_file, 'r') as f:
        return json.load(f)

def main():
    """Main benchmark runner"""
    print("MCP Memory Server Benchmark")
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
    # Generate test data using the function from benchmark_suite
    from benchmark_suite import generate_test_data
    benchmark.test_data = generate_test_data(benchmark_config["test_data_size"])
    
    print(f"\nBenchmark Configuration:")
    print(f"  Test data size: {benchmark_config['test_data_size']}")
    print(f"  CRUD operations: {benchmark_config['crud_operations']}")
    print(f"  Concurrent threads: {benchmark_config['concurrent_threads']}")
    print(f"  Search queries: {', '.join(benchmark_config['search_queries'])}")
    
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
    
    # Compare basic operations
    print("\nBasic Operations Performance (lower latency is better):")
    print("-" * 80)
    
    # Find common operations
    common_ops = set()
    for client_name, summary in all_results.items():
        common_ops.update(summary.keys())
    
    for op in sorted(common_ops):
        if op in ["set", "get", "delete", "list"]:  # Basic operations
            print(f"\n{op.upper()}:")
            print("  " + "-" * 60)
            for client_name in sorted(all_results.keys()):
                if op in all_results[client_name]:
                    stats = all_results[client_name][op]
                    if stats.get("latency_mean_ms", 0) > 0:
                        throughput = 1000 / stats["latency_mean_ms"]
                        print(f"  {client_name:<15} {stats['latency_mean_ms']:7.2f} ms "
                              f"(±{stats.get('latency_std_ms', 0):.2f}) "
                              f"| {throughput:6.1f} ops/sec | "
                              f"Success: {stats.get('success_rate', 0):.1f}%")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"{benchmark_config['output_directory']}/raw/comparative_benchmark_{timestamp}.json"
    
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
    
    # Generate quick analysis
    print("\nQUICK ANALYSIS:")
    print("-" * 40)
    
    # Find fastest for each basic operation
    for op in ["set", "get", "delete", "list"]:
        fastest = None
        fastest_latency = float('inf')
        
        for client_name, summary in all_results.items():
            if op in summary:
                latency = summary[op].get("latency_mean_ms", float('inf'))
                if latency < fastest_latency:
                    fastest_latency = latency
                    fastest = client_name
        
        if fastest:
            print(f"Fastest {op.upper()}: {fastest} ({fastest_latency:.2f} ms)")

if __name__ == "__main__":
    main()