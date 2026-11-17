#!/usr/bin/env python3
"""Send new business news from RSS feeds to a Telegram chat/channel.

Env vars:
  TELEGRAM_BOT_TOKEN  - from @BotFather
  TELEGRAM_CHAT_ID    - your user id, group id, or @channelname
Optional:
  MAX_PER_RUN         - max messages per run (default 10)
  SEEN_FILE           - dedupe state file (default seen.json)
"""
import html
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

FEEDS = [
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147",
    "https://www.ft.com/companies?format=rss",
    "https://finance.yahoo.com/news/rssindex",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
]

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN", "10"))
SEEN_FILE = os.environ.get("SEEN_FILE", "seen.json")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 NewsBot"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def parse_feed(url):
    items = []
    root = ET.fromstring(fetch(url))
    source = root.findtext("./channel/title") or url
    for it in root.iter("item"):
        link = (it.findtext("link") or "").strip()
        title = (it.findtext("title") or "").strip()
        if link and title:
            items.append({"title": title, "link": link, "source": source})
    return items


def send(text):
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "false",
    }).encode()
    urllib.request.urlopen(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data, timeout=20
    ).read()


def main():
    try:
        seen = set(json.load(open(SEEN_FILE)))
    except (FileNotFoundError, json.JSONDecodeError):
        seen = set()
    first_run = not seen

    new = []
    for url in FEEDS:
        try:
            for item in parse_feed(url):
                if item["link"] not in seen:
                    new.append(item)
        except Exception as e:
            print(f"feed failed {url}: {e}", file=sys.stderr)

    # On the very first run, just record existing items so you aren't flooded.
    if first_run:
        seen.update(i["link"] for i in new)
        new = []

    sent = 0
    for item in new:
        if sent >= MAX_PER_RUN:
            break
        msg = (
            f"📰 <b>{html.escape(item['title'])}</b>\n"
            f"<i>{html.escape(item['source'])}</i>\n"
            f"{html.escape(item['link'])}"
        )
        try:
            send(msg)
            seen.add(item["link"])
            sent += 1
            time.sleep(1)
        except Exception as e:
            print(f"send failed: {e}", file=sys.stderr)

    json.dump(sorted(seen)[-2000:], open(SEEN_FILE, "w"))
    print(f"sent {sent}, pending {max(0, len(new) - sent)}")


if __name__ == "__main__":
    main()
