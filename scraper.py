import json
import os
import requests
from datetime import date, timedelta
from typing import Optional

from team_names import catalan_to_espn

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
RESULTATS_FILE = os.path.join(DATA_DIR, "resultats.json")
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
HEADERS = {"User-Agent": "Mozilla/5.0"}

TOURNAMENT_START = date(2026, 6, 11)
TOURNAMENT_END = date(2026, 7, 19)


def _fetch_day(d: date) -> list[dict]:
    try:
        r = requests.get(ESPN_URL, params={"dates": d.strftime("%Y%m%d")}, headers=HEADERS, timeout=10)
        r.raise_for_status()
        events = r.json().get("events", [])
    except Exception as e:
        print(f"[scraper] Error fetching {d}: {e}")
        return []

    results = []
    for event in events:
        comp = event.get("competitions", [{}])[0]
        status = comp.get("status", {}).get("type", {}).get("name", "")
        if status not in ("STATUS_FULL_TIME", "STATUS_FULL_PEN", "STATUS_FT"):
            continue
        teams = comp.get("competitors", [])
        if len(teams) < 2:
            continue
        home = next((t for t in teams if t.get("homeAway") == "home"), teams[0])
        away = next((t for t in teams if t.get("homeAway") == "away"), teams[1])
        results.append({
            "home_espn": home["team"]["displayName"],
            "away_espn": away["team"]["displayName"],
            "home_score": int(home.get("score", 0)),
            "away_score": int(away.get("score", 0)),
            "date": d.isoformat(),
        })
    return results


def load_resultats() -> dict:
    if os.path.exists(RESULTATS_FILE):
        with open(RESULTATS_FILE) as f:
            return json.load(f)
    return {}


def save_resultats(data: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(RESULTATS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_match_key(home_espn: str, away_espn: str) -> str:
    return f"{home_espn}|{away_espn}"


def scrape_all() -> dict:
    """Fetch all completed matches since tournament start. Returns {match_key: result}."""
    existing = load_resultats()
    today = date.today()
    end = min(today, TOURNAMENT_END)
    d = TOURNAMENT_START
    new_count = 0
    while d <= end:
        day_results = _fetch_day(d)
        for r in day_results:
            key = build_match_key(r["home_espn"], r["away_espn"])
            if key not in existing:
                existing[key] = r
                new_count += 1
        d += timedelta(days=1)
    if new_count:
        save_resultats(existing)
        print(f"[scraper] Fetched {new_count} new results. Total: {len(existing)}")
    else:
        print(f"[scraper] No new results. Total cached: {len(existing)}")
    return existing


def get_match_result(home_catalan: str, away_catalan: str, resultats: dict) -> Optional[dict]:
    """Look up a match result by Catalan team names."""
    home_espn = catalan_to_espn(home_catalan)
    away_espn = catalan_to_espn(away_catalan)
    return resultats.get(build_match_key(home_espn, away_espn))


if __name__ == "__main__":
    results = scrape_all()
    for k, v in results.items():
        print(f"{v['home_espn']} {v['home_score']} - {v['away_score']} {v['away_espn']} ({v['date']})")
