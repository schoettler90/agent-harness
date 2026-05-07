import os
import re

import httpx
import litellm
from agents import function_tool

from harness.litellm_factory import LiteLLMFactory
from harness.tools import register_tool
from src.settings import settings
from src.utils import LoggerSetup

logger = LoggerSetup("WebSearchTool")

GOOGLE_CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
WEB_FETCH_MAX_CHARS = 50_000
WEB_FETCH_TIMEOUT_S = 20


@register_tool("web_search")
def make_web_search_tool(**_: object):
    @function_tool(
        name_override="web_search",
        description_override=(
            "Search the web via Google Custom Search. Requires GOOGLE_API_KEY and GOOGLE_CSE_ID."
        ),
    )
    async def web_search(query: str, max_results: int = 5) -> str:
        """Search the web via Google Custom Search.

        Args:
            query: The search query.
            max_results: Maximum number of results to return (1-10).
        """
        api_key = os.environ.get("GOOGLE_API_KEY")
        cse_id = os.environ.get("GOOGLE_CSE_ID")
        if not api_key or not cse_id:
            return "Error: GOOGLE_API_KEY and GOOGLE_CSE_ID must be set."

        num = max(1, min(10, max_results))
        params = {"key": api_key, "cx": cse_id, "q": query, "num": num}
        logger.info("Google search: {query!r} (num={num})", query=query, num=num)

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(GOOGLE_CSE_ENDPOINT, params=params)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("Google CSE HTTP error: {e}", e=e)
            return f"Error: Google CSE returned {e.response.status_code}: {e.response.text[:300]}"
        except Exception as e:
            logger.error("Google CSE failed: {e}", e=e)
            return f"Error during web search: {e}"

        items = payload.get("items", [])
        if not items:
            return "No results found."

        formatted = []
        for r in items:
            title = r.get("title", "(no title)")
            link = r.get("link", "")
            snippet = r.get("snippet", "")
            formatted.append(f"**{title}**\n{link}\n{snippet}")
        return "\n\n---\n\n".join(formatted)

    return web_search


def _html_to_text(html: str) -> str:
    """Strip HTML tags and collapse whitespace. Lightweight, no extra deps."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@register_tool("web_fetch")
def make_web_fetch_tool(**_: object):
    @function_tool(
        name_override="web_fetch",
        description_override=(
            "Fetch a URL and use an LLM to answer a query against its contents. "
            "Use this to extract a focused answer from a known page."
        ),
    )
    async def web_fetch(url: str, query: str) -> str:
        """Fetch a URL and answer a query against its contents.

        Args:
            url: The page URL to fetch.
            query: What to extract or answer from the page.
        """
        logger.info("web_fetch: {url} -- {q!r}", url=url, q=query)
        try:
            async with httpx.AsyncClient(timeout=WEB_FETCH_TIMEOUT_S, follow_redirects=True) as c:
                resp = await c.get(url, headers={"User-Agent": "agent-harness/1.0"})
                resp.raise_for_status()
                body = resp.text
        except httpx.HTTPStatusError as e:
            return f"Error: fetch returned {e.response.status_code} for {url}"
        except Exception as e:
            logger.error("web_fetch network error: {e}", e=e)
            return f"Error fetching {url}: {e}"

        text = _html_to_text(body)[:WEB_FETCH_MAX_CHARS]
        if not text:
            return f"Error: empty content from {url}"

        model = LiteLLMFactory.resolve_model(settings.model)
        prompt = (
            f"You are reading a web page to answer a user's query.\n\n"
            f"Query: {query}\n\n"
            f"Page URL: {url}\n\n"
            f"Page content (may be truncated):\n{text}\n\n"
            f"Answer the query using only the page content. "
            f"Quote URLs or values verbatim where relevant. "
            f"If the page does not contain the answer, say so."
        )

        try:
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            return response.choices[0].message.content or "(empty LLM response)"
        except Exception as e:
            logger.error("web_fetch LLM call failed: {e}", e=e)
            return f"Error from LLM extraction: {e}"

    return web_fetch
