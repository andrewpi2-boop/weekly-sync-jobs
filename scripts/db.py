"""Tiny Supabase REST (PostgREST) helper. No SDK dependency, just requests.

Reads SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from the environment
(set as GitHub Actions secrets, never committed).
"""
import os
import sys
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SERVICE_KEY:
    print("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY env vars.", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}


def upsert(table, rows, on_conflict=None):
    """Upsert a list of row dicts into `table`. Returns the response JSON."""
    if not rows:
        return []
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = dict(HEADERS)
    prefer = "resolution=merge-duplicates,return=representation"
    headers["Prefer"] = prefer
    params = {}
    if on_conflict:
        params["on_conflict"] = on_conflict
    resp = requests.post(url, headers=headers, params=params, json=rows, timeout=30)
    if not resp.ok:
        print(f"Upsert into {table} failed: {resp.status_code} {resp.text[:500]}", file=sys.stderr)
        resp.raise_for_status()
    return resp.json()


def select(table, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    resp = requests.get(url, headers=HEADERS, params=params or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def insert(table, rows):
    if not rows:
        return []
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = dict(HEADERS)
    headers["Prefer"] = "return=representation"
    resp = requests.post(url, headers=headers, json=rows, timeout=30)
    if not resp.ok:
        print(f"Insert into {table} failed: {resp.status_code} {resp.text[:500]}", file=sys.stderr)
        resp.raise_for_status()
    return resp.json()


def patch(table, params, body):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = dict(HEADERS)
    headers["Prefer"] = "return=representation"
    resp = requests.patch(url, headers=headers, params=params, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()
