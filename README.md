# Fact Checker MCP Server

Hybrid CrewAI + MCP implementation for fact-checking with multi-agent verification system.

## Overview

This tool works as both:
1. **CrewAI multi-agent system** for comprehensive fact-checking with multiple specialized agents
2. **MCP server** for direct integration with Claude Desktop and other MCP clients

## Installation & Development

This project uses [UV](https://docs.astral.sh/uv/) for dependency management and virtual environment handling.

### Setup

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Environment variables:**
   Create a `.env` file with:
   ```bash
   OPENAI_API_KEY=your_openai_api_key
   SERPER_API_KEY=your_serper_api_key  # Optional: for enhanced web search
   BRAVE_API_KEY=your_brave_api_key    # Optional: for additional search provider
   ```

## Usage

### As MCP Server (for Claude Desktop)

**Development mode:**
```bash
mcp dev fact-checker.py
```

**Production mode:**
```bash
uv run python fact-checker.py --mcp
```

### As Standalone Application

**Interactive mode:**
```bash
uv run python fact-checker.py --check
```

**File input:**
```bash
uv run python fact-checker.py --check input_text.txt
```

**Pipeline usage:**
```bash
echo "Your text to fact-check" | uv run python fact-checker.py --check
```

### In Python Code

```python
from fact_checker import run_fact_check_crew

# Analyze text for fact checking
report = run_fact_check_crew("Your text to analyze")
print(report.overall_reliability)
```

## Help

Display usage instructions:
```bash
python fact-checker.py --help
```

## MCP Server Tools

When running as MCP server, the following tools are available:

- **`quick_verify(text: str)`** - Fast verification of short claims (< 500 chars)
- **`deep_fact_check(text: str)`** - Comprehensive multi-agent fact-checking
- **`check_specific_statistic(statistic: str, context: str, year: int)`** - Targeted statistic verification
- **`get_history_summary()`** - Summary of all completed fact checks

## MCP Resources

- **`history://list`** - List of all fact-check reports
- **`history://report/{id}`** - Specific fact-check report details

## Features

- **Multi-Provider Search**: Automatic fallback between Serper, SearXNG, Brave Search, and web scraping
- **Smart Usage Tracking**: Monitors API usage limits and rotates between providers
- **Comprehensive Analysis**: Extracts and verifies claims, statistics, quotes, and facts
- **Detailed Reporting**: Provides confidence scores, sources, and explanations
- **Memory & Caching**: Built-in caching and memory management for efficiency

## Code Quality

**Format and lint:**
```bash
uv run ruff format .
uv run ruff check . --fix
```

**Run tests:**
```bash
uv run pytest
```

## Architecture

- **fact-checker.py** - Main server with CrewAI agents and MCP endpoints
- **smart_search_tool.py** - Multi-provider search system with automatic fallback
- **pyproject.toml** - UV project configuration with all dependencies

## Requirements

- Python 3.10+
- OpenAI API key (required)
- Serper API key (optional, enhances search capabilities)
- Brave API key (optional, additional search provider)

## Virtual Environment

The project uses UV's managed virtual environment. The previous manual `.venv` setup has been replaced with proper UV project structure to resolve MCP CLI compatibility issues.