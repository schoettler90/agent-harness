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

WEB_SEARCH_DESCRIPTION = (
    "\n- Search the web and use the results to inform responses"
    "\n- Provides up-to-date information for current events and recent data"
    "\n- Returns search result information formatted as search result blocks,"
    " including links as markdown hyperlinks"
    "\n- Use this tool for accessing information beyond the model's knowledge cutoff"
    "\n- Searches are performed automatically within a single API call"
    "\n\nCRITICAL REQUIREMENT - You MUST follow this:"
    '\n  - After answering the user\'s question, you MUST include a "Sources:"'
    " section at the end of your response"
    "\n  - In the Sources section, list all relevant URLs from the search results"
    " as markdown hyperlinks: [Title](URL)"
    "\n  - This is MANDATORY - never skip including sources in your response"
    "\n  - Example format:"
    "\n"
    "\n    [Your answer here]"
    "\n"
    "\n    Sources:"
    "\n    - [Source Title 1](https://example.com/1)"
    "\n    - [Source Title 2](https://example.com/2)"
    "\n"
    "\nUsage notes:"
    "\n  - Domain filtering is supported to include or block specific websites"
    "\n  - Web search is only available in the US"
)

WEB_FETCH_DESCRIPTION = (
    "IMPORTANT: This tool WILL FAIL for authenticated or private URLs."
    " Before using this tool, check if the URL points to an authenticated service"
    " (e.g. Google Docs, Confluence, Jira, GitHub)."
    " If so, look for a specialized MCP tool that provides authenticated access."
    "\n\n- Fetches content from a specified URL and processes it using an AI model"
    "\n- Takes a URL and a prompt as input"
    "\n- Fetches the URL content, converts HTML to markdown"
    "\n- Processes the content with the prompt using a small, fast model"
    "\n- Returns the model's response about the content"
    "\n- Use this tool when you need to retrieve and analyze web content"
    "\n\nUsage notes:"
    "\n  - IMPORTANT: If an MCP-provided web fetch tool is available, prefer using"
    " that tool instead of this one, as it may have fewer restrictions."
    "\n  - The URL must be a fully-formed valid URL"
    "\n  - HTTP URLs will be automatically upgraded to HTTPS"
    "\n  - The prompt should describe what information you want to extract from the page"
    "\n  - This tool is read-only and does not modify any files"
    "\n  - Results may be summarized if the content is very large"
    "\n  - When a URL redirects to a different host, the tool will inform you and"
    " provide the redirect URL in a special format."
    " You should then make a new web_fetch request with the redirect URL to fetch the content."
    "\n  - For GitHub URLs, prefer using the gh CLI via Bash instead"
    " (e.g., gh pr view, gh issue view, gh api)."
)


def _apply_domain_filters(
    query: str,
    allowed_domains: list[str] | None,
    blocked_domains: list[str] | None,
) -> str:
    parts = [query]
    if allowed_domains:
        clauses = " OR ".join(f"site:{d}" for d in allowed_domains)
        parts.append(f"({clauses})")
    if blocked_domains:
        parts.extend(f"-site:{d}" for d in blocked_domains)
    return " ".join(parts)


@register_tool("web_search")
def make_web_search_tool(**_: object):
    @function_tool(description_override=WEB_SEARCH_DESCRIPTION)
    async def web_search(
        query: str,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
    ) -> str:
        """Search the web.

        Args:
            query: The search query to use.
            allowed_domains: Only include search results from these domains.
            blocked_domains: Never include search results from these domains.
        """
        api_key = os.environ.get("GOOGLE_API_KEY")
        cse_id = os.environ.get("GOOGLE_CSE_ID")
        if not api_key or not cse_id:
            return "Error: GOOGLE_API_KEY and GOOGLE_CSE_ID must be set."

        effective_query = _apply_domain_filters(query, allowed_domains, blocked_domains)
        params = {"key": api_key, "cx": cse_id, "q": effective_query, "num": 10}
        logger.info("Google search: {q!r}", q=effective_query)

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
    @function_tool(description_override=WEB_FETCH_DESCRIPTION)
    async def web_fetch(url: str, prompt: str) -> str:
        """Fetch a URL and process its content with a prompt.

        Args:
            url: The URL to fetch content from.
            prompt: The prompt to run on the fetched content.
        """
        if url.startswith("http://"):
            url = "https://" + url[len("http://"):]

        logger.info("web_fetch: {url} -- {p!r}", url=url, p=prompt)
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
        full_prompt = (
            f"You are reading a web page to respond to the following prompt.\n\n"
            f"Prompt: {prompt}\n\n"
            f"Page URL: {url}\n\n"
            f"Page content (may be truncated):\n{text}\n\n"
            f"Respond using only the page content. "
            f"Quote URLs or values verbatim where relevant. "
            f"If the page does not contain the answer, say so."
        )

        try:
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0,
            )
            return response.choices[0].message.content or "(empty LLM response)"
        except Exception as e:
            logger.error("web_fetch LLM call failed: {e}", e=e)
            return f"Error from LLM extraction: {e}"

    return web_fetch
