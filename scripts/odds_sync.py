"""Pull NFL spreads/totals from The Odds API (free tier, 500 req/month cap
- PRD Section 8) as a game-script proxy, and store a lightweight game-level
snapshot into `projections.raw` keyed by team, so the advisor logic (Phase 3+)
can look up a player's team's spread/total for the week.

Requires ODDS_API_KEY as a GitHub Actions secret.
"""
import datetime
import os
import sys

import requests

from db import insert

API_KEY = os.environ.get("ODDS_API_KEY")
ODDS_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"


def sync():
    if not API_KEY:
        print("ODDS_API_KEY not set, skipping (this cron will no-op until it's added as a secret).")
        return

    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "spreads,totals",
        "oddsFormat": "american",
    }
    resp = requests.get(ODDS_URL, params=params, timeout=30)
    if resp.status_code == 401:
        print("Odds API key rejected - check ODDS_API_KEY secret.", file=sys.stderr)
        sys.exit(1)
    resp.raise_for_status()
    games = resp.json()

    remaining = resp.headers.get("x-requests-remaining")
    used = resp.headers.get("x-requests-used")
    if remaining is not None:
        print(f"Odds API usage: {used} used, {remaining} remaining this month.")
        try:
            if int(used) > 400:  # 80% of the 500/month free cap (PRD Section 14 risk register)
                print("WARNING: Odds API usage is above 80% of the free-tier monthly cap.", file=sys.stderr)
        except (TypeError, ValueError):
            pass

    rows = []
    now = datetime.datetime.utcnow().isoformat()
    for game in games:
        rows.append({
            "player_id": None,  # game-level snapshot, not player-specific; joined by team downstream
            "season": datetime.date.today().year,
            "week": None,
            "source": "the_odds_api",
            "raw": game,
            "created_at": now,
        })

    print(f"Storing {len(rows)} game odds snapshots...")
    insert("projections", rows)
    print("Done.")


if __name__ == "__main__":
    try:
        sync()
    except Exception as e:
        print(f"odds_sync failed: {e}", file=sys.stderr)
        sys.exit(1)
