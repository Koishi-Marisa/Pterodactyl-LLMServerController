"""
联网搜索模块
支持 DuckDuckGo（免费无需 Key）和 Tavily（需 API Key）
"""
import asyncio
import logging

import aiohttp

logger = logging.getLogger(__name__)

# 搜索结果缓存 {query: (result_text, timestamp)}
_search_cache: dict[str, tuple[str, float]] = {}
CACHE_TTL = 300  # 缓存有效期 5 分钟


def _get_cache(query: str) -> str | None:
    """从缓存获取搜索结果"""
    import time
    if query in _search_cache:
        text, ts = _search_cache[query]
        if time.time() - ts < CACHE_TTL:
            return text
        del _search_cache[query]
    return None


def _set_cache(query: str, text: str):
    """写入缓存"""
    import time
    _search_cache[query] = (text, time.time())
    # 限制缓存大小
    if len(_search_cache) > 100:
        oldest = min(_search_cache, key=lambda k: _search_cache[k][1])
        del _search_cache[oldest]


async def search_duckduckgo(query: str, max_results: int = 3) -> str:
    """使用 DuckDuckGo 搜索（免费，无需 API Key）"""
    cached = _get_cache(query)
    if cached:
        logger.debug(f"[搜索缓存] DuckDuckGo: {query}")
        return cached

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; PterodactylBot/1.0)",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://html.duckduckgo.com/html/",
                headers=headers,
                data={"q": query},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"DuckDuckGo 搜索失败: HTTP {resp.status}")
                    return ""

                html = await resp.text()

                # 简单提取搜索结果片段（从 HTML 中提取 snippet）
                results = _extract_ddg_snippets(html, max_results)
                if not results:
                    return ""

                summary = "以下是最新的搜索结果:\n"
                for i, (title, snippet) in enumerate(results, 1):
                    summary += f"{i}. {title}: {snippet}\n"

                _set_cache(query, summary)
                return summary

    except asyncio.TimeoutError:
        logger.warning("DuckDuckGo 搜索超时")
        return ""
    except Exception as e:
        logger.warning(f"DuckDuckGo 搜索异常: {e}")
        return ""


async def search_tavily(query: str, api_key: str, max_results: int = 3) -> str:
    """使用 Tavily 搜索（需要 API Key，每月 1000 次免费）"""
    cached = _get_cache(query)
    if cached:
        logger.debug(f"[搜索缓存] Tavily: {query}")
        return cached

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "query": query,
            "max_results": max_results,
            "include_answer": False,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.tavily.com/search",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Tavily 搜索失败: HTTP {resp.status}")
                    return ""

                data = await resp.json()
                results = data.get("results", [])

                if not results:
                    return ""

                summary = "以下是最新的搜索结果:\n"
                for i, r in enumerate(results[:max_results], 1):
                    title = r.get("title", "")
                    content = r.get("content", "")
                    summary += f"{i}. {title}: {content}\n"

                _set_cache(query, summary)
                return summary

    except asyncio.TimeoutError:
        logger.warning("Tavily 搜索超时")
        return ""
    except Exception as e:
        logger.warning(f"Tavily 搜索异常: {e}")
        return ""


def _extract_ddg_snippets(html: str, max_results: int) -> list[tuple[str, str]]:
    """
    从 DuckDuckGo HTML 响应中提取搜索结果

    Returns:
        [(title, snippet), ...]
    """
    import re

    results = []

    # DuckDuckGo HTML 结果格式：class="result__title" 和 class="result__snippet"
    # 提取所有结果块
    blocks = re.findall(
        r'<a[^>]*class="result__a"[^>]*>(.*?)</a>.*?'
        r'class="result__snippet"[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    )

    for title_html, snippet_html in blocks:
        # 去除 HTML 标签
        title = re.sub(r"<[^>]+>", "", title_html).strip()
        snippet = re.sub(r"<[^>]+>", "", snippet_html).strip()
        if title and snippet:
            results.append((title, snippet))

    return results[:max_results]


async def web_search(
    query: str,
    provider: str = "duckduckgo",
    api_key: str = "",
    max_results: int = 3,
) -> str:
    """
    统一搜索接口

    Args:
        query: 搜索关键词
        provider: 搜索引擎 (duckduckgo / tavily)
        api_key: API Key（Tavily 需要）
        max_results: 最大结果数

    Returns:
        搜索结果摘要文本，搜索失败返回空字符串
    """
    if not query or len(query) < 2:
        return ""

    if provider == "tavily":
        if not api_key:
            logger.warning("Tavily 搜索需要 API_KEY，回退到 DuckDuckGo")
            return await search_duckduckgo(query, max_results)
        return await search_tavily(query, api_key, max_results)

    # 默认使用 DuckDuckGo
    return await search_duckduckgo(query, max_results)
