#!/bin/bash
# Setup script for MCP Memory Benchmark Framework

echo "Setting up MCP Memory Benchmark Framework..."
echo "=============================================="

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Python3 is not installed. Please install Python 3.10+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Check for Go (required for git-mem and engram)
if ! command -v go &> /dev/null; then
    echo "Go is not installed. Some MCP servers require Go."
    echo "Install Go from: https://golang.org/dl/"
fi

# Create virtual environment
echo ""
echo "Creating Python virtual environment..."
python3 -m venv venv || {
    echo "Failed to create virtual environment"
    echo "You may need to install python3-venv package"
    exit 1
}

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install psutil pandas matplotlib seaborn || {
    echo "Failed to install Python dependencies"
    echo "You can skip psutil installation but resource monitoring will be disabled"
    read -p "Continue without psutil? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Continuing without psutil..."
    else
        exit 1
    fi
}

# Check for MCP servers
echo ""
echo "Checking for MCP servers..."

# Check git-mem
if command -v git-mem &> /dev/null; then
    echo "✓ git-mem is installed"
    git-mem -version
else
    echo "✗ git-mem is not installed"
    echo "Install with: go install github.com/imran31415/git-mem/cmd/git-mem@latest"
fi

# Check engram
if command -v engram &> /dev/null; then
    echo "✓ engram is installed"
    engram version 2>/dev/null || echo "  (version check failed)"
else
    echo "✗ engram is not installed"
    echo "Install with: go install github.com/Gentleman-Programming/engram/cmd/engram@latest"
fi

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p results/{raw,processed,visualizations}
mkdir -p config
mkdir -p docs/final_report

# Copy configuration if it doesn't exist
if [ ! -f config/benchmark_config.json ]; then
    echo "Creating default configuration..."
    cat > config/benchmark_config.json << 'EOF'
{
  "servers": {
    "git-mem-sync": {
      "command": ["git-mem", "-repo", "/tmp/benchmark-git-mem-sync"],
      "enabled": true,
      "description": "git-mem with synchronous writes"
    },
    "git-mem-async": {
      "command": ["git-mem", "-repo", "/tmp/benchmark-git-mem-async", "-async-writes", "10ms"],
      "enabled": true,
      "description": "git-mem with async writes (10ms flush)"
    },
    "engram": {
      "command": ["engram", "mcp", "--tools=agent"],
      "enabled": true,
      "description": "SQLite-based memory with full-text search"
    }
  },
  "benchmark": {
    "test_data_size": 100,
    "crud_operations": 50,
    "search_queries": ["test", "item", "document", "benchmark"],
    "concurrent_threads": 3,
    "output_directory": "./results"
  }
}
EOF
fi

echo ""
echo "Setup complete!"
echo ""
echo "To run benchmarks:"
echo "1. Activate virtual environment: source venv/bin/activate"
echo "2. Run basic benchmark: python3 run_benchmark.py"
echo "3. Run async benchmark: python3 run_async_benchmark.py"
echo ""
echo "Edit config/benchmark_config.json to customize benchmark settings."