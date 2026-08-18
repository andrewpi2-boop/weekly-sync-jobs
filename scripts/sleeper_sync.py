"""Match existing players to Sleeper's public player directory and patch
sleeper_player_id + status_detail onto the players table.

Sleeper's /v1/players/nfl endpoint returns the full player dictionary in one
shot (no auth required, no rate limit documented, but it's a big payload so
we only call it once per run). Matching is by normalized full name since
there's no shared external ID between nflverse and Sleeper.
"""
import re
import sys
import requests
from db import select, patch

SLEEPER_URL = "https://api.sleeper.app/v1/players/nfl"

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def normalize(name):
    if not name:
        return ""
    name = name.lower()
    name = re.sub(r"[.'\-]", "", name)
    parts = [p for p in name.split() if p not in SUFFIXES]
    return " ".join(parts).strip()


def main():
    print("Fetching players from Supabase...")
    existing = select("players", {"select": "id,full_name,position,sleeper_player_id"})
    print(f"Loaded {len(existing)} players from Supabase.")

    by_name = {}
    for p in existing:
        key = normalize(p.get("full_name"))
        if key:
            by_name.setdefault(key, []).append(p)

    print("Fetching Sleeper player directory...")
    resp = requests.get(SLEEPER_URL, timeout=60)
    resp.raise_for_status()
    sleeper_players = resp.json()
    print(f"Sleeper returned {len(sleeper_players)} players.")

    matched = 0
    skipped_ambiguous = 0
    for sleeper_id, sp in sleeper_players.items():
        full_name = sp.get("full_name") or f"{sp.get('first_name', '')} {sp.get('last_name', '')}".strip()
        key = normalize(full_name)
        if not key or key not in by_name:
            continue
        candidates = by_name[key]
        if len(candidates) > 1:
            position = sp.get("position")
            position_matches = [c for c in candidates if c.get("position") == position]
            if len(position_matches) == 1:
                candidates = position_matches
            else:
                skipped_ambiguous += 1
                continue
        target = candidates[0]
        body = {
            "sleeper_player_id": sleeper_id,
            "status_detail": sp.get("injury_status") or sp.get("status"),
        }
        patch("players", {"id": f"eq.{target['id']}"}, body)
        matched += 1

    print(f"Matched and patched {matched} players. Skipped {skipped_ambiguous} ambiguous name collisions.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"sleeper_sync failed: {exc}", file=sys.stderr)
        sys.exit(1)
