"""Pull the current-season player/roster crosswalk and basic weekly stats
from nflverse (via nfl_data_py) and upsert into `players` / `projections`.

Free, no auth required. This is the anchor source for the player ID
crosswalk (gsis_id) that other sources join against.
"""
import datetime
import sys

import nfl_data_py as nfl

from db import upsert

SEASON = datetime.date.today().year
# NFL season effectively starts in September; before that, pull the prior
# season's roster as the closest available crosswalk.
if datetime.date.today().month < 8:
    SEASON -= 1


def sync_players():
    rosters = nfl.import_seasonal_rosters([SEASON])
    if rosters.empty:
        print(f"No roster data yet for {SEASON}, nothing to sync.")
        return

    rosters = rosters[rosters["position"].isin(["QB", "RB", "WR", "TE", "DST", "DEF", "K"])]

    rows = []
    for _, r in rosters.iterrows():
        pos = r.get("position") or ""
        if pos == "DEF":
            pos = "DST"
        rows.append({
            "full_name": r.get("player_name") or r.get("football_name") or "",
            "position": pos,
            "nfl_team": r.get("team"),
            "gsis_id": r.get("player_id"),
            "status": "active",
            "last_synced_at": datetime.datetime.utcnow().isoformat(),
        })

    # de-dupe by gsis_id, keep last occurrence (most recent week's row)
    dedup = {}
    for row in rows:
        if row["gsis_id"]:
            dedup[row["gsis_id"]] = row
    rows = list(dedup.values())

    print(f"Upserting {len(rows)} players from nflverse ({SEASON} season)...")
    upsert("players", rows, on_conflict="gsis_id")
    print("Done.")


if __name__ == "__main__":
    try:
        sync_players()
    except Exception as e:
        print(f"nflverse_sync failed: {e}", file=sys.stderr)
        sys.exit(1)
