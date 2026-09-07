"""Free per-ticker news headlines via Google News RSS.

No API key, no signup, no daily quota. FMP's per-ticker news endpoint is
restricted on the free tier (confirmed directly against a live key), so
this replaces it for the research_ticker node.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

import requests


class NewsClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        # Google News RSS frequently 403s requests without a browser-like
        # User-Agent header, even though no auth/API key is otherwise required.
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
            }
        )

    def get_headlines(self, query: str, limit: int = 8) -> list[dict[str, str]]:
        """`query` is typically "TICKER stock" -- Google News searches the web,
        so a plain company/ticker query works better than a strict API filter.
        """
        resp = self.session.get(
            "https://news.google.com/rss/search",
            params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
            timeout=20,
        )
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        headlines: list[dict[str, str]] = []
        for item in root.findall(".//item")[:limit]:
            title = (item.findtext("title") or "").strip()
            if not title:
                continue
            headlines.append(
                {
                    "title": title,
                    "publishedDate": (item.findtext("pubDate") or "").strip(),
                    "text": (item.findtext("description") or "").strip(),
                }
            )
        return headlines
