#!/usr/bin/env python3
"""
Generic MCP Client Wrapper for Benchmarking MCP Memory Servers
"""
import json
import subprocess
import time
import threading
import queue
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple
import statistics
import time

# Try to import psutil, but provide fallback
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available. Resource monitoring disabled.")

@dataclass
class BenchmarkResult:
    """Container for benchmark results"""
    operation: str
    success: bool
    latency_ms: float
    memory_usage_mb: float
    cpu_percent: float
    error_message: Optional[str] = None
    additional_metrics: Optional[Dict[str, Any]] = None

class MCPClient:
    """Generic MCP client for benchmarking memory servers"""

    def __init__(self, command: List[str], name: str = "unknown",
                 extra_env: Optional[Dict[str, str]] = None):
        self.command = command
        self.name = name
        self.extra_env = extra_env or {}
        self.process = None
        self.stdin = None
        self.stdout = None
        self.stderr = None
        self.request_id = 0
        self.responses = {}
        self.response_queue = queue.Queue()
        self.reader_thread = None
        self.initialized = False

    def start(self):
        """Start the MCP server process. Returns False if it can't be launched."""
        import os
        env = os.environ.copy()
        env.update(self.extra_env)

        try:
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env,
            )
        except (FileNotFoundError, OSError) as e:
            # Binary not installed / not executable — let the caller skip it
            print(f"Could not launch {self.name}: {e}")
            self.process = None
            return False

        # Start response reader thread
        self.reader_thread = threading.Thread(target=self._read_responses, daemon=True)
        self.reader_thread.start()

        # Initialize connection
        return self._initialize()
    
    def _read_responses(self):
        """Read responses from stdout in background thread"""
        while self.process and self.process.poll() is None:
            try:
                line = self.process.stdout.readline()
                if line:
                    try:
                        response = json.loads(line.strip())
                        if 'id' in response:
                            self.response_queue.put(response)
                    except json.JSONDecodeError:
                        # Not a JSON response, likely debug output
                        pass
            except (ValueError, IOError):
                break
    
    def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC request and wait for response"""
        self.request_id += 1
        request_id = self.request_id
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        # Send request
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        
        # Wait for response with timeout
        timeout = 10.0  # seconds
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = self.response_queue.get(timeout=0.1)
                if response.get('id') == request_id:
                    return response
            except queue.Empty:
                continue
        
        raise TimeoutError(f"No response for request {request_id} within {timeout} seconds")
    
    def _initialize(self) -> bool:
        """Initialize MCP connection"""
        try:
            response = self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "mcp-benchmark",
                    "version": "1.0.0"
                }
            })
            self.initialized = True
            return True
        except Exception as e:
            print(f"Failed to initialize {self.name}: {e}")
            return False
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools"""
        response = self._send_request("tools/list", {})
        return response.get('result', {}).get('tools', [])
    
    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a specific tool"""
        response = self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        return response.get('result', {})
    
    def stop(self):
        """Stop the MCP server process"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
        
        if self.reader_thread:
            self.reader_thread.join(timeout=1)
            self.reader_thread = None

class BenchmarkRunner:
    """Runner for MCP memory server benchmarks"""
    
    def __init__(self):
        self.results = []
        self.clients = {}
        
    def add_client(self, name: str, client: MCPClient):
        """Add an MCP client for benchmarking"""
        self.clients[name] = client
    
    def measure_operation(self, client_name: str, operation: str, 
                         func, *args, **kwargs) -> BenchmarkResult:
        """Measure a single operation"""
        client = self.clients[client_name]
        
        # Measure memory before if psutil is available
        if PSUTIL_AVAILABLE and client.process:
            process = psutil.Process(client.process.pid)
            memory_before = process.memory_info().rss / 1024 / 1024  # MB
            cpu_before = process.cpu_percent(interval=None)
        else:
            memory_before = 0
            cpu_before = 0
        
        # Time the operation
        start_time = time.perf_counter()
        
        try:
            result = func(*args, **kwargs)
            success = True
            error = None
        except Exception as e:
            result = None
            success = False
            error = str(e)
        
        end_time = time.perf_counter()
        
        # Measure memory after if psutil is available
        if PSUTIL_AVAILABLE and client.process:
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            cpu_after = process.cpu_percent(interval=None)
            memory_delta = memory_after - memory_before
            cpu_delta = cpu_after - cpu_before
        else:
            memory_delta = 0
            cpu_delta = 0
        
        latency_ms = (end_time - start_time) * 1000
        
        benchmark_result = BenchmarkResult(
            operation=operation,
            success=success,
            latency_ms=latency_ms,
            memory_usage_mb=memory_delta,
            cpu_percent=cpu_delta,
            error_message=error,
            additional_metrics={"result": result} if result else None
        )
        
        self.results.append((client_name, benchmark_result))
        return benchmark_result
    
    def run_batch(self, client_name: str, operation: str, 
                 count: int, func, *args, **kwargs) -> List[BenchmarkResult]:
        """Run a batch of operations"""
        results = []
        for i in range(count):
            result = self.measure_operation(client_name, f"{operation}_{i}", func, *args, **kwargs)
            results.append(result)
        return results
    
    def get_summary_stats(self, client_name: str, operation: str) -> Dict[str, Any]:
        """Get summary statistics for an operation type"""
        client_results = [
            r for name, r in self.results
            if name == client_name and r.operation.startswith(operation)
        ]

        if not client_results:
            return {}

        latencies = sorted(r.latency_ms for r in client_results if r.success)
        successes = sum(1 for r in client_results if r.success)

        def percentile(data, pct):
            if not data:
                return 0
            k = (len(data) - 1) * pct / 100
            lo, hi = int(k), min(int(k) + 1, len(data) - 1)
            return data[lo] + (data[hi] - data[lo]) * (k - lo)

        mean_ms = statistics.mean(latencies) if latencies else 0
        return {
            "operation": operation,
            "total_operations": len(client_results),
            "successful_operations": successes,
            "success_rate": successes / len(client_results) * 100 if client_results else 0,
            "latency_mean_ms": mean_ms,
            "latency_median_ms": statistics.median(latencies) if latencies else 0,
            "latency_std_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0,
            "latency_min_ms": latencies[0] if latencies else 0,
            "latency_max_ms": latencies[-1] if latencies else 0,
            "latency_p75_ms": percentile(latencies, 75),
            "latency_p95_ms": percentile(latencies, 95),
            "latency_p99_ms": percentile(latencies, 99),
            "throughput_ops_sec": (1000.0 / mean_ms) if mean_ms > 0 else 0,
            "avg_memory_delta_mb": statistics.mean([r.memory_usage_mb for r in client_results]),
            "avg_cpu_delta": statistics.mean([r.cpu_percent for r in client_results]),
        }
    
    def export_results(self, filename: str):
        """Export results to JSON file"""
        export_data = {
            "clients": list(self.clients.keys()),
            "results": [
                {
                    "client": client_name,
                    "operation": result.operation,
                    "success": result.success,
                    "latency_ms": result.latency_ms,
                    "memory_usage_mb": result.memory_usage_mb,
                    "cpu_percent": result.cpu_percent,
                    "error_message": result.error_message,
                }
                for client_name, result in self.results
            ],
            "summaries": {
                client_name: {
                    op: self.get_summary_stats(client_name, op)
                    for op in set(r.operation.split('_')[0] for _, r in self.results 
                                 if _.startswith(client_name))
                }
                for client_name in self.clients.keys()
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"Results exported to {filename}")
    
    def print_summary(self):
        """Print a summary of benchmark results"""
        print("\n" + "="*80)
        print("BENCHMARK SUMMARY")
        print("="*80)
        
        for client_name in self.clients.keys():
            print(f"\n{client_name}:")
            print("-" * 40)
            
            # Group by operation type
            operations = set(r.operation.split('_')[0] for _, r in self.results 
                           if _.startswith(client_name))
            
            for op in sorted(operations):
                stats = self.get_summary_stats(client_name, op)
                if stats:
                    print(f"  {op}:")
                    print(f"    Success Rate: {stats['success_rate']:.1f}%")
                    print(f"    Latency: {stats['latency_mean_ms']:.2f}ms mean "
                          f"({stats['latency_min_ms']:.2f}-{stats['latency_max_ms']:.2f}ms)")
                    print(f"    Throughput: {1000/stats['latency_mean_ms']:.1f} ops/sec "
                          f"(estimated)" if stats['latency_mean_ms'] > 0 else "    Throughput: N/A")

# Example usage
if __name__ == "__main__":
    # Example configuration for git-mem
    git_mem_config = {
        "command": ["git-mem", "-repo", "/tmp/benchmark-git-mem"],
        "name": "git-mem"
    }
    
    print("MCP Benchmark Client Test")
    print("This is a generic MCP client wrapper for benchmarking memory servers.")
    print("\nTo use:")
    print("1. Create MCPClient instances for each server")
    print("2. Add them to BenchmarkRunner")
    print("3. Run benchmark operations")
    print("4. Analyze results")