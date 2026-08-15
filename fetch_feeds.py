"""Fetch candidate stories for the Morning Edition.

Sources (in priority order):
  1. Hacker News top 30 (firebase api, very reliable)
  2. Lobste.rs hottest (tech / AI leaning, reliable)
  3. Reddit hot posts for Kavi's subs (best-effort; often 403s unauth'd)
  4. Reuters / BBC / NYT RSS feeds (politics, markets, weird science)

Emits one JSON blob to stdout. Claude curates down to the top 10.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import time
from base64 import b64encode
from html.parser import HTMLParser
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

UA = "python:morning-edition:1.0 (by /u/CraftyCoder85)"

# Reddit hard-blocks the unauthenticated .json endpoints (403 Blocked) regardless
# of user agent, but still serves the per-subreddit Atom feeds to a browser UA.
# Probed 2026-08-14: www .json = 403, old .json = 403, www /hot/.rss = 200.
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

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


def fetch_bytes(url: str, timeout: int = 20, accept: str = "*/*", ua: str = UA,
                token: str | None = None) -> bytes:
    headers = {
        "User-Agent": ua,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
    }
    if token:
        headers["Authorization"] = f"bearer {token}"
    req = Request(url, headers=headers)
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


# ---------------- Reddit ----------------

def reddit_token():
    """App-only OAuth token, or None if credentials are not configured.

    Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in the environment. Create the
    pair at https://www.reddit.com/prefs/apps (type: "script"). This lifts the
    limit to ~100 requests/minute AND restores score and comment counts, which
    the curation step ranks on. Without it we fall back to Atom feeds.
    """
    cid = os.environ.get("REDDIT_CLIENT_ID")
    secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not (cid and secret):
        return None
    body = urlencode({"grant_type": "client_credentials"}).encode()
    basic = b64encode(f"{cid}:{secret}".encode()).decode()
    req = Request(
        "https://www.reddit.com/api/v1/access_token",
        data=body,
        headers={"Authorization": f"Basic {basic}", "User-Agent": UA},
    )
    try:
        with urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8", "replace")).get("access_token")
    except Exception:
        return None


def fetch_reddit_oauth(sub: str, token: str, n: int = 8):
    """Authenticated pull. Returns the rich shape: score, comments, selftext."""
    raw = fetch_bytes(
        f"https://oauth.reddit.com/r/{sub}/hot?limit={n}",
        accept="application/json",
        ua=UA,
        token=token,
    )
    data = json.loads(raw.decode("utf-8", "replace"))
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


def fetch_reddit(sub: str, n: int = 8):
    """Pull a subreddit's hot posts via its Atom feed.

    The .json API returns 403 Blocked unauthenticated, whatever user agent you
    send. The Atom feed still serves to a browser UA, so that is the route.
    Trade-off: Atom gives no score or comment count, so curation ranks these on
    title and recency alone. To get scores back, register a Reddit "script" app
    and swap this for an OAuth client_credentials call to oauth.reddit.com.

    Anonymous Reddit tolerates roughly one request a minute before it 429s, so
    main() paces this route hard and caps the total sweep. On a 429 we back off
    once and retry rather than giving up on the sub.
    """
    url = f"https://www.reddit.com/r/{sub}/hot/.rss?limit={n}"
    last_err = None
    for attempt in range(2):
        try:
            raw = fetch_bytes(
                url,
                accept="application/atom+xml, application/xml, text/xml, */*",
                ua=BROWSER_UA,
            )
            txt = raw.decode("utf-8", errors="replace")
            posts = []
            for block in _RSS_ENTRY_RE.findall(txt)[:n]:
                title = _tag(block, "title")
                link = _attr_tag(block, "link", "href")
                if not (title and link):
                    continue
                posts.append({
                    "source": "reddit",
                    "sub": sub,
                    "title": title[:400],
                    "url": link,
                    "permalink": link,
                    "author": _tag(block, "name"),
                    "published": _tag(block, "updated") or _tag(block, "published"),
                    "score": None,       # not exposed by the Atom feed
                    "comments": None,    # not exposed by the Atom feed
                })
            if posts:
                return posts
            last_err = "atom feed parsed to zero entries"
        except (URLError, HTTPError, TimeoutError) as e:
            last_err = str(e)
        except Exception as e:
            # Reddit is best-effort and flaky. Never let one subreddit's oddity
            # crash the whole 7am run - log it and move on.
            last_err = f"{type(e).__name__}: {e}"
        if attempt == 0:
            time.sleep(6)
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

    # Every section below is individually best-effort: if one source misbehaves
    # in a way its own fetch_* function didn't anticipate, log the failure into
    # the output and keep going. The 7am contract with update_index.py / the
    # curation step depends on this script ALWAYS emitting valid JSON to
    # stdout, even in a worst-case run where every source fails.
    try:
        hn = fetch_hn(30)
        out["hackernews"] = hn.get("items", [])
        if "error" in hn:
            out["hackernews_error"] = hn["error"]
    except Exception as e:
        out["hackernews_error"] = f"{type(e).__name__}: {e}"

    try:
        lob = fetch_lobsters(20)
        out["lobsters"] = lob.get("items", [])
        if "error" in lob:
            out["lobsters_error"] = lob["error"]
    except Exception as e:
        out["lobsters_error"] = f"{type(e).__name__}: {e}"

    # Authenticated if credentials are set, anonymous Atom feeds otherwise.
    # The two routes have very different budgets: OAuth allows ~100 req/min,
    # anonymous RSS allows roughly one per minute before it starts 429ing, so
    # the unauthenticated sweep is paced and capped rather than run to the end.
    token = reddit_token()
    out["reddit_route"] = "oauth" if token else "anonymous-atom"
    anon_deadline = time.time() + 300  # 5 min ceiling on the anonymous sweep

    for sub in SUBS:
        if token:
            try:
                out["reddit"][sub] = fetch_reddit_oauth(sub, token, 8)
            except Exception as e:
                out["reddit"][sub] = [{"source": "reddit", "sub": sub, "error": f"{type(e).__name__}: {e}"}]
            time.sleep(0.8)
            continue

        if time.time() > anon_deadline:
            out["reddit"][sub] = [{"source": "reddit", "sub": sub,
                                   "error": "skipped: anonymous rate-limit budget exhausted"}]
            continue
        try:
            out["reddit"][sub] = fetch_reddit(sub, 8)
        except Exception as e:
            out["reddit"][sub] = [{"source": "reddit", "sub": sub, "error": f"{type(e).__name__}: {e}"}]
        time.sleep(20.0)

    for name, url in RSS_FEEDS.items():
        try:
            feed = fetch_rss(name, url, 10)
            out["rss"][name] = feed.get("items", [])
            if "error" in feed:
                out["rss"][name] = [{"error": feed["error"]}]
        except Exception as e:
            out["rss"][name] = [{"error": f"{type(e).__name__}: {e}"}]
        time.sleep(0.3)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
