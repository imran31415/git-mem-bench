#!/usr/bin/env python3
"""
Create CSV export of benchmark results for spreadsheet analysis
"""
import json
import csv
import os
from pathlib import Path
from datetime import datetime

def load_json_file(filepath):
    """Load JSON data from file"""
    with open(filepath, 'r') as f:
        return json.load(f)

def extract_benchmark_results(results_data):
    """Extract benchmark results in tabular format"""
    rows = []
    
    if "results" not in results_data:
        return rows
    
    # Extract server configurations
    servers = list(results_data["results"].keys())
    operations = ["set", "get", "delete", "list", "search"]
    
    for server in servers:
        server_results = results_data["results"][server]
        
        for op in operations:
            # Handle search operations specially
            if op == "search":
                search_tools = [k for k in server_results.keys() if "search" in k.lower()]
                for search_tool in search_tools:
                    if search_tool in server_results:
                        tool_data = server_results[search_tool]
                        rows.append({
                            "server": server,
                            "operation": search_tool,
                            "latency_ms": tool_data.get("latency_mean_ms", 0),
                            "throughput_ops_sec": 1000 / tool_data.get("latency_mean_ms", 0.001) 
                                if tool_data.get("latency_mean_ms", 0) > 0 else 0,
                            "success_rate": tool_data.get("success_rate", 0),
                            "total_operations": tool_data.get("total_operations", 0),
                            "successful_operations": tool_data.get("successful_operations", 0)
                        })
            elif op in server_results:
                op_data = server_results[op]
                rows.append({
                    "server": server,
                    "operation": op,
                    "latency_ms": op_data.get("latency_mean_ms", 0),
                    "throughput_ops_sec": 1000 / op_data.get("latency_mean_ms", 0.001) 
                        if op_data.get("latency_mean_ms", 0) > 0 else 0,
                    "success_rate": op_data.get("success_rate", 0),
                    "total_operations": op_data.get("total_operations", 0),
                    "successful_operations": op_data.get("successful_operations", 0),
                    "latency_min_ms": op_data.get("latency_min_ms", 0),
                    "latency_max_ms": op_data.get("latency_max_ms", 0),
                    "latency_std_ms": op_data.get("latency_std_ms", 0)
                })
    
    return rows

def create_csv_export(results_data, output_path):
    """Create CSV export of benchmark results"""
    rows = extract_benchmark_results(results_data)
    
    if not rows:
        print("No benchmark results to export")
        return False
    
    # Define CSV fields
    fieldnames = [
        "server", "operation", "latency_ms", "throughput_ops_sec", 
        "success_rate", "total_operations", "successful_operations",
        "latency_min_ms", "latency_max_ms", "latency_std_ms"
    ]
    
    with open(output_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    return True

def create_comparison_csv(comparison_data, output_path):
    """Create comparison CSV with summarized data"""
    if "results" not in comparison_data:
        return False
    
    servers = list(comparison_data["results"].keys())
    operations = ["set", "get", "delete", "list"]
    
    rows = []
    
    for server in servers:
        server_results = comparison_data["results"][server]
        
        for op in operations:
            if op in server_results:
                op_data = server_results[op]
                rows.append({
                    "server": server,
                    "operation": op,
                    "latency_mean_ms": op_data.get("latency_mean_ms", 0),
                    "latency_median_ms": op_data.get("latency_median_ms", 0),
                    "latency_min_ms": op_data.get("latency_min_ms", 0),
                    "latency_max_ms": op_data.get("latency_max_ms", 0),
                    "latency_std_ms": op_data.get("latency_std_ms", 0),
                    "throughput_ops_sec": 1000 / op_data.get("latency_mean_ms", 0.001) 
                        if op_data.get("latency_mean_ms", 0) > 0 else 0,
                    "success_rate": op_data.get("success_rate", 0),
                    "total_ops": op_data.get("total_operations", 0),
                    "successful_ops": op_data.get("successful_operations", 0)
                })
    
    if not rows:
        return False
    
    fieldnames = [
        "server", "operation", "latency_mean_ms", "latency_median_ms",
        "latency_min_ms", "latency_max_ms", "latency_std_ms",
        "throughput_ops_sec", "success_rate", "total_ops", "successful_ops"
    ]
    
    with open(output_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    return True

def create_evolution_csv(evolution_data, output_path):
    """Create evolution timeline CSV"""
    if "performance_evolution" not in evolution_data:
        return False
    
    rows = []
    
    for version_name, version_data in evolution_data["performance_evolution"].items():
        if "metrics" in version_data:
            for server_name, server_metrics in version_data["metrics"].items():
                if "set" in server_metrics:
                    set_data = server_metrics["set"]
                    rows.append({
                        "version": version_name,
                        "server": server_name,
                        "set_latency_ms": set_data.get("latency_mean_ms", 0),
                        "set_throughput_ops_sec": set_data.get("throughput_ops_sec", 0),
                        "set_success_rate": set_data.get("success_rate", 0)
                    })
    
    if not rows:
        return False
    
    fieldnames = [
        "version", "server", "set_latency_ms", 
        "set_throughput_ops_sec", "set_success_rate"
    ]
    
    with open(output_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    return True

def create_improvement_csv(comparison_data, output_path):
    """Create improvement calculation CSV"""
    if "results" not in comparison_data:
        return False
    
    # Find git-mem variants
    servers = list(comparison_data["results"].keys())
    gitmem_servers = [s for s in servers if "git-mem" in s]
    
    if len(gitmem_servers) < 2:
        return False
    
    # Find sync and async servers
    sync_server = None
    async_server = None
    
    for server in gitmem_servers:
        if "sync" in server.lower():
            sync_server = server
        elif "async" in server.lower():
            async_server = server
    
    if not sync_server or not async_server:
        return False
    
    sync_results = comparison_data["results"][sync_server]
    async_results = comparison_data["results"][async_server]
    
    rows = []
    operations = ["set", "get", "delete", "list"]
    
    for op in operations:
        if op in sync_results and op in async_results:
            sync_data = sync_results[op]
            async_data = async_results[op]
            
            sync_latency = sync_data.get("latency_mean_ms", 0)
            async_latency = async_data.get("latency_mean_ms", 0)
            
            if sync_latency > 0:
                improvement = ((sync_latency - async_latency) / sync_latency) * 100
                speedup = sync_latency / async_latency if async_latency > 0 else 0
                
                rows.append({
                    "operation": op,
                    "sync_latency_ms": sync_latency,
                    "async_latency_ms": async_latency,
                    "improvement_percent": improvement,
                    "speedup_factor": speedup,
                    "sync_throughput_ops_sec": 1000 / sync_latency if sync_latency > 0 else 0,
                    "async_throughput_ops_sec": 1000 / async_latency if async_latency > 0 else 0,
                    "throughput_improvement_percent": ((1000/async_latency - 1000/sync_latency) / (1000/sync_latency)) * 100 
                        if sync_latency > 0 and async_latency > 0 else 0
                })
    
    if not rows:
        return False
    
    fieldnames = [
        "operation", "sync_latency_ms", "async_latency_ms",
        "improvement_percent", "speedup_factor",
        "sync_throughput_ops_sec", "async_throughput_ops_sec",
        "throughput_improvement_percent"
    ]
    
    with open(output_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    return True

def main():
    """Main function to create CSV exports"""
    print("Creating CSV Exports of Benchmark Results")
    print("="*50)
    
    # Load data files
    data_files = {
        "comparison": "results/raw/async_benchmark_20260612_035921.json",
        "evolution": "results/processed/git_mem_evolution_analysis.json"
    }
    
    loaded_data = {}
    for name, filepath in data_files.items():
        full_path = Path(__file__).parent / filepath
        if full_path.exists():
            try:
                loaded_data[name] = load_json_file(full_path)
                print(f"✓ Loaded: {name}")
            except Exception as e:
                print(f"✗ Failed to load {name}: {e}")
        else:
            print(f"✗ File not found: {filepath}")
    
    if not loaded_data:
        print("\nNo data files found. Please run benchmarks first.")
        return
    
    # Create output directory
    output_dir = Path(__file__).parent / "results" / "visualizations"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create CSV exports
    csv_files_created = []
    
    # 1. Detailed benchmark results
    if "comparison" in loaded_data:
        detailed_csv = output_dir / f"detailed_results_{timestamp}.csv"
        if create_csv_export(loaded_data["comparison"], detailed_csv):
            csv_files_created.append(detailed_csv)
            print(f"✓ Created detailed results CSV: {detailed_csv}")
    
    # 2. Comparison summary
    if "comparison" in loaded_data:
        comparison_csv = output_dir / f"comparison_summary_{timestamp}.csv"
        if create_comparison_csv(loaded_data["comparison"], comparison_csv):
            csv_files_created.append(comparison_csv)
            print(f"✓ Created comparison summary CSV: {comparison_csv}")
    
    # 3. Performance evolution
    if "evolution" in loaded_data:
        evolution_csv = output_dir / f"performance_evolution_{timestamp}.csv"
        if create_evolution_csv(loaded_data["evolution"], evolution_csv):
            csv_files_created.append(evolution_csv)
            print(f"✓ Created performance evolution CSV: {evolution_csv}")
    
    # 4. Improvement calculations
    if "comparison" in loaded_data:
        improvement_csv = output_dir / f"improvement_calculations_{timestamp}.csv"
        if create_improvement_csv(loaded_data["comparison"], improvement_csv):
            csv_files_created.append(improvement_csv)
            print(f"✓ Created improvement calculations CSV: {improvement_csv}")
    
    print("\n" + "="*50)
    print("CSV EXPORTS SUMMARY")
    print("="*50)
    
    if csv_files_created:
        print(f"\nCreated {len(csv_files_created)} CSV files:")
        for csv_file in csv_files_created:
            print(f"  • {csv_file.name}")
        
        print("\nYou can open these CSV files in:")
        print("  - Microsoft Excel")
        print("  - Google Sheets")
        print("  - LibreOffice Calc")
        print("  - Any spreadsheet application")
        
        print("\nThe CSV files contain:")
        print("  1. Detailed benchmark results")
        print("  2. Comparison summary data")
        print("  3. Performance evolution timeline")
        print("  4. Improvement calculations")
    else:
        print("\nNo CSV files were created. Check the data files and try again.")

if __name__ == "__main__":
    main()