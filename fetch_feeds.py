"""Fetch candidate stories for the Morning Edition.

Sources (in priority order):
  1. Hacker News top 30 (firebase api — very reliable)
  2. Lobste.rs hottest (tech / AI leaning, reliable)
  3. Reddit hot posts for Kavi's subs (best-effort; often 403s unauth'd)
  4. Reuters / BBC / NYT RSS feeds (politics, markets, weird science)

Emits one JSON blob to stdout. Claude curates down to the top 10.
"""
from __future__ import annotations

import io
import json
import re
import sys
import time
from html.parser import HTMLParser
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

UA = "python:morning-edition:1.0 (by /u/CraftyCoder85)"

SUBS = [
    "artificial", "OpenAI", "LocalLLaMA", "singularity",
    "politics", "wallstreetbets", "stocks",
    "Superstonk", "GME",
    "science", "Futurology", "technology",
]

# RSS feeds chosen to cover Kavi's remaining interest areas reliably.
RSS_FEEDS = {
    "bbc_us_politics": "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml",
    "bbc_business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "bbc_science": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    "nyt_politics": "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
    "nyt_business": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    "nyt_science": "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml",
    "ars_technica": "https://feeds.arstechnica.com/arstechnica/index",
    "the_verge_ai": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "marketwatch_top": "https://feeds.marketwatch.com/marketwatch/topstories/",
}


def fetch_bytes(url: str, timeout: int = 20, accept: str = "*/*") -> bytes:
    req = Request(url, headers={
        "User-Agent": UA,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_json(url: str, timeout: int = 20):
    raw = fetch_bytes(url, timeout, accept="application/json")
    return json.loads(raw.decode("utf-8", errors="replace"))


# ---------------- Hacker News ----------------

def fetch_hn(n: int = 30):
    try:
        ids = fetch_json("https://hacker-news.firebaseio.com/v0/topstories.json")[:n]
    except Exception as e:
        return {"error": f"topstories: {e}", "items": []}
    out = []
    for i, sid in enumerate(ids):
        try:
            item = fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
            if not item or item.get("type") != "story":
                continue
            out.append({
                "source": "hackernews",
                "rank": i + 1,
                "id": item.get("id"),
                "title": item.get("title", ""),
                "url": item.get("url") or f"https://news.ycombinator.com/item?id={sid}",
                "score": item.get("score", 0),
                "by": item.get("by", ""),
                "comments": item.get("descendants", 0),
                "hn_discussion": f"https://news.ycombinator.com/item?id={sid}",
            })
        except Exception:
            continue
        time.sleep(0.05)
    return {"items": out}


# ---------------- Lobsters ----------------

def fetch_lobsters(n: int = 20):
    try:
        raw = fetch_json("https://lobste.rs/hottest.json")[:n]
    except Exception as e:
        return {"error": str(e), "items": []}
    out = []
    for i, p in enumerate(raw):
        out.append({
            "source": "lobsters",
            "rank": i + 1,
            "title": p.get("title", ""),
            "url": p.get("url") or p.get("comments_url", ""),
            "score": p.get("score", 0),
            "comments": p.get("comment_count", 0),
            "tags": p.get("tags", []),
            "comments_url": p.get("comments_url", ""),
        })
    return {"items": out}


# ---------------- Reddit (best-effort) ----------------

def fetch_reddit(sub: str, n: int = 8):
    last_err = None
    for host in ("www.reddit.com", "old.reddit.com"):
        url = f"https://{host}/r/{sub}/hot.json?limit={n}"
        try:
            data = fetch_json(url)
            posts = []
            for child in data.get("data", {}).get("children", []):
                p = child.get("data", {})
                if p.get("stickied"):
                    continue
                posts.append({
                    "source": "reddit",
                    "sub": sub,
                    "id": p.get("id"),
                    "title": p.get("title", ""),
                    "url": p.get("url_overridden_by_dest") or f"https://www.reddit.com{p.get('permalink','')}",
                    "permalink": f"https://www.reddit.com{p.get('permalink','')}",
                    "score": p.get("score", 0),
                    "comments": p.get("num_comments", 0),
                    "selftext": (p.get("selftext", "") or "")[:600],
                    "flair": p.get("link_flair_text") or "",
                })
            return posts
        except (URLError, HTTPError, TimeoutError, json.JSONDecodeError) as e:
            last_err = str(e)
            time.sleep(1.5)
    return [{"source": "reddit", "sub": sub, "error": last_err}]


# ---------------- RSS ----------------

_RSS_ITEM_RE = re.compile(r"<item[^>]*>(.*?)</item>", re.DOTALL | re.IGNORECASE)
_RSS_ENTRY_RE = re.compile(r"<entry[^>]*>(.*?)</entry>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<([a-zA-Z0-9:]+)[^>]*>(.*?)</\1>", re.DOTALL)


class _Strip(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _strip_html(s: str) -> str:
    s = s.replace("<![CDATA[", "").replace("]]>", "")
    p = _Strip()
    try:
        p.feed(s)
    except Exception:
        return re.sub(r"<[^>]+>", "", s).strip()
    return "".join(p.parts).strip()


def _tag(block: str, name: str) -> str:
    m = re.search(rf"<{name}[^>]*>(.*?)</{name}>", block, re.DOTALL | re.IGNORECASE)
    return _strip_html(m.group(1)) if m else ""


def _attr_tag(block: str, name: str, attr: str) -> str:
    m = re.search(rf"<{name}[^>]*\b{attr}=[\"']([^\"']+)[\"']", block, re.IGNORECASE)
    return m.group(1) if m else ""


def fetch_rss(name: str, url: str, n: int = 10):
    try:
        raw = fetch_bytes(url, accept="application/rss+xml, application/xml, text/xml, */*")
        txt = raw.decode("utf-8", errors="replace")
    except Exception as e:
        return {"error": str(e), "items": []}

    items = _RSS_ITEM_RE.findall(txt) or _RSS_ENTRY_RE.findall(txt)
    out = []
    for block in items[:n]:
        title = _tag(block, "title")
        link = _tag(block, "link") or _attr_tag(block, "link", "href")
        desc = _tag(block, "description") or _tag(block, "summary") or ""
        pub = _tag(block, "pubDate") or _tag(block, "updated") or ""
        if title and link:
            out.append({
                "source": "rss",
                "feed": name,
                "title": title[:400],
                "url": link,
                "summary": desc[:500],
                "published": pub,
            })
    return {"items": out}


# ---------------- Main ----------------

def main():
    out = {
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "hackernews": [],
        "lobsters": [],
        "reddit": {},
        "rss": {},
    }

    hn = fetch_hn(30)
    out["hackernews"] = hn.get("items", [])
    if "error" in hn:
        out["hackernews_error"] = hn["error"]

    lob = fetch_lobsters(20)
    out["lobsters"] = lob.get("items", [])
    if "error" in lob:
        out["lobsters_error"] = lob["error"]

    for sub in SUBS:
        out["reddit"][sub] = fetch_reddit(sub, 8)
        time.sleep(1.2)

    for name, url in RSS_FEEDS.items():
        feed = fetch_rss(name, url, 10)
        out["rss"][name] = feed.get("items", [])
        if "error" in feed:
            out["rss"][name] = [{"error": feed["error"]}]
        time.sleep(0.3)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
