"""
Search Wrapper for Fact Checker
Wraps multi-search-api package for fact checking use cases
"""

import logging
import os
from typing import Any, Dict

from multi_search_api import SmartSearchTool as MultiSearchAPI

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FactCheckerSearchTool:
    """
    Wrapper around multi-search-api for fact checking.

    Provides automatic fallback between search providers:
    1. Serper (best results, free up to 2,500/month)
    2. SearXNG (fully free, open source)
    3. Brave (free tier available)
    4. Google Scraper (last resort)
    """

    def __init__(
        self,
        serper_api_key: str = None,
        brave_api_key: str = None,
        searxng_instance: str = None,
    ):
        """
        Initialize the search tool with API keys.

        Args:
            serper_api_key: Serper API key (optional, falls back to env var)
            brave_api_key: Brave API key (optional, falls back to env var)
            searxng_instance: SearXNG instance URL (optional)
        """
        # Get API keys from environment if not provided
        serper_key = serper_api_key or os.getenv("SERPER_API_KEY")
        brave_key = brave_api_key or os.getenv("BRAVE_API_KEY")

        # Initialize multi-search-api tool
        self.search_tool = MultiSearchAPI(
            serper_api_key=serper_key,
            brave_api_key=brave_key,
            searxng_instance=searxng_instance,
        )

        logger.info("FactCheckerSearchTool initialized with multi-search-api")

    def search(self, query: str, num_results: int = 10) -> Dict[str, Any]:
        """
        Perform a web search with automatic fallback.

        Args:
            query: Search query string
            num_results: Number of results to return (default: 10)

        Returns:
            Dict with search results and metadata
        """
        try:
            result = self.search_tool.search(query, num_results=num_results)
            logger.info(
                f"Search completed via {result.get('provider', 'unknown')} for query: {query[:50]}..."
            )
            return result
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            return {
                "query": query,
                "provider": "error",
                "results": [],
                "error": str(e),
            }

    def run(self, query: str) -> str:
        """
        CrewAI/LangChain compatible interface.

        Performs search and returns formatted string suitable for LLM consumption.

        Args:
            query: Search query string

        Returns:
            Formatted string with search results
        """
        result = self.search(query)

        if not result.get("results"):
            error_msg = result.get("error", "Unknown error")
            return f"No search results found for '{query}'. Error: {error_msg}"

        # Format results for LLM
        formatted = f"Search results for '{query}' (via {result['provider']}):\n\n"

        for i, r in enumerate(result["results"][:5], 1):
            formatted += f"{i}. {r['title']}\n"
            formatted += f"   {r['snippet']}\n"
            formatted += f"   URL: {r['link']}\n\n"

        return formatted

    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all search providers.

        Returns:
            Dict with provider status and usage info
        """
        return self.search_tool.get_status()


def create_search_tool() -> FactCheckerSearchTool:
    """
    Factory function to create a search tool instance.

    Returns:
        Initialized FactCheckerSearchTool
    """
    return FactCheckerSearchTool()


# For backward compatibility with old smart_search_tool
class SmartSearchTool:
    """Backward compatibility wrapper."""

    def __init__(self, serper_api_key: str = None, brave_api_key: str = None):
        self._tool = FactCheckerSearchTool(serper_api_key, brave_api_key)

    def run(self, query: str) -> str:
        return self._tool.run(query)

    def search(self, query: str, **kwargs) -> Dict[str, Any]:
        return self._tool.search(query, **kwargs)


def create_smart_search_tool() -> SmartSearchTool:
    """Backward compatibility factory."""
    return SmartSearchTool()
