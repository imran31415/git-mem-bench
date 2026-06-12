#!/usr/bin/env python3
"""
MCP Memory Benchmark Suite
"""
import json
import time
import random
import string
from datetime import datetime
from typing import Dict, List, Any, Callable
from mcp_client import MCPClient, BenchmarkRunner

def generate_test_data(count: int = 1000) -> List[Dict[str, Any]]:
    """Generate test data for benchmarking"""
    test_data = []
    
    for i in range(count):
        # Generate random key
        key_parts = []
        for _ in range(random.randint(1, 4)):
            part = ''.join(random.choices(string.ascii_lowercase, k=random.randint(3, 8)))
            key_parts.append(part)
        key = ".".join(key_parts)
        
        # Generate value of different sizes
        size_type = random.choice(["small", "medium", "large"])
        
        if size_type == "small":
            value = {
                "id": i,
                "timestamp": datetime.now().isoformat(),
                "active": random.choice([True, False]),
                "count": random.randint(1, 100)
            }
        elif size_type == "medium":
            value = {
                "metadata": {
                    "id": i,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "version": f"1.{random.randint(0, 9)}.{random.randint(0, 9)}"
                },
                "data": {
                    "name": f"Test Item {i}",
                    "description": " ".join([''.join(random.choices(string.ascii_letters, k=random.randint(5, 15))) 
                                            for _ in range(10)]),
                    "tags": [f"tag_{j}" for j in range(random.randint(1, 5))],
                    "settings": {
                        "enabled": random.choice([True, False]),
                        "priority": random.randint(1, 10),
                        "timeout": random.randint(1000, 10000)
                    }
                }
            }
        else:  # large
            content = " ".join([''.join(random.choices(string.ascii_letters + " ", k=random.randint(20, 100))) 
                              for _ in range(50)])
            value = {
                "document": {
                    "id": i,
                    "title": f"Document {i}: Benchmark Test",
                    "content": content,
                    "author": f"author_{random.randint(1, 100)}",
                    "created": datetime.now().isoformat(),
                    "modified": datetime.now().isoformat(),
                    "sections": [
                        {
                            "id": j,
                            "title": f"Section {j}",
                            "content": " ".join([''.join(random.choices(string.ascii_letters + " ", k=random.randint(50, 200))) 
                                              for _ in range(5)]),
                            "order": j
                        }
                        for j in range(random.randint(3, 10))
                    ],
                    "references": [
                        {
                            "id": ref_id,
                            "url": f"https://example.com/ref/{ref_id}",
                            "title": f"Reference {ref_id}"
                        }
                        for ref_id in range(random.randint(5, 20))
                    ]
                }
            }
        
        test_data.append({
            "key": key,
            "value": value,
            "size_type": size_type
        })
    
    return test_data

class MCPMemoryBenchmark:
    """Benchmark suite for MCP memory servers"""
    
    def __init__(self):
        self.runner = BenchmarkRunner()
        self.test_data = generate_test_data(100)  # Start with 100 items
    
    def setup_client(self, name: str, command: List[str]) -> bool:
        """Set up an MCP client"""
        client = MCPClient(command, name)
        if client.start():
            self.runner.add_client(name, client)
            
            # List available tools
            try:
                tools = client.list_tools()
                print(f"{name}: Found {len(tools)} tools")
                for tool in tools[:5]:  # Show first 5 tools
                    print(f"  - {tool['name']}: {tool.get('description', 'No description')[:60]}...")
                if len(tools) > 5:
                    print(f"  ... and {len(tools) - 5} more tools")
            except Exception as e:
                print(f"{name}: Failed to list tools: {e}")
            
            return True
        return False
    
    def test_basic_crud(self, client_name: str, test_items: List[Dict[str, Any]]):
        """Test basic CRUD operations"""
        client = self.runner.clients[client_name]
        
        print(f"\nTesting basic CRUD for {client_name}...")
        
        # Test SET operations
        set_results = []
        for i, item in enumerate(test_items[:50]):  # Test with first 50 items
            def set_operation():
                return client.call_tool("memSet", {
                    "key": item["key"],
                    "value": item["value"]
                })
            
            result = self.runner.measure_operation(
                client_name, f"set_{i}", set_operation
            )
            set_results.append(result)
            if i % 10 == 0:
                print(f"  Set {i+1}/50...")
        
        # Test GET operations
        get_results = []
        for i, item in enumerate(test_items[:50]):
            def get_operation():
                return client.call_tool("memGet", {
                    "key": item["key"]
                })
            
            result = self.runner.measure_operation(
                client_name, f"get_{i}", get_operation
            )
            get_results.append(result)
            if i % 10 == 0:
                print(f"  Get {i+1}/50...")
        
        # Test LIST operation
        def list_operation():
            return client.call_tool("memList", {})
        
        list_result = self.runner.measure_operation(
            client_name, "list_all", list_operation
        )
        
        # Test DELETE operations
        delete_results = []
        for i, item in enumerate(test_items[:25]):  # Delete first 25
            def delete_operation():
                return client.call_tool("memDelete", {
                    "key": item["key"]
                })
            
            result = self.runner.measure_operation(
                client_name, f"delete_{i}", delete_operation
            )
            delete_results.append(result)
            if i % 5 == 0:
                print(f"  Delete {i+1}/25...")
        
        print(f"  Completed CRUD test for {client_name}")
    
    def test_search(self, client_name: str):
        """Test search operations"""
        client = self.runner.clients[client_name]
        
        print(f"\nTesting search for {client_name}...")
        
        # Check if search tool exists
        tools = client.list_tools()
        search_tools = [t for t in tools if "search" in t["name"].lower()]
        
        if not search_tools:
            print(f"  No search tools found for {client_name}")
            return
        
        # Test each search tool
        for tool in search_tools:
            tool_name = tool["name"]
            print(f"  Testing {tool_name}...")
            
            # Try different search queries
            queries = ["test", "item", "document", "benchmark"]
            
            for i, query in enumerate(queries):
                def search_operation():
                    return client.call_tool(tool_name, {"query": query})
                
                try:
                    result = self.runner.measure_operation(
                        client_name, f"{tool_name}_{i}", search_operation
                    )
                    if result.success:
                        print(f"    Query '{query}': {result.latency_ms:.2f}ms")
                except Exception as e:
                    print(f"    Query '{query}' failed: {e}")
    
    def test_concurrent_operations(self, client_name: str, num_threads: int = 5):
        """Test concurrent operations (simplified)"""
        client = self.runner.clients[client_name]
        
        print(f"\nTesting concurrent operations for {client_name} ({num_threads} threads)...")
        
        # Create test keys for concurrent access
        test_keys = [f"concurrent.test.{i}" for i in range(num_threads * 2)]
        
        # Concurrent SETs
        print("  Concurrent SET operations...")
        for i in range(num_threads):
            key = test_keys[i]
            value = {"thread": i, "timestamp": datetime.now().isoformat()}
            
            def set_op():
                return client.call_tool("memSet", {
                    "key": key,
                    "value": value
                })
            
            self.runner.measure_operation(
                client_name, f"concurrent_set_{i}", set_op
            )
        
        # Concurrent GETs
        print("  Concurrent GET operations...")
        for i in range(num_threads):
            key = test_keys[i]
            
            def get_op():
                return client.call_tool("memGet", {
                    "key": key
                })
            
            self.runner.measure_operation(
                client_name, f"concurrent_get_{i}", get_op
            )
        
        print(f"  Completed concurrent test for {client_name}")
    
    def run_comprehensive_benchmark(self, client_name: str):
        """Run comprehensive benchmark for a client"""
        print(f"\n{'='*80}")
        print(f"RUNNING COMPREHENSIVE BENCHMARK FOR: {client_name}")
        print(f"{'='*80}")
        
        start_time = time.time()
        
        # Run tests
        self.test_basic_crud(client_name, self.test_data)
        self.test_search(client_name)
        self.test_concurrent_operations(client_name, num_threads=3)
        
        end_time = time.time()
        
        print(f"\nBenchmark completed in {end_time - start_time:.2f} seconds")
        
        # Print summary
        self.runner.print_summary()
    
    def cleanup(self):
        """Clean up all clients"""
        print("\nCleaning up...")
        for name, client in self.runner.clients.items():
            print(f"  Stopping {name}...")
            client.stop()
    
    def save_results(self, filename: str = None):
        """Save benchmark results"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"/home/dev/t/mcp-memory-benchmark/results/raw/benchmark_{timestamp}.json"
        
        self.runner.export_results(filename)
        
        # Also save test data for reference
        test_data_file = filename.replace(".json", "_testdata.json")
        with open(test_data_file, 'w') as f:
            json.dump(self.test_data, f, indent=2)
        
        print(f"\nResults saved to: {filename}")
        print(f"Test data saved to: {test_data_file}")

def main():
    """Main benchmark runner"""
    benchmark = MCPMemoryBenchmark()
    
    # Configuration for different MCP servers
    servers = {
        "git-mem": {
            "command": ["git-mem", "-repo", "/tmp/benchmark-git-mem"],
            "enabled": True
        },
        # Additional servers will be added as we install them
    }
    
    print("MCP Memory Server Benchmark")
    print("="*80)
    
    # Set up and test each server
    for name, config in servers.items():
        if config.get("enabled", False):
            print(f"\nSetting up {name}...")
            if benchmark.setup_client(name, config["command"]):
                print(f"✓ {name} setup successful")
            else:
                print(f"✗ {name} setup failed")
    
    if not benchmark.runner.clients:
        print("\nNo clients successfully set up. Exiting.")
        return
    
    # Run benchmarks for each client
    for client_name in benchmark.runner.clients.keys():
        benchmark.run_comprehensive_benchmark(client_name)
    
    # Save results
    benchmark.save_results()
    
    # Cleanup
    benchmark.cleanup()
    
    print("\n" + "="*80)
    print("BENCHMARK COMPLETED")
    print("="*80)

if __name__ == "__main__":
    main()