# MCP Memory Solutions Benchmark Analysis Report

## Executive Summary

We benchmarked two MCP memory solutions:
1. **git-mem**: Git-backed memory with version control and code mode
2. **engram**: SQLite-based memory with full-text search and 19 tools

**Key Finding**: engram demonstrates significantly better performance for write operations (SET), while both solutions perform well for read operations (GET).

## Performance Comparison

### Basic CRUD Operations (Latency in milliseconds, lower is better)

| Operation | git-mem | engram | Winner | Performance Ratio |
|-----------|---------|--------|--------|-------------------|
| **SET** | 22.16 ms | 0.50 ms | **engram** | 44x faster |
| **GET** | 0.17 ms | 0.18 ms | git-mem | 1.06x faster |
| **DELETE** | 3.71 ms | 0.25 ms | **engram** | 15x faster |
| **LIST** | 3.05 ms | 0.14 ms | **engram** | 22x faster |

### Throughput Comparison (Operations per second, higher is better)

| Operation | git-mem | engram | Winner |
|-----------|---------|--------|--------|
| **SET** | 45.1 ops/sec | 1,986.5 ops/sec | **engram** |
| **GET** | 6,058.1 ops/sec | 5,585.8 ops/sec | git-mem |
| **DELETE** | 269.2 ops/sec | 4,071.8 ops/sec | **engram** |
| **LIST** | 328.1 ops/sec | 7,058.7 ops/sec | **engram** |

## Detailed Analysis

### git-mem Performance Profile
- **Strengths**: Excellent read performance (GET operations), git-based version control, unique code mode feature
- **Weaknesses**: Slow write operations (SET), search performance not measured (tool found but not tested)
- **Best For**: Use cases requiring version history, audit trails, or where reads vastly outnumber writes

### engram Performance Profile
- **Strengths**: Exceptional write performance, fast search operations (~6-7ms per query), 15 tools available
- **Weaknesses**: Slightly slower read performance than git-mem
- **Best For**: General-purpose memory storage, applications requiring frequent writes, full-text search needs

## Feature Comparison

| Feature | git-mem | engram |
|---------|---------|--------|
| **Storage Backend** | Git repository | SQLite + FTS5 |
| **Version Control** | ✅ Built-in (git) | ❌ Not native |
| **Full-text Search** | ✅ (memSearch tool) | ✅ (FTS5 integrated) |
| **Number of Tools** | 9 | 15 (agent profile) |
| **Code Mode** | ✅ Unique feature | ❌ Not available |
| **Conflict Resolution** | ✅ Git merge-based | ✅ Through tools |
| **Persistence** | ✅ Git commits | ✅ SQLite database |
| **Performance** | Read-optimized | Write-optimized |

## Search Performance
- **engram search**: 6-7ms per query
- **git-mem search**: Not measured in this benchmark (tool available but timing not captured)

## Recommendations

### Based on Use Case:

1. **For Read-Heavy Workloads** (90%+ reads):
   - **git-mem** is competitive for GET operations
   - Consider if version history is valuable

2. **For Write-Heavy or Balanced Workloads**:
   - **engram** is clearly superior with 44x faster SET operations
   - Better for applications with frequent memory updates

3. **For Full-Text Search Requirements**:
   - **engram** has integrated FTS5 with 6-7ms query times
   - git-mem search performance unknown from this benchmark

4. **For Version Control Needs**:
   - **git-mem** provides native git versioning
   - Essential for audit trails or rollback capabilities

5. **For Code/Programmatic Access**:
   - **git-mem** offers unique "code mode" for batch operations
   - Useful for complex memory manipulation

## Test Methodology Notes

### Limitations:
1. **Resource Monitoring**: psutil not available, so memory/CPU metrics not captured
2. **Search Benchmark**: git-mem search tool found but not properly timed
3. **Concurrent Operations**: Simplified concurrency test (3 threads)
4. **Dataset Size**: 100 test items, 50 CRUD operations

### Strengths:
1. **Real MCP Protocol**: Both solutions tested via actual MCP stdio interface
2. **Comparative Metrics**: Direct comparison of identical operations
3. **Tool Discovery**: Verified available tools for each solution
4. **Success Rates**: 100% success rate for basic operations on both

## Future Benchmark Extensions

### Recommended Next Tests:
1. **Larger Datasets**: Test with 10k+ entries
2. **Concurrent Load**: 10+ simultaneous clients
3. **Special Features**:
   - git-mem code mode performance
   - engram TUI and advanced tools
   - Conflict resolution scenarios
4. **Resource Usage**: Memory and CPU with psutil
5. **Durability Tests**: Process termination and recovery

### Additional Solutions to Test:
1. **SimpleMem**: Python-based with multimodal support
2. **codebase-memory-mcp**: C-based code intelligence server
3. **Custom baseline**: Simple JSON file storage for comparison

## Conclusion

**engram** emerges as the overall performance winner for general-purpose MCP memory needs, offering significantly better write performance and fast full-text search. **git-mem** remains valuable for specific use cases requiring git-based version control or where its unique code mode feature is beneficial.

The choice depends heavily on the specific requirements:
- **Choose engram for**: Performance, full-text search, frequent writes
- **Choose git-mem for**: Version control, audit trails, git integration

Both solutions successfully implement the MCP protocol and provide reliable memory storage for LLM agents.

---

*Benchmark conducted on: 2026-06-11  
Environment: Ubuntu, 4 vCPUs, 8GB RAM  
Test dataset: 100 items, 50 CRUD operations each*