import os
from datetime import datetime, timedelta, timezone

import pandas as pd
from flask import Flask, jsonify, render_template, request

from scoring import refresh, run
from scraper import load_resultats, scrape_all

app = Flask(__name__)
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# APScheduler — only start when running as a server, not during imports
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(refresh, "interval", minutes=10, id="auto_refresh")
    _scheduler.start()
except Exception:
    _scheduler = None


def _load_gent() -> pd.DataFrame:
    return pd.read_csv(os.path.join(DATA_DIR, "gent.csv"), parse_dates=["dia"])


def _load_partits() -> pd.DataFrame:
    return pd.read_csv(os.path.join(DATA_DIR, "partits.csv"), parse_dates=["dia"])


def _standings_at(df: pd.DataFrame, before: datetime) -> pd.DataFrame:
    subset = df[df["dia"] < before].dropna(subset=["punts"])
    return (
        subset.groupby("nom")["punts"]
        .sum()
        .reset_index()
        .rename(columns={"punts": "puntuacio"})
        .sort_values(["puntuacio", "nom"], ascending=[False, True])
        .assign(posicio=lambda x: range(1, len(x) + 1))
    )


# ── API ──────────────────────────────────────────────────────────────────────

@app.route("/api/standings")
def api_standings():
    df = _load_gent()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    yesterday = now - timedelta(hours=24)

    current = _standings_at(df, now + timedelta(days=1))
    old = _standings_at(df, yesterday)

    merged = current.merge(old[["nom", "posicio", "puntuacio"]], on="nom", suffixes=("", "_ahir"), how="left")
    merged["dif_pos"] = (merged["posicio_ahir"].fillna(merged["posicio"]) - merged["posicio"]).astype(int)
    merged["dif_punts"] = (merged["puntuacio"] - merged["puntuacio_ahir"].fillna(0)).astype(int)

    return jsonify(merged[["posicio", "nom", "puntuacio", "dif_pos", "dif_punts"]].to_dict(orient="records"))


@app.route("/api/daily")
def api_daily():
    df = _load_gent()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(hours=24)
    recent = df[df["dia"] > cutoff].dropna(subset=["punts"])
    if recent.empty:
        return jsonify([])
    result = (
        recent.groupby("nom")["punts"]
        .sum()
        .reset_index()
        .rename(columns={"punts": "puntuacio"})
        .sort_values(["puntuacio", "nom"], ascending=[False, True])
        .assign(posicio=lambda x: range(1, len(x) + 1))
    )
    return jsonify(result.to_dict(orient="records"))


@app.route("/api/match/<int:n_partit>")
def api_match(n_partit):
    df = _load_gent()
    partits = _load_partits()
    match_row = partits[partits["n_partit"] == n_partit]
    if match_row.empty:
        return jsonify({"error": "Match not found"}), 404
    partit_name = match_row.iloc[0]["partit"]
    preds = df[df["partit"] == partit_name].copy()
    preds["local"] = preds["local"].astype(int)
    preds["visitant"] = preds["visitant"].astype(int)
    preds["resultat"] = preds["local"].astype(str) + "-" + preds["visitant"].astype(str)

    # Aggregate predictions
    agg = (
        preds.groupby("resultat")
        .agg(n=("nom", "count"), punts=("punts", "first"))
        .reset_index()
        .sort_values("n", ascending=False)
    )
    return jsonify({
        "partit": partit_name,
        "predictions": agg.to_dict(orient="records"),
    })


@app.route("/api/matches")
def api_matches():
    partits = _load_partits()
    gent = _load_gent()
    resultats = load_resultats()
    from team_names import catalan_to_espn
    from scraper import build_match_key

    rows = []
    for _, row in partits.iterrows():
        parts = row["partit"].split(" - ", 1)
        home, away = parts[0].strip(), parts[1].strip()
        key = build_match_key(catalan_to_espn(home), catalan_to_espn(away))
        result = resultats.get(key)
        match_gent = gent[gent["partit"] == row["partit"]]
        clavats = int((match_gent["punts"] == 15).sum())
        rows.append({
            "n_partit": int(row["n_partit"]),
            "dia": row["dia"].isoformat() if hasattr(row["dia"], "isoformat") else str(row["dia"]),
            "grup": row["grup"],
            "partit": row["partit"],
            "resultat": f"{result['home_score']}-{result['away_score']}" if result else None,
            "clavats": clavats,
        })
    return jsonify(rows)


@app.route("/api/clavats")
def api_clavats():
    df = _load_gent()
    clavats = (
        df[df["punts"] == 15]
        .groupby("nom")
        .agg(clavats=("punts", "count"), primer=("dia", "min"), ultim=("dia", "max"))
        .reset_index()
        .sort_values("clavats", ascending=False)
    )
    clavats["primer"] = clavats["primer"].astype(str)
    clavats["ultim"] = clavats["ultim"].astype(str)
    return jsonify(clavats.to_dict(orient="records"))


@app.route("/api/match-clavats")
def api_match_clavats():
    df = _load_gent()
    mc = (
        df[df["punts"] == 15]
        .groupby("partit")
        .agg(clavats=("punts", "count"), dia=("dia", "min"))
        .reset_index()
        .sort_values("clavats", ascending=False)
    )
    mc["dia"] = mc["dia"].astype(str)
    return jsonify(mc.to_dict(orient="records"))


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    token = request.headers.get("X-Token", "")
    if token != os.environ.get("REFRESH_TOKEN", "porra2026"):
        return jsonify({"error": "unauthorized"}), 401
    df = refresh()
    scored = int(df["punts"].notna().sum())
    return jsonify({"ok": True, "scored": scored})


@app.route("/api/last-update")
def api_last_update():
    resultats = load_resultats()
    if not resultats:
        return jsonify({"last_update": None, "n_matches": 0})
    dates = [v["date"] for v in resultats.values()]
    return jsonify({"last_update": max(dates), "n_matches": len(resultats)})


# ── Frontend ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    partits = _load_partits()
    grups = sorted(partits["grup"].unique())
    return render_template("index.html", grups=grups, partits=partits.to_dict(orient="records"))


if __name__ == "__main__":
    app.run(debug=True)
