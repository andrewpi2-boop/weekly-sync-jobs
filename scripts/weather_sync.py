"""Pull game-day stadium weather from Open-Meteo (free, no auth - PRD
Section 8) for outdoor NFL stadiums, and stash it as a standalone
projections row so it can be joined to a player's team/game downstream.

Static outdoor-stadium coordinate table below covers the outdoor/retractable
venues where weather actually matters; domes are skipped entirely.
"""
import datetime
import sys

import requests

from db import insert

# Outdoor (or retractable-roof, treated as outdoor for cron simplicity) NFL stadiums.
# lat/lon are approximate stadium locations.
STADIUMS = {
    "BUF": (42.7738, -78.7870), "MIA": (25.9580, -80.2389), "NE": (42.0909, -71.2643),
    "NYJ": (40.8135, -74.0745), "BAL": (39.2780, -76.6227), "CIN": (39.0954, -84.5160),
    "CLE": (41.5061, -81.6995), "PIT": (40.4468, -80.0158), "DEN": (39.7439, -105.0201),
    "KC": (39.0489, -94.4839), "LAC": (33.9535, -118.3392), "CHI": (41.8623, -87.6167),
    "GB": (44.5013, -88.0622), "SF": (37.4030, -121.9700), "SEA": (47.5952, -122.3316),
    "TB": (27.9759, -82.5033), "CAR": (35.2258, -80.8528), "WAS": (38.9078, -76.8645),
    "PHI": (39.9008, -75.1675), "NYG": (40.8135, -74.0745), "TEN": (36.1665, -86.7713),
    "JAX": (30.3239, -81.6373), "NO": (29.9509, -90.0815),
}


def sync():
    now = datetime.datetime.utcnow().isoformat()
    rows = []
    for team, (lat, lon) in STADIUMS.items():
        try:
            resp = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "hourly": "temperature_2m,precipitation_probability,wind_speed_10m",
                    "forecast_days": 7,
                    "temperature_unit": "fahrenheit",
                    "wind_speed_unit": "mph",
                },
                timeout=20,
            )
            resp.raise_for_status()
            rows.append({
                "player_id": None,
                "season": datetime.date.today().year,
                "week": None,
                "source": "open_meteo",
                "weather_json": {"team": team, **resp.json()},
                "created_at": now,
            })
        except Exception as e:
            print(f"Weather pull failed for {team}: {e}", file=sys.stderr)

    print(f"Storing weather snapshots for {len(rows)} outdoor stadiums...")
    insert("projections", rows)
    print("Done.")


if __name__ == "__main__":
    try:
        sync()
    except Exception as e:
        print(f"weather_sync failed: {e}", file=sys.stderr)
        sys.exit(1)
