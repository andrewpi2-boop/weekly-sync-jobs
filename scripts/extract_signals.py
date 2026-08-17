"""Lightweight Haiku call per unprocessed news item: extract which
player(s) are mentioned, the signal type, and severity -> `news_signals`
(PRD Section 11 Phase 2).

Confidence is NOT the model's self-reported certainty (PRD Section 10
explicitly rules that out) - it's computed here from source tier only,
as a starting heuristic. Once Phase 3's cross-source agreement logic
exists, this should be replaced with the real computed-confidence formula.

Requires ANTHROPIC_API_KEY as a GitHub Actions secret.
"""
import json
import os
import sys

import anthropic

from db import select, patch, insert

MODEL = "claude-haiku-4-5"
API_KEY = os.environ.get("ANTHROPIC_API_KEY")

TIER_BASE_CONFIDENCE = {
    "official": 0.9,
    "beat_reporter": 0.65,
    "aggregator": 0.45,
    "social": 0.3,
}

EXTRACT_PROMPT = """You are extracting structured fantasy-football signals from a news item.
Given the headline and text below, identify every NFL player mentioned and what's being reported.

Headline: {headline}
Text: {text}

Respond with ONLY a JSON array (no prose), one object per player mentioned:
[{{"player_name": "...", "signal_type": "injury|role_change|depth_chart|suspension|trade|other", "severity": "low|medium|high", "summary": "one sentence"}}]
If no players are clearly identifiable, respond with an empty array: []
"""


def sync():
    if not API_KEY:
        print("ANTHROPIC_API_KEY not set, skipping (this cron will no-op until it's added as a secret).")
        return

    client = anthropic.Anthropic(api_key=API_KEY)

    unprocessed = select("news_items", params={"processed": "eq.false", "limit": 50})
    print(f"Processing {len(unprocessed)} unprocessed news items...")

    players = select("players", params={"select": "id,full_name"})
    by_name = {p["full_name"].lower(): p["id"] for p in players}

    for item in unprocessed:
        prompt = EXTRACT_PROMPT.format(
            headline=item.get("headline", ""), text=(item.get("raw_text") or "")[:2000]
        )
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            signals = json.loads(text)
        except Exception as e:
            print(f"Extraction failed for news_item {item['id']}: {e}", file=sys.stderr)
            continue

        rows = []
        for sig in signals:
            player_id = by_name.get((sig.get("player_name") or "").lower())
            if not player_id:
                continue  # PRD Section 10: don't guess a player match, skip rather than mis-link
            rows.append({
                "news_item_id": item["id"],
                "player_id": player_id,
                "signal_type": sig.get("signal_type", "other"),
                "severity": sig.get("severity", "low"),
                "confidence": TIER_BASE_CONFIDENCE.get(item.get("source_tier"), 0.3),
                "source_tier": item.get("source_tier"),
                "summary": sig.get("summary", ""),
            })

        if rows:
            insert("news_signals", rows)
        patch("news_items", params={"id": f"eq.{item['id']}"}, body={"processed": True})

    print("Done.")


if __name__ == "__main__":
    try:
        sync()
    except Exception as e:
        print(f"extract_signals failed: {e}", file=sys.stderr)
        sys.exit(1)
