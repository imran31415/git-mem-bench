#!/usr/bin/env python3
"""
Compare git-mem performance before and after performance improvements
"""
import json
import sys
from datetime import datetime

def load_results(filepath):
    """Load benchmark results from JSON file"""
    with open(filepath, 'r') as f:
        return json.load(f)

def extract_performance_metrics(results_data, server_name="git-mem"):
    """Extract performance metrics for a specific server"""
    if "results" in results_data and server_name in results_data["results"]:
        server_results = results_data["results"][server_name]
        metrics = {}
        
        for op in ["set", "get", "delete", "list"]:
            if op in server_results:
                metrics[op] = {
                    "latency_mean_ms": server_results[op].get("latency_mean_ms", 0),
                    "throughput_ops_sec": 1000 / server_results[op].get("latency_mean_ms", 0.001) if server_results[op].get("latency_mean_ms", 0) > 0 else 0,
                    "success_rate": server_results[op].get("success_rate", 0)
                }
        
        # Check if search metrics are available
        search_keys = [k for k in server_results.keys() if "search" in k.lower()]
        if search_keys:
            search_key = search_keys[0]
            if search_key in server_results:
                metrics["search"] = {
                    "latency_mean_ms": server_results[search_key].get("latency_mean_ms", 0),
                    "success_rate": server_results[search_key].get("success_rate", 0)
                }
        
        return metrics
    return {}

def compare_performance(old_metrics, new_metrics):
    """Compare performance metrics and calculate improvements"""
    comparison = {}
    
    for op in ["set", "get", "delete", "list", "search"]:
        if op in old_metrics and op in new_metrics:
            old_latency = old_metrics[op].get("latency_mean_ms", 0)
            new_latency = new_metrics[op].get("latency_mean_ms", 0)
            
            if old_latency > 0 and new_latency > 0:
                improvement_ratio = old_latency / new_latency
                improvement_pct = ((old_latency - new_latency) / old_latency) * 100
                
                old_throughput = old_metrics[op].get("throughput_ops_sec", 0)
                new_throughput = new_metrics[op].get("throughput_ops_sec", 0)
                throughput_improvement = (new_throughput - old_throughput) / old_throughput * 100 if old_throughput > 0 else 0
                
                comparison[op] = {
                    "old_latency_ms": old_latency,
                    "new_latency_ms": new_latency,
                    "improvement_ratio": improvement_ratio,
                    "improvement_percentage": improvement_pct,
                    "old_throughput_ops_sec": old_throughput,
                    "new_throughput_ops_sec": new_throughput,
                    "throughput_improvement_pct": throughput_improvement,
                    "old_success_rate": old_metrics[op].get("success_rate", 0),
                    "new_success_rate": new_metrics[op].get("success_rate", 0)
                }
    
    return comparison

def main():
    """Main comparison function"""
    print("git-mem Performance Comparison: Before vs After Improvements")
    print("="*80)
    
    # Load old results (before improvements)
    old_file = "/home/dev/t/mcp-memory-benchmark/results/raw/comparative_benchmark_20260611_225923.json"
    new_file = "/home/dev/t/mcp-memory-benchmark/results/raw/comparative_benchmark_20260612_030047.json"
    
    try:
        old_results = load_results(old_file)
        new_results = load_results(new_file)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return
    
    print(f"Old benchmark: {old_results.get('timestamp', 'unknown')}")
    print(f"New benchmark: {new_results.get('timestamp', 'unknown')}")
    print(f"git-mem changes: {new_results.get('config', {}).get('git_mem_changes', 'unknown')}")
    print()
    
    # Extract metrics
    old_metrics = extract_performance_metrics(old_results, "git-mem")
    new_metrics = extract_performance_metrics(new_results, "git-mem")
    
    # Compare
    comparison = compare_performance(old_metrics, new_metrics)
    
    # Print comparison table
    print("PERFORMANCE IMPROVEMENTS")
    print("-" * 80)
    print(f"{'Operation':<10} {'Old Latency':>12} {'New Latency':>12} {'Improvement':>12} {'Speedup':>10} {'Throughput Gain':>15}")
    print("-" * 80)
    
    for op in ["set", "get", "delete", "list", "search"]:
        if op in comparison:
            cmp = comparison[op]
            print(f"{op.upper():<10} {cmp['old_latency_ms']:>11.2f}ms {cmp['new_latency_ms']:>11.2f}ms "
                  f"{cmp['improvement_percentage']:>11.1f}% {cmp['improvement_ratio']:>9.1f}x "
                  f"{cmp['throughput_improvement_pct']:>14.1f}%")
    
    print("\n" + "="*80)
    print("DETAILED ANALYSIS")
    print("="*80)
    
    # Detailed analysis for each operation
    for op in ["set", "get", "delete", "list", "search"]:
        if op in comparison:
            cmp = comparison[op]
            print(f"\n{op.upper()} Operation:")
            print(f"  • Latency reduced from {cmp['old_latency_ms']:.2f}ms to {cmp['new_latency_ms']:.2f}ms "
                  f"({cmp['improvement_percentage']:.1f}% improvement)")
            print(f"  • Speedup: {cmp['improvement_ratio']:.1f}x faster")
            print(f"  • Throughput: {cmp['old_throughput_ops_sec']:.1f} → {cmp['new_throughput_ops_sec']:.1f} ops/sec "
                  f"({cmp['throughput_improvement_pct']:+.1f}%)")
            print(f"  • Success rate: {cmp['old_success_rate']:.1f}% → {cmp['new_success_rate']:.1f}%")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    total_improvement = 0
    count = 0
    for op in comparison:
        total_improvement += comparison[op]["improvement_percentage"]
        count += 1
    
    if count > 0:
        avg_improvement = total_improvement / count
        print(f"Average improvement across all operations: {avg_improvement:.1f}%")
    
    # Most improved operation
    if comparison:
        most_improved = max(comparison.items(), key=lambda x: x[1]["improvement_percentage"])
        print(f"Most improved operation: {most_improved[0].upper()} "
              f"({most_improved[1]['improvement_percentage']:.1f}% improvement, "
              f"{most_improved[1]['improvement_ratio']:.1f}x faster)")
    
    # Compare with engram
    print("\n" + "="*80)
    print("COMPARISON WITH ENGRAM (Current Benchmark)")
    print("="*80)
    
    engram_metrics = extract_performance_metrics(new_results, "engram")
    
    print(f"{'Operation':<10} {'git-mem (new)':>15} {'engram':>15} {'Difference':>15}")
    print("-" * 60)
    
    for op in ["set", "get", "delete", "list", "search"]:
        if op in new_metrics and op in engram_metrics:
            gitmem_latency = new_metrics[op].get("latency_mean_ms", 0)
            engram_latency = engram_metrics[op].get("latency_mean_ms", 0)
            
            if gitmem_latency > 0 and engram_latency > 0:
                diff_pct = ((gitmem_latency - engram_latency) / engram_latency) * 100
                print(f"{op.upper():<10} {gitmem_latency:>14.2f}ms {engram_latency:>14.2f}ms {diff_pct:>14.1f}%")
    
    print(f"\nNotes:")
    print(f"- Positive % means git-mem is slower than engram")
    print(f"- Negative % means git-mem is faster than engram")
    
    # Save comparison results
    output = {
        "comparison_timestamp": datetime.now().isoformat(),
        "old_benchmark": old_results.get("timestamp"),
        "new_benchmark": new_results.get("timestamp"),
        "git_mem_changes": new_results.get("config", {}).get("git_mem_changes"),
        "performance_comparison": comparison,
        "git_mem_new_metrics": new_metrics,
        "engram_metrics": engram_metrics
    }
    
    output_file = "/home/dev/t/mcp-memory-benchmark/results/processed/git_mem_performance_comparison.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nDetailed comparison saved to: {output_file}")

if __name__ == "__main__":
    main()