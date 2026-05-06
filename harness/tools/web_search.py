import os

from agents import function_tool

from harness.tools import register_tool
from src.utils import LoggerSetup

logger = LoggerSetup("WebSearchTool")


@register_tool("web_search")
def make_web_search_tool():
    @function_tool(
        name_override="web_search",
        description_override="Search the web for current information. Requires TAVILY_API_KEY.",
    )
    async def web_search(query: str, max_results: int = 5) -> str:
        """Search the web for information.

        Args:
            query: The search query
            max_results: Maximum number of results to return
        """
        tavily_key = os.environ.get("TAVILY_API_KEY")
        if not tavily_key:
            return "Error: TAVILY_API_KEY not configured. Web search unavailable."

        logger.info("Web search: {query!r}", query=query)

        try:
            from tavily import AsyncTavilyClient

            client = AsyncTavilyClient(api_key=tavily_key)
            response = await client.search(query, max_results=max_results)
            results = response.get("results", [])
            formatted = []
            for r in results:
                formatted.append(f"**{r['title']}**\n{r['url']}\n{r['content'][:300]}")
            return "\n\n---\n\n".join(formatted) or "No results found."
        except ImportError:
            return "Error: tavily-python not installed. Run: uv add tavily-python"
        except Exception as e:
            return f"Error during web search: {e}"

    return web_search
