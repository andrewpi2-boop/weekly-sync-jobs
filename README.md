# weekly-sync-jobs

Scheduled GitHub Actions jobs that pull player/team data from a handful of
free public sources and write it into a Supabase Postgres database. No
credentials are stored in this repo — everything below is a GitHub Actions
secret, read from the environment at runtime only.

## Jobs

| Workflow | Schedule | What it does |
|---|---|---|
| `nflverse-daily.yml` | daily | Player/roster crosswalk (canonical `gsis_id`) via `nfl_data_py` |
| `sleeper-sync.yml` | every 3h | Injury/status data, matched to existing players by name |
| `odds-sync.yml` | every 4h | Game spreads/totals (The Odds API, free tier) |
| `weather-sync.yml` | 2x/day | Game-day weather for outdoor stadiums (Open-Meteo) |
| `news-pipeline.yml` | every 15m | RSS ingestion + a small LLM extraction pass per new item |

## Required secrets

Set these under repo Settings → Secrets and variables → Actions:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `ODDS_API_KEY` (optional — odds job no-ops without it)
- `ANTHROPIC_API_KEY` (optional — signal extraction no-ops without it)

## Local run

```
pip install -r requirements.txt
export SUPABASE_URL=...
export SUPABASE_SERVICE_ROLE_KEY=...
python scripts/nflverse_sync.py
```

## Notes

- Every job is safe to no-op: missing optional secrets just skip that
  step and log why, rather than failing the whole workflow.
- `db.py` is a minimal PostgREST wrapper — no ORM, no Supabase SDK
  dependency, just `requests`.
- Not yet implemented: NFL.com official injury report ingestion, Reddit
  sentiment pull. Both are on the source list but don't have a clean
  free feed the way RotoWire/PFF do — worth revisiting.
