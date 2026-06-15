#!/usr/bin/env python3
"""
Multi-Agent MCP Memory Benchmark Suite

This module provides comprehensive benchmarks for real-world MCP multi-turn use cases,
simulating multiple agents working together with mock LLM decision making.

Key scenarios:
1. Single agent multi-turn conversations
2. Multi-agent collaborative tasks
3. Agent handoffs and delegation
4. Long-term memory across sessions
5. Concurrent operations and contention
6. Error recovery and retry scenarios
7. Complex search and retrieval patterns
8. Edge cases (large data, special chars, concurrent access)
"""
import json
import time
import random
import string
import threading
import queue
import asyncio
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from datetime import datetime, timedelta
from enum import Enum
from contextlib import contextmanager
import uuid
import hashlib


# ============================================================================
# MOCK LLM DECISION ENGINE
# ============================================================================

class MockLLMDecision:
    """Simulates LLM decision-making patterns for agent behavior."""

    # Common LLM response patterns with realistic delays
    THINKING_DELAYS = {
        "quick": (5, 15),      # Simple decisions
        "standard": (20, 50),  # Normal reasoning
        "complex": (50, 150),  # Complex reasoning
        "analysis": (100, 300),  # Deep analysis
    }

    def __init__(self, base_delay_range: Tuple[float, float] = (10, 30)):
        self.base_delay_range = base_delay_range
        self.decision_count = 0

    def think(self, complexity: str = "standard") -> float:
        """Simulate LLM thinking time."""
        min_d, max_d = self.THINKING_DELAYS.get(complexity, (20, 50))
        delay = random.uniform(min_d, max_d) / 1000  # Convert to seconds
        self.decision_count += 1
        time.sleep(delay)
        return delay * 1000  # Return in ms

    def decide_action(self, options: List[str], context: Dict = None) -> str:
        """Simulate LLM choosing an action from options."""
        self.think("standard")
        # Simulate realistic decision patterns
        return random.choice(options)

    def generate_search_query(self, goal: str, history: List[str] = None) -> str:
        """Simulate LLM generating a search query."""
        self.think("complex")
        # Generate realistic search queries based on goal
        keywords = goal.lower().split()
        return random.choice(keywords) if keywords else goal[:20]

    def extract_entities(self, text: str) -> List[str]:
        """Simulate LLM extracting key entities."""
        self.think("analysis")
        # Simple mock extraction - in reality would be more sophisticated
        words = text.split()
        return [w for w in words if len(w) > 5][:5]


class MockLLMEngine:
    """
    Complete mock LLM engine for simulating agent behavior.
    Includes tool selection, reasoning chains, and response generation.
    """

    def __init__(self, agent_id: str, verbose: bool = False):
        self.agent_id = agent_id
        self.verbose = verbose
        self.session_id = str(uuid.uuid4())
        self.conversation_history: List[Dict] = []
        self.decisions: List[Dict] = []
        self.total_think_time_ms = 0

    def log(self, message: str):
        if self.verbose:
            print(f"  [{self.agent_id}] {message}")

    def think(self, complexity: str = "standard") -> float:
        """Simulate LLM thinking."""
        min_d, max_d = MockLLMDecision.THINKING_DELAYS.get(complexity, (20, 50))
        delay = random.uniform(min_d, max_d) / 1000
        self.total_think_time_ms += delay * 1000
        time.sleep(delay)
        return delay * 1000

    def select_tool(self, available_tools: List[str], goal: str,
                    history: List[Dict] = None) -> str:
        """Simulate LLM tool selection."""
        self.think("complex")

        # Realistic tool selection logic
        goal_lower = goal.lower()

        # Match goals to tools
        if "search" in goal_lower or "find" in goal_lower or "look" in goal_lower:
            matching = [t for t in available_tools if "search" in t.lower() or "find" in t.lower()]
            if matching:
                tool = random.choice(matching)
                self.decisions.append({
                    "type": "tool_selection",
                    "goal": goal,
                    "selected": tool,
                    "reasoning": "Goal requires search capability"
                })
                return tool

        if "write" in goal_lower or "save" in goal_lower or "store" in goal_lower or "remember" in goal_lower:
            matching = [t for t in available_tools if "write" in t.lower() or "save" in t.lower() or "set" in t.lower()]
            if matching:
                tool = random.choice(matching)
                self.decisions.append({
                    "type": "tool_selection",
                    "goal": goal,
                    "selected": tool,
                    "reasoning": "Goal requires write capability"
                })
                return tool

        if "read" in goal_lower or "get" in goal_lower or "retrieve" in goal_lower:
            matching = [t for t in available_tools if "read" in t.lower() or "get" in t.lower() or "open" in t.lower()]
            if matching:
                tool = random.choice(matching)
                self.decisions.append({
                    "type": "tool_selection",
                    "goal": goal,
                    "selected": tool,
                    "reasoning": "Goal requires read capability"
                })
                return tool

        # Default selection
        tool = random.choice(available_tools)
        self.decisions.append({
            "type": "tool_selection",
            "goal": goal,
            "selected": tool,
            "reasoning": "Default selection"
        })
        return tool

    def plan_reasoning_chain(self, goal: str, available_tools: List[str]) -> List[Dict]:
        """Simulate multi-step reasoning for complex tasks."""
        self.think("analysis")

        steps = []
        # Generate 2-5 reasoning steps
        num_steps = random.randint(2, min(5, len(available_tools)))

        for i in range(num_steps):
            step_goal = f"Step {i+1}: {goal}"
            tool = self.select_tool(available_tools, step_goal)
            steps.append({
                "step": i + 1,
                "goal": step_goal,
                "tool": tool,
                "reasoning": f"Reasoning step {i+1} toward goal: {goal}"
            })

        self.decisions.append({
            "type": "reasoning_chain",
            "goal": goal,
            "steps": len(steps)
        })

        return steps

    def generate_memory_content(self, context: str, memory_type: str = "fact") -> Dict:
        """Simulate LLM generating memory content."""
        self.think("complex")

        if memory_type == "fact":
            content = {
                "fact": context,
                "confidence": random.uniform(0.7, 0.99),
                "sources": ["analysis", "retrieval"][:random.randint(1, 2)]
            }
        elif memory_type == "observation":
            content = {
                "observation": context,
                "timestamp": datetime.now().isoformat(),
                "importance": random.choice(["high", "medium", "low"])
            }
        elif memory_type == "procedure":
            content = {
                "procedure": context,
                "steps": random.randint(2, 8),
                "verified": random.random() > 0.3
            }
        else:
            content = {"content": context}

        self.decisions.append({
            "type": "memory_generation",
            "memory_type": memory_type,
            "content_size": len(json.dumps(content))
        })

        return content

    def generate_search_query(self, goal: str, history: List[str] = None) -> str:
        """Simulate LLM generating a search query from a goal."""
        self.think("complex")
        keywords = goal.lower().split()
        query = random.choice(keywords) if keywords else goal[:20]
        self.decisions.append({
            "type": "search_query",
            "goal": goal,
            "query": query,
        })
        return query

    def summarize_conversation(self, messages: List[Dict], max_length: int = 500) -> str:
        """Simulate LLM summarizing conversation history."""
        self.think("complex")

        # Generate a summary
        summary_parts = []
        for msg in messages[-5:]:  # Last 5 messages
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:100]
            summary_parts.append(f"{role}: {content}...")

        summary = " | ".join(summary_parts)
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."

        self.decisions.append({
            "type": "summarization",
            "input_messages": len(messages),
            "output_length": len(summary)
        })

        return summary

    def decide_continue_or_stop(self, context: Dict) -> bool:
        """Decide if agent should continue or stop."""
        self.think("quick")

        # Simple stopping criteria
        steps = context.get("steps", 0)
        iterations = context.get("iterations", 0)

        if steps >= 10 or iterations >= 5:
            decision = False
        elif random.random() > 0.8:  # 20% chance to continue if under limits
            decision = True
        else:
            decision = False

        self.decisions.append({
            "type": "continue_decision",
            "context": context,
            "decision": "continue" if decision else "stop"
        })

        return decision


# ============================================================================
# AGENT SIMULATION
# ============================================================================

class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING = "waiting"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class AgentAction:
    """Represents an action taken by an agent."""
    timestamp: datetime
    tool: str
    arguments: Dict[str, Any]
    result: Any
    duration_ms: float
    success: bool
    error: Optional[str] = None


@dataclass
class AgentSession:
    """Tracks an agent's session state."""
    agent_id: str
    session_id: str
    goal: str
    state: AgentState = AgentState.IDLE
    actions: List[AgentAction] = field(default_factory=list)
    memories_written: int = 0
    memories_read: int = 0
    searches_performed: int = 0
    total_think_time_ms: float = 0
    total_action_time_ms: float = 0
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "goal": self.goal,
            "state": self.state.value,
            "actions_count": len(self.actions),
            "memories_written": self.memories_written,
            "memories_read": self.memories_read,
            "searches_performed": self.searches_performed,
            "total_think_time_ms": self.total_think_time_ms,
            "total_action_time_ms": self.total_action_time_ms,
            "duration_ms": (self.completed_at - self.created_at).total_seconds() * 1000
                if self.completed_at else None
        }


class SimulatedAgent:
    """
    A simulated agent that uses MCP tools through an adapter,
    with mock LLM decision making.
    """

    # The logical memory operations every adapter exposes. These are the only
    # callable "tools" — adapter attributes like read_mode/delete_mode (str
    # properties) or the underlying client/store object are not operations.
    OPERATION_TOOLS = ("write", "read", "search", "delete", "list_all")

    def __init__(self, agent_id: str, adapter, llm_engine: MockLLMEngine = None):
        self.agent_id = agent_id
        self.adapter = adapter
        self.llm = llm_engine or MockLLMEngine(agent_id)
        self.session: Optional[AgentSession] = None
        self.conversation: List[Dict] = []
        self._running = False

    def get_available_tools(self) -> List[str]:
        """Get the logical memory operations the adapter supports.

        Only the canonical operations (write/read/search/delete/list_all) are
        tools. We must not enumerate every public attribute via dir(), or
        non-callable members (read_mode/delete_mode properties, the client or
        vector store backend) get mistaken for tools and blow up on call.
        """
        return [op for op in self.OPERATION_TOOLS
                if callable(getattr(self.adapter, op, None))]

    def execute_tool(self, tool_name: str, arguments: Dict = None) -> Tuple[Any, float, bool, Optional[str]]:
        """Execute a tool with timing."""
        start = time.perf_counter()

        try:
            if hasattr(self.adapter, tool_name):
                method = getattr(self.adapter, tool_name)
                if arguments:
                    result = method(**arguments) if arguments else method()
                else:
                    result = method()
                duration = (time.perf_counter() - start) * 1000
                return result, duration, True, None
            else:
                raise AttributeError(f"Tool {tool_name} not found")
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return None, duration, False, str(e)

    def run_task(self, goal: str, max_steps: int = 10, context: Dict = None) -> AgentSession:
        """Run a task with mock LLM decision making."""
        context = context or {}
        tools = self.get_available_tools()

        self.session = AgentSession(
            agent_id=self.agent_id,
            session_id=self.llm.session_id,
            goal=goal
        )
        self.session.state = AgentState.THINKING
        self._running = True

        self.conversation.append({
            "role": "system",
            "content": f"Agent initialized for task: {goal}"
        })

        # Plan reasoning chain
        plan = self.llm.plan_reasoning_chain(goal, tools)

        for step_idx, step in enumerate(plan[:max_steps]):
            if not self._running:
                break

            # Mock LLM decides what to do
            self.session.state = AgentState.THINKING
            think_time = self.llm.think("standard")
            self.session.total_think_time_ms += think_time

            # Decide action
            tool_name = step["tool"]
            args = self._generate_tool_args(tool_name, context)

            # Execute action
            self.session.state = AgentState.ACTING
            result, action_time, success, error = self.execute_tool(tool_name, args)
            self.session.total_action_time_ms += action_time

            action = AgentAction(
                timestamp=datetime.now(),
                tool=tool_name,
                arguments=args,
                result=result,
                duration_ms=action_time,
                success=success,
                error=error
            )
            self.session.actions.append(action)

            # Track memory operations
            if tool_name == "write" or tool_name == "memSet" or tool_name == "create_entities":
                self.session.memories_written += 1
            elif tool_name == "read" or tool_name == "memGet" or tool_name == "open_nodes":
                self.session.memories_read += 1
            elif tool_name == "search" or tool_name == "memSearch" or tool_name == "search_nodes":
                self.session.searches_performed += 1

            # Log conversation
            self.conversation.append({
                "role": "assistant",
                "content": f"Step {step_idx + 1}: Used {tool_name}"
            })
            self.conversation.append({
                "role": "tool",
                "content": json.dumps(result) if result else str(error)
            })

            # Decide if continue
            if not self.llm.decide_continue_or_stop({
                "steps": step_idx + 1,
                "max_steps": max_steps
            }):
                break

        self.session.state = AgentState.COMPLETE
        self.session.completed_at = datetime.now()
        self._running = False

        return self.session

    def _generate_tool_args(self, tool_name: str, context: Dict) -> Dict:
        """Generate appropriate arguments for a tool."""
        args = {}

        if tool_name == "write" or tool_name == "memSet":
            key = context.get("current_key", f"{self.agent_id}.{uuid.uuid4().hex[:8]}")
            value = context.get("current_value", self.llm.generate_memory_content("memory content"))
            args = {"key": key, "value": value}

        elif tool_name == "read" or tool_name == "memGet":
            key = context.get("search_key", f"{self.agent_id}.default")
            args = {"key": key}

        elif tool_name == "search" or tool_name == "memSearch":
            query = context.get("query", self.llm.generate_search_query("information"))
            args = {"query": query}

        elif tool_name == "delete" or tool_name == "memDelete":
            key = context.get("delete_key", f"{self.agent_id}.to_delete")
            args = {"key": key}

        elif tool_name == "list_all" or tool_name == "list":
            pass  # No args needed

        return args


# ============================================================================
# MULTI-AGENT ORCHESTRATION
# ============================================================================

class AgentRole(Enum):
    COORDINATOR = "coordinator"
    RESEARCHER = "researcher"
    EXECUTOR = "executor"
    REVIEWER = "reviewer"
    ARCHIVER = "archiver"


@dataclass
class OrchestrationResult:
    """Results from orchestrating multiple agents."""
    scenario_name: str
    total_duration_ms: float
    agents: List[AgentSession]
    operations: List[Tuple[str, str, float, bool]]  # (agent_id, operation, duration_ms, success)
    memory_contention_events: int
    coordination_overhead_ms: float
    errors: List[str]

    def to_dict(self) -> Dict:
        return {
            "scenario_name": self.scenario_name,
            "total_duration_ms": self.total_duration_ms,
            "agent_count": len(self.agents),
            "total_operations": len(self.operations),
            "memory_contention_events": self.memory_contention_events,
            "coordination_overhead_ms": self.coordination_overhead_ms,
            "success_rate": sum(1 for _, _, _, s in self.operations if s) / len(self.operations) if self.operations else 0,
            "errors": self.errors,
            "agents": [a.to_dict() for a in self.agents]
        }


class MultiAgentOrchestrator:
    """
    Orchestrates multiple simulated agents working together on tasks.
    Supports various coordination patterns: sequential, parallel, hierarchical.
    """

    def __init__(self, adapter_factory: Callable[[str], Any]):
        """
        Initialize orchestrator.

        Args:
            adapter_factory: A callable that creates a new adapter instance.
                             Should accept agent_id and return an adapter.
        """
        self.adapter_factory = adapter_factory
        self.agents: Dict[str, SimulatedAgent] = {}
        self.active_sessions: List[AgentSession] = []
        self.results: List[OrchestrationResult] = []

    def create_agent(self, agent_id: str, role: AgentRole = None) -> SimulatedAgent:
        """Create a new simulated agent with its own adapter."""
        adapter = self.adapter_factory(agent_id)
        llm = MockLLMEngine(agent_id, verbose=False)
        agent = SimulatedAgent(agent_id, adapter, llm)
        self.agents[agent_id] = agent
        return agent

    def run_sequential_scenario(self, scenario_name: str,
                                agent_goals: List[Tuple[str, str]]) -> OrchestrationResult:
        """
        Run agents sequentially, each waiting for the previous to complete.

        Args:
            scenario_name: Name of the benchmark scenario
            agent_goals: List of (agent_id, goal) tuples
        """
        start_time = time.perf_counter()
        sessions = []
        operations = []
        errors = []
        memory_contention = 0

        for agent_id, goal in agent_goals:
            agent = self.agents.get(agent_id) or self.create_agent(agent_id)

            try:
                session = agent.run_task(goal)
                sessions.append(session)

                for action in session.actions:
                    operations.append((
                        agent_id,
                        action.tool,
                        action.duration_ms,
                        action.success
                    ))
                    if not action.success:
                        errors.append(f"{agent_id}/{action.tool}: {action.error}")

            except Exception as e:
                errors.append(f"{agent_id}: {str(e)}")

        total_duration = (time.perf_counter() - start_time) * 1000

        return OrchestrationResult(
            scenario_name=scenario_name,
            total_duration_ms=total_duration,
            agents=sessions,
            operations=operations,
            memory_contention_events=memory_contention,
            coordination_overhead_ms=0,
            errors=errors
        )

    def run_parallel_scenario(self, scenario_name: str,
                              agent_configs: List[Dict]) -> OrchestrationResult:
        """
        Run multiple agents in parallel with shared memory access.

        Args:
            scenario_name: Name of the benchmark scenario
            agent_configs: List of dicts with 'agent_id', 'goal', 'role'
        """
        start_time = time.perf_counter()
        sessions = []
        operations = []
        errors = []
        memory_contention = 0
        coordination_overhead = 0

        # Create all agents
        threads = []
        results_lock = threading.Lock()

        def run_agent(config: Dict):
            nonlocal memory_contention, coordination_overhead
            agent = self.agents.get(config['agent_id']) or self.create_agent(config['agent_id'])

            # Simulate coordination overhead
            coord_start = time.perf_counter()
            time.sleep(random.uniform(0.001, 0.01))  # Agent startup overhead
            coord_time = (time.perf_counter() - coord_start) * 1000
            with results_lock:
                coordination_overhead += coord_time

            try:
                context = config.get('context', {})
                session = agent.run_task(config['goal'], context=context)
                with results_lock:
                    sessions.append(session)
                    for action in session.actions:
                        operations.append((
                            config['agent_id'],
                            action.tool,
                            action.duration_ms,
                            action.success
                        ))
                        if not action.success:
                            errors.append(f"{config['agent_id']}/{action.tool}: {action.error}")

                        # Simulate memory contention detection
                        if random.random() < 0.1:  # 10% chance of contention
                            memory_contention += 1

            except Exception as e:
                with results_lock:
                    errors.append(f"{config['agent_id']}: {str(e)}")

        # Start all threads
        for config in agent_configs:
            t = threading.Thread(target=run_agent, args=(config,))
            threads.append(t)
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        total_duration = (time.perf_counter() - start_time) * 1000

        return OrchestrationResult(
            scenario_name=scenario_name,
            total_duration_ms=total_duration,
            agents=sessions,
            operations=operations,
            memory_contention_events=memory_contention,
            coordination_overhead_ms=coordination_overhead,
            errors=errors
        )

    def run_hierarchical_scenario(self, scenario_name: str,
                                  coordinator_id: str,
                                  sub_agent_configs: List[Dict]) -> OrchestrationResult:
        """
        Run a hierarchical scenario with a coordinator delegating to sub-agents.

        Args:
            scenario_name: Name of the benchmark scenario
            coordinator_id: ID of the coordinator agent
            sub_agent_configs: List of sub-agent configurations
        """
        start_time = time.perf_counter()
        sessions = []
        operations = []
        errors = []
        coordination_overhead = 0

        # Coordinator plans and delegates
        coordinator = self.agents.get(coordinator_id) or self.create_agent(coordinator_id)

        # Coordinator's planning phase
        coord_llm = coordinator.llm
        plan_time = coord_llm.think("analysis")
        coordination_overhead += plan_time

        # Create sub-agents and assign tasks
        sub_agents = []
        for config in sub_agent_configs:
            agent = self.create_agent(config['agent_id'])
            sub_agents.append((agent, config))

        # Simulate delegation overhead
        delegation_time = random.uniform(5, 15)
        coordination_overhead += delegation_time
        time.sleep(delegation_time / 1000)

        # Run sub-agents in parallel
        threads = []
        results_lock = threading.Lock()

        def run_sub_agent(agent: SimulatedAgent, config: Dict):
            session = agent.run_task(config['goal'], context=config.get('context', {}))
            with results_lock:
                sessions.append(session)
                for action in session.actions:
                    operations.append((
                        config['agent_id'],
                        action.tool,
                        action.duration_ms,
                        action.success
                    ))
                    if not action.success:
                        errors.append(f"{config['agent_id']}/{action.tool}: {action.error}")

        for agent, config in sub_agents:
            t = threading.Thread(target=run_sub_agent, args=(agent, config))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Coordinator synthesizes results
        synthesis_time = coord_llm.think("complex")
        coordination_overhead += synthesis_time

        total_duration = (time.perf_counter() - start_time) * 1000

        return OrchestrationResult(
            scenario_name=scenario_name,
            total_duration_ms=total_duration,
            agents=sessions,
            operations=operations,
            memory_contention_events=0,
            coordination_overhead_ms=coordination_overhead,
            errors=errors
        )


# ============================================================================
# BENCHMARK SCENARIOS
# ============================================================================

class MCPMultiAgentBenchmark:
    """
    Comprehensive benchmark suite for MCP memory servers in multi-agent scenarios.
    """

    def __init__(self, adapter_factory: Callable[[str], Any]):
        self.orchestrator = MultiAgentOrchestrator(adapter_factory)
        self.results: List[OrchestrationResult] = []

    # -------------------------------------------------------------------------
    # Scenario 1: Single Agent Long Conversation
    # -------------------------------------------------------------------------

    def scenario_single_agent_long_conversation(self, agent_id: str = "agent_1",
                                                num_turns: int = 20,
                                                adapter=None) -> OrchestrationResult:
        """
        Simulates a single agent maintaining context across many conversation turns.
        Real-world use case: A coding assistant helping with a large refactoring task.
        """
        print(f"\n  [Scenario 1] Single Agent Long Conversation ({num_turns} turns)")

        if adapter is None:
            raise ValueError("Adapter required")

        agent = self.orchestrator.create_agent(agent_id)
        agent.adapter = adapter

        start_time = time.perf_counter()
        sessions = []
        operations = []
        errors = []
        total_think_time = 0

        for turn in range(num_turns):
            # Each turn: think, write context, read previous context, search, potentially update
            goal = f"Conversation turn {turn + 1}: Process user input and maintain context"

            llm = agent.llm
            think_time = llm.think("standard")
            total_think_time += think_time

            # Write current turn context
            key = f"conversation/{agent_id}/turn_{turn}"
            value = {
                "turn": turn,
                "timestamp": datetime.now().isoformat(),
                "context_summary": f"Processing turn {turn + 1} of {num_turns}",
                "previous_turn_key": f"conversation/{agent_id}/turn_{turn - 1}" if turn > 0 else None
            }

            write_start = time.perf_counter()
            try:
                agent.adapter.write(key, value)
                write_time = (time.perf_counter() - write_start) * 1000
                operations.append((agent_id, "write", write_time, True))
            except Exception as e:
                operations.append((agent_id, "write", 0, False))
                errors.append(str(e))

            # Read previous context (simulated - only for turns > 0)
            if turn > 0:
                read_key = f"conversation/{agent_id}/turn_{turn - 1}"
                read_start = time.perf_counter()
                try:
                    agent.adapter.read(read_key)
                    read_time = (time.perf_counter() - read_start) * 1000
                    operations.append((agent_id, "read", read_time, True))
                except Exception as e:
                    operations.append((agent_id, "read", 0, False))
                    errors.append(str(e))

            # Periodic search to find relevant context
            if turn % 5 == 0:
                query = f"conversation turn {turn}"
                search_start = time.perf_counter()
                try:
                    agent.adapter.search(query)
                    search_time = (time.perf_counter() - search_start) * 1000
                    operations.append((agent_id, "search", search_time, True))
                except Exception as e:
                    operations.append((agent_id, "search", 0, False))
                    errors.append(str(e))

            if (turn + 1) % 5 == 0:
                print(f"    Turn {turn + 1}/{num_turns} completed")

        session = AgentSession(
            agent_id=agent_id,
            session_id=agent.llm.session_id,
            goal=f"Long conversation with {num_turns} turns",
            state=AgentState.COMPLETE,
            memories_written=num_turns,
            memories_read=num_turns - 1,
            searches_performed=num_turns // 5,
            total_think_time_ms=total_think_time
        )
        session.completed_at = datetime.now()
        sessions.append(session)

        total_duration = (time.perf_counter() - start_time) * 1000

        result = OrchestrationResult(
            scenario_name="single_agent_long_conversation",
            total_duration_ms=total_duration,
            agents=sessions,
            operations=operations,
            memory_contention_events=0,
            coordination_overhead_ms=total_think_time,
            errors=errors
        )
        self.results.append(result)
        return result

    # -------------------------------------------------------------------------
    # Scenario 2: Multi-Agent Collaborative Task
    # -------------------------------------------------------------------------

    def scenario_multi_agent_collaborative(self, agent_ids: List[str] = None,
                                           num_agents: int = 3,
                                           tasks_per_agent: int = 5,
                                           adapter=None) -> OrchestrationResult:
        """
        Multiple agents collaborate on a shared task with memory access.
        Real-world use case: A team of agents working on a code review.
        """
        if agent_ids is None:
            agent_ids = [f"agent_{i}" for i in range(num_agents)]
        if adapter is None:
            raise ValueError("Adapter required")

        print(f"\n  [Scenario 2] Multi-Agent Collaborative ({num_agents} agents, {tasks_per_agent} tasks each)")

        # Each agent does some work and writes findings
        agent_configs = []
        for agent_id in agent_ids:
            for task in range(tasks_per_agent):
                agent_configs.append({
                    "agent_id": f"{agent_id}_task_{task}",
                    "goal": f"Agent {agent_id} performs subtask {task + 1}",
                    "context": {
                        "current_key": f"shared/{agent_id}/task_{task}",
                        "query": f"task {task}"
                    }
                })

        # Patch the orchestrator to use the same adapter
        original_factory = self.orchestrator.adapter_factory
        self.orchestrator.adapter_factory = lambda aid: adapter

        result = self.orchestrator.run_parallel_scenario(
            "multi_agent_collaborative",
            agent_configs
        )

        # Restore original factory
        self.orchestrator.adapter_factory = original_factory

        self.results.append(result)
        return result

    # -------------------------------------------------------------------------
    # Scenario 3: Agent Handoff
    # -------------------------------------------------------------------------

    def scenario_agent_handoff(self, num_handlers: int = 4,
                               items_per_handler: int = 3,
                               adapter=None) -> OrchestrationResult:
        """
        Simulates agents handing off tasks to each other.
        Real-world use case: Ticket escalation system.
        """
        if adapter is None:
            raise ValueError("Adapter required")

        print(f"\n  [Scenario 3] Agent Handoff ({num_handlers} handlers, {items_per_handler} items each)")

        start_time = time.perf_counter()
        sessions = []
        operations = []
        errors = []
        memory_contention = 0

        # Simulate handoff chain: handler_1 -> handler_2 -> ... -> handler_n
        for item in range(items_per_handler):
            current_handler = 1

            while current_handler <= num_handlers:
                agent_id = f"handler_{current_handler}"

                # Create agent for this step
                agent = self.orchestrator.create_agent(agent_id)
                agent.adapter = adapter

                # Agent processes and potentially hands off
                goal = f"Handle item {item} (level {current_handler})"

                llm = agent.llm
                think_time = llm.think("standard")

                # Write processing result
                key = f"handoff/item_{item}/level_{current_handler}"
                value = {
                    "item": item,
                    "handler": agent_id,
                    "level": current_handler,
                    "processed_at": datetime.now().isoformat()
                }

                write_start = time.perf_counter()
                try:
                    adapter.write(key, value)
                    write_time = (time.perf_counter() - write_start) * 1000
                    operations.append((agent_id, "write", write_time, True))
                except Exception as e:
                    operations.append((agent_id, "write", 0, False))
                    errors.append(str(e))

                # Read previous level's work
                if current_handler > 1:
                    prev_key = f"handoff/item_{item}/level_{current_handler - 1}"
                    read_start = time.perf_counter()
                    try:
                        adapter.read(prev_key)
                        read_time = (time.perf_counter() - read_start) * 1000
                        operations.append((agent_id, "read", read_time, True))
                    except Exception as e:
                        operations.append((agent_id, "read", 0, False))
                        errors.append(str(e))

                session = AgentSession(
                    agent_id=agent_id,
                    session_id=llm.session_id,
                    goal=goal,
                    state=AgentState.COMPLETE,
                    memories_written=1,
                    memories_read=1 if current_handler > 1 else 0
                )
                session.completed_at = datetime.now()
                sessions.append(session)

                # Decide if hand off to next level (simulate 30% escalation rate)
                if current_handler < num_handlers and random.random() < 0.3:
                    current_handler += 1
                else:
                    break

        total_duration = (time.perf_counter() - start_time) * 1000

        result = OrchestrationResult(
            scenario_name="agent_handoff",
            total_duration_ms=total_duration,
            agents=sessions,
            operations=operations,
            memory_contention_events=memory_contention,
            coordination_overhead_ms=0,
            errors=errors
        )
        self.results.append(result)
        return result

    # -------------------------------------------------------------------------
    # Scenario 4: Long-term Memory Session Recovery
    # -------------------------------------------------------------------------

    def scenario_session_recovery(self, sessions: int = 5,
                                  items_per_session: int = 10,
                                  adapter=None) -> OrchestrationResult:
        """
        Simulates agents resuming work from previous sessions.
        Real-world use case: Developer returning to a codebase after a break.
        """
        if adapter is None:
            raise ValueError("Adapter required")

        print(f"\n  [Scenario 4] Session Recovery ({sessions} sessions, {items_per_session} items each)")

        start_time = time.perf_counter()
        all_sessions = []
        all_operations = []
        all_errors = []

        for session_num in range(sessions):
            agent_id = f"developer_session_{session_num}"

            # Simulate session start - search for previous context
            search_start = time.perf_counter()
            try:
                adapter.search(f"session {session_num - 1}" if session_num > 0 else "initial")
                search_time = (time.perf_counter() - search_start) * 1000
                all_operations.append((agent_id, "search", search_time, True))
            except Exception as e:
                all_operations.append((agent_id, "search", 0, False))
                all_errors.append(str(e))

            # Continue working
            writes = 0
            reads = 0
            for item in range(items_per_session):
                key = f"session/{session_num}/work_{item}"

                # Write current work
                write_start = time.perf_counter()
                try:
                    adapter.write(key, {
                        "session": session_num,
                        "item": item,
                        "timestamp": datetime.now().isoformat()
                    })
                    write_time = (time.perf_counter() - write_start) * 1000
                    all_operations.append((agent_id, "write", write_time, True))
                    writes += 1
                except Exception as e:
                    all_operations.append((agent_id, "write", 0, False))
                    all_errors.append(str(e))

                # Read previous session's corresponding item (if exists)
                if session_num > 0 and item < items_per_session:
                    prev_key = f"session/{session_num - 1}/work_{item}"
                    read_start = time.perf_counter()
                    try:
                        adapter.read(prev_key)
                        read_time = (time.perf_counter() - read_start) * 1000
                        all_operations.append((agent_id, "read", read_time, True))
                        reads += 1
                    except Exception as e:
                        all_operations.append((agent_id, "read", 0, False))
                        all_errors.append(str(e))

            session = AgentSession(
                agent_id=agent_id,
                session_id=str(uuid.uuid4()),
                goal=f"Session {session_num} with {items_per_session} items",
                state=AgentState.COMPLETE,
                memories_written=writes,
                memories_read=reads,
                searches_performed=1
            )
            session.completed_at = datetime.now()
            all_sessions.append(session)

        total_duration = (time.perf_counter() - start_time) * 1000

        result = OrchestrationResult(
            scenario_name="session_recovery",
            total_duration_ms=total_duration,
            agents=all_sessions,
            operations=all_operations,
            memory_contention_events=0,
            coordination_overhead_ms=0,
            errors=all_errors
        )
        self.results.append(result)
        return result

    # -------------------------------------------------------------------------
    # Scenario 5: Concurrent Memory Access Contention
    # -------------------------------------------------------------------------

    def scenario_concurrent_contention(self, num_agents: int = 10,
                                       operations_per_agent: int = 5,
                                       adapter=None) -> OrchestrationResult:
        """
        Multiple agents contend for the same memory keys.
        Real-world use case: Multiple agents accessing a shared configuration.
        """
        if adapter is None:
            raise ValueError("Adapter required")

        print(f"\n  [Scenario 5] Concurrent Contention ({num_agents} agents, {operations_per_agent} ops each)")

        # Pre-populate some shared keys
        shared_keys = [f"shared/config_{i}" for i in range(5)]
        for key in shared_keys:
            try:
                adapter.write(key, {"config": key, "value": "initial"})
            except:
                pass

        start_time = time.perf_counter()
        sessions = []
        operations = []
        errors = []
        contention_count = 0

        lock = threading.Lock()

        def agent_worker(agent_id: str):
            nonlocal contention_count
            session_ops = []
            session_errors = []

            agent = self.orchestrator.create_agent(agent_id)
            agent.adapter = adapter

            for op in range(operations_per_agent):
                # All agents try to access shared keys
                key = random.choice(shared_keys)

                # Decide operation (read or write)
                if random.random() < 0.7:  # 70% reads, 30% writes
                    # Read with contention
                    read_start = time.perf_counter()
                    try:
                        adapter.read(key)
                        read_time = (time.perf_counter() - read_start) * 1000
                        session_ops.append((agent_id, "read", read_time, True))

                        # Simulate detected contention
                        if random.random() < 0.15:
                            with lock:
                                contention_count += 1
                    except Exception as e:
                        session_ops.append((agent_id, "read", 0, False))
                        session_errors.append(str(e))
                else:
                    # Write with potential conflict
                    write_start = time.perf_counter()
                    try:
                        adapter.write(key, {
                            "updated_by": agent_id,
                            "timestamp": datetime.now().isoformat()
                        })
                        write_time = (time.perf_counter() - write_start) * 1000
                        session_ops.append((agent_id, "write", write_time, True))

                        if random.random() < 0.2:
                            with lock:
                                contention_count += 1
                    except Exception as e:
                        session_ops.append((agent_id, "write", 0, False))
                        session_errors.append(str(e))

                # Small delay to simulate processing
                time.sleep(random.uniform(0.001, 0.005))

            session = AgentSession(
                agent_id=agent_id,
                session_id=agent.llm.session_id,
                goal=f"Contention test with {operations_per_agent} operations",
                state=AgentState.COMPLETE,
                memories_written=operations_per_agent // 3,
                memories_read=operations_per_agent - operations_per_agent // 3
            )
            session.completed_at = datetime.now()

            with lock:
                sessions.append(session)
                operations.extend(session_ops)
                errors.extend(session_errors)

        # Run all agents in parallel
        threads = []
        for i in range(num_agents):
            t = threading.Thread(target=agent_worker, args=(f"contention_agent_{i}",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        total_duration = (time.perf_counter() - start_time) * 1000

        result = OrchestrationResult(
            scenario_name="concurrent_contention",
            total_duration_ms=total_duration,
            agents=sessions,
            operations=operations,
            memory_contention_events=contention_count,
            coordination_overhead_ms=0,
            errors=errors
        )
        self.results.append(result)
        return result

    # -------------------------------------------------------------------------
    # Scenario 6: Error Recovery and Retry
    # -------------------------------------------------------------------------

    def scenario_error_recovery(self, num_agents: int = 5,
                                error_rate: float = 0.2,
                                adapter=None) -> OrchestrationResult:
        """
        Simulates agents recovering from errors with retry logic.
        Real-world use case: Network blips, temporary server issues.
        """
        if adapter is None:
            raise ValueError("Adapter required")

        print(f"\n  [Scenario 6] Error Recovery ({num_agents} agents, {error_rate*100}% error rate)")

        start_time = time.perf_counter()
        sessions = []
        operations = []
        errors = []
        recovery_count = 0

        for agent_num in range(num_agents):
            agent_id = f"recovery_agent_{agent_num}"

            # Simulate a task that may encounter errors
            for attempt in range(3):
                key = f"recovery/{agent_id}/attempt_{attempt}"

                write_start = time.perf_counter()

                # Simulate error based on error_rate
                if random.random() < error_rate:
                    # Simulate failure (in real scenario this would be actual exception)
                    time.sleep(random.uniform(0.01, 0.02))
                    write_time = (time.perf_counter() - write_start) * 1000
                    operations.append((agent_id, "write", write_time, False))
                    errors.append(f"{agent_id}: Simulated error on attempt {attempt + 1}")
                    recovery_count += 1

                    # Retry after backoff
                    backoff = random.uniform(0.01, 0.05)
                    time.sleep(backoff)
                    continue

                # Success
                try:
                    adapter.write(key, {
                        "agent_id": agent_id,
                        "attempt": attempt,
                        "timestamp": datetime.now().isoformat()
                    })
                    write_time = (time.perf_counter() - write_start) * 1000
                    operations.append((agent_id, "write", write_time, True))
                except Exception as e:
                    write_time = (time.perf_counter() - write_start) * 1000
                    operations.append((agent_id, "write", write_time, False))
                    errors.append(str(e))

            session = AgentSession(
                agent_id=agent_id,
                session_id=str(uuid.uuid4()),
                goal=f"Error recovery test with {error_rate*100}% error rate",
                state=AgentState.COMPLETE
            )
            session.completed_at = datetime.now()
            sessions.append(session)

        total_duration = (time.perf_counter() - start_time) * 1000

        result = OrchestrationResult(
            scenario_name="error_recovery",
            total_duration_ms=total_duration,
            agents=sessions,
            operations=operations,
            memory_contention_events=0,
            coordination_overhead_ms=0,
            errors=errors
        )
        self.results.append(result)

        print(f"    Recovery attempts: {recovery_count}")
        return result

    # -------------------------------------------------------------------------
    # Scenario 7: Complex Search and Retrieval
    # -------------------------------------------------------------------------

    def scenario_complex_search(self, num_agents: int = 3,
                               searches_per_agent: int = 10,
                               adapter=None) -> OrchestrationResult:
        """
        Agents perform complex search queries with various patterns.
        Real-world use case: Debugging a production issue with complex log search.
        """
        if adapter is None:
            raise ValueError("Adapter required")

        print(f"\n  [Scenario 7] Complex Search ({num_agents} agents, {searches_per_agent} searches each)")

        # Pre-populate memory with diverse content
        content_patterns = [
            "error", "warning", "info", "debug",
            "user", "admin", "system", "api",
            "database", "cache", "queue", "worker",
            "request", "response", "timeout", "retry"
        ]

        for pattern in content_patterns:
            for i in range(5):
                key = f"logs/{pattern}_{i}"
                try:
                    adapter.write(key, {
                        "pattern": pattern,
                        "index": i,
                        "content": f"Sample log content for {pattern} at index {i}",
                        "timestamp": datetime.now().isoformat()
                    })
                except:
                    pass

        start_time = time.perf_counter()
        sessions = []
        operations = []
        errors = []
        search_results_count = 0

        for agent_num in range(num_agents):
            agent_id = f"search_agent_{agent_num}"

            for search_num in range(searches_per_agent):
                # Generate complex search queries
                query_type = random.choice(["single", "combined", "prefix", "fuzzy"])
                pattern = random.choice(content_patterns)

                if query_type == "single":
                    query = pattern
                elif query_type == "combined":
                    query = f"{pattern} {random.choice(content_patterns)}"
                elif query_type == "prefix":
                    query = pattern[:3]
                else:
                    query = pattern[:-1] if len(pattern) > 3 else pattern

                search_start = time.perf_counter()
                try:
                    result = adapter.search(query)
                    search_time = (time.perf_counter() - search_start) * 1000
                    operations.append((agent_id, "search", search_time, True))

                    # Count results
                    if result:
                        search_results_count += 1
                except Exception as e:
                    search_time = (time.perf_counter() - search_start) * 1000
                    operations.append((agent_id, "search", search_time, False))
                    errors.append(f"{agent_id}: Search failed: {str(e)}")

            session = AgentSession(
                agent_id=agent_id,
                session_id=str(uuid.uuid4()),
                goal=f"Complex search with {searches_per_agent} queries",
                state=AgentState.COMPLETE,
                searches_performed=searches_per_agent
            )
            session.completed_at = datetime.now()
            sessions.append(session)

        total_duration = (time.perf_counter() - start_time) * 1000

        result = OrchestrationResult(
            scenario_name="complex_search",
            total_duration_ms=total_duration,
            agents=sessions,
            operations=operations,
            memory_contention_events=0,
            coordination_overhead_ms=0,
            errors=errors
        )
        self.results.append(result)

        print(f"    Total search results: {search_results_count}")
        return result

    # -------------------------------------------------------------------------
    # Scenario 8: Batch vs Streaming Operations
    # -------------------------------------------------------------------------

    def scenario_batch_vs_streaming(self, batch_size: int = 50,
                                    streaming_chunk: int = 5,
                                    adapter=None) -> OrchestrationResult:
        """
        Compare batched writes vs streaming individual writes.
        Real-world use case: Bulk import vs real-time logging.
        """
        if adapter is None:
            raise ValueError("Adapter required")

        print(f"\n  [Scenario 8] Batch vs Streaming (batch={batch_size}, streaming={batch_size} in chunks of {streaming_chunk})")

        operations = []
        errors = []
        sessions = []

        # Batch approach
        batch_start = time.perf_counter()
        for i in range(batch_size):
            key = f"batch/item_{i}"
            try:
                adapter.write(key, {"index": i, "mode": "batch"})
            except Exception as e:
                errors.append(f"batch_write_{i}: {str(e)}")
        batch_time = (time.perf_counter() - batch_start) * 1000
        operations.append(("batch_mode", "write", batch_time, True))

        # Streaming approach (chunked)
        streaming_start = time.perf_counter()
        chunks = [batch_size // streaming_chunk] * streaming_chunk
        for chunk_idx in range(streaming_chunk):
            for i in range(chunks[chunk_idx]):
                key = f"stream/item_{chunk_idx}_{i}"
                try:
                    adapter.write(key, {"chunk": chunk_idx, "index": i, "mode": "stream"})
                except Exception as e:
                    errors.append(f"stream_write_{chunk_idx}_{i}: {str(e)}")
        streaming_time = (time.perf_counter() - streaming_start) * 1000
        operations.append(("streaming_mode", "write", streaming_time, True))

        session = AgentSession(
            agent_id="comparison_agent",
            session_id=str(uuid.uuid4()),
            goal=f"Batch ({batch_size}) vs Streaming ({streaming_chunk} chunks)",
            state=AgentState.COMPLETE,
            memories_written=batch_size * 2
        )
        session.completed_at = datetime.now()
        sessions.append(session)

        total_duration = (time.perf_counter() - streaming_start) * 1000

        result = OrchestrationResult(
            scenario_name="batch_vs_streaming",
            total_duration_ms=total_duration,
            agents=sessions,
            operations=operations,
            memory_contention_events=0,
            coordination_overhead_ms=0,
            errors=errors
        )
        self.results.append(result)

        print(f"    Batch time: {batch_time:.2f}ms")
        print(f"    Streaming time: {streaming_time:.2f}ms")
        print(f"    Ratio: {streaming_time/batch_time:.2f}x")
        return result

    # -------------------------------------------------------------------------
    # Scenario 9: Edge Case - Large Payloads
    # -------------------------------------------------------------------------

    def scenario_large_payloads(self, sizes: List[int] = None,
                               adapter=None) -> OrchestrationResult:
        """
        Test memory server behavior with large data payloads.
        Real-world use case: Storing code files, stack traces, or serialized objects.
        """
        if sizes is None:
            sizes = [1_000, 10_000, 100_000, 500_000]  # bytes
        if adapter is None:
            raise ValueError("Adapter required")

        print(f"\n  [Scenario 9] Large Payloads (sizes: {sizes})")

        operations = []
        errors = []
        sessions = []

        for size in sizes:
            key = f"large_payload/{size}_bytes"

            # Generate large content
            large_content = {
                "data": "x" * size,
                "size": size,
                "checksum": hashlib.md5(b"x" * size).hexdigest()
            }

            write_start = time.perf_counter()
            try:
                adapter.write(key, large_content)
                write_time = (time.perf_counter() - write_start) * 1000
                operations.append(("large_payload", f"write_{size}", write_time, True))
                print(f"    {size:,} bytes: {write_time:.2f}ms")
            except Exception as e:
                write_time = (time.perf_counter() - write_start) * 1000
                operations.append(("large_payload", f"write_{size}", write_time, False))
                errors.append(f"write_{size}: {str(e)}")
                print(f"    {size:,} bytes: FAILED - {str(e)}")

            # Read back
            read_start = time.perf_counter()
            try:
                result = adapter.read(key)
                read_time = (time.perf_counter() - read_start) * 1000
                operations.append(("large_payload", f"read_{size}", read_time, True))
            except Exception as e:
                read_time = (time.perf_counter() - read_start) * 1000
                operations.append(("large_payload", f"read_{size}", read_time, False))
                errors.append(f"read_{size}: {str(e)}")

        session = AgentSession(
            agent_id="large_payload_tester",
            session_id=str(uuid.uuid4()),
            goal=f"Test payloads up to {max(sizes)} bytes",
            state=AgentState.COMPLETE,
            memories_written=len(sizes),
            memories_read=len(sizes)
        )
        session.completed_at = datetime.now()
        sessions.append(session)

        total_duration = sum(op[2] for op in operations if op[3])

        result = OrchestrationResult(
            scenario_name="large_payloads",
            total_duration_ms=total_duration,
            agents=sessions,
            operations=operations,
            memory_contention_events=0,
            coordination_overhead_ms=0,
            errors=errors
        )
        self.results.append(result)
        return result

    # -------------------------------------------------------------------------
    # Scenario 10: Edge Case - Special Characters and Unicode
    # -------------------------------------------------------------------------

    def scenario_special_characters(self, adapter=None) -> OrchestrationResult:
        """
        Test memory server with special characters, unicode, and edge case keys.
        Real-world use case: Internationalization, technical content with symbols.
        """
        if adapter is None:
            raise ValueError("Adapter required")

        print(f"\n  [Scenario 10] Special Characters and Unicode")

        test_cases = [
            ("emoji_key_", "Testing with 😀 🎉"),
            ("unicode_中文_日本語", "多言語コンテンツ"),
            ("spaces in key", "value with spaces"),
            ("key/with/slashes", "path-like content"),
            ("key.with.dots", "dotted.content"),
            ("key<>\"':;", "special characters"),
            ("key\t\n\r", "whitespace content"),
            ("key" + chr(0), "null character"),
            ("key" + " " * 100, "long whitespace key"),
            ("CamelCase", "mixedCaseValue"),
            ("ALLCAPS", "shouty_value"),
            ("mixed_Case_With_Numbers123", "value456"),
        ]

        operations = []
        errors = []
        sessions = []

        for key, value in test_cases:
            write_start = time.perf_counter()
            try:
                adapter.write(key, {"content": value, "original_key": key})
                write_time = (time.perf_counter() - write_start) * 1000
                operations.append(("special_chars", "write", write_time, True))
                print(f"    Key: {key[:30]:30s} | Value: {value[:20]:20s} | {write_time:.2f}ms")
            except Exception as e:
                write_time = (time.perf_counter() - write_start) * 1000
                operations.append(("special_chars", "write", write_time, False))
                errors.append(f"{key}: {str(e)}")
                print(f"    Key: {key[:30]:30s} | FAILED - {str(e)}")

        session = AgentSession(
            agent_id="special_chars_tester",
            session_id=str(uuid.uuid4()),
            goal="Test special characters and unicode",
            state=AgentState.COMPLETE,
            memories_written=len(test_cases)
        )
        session.completed_at = datetime.now()
        sessions.append(session)

        result = OrchestrationResult(
            scenario_name="special_characters",
            total_duration_ms=sum(op[2] for op in operations if op[3]),
            agents=sessions,
            operations=operations,
            memory_contention_events=0,
            coordination_overhead_ms=0,
            errors=errors
        )
        self.results.append(result)
        return result

    # -------------------------------------------------------------------------
    # Scenario 11: Hierarchical Agent Structure
    # -------------------------------------------------------------------------

    def scenario_hierarchical_structure(self, coordinator_id: str = "coordinator",
                                       num_workers: int = 4,
                                       tasks_per_worker: int = 3,
                                       adapter=None) -> OrchestrationResult:
        """
        Simulates a hierarchical agent structure with coordinator and workers.
        Real-world use case: Project manager delegating to specialized workers.
        """
        if adapter is None:
            raise ValueError("Adapter required")

        print(f"\n  [Scenario 11] Hierarchical Structure (1 coordinator, {num_workers} workers)")

        sub_configs = []
        for worker_num in range(num_workers):
            for task in range(tasks_per_worker):
                sub_configs.append({
                    "agent_id": f"worker_{worker_num}_task_{task}",
                    "goal": f"Worker {worker_num} performs task {task}",
                    "context": {
                        "worker_id": worker_num,
                        "task_id": task
                    }
                })

        # Create coordinator with adapter
        coordinator = self.orchestrator.create_agent(coordinator_id)
        coordinator.adapter = adapter

        result = self.orchestrator.run_hierarchical_scenario(
            "hierarchical_structure",
            coordinator_id,
            sub_configs
        )

        self.results.append(result)
        return result

    # -------------------------------------------------------------------------
    # Scenario 12: Memory Eviction and Cleanup
    # -------------------------------------------------------------------------

    def scenario_memory_eviction(self, initial_items: int = 100,
                                iterations: int = 20,
                                adapter=None) -> OrchestrationResult:
        """
        Tests memory behavior under continuous write/delete cycles.
        Real-world use case: Long-running agent with cleanup requirements.
        """
        if adapter is None:
            raise ValueError("Adapter required")

        print(f"\n  [Scenario 12] Memory Eviction ({initial_items} initial, {iterations} iterations)")

        operations = []
        errors = []

        # Initial population
        for i in range(initial_items):
            key = f"eviction/initial_{i}"
            try:
                adapter.write(key, {"index": i, "type": "initial"})
            except Exception as e:
                errors.append(f"initial_write_{i}: {str(e)}")

        # Track list before
        list_start = time.perf_counter()
        try:
            adapter.list_all()
            list_time = (time.perf_counter() - list_start) * 1000
            operations.append(("eviction", "list_before", list_time, True))
        except Exception as e:
            errors.append(f"list_before: {str(e)}")

        # Continuous write/delete cycles
        for iteration in range(iterations):
            # Write new item
            key = f"eviction/iter_{iteration}"
            try:
                adapter.write(key, {"iteration": iteration, "type": "new"})
                operations.append(("eviction", "write", 0, True))
            except Exception as e:
                errors.append(f"iter_write_{iteration}: {str(e)}")

            # Delete old item
            if iteration < initial_items:
                old_key = f"eviction/initial_{iteration}"
                try:
                    adapter.delete(old_key)
                    operations.append(("eviction", "delete", 0, True))
                except Exception as e:
                    errors.append(f"iter_delete_{iteration}: {str(e)}")

        # List after
        list_start = time.perf_counter()
        try:
            adapter.list_all()
            list_time = (time.perf_counter() - list_start) * 1000
            operations.append(("eviction", "list_after", list_time, True))
        except Exception as e:
            errors.append(f"list_after: {str(e)}")

        session = AgentSession(
            agent_id="eviction_tester",
            session_id=str(uuid.uuid4()),
            goal=f"Memory eviction with {iterations} iterations",
            state=AgentState.COMPLETE,
            memories_written=iterations,
            memories_read=0
        )
        session.completed_at = datetime.now()

        result = OrchestrationResult(
            scenario_name="memory_eviction",
            total_duration_ms=0,
            agents=[session],
            operations=operations,
            memory_contention_events=0,
            coordination_overhead_ms=0,
            errors=errors
        )
        self.results.append(result)
        return result

    # -------------------------------------------------------------------------
    # Run All Scenarios
    # -------------------------------------------------------------------------

    def run_all_scenarios(self, adapter, clear_between: bool = True) -> List[OrchestrationResult]:
        """Run all benchmark scenarios."""
        print("\n" + "=" * 70)
        print("RUNNING MULTI-AGENT MCP BENCHMARK SCENARIOS")
        print("=" * 70)

        if clear_between:
            # Try to clear memory between scenarios
            try:
                adapter.list_all()
            except:
                pass

        scenarios = [
            ("Long Conversation", lambda: self.scenario_single_agent_long_conversation(
                adapter=adapter, num_turns=20)),
            ("Multi-Agent Collaborative", lambda: self.scenario_multi_agent_collaborative(
                adapter=adapter, num_agents=3, tasks_per_agent=5)),
            ("Agent Handoff", lambda: self.scenario_agent_handoff(
                adapter=adapter, num_handlers=4, items_per_handler=3)),
            ("Session Recovery", lambda: self.scenario_session_recovery(
                adapter=adapter, sessions=5, items_per_session=10)),
            ("Concurrent Contention", lambda: self.scenario_concurrent_contention(
                adapter=adapter, num_agents=10, operations_per_agent=5)),
            ("Error Recovery", lambda: self.scenario_error_recovery(
                adapter=adapter, num_agents=5, error_rate=0.2)),
            ("Complex Search", lambda: self.scenario_complex_search(
                adapter=adapter, num_agents=3, searches_per_agent=10)),
            ("Batch vs Streaming", lambda: self.scenario_batch_vs_streaming(
                adapter=adapter, batch_size=50, streaming_chunk=5)),
            ("Large Payloads", lambda: self.scenario_large_payloads(
                adapter=adapter, sizes=[1_000, 10_000, 100_000])),
            ("Special Characters", lambda: self.scenario_special_characters(
                adapter=adapter)),
            ("Hierarchical Structure", lambda: self.scenario_hierarchical_structure(
                adapter=adapter, num_workers=4, tasks_per_worker=3)),
            ("Memory Eviction", lambda: self.scenario_memory_eviction(
                adapter=adapter, initial_items=50, iterations=20)),
        ]

        results = []
        for name, scenario_fn in scenarios:
            try:
                result = scenario_fn()
                results.append(result)
            except Exception as e:
                print(f"\n  ERROR in {name}: {str(e)}")
                results.append(OrchestrationResult(
                    scenario_name=name,
                    total_duration_ms=0,
                    agents=[],
                    operations=[],
                    memory_contention_events=0,
                    coordination_overhead_ms=0,
                    errors=[str(e)]
                ))

        return results

    def print_summary(self):
        """Print summary of all scenario results."""
        print("\n" + "=" * 70)
        print("MULTI-AGENT BENCHMARK SUMMARY")
        print("=" * 70)

        for result in self.results:
            print(f"\n  {result.scenario_name}:")
            print(f"    Duration: {result.total_duration_ms:.2f}ms")
            print(f"    Agents: {len(result.agents)}")
            print(f"    Operations: {len(result.operations)}")
            print(f"    Success Rate: {sum(1 for _, _, _, s in result.operations if s) / len(result.operations) * 100:.1f}%"
                  if result.operations else "    Success Rate: N/A")
            print(f"    Contention Events: {result.memory_contention_events}")
            print(f"    Errors: {len(result.errors)}")

    def export_results(self, filepath: str):
        """Export all results to JSON."""
        export_data = {
            "timestamp": datetime.now().isoformat(),
            "scenarios": [r.to_dict() for r in self.results],
            "total_scenarios": len(self.results)
        }

        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)

        print(f"\nResults exported to: {filepath}")