#!/usr/bin/env python3
"""
MCP Memory Benchmark Visualization Script
Creates charts and graphs from benchmark results
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Try to import visualization libraries
try:
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    import numpy as np
    import seaborn as sns
    VISUALIZATION_AVAILABLE = True
    print("Visualization libraries available")
except ImportError as e:
    print(f"Visualization libraries not available: {e}")
    print("Creating text-based visualizations instead")
    VISUALIZATION_AVAILABLE = False

def load_benchmark_data(filepath):
    """Load benchmark data from JSON file"""
    with open(filepath, 'r') as f:
        return json.load(f)

def extract_comparison_data(results_data):
    """Extract comparison data for visualization"""
    comparisons = {}
    
    if "results" in results_data:
        for server_name, server_results in results_data["results"].items():
            server_comparison = {}
            for op in ["set", "get", "delete", "list"]:
                if op in server_results:
                    server_comparison[op] = {
                        "latency_ms": server_results[op].get("latency_mean_ms", 0),
                        "throughput_ops_sec": 1000 / server_results[op].get("latency_mean_ms", 0.001) 
                            if server_results[op].get("latency_mean_ms", 0) > 0 else 0,
                        "success_rate": server_results[op].get("success_rate", 0)
                    }
            comparisons[server_name] = server_comparison
    
    return comparisons

def create_text_chart(data, title, value_label="Value"):
    """Create ASCII/text-based chart"""
    print(f"\n{'='*60}")
    print(f"{title:^60}")
    print(f"{'='*60}")
    
    # Find max value for scaling
    max_value = max([v for server in data.values() for v in server.values()])
    scale_factor = 50 / max_value if max_value > 0 else 1
    
    for server_name, server_data in data.items():
        print(f"\n{server_name}:")
        for key, value in server_data.items():
            bar_length = int(value * scale_factor)
            bar = "█" * bar_length
            print(f"  {key:<10} {value:>8.2f} {bar}")

def create_latency_comparison_chart(comparisons, output_dir):
    """Create latency comparison chart"""
    if not VISUALIZATION_AVAILABLE:
        print("\nCreating text-based latency comparison...")
        text_data = {}
        for server_name, server_data in comparisons.items():
            text_data[server_name] = {op: data["latency_ms"] 
                                     for op, data in server_data.items() 
                                     if op in ["set", "get", "delete", "list"]}
        create_text_chart(text_data, "Operation Latency Comparison (ms)", "Latency (ms)")
        return
    
    # Prepare data for visualization
    servers = list(comparisons.keys())
    operations = ["set", "get", "delete", "list"]
    
    # Create figure
    fig, axes = plt.subplots(2, 2, figsize=(12,他们所10))
    fig.suptitle('MCP Memory Server Performance Comparison', fontsize=16, fontweight='bold')
    
    colors = plt.cm.Set2(np.linspace(0, 1, len(servers)))
    
    # Plot 1: Latency comparison
    ax1 = axes[0, 0]
    x = np.arange(len(operations))
    width = 0.8 / len(servers)
    
    for i, server in enumerate(servers):
        latencies = [comparisons[server].get(op, {}).get("latency_ms", 0) for op in operations]
        ax1.bar(x + i*width - width*(len(servers)-1)/2, latencies, width, 
                label=server, color=colors[i], alpha=0.8)
    
    ax1.set_ylabel('Latency (ms)')
    ax1.set_title('Operation Latency')
    ax1.set_xticks(x)
    ax1.set_xticklabels([op.upper() for op in operations])
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Throughput comparison
    ax2 = axes[0, 1]
    for i, server in enumerate(servers):
        throughputs = [comparisons[server].get(op, {}).get("throughput_ops_sec", 0) for op in operations]
        ax2.bar(x + i*width - width*(len(servers)-1)/2, throughputs, width,
                label=server, color=colors[i], alpha=0.8)
    
    ax2.set_ylabel('Throughput (ops/sec)')
    ax2.set_title('Operation Throughput')
    ax2.set_xticks(x)
    ax2.set_xticklabels([op.upper() for op in operations])
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Plot 3: Success rates
    ax3 = axes[1, 0]
    for i, server in enumerate(servers):
        success_rates = [comparisons[server].get(op, {}).get("success_rate", 0) for op in operations]
        ax3.bar(x + i*width - width*(len(servers)-1)/2, success_rates, width,
                label=server, color=colors[i], alpha=0.8)
    
    ax3.set_ylabel('Success Rate (%)')
    ax3.set_title('Operation Success Rate')
    ax3.set_xticks(x)
    ax3.set_xticklabels([op.upper() for op in operations])
    ax3.set_ylim([0, 105])
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # Plot 4: Latency comparison heatmap style
    ax4 = axes[1, 1]
    latency_matrix = []
    for op in operations:
        row = []
        for server in servers:
            latency = comparisons[server].get(op, {}).get("latency_ms", 0)
            row.append(latency)
        latency_matrix.append(row)
    
    im = ax4.imshow(latency_matrix, cmap='YlOrRd', aspect='auto')
    ax4.set_xticks(np.arange(len(servers)))
    ax4.set_yticks(np.arange(len(operations)))
    ax4.set_xticklabels([s[:15] + '...' if len(s) > 15 else s for s in servers])
    ax4.set_yticklabels([op.upper() for op in operations])
    
    # Add text annotations
    for i in range(len(operations)):
        for j in range(len(servers)):
            text = ax4.text(j, i, f'{latency_matrix[i][j]:.1f}',
                           ha="center", va="center", color="black", fontsize=9)
    
    ax4.set_title('Latency Heatmap (ms)')
    plt.colorbar(im, ax=ax4, label='Latency (ms)')
    
    plt.tight_layout()
    
    # Save figure
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f'performance_comparison_{timestamp}.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Saved latency comparison chart to: {output_path}")
    
    # Also create individual charts
    create_individual_charts(comparisons, output_dir)
    
    plt.close()

def create_individual_charts(comparisons, output_dir):
    """Create individual comparison charts"""
    if not VISUALIZATION_AVAILABLE:
        return
    
    operations = ["set", "get", "delete", "list"]
    servers = list(comparisons.keys())
    
    # Create directory for individual charts
    individual_dir = os.path.join(output_dir, "individual")
    os.makedirs(individual_dir, exist_ok=True)
    
    # Create chart for each operation
    for operation in operations:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        fig.suptitle(f'{operation.upper()} Operation Performance', fontsize=14, fontweight='bold')
        
        # Prepare data
        latencies = []
        throughputs = []
        server_labels = []
        
        for server in servers:
            if operation in comparisons[server]:
                latencies.append(comparisons[server][operation]["latency_ms"])
                throughputs.append(comparisons[server][operation]["throughput_ops_sec"])
                server_labels.append(server)
        
        if not latencies:
            continue
        
        colors = plt.cm.tab20c(np.linspace(0, 1, len(server_labels)))
        
        # Latency chart
        bars1 = ax1.bar(server_labels, latencies, color=colors, alpha=0.7)
        ax1.set_ylabel('Latency (ms)')
        ax1.set_title(f'{operation.upper()} Latency')
        ax1.grid(True, alpha=0.3)
        
        # Add value labels on bars
        for bar in bars1:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}', ha='center', va='bottom', fontsize=9)
        
        # Throughput chart
        bars2 = ax2.bar(server_labels, throughputs, color=colors, alpha=0.7)
        ax2.set_ylabel('Throughput (ops/sec)')
        ax2.set_title(f'{operation.upper()} Throughput')
        ax2.grid(True, alpha=0.3)
        
        # Add value labels on bars
        for bar in bars2:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height):,}', ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        
        # Save individual chart
        output_path = os.path.join(individual_dir, f'{operation}_performance.png')
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
    
    print(f"Individual operation charts saved to: {individual_dir}")

def create_performance_evolution_chart(evolution_data, output_dir):
    """Create performance evolution chart"""
    if not VISUALIZATION_AVAILABLE:
        print("\nCreating text-based performance evolution...")
        if "performance_evolution" in evolution_data:
            for version_name, version_data in evolution_data["performance_evolution"].items():
                print(f"\n{version_name}:")
                if "metrics" in version_data:
                    for server_name, server_metrics in version_data["metrics"].items():
                        if "set" in server_metrics:
                            latency = server_metrics["set"]["latency_mean_ms"]
                            print(f"  {server_name}: SET = {latency:.2f}ms")
        return
    
    # Extract SET operation evolution
    evolution_points = []
    latencies = []
    versions = []
    
    if "performance_evolution" in evolution_data:
        for version_name, version_data in evolution_data["performance_evolution"].items():
            if "metrics" in version_data:
                for server_name, server_metrics in version_data["metrics"].items():
                    if "set" in server_metrics:
                        evolution_points.append({
                            "version": version_name,
                            "server": server_name,
                            "latency": server_metrics["set"]["latency_mean_ms"],
                            "throughput": server_metrics["set"]["throughput_ops_sec"]
                        })
                        latencies.append(server_metrics["set"]["latency_mean_ms"])
                        versions.append(f"{version_name}\n{server_name}")
    
    if not evolution_points:
        print("No evolution data found")
        return
    
    # Create evolution chart
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    fig.suptitle('git-mem Performance Evolution (SET Operation)', fontsize=14, fontweight='bold')
    
    # Latency evolution
    x = np.arange(len(evolution_points))
    colors = plt.cm.viridis(np.linspace(0, 1, len(evolution_points)))
    
    bars1 = ax1.bar(x, latencies, color=colors, alpha=0.7)
    ax1.set_ylabel('Latency (ms)')
    ax1.set_title('SET Operation Latency Over Time')
    ax1.set_xticks(x)
    ax1.set_xticklabels(versions, rotation=45, ha='right')
    ax1.grid(True, alpha=0.3)
    
    # Add value labels
    for bar in bars1:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.2f}', ha='center', va='bottom', fontsize=9)
    
    # Calculate improvements
    improvements = []
    for i in range(1, len(latencies)):
        improvement = ((latencies[i-1] - latencies[i]) / latencies[i-1]) * 100
        improvements.append(improvement)
    
    # Improvement chart
    if improvements:
        ax2.bar(range(1, len(latencies)), improvements, color='green', alpha=0.7)
        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        ax2.set_ylabel('Improvement (%)')
        ax2.set_title('Performance Improvement Between Versions')
        ax2.set_xlabel('Version Transition')
        ax2.grid(True, alpha=0.3)
        
        # Add value labels
        for i, improvement in enumerate(improvements):
            ax2.text(i+1, improvement, f'{improvement:+.1f}%', 
                    ha='center', va='bottom' if improvement >= 0 else 'top', fontsize=9)
    
    plt.tight_layout()
    
    # Save evolution chart
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f'performance_evolution_{timestamp}.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Saved performance evolution chart to: {output_path}")
    
    plt.close()

def create_async_vs_sync_chart(async_data, output_dir):
    """Create async vs sync comparison chart"""
    if not VISUALIZATION_AVAILABLE:
        print("\nCreating text-based async vs sync comparison...")
        if "results" in async_data:
            gitmem_servers = {k: v for k, v in async_data["results"].items() if "git-mem" in k}
            text_data = {}
            for server_name, server_results in gitmem_servers.items():
                text_data[server_name] = {}
                for op in ["set", "get", "delete", "list"]:
                    if op in server_results:
                        text_data[server_name][op] = server_results[op].get("latency_mean_ms", 0)
            create_text_chart(text_data, "git-mem Async vs Sync Performance", "Latency (ms)")
        return
    
    # Extract git-mem async vs sync data
    gitmem_data = {}
    if "results" in async_data:
        for server_name, server_results in async_data["results"].items():
            if "git-mem" in server_name:
                gitmem_data[server_name] = {}
                for op in ["set", "get", "delete", "list"]:
                    if op in server_results:
                        gitmem_data[server_name][op] = {
                            "latency": server_results[op].get("latency_mean_ms", 0),
                            "throughput": 1000 / server_results[op].get("latency_mean_ms", 0.001) 
                                if server_results[op].get("latency_mean_ms", 0) > 0 else 0
                        }
    
    if len(gitmem_data) < 2:
        print("Not enough git-mem data for async vs sync comparison")
        return
    
    # Create comparison chart
    operations = ["set", "get", "delete", "list"]
    servers = list(gitmem_data.keys())
    
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle('git-mem Async vs Sync Performance Comparison', fontsize=16, fontweight='bold')
    
    colors = {'sync': 'blue', 'async': 'green'}
    
    for idx, operation in enumerate(operations):
        ax = axes[idx // 2, idx % 2]
        
        sync_latency = None
        async_latency = None
        sync_server = None
        async_server = None
        
        for server in servers:
            if operation in gitmem_data[server]:
                latency = gitmem_data[server][operation]["latency"]
                if "async" in server.lower():
                    async_latency = latency
                    async_server = server
                elif "sync" in server.lower():
                    sync_latency = latency
                    sync_server = server
        
        if sync_latency is not None and async_latency is not None:
            # Calculate improvement
            improvement = ((sync_latency - async_latency) / sync_latency) * 100
            
            # Create grouped bar chart
            x = [0, 1]
            latencies = [sync_latency, async_latency]
            labels = [sync_server, async_server]
            bar_colors = [colors['sync'], colors['async']]
            
            bars = ax.bar(x, latencies, color=bar_colors, alpha=0.7, width=0.6)
            ax.set_ylabel('Latency (ms)')
            ax.set_title(f'{operation.upper()} Operation\nImprovement: {improvement:+.1f}%')
            ax.set_xticks(x)
            ax.set_xticklabels(['Sync', 'Async'])
            ax.grid(True, alpha=0.3)
            
            # Add value labels
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.2f}ms', ha='center', va='bottom', fontsize=9)
        else:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title(f'{operation.upper()} Operation')
    
    plt.tight_layout()
    
    # Save chart
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f'async_vs_sync_{timestamp}.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Saved async vs sync chart to: {output_path}")
    
    plt.close()

def main():
    """Main visualization function"""
    print("MCP Memory Benchmark Visualization")
    print("="*60)
    
    # Create output directory
    output_dir = Path(__file__).parent / "results" / "visualizations"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load data files
    data_files = {
        "async_benchmark": "results/raw/async_benchmark_20260612_035921.json",
        "evolution_analysis": "results/processed/git_mem_evolution_analysis.json",
        "performance_comparison": "results/processed/git_mem_performance_comparison.json"
    }
    
    loaded_data = {}
    for name, filepath in data_files.items():
        full_path = Path(__file__).parent / filepath
        if full_path.exists():
            try:
                loaded_data[name] = load_benchmark_data(full_path)
                print(f"✓ Loaded: {name}")
            except Exception as e:
                print(f"✗ Failed to load {name}: {e}")
        else:
            print(f"✗ File not found: {filepath}")
    
    if not loaded_data:
        print("\nNo data files found. Please run benchmarks first.")
        return
    
    # Create visualizations
    print("\n" + "="*60)
    print("Creating Visualizations")
    print("="*60)
    
    # 1. Performance comparison chart
    if "async_benchmark" in loaded_data:
        print("\n1. Creating performance comparison chart...")
        comparisons = extract_comparison_data(loaded_data["async_benchmark"])
        if comparisons:
            create_latency_comparison_chart(comparisons, output_dir)
        else:
            print("  No comparison data found")
    
    # 2. Performance evolution chart
    if "evolution_analysis" in loaded_data:
        print("\n2. Creating performance evolution chart...")
        create_performance_evolution_chart(loaded_data["evolution_analysis"], output_dir)
    
    # 3. Async vs sync chart
    if "async_benchmark" in loaded_data:
        print("\n3. Creating async vs sync comparison chart...")
        create_async_vs_sync_chart(loaded_data["async_benchmark"], output_dir)
    
    # 4. Text summary if no visualization libraries
    if not VISUALIZATION_AVAILABLE:
        print("\n" + "="*60)
        print("Text-Based Visualizations Complete")
        print("="*60)
        print("\nInstall matplotlib and seaborn for graphical visualizations:")
        print("  pip install matplotlib seaborn pandas numpy")
    else:
        print("\n" + "="*60)
        print("Visualizations Complete!")
        print("="*60)
        print(f"\nAll visualizations saved to: {output_dir}")
        print("\nTo view the charts, you can:")
        print("1. Navigate to the visualizations directory")
        print("2. Use an image viewer or web browser")
        print("3. Or embed them in documentation/reports")

if __name__ == "__main__":
    main()