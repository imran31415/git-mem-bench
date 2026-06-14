#!/usr/bin/env python3
"""
Server adapters that map common benchmark operations to each system's actual MCP tools.

Each MCP memory system has a different API paradigm:
  - git-mem: key-value store (memSet/memGet/memDelete/memList/memSearch)
  - engram: session/observation store (mem_save/mem_search/mem_delete)
  - @modelcontextprotocol/server-memory: knowledge graph (create_entities/open_nodes/search_nodes/delete_entities)

The adapters provide a uniform interface so the benchmark can measure equivalent
logical operations across all systems fairly.
"""
import json
import re
from typing import Any, Dict, Optional


class MemoryAdapter:
    """Base class: uniform interface over any MCP memory tool."""

    def __init__(self, client):
        self.client = client

    # -----------------------------------------------------------------
    # Operations that every adapter must implement
    # -----------------------------------------------------------------

    def write(self, key: str, value: Any) -> Dict:
        raise NotImplementedError

    def read(self, key: str) -> Dict:
        raise NotImplementedError

    def search(self, query: str) -> Dict:
        raise NotImplementedError

    def delete(self, key: str) -> Dict:
        raise NotImplementedError

    def list_all(self) -> Dict:
        raise NotImplementedError

    # -----------------------------------------------------------------
    # Metadata that the reporting layer reads
    # -----------------------------------------------------------------

    @property
    def read_mode(self) -> str:
        """Describe how READ is implemented (used in the benchmark report)."""
        return "direct key lookup"

    @property
    def delete_mode(self) -> str:
        return "direct key delete"


# ---------------------------------------------------------------------------
# git-mem adapter
# ---------------------------------------------------------------------------

class GitMemAdapter(MemoryAdapter):
    """
    Maps to git-mem's native key-value tools.
    All operations are O(1) on key; search does a full-text scan.
    """

    def write(self, key: str, value: Any) -> Dict:
        return self.client.call_tool("memSet", {"key": key, "value": value})

    def read(self, key: str) -> Dict:
        return self.client.call_tool("memGet", {"key": key})

    def search(self, query: str) -> Dict:
        return self.client.call_tool("memSearch", {"query": query})

    def delete(self, key: str) -> Dict:
        return self.client.call_tool("memDelete", {"key": key})

    def list_all(self) -> Dict:
        return self.client.call_tool("memList", {})


# ---------------------------------------------------------------------------
# engram adapter
# ---------------------------------------------------------------------------

class EngramAdapter(MemoryAdapter):
    """
    Maps to engram's session/observation API.

    Key design differences vs git-mem:
      - Writes produce an observation_id; the adapter tracks key→id for deletes.
      - There is no direct key lookup: READ is implemented as a title search
        (mem_search with the key as the query), so latency includes search overhead.
      - Delete requires the observation_id returned at write time.
    """

    def __init__(self, client):
        super().__init__(client)
        self._key_to_obs_id: Dict[str, str] = {}

    def _extract_obs_id(self, result: Dict) -> Optional[str]:
        """Parse the observation ID from a mem_save response."""
        try:
            text = result["content"][0]["text"]
            data = json.loads(text)
            return data.get("sync_id") or data.get("id") or None
        except (KeyError, IndexError, json.JSONDecodeError, TypeError):
            return None

    def write(self, key: str, value: Any) -> Dict:
        content = json.dumps(value) if not isinstance(value, str) else value
        result = self.client.call_tool("mem_save", {
            "title": key,
            "content": content,
        })
        obs_id = self._extract_obs_id(result)
        if obs_id:
            self._key_to_obs_id[key] = obs_id
        return result

    def read(self, key: str) -> Dict:
        # engram has no direct key lookup; closest equivalent is a title search
        return self.client.call_tool("mem_search", {"query": key, "limit": 1})

    def search(self, query: str) -> Dict:
        return self.client.call_tool("mem_search", {"query": query, "limit": 10})

    def delete(self, key: str) -> Dict:
        obs_id = self._key_to_obs_id.get(key)
        if obs_id:
            return self.client.call_tool("mem_delete", {"observation_id": obs_id})
        # Fallback: search to find ID, then delete
        result = self.client.call_tool("mem_search", {"query": key, "limit": 1})
        extracted_id = self._extract_id_from_search(result)
        if extracted_id:
            return self.client.call_tool("mem_delete", {"observation_id": extracted_id})
        return result

    def _extract_id_from_search(self, result: Dict) -> Optional[str]:
        """Try to pull an obs-id out of a mem_search text response."""
        try:
            text = result["content"][0]["text"]
            m = re.search(r'obs-[a-f0-9]+', text)
            return m.group(0) if m else None
        except (KeyError, IndexError, TypeError):
            return None

    def list_all(self) -> Dict:
        return self.client.call_tool("mem_context", {})

    @property
    def read_mode(self) -> str:
        return "search by title (no direct key lookup)"

    @property
    def delete_mode(self) -> str:
        return "delete by observation_id (tracked from write)"


# ---------------------------------------------------------------------------
# @modelcontextprotocol/server-memory adapter  (knowledge graph)
# ---------------------------------------------------------------------------

class MCPKnowledgeGraphAdapter(MemoryAdapter):
    """
    Maps to the official MCP knowledge-graph memory server.

    Storage model: entities with a name, type, and a list of text observations.
    This is a richer data model than key-value but the benchmark uses it in
    K/V mode (one observation per entity) to keep comparisons fair.
    """

    def write(self, key: str, value: Any) -> Dict:
        obs = json.dumps(value) if not isinstance(value, str) else value
        return self.client.call_tool("create_entities", {
            "entities": [{"name": key, "entityType": "memory", "observations": [obs]}]
        })

    def read(self, key: str) -> Dict:
        return self.client.call_tool("open_nodes", {"names": [key]})

    def search(self, query: str) -> Dict:
        return self.client.call_tool("search_nodes", {"query": query})

    def delete(self, key: str) -> Dict:
        return self.client.call_tool("delete_entities", {"entityNames": [key]})

    def list_all(self) -> Dict:
        return self.client.call_tool("read_graph", {})


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ADAPTER_REGISTRY: Dict[str, type] = {
    "git-mem": GitMemAdapter,
    "engram": EngramAdapter,
    "mcp-knowledge-graph": MCPKnowledgeGraphAdapter,
}
