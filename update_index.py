"""Regenerate index.html listing all issues in magazines/, newest first.

Run after writing a new magazine to keep the GitHub Pages landing page fresh.
"""
from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAGS = ROOT / "magazines"

DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.html$")
MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"]


def extract_title(path: Path) -> str:
    """Pull the first <h1> we can find, for the issue summary."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            html = f.read(8000)
    except OSError:
        return ""
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL | re.IGNORECASE)
    if not m:
        return ""
    txt = re.sub(r"<[^>]+>", "", m.group(1))
    return " ".join(txt.split())[:120]


def discover():
    issues = []
    if not MAGS.exists():
        return issues
    for name in os.listdir(MAGS):
        m = DATE_RE.match(name)
        if not m:
            continue
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        issues.append((y, mo, d, name))
    issues.sort(reverse=True)
    return issues


def card(y: int, mo: int, d: int, name: str, title: str) -> str:
    date_label = f"{d:02d} {MONTHS[mo-1]} {y}"
    link = f"magazines/{name}"
    return f"""
    <a class="issue" href="{link}">
      <div class="issue-date">{date_label}</div>
      <div class="issue-title">{title or 'Today&rsquo;s ten stories, curated.'}</div>
      <div class="issue-read">Read the issue →</div>
    </a>"""


def build():
    issues = discover()
    if not issues:
        cards = "<p class='empty'>No issues yet. First one lands tomorrow at 07:00.</p>"
    else:
        cards = "\n".join(card(y, mo, d, n, extract_title(MAGS / n)) for (y, mo, d, n) in issues)

    latest_link = f"magazines/{issues[0][3]}" if issues else ""
    latest_cta = f"<a class='cta' href='{latest_link}'>Read today&rsquo;s issue</a>" if latest_link else ""

    html = f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Morning Edition, archive</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=Inter:wght@400;500;600;700;900&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Inter', system-ui, sans-serif; font-size: 20px; line-height: 1.55; background: #f5f1e8; color: #1a1206; -webkit-font-smoothing: antialiased; }}
  a {{ color: inherit; text-decoration: none; }}
  .wrap {{ max-width: 1180px; margin: 0 auto; padding: clamp(40px, 6vw, 100px) clamp(24px, 5vw, 60px); }}
  .flag {{ border-top: 3px solid #1a1206; border-bottom: 1px solid #1a1206; padding: 18px 0; display: flex; justify-content: space-between; font-weight: 600; font-size: 17px; }}
  .word {{ font-family: 'Fraunces', serif; font-weight: 900; font-style: italic; font-size: clamp(80px, 14vw, 200px); line-height: 0.88; letter-spacing: -0.035em; margin-top: clamp(30px, 5vw, 60px); }}
  .sub {{ font-family: 'Fraunces', serif; font-style: italic; font-size: clamp(24px, 3vw, 38px); margin-top: 24px; max-width: 820px; font-weight: 400; line-height: 1.15; }}
  .cta {{ display: inline-block; margin-top: 36px; padding: 18px 28px; background: #1a1206; color: #f5f1e8; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; font-size: 16px; border-radius: 2px; }}
  .cta:hover {{ background: #8a2e13; }}
  .archive-head {{ margin-top: clamp(60px, 8vw, 120px); border-top: 1.5px solid #1a1206; padding-top: 28px; font-size: 15px; letter-spacing: 0.2em; text-transform: uppercase; font-weight: 700; }}
  .issues {{ margin-top: 30px; display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 22px; }}
  .issue {{ display: block; padding: 28px; background: #ead9b8; border-radius: 4px; transition: transform .15s, background .15s; }}
  .issue:hover {{ background: #dec89a; transform: translateY(-3px); }}
  .issue-date {{ font-size: 15px; letter-spacing: 0.18em; text-transform: uppercase; font-weight: 700; color: #6a4d1a; }}
  .issue-title {{ font-family: 'Fraunces', serif; font-weight: 800; font-size: 26px; line-height: 1.1; margin-top: 12px; letter-spacing: -0.01em; }}
  .issue-read {{ margin-top: 18px; font-size: 15px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; }}
  .empty {{ padding: 40px 0; font-style: italic; font-size: 22px; color: #6a4d1a; }}
  footer {{ margin-top: clamp(60px, 8vw, 100px); font-size: 15px; border-top: 1px solid #1a1206; padding-top: 22px; display: flex; justify-content: space-between; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="flag">
    <span>Vol. 1 · Archive</span>
    <span>Kavi&rsquo;s Desk</span>
    <span>Fresh at 07:00 daily</span>
  </div>
  <h1 class="word">Morning<br>Edition.</h1>
  <p class="sub">Ten stories. No small fonts. Curated each morning from Hacker News, Reddit, Lobsters and the wires, for the way you actually work.</p>
  {latest_cta}

  <div class="archive-head">All issues</div>
  <div class="issues">
    {cards}
  </div>

  <footer>
    <span>Built for Kavi · Claude at 07:00</span>
    <span>Published on GitHub Pages</span>
  </footer>
</div>
</body>
</html>
"""

    out = ROOT / "index.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    return out, len(issues)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    path, n = build()
    print(f"wrote {path} · {n} issue(s)")
