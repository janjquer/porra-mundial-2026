import os

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _calc_points(pred_home, pred_away, real_home, real_away) -> int:
    if pred_home == real_home and pred_away == real_away:
        return 15
    pred_result = (pred_home > pred_away) - (pred_home < pred_away)
    real_result = (real_home > real_away) - (real_home < real_away)
    if pred_result == real_result:
        return max(0, 10 - abs(pred_home - real_home) - abs(pred_away - real_away))
    return 0


def load_real() -> dict:
    """Load real.csv as {partit_name: {home_score, away_score}}."""
    path = os.path.join(DATA_DIR, "real.csv")
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    return {
        row["partit"]: {"home_score": int(row["local"]), "away_score": int(row["visitant"])}
        for _, row in df.iterrows()
    }


def save_real(results: dict):
    """Persist results dict back to real.csv."""
    rows = []
    for partit, r in results.items():
        h, a = r["home_score"], r["away_score"]
        rows.append({
            "partit": partit,
            "local": h,
            "visitant": a,
            "victoria_local": str(h > a).lower(),
            "victoria_visitant": str(h < a).lower(),
            "empat": str(h == a).lower(),
        })
    df = pd.DataFrame(rows, columns=["partit", "local", "visitant",
                                     "victoria_local", "victoria_visitant", "empat"])
    df.to_csv(os.path.join(DATA_DIR, "real.csv"), index=False)


def run(real=None) -> pd.DataFrame:
    """Compute gent DataFrame with updated points from real.csv."""
    if real is None:
        real = load_real()

    gent_path = os.path.join(DATA_DIR, "gent.csv")
    gent = pd.read_csv(gent_path, parse_dates=["dia"])

    def score_row(row):
        result = real.get(row["partit"])
        if result is None:
            return None
        return _calc_points(
            int(row["local"]), int(row["visitant"]),
            result["home_score"], result["away_score"],
        )

    gent["punts"] = gent.apply(score_row, axis=1)
    gent["victoria_local"] = gent["local"] > gent["visitant"]
    gent["victoria_visitant"] = gent["local"] < gent["visitant"]
    gent["empat"] = gent["local"] == gent["visitant"]

    cols = ["nom", "dia", "grup", "partit", "local", "visitant",
            "victoria_local", "victoria_visitant", "empat", "punts"]
    return gent[cols]


def save(df: pd.DataFrame):
    df.to_csv(os.path.join(DATA_DIR, "gent.csv"), index=False)


def refresh():
    df = run()
    save(df)
    scored = int(df["punts"].notna().sum())
    print(f"[scoring] Updated {scored} predictions with scores.")
    return df


if __name__ == "__main__":
    df = refresh()
    summary = df.dropna(subset=["punts"]).groupby("nom")["punts"].sum().sort_values(ascending=False)
    print("\n--- Top 5 ---")
    print(summary.head())
