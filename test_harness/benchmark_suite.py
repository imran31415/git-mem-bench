#!/usr/bin/env python3
"""
MCP Memory Benchmark Suite

Uses per-server adapters so the same logical operations (WRITE, READ, SEARCH,
DELETE, LIST) are tested on every system via its actual MCP tool API.
"""
import json
import time
import random
import string
from datetime import datetime
from typing import Dict, List, Any

from mcp_client import MCPClient, BenchmarkRunner
from vector_store import VectorStoreClient
from adapters import (
    GitMemAdapter,
    EngramAdapter,
    MCPKnowledgeGraphAdapter,
    VectorStoreAdapter,
    ADAPTER_REGISTRY,
)


def generate_test_data(count: int = 100) -> List[Dict[str, Any]]:
    """Generate synthetic key-value test data."""
    test_data = []
    for i in range(count):
        # dot-separated key, 1-4 segments
        parts = [
            "".join(random.choices(string.ascii_lowercase, k=random.randint(3, 8)))
            for _ in range(random.randint(1, 4))
        ]
        key = ".".join(parts)

        size_type = random.choice(["small", "medium", "large"])
        if size_type == "small":
            value = {
                "id": i,
                "timestamp": datetime.now().isoformat(),
                "active": random.choice([True, False]),
                "count": random.randint(1, 100),
            }
        elif size_type == "medium":
            value = {
                "metadata": {
                    "id": i,
                    "created_at": datetime.now().isoformat(),
                    "version": f"1.{random.randint(0, 9)}.{random.randint(0, 9)}",
                },
                "data": {
                    "name": f"Test Item {i}",
                    "description": " ".join(
                        "".join(random.choices(string.ascii_letters, k=random.randint(5, 15)))
                        for _ in range(10)
                    ),
                    "tags": [f"tag_{j}" for j in range(random.randint(1, 5))],
                },
            }
        else:
            content = " ".join(
                "".join(random.choices(string.ascii_letters + " ", k=random.randint(20, 100)))
                for _ in range(20)
            )
            value = {
                "document": {
                    "id": i,
                    "title": f"Document {i}: Benchmark Test",
                    "content": content,
                    "author": f"author_{random.randint(1, 100)}",
                }
            }

        test_data.append({"key": key, "value": value, "size_type": size_type})

    return test_data


class MCPMemoryBenchmark:
    """Orchestrates benchmark runs across multiple MCP memory servers."""

    def __init__(self):
        self.runner = BenchmarkRunner()
        self.adapters: Dict[str, Any] = {}
        self.test_data = generate_test_data(100)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup_client(self, name: str, command: List[str], adapter_type: str,
                     env: Dict[str, str] = None,
                     vector_cfg: Dict[str, Any] = None) -> bool:
        """Start the server (or in-process store) and attach the adapter."""
        if adapter_type == "vector-store":
            client = VectorStoreClient(name, **(vector_cfg or {}))
        else:
            client = MCPClient(command, name, extra_env=env)
        if not client.start():
            return False

        self.runner.add_client(name, client)

        # Show available tools
        try:
            tools = client.list_tools()
            print(f"  {name}: {len(tools)} tools available")
            for t in tools[:5]:
                print(f"    - {t['name']}: {t.get('description', '')[:60]}")
            if len(tools) > 5:
                print(f"    ... and {len(tools) - 5} more")
        except Exception as e:
            print(f"  {name}: could not list tools: {e}")

        # Attach adapter
        adapter_cls = ADAPTER_REGISTRY.get(adapter_type)
        if adapter_cls is None:
            print(f"  WARNING: unknown adapter_type '{adapter_type}', defaulting to GitMemAdapter")
            adapter_cls = GitMemAdapter
        self.adapters[name] = adapter_cls(client)
        print(f"  {name}: using {adapter_cls.__name__}")
        if isinstance(client, VectorStoreClient):
            print(f"    backend : {client.backend_name}")
            print(f"    embedder: {client.embedder_name}")
            if not client.is_semantic:
                print("    note    : non-semantic embedder — SEARCH matches "
                      "shared tokens only (install sentence-transformers for "
                      "true semantic recall)")
        return True

    # ------------------------------------------------------------------
    # Individual test suites
    # ------------------------------------------------------------------

    def test_write(self, client_name: str, items: List[Dict]) -> None:
        adapter = self.adapters[client_name]
        print(f"\n  [WRITE] {client_name} — {len(items)} items")
        for i, item in enumerate(items):
            key, value = item["key"], item["value"]

            def op(k=key, v=value):
                return adapter.write(k, v)

            result = self.runner.measure_operation(client_name, f"write_{i}", op)
            if i % 10 == 0:
                status = "OK" if result.success else f"ERR: {result.error_message}"
                print(f"    {i+1}/{len(items)}  {result.latency_ms:.2f}ms  {status}")

    def test_read(self, client_name: str, items: List[Dict]) -> None:
        adapter = self.adapters[client_name]
        print(f"\n  [READ]  {client_name} — {len(items)} items  "
              f"(mode: {adapter.read_mode})")
        for i, item in enumerate(items):
            key = item["key"]

            def op(k=key):
                return adapter.read(k)

            result = self.runner.measure_operation(client_name, f"read_{i}", op)
            if i % 10 == 0:
                status = "OK" if result.success else f"ERR: {result.error_message}"
                print(f"    {i+1}/{len(items)}  {result.latency_ms:.2f}ms  {status}")

    def test_search(self, client_name: str, queries: List[str]) -> None:
        adapter = self.adapters[client_name]
        print(f"\n  [SEARCH] {client_name} — {len(queries)} queries")
        for i, query in enumerate(queries):
            def op(q=query):
                return adapter.search(q)

            result = self.runner.measure_operation(client_name, f"search_{i}", op)
            status = "OK" if result.success else f"ERR: {result.error_message}"
            print(f"    '{query}'  {result.latency_ms:.2f}ms  {status}")

    def test_delete(self, client_name: str, items: List[Dict]) -> None:
        adapter = self.adapters[client_name]
        print(f"\n  [DELETE] {client_name} — {len(items)} items  "
              f"(mode: {adapter.delete_mode})")
        for i, item in enumerate(items):
            key = item["key"]

            def op(k=key):
                return adapter.delete(k)

            result = self.runner.measure_operation(client_name, f"delete_{i}", op)
            if i % 5 == 0:
                status = "OK" if result.success else f"ERR: {result.error_message}"
                print(f"    {i+1}/{len(items)}  {result.latency_ms:.2f}ms  {status}")

    def test_list(self, client_name: str) -> None:
        adapter = self.adapters[client_name]
        print(f"\n  [LIST]  {client_name}")
        result = self.runner.measure_operation(
            client_name, "list_0",
            lambda: adapter.list_all()
        )
        status = "OK" if result.success else f"ERR: {result.error_message}"
        print(f"    {result.latency_ms:.2f}ms  {status}")

    # ------------------------------------------------------------------
    # Full benchmark
    # ------------------------------------------------------------------

    def run_benchmark(self, client_name: str, crud_count: int,
                      search_queries: List[str]) -> None:
        print(f"\n{'='*70}")
        print(f"BENCHMARKING: {client_name}")
        print(f"{'='*70}")

        items = self.test_data[:crud_count]

        t0 = time.time()
        self.test_write(client_name, items)
        self.test_read(client_name, items)
        self.test_search(client_name, search_queries)
        self.test_delete(client_name, items[:crud_count // 2])
        self.test_list(client_name)
        elapsed = time.time() - t0

        print(f"\n  Done in {elapsed:.1f}s")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        for name, client in self.runner.clients.items():
            client.stop()
