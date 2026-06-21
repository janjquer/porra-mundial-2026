import os
from datetime import datetime, timezone

import pandas as pd

from scraper import get_match_result, scrape_all

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _calc_points(pred_home, pred_away, real_home, real_away) -> int:
    if pred_home == real_home and pred_away == real_away:
        return 15
    pred_result = (pred_home > pred_away) - (pred_home < pred_away)  # 1, 0, -1
    real_result = (real_home > real_away) - (real_home < real_away)
    if pred_result == real_result:
        return max(0, 10 - abs(pred_home - real_home) - abs(pred_away - real_away))
    return 0


def run(resultats=None) -> pd.DataFrame:
    """
    Compute gent DataFrame with updated points.

    Priority logic per row:
      1. If 'punts' is already set in gent.csv → keep it as-is (manual override).
      2. If 'punts' is null AND the match has already started/finished → scrape and score.
      3. If 'punts' is null AND match is in the future → leave as null.
    """
    if resultats is None:
        resultats = scrape_all()

    # Read current gent.csv (source of truth for manual punts)
    gent_path = os.path.join(DATA_DIR, "gent.csv")
    gent = pd.read_csv(gent_path, parse_dates=["dia"])

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    def score_row(row):
        # 1. Manual override: punts already set → keep it
        if pd.notna(row["punts"]):
            return row["punts"]

        # 2. Match not yet started → don't score
        match_time = row["dia"]
        if pd.isna(match_time) or match_time > now:
            return None

        # 3. punts is null + match has started/finished → try scraping
        parts = row["partit"].split(" - ", 1)
        if len(parts) != 2:
            return None
        home_catalan, away_catalan = parts[0].strip(), parts[1].strip()
        result = get_match_result(home_catalan, away_catalan, resultats)
        if result is None:
            return None
        return _calc_points(
            int(row["local"]), int(row["visitant"]),
            result["home_score"], result["away_score"],
        )

    gent["punts"] = gent.apply(score_row, axis=1)

    # Recompute boolean columns from predictions (not from result)
    gent["victoria_local"] = gent["local"] > gent["visitant"]
    gent["victoria_visitant"] = gent["local"] < gent["visitant"]
    gent["empat"] = gent["local"] == gent["visitant"]

    cols = ["nom", "dia", "grup", "partit", "local", "visitant",
            "victoria_local", "victoria_visitant", "empat", "punts"]
    return gent[cols]


def save(df: pd.DataFrame):
    path = os.path.join(DATA_DIR, "gent.csv")
    df.to_csv(path, index=False)


def refresh():
    """Scrape latest scores and fill in missing points (respecting manual overrides)."""
    resultats = scrape_all()
    df = run(resultats)
    save(df)
    scored = df["punts"].notna().sum()
    print(f"[scoring] Updated {scored} predictions with scores.")
    return df


if __name__ == "__main__":
    df = refresh()
    summary = df.dropna(subset=["punts"]).groupby("nom")["punts"].sum().sort_values(ascending=False)
    print("\n--- Top 5 ---")
    print(summary.head())