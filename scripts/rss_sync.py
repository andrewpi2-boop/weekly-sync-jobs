"""Ingest player-news RSS feeds into `news_items`, tagged with a source
tier (PRD Section 10: official > beat_reporter > aggregator > social).
No LLM calls here - that's extract_signals.py's job, kept as a separate
step so ingestion never blocks on (or costs) an API call.
"""
import datetime
import hashlib
import sys

import feedparser

from db import select, insert

# (feed url, source label, source tier)
FEEDS = [
    ("https://www.rotowire.com/rss/news.php?sport=NFL", "rotowire", "beat_reporter"),
    ("https://www.pff.com/feed", "pff", "beat_reporter"),
]


def item_key(entry):
    raw = (entry.get("link") or entry.get("id") or entry.get("title", "")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def sync():
    existing_urls = {
        row["url"] for row in select("news_items", params={"select": "url", "limit": 2000})
        if row.get("url")
    }

    rows = []
    now = datetime.datetime.utcnow().isoformat()
    for feed_url, source, tier in FEEDS:
        try:
            parsed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"Feed parse failed for {source}: {e}", file=sys.stderr)
            continue

        for entry in parsed.entries:
            link = entry.get("link")
            if not link or link in existing_urls:
                continue
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            published_iso = (
                datetime.datetime(*published[:6]).isoformat() if published else now
            )
            rows.append({
                "source": source,
                "source_tier": tier,
                "url": link,
                "headline": entry.get("title", "")[:500],
                "raw_text": (entry.get("summary") or "")[:5000],
                "published_at": published_iso,
                "ingested_at": now,
                "processed": False,
            })

    print(f"Ingesting {len(rows)} new news items...")
    if rows:
        insert("news_items", rows)
    print("Done.")


if __name__ == "__main__":
    try:
        sync()
    except Exception as e:
        print(f"rss_sync failed: {e}", file=sys.stderr)
        sys.exit(1)
