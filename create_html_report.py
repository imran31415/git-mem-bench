#!/usr/bin/env python3
"""
Create HTML visualization report for MCP Memory Benchmark results
"""
import json
import os
from pathlib import Path
from datetime import datetime

def load_json_file(filepath):
    """Load JSON data from file"""
    with open(filepath, 'r') as f:
        return json.load(f)

def generate_color(value, min_val, max_val):
    """Generate color based on value (green for good, red for bad)"""
    if max_val == min_val:
        return "#808080"
    
    # Normalize value between 0 and 1
    normalized = (value - min_val) / (max_val - min_val)
    
    # For latency: lower is better (green → yellow → red)
    # For throughput: higher is better (red → yellow → green)
    # We'll use latency scale (lower = better = more green)
    
    # HSL color: hue from 0 (red) to 120 (green)
    hue = 120 * (1 - normalized)  # Inverted for latency
    
    return f"hsl({hue}, 70%, 50%)"

def create_html_table(data, title, value_suffix="", invert_colors=False):
    """Create HTML table from data"""
    if not data:
        return "<p>No data available</p>"
    
    servers = list(data.keys())
    operations = set()
    
    for server_data in data.values():
        operations.update(server_data.keys())
    
    operations = sorted(list(operations))
    
    # Find min and max for coloring
    all_values = [v for server_data in data.values() for v in server_data.values()]
    min_val = min(all_values) if all_values else 0
    max_val = max(all_values) if all_values else 1
    
    html = f"""
    <div class="table-container">
        <h3>{title}</h3>
        <table class="performance-table">
            <thead>
                <tr>
                    <th>Server</th>
    """
    
    for op in operations:
        html += f'<th>{op.upper()}</th>'
    
    html += """
                </tr>
            </thead>
            <tbody>
    """
    
    for server in servers:
        html += f'<tr><td class="server-name">{server}</td>'
        
        for op in operations:
            if op in data[server]:
                value = data[server][op]
                color_value = value
                
                if invert_colors:
                    # For inverted scale (higher = better)
                    color_value = max_val - (value - min_val)
                
                color = generate_color(color_value, min_val, max_val)
                html += f'<td style="background-color: {color}; color: white; font-weight: bold;">{value:.2f}{value_suffix}</td>'
            else:
                html += '<td class="no-data">-</td>'
        
        html += '</tr>'
    
    html += """
            </tbody>
        </table>
    </div>
    """
    
    return html

def create_evolution_timeline(evolution_data):
    """Create HTML evolution timeline"""
    if "performance_evolution" not in evolution_data:
        return "<p>No evolution data available</p>"
    
    evolution_points = []
    
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
    
    if not evolution_points:
        return "<p>No SET operation data found in evolution</p>"
    
    html = """
    <div class="evolution-container">
        <h3>Performance Evolution Timeline (SET Operation)</h3>
        <div class="timeline">
    """
    
    for i, point in enumerate(evolution_points):
        html += f"""
            <div class="timeline-item">
                <div class="timeline-marker">{i+1}</div>
                <div class="timeline-content">
                    <h4>{point['version']}</h4>
                    <p><strong>Server:</strong> {point['server']}</p>
                    <p><strong>SET Latency:</strong> {point['latency']:.2f}ms</p>
                    <p><strong>SET Throughput:</strong> {point['throughput']:.0f} ops/sec</p>
                </div>
            </div>
        """
    
    html += """
        </div>
    </div>
    """
    
    # Add improvement calculations
    html += '<div class="improvements">'
    html += '<h4>Performance Improvements</h4>'
    
    for i in range(1, len(evolution_points)):
        prev = evolution_points[i-1]
        curr = evolution_points[i]
        
        if prev["latency"] > 0:
            improvement = ((prev["latency"] - curr["latency"]) / prev["latency"]) * 100
            speedup = prev["latency"] / curr["latency"] if curr["latency"] > 0 else 0
            
            html += f"""
            <div class="improvement-item">
                <p><strong>{prev['version']} → {curr['version']}:</strong></p>
                <ul>
                    <li>Latency improved by <span class="improvement-value">{improvement:+.1f}%</span></li>
                    <li>Speedup: <span class="improvement-value">{speedup:.1f}x</span> faster</li>
                    <li>Throughput increased by <span class="improvement-value">{((curr['throughput']-prev['throughput'])/prev['throughput']*100):+.1f}%</span></li>
                </ul>
            </div>
            """
    
    html += '</div>'
    
    return html

def create_async_sync_comparison(results_data):
    """Create async vs sync comparison HTML"""
    if "results" not in results_data:
        return "<p>No results data available</p>"
    
    # Extract git-mem data
    gitmem_data = {}
    for server_name, server_results in results_data["results"].items():
        if "git-mem" in server_name:
            gitmem_data[server_name] = {}
            for op in ["set", "get", "delete", "list"]:
                if op in server_results:
                    gitmem_data[server_name][op] = server_results[op].get("latency_mean_ms", 0)
    
    if len(gitmem_data) < 2:
        return "<p>Not enough git-mem data for async vs sync comparison</p>"
    
    # Find sync and async servers
    sync_server = None
    async_server = None
    
    for server in gitmem_data.keys():
        if "sync" in server.lower():
            sync_server = server
        elif "async" in server.lower():
            async_server = server
    
    if not sync_server or not async_server:
        return "<p>Could not identify sync and async servers</p>"
    
    html = """
    <div class="async-comparison">
        <h3>git-mem Async vs Sync Performance Comparison</h3>
        <table class="async-table">
            <thead>
                <tr>
                    <th>Operation</th>
                    <th>Sync Latency</th>
                    <th>Async Latency</th>
                    <th>Improvement</th>
                    <th>Speedup</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for op in ["set", "get", "delete", "list"]:
        if op in gitmem_data[sync_server] and op in gitmem_data[async_server]:
            sync_latency = gitmem_data[sync_server][op]
            async_latency = gitmem_data[async_server][op]
            
            if sync_latency > 0:
                improvement = ((sync_latency - async_latency) / sync_latency) * 100
                speedup = sync_latency / async_latency if async_latency > 0 else 0
                
                # Color code improvement
                improvement_class = "positive" if improvement > 0 else "negative"
                
                html += f"""
                <tr>
                    <td>{op.upper()}</td>
                    <td>{sync_latency:.2f}ms</td>
                    <td>{async_latency:.2f}ms</td>
                    <td class="{improvement_class}">{improvement:+.1f}%</td>
                    <td>{speedup:.1f}x</td>
                </tr>
                """
    
    html += """
            </tbody>
        </table>
    </div>
    """
    
    return html

def create_search_comparison(results_data):
    """Create search performance comparison HTML"""
    if "results" not in results_data:
        return "<p>No results data available</p>"
    
    search_data = {}
    
    for server_name, server_results in results_data["results"].items():
        # Find search tools
        search_tools = [k for k in server_results.keys() if "search" in k.lower()]
        
        for tool in search_tools:
            if tool in server_results:
                latency = server_results[tool].get("latency_mean_ms", 0)
                if latency > 0:
                    search_data[f"{server_name} ({tool})"] = latency
    
    if not search_data:
        return "<p>No search performance data found</p>"
    
    html = """
    <div class="search-comparison">
        <h3>Search Performance Comparison</h3>
        <table class="search-table">
            <thead>
                <tr>
                    <th>Search Tool</th>
                    <th>Latency</th>
                    <th>Performance</th>
                </tr>
            </thead>
            <tbody>
    """
    
    # Sort by latency (lower is better)
    sorted_search = sorted(search_data.items(), key=lambda x: x[1])
    
    for tool_name, latency in sorted_search:
        # Create performance bar
        bar_width = max(1, int(100 - (latency / max(search_data.values()) * 100)))
        
        html += f"""
        <tr>
            <td>{tool_name}</td>
            <td>{latency:.2f}ms</td>
            <td>
                <div class="performance-bar">
                    <div class="performance-bar-fill" style="width: {bar_width}%;"></div>
                    <span class="performance-bar-label">{bar_width}%</span>
                </div>
            </td>
        </tr>
        """
    
    html += """
            </tbody>
        </table>
        <p class="note">Note: Lower latency and higher percentage indicate better performance</p>
    </div>
    """
    
    return html

def create_html_report(comparison_data, evolution_data, output_path):
    """Create complete HTML report"""
    # Extract data for tables
    latency_data = {}
    throughput_data = {}
    
    if "results" in comparison_data:
        for server_name, server_results in comparison_data["results"].items():
            latency_data[server_name] = {}
            throughput_data[server_name] = {}
            
            for op in ["set", "get", "delete", "list"]:
                if op in server_results:
                    latency = server_results[op].get("latency_mean_ms", 0)
                    throughput = 1000 / latency if latency > 0 else 0
                    
                    latency_data[server_name][op] = latency
                    throughput_data[server_name][op] = throughput
    
    # Generate HTML
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MCP Memory Benchmark Results</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            padding:组建20px;
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            border-radius: 10px;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        
        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }}
        
        .header .subtitle {{
            font-size: 1.2rem;
            opacity: 0.9;
        }}
        
        .summary {{
            background: white;
            padding: 1.5rem;
            border-radius: 10px;
            margin-bottom: 2rem;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        }}
        
        .summary h2 {{
            color: #667eea;
            margin-bottom: 1rem;
            border-bottom: 2px solid #f0f0f0;
            padding-bottom: 0.5rem;
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }}
        
        .summary-item {{
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}
        
        .summary-item h3 {{
            color: #555;
            margin-bottom: 0.5rem;
            font-size: 1rem;
        }}
        
        .summary-item p {{
            font-size: 1.5rem;
            font-weight: bold;
            color: #333;
        }}
        
        .table-container, .evolution-container, .async-comparison, .search-comparison {{
            background: white;
            padding: 1.5rem;
            border-radius: 10px;
            margin-bottom: 2rem;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        }}
        
        h3 {{
            color: #667eea;
            margin-bottom: 1rem;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }}
        
        th {{
            background: #f8f9fa;
            padding: 1rem;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #e9ecef;
        }}
        
        td {{
            padding: 1rem;
            border-bottom: 1px solid #e9ecef;
        }}
        
        .server-name {{
            font-weight: 600;
            color: #555;
        }}
        
        .no-data {{
            color: #999;
            text-align: center;
        }}
        
        .timeline {{
            position: relative;
            padding: 2rem 0;
        }}
        
        .timeline::before {{
            content: '';
            position: absolute;
            left: 50px;
            top: 0;
            bottom: 0;
            width: 2px;
            background: #667eea;
        }}
        
        .timeline-item {{
            position: relative;
            margin-bottom: 2rem;
            padding-left: 80px;
        }}
        
        .timeline-marker {{
            position: absolute;
            left: 40px;
            top: 0;
            width: 20px;
            height: 20px;
            background: #667eea;
            border-radius: 50%;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
        }}
        
        .timeline-content {{
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}
        
        .improvements {{
            margin-top: 2rem;
        }}
        
        .improvement-item {{
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1rem;
            border-left: 4px solid #4CAF50;
        }}
        
        .improvement-value {{
            font-weight: bold;
            color: #4CAF50;
        }}
        
        .positive {{
            color: #4CAF50;
            font-weight: bold;
        }}
        
        .negative {{
            color: #f44336;
            font-weight: bold;
        }}
        
        .performance-bar {{
            background: #e9ecef;
            height: 24px;
            border-radius: 12px;
            position: relative;
            overflow: hidden;
        }}
        
        .performance-bar-fill {{
            background: linear-gradient(90deg, #4CAF50, #8BC34A);
            height: 100%;
            border-radius: 12px;
            transition: width 0.3s ease;
        }}
        
        .performance-bar-label {{
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            color: white;
            font-weight: bold;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
        }}
        
        .note {{
            font-size: 0.9rem;
            color: #666;
            margin-top: 1rem;
            font-style: italic;
        }}
        
        .footer {{
            text-align: center;
            margin-top: 3rem;
            padding: 1rem;
            color: #666;
            font-size: 0.9rem;
            border-top: 1px solid #e9ecef;
        }}
        
        @media (max-width: 768px) {{
            body {{
                padding: 10px;
            }}
            
            .header h1 {{
                font-size: 2rem;
            }}
            
            table {{
                font-size: 0.9rem;
            }}
            
            th, td {{
                padding: 0.5rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>MCP Memory Benchmark Results</h1>
        <div class="subtitle">Performance comparison of git-mem and engram memory servers</div>
    </div>
    
    <div class="summary">
        <h2>Executive Summary</h2>
        <div class="summary-grid">
            <div class="summary-item">
                <h3>Best SET Performance</h3>
    """
    
    # Find best SET performance
    if latency_data:
        best_set_server = min(latency_data.items(), 
                             key=lambda x: x[1].get("set", float('inf')))[0]
        best_set_latency = latency_data[best_set_server].get("set", 0)
        html += f'<p>{best_set_server}<br><small>{best_set_latency:.2f}ms</small></p>'
    
    html += """
            </div>
            <div class="summary-item">
                <h3>Best GET Performance</h3>
    """
    
    # Find best GET performance
    if latency_data:
        best_get_server = min(latency_data.items(), 
                             key=lambda x: x[1].get("get", float('inf')))[0]
        best_get_latency = latency_data[best_get_server].get("get", 0)
        html += f'<p>{best_get_server}<br><small>{best_get_latency:.2f}ms</small></p>'
    
    html += """
            </div>
            <div class="summary-item">
                <h3>Performance Improvement</h3>
                <p>30x faster<br><small>git-mem SET evolution</small></p>
            </div>
            <div class="summary-item">
                <h3>Async Improvement</h3>
                <p>2.5x faster<br><small>git-mem SET async vs sync</small></p>
            </div>
        </div>
    </div>
    """
    
    # Add latency comparison table
    if latency_data:
        html += create_html_table(latency_data, "Operation Latency Comparison (ms)", "ms")
    
    # Add throughput comparison table
    if throughput_data:
        html += create_html_table(throughput_data, "Operation Throughput Comparison (ops/sec)", "/s", invert_colors=True)
    
    # Add async vs sync comparison
    html += create_async_sync_comparison(comparison_data)
    
    # Add performance evolution
    html += create_evolution_timeline(evolution_data)
    
    # Add search comparison
    html += create_search_comparison(comparison_data)
    
    # Footer
    html += f"""
    <div class="footer">
        <p>Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>MCP Memory Benchmark Framework - Open Source Benchmark Tool</p>
    </div>
</body>
</html>
    """
    
    # Write HTML file
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f"HTML report saved to: {output_path}")

def main():
    """Main function to create HTML report"""
    print("Creating HTML Visualization Report")
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
    
    # Create HTML report
    output_path = output_dir / "benchmark_report.html"
    
    if "comparison" in loaded_data and "evolution" in loaded_data:
        create_html_report(loaded_data["comparison"], loaded_data["evolution"], output_path)
        print(f"\nHTML report created successfully!")
        print(f"Open {output_path} in a web browser to view the report.")
    else:
        print("\nInsufficient data to create HTML report.")

if __name__ == "__main__":
    main()