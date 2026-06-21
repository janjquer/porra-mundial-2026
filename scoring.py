import os
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
    """Compute gent DataFrame with updated points. Optionally pass pre-loaded resultats."""
    if resultats is None:
        resultats = scrape_all()

    partits = pd.read_csv(os.path.join(DATA_DIR, "partits.csv"))
    pronostics = pd.read_csv(os.path.join(DATA_DIR, "pronostics.csv"))

    # Join pronostics with match info
    gent = pronostics.merge(partits, on="n_partit")

    # Parse home/away from 'partit' column (format: "TeamA - TeamB")
    split = gent["partit"].str.split(" - ", n=1, expand=True)
    gent["home_team"] = split[0].str.strip()
    gent["away_team"] = split[1].str.strip()

    # Calculate points for each prediction
    def score_row(row):
        result = get_match_result(row["home_team"], row["away_team"], resultats)
        if result is None:
            return None
        return _calc_points(
            int(row["local"]), int(row["visitant"]),
            result["home_score"], result["away_score"],
        )

    gent["punts"] = gent.apply(score_row, axis=1)

    # Add derived boolean columns
    gent["victoria_local"] = gent["local"] > gent["visitant"]
    gent["victoria_visitant"] = gent["local"] < gent["visitant"]
    gent["empat"] = gent["local"] == gent["visitant"]

    # Reorder to match original gent.csv schema
    cols = ["nom", "dia", "grup", "partit", "local", "visitant",
            "victoria_local", "victoria_visitant", "empat", "punts"]
    return gent[cols]


def save(df: pd.DataFrame):
    path = os.path.join(DATA_DIR, "gent.csv")
    df.to_csv(path, index=False)


def refresh():
    """Scrape latest scores and recompute all points."""
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
