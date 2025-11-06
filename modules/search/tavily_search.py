import logging
import os
from typing import List, Dict, Optional

import httpx
from core.exceptions import SearchError
from settings import settings


class TavilySearch:
    """A class to handle internet search using Tavily API."""

    REQUIRED_ENV_VARS = ["TAVILY_API_KEY"]

    def __init__(self):
        """Initialize the TavilySearch class."""
        self._validate_env_vars()
        self.logger = logging.getLogger(__name__)
        self.api_key = settings.TAVILY_API_KEY
        self.api_url = "https://api.tavily.com/search"

    def _validate_env_vars(self) -> None:
        """Validate that environment variables are set."""
        missing_vars = [var for var in self.REQUIRED_ENV_VARS if not getattr(settings, var, None)]
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}\n"
                "Please set TAVILY_API_KEY in your .env file."
            )

    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        Search the internet using Tavily API.

        Args:
            query: The search query string
            max_results: Maximum number of results to return (default: 5)

        Returns:
            List of dictionaries containing search results with keys: title, content, url

        Raises:
            ValueError: If the query is empty
            SearchError: If the search fails
        """
        if not query.strip():
            raise ValueError("Search query cannot be empty")

        try:
            self.logger.info(f"Searching Tavily for: '{query}'")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "advanced",
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

            results = []
            for result in data.get("results", [])[:max_results]:
                results.append({
                    "title": result.get("title", "No title"),
                    "content": result.get("content", ""),
                    "url": result.get("url", ""),
                })

            self.logger.info(f"Found {len(results)} search results")
            return results

        except httpx.HTTPStatusError as e:
            error_msg = f"Tavily API error: {e.response.status_code} - {e.response.text}"
            self.logger.error(error_msg)
            raise SearchError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to search: {str(e)}"
            self.logger.error(error_msg)
            raise SearchError(error_msg) from e

    def format_search_results(self, results: List[Dict[str, str]]) -> str:
        """
        Format search results into a readable string.

        Args:
            results: List of search result dictionaries

        Returns:
            Formatted string with search results
        """
        if not results:
            return "No search results found."

        formatted = "Search Results:\n\n"
        for i, result in enumerate(results, 1):
            formatted += f"{i}. {result['title']}\n"
            formatted += f"   {result['content'][:200]}...\n"
            formatted += f"   Source: {result['url']}\n\n"

        return formatted
