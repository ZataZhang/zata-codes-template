"""Web Search 工具实现。"""

from __future__ import annotations

from typing import Any


def run_web_search_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """执行网页搜索（MVP 阶段返回 mock 结果）。"""
    query = arguments.get("query", "")
    return {
        "query": query,
        "results": [
            {
                "title": f"Result for: {query}",
                "snippet": "This is a mock search result used for demonstration.",
                "url": "https://example.com/mock-result",
            }
        ],
    }
