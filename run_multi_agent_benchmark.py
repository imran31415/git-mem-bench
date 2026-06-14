#!/usr/bin/env python3
"""
Multi-Agent MCP Memory Benchmark Runner

This script runs comprehensive multi-agent benchmarks that simulate real-world
MCP use cases with multiple agents, collaborative tasks, and complex scenarios.

Usage:
    python run_multi_agent_benchmark.py [--config CONFIG_FILE] [--server SERVER_NAME] [--output DIR]

For spawning agents via MCP orchestration:
    Uses the mcp__agent_orchestrator__spawn_agent tool for distributed benchmarking.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add test_harness to path
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO_ROOT, "test_harness"))

try:
    from multi_agent_benchmark import MCPMultiAgentBenchmark, OrchestrationResult
    from mcp_client import MCPClient
    from adapters import ADAPTER_REGISTRY
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you're running from the repository root directory")
    sys.exit(1)


# ============================================================================
# CONFIGURATION
# ============================================================================

DEFAULT_CONFIG = {
    "scenarios": {
        "single_agent_long_conversation": {"enabled": True, "num_turns": 20},
        "multi_agent_collaborative": {"enabled": True, "num_agents": 3, "tasks_per_agent": 5},
        "agent_handoff": {"enabled": True, "num_handlers": 4, "items_per_handler": 3},
        "session_recovery": {"enabled": True, "sessions": 5, "items_per_session": 10},
        "concurrent_contention": {"enabled": True, "num_agents": 10, "operations_per_agent": 5},
        "error_recovery": {"enabled": True, "num_agents": 5, "error_rate": 0.2},
        "complex_search": {"enabled": True, "num_agents": 3, "searches_per_agent": 10},
        "batch_vs_streaming": {"enabled": True, "batch_size": 50, "streaming_chunk": 5},
        "large_payloads": {"enabled": True, "sizes": [1000, 10000, 100000]},
        "special_characters": {"enabled": True},
        "hierarchical_structure": {"enabled": True, "num_workers": 4, "tasks_per_worker": 3},
        "memory_eviction": {"enabled": True, "initial_items": 50, "iterations": 20},
    },
    "output_directory": "/home/dev/git-mem-bench/results/multi_agent",
    "clear_between_scenarios": True,
}


# ============================================================================
# RESULTS COMPARISON
# ============================================================================

def print_scenario_comparison_table(all_results: Dict[str, List[OrchestrationResult]]) -> None:
    """Print a comparison table across all servers and scenarios."""
    if not all_results:
        return

    # Get all scenario names
    servers = list(all_results.keys())
    if not servers:
        return

    scenario_names = set()
    for results in all_results.values():
        for r in results:
            scenario_names.add(r.scenario_name)

    print("\n" + "=" * 100)
    print("MULTI-AGENT BENCHMARK COMPARISON TABLE")
    print("=" * 100)

    # Header
    print(f"\n{'Scenario':<35} {'Server':<20} {'Duration (ms)':<15} {'Ops':<8} {'Success':<10} {'Contention':<10}")
    print("-" * 100)

    for scenario in sorted(scenario_names):
        first_row = True
        for server in servers:
            results = all_results[server]
            matching = [r for r in results if r.scenario_name == scenario]
            if matching:
                result = matching[0]
                duration = result.total_duration_ms
                ops_count = len(result.operations)
                success_rate = sum(1 for _, _, _, s in result.operations if s) / ops_count * 100 if ops_count else 0
                contention = result.memory_contention_events

                scenario_display = scenario if first_row else ""
                print(f"{scenario_display:<35} {server:<20} {duration:<15.2f} {ops_count:<8} {success_rate:<10.1f}% {contention:<10}")

                first_row = False

        print("-" * 100)


def calculate_speedups(baseline_results: List[OrchestrationResult],
                      comparison_results: List[OrchestrationResult]) -> Dict[str, float]:
    """Calculate speedup factors between two sets of results."""
    speedups = {}

    baseline_by_scenario = {r.scenario_name: r for r in baseline_results}
    comparison_by_scenario = {r.scenario_name: r for r in comparison_results}

    for scenario_name, baseline in baseline_by_scenario.items():
        if scenario_name in comparison_by_scenario:
            comparison = comparison_by_scenario[scenario_name]
            if baseline.total_duration_ms > 0:
                speedup = baseline.total_duration_ms / comparison.total_duration_ms
                speedups[scenario_name] = speedup

    return speedups


# ============================================================================
# MCP ORCHESTRATION AGENT SPAWNER
# ============================================================================

class OrchestrationAgentSpawner:
    """
    Spawns and manages benchmark agents via MCP orchestration.
    Uses the mcp__agent_orchestrator__spawn_agent tool for distributed execution.
    """

    def __init__(self, benchmark: MCPMultiAgentBenchmark):
        self.benchmark = benchmark
        self.spawned_agents: List[Dict] = []
        self.results: Dict[str, Any] = {}

    def spawn_benchmark_agent(self, agent_id: str, scenario: str,
                            config: Dict = None) -> Optional[str]:
        """
        Spawn a benchmark agent for a specific scenario.
        Returns the task_id for tracking.
        """
        config = config or {}

        prompt = f"""
        Run benchmark scenario '{scenario}' for agent '{agent_id}'.

        Configuration:
        {json.dumps(config, indent=2)}

        Execute the benchmark and return the results as JSON with:
        - scenario_name
        - duration_ms
        - operations_count
        - success_rate
        - errors

        Working directory: {REPO_ROOT}
        """

        try:
            task_id = mcp__agent_orchestrator__spawn_agent(
                assistant="ante",
                prompt=prompt,
                workdir=REPO_ROOT
            )

            self.spawned_agents.append({
                "task_id": task_id,
                "agent_id": agent_id,
                "scenario": scenario
            })

            return task_id
        except NameError:
            # mcp__agent_orchestrator not available in this context
            return None

    def wait_for_agents(self, timeout: int = 300) -> Dict[str, Any]:
        """Wait for all spawned agents to complete."""
        results = {}

        for agent_info in self.spawned_agents:
            task_id = agent_info["task_id"]

            try:
                status = mcp__agent_orchestrator__get_agent_status(task_id)

                if status.get("state") == "exited":
                    output = mcp__agent_orchestrator__wait_for_agent(
                        task_id=task_id,
                        timeout=timeout
                    )
                    results[agent_info["agent_id"]] = {
                        "success": True,
                        "output": output
                    }
                else:
                    results[agent_info["agent_id"]] = {
                        "success": False,
                        "error": f"Agent still in state: {status.get('state')}"
                    }
            except Exception as e:
                results[agent_info["agent_id"]] = {
                    "success": False,
                    "error": str(e)
                }

        return results


# ============================================================================
# MAIN BENCHMARK RUNNER
# ============================================================================

def load_config(config_file: str = None) -> Dict:
    """Load benchmark configuration."""
    if config_file and os.path.exists(config_file):
        with open(config_file) as f:
            return json.load(f)
    return DEFAULT_CONFIG.copy()


def create_adapter_for_server(server_name: str, server_config: Dict) -> Any:
    """Create an adapter instance for a server."""
    adapter_type = server_config.get("adapter_type", "git-mem")
    adapter_cls = ADAPTER_REGISTRY.get(adapter_type)

    if adapter_cls is None:
        print(f"Warning: Unknown adapter type '{adapter_type}', using GitMemAdapter")
        adapter_cls = GitMemAdapter

    # Create MCP client
    command = server_config["command"]
    extra_env = server_config.get("env", {})

    client = MCPClient(command, server_name, extra_env=extra_env)
    if not client.start():
        raise RuntimeError(f"Failed to start MCP client for {server_name}")

    return adapter_cls(client)


def run_benchmark_for_server(server_name: str, server_config: Dict,
                             config: Dict) -> List[OrchestrationResult]:
    """Run benchmarks for a specific server."""
    print(f"\n{'='*70}")
    print(f"BENCHMARKING: {server_name}")
    print(f"{'='*70}")

    try:
        adapter = create_adapter_for_server(server_name, server_config)
    except Exception as e:
        print(f"  Failed to create adapter: {e}")
        return []

    benchmark = MCPMultiAgentBenchmark(lambda aid: adapter)

    # Run selected scenarios
    scenarios_config = config.get("scenarios", DEFAULT_CONFIG["scenarios"])
    clear_between = config.get("clear_between_scenarios", True)

    results = []

    # Scenario 1: Single Agent Long Conversation
    if scenarios_config.get("single_agent_long_conversation", {}).get("enabled", True):
        num_turns = scenarios_config.get("single_agent_long_conversation", {}).get("num_turns", 20)
        result = benchmark.scenario_single_agent_long_conversation(
            adapter=adapter, num_turns=num_turns
        )
        results.append(result)

    # Scenario 2: Multi-Agent Collaborative
    if scenarios_config.get("multi_agent_collaborative", {}).get("enabled", True):
        num_agents = scenarios_config.get("multi_agent_collaborative", {}).get("num_agents", 3)
        tasks = scenarios_config.get("multi_agent_collaborative", {}).get("tasks_per_agent", 5)
        result = benchmark.scenario_multi_agent_collaborative(
            adapter=adapter, num_agents=num_agents, tasks_per_agent=tasks
        )
        results.append(result)

    # Scenario 3: Agent Handoff
    if scenarios_config.get("agent_handoff", {}).get("enabled", True):
        handlers = scenarios_config.get("agent_handoff", {}).get("num_handlers", 4)
        items = scenarios_config.get("agent_handoff", {}).get("items_per_handler", 3)
        result = benchmark.scenario_agent_handoff(
            adapter=adapter, num_handlers=handlers, items_per_handler=items
        )
        results.append(result)

    # Scenario 4: Session Recovery
    if scenarios_config.get("session_recovery", {}).get("enabled", True):
        sessions = scenarios_config.get("session_recovery", {}).get("sessions", 5)
        items = scenarios_config.get("session_recovery", {}).get("items_per_session", 10)
        result = benchmark.scenario_session_recovery(
            adapter=adapter, sessions=sessions, items_per_session=items
        )
        results.append(result)

    # Scenario 5: Concurrent Contention
    if scenarios_config.get("concurrent_contention", {}).get("enabled", True):
        num_agents = scenarios_config.get("concurrent_contention", {}).get("num_agents", 10)
        ops = scenarios_config.get("concurrent_contention", {}).get("operations_per_agent", 5)
        result = benchmark.scenario_concurrent_contention(
            adapter=adapter, num_agents=num_agents, operations_per_agent=ops
        )
        results.append(result)

    # Scenario 6: Error Recovery
    if scenarios_config.get("error_recovery", {}).get("enabled", True):
        num_agents = scenarios_config.get("error_recovery", {}).get("num_agents", 5)
        error_rate = scenarios_config.get("error_recovery", {}).get("error_rate", 0.2)
        result = benchmark.scenario_error_recovery(
            adapter=adapter, num_agents=num_agents, error_rate=error_rate
        )
        results.append(result)

    # Scenario 7: Complex Search
    if scenarios_config.get("complex_search", {}).get("enabled", True):
        num_agents = scenarios_config.get("complex_search", {}).get("num_agents", 3)
        searches = scenarios_config.get("complex_search", {}).get("searches_per_agent", 10)
        result = benchmark.scenario_complex_search(
            adapter=adapter, num_agents=num_agents, searches_per_agent=searches
        )
        results.append(result)

    # Scenario 8: Batch vs Streaming
    if scenarios_config.get("batch_vs_streaming", {}).get("enabled", True):
        batch_size = scenarios_config.get("batch_vs_streaming", {}).get("batch_size", 50)
        chunk = scenarios_config.get("batch_vs_streaming", {}).get("streaming_chunk", 5)
        result = benchmark.scenario_batch_vs_streaming(
            adapter=adapter, batch_size=batch_size, streaming_chunk=chunk
        )
        results.append(result)

    # Scenario 9: Large Payloads
    if scenarios_config.get("large_payloads", {}).get("enabled", True):
        sizes = scenarios_config.get("large_payloads", {}).get("sizes", [1000, 10000, 100000])
        result = benchmark.scenario_large_payloads(adapter=adapter, sizes=sizes)
        results.append(result)

    # Scenario 10: Special Characters
    if scenarios_config.get("special_characters", {}).get("enabled", True):
        result = benchmark.scenario_special_characters(adapter=adapter)
        results.append(result)

    # Scenario 11: Hierarchical Structure
    if scenarios_config.get("hierarchical_structure", {}).get("enabled", True):
        num_workers = scenarios_config.get("hierarchical_structure", {}).get("num_workers", 4)
        tasks = scenarios_config.get("hierarchical_structure", {}).get("tasks_per_worker", 3)
        result = benchmark.scenario_hierarchical_structure(
            adapter=adapter, num_workers=num_workers, tasks_per_worker=tasks
        )
        results.append(result)

    # Scenario 12: Memory Eviction
    if scenarios_config.get("memory_eviction", {}).get("enabled", True):
        initial = scenarios_config.get("memory_eviction", {}).get("initial_items", 50)
        iterations = scenarios_config.get("memory_eviction", {}).get("iterations", 20)
        result = benchmark.scenario_memory_eviction(
            adapter=adapter, initial_items=initial, iterations=iterations
        )
        results.append(result)

    # Cleanup
    try:
        adapter.client.stop()
    except:
        pass

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Agent MCP Memory Benchmark Runner"
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to configuration file (JSON)",
        default=None
    )
    parser.add_argument(
        "--server", "-s",
        help="Specific server to benchmark (default: all enabled servers)",
        default=None
    )
    parser.add_argument(
        "--output", "-o",
        help="Output directory for results",
        default=None
    )
    parser.add_argument(
        "--spawn-agents",
        help="Use MCP orchestration to spawn agents (requires MCP agent orchestrator)",
        action="store_true"
    )

    args = parser.parse_args()

    # Load configuration
    config_file = args.config or os.path.join(REPO_ROOT, "config", "benchmark_config.json")
    config = load_config(config_file)

    if args.output:
        config["output_directory"] = args.output

    print("Multi-Agent MCP Memory Benchmark")
    print("=" * 70)
    print(f"Configuration: {config_file}")
    print(f"Output directory: {config['output_directory']}")

    # Load server configuration
    server_config_file = os.path.join(REPO_ROOT, "config", "benchmark_config.json")
    with open(server_config_file) as f:
        server_configs = json.load(f)["servers"]

    # Determine which servers to benchmark
    if args.server:
        servers_to_test = {args.server: server_configs.get(args.server)}
    else:
        servers_to_test = {
            name: cfg for name, cfg in server_configs.items()
            if cfg.get("enabled", False)
        }

    if not servers_to_test:
        print("\nNo servers to benchmark.")
        return

    print(f"Servers: {', '.join(servers_to_test.keys())}")
    print(f"Scenarios: {len(config['scenarios'])}")

    # Create output directory
    os.makedirs(config["output_directory"], exist_ok=True)
    os.makedirs(os.path.join(config["output_directory"], "raw"), exist_ok=True)

    # Run benchmarks for each server
    all_results: Dict[str, List[OrchestrationResult]] = {}

    for server_name, server_config in servers_to_test.items():
        if server_config is None:
            continue

        try:
            results = run_benchmark_for_server(server_name, server_config, config)
            all_results[server_name] = results

            # Print summary for this server
            print(f"\n  Results for {server_name}:")
            for result in results:
                ops_count = len(result.operations)
                success_rate = sum(1 for _, _, _, s in result.operations if s) / ops_count * 100 if ops_count else 0
                print(f"    {result.scenario_name}: {result.total_duration_ms:.2f}ms, "
                      f"{ops_count} ops, {success_rate:.1f}% success")

        except Exception as e:
            print(f"\n  ERROR benchmarking {server_name}: {str(e)}")
            import traceback
            traceback.print_exc()
            all_results[server_name] = []

    # Print comparison table
    print_scenario_comparison_table(all_results)

    # Calculate and print speedups (using first server as baseline)
    if len(all_results) > 1:
        baseline_server = list(all_results.keys())[0]
        baseline_results = all_results[baseline_server]

        print(f"\n{'='*70}")
        print(f"SPEEDUP ANALYSIS (vs {baseline_server})")
        print("=" * 70)

        for server_name, results in all_results.items():
            if server_name == baseline_server:
                continue

            speedups = calculate_speedups(baseline_results, results)

            if speedups:
                print(f"\n{server_name}:")
                for scenario, speedup in sorted(speedups.items()):
                    indicator = "faster" if speedup > 1 else "slower" if speedup < 1 else "same"
                    print(f"  {scenario}: {speedup:.2f}x {indicator}")

    # Export results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for server_name, results in all_results.items():
        if not results:
            continue

        export_file = os.path.join(
            config["output_directory"],
            "raw",
            f"multi_agent_{server_name}_{timestamp}.json"
        )

        export_data = {
            "timestamp": timestamp,
            "server": server_name,
            "scenarios": [r.to_dict() for r in results]
        }

        with open(export_file, 'w') as f:
            json.dump(export_data, f, indent=2)

        print(f"\nResults saved: {export_file}")

    # Combined summary
    combined_file = os.path.join(
        config["output_directory"],
        f"combined_summary_{timestamp}.json"
    )

    combined_data = {
        "timestamp": timestamp,
        "servers": list(all_results.keys()),
        "results_by_server": {
            server: [r.to_dict() for r in results]
            for server, results in all_results.items()
        }
    }

    with open(combined_file, 'w') as f:
        json.dump(combined_data, f, indent=2)

    print(f"Combined summary: {combined_file}")
    print("\nBenchmark complete.")


if __name__ == "__main__":
    main()